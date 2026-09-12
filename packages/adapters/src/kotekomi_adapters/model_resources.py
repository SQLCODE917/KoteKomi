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

import httpx
from kotekomi_application import (
    CoreferenceInput,
    LinguisticAnalysis,
    LinguisticAnalysisInput,
    ModelResourceId,
    ModelResourceInstallDisposition,
    ModelResourceInstallResult,
    ModelResourceReadiness,
    ModelResourceStatus,
    NaturalLanguageInferenceInput,
    NominalizationAnalysisInput,
)

from .refined_entity_linking import (
    REFINED_PACKAGE_REVISION,
    REFINED_RESOURCE_MANIFEST_SHA256,
)

GLINER_DIRECTORY = ModelResourceId.GLINER_MENTION_PROPOSER_V1.value
NLI_DIRECTORY = ModelResourceId.NLI_DEBERTA_V3_BASE_V1.value
REFINED_DIRECTORY = ModelResourceId.REFINED_WIKIPEDIA_V1.value
FCOREF_DIRECTORY = ModelResourceId.FCOREF_V1.value
STANZA_DIRECTORY = ModelResourceId.STANZA_ENGLISH_V1.value
QANOM_DIRECTORY = ModelResourceId.QANOM_NOMINALIZATION_V1.value
GLINER_MANIFEST_SCHEMA = "gliner_resource_installation_v1"
NLI_MANIFEST_SCHEMA = "nli_deberta_resource_installation_v1"
REFINED_MANIFEST_SCHEMA = "refined_resource_installation_v1"
FCOREF_MANIFEST_SCHEMA = "fcoref_resource_installation_v1"
STANZA_MANIFEST_SCHEMA = "stanza_resource_installation_v1"
QANOM_MANIFEST_SCHEMA = "qanom_resource_installation_v1"
REFINED_PYTHON_VERSION = "3.10"
REFINED_PACKAGE_VERSION = "1.0"
FCOREF_PYTHON_VERSION = "3.12"
FCOREF_PACKAGE_VERSION = "2.2.3"

type _CommandRunner = Callable[[tuple[str, ...]], None]
type _GlinerSmoke = Callable[[Path], None]
type _NliSmoke = Callable[[Path, str], None]
type _FCorefSmoke = Callable[[Path, Path, Path, str], None]
type _StanzaSmoke = Callable[[Path, str], None]
type _QANomSmoke = Callable[[Path, Path, str], None]
type _RuntimeProbe = Callable[[Path], tuple[str, str]]
type _FileDownloader = Callable[[str, Path], None]


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


@dataclass(frozen=True)
class _NliLock:
    transformers_version: str
    files: tuple[_GlinerFileLock, ...]
    identity: str


@dataclass(frozen=True)
class _FCorefLock:
    model_id: str
    model_revision: str
    package_revision: str
    files: tuple[_GlinerFileLock, ...]
    identity: str


@dataclass(frozen=True)
class _RemoteFileLock:
    download_url: str
    target_path: str
    sha256: str


@dataclass(frozen=True)
class _StanzaLock:
    package_version: str
    resources_json_url: str
    resources_json_sha256: str
    files: tuple[_GlinerFileLock, ...]
    identity: str


@dataclass(frozen=True)
class _QANomLock:
    transformers_version: str
    files: tuple[_GlinerFileLock, ...]
    lexical_files: tuple[_RemoteFileLock, ...]
    identity: str


class _Installer(Protocol):
    resource_id: ModelResourceId

    def inspect(self, resource_root: Path) -> ModelResourceReadiness: ...

    def install_staged(self, staged: Path, reusable_installation: Path | None) -> None: ...


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

    def install_staged(self, staged: Path, reusable_installation: Path | None) -> None:
        del reusable_installation
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


