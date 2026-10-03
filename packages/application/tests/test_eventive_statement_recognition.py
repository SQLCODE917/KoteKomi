"""Focused data-in/data-out tests for R13 eventive statement recognition."""

from __future__ import annotations

import pytest
from kotekomi_application import (
    EventiveStatementReport,
    Reification,
    ReificationHoldReason,
    ReificationOutcome,
    ReificationSubjectKind,
    StatementRecognition,
    StatementShape,
    StatementSlots,
    build_eventive_statement_report,
    eventive_statement_report_fingerprint,
    recognize_and_reify,
    recognize_statement,
    reify_statement,
)
from kotekomi_domain import (
    Assertion,
    AssertionStatus,
    AssertionType,
    AttributionBasis,
    EpistemicScope,
    Relationship,
    SourceAuthority,
)
from pydantic import ValidationError

_AHE004_SHA = "2564e4402fa1ba0f3ff23eb20d3a4460d7d443fe9ac1af3e382f429f132f85af"
_AHE004_STATEMENT = (
    "[2] Efforts to utilize artificial intelligence intensified under the term of "
    "Secretary Ash Carter."
)


def _slots(
    *,
    event_id: str = "AHE-004",
    statement: str = _AHE004_STATEMENT,
    subject_text: str | None = None,
    subject_entity_ref: str | None = None,
    predicate_text: str = "intensified",
    predicate_lemma: str = "intensify",
    object_text: str | None = None,
    object_entity_ref: str | None = None,
) -> StatementSlots:
    return StatementSlots(
        event_id=event_id,
        source_text_sha256=_AHE004_SHA,
        statement=statement,
        subject_text=subject_text,
        subject_entity_ref=subject_entity_ref,
        predicate_text=predicate_text,
        predicate_lemma=predicate_lemma,
        object_text=object_text,
        object_entity_ref=object_entity_ref,
    )


def _ahe004_slots() -> StatementSlots:
    """The recovered AHE-004 statement: eventive subject, change predicate, value object."""
    return _slots(subject_text="Efforts", object_text="under the term of Secretary Ash Carter")


def _connection_slots() -> StatementSlots:
    """A two-entity statement: subject and object both resolve to entity references."""
    return _slots(
        event_id="AHE-001",
        statement="Anthropic supplied compute to Stargate.",
        subject_text="Anthropic",
        subject_entity_ref="EGE-001",
        predicate_text="supplied",
        predicate_lemma="supply",
        object_text="Stargate",
        object_entity_ref="EGE-002",
    )


def _unknown_slots() -> StatementSlots:
    """An unassignable statement: eventive subject but a non-change predicate."""
    return _slots(
        subject_text="Efforts",
        predicate_lemma="publish",
        object_text="under the term of Secretary Ash Carter",
    )


def test_recognizer_assigns_eventive_state_change_for_ahe004() -> None:
    recognition = recognize_statement(slots=_ahe004_slots())
    assert recognition.shape is StatementShape.EVENTIVE_STATE_CHANGE


def test_recognizer_assigns_connection_for_two_entity_statement() -> None:
    recognition = recognize_statement(slots=_connection_slots())
    assert recognition.shape is StatementShape.CONNECTION


def test_closed_shape_vocabulary_is_exhaustive() -> None:
    assert {shape.value for shape in StatementShape} == {
        "connection",
        "eventive_state_change",
        "unknown_shape",
    }


def test_every_statement_lands_in_exactly_one_closed_shape() -> None:
    for slots in (_ahe004_slots(), _connection_slots(), _unknown_slots()):
        recognition = recognize_statement(slots=slots)
        assert isinstance(recognition, StatementRecognition)
        assert recognition.shape in StatementShape


def test_unassignable_statement_books_unknown_shape_and_typed_hold() -> None:
    item = recognize_and_reify(slots=_unknown_slots())
    assert item.recognition.shape is StatementShape.UNKNOWN_SHAPE
    assert item.reification.outcome is ReificationOutcome.HELD
    assert item.reification.hold_reason is ReificationHoldReason.UNKNOWN_SHAPE
    assert item.reification.draft is None


def test_eventive_statement_reifies_to_one_assertion_with_eventive_subject() -> None:
    item = recognize_and_reify(slots=_ahe004_slots())
    assert item.reification.outcome is ReificationOutcome.ASSERTION_DRAFT
    draft = item.reification.draft
    assert draft is not None
    assert draft.shape is StatementShape.EVENTIVE_STATE_CHANGE
    assert draft.subject.kind is ReificationSubjectKind.EVENT
    assert draft.subject.reference_id is None
    assert draft.subject.exact_text == "Efforts"
    assert draft.predicate_text == "intensified"
    assert draft.object is not None
    assert draft.object.value == "under the term of Secretary Ash Carter"


def test_eventive_reification_never_fabricates_actor_or_organization() -> None:
    draft = recognize_and_reify(slots=_ahe004_slots()).reification.draft
    assert draft is not None
    assert draft.subject.kind is not ReificationSubjectKind.ENTITY
    assert draft.subject.reference_id is None


def test_connection_statement_reifies_to_one_assertion_with_entity_subject_and_object() -> None:
    draft = recognize_and_reify(slots=_connection_slots()).reification.draft
    assert draft is not None
    assert draft.shape is StatementShape.CONNECTION
    assert draft.subject.kind is ReificationSubjectKind.ENTITY
    assert draft.subject.reference_id == "EGE-001"
    assert draft.object is not None
    assert draft.object.entity_ref == "EGE-002"


