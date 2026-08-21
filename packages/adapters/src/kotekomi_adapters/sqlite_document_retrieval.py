"""Disposable SQLite exact and FTS5 projections for DR-1 document retrieval."""

from __future__ import annotations

import hashlib
import re
import sqlite3
from pathlib import Path

from kotekomi_application.document_retrieval import (
    ChannelCandidate,
    DocumentRetrievalError,
    ProjectionBuildInput,
    RetrievalFailureCode,
)
from kotekomi_domain import (
    RetrievalChannel,
    RetrievalIndexManifest,
    RetrievalQueryRecord,
)


class SQLiteDocumentRetrievalAdapter:
    """A rebuildable index; it never persists authoritative source records."""

    def __init__(self, path: Path) -> None:
        self._connection = sqlite3.connect(path)
        self._connection.row_factory = sqlite3.Row
        self._initialize()

    def close(self) -> None:
        self._connection.close()

    def publish(self, build: ProjectionBuildInput) -> tuple[RetrievalIndexManifest, bool]:
        manifest = build.manifest
        self._connection.execute("BEGIN IMMEDIATE")
        try:
            row = self._connection.execute(
                "SELECT manifest_json FROM retrieval_manifests WHERE index_manifest_id = ?",
                (manifest.index_manifest_id,),
            ).fetchone()
            if row is not None:
                existing = RetrievalIndexManifest.model_validate_json(row["manifest_json"])
                self._validate_complete(existing)
                self._connection.execute("COMMIT")
                return existing, True
            prior_rows = self._connection.execute(
                "SELECT index_manifest_id FROM retrieval_manifests WHERE representation_id = ?",
                (manifest.representation_id,),
            ).fetchall()
            for prior in prior_rows:
                self._connection.execute(
                    "DELETE FROM retrieval_fts WHERE manifest_id = ?", (prior["index_manifest_id"],)
                )
            self._connection.execute(
                "DELETE FROM retrieval_manifests WHERE representation_id = ?",
                (manifest.representation_id,),
            )
            self._connection.execute(
                "DELETE FROM retrieval_units WHERE representation_id = ?",
                (manifest.representation_id,),
            )
            self._connection.execute(
                "DELETE FROM retrieval_exact_rows WHERE representation_id = ?",
                (manifest.representation_id,),
            )
            representations = {item.retrieval_unit_id: item for item in build.representations}
            if len(representations) != len(build.units):
                raise DocumentRetrievalError(
                    RetrievalFailureCode.INDEX_CORRUPT,
                    "Each document retrieval unit requires one projection.",
                )
            for unit in build.units:
                representation = representations.get(unit.retrieval_unit_id)
                if representation is None:
                    raise DocumentRetrievalError(
                        RetrievalFailureCode.INDEX_CORRUPT,
                        "A retrieval unit projection is missing.",
                    )
                self._connection.execute(
                    """
                    INSERT INTO retrieval_units (
                        retrieval_unit_id, representation_id, source_order, unit_json
                    ) VALUES (?, ?, ?, ?)
                    """,
                    (
                        unit.retrieval_unit_id,
                        unit.representation_id,
                        unit.source_order,
                        unit.model_dump_json(),
                    ),
                )
                self._connection.execute(
                    """
                    INSERT INTO retrieval_exact_rows (
                        manifest_id, representation_id, retrieval_unit_id, source_order,
                        body_nfc, body_casefold, source_title_nfc, heading_path_nfc,
                        representation_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        manifest.index_manifest_id,
                        unit.representation_id,
                        unit.retrieval_unit_id,
                        unit.source_order,
                        representation.exact_fields["body_nfc"],
                        representation.exact_fields["body_casefold"],
                        representation.exact_fields["source_title_nfc"],
                        representation.exact_fields["heading_path_nfc"],
                        representation.model_dump_json(),
                    ),
                )
                self._connection.execute(
                    """
                    INSERT INTO retrieval_fts (
                        manifest_id, retrieval_unit_id, body, heading_path,
                        source_title, structural_role
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        manifest.index_manifest_id,
                        unit.retrieval_unit_id,
                        representation.lexical_fields["body"],
                        representation.lexical_fields["heading_path"],
                        representation.lexical_fields["source_title"],
                        representation.lexical_fields["structural_role"],
                    ),
                )
            self._validate_written_build(manifest)
            self._connection.execute(
                """
                INSERT INTO retrieval_manifests (
                    index_manifest_id, representation_id, manifest_json
                )
                VALUES (?, ?, ?)
                """,
                (
                    manifest.index_manifest_id,
                    manifest.representation_id,
                    manifest.model_dump_json(),
                ),
            )
            self._connection.execute("COMMIT")
            return manifest, False
        except Exception:
            self._connection.execute("ROLLBACK")
            raise

    def get_complete_manifest(self, representation_id: str) -> RetrievalIndexManifest | None:
        row = self._connection.execute(
            "SELECT manifest_json FROM retrieval_manifests WHERE representation_id = ?",
            (representation_id,),
        ).fetchone()
        if row is None:
            return None
        try:
            manifest = RetrievalIndexManifest.model_validate_json(row["manifest_json"])
            self._validate_complete(manifest)
            return manifest
        except (ValueError, TypeError) as exc:
            raise DocumentRetrievalError(
                RetrievalFailureCode.INDEX_CORRUPT, "Retrieval index manifest is corrupt."
            ) from exc

    def exact_candidates(
        self, manifest: RetrievalIndexManifest, normalized_query: str
    ) -> tuple[ChannelCandidate, ...]:
        folded = normalized_query.casefold()
        rows = self._connection.execute(
            """
            SELECT retrieval_unit_id, source_order,
                CASE
                    WHEN instr(body_casefold, ?) > 0 THEN 'body_nfc'
                    WHEN instr(source_title_nfc, ?) > 0 THEN 'source_title_nfc'
                    WHEN instr(heading_path_nfc, ?) > 0 THEN 'heading_path_nfc'
                END AS matched_field
            FROM retrieval_exact_rows
            WHERE manifest_id = ?
              AND (
                  instr(body_casefold, ?) > 0
                  OR instr(lower(source_title_nfc), ?) > 0
                  OR instr(lower(heading_path_nfc), ?) > 0
              )
            ORDER BY
                CASE
                    WHEN instr(body_casefold, ?) > 0 THEN 0
                    WHEN instr(source_title_nfc, ?) > 0 THEN 1
                    ELSE 2
                END,
                source_order,
                retrieval_unit_id
            """,
            (
                folded,
                folded,
                folded,
                manifest.index_manifest_id,
                folded,
                folded,
                folded,
                folded,
                folded,
            ),
        ).fetchall()
        literal_digest = hashlib.sha256(normalized_query.encode("utf-8")).hexdigest()
        return tuple(
            ChannelCandidate(
                retrieval_unit_id=row["retrieval_unit_id"],
                channel=RetrievalChannel.EXACT,
                channel_rank=rank,
                matched_field=row["matched_field"],
                matched_literal_digest=literal_digest,
            )
            for rank, row in enumerate(rows, start=1)
        )

    def lexical_candidates(
        self, manifest: RetrievalIndexManifest, query_text: str
    ) -> tuple[ChannelCandidate, ...]:
        terms = tuple(re.findall(r"\w+", query_text, flags=re.UNICODE))
        if not terms:
            return ()
        fts_query = " OR ".join(f'"{term.replace(chr(34), chr(34) * 2)}"' for term in terms)
        rows = self._connection.execute(
            """
            SELECT retrieval_unit_id, bm25(retrieval_fts) AS score
            FROM retrieval_fts
            WHERE retrieval_fts MATCH ? AND manifest_id = ?
            ORDER BY score, retrieval_unit_id
            """,
            (fts_query, manifest.index_manifest_id),
        ).fetchall()
        return tuple(
            ChannelCandidate(
                retrieval_unit_id=row["retrieval_unit_id"],
                channel=RetrievalChannel.LEXICAL,
                channel_rank=rank,
                raw_score=float(row["score"]),
                matched_field="fts5",
            )
            for rank, row in enumerate(rows, start=1)
        )

    def save_query_record(self, record: RetrievalQueryRecord) -> None:
        self._connection.execute(
            """
            INSERT OR REPLACE INTO retrieval_query_records (retrieval_query_id, record_json)
            VALUES (?, ?)
            """,
            (record.retrieval_query_id, record.model_dump_json()),
        )
        self._connection.commit()

    def delete_projection(self, representation_id: str) -> None:
        """Delete derived rows only, for deterministic rebuild verification."""
        self._connection.execute("BEGIN IMMEDIATE")
        try:
            manifest = self.get_complete_manifest(representation_id)
            if manifest is not None:
                self._connection.execute(
                    "DELETE FROM retrieval_fts WHERE manifest_id = ?", (manifest.index_manifest_id,)
                )
            self._connection.execute(
                "DELETE FROM retrieval_exact_rows WHERE representation_id = ?",
                (representation_id,),
            )
            self._connection.execute(
                "DELETE FROM retrieval_units WHERE representation_id = ?", (representation_id,)
            )
            self._connection.execute(
                "DELETE FROM retrieval_manifests WHERE representation_id = ?",
                (representation_id,),
            )
            self._connection.execute("COMMIT")
        except Exception:
            self._connection.execute("ROLLBACK")
            raise

    def _validate_written_build(self, manifest: RetrievalIndexManifest) -> None:
        exact_count = self._connection.execute(
            "SELECT COUNT(*) FROM retrieval_exact_rows WHERE manifest_id = ?",
            (manifest.index_manifest_id,),
        ).fetchone()[0]
        fts_count = self._connection.execute(
            "SELECT COUNT(*) FROM retrieval_fts WHERE manifest_id = ?",
            (manifest.index_manifest_id,),
        ).fetchone()[0]
        if exact_count != manifest.unit_count or fts_count != manifest.unit_count:
            raise DocumentRetrievalError(
                RetrievalFailureCode.INDEX_INCOMPLETE,
                "Unpublished retrieval projection did not write all rows.",
            )

    def _validate_complete(self, manifest: RetrievalIndexManifest) -> None:
        if manifest.publication_status != "complete":
            raise DocumentRetrievalError(
                RetrievalFailureCode.INDEX_INCOMPLETE, "Retrieval index is not complete."
            )
        self._validate_written_build(manifest)

    def _initialize(self) -> None:
        self._connection.executescript(
            """
            PRAGMA foreign_keys = ON;
            CREATE TABLE IF NOT EXISTS retrieval_manifests (
                index_manifest_id TEXT PRIMARY KEY,
                representation_id TEXT NOT NULL UNIQUE,
                manifest_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS retrieval_units (
                retrieval_unit_id TEXT PRIMARY KEY,
                representation_id TEXT NOT NULL,
                source_order INTEGER NOT NULL,
                unit_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS retrieval_exact_rows (
                manifest_id TEXT NOT NULL,
                representation_id TEXT NOT NULL,
                retrieval_unit_id TEXT NOT NULL,
                source_order INTEGER NOT NULL,
                body_nfc TEXT NOT NULL,
                body_casefold TEXT NOT NULL,
                source_title_nfc TEXT NOT NULL,
                heading_path_nfc TEXT NOT NULL,
                representation_json TEXT NOT NULL,
                PRIMARY KEY (manifest_id, retrieval_unit_id)
            );
            CREATE VIRTUAL TABLE IF NOT EXISTS retrieval_fts USING fts5(
                manifest_id UNINDEXED,
                retrieval_unit_id UNINDEXED,
                body,
                heading_path,
                source_title,
                structural_role,
                tokenize = 'unicode61'
            );
            CREATE TABLE IF NOT EXISTS retrieval_query_records (
                retrieval_query_id TEXT PRIMARY KEY,
                record_json TEXT NOT NULL
            );
            """
        )
        self._connection.commit()
