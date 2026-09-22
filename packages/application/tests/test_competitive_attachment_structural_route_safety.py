from __future__ import annotations

import hashlib
from types import SimpleNamespace
from typing import Any, Literal, cast

import pytest
from kotekomi_application import (
    AttachmentCandidateRootEvidence,
    AttachmentGoldAuthority,
    AttachmentSourceRange,
    AttachmentStructuralEligibility,
    AttachmentStructuralSafetyCase,
    AttachmentStructuralSafetyOutcome,
    AttachmentStructuralSafetyPhase,
    AttachmentStructuralSafetyReport,
    AttachmentSyntaxObservation,
    CompetitiveAttachmentCandidate,
    CompetitiveAttachmentEventOption,
    PredicateArgumentHypothesis,
    PredicateArgumentToken,
    PropositionFragmentReason,
    attachment_complete_foreign_event_ids,
    attachment_structural_safety_fingerprint,
    classify_attachment_structural_safety_outcome,
    competitive_attachment_candidate_id,
    competitive_attachment_event_option_id,
)

SOURCE = "Alpha targeted Beta."
DIGEST = hashlib.sha256(SOURCE.encode()).hexdigest()


def test_foreign_event_exclusion_requires_complete_event_containment() -> None:
    source = {"source_segment_id": "seg_fixture", "source_text_sha256": "a" * 64}
    candidate = SimpleNamespace(**source, start=5, end=20)
    target = SimpleNamespace(**source, source_grounded_event_id="sge_target", start=8, end=10)
    contained = SimpleNamespace(
        **source,
        source_grounded_event_id="sge_contained",
        start=12,
        end=16,
    )
    partial = SimpleNamespace(
        **source,
        source_grounded_event_id="sge_partial",
        start=18,
        end=22,
    )

    result = attachment_complete_foreign_event_ids(
        cast(Any, candidate),
        cast(Any, target),
        cast(Any, (target, contained, partial)),
    )

    assert result == ("sge_contained",)


@pytest.mark.parametrize(
    ("eligible_negative_count", "excluded_positive_count", "expected"),
    (
        (0, 0, AttachmentStructuralSafetyOutcome.SUPPORTED),
        (0, 1, AttachmentStructuralSafetyOutcome.MIXED),
        (1, 0, AttachmentStructuralSafetyOutcome.FALSIFIED),
        (1, 1, AttachmentStructuralSafetyOutcome.FALSIFIED),
    ),
)
def test_structural_safety_terminal_outcomes(
    eligible_negative_count: int,
    excluded_positive_count: int,
    expected: AttachmentStructuralSafetyOutcome,
) -> None:
    assert (
        classify_attachment_structural_safety_outcome(
            eligible_negative_count=eligible_negative_count,
            excluded_positive_count=excluded_positive_count,
        )
        is expected
    )


@pytest.mark.parametrize(
    ("original_gold", "eligibility", "expected"),
    (
        (
            "Y",
            AttachmentStructuralEligibility.ELIGIBLE,
            AttachmentStructuralSafetyOutcome.SUPPORTED,
        ),
        (
            "Y",
            AttachmentStructuralEligibility.FOREIGN_EVENT,
            AttachmentStructuralSafetyOutcome.MIXED,
        ),
        (
            "N",
            AttachmentStructuralEligibility.ELIGIBLE,
            AttachmentStructuralSafetyOutcome.FALSIFIED,
        ),
    ),
)
def test_structural_safety_report_constructs_every_semantic_outcome(
    original_gold: Literal["Y", "N"],
    eligibility: AttachmentStructuralEligibility,
    expected: AttachmentStructuralSafetyOutcome,
) -> None:
    report = _report(original_gold=original_gold, eligibility=eligibility, outcome=expected)

    assert report.outcome is expected


def _report(
    *,
    original_gold: Literal["Y", "N"],
    eligibility: AttachmentStructuralEligibility,
    outcome: AttachmentStructuralSafetyOutcome,
) -> AttachmentStructuralSafetyReport:
    case = _case(original_gold=original_gold, eligibility=eligibility)
    development = _phase("development", (case,))
    validation = _phase("validation", ())
    phases = (development, validation)
    total_edge_count = sum(item.total_edge_count for item in phases)
    head_aligned_count = sum(item.head_aligned_count for item in phases)
    gold_conflict_count = sum(item.gold_conflict_count for item in phases)
    foreign_event_exclusion_count = sum(item.excluded_count for item in phases)
    eligible_count = sum(item.eligible_count for item in phases)
    eligible_negative_count = sum(item.eligible_negative_count for item in phases)
    excluded_positive_count = sum(item.excluded_positive_count for item in phases)
    draft = AttachmentStructuralSafetyReport.model_construct(
        inputs=(),
        development=development,
        validation=validation,
        outcome=outcome,
        total_edge_count=total_edge_count,
        head_aligned_count=head_aligned_count,
        gold_conflict_count=gold_conflict_count,
        foreign_event_exclusion_count=foreign_event_exclusion_count,
        eligible_count=eligible_count,
        eligible_negative_count=eligible_negative_count,
        excluded_positive_count=excluded_positive_count,
        model_execution_count=0,
        proposed_change_count=0,
        accepted_ledger_change_count=0,
        production_integration="not_activated",
        result_fingerprint="0" * 64,
    )
    return AttachmentStructuralSafetyReport(
        inputs=(),
        development=development,
        validation=validation,
        outcome=outcome,
        total_edge_count=total_edge_count,
        head_aligned_count=head_aligned_count,
        gold_conflict_count=gold_conflict_count,
        foreign_event_exclusion_count=foreign_event_exclusion_count,
        eligible_count=eligible_count,
        eligible_negative_count=eligible_negative_count,
        excluded_positive_count=excluded_positive_count,
        model_execution_count=0,
        proposed_change_count=0,
        accepted_ledger_change_count=0,
        production_integration="not_activated",
        result_fingerprint=attachment_structural_safety_fingerprint(draft),
    )


