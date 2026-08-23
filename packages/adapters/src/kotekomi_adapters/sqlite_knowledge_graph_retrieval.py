"""Disposable SQLite projection for Knowledge-Graph traversal retrieval."""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

from kotekomi_application.knowledge_graph_retrieval import (
    KnowledgeGraphProjectionBuildInput,
    KnowledgeGraphRetrievalError,
    KnowledgeGraphRetrievalFailureCode,
    KnowledgeGraphSeedMatch,
)
from kotekomi_domain import (
    KnowledgeGraphEdge,
    KnowledgeGraphRetrievalIndexManifest,
    KnowledgeGraphRetrievalQueryRecord,
    RetrievalChannel,
)

_SEED_NODE_TYPES = ("Actor", "Entity", "Event", "Organization", "Place")


class SQLiteKnowledgeGraphRetrievalAdapter:
    """A rebuildable graph-retrieval sidecar with atomic manifest publication."""

    def __init__(self, path: Path) -> None:
        self._connection = sqlite3.connect(path)
        self._connection.row_factory = sqlite3.Row
        self._initialize()

    def close(self) -> None:
        self._connection.close()

    def delete_projection(self) -> None:
        self._connection.executescript(
            """
            DELETE FROM knowledge_graph_seed_fts;
            DELETE FROM knowledge_graph_edges;
            DELETE FROM knowledge_graph_nodes;
            DELETE FROM knowledge_graph_units;
            DELETE FROM knowledge_graph_manifests;
            """
        )
        self._connection.commit()

    def publish(
        self, build: KnowledgeGraphProjectionBuildInput
    ) -> tuple[KnowledgeGraphRetrievalIndexManifest, bool]:
        manifest = build.manifest
        if len({item.retrieval_unit_id for item in build.units}) != len(build.units):
            raise KnowledgeGraphRetrievalError(
                KnowledgeGraphRetrievalFailureCode.INDEX_CORRUPT,
                "Knowledge-Graph retrieval units are not unique.",
            )
        if len({item.node_id for item in build.nodes}) != len(build.nodes):
            raise KnowledgeGraphRetrievalError(
                KnowledgeGraphRetrievalFailureCode.INDEX_CORRUPT,
                "Knowledge-Graph nodes are not unique.",
            )
        if len({item.edge_id for item in build.edges}) != len(build.edges):
            raise KnowledgeGraphRetrievalError(
                KnowledgeGraphRetrievalFailureCode.INDEX_CORRUPT,
                "Knowledge-Graph edges are not unique.",
            )
        self._connection.execute("BEGIN IMMEDIATE")
        try:
            row = self._connection.execute(
                "SELECT manifest_json FROM knowledge_graph_manifests WHERE index_manifest_id = ?",
                (manifest.index_manifest_id,),
            ).fetchone()
            if row is not None:
                existing = KnowledgeGraphRetrievalIndexManifest.model_validate_json(
                    str(row["manifest_json"])
                )
                self._validate_complete(existing)
                self._connection.execute("COMMIT")
                return existing, True
            self._connection.executescript(
                """
                DELETE FROM knowledge_graph_seed_fts;
                DELETE FROM knowledge_graph_edges;
                DELETE FROM knowledge_graph_nodes;
                DELETE FROM knowledge_graph_units;
                DELETE FROM knowledge_graph_manifests;
                """
            )
            for unit in build.units:
                self._connection.execute(
                    """
                    INSERT INTO knowledge_graph_units
                    (retrieval_unit_id, source_record_id, record_type, source_order, unit_json)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        unit.retrieval_unit_id,
                        unit.source_record_id,
                        unit.record_type.value,
                        unit.source_order,
                        unit.model_dump_json(),
                    ),
                )
            for node in build.nodes:
                self._connection.execute(
                    """
                    INSERT INTO knowledge_graph_nodes
                    (node_id, node_type, label, normalized_label, source_order, node_json)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        node.node_id,
                        node.node_type,
                        node.label,
                        node.normalized_label,
                        node.source_order,
                        node.model_dump_json(),
                    ),
                )
                self._connection.execute(
                    "INSERT INTO knowledge_graph_seed_fts (node_id, label) VALUES (?, ?)",
                    (node.node_id, node.label),
                )
            for edge in build.edges:
                self._connection.execute(
                    "INSERT INTO knowledge_graph_edges (edge_id, edge_json) VALUES (?, ?)",
                    (edge.edge_id, edge.model_dump_json()),
                )
            self._validate_written_build(manifest)
            self._connection.execute(
                """
                INSERT INTO knowledge_graph_manifests (index_manifest_id, manifest_json)
                VALUES (?, ?)
                """,
                (manifest.index_manifest_id, manifest.model_dump_json()),
            )
            self._connection.execute("COMMIT")
            return manifest, False
        except Exception:
            self._connection.execute("ROLLBACK")
            raise

    def get_complete_manifest(self) -> KnowledgeGraphRetrievalIndexManifest | None:
        row = self._connection.execute(
            "SELECT manifest_json FROM knowledge_graph_manifests ORDER BY index_manifest_id"
        ).fetchone()
        if row is None:
            return None
        try:
            manifest = KnowledgeGraphRetrievalIndexManifest.model_validate_json(
                str(row["manifest_json"])
            )
            self._validate_complete(manifest)
            return manifest
        except (TypeError, ValueError) as exc:
            raise KnowledgeGraphRetrievalError(
                KnowledgeGraphRetrievalFailureCode.INDEX_CORRUPT,
                "Knowledge-Graph index manifest is corrupt.",
            ) from exc

    def exact_seed_matches(
        self, manifest: KnowledgeGraphRetrievalIndexManifest, normalized_seed: str
    ) -> tuple[KnowledgeGraphSeedMatch, ...]:
        del manifest
        placeholders = ", ".join("?" for _ in _SEED_NODE_TYPES)
        rows = self._connection.execute(
            f"""
            SELECT node_id, node_type, label
            FROM knowledge_graph_nodes
            WHERE normalized_label = ? AND node_type IN ({placeholders})
            ORDER BY source_order, node_id
            """,
            (normalized_seed, *_SEED_NODE_TYPES),
        ).fetchall()
        return tuple(
            KnowledgeGraphSeedMatch(
                node_id=str(row["node_id"]),
                node_type=str(row["node_type"]),
                label=str(row["label"]),
                channel=RetrievalChannel.EXACT,
                channel_rank=index + 1,
            )
            for index, row in enumerate(rows)
        )

    def lexical_seed_matches(
        self, manifest: KnowledgeGraphRetrievalIndexManifest, seed_text: str
    ) -> tuple[KnowledgeGraphSeedMatch, ...]:
        del manifest
        terms = re.findall(r"\w+", seed_text, flags=re.UNICODE)
        if not terms:
            return ()
        placeholders = ", ".join("?" for _ in _SEED_NODE_TYPES)
        try:
            rows = self._connection.execute(
                f"""
                SELECT f.node_id, n.node_type, n.label, bm25(knowledge_graph_seed_fts) AS score
                FROM knowledge_graph_seed_fts f
                JOIN knowledge_graph_nodes n ON n.node_id = f.node_id
                WHERE knowledge_graph_seed_fts MATCH ? AND n.node_type IN ({placeholders})
                ORDER BY score, n.source_order, n.node_id
                """,
                (" OR ".join(terms), *_SEED_NODE_TYPES),
            ).fetchall()
        except sqlite3.OperationalError as exc:
            raise KnowledgeGraphRetrievalError(
                KnowledgeGraphRetrievalFailureCode.INDEX_CORRUPT,
                "Knowledge-Graph lexical index rejected the seed phrase.",
            ) from exc
        return tuple(
            KnowledgeGraphSeedMatch(
                node_id=str(row["node_id"]),
                node_type=str(row["node_type"]),
                label=str(row["label"]),
                channel=RetrievalChannel.LEXICAL,
                channel_rank=index + 1,
                raw_score=float(row["score"]),
            )
            for index, row in enumerate(rows)
        )

    def load_edges(
        self, manifest: KnowledgeGraphRetrievalIndexManifest
    ) -> tuple[KnowledgeGraphEdge, ...]:
        del manifest
        rows = self._connection.execute(
            "SELECT edge_json FROM knowledge_graph_edges ORDER BY edge_id"
        ).fetchall()
        try:
            return tuple(
                KnowledgeGraphEdge.model_validate_json(str(row["edge_json"])) for row in rows
            )
        except (TypeError, ValueError) as exc:
            raise KnowledgeGraphRetrievalError(
                KnowledgeGraphRetrievalFailureCode.INDEX_CORRUPT,
                "Knowledge-Graph edge payload is corrupt.",
            ) from exc

    def save_query_record(self, record: KnowledgeGraphRetrievalQueryRecord) -> None:
        self._connection.execute(
            """
            INSERT OR REPLACE INTO knowledge_graph_query_records
            (retrieval_query_id, record_json) VALUES (?, ?)
            """,
            (record.retrieval_query_id, record.model_dump_json()),
        )
        self._connection.commit()

    def _validate_complete(self, manifest: KnowledgeGraphRetrievalIndexManifest) -> None:
        if manifest.publication_status != "complete":
            raise KnowledgeGraphRetrievalError(
                KnowledgeGraphRetrievalFailureCode.INDEX_CORRUPT,
                "Knowledge-Graph index manifest is incomplete.",
            )

    def _validate_written_build(self, manifest: KnowledgeGraphRetrievalIndexManifest) -> None:
        counts = (
            self._connection.execute("SELECT COUNT(*) FROM knowledge_graph_units").fetchone()[0],
            self._connection.execute("SELECT COUNT(*) FROM knowledge_graph_nodes").fetchone()[0],
            self._connection.execute("SELECT COUNT(*) FROM knowledge_graph_edges").fetchone()[0],
        )
        expected = (manifest.unit_count, manifest.node_count, manifest.edge_count)
        if counts != expected:
            raise KnowledgeGraphRetrievalError(
                KnowledgeGraphRetrievalFailureCode.INDEX_CORRUPT,
                "Knowledge-Graph index write count does not match manifest.",
            )

    def _initialize(self) -> None:
        self._connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS knowledge_graph_manifests (
                index_manifest_id TEXT PRIMARY KEY NOT NULL,
                manifest_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS knowledge_graph_units (
                retrieval_unit_id TEXT PRIMARY KEY NOT NULL,
                source_record_id TEXT NOT NULL,
                record_type TEXT NOT NULL,
                source_order INTEGER NOT NULL,
                unit_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS knowledge_graph_nodes (
                node_id TEXT PRIMARY KEY NOT NULL,
                node_type TEXT NOT NULL,
                label TEXT NOT NULL,
                normalized_label TEXT NOT NULL,
                source_order INTEGER NOT NULL,
                node_json TEXT NOT NULL
            );
            CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_graph_seed_fts USING fts5(
                node_id UNINDEXED,
                label
            );
            CREATE TABLE IF NOT EXISTS knowledge_graph_edges (
                edge_id TEXT PRIMARY KEY NOT NULL,
                edge_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS knowledge_graph_query_records (
                retrieval_query_id TEXT PRIMARY KEY NOT NULL,
                record_json TEXT NOT NULL
            );
            """
        )
        self._connection.commit()
