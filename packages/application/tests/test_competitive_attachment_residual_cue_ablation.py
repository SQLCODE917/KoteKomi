from __future__ import annotations

import math

from kotekomi_application import (
    AttachmentAnswerProbability,
    AttachmentEdgeFilterAnswerValue,
    AttachmentEvidenceReference,
    AttachmentResidualCueAblationCase,
    AttachmentResidualCueAblationOutcome,
    AttachmentResidualCueAblationReport,
    attachment_residual_cue_ablation_fingerprint,
)

DIGEST = "a" * 64


def test_cue_ablation_report_classifies_all_four_outcomes() -> None:
    supported = _report(mode="supported")
    mixed = _report(mode="mixed")
    falsified = _report(mode="falsified")
    inconclusive = _report(mode="inconclusive")

    assert supported.outcome is AttachmentResidualCueAblationOutcome.SUPPORTED
    assert supported.positive_recovery_case_count == 1
    assert mixed.outcome is AttachmentResidualCueAblationOutcome.MIXED
    assert mixed.positive_yes_observation_count == 1
    assert falsified.outcome is AttachmentResidualCueAblationOutcome.FALSIFIED
    assert falsified.cue_no_count == 20
    assert inconclusive.outcome is AttachmentResidualCueAblationOutcome.INCONCLUSIVE
    assert inconclusive.probability_evidence_count == 19


def _report(
    *,
    mode: str,
) -> AttachmentResidualCueAblationReport:
    cases: list[AttachmentResidualCueAblationCase] = []
    for index in range(10):
        expected = "Y" if index < 7 else "N"
        answers: tuple[
            AttachmentEdgeFilterAnswerValue | None,
            AttachmentEdgeFilterAnswerValue | None,
        ] = (
            AttachmentEdgeFilterAnswerValue.NO,
            AttachmentEdgeFilterAnswerValue.NO,
        )
        if index == 0 and mode == "supported":
            answers = (
                AttachmentEdgeFilterAnswerValue.YES,
                AttachmentEdgeFilterAnswerValue.YES,
            )
        elif index == 0 and mode == "mixed":
            answers = (
                AttachmentEdgeFilterAnswerValue.YES,
                AttachmentEdgeFilterAnswerValue.NO,
            )
        elif index == 0 and mode == "inconclusive":
            answers = (None, AttachmentEdgeFilterAnswerValue.NO)
        first_probability = _probability(answers[0]) if answers[0] is not None else None
        second_probability = _probability(answers[1])
        cases.append(
            AttachmentResidualCueAblationCase(
                task_id=f"aro_{index + 1:024x}",
                edge_id=f"ape_{index + 1:024x}",
                expected_answer=expected,
                baseline_answers=(
                    AttachmentEdgeFilterAnswerValue.NO,
                    AttachmentEdgeFilterAnswerValue.NO,
                ),
                cue_answers=answers,
                cue_probabilities=(first_probability, second_probability),
                stable_cue_result=(answers[0] is not None and answers[0] is answers[1]),
                positive_yes_observation_count=(
                    sum(item is AttachmentEdgeFilterAnswerValue.YES for item in answers)
                    if expected == "Y"
                    else 0
                ),
                positive_recovery=(
                    expected == "Y"
                    and answers
                    == (
                        AttachmentEdgeFilterAnswerValue.YES,
                        AttachmentEdgeFilterAnswerValue.YES,
                    )
                ),
                negative_regression=(
                    expected == "N"
                    and any(item is not AttachmentEdgeFilterAnswerValue.NO for item in answers)
                ),
            )
        )
    values = tuple(cases)
    all_answers = tuple(item for case in values for item in case.cue_answers)
    probability_count = sum(item is not None for case in values for item in case.cue_probabilities)
    positive_yes = sum(item.positive_yes_observation_count for item in values)
    recoveries = sum(item.positive_recovery for item in values)
    regressions = sum(item.negative_regression for item in values)
    stable = sum(item.stable_cue_result for item in values)
    unresolved = sum(item is None for item in all_answers)
    if unresolved or probability_count != 20:
        outcome = AttachmentResidualCueAblationOutcome.INCONCLUSIVE
    elif positive_yes == 0:
        outcome = AttachmentResidualCueAblationOutcome.FALSIFIED
    elif recoveries and not regressions and stable == 10:
        outcome = AttachmentResidualCueAblationOutcome.SUPPORTED
    else:
        outcome = AttachmentResidualCueAblationOutcome.MIXED
    reference = AttachmentEvidenceReference(label="input", path="/input", sha256=DIGEST)
    draft = AttachmentResidualCueAblationReport.model_construct(
        inputs=(reference,),
        baseline_prompt=AttachmentEvidenceReference(
            label="baseline_prompt", path="/baseline", sha256="b" * 64
        ),
        cue_prompt=AttachmentEvidenceReference(label="cue_prompt", path="/cue", sha256="c" * 64),
        cases=values,
        cue_yes_count=sum(item is AttachmentEdgeFilterAnswerValue.YES for item in all_answers),
        cue_no_count=sum(item is AttachmentEdgeFilterAnswerValue.NO for item in all_answers),
        cue_unclear_count=sum(
            item is AttachmentEdgeFilterAnswerValue.UNCLEAR for item in all_answers
        ),
        unresolved_count=unresolved,
        probability_evidence_count=probability_count,
        stable_case_count=stable,
        positive_yes_observation_count=positive_yes,
        positive_recovery_case_count=recoveries,
        negative_regression_case_count=regressions,
        outcome=outcome,
        result_fingerprint="0" * 64,
    )
    return AttachmentResidualCueAblationReport(
        **draft.model_dump(exclude={"result_fingerprint"}),
        result_fingerprint=attachment_residual_cue_ablation_fingerprint(draft),
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