def _case(
    *,
    original_gold: Literal["Y", "N"],
    eligibility: AttachmentStructuralEligibility,
) -> AttachmentStructuralSafetyCase:
    token = PredicateArgumentToken(
        token_id="t1",
        sentence_id="s1",
        text="targeted",
        start=6,
        end=14,
        lemma="target",
        part_of_speech="VERB",
        dependency_relation="root",
    )
    reasons = (PropositionFragmentReason.EVENT_EXPRESSION,)
    parents = ("pfc_" + "1" * 24,)
    records = ("record_fixture",)
    candidate_id = competitive_attachment_candidate_id(
        source_segment_id="seg_fixture",
        source_text_sha256=DIGEST,
        start=6,
        end=14,
        text="targeted",
        reasons=reasons,
        parent_candidate_ids=parents,
        linguistic_token_ids=(token.token_id,),
        source_record_ids=records,
    )
    candidate = CompetitiveAttachmentCandidate(
        id=candidate_id,
        source_segment_id="seg_fixture",
        source_text_sha256=DIGEST,
        start=6,
        end=14,
        text="targeted",
        reasons=reasons,
        parent_candidate_ids=parents,
        linguistic_token_ids=(token.token_id,),
        source_record_ids=records,
    )
    event_id = "sge_" + "2" * 24
    trigger_id = "etd_" + "3" * 24
    event_option_id = competitive_attachment_event_option_id(
        source_grounded_event_id=event_id,
        event_trigger_id=trigger_id,
        source_segment_id="seg_fixture",
        source_text_sha256=DIGEST,
        start=6,
        end=14,
        text="targeted",
    )
    event = CompetitiveAttachmentEventOption(
        id=event_option_id,
        label="E1",
        source_grounded_event_id=event_id,
        event_trigger_id=trigger_id,
        source_segment_id="seg_fixture",
        source_text_sha256=DIGEST,
        start=6,
        end=14,
        text="targeted",
    )
    source_range = AttachmentSourceRange(start=6, end=14, text="targeted")
    syntax = AttachmentSyntaxObservation(
        phase="development",
        source_segment_id="seg_fixture",
        source_text_sha256=DIGEST,
        linguistic_trace_id="xst_" + "4" * 24,
        linguistic_resource_identity="5" * 64,
        candidate_id=candidate.id,
        source_grounded_event_id=event_id,
        candidate_range=source_range,
        event_range=source_range,
        event_head_range=source_range,
        event_anchor=token,
        candidate_anchor=token,
        path_tokens=(token,),
        path_steps=(),
        hypothesis=PredicateArgumentHypothesis.DIRECT_ARGUMENT,
        gap_code=None,
        own_event_expression=True,
        structurally_supported=True,
    )
    foreign_event_ids = (
        ("sge_" + "6" * 24,) if eligibility is AttachmentStructuralEligibility.FOREIGN_EVENT else ()
    )
    return AttachmentStructuralSafetyCase(
        phase="development",
        matrix_id="cam_" + "7" * 24,
        source_text=SOURCE,
        candidate=candidate,
        event=event,
        syntax=syntax,
        candidate_root_evidence=AttachmentCandidateRootEvidence(tokens=(token,), roots=(token,)),
        original_gold=original_gold,
        reviewed_gold=None,
        effective_gold=original_gold,
        gold_authority=AttachmentGoldAuthority.ORIGINAL,
        gold_conflict=False,
        foreign_event_ids=foreign_event_ids,
        eligibility=eligibility,
        structural_answer=(
            "Y" if eligibility is AttachmentStructuralEligibility.ELIGIBLE else None
        ),
        correctly_routed=(original_gold == "Y")
        == (eligibility is AttachmentStructuralEligibility.ELIGIBLE),
    )


def _phase(
    phase: Literal["development", "validation"],
    cases: tuple[AttachmentStructuralSafetyCase, ...],
) -> AttachmentStructuralSafetyPhase:
    values = tuple(
        item.model_copy(
            update={"phase": phase, "syntax": item.syntax.model_copy(update={"phase": phase})}
        )
        for item in cases
    )
    eligible = tuple(
        item for item in values if item.eligibility is AttachmentStructuralEligibility.ELIGIBLE
    )
    excluded = tuple(
        item for item in values if item.eligibility is AttachmentStructuralEligibility.FOREIGN_EVENT
    )
    return AttachmentStructuralSafetyPhase(
        phase=phase,
        total_edge_count=len(values),
        cases=values,
        head_aligned_count=len(values),
        original_positive_count=sum(item.original_gold == "Y" for item in values),
        original_negative_count=sum(item.original_gold == "N" for item in values),
        reviewed_edge_count=0,
        gold_conflict_count=0,
        effective_positive_count=sum(item.effective_gold == "Y" for item in values),
        effective_negative_count=sum(item.effective_gold == "N" for item in values),
        eligible_count=len(eligible),
        excluded_count=len(excluded),
        eligible_positive_count=sum(item.effective_gold == "Y" for item in eligible),
        eligible_negative_count=sum(item.effective_gold == "N" for item in eligible),
        excluded_positive_count=sum(item.effective_gold == "Y" for item in excluded),
        excluded_negative_count=sum(item.effective_gold == "N" for item in excluded),
    )
