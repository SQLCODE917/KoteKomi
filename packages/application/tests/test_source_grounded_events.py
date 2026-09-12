import hashlib
from datetime import UTC, datetime

import pytest
from kotekomi_application import (
    SourceGroundedEventDraft,
    build_source_grounded_event,
    build_source_grounded_event_draft,
    validate_source_grounded_event,
)
from kotekomi_domain import EvidenceTarget

NOW = datetime(2026, 9, 12, tzinfo=UTC)
SOURCE_TEXT = "Hegseth has publicly rebuked Anthropic."


def _target(identifier: str, start: int, end: int) -> EvidenceTarget:
    return EvidenceTarget(
        id=identifier,
        source_id="src_fixture",
        document_id="doc_fixture",
        representation_id="rep_fixture",
        text_view_id="tvw_fixture",
        text_view_digest=hashlib.sha256(SOURCE_TEXT.encode()).hexdigest(),
        start_char=start,
        end_char=end,
        exact_text=SOURCE_TEXT[start:end],
        normalization_policy="utf8_identity_v1",
        node_ids=("nod_fixture",),
        created_at=NOW,
    )


def _draft_and_evidence() -> tuple[SourceGroundedEventDraft, dict[str, EvidenceTarget]]:
    support = _target("etg_support", 0, len(SOURCE_TEXT))
    expression = _target("etg_expression", 12, 28)
    head = _target("etg_head", 21, 28)
    draft = build_source_grounded_event_draft(
        event_subject_id="esd_" + "a" * 24,
        trigger_id="etd_" + "b" * 24,
        source_segment_id="segment_fixture",
        source_text_sha256=hashlib.sha256(SOURCE_TEXT.encode()).hexdigest(),
        expression_text=expression.exact_text,
        head_text=head.exact_text,
        head_evidence_target_id=head.id,
        expression_evidence_target_id=expression.id,
        support_evidence_target_id=support.id,
    )
    return draft, {item.id: item for item in (head, expression, support)}


def test_source_grounded_event_preserves_exact_expression_and_evidence() -> None:
    draft, evidence = _draft_and_evidence()

    event = build_source_grounded_event(draft)
    validate_source_grounded_event(event, evidence)

    assert event.name == "publicly rebuked"
    assert event.participant_actor_ids == ()
    assert event.participant_organization_ids == ()
    assert event.mentions[0].head_evidence_target_id == "etg_head"


def test_source_grounded_event_rejects_a_name_different_from_the_source_expression() -> None:
    draft, evidence = _draft_and_evidence()
    event = build_source_grounded_event(draft)

    with pytest.raises(ValueError, match="must equal its exact expression"):
        validate_source_grounded_event(event.model_copy(update={"name": "rebuke"}), evidence)


def test_source_grounded_event_rejects_mixed_authoritative_lineage() -> None:
    draft, evidence = _draft_and_evidence()
    event = build_source_grounded_event(draft)
    evidence["etg_head"] = evidence["etg_head"].model_copy(update={"document_id": "doc_other"})

    with pytest.raises(ValueError, match="share authoritative lineage"):
        validate_source_grounded_event(event, evidence)


def test_source_grounded_event_rejects_a_head_outside_the_expression() -> None:
    draft, evidence = _draft_and_evidence()
    event = build_source_grounded_event(draft)
    evidence["etg_head"] = _target("etg_head", 0, 7)

    with pytest.raises(ValueError, match="head must lie inside"):
        validate_source_grounded_event(event, evidence)
