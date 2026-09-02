import pytest
from kotekomi_application.hybrid_atomic_claims import (
    AtomicClaimDraft,
    AtomicClaimObjectKind,
    EventSubjectDraft,
    OntologyValidationFinding,
    OntologyValidationReport,
    OntologyValidationStatus,
    atomic_claim_draft_id,
    event_subject_draft_id,
    ontology_validation_report_id,
)
from kotekomi_domain import HybridEventStructuralPredicate

PARENT_ID = "hep_" + "1" * 24
FRAME_ID = "efd_" + "2" * 24
TRIGGER_ID = "etd_" + "3" * 24
TARGET_ID = "etg_" + "4" * 24
ATTEMPT_ID = "eva_" + "5" * 24
TRACE_ID = "xst_" + "6" * 24


def _subject() -> EventSubjectDraft:
    return EventSubjectDraft(
        id=event_subject_draft_id(PARENT_ID, FRAME_ID, TRIGGER_ID),
        parent_preview_id=PARENT_ID,
        frame_id=FRAME_ID,
        trigger_id=TRIGGER_ID,
    )


def _claim(role_label: str = "beneficiary") -> AtomicClaimDraft:
    subject = _subject()
    candidate_id = "mnc_" + "7" * 24
    claim_id = atomic_claim_draft_id(
        frame_id=FRAME_ID,
        event_subject_id=subject.id,
        predicate=HybridEventStructuralPredicate.HAS_ARGUMENT,
        object_kind=AtomicClaimObjectKind.MENTION_CANDIDATE,
        object_reference_id=candidate_id,
        object_value=None,
        role_label=role_label,
        evidence_target_id=TARGET_ID,
        evidence_validation_attempt_id=ATTEMPT_ID,
        source_trace_ids=(TRACE_ID,),
    )
    return AtomicClaimDraft(
        id=claim_id,
        frame_id=FRAME_ID,
        event_subject_id=subject.id,
        predicate=HybridEventStructuralPredicate.HAS_ARGUMENT,
        object_kind=AtomicClaimObjectKind.MENTION_CANDIDATE,
        object_reference_id=candidate_id,
        role_label=role_label,
        evidence_target_id=TARGET_ID,
        evidence_validation_attempt_id=ATTEMPT_ID,
        source_trace_ids=(TRACE_ID,),
    )


def test_unknown_role_is_preserved_in_a_nonconformant_report() -> None:
    claim = _claim()
    finding = OntologyValidationFinding(
        code="unmapped_argument_role",
        frame_id=FRAME_ID,
        claim_id=claim.id,
        field_path="arguments[0].role_label",
        proposed_value="beneficiary",
    )
    report_id = ontology_validation_report_id(
        frame_id=FRAME_ID,
        ontology_slice_id="hybrid_event_core_v1",
        ontology_slice_sha256="8" * 64,
        claim_ids=(claim.id,),
        status=OntologyValidationStatus.NONCONFORMANT,
        findings=(finding,),
    )
    report = OntologyValidationReport(
        id=report_id,
        frame_id=FRAME_ID,
        ontology_slice_id="hybrid_event_core_v1",
        ontology_slice_sha256="8" * 64,
        claim_ids=(claim.id,),
        status=OntologyValidationStatus.NONCONFORMANT,
        findings=(finding,),
    )

    assert claim.role_label == "beneficiary"
    assert report.findings == (finding,)


def test_argument_claim_requires_a_candidate_reference() -> None:
    subject = _subject()
    claim_id = atomic_claim_draft_id(
        frame_id=FRAME_ID,
        event_subject_id=subject.id,
        predicate=HybridEventStructuralPredicate.HAS_ARGUMENT,
        object_kind=AtomicClaimObjectKind.LITERAL,
        object_reference_id=None,
        object_value="Anthropic",
        role_label="actor",
        evidence_target_id=TARGET_ID,
        evidence_validation_attempt_id=ATTEMPT_ID,
        source_trace_ids=(TRACE_ID,),
    )
    with pytest.raises(ValueError, match="MentionCandidate"):
        AtomicClaimDraft(
            id=claim_id,
            frame_id=FRAME_ID,
            event_subject_id=subject.id,
            predicate=HybridEventStructuralPredicate.HAS_ARGUMENT,
            object_kind=AtomicClaimObjectKind.LITERAL,
            object_value="Anthropic",
            role_label="actor",
            evidence_target_id=TARGET_ID,
            evidence_validation_attempt_id=ATTEMPT_ID,
            source_trace_ids=(TRACE_ID,),
        )
