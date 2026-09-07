from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from kotekomi_adapters.model_resources import (
    FCorefModelResourceAdapter,
    GlinerModelResourceAdapter,
    ModelResourceInstallationError,
    NliDebertaModelResourceAdapter,
    RefinedModelResourceAdapter,
    fcoref_model_path,
    fcoref_python_path,
    gliner_model_path,
    nli_model_path,
    refined_data_path,
    refined_python_path,
)
from kotekomi_application import ModelResourceInstallDisposition, ModelResourceStatus


def _digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _write_gliner_lock(path: Path, files: dict[str, bytes]) -> None:
    records: list[dict[str, object]] = []
    for filename, payload in files.items():
        records.append(
            {
                "repository": f"owner/{filename}",
                "revision": f"revision-{filename}",
                "source_path": filename,
                "target_path": filename,
                "sha256": _digest(payload),
            }
        )
    path.write_text(
        json.dumps(
            {
                "files": records,
                "package_version": "0.2.28",
                "resource_id": "gliner_mention_proposer_v1",
                "schema_version": "gliner_model_lock_v1",
            }
        ),
        encoding="utf-8",
    )


def test_gliner_install_is_pinned_reused_and_repaired(tmp_path: Path) -> None:
    files = {"gliner_config.json": b"config", "model.safetensors": b"weights"}
    lock = tmp_path / "lock.json"
    _write_gliner_lock(lock, files)
    download_calls: list[tuple[str, str, bool]] = []
    smoke_paths: list[Path] = []

    def download(
        *,
        repo_id: str,
        revision: str,
        allow_patterns: list[str],
        local_files_only: bool,
    ) -> str:
        download_calls.append((repo_id, revision, local_files_only))
        snapshot = tmp_path / "download-cache" / revision
        snapshot.mkdir(parents=True, exist_ok=True)
        for filename in allow_patterns:
            (snapshot / filename).write_bytes(files[filename])
        return str(snapshot)

    adapter = GlinerModelResourceAdapter(
        downloader=download,
        smoke=smoke_paths.append,
        lock_path=lock,
    )
    root = (tmp_path / "resources").resolve()

    installed = adapter.install(root, repair=False)
    reused = adapter.install(root, repair=False)

    assert installed.disposition is ModelResourceInstallDisposition.INSTALLED
    assert reused.disposition is ModelResourceInstallDisposition.REUSED
    assert len(download_calls) == 2
    assert all(not local_only for _, _, local_only in download_calls)
    assert len(smoke_paths) == 1
    assert smoke_paths[0].name == "model"
    assert smoke_paths[0].parent.parent == root
    assert adapter.inspect(root).status is ModelResourceStatus.READY
    manifest = json.loads((root / "gliner_mention_proposer_v1" / "manifest.json").read_text())
    assert manifest["files"] == [
        {
            "path": filename,
            "repository": f"owner/{filename}",
            "revision": f"revision-{filename}",
            "sha256": _digest(payload),
        }
        for filename, payload in files.items()
    ]

    (gliner_model_path(root) / "model.safetensors").write_bytes(b"corrupt")
    assert adapter.inspect(root).status is ModelResourceStatus.IDENTITY_MISMATCH
    with pytest.raises(ModelResourceInstallationError, match="--repair"):
        adapter.install(root, repair=False)

    def fail_download(
        *,
        repo_id: str,
        revision: str,
        allow_patterns: list[str],
        local_files_only: bool,
    ) -> str:
        del repo_id, revision, allow_patterns, local_files_only
        raise RuntimeError("download failed")

    failing_adapter = GlinerModelResourceAdapter(
        downloader=fail_download,
        smoke=smoke_paths.append,
        lock_path=lock,
    )
    with pytest.raises(RuntimeError, match="download failed"):
        failing_adapter.install(root, repair=True)
    assert (gliner_model_path(root) / "model.safetensors").read_bytes() == b"corrupt"

    repaired = adapter.install(root, repair=True)

    assert repaired.disposition is ModelResourceInstallDisposition.REPAIRED
    assert adapter.inspect(root).status is ModelResourceStatus.READY


def test_gliner_missing_and_partial_installations_are_distinct(tmp_path: Path) -> None:
    lock = tmp_path / "lock.json"
    _write_gliner_lock(lock, {"model.safetensors": b"weights"})
    adapter = GlinerModelResourceAdapter(
        downloader=lambda **_arguments: "unused",  # type: ignore[arg-type]
        smoke=lambda _path: None,
        lock_path=lock,
    )
    root = (tmp_path / "resources").resolve()

    assert adapter.inspect(root).status is ModelResourceStatus.MISSING
    gliner_model_path(root).mkdir(parents=True)
    assert adapter.inspect(root).status is ModelResourceStatus.INCOMPLETE


