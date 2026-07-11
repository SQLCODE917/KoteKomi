import sqlite3
from pathlib import Path

import pytest
from kotekomi_adapters import (
    ImmutableRecordConflict,
    SQLiteLedgerInitializer,
    sqlite_ledger_transaction,
)

from .domain_fixtures import sample_domain_records


def test_repository_round_trips_all_domain_records(tmp_path: Path) -> None:
    ledger_path = tmp_path / "kotekomi.db"
    SQLiteLedgerInitializer(ledger_path).initialize()
    (
        entity,
        actor,
        organization,
        place,
        event,
        source,
        document,
        evidence_target,
        assertion,
        relationship,
        outcome,
        argument_edge,
        provenance_activity,
        proposed_change,
        briefing,
    ) = sample_domain_records()

    with sqlite_ledger_transaction(ledger_path) as repository:
        repository.save_entity(entity)
        repository.save_actor(actor)
        repository.save_organization(organization)
        repository.save_place(place)
        repository.save_event(event)
        repository.save_source(source)
        repository.save_document(document)
        repository.save_evidence_target(evidence_target)
        repository.save_assertion(assertion)
        repository.save_relationship(relationship)
        repository.save_outcome(outcome)
        repository.save_argument_edge(argument_edge)
        repository.save_provenance_activity(provenance_activity)
        repository.save_proposed_change(proposed_change)
        repository.save_briefing(briefing)

    with sqlite_ledger_transaction(ledger_path) as repository:
        assert repository.get_entity(entity.id) == entity
        assert repository.get_actor(actor.id) == actor
        assert repository.get_organization(organization.id) == organization
        assert repository.get_place(place.id) == place
        assert repository.get_event(event.id) == event
        assert repository.get_source(source.id) == source
        assert repository.get_document(document.id) == document
        assert repository.get_evidence_target(evidence_target.id) == evidence_target
        assert repository.get_assertion(assertion.id) == assertion
        assert repository.get_relationship(relationship.id) == relationship
        assert repository.get_outcome(outcome.id) == outcome
        assert repository.get_argument_edge(argument_edge.id) == argument_edge
        assert repository.get_provenance_activity(provenance_activity.id) == provenance_activity
        assert repository.get_proposed_change(proposed_change.id) == proposed_change
        assert repository.get_briefing(briefing.id) == briefing


def test_repository_lists_records(tmp_path: Path) -> None:
    ledger_path = tmp_path / "kotekomi.db"
    SQLiteLedgerInitializer(ledger_path).initialize()
    actor = sample_domain_records()[1]

    with sqlite_ledger_transaction(ledger_path) as repository:
        repository.save_actor(actor)
        assert repository.list_actors() == (actor,)


def test_immutable_document_reuses_identical_payload_and_rejects_conflict(tmp_path: Path) -> None:
    ledger_path = tmp_path / "kotekomi.db"
    SQLiteLedgerInitializer(ledger_path).initialize()
    document = sample_domain_records()[6]
    with sqlite_ledger_transaction(ledger_path) as repository:
        repository.save_document(document)
        repository.save_document(document)
    conflicting_document = document.model_copy(update={"content_sha256": "b" * 64})
    with pytest.raises(ImmutableRecordConflict):
        with sqlite_ledger_transaction(ledger_path) as repository:
            repository.save_document(conflicting_document)
    with sqlite_ledger_transaction(ledger_path) as repository:
        assert repository.get_document(document.id) == document


def test_immutable_document_conflict_rolls_back_preceding_transaction_writes(
    tmp_path: Path,
) -> None:
    ledger_path = tmp_path / "kotekomi.db"
    SQLiteLedgerInitializer(ledger_path).initialize()
    source, document = sample_domain_records()[5:7]
    with sqlite_ledger_transaction(ledger_path) as repository:
        repository.save_document(document)
    with pytest.raises(ImmutableRecordConflict):
        with sqlite_ledger_transaction(ledger_path) as repository:
            repository.save_source(source)
            repository.save_document(document.model_copy(update={"content_sha256": "b" * 64}))
    with sqlite_ledger_transaction(ledger_path) as repository:
        assert repository.get_source(source.id) is None


def test_sqlite_rejects_direct_immutable_update_and_delete(tmp_path: Path) -> None:
    ledger_path = tmp_path / "kotekomi.db"
    SQLiteLedgerInitializer(ledger_path).initialize()
    document = sample_domain_records()[6]
    with sqlite_ledger_transaction(ledger_path) as repository:
        repository.save_document(document)
    with sqlite3.connect(ledger_path) as connection:
        with pytest.raises(sqlite3.DatabaseError, match="documents are immutable"):
            connection.execute(
                "UPDATE documents SET payload_json = '{}' WHERE id = ?", (document.id,)
            )
        with pytest.raises(sqlite3.DatabaseError, match="documents are immutable"):
            connection.execute("DELETE FROM documents WHERE id = ?", (document.id,))


def test_repository_lists_all_accepted_canonical_records(tmp_path: Path) -> None:
    ledger_path = tmp_path / "kotekomi.db"
    SQLiteLedgerInitializer(ledger_path).initialize()
    (
        entity,
        actor,
        organization,
        place,
        event,
        source,
        document,
        evidence_target,
        assertion,
        relationship,
        outcome,
        argument_edge,
        provenance_activity,
        proposed_change,
        briefing,
    ) = sample_domain_records()

    with sqlite_ledger_transaction(ledger_path) as repository:
        repository.save_entity(entity)
        repository.save_actor(actor)
        repository.save_organization(organization)
        repository.save_place(place)
        repository.save_event(event)
        repository.save_source(source)
        repository.save_document(document)
        repository.save_evidence_target(evidence_target)
        repository.save_assertion(assertion)
        repository.save_relationship(relationship)
        repository.save_outcome(outcome)
        repository.save_argument_edge(argument_edge)
        repository.save_provenance_activity(provenance_activity)
        repository.save_proposed_change(proposed_change)
        repository.save_briefing(briefing)

    with sqlite_ledger_transaction(ledger_path) as repository:
        record_ids = tuple(record.id for record in repository.list_accepted_canonical_records())

    assert record_ids == (
        "act_person_a",
        "arg_release_support",
        "ast_release_review",
        "doc_article_a",
        "ent_actor_a",
        "evt_article_a_release",
        "evt_model_forum",
        "org_lab_a",
        "out_release_review",
        "plc_event_hall",
        "rel_person_a_lab_a",
        "src_article_a",
    )
    assert provenance_activity.id not in record_ids
    assert proposed_change.id not in record_ids
    assert briefing.id not in record_ids
