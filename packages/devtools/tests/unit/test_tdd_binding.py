import hashlib
import json
from pathlib import Path

from kotekomi_devtools.tdd_binding import bind_tdd, derive_task_id, lookup_tdd_binding, slugify


def test_identity_slug_and_digest_suffix() -> None:
    assert slugify("Résumé: Harness") == "resume-harness"
    assert derive_task_id("Harness", "a" * 64) == "harness-aaaaaaaaaaaa"


def test_binding_writes_snapshot_revision_receipt_and_index(tmp_path: Path) -> None:
    path = tmp_path / "docs" / "one.md"
    path.parent.mkdir()
    content = b"# One\n"
    path.write_bytes(content)
    result = bind_tdd(path, cwd=tmp_path, state_root=tmp_path / "state")
    assert result.status == "ready"
    payload = result.as_json()
    task = str(payload["task_id"])
    assert (
        tmp_path / "state" / "experiments" / task / "spec" / "tdd-snapshot.md"
    ).read_bytes() == content
    assert Path(str(payload["latest_binding_revision_path"])).is_file()
    assert Path(str(payload["latest_binding_receipt_path"])).is_file()
    index = json.loads((tmp_path / "state" / "tdds" / "index.json").read_text())
    assert index["by_tdd_sha256"][hashlib.sha256(content).hexdigest()] == task


def test_equal_content_adds_alias_and_revision(tmp_path: Path) -> None:
    root = tmp_path / "state"
    first = tmp_path / "one.md"
    second = tmp_path / "two.md"
    first.write_text("# Same\n")
    second.write_text("# Same\n")
    original = bind_tdd(first, cwd=tmp_path, state_root=root)
    alias = bind_tdd(second, cwd=tmp_path, state_root=root)
    assert alias.status == "ready" and alias.binding is not None
    assert alias.binding["task_id"] == original.binding["task_id"]
    assert alias.binding["tdd_paths"] == ["one.md", "two.md"]
    assert alias.binding["latest_binding_revision"] == 2


def test_drift_blocks_and_preserves_binding(tmp_path: Path) -> None:
    path = tmp_path / "one.md"
    path.write_text("# One\n")
    root = tmp_path / "state"
    first = bind_tdd(path, cwd=tmp_path, state_root=root)
    path.write_text("# Changed\n")
    changed = bind_tdd(path, cwd=tmp_path, state_root=root)
    assert changed.status == "blocked"
    assert lookup_tdd_binding(root, tdd_path="one.md")["tdd_sha256"] == first.binding["tdd_sha256"]
