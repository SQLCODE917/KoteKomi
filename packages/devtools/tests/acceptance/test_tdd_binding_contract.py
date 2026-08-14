from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, cast

PROJECT_ROOT = Path(__file__).resolve().parents[4]


def _run_cli(args: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["uv", "run", "--project", str(PROJECT_ROOT), "kotekomi-agent", *args],
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
    )


def _payload(result: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    assert result.stdout.endswith("\n")
    value = json.loads(result.stdout)
    assert isinstance(value, dict)
    return cast(dict[str, Any], value)


def _bind(
    cwd: Path,
    tdd_path: str,
    output: str,
    receipt: str,
) -> tuple[int, dict[str, Any]]:
    state_root = cwd / "state"
    result = _run_cli(
        [
            "tdd-bind",
            tdd_path,
            "--output",
            output,
            "--receipt",
            receipt,
            "--state-root",
            str(state_root),
        ],
        cwd=cwd,
    )
    return result.returncode, _payload(result)


def test_tdd_bind_writes_canonical_evidence_snapshot_index_and_receipt(tmp_path: Path) -> None:
    tdd = tmp_path / "docs" / "example.md"
    content = b"# Example Harness TDD\n\nExact bytes.\n"
    tdd.parent.mkdir()
    tdd.write_bytes(content)

    code, result = _bind(tmp_path, "docs/example.md", "result/binding.json", "result/receipt.json")

    assert code == 0
    assert result["status"] == "ready"
    assert result["tdd_path"] == "docs/example.md"
    assert result["tdd_title"] == "Example Harness TDD"
    assert result["tdd_sha256"] == hashlib.sha256(content).hexdigest()
    canonical = Path(cast(str, result["canonical_binding_path"]))
    snapshot = Path(cast(str, result["tdd_snapshot_path"]))
    assert canonical == tmp_path / "state" / result["task_id"] / "spec" / "tdd-binding.json"
    assert snapshot.read_bytes() == content
    assert json.loads(
        (tmp_path / "result" / "binding.json").read_text(encoding="utf-8")
    ) == json.loads(canonical.read_text(encoding="utf-8"))
    index = json.loads((tmp_path / "state" / "tdd-index.json").read_text(encoding="utf-8"))
    assert index["by_tdd_path"]["docs/example.md"] == result["task_id"]
    assert index["by_task_id"][result["task_id"]] == str(canonical)

    receipt_payload = json.loads((tmp_path / "result" / "receipt.json").read_text(encoding="utf-8"))
    assert receipt_payload["record_kind"] == "tdd-binding"
    assert receipt_payload["task_id"] == result["task_id"]
    assert receipt_payload["fields"]["tdd_sha256"] == result["tdd_sha256"]
    assert receipt_payload["fields"]["canonical_binding_path"] == str(canonical)
    assert receipt_payload["artifacts"]["canonical_binding"]["path"] == str(canonical)


def test_tdd_bind_rejects_network_sources_and_unreadable_paths_as_json(tmp_path: Path) -> None:
    code, network = _bind(
        tmp_path, "https://example.invalid/tdd.md", "network.json", "network.receipt.json"
    )
    assert code != 0
    assert network["status"] == "blocked"
    assert network["diagnostics"][0]["code"] == "tdd_path.network_source"

    code, missing = _bind(tmp_path, "missing.md", "missing.json", "missing.receipt.json")
    assert code != 0
    assert missing["status"] == "blocked"
    assert missing["diagnostics"][0]["code"] == "tdd_path.unreadable"
    assert not missing["diagnostics"][0]["rule"].startswith("Traceback")


def test_tdd_bind_repeats_equal_digest_and_blocks_path_drift(tmp_path: Path) -> None:
    tdd = tmp_path / "drift.md"
    tdd.write_text("# Original\n", encoding="utf-8")
    code, first = _bind(tmp_path, "drift.md", "first.binding.json", "first.receipt.json")
    assert code == 0

    code, repeated = _bind(tmp_path, "drift.md", "second.binding.json", "second.receipt.json")
    assert code == 0
    assert repeated["status"] == "ready"
    assert repeated["canonical_binding_path"] == first["canonical_binding_path"]

    tdd.write_text("# Changed\n", encoding="utf-8")
    code, drifted = _bind(tmp_path, "drift.md", "changed.binding.json", "changed.receipt.json")
    assert code != 0
    assert drifted["status"] == "blocked"
    assert drifted["diagnostics"][0]["code"] == "tdd_binding.digest_conflict"
    assert not (tmp_path / "changed.binding.json").exists()


def test_tdd_bind_rebuilds_missing_and_stale_index_from_canonical_binding(
    tmp_path: Path,
) -> None:
    tdd = tmp_path / "lookup.md"
    tdd.write_text("# Lookup\n", encoding="utf-8")
    code, first = _bind(tmp_path, "lookup.md", "first.binding.json", "first.receipt.json")
    assert code == 0
    index = tmp_path / "state" / "tdd-index.json"
    index.unlink()

    code, rebuilt = _bind(tmp_path, "lookup.md", "second.binding.json", "second.receipt.json")
    assert code == 0
    assert rebuilt["canonical_binding_path"] == first["canonical_binding_path"]
    assert (
        json.loads(index.read_text(encoding="utf-8"))["by_tdd_path"]["lookup.md"]
        == first["task_id"]
    )

    index.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "by_tdd_path": {"lookup.md": "stale"},
                "by_tdd_sha256": {},
                "by_task_id": {"stale": "missing.json"},
                "diagnostics": [],
            }
        ),
        encoding="utf-8",
    )
    code, rebuilt = _bind(tmp_path, "lookup.md", "third.binding.json", "third.receipt.json")
    assert code == 0
    assert rebuilt["canonical_binding_path"] == first["canonical_binding_path"]
    assert (
        json.loads(index.read_text(encoding="utf-8"))["by_task_id"][first["task_id"]]
        == first["canonical_binding_path"]
    )


