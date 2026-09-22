"""Deterministic model-free attributed-statement construction contract tests.

Covers the D1 acceptance criteria AC-ASC-ATR-01..04, AC-ASC-RES-01..02,
AC-ASC-REC-01..03, AC-ASC-SCOPE-01/02, and AC-ASC-RUL-05.
"""

from __future__ import annotations

from kotekomi_application import (
    AttributedStatementFailureReason,
    AttributedStatementOutcome,
    AttributedStatementStatus,
    construct_attributed_statement,
)
from kotekomi_application.hybrid_event_semantics import (
    EventArgumentTargetDraft,
    EventAttributionKind,
    EventSemanticDraft,
    build_event_argument_target_draft,
    build_event_semantic_draft,
)
from kotekomi_domain import (
    AssertionType,
    AttributionBasis,
    EpistemicScope,
    ProposedAssertion,
    SemanticArgumentTargetKind,
    SourceAuthority,
)
from kotekomi_domain.models import JsonValue

_SUPPORT = "etg_" + "c" * 24
_TARGET_EVIDENCE = "etg_" + "e" * 24
_TARGET_ATTEMPT = "eva_" + "f" * 24


def _draft(
    *, kind: EventAttributionKind, attribution_target_id: str | None = None
) -> EventSemanticDraft:
    return build_event_semantic_draft(
        event_subject_id="esd_" + "a" * 24,
        trigger_id="etd_" + "b" * 24,
        trigger_text="stated",
        frame_id="statement",
        proposed_event_label="ran_a_sophisticated_regulatory_strategy",
        argument_assignment_ids=(),
        qualifier_ids=(),
        polarity="affirmed",
        modality="actual",
        attribution_kind=kind,
        attribution_target_id=attribution_target_id,
        support_evidence_target_id=_SUPPORT,
        frame_selection_task_id="ext_fixture",
        frame_selection_model_run_id="mrn_fixture",
        frame_selection_trace_id="xst_" + "d" * 24,
    )


def _target(
    *,
    kind: SemanticArgumentTargetKind,
    reference_id: str | None = None,
    text: str = "Sacks",
) -> EventArgumentTargetDraft:
    return build_event_argument_target_draft(
        kind=kind,
        reference_id=reference_id,
        source_segment_id="seg_fixture",
        text=text,
        start=0,
        end=len(text),
        evidence_target_id=_TARGET_EVIDENCE,
        evidence_validation_attempt_id=_TARGET_ATTEMPT,
    )


class _Resolver:
    def __init__(self, result: str | None) -> None:
        self.result = result
        self.calls = 0

    def resolve_attribution_target(self, target: EventArgumentTargetDraft) -> str | None:
        self.calls += 1
        return self.result


def _construct(
    draft: EventSemanticDraft,
    target: EventArgumentTargetDraft | None,
    resolver: _Resolver,
    *,
    object_entity_id: str | None = None,
    object_value: JsonValue = "a sophisticated regulatory strategy",
) -> AttributedStatementOutcome:
    return construct_attributed_statement(
        draft=draft,
        attribution_target=target,
        resolver=resolver,
        subject_entity_id="org_anthropic",
        object_entity_id=object_entity_id,
        object_value=object_value,
        source_id="src_article_a",
        support_evidence_target_id=_SUPPORT,
        assertion_id="ast_attributed_01",
    )


def test_mention_candidate_constructs_attributed_statement() -> None:
    target = _target(kind=SemanticArgumentTargetKind.MENTION_CANDIDATE, reference_id="mnc_sacks")
    draft = _draft(kind=EventAttributionKind.MENTION_CANDIDATE, attribution_target_id=target.id)
    outcome = _construct(draft, target, _Resolver("act_sacks"))

    assert outcome.status is AttributedStatementStatus.CONSTRUCTED
    assert outcome.failure_reason is None
    assert outcome.proposed_assertion is not None
    assert outcome.proposed_assertion.epistemic_scope is EpistemicScope.ATTRIBUTED_STATEMENT
    assert outcome.proposed_assertion.attributed_to_id == "act_sacks"


def test_source_span_organization_constructs_attributed_statement() -> None:
    target = _target(
        kind=SemanticArgumentTargetKind.SOURCE_SPAN, reference_id=None, text="Anthropic"
    )
    draft = _draft(kind=EventAttributionKind.SOURCE_SPAN, attribution_target_id=target.id)
    outcome = _construct(draft, target, _Resolver("org_anthropic"))

    assert outcome.status is AttributedStatementStatus.CONSTRUCTED
    assert outcome.proposed_assertion is not None
    assert outcome.proposed_assertion.attributed_to_id == "org_anthropic"


def test_source_narrator_produces_no_assertion() -> None:
    draft = _draft(kind=EventAttributionKind.SOURCE_NARRATOR)
    outcome = _construct(draft, None, _Resolver("act_sacks"))

    assert outcome.status is AttributedStatementStatus.NO_ASSERTION
    assert outcome.failure_reason is None
    assert outcome.proposed_assertion is None


