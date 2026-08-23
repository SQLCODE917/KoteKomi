"""Derived evidence contributions for current accepted Relationship records."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Protocol

from kotekomi_domain import (
    Assertion,
    AssertionEvidenceLink,
    AssertionStatus,
    AssertionType,
    CrossSourceRelationState,
    Document,
    EvidenceGraphContribution,
    EvidenceGraphEdge,
    EvidenceGraphExplanationRecord,
    EvidenceGraphLineageCluster,
    EvidenceGraphLineageMembership,
    EvidenceGraphProjectionManifest,
    EvidenceTarget,
    EvidenceValidationAttempt,
    EvidenceValidationAttemptStatus,
    LedgerContextResult,
    Relationship,
    SourceLineageRelation,
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
from kotekomi_application.ports import AcceptedCanonicalRecord

EVIDENCE_GRAPH_PROJECTION_POLICY_ID = "evidence_graph_relationship_contributions_v1"
EVIDENCE_GRAPH_BUILDER_VERSION = "dr6_1_evidence_graph_projection_v1"
EVIDENCE_GRAPH_EXPLANATION_POLICY_ID = "evidence_graph_relationship_explanation_v1"
EVIDENCE_GRAPH_LINEAGE_POLICY_ID = "reviewed_exact_content_sha256_v1"


class EvidenceGraphFailureCode(StrEnum):
    PROJECTION_NOT_FOUND = "evidence_graph_projection_not_found"
    PROJECTION_STALE = "evidence_graph_projection_stale"
    PROJECTION_CORRUPT = "evidence_graph_projection_corrupt"
    EVIDENCE_INVALID = "evidence_graph_evidence_invalid"
    RELATIONSHIP_NOT_FOUND = "evidence_graph_relationship_not_found"
    CONTEXT_PLANNING_FAILED = "evidence_graph_context_planning_failed"


class EvidenceGraphError(ValueError):
    def __init__(self, code: EvidenceGraphFailureCode, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class BuildEvidenceGraphProjectionCommand:
    pass


@dataclass(frozen=True)
class ExplainEvidenceGraphRelationshipCommand:
    relationship_id: str
    context_profile_id: str = "retrieval-validation-v1"
    policy_id: str = EVIDENCE_GRAPH_EXPLANATION_POLICY_ID


@dataclass(frozen=True)
class EvidenceGraphProjectionBuildInput:
    manifest: EvidenceGraphProjectionManifest
    edges: tuple[EvidenceGraphEdge, ...]
    contributions: tuple[EvidenceGraphContribution, ...]
    lineage_clusters: tuple[EvidenceGraphLineageCluster, ...]


@dataclass(frozen=True)
class BuildEvidenceGraphProjectionResult:
    status: str
    projection_manifest_id: str | None
    edge_count: int
    contribution_count: int
    lineage_cluster_count: int
    content_fingerprint: str | None
    reused_existing_manifest: bool
    failure: EvidenceGraphFailureCode | None = None


@dataclass(frozen=True)
class ExplainEvidenceGraphRelationshipResult:
    status: str
    explanation_id: str | None
    projection_manifest_id: str | None
    edge: EvidenceGraphEdge | None
    contributions: tuple[EvidenceGraphContribution, ...]
    lineage_clusters: tuple[EvidenceGraphLineageCluster, ...]
    context_results: tuple[LedgerContextResult, ...]
    raw_document_count: int = 0
    lineage_cluster_count: int = 0
    failure: EvidenceGraphFailureCode | None = None
    policy_id: str | None = None


class EvidenceGraphStateLedger(Protocol):
    def list_accepted_canonical_records(self) -> tuple[AcceptedCanonicalRecord, ...]: ...
    def get_evidence_target(self, record_id: str) -> EvidenceTarget | None: ...
    def list_assertion_evidence_links(self) -> tuple[AssertionEvidenceLink, ...]: ...
    def list_evidence_validation_attempts(self) -> tuple[EvidenceValidationAttempt, ...]: ...


class EvidenceGraphLedger(EvidenceGraphStateLedger, ContextPlanningLedger, Protocol):
    pass


class EvidenceGraphProjectionPort(Protocol):
    def publish_evidence_graph(
        self, build: EvidenceGraphProjectionBuildInput
    ) -> tuple[EvidenceGraphProjectionManifest, bool]: ...
    def get_complete_evidence_graph_manifest(self) -> EvidenceGraphProjectionManifest | None: ...
    def load_evidence_graph_edge(
        self, manifest: EvidenceGraphProjectionManifest, relationship_id: str
    ) -> EvidenceGraphEdge | None: ...
    def load_evidence_graph_contributions(
        self, manifest: EvidenceGraphProjectionManifest, edge_id: str
    ) -> tuple[EvidenceGraphContribution, ...]: ...
    def load_evidence_graph_lineage_clusters(
        self, manifest: EvidenceGraphProjectionManifest, lineage_cluster_ids: tuple[str, ...]
    ) -> tuple[EvidenceGraphLineageCluster, ...]: ...
    def save_evidence_graph_explanation(self, record: EvidenceGraphExplanationRecord) -> None: ...


def build_evidence_graph_projection(
    command: BuildEvidenceGraphProjectionCommand,
    *,
    ledger_repository: EvidenceGraphLedger,
    projection: EvidenceGraphProjectionPort,
) -> BuildEvidenceGraphProjectionResult:
    del command
    try:
        edges, contributions, clusters, snapshot = build_evidence_graph_state(ledger_repository)
        manifest = _manifest(snapshot, edges, contributions, clusters)
        published, reused = projection.publish_evidence_graph(
            EvidenceGraphProjectionBuildInput(manifest, edges, contributions, clusters)
        )
        return BuildEvidenceGraphProjectionResult(
            status="complete",
            projection_manifest_id=published.projection_manifest_id,
            edge_count=len(edges),
            contribution_count=len(contributions),
            lineage_cluster_count=len(clusters),
            content_fingerprint=published.content_fingerprint,
            reused_existing_manifest=reused,
        )
    except EvidenceGraphError as exc:
        return BuildEvidenceGraphProjectionResult(
            status="failed",
            projection_manifest_id=None,
            edge_count=0,
            contribution_count=0,
            lineage_cluster_count=0,
            content_fingerprint=None,
            reused_existing_manifest=False,
            failure=exc.code,
        )


def explain_evidence_graph_relationship(
    command: ExplainEvidenceGraphRelationshipCommand,
    *,
    ledger_repository: EvidenceGraphLedger,
    projection: EvidenceGraphProjectionPort,
    tokenizer: ContextTokenizer,
) -> ExplainEvidenceGraphRelationshipResult:
    try:
        if (
            not command.relationship_id.strip()
            or command.policy_id != EVIDENCE_GRAPH_EXPLANATION_POLICY_ID
        ):
            raise EvidenceGraphError(
                EvidenceGraphFailureCode.RELATIONSHIP_NOT_FOUND,
                "Evidence graph explanation requires a Relationship ID and known policy.",
            )
        _, _, _, snapshot = build_evidence_graph_state(ledger_repository)
        manifest = projection.get_complete_evidence_graph_manifest()
        if manifest is None:
            raise EvidenceGraphError(
                EvidenceGraphFailureCode.PROJECTION_NOT_FOUND,
                "No complete evidence graph projection exists.",
            )
        if manifest.source_snapshot_digest != snapshot:
            raise EvidenceGraphError(
                EvidenceGraphFailureCode.PROJECTION_STALE,
                "Evidence graph projection does not match current accepted Ledger state.",
            )
        edge = projection.load_evidence_graph_edge(manifest, command.relationship_id)
        if edge is None:
            return _failed_explanation(
                command,
                manifest,
                snapshot,
                projection,
                EvidenceGraphFailureCode.RELATIONSHIP_NOT_FOUND,
            )
        contributions = projection.load_evidence_graph_contributions(
            manifest, edge.evidence_graph_edge_id
        )
        if tuple(item.contribution_id for item in contributions) != edge.contribution_ids:
            raise EvidenceGraphError(
                EvidenceGraphFailureCode.PROJECTION_CORRUPT,
                "Evidence graph contribution rows do not match the projected edge.",
            )
        lineage_cluster_ids = tuple(
            sorted(
                {
                    membership.lineage_cluster_id
                    for item in contributions
                    for membership in item.lineage_memberships
                }
            )
        )
        clusters = projection.load_evidence_graph_lineage_clusters(manifest, lineage_cluster_ids)
        if tuple(item.lineage_cluster_id for item in clusters) != lineage_cluster_ids:
            raise EvidenceGraphError(
                EvidenceGraphFailureCode.PROJECTION_CORRUPT,
                "Evidence graph lineage rows do not match projected contributions.",
            )
        contexts = _context_results(contributions, command, ledger_repository, tokenizer)
        record = EvidenceGraphExplanationRecord(
            explanation_id=_explanation_id(command, manifest.projection_manifest_id, snapshot),
            projection_manifest_id=manifest.projection_manifest_id,
            source_snapshot_digest=snapshot,
            relationship_id=command.relationship_id,
            evidence_graph_edge_id=edge.evidence_graph_edge_id,
            contribution_ids=edge.contribution_ids,
            source_document_ids=tuple(
                sorted(
                    {
                        document_id
                        for item in contributions
                        for document_id in item.source_document_ids
                    }
                )
            ),
            lineage_cluster_ids=lineage_cluster_ids,
            context_results=contexts,
        )
        projection.save_evidence_graph_explanation(record)
        return ExplainEvidenceGraphRelationshipResult(
            status="complete",
            explanation_id=record.explanation_id,
            projection_manifest_id=manifest.projection_manifest_id,
            edge=edge,
            contributions=contributions,
            lineage_clusters=clusters,
            context_results=contexts,
            raw_document_count=len(record.source_document_ids),
            lineage_cluster_count=len(clusters),
            policy_id=command.policy_id,
        )
    except EvidenceGraphError as exc:
        return ExplainEvidenceGraphRelationshipResult(
            status="failed",
            explanation_id=None,
            projection_manifest_id=None,
            edge=None,
            contributions=(),
            lineage_clusters=(),
            context_results=(),
            raw_document_count=0,
            lineage_cluster_count=0,
            failure=exc.code,
        )


def build_evidence_graph_state(
    ledger_repository: EvidenceGraphStateLedger,
) -> tuple[
    tuple[EvidenceGraphEdge, ...],
    tuple[EvidenceGraphContribution, ...],
    tuple[EvidenceGraphLineageCluster, ...],
    str,
]:
    records = ledger_repository.list_accepted_canonical_records()
    assertions = tuple(item for item in records if isinstance(item, Assertion))
    current_assertions = tuple(sorted(_current_assertions(assertions), key=lambda item: item.id))
    current_assertion_ids = {item.id for item in current_assertions}
    relationships = tuple(
        sorted(
            (
                item
                for item in records
                if isinstance(item, Relationship)
                and set(item.assertion_ids).issubset(current_assertion_ids)
            ),
            key=lambda item: item.id,
        )
    )
    all_documents = tuple(
        sorted((item for item in records if isinstance(item, Document)), key=lambda item: item.id)
    )
    all_lineage_relations = tuple(
        sorted(
            (item for item in records if isinstance(item, SourceLineageRelation)),
            key=lambda item: item.id,
        )
    )
    links = ledger_repository.list_assertion_evidence_links()
    attempts = ledger_repository.list_evidence_validation_attempts()
    evidence_ids = {
        evidence_id
        for assertion in current_assertions
        for evidence_id in assertion.evidence_target_ids
    }
    targets = tuple(
        target
        for evidence_id in sorted(evidence_ids)
        if (target := ledger_repository.get_evidence_target(evidence_id)) is not None
    )
    assertions_by_id = {item.id: item for item in current_assertions}
    targets_by_id = {item.id: item for item in targets}
    contributing_document_ids = _contributing_document_ids(
        relationships, assertions_by_id, targets_by_id
    )
    documents = tuple(item for item in all_documents if item.id in contributing_document_ids)
    lineage_relations = tuple(
        item
        for item in all_lineage_relations
        if set(item.document_ids).issubset(contributing_document_ids)
    )
    snapshot = _digest(
        {
            "relationships": [item.model_dump(mode="json") for item in relationships],
            "assertions": [item.model_dump(mode="json") for item in current_assertions],
            "links": [
                item.model_dump(mode="json") for item in sorted(links, key=lambda item: item.id)
            ],
            "attempts": [
                item.model_dump(mode="json") for item in sorted(attempts, key=lambda item: item.id)
            ],
            "targets": [item.model_dump(mode="json") for item in targets],
            "documents": [item.model_dump(mode="json") for item in documents],
            "source_lineage_relations": [
                item.model_dump(mode="json") for item in lineage_relations
            ],
        }
    )
    links_by_assertion: dict[str, tuple[AssertionEvidenceLink, ...]] = {}
    for assertion in current_assertions:
        links_by_assertion[assertion.id] = tuple(
            sorted(
                (item for item in links if item.assertion_id == assertion.id),
                key=lambda item: item.id,
            )
        )
    attempts_by_id = {item.id: item for item in attempts}
    clusters, memberships_by_document = build_evidence_graph_lineage_clusters(
        snapshot=snapshot,
        documents=documents,
        lineage_relations=lineage_relations,
        contributing_document_ids=tuple(sorted(contributing_document_ids)),
    )
    edges: list[EvidenceGraphEdge] = []
    contributions: list[EvidenceGraphContribution] = []
    for relationship in relationships:
        edge_id = (
            f"ege_{_digest((relationship.id, snapshot, EVIDENCE_GRAPH_PROJECTION_POLICY_ID))[:24]}"
        )
        contribution_ids: list[str] = []
        for supporting_assertion_id in sorted(relationship.assertion_ids):
            contribution = _contribution(
                edge_id,
                relationship,
                supporting_assertion_id,
                assertions_by_id,
                links_by_assertion,
                attempts_by_id,
                targets_by_id,
                memberships_by_document,
            )
            contributions.append(contribution)
            contribution_ids.append(contribution.contribution_id)
        edges.append(
            EvidenceGraphEdge(
                evidence_graph_edge_id=edge_id,
                relationship_id=relationship.id,
                subject_id=relationship.subject_id,
                predicate=relationship.predicate,
                object_id=relationship.object_id,
                contribution_ids=tuple(sorted(contribution_ids)),
            )
        )
    return tuple(edges), tuple(contributions), clusters, snapshot


def _contributing_document_ids(
    relationships: tuple[Relationship, ...],
    assertions_by_id: dict[str, Assertion],
    targets_by_id: dict[str, EvidenceTarget],
) -> set[str]:
    document_ids: set[str] = set()
    for relationship in relationships:
        for supporting_assertion_id in relationship.assertion_ids:
            supporting = assertions_by_id.get(supporting_assertion_id)
            if supporting is None:
                raise EvidenceGraphError(
                    EvidenceGraphFailureCode.EVIDENCE_INVALID,
                    "Relationship support does not identify a current accepted Assertion.",
                )
            for terminal in _terminal_assertions(supporting, assertions_by_id):
                for evidence_target_id in terminal.evidence_target_ids:
                    target = targets_by_id.get(evidence_target_id)
                    if target is not None:
                        document_ids.add(target.document_id)
    return document_ids


def _current_assertions(assertions: tuple[Assertion, ...]) -> tuple[Assertion, ...]:
    superseded_ids = {
        item.supersedes_assertion_id for item in assertions if item.supersedes_assertion_id
    }
    return tuple(
        item
        for item in assertions
        if item.status
        not in {AssertionStatus.PROPOSED, AssertionStatus.SUPERSEDED, AssertionStatus.RETRACTED}
        and item.id not in superseded_ids
    )


def _contribution(
    edge_id: str,
    relationship: Relationship,
    supporting_assertion_id: str,
    assertions_by_id: dict[str, Assertion],
    links_by_assertion: dict[str, tuple[AssertionEvidenceLink, ...]],
    attempts_by_id: dict[str, EvidenceValidationAttempt],
    targets_by_id: dict[str, EvidenceTarget],
    memberships_by_document: dict[str, EvidenceGraphLineageMembership],
) -> EvidenceGraphContribution:
    supporting = assertions_by_id.get(supporting_assertion_id)
    if supporting is None:
        raise EvidenceGraphError(
            EvidenceGraphFailureCode.EVIDENCE_INVALID,
            "Relationship support does not identify a current accepted Assertion.",
        )
    terminals = _terminal_assertions(supporting, assertions_by_id)
    evidence_links: list[AssertionEvidenceLink] = []
    for terminal in terminals:
        terminal_links = tuple(
            item
            for item in links_by_assertion.get(terminal.id, ())
            if item.evidence_target_id in terminal.evidence_target_ids
        )
        if not terminal_links:
            raise EvidenceGraphError(
                EvidenceGraphFailureCode.EVIDENCE_INVALID,
                "Terminal Assertion has no accepted AssertionEvidenceLink.",
            )
        evidence_links.extend(terminal_links)
    validation_attempts: list[EvidenceValidationAttempt] = []
    for link in evidence_links:
        attempt = attempts_by_id.get(link.validation_attempt_id)
        if attempt is None or attempt.status is not EvidenceValidationAttemptStatus.SUCCEEDED:
            raise EvidenceGraphError(
                EvidenceGraphFailureCode.EVIDENCE_INVALID,
                "Evidence graph contribution requires successful evidence validation.",
            )
        if attempt.evidence_target_id != link.evidence_target_id:
            raise EvidenceGraphError(
                EvidenceGraphFailureCode.EVIDENCE_INVALID,
                "Evidence validation does not belong to the linked EvidenceTarget.",
            )
        if link.evidence_target_id not in targets_by_id:
            raise EvidenceGraphError(
                EvidenceGraphFailureCode.EVIDENCE_INVALID,
                "Evidence graph contribution references a missing EvidenceTarget.",
            )
        validation_attempts.append(attempt)
    fingerprint = _digest(
        {
            "edge": edge_id,
            "relationship": relationship.id,
            "supporting_assertion": supporting_assertion_id,
            "terminals": [item.id for item in terminals],
            "links": [item.id for item in evidence_links],
        }
    )
    return EvidenceGraphContribution(
        contribution_id=f"egc_{fingerprint[:24]}",
        evidence_graph_edge_id=edge_id,
        relationship_id=relationship.id,
        supporting_assertion_id=supporting_assertion_id,
        terminal_assertion_ids=tuple(item.id for item in terminals),
        assertion_evidence_link_ids=tuple(item.id for item in evidence_links),
        validation_attempt_ids=tuple(item.id for item in validation_attempts),
        evidence_target_ids=tuple(sorted({item.evidence_target_id for item in evidence_links})),
        source_document_ids=tuple(
            sorted({targets_by_id[item.evidence_target_id].document_id for item in evidence_links})
        ),
        lineage_memberships=tuple(
            memberships_by_document[document_id]
            for document_id in sorted(
                {targets_by_id[item.evidence_target_id].document_id for item in evidence_links}
            )
        ),
        assertion_status=supporting.status,
        source_authorities=tuple(item.source_authority for item in terminals),
        evidence_polarities=tuple(item.polarity for item in evidence_links),
        evidence_necessities=tuple(item.necessity for item in evidence_links),
    )


def build_evidence_graph_lineage_clusters(
    *,
    snapshot: str,
    documents: tuple[Document, ...],
    lineage_relations: tuple[SourceLineageRelation, ...],
    contributing_document_ids: tuple[str, ...],
) -> tuple[tuple[EvidenceGraphLineageCluster, ...], dict[str, EvidenceGraphLineageMembership]]:
    documents_by_id: dict[str, Document] = {item.id: item for item in documents}
    contributing_ids: set[str] = set(contributing_document_ids)
    if not contributing_ids.issubset(documents_by_id):
        raise EvidenceGraphError(
            EvidenceGraphFailureCode.EVIDENCE_INVALID,
            "Evidence graph source Document is missing from accepted canonical state.",
        )
    adjacency: dict[str, set[str]] = {document_id: set() for document_id in contributing_ids}
    relation_ids_by_pair: dict[frozenset[str], list[str]] = {}
    for relation in lineage_relations:
        first, second = relation.document_ids
        first_document = documents_by_id.get(first)
        second_document = documents_by_id.get(second)
        if first_document is None or second_document is None:
            raise EvidenceGraphError(
                EvidenceGraphFailureCode.EVIDENCE_INVALID,
                "Accepted source lineage relation references a missing Document.",
            )
        if (
            first_document.content_sha256 != second_document.content_sha256
            or first_document.content_sha256 != relation.shared_content_sha256
        ):
            raise EvidenceGraphError(
                EvidenceGraphFailureCode.EVIDENCE_INVALID,
                "Accepted source lineage relation has mismatched Document bytes.",
            )
        if first in contributing_ids and second in contributing_ids:
            adjacency[first].add(second)
            adjacency[second].add(first)
            relation_ids_by_pair.setdefault(frozenset((first, second)), []).append(relation.id)
    clusters: list[EvidenceGraphLineageCluster] = []
    memberships: dict[str, EvidenceGraphLineageMembership] = {}
    remaining = set(contributing_ids)
    while remaining:
        root = min(remaining)
        pending = [root]
        component: set[str] = set()
        while pending:
            current = pending.pop()
            if current in component:
                continue
            component.add(current)
            pending.extend(sorted(adjacency[current] - component, reverse=True))
        remaining -= component
        document_ids = tuple(sorted(component))
        relation_ids = tuple(
            sorted(
                relation_id
                for pair, ids in relation_ids_by_pair.items()
                if pair.issubset(component)
                for relation_id in ids
            )
        )
        state = (
            CrossSourceRelationState.RECORDED_RELATION
            if relation_ids
            else CrossSourceRelationState.NO_CROSS_SOURCE_RELATION_RECORDED
        )
        fingerprint = _digest(
            {
                "policy": EVIDENCE_GRAPH_LINEAGE_POLICY_ID,
                "snapshot": snapshot,
                "documents": document_ids,
                "relations": relation_ids,
                "state": state.value,
            }
        )
        cluster = EvidenceGraphLineageCluster(
            lineage_cluster_id=f"lcl_{fingerprint[:24]}",
            document_ids=document_ids,
            source_lineage_relation_ids=relation_ids,
            cross_source_relation_state=state,
            source_snapshot_digest=snapshot,
            policy_id=EVIDENCE_GRAPH_LINEAGE_POLICY_ID,
            cluster_fingerprint=fingerprint,
        )
        clusters.append(cluster)
        for document_id in document_ids:
            memberships[document_id] = EvidenceGraphLineageMembership(
                document_id=document_id,
                lineage_cluster_id=cluster.lineage_cluster_id,
                cross_source_relation_state=state,
            )
    return tuple(sorted(clusters, key=lambda item: item.lineage_cluster_id)), memberships


def _terminal_assertions(
    assertion: Assertion, assertions_by_id: dict[str, Assertion]
) -> tuple[Assertion, ...]:
    pending = [assertion]
    terminals: list[Assertion] = []
    visited: set[str] = set()
    while pending:
        current = pending.pop()
        if current.id in visited:
            continue
        visited.add(current.id)
        if current.assertion_type is AssertionType.ANALYTIC_INFERENCE:
            for support_id in current.supporting_assertion_ids:
                support = assertions_by_id.get(support_id)
                if support is None:
                    raise EvidenceGraphError(
                        EvidenceGraphFailureCode.EVIDENCE_INVALID,
                        "Analytic inference does not resolve to a current accepted Assertion.",
                    )
                pending.append(support)
        else:
            terminals.append(current)
    if not terminals:
        raise EvidenceGraphError(
            EvidenceGraphFailureCode.EVIDENCE_INVALID,
            "Relationship support does not resolve to terminal Direct Assertions.",
        )
    return tuple(sorted(terminals, key=lambda item: item.id))


def _context_results(
    contributions: tuple[EvidenceGraphContribution, ...],
    command: ExplainEvidenceGraphRelationshipCommand,
    ledger_repository: EvidenceGraphLedger,
    tokenizer: ContextTokenizer,
) -> tuple[LedgerContextResult, ...]:
    node_ids_by_representation: dict[str, set[str]] = {}
    for contribution in contributions:
        for evidence_id in contribution.evidence_target_ids:
            target = ledger_repository.get_evidence_target(evidence_id)
            if target is None:
                raise EvidenceGraphError(
                    EvidenceGraphFailureCode.EVIDENCE_INVALID,
                    "Evidence graph contribution references missing evidence.",
                )
            node_ids_by_representation.setdefault(target.representation_id, set()).update(
                target.node_ids
            )
    results: list[LedgerContextResult] = []
    for representation_id, node_ids in sorted(node_ids_by_representation.items()):
        focus_node_ids = tuple(sorted(node_ids))
        try:
            analysis_unit = create_analysis_unit_from_retrieval_selection(
                RetrievalSelectionAnalysisUnitInput(
                    representation_id=representation_id,
                    focus_node_ids=focus_node_ids,
                    policy_id=EVIDENCE_GRAPH_EXPLANATION_POLICY_ID,
                    task_type="evidence_graph_relationship_explanation",
                ),
                ledger_repository,
            )
            outcome = build_context_manifest(
                ContextManifestInput(
                    analysis_unit=analysis_unit,
                    model_profile=_context_profile(command.context_profile_id),
                    prompt_id="evidence-graph-explanation-prompt-v1",
                    prompt_bytes=b"Use only the supplied original source evidence.",
                    schema_id="evidence-graph-explanation-schema-v1",
                    schema_bytes=b'{"type":"object"}',
                    renderer_version="evidence-graph-explanation-context-v1",
                ),
                ledger_repository,
                tokenizer,
            )
            results.append(
                LedgerContextResult(
                    representation_id=representation_id,
                    focus_node_ids=focus_node_ids,
                    analysis_unit_id=analysis_unit.id,
                    context_manifest_id=outcome.manifest.id,
                    status=outcome.manifest.status.value,
                    blocked_reason=outcome.manifest.blocked_reason,
                )
            )
        except ValueError as exc:
            results.append(
                LedgerContextResult(
                    representation_id=representation_id,
                    focus_node_ids=focus_node_ids,
                    status="failed",
                    blocked_reason=str(exc),
                )
            )
    return tuple(results)


def _failed_explanation(
    command: ExplainEvidenceGraphRelationshipCommand,
    manifest: EvidenceGraphProjectionManifest,
    snapshot: str,
    projection: EvidenceGraphProjectionPort,
    failure: EvidenceGraphFailureCode,
) -> ExplainEvidenceGraphRelationshipResult:
    record = EvidenceGraphExplanationRecord(
        explanation_id=_explanation_id(command, manifest.projection_manifest_id, snapshot),
        projection_manifest_id=manifest.projection_manifest_id,
        source_snapshot_digest=snapshot,
        relationship_id=command.relationship_id,
        failure_code=failure.value,
    )
    projection.save_evidence_graph_explanation(record)
    return ExplainEvidenceGraphRelationshipResult(
        status="failed",
        explanation_id=record.explanation_id,
        projection_manifest_id=manifest.projection_manifest_id,
        edge=None,
        contributions=(),
        lineage_clusters=(),
        context_results=(),
        raw_document_count=0,
        lineage_cluster_count=0,
        failure=failure,
        policy_id=command.policy_id,
    )


def _manifest(
    snapshot: str,
    edges: tuple[EvidenceGraphEdge, ...],
    contributions: tuple[EvidenceGraphContribution, ...],
    lineage_clusters: tuple[EvidenceGraphLineageCluster, ...],
) -> EvidenceGraphProjectionManifest:
    content = _digest(
        {
            "snapshot": snapshot,
            "edges": [item.model_dump(mode="json") for item in edges],
            "contributions": [item.model_dump(mode="json") for item in contributions],
            "lineage_clusters": [item.model_dump(mode="json") for item in lineage_clusters],
        }
    )
    return EvidenceGraphProjectionManifest(
        projection_manifest_id=f"egm_{content[:24]}",
        source_snapshot_digest=snapshot,
        projection_policy_id=EVIDENCE_GRAPH_PROJECTION_POLICY_ID,
        builder_version=EVIDENCE_GRAPH_BUILDER_VERSION,
        adapter_identity="sqlite_evidence_graph_projection_v1",
        adapter_configuration_digest=_digest({"adapter": "sqlite_evidence_graph_projection_v1"}),
        edge_count=len(edges),
        contribution_count=len(contributions),
        lineage_cluster_count=len(lineage_clusters),
        content_fingerprint=content,
        publication_status="complete",
        published_at=datetime.now(UTC),
    )


def _explanation_id(
    command: ExplainEvidenceGraphRelationshipCommand, manifest_id: str, snapshot: str
) -> str:
    return f"egx_{_digest((command.relationship_id, manifest_id, snapshot))[:24]}"


def _context_profile(profile_id: str) -> ContextModelProfile:
    if not profile_id.strip():
        raise EvidenceGraphError(
            EvidenceGraphFailureCode.CONTEXT_PLANNING_FAILED,
            "Evidence graph explanation requires a context profile.",
        )
    return ContextModelProfile(profile_id, 16384, 512, 128)


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str
        ).encode()
    ).hexdigest()