class NliDebertaModelResourceAdapter:
    """Install and inspect the pinned local-only NLI model."""

    resource_id = ModelResourceId.NLI_DEBERTA_V3_BASE_V1

    def __init__(
        self,
        *,
        downloader: _SnapshotDownloader | None = None,
        smoke: _NliSmoke | None = None,
        lock_path: Path | None = None,
    ) -> None:
        self._lock = _load_nli_lock(lock_path)
        self._downloader = downloader or _snapshot_download
        self._smoke = smoke or _smoke_nli

    def inspect(self, resource_root: Path) -> ModelResourceReadiness:
        installation = nli_installation_path(resource_root)
        try:
            package_version = version("transformers")
        except PackageNotFoundError:
            return _not_ready(
                self.resource_id,
                installation,
                self._lock.identity,
                ModelResourceStatus.INCOMPLETE,
                "The pinned Transformers package is unavailable.",
            )
        if package_version != self._lock.transformers_version:
            return _not_ready(
                self.resource_id,
                installation,
                self._lock.identity,
                ModelResourceStatus.IDENTITY_MISMATCH,
                f"Transformers package version differs: {package_version}.",
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
                "NLI Resource Installation manifest is unavailable.",
            )
        observed = _manifest_identity(manifest)
        if (
            manifest.get("schema_version") != NLI_MANIFEST_SCHEMA
            or manifest.get("resource_id") != self.resource_id.value
            or observed != self._lock.identity
            or manifest.get("transformers_version") != self._lock.transformers_version
            or manifest.get("files") != _nli_file_manifest(self._lock)
            or manifest.get("smoke_status") != "passed"
        ):
            return _not_ready(
                self.resource_id,
                installation,
                self._lock.identity,
                ModelResourceStatus.IDENTITY_MISMATCH,
                "NLI Resource Installation manifest does not match the pinned lock.",
                observed,
            )
        model_dir = nli_model_path(resource_root)
        for item in self._lock.files:
            path = model_dir / item.target_path
            if not path.is_file():
                return _not_ready(
                    self.resource_id,
                    installation,
                    self._lock.identity,
                    ModelResourceStatus.INCOMPLETE,
                    f"NLI required file is unavailable: {item.target_path}.",
                    observed,
                )
            if _file_digest(path) != item.sha256:
                return _not_ready(
                    self.resource_id,
                    installation,
                    self._lock.identity,
                    ModelResourceStatus.IDENTITY_MISMATCH,
                    f"NLI required file digest differs: {item.target_path}.",
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

    def install_staged(self, staged: Path, reusable_installation: Path | None) -> None:
        del reusable_installation
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
                    f"Downloaded NLI file failed its pinned digest: {item.target_path}."
                )
        self._smoke(model_dir, self._lock.identity)
        _write_manifest(
            staged / "manifest.json",
            {
                "schema_version": NLI_MANIFEST_SCHEMA,
                "resource_id": self.resource_id.value,
                "identity": self._lock.identity,
                "transformers_version": self._lock.transformers_version,
                "files": _nli_file_manifest(self._lock),
                "smoke_status": "passed",
            },
        )


class StanzaEnglishModelResourceAdapter:
    """Install and inspect the pinned offline Stanza EWT pipeline."""

    resource_id = ModelResourceId.STANZA_ENGLISH_V1

    def __init__(
        self,
        *,
        downloader: _SnapshotDownloader | None = None,
        file_downloader: _FileDownloader | None = None,
        smoke: _StanzaSmoke | None = None,
        lock_path: Path | None = None,
    ) -> None:
        self._lock = _load_stanza_lock(lock_path)
        self._downloader = downloader or _snapshot_download
        self._file_downloader = file_downloader or _download_file
        self._smoke = smoke or _smoke_stanza

    def inspect(self, resource_root: Path) -> ModelResourceReadiness:
        return _inspect_file_resource(
            resource_id=self.resource_id,
            installation=stanza_model_path(resource_root),
            identity=self._lock.identity,
            schema=STANZA_MANIFEST_SCHEMA,
            package_name="stanza",
            package_version=self._lock.package_version,
            files=(*self._lock.files, _stanza_resources_file(self._lock)),
        )

    def install(
        self,
        resource_root: Path,
        *,
        repair: bool,
    ) -> ModelResourceInstallResult:
        return _install(self, resource_root, repair=repair)

    def install_staged(self, staged: Path, reusable_installation: Path | None) -> None:
        del reusable_installation
        _download_snapshot_files(staged, self._lock.files, self._downloader)
        resources_path = staged / "resources.json"
        self._file_downloader(self._lock.resources_json_url, resources_path)
        if _file_digest(resources_path) != self._lock.resources_json_sha256:
            raise ModelResourceInstallationError(
                "Downloaded Stanza resources.json failed its pinned digest."
            )
        _verify_pinned_files(staged, (*self._lock.files, _stanza_resources_file(self._lock)))
        self._smoke(staged, self._lock.identity)
        _write_file_resource_manifest(
            staged,
            schema=STANZA_MANIFEST_SCHEMA,
            resource_id=self.resource_id,
            identity=self._lock.identity,
            package_name="stanza",
            package_version=self._lock.package_version,
            files=(*self._lock.files, _stanza_resources_file(self._lock)),
        )


