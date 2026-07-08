from pathlib import Path

from kotekomi_adapters import SQLiteLedgerInitializer, sqlite_ledger_transaction

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
        evidence_span,
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
        repository.save_evidence_span(evidence_span)
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
        assert repository.get_evidence_span(evidence_span.id) == evidence_span
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
