from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

from kotekomi_application import (
    AttachmentSingleTokenOutcome,
    AttachmentSingleTokenPackageStatus,
    AttachmentSingleTokenReport,
)

ROOT = Path(__file__).resolve().parents[3]


def _runner() -> Any:
    scripts_path = str(ROOT / "scripts")
    if scripts_path not in sys.path:
        sys.path.insert(0, scripts_path)
    return importlib.import_module("run_competitive_attachment_single_token_termination")


def test_complete_status_exposes_review_and_second_opinion_paths(tmp_path: Path) -> None:
    runner = _runner()
    report = cast(
        AttachmentSingleTokenReport,
        SimpleNamespace(
            outcome=AttachmentSingleTokenOutcome.SUPPORTED,
            model_execution_count=20,
        ),
    )

    status = runner._status(
        tmp_path,
        AttachmentSingleTokenPackageStatus.COMPLETE,
        report=report,
    )

    assert status.report_path == str(tmp_path / "report.json")
    assert status.review_path == str(tmp_path / "comparison-review.md")
    assert status.handoff_path == str(tmp_path / "second-opinion-handoff.md")
    assert status.claude_review_path == str(tmp_path / "claude-opus-review.md")
    assert status.model_execution_count == 20
