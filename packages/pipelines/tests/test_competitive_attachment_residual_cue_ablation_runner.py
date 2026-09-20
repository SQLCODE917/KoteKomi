from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

from kotekomi_application import (
    AttachmentResidualCueAblationOutcome,
    AttachmentResidualCueAblationPackageStatus,
    AttachmentResidualCueAblationReport,
)

ROOT = Path(__file__).resolve().parents[3]


def _runner() -> Any:
    scripts_path = str(ROOT / "scripts")
    if scripts_path not in sys.path:
        sys.path.insert(0, scripts_path)
    return importlib.import_module("run_competitive_attachment_residual_cue_ablation")


def test_cue_ablation_prompt_is_plain_and_balances_the_other_event_cue() -> None:
    prompt = (ROOT / "prompts/competitive_attachment_residual_ownership_v2.md").read_text()

    assert 'E1: "arrived"' in prompt
    assert "Answer: `Y`" in prompt
    assert "KoteKomi" not in prompt


def test_complete_status_exposes_human_run_review_paths(tmp_path: Path) -> None:
    runner = _runner()
    report = cast(
        AttachmentResidualCueAblationReport,
        SimpleNamespace(
            outcome=AttachmentResidualCueAblationOutcome.SUPPORTED,
            model_execution_count=20,
        ),
    )

    status = runner._status(
        tmp_path,
        AttachmentResidualCueAblationPackageStatus.COMPLETE,
        report=report,
    )

    assert status.comparison_report_path == str(tmp_path / "comparison-report.json")
    assert status.handoff_path == str(tmp_path / "second-opinion-handoff.md")
    assert status.claude_review_path == str(tmp_path / "claude-opus-review.md")
    assert status.model_execution_count == 20


def test_cue_ablation_binds_the_sealed_predecessor_package_without_flattening_inputs(
    tmp_path: Path,
) -> None:
    runner = _runner()
    baseline_root = tmp_path / "baseline"
    baseline_root.mkdir()
    for name in ("preflight.json", "report.json", "run.json", "status.json"):
        (baseline_root / name).write_text(f"{name}\n", encoding="utf-8")

    references = runner._sealed_package_inputs(baseline_root)

    assert tuple(item.label for item in references) == (
        "baseline_preflight",
        "baseline_report",
        "baseline_run",
        "baseline_status",
        "tdd",
    )
    assert all(not item.label.startswith("predecessor_") for item in references)