def test_tdd_bind_index_maps_one_digest_to_multiple_task_identifiers(tmp_path: Path) -> None:
    content = b"Same body without a heading.\n"
    (tmp_path / "first.md").write_bytes(content)
    (tmp_path / "second.md").write_bytes(content)

    code, first = _bind(tmp_path, "first.md", "first.binding.json", "first.receipt.json")
    assert code == 0
    code, second = _bind(tmp_path, "second.md", "second.binding.json", "second.receipt.json")
    assert code == 0

    index = json.loads((tmp_path / "state" / "tdd-index.json").read_text(encoding="utf-8"))
    assert index["by_tdd_sha256"][first["tdd_sha256"]] == sorted(
        [first["task_id"], second["task_id"]]
    )


def test_tdd_bind_rejects_existing_invalid_receipt_without_mutating_canonical_state(
    tmp_path: Path,
) -> None:
    tdd = tmp_path / "receipt.md"
    tdd.write_text("# Receipt\n", encoding="utf-8")
    receipt = tmp_path / "receipt.json"
    receipt.write_text("{}\n", encoding="utf-8")

    code, result = _bind(tmp_path, "receipt.md", "binding.json", "receipt.json")

    assert code != 0
    assert result["status"] == "blocked"
    assert result["diagnostics"][0]["code"] == "tdd_binding.receipt_conflict"
    assert not (tmp_path / "state").exists()


def test_tdd_bind_rejects_the_removed_index_override(tmp_path: Path) -> None:
    result = _run_cli(
        [
            "tdd-bind",
            "missing.md",
            "--output",
            "binding.json",
            "--receipt",
            "receipt.json",
            "--index",
            "binding.json",
        ],
        cwd=tmp_path,
    )

    assert result.returncode == 2
    assert "unrecognized arguments" in result.stderr