def test_nli_install_is_pinned_local_and_reusable(tmp_path: Path) -> None:
    files = {"config.json": b"config", "model.safetensors": b"weights"}
    lock = tmp_path / "nli-lock.json"
    lock.write_text(
        json.dumps(
            {
                "files": [
                    {
                        "repository": "cross-encoder/fixture",
                        "revision": "fixture-revision",
                        "source_path": name,
                        "target_path": name,
                        "sha256": _digest(payload),
                    }
                    for name, payload in files.items()
                ],
                "resource_id": "nli_deberta_v3_base_v1",
                "schema_version": "nli_deberta_model_lock_v1",
                "transformers_version": "5.8.1",
            }
        ),
        encoding="utf-8",
    )
    calls: list[bool] = []

    def download(
        *,
        repo_id: str,
        revision: str,
        allow_patterns: list[str],
        local_files_only: bool,
    ) -> str:
        del repo_id, revision
        calls.append(local_files_only)
        snapshot = tmp_path / "download"
        snapshot.mkdir(exist_ok=True)
        for name in allow_patterns:
            (snapshot / name).write_bytes(files[name])
        return str(snapshot)

    smoke: list[tuple[Path, str]] = []
    adapter = NliDebertaModelResourceAdapter(
        downloader=download,
        smoke=lambda path, identity: smoke.append((path, identity)),
        lock_path=lock,
    )
    root = (tmp_path / "resources").resolve()

    assert adapter.install(root, repair=False).disposition is (
        ModelResourceInstallDisposition.INSTALLED
    )
    assert adapter.install(root, repair=False).disposition is (
        ModelResourceInstallDisposition.REUSED
    )
    assert calls == [False]
    assert len(smoke) == 1
    assert smoke[0][0].name == nli_model_path(root).name
    assert smoke[0][0].parent.name.startswith(".nli_deberta_v3_base_v1-")
    assert smoke[0][1] == adapter.inspect(root).expected_identity


def test_fcoref_install_is_isolated_pinned_and_optional(tmp_path: Path) -> None:
    checkout = tmp_path / "checkout"
    requirements = checkout / "tools" / "fcoref-worker" / "requirements.txt"
    requirements.parent.mkdir(parents=True)
    requirements.write_text("fastcoref==2.2.3\n", encoding="utf-8")
    worker = checkout / "scripts" / "fcoref_worker.py"
    worker.parent.mkdir()
    worker.write_text("# fixture\n", encoding="utf-8")
    files = {"config.json": b"config", "pytorch_model.bin": b"weights"}
    (requirements.parent / "resource-lock.json").write_text(
        json.dumps(
            {
                "schema_version": "fcoref_worker_resource_lock_v1",
                "model_id": "biu-nlp/f-coref",
                "model_revision": "fixture-model-revision",
                "package_revision": "fixture-package-revision",
                "files": [
                    {
                        "repository": "biu-nlp/f-coref",
                        "revision": "fixture-model-revision",
                        "source_path": name,
                        "target_path": name,
                        "sha256": _digest(payload),
                    }
                    for name, payload in files.items()
                ],
            }
        ),
        encoding="utf-8",
    )
    commands: list[tuple[str, ...]] = []

    def run(command: tuple[str, ...]) -> None:
        commands.append(command)
        if command[:2] == ("uv", "venv"):
            python = Path(command[-1]) / "bin" / "python"
            python.parent.mkdir(parents=True)
            python.write_text("fixture", encoding="utf-8")

    def download(**_arguments: object) -> str:
        snapshot = tmp_path / "snapshot"
        snapshot.mkdir()
        for name, payload in files.items():
            (snapshot / name).write_bytes(payload)
        return str(snapshot)

    smoke: list[tuple[Path, Path, Path, str]] = []

    def smoke_fcoref(python: Path, script: Path, model: Path, identity: str) -> None:
        smoke.append((python, script, model, identity))

    adapter = FCorefModelResourceAdapter(
        downloader=download,  # type: ignore[arg-type]
        command_runner=run,
        smoke=smoke_fcoref,
        checkout_root=checkout,
        runtime_probe=lambda _python: ("3.12.13", "2.2.3"),
    )
    root = (tmp_path / "resources").resolve()

    installed = adapter.install(root, repair=False)

    assert installed.disposition is ModelResourceInstallDisposition.INSTALLED
    assert adapter.inspect(root).status is ModelResourceStatus.READY
    assert fcoref_python_path(root).is_file()
    assert (fcoref_model_path(root) / "pytorch_model.bin").read_bytes() == b"weights"
    assert len(smoke) == 1
    assert smoke[0][0].name == "python"
    assert smoke[0][1] == worker
    assert smoke[0][2].name == "model"
    assert smoke[0][3] == adapter.inspect(root).expected_identity
    assert any(command[:3] == ("uv", "pip", "sync") for command in commands)


