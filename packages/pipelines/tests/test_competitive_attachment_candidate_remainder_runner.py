from __future__ import annotations

import hashlib
import importlib
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

from kotekomi_application import (
    AttachmentCandidateRemainderOutcome,
    AttachmentCandidateRemainderPackageStatus,
    AttachmentCandidateRemainderPreflight,
    AttachmentCandidateRemainderReport,
)

ROOT = Path(__file__).resolve().parents[3]


def _runner() -> Any:
    scripts_path = str(ROOT / "scripts")
    if scripts_path not in sys.path:
        sys.path.insert(0, scripts_path)
    return importlib.import_module("run_competitive_attachment_candidate_remainder")


def test_preflight_metadata_separates_dto_fingerprint_from_file_digest(
    tmp_path: Path,
) -> None:
    runner = _runner()
    path = tmp_path / "preflight.json"
    path.write_text('{"serialized":"evidence"}\n', encoding="utf-8")
    preflight = cast(
        AttachmentCandidateRemainderPreflight,
        SimpleNamespace(result_fingerprint="a" * 64),
    )

    metadata = runner._preflight_evidence_metadata(preflight, path)

    assert metadata == {
        "preflight_fingerprint": "a" * 64,
        "preflight_file_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }
    assert metadata["preflight_fingerprint"] != metadata["preflight_file_sha256"]


def test_complete_status_exposes_review_and_second_opinion_paths(tmp_path: Path) -> None:
    runner = _runner()
    report = cast(
        AttachmentCandidateRemainderReport,
        SimpleNamespace(
            outcome=AttachmentCandidateRemainderOutcome.SUPPORTED,
            model_execution_count=20,
        ),
    )

    status = runner._status(
        tmp_path,
        AttachmentCandidateRemainderPackageStatus.COMPLETE,
        report=report,
    )

    assert status.report_path == str(tmp_path / "report.json")
    assert status.review_path == str(tmp_path / "comparison-review.md")
    assert status.handoff_path == str(tmp_path / "second-opinion-handoff.md")
    assert status.claude_review_path == str(tmp_path / "claude-opus-review.md")
    assert status.model_execution_count == 20
