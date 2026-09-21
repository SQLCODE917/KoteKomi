from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from kotekomi_application import (
    AttachmentCalibratedTerminationOutcome,
    AttachmentCalibratedTerminationPackageStatus,
    AttachmentCalibratedTerminationReport,
)

ROOT = Path(__file__).resolve().parents[3]


def _runner() -> Any:
    scripts_path = str(ROOT / "scripts")
    if scripts_path not in sys.path:
        sys.path.insert(0, scripts_path)
    return importlib.import_module("run_competitive_attachment_runtime_calibrated_termination")


def test_complete_status_exposes_mechanism_and_review_paths(tmp_path: Path) -> None:
    runner = _runner()
    report = cast(
        AttachmentCalibratedTerminationReport,
        SimpleNamespace(
            outcome=AttachmentCalibratedTerminationOutcome.SUPPORTED,
            mechanism_proof=True,
            model_execution_count=20,
        ),
    )

    status = runner._status(
        tmp_path,
        AttachmentCalibratedTerminationPackageStatus.COMPLETE,
        report=report,
    )

    assert status.report_path == str(tmp_path / "report.json")
    assert status.review_path == str(tmp_path / "comparison-review.md")
    assert status.handoff_path == str(tmp_path / "second-opinion-handoff.md")
    assert status.claude_review_path == str(tmp_path / "claude-opus-review.md")
    assert status.mechanism_proof is True
    assert status.production_suitability == "unmet"


def test_probe_validation_requires_observed_zero_one_two_three_pattern(
    tmp_path: Path,
) -> None:
    runner = _runner()
    (tmp_path / "one-token-response-probe-request.json").write_text(
        json.dumps({"max_output_tokens": 1}),
        encoding="utf-8",
    )
    terminal: dict[str, object] = {
        "type": "response.completed",
        "response": {"output": [], "usage": {"output_tokens": 0}},
    }
    (tmp_path / "one-token-response-probe-response.sse").write_text(
        "data: " + json.dumps(terminal) + "\n",
        encoding="utf-8",
    )
    for limit, count in ((2, 1), (3, 2), (4, 3)):
        (tmp_path / f"output-limit-{limit}-summary.json").write_text(
            json.dumps(
                {
                    "max_output_tokens": limit,
                    "output": [{"content": [{"text": "Y"}]}],
                    "usage": {"output_tokens": count},
                }
            ),
            encoding="utf-8",
        )
    distribution = {"position": 0, "token": "Y"}
    for name in ("archived-limit-8-position-0.json", "probe-limit-2-position-0.json"):
        (tmp_path / name).write_text(json.dumps(distribution), encoding="utf-8")

    runner._validate_probe_evidence(tmp_path)

    (tmp_path / "output-limit-4-summary.json").write_text(
        json.dumps(
            {
                "max_output_tokens": 4,
                "output": [{"content": [{"text": "Y"}]}],
                "usage": {"output_tokens": 4},
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="limit-4 probe output count"):
        runner._validate_probe_evidence(tmp_path)


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
