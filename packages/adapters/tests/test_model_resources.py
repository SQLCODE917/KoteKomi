from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from kotekomi_adapters.model_resources import (
    GlinerModelResourceAdapter,
    ModelResourceInstallationError,
    RefinedModelResourceAdapter,
    gliner_model_path,
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
            data_dir.mkdir()
            (data_dir / "resource.bin").write_bytes(resource_payload)
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
    assert len(commands) == 3
    assert refined_python_path(root).is_file()
    assert (refined_data_path(root) / "resource.bin").read_bytes() == resource_payload
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
