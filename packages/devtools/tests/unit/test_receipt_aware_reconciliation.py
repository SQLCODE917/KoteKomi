from __future__ import annotations

import json
from pathlib import Path

import pytest
from kotekomi_devtools.feature_branch_reconciliation import (
    FeatureBranchReconciliationError,
    verified_merge_parent,
)


def _receipt_entries(tmp_path: Path, payload: dict[str, str]) -> list[dict[str, str]]:
    path = tmp_path / "receipt.json"
    path.write_text(json.dumps(payload))
    return [
        {
            "evidence_type": "candidate_verification_receipt",
            "subject_id": "portable-local",
            "path_scope": "state",
            "path": "receipt.json",
        }
    ]


def test_direct_candidate_is_the_verified_merge_parent(tmp_path: Path) -> None:
    parent = verified_merge_parent(tmp_path, [], "candidate", "specification", "candidate")

    assert parent == "candidate"


def test_passed_bound_portable_receipt_is_the_verified_merge_parent(tmp_path: Path) -> None:
    entries = _receipt_entries(
        tmp_path,
        {
            "outcome": "passed",
            "receipt_commit": "receipt",
            "candidate_revision": "candidate",
            "specification_revision": "specification",
        },
    )

    parent = verified_merge_parent(tmp_path, entries, "candidate", "specification", "receipt")

    assert parent == "receipt"


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        (
            {
                "outcome": "failed",
                "receipt_commit": "receipt",
                "candidate_revision": "candidate",
                "specification_revision": "specification",
            },
            "portable receipt outcome must be passed",
        ),
        (
            {
                "outcome": "passed",
                "receipt_commit": "receipt",
                "candidate_revision": "other",
                "specification_revision": "specification",
            },
            "portable receipt candidate revision must equal candidate commit",
        ),
        (
            {
                "outcome": "passed",
                "receipt_commit": "receipt",
                "candidate_revision": "candidate",
                "specification_revision": "other",
            },
            "portable receipt specification revision must equal specification evidence",
        ),
    ],
)
def test_unbound_portable_receipts_are_rejected(
    tmp_path: Path, payload: dict[str, str], message: str
) -> None:
    entries = _receipt_entries(tmp_path, payload)

    with pytest.raises(FeatureBranchReconciliationError, match=message):
        verified_merge_parent(tmp_path, entries, "candidate", "specification", "receipt")
