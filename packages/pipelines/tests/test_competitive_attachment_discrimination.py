from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Literal

import pytest
from kotekomi_application import (
    CompetitiveAttachmentDecisionStatus,
    CompetitiveAttachmentFailureShape,
    CompetitiveDiscriminationCaseResult,
    CompetitiveDiscriminationConditionReport,
    CompetitiveDiscriminationMetrics,
    CompetitiveDiscriminationOutcome,
    CompetitiveDiscriminationPromptArm,
    attachment_set_jaccard,
    competitive_attachment_failure_shape,
)
from kotekomi_pipelines.competitive_attachment_discrimination import (
    compare_competitive_discrimination_reports,
)
from pydantic import ValidationError

EVENT = "sge_" + "1" * 24
type EventOrder = Literal["source", "reversed"]
REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
PROMPT_PATHS = {
    CompetitiveDiscriminationPromptArm.CONTROL: REPOSITORY_ROOT
    / "prompts/competitive_event_attachment_v1.md",
    CompetitiveDiscriminationPromptArm.SCOPE: REPOSITORY_ROOT
    / "prompts/competitive_event_attachment_scope_v2.md",
    CompetitiveDiscriminationPromptArm.EXAMPLES: REPOSITORY_ROOT
    / "prompts/competitive_event_attachment_examples_v2.md",
    CompetitiveDiscriminationPromptArm.COMBINED: REPOSITORY_ROOT
    / "prompts/competitive_event_attachment_combined_v2.md",
}


def test_prompt_arms_change_only_their_declared_factors() -> None:
    sections = {
        arm: _prompt_sections(path.read_text(encoding="utf-8"))
        for arm, path in PROMPT_PATHS.items()
    }
    control_instruction, control_examples, control_output = sections[
        CompetitiveDiscriminationPromptArm.CONTROL
    ]
    scope_instruction, scope_examples, scope_output = sections[
        CompetitiveDiscriminationPromptArm.SCOPE
    ]
    examples_instruction, examples_examples, examples_output = sections[
        CompetitiveDiscriminationPromptArm.EXAMPLES
    ]
    combined_instruction, combined_examples, combined_output = sections[
        CompetitiveDiscriminationPromptArm.COMBINED
    ]

    assert scope_instruction != control_instruction
    assert scope_examples == control_examples
    assert examples_instruction == control_instruction
    assert examples_examples != control_examples
    assert combined_instruction == scope_instruction
    assert combined_examples == examples_examples
    assert control_output == scope_output == examples_output == combined_output
    assert all(
        answer in examples_examples
        for answer in ("Answer: `E2`", "Answer: `E1,E3`", "Answer: `E2,E4`")
    )
    assert not {"Anthropic", "Amodei", "Trump"} & set(examples_examples.split())


@pytest.mark.parametrize(
    ("mode", "expected"),
    (
        ("supported", CompetitiveDiscriminationOutcome.SUPPORTED),
        ("mixed", CompetitiveDiscriminationOutcome.MIXED),
        ("falsified", CompetitiveDiscriminationOutcome.FALSIFIED),
    ),
)
def test_comparison_classifies_all_terminal_outcomes(
    mode: str,
    expected: CompetitiveDiscriminationOutcome,
) -> None:
    reports = _reports(mode)
    report_sha256s = {
        (item.arm, item.event_order, item.repetition): f"{ordinal:064x}"
        for ordinal, item in enumerate(reports, start=1)
    }

    comparison = compare_competitive_discrimination_reports(
        failure_audit_sha256="a" * 64,
        catalog_sha256="b" * 64,
        reports=reports,
        report_sha256s=report_sha256s,
    )

    assert comparison.outcome is expected
    assert comparison.production_integration == "not_activated"


def test_condition_report_rejects_primary_metric_drift() -> None:
    report = _report(
        CompetitiveDiscriminationPromptArm.CONTROL,
        "source",
        1,
        omitted=frozenset(range(12, 24)),
        governing_matched=4,
        non_prefix_exact=2,
        fingerprint="a" * 64,
    )
    damaged_metrics = report.metrics.model_copy(update={"exact_set_accuracy": 1.0})

    with pytest.raises(ValidationError, match="primary metrics drifted"):
        CompetitiveDiscriminationConditionReport.model_validate(
            report.model_copy(update={"metrics": damaged_metrics}).model_dump(mode="python")
        )


def _reports(mode: str) -> tuple[CompetitiveDiscriminationConditionReport, ...]:
    control_by_order: dict[EventOrder, frozenset[int]] = {
        "source": frozenset(range(12, 24)),
        "reversed": frozenset(range(11, 23)),
    }
    result: list[CompetitiveDiscriminationConditionReport] = []
    for arm in CompetitiveDiscriminationPromptArm:
        for order in ("source", "reversed"):
            omissions: frozenset[int] = control_by_order[order]
            governing_matched = 4
            non_prefix_exact = 2
            if arm is CompetitiveDiscriminationPromptArm.SCOPE and mode != "falsified":
                governing_matched = 5
            if arm is CompetitiveDiscriminationPromptArm.EXAMPLES and mode != "falsified":
                non_prefix_exact = 3
            if arm is CompetitiveDiscriminationPromptArm.COMBINED:
                if mode == "supported" or (mode == "mixed" and order == "source"):
                    omissions = frozenset[int]()
                    governing_matched = 8
                    non_prefix_exact = 6
            fingerprint = _fingerprint(arm, order, omissions)
            result.append(
                _report(
                    arm,
                    order,
                    1,
                    omitted=omissions,
                    governing_matched=governing_matched,
                    non_prefix_exact=non_prefix_exact,
                    fingerprint=fingerprint,
                )
            )
    for order in ("source", "reversed"):
        first = next(
            item
            for item in result
            if item.arm is CompetitiveDiscriminationPromptArm.COMBINED and item.event_order == order
        )
        result.append(first.model_copy(update={"repetition": 2}))
    return tuple(result)


