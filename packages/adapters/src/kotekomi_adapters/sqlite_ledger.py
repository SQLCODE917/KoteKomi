"""SQLite implementation of the LedgerRepository Port."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from typing import TypeVar

from kotekomi_application import (
    AcceptedCanonicalRecord,
    BundleCommitDisposition,
    BundleCommitOutcome,
    LedgerInitResult,
    ProcessingTaskDisposition,
)
from kotekomi_application.record_serialization import canonical_record_json
from kotekomi_domain import (
    Actor,
    ArgumentEdge,
    Assertion,
    AssertionEvidenceLink,
    Briefing,
    CaptureDocumentResolution,
    Document,
    DocumentEdge,
    DocumentNode,
    DocumentRepresentation,
    DocumentRepresentationBundle,
    DocumentRevisionRelation,
    Entity,
    Event,
    EvidenceReanchoringRelation,
    EvidenceTarget,
    EvidenceValidationAttempt,
    Organization,
    Outcome,
    ParseQualityReport,
    Place,
    ProcessingAttempt,
    ProcessingAttemptOutcome,
    ProcessingTaskFingerprint,
    ProposedChange,
    ProvenanceActivity,
    RawBlob,
    Relationship,
    Source,
    SourceCapture,
    SourceRegion,
    TextView,
)
from pydantic import BaseModel

DomainRecord = TypeVar("DomainRecord", bound=BaseModel)


# Immutable generic records and processing-task fingerprints share the same
# application-level created/reused contract.  Keeping the alias preserves the
# repository's explicit name without giving SQLite a competing identity API.
ImmutableCommitDisposition = ProcessingTaskDisposition


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
        "capture_document_resolutions",
        "documents",
        "document_revision_relations",
        "document_representations",
        "text_views",
        "document_nodes",
        "document_edges",
        "source_regions",
        "parse_quality_reports",
        "provenance_activities",
        "evidence_targets",
        "evidence_validation_attempts",
        "processing_task_fingerprints",
        "processing_attempts",
        "processing_attempt_outcomes",
        "assertion_evidence_links",
        "evidence_reanchoring_relations",
    }
)

RELATIONAL_OWNERSHIP_COLUMNS: dict[str, tuple[tuple[str, str], ...]] = {
    "source_captures": (("source_id", "source_id"), ("blob_id", "blob_id")),
    "capture_document_resolutions": (
        ("capture_id", "capture_id"),
        ("document_id", "document_id"),
    ),
    "documents": (("source_id", "source_id"), ("provider_version", "provider_version")),
    "document_revision_relations": (
        ("earlier_document_id", "earlier_document_id"),
        ("later_document_id", "later_document_id"),
    ),
    "document_representations": (("document_id", "document_id"),),
    "text_views": (("representation_id", "representation_id"),),
    "document_nodes": (
        ("representation_id", "representation_id"),
        ("parent_node_id", "parent_node_id"),
    ),
    "document_edges": (("representation_id", "representation_id"),),
    "source_regions": (("representation_id", "representation_id"),),
    "parse_quality_reports": (("representation_id", "representation_id"),),
}


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
CAPTURE_DOCUMENT_RESOLUTION_SPEC = RecordSpec(
    "capture_document_resolutions", CaptureDocumentResolution
)
EVIDENCE_TARGET_SPEC = RecordSpec("evidence_targets", EvidenceTarget)
EVIDENCE_VALIDATION_ATTEMPT_SPEC = RecordSpec(
    "evidence_validation_attempts", EvidenceValidationAttempt
)
PROCESSING_TASK_FINGERPRINT_SPEC = RecordSpec(
    "processing_task_fingerprints", ProcessingTaskFingerprint
)
PROCESSING_ATTEMPT_SPEC = RecordSpec("processing_attempts", ProcessingAttempt)
PROCESSING_ATTEMPT_OUTCOME_SPEC = RecordSpec(
    "processing_attempt_outcomes", ProcessingAttemptOutcome
)
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
    EVIDENCE_TARGET_SPEC,
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
    "evidence_targets",
    "evidence_validation_attempts",
    "processing_task_fingerprints",
    "processing_attempts",
    "processing_attempt_outcomes",
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
    "capture_document_resolutions",
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
        ownership_columns = RELATIONAL_OWNERSHIP_COLUMNS.get(spec.table_name, ())
        column_names = (
            "id",
            "created_at",
            "updated_at",
            "status",
            "review_status",
            *(column_name for column_name, _ in ownership_columns),
            "payload_json",
        )
        values = (
            str(payload["id"]),
            _optional_text(payload.get("created_at") or payload.get("occurred_at")),
            _optional_text(payload.get("updated_at") or payload.get("generated_at")),
            _optional_text(payload.get("status")),
            _optional_text(payload.get("review_status")),
            *(_optional_text(payload.get(field_name)) for _, field_name in ownership_columns),
            incoming_json,
        )
        columns_sql = ", ".join(column_names)
        placeholders = ", ".join("?" for _ in column_names)
        cursor = self._connection.execute(
            f"INSERT INTO {spec.table_name} ({columns_sql}) VALUES ({placeholders}) "
            "ON CONFLICT(id) DO NOTHING",
            values,
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

    def _list_for_owner(
        self, spec: RecordSpec[DomainRecord], owner_column: str, owner_id: str
    ) -> tuple[DomainRecord, ...]:
        rows = self._connection.execute(
            f"SELECT payload_json FROM {spec.table_name} WHERE {owner_column} = ? ORDER BY id",
            (owner_id,),
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

    def list_documents_for_source(self, source_id: str) -> tuple[Document, ...]:
        return self._list_for_owner(DOCUMENT_SPEC, "source_id", source_id)

    def find_document_by_provider_version(
        self, source_id: str, provider_version: str
    ) -> Document | None:
        row = self._connection.execute(
            "SELECT payload_json FROM documents WHERE source_id = ? AND provider_version = ?",
            (source_id, provider_version),
        ).fetchone()
        return Document.model_validate_json(str(row[0])) if row is not None else None

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
        text_views = self.list_text_views_for_representation(representation.id)
        nodes = self.list_document_nodes_for_representation(representation.id)
        edges = self.list_document_edges_for_representation(representation.id)
        source_regions = self.list_source_regions_for_representation(representation.id)
        quality_reports = self.list_parse_quality_reports_for_representation(representation.id)
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

    def commit_document_representation_processing(
        self,
        *,
        bundle: DocumentRepresentationBundle,
        created_provenance_activity: ProvenanceActivity,
        created_outcome: ProcessingAttemptOutcome,
        reused_outcome: ProcessingAttemptOutcome,
    ) -> BundleCommitOutcome:
        """Commit output, production provenance, and exactly one outcome together."""
        self._connection.execute("SAVEPOINT document_representation_processing")
        try:
            outcome = self.commit_document_representation_bundle(bundle)
            if outcome.disposition is BundleCommitDisposition.CREATED:
                self.save_provenance_activity(created_provenance_activity)
                self.append_processing_attempt_outcome(created_outcome)
            else:
                self.append_processing_attempt_outcome(reused_outcome)
        except Exception:
            self._connection.execute("ROLLBACK TO SAVEPOINT document_representation_processing")
            self._connection.execute("RELEASE SAVEPOINT document_representation_processing")
            raise
        self._connection.execute("RELEASE SAVEPOINT document_representation_processing")
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
                return BundleCommitOutcome(BundleCommitDisposition.REUSED, bundle.representation.id)
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
            (
                self.list_text_views_for_representation(representation_id),
                self.list_document_nodes_for_representation(representation_id),
                self.list_document_edges_for_representation(representation_id),
                self.list_source_regions_for_representation(representation_id),
                self.list_parse_quality_reports_for_representation(representation_id),
            )
        )

    def save_text_view(self, record: TextView) -> None:
        self._save(TEXT_VIEW_SPEC, record)

    def get_text_view(self, record_id: str) -> TextView | None:
        return self._get(TEXT_VIEW_SPEC, record_id)

    def list_text_views(self) -> tuple[TextView, ...]:
        return self._list(TEXT_VIEW_SPEC)

    def list_text_views_for_representation(self, representation_id: str) -> tuple[TextView, ...]:
        return self._list_for_owner(TEXT_VIEW_SPEC, "representation_id", representation_id)

    def save_document_node(self, record: DocumentNode) -> None:
        self._save(DOCUMENT_NODE_SPEC, record)

    def get_document_node(self, record_id: str) -> DocumentNode | None:
        return self._get(DOCUMENT_NODE_SPEC, record_id)

    def list_document_nodes(self) -> tuple[DocumentNode, ...]:
        return self._list(DOCUMENT_NODE_SPEC)

    def list_document_nodes_for_representation(
        self, representation_id: str
    ) -> tuple[DocumentNode, ...]:
        return self._list_for_owner(DOCUMENT_NODE_SPEC, "representation_id", representation_id)

    def save_document_edge(self, record: DocumentEdge) -> None:
        self._save(DOCUMENT_EDGE_SPEC, record)

    def get_document_edge(self, record_id: str) -> DocumentEdge | None:
        return self._get(DOCUMENT_EDGE_SPEC, record_id)

    def list_document_edges(self) -> tuple[DocumentEdge, ...]:
        return self._list(DOCUMENT_EDGE_SPEC)

    def list_document_edges_for_representation(
        self, representation_id: str
    ) -> tuple[DocumentEdge, ...]:
        return self._list_for_owner(DOCUMENT_EDGE_SPEC, "representation_id", representation_id)

    def save_source_region(self, record: SourceRegion) -> None:
        self._save(SOURCE_REGION_SPEC, record)

    def get_source_region(self, record_id: str) -> SourceRegion | None:
        return self._get(SOURCE_REGION_SPEC, record_id)

    def list_source_regions(self) -> tuple[SourceRegion, ...]:
        return self._list(SOURCE_REGION_SPEC)

    def list_source_regions_for_representation(
        self, representation_id: str
    ) -> tuple[SourceRegion, ...]:
        return self._list_for_owner(SOURCE_REGION_SPEC, "representation_id", representation_id)

    def save_parse_quality_report(self, record: ParseQualityReport) -> None:
        self._save(PARSE_QUALITY_REPORT_SPEC, record)

    def get_parse_quality_report(self, record_id: str) -> ParseQualityReport | None:
        return self._get(PARSE_QUALITY_REPORT_SPEC, record_id)

    def list_parse_quality_reports(self) -> tuple[ParseQualityReport, ...]:
        return self._list(PARSE_QUALITY_REPORT_SPEC)

    def list_parse_quality_reports_for_representation(
        self, representation_id: str
    ) -> tuple[ParseQualityReport, ...]:
        return self._list_for_owner(
            PARSE_QUALITY_REPORT_SPEC, "representation_id", representation_id
        )

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

    def save_capture_document_resolution(self, record: CaptureDocumentResolution) -> None:
        self._save(CAPTURE_DOCUMENT_RESOLUTION_SPEC, record)

    def get_capture_document_resolution(self, record_id: str) -> CaptureDocumentResolution | None:
        return self._get(CAPTURE_DOCUMENT_RESOLUTION_SPEC, record_id)

    def list_capture_document_resolutions(self) -> tuple[CaptureDocumentResolution, ...]:
        return self._list(CAPTURE_DOCUMENT_RESOLUTION_SPEC)

    def save_document_revision_relation(self, record: DocumentRevisionRelation) -> None:
        self._save(DOCUMENT_REVISION_RELATION_SPEC, record)

    def get_document_revision_relation(self, record_id: str) -> DocumentRevisionRelation | None:
        return self._get(DOCUMENT_REVISION_RELATION_SPEC, record_id)

    def list_document_revision_relations(self) -> tuple[DocumentRevisionRelation, ...]:
        return self._list(DOCUMENT_REVISION_RELATION_SPEC)

    def list_document_revision_relations_from(
        self, document_id: str
    ) -> tuple[DocumentRevisionRelation, ...]:
        return self._list_for_owner(
            DOCUMENT_REVISION_RELATION_SPEC, "earlier_document_id", document_id
        )

    def save_evidence_target(self, record: EvidenceTarget) -> None:
        self._save(EVIDENCE_TARGET_SPEC, record)

    def get_evidence_target(self, record_id: str) -> EvidenceTarget | None:
        return self._get(EVIDENCE_TARGET_SPEC, record_id)

    def list_evidence_targets(self) -> tuple[EvidenceTarget, ...]:
        return self._list(EVIDENCE_TARGET_SPEC)

    def save_evidence_validation_attempt(self, record: EvidenceValidationAttempt) -> None:
        self._save(EVIDENCE_VALIDATION_ATTEMPT_SPEC, record)

    def get_evidence_validation_attempt(self, record_id: str) -> EvidenceValidationAttempt | None:
        return self._get(EVIDENCE_VALIDATION_ATTEMPT_SPEC, record_id)

    def list_evidence_validation_attempts(self) -> tuple[EvidenceValidationAttempt, ...]:
        return self._list(EVIDENCE_VALIDATION_ATTEMPT_SPEC)

    def ensure_processing_task_fingerprint(
        self, record: ProcessingTaskFingerprint
    ) -> ImmutableCommitDisposition:
        incoming_json = canonical_record_json(record)
        cursor = self._connection.execute(
            """
            INSERT INTO processing_task_fingerprints (
              id, task_kind, document_id, blob_id, fingerprint_digest,
              build_identity_digest, processor_name, processor_version,
              processor_config_digest, policy_id, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO NOTHING
            """,
            (
                record.id,
                record.task_kind,
                record.input_document_id,
                record.input_blob_id,
                record.fingerprint_digest,
                record.build_identity_digest,
                record.processor_name,
                record.processor_version,
                record.processor_config_digest,
                record.policy_id,
                incoming_json,
            ),
        )
        if cursor.rowcount == 1:
            return ImmutableCommitDisposition.CREATED
        existing = self.get_processing_task_fingerprint(record.id)
        if existing == record:
            return ImmutableCommitDisposition.REUSED
        raise ImmutableRecordConflict(
            "ProcessingTaskFingerprint",
            record.id,
            hashlib.sha256(canonical_record_json(existing).encode()).hexdigest()
            if existing is not None
            else "missing",
            hashlib.sha256(incoming_json.encode()).hexdigest(),
        )

    def get_processing_task_fingerprint(self, record_id: str) -> ProcessingTaskFingerprint | None:
        return self._get(PROCESSING_TASK_FINGERPRINT_SPEC, record_id)

    def append_processing_attempt(self, record: ProcessingAttempt) -> None:
        self._connection.execute(
            """
            INSERT INTO processing_attempts (id, task_fingerprint_id, started_at, payload_json)
            VALUES (?, ?, ?, ?)
            """,
            (
                record.id,
                record.task_fingerprint_id,
                record.started_at.isoformat(),
                canonical_record_json(record),
            ),
        )

    def get_processing_attempt(self, record_id: str) -> ProcessingAttempt | None:
        return self._get(PROCESSING_ATTEMPT_SPEC, record_id)

    def append_processing_attempt_outcome(self, record: ProcessingAttemptOutcome) -> None:
        attempt = self.get_processing_attempt(record.attempt_id)
        if attempt is None:
            raise ValueError(f"ProcessingAttempt not found: {record.attempt_id}")
        if record.finished_at < attempt.started_at:
            raise ValueError("ProcessingAttemptOutcome cannot finish before its attempt starts.")
        self._validate_processing_output_references(record)
        self._connection.execute(
            """
            INSERT INTO processing_attempt_outcomes (
              id, attempt_id, status, finished_at, payload_json
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                record.id,
                record.attempt_id,
                record.status.value,
                record.finished_at.isoformat(),
                canonical_record_json(record),
            ),
        )

    def _validate_processing_output_references(self, record: ProcessingAttemptOutcome) -> None:
        table_by_kind = {
            "document_representation": "document_representations",
            "text_view": "text_views",
            "document_node": "document_nodes",
            "document_edge": "document_edges",
            "source_region": "source_regions",
            "quality_report": "parse_quality_reports",
            "provenance_activity": "provenance_activities",
        }
        for artifact in record.output_artifacts:
            table_name = table_by_kind[artifact.kind.value]
            row = self._connection.execute(
                f"SELECT 1 FROM {table_name} WHERE id = ?", (artifact.artifact_id,)
            ).fetchone()
            if row is None:
                raise ValueError(
                    "ProcessingAttemptOutcome references missing output artifact: "
                    f"{artifact.kind.value}:{artifact.artifact_id}"
                )
        if record.provenance_activity_id is not None:
            provenance = self.get_provenance_activity(record.provenance_activity_id)
            if provenance is None:
                raise ValueError(
                    "ProcessingAttemptOutcome references missing ProvenanceActivity: "
                    f"{record.provenance_activity_id}"
                )

    def commit_processing_attempt_start(self) -> None:
        """Durably expose an attempt before any processor work begins."""
        self._connection.commit()

    def record_failed_processing_attempt_outcome(self, record: ProcessingAttemptOutcome) -> None:
        """Discard uncommitted output work, then durably close the attempt."""
        self._connection.rollback()
        self.append_processing_attempt_outcome(record)
        self._connection.commit()

    def get_processing_attempt_outcome(self, attempt_id: str) -> ProcessingAttemptOutcome | None:
        row = self._connection.execute(
            "SELECT payload_json FROM processing_attempt_outcomes WHERE attempt_id = ?",
            (attempt_id,),
        ).fetchone()
        return (
            ProcessingAttemptOutcome.model_validate_json(str(row[0])) if row is not None else None
        )

    def list_processing_attempts(
        self,
        fingerprint_id: str,
        *,
        after: str | None = None,
        limit: int = 100,
    ) -> tuple[ProcessingAttempt, ...]:
        if limit <= 0:
            raise ValueError("Processing attempt page limit must be positive.")
        after_attempt = self.get_processing_attempt(after) if after is not None else None
        if after is not None and after_attempt is None:
            raise ValueError(f"Processing attempt cursor not found: {after}")
        if after_attempt is not None and after_attempt.task_fingerprint_id != fingerprint_id:
            raise ValueError("Processing attempt cursor belongs to a different task fingerprint.")
        rows = self._connection.execute(
            """
            SELECT payload_json FROM processing_attempts
            WHERE task_fingerprint_id = ?
              AND (
                ? IS NULL
                OR started_at > ?
                OR (started_at = ? AND id > ?)
              )
            ORDER BY started_at, id LIMIT ?
            """,
            (
                fingerprint_id,
                after,
                after_attempt.started_at.isoformat() if after_attempt is not None else None,
                after_attempt.started_at.isoformat() if after_attempt is not None else None,
                after,
                limit,
            ),
        ).fetchall()
        return tuple(ProcessingAttempt.model_validate_json(str(row[0])) for row in rows)

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

    def commit_accepted_assertion_with_evidence(
        self,
        *,
        assertion: Assertion,
        evidence_links: tuple[AssertionEvidenceLink, ...],
        provenance_activity: ProvenanceActivity,
        reviewed_change: ProposedChange,
    ) -> None:
        self._connection.execute("SAVEPOINT accepted_assertion_with_evidence")
        try:
            self.save_provenance_activity(provenance_activity)
            self.save_assertion(assertion)
            for evidence_link in evidence_links:
                self.save_assertion_evidence_link(evidence_link)
            self.save_proposed_change(reviewed_change)
        except Exception:
            self._connection.execute("ROLLBACK TO SAVEPOINT accepted_assertion_with_evidence")
            self._connection.execute("RELEASE SAVEPOINT accepted_assertion_with_evidence")
            raise
        self._connection.execute("RELEASE SAVEPOINT accepted_assertion_with_evidence")

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
