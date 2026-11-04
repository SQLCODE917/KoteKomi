"""An unsupported object complement stays a persisted hold end to end.

The packet reports the hold, review still records the accepted identity, and
explicit recomposition persists the hold without proposing an Assertion.
The derivation is made unsupported deterministically; the hold behaviour under
test is the production path.
"""

from __future__ import annotations

import io
from datetime import UTC, datetime
from pathlib import Path

import pytest
from kotekomi_adapters import sqlite_ledger_transaction
from kotekomi_adapters.composition_outcome_store import CompositionOutcomeStore
from kotekomi_application import (
    EventCompositionStatus,
    EventConstructionDecisionInput,
    ObjectComplementUnsupported,
)
from kotekomi_domain import AssertionType, AttributionBasis, IdentityOccurrenceKind, SourceAuthority
from kotekomi_pipelines import event_review_workflow
from kotekomi_pipelines.event_review_workflow import (
    build_event_review_packet,
    recompose_reviewed_event,
    record_review_decision,
)
from kotekomi_pipelines.ingestion_workflow import run_ingestion_workflow

from packages.pipelines.tests.support.operator_journey_fixtures import (
    PDF_FIXTURE,
    install_ingestion_fixtures,
)

NOW = datetime(2026, 1, 1, tzinfo=UTC)
SOURCE_URL = "https://example.test/pdf"


@pytest.fixture
def ingested(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    install_ingestion_fixtures(monkeypatch)
    state = tmp_path / "state"
    config = tmp_path / "kotekomi.toml"
    config.write_text(
        f'ledger_path = "{(state / "kotekomi.db").as_posix()}"\n'
        f'archive_path = "{(state / "archive").as_posix()}"\n'
        'runtime_profile = "fixture"\n[processing]\n'
        'representation_policy_version = "deposited-source-v1"\n',
        encoding="utf-8",
    )
    result = run_ingestion_workflow(
        config_path=config,
        source_file_path=PDF_FIXTURE,
        source_url=SOURCE_URL,
        stdout=io.StringIO(),
        stderr=io.StringIO(),
    )
    assert result.ingestion_code == 0
    assert result.composition_records

    def unsupported(**_kwargs: object) -> None:
        raise ObjectComplementUnsupported("simulated governed clause")

    # Both call sites must see the same unsupported construction: the packet
    # derives it, and the retained composer re-derives it at its own boundary.
    monkeypatch.setattr(event_review_workflow, "derive_object_content_completion", unsupported)
    monkeypatch.setattr(
        "kotekomi_application.decontextualization_composition.derive_object_content_completion",
        unsupported,
    )
    return {
        "state": state,
        "ledger": state / "kotekomi.db",
        "archive": state / "archive",
        "run_id": result.ingestion_run_id,
        "event_id": result.composition_records[0].event_id,
    }


def _decision(packet) -> EventConstructionDecisionInput:
    candidate = packet.candidates[0]
    return EventConstructionDecisionInput(
        candidate_start=candidate.start,
        candidate_end=candidate.end,
        exact_text=candidate.exact_text,
        identity_kind=IdentityOccurrenceKind.ORGANIZATION,
        identity_decision="new_identity",
        identity_name=candidate.identity_name,
        existing_identity_id=None,
        predicate="shared",
        assertion_type=AssertionType.REPORTED_OBSERVATION,
        source_authority=SourceAuthority.SECONDARY,
        attribution_basis=AttributionBasis.DIRECT_DOCUMENT,
        reviewer="operator",
    )


def test_unsupported_complement_holds_through_the_pipeline(ingested) -> None:
    ledger, archive = ingested["ledger"], ingested["archive"]
    run_id, event_id = ingested["run_id"], ingested["event_id"]

    packet = build_event_review_packet(
        ledger_path=ledger,
        archive_path=archive,
        ingestion_run_id=run_id,
        event_id=event_id,
    )
    assert packet.hold_reason == "unsupported_object_complement"
    assert packet.object_completion is None

    review = record_review_decision(
        ledger_path=ledger,
        archive_path=archive,
        ingestion_run_id=run_id,
        event_id=event_id,
        decision=_decision(packet),
        now=NOW,
    )
    assert review.evidence_target_id

    first = recompose_reviewed_event(
        ledger_path=ledger,
        archive_path=archive,
        ingestion_run_id=run_id,
        event_id=event_id,
        now=NOW,
    )
    assert first.status is EventCompositionStatus.HELD
    assert first.hold_reason == "unsupported_object_complement"
    assert first.assertion is None
    assert first.object_text is None

    stored = CompositionOutcomeStore(ingested["state"] / "composition-outcomes").load(event_id)
    assert stored.hold_reason == "unsupported_object_complement"
    annotations = CompositionOutcomeStore(ingested["state"] / "composition-outcomes").annotations(
        (event_id,)
    )
    assert [item.status for item in annotations] == ["held"]

    with sqlite_ledger_transaction(ledger) as repository:
        assertion_proposals = [
            change
            for change in repository.list_proposed_changes()
            if change.proposed_json.get("record_type") == "Assertion"
        ]
    assert assertion_proposals == []

    second = recompose_reviewed_event(
        ledger_path=ledger,
        archive_path=archive,
        ingestion_run_id=run_id,
        event_id=event_id,
        now=NOW,
    )
    assert second.status is EventCompositionStatus.HELD
    assert second.hold_reason == "unsupported_object_complement"
    assert second.assertion is None
    with sqlite_ledger_transaction(ledger) as repository:
        assert [
            change
            for change in repository.list_proposed_changes()
            if change.proposed_json.get("record_type") == "Assertion"
        ] == []
