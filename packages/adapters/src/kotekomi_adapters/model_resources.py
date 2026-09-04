"""Managed local installations for specialized-model Adapters."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Protocol, cast

from kotekomi_application import (
    ModelResourceId,
    ModelResourceInstallDisposition,
    ModelResourceInstallResult,
    ModelResourceReadiness,
    ModelResourceStatus,
)

from .refined_entity_linking import (
    REFINED_PACKAGE_REVISION,
    REFINED_RESOURCE_MANIFEST_SHA256,
)

GLINER_DIRECTORY = ModelResourceId.GLINER_MENTION_PROPOSER_V1.value
REFINED_DIRECTORY = ModelResourceId.REFINED_WIKIPEDIA_V1.value
GLINER_MANIFEST_SCHEMA = "gliner_resource_installation_v1"
REFINED_MANIFEST_SCHEMA = "refined_resource_installation_v1"
REFINED_PYTHON_VERSION = "3.10"
REFINED_PACKAGE_VERSION = "1.0"

type _CommandRunner = Callable[[tuple[str, ...]], None]
type _GlinerSmoke = Callable[[Path], None]
type _RuntimeProbe = Callable[[Path], tuple[str, str]]


class _SnapshotDownloader(Protocol):
    def __call__(
        self,
        *,
        repo_id: str,
        revision: str,
        allow_patterns: list[str],
        local_files_only: bool,
    ) -> str: ...


class _GlinerSmokeModel(Protocol):
    def predict_entities(
        self,
        text: str,
        labels: list[str],
        *,
        threshold: float,
    ) -> list[dict[str, object]]: ...


class ModelResourceInstallationError(RuntimeError):
    """An explicit resource installation could not publish a ready result."""


@dataclass(frozen=True)
class _GlinerFileLock:
    repository: str
    revision: str
    source_path: str
    target_path: str
    sha256: str


@dataclass(frozen=True)
class _GlinerLock:
    package_version: str
    files: tuple[_GlinerFileLock, ...]
    identity: str


class _Installer(Protocol):
    resource_id: ModelResourceId

    def inspect(self, resource_root: Path) -> ModelResourceReadiness: ...

    def install_staged(self, staged: Path) -> None: ...


class GlinerModelResourceAdapter:
    resource_id = ModelResourceId.GLINER_MENTION_PROPOSER_V1

    def __init__(
        self,
        *,
        downloader: _SnapshotDownloader | None = None,
        smoke: _GlinerSmoke | None = None,
        lock_path: Path | None = None,
    ) -> None:
        self._lock = _load_gliner_lock(lock_path)
        self._downloader = downloader or _snapshot_download
        self._smoke = smoke or _smoke_gliner

    def inspect(self, resource_root: Path) -> ModelResourceReadiness:
        installation = gliner_installation_path(resource_root)
        try:
            package_version = version("gliner")
        except PackageNotFoundError:
            return _not_ready(
                self.resource_id,
                installation,
                self._lock.identity,
                ModelResourceStatus.INCOMPLETE,
                "The pinned GLiNER package is unavailable.",
            )
        if package_version != self._lock.package_version:
            return _not_ready(
                self.resource_id,
                installation,
                self._lock.identity,
                ModelResourceStatus.IDENTITY_MISMATCH,
                f"GLiNER package version differs: {package_version}.",
                package_version,
            )
        manifest = _load_manifest(installation / "manifest.json")
        if manifest is None:
            status = (
                ModelResourceStatus.INCOMPLETE
                if installation.exists()
                else ModelResourceStatus.MISSING
            )
            return _not_ready(
                self.resource_id,
                installation,
                self._lock.identity,
                status,
                "GLiNER Resource Installation manifest is unavailable.",
            )
        observed = _manifest_identity(manifest)
        if (
            manifest.get("schema_version") != GLINER_MANIFEST_SCHEMA
            or manifest.get("resource_id") != self.resource_id.value
            or observed != self._lock.identity
            or manifest.get("package_version") != self._lock.package_version
            or manifest.get("files") != _gliner_file_manifest(self._lock)
            or manifest.get("smoke_status") != "passed"
        ):
            return _not_ready(
                self.resource_id,
                installation,
                self._lock.identity,
                ModelResourceStatus.IDENTITY_MISMATCH,
                "GLiNER Resource Installation manifest does not match the pinned lock.",
                observed,
            )
        model_dir = installation / "model"
        for item in self._lock.files:
            path = model_dir / item.target_path
            if not path.is_file():
                return _not_ready(
                    self.resource_id,
                    installation,
                    self._lock.identity,
                    ModelResourceStatus.INCOMPLETE,
                    f"GLiNER required file is unavailable: {item.target_path}.",
                    observed,
                )
            if _file_digest(path) != item.sha256:
                return _not_ready(
                    self.resource_id,
                    installation,
                    self._lock.identity,
                    ModelResourceStatus.IDENTITY_MISMATCH,
                    f"GLiNER required file digest differs: {item.target_path}.",
                    observed,
                )
        return _ready(self.resource_id, installation, self._lock.identity)

    def install(
        self,
        resource_root: Path,
        *,
        repair: bool,
    ) -> ModelResourceInstallResult:
        return _install(self, resource_root, repair=repair)

    def install_staged(self, staged: Path) -> None:
        model_dir = staged / "model"
        model_dir.mkdir(parents=True)
        grouped: dict[tuple[str, str], list[_GlinerFileLock]] = {}
        for item in self._lock.files:
            grouped.setdefault((item.repository, item.revision), []).append(item)
        for (repository, revision), items in grouped.items():
            snapshot = Path(
                self._downloader(
                    repo_id=repository,
                    revision=revision,
                    allow_patterns=[item.source_path for item in items],
                    local_files_only=False,
                )
            )
            for item in items:
                _link_or_copy(snapshot / item.source_path, model_dir / item.target_path)
        for item in self._lock.files:
            if _file_digest(model_dir / item.target_path) != item.sha256:
                raise ModelResourceInstallationError(
                    f"Downloaded GLiNER file failed its pinned digest: {item.target_path}."
                )
        self._smoke(model_dir)
        _write_manifest(
            staged / "manifest.json",
            {
                "schema_version": GLINER_MANIFEST_SCHEMA,
                "resource_id": self.resource_id.value,
                "identity": self._lock.identity,
                "package_version": self._lock.package_version,
                "files": _gliner_file_manifest(self._lock),
                "smoke_status": "passed",
            },
        )


class RefinedModelResourceAdapter:
    resource_id = ModelResourceId.REFINED_WIKIPEDIA_V1

    def __init__(
        self,
        *,
        command_runner: _CommandRunner | None = None,
        checkout_root: Path | None = None,
        expected_resource_digest: str = REFINED_RESOURCE_MANIFEST_SHA256,
        tree_digest: Callable[[Path], str] | None = None,
        runtime_probe: _RuntimeProbe | None = None,
    ) -> None:
        self._checkout_root = checkout_root or Path(__file__).resolve().parents[4]
        self._runner = command_runner or _run_command
        self._requirements = self._checkout_root / "tools" / "refined-worker" / "requirements.txt"
        self._resource_lock = (
            self._checkout_root / "tools" / "refined-worker" / "resource-lock.json"
        )
        self._resource_lock_payload = cast(
            dict[str, object],
            json.loads(self._resource_lock.read_text(encoding="utf-8")),
        )
        self._identity = _refined_identity(self._requirements, self._resource_lock)
        self._expected_resource_digest = expected_resource_digest
        self._tree_digest = tree_digest or _tree_digest
        self._runtime_probe = runtime_probe or _probe_refined_runtime

    def inspect(self, resource_root: Path) -> ModelResourceReadiness:
        installation = refined_installation_path(resource_root)
        manifest = _load_manifest(installation / "manifest.json")
        if manifest is None:
            status = (
                ModelResourceStatus.INCOMPLETE
                if installation.exists()
                else ModelResourceStatus.MISSING
            )
            return _not_ready(
                self.resource_id,
                installation,
                self._identity,
                status,
                "ReFinED Resource Installation manifest is unavailable.",
            )
        observed = _manifest_identity(manifest)
        if (
            manifest.get("schema_version") != REFINED_MANIFEST_SCHEMA
            or manifest.get("resource_id") != self.resource_id.value
            or observed != self._identity
            or manifest.get("package_revision") != REFINED_PACKAGE_REVISION
            or manifest.get("python_version") != REFINED_PYTHON_VERSION
            or manifest.get("requirements_sha256") != _file_digest(self._requirements)
            or manifest.get("resource_manifest_sha256") != self._expected_resource_digest
            or manifest.get("smoke_status") != "passed"
        ):
            return _not_ready(
                self.resource_id,
                installation,
                self._identity,
                ModelResourceStatus.IDENTITY_MISMATCH,
                "ReFinED Resource Installation manifest does not match the pinned lock.",
                observed,
            )
        if not refined_python_path(resource_root).is_file():
            return _not_ready(
                self.resource_id,
                installation,
                self._identity,
                ModelResourceStatus.INCOMPLETE,
                "ReFinED managed Python executable is unavailable.",
                observed,
            )
        try:
            python_version, package_version = self._runtime_probe(
                refined_python_path(resource_root)
            )
        except (OSError, RuntimeError) as error:
            return _not_ready(
                self.resource_id,
                installation,
                self._identity,
                ModelResourceStatus.INCOMPLETE,
                f"ReFinED managed runtime is unavailable: {error}",
                observed,
            )
        if not python_version.startswith(f"{REFINED_PYTHON_VERSION}.") or (
            package_version != REFINED_PACKAGE_VERSION
        ):
            return _not_ready(
                self.resource_id,
                installation,
                self._identity,
                ModelResourceStatus.IDENTITY_MISMATCH,
                "ReFinED managed Python or package version differs from the pinned lock.",
                observed,
            )
        data_dir = refined_data_path(resource_root)
        if not data_dir.is_dir():
            return _not_ready(
                self.resource_id,
                installation,
                self._identity,
                ModelResourceStatus.INCOMPLETE,
                "ReFinED model resource directory is unavailable.",
                observed,
            )
        if self._tree_digest(data_dir) != self._expected_resource_digest:
            return _not_ready(
                self.resource_id,
                installation,
                self._identity,
                ModelResourceStatus.IDENTITY_MISMATCH,
                "ReFinED model resource digest differs from the pinned lock.",
                observed,
            )
        return _ready(self.resource_id, installation, self._identity)

    def install(
        self,
        resource_root: Path,
        *,
        repair: bool,
    ) -> ModelResourceInstallResult:
        return _install(self, resource_root, repair=repair)

    def install_staged(self, staged: Path) -> None:
        runtime = staged / "runtime"
        data_dir = staged / "data"
        setup_manifest = staged / "setup-manifest.json"
        python = _venv_python(runtime)
        setup_script = self._checkout_root / "scripts" / "setup_refined_organization_type_worker.py"
        self._runner(("uv", "venv", "--python", REFINED_PYTHON_VERSION, str(runtime)))
        self._runner(
            (
                "uv",
                "pip",
                "sync",
                "--python",
                str(python),
                "--strict",
                str(self._requirements),
            )
        )
        self._runner(
            (
                str(python),
                str(setup_script),
                "--data-dir",
                str(data_dir),
                "--manifest",
                str(setup_manifest),
            )
        )
        setup = _load_manifest(setup_manifest)
        locked_fields = (
            "package_version",
            "package_revision",
            "model_id",
            "model_revision",
            "entity_set",
            "smoke_spans",
        )
        if (
            setup is None
            or setup.get("resource_manifest_sha256") != self._expected_resource_digest
            or any(
                setup.get(field) != self._resource_lock_payload.get(field)
                for field in locked_fields
            )
        ):
            raise ModelResourceInstallationError(
                "ReFinED setup did not produce the pinned resource manifest."
            )
        setup_manifest.unlink()
        _write_manifest(
            staged / "manifest.json",
            {
                "schema_version": REFINED_MANIFEST_SCHEMA,
                "resource_id": self.resource_id.value,
                "identity": self._identity,
                "package_revision": REFINED_PACKAGE_REVISION,
                "python_version": REFINED_PYTHON_VERSION,
                "requirements_sha256": _file_digest(self._requirements),
                "resource_manifest_sha256": self._expected_resource_digest,
                "smoke_status": "passed",
            },
        )


def gliner_installation_path(resource_root: Path) -> Path:
    return resource_root / GLINER_DIRECTORY


def gliner_model_path(resource_root: Path) -> Path:
    return gliner_installation_path(resource_root) / "model"


def gliner_expected_resource_identity() -> str:
    return _load_gliner_lock().identity


def refined_installation_path(resource_root: Path) -> Path:
    return resource_root / REFINED_DIRECTORY


def refined_python_path(resource_root: Path) -> Path:
    return _venv_python(refined_installation_path(resource_root) / "runtime")


def refined_data_path(resource_root: Path) -> Path:
    return refined_installation_path(resource_root) / "data"


def _install(
    adapter: _Installer,
    resource_root: Path,
    *,
    repair: bool,
) -> ModelResourceInstallResult:
    resource_root = resource_root.resolve()
    current = adapter.inspect(resource_root)
    if current.ready:
        return ModelResourceInstallResult(ModelResourceInstallDisposition.REUSED, current)
    target = current.root
    if target.exists() and not repair:
        raise ModelResourceInstallationError(
            f"{adapter.resource_id.value} has an invalid installation. "
            "Run the install command again with --repair."
        )
    resource_root.mkdir(parents=True, exist_ok=True)
    staged = Path(tempfile.mkdtemp(prefix=f".{adapter.resource_id.value}-", dir=resource_root))
    backup = resource_root / f".{adapter.resource_id.value}-invalid"
    published = False
    try:
        adapter.install_staged(staged)
        if target.exists():
            if backup.exists():
                shutil.rmtree(backup)
            target.rename(backup)
        staged.rename(target)
        published = True
        final = adapter.inspect(resource_root)
        if not final.ready:
            raise ModelResourceInstallationError(
                f"Published {adapter.resource_id.value} installation failed validation."
            )
        if backup.exists():
            shutil.rmtree(backup)
        disposition = (
            ModelResourceInstallDisposition.REPAIRED
            if repair and current.status is not ModelResourceStatus.MISSING
            else ModelResourceInstallDisposition.INSTALLED
        )
        return ModelResourceInstallResult(disposition, final)
    except BaseException:
        if published and target.exists():
            shutil.rmtree(target)
        if backup.exists():
            backup.rename(target)
        raise
    finally:
        if staged.exists():
            shutil.rmtree(staged)


def _load_gliner_lock(lock_path: Path | None = None) -> _GlinerLock:
    path = lock_path or Path(__file__).with_name("gliner-model-lock.json")
    payload = cast(dict[str, object], json.loads(path.read_text(encoding="utf-8")))
    raw_files = cast(list[dict[str, object]], payload["files"])
    files = tuple(
        _GlinerFileLock(
            repository=str(item["repository"]),
            revision=str(item["revision"]),
            source_path=str(item["source_path"]),
            target_path=str(item["target_path"]),
            sha256=str(item["sha256"]),
        )
        for item in raw_files
    )
    identity = hashlib.sha256(_canonical_json(payload)).hexdigest()
    return _GlinerLock(str(payload["package_version"]), files, identity)


def _gliner_file_manifest(lock: _GlinerLock) -> list[dict[str, str]]:
    return [
        {
            "repository": item.repository,
            "revision": item.revision,
            "path": item.target_path,
            "sha256": item.sha256,
        }
        for item in lock.files
    ]


def _refined_identity(requirements: Path, resource_lock: Path) -> str:
    digest = hashlib.sha256()
    digest.update(requirements.read_bytes())
    digest.update(b"\0")
    digest.update(resource_lock.read_bytes())
    return digest.hexdigest()


def _load_manifest(path: Path) -> dict[str, object] | None:
    try:
        value: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return cast(dict[str, object], value) if isinstance(value, dict) else None


def _manifest_identity(manifest: dict[str, object]) -> str | None:
    value = manifest.get("identity")
    return value if isinstance(value, str) else None


def _write_manifest(path: Path, value: dict[str, object]) -> None:
    path.write_bytes(_canonical_json(value) + b"\n")


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def _file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _tree_digest(root: Path) -> str:
    files = tuple(sorted(path for path in root.rglob("*") if path.is_file()))
    digest = hashlib.sha256()
    for path in files:
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(str(path.stat().st_size).encode("ascii"))
        digest.update(b"\0")
        digest.update(_file_digest(path).encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def _ready(
    resource_id: ModelResourceId,
    installation: Path,
    identity: str,
) -> ModelResourceReadiness:
    return ModelResourceReadiness(
        resource_id=resource_id,
        status=ModelResourceStatus.READY,
        root=installation.resolve(),
        expected_identity=identity,
        observed_identity=identity,
        diagnostics=(),
    )


def _not_ready(
    resource_id: ModelResourceId,
    installation: Path,
    expected_identity: str,
    status: ModelResourceStatus,
    diagnostic: str,
    observed_identity: str | None = None,
) -> ModelResourceReadiness:
    return ModelResourceReadiness(
        resource_id=resource_id,
        status=status,
        root=installation.resolve(),
        expected_identity=expected_identity,
        observed_identity=observed_identity,
        diagnostics=(diagnostic,),
    )


def _snapshot_download(
    *,
    repo_id: str,
    revision: str,
    allow_patterns: list[str],
    local_files_only: bool,
) -> str:
    from huggingface_hub import snapshot_download  # pyright: ignore[reportUnknownVariableType]

    result = snapshot_download(
        repo_id=repo_id,
        revision=revision,
        allow_patterns=allow_patterns,
        local_files_only=local_files_only,
    )
    return result


def _link_or_copy(source: Path, target: Path) -> None:
    resolved_source = source.resolve(strict=True)
    try:
        os.link(resolved_source, target)
    except OSError:
        shutil.copyfile(resolved_source, target)


def _smoke_gliner(model_dir: Path) -> None:
    from gliner import GLiNER  # pyright: ignore[reportMissingTypeStubs]

    loader = cast(
        Callable[..., object],
        GLiNER.from_pretrained,  # pyright: ignore[reportUnknownMemberType]
    )
    model = cast(
        _GlinerSmokeModel,
        loader(str(model_dir), map_location="cpu", local_files_only=True),
    )
    model.predict_entities("Anthropic announced an update.", ["organization"], threshold=0.5)


def _run_command(command: tuple[str, ...]) -> None:
    try:
        result = subprocess.run(command, check=False)
    except OSError as error:
        raise ModelResourceInstallationError(f"Unable to run {command[0]}: {error}") from error
    if result.returncode != 0:
        raise ModelResourceInstallationError(
            f"Model Resource setup command failed with exit {result.returncode}: {command[0]}."
        )


def _probe_refined_runtime(python: Path) -> tuple[str, str]:
    probe = (
        "import importlib.metadata, platform; "
        "print(platform.python_version()); "
        "print(importlib.metadata.version('ReFinED'))"
    )
    result = subprocess.run(
        (str(python), "-c", probe),
        check=False,
        capture_output=True,
        text=True,
    )
    lines = result.stdout.splitlines()
    if result.returncode != 0 or len(lines) != 2 or any(not line for line in lines):
        raise RuntimeError("version probe failed")
    return lines[0], lines[1]


def _venv_python(runtime: Path) -> Path:
    if os.name == "nt":
        return runtime / "Scripts" / "python.exe"
    return runtime / "bin" / "python"