class QANomModelResourceAdapter:
    """Install and inspect the pinned QANom classifier and lexical resources."""

    resource_id = ModelResourceId.QANOM_NOMINALIZATION_V1

    def __init__(
        self,
        *,
        downloader: _SnapshotDownloader | None = None,
        file_downloader: _FileDownloader | None = None,
        smoke: _QANomSmoke | None = None,
        lock_path: Path | None = None,
    ) -> None:
        self._lock = _load_qanom_lock(lock_path)
        self._downloader = downloader or _snapshot_download
        self._file_downloader = file_downloader or _download_file
        self._smoke = smoke or _smoke_qanom

    def inspect(self, resource_root: Path) -> ModelResourceReadiness:
        return _inspect_file_resource(
            resource_id=self.resource_id,
            installation=qanom_installation_path(resource_root),
            identity=self._lock.identity,
            schema=QANOM_MANIFEST_SCHEMA,
            package_name="transformers",
            package_version=self._lock.transformers_version,
            files=(*self._lock.files, *self._lock.lexical_files),
        )

    def install(
        self,
        resource_root: Path,
        *,
        repair: bool,
    ) -> ModelResourceInstallResult:
        return _install(self, resource_root, repair=repair)

    def install_staged(self, staged: Path, reusable_installation: Path | None) -> None:
        del reusable_installation
        _download_snapshot_files(staged, self._lock.files, self._downloader)
        for item in self._lock.lexical_files:
            target = staged / item.target_path
            target.parent.mkdir(parents=True, exist_ok=True)
            self._file_downloader(item.download_url, target)
        files = (*self._lock.files, *self._lock.lexical_files)
        _verify_pinned_files(staged, files)
        self._smoke(staged / "model", staged / "lexical", self._lock.identity)
        _write_file_resource_manifest(
            staged,
            schema=QANOM_MANIFEST_SCHEMA,
            resource_id=self.resource_id,
            identity=self._lock.identity,
            package_name="transformers",
            package_version=self._lock.transformers_version,
            files=files,
        )


