"""Focused data-in/data-out tests for R14 centralized identity resolution."""

from __future__ import annotations

import pytest
from kotekomi_application import (
    IdentityResolutionHoldReason,
    IdentityResolutionMention,
    IdentityResolutionOutcome,
    IdentityResolutionReport,
    IdentityResolutionSignal,
    ReificationDraft,
    ReificationObject,
    ReificationSubject,
    ReificationSubjectKind,
    StatementShape,
    build_identity_resolution_report,
    identity_resolution_report_fingerprint,
    mention_from_reification,
    resolve_identity,
)
from kotekomi_domain import (
    Assertion,
    AssertionStatus,
    AssertionType,
    AttributionBasis,
    EpistemicScope,
    SourceAuthority,
)
from pydantic import ValidationError


def _subject(
    kind: ReificationSubjectKind,
    exact_text: str,
    reference_id: str | None = None,
) -> ReificationSubject:
    return ReificationSubject(kind=kind, exact_text=exact_text, reference_id=reference_id)


def _vague_mention() -> IdentityResolutionMention:
    """The kept AHE-004 vague mention: an eventive subject with no reference."""

    return IdentityResolutionMention(
        assertion_id="ast_vague_001",
        event_id="AHE-004",
        subject=_subject(ReificationSubjectKind.EVENT, "Efforts"),
    )


def _concrete_mention(
    *,
    supersedes: str | None = None,
    reference_id: str | None = "ent_efforts_001",
) -> IdentityResolutionMention:
    """One later concrete mention with a resolved entity subject."""

    return IdentityResolutionMention(
        assertion_id="ast_concrete_001",
        event_id="TGE-017",
        subject=_subject(
            ReificationSubjectKind.ENTITY,
            "AI/autonomy efforts",
            reference_id=reference_id,
        ),
        supersedes_assertion_id=supersedes,
    )


def test_explicit_supersede_resolves_a_vague_to_concrete_pair() -> None:
    resolution = resolve_identity(
        vague=_vague_mention(),
        concrete=_concrete_mention(supersedes="ast_vague_001"),
    )
    assert resolution.signal is IdentityResolutionSignal.EXPLICIT_SUPERSEDE
    assert resolution.outcome is IdentityResolutionOutcome.RESOLVED_SAME_ACTIVITY
    assert resolution.hold_reason is None


def test_shared_subject_reference_resolves_a_concrete_to_concrete_pair() -> None:
    vague = IdentityResolutionMention(
        assertion_id="ast_conn_001",
        event_id="TGE-016",
        subject=_subject(
            ReificationSubjectKind.ENTITY,
            "AI/autonomy efforts",
            reference_id="ent_efforts_001",
        ),
    )
    concrete = _concrete_mention(reference_id="ent_efforts_001")
    resolution = resolve_identity(vague=vague, concrete=concrete)
    assert resolution.signal is IdentityResolutionSignal.SHARED_SUBJECT_REFERENCE
    assert resolution.outcome is IdentityResolutionOutcome.RESOLVED_SAME_ACTIVITY


def test_pair_without_any_identity_key_books_no_shared_identity_key() -> None:
    resolution = resolve_identity(vague=_vague_mention(), concrete=_concrete_mention())
    assert resolution.signal is IdentityResolutionSignal.NO_SHARED_IDENTITY_KEY
    assert resolution.outcome is IdentityResolutionOutcome.UNRESOLVED
    assert resolution.link is None
    assert resolution.hold_reason is IdentityResolutionHoldReason.NO_SHARED_IDENTITY_KEY


def test_one_resolver_serves_every_shape() -> None:
    eventive_to_connection = resolve_identity(
        vague=_vague_mention(),
        concrete=_concrete_mention(supersedes="ast_vague_001"),
    )
    connection_to_connection = resolve_identity(
        vague=IdentityResolutionMention(
            assertion_id="ast_conn_001",
            event_id="TGE-016",
            subject=_subject(
                ReificationSubjectKind.ENTITY,
                "AI/autonomy efforts",
                reference_id="ent_efforts_001",
            ),
        ),
        concrete=_concrete_mention(reference_id="ent_efforts_001"),
    )
    eventive_to_eventive = resolve_identity(
        vague=_vague_mention(),
        concrete=IdentityResolutionMention(
            assertion_id="ast_vague_002",
            event_id="AHE-005",
            subject=_subject(ReificationSubjectKind.EVENT, "Recruitment"),
        ),
    )
    assert eventive_to_connection.outcome is IdentityResolutionOutcome.RESOLVED_SAME_ACTIVITY
    assert connection_to_connection.outcome is IdentityResolutionOutcome.RESOLVED_SAME_ACTIVITY
    assert eventive_to_eventive.outcome is IdentityResolutionOutcome.UNRESOLVED


def test_resolved_pair_marks_concrete_as_successor_and_keeps_vague() -> None:
    resolution = resolve_identity(
        vague=_vague_mention(),
        concrete=_concrete_mention(supersedes="ast_vague_001"),
    )
    assert resolution.link is not None
    assert resolution.link.successor_assertion_id == "ast_concrete_001"
    assert resolution.link.predecessor_assertion_id == "ast_vague_001"


