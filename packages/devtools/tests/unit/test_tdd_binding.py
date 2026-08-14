from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from kotekomi_devtools.tdd_binding import (
    TddBindingError,
    bind_tdd,
    derive_task_id,
    lookup_tdd_bindings,
    read_tdd_binding,
    rebuild_tdd_index,
    slugify,
)


def _bind(tmp_path: Path, name: str, content: bytes, *, output: Path | None = None):
    tdd = tmp_path / name
    tdd.parent.mkdir(parents=True, exist_ok=True)
    tdd.write_bytes(content)
    return bind_tdd(
        tdd,
        output=output or tmp_path / f"{tdd.stem}.binding.json",
        receipt=tmp_path / f"{tdd.stem}.receipt.json",
        cwd=tmp_path,
        state_root=tmp_path / "state",
    )


def test_task_identity_uses_slug_and_short_digest_suffix() -> None:
    digest = "0123456789abcdef" * 4

    assert slugify("Résumé: Harness Binding!") == "resume-harness-binding"
    assert derive_task_id("Harness Binding", digest) == "harness-binding-0123456789ab"


def test_task_identity_reads_heading_and_falls_back_to_filename(tmp_path: Path) -> None:
    heading = _bind(tmp_path, "heading.md", b"Setext Title\n============\n")
    fallback = _bind(tmp_path, "filename fallback.md", b"No heading here.\n")

    assert heading.tdd_title == "Setext Title"
    assert heading.task_id is not None and heading.task_id.startswith("setext-title-")
    assert fallback.tdd_title == "filename fallback"
    assert fallback.task_id is not None and fallback.task_id.startswith("filename-fallback-")


def test_binding_uses_canonical_task_evidence_and_exact_snapshot(tmp_path: Path) -> None:
    content = b"# Example Harness TDD\n\nExact bytes.\n"
    result = _bind(tmp_path, "docs/example.md", content)

    assert result.status == "ready"
    assert result.task_id is not None
    canonical = tmp_path / "state" / result.task_id / "spec" / "tdd-binding.json"
    snapshot = tmp_path / "state" / result.task_id / "spec" / "tdd-snapshot.md"
    assert Path(cast_str(result.canonical_binding_path)) == canonical
    assert Path(cast_str(result.tdd_snapshot_path)) == snapshot
    assert snapshot.read_bytes() == content
    assert (
        json.loads(canonical.read_text(encoding="utf-8"))["tdd_sha256"]
        == hashlib.sha256(content).hexdigest()
    )
    assert json.loads(
        (tmp_path / "example.binding.json").read_text(encoding="utf-8")
    ) == json.loads(canonical.read_text(encoding="utf-8"))


def test_relative_output_path_does_not_break_index_lookup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    result = _bind(
        tmp_path,
        "copy.md",
        b"# Relative output\n",
        output=Path("state-output/binding.json"),
    )

    found = lookup_tdd_bindings(Path("state"), tdd_path="copy.md")

    assert result.status == "ready"
    assert [item.task_id for item in found] == [result.task_id]


def test_index_rebuilds_when_missing_or_stale_and_canonical_bindings_win(tmp_path: Path) -> None:
    result = _bind(tmp_path, "one.md", b"# One\n")
    index_path = tmp_path / "state" / "tdd-index.json"
    index_path.unlink()

    found = lookup_tdd_bindings(tmp_path / "state", tdd_path="one.md")
    assert [item.task_id for item in found] == [result.task_id]

    index_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "by_tdd_path": {"one.md": "wrong-task"},
                "by_tdd_sha256": {},
                "by_task_id": {"wrong-task": "missing.json"},
                "diagnostics": [],
            }
        ),
        encoding="utf-8",
    )
    rebuilt = rebuild_tdd_index(tmp_path / "state")
    assert rebuilt.by_tdd_path["one.md"] == result.task_id
    assert lookup_tdd_bindings(tmp_path / "state", tdd_path="one.md")[0].task_id == result.task_id


def test_same_digest_can_bind_to_different_paths_when_identity_is_distinct(tmp_path: Path) -> None:
    content = b"Shared content without a heading.\n"
    first = _bind(tmp_path, "first.md", content)
    second = _bind(tmp_path, "second.md", content)

    assert first.status == second.status == "ready"
    assert first.tdd_sha256 == second.tdd_sha256
    assert first.task_id != second.task_id
    index = json.loads((tmp_path / "state" / "tdd-index.json").read_text(encoding="utf-8"))
    assert index["by_tdd_sha256"][cast_str(first.tdd_sha256)] == sorted(
        [cast_str(first.task_id), cast_str(second.task_id)]
    )


