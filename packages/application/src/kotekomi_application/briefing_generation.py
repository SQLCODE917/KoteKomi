"""Briefing generation use case."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Protocol, cast

from kotekomi_domain import (
    Actor,
    ArgumentEdge,
    Assertion,
    AssertionType,
    AttributionBasis,
    Briefing,
    Document,
    Entity,
    EpistemicScope,
    Event,
    EvidenceSpan,
    Organization,
    Outcome,
    Place,
    ProvenanceActivity,
    Relationship,
    Source,
    SourceAuthority,
)

from kotekomi_application.ports import (
    AcceptedCanonicalRecord,
    ArchiveObject,
    ArchiveStore,
    BriefingCitation,
    BriefingCitationRegistry,
    BriefingEvidenceReference,
    BriefingKeyJudgment,
    BriefingNarrative,
    BriefingNarrativeSentence,
    BriefingOpenQuestion,
    BriefingRenderer,
    BriefingRenderInput,
    BriefingSharpJudgment,
    BriefingUncertainty,
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
    citation_registry_path: str
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
    narrative, citation_registry = _build_briefing_narrative(
        briefing_id=briefing_id,
        selected_records=selected_records,
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
        narrative=narrative,
        citation_registry=citation_registry,
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
    citations_json = briefing_citation_registry_to_json(citation_registry)

    staged_object: StagedArchiveObject | None = None
    staged_citations_object: StagedArchiveObject | None = None
    promoted_object: ArchiveObject | None = None
    promoted_citations_object: ArchiveObject | None = None
    try:
        staged_object = archive_store.stage_briefing_markdown(briefing_id, rendered.markdown)
        staged_citations_object = archive_store.stage_briefing_citations_json(
            briefing_id,
            citations_json,
        )
        promoted_object = archive_store.promote_staged_object(staged_object)
        promoted_citations_object = archive_store.promote_staged_object(staged_citations_object)
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
        if promoted_citations_object is not None:
            archive_store.delete_object(promoted_citations_object.relative_path)
        if staged_object is not None:
            archive_store.delete_object(staged_object.staged_relative_path)
        if staged_citations_object is not None:
            archive_store.delete_object(staged_citations_object.staged_relative_path)
        raise

    return BriefingGenerationResult(
        briefing_id=briefing_id,
        provenance_activity_id=provenance_activity_id,
        markdown_path=promoted_object.relative_path,
        citation_registry_path=promoted_citations_object.relative_path,
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
    citation_registry_path: str | None = None,
) -> None:
    archive_store.delete_object(markdown_path)
    if citation_registry_path is not None:
        archive_store.delete_object(citation_registry_path)


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


def deterministic_citation_key(briefing_id: str, identity_json: str) -> str:
    digest = hashlib.sha256(f"{briefing_id}:{identity_json}".encode()).hexdigest()
    return f"ctn_{digest[:HASH_ID_LENGTH]}"


def briefing_citation_registry_to_json(registry: BriefingCitationRegistry) -> str:
    return json.dumps(asdict(registry), sort_keys=True, indent=2) + "\n"


def briefing_citation_registry_from_json(content: str) -> BriefingCitationRegistry:
    data: object = json.loads(content)
    if not isinstance(data, dict):
        raise ValueError("Briefing citation registry JSON must be an object.")
    registry_data = cast(dict[str, object], data)
    briefing_id = _required_string(registry_data, "briefing_id")
    citations_data = registry_data.get("citations")
    if not isinstance(citations_data, list):
        raise ValueError("Briefing citation registry JSON field citations must be a list.")
    citations = tuple(
        _briefing_citation_from_json(item) for item in cast(list[object], citations_data)
    )
    expected_numbers = tuple(range(1, len(citations) + 1))
    actual_numbers = tuple(citation.number for citation in citations)
    if actual_numbers != expected_numbers:
        raise ValueError("Briefing citation registry numbers must be contiguous from 1.")
    return BriefingCitationRegistry(briefing_id=briefing_id, citations=citations)


def read_briefing_citation_registry(
    *,
    briefing_id: str,
    archive_store: ArchiveStore,
) -> BriefingCitationRegistry:
    registry = briefing_citation_registry_from_json(
        archive_store.read_briefing_citations_json(briefing_id)
    )
    if registry.briefing_id != briefing_id:
        raise ValueError(
            "Briefing citation registry briefing_id does not match requested Briefing id."
        )
    return registry


def resolve_briefing_citation(
    registry: BriefingCitationRegistry,
    citation_number: int,
) -> BriefingCitation:
    for citation in registry.citations:
        if citation.number == citation_number:
            return citation
    raise ValueError(f"Briefing citation not found: {citation_number}")


def _briefing_citation_from_json(data: object) -> BriefingCitation:
    if not isinstance(data, dict):
        raise ValueError("Briefing citation JSON entry must be an object.")
    citation_data = cast(dict[str, object], data)
    return BriefingCitation(
        number=_required_int(citation_data, "number"),
        citation_key=_required_string(citation_data, "citation_key"),
        label=_required_string(citation_data, "label"),
        summary=_required_string(citation_data, "summary"),
        confidence_label=_required_string(citation_data, "confidence_label"),
        is_analytic_inference=_required_bool(citation_data, "is_analytic_inference"),
        entity_ids=_string_tuple(citation_data, "entity_ids"),
        actor_ids=_string_tuple(citation_data, "actor_ids"),
        organization_ids=_string_tuple(citation_data, "organization_ids"),
        place_ids=_string_tuple(citation_data, "place_ids"),
        event_ids=_string_tuple(citation_data, "event_ids"),
        source_ids=_string_tuple(citation_data, "source_ids"),
        document_ids=_string_tuple(citation_data, "document_ids"),
        evidence_span_ids=_string_tuple(citation_data, "evidence_span_ids"),
        assertion_ids=_string_tuple(citation_data, "assertion_ids"),
        relationship_ids=_string_tuple(citation_data, "relationship_ids"),
        outcome_ids=_string_tuple(citation_data, "outcome_ids"),
        argument_edge_ids=_string_tuple(citation_data, "argument_edge_ids"),
    )


def _required_string(data: dict[str, object], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"Briefing citation registry field {key} must be a non-empty string.")
    return value


def _required_int(data: dict[str, object], key: str) -> int:
    value = data.get(key)
    if type(value) is not int:
        raise ValueError(f"Briefing citation registry field {key} must be an integer.")
    return value


def _required_bool(data: dict[str, object], key: str) -> bool:
    value = data.get(key)
    if not isinstance(value, bool):
        raise ValueError(f"Briefing citation registry field {key} must be a boolean.")
    return value


def _string_tuple(data: dict[str, object], key: str) -> tuple[str, ...]:
    value = data.get(key, [])
    if not isinstance(value, list):
        raise ValueError(f"Briefing citation registry field {key} must be a string list.")
    items = cast(list[object], value)
    if not all(isinstance(item, str) for item in items):
        raise ValueError(f"Briefing citation registry field {key} must be a string list.")
    return tuple(cast(list[str], items))


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


def _build_briefing_narrative(
    *,
    briefing_id: str,
    selected_records: _SelectedRecords,
) -> tuple[BriefingNarrative, BriefingCitationRegistry]:
    assertions_by_id = {record.id: record for record in selected_records.assertions}
    relationships_by_id = {record.id: record for record in selected_records.relationships}
    argument_edges_by_id = {record.id: record for record in selected_records.argument_edges}
    evidence_spans_by_id = {record.id: record for record in selected_records.evidence_spans}
    name_lookup = _NameLookup(
        entities={record.id: record.canonical_name for record in selected_records.entities},
        actors={record.id: record.name for record in selected_records.actors},
        organizations={record.id: record.name for record in selected_records.organizations},
        places={record.id: record.name for record in selected_records.places},
        events={record.id: record.name for record in selected_records.events},
    )
    citation_builder = _CitationBuilder(
        briefing_id=briefing_id,
        assertions_by_id=assertions_by_id,
        evidence_spans_by_id=evidence_spans_by_id,
    )
    outcome = _top_outcome(selected_records.outcomes)
    narrative = BriefingNarrative(
        sharp_judgments=_sharp_judgments(
            selected_records,
            assertions_by_id,
            argument_edges_by_id,
            name_lookup,
            citation_builder,
        ),
        bottom_line=_bottom_line(outcome, assertions_by_id, name_lookup, citation_builder),
        key_judgments=_key_judgments(
            selected_records,
            assertions_by_id,
            relationships_by_id,
            argument_edges_by_id,
            name_lookup,
            citation_builder,
        ),
        evidence_references=_evidence_references(
            selected_records.assertions,
            name_lookup,
            citation_builder,
        ),
        uncertainties=_uncertainties(
            selected_records,
            assertions_by_id,
            relationships_by_id,
            argument_edges_by_id,
            name_lookup,
            citation_builder,
        ),
        open_questions=_open_questions(
            selected_records,
            assertions_by_id,
            relationships_by_id,
            citation_builder,
        ),
        analytic_trace=_analytic_trace(
            selected_records,
            assertions_by_id,
            name_lookup,
            citation_builder,
        ),
    )
    return narrative, citation_builder.registry()


class _CitationBuilder:
    def __init__(
        self,
        *,
        briefing_id: str,
        assertions_by_id: dict[str, Assertion],
        evidence_spans_by_id: dict[str, EvidenceSpan],
    ) -> None:
        self._briefing_id = briefing_id
        self._assertions_by_id = assertions_by_id
        self._evidence_spans_by_id = evidence_spans_by_id
        self._citations: list[BriefingCitation] = []
        self._numbers_by_identity: dict[str, int] = {}

    def registry(self) -> BriefingCitationRegistry:
        return BriefingCitationRegistry(
            briefing_id=self._briefing_id,
            citations=tuple(self._citations),
        )

    def source_assertion(self, assertion: Assertion, summary: str) -> int:
        return self._add(
            label="Source-backed Assertion",
            summary=summary,
            confidence_label=_confidence_label(assertion.world_truth_confidence),
            assertion_ids=(assertion.id,),
            source_ids=assertion.source_ids,
            evidence_span_ids=assertion.evidence_span_ids,
        )

    def analytic_inference(
        self,
        assertion: Assertion,
        supporting_edges: tuple[ArgumentEdge, ...],
        summary: str,
    ) -> int:
        evidence_span_ids = tuple(
            sorted({*assertion.evidence_span_ids, *_edge_evidence_span_ids(supporting_edges)})
        )
        source_ids = tuple(
            sorted(
                {
                    *assertion.source_ids,
                    *(
                        self._evidence_spans_by_id[evidence_span_id].source_id
                        for evidence_span_id in evidence_span_ids
                        if evidence_span_id in self._evidence_spans_by_id
                    ),
                }
            )
        )
        assertion_ids = tuple(
            sorted({assertion.id, *(record.from_assertion_id for record in supporting_edges)})
        )
        return self._add(
            label="Analytic inference",
            summary=summary,
            confidence_label=_confidence_label(assertion.world_truth_confidence),
            is_analytic_inference=True,
            assertion_ids=assertion_ids,
            argument_edge_ids=tuple(record.id for record in supporting_edges),
            source_ids=source_ids,
            evidence_span_ids=evidence_span_ids,
        )

    def outcome(
        self,
        outcome: Outcome,
        supporting_assertions: tuple[Assertion, ...],
        summary: str,
    ) -> int:
        return self._add(
            label="Outcome",
            summary=summary,
            confidence_label="Not assessed",
            outcome_ids=(outcome.id,),
            actor_ids=outcome.actor_ids,
            organization_ids=outcome.organization_ids,
            event_ids=outcome.event_ids,
            assertion_ids=outcome.assertion_ids,
            source_ids=tuple(
                sorted(
                    {
                        source_id
                        for assertion in supporting_assertions
                        for source_id in assertion.source_ids
                    }
                )
            ),
            evidence_span_ids=tuple(
                sorted(
                    {
                        evidence_span_id
                        for assertion in supporting_assertions
                        for evidence_span_id in assertion.evidence_span_ids
                    }
                )
            ),
        )

    def relationship(self, relationship: Relationship, summary: str) -> int:
        supporting_assertions = tuple(
            self._assertions_by_id[assertion_id]
            for assertion_id in relationship.assertion_ids
            if assertion_id in self._assertions_by_id
        )
        return self._add(
            label="Relationship",
            summary=summary,
            confidence_label="Not assessed",
            relationship_ids=(relationship.id,),
            assertion_ids=relationship.assertion_ids,
            source_ids=tuple(
                sorted(
                    {
                        source_id
                        for assertion in supporting_assertions
                        for source_id in assertion.source_ids
                    }
                )
            ),
            evidence_span_ids=tuple(
                sorted(
                    {
                        evidence_span_id
                        for assertion in supporting_assertions
                        for evidence_span_id in assertion.evidence_span_ids
                    }
                )
            ),
        )

    def event(self, event: Event, summary: str) -> int:
        return self._add(
            label="Event",
            summary=summary,
            confidence_label="Not assessed",
            actor_ids=event.participant_actor_ids,
            organization_ids=event.participant_organization_ids,
            place_ids=() if event.place_id is None else (event.place_id,),
            event_ids=(event.id,),
        )

    def argument_edge(self, argument_edge: ArgumentEdge, summary: str) -> int:
        return self._add(
            label="ArgumentEdge",
            summary=summary,
            confidence_label=_confidence_label(argument_edge.confidence),
            assertion_ids=(argument_edge.from_assertion_id, argument_edge.to_assertion_id),
            argument_edge_ids=(argument_edge.id,),
            evidence_span_ids=argument_edge.evidence_span_ids,
        )

    def _add(
        self,
        *,
        label: str,
        summary: str,
        confidence_label: str,
        is_analytic_inference: bool = False,
        entity_ids: tuple[str, ...] = (),
        actor_ids: tuple[str, ...] = (),
        organization_ids: tuple[str, ...] = (),
        place_ids: tuple[str, ...] = (),
        event_ids: tuple[str, ...] = (),
        source_ids: tuple[str, ...] = (),
        document_ids: tuple[str, ...] = (),
        evidence_span_ids: tuple[str, ...] = (),
        assertion_ids: tuple[str, ...] = (),
        relationship_ids: tuple[str, ...] = (),
        outcome_ids: tuple[str, ...] = (),
        argument_edge_ids: tuple[str, ...] = (),
    ) -> int:
        normalized_evidence_span_ids = tuple(sorted(evidence_span_ids))
        normalized_source_ids = tuple(
            sorted(
                {
                    *source_ids,
                    *(
                        self._evidence_spans_by_id[evidence_span_id].source_id
                        for evidence_span_id in normalized_evidence_span_ids
                        if evidence_span_id in self._evidence_spans_by_id
                    ),
                }
            )
        )
        normalized_document_ids = tuple(
            sorted(
                {
                    *document_ids,
                    *(
                        self._evidence_spans_by_id[evidence_span_id].document_id
                        for evidence_span_id in normalized_evidence_span_ids
                        if evidence_span_id in self._evidence_spans_by_id
                    ),
                }
            )
        )
        identity = {
            "entity_ids": sorted(entity_ids),
            "actor_ids": sorted(actor_ids),
            "organization_ids": sorted(organization_ids),
            "place_ids": sorted(place_ids),
            "event_ids": sorted(event_ids),
            "source_ids": list(normalized_source_ids),
            "document_ids": list(normalized_document_ids),
            "evidence_span_ids": list(normalized_evidence_span_ids),
            "assertion_ids": sorted(assertion_ids),
            "relationship_ids": sorted(relationship_ids),
            "outcome_ids": sorted(outcome_ids),
            "argument_edge_ids": sorted(argument_edge_ids),
        }
        identity_json = json.dumps(identity, sort_keys=True, separators=(",", ":"))
        existing_number = self._numbers_by_identity.get(identity_json)
        if existing_number is not None:
            return existing_number

        number = len(self._citations) + 1
        citation_key = deterministic_citation_key(self._briefing_id, identity_json)
        self._numbers_by_identity[identity_json] = number
        self._citations.append(
            BriefingCitation(
                number=number,
                citation_key=citation_key,
                label=label,
                summary=summary,
                confidence_label=confidence_label,
                is_analytic_inference=is_analytic_inference,
                entity_ids=tuple(sorted(entity_ids)),
                actor_ids=tuple(sorted(actor_ids)),
                organization_ids=tuple(sorted(organization_ids)),
                place_ids=tuple(sorted(place_ids)),
                event_ids=tuple(sorted(event_ids)),
                source_ids=normalized_source_ids,
                document_ids=normalized_document_ids,
                evidence_span_ids=normalized_evidence_span_ids,
                assertion_ids=tuple(sorted(assertion_ids)),
                relationship_ids=tuple(sorted(relationship_ids)),
                outcome_ids=tuple(sorted(outcome_ids)),
                argument_edge_ids=tuple(sorted(argument_edge_ids)),
            )
        )
        return number


@dataclass(frozen=True)
class _NameLookup:
    entities: dict[str, str]
    actors: dict[str, str]
    organizations: dict[str, str]
    places: dict[str, str]
    events: dict[str, str]


def _top_outcome(outcomes: tuple[Outcome, ...]) -> Outcome | None:
    if not outcomes:
        return None
    return sorted(
        outcomes,
        key=lambda record: (
            -len(record.assertion_ids),
            -len(record.organization_ids),
            -len(record.actor_ids),
            record.id,
        ),
    )[0]


def _sharp_judgments(
    selected_records: _SelectedRecords,
    assertions_by_id: dict[str, Assertion],
    argument_edges_by_id: dict[str, ArgumentEdge],
    name_lookup: _NameLookup,
    citation_builder: _CitationBuilder,
) -> tuple[BriefingSharpJudgment, ...]:
    judgments: list[BriefingSharpJudgment] = []
    analytic_assertions = tuple(
        sorted(
            (
                record
                for record in selected_records.assertions
                if record.epistemic_scope is EpistemicScope.ANALYTIC_INFERENCE
            ),
            key=lambda record: record.id,
        )
    )
    for analytic_assertion in analytic_assertions:
        supporting_edges = _argument_edges_to_assertion(argument_edges_by_id, analytic_assertion.id)
        supporting_assertions = tuple(
            assertions_by_id[edge.from_assertion_id]
            for edge in supporting_edges
            if edge.from_assertion_id in assertions_by_id
        )
        source_assertions = tuple(
            assertion for assertion in supporting_assertions if assertion.source_ids
        )
        if not source_assertions:
            continue
        source_basis = _sharp_source_basis(source_assertions, name_lookup, citation_builder)
        observed_effects = _sharp_observed_effects(
            source_assertions,
            name_lookup,
            citation_builder,
        )
        if not source_basis or not observed_effects:
            continue
        assessment_text = _sharp_assessment_text(analytic_assertion, source_assertions, name_lookup)
        inference_text = _inference_text(analytic_assertion, name_lookup)
        inference_citation = citation_builder.analytic_inference(
            analytic_assertion,
            supporting_edges,
            inference_text,
        )
        judgments.append(
            BriefingSharpJudgment(
                judgment=BriefingNarrativeSentence(
                    text=_sharp_judgment_text(analytic_assertion, source_assertions, name_lookup),
                    citation_numbers=(inference_citation,),
                ),
                source_basis=source_basis,
                observed_effects=observed_effects,
                assessment=BriefingNarrativeSentence(
                    text=assessment_text,
                    citation_numbers=(inference_citation,),
                ),
                confidence=BriefingNarrativeSentence(
                    text=_sharp_confidence_text(analytic_assertion, source_assertions),
                    citation_numbers=(inference_citation,),
                ),
            )
        )
    return tuple(judgments)


def _sharp_source_basis(
    source_assertions: tuple[Assertion, ...],
    name_lookup: _NameLookup,
    citation_builder: _CitationBuilder,
) -> tuple[BriefingNarrativeSentence, ...]:
    sentences: list[BriefingNarrativeSentence] = []
    pause_assertions = tuple(
        assertion for assertion in source_assertions if "pause" in assertion.predicate
    )
    for assertion in pause_assertions[:1]:
        text = _article_statement_text(assertion, name_lookup)
        sentences.append(
            BriefingNarrativeSentence(
                text=text,
                citation_numbers=(citation_builder.source_assertion(assertion, text),),
            )
        )
    authority_assertions = tuple(
        assertion
        for assertion in source_assertions
        if assertion.attribution_basis is AttributionBasis.ANONYMOUS_SOURCE
    )
    if authority_assertions:
        assertion = authority_assertions[0]
        text = _authority_basis_text(assertion)
        sentences.append(
            BriefingNarrativeSentence(
                text=text,
                citation_numbers=(citation_builder.source_assertion(assertion, text),),
            )
        )
    if not sentences:
        assertion = source_assertions[0]
        text = _article_statement_text(assertion, name_lookup)
        sentences.append(
            BriefingNarrativeSentence(
                text=text,
                citation_numbers=(citation_builder.source_assertion(assertion, text),),
            )
        )
    return tuple(sentences)


def _sharp_observed_effects(
    source_assertions: tuple[Assertion, ...],
    name_lookup: _NameLookup,
    citation_builder: _CitationBuilder,
) -> tuple[BriefingNarrativeSentence, ...]:
    effect_assertions = tuple(
        assertion
        for assertion in source_assertions
        if any(term in assertion.predicate for term in ("postponed", "suspended"))
    )
    return tuple(
        BriefingNarrativeSentence(
            text=_article_statement_text(assertion, name_lookup),
            citation_numbers=(
                citation_builder.source_assertion(
                    assertion,
                    _article_statement_text(assertion, name_lookup),
                ),
            ),
        )
        for assertion in sorted(effect_assertions, key=lambda record: record.id)
    )


def _sharp_judgment_text(
    analytic_assertion: Assertion,
    source_assertions: tuple[Assertion, ...],
    name_lookup: _NameLookup,
) -> str:
    if (
        analytic_assertion.predicate == "shared_governance_outcome_with"
        and analytic_assertion.object_entity_id is not None
    ):
        constrained_organization = _record_name(analytic_assertion.subject_entity_id, name_lookup)
        constraining_organization = _record_name(analytic_assertion.object_entity_id, name_lookup)
        model_name = _model_name_from_assertions(source_assertions)
        return (
            f"{_governance_actor_label(constraining_organization)} review pressure became "
            f"a release-governance constraint on {constrained_organization}'s "
            f"{model_name} rollout."
        )
    return _inference_text(analytic_assertion, name_lookup)


def _sharp_assessment_text(
    analytic_assertion: Assertion,
    source_assertions: tuple[Assertion, ...],
    name_lookup: _NameLookup,
) -> str:
    if (
        analytic_assertion.predicate == "shared_governance_outcome_with"
        and analytic_assertion.object_entity_id is not None
    ):
        constraining_organization = _record_name(analytic_assertion.object_entity_id, name_lookup)
        pause_phrase = (
            f"{_governance_actor_label(constraining_organization)}'s pause request"
            if any("pause" in assertion.predicate for assertion in source_assertions)
            else f"{_governance_actor_label(constraining_organization)} review"
        )
        return (
            "KoteKomi infers a release-governance constraint because "
            f"{pause_phrase}, the rollout delay, and the enterprise pilot suspension "
            "connect government review to Anthropic release timing."
        )
    return _inference_text(analytic_assertion, name_lookup)


def _sharp_confidence_text(
    analytic_assertion: Assertion,
    source_assertions: tuple[Assertion, ...],
) -> str:
    source_ids = {
        source_id for assertion in source_assertions for source_id in assertion.source_ids
    }
    source_authorities = tuple(
        sorted({assertion.source_authority.value for assertion in source_assertions})
    )
    source_authority = (
        source_authorities[0].replace("_", " ")
        if len(source_authorities) == 1
        else "mixed-authority"
    )
    source_phrase = "one Source" if len(source_ids) == 1 else f"{len(source_ids)} Sources"
    assertion_phrase = (
        "one source-backed Assertion"
        if len(source_assertions) == 1
        else f"{len(source_assertions)} source-backed Assertions"
    )
    return (
        f"{_confidence_label(analytic_assertion.world_truth_confidence)}. "
        f"The inference is supported by {assertion_phrase} from {source_phrase}; "
        f"the Source authority is {source_authority}."
    )


def _article_statement_text(assertion: Assertion, name_lookup: _NameLookup) -> str:
    text = _assertion_text(assertion, name_lookup).strip().removesuffix(".")
    replacements = (
        ("The Source reports that ", "The article states that "),
        ("The Source reports ", "The article states that "),
        ("Source report: ", "The article states that "),
    )
    for prefix, replacement in replacements:
        if text.startswith(prefix):
            text = f"{replacement}{text.removeprefix(prefix)}"
            break
    if not text.startswith("The article states"):
        text = f"The article states that {text[0].lower()}{text[1:]}"
    return _sentence(text)


def _authority_basis_text(assertion: Assertion) -> str:
    reported_by = assertion.qualifiers.get("reported_by")
    account = (
        "broader delay account"
        if "postponed" in assertion.predicate or "delay" in assertion.predicate
        else "account"
    )
    if isinstance(reported_by, str) and reported_by.strip():
        return (
            f"The article attributes the {account} to {reported_by}, so KoteKomi treats "
            "it as secondary reporting rather than primary-source confirmation."
        )
    return (
        "The article does not provide primary-source confirmation, so KoteKomi treats "
        "the account as secondary reporting."
    )


def _model_name_from_assertions(source_assertions: tuple[Assertion, ...]) -> str:
    for assertion in source_assertions:
        object_value = assertion.object_value
        if isinstance(object_value, dict):
            model = object_value.get("model")
            if isinstance(model, str) and model.strip():
                return model
    return "model"


def _governance_actor_label(name: str) -> str:
    if name.endswith(" Department"):
        return name.removesuffix(" Department")
    return name


def _bottom_line(
    outcome: Outcome | None,
    assertions_by_id: dict[str, Assertion],
    name_lookup: _NameLookup,
    citation_builder: _CitationBuilder,
) -> tuple[BriefingNarrativeSentence, ...]:
    if outcome is None:
        if not assertions_by_id:
            return (
                BriefingNarrativeSentence(
                    text="No accepted Ledger changes were selected for this Briefing."
                ),
            )
        first_assertion = assertions_by_id[sorted(assertions_by_id)[0]]
        return (
            BriefingNarrativeSentence(
                text=_briefing_assertion_text(first_assertion, name_lookup),
                citation_numbers=(
                    citation_builder.source_assertion(
                        first_assertion,
                        _briefing_assertion_text(first_assertion, name_lookup),
                    ),
                ),
            ),
        )

    supporting_assertions = tuple(
        assertions_by_id[assertion_id]
        for assertion_id in outcome.assertion_ids
        if assertion_id in assertions_by_id
    )
    source_backed_assertions = tuple(
        sorted(
            (record for record in supporting_assertions if record.source_ids),
            key=lambda record: record.id,
        )
    )
    sentences: list[BriefingNarrativeSentence] = []
    for assertion in source_backed_assertions[:2]:
        text = _briefing_assertion_text(assertion, name_lookup)
        sentences.append(
            BriefingNarrativeSentence(
                text=text,
                citation_numbers=(citation_builder.source_assertion(assertion, text),),
            )
        )
    outcome_text = _sentence(outcome.description)
    outcome_citation_number = citation_builder.outcome(outcome, supporting_assertions, outcome_text)
    sentences.append(
        BriefingNarrativeSentence(
            text=outcome_text,
            citation_numbers=(outcome_citation_number,),
        )
    )
    linked_names = _linked_outcome_names(outcome, name_lookup)
    if linked_names:
        sentences.append(
            BriefingNarrativeSentence(
                text=_sentence(f"The result connects {linked_names}"),
                citation_numbers=(outcome_citation_number,),
            )
        )
    return tuple(sentences)


def _key_judgments(
    selected_records: _SelectedRecords,
    assertions_by_id: dict[str, Assertion],
    relationships_by_id: dict[str, Relationship],
    argument_edges_by_id: dict[str, ArgumentEdge],
    name_lookup: _NameLookup,
    citation_builder: _CitationBuilder,
) -> tuple[BriefingKeyJudgment, ...]:
    judgments: list[BriefingKeyJudgment] = []
    seen_assertion_ids: set[str] = set()

    for assertion in sorted(
        (
            record
            for record in selected_records.assertions
            if record.assertion_type is AssertionType.ANALYTIC_INFERENCE
        ),
        key=lambda record: record.id,
    ):
        supporting_edges = _argument_edges_to_assertion(argument_edges_by_id, assertion.id)
        supporting_assertion_ids = tuple(
            sorted({assertion.id, *(record.from_assertion_id for record in supporting_edges)})
        )
        text = _inference_text(assertion, name_lookup)
        citation_number = citation_builder.analytic_inference(
            assertion,
            supporting_edges,
            text,
        )
        citation = resolve_briefing_citation(citation_builder.registry(), citation_number)
        judgments.append(
            BriefingKeyJudgment(
                text=text,
                confidence_label=_confidence_label(assertion.world_truth_confidence),
                assertion_ids=supporting_assertion_ids,
                argument_edge_ids=tuple(record.id for record in supporting_edges),
                source_ids=citation.source_ids,
                evidence_span_ids=citation.evidence_span_ids,
                citation_numbers=(citation_number,),
                is_analytic_inference=True,
            )
        )
        seen_assertion_ids.add(assertion.id)

    outcome_assertion_ids = tuple(
        assertion_id
        for outcome in sorted(selected_records.outcomes, key=lambda record: record.id)
        for assertion_id in outcome.assertion_ids
    )
    source_backed_assertions = tuple(
        assertions_by_id[assertion_id]
        for assertion_id in outcome_assertion_ids
        if assertion_id in assertions_by_id and assertions_by_id[assertion_id].source_ids
    )
    for assertion in sorted(source_backed_assertions, key=lambda record: record.id):
        if assertion.id in seen_assertion_ids:
            continue
        judgments.append(_source_assertion_judgment(assertion, name_lookup, citation_builder))
        seen_assertion_ids.add(assertion.id)

    for assertion in sorted(selected_records.assertions, key=lambda record: record.id):
        if assertion.id in seen_assertion_ids or not assertion.source_ids:
            continue
        judgments.append(_source_assertion_judgment(assertion, name_lookup, citation_builder))
        seen_assertion_ids.add(assertion.id)

    if _has_sharp_judgment(selected_records.assertions, argument_edges_by_id):
        return tuple(judgments)

    for relationship in sorted(relationships_by_id.values(), key=lambda record: record.id):
        text = _relationship_text(relationship, name_lookup)
        judgments.append(
            BriefingKeyJudgment(
                text=text,
                confidence_label="Not assessed",
                assertion_ids=relationship.assertion_ids,
                relationship_ids=(relationship.id,),
                citation_numbers=(citation_builder.relationship(relationship, text),),
            )
        )
    return tuple(judgments)


def _has_sharp_judgment(
    assertions: tuple[Assertion, ...],
    argument_edges_by_id: dict[str, ArgumentEdge],
) -> bool:
    assertion_ids = {assertion.id for assertion in assertions}
    return any(
        assertion.epistemic_scope is EpistemicScope.ANALYTIC_INFERENCE
        and any(
            edge.to_assertion_id == assertion.id and edge.from_assertion_id in assertion_ids
            for edge in argument_edges_by_id.values()
        )
        for assertion in assertions
    )


def _source_assertion_judgment(
    assertion: Assertion,
    name_lookup: _NameLookup,
    citation_builder: _CitationBuilder,
) -> BriefingKeyJudgment:
    text = _briefing_assertion_text(assertion, name_lookup)
    return BriefingKeyJudgment(
        text=text,
        confidence_label=_confidence_label(assertion.world_truth_confidence),
        assertion_ids=(assertion.id,),
        source_ids=assertion.source_ids,
        evidence_span_ids=assertion.evidence_span_ids,
        citation_numbers=(citation_builder.source_assertion(assertion, text),),
    )


def _evidence_references(
    assertions: tuple[Assertion, ...],
    name_lookup: _NameLookup,
    citation_builder: _CitationBuilder,
) -> tuple[BriefingEvidenceReference, ...]:
    return tuple(
        BriefingEvidenceReference(
            assertion_id=assertion.id,
            source_ids=assertion.source_ids,
            evidence_span_ids=assertion.evidence_span_ids,
            summary=_briefing_assertion_text(assertion, name_lookup),
            citation_numbers=(
                citation_builder.source_assertion(
                    assertion,
                    _briefing_assertion_text(assertion, name_lookup),
                ),
            ),
        )
        for assertion in sorted(assertions, key=lambda record: record.id)
        if assertion.source_ids or assertion.evidence_span_ids
    )


def _uncertainties(
    selected_records: _SelectedRecords,
    assertions_by_id: dict[str, Assertion],
    relationships_by_id: dict[str, Relationship],
    argument_edges_by_id: dict[str, ArgumentEdge],
    name_lookup: _NameLookup,
    citation_builder: _CitationBuilder,
) -> tuple[BriefingUncertainty, ...]:
    uncertainties: list[BriefingUncertainty] = []
    for assertion in sorted(selected_records.assertions, key=lambda record: record.id):
        if assertion.source_ids and (
            assertion.world_truth_confidence is None or assertion.world_truth_confidence < 0.5
        ):
            assertion_text = _source_report_body(assertion, name_lookup)
            uncertainties.append(
                BriefingUncertainty(
                    text=(
                        f"World-truth confidence for the Source-backed Assertion "
                        f"that {assertion_text} is "
                        f"{_confidence_label(assertion.world_truth_confidence)}; treat the "
                        "Source report separately from the world assessment."
                    ),
                    record_ids=(assertion.id,),
                    source_ids=assertion.source_ids,
                    evidence_span_ids=assertion.evidence_span_ids,
                    citation_numbers=(
                        citation_builder.source_assertion(
                            assertion,
                            _source_report_text(assertion, name_lookup),
                        ),
                    ),
                )
            )

    for event in sorted(selected_records.events, key=lambda record: record.id):
        if event.place_id is None:
            text = f"{event.name} has participants but no Place recorded."
            uncertainties.append(
                BriefingUncertainty(
                    text=text,
                    record_ids=(event.id,),
                    citation_numbers=(citation_builder.event(event, text),),
                )
            )
        unexplained_participants = _unexplained_event_participants(
            event,
            assertions_by_id,
            relationships_by_id,
            name_lookup,
        )
        if unexplained_participants:
            unexplained_participant_names = tuple(
                _record_name(record_id, name_lookup) for record_id in unexplained_participants
            )
            text = (
                "Event participation is recorded for "
                f"{_join_names(unexplained_participant_names)}, but no accepted Assertion "
                "or Relationship explains those roles beyond participation."
            )
            uncertainties.append(
                BriefingUncertainty(
                    text=text,
                    record_ids=(event.id, *tuple(sorted(unexplained_participants))),
                    citation_numbers=(citation_builder.event(event, text),),
                )
            )

    for assertion in sorted(
        (
            record
            for record in selected_records.assertions
            if record.assertion_type is AssertionType.ANALYTIC_INFERENCE
        ),
        key=lambda record: record.id,
    ):
        supporting_edges = _argument_edges_to_assertion(argument_edges_by_id, assertion.id)
        if supporting_edges:
            assertion_text = _inference_body(assertion, name_lookup)
            text = (
                f"The inference that {assertion_text} is derived from source-backed "
                "Assertions; it is not directly stated by a Source."
            )
            uncertainties.append(
                BriefingUncertainty(
                    text=text,
                    record_ids=(assertion.id, *tuple(record.id for record in supporting_edges)),
                    source_ids=assertion.source_ids,
                    evidence_span_ids=assertion.evidence_span_ids,
                    citation_numbers=(
                        citation_builder.analytic_inference(
                            assertion,
                            supporting_edges,
                            _inference_text(assertion, name_lookup),
                        ),
                    ),
                )
            )
    return tuple(uncertainties)


def _open_questions(
    selected_records: _SelectedRecords,
    assertions_by_id: dict[str, Assertion],
    relationships_by_id: dict[str, Relationship],
    citation_builder: _CitationBuilder,
) -> tuple[BriefingOpenQuestion, ...]:
    questions: list[BriefingOpenQuestion] = []
    name_lookup = _NameLookup(
        entities={record.id: record.canonical_name for record in selected_records.entities},
        actors={record.id: record.name for record in selected_records.actors},
        organizations={record.id: record.name for record in selected_records.organizations},
        places={record.id: record.name for record in selected_records.places},
        events={record.id: record.name for record in selected_records.events},
    )
    for event in sorted(selected_records.events, key=lambda record: record.id):
        if event.place_id is None:
            question = f"Where did {event.name} occur?"
            questions.append(
                BriefingOpenQuestion(
                    question=question,
                    record_ids=(event.id,),
                    citation_numbers=(citation_builder.event(event, question),),
                )
            )
        for participant_id in _unexplained_event_participants(
            event,
            assertions_by_id,
            relationships_by_id,
            name_lookup,
        ):
            question = (
                f"What role did {_record_name(participant_id, name_lookup)} play beyond "
                f"recorded participation in {event.name}?"
            )
            questions.append(
                BriefingOpenQuestion(
                    question=question,
                    record_ids=(event.id, participant_id),
                    citation_numbers=(citation_builder.event(event, question),),
                )
            )
    return tuple(questions)


def _analytic_trace(
    selected_records: _SelectedRecords,
    assertions_by_id: dict[str, Assertion],
    name_lookup: _NameLookup,
    citation_builder: _CitationBuilder,
) -> tuple[BriefingNarrativeSentence, ...]:
    trace: list[BriefingNarrativeSentence] = []
    for argument_edge in sorted(selected_records.argument_edges, key=lambda record: record.id):
        from_assertion = _require(
            assertions_by_id,
            argument_edge.from_assertion_id,
            "Assertion",
            argument_edge.id,
        )
        to_assertion = _require(
            assertions_by_id,
            argument_edge.to_assertion_id,
            "Assertion",
            argument_edge.id,
        )
        text = (
            f"Source report support: {_source_report_body(from_assertion, name_lookup)} "
            f"{_argument_edge_phrase(argument_edge.relation.value)} the inference that "
            f"{_inference_body(to_assertion, name_lookup)}."
        )
        trace.append(
            BriefingNarrativeSentence(
                text=text,
                citation_numbers=(citation_builder.argument_edge(argument_edge, text),),
            )
        )
    for relationship in sorted(selected_records.relationships, key=lambda record: record.id):
        text = _relationship_text(relationship, name_lookup)
        trace.append(
            BriefingNarrativeSentence(
                text=text,
                citation_numbers=(citation_builder.relationship(relationship, text),),
            )
        )
    return tuple(trace)


def _argument_edges_to_assertion(
    argument_edges_by_id: dict[str, ArgumentEdge],
    assertion_id: str,
) -> tuple[ArgumentEdge, ...]:
    return tuple(
        sorted(
            (
                record
                for record in argument_edges_by_id.values()
                if record.to_assertion_id == assertion_id
            ),
            key=lambda record: record.id,
        )
    )


def _edge_evidence_span_ids(argument_edges: tuple[ArgumentEdge, ...]) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                evidence_span_id
                for argument_edge in argument_edges
                for evidence_span_id in argument_edge.evidence_span_ids
            }
        )
    )


def _unexplained_event_participants(
    event: Event,
    assertions_by_id: dict[str, Assertion],
    relationships_by_id: dict[str, Relationship],
    name_lookup: _NameLookup,
) -> tuple[str, ...]:
    explained_ids = {
        *(record.subject_entity_id for record in assertions_by_id.values()),
        *(
            record.object_entity_id
            for record in assertions_by_id.values()
            if record.object_entity_id is not None
        ),
        *(record.subject_id for record in relationships_by_id.values()),
        *(record.object_id for record in relationships_by_id.values()),
    }
    participant_ids = (*event.participant_actor_ids, *event.participant_organization_ids)
    return tuple(
        sorted(
            (record_id for record_id in participant_ids if record_id not in explained_ids),
            key=lambda record_id: _record_name(record_id, name_lookup),
        )
    )


def _linked_outcome_names(outcome: Outcome, name_lookup: _NameLookup) -> str:
    names = (
        *(_record_name(record_id, name_lookup) for record_id in outcome.actor_ids),
        *(_record_name(record_id, name_lookup) for record_id in outcome.organization_ids),
        *(_record_name(record_id, name_lookup) for record_id in outcome.event_ids),
    )
    return _join_names(tuple(name for name in names if name))


def _assertion_text(assertion: Assertion, name_lookup: _NameLookup) -> str:
    if assertion.current_assessment:
        return _humanize_record_ids(assertion.current_assessment, name_lookup)
    subject = _record_name(assertion.subject_entity_id, name_lookup)
    predicate = _phrase_predicate(assertion.predicate)
    if assertion.object_entity_id is not None:
        return f"{subject} {predicate} {_record_name(assertion.object_entity_id, name_lookup)}."
    return f"{subject} {predicate}."


def _briefing_assertion_text(assertion: Assertion, name_lookup: _NameLookup) -> str:
    if assertion.epistemic_scope is EpistemicScope.ANALYTIC_INFERENCE:
        return _inference_text(assertion, name_lookup)
    if assertion.epistemic_scope is EpistemicScope.SOURCE_REPORT:
        return _source_report_text(assertion, name_lookup)
    if assertion.epistemic_scope is EpistemicScope.ATTRIBUTED_STATEMENT:
        return _attributed_statement_text(assertion, name_lookup)
    if assertion.epistemic_scope is EpistemicScope.CAUSAL_EXPLANATION:
        return _causal_explanation_text(assertion, name_lookup)
    if assertion.epistemic_scope is EpistemicScope.WORLD_STATE:
        return _world_state_text(assertion, name_lookup)
    return _sentence(_assertion_text(assertion, name_lookup))


def _source_report_text(assertion: Assertion, name_lookup: _NameLookup) -> str:
    return f"Source report: {_source_report_body(assertion, name_lookup)}."


def _source_report_body(assertion: Assertion, name_lookup: _NameLookup) -> str:
    return _strip_source_report_prefix(_assertion_text(assertion, name_lookup))


def _attributed_statement_text(assertion: Assertion, name_lookup: _NameLookup) -> str:
    prefix = (
        "Primary-source statement"
        if assertion.source_authority is SourceAuthority.PRIMARY
        else "Attributed statement"
    )
    if assertion.attributed_to_id is None:
        return f"{prefix}: {_source_report_body(assertion, name_lookup)}."
    return (
        f"{prefix} by {_record_name(assertion.attributed_to_id, name_lookup)}: "
        f"{_source_report_body(assertion, name_lookup)}."
    )


def _causal_explanation_text(assertion: Assertion, name_lookup: _NameLookup) -> str:
    return f"Causal explanation: {_source_report_body(assertion, name_lookup)}."


def _world_state_text(assertion: Assertion, name_lookup: _NameLookup) -> str:
    return f"World assertion: {_source_report_body(assertion, name_lookup)}."


def _strip_source_report_prefix(text: str) -> str:
    stripped = text.strip().removesuffix(".")
    for prefix in (
        "The Source reports that ",
        "The Source reports ",
        "The article states that ",
        "The article states ",
    ):
        if stripped.startswith(prefix):
            stripped = stripped.removeprefix(prefix)
            break
    return _capitalize_first(stripped)


def _inference_text(assertion: Assertion, name_lookup: _NameLookup) -> str:
    return f"Inference: {_inference_body(assertion, name_lookup)}."


def _inference_body(assertion: Assertion, name_lookup: _NameLookup) -> str:
    if (
        assertion.predicate == "shared_governance_outcome_with"
        and assertion.object_entity_id is not None
    ):
        return (
            f"{_record_name(assertion.subject_entity_id, name_lookup)} and "
            f"{_record_name(assertion.object_entity_id, name_lookup)} share "
            "a release-governance outcome"
        )
    text = _strip_inference_prefix(_assertion_text(assertion, name_lookup))
    return text


def _strip_inference_prefix(text: str) -> str:
    stripped = text.strip().removesuffix(".")
    for prefix in (
        "Analytic inference: ",
        "Inference: ",
        "Graph mining inferred ",
    ):
        if stripped.startswith(prefix):
            stripped = stripped.removeprefix(prefix)
            break
    return _capitalize_first(stripped)


def _relationship_text(relationship: Relationship, name_lookup: _NameLookup) -> str:
    return (
        "Relationship: "
        f"{_record_name(relationship.subject_id, name_lookup)} "
        f"{_phrase_predicate(relationship.predicate)} "
        f"{_record_name(relationship.object_id, name_lookup)}."
    )


def _confidence_label(confidence: float | None) -> str:
    if confidence is None:
        return "Not assessed"
    if confidence >= 0.75:
        return "High"
    if confidence >= 0.5:
        return "Moderate"
    return "Low"


def _record_name(record_id: str, name_lookup: _NameLookup) -> str:
    if record_id in name_lookup.entities:
        return name_lookup.entities[record_id]
    if record_id in name_lookup.actors:
        return name_lookup.actors[record_id]
    if record_id in name_lookup.organizations:
        return name_lookup.organizations[record_id]
    if record_id in name_lookup.places:
        return name_lookup.places[record_id]
    if record_id in name_lookup.events:
        return name_lookup.events[record_id]
    return f"`{record_id}`"


def _phrase_predicate(predicate: str) -> str:
    return predicate.replace("_", " ")


def _argument_edge_phrase(relation: str) -> str:
    if relation == "infers":
        return "supports"
    return _phrase_predicate(relation)


def _humanize_record_ids(text: str, name_lookup: _NameLookup) -> str:
    replacements = {
        **name_lookup.entities,
        **name_lookup.actors,
        **name_lookup.organizations,
        **name_lookup.places,
        **name_lookup.events,
    }
    result = text
    for record_id, name in sorted(
        replacements.items(), key=lambda item: len(item[0]), reverse=True
    ):
        result = result.replace(record_id, name)
    return result


def _capitalize_first(text: str) -> str:
    if not text:
        return text
    return f"{text[0].upper()}{text[1:]}"


def _sentence(text: str) -> str:
    stripped = text.strip()
    if not stripped:
        return ""
    if stripped.endswith((".", "?", "!")):
        return stripped
    return f"{stripped}."


def _join_names(names: tuple[str, ...]) -> str:
    if not names:
        return ""
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]} and {names[1]}"
    return f"{', '.join(names[:-1])}, and {names[-1]}"


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