def test_resolved_pair_never_deletes_the_vague_assertion() -> None:
    predecessor = _direct_assertion("ast_vague_001")
    original = predecessor.model_dump(mode="json")
    successor = _direct_assertion("ast_concrete_001").model_copy(
        update={"supersedes_assertion_id": predecessor.id}
    )
    assert successor.supersedes_assertion_id == predecessor.id
    assert predecessor.model_dump(mode="json") == original


def test_resolver_never_fabricates_a_subject_reference() -> None:
    vague = _vague_mention()
    concrete = _concrete_mention()
    resolution = resolve_identity(vague=vague, concrete=concrete)
    assert resolution.outcome is IdentityResolutionOutcome.UNRESOLVED
    assert vague.subject.reference_id is None
    assert concrete.subject.reference_id == "ent_efforts_001"


def test_mention_from_reification_drops_shape() -> None:
    connection = mention_from_reification(draft=_connection_draft(), assertion_id="ast_conn_001")
    eventive = mention_from_reification(draft=_eventive_draft(), assertion_id="ast_vague_001")
    assert connection.event_id == "AHE-001"
    assert connection.subject.kind is ReificationSubjectKind.ENTITY
    assert eventive.event_id == "AHE-004"
    assert eventive.subject.kind is ReificationSubjectKind.EVENT
    assert eventive.subject.reference_id is None


def test_closed_identity_key_vocabulary_is_exhaustive() -> None:
    assert {key.value for key in IdentityResolutionSignal} == {
        "explicit_supersede",
        "shared_subject_reference",
        "no_shared_identity_key",
    }


def test_report_records_zero_writes_and_seals_fingerprint() -> None:
    item = resolve_identity(
        vague=_vague_mention(),
        concrete=_concrete_mention(supersedes="ast_vague_001"),
    )
    report = build_identity_resolution_report(items=(item,))
    assert report.canonical_write_count == 0
    assert report.proposed_change_count == 0
    assert report.model_execution_count == 0
    assert report.result_fingerprint == identity_resolution_report_fingerprint(report)


def test_report_fingerprint_changes_when_signal_changes() -> None:
    resolved = build_identity_resolution_report(
        items=(
            resolve_identity(
                vague=_vague_mention(),
                concrete=_concrete_mention(supersedes="ast_vague_001"),
            ),
        )
    )
    unresolved = build_identity_resolution_report(
        items=(resolve_identity(vague=_vague_mention(), concrete=_concrete_mention()),)
    )
    assert resolved.result_fingerprint != unresolved.result_fingerprint


def test_report_items_must_be_distinct_and_ordered() -> None:
    item = resolve_identity(
        vague=_vague_mention(),
        concrete=_concrete_mention(supersedes="ast_vague_001"),
    )
    with pytest.raises(ValidationError):
        IdentityResolutionReport(
            items=(item, item),
            canonical_write_count=0,
            proposed_change_count=0,
            model_execution_count=0,
            result_fingerprint="0" * 64,
        )


def test_resolver_rejects_two_identical_assertions() -> None:
    vague = _vague_mention()
    with pytest.raises(ValueError):
        resolve_identity(vague=vague, concrete=vague)


def test_mention_rejects_self_supersede() -> None:
    with pytest.raises(ValidationError):
        IdentityResolutionMention(
            assertion_id="ast_self_001",
            event_id="TGE-017",
            subject=_subject(
                ReificationSubjectKind.ENTITY,
                "AI/autonomy efforts",
                "ent_efforts_001",
            ),
            supersedes_assertion_id="ast_self_001",
        )


def _direct_assertion(assertion_id: str) -> Assertion:
    return Assertion(
        id=assertion_id,
        assertion_type=AssertionType.SOURCE_CLAIM,
        epistemic_scope=EpistemicScope.SOURCE_REPORT,
        subject_entity_id="evt_ahe004_activity",
        predicate="describes",
        object_value="an artificial-intelligence effort",
        status=AssertionStatus.PROPOSED,
        source_authority=SourceAuthority.SECONDARY,
        attribution_basis=AttributionBasis.DIRECT_DOCUMENT,
        source_ids=("src_example",),
        evidence_target_ids=("etg_example",),
    )


def _connection_draft() -> ReificationDraft:
    return ReificationDraft(
        event_id="AHE-001",
        source_text_sha256="0" * 64,
        statement="Anthropic supplied compute to Stargate.",
        shape=StatementShape.CONNECTION,
        subject=_subject(ReificationSubjectKind.ENTITY, "Anthropic", "EGE-001"),
        predicate_text="supplied",
        predicate_lemma="supply",
        object=ReificationObject(exact_text="Stargate", entity_ref="EGE-002"),
    )


def _eventive_draft() -> ReificationDraft:
    return ReificationDraft(
        event_id="AHE-004",
        source_text_sha256="0" * 64,
        statement=(
            "Efforts to utilize artificial intelligence intensified under the term of "
            "Secretary Ash Carter."
        ),
        shape=StatementShape.EVENTIVE_STATE_CHANGE,
        subject=_subject(ReificationSubjectKind.EVENT, "Efforts"),
        predicate_text="intensified",
        predicate_lemma="intensify",
        object=ReificationObject(
            exact_text="under the term of Secretary Ash Carter",
            value="under the term of Secretary Ash Carter",
        ),
    )