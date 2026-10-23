"""Current regression tests for the frozen R17 digest boundary.

The frozen verifier (`data/r17-semantic-selection-contract/verify_policy_records.py`)
re-runs the live R4 composer and requires byte-identical composition probes. That
reproducibility bound is historical, not regression protection for the current
(R19) composer: it reproduces only in the isolated pinned-checkout command
`scripts/run_r17_historical_reproduction.sh` (see `docs/CHECK_PLAN.md`).

These current tests verify the digest boundary directly — the frozen R17 result
files, the reviewed-contract and approval evidence, and the verifier manifest are
byte-identical to their recorded SHA-256 digests — without invoking the changed
composer and without silently skipping a failure.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = REPO_ROOT / "data/r17-semantic-selection-contract"

LIVING_TDD = "docs/2026-10-07-semantic-selection-contract.md"
LIVING_REVIEW = "docs/2026-10-07-semantic-selection-policy-review.md"


def _verify_handle(handle: dict[str, str]) -> Path:
    path = (REPO_ROOT / handle["path"]).resolve()
    assert path.is_relative_to(REPO_ROOT), f"Handle escapes the repository: {handle['path']}"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == handle["sha256"], (
        f"File digest drift: {handle['path']}"
    )
    return path


def test_frozen_result_files_match_checksums() -> None:
    checksums = json.loads((DATA_DIR / "checksums.json").read_text())
    assert checksums["schema_version"] == "r17_policy_review_checksums_v1"
    assert checksums["status"] == "contract_frozen"
    assert checksums["acceptance_evidence"] is True
    for handle in checksums["files"]:
        _verify_handle(handle)


def test_frozen_verifier_manifest_binds_the_verifier() -> None:
    manifest = json.loads((DATA_DIR / "implementation_checksums.json").read_text())
    assert manifest["schema_version"] == "r17_implementation_checksums_v1"
    assert manifest["status"] == "contract_frozen"
    assert [handle["path"] for handle in manifest["files"]] == [
        "data/r17-semantic-selection-contract/verify_policy_records.py"
    ]
    for handle in manifest["files"]:
        _verify_handle(handle)


def test_reviewed_contract_spec_and_approval_are_digest_bound() -> None:
    records = json.loads((DATA_DIR / "reference_policy_records.json").read_text())
    _verify_handle(records["human_approval"])
    approval = json.loads(_verify_handle(records["human_approval"]).read_text())
    _verify_handle(approval["reviewed_contract_spec"])


def test_digest_closure_excludes_living_docs() -> None:
    checksums = json.loads((DATA_DIR / "checksums.json").read_text())
    implementation = json.loads((DATA_DIR / "implementation_checksums.json").read_text())
    bound_paths = {handle["path"] for handle in checksums["files"]}
    bound_paths.update(handle["path"] for handle in implementation["files"])

    records = json.loads((DATA_DIR / "reference_policy_records.json").read_text())
    assert "contract_spec" not in records

    assert LIVING_TDD not in bound_paths
    assert LIVING_REVIEW not in bound_paths
    assert all(not path.startswith("docs/") for path in bound_paths)