def test_same_title_and_digest_at_different_paths_blocks_task_identity_collision(
    tmp_path: Path,
) -> None:
    content = b"# Shared TDD\n\nSame exact content.\n"
    first = _bind(tmp_path, "first.md", content)
    second = _bind(tmp_path, "second.md", content)

    assert first.status == "ready"
    assert second.status == "blocked"
    assert second.task_id == first.task_id
    assert second.diagnostics[0].code == "tdd_binding.task_id_collision"


def test_path_drift_preserves_the_original_snapshot_and_binding(tmp_path: Path) -> None:
    original = b"# Original\n"
    first = _bind(tmp_path, "drift.md", original)
    tdd = tmp_path / "drift.md"
    tdd.write_bytes(b"# Changed\n")
    drifted = bind_tdd(
        tdd,
        output=tmp_path / "changed.binding.json",
        receipt=tmp_path / "changed.receipt.json",
        cwd=tmp_path,
        state_root=tmp_path / "state",
    )

    assert drifted.status == "blocked"
    assert drifted.diagnostics[0].code == "tdd_binding.digest_conflict"
    assert drifted.tdd_sha256 != first.tdd_sha256
    assert Path(cast_str(first.tdd_snapshot_path)).read_bytes() == original
    assert not (tmp_path / "changed.binding.json").exists()


def test_binding_rejects_corrupt_snapshot_and_canonical_binding(tmp_path: Path) -> None:
    result = _bind(tmp_path, "corrupt.md", b"# Corrupt\n")
    snapshot = Path(cast_str(result.tdd_snapshot_path))
    snapshot.write_bytes(b"tampered")

    repeated = bind_tdd(
        tmp_path / "corrupt.md",
        output=tmp_path / "repeat.binding.json",
        receipt=tmp_path / "repeat.receipt.json",
        cwd=tmp_path,
        state_root=tmp_path / "state",
    )
    assert repeated.status == "blocked"
    assert repeated.diagnostics[0].code == "tdd_binding.invalid_canonical_binding"
    with pytest.raises(TddBindingError, match="digest"):
        read_tdd_binding(Path(cast_str(result.canonical_binding_path)))


def test_binding_rejects_existing_output_or_receipt_that_attests_to_other_data(
    tmp_path: Path,
) -> None:
    output = tmp_path / "binding.json"
    receipt = tmp_path / "receipt.json"
    output.write_text("{}\n", encoding="utf-8")
    blocked_output = bind_tdd(
        tmp_path / "new.md",
        output=output,
        receipt=receipt,
        cwd=tmp_path,
        state_root=tmp_path / "state",
    )
    assert blocked_output.status == "blocked"
    assert blocked_output.diagnostics[0].code == "tdd_path.unreadable"

    tdd = tmp_path / "new.md"
    tdd.write_text("# New\n", encoding="utf-8")
    blocked_output = bind_tdd(
        tdd,
        output=output,
        receipt=receipt,
        cwd=tmp_path,
        state_root=tmp_path / "state",
    )
    assert blocked_output.diagnostics[0].code == "tdd_binding.output_conflict"
    assert not (tmp_path / "state").exists()

    output.unlink()
    receipt.write_text("{}\n", encoding="utf-8")
    blocked_receipt = bind_tdd(
        tdd,
        output=output,
        receipt=receipt,
        cwd=tmp_path,
        state_root=tmp_path / "state",
    )
    assert blocked_receipt.diagnostics[0].code == "tdd_binding.receipt_conflict"
    assert not (tmp_path / "state").exists()


def test_rebuild_blocks_a_canonical_record_outside_its_task_evidence_directory(
    tmp_path: Path,
) -> None:
    result = _bind(tmp_path, "one.md", b"# One\n")
    canonical = Path(cast_str(result.canonical_binding_path))
    duplicate = tmp_path / "state" / "another-task" / "spec" / "tdd-binding.json"
    duplicate.parent.mkdir(parents=True)
    duplicate.write_text(canonical.read_text(encoding="utf-8"), encoding="utf-8")

    with pytest.raises(TddBindingError, match="task evidence directory"):
        rebuild_tdd_index(tmp_path / "state")


def test_output_and_receipt_cannot_alias_canonical_state(tmp_path: Path) -> None:
    tdd = tmp_path / "alias.md"
    tdd.write_text("# Alias\n", encoding="utf-8")
    digest = hashlib.sha256(tdd.read_bytes()).hexdigest()
    task_id = derive_task_id("Alias", digest)
    canonical = tmp_path / "state" / task_id / "spec" / "tdd-binding.json"
    result = bind_tdd(
        tdd,
        output=canonical,
        receipt=tmp_path / "receipt.json",
        cwd=tmp_path,
        state_root=tmp_path / "state",
    )

    assert result.status == "blocked"
    assert result.diagnostics[0].code == "tdd_binding.destination_conflict"


def cast_str(value: str | None) -> str:
    assert value is not None
    return value
