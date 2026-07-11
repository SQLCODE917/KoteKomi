"""SQLite implementation of the LedgerRepository Port."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from enum import StrEnum
from importlib.resources import files
from pathlib import Path
from typing import TypeVar

from kotekomi_application import (
    AcceptedCanonicalRecord,
    BundleCommitDisposition,
    BundleCommitOutcome,
    LedgerInitResult,
)
from kotekomi_domain import (
    Actor,
    ArgumentEdge,
    Assertion,
    AssertionEvidenceLink,
    Briefing,
    Document,
    DocumentEdge,
    DocumentNode,
    DocumentRepresentation,
    DocumentRepresentationBundle,
    DocumentRevisionRelation,
    Entity,
    Event,
    EvidenceReanchoringRelation,
    EvidenceSpan,
    Organization,
    Outcome,
    ParseQualityReport,
    Place,
    ProposedChange,
    ProvenanceActivity,
    RawBlob,
    Relationship,
    Source,
    SourceCapture,
    SourceRegion,
    TextView,
    canonical_evidence_target_digest,
)
from pydantic import BaseModel

DomainRecord = TypeVar("DomainRecord", bound=BaseModel)


class ImmutableCommitDisposition(StrEnum):
    CREATED = "created"
    REUSED = "reused"


@dataclass
class ImmutableRecordConflict(Exception):
    record_type: str
    record_id: str
    existing_digest: str
    incoming_digest: str


@dataclass
class NonDeterministicParserOutputConflict(Exception):
    representation_id: str
    existing_output_digest: str
    incoming_output_digest: str


IMMUTABLE_TABLES = frozenset(
    {
        "raw_blobs",
        "source_captures",
        "documents",
        "document_revision_relations",
        "document_representations",
        "text_views",
        "document_nodes",
        "document_edges",
        "source_regions",
        "parse_quality_reports",
        "assertion_evidence_links",
        "evidence_reanchoring_relations",
    }
)


@dataclass(frozen=True)
class RecordSpec[DomainRecord]:
    table_name: str
    model_type: type[DomainRecord]


ENTITY_SPEC = RecordSpec("entities", Entity)
ACTOR_SPEC = RecordSpec("actors", Actor)
ORGANIZATION_SPEC = RecordSpec("organizations", Organization)
PLACE_SPEC = RecordSpec("places", Place)
EVENT_SPEC = RecordSpec("events", Event)
SOURCE_SPEC = RecordSpec("sources", Source)
DOCUMENT_SPEC = RecordSpec("documents", Document)
DOCUMENT_REPRESENTATION_SPEC = RecordSpec("document_representations", DocumentRepresentation)
TEXT_VIEW_SPEC = RecordSpec("text_views", TextView)
DOCUMENT_NODE_SPEC = RecordSpec("document_nodes", DocumentNode)
DOCUMENT_EDGE_SPEC = RecordSpec("document_edges", DocumentEdge)
SOURCE_REGION_SPEC = RecordSpec("source_regions", SourceRegion)
PARSE_QUALITY_REPORT_SPEC = RecordSpec("parse_quality_reports", ParseQualityReport)
DOCUMENT_REVISION_RELATION_SPEC = RecordSpec(
    "document_revision_relations",
    DocumentRevisionRelation,
)
RAW_BLOB_SPEC = RecordSpec("raw_blobs", RawBlob)
SOURCE_CAPTURE_SPEC = RecordSpec("source_captures", SourceCapture)
EVIDENCE_SPAN_SPEC = RecordSpec("evidence_spans", EvidenceSpan)
ASSERTION_EVIDENCE_LINK_SPEC = RecordSpec("assertion_evidence_links", AssertionEvidenceLink)
EVIDENCE_REANCHORING_RELATION_SPEC = RecordSpec(
    "evidence_reanchoring_relations",
    EvidenceReanchoringRelation,
)
ASSERTION_SPEC = RecordSpec("assertions", Assertion)
RELATIONSHIP_SPEC = RecordSpec("relationships", Relationship)
OUTCOME_SPEC = RecordSpec("outcomes", Outcome)
ARGUMENT_EDGE_SPEC = RecordSpec("argument_edges", ArgumentEdge)
PROVENANCE_ACTIVITY_SPEC = RecordSpec("provenance_activities", ProvenanceActivity)
PROPOSED_CHANGE_SPEC = RecordSpec("proposed_changes", ProposedChange)
BRIEFING_SPEC = RecordSpec("briefings", Briefing)

ACCEPTED_CANONICAL_RECORD_SPECS = (
    ENTITY_SPEC,
    ACTOR_SPEC,
    ORGANIZATION_SPEC,
    PLACE_SPEC,
    EVENT_SPEC,
    SOURCE_SPEC,
    DOCUMENT_SPEC,
    EVIDENCE_SPAN_SPEC,
    ASSERTION_SPEC,
    RELATIONSHIP_SPEC,
    OUTCOME_SPEC,
    ARGUMENT_EDGE_SPEC,
)

REQUIRED_LEDGER_TABLES = (
    "ledger_migrations",
    "entities",
    "actors",
    "organizations",
    "places",
    "events",
    "sources",
    "documents",
    "document_representations",
    "text_views",
    "document_nodes",
    "document_edges",
    "source_regions",
    "parse_quality_reports",
    "document_revision_relations",
    "evidence_spans",
    "assertion_evidence_links",
    "evidence_reanchoring_relations",
    "assertions",
    "relationships",
    "outcomes",
    "argument_edges",
    "provenance_activities",
    "proposed_changes",
    "raw_blobs",
    "source_captures",
    "briefings",
)


def _connect(ledger_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(ledger_path)
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def _migration_files() -> tuple[tuple[str, str, str], ...]:
    migration_root = files("kotekomi_adapters.migrations")
    migrations: list[tuple[str, str, str]] = []
    for path in sorted(migration_root.iterdir(), key=lambda item: item.name):
        if not path.name.endswith(".sql"):
            continue
        version, _, remainder = path.name.partition("_")
        name = remainder.removesuffix(".sql")
        migrations.append((version, name, path.read_text()))
    return tuple(migrations)


class SQLiteLedgerInitializer:
    def __init__(self, ledger_path: Path) -> None:
        self.ledger_path = ledger_path

    def initialize(self) -> LedgerInitResult:
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        applied_migrations: list[str] = []
        connection = _connect(self.ledger_path)
        try:
            connection.execute("BEGIN")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS ledger_migrations (
                  version TEXT PRIMARY KEY,
                  name TEXT NOT NULL,
                  applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            applied_versions = {
                row[0] for row in connection.execute("SELECT version FROM ledger_migrations")
            }
            for version, name, sql in _migration_files():
                if version in applied_versions:
                    continue
                connection.executescript(sql)
                connection.execute(
                    "INSERT INTO ledger_migrations(version, name) VALUES (?, ?)",
                    (version, name),
                )
                applied_migrations.append(version)
            self._verify_required_tables(connection)
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
        return LedgerInitResult(
            ledger_path=self.ledger_path,
            applied_migrations=tuple(applied_migrations),
        )

    def _verify_required_tables(self, connection: sqlite3.Connection) -> None:
        existing_tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        missing_tables = sorted(set(REQUIRED_LEDGER_TABLES) - existing_tables)
        if missing_tables:
            raise RuntimeError(f"Ledger is missing required tables: {', '.join(missing_tables)}")


@contextmanager
def sqlite_ledger_transaction(ledger_path: Path) -> Generator[SQLiteLedgerRepository]:
    connection = _connect(ledger_path)
    try:
        connection.execute("BEGIN")
        yield SQLiteLedgerRepository(connection)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


class SQLiteLedgerRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def _save(self, spec: RecordSpec[DomainRecord], record: DomainRecord) -> None:
        if spec.table_name in IMMUTABLE_TABLES:
            self._insert_immutable(spec, record)
            return
        self._upsert_mutable(spec, record)

    def _upsert_mutable(self, spec: RecordSpec[DomainRecord], record: DomainRecord) -> None:
        payload = record.model_dump(mode="json")
        self._connection.execute(
            f"""
            INSERT INTO {spec.table_name} (
              id,
              created_at,
              updated_at,
              status,
              review_status,
              payload_json
            )
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
              created_at = excluded.created_at,
              updated_at = excluded.updated_at,
              status = excluded.status,
              review_status = excluded.review_status,
              payload_json = excluded.payload_json
            """,
            (
                str(payload["id"]),
                _optional_text(payload.get("created_at") or payload.get("occurred_at")),
                _optional_text(payload.get("updated_at") or payload.get("generated_at")),
                _optional_text(payload.get("status")),
                _optional_text(payload.get("review_status")),
                canonical_record_json(record),
            ),
        )

    def _insert_immutable(
        self, spec: RecordSpec[DomainRecord], record: DomainRecord
    ) -> ImmutableCommitDisposition:
        payload = record.model_dump(mode="json")
        incoming_json = canonical_record_json(record)
        cursor = self._connection.execute(
            f"""
            INSERT INTO {spec.table_name} (
              id, created_at, updated_at, status, review_status, payload_json
            )
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO NOTHING
            """,
            (
                str(payload["id"]),
                _optional_text(payload.get("created_at") or payload.get("occurred_at")),
                _optional_text(payload.get("updated_at") or payload.get("generated_at")),
                _optional_text(payload.get("status")),
                _optional_text(payload.get("review_status")),
                incoming_json,
            ),
        )
        if cursor.rowcount == 1:
            return ImmutableCommitDisposition.CREATED
        row = self._connection.execute(
            f"SELECT payload_json FROM {spec.table_name} WHERE id = ?", (str(payload["id"]),)
        ).fetchone()
        if row is not None and canonical_json_text(str(row[0])) == incoming_json:
            return ImmutableCommitDisposition.REUSED
        existing_digest = hashlib.sha256(str(row[0]).encode()).hexdigest() if row else "missing"
        incoming_digest = hashlib.sha256(incoming_json.encode()).hexdigest()
        raise ImmutableRecordConflict(
            record_type=spec.model_type.__name__,
            record_id=str(payload["id"]),
            existing_digest=existing_digest,
            incoming_digest=incoming_digest,
        )

    def _get(self, spec: RecordSpec[DomainRecord], record_id: str) -> DomainRecord | None:
        row = self._connection.execute(
            f"SELECT payload_json FROM {spec.table_name} WHERE id = ?",
            (record_id,),
        ).fetchone()
        if row is None:
            return None
        return spec.model_type.model_validate_json(str(row[0]))

    def _list(self, spec: RecordSpec[DomainRecord]) -> tuple[DomainRecord, ...]:
        rows = self._connection.execute(
            f"SELECT payload_json FROM {spec.table_name} ORDER BY id"
        ).fetchall()
        return tuple(spec.model_type.model_validate_json(str(row[0])) for row in rows)

    def list_accepted_canonical_records(self) -> tuple[AcceptedCanonicalRecord, ...]:
        records: list[AcceptedCanonicalRecord] = []
        for spec in ACCEPTED_CANONICAL_RECORD_SPECS:
            records.extend(self._list(spec))
        return tuple(sorted(records, key=lambda record: record.id))

    def save_entity(self, record: Entity) -> None:
        self._save(ENTITY_SPEC, record)

    def get_entity(self, record_id: str) -> Entity | None:
        return self._get(ENTITY_SPEC, record_id)

    def list_entities(self) -> tuple[Entity, ...]:
        return self._list(ENTITY_SPEC)

    def save_actor(self, record: Actor) -> None:
        self._save(ACTOR_SPEC, record)

    def get_actor(self, record_id: str) -> Actor | None:
        return self._get(ACTOR_SPEC, record_id)

    def list_actors(self) -> tuple[Actor, ...]:
        return self._list(ACTOR_SPEC)

    def save_organization(self, record: Organization) -> None:
        self._save(ORGANIZATION_SPEC, record)

    def get_organization(self, record_id: str) -> Organization | None:
        return self._get(ORGANIZATION_SPEC, record_id)

    def list_organizations(self) -> tuple[Organization, ...]:
        return self._list(ORGANIZATION_SPEC)

    def save_place(self, record: Place) -> None:
        self._save(PLACE_SPEC, record)

    def get_place(self, record_id: str) -> Place | None:
        return self._get(PLACE_SPEC, record_id)

    def list_places(self) -> tuple[Place, ...]:
        return self._list(PLACE_SPEC)

    def save_event(self, record: Event) -> None:
        self._save(EVENT_SPEC, record)

    def get_event(self, record_id: str) -> Event | None:
        return self._get(EVENT_SPEC, record_id)

    def list_events(self) -> tuple[Event, ...]:
        return self._list(EVENT_SPEC)

    def save_source(self, record: Source) -> None:
        self._save(SOURCE_SPEC, record)

    def get_source(self, record_id: str) -> Source | None:
        return self._get(SOURCE_SPEC, record_id)

    def list_sources(self) -> tuple[Source, ...]:
        return self._list(SOURCE_SPEC)

    def save_document(self, record: Document) -> None:
        self._save(DOCUMENT_SPEC, record)

    def get_document(self, record_id: str) -> Document | None:
        return self._get(DOCUMENT_SPEC, record_id)

    def list_documents(self) -> tuple[Document, ...]:
        return self._list(DOCUMENT_SPEC)

    def save_document_representation(self, record: DocumentRepresentation) -> None:
        self._save(DOCUMENT_REPRESENTATION_SPEC, record)

    def get_document_representation(self, record_id: str) -> DocumentRepresentation | None:
        return self._get(DOCUMENT_REPRESENTATION_SPEC, record_id)

    def list_document_representations(self) -> tuple[DocumentRepresentation, ...]:
        return self._list(DOCUMENT_REPRESENTATION_SPEC)

    def get_document_representation_bundle(
        self, record_id: str
    ) -> DocumentRepresentationBundle | None:
        representation = self.get_document_representation(record_id)
        if representation is None:
            return None
        text_views = tuple(
            view for view in self.list_text_views() if view.representation_id == representation.id
        )
        nodes = tuple(
            node
            for node in self.list_document_nodes()
            if node.representation_id == representation.id
        )
        edges = tuple(
            edge
            for edge in self.list_document_edges()
            if edge.representation_id == representation.id
        )
        source_regions = tuple(
            source_region
            for source_region in self.list_source_regions()
            if source_region.representation_id == representation.id
        )
        quality_reports = tuple(
            report
            for report in self.list_parse_quality_reports()
            if report.representation_id == representation.id
        )
        if len(quality_reports) != 1:
            raise RuntimeError("Document representation must have exactly one ParseQualityReport.")
        return DocumentRepresentationBundle(
            representation=representation,
            text_views=text_views,
            nodes=nodes,
            edges=edges,
            source_regions=source_regions,
            quality_report=quality_reports[0],
        )

    def commit_document_representation_bundle(
        self, bundle: DocumentRepresentationBundle
    ) -> BundleCommitOutcome:
        validated_bundle = DocumentRepresentationBundle.model_validate(bundle.model_dump())
        self._connection.execute("SAVEPOINT document_representation_bundle_commit")
        try:
            outcome = self._commit_validated_document_representation_bundle(validated_bundle)
        except Exception:
            self._connection.execute("ROLLBACK TO SAVEPOINT document_representation_bundle_commit")
            self._connection.execute("RELEASE SAVEPOINT document_representation_bundle_commit")
            raise
        self._connection.execute("RELEASE SAVEPOINT document_representation_bundle_commit")
        return outcome

    def _commit_validated_document_representation_bundle(
        self, bundle: DocumentRepresentationBundle
    ) -> BundleCommitOutcome:
        existing_representation = self.get_document_representation(bundle.representation.id)
        if existing_representation is not None:
            try:
                existing_bundle = self.get_document_representation_bundle(bundle.representation.id)
            except RuntimeError as exc:
                raise ImmutableRecordConflict(
                    "DocumentRepresentationBundle",
                    bundle.representation.id,
                    "partial",
                    _bundle_digest(bundle),
                ) from exc
            if existing_bundle is None:
                raise RuntimeError(
                    "Existing DocumentRepresentation disappeared during bundle commit."
                )
            if _same_representation_bundle(existing_bundle, bundle):
                return BundleCommitOutcome(
                    BundleCommitDisposition.REUSED, bundle.representation.id
                )
            if (
                existing_bundle.representation.canonical_output_digest
                != bundle.representation.canonical_output_digest
            ):
                raise NonDeterministicParserOutputConflict(
                    bundle.representation.id,
                    existing_bundle.representation.canonical_output_digest,
                    bundle.representation.canonical_output_digest,
                )
            raise ImmutableRecordConflict(
                "DocumentRepresentationBundle",
                bundle.representation.id,
                _bundle_digest(existing_bundle),
                _bundle_digest(bundle),
            )
        if self._representation_children_exist(bundle.representation.id):
            raise ImmutableRecordConflict(
                "DocumentRepresentationBundle",
                bundle.representation.id,
                "partial",
                _bundle_digest(bundle),
            )
        self.save_document_representation(bundle.representation)
        for view in bundle.text_views:
            self.save_text_view(view)
        for node in bundle.nodes:
            self.save_document_node(node)
        for region in bundle.source_regions:
            self.save_source_region(region)
        for edge in bundle.edges:
            self.save_document_edge(edge)
        self.save_parse_quality_report(bundle.quality_report)
        return BundleCommitOutcome(BundleCommitDisposition.CREATED, bundle.representation.id)

    def _representation_children_exist(self, representation_id: str) -> bool:
        return any(
            record.representation_id == representation_id
            for records in (
                self.list_text_views(),
                self.list_document_nodes(),
                self.list_document_edges(),
                self.list_source_regions(),
                self.list_parse_quality_reports(),
            )
            for record in records
        )

    def save_text_view(self, record: TextView) -> None:
        self._save(TEXT_VIEW_SPEC, record)

    def get_text_view(self, record_id: str) -> TextView | None:
        return self._get(TEXT_VIEW_SPEC, record_id)

    def list_text_views(self) -> tuple[TextView, ...]:
        return self._list(TEXT_VIEW_SPEC)

    def save_document_node(self, record: DocumentNode) -> None:
        self._save(DOCUMENT_NODE_SPEC, record)

    def get_document_node(self, record_id: str) -> DocumentNode | None:
        return self._get(DOCUMENT_NODE_SPEC, record_id)

    def list_document_nodes(self) -> tuple[DocumentNode, ...]:
        return self._list(DOCUMENT_NODE_SPEC)

    def save_document_edge(self, record: DocumentEdge) -> None:
        self._save(DOCUMENT_EDGE_SPEC, record)

    def get_document_edge(self, record_id: str) -> DocumentEdge | None:
        return self._get(DOCUMENT_EDGE_SPEC, record_id)

    def list_document_edges(self) -> tuple[DocumentEdge, ...]:
        return self._list(DOCUMENT_EDGE_SPEC)

    def save_source_region(self, record: SourceRegion) -> None:
        self._save(SOURCE_REGION_SPEC, record)

    def get_source_region(self, record_id: str) -> SourceRegion | None:
        return self._get(SOURCE_REGION_SPEC, record_id)

    def list_source_regions(self) -> tuple[SourceRegion, ...]:
        return self._list(SOURCE_REGION_SPEC)

    def save_parse_quality_report(self, record: ParseQualityReport) -> None:
        self._save(PARSE_QUALITY_REPORT_SPEC, record)

    def get_parse_quality_report(self, record_id: str) -> ParseQualityReport | None:
        return self._get(PARSE_QUALITY_REPORT_SPEC, record_id)

    def list_parse_quality_reports(self) -> tuple[ParseQualityReport, ...]:
        return self._list(PARSE_QUALITY_REPORT_SPEC)

    def save_raw_blob(self, record: RawBlob) -> None:
        self._save(RAW_BLOB_SPEC, record)

    def get_raw_blob(self, record_id: str) -> RawBlob | None:
        return self._get(RAW_BLOB_SPEC, record_id)

    def list_raw_blobs(self) -> tuple[RawBlob, ...]:
        return self._list(RAW_BLOB_SPEC)

    def save_source_capture(self, record: SourceCapture) -> None:
        self._save(SOURCE_CAPTURE_SPEC, record)

    def get_source_capture(self, record_id: str) -> SourceCapture | None:
        return self._get(SOURCE_CAPTURE_SPEC, record_id)

    def list_source_captures(self) -> tuple[SourceCapture, ...]:
        return self._list(SOURCE_CAPTURE_SPEC)

    def save_document_revision_relation(self, record: DocumentRevisionRelation) -> None:
        self._save(DOCUMENT_REVISION_RELATION_SPEC, record)

    def get_document_revision_relation(self, record_id: str) -> DocumentRevisionRelation | None:
        return self._get(DOCUMENT_REVISION_RELATION_SPEC, record_id)

    def list_document_revision_relations(self) -> tuple[DocumentRevisionRelation, ...]:
        return self._list(DOCUMENT_REVISION_RELATION_SPEC)

    def save_evidence_span(self, record: EvidenceSpan) -> None:
        existing = self.get_evidence_span(record.id)
        if existing is not None and canonical_evidence_target_digest(
            existing
        ) != canonical_evidence_target_digest(record):
            raise ImmutableRecordConflict(
                "EvidenceSpan",
                record.id,
                hashlib.sha256(canonical_evidence_target_digest(existing).encode()).hexdigest(),
                hashlib.sha256(canonical_evidence_target_digest(record).encode()).hexdigest(),
            )
        self._upsert_mutable(EVIDENCE_SPAN_SPEC, record)

    def get_evidence_span(self, record_id: str) -> EvidenceSpan | None:
        return self._get(EVIDENCE_SPAN_SPEC, record_id)

    def list_evidence_spans(self) -> tuple[EvidenceSpan, ...]:
        return self._list(EVIDENCE_SPAN_SPEC)

    def save_assertion_evidence_link(self, record: AssertionEvidenceLink) -> None:
        self._save(ASSERTION_EVIDENCE_LINK_SPEC, record)

    def get_assertion_evidence_link(self, record_id: str) -> AssertionEvidenceLink | None:
        return self._get(ASSERTION_EVIDENCE_LINK_SPEC, record_id)

    def list_assertion_evidence_links(self) -> tuple[AssertionEvidenceLink, ...]:
        return self._list(ASSERTION_EVIDENCE_LINK_SPEC)

    def save_evidence_reanchoring_relation(self, record: EvidenceReanchoringRelation) -> None:
        self._save(EVIDENCE_REANCHORING_RELATION_SPEC, record)

    def get_evidence_reanchoring_relation(
        self, record_id: str
    ) -> EvidenceReanchoringRelation | None:
        return self._get(EVIDENCE_REANCHORING_RELATION_SPEC, record_id)

    def list_evidence_reanchoring_relations(
        self,
    ) -> tuple[EvidenceReanchoringRelation, ...]:
        return self._list(EVIDENCE_REANCHORING_RELATION_SPEC)

    def save_assertion(self, record: Assertion) -> None:
        self._save(ASSERTION_SPEC, record)

    def get_assertion(self, record_id: str) -> Assertion | None:
        return self._get(ASSERTION_SPEC, record_id)

    def list_assertions(self) -> tuple[Assertion, ...]:
        return self._list(ASSERTION_SPEC)

    def save_relationship(self, record: Relationship) -> None:
        self._save(RELATIONSHIP_SPEC, record)

    def get_relationship(self, record_id: str) -> Relationship | None:
        return self._get(RELATIONSHIP_SPEC, record_id)

    def list_relationships(self) -> tuple[Relationship, ...]:
        return self._list(RELATIONSHIP_SPEC)

    def save_outcome(self, record: Outcome) -> None:
        self._save(OUTCOME_SPEC, record)

    def get_outcome(self, record_id: str) -> Outcome | None:
        return self._get(OUTCOME_SPEC, record_id)

    def list_outcomes(self) -> tuple[Outcome, ...]:
        return self._list(OUTCOME_SPEC)

    def save_argument_edge(self, record: ArgumentEdge) -> None:
        self._save(ARGUMENT_EDGE_SPEC, record)

    def get_argument_edge(self, record_id: str) -> ArgumentEdge | None:
        return self._get(ARGUMENT_EDGE_SPEC, record_id)

    def list_argument_edges(self) -> tuple[ArgumentEdge, ...]:
        return self._list(ARGUMENT_EDGE_SPEC)

    def save_provenance_activity(self, record: ProvenanceActivity) -> None:
        self._save(PROVENANCE_ACTIVITY_SPEC, record)

    def get_provenance_activity(self, record_id: str) -> ProvenanceActivity | None:
        return self._get(PROVENANCE_ACTIVITY_SPEC, record_id)

    def list_provenance_activities(self) -> tuple[ProvenanceActivity, ...]:
        return self._list(PROVENANCE_ACTIVITY_SPEC)

    def save_proposed_change(self, record: ProposedChange) -> None:
        self._save(PROPOSED_CHANGE_SPEC, record)

    def get_proposed_change(self, record_id: str) -> ProposedChange | None:
        return self._get(PROPOSED_CHANGE_SPEC, record_id)

    def list_proposed_changes(self) -> tuple[ProposedChange, ...]:
        return self._list(PROPOSED_CHANGE_SPEC)

    def save_briefing(self, record: Briefing) -> None:
        self._save(BRIEFING_SPEC, record)

    def get_briefing(self, record_id: str) -> Briefing | None:
        return self._get(BRIEFING_SPEC, record_id)

    def list_briefings(self) -> tuple[Briefing, ...]:
        return self._list(BRIEFING_SPEC)


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


def canonical_record_json(record: BaseModel) -> str:
    return json.dumps(
        record.model_dump(mode="json"), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )


def _same_representation_bundle(
    existing: DocumentRepresentationBundle,
    incoming: DocumentRepresentationBundle,
) -> bool:
    return (
        existing.representation.canonical_output_digest
        == incoming.representation.canonical_output_digest
    )


def _bundle_digest(bundle: DocumentRepresentationBundle) -> str:
    return hashlib.sha256(canonical_record_json(bundle).encode()).hexdigest()


def canonical_json_text(payload_json: str) -> str:
    return json.dumps(
        json.loads(payload_json), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