def _report(
    arm: CompetitiveDiscriminationPromptArm,
    event_order: EventOrder,
    repetition: int,
    *,
    omitted: frozenset[int],
    governing_matched: int,
    non_prefix_exact: int,
    fingerprint: str,
) -> CompetitiveDiscriminationConditionReport:
    cases = tuple(
        _case(ordinal, gold=() if ordinal == 0 else (EVENT,), predicted=())
        if ordinal in omitted
        else _case(
            ordinal,
            gold=() if ordinal == 0 else (EVENT,),
            predicted=() if ordinal == 0 else (EVENT,),
        )
        for ordinal in range(24)
    )
    protected_matched = 20 if not omitted else 15
    metrics = _metrics(
        cases,
        governing_matched=governing_matched,
        non_prefix_exact=non_prefix_exact,
        protected_matched=protected_matched,
    )
    return CompetitiveDiscriminationConditionReport(
        arm=arm,
        event_order=event_order,
        repetition=repetition,
        prompt_sha256="c" * 64,
        cases=cases,
        metrics=metrics,
        model_execution_count=24,
        input_token_count=240,
        output_token_count=24,
        elapsed_milliseconds=2400,
        result_fingerprint=fingerprint,
    )


def _case(
    ordinal: int,
    *,
    gold: tuple[str, ...],
    predicted: tuple[str, ...],
) -> CompetitiveDiscriminationCaseResult:
    return CompetitiveDiscriminationCaseResult(
        candidate_id=f"cac_{ordinal + 1:024x}",
        gold_event_ids=gold,
        predicted_event_ids=predicted,
        status=CompetitiveAttachmentDecisionStatus.COMPLETE,
        exact=gold == predicted,
        jaccard_similarity=attachment_set_jaccard(gold, predicted),
        hamming_error_count=len(set(gold) ^ set(predicted)),
        hamming_cell_count=1,
    )


def _metrics(
    cases: tuple[CompetitiveDiscriminationCaseResult, ...],
    *,
    governing_matched: int,
    non_prefix_exact: int,
    protected_matched: int,
) -> CompetitiveDiscriminationMetrics:
    true_positive = sum(
        len(set(item.gold_event_ids) & set(item.predicted_event_ids)) for item in cases
    )
    false_positive = sum(
        len(set(item.predicted_event_ids) - set(item.gold_event_ids)) for item in cases
    )
    false_negative = sum(
        len(set(item.gold_event_ids) - set(item.predicted_event_ids)) for item in cases
    )
    shapes: Counter[CompetitiveAttachmentFailureShape] = Counter(
        competitive_attachment_failure_shape(item.gold_event_ids, item.predicted_event_ids)
        for item in cases
        if item.gold_event_ids != item.predicted_event_ids
    )
    return CompetitiveDiscriminationMetrics(
        candidate_count=24,
        exact_set_accuracy=sum(item.exact for item in cases) / 24,
        mean_jaccard_similarity=sum(item.jaccard_similarity for item in cases) / 24,
        hamming_loss=sum(item.hamming_error_count for item in cases) / 24,
        edge_precision=_ratio(true_positive, true_positive + false_positive),
        edge_recall=_ratio(true_positive, true_positive + false_negative),
        complete_omission_count=shapes[CompetitiveAttachmentFailureShape.COMPLETE_OMISSION],
        under_attachment_count=shapes[CompetitiveAttachmentFailureShape.UNDER_ATTACHMENT],
        false_positive_none_count=shapes[CompetitiveAttachmentFailureShape.FALSE_POSITIVE_NONE],
        over_attachment_count=shapes[CompetitiveAttachmentFailureShape.OVER_ATTACHMENT],
        wrong_set_substitution_count=shapes[
            CompetitiveAttachmentFailureShape.WRONG_SET_SUBSTITUTION
        ],
        sibling_event_leakage_count=sum(
            len(set(item.predicted_event_ids) - set(item.gold_event_ids))
            for item in cases
            if item.gold_event_ids
        ),
        non_prefix_case_count=6,
        non_prefix_exact_count=non_prefix_exact,
        governing_gold_edge_count=8,
        governing_matched_edge_count=governing_matched,
        shared_gold_edge_count=20,
        shared_matched_edge_count=protected_matched,
        none_case_count=1,
        none_correct_count=1,
        entity_gold_edge_count=20,
        entity_matched_edge_count=protected_matched,
        qualification_gold_edge_count=20,
        qualification_matched_edge_count=protected_matched,
        unclear_count=0,
        invalid_output_count=0,
        model_failed_count=0,
        context_budget_blocked_count=0,
        unresolved_count=0,
    )


def _fingerprint(
    arm: CompetitiveDiscriminationPromptArm,
    order: str,
    omitted: frozenset[int],
) -> str:
    value = len(arm.value) * 10_000 + len(order) * 100 + sum(omitted)
    return f"{value:064x}"


def _ratio(numerator: int, denominator: int) -> float:
    return 1.0 if denominator == 0 else numerator / denominator


def _prompt_sections(value: str) -> tuple[str, str, str]:
    example_start = value.index("Example 1:")
    output_start = value.index("Return `NONE`")
    return value[:example_start], value[example_start:output_start], value[output_start:]
