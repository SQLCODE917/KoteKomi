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
    Actor,
    Assertion,
    AssertionEvidenceLink,
    Document,
    DocumentRepresentationBundle,
    Entity,
    Event,
    EvidenceTarget,
    EvidenceValidationAttempt,
    IngestionChangeSet,
    IngestionRun,
    IngestionRunStatus,
    Organization,
    Place,
    ProposedAssertion,
    ProposedChange,
    ReviewStatus,
    Source,
)
from pydantic import BaseModel, ConfigDict, model_validator

from kotekomi_application.evidence_targets import verify_evidence_target
from kotekomi_application.record_serialization import canonical_record_json

CANDIDATE_WIKI_VIEW_POLICY_ID = "candidate_wiki_view_v1"
CANDIDATE_WIKI_RENDERER_POLICY_ID = "deterministic_markdown_wiki_v1"
HASH_ID_LENGTH = 24

type WikiIntelligenceRecord = (
    Entity | Actor | Organization | Place | Event | Assertion | ProposedAssertion
)
type WikiNamedRecord = Entity | Actor | Organization | Place | Event
type WikiRecordType = Literal["Entity", "Actor", "Organization", "Place", "Event", "Assertion"]
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


@dataclass(frozen=True)
class CandidateIngestionSelection:
    matches: tuple[IngestionRun, ...]


@dataclass(frozen=True)
class CandidateViewRecord:
    record_type: WikiRecordType
    record: WikiIntelligenceRecord
    review_status: ReviewStatus
    proposed_change_id: str | None
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
class WikiStatement:
    subject_label: str
    subject_path: str
    relation_label: str
    object_label: str
    object_path: str | None
    state: Literal["accepted", "pending"]
    citation_numbers: tuple[int, ...]


@dataclass(frozen=True)
class WikiPageInput:
    relative_path: str
    page_kind: str
    display_label: str
    state: Literal["accepted", "pending"] | None
    details: tuple[WikiDetail, ...]
    links: tuple[WikiLink, ...]
    outgoing_statements: tuple[WikiStatement, ...]
    inbound_statements: tuple[WikiStatement, ...]
    citation_numbers: tuple[int, ...]
    input_fingerprint: str


@dataclass(frozen=True)
class WikiCitationRegistry:
    candidate_snapshot_digest: str
    citations: tuple[WikiEvidenceReference, ...]


@dataclass(frozen=True)
class CandidateWikiPlan:
    view_policy_id: str
    renderer_policy_id: str
    ingestion_run_id: str
    ingestion_change_set_id: str
    candidate_snapshot_digest: str
    pages: tuple[WikiPageInput, ...]
    citation_registry: WikiCitationRegistry
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


