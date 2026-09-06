"""Read-only Candidate Wiki resolution and deterministic page planning."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections import Counter, deque
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Literal, Protocol, Self, cast

from kotekomi_domain import (
    HYBRID_EVENT_SEMANTICS_V1,
    Actor,
    Assertion,
    AssertionEvidenceLink,
    Document,
    DocumentRepresentationBundle,
    Entity,
    Event,
    EvidenceTarget,
    EvidenceValidationAttempt,
    HybridEventStructuralPredicate,
    IngestionChangeSet,
    IngestionRun,
    IngestionRunStatus,
    Organization,
    Place,
    ProposedAssertion,
    ProposedChange,
    ReviewStatus,
    SemanticArgumentTargetKind,
    Source,
)
from kotekomi_domain.models import JsonValue
from pydantic import BaseModel, ConfigDict, model_validator

from kotekomi_application.evidence_targets import verify_evidence_target
from kotekomi_application.hybrid_event_frames import EventModality, EventPolarity
from kotekomi_application.record_serialization import canonical_record_json

CANDIDATE_WIKI_VIEW_POLICY_ID = "candidate_wiki_view_v4"
CANDIDATE_WIKI_RENDERER_POLICY_ID = "ontology_graph_markdown_wiki_v6"
HASH_ID_LENGTH = 24

type WikiIntelligenceRecord = (
    Entity | Actor | Organization | Place | Event | Assertion | ProposedAssertion
)
type WikiNamedRecord = Entity | Actor | Organization | Place | Event
type WikiRecordType = Literal["Entity", "Actor", "Organization", "Place", "Event", "Assertion"]
type WikiAuditRecordType = Literal[
    "Source", "Document", "Entity", "Actor", "Organization", "Place", "Event", "Assertion"
]
type WikiReferenceKind = Literal["evidence_target", "proposal_evidence"]


class CandidateWikiLedger(Protocol):
    def list_ingestion_runs(self) -> tuple[IngestionRun, ...]: ...
    def get_ingestion_change_set(self, record_id: str) -> IngestionChangeSet | None: ...
    def get_proposed_change(self, record_id: str) -> ProposedChange | None: ...
    def get_source(self, record_id: str) -> Source | None: ...
    def get_document(self, record_id: str) -> Document | None: ...
    def get_document_representation_bundle(
        self, record_id: str
    ) -> DocumentRepresentationBundle | None: ...
    def get_entity(self, record_id: str) -> Entity | None: ...
    def get_actor(self, record_id: str) -> Actor | None: ...
    def get_organization(self, record_id: str) -> Organization | None: ...
    def get_place(self, record_id: str) -> Place | None: ...
    def get_event(self, record_id: str) -> Event | None: ...
    def get_assertion(self, record_id: str) -> Assertion | None: ...
    def get_evidence_target(self, record_id: str) -> EvidenceTarget | None: ...
    def get_evidence_validation_attempt(
        self, record_id: str
    ) -> EvidenceValidationAttempt | None: ...
    def list_assertion_evidence_links(self) -> tuple[AssertionEvidenceLink, ...]: ...


class _ProposalEvidenceLocation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    representation_id: str
    text_view_id: str
    start_char: int
    end_char: int
    node_ids: tuple[str, ...]


class _ProposalEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    selector_type: Literal["pinned_text"]
    source_id: str
    document_id: str
    exact_text: str
    prefix_text: str
    suffix_text: str
    location: _ProposalEvidenceLocation


class _ProposalEvidenceLink(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    evidence_target_id: str
    validation_attempt_id: str
    role: str
    polarity: str
    necessity: str


class _WikiEvidenceRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    citation_number: int
    reference_key: str
    reference_kind: WikiReferenceKind
    source_id: str
    document_id: str
    representation_id: str
    text_view_id: str
    start_char: int
    end_char: int
    exact_text: str
    prefix_text: str
    suffix_text: str
    node_ids: tuple[str, ...]
    page_numbers: tuple[int, ...]
    evidence_target_id: str | None
    evidence_validation_attempt_id: str | None
    proposed_change_id: str | None

    @model_validator(mode="after")
    def validate_shape(self) -> Self:
        if self.citation_number <= 0 or self.end_char <= self.start_char or not self.exact_text:
            raise ValueError("Candidate Wiki citation has an invalid range or number.")
        if self.reference_kind == "evidence_target":
            if (
                self.evidence_target_id is None
                or self.evidence_validation_attempt_id is None
                or self.proposed_change_id is not None
            ):
                raise ValueError("EvidenceTarget citation origin is invalid.")
        elif (
            self.proposed_change_id is None
            or self.evidence_target_id is not None
            or self.evidence_validation_attempt_id is not None
        ):
            raise ValueError("Proposal evidence citation origin is invalid.")
        return self


class _WikiCitationFile(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["candidate_wiki_citations_v1"]
    candidate_snapshot_digest: str
    citations: tuple[_WikiEvidenceRecord, ...]

    @model_validator(mode="after")
    def validate_registry(self) -> Self:
        if re.fullmatch(r"[a-f0-9]{64}", self.candidate_snapshot_digest) is None:
            raise ValueError("Candidate Wiki citation snapshot identity is invalid.")
        if tuple(item.citation_number for item in self.citations) != tuple(
            range(1, len(self.citations) + 1)
        ):
            raise ValueError("Candidate Wiki citations must be contiguously numbered.")
        keys = tuple(item.reference_key for item in self.citations)
        if len(set(keys)) != len(keys):
            raise ValueError("Candidate Wiki citation reference keys must be unique.")
        return self


class _WikiAuditQualifierRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    key: str
    value: str
    value_path: str | None


class _WikiAuditEdgeRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    assertion_id: str
    subject_label: str
    subject_path: str
    predicate: str
    object_label: str
    object_path: str | None
    qualifiers: tuple[_WikiAuditQualifierRecord, ...]


class _WikiAuditRecordFileEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    record_id: str
    record_type: WikiAuditRecordType
    state: Literal["accepted", "pending"]
    review_status: str | None
    record_payload: dict[str, JsonValue]
    record_payload_sha256: str
    proposed_change_ids: tuple[str, ...]
    provenance_activity_ids: tuple[str, ...]
    evidence_reference_keys: tuple[str, ...]
    ontology_edges: tuple[_WikiAuditEdgeRecord, ...]


class _WikiAuditFile(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["candidate_wiki_audit_v1"]
    candidate_snapshot_digest: str
    records: tuple[_WikiAuditRecordFileEntry, ...]

    @model_validator(mode="after")
    def validate_catalog(self) -> Self:
        if re.fullmatch(r"[a-f0-9]{64}", self.candidate_snapshot_digest) is None:
            raise ValueError("Candidate Wiki audit snapshot identity is invalid.")
        record_ids = tuple(item.record_id for item in self.records)
        if record_ids != tuple(sorted(record_ids)) or len(record_ids) != len(set(record_ids)):
            raise ValueError("Candidate Wiki audit records must have unique, ordered identities.")
        for item in self.records:
            if (
                re.fullmatch(r"[a-f0-9]{64}", item.record_payload_sha256) is None
                or _sha256_json(item.record_payload) != item.record_payload_sha256
            ):
                raise ValueError("Candidate Wiki audit record payload digest is invalid.")
            payload = item.record_payload.get("record", item.record_payload)
            if not isinstance(payload, dict) or payload.get("id") != item.record_id:
                raise ValueError("Candidate Wiki audit payload does not identify its record.")
            for values in (
                item.proposed_change_ids,
                item.provenance_activity_ids,
                item.evidence_reference_keys,
            ):
                if values != tuple(sorted(set(values))):
                    raise ValueError("Candidate Wiki audit references must be unique and ordered.")
        return self


@dataclass(frozen=True)
class CandidateIngestionSelection:
    matches: tuple[IngestionRun, ...]


@dataclass(frozen=True)
class CandidateViewRecord:
    record_type: WikiRecordType
    record: WikiIntelligenceRecord
    review_status: ReviewStatus
    proposed_change_id: str | None
    provenance_activity_ids: tuple[str, ...]
    record_payload_json: str
    source_payload_json: str
    source_payload_sha256: str
    evidence_reference_keys: tuple[str, ...]

    @property
    def is_pending(self) -> bool:
        return self.review_status is ReviewStatus.PENDING


@dataclass(frozen=True)
class WikiEvidenceReference:
    citation_number: int
    reference_key: str
    reference_kind: WikiReferenceKind
    source_id: str
    document_id: str
    representation_id: str
    text_view_id: str
    start_char: int
    end_char: int
    exact_text: str
    prefix_text: str
    suffix_text: str
    node_ids: tuple[str, ...]
    page_numbers: tuple[int, ...]
    evidence_target_id: str | None
    evidence_validation_attempt_id: str | None
    proposed_change_id: str | None


@dataclass(frozen=True)
class CandidateKnowledgeView:
    view_policy_id: str
    ingestion_run: IngestionRun
    ingestion_change_set: IngestionChangeSet
    source: Source
    document: Document
    candidate_snapshot_digest: str
    records: tuple[CandidateViewRecord, ...]
    evidence_references: tuple[WikiEvidenceReference, ...]
    excluded_proposal_counts: tuple[tuple[str, int], ...]


@dataclass(frozen=True)
class WikiLink:
    record_id: str
    label: str
    relative_path: str
    state: Literal["accepted", "pending"]
    record_type: str
    citation_numbers: tuple[int, ...] = ()


@dataclass(frozen=True)
class WikiDetail:
    label: str
    value: str
    relative_path: str | None = None


@dataclass(frozen=True)
class WikiOntologyQualifier:
    key: str
    value: str
    value_path: str | None = None


@dataclass(frozen=True)
class WikiOntologyEdge:
    assertion_id: str
    subject_label: str
    subject_path: str
    predicate: str
    object_label: str
    object_path: str | None
    qualifiers: tuple[WikiOntologyQualifier, ...]


@dataclass(frozen=True)
class WikiAssertionPresentation:
    presentation_id: str
    proposed_change_id: str | None
    edge: WikiOntologyEdge
    state: Literal["accepted", "pending"]
    citation_numbers: tuple[int, ...]
    related_paths: tuple[str, ...]


@dataclass(frozen=True)
class WikiEventPresentation:
    presentation_id: str
    event_id: str
    assertion_ids: tuple[str, ...]
    proposed_change_ids: tuple[str, ...]
    frame_id: str
    complete: bool
    state: Literal["accepted", "pending"]
    edges: tuple[WikiOntologyEdge, ...]
    issues: tuple[str, ...]
    citation_numbers: tuple[int, ...]
    related_paths: tuple[str, ...]


type WikiPresentation = WikiAssertionPresentation | WikiEventPresentation


@dataclass(frozen=True)
class WikiPageInput:
    relative_path: str
    page_kind: str
    record_id: str | None
    display_label: str
    state: Literal["accepted", "pending"] | None
    details: tuple[WikiDetail, ...]
    links: tuple[WikiLink, ...]
    presentations: tuple[WikiPresentation, ...]
    citation_numbers: tuple[int, ...]
    input_fingerprint: str


@dataclass(frozen=True)
class WikiCitationRegistry:
    candidate_snapshot_digest: str
    citations: tuple[WikiEvidenceReference, ...]


@dataclass(frozen=True)
class WikiAuditRecord:
    record_id: str
    record_type: WikiAuditRecordType
    state: Literal["accepted", "pending"]
    review_status: str | None
    record_payload: dict[str, JsonValue]
    record_payload_sha256: str
    proposed_change_ids: tuple[str, ...]
    provenance_activity_ids: tuple[str, ...]
    evidence_reference_keys: tuple[str, ...]
    ontology_edges: tuple[WikiOntologyEdge, ...]


@dataclass(frozen=True)
class WikiAuditCatalog:
    candidate_snapshot_digest: str
    records: tuple[WikiAuditRecord, ...]


@dataclass(frozen=True)
class CandidateWikiPlan:
    view_policy_id: str
    renderer_policy_id: str
    ingestion_run_id: str
    ingestion_change_set_id: str
    candidate_snapshot_digest: str
    pages: tuple[WikiPageInput, ...]
    citation_registry: WikiCitationRegistry
    audit_catalog: WikiAuditCatalog
    counts: tuple[tuple[str, int], ...]


@dataclass(frozen=True)
class WikiBuildFileEntry:
    relative_path: str
    input_fingerprint: str
    content_sha256: str


@dataclass(frozen=True)
class WikiBuildManifest:
    schema_version: str
    build_id: str
    view_policy_id: str
    renderer_policy_id: str
    ingestion_run_id: str
    ingestion_change_set_id: str
    candidate_snapshot_digest: str
    files: tuple[WikiBuildFileEntry, ...]
    counts: tuple[tuple[str, int], ...]


@dataclass(frozen=True)
class RenderedWikiFile:
    relative_path: str
    payload: bytes


@dataclass(frozen=True)
class RenderedCandidateWiki:
    manifest: WikiBuildManifest
    files: tuple[RenderedWikiFile, ...]


@dataclass(frozen=True)
class CandidateWikiPublishResult:
    build_id: str
    active_relative_path: str
    disposition: Literal["created", "reused"]


@dataclass(frozen=True)
class CandidateWikiAuditBundle:
    manifest: WikiBuildManifest
    citation_registry: WikiCitationRegistry
    audit_catalog: WikiAuditCatalog


@dataclass(frozen=True)
class AuditCandidateWikiRecordCommand:
    build_id: str
    record_id: str


@dataclass(frozen=True)
class CandidateWikiRecordAudit:
    build_id: str
    candidate_snapshot_digest: str
    record: WikiAuditRecord
    evidence: tuple[WikiEvidenceReference, ...]


class CandidateWikiArchive(Protocol):
    def publish_candidate_wiki(
        self, rendered_wiki: RenderedCandidateWiki
    ) -> CandidateWikiPublishResult: ...


class CandidateWikiAuditArchive(Protocol):
    def read_candidate_wiki_audit_bundle(self, build_id: str) -> CandidateWikiAuditBundle: ...


def select_candidate_ingestions(
    filename: str, ledger: CandidateWikiLedger
) -> CandidateIngestionSelection:
    """Return closed captured runs for one exact display filename, newest first."""
    if (
        not filename
        or "/" in filename
        or "\\" in filename
        or filename != PurePosixPath(filename).name
    ):
        raise ValueError("Candidate Wiki filename must be one exact filename basename.")
    matches = tuple(
        sorted(
            (
                run
                for run in ledger.list_ingestion_runs()
                if run.display_filename == filename
                and run.status is IngestionRunStatus.CAPTURED
                and run.ingestion_change_set_id is not None
            ),
            key=lambda run: (run.started_at, run.id),
            reverse=True,
        )
    )
    if not matches:
        raise ValueError(f"No closed ingestion found for filename: {filename}")
    return CandidateIngestionSelection(matches)


def build_candidate_knowledge_view(
    ingestion_run: IngestionRun,
    ledger: CandidateWikiLedger,
) -> CandidateKnowledgeView:
    """Resolve one closed change set into a validated, read-only candidate snapshot."""
    change_set, source, document, bundle = _candidate_wiki_authority(ingestion_run, ledger)
    proposals = _candidate_wiki_proposals(change_set, source, document, ledger)
    records, excluded, evidence_by_key = _candidate_wiki_content(proposals, bundle, ledger)
    _close_references(records, evidence_by_key, bundle, ledger)
    ordered_records = tuple(
        sorted(records.values(), key=lambda item: (item.record_type, item.record.id))
    )
    ordered_evidence = tuple(
        _numbered_evidence(item, number)
        for number, item in enumerate(
            sorted(
                evidence_by_key.values(),
                key=lambda item: (
                    item.document_id,
                    item.start_char,
                    item.end_char,
                    item.reference_kind,
                    item.reference_key,
                ),
            ),
            start=1,
        )
    )
    evidence_number_by_key = {item.reference_key: item.citation_number for item in ordered_evidence}
    ordered_records = tuple(
        CandidateViewRecord(
            record_type=item.record_type,
            record=item.record,
            review_status=item.review_status,
            proposed_change_id=item.proposed_change_id,
            provenance_activity_ids=item.provenance_activity_ids,
            record_payload_json=item.record_payload_json,
            source_payload_json=item.source_payload_json,
            source_payload_sha256=item.source_payload_sha256,
            evidence_reference_keys=tuple(
                sorted(item.evidence_reference_keys, key=evidence_number_by_key.__getitem__)
            ),
        )
        for item in ordered_records
    )
    snapshot_payload = {
        "view_policy_id": CANDIDATE_WIKI_VIEW_POLICY_ID,
        "ingestion_run_id": ingestion_run.id,
        "ingestion_change_set_id": change_set.id,
        "change_set_digest": change_set.change_set_digest,
        "source_record_sha256": hashlib.sha256(
            canonical_record_json(source).encode("utf-8")
        ).hexdigest(),
        "document_record_sha256": hashlib.sha256(
            canonical_record_json(document).encode("utf-8")
        ).hexdigest(),
        "representation_output_digest": bundle.representation.canonical_output_digest,
        "proposals": [_proposal_snapshot(item) for item in proposals],
        "records": [
            {
                "record_type": item.record_type,
                "record_id": item.record.id,
                "review_status": item.review_status.value,
                "proposed_change_id": item.proposed_change_id,
                "provenance_activity_ids": list(item.provenance_activity_ids),
                "record_payload_sha256": hashlib.sha256(
                    item.record_payload_json.encode("utf-8")
                ).hexdigest(),
                "source_payload_sha256": item.source_payload_sha256,
                "evidence_reference_keys": list(item.evidence_reference_keys),
            }
            for item in ordered_records
        ],
        "evidence": [_evidence_identity(item) for item in ordered_evidence],
        "excluded_proposal_counts": dict(sorted(excluded.items())),
    }
    return CandidateKnowledgeView(
        view_policy_id=CANDIDATE_WIKI_VIEW_POLICY_ID,
        ingestion_run=ingestion_run,
        ingestion_change_set=change_set,
        source=source,
        document=document,
        candidate_snapshot_digest=_sha256_json(snapshot_payload),
        records=ordered_records,
        evidence_references=ordered_evidence,
        excluded_proposal_counts=tuple(sorted(excluded.items())),
    )


def _candidate_wiki_authority(
    ingestion_run: IngestionRun, ledger: CandidateWikiLedger
) -> tuple[IngestionChangeSet, Source, Document, DocumentRepresentationBundle]:
    if (
        ingestion_run.status is not IngestionRunStatus.CAPTURED
        or ingestion_run.ingestion_change_set_id is None
        or ingestion_run.source_id is None
        or ingestion_run.document_id is None
        or ingestion_run.representation_id is None
    ):
        raise ValueError("Candidate Wiki requires one captured ingestion with a closed change set.")
    change_set = ledger.get_ingestion_change_set(ingestion_run.ingestion_change_set_id)
    if change_set is None or change_set.ingestion_run_id != ingestion_run.id:
        raise ValueError("IngestionRun references an invalid IngestionChangeSet.")
    _validate_change_set_digest(change_set)
    if change_set.representation_id != ingestion_run.representation_id:
        raise ValueError("IngestionRun and IngestionChangeSet representations differ.")
    source = ledger.get_source(ingestion_run.source_id)
    document = ledger.get_document(ingestion_run.document_id)
    bundle = ledger.get_document_representation_bundle(ingestion_run.representation_id)
    if source is None or document is None or bundle is None:
        raise ValueError("Candidate Wiki authoritative source state is incomplete.")
    if document.source_id != source.id or bundle.representation.document_id != document.id:
        raise ValueError("Candidate Wiki authoritative source references are inconsistent.")
    return change_set, source, document, bundle


def _candidate_wiki_proposals(
    change_set: IngestionChangeSet,
    source: Source,
    document: Document,
    ledger: CandidateWikiLedger,
) -> tuple[ProposedChange, ...]:
    proposals: list[ProposedChange] = []
    for proposal_id in change_set.proposed_change_ids:
        proposal = ledger.get_proposed_change(proposal_id)
        if proposal is None:
            raise ValueError(f"IngestionChangeSet references missing ProposedChange: {proposal_id}")
        if proposal.document_id != document.id or proposal.source_id != source.id:
            raise ValueError("IngestionChangeSet contains a foreign ProposedChange.")
        proposals.append(proposal)
    return tuple(proposals)


def _candidate_wiki_content(
    proposals: tuple[ProposedChange, ...],
    bundle: DocumentRepresentationBundle,
    ledger: CandidateWikiLedger,
) -> tuple[
    dict[str, CandidateViewRecord],
    Counter[str],
    dict[str, WikiEvidenceReference],
]:
    records: dict[str, CandidateViewRecord] = {}
    excluded = Counter[str]()
    evidence_by_key: dict[str, WikiEvidenceReference] = {}
    for proposal in proposals:
        if proposal.review_status is ReviewStatus.REJECTED:
            record_type = proposal.proposed_json.get("record_type")
            excluded[str(record_type) if isinstance(record_type, str) else "invalid"] += 1
            continue
        view_record = _proposal_view_record(proposal, bundle, ledger)
        _add_record(records, view_record)
        for evidence in _proposal_evidence_references(proposal, view_record, bundle, ledger):
            evidence_by_key[evidence.reference_key] = evidence
    return records, excluded, evidence_by_key


def plan_candidate_wiki(view: CandidateKnowledgeView) -> CandidateWikiPlan:
    """Turn one validated view into deterministic, renderer-ready page inputs."""
    named_records = tuple(item for item in view.records if item.record_type != "Assertion")
    paths = _record_paths(named_records)
    evidence_numbers = {
        item.reference_key: item.citation_number for item in view.evidence_references
    }
    evidence_by_number = {item.citation_number: item for item in view.evidence_references}
    by_id = {item.record.id: item for item in view.records}
    presentations = _plan_presentations(view.records, by_id, paths, evidence_numbers)
    pages: list[WikiPageInput] = []
    counts = Counter[str]()
    for item in view.records:
        state = "pending" if item.is_pending else "accepted"
        counts[f"{item.record_type}.{state}"] += 1
    for record_type, count in view.excluded_proposal_counts:
        counts[f"{record_type}.rejected"] += count

    all_links = tuple(
        _record_link(item, paths[item.record.id], evidence_numbers) for item in named_records
    )
    pages.append(
        _page(
            relative_path="index.md",
            page_kind="home",
            record_id=None,
            display_label="Candidate Wiki",
            state=None,
            details=(
                WikiDetail("Document", view.ingestion_run.display_filename),
                WikiDetail("Source", view.ingestion_run.normalized_source_url or "Unavailable"),
                WikiDetail("Candidate records", str(len(view.records))),
            ),
            links=all_links,
            presentations=(),
            citations=(),
            evidence_by_number=evidence_by_number,
        )
    )
    document_path = f"documents/{_slug(view.ingestion_run.display_filename)}.md"
    pages.append(
        _page(
            relative_path=document_path,
            page_kind="document",
            record_id=view.document.id,
            display_label=view.ingestion_run.display_filename,
            state="accepted",
            details=(
                WikiDetail("Source URL", view.ingestion_run.normalized_source_url or "Unavailable"),
                WikiDetail("Content SHA-256", view.document.content_sha256),
            ),
            links=all_links,
            presentations=presentations,
            citations=tuple(item.citation_number for item in view.evidence_references),
            evidence_by_number=evidence_by_number,
        )
    )
    for item in named_records:
        record_id = item.record.id
        pages.append(
            _page(
                relative_path=paths[record_id],
                page_kind=item.record_type.casefold(),
                record_id=record_id,
                display_label=_record_label(cast(WikiNamedRecord, item.record)),
                state="pending" if item.is_pending else "accepted",
                details=_record_details(item.record, by_id, paths),
                links=(),
                presentations=tuple(
                    presentation
                    for presentation in presentations
                    if paths[record_id] in presentation.related_paths
                ),
                citations=_record_citation_numbers(item, evidence_numbers),
                evidence_by_number=evidence_by_number,
            )
        )
    ordered_pages = tuple(
        sorted(
            pages,
            key=lambda item: (
                _page_order(item.page_kind),
                item.display_label.casefold(),
                item.relative_path,
            ),
        )
    )
    audit_catalog = _plan_wiki_audit_catalog(view, presentations)
    return CandidateWikiPlan(
        view_policy_id=view.view_policy_id,
        renderer_policy_id=CANDIDATE_WIKI_RENDERER_POLICY_ID,
        ingestion_run_id=view.ingestion_run.id,
        ingestion_change_set_id=view.ingestion_change_set.id,
        candidate_snapshot_digest=view.candidate_snapshot_digest,
        pages=ordered_pages,
        citation_registry=WikiCitationRegistry(
            candidate_snapshot_digest=view.candidate_snapshot_digest,
            citations=view.evidence_references,
        ),
        audit_catalog=audit_catalog,
        counts=tuple(sorted(counts.items())),
    )


def canonical_wiki_manifest_bytes(manifest: WikiBuildManifest) -> bytes:
    return (_canonical_json(_manifest_json(manifest)) + "\n").encode("utf-8")


def canonical_wiki_citations_bytes(registry: WikiCitationRegistry) -> bytes:
    value = {
        "schema_version": "candidate_wiki_citations_v1",
        "candidate_snapshot_digest": registry.candidate_snapshot_digest,
        "citations": [_evidence_json(item) for item in registry.citations],
    }
    return (_canonical_json(value) + "\n").encode("utf-8")


def canonical_wiki_audit_bytes(catalog: WikiAuditCatalog) -> bytes:
    value = {
        "schema_version": "candidate_wiki_audit_v1",
        "candidate_snapshot_digest": catalog.candidate_snapshot_digest,
        "records": [_wiki_audit_record_json(item) for item in catalog.records],
    }
    return (_canonical_json(value) + "\n").encode("utf-8")


def wiki_citation_registry_from_bytes(payload: bytes) -> WikiCitationRegistry:
    parsed = _WikiCitationFile.model_validate_json(payload)
    return WikiCitationRegistry(
        candidate_snapshot_digest=parsed.candidate_snapshot_digest,
        citations=tuple(
            WikiEvidenceReference(
                citation_number=item.citation_number,
                reference_key=item.reference_key,
                reference_kind=item.reference_kind,
                source_id=item.source_id,
                document_id=item.document_id,
                representation_id=item.representation_id,
                text_view_id=item.text_view_id,
                start_char=item.start_char,
                end_char=item.end_char,
                exact_text=item.exact_text,
                prefix_text=item.prefix_text,
                suffix_text=item.suffix_text,
                node_ids=item.node_ids,
                page_numbers=item.page_numbers,
                evidence_target_id=item.evidence_target_id,
                evidence_validation_attempt_id=item.evidence_validation_attempt_id,
                proposed_change_id=item.proposed_change_id,
            )
            for item in parsed.citations
        ),
    )


def wiki_audit_catalog_from_bytes(payload: bytes) -> WikiAuditCatalog:
    parsed = _WikiAuditFile.model_validate_json(payload)
    return WikiAuditCatalog(
        candidate_snapshot_digest=parsed.candidate_snapshot_digest,
        records=tuple(
            WikiAuditRecord(
                record_id=item.record_id,
                record_type=item.record_type,
                state=item.state,
                review_status=item.review_status,
                record_payload=item.record_payload,
                record_payload_sha256=item.record_payload_sha256,
                proposed_change_ids=item.proposed_change_ids,
                provenance_activity_ids=item.provenance_activity_ids,
                evidence_reference_keys=item.evidence_reference_keys,
                ontology_edges=tuple(
                    _wiki_audit_edge_from_file(edge) for edge in item.ontology_edges
                ),
            )
            for item in parsed.records
        ),
    )


def audit_candidate_wiki_record(
    command: AuditCandidateWikiRecordCommand,
    archive: CandidateWikiAuditArchive,
) -> CandidateWikiRecordAudit:
    """Resolve one stable record from one immutable Wiki build without parsing Markdown."""
    bundle = archive.read_candidate_wiki_audit_bundle(command.build_id)
    validate_candidate_wiki_audit_bundle(bundle)
    if bundle.manifest.build_id != command.build_id:
        raise ValueError("Candidate Wiki audit returned a different build identity.")
    by_record_id = {item.record_id: item for item in bundle.audit_catalog.records}
    record = by_record_id.get(command.record_id)
    if record is None:
        raise ValueError(
            f"Candidate Wiki build {command.build_id} has no record: {command.record_id}"
        )
    evidence_by_key = {item.reference_key: item for item in bundle.citation_registry.citations}
    missing = set(record.evidence_reference_keys).difference(evidence_by_key)
    if missing:
        raise ValueError(
            "Candidate Wiki audit record references missing evidence: " + ", ".join(sorted(missing))
        )
    return CandidateWikiRecordAudit(
        build_id=command.build_id,
        candidate_snapshot_digest=bundle.manifest.candidate_snapshot_digest,
        record=record,
        evidence=tuple(
            sorted(
                (evidence_by_key[key] for key in record.evidence_reference_keys),
                key=lambda item: item.citation_number,
            )
        ),
    )


def validate_candidate_wiki_audit_bundle(bundle: CandidateWikiAuditBundle) -> None:
    snapshot_digests = {
        bundle.manifest.candidate_snapshot_digest,
        bundle.citation_registry.candidate_snapshot_digest,
        bundle.audit_catalog.candidate_snapshot_digest,
    }
    if len(snapshot_digests) != 1:
        raise ValueError("Candidate Wiki audit artifacts describe different snapshots.")
    evidence_keys = {item.reference_key for item in bundle.citation_registry.citations}
    record_ids = {item.record_id for item in bundle.audit_catalog.records}
    for record in bundle.audit_catalog.records:
        missing_evidence = set(record.evidence_reference_keys).difference(evidence_keys)
        if missing_evidence:
            raise ValueError(
                "Candidate Wiki audit record references missing evidence: "
                + ", ".join(sorted(missing_evidence))
            )
        missing_assertions = {edge.assertion_id for edge in record.ontology_edges}.difference(
            record_ids
        )
        if missing_assertions:
            raise ValueError(
                "Candidate Wiki audit graph references missing Assertion records: "
                + ", ".join(sorted(missing_assertions))
            )


def candidate_wiki_record_audit_json(result: CandidateWikiRecordAudit) -> dict[str, object]:
    return {
        "schema_version": "candidate_wiki_record_audit_v1",
        "build_id": result.build_id,
        "candidate_snapshot_digest": result.candidate_snapshot_digest,
        "record": _wiki_audit_record_json(result.record),
        "evidence": [_audit_evidence_json(item) for item in result.evidence],
    }


def wiki_build_manifest_from_bytes(payload: bytes) -> WikiBuildManifest:
    decoded: object = json.loads(payload)
    if not isinstance(decoded, dict):
        raise ValueError("Candidate Wiki manifest must be one JSON object.")
    value = cast(dict[str, object], decoded)
    files_value = value.get("files")
    counts_value = value.get("counts")
    if not isinstance(files_value, list) or not isinstance(counts_value, dict):
        raise ValueError("Candidate Wiki manifest has an invalid shape.")
    raw_files = cast(list[object], files_value)
    file_entries: list[WikiBuildFileEntry] = []
    for raw_file in raw_files:
        if not isinstance(raw_file, dict):
            raise ValueError("Candidate Wiki manifest file entries are invalid.")
        file_value = cast(dict[str, object], raw_file)
        file_entries.append(
            WikiBuildFileEntry(
                relative_path=_required_string(file_value, "relative_path"),
                input_fingerprint=_required_digest(file_value, "input_fingerprint"),
                content_sha256=_required_digest(file_value, "content_sha256"),
            )
        )
    raw_counts = cast(dict[object, object], counts_value)
    manifest = WikiBuildManifest(
        schema_version=_required_string(value, "schema_version"),
        build_id=_required_string(value, "build_id"),
        view_policy_id=_required_string(value, "view_policy_id"),
        renderer_policy_id=_required_string(value, "renderer_policy_id"),
        ingestion_run_id=_required_string(value, "ingestion_run_id"),
        ingestion_change_set_id=_required_string(value, "ingestion_change_set_id"),
        candidate_snapshot_digest=_required_digest(value, "candidate_snapshot_digest"),
        files=tuple(file_entries),
        counts=tuple(sorted((str(key), _integer_value(item)) for key, item in raw_counts.items())),
    )
    if manifest.schema_version != "candidate_wiki_manifest_v2":
        raise ValueError("Candidate Wiki manifest schema version is unsupported.")
    expected_id = _wiki_build_id(manifest)
    if manifest.build_id != expected_id:
        raise ValueError("Candidate Wiki manifest build identity is invalid.")
    if tuple(sorted(manifest.files, key=lambda item: item.relative_path)) != manifest.files:
        raise ValueError("Candidate Wiki manifest files must be ordered by path.")
    return manifest


def _proposal_view_record(
    proposal: ProposedChange,
    bundle: DocumentRepresentationBundle,
    ledger: CandidateWikiLedger,
) -> CandidateViewRecord:
    record_type = proposal.proposed_json.get("record_type")
    if record_type not in {"Actor", "Organization", "Event", "Assertion"}:
        raise ValueError(f"Unsupported Candidate Wiki proposal record type: {record_type}")
    typed_record_type = cast(WikiRecordType, record_type)
    if proposal.review_status is ReviewStatus.PENDING:
        payload = proposal.proposed_json.get("record")
        if not isinstance(payload, dict):
            raise ValueError("ProposedChange record payload must be one object.")
        record_payload_json = _canonical_json(payload)
        source_payload_json = _canonical_json(proposal.proposed_json)
        record = _parse_record(typed_record_type, payload, proposed=True)
    elif proposal.review_status in {ReviewStatus.APPROVED, ReviewStatus.EDITED}:
        if proposal.accepted_json is None:
            raise ValueError("Reviewed ProposedChange has no accepted record payload.")
        record = _parse_record(typed_record_type, proposal.accepted_json, proposed=False)
        persisted = _load_record(record.id, ledger)
        if persisted is None or persisted != record:
            raise ValueError("Reviewed ProposedChange accepted record is absent or changed.")
        record_payload_json = _canonical_json(proposal.accepted_json)
        source_payload_json = canonical_record_json(record)
    else:
        raise ValueError("Rejected ProposedChange cannot become a Candidate Wiki record.")
    evidence_keys = _proposal_evidence_keys(proposal, typed_record_type)
    return CandidateViewRecord(
        record_type=typed_record_type,
        record=record,
        review_status=proposal.review_status,
        proposed_change_id=proposal.id,
        provenance_activity_ids=tuple(
            sorted(
                {
                    *(record.provenance_activity_ids if isinstance(record, Assertion) else ()),
                    *(
                        (proposal.provenance_activity_id,)
                        if proposal.provenance_activity_id is not None
                        else ()
                    ),
                }
            )
        ),
        record_payload_json=record_payload_json,
        source_payload_json=source_payload_json,
        source_payload_sha256=hashlib.sha256(source_payload_json.encode("utf-8")).hexdigest(),
        evidence_reference_keys=evidence_keys,
    )


def _parse_record(
    record_type: WikiRecordType, payload: object, *, proposed: bool
) -> WikiIntelligenceRecord:
    model_by_type: dict[str, type[BaseModel]] = {
        "Actor": Actor,
        "Organization": Organization,
        "Event": Event,
        "Assertion": ProposedAssertion if proposed else Assertion,
        "Entity": Entity,
        "Place": Place,
    }
    return cast(
        WikiIntelligenceRecord,
        model_by_type[record_type].model_validate_json(_canonical_json(payload)),
    )


def _proposal_evidence_keys(
    proposal: ProposedChange, record_type: WikiRecordType
) -> tuple[str, ...]:
    if record_type != "Assertion":
        evidence = _reconciled_proposal_evidence(proposal)
        if evidence is not None:
            return tuple(f"proposal:{proposal.id}:{ordinal}" for ordinal, _ in enumerate(evidence))
        return (f"proposal:{proposal.id}",)
    raw_links = proposal.proposed_json.get("evidence_links")
    if not isinstance(raw_links, list):
        raise ValueError("Assertion proposal requires evidence_links.")
    links = tuple(
        _ProposalEvidenceLink.model_validate_json(_canonical_json(item)) for item in raw_links
    )
    return tuple(f"target:{item.evidence_target_id}:{item.validation_attempt_id}" for item in links)


def _proposal_evidence_references(
    proposal: ProposedChange,
    record: CandidateViewRecord,
    bundle: DocumentRepresentationBundle,
    ledger: CandidateWikiLedger,
) -> tuple[WikiEvidenceReference, ...]:
    if record.record_type != "Assertion":
        reconciled_evidence = _reconciled_proposal_evidence(proposal)
        if reconciled_evidence is not None:
            references: list[WikiEvidenceReference] = []
            for ordinal, evidence in enumerate(reconciled_evidence):
                if (
                    evidence.source_id != proposal.source_id
                    or evidence.document_id != proposal.document_id
                ):
                    raise ValueError(
                        "Reconciled proposal evidence does not belong to its ProposedChange."
                    )
                references.append(
                    _proposal_evidence_reference(
                        proposal.id,
                        evidence,
                        bundle,
                        reference_key=f"proposal:{proposal.id}:{ordinal}",
                    )
                )
            return tuple(references)
        evidence = _ProposalEvidence.model_validate_json(
            _canonical_json(proposal.proposed_json.get("evidence"))
        )
        if evidence.source_id != proposal.source_id or evidence.document_id != proposal.document_id:
            raise ValueError("Proposal evidence does not belong to its ProposedChange.")
        return (_proposal_evidence_reference(proposal.id, evidence, bundle),)
    references: list[WikiEvidenceReference] = []
    raw_links = proposal.proposed_json.get("evidence_links")
    if not isinstance(raw_links, list):
        raise ValueError("Assertion proposal requires evidence_links.")
    for raw_link in raw_links:
        link = _ProposalEvidenceLink.model_validate_json(_canonical_json(raw_link))
        target = ledger.get_evidence_target(link.evidence_target_id)
        attempt = ledger.get_evidence_validation_attempt(link.validation_attempt_id)
        if target is None or attempt is None:
            raise ValueError("Assertion proposal references missing evidence validation state.")
        replay = verify_evidence_target(target, attempt, ledger)
        if not replay.valid:
            raise ValueError(f"Candidate Wiki evidence replay failed: {replay.error_message}")
        references.append(_target_evidence_reference(target, attempt, bundle))
    return tuple(references)


def _proposal_evidence_reference(
    proposal_id: str,
    evidence: _ProposalEvidence,
    bundle: DocumentRepresentationBundle,
    *,
    reference_key: str | None = None,
) -> WikiEvidenceReference:
    location = evidence.location
    _validate_selector(
        representation_id=location.representation_id,
        text_view_id=location.text_view_id,
        start_char=location.start_char,
        end_char=location.end_char,
        exact_text=evidence.exact_text,
        prefix_text=evidence.prefix_text,
        suffix_text=evidence.suffix_text,
        node_ids=location.node_ids,
        bundle=bundle,
    )
    return WikiEvidenceReference(
        citation_number=0,
        reference_key=reference_key or f"proposal:{proposal_id}",
        reference_kind="proposal_evidence",
        source_id=evidence.source_id,
        document_id=evidence.document_id,
        representation_id=location.representation_id,
        text_view_id=location.text_view_id,
        start_char=location.start_char,
        end_char=location.end_char,
        exact_text=evidence.exact_text,
        prefix_text=evidence.prefix_text,
        suffix_text=evidence.suffix_text,
        node_ids=location.node_ids,
        page_numbers=_page_numbers(location.node_ids, bundle),
        evidence_target_id=None,
        evidence_validation_attempt_id=None,
        proposed_change_id=proposal_id,
    )


def _reconciled_proposal_evidence(
    proposal: ProposedChange,
) -> tuple[_ProposalEvidence, ...] | None:
    reconciliation = proposal.proposed_json.get("identity_reconciliation")
    if not isinstance(reconciliation, dict):
        return None
    raw = reconciliation.get("mention_evidence")
    if raw is None:
        return None
    if not isinstance(raw, list) or not raw:
        raise ValueError("Reconciled named-entity proposal requires mention evidence.")
    evidence = tuple(_ProposalEvidence.model_validate_json(_canonical_json(item)) for item in raw)
    if len(set(evidence)) != len(evidence):
        raise ValueError("Reconciled named-entity proposal repeats mention evidence.")
    return evidence


def _target_evidence_reference(
    target: EvidenceTarget,
    attempt: EvidenceValidationAttempt,
    bundle: DocumentRepresentationBundle,
) -> WikiEvidenceReference:
    if (
        target.representation_id != bundle.representation.id
        or target.document_id != bundle.representation.document_id
    ):
        raise ValueError("Candidate Wiki EvidenceTarget belongs to a different Document.")
    return WikiEvidenceReference(
        citation_number=0,
        reference_key=f"target:{target.id}:{attempt.id}",
        reference_kind="evidence_target",
        source_id=target.source_id,
        document_id=target.document_id,
        representation_id=target.representation_id,
        text_view_id=target.text_view_id,
        start_char=target.start_char,
        end_char=target.end_char,
        exact_text=target.exact_text,
        prefix_text=target.prefix_text,
        suffix_text=target.suffix_text,
        node_ids=target.node_ids,
        page_numbers=_page_numbers(target.node_ids, bundle),
        evidence_target_id=target.id,
        evidence_validation_attempt_id=attempt.id,
        proposed_change_id=None,
    )


def _validate_selector(
    *,
    representation_id: str,
    text_view_id: str,
    start_char: int,
    end_char: int,
    exact_text: str,
    prefix_text: str,
    suffix_text: str,
    node_ids: tuple[str, ...],
    bundle: DocumentRepresentationBundle,
) -> None:
    if representation_id != bundle.representation.id:
        raise ValueError("Proposal evidence references a foreign representation.")
    view = next((item for item in bundle.text_views if item.id == text_view_id), None)
    if view is None or end_char <= start_char or end_char > len(view.text):
        raise ValueError("Proposal evidence text selector is invalid.")
    if view.text[start_char:end_char] != exact_text:
        raise ValueError("Proposal evidence exact text does not replay.")
    if view.text[max(0, start_char - len(prefix_text)) : start_char] != prefix_text:
        raise ValueError("Proposal evidence prefix does not replay.")
    if view.text[end_char : end_char + len(suffix_text)] != suffix_text:
        raise ValueError("Proposal evidence suffix does not replay.")
    nodes = {item.id: item for item in bundle.nodes}
    if not node_ids:
        raise ValueError("Proposal evidence requires a structural node selector.")
    for node_id in node_ids:
        node = nodes.get(node_id)
        if (
            node is None
            or node.text_view_id != text_view_id
            or node.start_char > start_char
            or node.end_char < end_char
        ):
            raise ValueError("Proposal evidence node selector does not contain its text.")


def _page_numbers(
    node_ids: tuple[str, ...], bundle: DocumentRepresentationBundle
) -> tuple[int, ...]:
    nodes = {item.id: item for item in bundle.nodes}
    return tuple(
        sorted({page for node_id in node_ids for page in nodes[node_id].source_page_numbers})
    )


def _close_references(
    records: dict[str, CandidateViewRecord],
    evidence_by_key: dict[str, WikiEvidenceReference],
    bundle: DocumentRepresentationBundle,
    ledger: CandidateWikiLedger,
) -> None:
    queue = deque(record.record.id for record in records.values())
    checked: set[str] = set()
    while queue:
        record_id = queue.popleft()
        if record_id in checked:
            continue
        checked.add(record_id)
        item = records[record_id]
        for reference_id in _record_reference_ids(item.record):
            if reference_id in records:
                continue
            referenced = _load_record(reference_id, ledger)
            if referenced is None:
                raise ValueError(
                    f"Candidate Wiki record references missing accepted record: {reference_id}"
                )
            evidence_keys: tuple[str, ...] = ()
            if isinstance(referenced, Assertion):
                evidence = _accepted_assertion_evidence(referenced, bundle, ledger)
                for reference in evidence:
                    evidence_by_key[reference.reference_key] = reference
                evidence_keys = tuple(reference.reference_key for reference in evidence)
            source_json = canonical_record_json(referenced)
            accepted = CandidateViewRecord(
                record_type=_record_type(referenced),
                record=referenced,
                review_status=ReviewStatus.APPROVED,
                proposed_change_id=None,
                provenance_activity_ids=(
                    referenced.provenance_activity_ids if isinstance(referenced, Assertion) else ()
                ),
                record_payload_json=source_json,
                source_payload_json=source_json,
                source_payload_sha256=hashlib.sha256(source_json.encode()).hexdigest(),
                evidence_reference_keys=evidence_keys,
            )
            _add_record(records, accepted)
            queue.append(reference_id)


def _accepted_assertion_evidence(
    assertion: Assertion,
    bundle: DocumentRepresentationBundle,
    ledger: CandidateWikiLedger,
) -> tuple[WikiEvidenceReference, ...]:
    links = tuple(
        sorted(
            (
                link
                for link in ledger.list_assertion_evidence_links()
                if link.assertion_id == assertion.id
            ),
            key=lambda item: item.id,
        )
    )
    if {link.evidence_target_id for link in links} != set(assertion.evidence_target_ids):
        raise ValueError("Accepted Assertion evidence links do not match its EvidenceTargets.")
    references: list[WikiEvidenceReference] = []
    for link in links:
        target = ledger.get_evidence_target(link.evidence_target_id)
        attempt = ledger.get_evidence_validation_attempt(link.validation_attempt_id)
        if target is None or attempt is None:
            raise ValueError("Accepted Assertion references missing evidence validation state.")
        replay = verify_evidence_target(target, attempt, ledger)
        if not replay.valid:
            raise ValueError(f"Candidate Wiki evidence replay failed: {replay.error_message}")
        references.append(_target_evidence_reference(target, attempt, bundle))
    return tuple(references)


def _record_reference_ids(record: WikiIntelligenceRecord) -> tuple[str, ...]:
    if isinstance(record, Actor):
        return record.organization_ids
    if isinstance(record, Event):
        return tuple(
            item
            for item in (
                record.place_id,
                *record.participant_actor_ids,
                *record.participant_organization_ids,
            )
            if item is not None
        )
    if isinstance(record, (Assertion, ProposedAssertion)):
        return tuple(
            item
            for item in (
                record.subject_entity_id,
                record.object_entity_id,
                record.attributed_to_id,
                *record.supporting_assertion_ids,
            )
            if item is not None
        )
    return ()


def _load_record(record_id: str, ledger: CandidateWikiLedger) -> WikiIntelligenceRecord | None:
    loaders = {
        "ent_": ledger.get_entity,
        "act_": ledger.get_actor,
        "org_": ledger.get_organization,
        "plc_": ledger.get_place,
        "evt_": ledger.get_event,
        "ast_": ledger.get_assertion,
    }
    for prefix, loader in loaders.items():
        if record_id.startswith(prefix):
            return loader(record_id)
    raise ValueError(f"Candidate Wiki reference has an unsupported identity: {record_id}")


def _add_record(records: dict[str, CandidateViewRecord], item: CandidateViewRecord) -> None:
    existing = records.get(item.record.id)
    if existing is not None and existing != item:
        raise ValueError(f"Candidate Wiki contains conflicting record identity: {item.record.id}")
    records[item.record.id] = item


def _record_type(record: WikiIntelligenceRecord) -> WikiRecordType:
    if isinstance(record, Entity):
        return "Entity"
    if isinstance(record, Actor):
        return "Actor"
    if isinstance(record, Organization):
        return "Organization"
    if isinstance(record, Place):
        return "Place"
    if isinstance(record, Event):
        return "Event"
    return "Assertion"


def _record_paths(records: tuple[CandidateViewRecord, ...]) -> dict[str, str]:
    directory = {
        "Entity": "entities",
        "Actor": "actors",
        "Organization": "organizations",
        "Place": "places",
        "Event": "events",
    }
    base_by_id: dict[str, str] = {}
    for item in records:
        label = _record_label(cast(WikiNamedRecord, item.record))
        base_by_id[item.record.id] = f"{directory[item.record_type]}/{_slug(label)}.md"
    grouped: dict[str, list[str]] = {}
    for record_id, path in base_by_id.items():
        grouped.setdefault(path.casefold(), []).append(record_id)
    paths: dict[str, str] = {}
    for record_ids in grouped.values():
        for record_id in sorted(record_ids):
            path = base_by_id[record_id]
            if len(record_ids) > 1:
                stem = path.removesuffix(".md")
                suffix = hashlib.sha256(record_id.encode()).hexdigest()[:8]
                path = f"{stem}--{suffix}.md"
            paths[record_id] = path
    return paths


def _record_label(record: WikiNamedRecord) -> str:
    if isinstance(record, Entity):
        return record.canonical_name
    return record.name


def _record_link(item: CandidateViewRecord, path: str, numbers: dict[str, int]) -> WikiLink:
    return WikiLink(
        record_id=item.record.id,
        label=_record_label(cast(WikiNamedRecord, item.record)),
        relative_path=path,
        state="pending" if item.is_pending else "accepted",
        record_type=item.record_type,
        citation_numbers=_record_citation_numbers(item, numbers),
    )


def _record_citation_numbers(item: CandidateViewRecord, numbers: dict[str, int]) -> tuple[int, ...]:
    return tuple(numbers[key] for key in item.evidence_reference_keys)


def _plan_presentations(
    records: tuple[CandidateViewRecord, ...],
    by_id: dict[str, CandidateViewRecord],
    paths: dict[str, str],
    evidence_numbers: dict[str, int],
) -> tuple[WikiPresentation, ...]:
    assertion_items = tuple(item for item in records if item.record_type == "Assertion")
    structural_values = {item.value for item in HybridEventStructuralPredicate}
    event_assertions: dict[str, list[CandidateViewRecord]] = {}
    for item in assertion_items:
        assertion = cast(Assertion | ProposedAssertion, item.record)
        subject = by_id[assertion.subject_entity_id]
        if (
            subject.record_type != "Event"
            or _assertion_relation(assertion) not in structural_values
        ):
            continue
        event_assertions.setdefault(assertion.subject_entity_id, []).append(item)

    grouped_assertion_ids: set[str] = set()
    presentations: list[WikiPresentation] = []
    for event_id, items in sorted(event_assertions.items()):
        if not any(
            _assertion_relation(cast(Assertion | ProposedAssertion, item.record))
            == HybridEventStructuralPredicate.HAS_EVENT_TYPE.value
            for item in items
        ):
            continue
        ordered = tuple(sorted(items, key=lambda item: item.record.id))
        grouped_assertion_ids.update(item.record.id for item in ordered)
        presentations.append(
            _event_presentation(
                by_id[event_id],
                ordered,
                by_id,
                paths,
                evidence_numbers,
            )
        )

    presentations.extend(
        _assertion_presentation(item, by_id, paths, evidence_numbers)
        for item in assertion_items
        if item.record.id not in grouped_assertion_ids
    )
    return tuple(sorted(presentations, key=_presentation_sort_key))


def _assertion_presentation(
    item: CandidateViewRecord,
    by_id: dict[str, CandidateViewRecord],
    paths: dict[str, str],
    evidence_numbers: dict[str, int],
) -> WikiAssertionPresentation:
    assertion = cast(Assertion | ProposedAssertion, item.record)
    edge = _ontology_edge(assertion, by_id, paths)
    related_paths = {
        paths[assertion.subject_entity_id],
        *(
            paths[item_id]
            for item_id in (assertion.object_entity_id, assertion.attributed_to_id)
            if item_id
        ),
    }
    return WikiAssertionPresentation(
        presentation_id=f"assertion:{assertion.id}",
        proposed_change_id=item.proposed_change_id,
        edge=edge,
        state="pending" if item.is_pending else "accepted",
        citation_numbers=_record_citation_numbers(item, evidence_numbers),
        related_paths=tuple(sorted(related_paths)),
    )


def _event_presentation(
    event_item: CandidateViewRecord,
    assertion_items: tuple[CandidateViewRecord, ...],
    by_id: dict[str, CandidateViewRecord],
    paths: dict[str, str],
    evidence_numbers: dict[str, int],
) -> WikiEventPresentation:
    event = cast(Event, event_item.record)
    assertions = tuple(cast(Assertion | ProposedAssertion, item.record) for item in assertion_items)
    issues: list[str] = []
    event_type_assertions = tuple(
        assertion
        for assertion in assertions
        if _assertion_relation(assertion) == HybridEventStructuralPredicate.HAS_EVENT_TYPE.value
    )
    if len(event_type_assertions) != 1:
        issues.append("The Event must have exactly one governed frame.")
        frame_id = "unknown"
        frame = None
    else:
        value = event_type_assertions[0].object_value
        frame_id = value if isinstance(value, str) else "unknown"
        frame = next(
            (item for item in HYBRID_EVENT_SEMANTICS_V1.frames if item.id == frame_id), None
        )
        if frame is None:
            issues.append(f"Unknown governed frame: {frame_id}.")

    role_assertion_ids: dict[str, str] = {}
    role_definitions = {item.id: item for item in frame.roles} if frame is not None else {}
    related_paths = {paths[event.id]}
    for assertion in assertions:
        if assertion.object_entity_id is not None:
            related_paths.add(paths[assertion.object_entity_id])
        if assertion.attributed_to_id is not None:
            related_paths.add(paths[assertion.attributed_to_id])
        if _assertion_relation(assertion) != HybridEventStructuralPredicate.HAS_ARGUMENT.value:
            continue
        role_id = assertion.qualifiers.get("frame_role_id")
        upper_role = assertion.qualifiers.get("upper_role")
        if not isinstance(role_id, str) or not isinstance(upper_role, str):
            issues.append(f"Argument {assertion.id} lacks governed role qualifiers.")
            continue
        role = role_definitions.get(role_id)
        if role is None or role.upper_role.value != upper_role:
            issues.append(f"Argument {assertion.id} has an invalid governed role.")
            continue
        target_kind = _semantic_argument_target_kind(assertion, by_id)
        if target_kind not in role.allowed_target_kinds:
            issues.append(
                f"Argument {assertion.id} uses {target_kind.value} "
                f"where {role.id} does not allow it."
            )
            continue
        if role_id in role_assertion_ids:
            issues.append(f"Governed role {role_id} occurs more than once.")
            continue
        role_assertion_ids[role_id] = assertion.id

    if frame is not None:
        for role in frame.roles:
            if role.required and role.id not in role_assertion_ids:
                issues.append(f"Missing required role: {role.id}.")

    _single_structural_value(
        assertions,
        HybridEventStructuralPredicate.HAS_POLARITY,
        issues,
        required=True,
        allowed_values={item.value for item in EventPolarity},
    )
    _single_structural_value(
        assertions,
        HybridEventStructuralPredicate.HAS_MODALITY,
        issues,
        required=True,
        allowed_values={item.value for item in EventModality},
    )
    related_paths.update(
        paths[record_id]
        for record_id in (
            event.place_id,
            *event.participant_actor_ids,
            *event.participant_organization_ids,
        )
        if record_id is not None
    )
    edges = tuple(
        sorted(
            (_ontology_edge(assertion, by_id, paths) for assertion in assertions),
            key=_event_edge_sort_key,
        )
    )
    citations = {
        *_record_citation_numbers(event_item, evidence_numbers),
        *(
            number
            for item in assertion_items
            for number in _record_citation_numbers(item, evidence_numbers)
        ),
    }
    proposed_change_ids = {
        item.proposed_change_id
        for item in (event_item, *assertion_items)
        if item.proposed_change_id is not None
    }
    state = (
        "pending" if any(item.is_pending for item in (event_item, *assertion_items)) else "accepted"
    )
    return WikiEventPresentation(
        presentation_id=f"event:{event.id}",
        event_id=event.id,
        assertion_ids=tuple(sorted(assertion.id for assertion in assertions)),
        proposed_change_ids=tuple(sorted(proposed_change_ids)),
        frame_id=frame_id,
        complete=frame is not None and not issues,
        state=state,
        edges=edges,
        issues=tuple(sorted(issues)),
        citation_numbers=tuple(sorted(citations)),
        related_paths=tuple(sorted(related_paths)),
    )


def _single_structural_value(
    assertions: tuple[Assertion | ProposedAssertion, ...],
    predicate: HybridEventStructuralPredicate,
    issues: list[str],
    *,
    required: bool,
    allowed_values: set[str] | None = None,
) -> str | None:
    values = tuple(
        assertion.object_value
        for assertion in assertions
        if _assertion_relation(assertion) == predicate.value
    )
    if len(values) != 1 or not isinstance(values[0], str):
        if required:
            issues.append(f"The Event must have exactly one {predicate.value} value.")
        return None
    value = values[0]
    if allowed_values is not None and value not in allowed_values:
        issues.append(f"The Event has an unknown {predicate.value} value: {value}.")
        return None
    return value


def _assertion_relation(assertion: Assertion | ProposedAssertion) -> str:
    return assertion.predicate if isinstance(assertion, Assertion) else assertion.relation_label


def _assertion_object(
    assertion: Assertion | ProposedAssertion,
    by_id: dict[str, CandidateViewRecord],
    paths: dict[str, str],
) -> tuple[str, str | None]:
    if assertion.object_entity_id is None:
        return _display_value(assertion.object_value), None
    object_record = by_id[assertion.object_entity_id]
    return (
        _record_label(cast(WikiNamedRecord, object_record.record)),
        paths[assertion.object_entity_id],
    )


def _ontology_edge(
    assertion: Assertion | ProposedAssertion,
    by_id: dict[str, CandidateViewRecord],
    paths: dict[str, str],
) -> WikiOntologyEdge:
    subject = by_id[assertion.subject_entity_id]
    object_label, object_path = _assertion_object(assertion, by_id, paths)
    qualifiers = [
        WikiOntologyQualifier(key, _display_value(value))
        for key, value in sorted(assertion.qualifiers.items())
    ]
    if assertion.attributed_to_id is not None:
        attributed = by_id[assertion.attributed_to_id]
        qualifiers.append(
            WikiOntologyQualifier(
                "attributed_to_id",
                _record_label(cast(WikiNamedRecord, attributed.record)),
                paths[assertion.attributed_to_id],
            )
        )
    return WikiOntologyEdge(
        assertion_id=assertion.id,
        subject_label=_record_label(cast(WikiNamedRecord, subject.record)),
        subject_path=paths[assertion.subject_entity_id],
        predicate=_assertion_relation(assertion),
        object_label=object_label,
        object_path=object_path,
        qualifiers=tuple(qualifiers),
    )


def _event_edge_sort_key(edge: WikiOntologyEdge) -> tuple[int, str, str]:
    predicate_order = {
        HybridEventStructuralPredicate.HAS_EVENT_TYPE.value: 0,
        HybridEventStructuralPredicate.HAS_ARGUMENT.value: 1,
        HybridEventStructuralPredicate.HAS_TIME.value: 2,
        HybridEventStructuralPredicate.HAS_PLACE.value: 3,
        HybridEventStructuralPredicate.HAS_POLARITY.value: 4,
        HybridEventStructuralPredicate.HAS_MODALITY.value: 5,
        HybridEventStructuralPredicate.ACCORDING_TO.value: 6,
    }
    qualifiers = {item.key: item.value for item in edge.qualifiers}
    return (
        predicate_order[edge.predicate],
        qualifiers.get("frame_role_id", ""),
        edge.assertion_id,
    )


def _semantic_argument_target_kind(
    assertion: Assertion | ProposedAssertion,
    by_id: dict[str, CandidateViewRecord],
) -> SemanticArgumentTargetKind:
    if assertion.object_entity_id is None:
        return SemanticArgumentTargetKind.SOURCE_SPAN
    if by_id[assertion.object_entity_id].record_type == "Event":
        return SemanticArgumentTargetKind.EVENT_SUBJECT
    return SemanticArgumentTargetKind.MENTION_CANDIDATE


def _display_value(value: object) -> str:
    return value if isinstance(value, str) else _canonical_json(value)


def _presentation_sort_key(presentation: WikiPresentation) -> tuple[int, str]:
    first_citation = min(presentation.citation_numbers, default=2**31)
    return first_citation, presentation.presentation_id


def _record_details(
    record: WikiIntelligenceRecord,
    by_id: dict[str, CandidateViewRecord],
    paths: dict[str, str],
) -> tuple[WikiDetail, ...]:
    if isinstance(record, Entity):
        return (WikiDetail("Kind", record.entity_kind.value),)
    if isinstance(record, Organization):
        return (WikiDetail("Type", record.organization_type or "Unspecified"),)
    if isinstance(record, Place):
        return ()
    if isinstance(record, Actor):
        details = [WikiDetail("Roles", ", ".join(record.role_names) or "Unspecified")]
        details.extend(
            WikiDetail(
                "Organization",
                _record_label(cast(WikiNamedRecord, by_id[item].record)),
                paths[item],
            )
            for item in record.organization_ids
        )
        return tuple(details)
    if isinstance(record, Event):
        details = [
            WikiDetail("Start", record.start_at.isoformat() if record.start_at else "Unspecified"),
            WikiDetail("End", record.end_at.isoformat() if record.end_at else "Unspecified"),
        ]
        for label, ids in (
            ("Place", (record.place_id,) if record.place_id else ()),
            ("Participant", record.participant_actor_ids),
            ("Participant", record.participant_organization_ids),
        ):
            details.extend(
                WikiDetail(
                    label,
                    _record_label(cast(WikiNamedRecord, by_id[item].record)),
                    paths[item],
                )
                for item in ids
            )
        return tuple(details)
    raise TypeError("Assertions do not have standalone Wiki pages.")


def _plan_wiki_audit_catalog(
    view: CandidateKnowledgeView,
    presentations: tuple[WikiPresentation, ...],
) -> WikiAuditCatalog:
    items_by_id = {item.record.id: item for item in view.records}
    evidence_key_by_number = {
        item.citation_number: item.reference_key for item in view.evidence_references
    }
    edge_by_assertion_id: dict[str, WikiOntologyEdge] = {}
    event_by_id: dict[str, WikiEventPresentation] = {}
    for presentation in presentations:
        if isinstance(presentation, WikiEventPresentation):
            event_by_id[presentation.event_id] = presentation
            edges = presentation.edges
        else:
            edges = (presentation.edge,)
        for edge in edges:
            edge_by_assertion_id[edge.assertion_id] = edge

    records: list[WikiAuditRecord] = [
        _authority_audit_record(
            "Source",
            view.source.id,
            canonical_record_json(view.source),
            view.ingestion_run.provenance_activity_id,
        ),
        _authority_audit_record(
            "Document",
            view.document.id,
            canonical_record_json(view.document),
            view.ingestion_run.provenance_activity_id,
        ),
    ]
    for item in view.records:
        record_id = item.record.id
        proposed_change_ids: set[str] = (
            {item.proposed_change_id} if item.proposed_change_id else set()
        )
        provenance_activity_ids = set(item.provenance_activity_ids)
        evidence_reference_keys = set(item.evidence_reference_keys)
        state: Literal["accepted", "pending"] = "pending" if item.is_pending else "accepted"
        edges = (edge_by_assertion_id[record_id],) if record_id in edge_by_assertion_id else ()
        event = event_by_id.get(record_id)
        if event is not None:
            state = event.state
            edges = event.edges
            proposed_change_ids.update(event.proposed_change_ids)
            for assertion_id in event.assertion_ids:
                assertion_item = items_by_id[assertion_id]
                if assertion_item.proposed_change_id is not None:
                    proposed_change_ids.add(assertion_item.proposed_change_id)
                provenance_activity_ids.update(assertion_item.provenance_activity_ids)
            evidence_reference_keys.update(
                evidence_key_by_number[number] for number in event.citation_numbers
            )
        record_payload = _json_object(item.record_payload_json)
        records.append(
            WikiAuditRecord(
                record_id=record_id,
                record_type=cast(WikiAuditRecordType, item.record_type),
                state=state,
                review_status=item.review_status.value,
                record_payload=record_payload,
                record_payload_sha256=_sha256_json(record_payload),
                proposed_change_ids=tuple(sorted(proposed_change_ids)),
                provenance_activity_ids=tuple(sorted(provenance_activity_ids)),
                evidence_reference_keys=tuple(sorted(evidence_reference_keys)),
                ontology_edges=edges,
            )
        )
    return WikiAuditCatalog(
        candidate_snapshot_digest=view.candidate_snapshot_digest,
        records=tuple(sorted(records, key=lambda item: item.record_id)),
    )


def _authority_audit_record(
    record_type: Literal["Source", "Document"],
    record_id: str,
    record_payload_json: str,
    provenance_activity_id: str | None,
) -> WikiAuditRecord:
    payload = _json_object(record_payload_json)
    return WikiAuditRecord(
        record_id=record_id,
        record_type=record_type,
        state="accepted",
        review_status=None,
        record_payload=payload,
        record_payload_sha256=_sha256_json(payload),
        proposed_change_ids=(),
        provenance_activity_ids=(
            (provenance_activity_id,) if provenance_activity_id is not None else ()
        ),
        evidence_reference_keys=(),
        ontology_edges=(),
    )


def _page(
    *,
    relative_path: str,
    page_kind: str,
    record_id: str | None,
    display_label: str,
    state: Literal["accepted", "pending"] | None,
    details: tuple[WikiDetail, ...],
    links: tuple[WikiLink, ...],
    presentations: tuple[WikiPresentation, ...],
    citations: tuple[int, ...],
    evidence_by_number: dict[int, WikiEvidenceReference],
) -> WikiPageInput:
    all_citations = tuple(
        sorted(
            {
                *citations,
                *(number for link in links for number in link.citation_numbers),
                *(
                    number
                    for presentation in presentations
                    for number in presentation.citation_numbers
                ),
            }
        )
    )
    payload = {
        "renderer_policy_id": CANDIDATE_WIKI_RENDERER_POLICY_ID,
        "relative_path": relative_path,
        "page_kind": page_kind,
        "record_id": record_id,
        "display_label": display_label,
        "state": state,
        "details": [item.__dict__ for item in details],
        "links": [item.__dict__ for item in links],
        "presentations": [_presentation_json(item) for item in presentations],
        "citations": list(all_citations),
        "evidence": [_evidence_identity(evidence_by_number[number]) for number in all_citations],
    }
    return WikiPageInput(
        relative_path=relative_path,
        page_kind=page_kind,
        record_id=record_id,
        display_label=display_label,
        state=state,
        details=details,
        links=links,
        presentations=presentations,
        citation_numbers=all_citations,
        input_fingerprint=_sha256_json(payload),
    )


def _presentation_json(presentation: WikiPresentation) -> dict[str, object]:
    common: dict[str, object] = {
        "presentation_id": presentation.presentation_id,
        "state": presentation.state,
        "citation_numbers": list(presentation.citation_numbers),
        "related_paths": list(presentation.related_paths),
    }
    if isinstance(presentation, WikiEventPresentation):
        return common | {
            "presentation_kind": "event",
            "event_id": presentation.event_id,
            "assertion_ids": list(presentation.assertion_ids),
            "proposed_change_ids": list(presentation.proposed_change_ids),
            "frame_id": presentation.frame_id,
            "complete": presentation.complete,
            "edges": [_ontology_edge_json(item) for item in presentation.edges],
            "issues": list(presentation.issues),
        }
    return common | {
        "presentation_kind": "assertion",
        "proposed_change_id": presentation.proposed_change_id,
        "edge": _ontology_edge_json(presentation.edge),
    }


def _ontology_edge_json(edge: WikiOntologyEdge) -> dict[str, object]:
    return {
        "assertion_id": edge.assertion_id,
        "subject_label": edge.subject_label,
        "subject_path": edge.subject_path,
        "predicate": edge.predicate,
        "object_label": edge.object_label,
        "object_path": edge.object_path,
        "qualifiers": [item.__dict__ for item in edge.qualifiers],
    }


def _wiki_audit_record_json(record: WikiAuditRecord) -> dict[str, object]:
    return {
        "record_id": record.record_id,
        "record_type": record.record_type,
        "state": record.state,
        "review_status": record.review_status,
        "record_payload": record.record_payload,
        "record_payload_sha256": record.record_payload_sha256,
        "proposed_change_ids": list(record.proposed_change_ids),
        "provenance_activity_ids": list(record.provenance_activity_ids),
        "evidence_reference_keys": list(record.evidence_reference_keys),
        "ontology_edges": [_ontology_edge_json(item) for item in record.ontology_edges],
    }


def _wiki_audit_edge_from_file(edge: _WikiAuditEdgeRecord) -> WikiOntologyEdge:
    return WikiOntologyEdge(
        assertion_id=edge.assertion_id,
        subject_label=edge.subject_label,
        subject_path=edge.subject_path,
        predicate=edge.predicate,
        object_label=edge.object_label,
        object_path=edge.object_path,
        qualifiers=tuple(
            WikiOntologyQualifier(
                key=item.key,
                value=item.value,
                value_path=item.value_path,
            )
            for item in edge.qualifiers
        ),
    )


def _slug(value: str) -> str:
    normalized = unicodedata.normalize("NFC", value).strip()
    slug = re.sub(r"[^\w.\-]+", "_", normalized, flags=re.UNICODE).strip("._-")
    slug = slug or "Record"
    if len(slug.encode("utf-8")) <= 120:
        return slug
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:8]
    while len(slug.encode("utf-8")) > 108:
        slug = slug[:-1]
    return f"{slug.rstrip('._-')}--{digest}"


def _page_order(page_kind: str) -> int:
    return {
        "home": 0,
        "document": 1,
        "entity": 2,
        "actor": 3,
        "organization": 4,
        "place": 5,
        "event": 6,
    }[page_kind]


def _numbered_evidence(item: WikiEvidenceReference, number: int) -> WikiEvidenceReference:
    return WikiEvidenceReference(
        citation_number=number,
        reference_key=item.reference_key,
        reference_kind=item.reference_kind,
        source_id=item.source_id,
        document_id=item.document_id,
        representation_id=item.representation_id,
        text_view_id=item.text_view_id,
        start_char=item.start_char,
        end_char=item.end_char,
        exact_text=item.exact_text,
        prefix_text=item.prefix_text,
        suffix_text=item.suffix_text,
        node_ids=item.node_ids,
        page_numbers=item.page_numbers,
        evidence_target_id=item.evidence_target_id,
        evidence_validation_attempt_id=item.evidence_validation_attempt_id,
        proposed_change_id=item.proposed_change_id,
    )


def _evidence_identity(item: WikiEvidenceReference) -> dict[str, object]:
    value = _evidence_json(item)
    value.pop("citation_number")
    return value


def _proposal_snapshot(proposal: ProposedChange) -> dict[str, object]:
    return {
        "proposed_change_id": proposal.id,
        "review_status": proposal.review_status.value,
        "proposed_json_sha256": _sha256_json(proposal.proposed_json),
        "original_proposed_json_sha256": (
            _sha256_json(proposal.original_proposed_json)
            if proposal.original_proposed_json is not None
            else None
        ),
        "accepted_json_sha256": (
            _sha256_json(proposal.accepted_json) if proposal.accepted_json is not None else None
        ),
    }


def _evidence_json(item: WikiEvidenceReference) -> dict[str, object]:
    return {
        "citation_number": item.citation_number,
        "reference_key": item.reference_key,
        "reference_kind": item.reference_kind,
        "source_id": item.source_id,
        "document_id": item.document_id,
        "representation_id": item.representation_id,
        "text_view_id": item.text_view_id,
        "start_char": item.start_char,
        "end_char": item.end_char,
        "exact_text": item.exact_text,
        "prefix_text": item.prefix_text,
        "suffix_text": item.suffix_text,
        "node_ids": list(item.node_ids),
        "page_numbers": list(item.page_numbers),
        "evidence_target_id": item.evidence_target_id,
        "evidence_validation_attempt_id": item.evidence_validation_attempt_id,
        "proposed_change_id": item.proposed_change_id,
    }


def _audit_evidence_json(item: WikiEvidenceReference) -> dict[str, object]:
    value = _evidence_json(item)
    value.pop("citation_number")
    return value


def _validate_change_set_digest(change_set: IngestionChangeSet) -> None:
    payload = {
        "ingestion_run_id": change_set.ingestion_run_id,
        "analysis_run_id": change_set.analysis_run_id,
        "representation_id": change_set.representation_id,
        "coverage_report_digest": change_set.coverage_report_digest,
        "proposed_change_ids": list(change_set.proposed_change_ids),
        "analysis_origin": change_set.analysis_origin.value,
    }
    digest = _sha256_json(payload)
    if change_set.change_set_digest != digest or change_set.id != f"ics_{digest[:HASH_ID_LENGTH]}":
        raise ValueError("IngestionChangeSet digest is invalid.")


def _manifest_json(manifest: WikiBuildManifest) -> dict[str, object]:
    return {
        "schema_version": manifest.schema_version,
        "build_id": manifest.build_id,
        "view_policy_id": manifest.view_policy_id,
        "renderer_policy_id": manifest.renderer_policy_id,
        "ingestion_run_id": manifest.ingestion_run_id,
        "ingestion_change_set_id": manifest.ingestion_change_set_id,
        "candidate_snapshot_digest": manifest.candidate_snapshot_digest,
        "files": [item.__dict__ for item in manifest.files],
        "counts": dict(manifest.counts),
    }


def _wiki_build_id(manifest: WikiBuildManifest) -> str:
    value = _manifest_json(manifest)
    value.pop("build_id")
    value.pop("files")
    return f"wkb_{_sha256_json(value)[:HASH_ID_LENGTH]}"


def candidate_wiki_build_id(
    *,
    view_policy_id: str,
    renderer_policy_id: str,
    ingestion_run_id: str,
    ingestion_change_set_id: str,
    candidate_snapshot_digest: str,
    counts: tuple[tuple[str, int], ...],
) -> str:
    manifest = WikiBuildManifest(
        schema_version="candidate_wiki_manifest_v2",
        build_id="pending",
        view_policy_id=view_policy_id,
        renderer_policy_id=renderer_policy_id,
        ingestion_run_id=ingestion_run_id,
        ingestion_change_set_id=ingestion_change_set_id,
        candidate_snapshot_digest=candidate_snapshot_digest,
        files=(),
        counts=counts,
    )
    return _wiki_build_id(manifest)


def _required_string(value: dict[str, object], key: str) -> str:
    item = value.get(key)
    if not isinstance(item, str) or not item:
        raise ValueError(f"Candidate Wiki manifest {key} must be a nonempty string.")
    return item


def _required_digest(value: dict[str, object], key: str) -> str:
    item = _required_string(value, key)
    if re.fullmatch(r"[a-f0-9]{64}", item) is None:
        raise ValueError(f"Candidate Wiki manifest {key} must be a SHA-256 digest.")
    return item


def _integer_value(value: object) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError("Candidate Wiki manifest counts must be nonnegative integers.")
    return value


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _json_object(value: str) -> dict[str, JsonValue]:
    parsed: object = json.loads(value)
    if not isinstance(parsed, dict):
        raise ValueError("Candidate Wiki record payload must be one JSON object.")
    return cast(dict[str, JsonValue], parsed)


def _sha256_json(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()