def test_one_statement_yields_exactly_one_assertion_for_each_known_shape() -> None:
    for slots in (_ahe004_slots(), _connection_slots()):
        item = recognize_and_reify(slots=slots)
        assert item.reification.outcome is ReificationOutcome.ASSERTION_DRAFT
        assert item.reification.draft is not None


def test_recognizer_is_blind_to_held_out_gold() -> None:
    slots = _ahe004_slots()
    assert slots.subject_entity_ref is None
    assert slots.object_entity_ref is None
    assert recognize_statement(slots=slots).shape is StatementShape.EVENTIVE_STATE_CHANGE


def test_single_dispatch_serves_every_shape() -> None:
    expected = {
        "connection": _connection_slots(),
        "eventive_state_change": _ahe004_slots(),
        "unknown_shape": _unknown_slots(),
    }
    for shape, slots in expected.items():
        item = recognize_and_reify(slots=slots)
        assert item.recognition.shape.value == shape
        assert isinstance(reify_statement(recognition=item.recognition, slots=slots), Reification)


def _direct_assertion(assertion_id: str) -> Assertion:
    return Assertion(
        id=assertion_id,
        assertion_type=AssertionType.SOURCE_CLAIM,
        epistemic_scope=EpistemicScope.SOURCE_REPORT,
        subject_entity_id="evt_ahe004_activity",
        predicate="describes",
        object_value="a software-safety effort",
        status=AssertionStatus.PROPOSED,
        source_authority=SourceAuthority.SECONDARY,
        attribution_basis=AttributionBasis.DIRECT_DOCUMENT,
        source_ids=("src_example",),
        evidence_target_ids=("etg_example",),
    )


def test_superseded_assertion_keeps_its_original_record() -> None:
    predecessor = _direct_assertion("ast_vague_001")
    original = predecessor.model_dump(mode="json")
    successor = _direct_assertion("ast_concrete_001").model_copy(
        update={"supersedes_assertion_id": predecessor.id}
    )
    assert successor.supersedes_assertion_id == predecessor.id
    assert predecessor.model_dump(mode="json") == original


def test_successor_names_predecessor_through_supersedes_assertion_id() -> None:
    predecessor = _direct_assertion("ast_vague_001")
    successor = _direct_assertion("ast_concrete_001").model_copy(
        update={"supersedes_assertion_id": predecessor.id}
    )
    assert successor.supersedes_assertion_id == predecessor.id


def test_keep_and_link_joins_through_relationship_never_deleting_predecessor() -> None:
    predecessor = _direct_assertion("ast_vague_001")
    successor = _direct_assertion("ast_concrete_001")
    original = predecessor.model_dump(mode="json")
    relationship = Relationship(
        id="rel_same_activity_001",
        subject_id="evt_ahe004_activity",
        predicate="same_activity",
        object_id="evt_ahe004_activity_concrete",
        assertion_ids=(predecessor.id, successor.id),
    )
    assert predecessor.id in relationship.assertion_ids
    assert successor.id in relationship.assertion_ids
    assert predecessor.model_dump(mode="json") == original


def test_keep_and_link_joins_through_analytic_inference_never_deleting_predecessor() -> None:
    predecessor = _direct_assertion("ast_vague_001")
    successor = _direct_assertion("ast_concrete_001")
    original = predecessor.model_dump(mode="json")
    inference = Assertion(
        id="ast_infer_001",
        assertion_type=AssertionType.ANALYTIC_INFERENCE,
        epistemic_scope=EpistemicScope.ANALYTIC_INFERENCE,
        subject_entity_id="evt_ahe004_activity",
        predicate="shares_activity_with",
        object_entity_id="evt_ahe004_activity_concrete",
        status=AssertionStatus.PROPOSED,
        source_authority=SourceAuthority.NOT_APPLICABLE,
        attribution_basis=AttributionBasis.NOT_APPLICABLE,
        supporting_assertion_ids=(predecessor.id, successor.id),
    )
    assert inference.assertion_type is AssertionType.ANALYTIC_INFERENCE
    assert inference.supporting_assertion_ids == (predecessor.id, successor.id)
    assert predecessor.model_dump(mode="json") == original


def test_slots_reject_resolved_subject_without_subject_text() -> None:
    with pytest.raises(ValidationError):
        _slots(subject_text=None, subject_entity_ref="EGE-001")


def test_report_records_zero_writes_and_seals_fingerprint() -> None:
    report = build_eventive_statement_report(items=(recognize_and_reify(slots=_ahe004_slots()),))
    assert report.canonical_write_count == 0
    assert report.proposed_change_count == 0
    assert report.model_execution_count == 0
    assert report.result_fingerprint == eventive_statement_report_fingerprint(report)


def test_report_fingerprint_changes_when_a_shape_changes() -> None:
    report_a = build_eventive_statement_report(items=(recognize_and_reify(slots=_ahe004_slots()),))
    report_b = build_eventive_statement_report(
        items=(recognize_and_reify(slots=_connection_slots()),)
    )
    assert report_a.result_fingerprint != report_b.result_fingerprint


def test_report_items_must_be_distinct_and_ordered() -> None:
    item = recognize_and_reify(slots=_ahe004_slots())
    with pytest.raises(ValidationError):
        EventiveStatementReport(
            items=(item, item),
            canonical_write_count=0,
            proposed_change_count=0,
            model_execution_count=0,
            result_fingerprint="0" * 64,
        )
