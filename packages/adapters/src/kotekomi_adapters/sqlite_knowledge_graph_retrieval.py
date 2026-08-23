"""Disposable SQLite projection for Knowledge-Graph traversal retrieval."""

from __future__ import annotations

import re
import sqlite3
from datetime import datetime
from pathlib import Path

from kotekomi_application.evidence_graph_projection import (
    EvidenceGraphError,
    EvidenceGraphFailureCode,
    EvidenceGraphProjectionBuildInput,
)
from kotekomi_application.knowledge_graph_retrieval import (
    KnowledgeGraphProjectionBuildInput,
    KnowledgeGraphRetrievalError,
    KnowledgeGraphRetrievalFailureCode,
    KnowledgeGraphSeedMatch,
)
from kotekomi_domain import (
    EvidenceGraphContribution,
    EvidenceGraphEdge,
    EvidenceGraphExplanationRecord,
    EvidenceGraphLineageCluster,
    EvidenceGraphProjectionManifest,
    EvidenceGraphViewKind,
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

    def delete_evidence_graph_projection(
        self,
        view_kind: EvidenceGraphViewKind = EvidenceGraphViewKind.CURRENT,
        as_of: datetime | None = None,
    ) -> None:
        manifest_ids = self._evidence_graph_manifest_ids(view_kind, as_of)
        self._delete_evidence_graph_manifests(manifest_ids)
        self._connection.commit()

    def publish_evidence_graph(
        self, build: EvidenceGraphProjectionBuildInput
    ) -> tuple[EvidenceGraphProjectionManifest, bool]:
        manifest = build.manifest
        if len({item.evidence_graph_edge_id for item in build.edges}) != len(build.edges):
            raise EvidenceGraphError(
                EvidenceGraphFailureCode.PROJECTION_CORRUPT,
                "Evidence graph edges are not unique.",
            )
        if len({item.contribution_id for item in build.contributions}) != len(build.contributions):
            raise EvidenceGraphError(
                EvidenceGraphFailureCode.PROJECTION_CORRUPT,
                "Evidence graph contributions are not unique.",
            )
        if len({item.lineage_cluster_id for item in build.lineage_clusters}) != len(
            build.lineage_clusters
        ):
            raise EvidenceGraphError(
                EvidenceGraphFailureCode.PROJECTION_CORRUPT,
                "Evidence graph lineage clusters are not unique.",
            )
        if any(
            item.source_snapshot_digest != manifest.source_snapshot_digest
            for item in build.lineage_clusters
        ):
            raise EvidenceGraphError(
                EvidenceGraphFailureCode.PROJECTION_CORRUPT,
                "Evidence graph lineage cluster does not belong to the projection snapshot.",
            )
        self._connection.execute("BEGIN IMMEDIATE")
        try:
            row = self._connection.execute(
                "SELECT manifest_json FROM evidence_graph_manifests "
                "WHERE projection_manifest_id = ?",
                (manifest.projection_manifest_id,),
            ).fetchone()
            if row is not None:
                existing = EvidenceGraphProjectionManifest.model_validate_json(
                    str(row["manifest_json"])
                )
                self._validate_evidence_graph_manifest(existing)
                self._validate_evidence_graph_written_build(existing)
                self._connection.execute("COMMIT")
                return existing, True
            self._delete_evidence_graph_manifests(
                self._evidence_graph_manifest_ids(manifest.view_kind, manifest.as_of)
            )
            for edge in build.edges:
                self._connection.execute(
                    """
                    INSERT INTO evidence_graph_edges
                    (projection_manifest_id, evidence_graph_edge_id, relationship_id, edge_json)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        manifest.projection_manifest_id,
                        edge.evidence_graph_edge_id,
                        edge.relationship_id,
                        edge.model_dump_json(),
                    ),
                )
            for contribution in build.contributions:
                self._connection.execute(
                    """
                    INSERT INTO evidence_graph_contributions
                    (projection_manifest_id, contribution_id, evidence_graph_edge_id,
                     contribution_json)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        manifest.projection_manifest_id,
                        contribution.contribution_id,
                        contribution.evidence_graph_edge_id,
                        contribution.model_dump_json(),
                    ),
                )
            for cluster in build.lineage_clusters:
                self._connection.execute(
                    """
                    INSERT INTO evidence_graph_lineage_clusters
                    (projection_manifest_id, lineage_cluster_id, cluster_json) VALUES (?, ?, ?)
                    """,
                    (
                        manifest.projection_manifest_id,
                        cluster.lineage_cluster_id,
                        cluster.model_dump_json(),
                    ),
                )
            counts = (
                self._connection.execute(
                    "SELECT COUNT(*) FROM evidence_graph_edges WHERE projection_manifest_id = ?",
                    (manifest.projection_manifest_id,),
                ).fetchone()[0],
                self._connection.execute(
                    "SELECT COUNT(*) FROM evidence_graph_contributions "
                    "WHERE projection_manifest_id = ?",
                    (manifest.projection_manifest_id,),
                ).fetchone()[0],
                self._connection.execute(
                    "SELECT COUNT(*) FROM evidence_graph_lineage_clusters "
                    "WHERE projection_manifest_id = ?",
                    (manifest.projection_manifest_id,),
                ).fetchone()[0],
            )
            if counts != (
                manifest.edge_count,
                manifest.contribution_count,
                manifest.lineage_cluster_count,
            ):
                raise EvidenceGraphError(
                    EvidenceGraphFailureCode.PROJECTION_CORRUPT,
                    "Evidence graph write count does not match the projection manifest.",
                )
            self._connection.execute(
                """
                INSERT INTO evidence_graph_manifests
                (projection_manifest_id, view_kind, as_of, manifest_json)
                VALUES (?, ?, ?, ?)
                """,
                (
                    manifest.projection_manifest_id,
                    manifest.view_kind.value,
                    _timestamp(manifest.as_of),
                    manifest.model_dump_json(),
                ),
            )
            self._connection.execute("COMMIT")
            return manifest, False
        except Exception:
            self._connection.execute("ROLLBACK")
            raise

    def get_complete_evidence_graph_manifest(
        self,
        view_kind: EvidenceGraphViewKind = EvidenceGraphViewKind.CURRENT,
        as_of: datetime | None = None,
    ) -> EvidenceGraphProjectionManifest | None:
        row = self._connection.execute(
            "SELECT manifest_json FROM evidence_graph_manifests "
            "WHERE view_kind = ? AND ((as_of IS NULL AND ? IS NULL) OR as_of = ?) "
            "ORDER BY projection_manifest_id",
            (view_kind.value, _timestamp(as_of), _timestamp(as_of)),
        ).fetchone()
        if row is None:
            return None
        try:
            manifest = EvidenceGraphProjectionManifest.model_validate_json(
                str(row["manifest_json"])
            )
            self._validate_evidence_graph_manifest(manifest)
            self._validate_evidence_graph_written_build(manifest)
            return manifest
        except (TypeError, ValueError) as exc:
            raise EvidenceGraphError(
                EvidenceGraphFailureCode.PROJECTION_CORRUPT,
                "Evidence graph projection manifest is corrupt.",
            ) from exc

    def load_evidence_graph_edge(
        self, manifest: EvidenceGraphProjectionManifest, relationship_id: str
    ) -> EvidenceGraphEdge | None:
        row = self._connection.execute(
            "SELECT edge_json FROM evidence_graph_edges "
            "WHERE projection_manifest_id = ? AND relationship_id = ?",
            (manifest.projection_manifest_id, relationship_id),
        ).fetchone()
        if row is None:
            return None
        try:
            return EvidenceGraphEdge.model_validate_json(str(row["edge_json"]))
        except (TypeError, ValueError) as exc:
            raise EvidenceGraphError(
                EvidenceGraphFailureCode.PROJECTION_CORRUPT,
                "Evidence graph edge payload is corrupt.",
            ) from exc

    def load_evidence_graph_contributions(
        self, manifest: EvidenceGraphProjectionManifest, edge_id: str
    ) -> tuple[EvidenceGraphContribution, ...]:
        rows = self._connection.execute(
            """
            SELECT contribution_json FROM evidence_graph_contributions
            WHERE projection_manifest_id = ? AND evidence_graph_edge_id = ? ORDER BY contribution_id
            """,
            (manifest.projection_manifest_id, edge_id),
        ).fetchall()
        try:
            return tuple(
                EvidenceGraphContribution.model_validate_json(str(row["contribution_json"]))
                for row in rows
            )
        except (TypeError, ValueError) as exc:
            raise EvidenceGraphError(
                EvidenceGraphFailureCode.PROJECTION_CORRUPT,
                "Evidence graph contribution payload is corrupt.",
            ) from exc

    def load_evidence_graph_lineage_clusters(
        self, manifest: EvidenceGraphProjectionManifest, lineage_cluster_ids: tuple[str, ...]
    ) -> tuple[EvidenceGraphLineageCluster, ...]:
        if not lineage_cluster_ids:
            return ()
        placeholders = ", ".join("?" for _ in lineage_cluster_ids)
        rows = self._connection.execute(
            f"""
            SELECT cluster_json FROM evidence_graph_lineage_clusters
            WHERE projection_manifest_id = ? AND lineage_cluster_id IN ({placeholders})
            ORDER BY lineage_cluster_id
            """,
            (manifest.projection_manifest_id, *lineage_cluster_ids),
        ).fetchall()
        try:
            clusters = tuple(
                EvidenceGraphLineageCluster.model_validate_json(str(row["cluster_json"]))
                for row in rows
            )
            if any(
                item.source_snapshot_digest != manifest.source_snapshot_digest
                for item in clusters
            ):
                raise ValueError("Evidence graph lineage cluster has another source snapshot.")
            return clusters
        except (TypeError, ValueError) as exc:
            raise EvidenceGraphError(
                EvidenceGraphFailureCode.PROJECTION_CORRUPT,
                "Evidence graph lineage cluster payload is corrupt.",
            ) from exc

    def save_evidence_graph_explanation(self, record: EvidenceGraphExplanationRecord) -> None:
        self._connection.execute(
            """
            INSERT OR REPLACE INTO evidence_graph_explanation_records
            (explanation_id, projection_manifest_id, record_json) VALUES (?, ?, ?)
            """,
            (record.explanation_id, record.projection_manifest_id, record.model_dump_json()),
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

    def _validate_evidence_graph_manifest(self, manifest: EvidenceGraphProjectionManifest) -> None:
        if manifest.publication_status != "complete":
            raise EvidenceGraphError(
                EvidenceGraphFailureCode.PROJECTION_CORRUPT,
                "Evidence graph projection manifest is incomplete.",
            )

    def _validate_evidence_graph_written_build(
        self, manifest: EvidenceGraphProjectionManifest
    ) -> None:
        counts = (
            self._connection.execute(
                "SELECT COUNT(*) FROM evidence_graph_edges WHERE projection_manifest_id = ?",
                (manifest.projection_manifest_id,),
            ).fetchone()[0],
            self._connection.execute(
                "SELECT COUNT(*) FROM evidence_graph_contributions "
                "WHERE projection_manifest_id = ?",
                (manifest.projection_manifest_id,),
            ).fetchone()[0],
            self._connection.execute(
                "SELECT COUNT(*) FROM evidence_graph_lineage_clusters "
                "WHERE projection_manifest_id = ?",
                (manifest.projection_manifest_id,),
            ).fetchone()[0],
        )
        if counts != (
            manifest.edge_count,
            manifest.contribution_count,
            manifest.lineage_cluster_count,
        ):
            raise EvidenceGraphError(
                EvidenceGraphFailureCode.PROJECTION_CORRUPT,
                "Evidence graph rows do not match the projection manifest.",
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
        rows = self._connection.execute("PRAGMA table_info(evidence_graph_edges)").fetchall()
        columns = {str(row["name"]) for row in rows}
        if columns and "projection_manifest_id" not in columns:
            self._connection.executescript(
                """
                DROP TABLE IF EXISTS evidence_graph_explanation_records;
                DROP TABLE IF EXISTS evidence_graph_lineage_clusters;
                DROP TABLE IF EXISTS evidence_graph_contributions;
                DROP TABLE IF EXISTS evidence_graph_edges;
                DROP TABLE IF EXISTS evidence_graph_manifests;
                """
            )
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
            CREATE TABLE IF NOT EXISTS evidence_graph_manifests (
                projection_manifest_id TEXT PRIMARY KEY NOT NULL,
                view_kind TEXT NOT NULL,
                as_of TEXT,
                manifest_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS evidence_graph_edges (
                projection_manifest_id TEXT NOT NULL,
                evidence_graph_edge_id TEXT NOT NULL,
                relationship_id TEXT NOT NULL,
                edge_json TEXT NOT NULL,
                PRIMARY KEY (projection_manifest_id, evidence_graph_edge_id),
                UNIQUE (projection_manifest_id, relationship_id)
            );
            CREATE TABLE IF NOT EXISTS evidence_graph_contributions (
                projection_manifest_id TEXT NOT NULL,
                contribution_id TEXT NOT NULL,
                evidence_graph_edge_id TEXT NOT NULL,
                contribution_json TEXT NOT NULL,
                PRIMARY KEY (projection_manifest_id, contribution_id)
            );
            CREATE INDEX IF NOT EXISTS evidence_graph_contributions_by_edge
                ON evidence_graph_contributions
                (projection_manifest_id, evidence_graph_edge_id, contribution_id);
            CREATE TABLE IF NOT EXISTS evidence_graph_explanation_records (
                explanation_id TEXT PRIMARY KEY NOT NULL,
                projection_manifest_id TEXT NOT NULL,
                record_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS evidence_graph_lineage_clusters (
                projection_manifest_id TEXT NOT NULL,
                lineage_cluster_id TEXT NOT NULL,
                cluster_json TEXT NOT NULL,
                PRIMARY KEY (projection_manifest_id, lineage_cluster_id)
            );
            """
        )
        self._connection.commit()

    def _evidence_graph_manifest_ids(
        self, view_kind: EvidenceGraphViewKind, as_of: datetime | None
    ) -> tuple[str, ...]:
        rows = self._connection.execute(
            "SELECT projection_manifest_id FROM evidence_graph_manifests "
            "WHERE view_kind = ? AND ((as_of IS NULL AND ? IS NULL) OR as_of = ?)",
            (view_kind.value, _timestamp(as_of), _timestamp(as_of)),
        ).fetchall()
        return tuple(str(row["projection_manifest_id"]) for row in rows)

    def _delete_evidence_graph_manifests(self, manifest_ids: tuple[str, ...]) -> None:
        if not manifest_ids:
            return
        placeholders = ", ".join("?" for _ in manifest_ids)
        self._connection.execute(
            f"DELETE FROM evidence_graph_explanation_records "
            f"WHERE projection_manifest_id IN ({placeholders})",
            manifest_ids,
        )
        for table in (
            "evidence_graph_lineage_clusters",
            "evidence_graph_contributions",
            "evidence_graph_edges",
            "evidence_graph_manifests",
        ):
            self._connection.execute(
                f"DELETE FROM {table} WHERE projection_manifest_id IN ({placeholders})",
                manifest_ids,
            )


def _timestamp(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None
