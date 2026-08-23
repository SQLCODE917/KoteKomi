"""Derived exact, lexical, and structured retrieval over accepted Ledger records."""

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
    LedgerContextResult,
    LedgerExactLexicalRepresentation,
    LedgerRetrievalHit,
    LedgerRetrievalIndexManifest,
    LedgerRetrievalQueryRecord,
    LedgerRetrievalRecordType,
    LedgerRetrievalUnit,
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

LEDGER_UNIT_POLICY_ID = "ledger_accepted_record_unit_v1"
LEDGER_PROJECTION_POLICY_ID = "ledger_exact_lexical_projection_v1"
LEDGER_PROJECTION_BUILDER_VERSION = "dr5_ledger_projection_v1"
LEDGER_CURRENT_RELEVANCE_POLICY_ID = "ledger_current_relevance_v1"
LEDGER_CURRENT_LATEST_POLICY_ID = "ledger_current_latest_v1"
LEDGER_AUDIT_HISTORY_POLICY_ID = "ledger_audit_history_v1"
LEDGER_CONTEXT_PLANNER_POLICY_ID = "ledger_retrieval_selection_v1"


class LedgerRetrievalFailureCode(StrEnum):
    INDEX_NOT_FOUND = "ledger_retrieval_index_not_found"
    INDEX_STALE = "ledger_retrieval_index_stale"
    INDEX_CORRUPT = "ledger_retrieval_index_corrupt"
    QUERY_EMPTY = "ledger_retrieval_query_empty"
    INVALID_FILTER = "ledger_retrieval_invalid_filter"
    EVIDENCE_MISSING = "ledger_retrieval_evidence_missing"
    CONTEXT_PLANNING_FAILED = "ledger_retrieval_context_planning_failed"


