"""Disposable SQLite exact, lexical, and structured Ledger retrieval projection."""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

from kotekomi_application.ledger_retrieval import (
    LedgerChannelCandidate,
    LedgerProjectionBuildInput,
    LedgerRetrievalError,
    LedgerRetrievalFailureCode,
    LedgerRetrievalFilters,
)
from kotekomi_domain import (
    LedgerRetrievalIndexManifest,
    LedgerRetrievalQueryRecord,
    RetrievalChannel,
)


class SQLiteLedgerRetrievalAdapter:
    """A rebuildable index that stores only derived Ledger retrieval state."""

    def __init__(self, path: Path) -> None:
        self._connection = sqlite3.connect(path)
        self._connection.row_factory = sqlite3.Row
        self._initialize()

    def close(self) -> None:
        self._connection.close()

    def delete_projection(self) -> None:
        self._connection.execute("DELETE FROM ledger_retrieval_fts")
        self._connection.execute("DELETE FROM ledger_retrieval_rows")
        self._connection.execute("DELETE FROM ledger_retrieval_units")
        self._connection.execute("DELETE FROM ledger_retrieval_manifests")
        self._connection.commit()

    def publish(
        self, build: LedgerProjectionBuildInput
    ) -> tuple[LedgerRetrievalIndexManifest, bool]:
        manifest = build.manifest
        if len(build.units) != len(build.representations):
            raise LedgerRetrievalError(
                LedgerRetrievalFailureCode.INDEX_CORRUPT,
                "Each Ledger retrieval unit requires one representation.",
            )
        representations = {item.retrieval_unit_id: item for item in build.representations}
        if len(representations) != len(build.units):
            raise LedgerRetrievalError(
                LedgerRetrievalFailureCode.INDEX_CORRUPT,
                "Ledger retrieval representations are not unique by unit.",
            )
        self._connection.execute("BEGIN IMMEDIATE")
        try:
            row = self._connection.execute(
                "SELECT manifest_json FROM ledger_retrieval_manifests WHERE index_manifest_id = ?",
                (manifest.index_manifest_id,),
            ).fetchone()
            if row is not None:
                existing = LedgerRetrievalIndexManifest.model_validate_json(
                    str(row["manifest_json"])
                )
                self._validate_complete(existing)
                self._connection.execute("COMMIT")
                return existing, True
            self._connection.execute("DELETE FROM ledger_retrieval_fts")
            self._connection.execute("DELETE FROM ledger_retrieval_rows")
            self._connection.execute("DELETE FROM ledger_retrieval_units")
            self._connection.execute("DELETE FROM ledger_retrieval_manifests")
            for unit in build.units:
                representation = representations.get(unit.retrieval_unit_id)
                if representation is None:
                    raise LedgerRetrievalError(
                        LedgerRetrievalFailureCode.INDEX_CORRUPT,
                        "Ledger retrieval unit projection is missing.",
                    )
                self._connection.execute(
                    """
                    INSERT INTO ledger_retrieval_units (
                        retrieval_unit_id, source_record_id, record_type, assertion_status,
                        subject_id, predicate, updated_at, source_order, unit_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        unit.retrieval_unit_id,
                        unit.source_record_id,
                        unit.record_type.value,
                        unit.assertion_status.value if unit.assertion_status is not None else None,
                        unit.subject_id,
                        unit.predicate,
                        unit.updated_at.isoformat(),
                        unit.source_order,
                        unit.model_dump_json(),
                    ),
                )
                self._connection.execute(
                    """
                    INSERT INTO ledger_retrieval_rows (
                        manifest_id, retrieval_unit_id, exact_text, exact_casefold,
                        representation_json
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        manifest.index_manifest_id,
                        unit.retrieval_unit_id,
                        representation.exact_text,
                        representation.exact_text.casefold(),
                        representation.model_dump_json(),
                    ),
                )
                self._connection.execute(
                    """
                    INSERT INTO ledger_retrieval_fts (manifest_id, retrieval_unit_id, body)
                    VALUES (?, ?, ?)
                    """,
                    (
                        manifest.index_manifest_id,
                        unit.retrieval_unit_id,
                        representation.lexical_text,
                    ),
                )
            self._validate_written_build(manifest)
            self._connection.execute(
                """
                INSERT INTO ledger_retrieval_manifests (index_manifest_id, manifest_json)
                VALUES (?, ?)
                """,
                (manifest.index_manifest_id, manifest.model_dump_json()),
            )
            self._connection.execute("COMMIT")
            return manifest, False
        except Exception:
            self._connection.execute("ROLLBACK")
            raise

    def get_complete_manifest(self) -> LedgerRetrievalIndexManifest | None:
        row = self._connection.execute(
            "SELECT manifest_json FROM ledger_retrieval_manifests ORDER BY index_manifest_id"
        ).fetchone()
        if row is None:
            return None
        try:
            manifest = LedgerRetrievalIndexManifest.model_validate_json(str(row["manifest_json"]))
            self._validate_complete(manifest)
            return manifest
        except (TypeError, ValueError) as exc:
            raise LedgerRetrievalError(
                LedgerRetrievalFailureCode.INDEX_CORRUPT,
                "Ledger retrieval index manifest is corrupt.",
            ) from exc

    def exact_candidates(
        self,
        manifest: LedgerRetrievalIndexManifest,
        normalized_query: str,
        filters: LedgerRetrievalFilters,
    ) -> tuple[LedgerChannelCandidate, ...]:
        where, values = self._filter_clause(filters, "u")
        rows = self._connection.execute(
            f"""
            SELECT r.retrieval_unit_id,
                CASE WHEN instr(r.exact_casefold, ?) > 0 THEN 'projection_text' END AS matched_field
            FROM ledger_retrieval_rows r
            JOIN ledger_retrieval_units u ON u.retrieval_unit_id = r.retrieval_unit_id
            WHERE r.manifest_id = ? AND instr(r.exact_casefold, ?) > 0 {where}
            ORDER BY u.source_order, u.retrieval_unit_id
            """,
            (
                normalized_query.casefold(),
                manifest.index_manifest_id,
                normalized_query.casefold(),
                *values,
            ),
        ).fetchall()
        return tuple(
            LedgerChannelCandidate(
                retrieval_unit_id=str(row["retrieval_unit_id"]),
                channel=RetrievalChannel.EXACT,
                channel_rank=index + 1,
                matched_field=str(row["matched_field"]),
            )
            for index, row in enumerate(rows)
        )

    def lexical_candidates(
        self,
        manifest: LedgerRetrievalIndexManifest,
        query_text: str,
        filters: LedgerRetrievalFilters,
    ) -> tuple[LedgerChannelCandidate, ...]:
        terms = re.findall(r"\w+", query_text, flags=re.UNICODE)
        if not terms:
            return ()
        where, values = self._filter_clause(filters, "u")
        try:
            rows = self._connection.execute(
                f"""
                SELECT f.retrieval_unit_id, bm25(ledger_retrieval_fts) AS score
                FROM ledger_retrieval_fts f
                JOIN ledger_retrieval_units u ON u.retrieval_unit_id = f.retrieval_unit_id
                WHERE f.manifest_id = ? AND ledger_retrieval_fts MATCH ? {where}
                ORDER BY score, u.source_order, f.retrieval_unit_id
                """,
                (manifest.index_manifest_id, " OR ".join(terms), *values),
            ).fetchall()
        except sqlite3.OperationalError as exc:
            raise LedgerRetrievalError(
                LedgerRetrievalFailureCode.INDEX_CORRUPT,
                "Ledger lexical index rejected a normalized query.",
            ) from exc
        return tuple(
            LedgerChannelCandidate(
                retrieval_unit_id=str(row["retrieval_unit_id"]),
                channel=RetrievalChannel.LEXICAL,
                channel_rank=index + 1,
                raw_score=float(row["score"]),
                matched_field="projection_text",
            )
            for index, row in enumerate(rows)
        )

    def structured_candidates(
        self,
        manifest: LedgerRetrievalIndexManifest,
        filters: LedgerRetrievalFilters,
    ) -> tuple[LedgerChannelCandidate, ...]:
        where, values = self._filter_clause(filters, "u")
        rows = self._connection.execute(
            f"""
            SELECT u.retrieval_unit_id
            FROM ledger_retrieval_units u
            JOIN ledger_retrieval_rows r ON r.retrieval_unit_id = u.retrieval_unit_id
            WHERE r.manifest_id = ? {where}
            ORDER BY u.updated_at DESC, u.source_order, u.retrieval_unit_id
            """,
            (manifest.index_manifest_id, *values),
        ).fetchall()
        return tuple(
            LedgerChannelCandidate(
                retrieval_unit_id=str(row["retrieval_unit_id"]),
                channel=RetrievalChannel.STRUCTURED_FILTER,
                channel_rank=index + 1,
                matched_field="structured_filter",
            )
            for index, row in enumerate(rows)
        )

    def save_query_record(self, record: LedgerRetrievalQueryRecord) -> None:
        self._connection.execute(
            """
            INSERT OR REPLACE INTO ledger_retrieval_query_records
            (retrieval_query_id, record_json) VALUES (?, ?)
            """,
            (record.retrieval_query_id, record.model_dump_json()),
        )
        self._connection.commit()

    def _filter_clause(
        self, filters: LedgerRetrievalFilters, alias: str
    ) -> tuple[str, tuple[object, ...]]:
        clauses: list[str] = []
        values: list[object] = []
        if filters.record_id is not None:
            clauses.append(f"AND {alias}.source_record_id = ?")
            values.append(filters.record_id)
        if filters.record_type is not None:
            clauses.append(f"AND {alias}.record_type = ?")
            values.append(filters.record_type.value)
        if filters.assertion_statuses:
            placeholders = ", ".join("?" for _ in filters.assertion_statuses)
            clauses.append(f"AND {alias}.assertion_status IN ({placeholders})")
            values.extend(item.value for item in filters.assertion_statuses)
        if filters.subject_id is not None:
            clauses.append(f"AND {alias}.subject_id = ?")
            values.append(filters.subject_id)
        if filters.predicate is not None:
            clauses.append(f"AND {alias}.predicate = ?")
            values.append(filters.predicate)
        return " " + " ".join(clauses), tuple(values)

    def _validate_complete(self, manifest: LedgerRetrievalIndexManifest) -> None:
        if manifest.publication_status != "complete":
            raise LedgerRetrievalError(
                LedgerRetrievalFailureCode.INDEX_CORRUPT,
                "Ledger retrieval index manifest is incomplete.",
            )

    def _validate_written_build(self, manifest: LedgerRetrievalIndexManifest) -> None:
        unit_count = self._connection.execute(
            "SELECT COUNT(*) FROM ledger_retrieval_units"
        ).fetchone()[0]
        row_count = self._connection.execute(
            "SELECT COUNT(*) FROM ledger_retrieval_rows WHERE manifest_id = ?",
            (manifest.index_manifest_id,),
        ).fetchone()[0]
        fts_count = self._connection.execute(
            "SELECT COUNT(*) FROM ledger_retrieval_fts WHERE manifest_id = ?",
            (manifest.index_manifest_id,),
        ).fetchone()[0]
        if (unit_count, row_count, fts_count) != (manifest.unit_count,) * 3:
            raise LedgerRetrievalError(
                LedgerRetrievalFailureCode.INDEX_CORRUPT,
                "Ledger retrieval index write count does not match manifest.",
            )

    def _initialize(self) -> None:
        self._connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS ledger_retrieval_manifests (
                index_manifest_id TEXT PRIMARY KEY NOT NULL,
                manifest_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS ledger_retrieval_units (
                retrieval_unit_id TEXT PRIMARY KEY NOT NULL,
                source_record_id TEXT NOT NULL,
                record_type TEXT NOT NULL,
                assertion_status TEXT,
                subject_id TEXT,
                predicate TEXT,
                updated_at TEXT NOT NULL,
                source_order INTEGER NOT NULL,
                unit_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS ledger_retrieval_rows (
                manifest_id TEXT NOT NULL,
                retrieval_unit_id TEXT PRIMARY KEY NOT NULL,
                exact_text TEXT NOT NULL,
                exact_casefold TEXT NOT NULL,
                representation_json TEXT NOT NULL
            );
            CREATE VIRTUAL TABLE IF NOT EXISTS ledger_retrieval_fts USING fts5(
                manifest_id UNINDEXED,
                retrieval_unit_id UNINDEXED,
                body
            );
            CREATE TABLE IF NOT EXISTS ledger_retrieval_query_records (
                retrieval_query_id TEXT PRIMARY KEY NOT NULL,
                record_json TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS ledger_retrieval_units_filter_idx
            ON ledger_retrieval_units (
                record_type, assertion_status, subject_id, predicate, updated_at
            );
            """
        )
        self._connection.commit()
