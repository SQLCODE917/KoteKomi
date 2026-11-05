"""Operator journey on the saved Anthropic-DoD run with its real tokens.

Precondition: the disposable operator run exists at
`data/operator-r20-20261103-150517`. The test makes no accepted-state writes outside
that disposable Ledger and calls no model.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from kotekomi_adapters import SQLiteLedgerInitializer, sqlite_ledger_transaction
from kotekomi_adapters.composition_outcome_store import CompositionOutcomeStore
from kotekomi_application import (
    EventCompositionStatus,
    EventConstructionDecisionInput,
)
from kotekomi_domain import AssertionType, AttributionBasis, IdentityOccurrenceKind, SourceAuthority
from kotekomi_pipelines.event_review_workflow import (
    build_event_review_packet,
    recompose_reviewed_event,
    record_review_decision,
)

RETAINED = Path(__file__).resolve().parents[3] / "data" / "operator-r20-20261103-150517"
RUN = "igr_3a167add040a4fcc8aec6aba36363502"
EVENT = "sge_fe4ca1d0afb0c91dbfa9df9d"
NOW = datetime(2026, 1, 1, tzinfo=UTC)

pytestmark = pytest.mark.skipif(
    not (RETAINED / "kotekomi.db").is_file(),
    reason="the retained Anthropic-DoD operator run is not present in this checkout",
)


def _isolated_copy(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Copy the retained run so the tests never mutate operator evidence."""
    import shutil

    root = tmp_path / "state"
    shutil.copytree(RETAINED, root)
    return root, root / "kotekomi.db", root / "archive"


def test_operator_journey_on_the_stored_case(tmp_path: Path) -> None:
    # The disposable run predates the reviewed-decision table; migrate it in place.
    root, LEDGER, ARCHIVE = _isolated_copy(tmp_path)
    SQLiteLedgerInitializer(LEDGER).initialize()

    packet = build_event_review_packet(
        ledger_path=LEDGER,
        archive_path=ARCHIVE,
        ingestion_run_id=RUN,
        event_id=EVENT,
    )
    # The disposable Ledger may already hold this review on a repeated run.
    assert packet.hold_reason in {"assertion_inputs_unavailable", None}
    assert packet.subject_text == "the US"
    assert packet.object_text == "the 2026 Iran war"
    assert (packet.statement_start, packet.statement_end) == (89, 121)

    candidate = next(item for item in packet.candidates if item.exact_text == "US")
    review = record_review_decision(
        ledger_path=LEDGER,
        archive_path=ARCHIVE,
        ingestion_run_id=RUN,
        event_id=EVENT,
        decision=EventConstructionDecisionInput(
            candidate_start=candidate.start,
            candidate_end=candidate.end,
            exact_text=candidate.exact_text,
            identity_kind=IdentityOccurrenceKind.ORGANIZATION,
            identity_decision="new_identity",
            identity_name="United States",
            existing_identity_id=None,
            predicate="started",
            assertion_type=AssertionType.REPORTED_OBSERVATION,
            source_authority=SourceAuthority.SECONDARY,
            attribution_basis=AttributionBasis.DIRECT_DOCUMENT,
            reviewer="operator",
        ),
        now=NOW,
    )

    record = recompose_reviewed_event(
        ledger_path=LEDGER,
        archive_path=ARCHIVE,
        ingestion_run_id=RUN,
        event_id=EVENT,
        now=NOW,
    )

    assert record.status is EventCompositionStatus.COMPOSED
    assertion = record.assertion
    assert assertion is not None
    assert assertion.subject_entity_id == review.subject_identity_id
    assert assertion.predicate == "started"
    assert assertion.object_value == "the 2026 Iran war"
    assert assertion.qualifiers == {"polarity": "affirmed", "modality": "actual"}
    assert assertion.status.value == "proposed"
    assert assertion.evidence_target_ids == (review.statement_evidence_target_id,)

    annotations = CompositionOutcomeStore(root / "composition-outcomes").annotations((EVENT,))
    assert [item.status for item in annotations] == ["composed"]

    with sqlite_ledger_transaction(LEDGER) as repository:
        proposals = [
            change
            for change in repository.list_proposed_changes()
            if change.proposed_json.get("record_type") == "Assertion"
            and change.proposed_json.get("stable_label") == assertion.id
        ]
        target = repository.get_evidence_target(review.statement_evidence_target_id)
    assert len(proposals) == 1
    assert target is not None
    assert target.exact_text == "the US started the 2026 Iran war"


UNSUPPORTED_EVENT = "sge_14b44ada5ff18cabf168a42b"


def test_stored_unsupported_case_holds_without_patching(tmp_path: Path) -> None:
    """The stored blog-post complement governs a clause, so it holds unpatched."""
    root, LEDGER, ARCHIVE = _isolated_copy(tmp_path)
    SQLiteLedgerInitializer(LEDGER).initialize()

    packet = build_event_review_packet(
        ledger_path=LEDGER,
        archive_path=ARCHIVE,
        ingestion_run_id=RUN,
        event_id=UNSUPPORTED_EVENT,
    )
    # A repeated run may already carry the persisted hold instead of the initial one.
    assert packet.hold_reason in {"unsupported_object_complement", "assertion_inputs_unavailable"}
    assert packet.object_completion is None

    with sqlite_ledger_transaction(LEDGER) as repository:
        proposals_before = len(
            [
                change
                for change in repository.list_proposed_changes()
                if change.proposed_json.get("record_type") == "Assertion"
            ]
        )

    candidate = packet.candidates[0]
    record_review_decision(
        ledger_path=LEDGER,
        archive_path=ARCHIVE,
        ingestion_run_id=RUN,
        event_id=UNSUPPORTED_EVENT,
        decision=EventConstructionDecisionInput(
            candidate_start=candidate.start,
            candidate_end=candidate.end,
            exact_text=candidate.exact_text,
            identity_kind=IdentityOccurrenceKind.ORGANIZATION,
            identity_decision="new_identity",
            identity_name="Amodei",
            existing_identity_id=None,
            predicate="published",
            assertion_type=AssertionType.REPORTED_OBSERVATION,
            source_authority=SourceAuthority.SECONDARY,
            attribution_basis=AttributionBasis.DIRECT_DOCUMENT,
            reviewer="operator",
        ),
        now=NOW,
    )

    composed = recompose_reviewed_event(
        ledger_path=LEDGER,
        archive_path=ARCHIVE,
        ingestion_run_id=RUN,
        event_id=UNSUPPORTED_EVENT,
        now=NOW,
    )
    assert composed.status is EventCompositionStatus.HELD
    assert composed.hold_reason == "unsupported_object_complement"
    assert composed.assertion is None

    with sqlite_ledger_transaction(LEDGER) as repository:
        proposals_after = [
            change
            for change in repository.list_proposed_changes()
            if change.proposed_json.get("record_type") == "Assertion"
        ]
    # Recomposition must not add an Assertion proposal for this Event.
    assert len(proposals_after) == proposals_before
