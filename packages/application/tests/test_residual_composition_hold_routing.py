"""Focused data-in/data-out tests for R10 residual composition-hold routing."""

from __future__ import annotations

import pytest
from kotekomi_application import (
    AttachmentSourceRange,
    DecontextualizationAttributionKind,
    DecontextualizationHoldReason,
    DecontextualizationRoleKind,
    DecontextualizationStatus,
    DecontextualizedAttribution,
    DecontextualizedProposition,
    DecontextualizedRole,
    EventModality,
    EventPolarity,
    ResidualDisposition,
    ResidualDispositionReason,
    ResidualReviewReason,
    SelectionRouting,
    SelectionRoutingDecision,
    build_residual_composition_hold_report,
    dispose_residual_event,
    dispose_residual_set,
    residual_composition_hold_report_fingerprint,
    validate_held_safety,
)
from pydantic import ValidationError

_SHA = "a" * 64


def _routing(event_id: str, reason: ResidualReviewReason) -> SelectionRouting:
    return SelectionRouting(
        event_id=event_id,
        decision=SelectionRoutingDecision.RESIDUAL_REVIEW,
        reason=reason,
    )


def _accepted(event_id: str) -> SelectionRouting:
    return SelectionRouting(
        event_id=event_id,
        decision=SelectionRoutingDecision.ACCEPTED_SELECTION,
        reason=None,
    )


def _held(event_id: str, reason: DecontextualizationHoldReason) -> DecontextualizedProposition:
    return DecontextualizedProposition(
        event_id=event_id,
        source_text_sha256=_SHA,
        status=DecontextualizationStatus.HELD,
        hold_reason=reason,
    )


def _proposition(event_id: str) -> DecontextualizedProposition:
    return DecontextualizedProposition(
        event_id=event_id,
        source_text_sha256=_SHA,
        relation_label="criticized",
        subject=DecontextualizedRole(
            role=DecontextualizationRoleKind.SUBJECT,
            exact_fragment=AttachmentSourceRange(start=0, end=1, text="A"),
            entity_ref="EGE-001",
        ),
        polarity=EventPolarity.AFFIRMED,
        modality=EventModality.ACTUAL,
        attribution=DecontextualizedAttribution(
            kind=DecontextualizationAttributionKind.SOURCE_NARRATOR
        ),
        status=DecontextualizationStatus.PROPOSITION,
    )


def test_rejected_routing_maps_to_selection_rejected() -> None:
    disposition = dispose_residual_event(
        routing=_routing("AHE-004", ResidualReviewReason.REJECTED)
    )
    assert disposition.event_id == "AHE-004"
    assert disposition.reason is ResidualDispositionReason.SELECTION_REJECTED
    assert disposition.hold_reason is None
    assert disposition.proposition is None


def test_censored_routing_maps_to_selection_censored() -> None:
    disposition = dispose_residual_event(
        routing=_routing("AHE-010", ResidualReviewReason.CENSORED)
    )
    assert disposition.reason is ResidualDispositionReason.SELECTION_CENSORED


def test_below_threshold_routing_maps_to_selection_below_threshold() -> None:
    disposition = dispose_residual_event(
        routing=_routing("AHE-011", ResidualReviewReason.BELOW_THRESHOLD)
    )
    assert disposition.reason is ResidualDispositionReason.SELECTION_BELOW_THRESHOLD


def test_composition_hold_routing_maps_to_selection_abstained() -> None:
    disposition = dispose_residual_event(
        routing=_routing("AHE-051", ResidualReviewReason.COMPOSITION_HOLD)
    )
    assert disposition.reason is ResidualDispositionReason.SELECTION_ABSTAINED
    assert disposition.hold_reason is None


def test_accepted_held_composition_maps_to_composition_hold() -> None:
    composition = _held("AHE-002", DecontextualizationHoldReason.SUBJECT_UNAVAILABLE)
    disposition = dispose_residual_event(routing=_accepted("AHE-002"), composition=composition)
    assert disposition.reason is ResidualDispositionReason.COMPOSITION_HOLD
    assert disposition.hold_reason is DecontextualizationHoldReason.SUBJECT_UNAVAILABLE
    assert disposition.proposition is None


