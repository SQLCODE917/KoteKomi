"""Briefing generation use case."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from kotekomi_domain import (
    Actor,
    ArgumentEdge,
    Assertion,
    AssertionType,
    Briefing,
    Document,
    Entity,
    Event,
    EvidenceSpan,
    Organization,
    Outcome,
    Place,
    ProvenanceActivity,
    Relationship,
    Source,
)

from kotekomi_application.ports import (
    AcceptedCanonicalRecord,
    ArchiveObject,
    ArchiveStore,
    BriefingRenderer,
    BriefingRenderInput,
    StagedArchiveObject,
)

HASH_ID_LENGTH = 24
BRIEFING_GENERATION_ACTIVITY = "briefing_generation"
BRIEFING_GENERATION_AGENT = "kotekomi_briefing"


class BriefingGenerationLedger(Protocol):
    def list_accepted_canonical_records(self) -> tuple[AcceptedCanonicalRecord, ...]: ...
    def list_briefings(self) -> tuple[Briefing, ...]: ...
    def get_briefing(self, record_id: str) -> Briefing | None: ...
    def save_provenance_activity(self, record: ProvenanceActivity) -> None: ...
    def save_briefing(self, record: Briefing) -> None: ...


@dataclass(frozen=True)
class BriefingGenerationInput:
    title: str
    generated_at: datetime
    previous_briefing_id: str | None = None


@dataclass(frozen=True)
class BriefingGenerationResult:
    briefing_id: str
    provenance_activity_id: str
    markdown_path: str
    entity_count: int
    actor_count: int
    organization_count: int
    place_count: int
    event_count: int
    source_count: int
    document_count: int
    evidence_span_count: int
    assertion_count: int
    relationship_count: int
    outcome_count: int
    argument_edge_count: int
    analytic_inference_count: int


def generate_briefing(
    generation_input: BriefingGenerationInput,
    ledger_repository: BriefingGenerationLedger,
    archive_store: ArchiveStore,
    briefing_renderer: BriefingRenderer,
) -> BriefingGenerationResult:
    previous_briefing = _previous_briefing(
        generation_input.previous_briefing_id,
        ledger_repository,
    )
    boundary = previous_briefing.generated_at if previous_briefing is not None else None
    indexes = _record_indexes(ledger_repository.list_accepted_canonical_records())
    selected_ids = _changed_record_ids(indexes, boundary)
    _close_context(selected_ids, indexes)
    selected_records = _selected_records(indexes, selected_ids)

    briefing_id = deterministic_briefing_id(
        title=generation_input.title,
        generated_at=generation_input.generated_at,
        previous_briefing_id=previous_briefing.id if previous_briefing is not None else None,
    )
    provenance_activity_id = deterministic_briefing_provenance_activity_id(
        briefing_id=briefing_id,
        generated_at=generation_input.generated_at,
    )
    render_input = BriefingRenderInput(
        briefing_id=briefing_id,
        title=generation_input.title,
        generated_at=generation_input.generated_at.isoformat(),
        previous_briefing_id=previous_briefing.id if previous_briefing is not None else None,
        entities=selected_records.entities,
        actors=selected_records.actors,
        organizations=selected_records.organizations,
        places=selected_records.places,
        events=selected_records.events,
        sources=selected_records.sources,
        documents=selected_records.documents,
        assertions=selected_records.assertions,
        relationships=selected_records.relationships,
        outcomes=selected_records.outcomes,
        argument_edges=selected_records.argument_edges,
        evidence_spans=selected_records.evidence_spans,
        analytic_inference_assertion_ids=selected_records.analytic_inference_assertion_ids,
    )
    rendered = briefing_renderer.render(render_input)

    staged_object: StagedArchiveObject | None = None
    promoted_object: ArchiveObject | None = None
    try:
        staged_object = archive_store.stage_briefing_markdown(briefing_id, rendered.markdown)
        promoted_object = archive_store.promote_staged_object(staged_object)
        provenance_activity = ProvenanceActivity(
            id=provenance_activity_id,
            activity_type=BRIEFING_GENERATION_ACTIVITY,
            agent=BRIEFING_GENERATION_AGENT,
            input_ids=selected_records.input_ids,
            output_ids=(briefing_id,),
            occurred_at=generation_input.generated_at,
        )
        briefing = Briefing(
            id=briefing_id,
            title=generation_input.title,
            previous_briefing_id=previous_briefing.id if previous_briefing is not None else None,
            entity_ids=tuple(record.id for record in selected_records.entities),
            actor_ids=tuple(record.id for record in selected_records.actors),
            organization_ids=tuple(record.id for record in selected_records.organizations),
            place_ids=tuple(record.id for record in selected_records.places),
            event_ids=tuple(record.id for record in selected_records.events),
            document_ids=tuple(record.id for record in selected_records.documents),
            assertion_ids=tuple(record.id for record in selected_records.assertions),
            relationship_ids=tuple(record.id for record in selected_records.relationships),
            argument_edge_ids=tuple(record.id for record in selected_records.argument_edges),
            outcome_ids=tuple(record.id for record in selected_records.outcomes),
            source_ids=tuple(record.id for record in selected_records.sources),
            evidence_span_ids=tuple(record.id for record in selected_records.evidence_spans),
            analytic_inference_assertion_ids=selected_records.analytic_inference_assertion_ids,
            provenance_activity_id=provenance_activity_id,
            markdown_path=promoted_object.relative_path,
            generated_at=generation_input.generated_at,
        )
        ledger_repository.save_provenance_activity(provenance_activity)
        ledger_repository.save_briefing(briefing)
    except Exception:
        if promoted_object is not None:
            archive_store.delete_object(promoted_object.relative_path)
        if staged_object is not None:
            archive_store.delete_object(staged_object.staged_relative_path)
        raise

    return BriefingGenerationResult(
        briefing_id=briefing_id,
        provenance_activity_id=provenance_activity_id,
        markdown_path=promoted_object.relative_path,
        entity_count=len(selected_records.entities),
        actor_count=len(selected_records.actors),
        organization_count=len(selected_records.organizations),
        place_count=len(selected_records.places),
        event_count=len(selected_records.events),
        source_count=len(selected_records.sources),
        document_count=len(selected_records.documents),
        evidence_span_count=len(selected_records.evidence_spans),
        assertion_count=len(selected_records.assertions),
        relationship_count=len(selected_records.relationships),
        outcome_count=len(selected_records.outcomes),
        argument_edge_count=len(selected_records.argument_edges),
        analytic_inference_count=len(selected_records.analytic_inference_assertion_ids),
    )


def cleanup_created_briefing_archive_object(
    *,
    archive_store: ArchiveStore,
    markdown_path: str,
) -> None:
    archive_store.delete_object(markdown_path)


def deterministic_briefing_id(
    *,
    title: str,
    generated_at: datetime,
    previous_briefing_id: str | None,
) -> str:
    digest = hashlib.sha256(
        f"{title}:{generated_at.isoformat()}:{previous_briefing_id or ''}".encode()
    ).hexdigest()
    return f"brf_{digest[:HASH_ID_LENGTH]}"


def deterministic_briefing_provenance_activity_id(
    *,
    briefing_id: str,
    generated_at: datetime,
) -> str:
    digest = hashlib.sha256(
        f"{BRIEFING_GENERATION_ACTIVITY}:{briefing_id}:{generated_at.isoformat()}".encode()
    ).hexdigest()
    return f"prv_{digest[:HASH_ID_LENGTH]}"


@dataclass(frozen=True)
class _RecordIndexes:
    entities: dict[str, Entity]
    actors: dict[str, Actor]
    organizations: dict[str, Organization]
    places: dict[str, Place]
    events: dict[str, Event]
    sources: dict[str, Source]
    documents: dict[str, Document]
    evidence_spans: dict[str, EvidenceSpan]
    assertions: dict[str, Assertion]
    relationships: dict[str, Relationship]
    outcomes: dict[str, Outcome]
    argument_edges: dict[str, ArgumentEdge]


def _empty_id_set() -> set[str]:
    return set()


@dataclass
class _SelectedIds:
    entity_ids: set[str] = field(default_factory=_empty_id_set)
    actor_ids: set[str] = field(default_factory=_empty_id_set)
    organization_ids: set[str] = field(default_factory=_empty_id_set)
    place_ids: set[str] = field(default_factory=_empty_id_set)
    event_ids: set[str] = field(default_factory=_empty_id_set)
    source_ids: set[str] = field(default_factory=_empty_id_set)
    document_ids: set[str] = field(default_factory=_empty_id_set)
    evidence_span_ids: set[str] = field(default_factory=_empty_id_set)
    assertion_ids: set[str] = field(default_factory=_empty_id_set)
    relationship_ids: set[str] = field(default_factory=_empty_id_set)
    outcome_ids: set[str] = field(default_factory=_empty_id_set)
    argument_edge_ids: set[str] = field(default_factory=_empty_id_set)


@dataclass(frozen=True)
class _SelectedRecords:
    entities: tuple[Entity, ...]
    actors: tuple[Actor, ...]
    organizations: tuple[Organization, ...]
    places: tuple[Place, ...]
    events: tuple[Event, ...]
    sources: tuple[Source, ...]
    documents: tuple[Document, ...]
    evidence_spans: tuple[EvidenceSpan, ...]
    assertions: tuple[Assertion, ...]
    relationships: tuple[Relationship, ...]
    outcomes: tuple[Outcome, ...]
    argument_edges: tuple[ArgumentEdge, ...]
    analytic_inference_assertion_ids: tuple[str, ...]
    input_ids: tuple[str, ...]


def _previous_briefing(
    previous_briefing_id: str | None,
    ledger_repository: BriefingGenerationLedger,
) -> Briefing | None:
    if previous_briefing_id is not None:
        briefing = ledger_repository.get_briefing(previous_briefing_id)
        if briefing is None:
            raise ValueError(f"Previous Briefing not found: {previous_briefing_id}")
        return briefing
    briefings = ledger_repository.list_briefings()
    if not briefings:
        return None
    return max(briefings, key=lambda briefing: briefing.generated_at)


def _record_indexes(records: tuple[AcceptedCanonicalRecord, ...]) -> _RecordIndexes:
    indexes = _RecordIndexes(
        entities={},
        actors={},
        organizations={},
        places={},
        events={},
        sources={},
        documents={},
        evidence_spans={},
        assertions={},
        relationships={},
        outcomes={},
        argument_edges={},
    )
    for record in records:
        if isinstance(record, Entity):
            indexes.entities[record.id] = record
        elif isinstance(record, Actor):
            indexes.actors[record.id] = record
        elif isinstance(record, Organization):
            indexes.organizations[record.id] = record
        elif isinstance(record, Place):
            indexes.places[record.id] = record
        elif isinstance(record, Event):
            indexes.events[record.id] = record
        elif isinstance(record, Source):
            indexes.sources[record.id] = record
        elif isinstance(record, Document):
            indexes.documents[record.id] = record
        elif isinstance(record, EvidenceSpan):
            indexes.evidence_spans[record.id] = record
        elif isinstance(record, Assertion):
            indexes.assertions[record.id] = record
        elif isinstance(record, Relationship):
            indexes.relationships[record.id] = record
        elif isinstance(record, Outcome):
            indexes.outcomes[record.id] = record
        elif isinstance(record, ArgumentEdge):  # pyright: ignore[reportUnnecessaryIsInstance]
            indexes.argument_edges[record.id] = record
        else:
            raise TypeError(f"Unsupported accepted canonical record type: {type(record).__name__}")
    return indexes


def _changed_record_ids(indexes: _RecordIndexes, boundary: datetime | None) -> _SelectedIds:
    selected_ids = _SelectedIds()
    selected_ids.entity_ids.update(
        record.id
        for record in indexes.entities.values()
        if _is_changed(record.created_at, boundary)
    )
    selected_ids.actor_ids.update(
        record.id for record in indexes.actors.values() if _is_changed(record.updated_at, boundary)
    )
    selected_ids.organization_ids.update(
        record.id
        for record in indexes.organizations.values()
        if _is_changed(record.updated_at, boundary)
    )
    selected_ids.place_ids.update(
        record.id for record in indexes.places.values() if _is_changed(record.updated_at, boundary)
    )
    selected_ids.event_ids.update(
        record.id for record in indexes.events.values() if _is_changed(record.updated_at, boundary)
    )
    selected_ids.source_ids.update(
        record.id for record in indexes.sources.values() if _is_changed(record.updated_at, boundary)
    )
    selected_ids.document_ids.update(
        record.id
        for record in indexes.documents.values()
        if _is_changed(record.updated_at, boundary)
    )
    selected_ids.evidence_span_ids.update(
        record.id
        for record in indexes.evidence_spans.values()
        if _is_changed(record.created_at, boundary)
    )
    selected_ids.assertion_ids.update(
        record.id
        for record in indexes.assertions.values()
        if _is_changed(record.updated_at, boundary)
    )
    selected_ids.relationship_ids.update(
        record.id
        for record in indexes.relationships.values()
        if _is_changed(record.updated_at, boundary)
    )
    selected_ids.outcome_ids.update(
        record.id
        for record in indexes.outcomes.values()
        if _is_changed(record.updated_at, boundary)
    )
    selected_ids.argument_edge_ids.update(
        record.id
        for record in indexes.argument_edges.values()
        if _is_changed(record.created_at, boundary)
    )
    return selected_ids


def _close_context(selected_ids: _SelectedIds, indexes: _RecordIndexes) -> None:
    changed = True
    while changed:
        changed = False
        for actor_id in tuple(selected_ids.actor_ids):
            actor = _require(indexes.actors, actor_id, "Actor", actor_id)
            for organization_id in actor.organization_ids:
                changed |= _add_required(
                    selected_ids.organization_ids,
                    indexes.organizations,
                    organization_id,
                    "Organization",
                    actor.id,
                )
        for event_id in tuple(selected_ids.event_ids):
            event = _require(indexes.events, event_id, "Event", event_id)
            if event.place_id is not None:
                changed |= _add_required(
                    selected_ids.place_ids,
                    indexes.places,
                    event.place_id,
                    "Place",
                    event.id,
                )
            for actor_id in event.participant_actor_ids:
                changed |= _add_required(
                    selected_ids.actor_ids,
                    indexes.actors,
                    actor_id,
                    "Actor",
                    event.id,
                )
            for organization_id in event.participant_organization_ids:
                changed |= _add_required(
                    selected_ids.organization_ids,
                    indexes.organizations,
                    organization_id,
                    "Organization",
                    event.id,
                )
        for document_id in tuple(selected_ids.document_ids):
            document = _require(indexes.documents, document_id, "Document", document_id)
            changed |= _add_required(
                selected_ids.source_ids,
                indexes.sources,
                document.source_id,
                "Source",
                document.id,
            )
        for evidence_span_id in tuple(selected_ids.evidence_span_ids):
            evidence_span = _require(
                indexes.evidence_spans,
                evidence_span_id,
                "EvidenceSpan",
                evidence_span_id,
            )
            changed |= _add_required(
                selected_ids.source_ids,
                indexes.sources,
                evidence_span.source_id,
                "Source",
                evidence_span.id,
            )
            changed |= _add_required(
                selected_ids.document_ids,
                indexes.documents,
                evidence_span.document_id,
                "Document",
                evidence_span.id,
            )
            if evidence_span.assertion_id is not None:
                changed |= _add_required(
                    selected_ids.assertion_ids,
                    indexes.assertions,
                    evidence_span.assertion_id,
                    "Assertion",
                    evidence_span.id,
                )
        for assertion_id in tuple(selected_ids.assertion_ids):
            assertion = _require(indexes.assertions, assertion_id, "Assertion", assertion_id)
            changed |= _add_entity_reference(
                selected_ids,
                indexes,
                assertion.subject_entity_id,
                assertion.id,
            )
            if assertion.object_entity_id is not None:
                changed |= _add_entity_reference(
                    selected_ids,
                    indexes,
                    assertion.object_entity_id,
                    assertion.id,
                )
            for source_id in assertion.source_ids:
                changed |= _add_required(
                    selected_ids.source_ids,
                    indexes.sources,
                    source_id,
                    "Source",
                    assertion.id,
                )
            for evidence_span_id in assertion.evidence_span_ids:
                changed |= _add_required(
                    selected_ids.evidence_span_ids,
                    indexes.evidence_spans,
                    evidence_span_id,
                    "EvidenceSpan",
                    assertion.id,
                )
        for relationship_id in tuple(selected_ids.relationship_ids):
            relationship = _require(
                indexes.relationships,
                relationship_id,
                "Relationship",
                relationship_id,
            )
            changed |= _add_entity_reference(
                selected_ids,
                indexes,
                relationship.subject_id,
                relationship.id,
            )
            changed |= _add_entity_reference(
                selected_ids,
                indexes,
                relationship.object_id,
                relationship.id,
            )
            for assertion_id in relationship.assertion_ids:
                changed |= _add_required(
                    selected_ids.assertion_ids,
                    indexes.assertions,
                    assertion_id,
                    "Assertion",
                    relationship.id,
                )
        for outcome_id in tuple(selected_ids.outcome_ids):
            outcome = _require(indexes.outcomes, outcome_id, "Outcome", outcome_id)
            for actor_id in outcome.actor_ids:
                changed |= _add_required(
                    selected_ids.actor_ids,
                    indexes.actors,
                    actor_id,
                    "Actor",
                    outcome.id,
                )
            for organization_id in outcome.organization_ids:
                changed |= _add_required(
                    selected_ids.organization_ids,
                    indexes.organizations,
                    organization_id,
                    "Organization",
                    outcome.id,
                )
            for event_id in outcome.event_ids:
                changed |= _add_required(
                    selected_ids.event_ids,
                    indexes.events,
                    event_id,
                    "Event",
                    outcome.id,
                )
            for assertion_id in outcome.assertion_ids:
                changed |= _add_required(
                    selected_ids.assertion_ids,
                    indexes.assertions,
                    assertion_id,
                    "Assertion",
                    outcome.id,
                )
        for argument_edge_id in tuple(selected_ids.argument_edge_ids):
            argument_edge = _require(
                indexes.argument_edges,
                argument_edge_id,
                "ArgumentEdge",
                argument_edge_id,
            )
            for assertion_id in (argument_edge.from_assertion_id, argument_edge.to_assertion_id):
                changed |= _add_required(
                    selected_ids.assertion_ids,
                    indexes.assertions,
                    assertion_id,
                    "Assertion",
                    argument_edge.id,
                )
            for evidence_span_id in argument_edge.evidence_span_ids:
                changed |= _add_required(
                    selected_ids.evidence_span_ids,
                    indexes.evidence_spans,
                    evidence_span_id,
                    "EvidenceSpan",
                    argument_edge.id,
                )


def _selected_records(indexes: _RecordIndexes, selected_ids: _SelectedIds) -> _SelectedRecords:
    entities = _records_for_ids(indexes.entities, selected_ids.entity_ids)
    actors = _records_for_ids(indexes.actors, selected_ids.actor_ids)
    organizations = _records_for_ids(indexes.organizations, selected_ids.organization_ids)
    places = _records_for_ids(indexes.places, selected_ids.place_ids)
    events = _records_for_ids(indexes.events, selected_ids.event_ids)
    sources = _records_for_ids(indexes.sources, selected_ids.source_ids)
    documents = _records_for_ids(indexes.documents, selected_ids.document_ids)
    evidence_spans = _records_for_ids(indexes.evidence_spans, selected_ids.evidence_span_ids)
    assertions = _records_for_ids(indexes.assertions, selected_ids.assertion_ids)
    relationships = _records_for_ids(indexes.relationships, selected_ids.relationship_ids)
    outcomes = _records_for_ids(indexes.outcomes, selected_ids.outcome_ids)
    argument_edges = _records_for_ids(indexes.argument_edges, selected_ids.argument_edge_ids)
    analytic_inference_assertion_ids = tuple(
        record.id
        for record in assertions
        if record.assertion_type is AssertionType.ANALYTIC_INFERENCE
    )
    input_ids = tuple(
        sorted(
            {
                *(record.id for record in entities),
                *(record.id for record in actors),
                *(record.id for record in organizations),
                *(record.id for record in places),
                *(record.id for record in events),
                *(record.id for record in sources),
                *(record.id for record in documents),
                *(record.id for record in evidence_spans),
                *(record.id for record in assertions),
                *(record.id for record in relationships),
                *(record.id for record in outcomes),
                *(record.id for record in argument_edges),
            }
        )
    )
    return _SelectedRecords(
        entities=entities,
        actors=actors,
        organizations=organizations,
        places=places,
        events=events,
        sources=sources,
        documents=documents,
        evidence_spans=evidence_spans,
        assertions=assertions,
        relationships=relationships,
        outcomes=outcomes,
        argument_edges=argument_edges,
        analytic_inference_assertion_ids=analytic_inference_assertion_ids,
        input_ids=input_ids,
    )


def _is_changed(record_time: datetime, boundary: datetime | None) -> bool:
    return boundary is None or record_time > boundary


def _add_entity_reference(
    selected_ids: _SelectedIds,
    indexes: _RecordIndexes,
    record_id: str,
    referring_record_id: str,
) -> bool:
    if record_id.startswith("ent_"):
        return _add_required(
            selected_ids.entity_ids,
            indexes.entities,
            record_id,
            "Entity",
            referring_record_id,
        )
    if record_id.startswith("act_"):
        return _add_required(
            selected_ids.actor_ids,
            indexes.actors,
            record_id,
            "Actor",
            referring_record_id,
        )
    if record_id.startswith("org_"):
        return _add_required(
            selected_ids.organization_ids,
            indexes.organizations,
            record_id,
            "Organization",
            referring_record_id,
        )
    if record_id.startswith("evt_"):
        return _add_required(
            selected_ids.event_ids,
            indexes.events,
            record_id,
            "Event",
            referring_record_id,
        )
    if record_id.startswith("plc_"):
        return _add_required(
            selected_ids.place_ids,
            indexes.places,
            record_id,
            "Place",
            referring_record_id,
        )
    raise ValueError(
        f"Briefing record {referring_record_id} references unsupported entity record: {record_id}"
    )


def _add_required[DomainRecord](
    selected_ids: set[str],
    records_by_id: dict[str, DomainRecord],
    record_id: str,
    record_type: str,
    referring_record_id: str,
) -> bool:
    _require(records_by_id, record_id, record_type, referring_record_id)
    before = len(selected_ids)
    selected_ids.add(record_id)
    return len(selected_ids) != before


def _require[DomainRecord](
    records_by_id: dict[str, DomainRecord],
    record_id: str,
    record_type: str,
    referring_record_id: str,
) -> DomainRecord:
    record = records_by_id.get(record_id)
    if record is None:
        raise ValueError(
            f"Briefing record {referring_record_id} references missing {record_type}: {record_id}"
        )
    return record


def _records_for_ids[DomainRecord](
    records_by_id: dict[str, DomainRecord],
    record_ids: set[str],
) -> tuple[DomainRecord, ...]:
    return tuple(records_by_id[record_id] for record_id in sorted(record_ids))
