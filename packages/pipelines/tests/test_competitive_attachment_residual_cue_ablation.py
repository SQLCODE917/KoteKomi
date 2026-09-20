from __future__ import annotations

import math
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest
from kotekomi_application import (
    AttachmentAnswerProbability,
    AttachmentEdgeFilterAnswerValue,
    AttachmentEdgeFilterDecisionStatus,
    AttachmentEvidenceReference,
    AttachmentResidualOwnershipReport,
)
from kotekomi_pipelines.competitive_attachment_residual_cue_ablation import (
    build_residual_cue_ablation_report,
    validate_residual_cue_prompt_pair,
)

ROOT = Path(__file__).resolve().parents[3]
DIGEST = "a" * 64


def test_cue_prompt_changes_only_the_positive_example() -> None:
    baseline = (ROOT / "prompts/competitive_attachment_residual_ownership_v1.md").read_text()
    cue = (ROOT / "prompts/competitive_attachment_residual_ownership_v2.md").read_text()

    validate_residual_cue_prompt_pair(baseline, cue)

    with pytest.raises(ValueError, match="outside the positive example"):
        validate_residual_cue_prompt_pair(baseline, cue + "Changed suffix.\n")


@pytest.mark.parametrize(
    ("mode", "expected_outcome"),
    (
        ("supported", "supported"),
        ("mixed", "mixed"),
        ("falsified", "falsified"),
        ("inconclusive", "inconclusive"),
    ),
)
def test_report_aligns_exact_cases_and_classifies_the_cue_effect(
    mode: str,
    expected_outcome: str,
) -> None:
    baseline_cases: list[object] = []
    cue_cases: list[object] = []
    probabilities: dict[tuple[str, int], AttachmentAnswerProbability | None] = {}
    for index in range(10):
        task_id = f"aro_{index + 1:024x}"
        expected = "Y" if index < 7 else "N"
        task = SimpleNamespace(
            id=task_id,
            edge_filter_task=SimpleNamespace(edge=SimpleNamespace(id=f"ape_{index + 1:024x}")),
        )
        baseline_cases.append(_case(task, expected, ("N", "N")))
        cue_answers: tuple[str | None, str | None] = ("N", "N")
        if index == 0 and mode == "supported":
            cue_answers = ("Y", "Y")
        elif index == 0 and mode == "mixed":
            cue_answers = ("Y", "N")
        elif index == 0 and mode == "inconclusive":
            cue_answers = (None, "N")
        cue_cases.append(_case(task, expected, cue_answers))
        for repetition, answer in enumerate(cue_answers, start=1):
            probabilities[(task_id, repetition)] = (
                _probability(AttachmentEdgeFilterAnswerValue(answer))
                if answer is not None
                else None
            )
    baseline = cast(
        AttachmentResidualOwnershipReport,
        SimpleNamespace(cases=tuple(baseline_cases)),
    )
    cue = cast(
        AttachmentResidualOwnershipReport,
        SimpleNamespace(cases=tuple(cue_cases)),
    )
    reference = AttachmentEvidenceReference(label="input", path="/input", sha256=DIGEST)

    report = build_residual_cue_ablation_report(
        inputs=(reference,),
        baseline_prompt=AttachmentEvidenceReference(
            label="baseline_prompt", path="/baseline", sha256="b" * 64
        ),
        cue_prompt=AttachmentEvidenceReference(label="cue_prompt", path="/cue", sha256="c" * 64),
        baseline_report=baseline,
        cue_report=cue,
        probabilities=probabilities,
    )

    assert report.outcome.value == expected_outcome
    assert report.positive_recovery_case_count == (1 if mode == "supported" else 0)
    assert report.negative_regression_case_count == 0
    assert report.probability_evidence_count == (19 if mode == "inconclusive" else 20)


def _case(task: object, expected: str, answers: tuple[str | None, str | None]) -> object:
    return SimpleNamespace(
        task=task,
        expected_answer=expected,
        observations=tuple(
            SimpleNamespace(
                decision=SimpleNamespace(
                    answer=(
                        AttachmentEdgeFilterAnswerValue(answer) if answer is not None else None
                    ),
                    status=(
                        AttachmentEdgeFilterDecisionStatus.COMPLETE
                        if answer is not None
                        else AttachmentEdgeFilterDecisionStatus.INVALID_OUTPUT
                    ),
                )
            )
            for answer in answers
        ),
    )


def _probability(answer: AttachmentEdgeFilterAnswerValue) -> AttachmentAnswerProbability:
    masses = {
        AttachmentEdgeFilterAnswerValue.YES: 0.1,
        AttachmentEdgeFilterAnswerValue.NO: 0.1,
        AttachmentEdgeFilterAnswerValue.UNCLEAR: 0.1,
    }
    masses[answer] = 0.8
    yes = math.log(masses[AttachmentEdgeFilterAnswerValue.YES])
    no = math.log(masses[AttachmentEdgeFilterAnswerValue.NO])
    unclear = math.log(masses[AttachmentEdgeFilterAnswerValue.UNCLEAR])
    return AttachmentAnswerProbability(
        token_position=0,
        emitted_answer=answer,
        yes_log_probability=yes,
        no_log_probability=no,
        unclear_log_probability=unclear,
        attachment_score=yes - math.log(math.exp(no) + math.exp(unclear)),
    )