class LedgerRetrievalError(ValueError):
    def __init__(self, code: LedgerRetrievalFailureCode, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class LedgerRetrievalFilters:
    record_id: str | None = None
    record_type: LedgerRetrievalRecordType | None = None
    assertion_statuses: tuple[AssertionStatus, ...] = ()
    subject_id: str | None = None
    predicate: str | None = None


@dataclass(frozen=True)
class BuildLedgerRetrievalProjectionCommand:
    pass


@dataclass(frozen=True)
class QueryLedgerRetrievalCommand:
    query_text: str = ""
    filters: LedgerRetrievalFilters = LedgerRetrievalFilters()
    policy_id: str = LEDGER_CURRENT_RELEVANCE_POLICY_ID
    maximum_hits: int = 10
    context_profile_id: str = "retrieval-validation-v1"


@dataclass(frozen=True)
class LedgerProjectionBuildInput:
    manifest: LedgerRetrievalIndexManifest
    units: tuple[LedgerRetrievalUnit, ...]
    representations: tuple[LedgerExactLexicalRepresentation, ...]


@dataclass(frozen=True)
class LedgerChannelCandidate:
    retrieval_unit_id: str
    channel: RetrievalChannel
    channel_rank: int
    raw_score: float | None = None
    matched_field: str | None = None


@dataclass(frozen=True)
class BuildLedgerRetrievalProjectionResult:
    status: str
    index_manifest_id: str | None
    unit_count: int
    representation_count: int
    content_fingerprint: str | None
    reused_existing_manifest: bool
    failure: LedgerRetrievalFailureCode | None = None


@dataclass(frozen=True)
class QueryLedgerRetrievalResult:
    status: str
    retrieval_query_id: str | None
    index_manifest_id: str | None
    hits: tuple[LedgerRetrievalHit, ...]
    selected_record_ids: tuple[str, ...]
    context_results: tuple[LedgerContextResult, ...]
    failure: LedgerRetrievalFailureCode | None = None
    query_policy_id: str | None = None


class LedgerRetrievalLedger(ContextPlanningLedger, Protocol):
    def list_accepted_canonical_records(self) -> tuple[AcceptedCanonicalRecord, ...]: ...
    def get_assertion(self, record_id: str) -> Assertion | None: ...
    def get_evidence_target(self, record_id: str) -> EvidenceTarget | None: ...
    def get_entity(self, record_id: str) -> Entity | None: ...
    def get_actor(self, record_id: str) -> Actor | None: ...
    def get_organization(self, record_id: str) -> Organization | None: ...
    def get_event(self, record_id: str) -> Event | None: ...
    def get_place(self, record_id: str) -> Place | None: ...
    def get_document_representation_bundle(
        self, record_id: str
    ) -> DocumentRepresentationBundle | None: ...


class LedgerRetrievalProjectionPort(Protocol):
    def publish(
        self, build: LedgerProjectionBuildInput
    ) -> tuple[LedgerRetrievalIndexManifest, bool]: ...
    def get_complete_manifest(self) -> LedgerRetrievalIndexManifest | None: ...
    def exact_candidates(
        self,
        manifest: LedgerRetrievalIndexManifest,
        normalized_query: str,
        filters: LedgerRetrievalFilters,
    ) -> tuple[LedgerChannelCandidate, ...]: ...
    def lexical_candidates(
        self,
        manifest: LedgerRetrievalIndexManifest,
        query_text: str,
        filters: LedgerRetrievalFilters,
    ) -> tuple[LedgerChannelCandidate, ...]: ...
    def structured_candidates(
        self,
        manifest: LedgerRetrievalIndexManifest,
        filters: LedgerRetrievalFilters,
    ) -> tuple[LedgerChannelCandidate, ...]: ...
    def save_query_record(self, record: LedgerRetrievalQueryRecord) -> None: ...


def build_ledger_retrieval_projection(
    command: BuildLedgerRetrievalProjectionCommand,
    *,
    ledger_repository: LedgerRetrievalLedger,
    projection: LedgerRetrievalProjectionPort,
) -> BuildLedgerRetrievalProjectionResult:
    del command
    try:
        units, source_snapshot_digest = build_ledger_retrieval_units(ledger_repository)
        representations = tuple(
            build_ledger_exact_lexical_representation(unit, ledger_repository) for unit in units
        )
        manifest = _index_manifest(source_snapshot_digest, units, representations)
        published, reused = projection.publish(
            LedgerProjectionBuildInput(
                manifest=manifest, units=units, representations=representations
            )
        )
        return BuildLedgerRetrievalProjectionResult(
            status="complete",
            index_manifest_id=published.index_manifest_id,
            unit_count=len(units),
            representation_count=len(representations),
            content_fingerprint=published.content_fingerprint,
            reused_existing_manifest=reused,
        )
    except LedgerRetrievalError as exc:
        return BuildLedgerRetrievalProjectionResult(
            status="failed",
            index_manifest_id=None,
            unit_count=0,
            representation_count=0,
            content_fingerprint=None,
            reused_existing_manifest=False,
            failure=exc.code,
        )


def query_ledger_retrieval(
    command: QueryLedgerRetrievalCommand,
    *,
    ledger_repository: LedgerRetrievalLedger,
    projection: LedgerRetrievalProjectionPort,
    tokenizer: ContextTokenizer,
) -> QueryLedgerRetrievalResult:
    try:
        _validate_query(command)
        normalized_query = normalize_exact_text(command.query_text)
        units, source_snapshot_digest = build_ledger_retrieval_units(ledger_repository)
        manifest = projection.get_complete_manifest()
        if manifest is None:
            raise LedgerRetrievalError(
                LedgerRetrievalFailureCode.INDEX_NOT_FOUND,
                "No complete Ledger retrieval index exists.",
            )
        if manifest.source_snapshot_digest != source_snapshot_digest:
            raise LedgerRetrievalError(
                LedgerRetrievalFailureCode.INDEX_STALE,
                "Ledger retrieval index does not match accepted Ledger state.",
            )
        units_by_id = {unit.retrieval_unit_id: unit for unit in units}
        candidates = _query_candidates(command, projection, manifest, normalized_query)
        candidates = _policy_candidates(candidates, units_by_id, command.policy_id)
        hits = _rank_hits(
            candidates,
            units_by_id,
            manifest.index_manifest_id,
            command.maximum_hits,
            ledger_repository,
        )
        contexts = _context_results(hits, command, ledger_repository, tokenizer)
        record = LedgerRetrievalQueryRecord(
            retrieval_query_id=_query_id(
                command, manifest.index_manifest_id, source_snapshot_digest
            ),
            source_snapshot_digest=source_snapshot_digest,
            query_text=command.query_text,
            normalized_query_text=normalized_query,
            query_policy_id=command.policy_id,
            index_manifest_id=manifest.index_manifest_id,
            record_type=command.filters.record_type,
            record_id=command.filters.record_id,
            assertion_statuses=command.filters.assertion_statuses,
            subject_id=command.filters.subject_id,
            predicate=command.filters.predicate,
            candidate_hits=hits,
            selected_record_ids=tuple(hit.source_record_id for hit in hits if hit.selected),
            context_results=contexts,
        )
        projection.save_query_record(record)
        return QueryLedgerRetrievalResult(
            status="complete",
            retrieval_query_id=record.retrieval_query_id,
            index_manifest_id=manifest.index_manifest_id,
            hits=hits,
            selected_record_ids=record.selected_record_ids,
            context_results=contexts,
            query_policy_id=command.policy_id,
        )
    except LedgerRetrievalError as exc:
        return QueryLedgerRetrievalResult(
            status="failed",
            retrieval_query_id=None,
            index_manifest_id=None,
            hits=(),
            selected_record_ids=(),
            context_results=(),
            failure=exc.code,
            query_policy_id=command.policy_id,
        )


def build_ledger_retrieval_units(
    ledger_repository: LedgerRetrievalLedger,
) -> tuple[tuple[LedgerRetrievalUnit, ...], str]:
    records = tuple(
        item
        for item in ledger_repository.list_accepted_canonical_records()
        if isinstance(item, (Assertion, Relationship, Outcome))
    )
    records = tuple(sorted(records, key=lambda item: (type(item).__name__, item.id)))
    snapshot = _digest(
        [
            {
                "record": item.model_dump(mode="json"),
                "labels": _record_labels(item, ledger_repository),
            }
            for item in records
        ]
    )
    units: list[LedgerRetrievalUnit] = []
    for order, record in enumerate(records):
        record_type = _record_type(record)
        evidence_assertion_ids = _evidence_assertion_ids(record)
        fingerprint = _digest(
            {
                "source_record_id": record.id,
                "record_type": record_type.value,
                "record": record.model_dump(mode="json"),
                "labels": _record_labels(record, ledger_repository),
                "source_snapshot_digest": snapshot,
                "unit_policy_id": LEDGER_UNIT_POLICY_ID,
            }
        )
        units.append(
            LedgerRetrievalUnit(
                retrieval_unit_id=f"lru_{fingerprint[:24]}",
                source_record_id=record.id,
                record_type=record_type,
                evidence_assertion_ids=evidence_assertion_ids,
                assertion_status=record.status if isinstance(record, Assertion) else None,
                subject_id=(
                    record.subject_entity_id
                    if isinstance(record, Assertion)
                    else record.subject_id
                    if isinstance(record, Relationship)
                    else None
                ),
                predicate=(
                    record.predicate if isinstance(record, (Assertion, Relationship)) else None
                ),
                updated_at=record.updated_at,
                source_snapshot_digest=snapshot,
                source_order=order,
                unit_policy_id=LEDGER_UNIT_POLICY_ID,
                unit_fingerprint=fingerprint,
            )
        )
    return tuple(units), snapshot


def build_ledger_exact_lexical_representation(
    unit: LedgerRetrievalUnit,
    ledger_repository: LedgerRetrievalLedger,
) -> LedgerExactLexicalRepresentation:
    record = _record_by_id(unit.source_record_id, ledger_repository)
    text = _projection_text(record, ledger_repository)
    fingerprint = _digest(
        {
            "unit_fingerprint": unit.unit_fingerprint,
            "source_snapshot_digest": unit.source_snapshot_digest,
            "projection_policy_id": LEDGER_PROJECTION_POLICY_ID,
            "projection_builder_version": LEDGER_PROJECTION_BUILDER_VERSION,
            "text": text,
        }
    )
    return LedgerExactLexicalRepresentation(
        retrieval_representation_id=f"lrr_{fingerprint[:24]}",
        retrieval_unit_id=unit.retrieval_unit_id,
        source_snapshot_digest=unit.source_snapshot_digest,
        projection_policy_id=LEDGER_PROJECTION_POLICY_ID,
        projection_builder_version=LEDGER_PROJECTION_BUILDER_VERSION,
        exact_text=normalize_exact_text(text),
        lexical_text=text,
        representation_fingerprint=fingerprint,
    )


def _validate_query(command: QueryLedgerRetrievalCommand) -> None:
    filters = command.filters
    if command.maximum_hits <= 0:
        raise LedgerRetrievalError(
            LedgerRetrievalFailureCode.QUERY_EMPTY, "maximum_hits must be positive."
        )
    if command.policy_id not in {
        LEDGER_CURRENT_RELEVANCE_POLICY_ID,
        LEDGER_CURRENT_LATEST_POLICY_ID,
        LEDGER_AUDIT_HISTORY_POLICY_ID,
    }:
        raise LedgerRetrievalError(
            LedgerRetrievalFailureCode.INVALID_FILTER, "Unknown Ledger query policy."
        )
    if (
        command.policy_id != LEDGER_CURRENT_LATEST_POLICY_ID
        and not normalize_exact_text(command.query_text)
        and not any(
            (
                filters.record_id,
                filters.record_type,
                filters.assertion_statuses,
                filters.subject_id,
                filters.predicate,
            )
        )
    ):
        raise LedgerRetrievalError(
            LedgerRetrievalFailureCode.QUERY_EMPTY, "Ledger query requires text or a filter."
        )
    if (
        filters.assertion_statuses
        and filters.record_type is not LedgerRetrievalRecordType.ASSERTION
    ):
        raise LedgerRetrievalError(
            LedgerRetrievalFailureCode.INVALID_FILTER,
            "Assertion status requires Assertion record type.",
        )
    if (filters.subject_id or filters.predicate) and filters.record_type not in {
        LedgerRetrievalRecordType.ASSERTION,
        LedgerRetrievalRecordType.RELATIONSHIP,
    }:
        raise LedgerRetrievalError(
            LedgerRetrievalFailureCode.INVALID_FILTER,
            "Subject and predicate require Assertion or Relationship record type.",
        )


def _query_candidates(
    command: QueryLedgerRetrievalCommand,
    projection: LedgerRetrievalProjectionPort,
    manifest: LedgerRetrievalIndexManifest,
    normalized_query: str,
) -> tuple[LedgerChannelCandidate, ...]:
    filters = command.filters
    if command.policy_id == LEDGER_CURRENT_LATEST_POLICY_ID:
        return projection.structured_candidates(manifest, filters)
    candidates: list[LedgerChannelCandidate] = []
    if normalized_query:
        candidates.extend(projection.exact_candidates(manifest, normalized_query, filters))
        candidates.extend(projection.lexical_candidates(manifest, command.query_text, filters))
    else:
        candidates.extend(projection.structured_candidates(manifest, filters))
    return tuple(candidates)


def _rank_hits(
    candidates: tuple[LedgerChannelCandidate, ...],
    units: dict[str, LedgerRetrievalUnit],
    manifest_id: str,
    maximum_hits: int,
    ledger_repository: LedgerRetrievalLedger,
) -> tuple[LedgerRetrievalHit, ...]:
    exact = [item for item in candidates if item.channel is RetrievalChannel.EXACT]
    chosen = exact if len(exact) == 1 else list(candidates)
    seen: set[str] = set()
    hits: list[LedgerRetrievalHit] = []
    for candidate in chosen:
        if candidate.retrieval_unit_id in seen:
            continue
        unit = units.get(candidate.retrieval_unit_id)
        if unit is None:
            raise LedgerRetrievalError(
                LedgerRetrievalFailureCode.INDEX_CORRUPT, "Index references an unknown Ledger unit."
            )
        seen.add(unit.retrieval_unit_id)
        terminal = _terminal_evidence_target_ids(unit.evidence_assertion_ids, ledger_repository)
        record = _record_by_id(unit.source_record_id, ledger_repository)
        predecessor_id, successor_id = _assertion_lineage(record, ledger_repository)
        hits.append(
            LedgerRetrievalHit(
                retrieval_unit_id=unit.retrieval_unit_id,
                source_record_id=unit.source_record_id,
                record_type=unit.record_type,
                terminal_evidence_target_ids=terminal,
                channel_observations=(
                    RetrievalChannelObservation(
                        channel=candidate.channel,
                        index_manifest_id=manifest_id,
                        channel_rank=candidate.channel_rank,
                        raw_score=candidate.raw_score,
                        matched_field=candidate.matched_field,
                    ),
                ),
                lineage_predecessor_id=predecessor_id,
                lineage_successor_id=successor_id,
                final_rank=len(hits) + 1,
                selected=True,
                selection_reason=(
                    "unique_exact_guard"
                    if len(exact) == 1 and candidate.channel is RetrievalChannel.EXACT
                    else "ledger_channel_rank"
                ),
            )
        )
        if len(hits) == maximum_hits:
            break
    return tuple(hits)


def _policy_candidates(
    candidates: tuple[LedgerChannelCandidate, ...],
    units: dict[str, LedgerRetrievalUnit],
    policy_id: str,
) -> tuple[LedgerChannelCandidate, ...]:
    current_only = policy_id in {
        LEDGER_CURRENT_RELEVANCE_POLICY_ID,
        LEDGER_CURRENT_LATEST_POLICY_ID,
    }
    result = tuple(
        item
        for item in candidates
        if (unit := units.get(item.retrieval_unit_id)) is not None
        and (
            not current_only
            or unit.assertion_status not in {AssertionStatus.SUPERSEDED, AssertionStatus.RETRACTED}
        )
    )
    if policy_id == LEDGER_CURRENT_LATEST_POLICY_ID:
        return tuple(
            sorted(
                result,
                key=lambda item: (
                    units[item.retrieval_unit_id].updated_at,
                    units[item.retrieval_unit_id].source_record_id,
                ),
                reverse=True,
            )
        )
    return result


def _context_results(
    hits: tuple[LedgerRetrievalHit, ...],
    command: QueryLedgerRetrievalCommand,
    ledger_repository: LedgerRetrievalLedger,
    tokenizer: ContextTokenizer,
) -> tuple[LedgerContextResult, ...]:
    node_ids_by_representation: dict[str, set[str]] = {}
    for hit in hits:
        for evidence_id in hit.terminal_evidence_target_ids:
            evidence = ledger_repository.get_evidence_target(evidence_id)
            if evidence is None:
                raise LedgerRetrievalError(
                    LedgerRetrievalFailureCode.EVIDENCE_MISSING,
                    "Terminal EvidenceTarget is missing a representation.",
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
                    policy_id=LEDGER_CONTEXT_PLANNER_POLICY_ID,
                    task_type="ledger_retrieval",
                ),
                ledger_repository,
            )
            outcome = build_context_manifest(
                ContextManifestInput(
                    analysis_unit=unit,
                    model_profile=_context_profile(command.context_profile_id),
                    prompt_id="ledger-retrieval-validation-prompt-v1",
                    prompt_bytes=b"Use only the supplied original source evidence.",
                    schema_id="ledger-retrieval-validation-schema-v1",
                    schema_bytes=b'{"type":"object"}',
                    renderer_version="ledger-retrieval-context-v1",
                ),
                ledger_repository,
                tokenizer,
            )
            manifest = outcome.manifest
            results.append(
                LedgerContextResult(
                    representation_id=representation_id,
                    focus_node_ids=focus_ids,
                    analysis_unit_id=unit.id,
                    context_manifest_id=manifest.id,
                    status=manifest.status.value,
                    blocked_reason=manifest.blocked_reason,
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
    assertion_ids: tuple[str, ...], ledger_repository: LedgerRetrievalLedger
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
            raise LedgerRetrievalError(
                LedgerRetrievalFailureCode.EVIDENCE_MISSING,
                "Evidence Assertion is missing or proposed.",
            )
        if assertion.assertion_type is AssertionType.ANALYTIC_INFERENCE:
            pending.extend(assertion.supporting_assertion_ids)
        else:
            evidence_ids.update(assertion.evidence_target_ids)
    if not evidence_ids:
        raise LedgerRetrievalError(
            LedgerRetrievalFailureCode.EVIDENCE_MISSING,
            "Ledger result has no terminal EvidenceTarget.",
        )
    return tuple(sorted(evidence_ids))


def _record_type(record: Assertion | Relationship | Outcome) -> LedgerRetrievalRecordType:
    if isinstance(record, Assertion):
        return LedgerRetrievalRecordType.ASSERTION
    if isinstance(record, Relationship):
        return LedgerRetrievalRecordType.RELATIONSHIP
    return LedgerRetrievalRecordType.OUTCOME


def _evidence_assertion_ids(record: Assertion | Relationship | Outcome) -> tuple[str, ...]:
    return (record.id,) if isinstance(record, Assertion) else record.assertion_ids


def _record_by_id(
    record_id: str, ledger_repository: LedgerRetrievalLedger
) -> Assertion | Relationship | Outcome:
    for record in ledger_repository.list_accepted_canonical_records():
        if record.id == record_id and isinstance(record, (Assertion, Relationship, Outcome)):
            return record
    raise LedgerRetrievalError(
        LedgerRetrievalFailureCode.INDEX_CORRUPT, "Ledger unit record is missing."
    )


def _assertion_lineage(
    record: Assertion | Relationship | Outcome,
    ledger_repository: LedgerRetrievalLedger,
) -> tuple[str | None, str | None]:
    if not isinstance(record, Assertion):
        return None, None
    successor_id = next(
        (
            item.id
            for item in ledger_repository.list_accepted_canonical_records()
            if isinstance(item, Assertion) and item.supersedes_assertion_id == record.id
        ),
        None,
    )
    return record.supersedes_assertion_id, successor_id


def _record_labels(
    record: Assertion | Relationship | Outcome, ledger_repository: LedgerRetrievalLedger
) -> tuple[str, ...]:
    if isinstance(record, Assertion):
        labels = [_entity_label(record.subject_entity_id, ledger_repository)]
        if record.object_entity_id is not None:
            labels.append(_entity_label(record.object_entity_id, ledger_repository))
        return tuple(labels)
    if isinstance(record, Relationship):
        return (
            _entity_label(record.subject_id, ledger_repository),
            _entity_label(record.object_id, ledger_repository),
        )
    return tuple(
        _entity_label(identifier, ledger_repository)
        for identifier in (*record.actor_ids, *record.organization_ids, *record.event_ids)
    )


def _projection_text(
    record: Assertion | Relationship | Outcome, ledger_repository: LedgerRetrievalLedger
) -> str:
    labels = _record_labels(record, ledger_repository)
    if isinstance(record, Assertion):
        object_text = (
            labels[1]
            if record.object_entity_id is not None
            else json.dumps(record.object_value, sort_keys=True)
        )
        qualifiers = json.dumps(record.qualifiers, sort_keys=True)
        return " ".join(
            (labels[0], record.predicate, object_text, qualifiers, record.current_assessment)
        )
    if isinstance(record, Relationship):
        return " ".join((labels[0], record.predicate, labels[1]))
    return " ".join((record.description, *labels))


def _entity_label(record_id: str, ledger_repository: LedgerRetrievalLedger) -> str:
    record: Entity | Actor | Organization | Event | Place | None
    if record_id.startswith("ent_"):
        record = ledger_repository.get_entity(record_id)
    elif record_id.startswith("act_"):
        record = ledger_repository.get_actor(record_id)
    elif record_id.startswith("org_"):
        record = ledger_repository.get_organization(record_id)
    elif record_id.startswith("evt_"):
        record = ledger_repository.get_event(record_id)
    elif record_id.startswith("plc_"):
        record = ledger_repository.get_place(record_id)
    else:
        record = None
    if record is None:
        raise LedgerRetrievalError(
            LedgerRetrievalFailureCode.EVIDENCE_MISSING, f"Missing lookup record: {record_id}"
        )
    return record.canonical_name if isinstance(record, Entity) else record.name


def _index_manifest(
    source_snapshot_digest: str,
    units: tuple[LedgerRetrievalUnit, ...],
    representations: tuple[LedgerExactLexicalRepresentation, ...],
) -> LedgerRetrievalIndexManifest:
    content_fingerprint = _digest(
        {
            "source_snapshot_digest": source_snapshot_digest,
            "unit_fingerprints": tuple(item.unit_fingerprint for item in units),
            "representation_fingerprints": tuple(
                item.representation_fingerprint for item in representations
            ),
        }
    )
    return LedgerRetrievalIndexManifest(
        index_manifest_id=f"lrm_{content_fingerprint[:24]}",
        channels=(
            RetrievalChannel.EXACT,
            RetrievalChannel.LEXICAL,
            RetrievalChannel.STRUCTURED_FILTER,
        ),
        source_snapshot_digest=source_snapshot_digest,
        unit_policy_id=LEDGER_UNIT_POLICY_ID,
        projection_policy_id=LEDGER_PROJECTION_POLICY_ID,
        query_policy_compatibility=LEDGER_CURRENT_RELEVANCE_POLICY_ID,
        adapter_identity="sqlite_ledger_retrieval_v1",
        adapter_configuration_digest=_digest({"adapter": "sqlite_ledger_retrieval_v1"}),
        unit_count=len(units),
        representation_count=len(representations),
        content_fingerprint=content_fingerprint,
        publication_status="complete",
        published_at=datetime.now(UTC),
    )


def _query_id(command: QueryLedgerRetrievalCommand, manifest_id: str, snapshot: str) -> str:
    fingerprint = _digest(
        {
            "query": command.query_text,
            "filters": command.filters.__dict__,
            "policy": command.policy_id,
            "manifest": manifest_id,
            "snapshot": snapshot,
        }
    )
    return f"lrq_{fingerprint[:24]}"


def _context_profile(profile_id: str) -> ContextModelProfile:
    if not profile_id.strip():
        raise LedgerRetrievalError(
            LedgerRetrievalFailureCode.CONTEXT_PLANNING_FAILED, "Context profile is empty."
        )
    return ContextModelProfile(profile_id, 16384, 512, 128)


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str
        ).encode("utf-8")
    ).hexdigest()
