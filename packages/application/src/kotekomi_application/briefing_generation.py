"""Briefing generation use case."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from kotekomi_domain import (
    ArgumentEdge,
    Assertion,
    AssertionType,
    Briefing,
    EvidenceSpan,
    ProvenanceActivity,
    Relationship,
    Source,
)

from kotekomi_application.ports import (
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
    def list_sources(self) -> tuple[Source, ...]: ...
    def list_assertions(self) -> tuple[Assertion, ...]: ...
    def list_relationships(self) -> tuple[Relationship, ...]: ...
    def list_argument_edges(self) -> tuple[ArgumentEdge, ...]: ...
    def list_evidence_spans(self) -> tuple[EvidenceSpan, ...]: ...
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
    assertion_count: int
    relationship_count: int
    argument_edge_count: int
    source_count: int
    evidence_span_count: int
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
    selected_records = _selected_records(ledger_repository, boundary)
    _validate_briefing_references(selected_records)

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
        sources=selected_records.sources,
        assertions=selected_records.assertions,
        relationships=selected_records.relationships,
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
            assertion_ids=tuple(record.id for record in selected_records.assertions),
            relationship_ids=tuple(record.id for record in selected_records.relationships),
            argument_edge_ids=tuple(record.id for record in selected_records.argument_edges),
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
        assertion_count=len(selected_records.assertions),
        relationship_count=len(selected_records.relationships),
        argument_edge_count=len(selected_records.argument_edges),
        source_count=len(selected_records.sources),
        evidence_span_count=len(selected_records.evidence_spans),
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
class _SelectedRecords:
    sources: tuple[Source, ...]
    assertions: tuple[Assertion, ...]
    relationships: tuple[Relationship, ...]
    argument_edges: tuple[ArgumentEdge, ...]
    evidence_spans: tuple[EvidenceSpan, ...]
    analytic_inference_assertion_ids: tuple[str, ...]
    input_ids: tuple[str, ...]
    all_assertion_ids: frozenset[str]


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


def _selected_records(
    ledger_repository: BriefingGenerationLedger,
    boundary: datetime | None,
) -> _SelectedRecords:
    all_sources = {record.id: record for record in ledger_repository.list_sources()}
    all_evidence_spans = {record.id: record for record in ledger_repository.list_evidence_spans()}
    all_assertions = ledger_repository.list_assertions()
    all_assertion_ids = frozenset(record.id for record in all_assertions)
    assertions = tuple(
        sorted(
            (record for record in all_assertions if _is_changed(record.updated_at, boundary)),
            key=lambda record: record.id,
        )
    )
    relationships = tuple(
        sorted(
            (
                record
                for record in ledger_repository.list_relationships()
                if _is_changed(record.updated_at, boundary)
            ),
            key=lambda record: record.id,
        )
    )
    argument_edges = tuple(
        sorted(
            (
                record
                for record in ledger_repository.list_argument_edges()
                if _is_changed(record.created_at, boundary)
            ),
            key=lambda record: record.id,
        )
    )

    source_ids = set(
        record.id
        for record in ledger_repository.list_sources()
        if _is_changed(record.updated_at, boundary)
    )
    evidence_span_ids = set(
        record.id
        for record in ledger_repository.list_evidence_spans()
        if _is_changed(record.created_at, boundary)
    )
    for assertion in assertions:
        source_ids.update(assertion.source_ids)
        evidence_span_ids.update(assertion.evidence_span_ids)
    for argument_edge in argument_edges:
        evidence_span_ids.update(argument_edge.evidence_span_ids)

    sources = tuple(
        all_sources[source_id] for source_id in sorted(source_ids) if source_id in all_sources
    )
    evidence_spans = tuple(
        all_evidence_spans[evidence_span_id]
        for evidence_span_id in sorted(evidence_span_ids)
        if evidence_span_id in all_evidence_spans
    )
    analytic_inference_assertion_ids = tuple(
        record.id
        for record in assertions
        if record.assertion_type is AssertionType.ANALYTIC_INFERENCE
    )
    input_ids = tuple(
        sorted(
            {
                *(record.id for record in sources),
                *(record.id for record in assertions),
                *(record.id for record in relationships),
                *(record.id for record in argument_edges),
                *(record.id for record in evidence_spans),
            }
        )
    )
    return _SelectedRecords(
        sources=sources,
        assertions=assertions,
        relationships=relationships,
        argument_edges=argument_edges,
        evidence_spans=evidence_spans,
        analytic_inference_assertion_ids=analytic_inference_assertion_ids,
        input_ids=input_ids,
        all_assertion_ids=all_assertion_ids,
    )


def _is_changed(record_time: datetime, boundary: datetime | None) -> bool:
    return boundary is None or record_time > boundary


def _validate_briefing_references(selected_records: _SelectedRecords) -> None:
    source_ids = {record.id for record in selected_records.sources}
    evidence_span_ids = {record.id for record in selected_records.evidence_spans}
    assertion_ids = selected_records.all_assertion_ids

    for assertion in selected_records.assertions:
        for source_id in assertion.source_ids:
            if source_id not in source_ids:
                raise ValueError(
                    f"Briefing Assertion {assertion.id} references missing Source: {source_id}"
                )
        for evidence_span_id in assertion.evidence_span_ids:
            if evidence_span_id not in evidence_span_ids:
                raise ValueError(
                    "Briefing Assertion "
                    f"{assertion.id} references missing EvidenceSpan: {evidence_span_id}"
                )
    for relationship in selected_records.relationships:
        for assertion_id in relationship.assertion_ids:
            if assertion_id not in assertion_ids:
                raise ValueError(
                    "Briefing Relationship "
                    f"{relationship.id} references missing Assertion: {assertion_id}"
                )
    for argument_edge in selected_records.argument_edges:
        for assertion_id in (argument_edge.from_assertion_id, argument_edge.to_assertion_id):
            if assertion_id not in assertion_ids:
                raise ValueError(
                    "Briefing ArgumentEdge "
                    f"{argument_edge.id} references missing Assertion: {assertion_id}"
                )
        for evidence_span_id in argument_edge.evidence_span_ids:
            if evidence_span_id not in evidence_span_ids:
                raise ValueError(
                    "Briefing ArgumentEdge "
                    f"{argument_edge.id} references missing EvidenceSpan: {evidence_span_id}"
                )
