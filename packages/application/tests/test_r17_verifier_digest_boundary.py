"""Regression tests for the R17 frozen-record verifier digest boundary.

The freeze boundary binds approval evidence and data artifacts by digest while
living TDD/review write-ups under `docs/` stay edit-safe. These tests exercise
`data/r17-semantic-selection-contract/verify_policy_records.py` against a
throwaway copy of the frozen tree so the repository's frozen files are never
mutated in place.
"""

import contextlib
import hashlib
import importlib.util
import io
import json
import re
import shutil
import types
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = REPO_ROOT / "data/r17-semantic-selection-contract"
VERIFIER_PATH = DATA_DIR / "verify_policy_records.py"

LIVING_TDD = "docs/2026-10-07-semantic-selection-contract.md"
LIVING_REVIEW = "docs/2026-10-07-semantic-selection-policy-review.md"
PASS_MARKER = "mechanically_valid_frozen_semantic_selection_contract"

_PATH_REFERENCE = re.compile(r'"path":\s*"((?:data/)[^"]+)"')


@dataclass
class VerifierTree:
    module: types.ModuleType
    root: Path
    data: Path


def _load_verifier() -> types.ModuleType:
    spec = importlib.util.spec_from_file_location("r17_verifier_policy_records", VERIFIER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _copy_referenced_data(root: Path) -> None:
    """Mirror every out-of-directory `data/` path the frozen verifier reads."""
    referenced: set[str] = set()
    for file in DATA_DIR.rglob("*.json"):
        for match in _PATH_REFERENCE.findall(file.read_text()):
            if not match.startswith("data/r17-semantic-selection-contract/"):
                referenced.add(match)
    for rel in referenced:
        source = REPO_ROOT / rel
        if not source.exists():
            continue
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(source, target)


@pytest.fixture()
def verifier(tmp_path: Path) -> VerifierTree:
    root = tmp_path / "repo"
    data = root / "data/r17-semantic-selection-contract"
    shutil.copytree(DATA_DIR, data)
    _copy_referenced_data(root)

    docs = root / "docs"
    docs.mkdir()
    for name in (
        "2026-10-07-semantic-selection-contract.md",
        "2026-10-07-semantic-selection-policy-review.md",
    ):
        shutil.copy(REPO_ROOT / "docs" / name, docs / name)

    module: Any = _load_verifier()
    # Point the verifier at the throwaway tree by overriding its module globals.
    module.ROOT = root.resolve()
    module.DIRECTORY = data.resolve()
    return VerifierTree(module, root.resolve(), data.resolve())


def _run(tree: VerifierTree) -> str:
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        tree.module.main()
    return buffer.getvalue()


def test_frozen_baseline_verifies(verifier: VerifierTree) -> None:
    assert PASS_MARKER in _run(verifier)


def test_living_doc_navigation_and_prose_edits_remain_valid(verifier: VerifierTree) -> None:
    tdd = verifier.root / LIVING_TDD
    review = verifier.root / LIVING_REVIEW
    tdd.write_text(tdd.read_text() + "\n- Navigation note for the R18 plan.\n")
    review.write_text(review.read_text() + "\n\nProse edit outside the digest boundary.\n")
    assert PASS_MARKER in _run(verifier)


def test_digest_closure_excludes_living_docs(verifier: VerifierTree) -> None:
    checksums = json.loads((verifier.data / "checksums.json").read_text())
    implementation = json.loads((verifier.data / "implementation_checksums.json").read_text())
    bound_paths = {handle["path"] for handle in checksums["files"]}
    bound_paths.update(handle["path"] for handle in implementation["files"])

    records = json.loads((verifier.data / "reference_policy_records.json").read_text())
    assert "contract_spec" not in records

    assert LIVING_TDD not in bound_paths
    assert LIVING_REVIEW not in bound_paths
    assert all(not path.startswith("docs/") for path in bound_paths)


def test_frozen_reviewed_contract_spec_change_fails(verifier: VerifierTree) -> None:
    spec = verifier.data / "reviewed_contract_spec.md"
    spec.write_text(spec.read_text() + "\nTampered approval evidence.\n")
    with pytest.raises(ValueError):
        verifier.module.main()


def test_frozen_input_change_fails(verifier: VerifierTree) -> None:
    fixture = verifier.data / "inputs/AHE-022.json"
    payload = json.loads(fixture.read_text())
    payload["source_text"] = payload["source_text"] + " TAMPERED"
    fixture.write_text(json.dumps(payload, indent=2) + "\n")
    with pytest.raises(ValueError):
        verifier.module.main()


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_implementation_manifest(tree: VerifierTree, manifest: dict[str, Any]) -> None:
    (tree.data / "implementation_checksums.json").write_text(json.dumps(manifest, indent=2) + "\n")


def test_empty_implementation_manifest_fails(verifier: VerifierTree) -> None:
    manifest = json.loads((verifier.data / "implementation_checksums.json").read_text())
    manifest["files"] = []
    _write_implementation_manifest(verifier, manifest)
    with pytest.raises(ValueError):
        verifier.module.main()


def test_missing_verifier_entry_fails(verifier: VerifierTree) -> None:
    manifest = json.loads((verifier.data / "implementation_checksums.json").read_text())
    manifest["files"] = [
        {
            "path": "data/r17-semantic-selection-contract/reviewed_contract_spec.md",
            "sha256": _file_sha256(verifier.data / "reviewed_contract_spec.md"),
        }
    ]
    _write_implementation_manifest(verifier, manifest)
    with pytest.raises(ValueError):
        verifier.module.main()


def test_invalid_implementation_status_fails(verifier: VerifierTree) -> None:
    manifest = json.loads((verifier.data / "implementation_checksums.json").read_text())
    manifest["status"] = "not_frozen"
    _write_implementation_manifest(verifier, manifest)
    with pytest.raises(ValueError):
        verifier.module.main()


def test_verifier_byte_drift_fails(verifier: VerifierTree) -> None:
    implementation = verifier.data / "verify_policy_records.py"
    implementation.write_text(implementation.read_text() + "\n# tampered verifier byte\n")
    with pytest.raises(ValueError):
        verifier.module.main()