def test_accepted_proposition_maps_to_composable() -> None:
    composition = _proposition("AHE-001")
    disposition = dispose_residual_event(routing=_accepted("AHE-001"), composition=composition)
    assert disposition.reason is ResidualDispositionReason.COMPOSABLE
    assert disposition.proposition is composition


def test_held_composition_never_yields_composable() -> None:
    composition = _held("AHE-002", DecontextualizationHoldReason.ATTRIBUTION_AMBIGUOUS)
    disposition = dispose_residual_event(routing=_accepted("AHE-002"), composition=composition)
    assert disposition.reason is not ResidualDispositionReason.COMPOSABLE


def test_unsupported_residual_reason_raises() -> None:
    with pytest.raises(ValueError):
        dispose_residual_event(
            routing=_routing("AHE-012", ResidualReviewReason.NO_SELECTABLE)
        )


def test_selection_disposition_rejects_a_proposition() -> None:
    with pytest.raises(ValidationError):
        ResidualDisposition(
            event_id="AHE-004",
            reason=ResidualDispositionReason.SELECTION_REJECTED,
            proposition=_proposition("AHE-004"),
        )


def test_composition_hold_requires_one_hold_reason() -> None:
    with pytest.raises(ValidationError):
        ResidualDisposition(
            event_id="AHE-002",
            reason=ResidualDispositionReason.COMPOSITION_HOLD,
        )


def test_composable_rejects_a_held_proposition() -> None:
    with pytest.raises(ValidationError):
        ResidualDisposition(
            event_id="AHE-002",
            reason=ResidualDispositionReason.COMPOSABLE,
            proposition=_held("AHE-002", DecontextualizationHoldReason.SUBJECT_UNAVAILABLE),
        )


def test_dispose_residual_set_is_ordered_and_restricted() -> None:
    routing = (
        _routing("AHE-051", ResidualReviewReason.COMPOSITION_HOLD),
        _routing("AHE-004", ResidualReviewReason.REJECTED),
        _accepted("AHE-001"),
        _routing("AHE-022", ResidualReviewReason.REJECTED),
    )
    dispositions = dispose_residual_set(routing=routing)
    assert tuple(item.event_id for item in dispositions) == ("AHE-004", "AHE-022", "AHE-051")
    assert tuple(item.reason for item in dispositions) == (
        ResidualDispositionReason.SELECTION_REJECTED,
        ResidualDispositionReason.SELECTION_REJECTED,
        ResidualDispositionReason.SELECTION_ABSTAINED,
    )


def test_validate_held_safety_rejects_drift() -> None:
    dispositions = dispose_residual_set(
        routing=(_routing("AHE-004", ResidualReviewReason.REJECTED),)
    )
    with pytest.raises(ValueError):
        validate_held_safety(dispositions=dispositions, residual_event_ids=("AHE-004", "AHE-022"))
    assert (
        validate_held_safety(dispositions=dispositions, residual_event_ids=("AHE-004",))
        == dispositions
    )


def test_report_records_zero_writes_and_seals_fingerprint() -> None:
    dispositions = dispose_residual_set(
        routing=(
            _routing("AHE-004", ResidualReviewReason.REJECTED),
            _routing("AHE-022", ResidualReviewReason.REJECTED),
            _routing("AHE-051", ResidualReviewReason.COMPOSITION_HOLD),
        )
    )
    report = build_residual_composition_hold_report(
        dispositions=dispositions,
        residual_review_event_ids=("AHE-004", "AHE-022", "AHE-051"),
    )
    assert report.canonical_write_count == 0
    assert report.proposed_change_count == 0
    assert report.model_execution_count == 0
    assert report.result_fingerprint == residual_composition_hold_report_fingerprint(report)


def test_report_fingerprint_changes_when_a_disposition_changes() -> None:
    report_a = build_residual_composition_hold_report(
        dispositions=dispose_residual_set(
            routing=(_routing("AHE-004", ResidualReviewReason.REJECTED),)
        ),
        residual_review_event_ids=("AHE-004",),
    )
    report_b = build_residual_composition_hold_report(
        dispositions=dispose_residual_set(
            routing=(_routing("AHE-004", ResidualReviewReason.CENSORED),)
        ),
        residual_review_event_ids=("AHE-004",),
    )
    assert report_a.result_fingerprint != report_b.result_fingerprint