def test_unresolved_attribution_fails_fast() -> None:
    draft = _draft(kind=EventAttributionKind.UNRESOLVED)
    outcome = _construct(draft, None, _Resolver("act_sacks"))

    assert outcome.status is AttributedStatementStatus.FAILED
    assert outcome.failure_reason is AttributedStatementFailureReason.ATTRIBUTION_UNRESOLVED
    assert outcome.proposed_assertion is None


def test_source_span_without_actor_or_organization_fails_fast() -> None:
    target = _target(
        kind=SemanticArgumentTargetKind.SOURCE_SPAN, reference_id=None, text="a strategy"
    )
    draft = _draft(kind=EventAttributionKind.SOURCE_SPAN, attribution_target_id=target.id)
    outcome = _construct(draft, target, _Resolver(None))

    assert outcome.status is AttributedStatementStatus.FAILED
    assert (
        outcome.failure_reason
        is AttributedStatementFailureReason.ATTRIBUTION_TARGET_NOT_ACTOR_OR_ORGANIZATION
    )
    assert outcome.proposed_assertion is None


def test_resolved_target_must_be_actor_or_organization() -> None:
    target = _target(kind=SemanticArgumentTargetKind.MENTION_CANDIDATE, reference_id="mnc_sacks")
    draft = _draft(kind=EventAttributionKind.MENTION_CANDIDATE, attribution_target_id=target.id)
    outcome = _construct(draft, target, _Resolver("evt_123"))

    assert outcome.status is AttributedStatementStatus.FAILED
    assert (
        outcome.failure_reason
        is AttributedStatementFailureReason.ATTRIBUTION_TARGET_NOT_ACTOR_OR_ORGANIZATION
    )
    assert outcome.proposed_assertion is None


def test_missing_attribution_target_fails_fast() -> None:
    target = _target(kind=SemanticArgumentTargetKind.MENTION_CANDIDATE, reference_id="mnc_sacks")
    draft = _draft(kind=EventAttributionKind.MENTION_CANDIDATE, attribution_target_id=target.id)
    outcome = _construct(draft, None, _Resolver("act_sacks"))

    assert outcome.status is AttributedStatementStatus.FAILED
    assert outcome.failure_reason is AttributedStatementFailureReason.ATTRIBUTION_TARGET_MISSING
    assert outcome.proposed_assertion is None


def test_constructed_record_carries_contract_fields() -> None:
    target = _target(kind=SemanticArgumentTargetKind.MENTION_CANDIDATE, reference_id="mnc_sacks")
    draft = _draft(kind=EventAttributionKind.MENTION_CANDIDATE, attribution_target_id=target.id)
    outcome = _construct(draft, target, _Resolver("act_sacks"))

    record = outcome.proposed_assertion
    assert isinstance(record, ProposedAssertion)
    assert record.attributed_to_id == "act_sacks"
    assert record.attribution_basis is AttributionBasis.REPORTED_BY_SOURCE
    assert record.assertion_type is AssertionType.SOURCE_CLAIM
    assert record.epistemic_scope is EpistemicScope.ATTRIBUTED_STATEMENT
    assert record.source_authority is SourceAuthority.SECONDARY
    assert record.source_ids == ("src_article_a",)
    assert record.evidence_target_ids == (_SUPPORT,)
    assert record.relation_label == draft.proposed_event_label
    assert record.subject_entity_id == "org_anthropic"
    assert record.object_value == "a sophisticated regulatory strategy"
    ProposedAssertion.model_validate(record.model_dump(mode="python"))


def test_object_entity_id_path_validates() -> None:
    target = _target(
        kind=SemanticArgumentTargetKind.SOURCE_SPAN, reference_id=None, text="Anthropic"
    )
    draft = _draft(kind=EventAttributionKind.SOURCE_SPAN, attribution_target_id=target.id)
    outcome = _construct(
        draft,
        target,
        _Resolver("org_anthropic"),
        object_entity_id="org_ai_industry",
        object_value=None,
    )

    assert outcome.status is AttributedStatementStatus.CONSTRUCTED
    assert outcome.proposed_assertion is not None
    assert outcome.proposed_assertion.object_entity_id == "org_ai_industry"
    assert outcome.proposed_assertion.object_value is None


def test_construction_invokes_no_model_and_resolves_only_targeted_kinds() -> None:
    mention = _target(kind=SemanticArgumentTargetKind.MENTION_CANDIDATE, reference_id="mnc_sacks")
    draft = _draft(kind=EventAttributionKind.MENTION_CANDIDATE, attribution_target_id=mention.id)
    resolver = _Resolver("act_sacks")
    _construct(draft, mention, resolver)
    assert resolver.calls == 1

    narrator = _Resolver("act_sacks")
    _construct(_draft(kind=EventAttributionKind.SOURCE_NARRATOR), None, narrator)
    assert narrator.calls == 0

    unresolved = _Resolver("act_sacks")
    _construct(_draft(kind=EventAttributionKind.UNRESOLVED), None, unresolved)
    assert unresolved.calls == 0
