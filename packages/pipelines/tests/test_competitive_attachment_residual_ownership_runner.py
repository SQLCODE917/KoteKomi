from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

from kotekomi_application import (
    AttachmentResidualOwnershipOutcome,
    AttachmentResidualOwnershipPackageStatus,
    AttachmentResidualOwnershipReport,
)

ROOT = Path(__file__).resolve().parents[3]


def _runner() -> Any:
    scripts_path = str(ROOT / "scripts")
    if scripts_path not in sys.path:
        sys.path.insert(0, scripts_path)
    return importlib.import_module("run_competitive_attachment_residual_ownership")


def test_prepared_status_contains_no_terminal_result_paths(tmp_path: Path) -> None:
    runner = _runner()

    status = runner._status(tmp_path, AttachmentResidualOwnershipPackageStatus.PREPARED)

    assert status.status is AttachmentResidualOwnershipPackageStatus.PREPARED
    assert status.report_path is None
    assert status.handoff_path is None
    assert status.model_execution_count == 0


def test_complete_status_reports_human_run_claude_review_path(tmp_path: Path) -> None:
    runner = _runner()
    report = cast(
        AttachmentResidualOwnershipReport,
        SimpleNamespace(
            outcome=AttachmentResidualOwnershipOutcome.SUPPORTED,
            model_execution_count=20,
        ),
    )

    status = runner._status(
        tmp_path,
        AttachmentResidualOwnershipPackageStatus.COMPLETE,
        report=report,
    )

    assert status.report_path == str(tmp_path / "report.json")
    assert status.review_path == str(tmp_path / "diagnostic-review.md")
    assert status.handoff_path == str(tmp_path / "second-opinion-handoff.md")
    assert status.claude_review_path == str(tmp_path / "claude-opus-review.md")
    assert status.model_execution_count == 20


def test_residual_prompt_uses_plain_task_terms() -> None:
    prompt = (ROOT / "prompts/competitive_attachment_residual_ownership_v1.md").read_text()

    assert "The Candidate is" in prompt
    assert "The Target Event is" in prompt
    assert "Return exactly one answer character" in prompt
    assert "KoteKomi" not in prompt
