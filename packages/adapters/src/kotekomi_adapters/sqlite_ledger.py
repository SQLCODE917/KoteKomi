"""SQLite implementation of the LedgerRepository Port."""

from __future__ import annotations

import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from typing import TypeVar

from kotekomi_application import LedgerInitResult
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
from pydantic import BaseModel

DomainRecord = TypeVar("DomainRecord", bound=BaseModel)


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
EVIDENCE_SPAN_SPEC = RecordSpec("evidence_spans", EvidenceSpan)
ASSERTION_SPEC = RecordSpec("assertions", Assertion)
RELATIONSHIP_SPEC = RecordSpec("relationships", Relationship)
OUTCOME_SPEC = RecordSpec("outcomes", Outcome)
ARGUMENT_EDGE_SPEC = RecordSpec("argument_edges", ArgumentEdge)
PROVENANCE_ACTIVITY_SPEC = RecordSpec("provenance_activities", ProvenanceActivity)
PROPOSED_CHANGE_SPEC = RecordSpec("proposed_changes", ProposedChange)
BRIEFING_SPEC = RecordSpec("briefings", Briefing)

REQUIRED_LEDGER_TABLES = (
    "ledger_migrations",
    "entities",
    "actors",
    "organizations",
    "places",
    "events",
    "sources",
    "documents",
    "evidence_spans",
    "assertions",
    "relationships",
    "outcomes",
    "argument_edges",
    "provenance_activities",
    "proposed_changes",
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
                record.model_dump_json(),
            ),
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

    def save_evidence_span(self, record: EvidenceSpan) -> None:
        self._save(EVIDENCE_SPAN_SPEC, record)

    def get_evidence_span(self, record_id: str) -> EvidenceSpan | None:
        return self._get(EVIDENCE_SPAN_SPEC, record_id)

    def list_evidence_spans(self) -> tuple[EvidenceSpan, ...]:
        return self._list(EVIDENCE_SPAN_SPEC)

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
