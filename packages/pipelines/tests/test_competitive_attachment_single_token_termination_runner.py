from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from kotekomi_application import (
    AttachmentSingleTokenOutcome,
    AttachmentSingleTokenPackageStatus,
    AttachmentSingleTokenReport,
)

ROOT = Path(__file__).resolve().parents[3]
DIGEST = "a" * 64


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


def test_model_identity_comes_from_ready_admission_without_a_response_receipt() -> None:
    runner = _runner()
    model_run = SimpleNamespace(
        input_admission=SimpleNamespace(
            status=SimpleNamespace(value="ready"),
            model_identity_digest=DIGEST,
        )
    )

    assert runner._admitted_model_identity_digest(model_run) == DIGEST


def test_model_identity_rejects_an_attempt_without_ready_admission() -> None:
    runner = _runner()

    with pytest.raises(ValueError, match="ready input admission"):
        runner._admitted_model_identity_digest(SimpleNamespace(input_admission=None))


def test_finalize_does_not_dispatch_model_execution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = _runner()
    executions: list[bool] = []

    def fake_run_or_finalize(_args: object, *, execute: bool) -> int:
        executions.append(execute)
        return 0

    monkeypatch.setattr(runner, "_run_or_finalize", fake_run_or_finalize)

    assert runner._finalize(SimpleNamespace()) == 0
    assert executions == [False]
