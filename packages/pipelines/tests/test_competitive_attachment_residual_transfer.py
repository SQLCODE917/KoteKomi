from __future__ import annotations

import hashlib
import importlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from kotekomi_application import (
    AttachmentResidualTransferObservation,
    AttachmentResidualTransferOutcome,
)
from kotekomi_pipelines.competitive_attachment_residual_transfer import (
    classify_residual_transfer_outcome,
    select_residual_transfer_threshold,
)

ROOT = Path(__file__).resolve().parents[3]


def _runner() -> Any:
    scripts_path = str(ROOT / "scripts")
    if scripts_path not in sys.path:
        sys.path.insert(0, scripts_path)
    return importlib.import_module("run_competitive_attachment_residual_transfer")


def test_threshold_prefers_specificity_when_accuracy_ties() -> None:
    scores = (
        (4.71477585317935, "Y"),
        (2.225679173040638, "Y"),
        (7.538867823036009, "Y"),
        (0.742627070124795, "Y"),
        (-5.000503462291326, "Y"),
        (8.896987431487899, "Y"),
        (-8.536483798151743, "N"),
        (4.92358672979596, "Y"),
        (0.37559119754594983, "N"),
        (5.186837124947065, "Y"),
    )
    observations = cast(
        tuple[AttachmentResidualTransferObservation, ...],
        tuple(
            SimpleNamespace(
                repetition=repetition,
                expected_answer=expected,
                evidence=SimpleNamespace(attachment_score=score),
            )
            for repetition in (1, 2)
            for score, expected in scores
        ),
    )

    assert (
        select_residual_transfer_threshold(observations)
        == (0.37559119754594983 + 0.742627070124795) / 2
    )


@pytest.mark.parametrize(
    (
        "strict_count",
        "stable_count",
        "threshold_accuracy",
        "literal_accuracy",
        "false_positives",
        "expected",
    ),
    (
        (13, 7, 1.0, 1.0, 0, AttachmentResidualTransferOutcome.INCONCLUSIVE),
        (14, 7, 6 / 7, 5 / 7, 0, AttachmentResidualTransferOutcome.SUPPORTED),
        (14, 7, 5 / 7, 5 / 7, 0, AttachmentResidualTransferOutcome.MIXED),
        (14, 7, 5 / 7, 6 / 7, 0, AttachmentResidualTransferOutcome.FALSIFIED),
        (14, 7, 6 / 7, 5 / 7, 1, AttachmentResidualTransferOutcome.FALSIFIED),
    ),
)
def test_terminal_outcome_contract(
    strict_count: int,
    stable_count: int,
    threshold_accuracy: float,
    literal_accuracy: float,
    false_positives: int,
    expected: AttachmentResidualTransferOutcome,
) -> None:
    metric = SimpleNamespace(
        accuracy=threshold_accuracy,
        false_positive_count=false_positives,
    )
    literal = SimpleNamespace(accuracy=literal_accuracy)
    validation = cast(
        Any,
        SimpleNamespace(
            strict_observation_count=strict_count,
            stable_case_count=stable_count,
            threshold_metrics=(metric, metric),
            literal_metrics=(literal, literal),
        ),
    )

    assert classify_residual_transfer_outcome(validation) is expected


def test_validation_lineage_recovers_root_omitted_by_development_only_successor(
    tmp_path: Path,
) -> None:
    runner = _runner()
    validation_root = tmp_path / "validation"
    calibration_root = tmp_path / "calibration"
    residual_root = tmp_path / "residual"
    for path in (validation_root, calibration_root, residual_root):
        path.mkdir()
    files = {
        validation_root / "run.json": b'{"phase":"validation"}\n',
        validation_root / "canonical-state.json": b"{}\n",
        validation_root / "inputs.jsonl": b'{"phase":"validation"}\n',
    }
    for path, contents in files.items():
        path.write_bytes(contents)
    (calibration_root / "run.json").write_text(
        json.dumps(
            {
                "schema_version": "attachment_calibration_run_v1",
                "status": "diagnostic_complete",
                "validation_run_root": str(validation_root),
            }
        )
    )
    (residual_root / "run.json").write_text(
        json.dumps(
            {
                "schema_version": "attachment_residual_ownership_run_v1",
                "status": "complete",
                "calibration_root": str(calibration_root),
                "validation_run_root": str(validation_root),
            }
        )
    )

    observed_root, references = runner._validation_evidence_lineage(residual_root)

    assert observed_root == validation_root
    assert {item.label for item in references} == {
        "calibration_run",
        "residual_run",
        "validation_canonical_state",
        "validation_inputs",
        "validation_run",
    }
    assert all(
        item.sha256 == hashlib.sha256(Path(item.path).read_bytes()).hexdigest()
        for item in references
    )


def test_validation_lineage_rejects_disagreeing_upstream_roots(tmp_path: Path) -> None:
    runner = _runner()
    calibration_root = tmp_path / "calibration"
    residual_root = tmp_path / "residual"
    calibration_root.mkdir()
    residual_root.mkdir()
    (calibration_root / "run.json").write_text(
        json.dumps(
            {
                "schema_version": "attachment_calibration_run_v1",
                "status": "diagnostic_complete",
                "validation_run_root": str(tmp_path / "calibration-validation"),
            }
        )
    )
    (residual_root / "run.json").write_text(
        json.dumps(
            {
                "schema_version": "attachment_residual_ownership_run_v1",
                "status": "complete",
                "calibration_root": str(calibration_root),
                "validation_run_root": str(tmp_path / "residual-validation"),
            }
        )
    )

    with pytest.raises(ValueError, match="validation evidence roots disagree"):
        runner._validation_evidence_lineage(residual_root)
