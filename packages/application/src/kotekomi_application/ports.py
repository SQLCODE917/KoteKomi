"""Application Layer Ports."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from kotekomi_domain import (
    Actor,
    ArgumentEdge,
    Assertion,
    Briefing,
    Document,
    Entity,
    Event,
    EvidenceSpan,
    Organization,
    Outcome,
    Place,
    ProposedChange,
    ProvenanceActivity,
    Relationship,
    Source,
)
from kotekomi_domain.models import JsonValue


@dataclass(frozen=True)
class LedgerInitResult:
    ledger_path: Path
    applied_migrations: tuple[str, ...]


class LedgerInitializer(Protocol):
    def initialize(self) -> LedgerInitResult: ...


@dataclass(frozen=True)
class ArchiveObject:
    relative_path: str
    size_bytes: int


@dataclass(frozen=True)
class StagedArchiveObject:
    staged_relative_path: str
    final_object: ArchiveObject


class ArchiveStore(Protocol):
    def initialize(self) -> None: ...
    def write_raw_source(self, source_id: str, content: bytes) -> ArchiveObject: ...
    def read_raw_source(self, source_id: str) -> bytes: ...
    def write_document_text(self, document_id: str, text: str) -> ArchiveObject: ...
    def read_document_text(self, document_id: str) -> str: ...
    def read_briefing_markdown(self, briefing_id: str) -> str: ...
    def stage_raw_source(self, source_id: str, content: bytes) -> StagedArchiveObject: ...
    def stage_document_text(self, document_id: str, text: str) -> StagedArchiveObject: ...
    def stage_briefing_markdown(
        self,
        briefing_id: str,
        markdown: str,
    ) -> StagedArchiveObject: ...
    def promote_staged_object(self, staged_object: StagedArchiveObject) -> ArchiveObject: ...
    def delete_object(self, relative_path: str) -> None: ...


@dataclass(frozen=True)
class BriefingRenderInput:
    briefing_id: str
    title: str
    generated_at: str
    previous_briefing_id: str | None
    sources: tuple[Source, ...]
    assertions: tuple[Assertion, ...]
    relationships: tuple[Relationship, ...]
    argument_edges: tuple[ArgumentEdge, ...]
    evidence_spans: tuple[EvidenceSpan, ...]
    analytic_inference_assertion_ids: tuple[str, ...]


@dataclass(frozen=True)
class BriefingMarkdown:
    markdown: str


class BriefingRenderer(Protocol):
    def render(self, render_input: BriefingRenderInput) -> BriefingMarkdown: ...


@dataclass(frozen=True)
class ModelProposal:
    record_type: str
    stable_label: str
    record: dict[str, JsonValue]
    evidence: dict[str, JsonValue]


class ModelRuntime(Protocol):
    @property
    def model_name(self) -> str: ...

    @property
    def prompt_id(self) -> str: ...

    def propose_assertions(
        self,
        *,
        document_id: str,
        source_id: str,
        document_text: str,
    ) -> tuple[ModelProposal, ...]: ...


@dataclass(frozen=True)
class GraphNode:
    id: str
    node_type: str
    label: str


@dataclass(frozen=True)
class GraphEdge:
    id: str
    source_id: str
    target_id: str
    edge_type: str
    label: str
    source_record_id: str


@dataclass(frozen=True)
class GraphProjection:
    nodes: tuple[GraphNode, ...]
    edges: tuple[GraphEdge, ...]


@dataclass(frozen=True)
class GraphConnectionCandidate:
    subject_organization_id: str
    object_organization_id: str
    outcome_id: str
    supporting_assertion_ids: tuple[str, ...]


class GraphAnalyzer(Protocol):
    def project(
        self,
        nodes: tuple[GraphNode, ...],
        edges: tuple[GraphEdge, ...],
    ) -> GraphProjection: ...


class LedgerRepository(Protocol):
    def save_entity(self, record: Entity) -> None: ...
    def get_entity(self, record_id: str) -> Entity | None: ...
    def list_entities(self) -> tuple[Entity, ...]: ...

    def save_actor(self, record: Actor) -> None: ...
    def get_actor(self, record_id: str) -> Actor | None: ...
    def list_actors(self) -> tuple[Actor, ...]: ...

    def save_organization(self, record: Organization) -> None: ...
    def get_organization(self, record_id: str) -> Organization | None: ...
    def list_organizations(self) -> tuple[Organization, ...]: ...

    def save_place(self, record: Place) -> None: ...
    def get_place(self, record_id: str) -> Place | None: ...
    def list_places(self) -> tuple[Place, ...]: ...

    def save_event(self, record: Event) -> None: ...
    def get_event(self, record_id: str) -> Event | None: ...
    def list_events(self) -> tuple[Event, ...]: ...

    def save_source(self, record: Source) -> None: ...
    def get_source(self, record_id: str) -> Source | None: ...
    def list_sources(self) -> tuple[Source, ...]: ...

    def save_document(self, record: Document) -> None: ...
    def get_document(self, record_id: str) -> Document | None: ...
    def list_documents(self) -> tuple[Document, ...]: ...

    def save_evidence_span(self, record: EvidenceSpan) -> None: ...
    def get_evidence_span(self, record_id: str) -> EvidenceSpan | None: ...
    def list_evidence_spans(self) -> tuple[EvidenceSpan, ...]: ...

    def save_assertion(self, record: Assertion) -> None: ...
    def get_assertion(self, record_id: str) -> Assertion | None: ...
    def list_assertions(self) -> tuple[Assertion, ...]: ...

    def save_relationship(self, record: Relationship) -> None: ...
    def get_relationship(self, record_id: str) -> Relationship | None: ...
    def list_relationships(self) -> tuple[Relationship, ...]: ...

    def save_outcome(self, record: Outcome) -> None: ...
    def get_outcome(self, record_id: str) -> Outcome | None: ...
    def list_outcomes(self) -> tuple[Outcome, ...]: ...

    def save_argument_edge(self, record: ArgumentEdge) -> None: ...
    def get_argument_edge(self, record_id: str) -> ArgumentEdge | None: ...
    def list_argument_edges(self) -> tuple[ArgumentEdge, ...]: ...

    def save_provenance_activity(self, record: ProvenanceActivity) -> None: ...
    def get_provenance_activity(self, record_id: str) -> ProvenanceActivity | None: ...
    def list_provenance_activities(self) -> tuple[ProvenanceActivity, ...]: ...

    def save_proposed_change(self, record: ProposedChange) -> None: ...
    def get_proposed_change(self, record_id: str) -> ProposedChange | None: ...
    def list_proposed_changes(self) -> tuple[ProposedChange, ...]: ...

    def save_briefing(self, record: Briefing) -> None: ...
    def get_briefing(self, record_id: str) -> Briefing | None: ...
    def list_briefings(self) -> tuple[Briefing, ...]: ...
