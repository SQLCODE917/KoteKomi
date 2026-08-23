"""Disposable SQLite exact and FTS5 projections for DR-1 document retrieval."""

from __future__ import annotations

import hashlib
import math
import re
import sqlite3
import struct
from pathlib import Path
from typing import cast

from kotekomi_application.document_retrieval import (
    ChannelCandidate,
    DocumentRetrievalError,
    ProjectionBuildInput,
    RetrievalFailureCode,
    SemanticProjectionBuildInput,
)
from kotekomi_domain import (
    DocumentRetrievalUnit,
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
        self._validate_unit_policies(manifest, build.units)
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

    def publish_semantic(
        self, build: SemanticProjectionBuildInput
    ) -> tuple[RetrievalIndexManifest, bool]:
        """Publish one complete semantic projection atomically, separate from DR-1 rows."""
        manifest = build.manifest
        if (
            manifest.channels != (RetrievalChannel.SEMANTIC,)
            or manifest.embedding_profile_id is None
            or manifest.embedding_model_identity is None
        ):
            raise DocumentRetrievalError(
                RetrievalFailureCode.INDEX_CORRUPT, "Semantic build requires a semantic manifest."
            )
        self._validate_unit_policies(manifest, build.units)
        self._connection.execute("BEGIN IMMEDIATE")
        try:
            existing_row = self._connection.execute(
                "SELECT manifest_json FROM semantic_retrieval_manifests "
                "WHERE index_manifest_id = ?",
                (manifest.index_manifest_id,),
            ).fetchone()
            if existing_row is not None:
                existing = RetrievalIndexManifest.model_validate_json(existing_row["manifest_json"])
                self._validate_semantic_complete(existing)
                self._connection.execute("COMMIT")
                return existing, True
            self._delete_semantic_rows(manifest.representation_id, manifest.embedding_profile_id)
            representations = {item.retrieval_unit_id: item for item in build.representations}
            vectors = {item.retrieval_unit_id: item for item in build.vectors}
            if len(representations) != len(build.units) or len(vectors) != len(build.units):
                raise DocumentRetrievalError(
                    RetrievalFailureCode.INDEX_CORRUPT,
                    "Each semantic retrieval unit requires one representation and vector.",
                )
            for unit in build.units:
                representation = representations.get(unit.retrieval_unit_id)
                vector = vectors.get(unit.retrieval_unit_id)
                if representation is None or vector is None:
                    raise DocumentRetrievalError(
                        RetrievalFailureCode.INDEX_CORRUPT,
                        "A semantic retrieval unit projection is missing.",
                    )
                self._validate_vector(
                    vector.vector, manifest.embedding_model_identity.vector_dimension
                )
                self._connection.execute(
                    """
                    INSERT INTO semantic_retrieval_units (
                        manifest_id, retrieval_unit_id, source_order, unit_json,
                        representation_json, vector, vector_digest
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        manifest.index_manifest_id,
                        unit.retrieval_unit_id,
                        unit.source_order,
                        unit.model_dump_json(),
                        representation.model_dump_json(),
                        vector.vector,
                        vector.vector_digest,
                    ),
                )
            self._validate_semantic_written_build(manifest)
            self._connection.execute(
                """
                INSERT INTO semantic_retrieval_manifests (
                    index_manifest_id, representation_id, embedding_profile_id, manifest_json
                ) VALUES (?, ?, ?, ?)
                """,
                (
                    manifest.index_manifest_id,
                    manifest.representation_id,
                    manifest.embedding_profile_id,
                    manifest.model_dump_json(),
                ),
            )
            self._connection.execute("COMMIT")
            return manifest, False
        except Exception:
            self._connection.execute("ROLLBACK")
            raise

    def get_complete_semantic_manifest(
        self, representation_id: str, profile_id: str
    ) -> RetrievalIndexManifest | None:
        row = self._connection.execute(
            """
            SELECT manifest_json FROM semantic_retrieval_manifests
            WHERE representation_id = ? AND embedding_profile_id = ?
            """,
            (representation_id, profile_id),
        ).fetchone()
        if row is None:
            return None
        try:
            manifest = RetrievalIndexManifest.model_validate_json(row["manifest_json"])
            self._validate_semantic_complete(manifest)
            return manifest
        except (ValueError, TypeError) as exc:
            raise DocumentRetrievalError(
                RetrievalFailureCode.INDEX_CORRUPT, "Semantic retrieval index manifest is corrupt."
            ) from exc

    def semantic_candidates(
        self, manifest: RetrievalIndexManifest, query_vector: bytes
    ) -> tuple[ChannelCandidate, ...]:
        identity = manifest.embedding_model_identity
        if identity is None:
            raise DocumentRetrievalError(
                RetrievalFailureCode.INDEX_CORRUPT, "Semantic manifest lacks model identity."
            )
        query = self._validate_vector(query_vector, identity.vector_dimension)
        rows = self._connection.execute(
            """
            SELECT retrieval_unit_id, source_order, vector
            FROM semantic_retrieval_units
            WHERE manifest_id = ?
            """,
            (manifest.index_manifest_id,),
        ).fetchall()
        scored: list[tuple[float, int, str]] = []
        for row in rows:
            vector = self._validate_vector(cast(bytes, row["vector"]), identity.vector_dimension)
            scored.append(
                (
                    self._cosine(query, vector),
                    cast(int, row["source_order"]),
                    cast(str, row["retrieval_unit_id"]),
                )
            )
        scored.sort(key=lambda item: (-item[0], item[1], item[2]))
        return tuple(
            ChannelCandidate(
                retrieval_unit_id=unit_id,
                channel=RetrievalChannel.SEMANTIC,
                channel_rank=rank,
                raw_score=score,
                matched_field="cosine_similarity",
            )
            for rank, (score, _, unit_id) in enumerate(scored, start=1)
        )

    def delete_semantic_projection(self, representation_id: str, profile_id: str) -> None:
        """Delete semantic derived rows only; Ledger and Archive remain untouched."""
        self._connection.execute("BEGIN IMMEDIATE")
        try:
            self._delete_semantic_rows(representation_id, profile_id)
            self._connection.execute("COMMIT")
        except Exception:
            self._connection.execute("ROLLBACK")
            raise

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

    @staticmethod
    def _validate_unit_policies(
        manifest: RetrievalIndexManifest, units: tuple[DocumentRetrievalUnit, ...]
    ) -> None:
        if any(unit.unit_policy_id != manifest.unit_policy_id for unit in units):
            raise DocumentRetrievalError(
                RetrievalFailureCode.INDEX_CORRUPT,
                "Retrieval unit policy does not match its index manifest.",
            )

    def _validate_complete(self, manifest: RetrievalIndexManifest) -> None:
        if manifest.publication_status != "complete":
            raise DocumentRetrievalError(
                RetrievalFailureCode.INDEX_INCOMPLETE, "Retrieval index is not complete."
            )
        self._validate_written_build(manifest)

    def _validate_semantic_complete(self, manifest: RetrievalIndexManifest) -> None:
        if manifest.channels != (RetrievalChannel.SEMANTIC,):
            raise DocumentRetrievalError(
                RetrievalFailureCode.INDEX_CORRUPT, "Semantic index has non-semantic channels."
            )
        if manifest.publication_status != "complete":
            raise DocumentRetrievalError(
                RetrievalFailureCode.INDEX_INCOMPLETE, "Semantic index is not complete."
            )
        self._validate_semantic_written_build(manifest)

    def _validate_semantic_written_build(self, manifest: RetrievalIndexManifest) -> None:
        count = self._connection.execute(
            "SELECT COUNT(*) FROM semantic_retrieval_units WHERE manifest_id = ?",
            (manifest.index_manifest_id,),
        ).fetchone()[0]
        if count != manifest.unit_count:
            raise DocumentRetrievalError(
                RetrievalFailureCode.INDEX_INCOMPLETE,
                "Unpublished semantic projection did not write all rows.",
            )

    def _delete_semantic_rows(self, representation_id: str, profile_id: str) -> None:
        rows = self._connection.execute(
            """
            SELECT index_manifest_id FROM semantic_retrieval_manifests
            WHERE representation_id = ? AND embedding_profile_id = ?
            """,
            (representation_id, profile_id),
        ).fetchall()
        for row in rows:
            self._connection.execute(
                "DELETE FROM semantic_retrieval_units WHERE manifest_id = ?",
                (row["index_manifest_id"],),
            )
        self._connection.execute(
            """
            DELETE FROM semantic_retrieval_manifests
            WHERE representation_id = ? AND embedding_profile_id = ?
            """,
            (representation_id, profile_id),
        )

    @staticmethod
    def _validate_vector(payload: bytes, dimension: int) -> tuple[float, ...]:
        if len(payload) != dimension * 4:
            raise DocumentRetrievalError(
                RetrievalFailureCode.INDEX_CORRUPT, "Semantic vector has an invalid byte length."
            )
        vector = struct.unpack(f"<{dimension}f", payload)
        if not all(math.isfinite(value) for value in vector):
            raise DocumentRetrievalError(
                RetrievalFailureCode.INDEX_CORRUPT, "Semantic vector has a non-finite value."
            )
        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0 or not math.isfinite(norm):
            raise DocumentRetrievalError(
                RetrievalFailureCode.INDEX_CORRUPT, "Semantic vector is zero or invalid."
            )
        return vector

    @staticmethod
    def _cosine(left: tuple[float, ...], right: tuple[float, ...]) -> float:
        score = sum(a * b for a, b in zip(left, right, strict=True))
        if not math.isfinite(score):
            raise DocumentRetrievalError(
                RetrievalFailureCode.INDEX_CORRUPT, "Semantic cosine score is non-finite."
            )
        return score

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
            CREATE TABLE IF NOT EXISTS semantic_retrieval_manifests (
                index_manifest_id TEXT PRIMARY KEY,
                representation_id TEXT NOT NULL,
                embedding_profile_id TEXT NOT NULL,
                manifest_json TEXT NOT NULL,
                UNIQUE (representation_id, embedding_profile_id)
            );
            CREATE TABLE IF NOT EXISTS semantic_retrieval_units (
                manifest_id TEXT NOT NULL,
                retrieval_unit_id TEXT NOT NULL,
                source_order INTEGER NOT NULL,
                unit_json TEXT NOT NULL,
                representation_json TEXT NOT NULL,
                vector BLOB NOT NULL,
                vector_digest TEXT NOT NULL,
                PRIMARY KEY (manifest_id, retrieval_unit_id)
            );
            """
        )
        self._connection.commit()
