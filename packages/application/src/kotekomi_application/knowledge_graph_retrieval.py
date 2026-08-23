"""Derived, evidence-linked Knowledge-Graph traversal over current Ledger state."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Protocol

from kotekomi_domain import (
    Actor,
    Assertion,
    AssertionStatus,
    AssertionType,
    DocumentRepresentationBundle,
    Entity,
    Event,
    EvidenceTarget,
    KnowledgeGraphEdge,
    KnowledgeGraphNode,
    KnowledgeGraphRetrievalHit,
    KnowledgeGraphRetrievalIndexManifest,
    KnowledgeGraphRetrievalQueryRecord,
    KnowledgeGraphRetrievalUnit,
    KnowledgeGraphSeedCandidate,
    KnowledgeGraphTraversalPath,
    LedgerContextResult,
    LedgerRetrievalRecordType,
    Organization,
    Outcome,
    Place,
    Relationship,
    RetrievalChannel,
    RetrievalChannelObservation,
)

from kotekomi_application.context_planning import (
    ContextManifestInput,
    ContextModelProfile,
    ContextPlanningLedger,
    ContextTokenizer,
    RetrievalSelectionAnalysisUnitInput,
    build_context_manifest,
    create_analysis_unit_from_retrieval_selection,
)
from kotekomi_application.document_retrieval import normalize_exact_text
from kotekomi_application.ports import AcceptedCanonicalRecord

KNOWLEDGE_GRAPH_UNIT_POLICY_ID = "knowledge_graph_current_unit_v1"
KNOWLEDGE_GRAPH_PROJECTION_POLICY_ID = "knowledge_graph_current_projection_v1"
KNOWLEDGE_GRAPH_QUERY_POLICY_ID = "knowledge_graph_current_traversal_v1"
KNOWLEDGE_GRAPH_BUILDER_VERSION = "dr6_knowledge_graph_projection_v1"
KNOWLEDGE_GRAPH_CONTEXT_PLANNER_POLICY_ID = "knowledge_graph_retrieval_selection_v1"


class KnowledgeGraphRetrievalFailureCode(StrEnum):
    INDEX_NOT_FOUND = "knowledge_graph_index_not_found"
    INDEX_STALE = "knowledge_graph_index_stale"
    INDEX_CORRUPT = "knowledge_graph_index_corrupt"
    SEED_EMPTY = "knowledge_graph_seed_empty"
    SEED_MISSING = "knowledge_graph_seed_missing"
    SEED_AMBIGUOUS = "knowledge_graph_seed_ambiguous"
    EVIDENCE_MISSING = "knowledge_graph_evidence_missing"
    CONTEXT_PLANNING_FAILED = "knowledge_graph_context_planning_failed"


class KnowledgeGraphRetrievalError(ValueError):
    def __init__(
        self,
        code: KnowledgeGraphRetrievalFailureCode,
        message: str,
        *,
        seed_candidates: tuple[KnowledgeGraphSeedCandidate, ...] = (),
    ) -> None:
        super().__init__(message)
        self.code = code
        self.seed_candidates = seed_candidates


@dataclass(frozen=True)
class BuildKnowledgeGraphProjectionCommand:
    pass


@dataclass(frozen=True)
class QueryKnowledgeGraphCommand:
    seed_text: str
    maximum_hops: int = 2
    maximum_hits: int = 10
    context_profile_id: str = "retrieval-validation-v1"
    policy_id: str = KNOWLEDGE_GRAPH_QUERY_POLICY_ID


@dataclass(frozen=True)
class KnowledgeGraphProjectionBuildInput:
    manifest: KnowledgeGraphRetrievalIndexManifest
    units: tuple[KnowledgeGraphRetrievalUnit, ...]
    nodes: tuple[KnowledgeGraphNode, ...]
    edges: tuple[KnowledgeGraphEdge, ...]


@dataclass(frozen=True)
class KnowledgeGraphSeedMatch:
    node_id: str
    node_type: str
    label: str
    channel: RetrievalChannel
    channel_rank: int
    raw_score: float | None = None


@dataclass(frozen=True)
class BuildKnowledgeGraphProjectionResult:
    status: str
    index_manifest_id: str | None
    unit_count: int
    node_count: int
    edge_count: int
    content_fingerprint: str | None
    reused_existing_manifest: bool
    failure: KnowledgeGraphRetrievalFailureCode | None = None


@dataclass(frozen=True)
class QueryKnowledgeGraphResult:
    status: str
    retrieval_query_id: str | None
    index_manifest_id: str | None
    seed_candidates: tuple[KnowledgeGraphSeedCandidate, ...]
    hits: tuple[KnowledgeGraphRetrievalHit, ...]
    selected_record_ids: tuple[str, ...]
    context_results: tuple[LedgerContextResult, ...]
    failure: KnowledgeGraphRetrievalFailureCode | None = None
    query_policy_id: str | None = None


class KnowledgeGraphStateLedger(Protocol):
    def list_accepted_canonical_records(self) -> tuple[AcceptedCanonicalRecord, ...]: ...


class KnowledgeGraphLedger(KnowledgeGraphStateLedger, ContextPlanningLedger, Protocol):
    def get_assertion(self, record_id: str) -> Assertion | None: ...
    def get_evidence_target(self, record_id: str) -> EvidenceTarget | None: ...
    def get_document_representation_bundle(
        self, record_id: str
    ) -> DocumentRepresentationBundle | None: ...


class KnowledgeGraphProjectionPort(Protocol):
    def publish(
        self, build: KnowledgeGraphProjectionBuildInput
    ) -> tuple[KnowledgeGraphRetrievalIndexManifest, bool]: ...
    def get_complete_manifest(self) -> KnowledgeGraphRetrievalIndexManifest | None: ...
    def exact_seed_matches(
        self, manifest: KnowledgeGraphRetrievalIndexManifest, normalized_seed: str
    ) -> tuple[KnowledgeGraphSeedMatch, ...]: ...
    def lexical_seed_matches(
        self, manifest: KnowledgeGraphRetrievalIndexManifest, seed_text: str
    ) -> tuple[KnowledgeGraphSeedMatch, ...]: ...
    def load_edges(
        self, manifest: KnowledgeGraphRetrievalIndexManifest
    ) -> tuple[KnowledgeGraphEdge, ...]: ...
    def save_query_record(self, record: KnowledgeGraphRetrievalQueryRecord) -> None: ...


def build_knowledge_graph_projection(
    command: BuildKnowledgeGraphProjectionCommand,
    *,
    ledger_repository: KnowledgeGraphLedger,
    projection: KnowledgeGraphProjectionPort,
) -> BuildKnowledgeGraphProjectionResult:
    del command
    try:
        units, nodes, edges, snapshot = build_knowledge_graph_retrieval_state(ledger_repository)
        manifest = _manifest(snapshot, units, nodes, edges)
        published, reused = projection.publish(
            KnowledgeGraphProjectionBuildInput(manifest, units, nodes, edges)
        )
        return BuildKnowledgeGraphProjectionResult(
            status="complete",
            index_manifest_id=published.index_manifest_id,
            unit_count=len(units),
            node_count=len(nodes),
            edge_count=len(edges),
            content_fingerprint=published.content_fingerprint,
            reused_existing_manifest=reused,
        )
    except KnowledgeGraphRetrievalError as exc:
        return BuildKnowledgeGraphProjectionResult(
            status="failed",
            index_manifest_id=None,
            unit_count=0,
            node_count=0,
            edge_count=0,
            content_fingerprint=None,
            reused_existing_manifest=False,
            failure=exc.code,
        )


def query_knowledge_graph(
    command: QueryKnowledgeGraphCommand,
    *,
    ledger_repository: KnowledgeGraphLedger,
    projection: KnowledgeGraphProjectionPort,
    tokenizer: ContextTokenizer,
) -> QueryKnowledgeGraphResult:
    try:
        _validate_query(command)
        normalized_seed = normalize_exact_text(command.seed_text)
        units, _, _, snapshot = build_knowledge_graph_retrieval_state(ledger_repository)
        manifest = projection.get_complete_manifest()
        if manifest is None:
            raise KnowledgeGraphRetrievalError(
                KnowledgeGraphRetrievalFailureCode.INDEX_NOT_FOUND,
                "No complete Knowledge-Graph retrieval projection exists.",
            )
        if manifest.source_snapshot_digest != snapshot:
            raise KnowledgeGraphRetrievalError(
                KnowledgeGraphRetrievalFailureCode.INDEX_STALE,
                "Knowledge-Graph retrieval projection does not match current Ledger state.",
            )
        try:
            seed_candidates, seed_id = _resolve_seed(
                command.seed_text, normalized_seed, manifest, projection
            )
        except KnowledgeGraphRetrievalError as exc:
            record = KnowledgeGraphRetrievalQueryRecord(
                retrieval_query_id=_query_id(command, manifest.index_manifest_id, snapshot),
                source_snapshot_digest=snapshot,
                seed_text=command.seed_text,
                normalized_seed_text=normalized_seed,
                query_policy_id=command.policy_id,
                index_manifest_id=manifest.index_manifest_id,
                maximum_hops=command.maximum_hops,
                seed_candidates=exc.seed_candidates,
                failure_code=exc.code.value,
            )
            projection.save_query_record(record)
            return QueryKnowledgeGraphResult(
                status="failed",
                retrieval_query_id=record.retrieval_query_id,
                index_manifest_id=manifest.index_manifest_id,
                seed_candidates=exc.seed_candidates,
                hits=(),
                selected_record_ids=(),
                context_results=(),
                failure=exc.code,
                query_policy_id=command.policy_id,
            )
        edges = projection.load_edges(manifest)
        hits = _traverse(
            seed_id,
            units,
            edges,
            manifest.index_manifest_id,
            command.maximum_hops,
            command.maximum_hits,
            ledger_repository,
        )
        contexts = _context_results(hits, command, ledger_repository, tokenizer)
        record = KnowledgeGraphRetrievalQueryRecord(
            retrieval_query_id=_query_id(command, manifest.index_manifest_id, snapshot),
            source_snapshot_digest=snapshot,
            seed_text=command.seed_text,
            normalized_seed_text=normalized_seed,
            query_policy_id=command.policy_id,
            index_manifest_id=manifest.index_manifest_id,
            maximum_hops=command.maximum_hops,
            seed_candidates=seed_candidates,
            candidate_hits=hits,
            selected_record_ids=tuple(hit.source_record_id for hit in hits if hit.selected),
            context_results=contexts,
        )
        projection.save_query_record(record)
        return QueryKnowledgeGraphResult(
            status="complete",
            retrieval_query_id=record.retrieval_query_id,
            index_manifest_id=manifest.index_manifest_id,
            seed_candidates=seed_candidates,
            hits=hits,
            selected_record_ids=record.selected_record_ids,
            context_results=contexts,
            query_policy_id=command.policy_id,
        )
    except KnowledgeGraphRetrievalError as exc:
        return QueryKnowledgeGraphResult(
            status="failed",
            retrieval_query_id=None,
            index_manifest_id=None,
            seed_candidates=(),
            hits=(),
            selected_record_ids=(),
            context_results=(),
            failure=exc.code,
        )


def build_knowledge_graph_retrieval_state(
    ledger_repository: KnowledgeGraphStateLedger,
) -> tuple[
    tuple[KnowledgeGraphRetrievalUnit, ...],
    tuple[KnowledgeGraphNode, ...],
    tuple[KnowledgeGraphEdge, ...],
    str,
]:
    records = ledger_repository.list_accepted_canonical_records()
    snapshot = _digest(
        tuple(
            (type(item).__name__, item.id, item.model_dump(mode="json"))
            for item in sorted(records, key=lambda item: (type(item).__name__, item.id))
        )
    )
    current_assertions = _current_assertions(records)
    current_assertion_ids = {item.id for item in current_assertions}
    knowledge_records = (
        tuple(
            item
            for item in records
            if isinstance(item, (Relationship, Outcome))
            and set(item.assertion_ids).issubset(current_assertion_ids)
        )
        + current_assertions
    )
    knowledge_records = tuple(sorted(knowledge_records, key=lambda item: item.id))
    node_records = tuple(
        item for item in records if isinstance(item, (Entity, Actor, Organization, Event, Place))
    )
    nodes = _nodes(node_records, knowledge_records)
    node_ids = {item.node_id for item in nodes}
    units = tuple(_unit(record, snapshot, index) for index, record in enumerate(knowledge_records))
    edges = _edges(knowledge_records, node_ids)
    return units, nodes, edges, snapshot


def _current_assertions(records: tuple[AcceptedCanonicalRecord, ...]) -> tuple[Assertion, ...]:
    assertions = tuple(item for item in records if isinstance(item, Assertion))
    superseded = {
        item.supersedes_assertion_id for item in assertions if item.supersedes_assertion_id
    }
    return tuple(
        item
        for item in assertions
        if item.status
        not in {AssertionStatus.PROPOSED, AssertionStatus.SUPERSEDED, AssertionStatus.RETRACTED}
        and item.id not in superseded
    )


def _nodes(
    node_records: tuple[Entity | Actor | Organization | Event | Place, ...],
    knowledge_records: tuple[Assertion | Relationship | Outcome, ...],
) -> tuple[KnowledgeGraphNode, ...]:
    result: list[KnowledgeGraphNode] = []
    for item in node_records:
        label = item.canonical_name if isinstance(item, Entity) else item.name
        result.append(
            KnowledgeGraphNode(
                node_id=item.id,
                node_type=type(item).__name__,
                label=label,
                normalized_label=normalize_exact_text(label),
                source_order=len(result),
            )
        )
    for item in knowledge_records:
        label = item.predicate if isinstance(item, (Assertion, Relationship)) else item.description
        result.append(
            KnowledgeGraphNode(
                node_id=item.id,
                node_type=type(item).__name__,
                label=label,
                normalized_label=normalize_exact_text(label),
                source_order=len(result),
            )
        )
    return tuple(sorted(result, key=lambda item: item.node_id))


def _unit(
    record: Assertion | Relationship | Outcome, snapshot: str, source_order: int
) -> KnowledgeGraphRetrievalUnit:
    record_type = _record_type(record)
    assertion_ids = (record.id,) if isinstance(record, Assertion) else record.assertion_ids
    fingerprint = _digest(
        {
            "record_id": record.id,
            "record_type": record_type.value,
            "assertion_ids": assertion_ids,
            "snapshot": snapshot,
            "source_order": source_order,
            "policy": KNOWLEDGE_GRAPH_UNIT_POLICY_ID,
        }
    )
    return KnowledgeGraphRetrievalUnit(
        retrieval_unit_id=f"gru_{fingerprint[:24]}",
        source_record_id=record.id,
        record_type=record_type,
        evidence_assertion_ids=assertion_ids,
        source_snapshot_digest=snapshot,
        source_order=source_order,
        unit_policy_id=KNOWLEDGE_GRAPH_UNIT_POLICY_ID,
        unit_fingerprint=fingerprint,
    )


def _edges(
    records: tuple[Assertion | Relationship | Outcome, ...], node_ids: set[str]
) -> tuple[KnowledgeGraphEdge, ...]:
    edges: list[KnowledgeGraphEdge] = []
    for record in records:
        assertion_ids = (record.id,) if isinstance(record, Assertion) else record.assertion_ids
        destinations: list[tuple[str, str]] = []
        if isinstance(record, Assertion):
            destinations.append((record.subject_entity_id, "assertion_subject"))
            if record.object_entity_id is not None:
                destinations.append((record.object_entity_id, "assertion_object"))
        elif isinstance(record, Relationship):
            destinations.extend(
                (
                    (record.subject_id, "relationship_subject"),
                    (record.object_id, "relationship_object"),
                )
            )
            destinations.extend((item, "relationship_assertion") for item in record.assertion_ids)
        else:
            destinations.extend((item, "outcome_actor") for item in record.actor_ids)
            destinations.extend((item, "outcome_organization") for item in record.organization_ids)
            destinations.extend((item, "outcome_event") for item in record.event_ids)
            destinations.extend((item, "outcome_assertion") for item in record.assertion_ids)
        for target_id, edge_type in destinations:
            if record.id not in node_ids or target_id not in node_ids:
                raise KnowledgeGraphRetrievalError(
                    KnowledgeGraphRetrievalFailureCode.INDEX_CORRUPT,
                    "Knowledge-Graph edge references a node outside the current projection.",
                )
            fingerprint = _digest(
                (
                    record.id,
                    target_id,
                    edge_type,
                    assertion_ids,
                    KNOWLEDGE_GRAPH_PROJECTION_POLICY_ID,
                )
            )
            edges.append(
                KnowledgeGraphEdge(
                    edge_id=f"gre_{fingerprint[:24]}",
                    source_node_id=record.id,
                    target_node_id=target_id,
                    edge_type=edge_type,
                    source_record_id=record.id,
                    evidence_assertion_ids=assertion_ids,
                )
            )
    return tuple(sorted(edges, key=lambda item: item.edge_id))


def _resolve_seed(
    seed_text: str,
    normalized_seed: str,
    manifest: KnowledgeGraphRetrievalIndexManifest,
    projection: KnowledgeGraphProjectionPort,
) -> tuple[tuple[KnowledgeGraphSeedCandidate, ...], str]:
    exact = projection.exact_seed_matches(manifest, normalized_seed)
    matches = exact if exact else projection.lexical_seed_matches(manifest, seed_text)
    candidates = tuple(
        KnowledgeGraphSeedCandidate(
            node_id=item.node_id,
            node_type=item.node_type,
            label=item.label,
            channel_observation=RetrievalChannelObservation(
                channel=item.channel,
                index_manifest_id=manifest.index_manifest_id,
                channel_rank=item.channel_rank,
                raw_score=item.raw_score,
                matched_field="node_label",
            ),
        )
        for item in matches
    )
    if not candidates:
        raise KnowledgeGraphRetrievalError(
            KnowledgeGraphRetrievalFailureCode.SEED_MISSING,
            "No current Knowledge-Graph node matches the supplied name.",
        )
    if len(candidates) != 1:
        raise KnowledgeGraphRetrievalError(
            KnowledgeGraphRetrievalFailureCode.SEED_AMBIGUOUS,
            "The supplied name identifies more than one Knowledge-Graph node.",
            seed_candidates=candidates,
        )
    return candidates, candidates[0].node_id


def _traverse(
    seed_id: str,
    units: tuple[KnowledgeGraphRetrievalUnit, ...],
    edges: tuple[KnowledgeGraphEdge, ...],
    manifest_id: str,
    maximum_hops: int,
    maximum_hits: int,
    ledger_repository: KnowledgeGraphLedger,
) -> tuple[KnowledgeGraphRetrievalHit, ...]:
    by_node: dict[str, list[tuple[str, KnowledgeGraphEdge, str]]] = {}
    for edge in edges:
        by_node.setdefault(edge.source_node_id, []).append((edge.target_node_id, edge, "forward"))
        by_node.setdefault(edge.target_node_id, []).append((edge.source_node_id, edge, "reverse"))
    paths: dict[str, KnowledgeGraphTraversalPath] = {}
    pending: list[KnowledgeGraphTraversalPath] = [
        KnowledgeGraphTraversalPath(node_ids=(seed_id,), edge_ids=(), edge_directions=())
    ]
    while pending:
        path = pending.pop(0)
        if len(path.edge_ids) == maximum_hops:
            continue
        for target_id, edge, direction in sorted(
            by_node.get(path.node_ids[-1], []), key=lambda item: (item[1].edge_id, item[0])
        ):
            if target_id in path.node_ids:
                continue
            next_path = KnowledgeGraphTraversalPath(
                node_ids=(*path.node_ids, target_id),
                edge_ids=(*path.edge_ids, edge.edge_id),
                edge_directions=(*path.edge_directions, direction),
            )
            existing = paths.get(target_id)
            if existing is None or _path_key(next_path) < _path_key(existing):
                paths[target_id] = next_path
                pending.append(next_path)
    units_by_record = {unit.source_record_id: unit for unit in units}
    candidates = tuple(
        (record_id, path) for record_id, path in paths.items() if record_id in units_by_record
    )
    ordered = sorted(candidates, key=lambda item: (_path_key(item[1]), item[0]))[:maximum_hits]
    hits: list[KnowledgeGraphRetrievalHit] = []
    for rank, (record_id, path) in enumerate(ordered, start=1):
        unit = units_by_record[record_id]
        hits.append(
            KnowledgeGraphRetrievalHit(
                retrieval_unit_id=unit.retrieval_unit_id,
                source_record_id=record_id,
                record_type=unit.record_type,
                terminal_evidence_target_ids=_terminal_evidence_target_ids(
                    unit.evidence_assertion_ids, ledger_repository
                ),
                traversal_path=path,
                channel_observations=(
                    RetrievalChannelObservation(
                        channel=RetrievalChannel.GRAPH_TRAVERSAL,
                        index_manifest_id=manifest_id,
                        channel_rank=rank,
                        matched_field="graph_path",
                    ),
                ),
                final_rank=rank,
                selected=True,
                selection_reason="shortest_canonical_graph_path",
            )
        )
    return tuple(hits)


def _path_key(path: KnowledgeGraphTraversalPath) -> tuple[int, tuple[str, ...], tuple[str, ...]]:
    return len(path.edge_ids), path.edge_ids, path.node_ids


def _context_results(
    hits: tuple[KnowledgeGraphRetrievalHit, ...],
    command: QueryKnowledgeGraphCommand,
    ledger_repository: KnowledgeGraphLedger,
    tokenizer: ContextTokenizer,
) -> tuple[LedgerContextResult, ...]:
    node_ids_by_representation: dict[str, set[str]] = {}
    for hit in hits:
        for evidence_id in hit.terminal_evidence_target_ids:
            evidence = ledger_repository.get_evidence_target(evidence_id)
            if evidence is None:
                raise KnowledgeGraphRetrievalError(
                    KnowledgeGraphRetrievalFailureCode.EVIDENCE_MISSING,
                    "Knowledge-Graph hit references missing evidence.",
                )
            node_ids_by_representation.setdefault(evidence.representation_id, set()).update(
                evidence.node_ids
            )
    results: list[LedgerContextResult] = []
    for representation_id, node_ids in sorted(node_ids_by_representation.items()):
        focus_ids = tuple(sorted(node_ids))
        try:
            unit = create_analysis_unit_from_retrieval_selection(
                RetrievalSelectionAnalysisUnitInput(
                    representation_id=representation_id,
                    focus_node_ids=focus_ids,
                    policy_id=KNOWLEDGE_GRAPH_CONTEXT_PLANNER_POLICY_ID,
                    task_type="knowledge_graph_retrieval",
                ),
                ledger_repository,
            )
            outcome = build_context_manifest(
                ContextManifestInput(
                    analysis_unit=unit,
                    model_profile=_context_profile(command.context_profile_id),
                    prompt_id="knowledge-graph-retrieval-validation-prompt-v1",
                    prompt_bytes=b"Use only the supplied original source evidence.",
                    schema_id="knowledge-graph-retrieval-validation-schema-v1",
                    schema_bytes=b'{"type":"object"}',
                    renderer_version="knowledge-graph-retrieval-context-v1",
                ),
                ledger_repository,
                tokenizer,
            )
            results.append(
                LedgerContextResult(
                    representation_id=representation_id,
                    focus_node_ids=focus_ids,
                    analysis_unit_id=unit.id,
                    context_manifest_id=outcome.manifest.id,
                    status=outcome.manifest.status.value,
                    blocked_reason=outcome.manifest.blocked_reason,
                )
            )
        except ValueError as exc:
            results.append(
                LedgerContextResult(
                    representation_id=representation_id,
                    focus_node_ids=focus_ids,
                    status="failed",
                    blocked_reason=str(exc),
                )
            )
    return tuple(results)


def _terminal_evidence_target_ids(
    assertion_ids: tuple[str, ...], ledger_repository: KnowledgeGraphLedger
) -> tuple[str, ...]:
    pending = list(assertion_ids)
    visited: set[str] = set()
    evidence_ids: set[str] = set()
    while pending:
        assertion_id = pending.pop()
        if assertion_id in visited:
            continue
        visited.add(assertion_id)
        assertion = ledger_repository.get_assertion(assertion_id)
        if assertion is None or assertion.status is AssertionStatus.PROPOSED:
            raise KnowledgeGraphRetrievalError(
                KnowledgeGraphRetrievalFailureCode.EVIDENCE_MISSING,
                "Knowledge-Graph edge references a missing or proposed Assertion.",
            )
        if assertion.assertion_type is AssertionType.ANALYTIC_INFERENCE:
            pending.extend(assertion.supporting_assertion_ids)
        else:
            evidence_ids.update(assertion.evidence_target_ids)
    if not evidence_ids:
        raise KnowledgeGraphRetrievalError(
            KnowledgeGraphRetrievalFailureCode.EVIDENCE_MISSING,
            "Knowledge-Graph result has no terminal EvidenceTarget.",
        )
    return tuple(sorted(evidence_ids))


def _record_type(record: Assertion | Relationship | Outcome) -> LedgerRetrievalRecordType:
    if isinstance(record, Assertion):
        return LedgerRetrievalRecordType.ASSERTION
    if isinstance(record, Relationship):
        return LedgerRetrievalRecordType.RELATIONSHIP
    return LedgerRetrievalRecordType.OUTCOME


def _manifest(
    snapshot: str,
    units: tuple[KnowledgeGraphRetrievalUnit, ...],
    nodes: tuple[KnowledgeGraphNode, ...],
    edges: tuple[KnowledgeGraphEdge, ...],
) -> KnowledgeGraphRetrievalIndexManifest:
    content = _digest(
        {
            "snapshot": snapshot,
            "units": tuple(item.unit_fingerprint for item in units),
            "nodes": tuple(item.model_dump(mode="json") for item in nodes),
            "edges": tuple(item.model_dump(mode="json") for item in edges),
        }
    )
    return KnowledgeGraphRetrievalIndexManifest(
        index_manifest_id=f"grm_{content[:24]}",
        channels=(
            RetrievalChannel.EXACT,
            RetrievalChannel.LEXICAL,
            RetrievalChannel.GRAPH_TRAVERSAL,
        ),
        source_snapshot_digest=snapshot,
        unit_policy_id=KNOWLEDGE_GRAPH_UNIT_POLICY_ID,
        projection_policy_id=KNOWLEDGE_GRAPH_PROJECTION_POLICY_ID,
        query_policy_compatibility=KNOWLEDGE_GRAPH_QUERY_POLICY_ID,
        adapter_identity="sqlite_knowledge_graph_retrieval_v1",
        adapter_configuration_digest=_digest({"adapter": "sqlite_knowledge_graph_retrieval_v1"}),
        unit_count=len(units),
        node_count=len(nodes),
        edge_count=len(edges),
        content_fingerprint=content,
        publication_status="complete",
        published_at=datetime.now(UTC),
    )


def _validate_query(command: QueryKnowledgeGraphCommand) -> None:
    if not command.seed_text.strip():
        raise KnowledgeGraphRetrievalError(
            KnowledgeGraphRetrievalFailureCode.SEED_EMPTY,
            "Knowledge-Graph traversal requires a name phrase.",
        )
    if command.maximum_hops not in {1, 2} or command.maximum_hits < 1:
        raise KnowledgeGraphRetrievalError(
            KnowledgeGraphRetrievalFailureCode.SEED_EMPTY,
            "Knowledge-Graph traversal limits are invalid.",
        )
    if command.policy_id != KNOWLEDGE_GRAPH_QUERY_POLICY_ID:
        raise KnowledgeGraphRetrievalError(
            KnowledgeGraphRetrievalFailureCode.SEED_EMPTY,
            "Knowledge-Graph traversal policy is unknown.",
        )


def _query_id(command: QueryKnowledgeGraphCommand, manifest_id: str, snapshot: str) -> str:
    fingerprint = _digest(
        (command.seed_text, command.maximum_hops, command.maximum_hits, manifest_id, snapshot)
    )
    return f"grq_{fingerprint[:24]}"


def _context_profile(profile_id: str) -> ContextModelProfile:
    if not profile_id.strip():
        raise KnowledgeGraphRetrievalError(
            KnowledgeGraphRetrievalFailureCode.CONTEXT_PLANNING_FAILED,
            "Context profile is empty.",
        )
    return ContextModelProfile(profile_id, 16384, 512, 128)


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str
        ).encode()
    ).hexdigest()