class FCorefModelResourceAdapter:
    """Install and inspect the isolated, pinned F-Coref worker."""

    resource_id = ModelResourceId.FCOREF_V1

    def __init__(
        self,
        *,
        downloader: _SnapshotDownloader | None = None,
        command_runner: _CommandRunner | None = None,
        smoke: _FCorefSmoke | None = None,
        checkout_root: Path | None = None,
        runtime_probe: _RuntimeProbe | None = None,
    ) -> None:
        self._checkout_root = checkout_root or Path(__file__).resolve().parents[4]
        self._requirements = self._checkout_root / "tools" / "fcoref-worker" / "requirements.txt"
        self._resource_lock = self._checkout_root / "tools" / "fcoref-worker" / "resource-lock.json"
        self._lock = _load_fcoref_lock(self._requirements, self._resource_lock)
        self._downloader = downloader or _snapshot_download
        self._runner = command_runner or _run_command
        self._smoke = smoke or _smoke_fcoref
        self._runtime_probe = runtime_probe or _probe_fcoref_runtime

    def inspect(self, resource_root: Path) -> ModelResourceReadiness:
        installation = fcoref_installation_path(resource_root)
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
                "F-Coref Resource Installation manifest is unavailable.",
            )
        observed = _manifest_identity(manifest)
        if (
            manifest.get("schema_version") != FCOREF_MANIFEST_SCHEMA
            or manifest.get("resource_id") != self.resource_id.value
            or observed != self._lock.identity
            or manifest.get("package_revision") != self._lock.package_revision
            or manifest.get("python_version") != FCOREF_PYTHON_VERSION
            or manifest.get("requirements_sha256") != _file_digest(self._requirements)
            or manifest.get("files") != _fcoref_file_manifest(self._lock)
            or manifest.get("dependency_check_status") != "passed"
            or manifest.get("smoke_status") != "passed"
        ):
            return _not_ready(
                self.resource_id,
                installation,
                self._lock.identity,
                ModelResourceStatus.IDENTITY_MISMATCH,
                "F-Coref Resource Installation manifest does not match the pinned lock.",
                observed,
            )
        python = fcoref_python_path(resource_root)
        if not python.is_file():
            return _not_ready(
                self.resource_id,
                installation,
                self._lock.identity,
                ModelResourceStatus.INCOMPLETE,
                "F-Coref managed Python executable is unavailable.",
                observed,
            )
        try:
            python_version, package_version = self._runtime_probe(python)
        except (OSError, RuntimeError) as error:
            return _not_ready(
                self.resource_id,
                installation,
                self._lock.identity,
                ModelResourceStatus.INCOMPLETE,
                f"F-Coref managed runtime is unavailable: {error}",
                observed,
            )
        if not python_version.startswith(f"{FCOREF_PYTHON_VERSION}.") or (
            package_version != FCOREF_PACKAGE_VERSION
        ):
            return _not_ready(
                self.resource_id,
                installation,
                self._lock.identity,
                ModelResourceStatus.IDENTITY_MISMATCH,
                "F-Coref managed Python or package version differs from the pinned lock.",
                observed,
            )
        for item in self._lock.files:
            path = fcoref_model_path(resource_root) / item.target_path
            if not path.is_file():
                return _not_ready(
                    self.resource_id,
                    installation,
                    self._lock.identity,
                    ModelResourceStatus.INCOMPLETE,
                    f"F-Coref required file is unavailable: {item.target_path}.",
                    observed,
                )
            if _file_digest(path) != item.sha256:
                return _not_ready(
                    self.resource_id,
                    installation,
                    self._lock.identity,
                    ModelResourceStatus.IDENTITY_MISMATCH,
                    f"F-Coref required file digest differs: {item.target_path}.",
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

    def install_staged(self, staged: Path, reusable_installation: Path | None) -> None:
        del reusable_installation
        runtime = staged / "runtime"
        model_dir = staged / "model"
        python = _venv_python(runtime)
        self._runner(("uv", "venv", "--python", FCOREF_PYTHON_VERSION, str(runtime)))
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
        self._runner(("uv", "pip", "check", "--python", str(python)))
        model_dir.mkdir()
        snapshot = Path(
            self._downloader(
                repo_id=self._lock.model_id,
                revision=self._lock.model_revision,
                allow_patterns=[item.source_path for item in self._lock.files],
                local_files_only=False,
            )
        )
        for item in self._lock.files:
            _link_or_copy(snapshot / item.source_path, model_dir / item.target_path)
            if _file_digest(model_dir / item.target_path) != item.sha256:
                raise ModelResourceInstallationError(
                    f"Downloaded F-Coref file failed its pinned digest: {item.target_path}."
                )
        worker = self._checkout_root / "scripts" / "fcoref_worker.py"
        self._smoke(python, worker, model_dir, self._lock.identity)
        _write_manifest(
            staged / "manifest.json",
            {
                "schema_version": FCOREF_MANIFEST_SCHEMA,
                "resource_id": self.resource_id.value,
                "identity": self._lock.identity,
                "package_revision": self._lock.package_revision,
                "python_version": FCOREF_PYTHON_VERSION,
                "requirements_sha256": _file_digest(self._requirements),
                "files": _fcoref_file_manifest(self._lock),
                "dependency_check_status": "passed",
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
            or manifest.get("dependency_check_status") != "passed"
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

    def install_staged(self, staged: Path, reusable_installation: Path | None) -> None:
        runtime = staged / "runtime"
        data_dir = staged / "data"
        setup_manifest = staged / "setup-manifest.json"
        python = _venv_python(runtime)
        setup_script = self._checkout_root / "scripts" / "setup_refined_organization_type_worker.py"
        reused_resources = self._reuse_verified_resources(reusable_installation, data_dir)
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
        self._runner(("uv", "pip", "check", "--python", str(python)))
        setup_command = (
            str(python),
            str(setup_script),
            "--data-dir",
            str(data_dir),
            "--manifest",
            str(setup_manifest),
        )
        if reused_resources:
            setup_command += ("--offline",)
        self._runner(setup_command)
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
                "dependency_check_status": "passed",
                "resource_materialization": (
                    "reused_verified_tree" if reused_resources else "downloaded"
                ),
                "smoke_status": "passed",
            },
        )

    def _reuse_verified_resources(
        self,
        reusable_installation: Path | None,
        staged_data_dir: Path,
    ) -> bool:
        if reusable_installation is None:
            return False
        existing_data_dir = reusable_installation / "data"
        try:
            if (
                not existing_data_dir.is_dir()
                or self._tree_digest(existing_data_dir) != self._expected_resource_digest
            ):
                return False
            _link_tree(existing_data_dir, staged_data_dir)
        except OSError:
            if staged_data_dir.exists():
                shutil.rmtree(staged_data_dir)
            return False
        return True


def gliner_installation_path(resource_root: Path) -> Path:
    return resource_root / GLINER_DIRECTORY


def gliner_model_path(resource_root: Path) -> Path:
    return gliner_installation_path(resource_root) / "model"


def gliner_expected_resource_identity() -> str:
    return _load_gliner_lock().identity


def nli_installation_path(resource_root: Path) -> Path:
    return resource_root / NLI_DIRECTORY


def nli_model_path(resource_root: Path) -> Path:
    return nli_installation_path(resource_root) / "model"


def nli_expected_resource_identity() -> str:
    return _load_nli_lock().identity


def stanza_installation_path(resource_root: Path) -> Path:
    return resource_root / STANZA_DIRECTORY


def stanza_model_path(resource_root: Path) -> Path:
    return stanza_installation_path(resource_root)


def stanza_expected_resource_identity() -> str:
    return _load_stanza_lock().identity


def qanom_installation_path(resource_root: Path) -> Path:
    return resource_root / QANOM_DIRECTORY


def qanom_model_path(resource_root: Path) -> Path:
    return qanom_installation_path(resource_root) / "model"


def qanom_lexical_resource_path(resource_root: Path) -> Path:
    return qanom_installation_path(resource_root) / "lexical"


def qanom_expected_resource_identity() -> str:
    return _load_qanom_lock().identity


def fcoref_installation_path(resource_root: Path) -> Path:
    return resource_root / FCOREF_DIRECTORY


def fcoref_python_path(resource_root: Path) -> Path:
    return _venv_python(fcoref_installation_path(resource_root) / "runtime")


def fcoref_model_path(resource_root: Path) -> Path:
    return fcoref_installation_path(resource_root) / "model"


def fcoref_expected_resource_identity() -> str:
    checkout_root = Path(__file__).resolve().parents[4]
    return _load_fcoref_lock(
        checkout_root / "tools" / "fcoref-worker" / "requirements.txt",
        checkout_root / "tools" / "fcoref-worker" / "resource-lock.json",
    ).identity


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
        adapter.install_staged(staged, target if target.exists() else None)
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


def _load_nli_lock(lock_path: Path | None = None) -> _NliLock:
    path = lock_path or Path(__file__).with_name("nli-deberta-model-lock.json")
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
    return _NliLock(str(payload["transformers_version"]), files, identity)


def _load_fcoref_lock(requirements: Path, resource_lock: Path) -> _FCorefLock:
    payload = cast(dict[str, object], json.loads(resource_lock.read_text(encoding="utf-8")))
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
    identity = hashlib.sha256(
        requirements.read_bytes() + b"\0" + resource_lock.read_bytes()
    ).hexdigest()
    return _FCorefLock(
        model_id=str(payload["model_id"]),
        model_revision=str(payload["model_revision"]),
        package_revision=str(payload["package_revision"]),
        files=files,
        identity=identity,
    )


def _load_stanza_lock(lock_path: Path | None = None) -> _StanzaLock:
    path = lock_path or Path(__file__).with_name("stanza-model-lock.json")
    payload = _load_required_lock(
        path,
        schema="stanza_model_lock_v1",
        resource_id=ModelResourceId.STANZA_ENGLISH_V1,
    )
    files = _pinned_snapshot_files(payload.get("files"), "Stanza")
    package_version = _required_non_empty_string(payload, "package_version", "Stanza")
    resources_url = _required_non_empty_string(payload, "resources_json_url", "Stanza")
    resources_sha = _required_sha256(payload, "resources_json_sha256", "Stanza")
    return _StanzaLock(
        package_version=package_version,
        resources_json_url=resources_url,
        resources_json_sha256=resources_sha,
        files=files,
        identity=hashlib.sha256(_canonical_json(payload)).hexdigest(),
    )


def _load_qanom_lock(lock_path: Path | None = None) -> _QANomLock:
    path = lock_path or Path(__file__).with_name("qanom-model-lock.json")
    payload = _load_required_lock(
        path,
        schema="qanom_model_lock_v1",
        resource_id=ModelResourceId.QANOM_NOMINALIZATION_V1,
    )
    files = _pinned_snapshot_files(payload.get("files"), "QANom")
    raw_lexical = payload.get("lexical_files")
    if not isinstance(raw_lexical, list) or not raw_lexical:
        raise ModelResourceInstallationError("The QANom lexical resource lock is incomplete.")
    lexical_files: list[_RemoteFileLock] = []
    for value in cast(list[object], raw_lexical):
        if not isinstance(value, dict):
            raise ModelResourceInstallationError("The QANom lexical file lock is invalid.")
        item = cast(dict[str, object], value)
        lexical_files.append(
            _RemoteFileLock(
                download_url=_required_non_empty_string(item, "download_url", "QANom"),
                target_path=_required_non_empty_string(item, "target_path", "QANom"),
                sha256=_required_sha256(item, "sha256", "QANom"),
            )
        )
    return _QANomLock(
        transformers_version=_required_non_empty_string(payload, "transformers_version", "QANom"),
        files=files,
        lexical_files=tuple(lexical_files),
        identity=hashlib.sha256(_canonical_json(payload)).hexdigest(),
    )


def _load_required_lock(
    path: Path,
    *,
    schema: str,
    resource_id: ModelResourceId,
) -> dict[str, object]:
    try:
        value: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ModelResourceInstallationError(
            f"The {resource_id.value} model lock is unreadable."
        ) from error
    if not isinstance(value, dict):
        raise ModelResourceInstallationError(
            f"The {resource_id.value} model lock must be an object."
        )
    payload = cast(dict[str, object], value)
    if payload.get("schema_version") != schema or payload.get("resource_id") != resource_id.value:
        raise ModelResourceInstallationError(
            f"The {resource_id.value} model lock contract is invalid."
        )
    return payload


def _pinned_snapshot_files(value: object, label: str) -> tuple[_GlinerFileLock, ...]:
    if not isinstance(value, list) or not value:
        raise ModelResourceInstallationError(f"The {label} model file lock is incomplete.")
    files: list[_GlinerFileLock] = []
    for raw in cast(list[object], value):
        if not isinstance(raw, dict):
            raise ModelResourceInstallationError(f"The {label} model file lock is invalid.")
        item = cast(dict[str, object], raw)
        files.append(
            _GlinerFileLock(
                repository=_required_non_empty_string(item, "repository", label),
                revision=_required_non_empty_string(item, "revision", label),
                source_path=_required_non_empty_string(item, "source_path", label),
                target_path=_required_non_empty_string(item, "target_path", label),
                sha256=_required_sha256(item, "sha256", label),
            )
        )
    return tuple(files)


def _required_non_empty_string(
    payload: dict[str, object],
    key: str,
    label: str,
) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise ModelResourceInstallationError(f"The {label} model lock has no {key}.")
    return value


def _required_sha256(payload: dict[str, object], key: str, label: str) -> str:
    value = _required_non_empty_string(payload, key, label)
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise ModelResourceInstallationError(f"The {label} model lock has an invalid {key}.")
    return value


def _nli_file_manifest(lock: _NliLock) -> list[dict[str, str]]:
    return [
        {
            "repository": item.repository,
            "revision": item.revision,
            "path": item.target_path,
            "sha256": item.sha256,
        }
        for item in lock.files
    ]


def _fcoref_file_manifest(lock: _FCorefLock) -> list[dict[str, str]]:
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


def _download_file(url: str, target: Path) -> None:
    try:
        with httpx.stream(
            "GET",
            url,
            follow_redirects=True,
            timeout=httpx.Timeout(300.0, connect=30.0),
        ) as response:
            response.raise_for_status()
            with target.open("wb") as file:
                for block in response.iter_bytes():
                    file.write(block)
    except (OSError, httpx.HTTPError) as error:
        raise ModelResourceInstallationError(
            f"Unable to download a pinned model resource: {error}"
        ) from error


def _download_snapshot_files(
    target: Path,
    files: tuple[_GlinerFileLock, ...],
    downloader: _SnapshotDownloader,
) -> None:
    grouped: dict[tuple[str, str], list[_GlinerFileLock]] = {}
    for item in files:
        grouped.setdefault((item.repository, item.revision), []).append(item)
    for (repository, revision), items in grouped.items():
        snapshot = Path(
            downloader(
                repo_id=repository,
                revision=revision,
                allow_patterns=[item.source_path for item in items],
                local_files_only=False,
            )
        )
        for item in items:
            destination = target / item.target_path
            destination.parent.mkdir(parents=True, exist_ok=True)
            _link_or_copy(snapshot / item.source_path, destination)


def _verify_pinned_files(
    root: Path,
    files: tuple[_GlinerFileLock | _RemoteFileLock, ...],
) -> None:
    for item in files:
        path = root / item.target_path
        if not path.is_file():
            raise ModelResourceInstallationError(
                f"Required model file is unavailable: {item.target_path}."
            )
        if _file_digest(path) != item.sha256:
            raise ModelResourceInstallationError(
                f"Required model file digest differs: {item.target_path}."
            )


def _managed_file_manifest(
    files: tuple[_GlinerFileLock | _RemoteFileLock, ...],
) -> list[dict[str, str]]:
    return [{"path": item.target_path, "sha256": item.sha256} for item in files]


def _inspect_file_resource(
    *,
    resource_id: ModelResourceId,
    installation: Path,
    identity: str,
    schema: str,
    package_name: str,
    package_version: str,
    files: tuple[_GlinerFileLock | _RemoteFileLock, ...],
) -> ModelResourceReadiness:
    try:
        observed_package_version = version(package_name)
    except PackageNotFoundError:
        return _not_ready(
            resource_id,
            installation,
            identity,
            ModelResourceStatus.INCOMPLETE,
            f"The pinned {package_name} package is unavailable.",
        )
    if observed_package_version != package_version:
        return _not_ready(
            resource_id,
            installation,
            identity,
            ModelResourceStatus.IDENTITY_MISMATCH,
            f"{package_name} package version differs: {observed_package_version}.",
            observed_package_version,
        )
    manifest = _load_manifest(installation / "manifest.json")
    if manifest is None:
        status = (
            ModelResourceStatus.INCOMPLETE if installation.exists() else ModelResourceStatus.MISSING
        )
        return _not_ready(
            resource_id,
            installation,
            identity,
            status,
            f"{resource_id.value} Resource Installation manifest is unavailable.",
        )
    observed = _manifest_identity(manifest)
    if (
        manifest.get("schema_version") != schema
        or manifest.get("resource_id") != resource_id.value
        or observed != identity
        or manifest.get("package_name") != package_name
        or manifest.get("package_version") != package_version
        or manifest.get("files") != _managed_file_manifest(files)
        or manifest.get("smoke_status") != "passed"
    ):
        return _not_ready(
            resource_id,
            installation,
            identity,
            ModelResourceStatus.IDENTITY_MISMATCH,
            f"{resource_id.value} Resource Installation manifest does not match its lock.",
            observed,
        )
    try:
        _verify_pinned_files(installation, files)
    except ModelResourceInstallationError as error:
        return _not_ready(
            resource_id,
            installation,
            identity,
            ModelResourceStatus.IDENTITY_MISMATCH,
            str(error),
            observed,
        )
    return _ready(resource_id, installation, identity)


def _write_file_resource_manifest(
    installation: Path,
    *,
    schema: str,
    resource_id: ModelResourceId,
    identity: str,
    package_name: str,
    package_version: str,
    files: tuple[_GlinerFileLock | _RemoteFileLock, ...],
) -> None:
    _write_manifest(
        installation / "manifest.json",
        {
            "schema_version": schema,
            "resource_id": resource_id.value,
            "identity": identity,
            "package_name": package_name,
            "package_version": package_version,
            "files": _managed_file_manifest(files),
            "smoke_status": "passed",
        },
    )


def _stanza_resources_file(lock: _StanzaLock) -> _RemoteFileLock:
    return _RemoteFileLock(
        download_url=lock.resources_json_url,
        target_path="resources.json",
        sha256=lock.resources_json_sha256,
    )


def _link_or_copy(source: Path, target: Path) -> None:
    resolved_source = source.resolve(strict=True)
    try:
        os.link(resolved_source, target)
    except OSError:
        shutil.copyfile(resolved_source, target)


def _link_tree(source: Path, target: Path) -> None:
    target.mkdir(parents=True)
    for source_path in sorted(path for path in source.rglob("*") if path.is_file()):
        relative_path = source_path.relative_to(source)
        target_path = target / relative_path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        _link_or_copy(source_path, target_path)


def _smoke_gliner(model_dir: Path) -> None:
    from .gliner_organization_mention_proposer import load_gliner_model

    model = cast(_GlinerSmokeModel, load_gliner_model(model_dir, "cpu"))
    model.predict_entities("Anthropic announced an update.", ["organization"], threshold=0.5)


def _smoke_nli(model_dir: Path, resource_identity: str) -> None:
    from .deberta_nli import DebertaNliAdapter

    execution = DebertaNliAdapter(
        model_directory=model_dir.resolve(),
        resource_identity=resource_identity,
    ).classify(
        NaturalLanguageInferenceInput(
            premise="Anthropic is an organization.",
            hypothesis="Anthropic is an organization.",
        )
    )
    if execution.selected_label.value != "entailment":
        raise ModelResourceInstallationError("The NLI smoke test did not return entailment.")


def _smoke_stanza(model_dir: Path, resource_identity: str) -> None:
    from .stanza_linguistic_analysis import StanzaLinguisticAnalyzer

    analysis = StanzaLinguisticAnalyzer(
        model_directory=model_dir.resolve(),
        resource_identity=resource_identity,
    ).analyze(
        LinguisticAnalysisInput(
            source_text="Anthropic partnered with an institute under an agreement."
        )
    )
    by_text = {token.text: token.part_of_speech.value for token in analysis.tokens}
    if by_text.get("partnered") != "VERB" or by_text.get("agreement") != "NOUN":
        raise ModelResourceInstallationError(
            "The Stanza smoke test did not identify the pinned predicate candidates."
        )


def _smoke_qanom(
    model_dir: Path,
    lexical_dir: Path,
    resource_identity: str,
) -> None:
    from .qanom_nominalization import QANomNominalizationAnalyzer

    source_text = "Officials conducted negotiations."
    linguistic = _smoke_stanza_analysis(source_text, resource_identity)
    analysis = QANomNominalizationAnalyzer(
        model_directory=model_dir.resolve(),
        lexical_resource_directory=lexical_dir.resolve(),
        resource_identity=resource_identity,
    ).analyze(NominalizationAnalysisInput(source_text, linguistic))
    negotiations = next((item for item in analysis.candidates if item.text == "negotiations"), None)
    if negotiations is None or not negotiations.lexical_candidate:
        raise ModelResourceInstallationError(
            "The QANom smoke test did not identify the pinned nominal candidate."
        )


def _smoke_stanza_analysis(source_text: str, resource_identity: str) -> LinguisticAnalysis:
    """Build a tiny valid syntax fixture for the QANom installation smoke test."""
    from kotekomi_application import LinguisticToken, UniversalPartOfSpeech

    return LinguisticAnalysis(
        source_text_sha256=hashlib.sha256(source_text.encode()).hexdigest(),
        producer_id="qanom_smoke_fixture",
        model_id="fixture",
        model_version="1",
        resource_identity=resource_identity,
        tokens=(
            LinguisticToken(
                token_id="t1",
                sentence_id="s1",
                text="Officials",
                start=0,
                end=9,
                lemma="official",
                part_of_speech=UniversalPartOfSpeech.NOUN,
                dependency_relation="nsubj",
                head_token_id="t2",
            ),
            LinguisticToken(
                token_id="t2",
                sentence_id="s1",
                text="conducted",
                start=10,
                end=19,
                lemma="conduct",
                part_of_speech=UniversalPartOfSpeech.VERB,
                dependency_relation="root",
                head_token_id=None,
            ),
            LinguisticToken(
                token_id="t3",
                sentence_id="s1",
                text="negotiations",
                start=20,
                end=32,
                lemma="negotiation",
                part_of_speech=UniversalPartOfSpeech.NOUN,
                dependency_relation="obj",
                head_token_id="t2",
            ),
            LinguisticToken(
                token_id="t4",
                sentence_id="s1",
                text=".",
                start=32,
                end=33,
                lemma=".",
                part_of_speech=UniversalPartOfSpeech.PUNCTUATION,
                dependency_relation="punct",
                head_token_id="t2",
            ),
        ),
    )


def _smoke_fcoref(
    python: Path,
    worker_script: Path,
    model_dir: Path,
    resource_identity: str,
) -> None:
    from .fcoref import FCorefAdapter, FCorefConfig

    adapter = FCorefAdapter(
        FCorefConfig(
            python_executable=python,
            worker_script=worker_script,
            model_directory=model_dir.resolve(),
            resource_identity=resource_identity,
        )
    )
    try:
        if adapter.count_tokens(b"Trump spoke. He replied.") < 1:
            raise ModelResourceInstallationError("F-Coref smoke tokenization failed.")
        execution = adapter.propose(
            CoreferenceInput(
                source_segment_id="fcoref_smoke",
                source_text="Trump spoke. He replied.",
                target_start=13,
                target_end=15,
            )
        )
        if execution.model_id != "biu-nlp/f-coref":
            raise ModelResourceInstallationError("F-Coref smoke identity drifted.")
    finally:
        adapter.close()


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


def _probe_fcoref_runtime(python: Path) -> tuple[str, str]:
    probe = (
        "import importlib.metadata, platform; "
        "print(platform.python_version()); "
        "print(importlib.metadata.version('fastcoref'))"
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