def _tree_digest(filename: str, payload: bytes) -> str:
    digest = hashlib.sha256()
    digest.update(filename.encode())
    digest.update(b"\0")
    digest.update(str(len(payload)).encode("ascii"))
    digest.update(b"\0")
    digest.update(hashlib.sha256(payload).hexdigest().encode("ascii"))
    digest.update(b"\n")
    return digest.hexdigest()


def test_refined_install_manages_runtime_resources_and_reuses_them(tmp_path: Path) -> None:
    checkout = tmp_path / "checkout"
    tools = checkout / "tools" / "refined-worker"
    scripts = checkout / "scripts"
    tools.mkdir(parents=True)
    scripts.mkdir()
    requirements = b"ReFinED==1.0\n"
    (tools / "requirements.txt").write_bytes(requirements)
    resource_lock: dict[str, object] = {
        "package_version": "1.0",
        "package_revision": "package-revision",
        "model_id": "wikipedia_model",
        "model_revision": "model-revision",
        "entity_set": "wikipedia",
        "smoke_spans": [],
    }
    (tools / "resource-lock.json").write_text(json.dumps(resource_lock), encoding="utf-8")
    (scripts / "setup_refined_organization_type_worker.py").write_text(
        "# fixture\n", encoding="utf-8"
    )
    resource_payload = b"pinned-resource"
    expected_digest = _tree_digest("resource.bin", resource_payload)
    commands: list[tuple[str, ...]] = []

    def run(command: tuple[str, ...]) -> None:
        commands.append(command)
        if command[:2] == ("uv", "venv"):
            python = Path(command[-1]) / "bin" / "python"
            python.parent.mkdir(parents=True)
            python.write_text("", encoding="utf-8")
        elif command[0].endswith("/python") and "--data-dir" in command:
            data_dir = Path(command[command.index("--data-dir") + 1])
            manifest = Path(command[command.index("--manifest") + 1])
            data_dir.mkdir(exist_ok=True)
            resource_path = data_dir / "resource.bin"
            if "--offline" in command:
                assert resource_path.read_bytes() == resource_payload
            else:
                resource_path.write_bytes(resource_payload)
            manifest.write_text(
                json.dumps(
                    {
                        **resource_lock,
                        "resource_manifest_sha256": expected_digest,
                    }
                ),
                encoding="utf-8",
            )

    adapter = RefinedModelResourceAdapter(
        command_runner=run,
        checkout_root=checkout,
        expected_resource_digest=expected_digest,
        runtime_probe=lambda _python: ("3.10.14", "1.0"),
    )
    root = (tmp_path / "resources").resolve()

    installed = adapter.install(root, repair=False)
    reused = adapter.install(root, repair=False)

    assert installed.disposition is ModelResourceInstallDisposition.INSTALLED
    assert reused.disposition is ModelResourceInstallDisposition.REUSED
    assert len(commands) == 4
    assert commands[2][:3] == ("uv", "pip", "check")
    assert refined_python_path(root).is_file()
    assert (refined_data_path(root) / "resource.bin").read_bytes() == resource_payload
    assert adapter.inspect(root).status is ModelResourceStatus.READY

    manifest_path = root / "refined_wikipedia_v1" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["identity"] = "stale-runtime-identity"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    repaired = adapter.install(root, repair=True)

    assert repaired.disposition is ModelResourceInstallDisposition.REPAIRED
    assert "--offline" in commands[-1]
    repaired_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert repaired_manifest["dependency_check_status"] == "passed"
    assert repaired_manifest["resource_materialization"] == "reused_verified_tree"
    assert adapter.inspect(root).status is ModelResourceStatus.READY

    (refined_data_path(root) / "resource.bin").write_bytes(b"wrong-resource")

    repaired_after_resource_drift = adapter.install(root, repair=True)

    assert repaired_after_resource_drift.disposition is ModelResourceInstallDisposition.REPAIRED
    assert "--offline" not in commands[-1]
    assert adapter.inspect(root).status is ModelResourceStatus.READY


def test_production_gliner_lock_has_expected_model_and_tokenizer_files() -> None:
    adapter = GlinerModelResourceAdapter(smoke=lambda _path: None)
    missing = adapter.inspect(Path("/definitely/not/installed").resolve())

    assert missing.status is ModelResourceStatus.MISSING
    lock = json.loads(
        Path(__file__)
        .resolve()
        .parents[1]
        .joinpath("src/kotekomi_adapters/gliner-model-lock.json")
        .read_text(encoding="utf-8")
    )
    assert {item["target_path"] for item in lock["files"]} == {
        "config.json",
        "gliner_config.json",
        "model.safetensors",
        "spm.model",
        "tokenizer_config.json",
    }


def test_production_refined_requirements_pin_setuptools_for_complete_dependencies() -> None:
    requirements = (
        Path(__file__)
        .resolve()
        .parents[3]
        .joinpath("tools/refined-worker/requirements.txt")
        .read_text(encoding="utf-8")
        .splitlines()
    )

    assert "setuptools==83.0.0" in requirements