class CandidateWikiArchive(Protocol):
    def publish_candidate_wiki(
        self, rendered_wiki: RenderedCandidateWiki
    ) -> CandidateWikiPublishResult: ...


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
    by_id = {item.record.id: item for item in view.records}
    statements = tuple(
        _statement(item, by_id, paths, evidence_numbers)
        for item in view.records
        if item.record_type == "Assertion"
    )
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
            display_label="Candidate Wiki",
            state=None,
            details=(
                WikiDetail("Document", view.ingestion_run.display_filename),
                WikiDetail("Source", view.ingestion_run.normalized_source_url or "Unavailable"),
                WikiDetail("Candidate records", str(len(view.records))),
            ),
            links=all_links,
            outgoing=(),
            inbound=(),
            citations=(),
        )
    )
    document_path = f"documents/{_slug(view.ingestion_run.display_filename)}.md"
    pages.append(
        _page(
            relative_path=document_path,
            page_kind="document",
            display_label=view.ingestion_run.display_filename,
            state="accepted",
            details=(
                WikiDetail("Source URL", view.ingestion_run.normalized_source_url or "Unavailable"),
                WikiDetail("Content SHA-256", view.document.content_sha256),
            ),
            links=all_links,
            outgoing=statements,
            inbound=(),
            citations=tuple(item.citation_number for item in view.evidence_references),
        )
    )
    for item in named_records:
        record_id = item.record.id
        pages.append(
            _page(
                relative_path=paths[record_id],
                page_kind=item.record_type.casefold(),
                display_label=_record_label(cast(WikiNamedRecord, item.record)),
                state="pending" if item.is_pending else "accepted",
                details=_record_details(item.record, by_id, paths),
                links=(),
                outgoing=tuple(row for row in statements if row.subject_path == paths[record_id]),
                inbound=tuple(row for row in statements if row.object_path == paths[record_id]),
                citations=_record_citation_numbers(item, evidence_numbers),
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
    if manifest.schema_version != "candidate_wiki_manifest_v1":
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
        source_payload_json = _canonical_json(proposal.proposed_json)
        record = _parse_record(typed_record_type, payload, proposed=True)
    elif proposal.review_status in {ReviewStatus.APPROVED, ReviewStatus.EDITED}:
        if proposal.accepted_json is None:
            raise ValueError("Reviewed ProposedChange has no accepted record payload.")
        record = _parse_record(typed_record_type, proposal.accepted_json, proposed=False)
        persisted = _load_record(record.id, ledger)
        if persisted is None or persisted != record:
            raise ValueError("Reviewed ProposedChange accepted record is absent or changed.")
        source_payload_json = canonical_record_json(record)
    else:
        raise ValueError("Rejected ProposedChange cannot become a Candidate Wiki record.")
    evidence_keys = _proposal_evidence_keys(proposal, typed_record_type)
    return CandidateViewRecord(
        record_type=typed_record_type,
        record=record,
        review_status=proposal.review_status,
        proposed_change_id=proposal.id,
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
        reference_key=f"proposal:{proposal_id}",
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
        label=_record_label(cast(WikiNamedRecord, item.record)),
        relative_path=path,
        state="pending" if item.is_pending else "accepted",
        record_type=item.record_type,
        citation_numbers=_record_citation_numbers(item, numbers),
    )


def _record_citation_numbers(item: CandidateViewRecord, numbers: dict[str, int]) -> tuple[int, ...]:
    return tuple(numbers[key] for key in item.evidence_reference_keys)


def _statement(
    item: CandidateViewRecord,
    by_id: dict[str, CandidateViewRecord],
    paths: dict[str, str],
    evidence_numbers: dict[str, int],
) -> WikiStatement:
    assertion = cast(Assertion | ProposedAssertion, item.record)
    subject = by_id[assertion.subject_entity_id]
    subject_record = cast(WikiNamedRecord, subject.record)
    if assertion.object_entity_id is not None:
        object_record = by_id[assertion.object_entity_id]
        object_label = _record_label(cast(WikiNamedRecord, object_record.record))
        object_path = paths[assertion.object_entity_id]
    else:
        object_label = _canonical_json(assertion.object_value)
        object_path = None
    relation = assertion.predicate if isinstance(assertion, Assertion) else assertion.relation_label
    return WikiStatement(
        subject_label=_record_label(subject_record),
        subject_path=paths[assertion.subject_entity_id],
        relation_label=relation,
        object_label=object_label,
        object_path=object_path,
        state="pending" if item.is_pending else "accepted",
        citation_numbers=_record_citation_numbers(item, evidence_numbers),
    )


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


def _page(
    *,
    relative_path: str,
    page_kind: str,
    display_label: str,
    state: Literal["accepted", "pending"] | None,
    details: tuple[WikiDetail, ...],
    links: tuple[WikiLink, ...],
    outgoing: tuple[WikiStatement, ...],
    inbound: tuple[WikiStatement, ...],
    citations: tuple[int, ...],
) -> WikiPageInput:
    all_citations = tuple(
        sorted(
            {
                *citations,
                *(number for link in links for number in link.citation_numbers),
                *(number for statement in outgoing for number in statement.citation_numbers),
                *(number for statement in inbound for number in statement.citation_numbers),
            }
        )
    )
    payload = {
        "renderer_policy_id": CANDIDATE_WIKI_RENDERER_POLICY_ID,
        "relative_path": relative_path,
        "page_kind": page_kind,
        "display_label": display_label,
        "state": state,
        "details": [item.__dict__ for item in details],
        "links": [item.__dict__ for item in links],
        "outgoing": [item.__dict__ for item in outgoing],
        "inbound": [item.__dict__ for item in inbound],
        "citations": list(all_citations),
    }
    return WikiPageInput(
        relative_path=relative_path,
        page_kind=page_kind,
        display_label=display_label,
        state=state,
        details=details,
        links=links,
        outgoing_statements=outgoing,
        inbound_statements=inbound,
        citation_numbers=all_citations,
        input_fingerprint=_sha256_json(payload),
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
    return f"wkb_{_sha256_json(value)[:HASH_ID_LENGTH]}"


def candidate_wiki_build_id(
    *,
    view_policy_id: str,
    renderer_policy_id: str,
    ingestion_run_id: str,
    ingestion_change_set_id: str,
    candidate_snapshot_digest: str,
    files: tuple[WikiBuildFileEntry, ...],
    counts: tuple[tuple[str, int], ...],
) -> str:
    manifest = WikiBuildManifest(
        schema_version="candidate_wiki_manifest_v1",
        build_id="pending",
        view_policy_id=view_policy_id,
        renderer_policy_id=renderer_policy_id,
        ingestion_run_id=ingestion_run_id,
        ingestion_change_set_id=ingestion_change_set_id,
        candidate_snapshot_digest=candidate_snapshot_digest,
        files=files,
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


def _sha256_json(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()
