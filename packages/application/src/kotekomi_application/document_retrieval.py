"""Derived document-plane exact and lexical retrieval use cases."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Protocol

from kotekomi_domain import (
    DocumentExactLexicalRepresentation,
    DocumentRepresentationBundle,
    DocumentRetrievalUnit,
    RepresentationAnalyzability,
    RetrievalChannel,
    RetrievalChannelObservation,
    RetrievalHit,
    RetrievalIndexManifest,
    RetrievalQueryRecord,
    canonical_representation_digest,
    deterministic_document_retrieval_unit_id,
    deterministic_retrieval_representation_id,
    document_exact_lexical_representation_fingerprint,
    document_retrieval_unit_fingerprint,
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

DOCUMENT_UNIT_POLICY_ID = "document_node_unit_v1"
DOCUMENT_PROJECTION_POLICY_ID = "document_exact_lexical_projection_v1"
DOCUMENT_QUERY_POLICY_ID = "document_exact_before_lexical_v1"
DOCUMENT_PROJECTION_BUILDER_VERSION = "dr1_document_projection_v1"
RETRIEVAL_CONTEXT_PLANNER_POLICY_ID = "retrieval_selection_v1"


class RetrievalFailureCode(StrEnum):
    REPRESENTATION_NOT_FOUND = "retrieval_representation_not_found"
    REPRESENTATION_NOT_ACCEPTABLE = "retrieval_representation_not_acceptable"
    SOURCE_SNAPSHOT_MISMATCH = "retrieval_source_snapshot_mismatch"
    INDEX_NOT_FOUND = "retrieval_index_not_found"
    INDEX_STALE = "retrieval_index_stale"
    INDEX_INCOMPLETE = "retrieval_index_incomplete"
    INDEX_CORRUPT = "retrieval_index_corrupt"
    QUERY_EMPTY = "retrieval_query_empty"
    HIT_SOURCE_MISSING = "retrieval_hit_source_missing"
    HIT_DIGEST_MISMATCH = "retrieval_hit_digest_mismatch"
    CONTEXT_PLANNING_FAILED = "retrieval_context_planning_failed"


class DocumentRetrievalError(ValueError):
    def __init__(self, code: RetrievalFailureCode, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class BuildDocumentRetrievalProjectionCommand:
    representation_id: str
    expected_representation_digest: str | None = None


@dataclass(frozen=True)
class QueryDocumentRetrievalCommand:
    representation_id: str
    query_text: str
    maximum_hits: int
    context_profile_id: str
    expected_index_manifest_id: str | None = None


@dataclass(frozen=True)
class BuildDocumentRetrievalProjectionResult:
    status: str
    representation_id: str
    index_manifest_id: str | None
    unit_count: int
    representation_count: int
    content_fingerprint: str | None
    reused_existing_manifest: bool
    failure: RetrievalFailureCode | None = None


@dataclass(frozen=True)
class QueryDocumentRetrievalResult:
    status: str
    retrieval_query_id: str | None
    representation_id: str
    index_manifest_ids: tuple[str, ...]
    hits: tuple[RetrievalHit, ...]
    selected_node_ids: tuple[str, ...]
    analysis_unit_id: str | None
    context_manifest_id: str | None
    context_manifest_rendered_input: bytes | None
    failure: RetrievalFailureCode | None = None


@dataclass(frozen=True)
class ProjectionBuildInput:
    manifest: RetrievalIndexManifest
    units: tuple[DocumentRetrievalUnit, ...]
    representations: tuple[DocumentExactLexicalRepresentation, ...]


@dataclass(frozen=True)
class ChannelCandidate:
    retrieval_unit_id: str
    channel: RetrievalChannel
    channel_rank: int
    raw_score: float | None = None
    matched_field: str | None = None
    matched_literal_digest: str | None = None


class DocumentRetrievalProjectionPort(Protocol):
    def publish(self, build: ProjectionBuildInput) -> tuple[RetrievalIndexManifest, bool]: ...

    def get_complete_manifest(self, representation_id: str) -> RetrievalIndexManifest | None: ...

    def exact_candidates(
        self, manifest: RetrievalIndexManifest, normalized_query: str
    ) -> tuple[ChannelCandidate, ...]: ...

    def lexical_candidates(
        self, manifest: RetrievalIndexManifest, query_text: str
    ) -> tuple[ChannelCandidate, ...]: ...

    def save_query_record(self, record: RetrievalQueryRecord) -> None: ...


def normalize_exact_text(value: str) -> str:
    """Apply the DR-1 literal-match normalization without changing punctuation or case."""
    normalized = unicodedata.normalize("NFC", value).replace("\r\n", "\n").replace("\r", "\n")
    return re.sub(r"\s+", " ", normalized).strip()


def build_document_retrieval_projection(
    command: BuildDocumentRetrievalProjectionCommand,
    *,
    ledger_repository: ContextPlanningLedger,
    projection: DocumentRetrievalProjectionPort,
) -> BuildDocumentRetrievalProjectionResult:
    try:
        bundle, representation_digest = _load_acceptable_bundle(
            command.representation_id, ledger_repository
        )
        if (
            command.expected_representation_digest is not None
            and command.expected_representation_digest != representation_digest
        ):
            raise DocumentRetrievalError(
                RetrievalFailureCode.SOURCE_SNAPSHOT_MISMATCH,
                "Document retrieval representation digest does not match the requested snapshot.",
            )
        units = build_document_retrieval_units(bundle, representation_digest)
        representations = tuple(
            build_document_exact_lexical_representation(unit, bundle, representation_digest)
            for unit in units
        )
        manifest = _index_manifest(bundle, representation_digest, units, representations)
        published, reused = projection.publish(
            ProjectionBuildInput(manifest=manifest, units=units, representations=representations)
        )
        return BuildDocumentRetrievalProjectionResult(
            status="complete",
            representation_id=command.representation_id,
            index_manifest_id=published.index_manifest_id,
            unit_count=len(units),
            representation_count=len(representations),
            content_fingerprint=published.content_fingerprint,
            reused_existing_manifest=reused,
        )
    except DocumentRetrievalError as exc:
        return BuildDocumentRetrievalProjectionResult(
            status="failed",
            representation_id=command.representation_id,
            index_manifest_id=None,
            unit_count=0,
            representation_count=0,
            content_fingerprint=None,
            reused_existing_manifest=False,
            failure=exc.code,
        )


def query_document_retrieval(
    command: QueryDocumentRetrievalCommand,
    *,
    ledger_repository: ContextPlanningLedger,
    projection: DocumentRetrievalProjectionPort,
    tokenizer: ContextTokenizer,
) -> QueryDocumentRetrievalResult:
    """Retrieve authoritative nodes and hand their identities to ContextPlanner."""
    try:
        if command.maximum_hits <= 0:
            raise DocumentRetrievalError(
                RetrievalFailureCode.QUERY_EMPTY, "maximum_hits must be positive."
            )
        normalized_query = normalize_exact_text(command.query_text)
        if not normalized_query:
            raise DocumentRetrievalError(
                RetrievalFailureCode.QUERY_EMPTY, "Retrieval query is empty."
            )
        bundle, representation_digest = _load_acceptable_bundle(
            command.representation_id, ledger_repository
        )
        manifest = projection.get_complete_manifest(command.representation_id)
        if manifest is None:
            raise DocumentRetrievalError(
                RetrievalFailureCode.INDEX_NOT_FOUND, "No complete retrieval index exists."
            )
        _validate_manifest(
            manifest, bundle, representation_digest, command.expected_index_manifest_id
        )
        units = {
            unit.retrieval_unit_id: unit
            for unit in build_document_retrieval_units(bundle, representation_digest)
        }
        exact = projection.exact_candidates(manifest, normalized_query)
        lexical = projection.lexical_candidates(manifest, command.query_text)
        hits = _rank_hits(exact, lexical, units, manifest.index_manifest_id, command.maximum_hits)
        _validate_hit_sources(hits, units, bundle)
        selected_node_ids = tuple(
            node_id for hit in hits if hit.selected for node_id in hit.authoritative_node_ids
        )
        analysis_unit_id: str | None = None
        context_manifest_id: str | None = None
        rendered_input: bytes | None = None
        if selected_node_ids:
            try:
                unit = create_analysis_unit_from_retrieval_selection(
                    RetrievalSelectionAnalysisUnitInput(
                        representation_id=command.representation_id,
                        focus_node_ids=selected_node_ids,
                        policy_id=RETRIEVAL_CONTEXT_PLANNER_POLICY_ID,
                    ),
                    ledger_repository,
                )
                outcome = build_context_manifest(
                    ContextManifestInput(
                        analysis_unit=unit,
                        model_profile=_context_profile(command.context_profile_id),
                        prompt_id="retrieval-validation-prompt-v1",
                        prompt_bytes=b"Use only the supplied original source evidence.",
                        schema_id="retrieval-validation-schema-v1",
                        schema_bytes=b'{"type":"object"}',
                        renderer_version="retrieval-validation-renderer-v1",
                    ),
                    ledger_repository,
                    tokenizer,
                )
                analysis_unit_id = unit.id
                context_manifest_id = outcome.manifest.id
                rendered_input = outcome.manifest.rendered_input
            except ValueError as exc:
                raise DocumentRetrievalError(
                    RetrievalFailureCode.CONTEXT_PLANNING_FAILED, str(exc)
                ) from exc
        query_record = RetrievalQueryRecord(
            retrieval_query_id=_query_id(
                command.representation_id, command.query_text, manifest.index_manifest_id
            ),
            representation_id=command.representation_id,
            source_snapshot_id=manifest.source_snapshot_id,
            query_text=command.query_text,
            normalized_query_text=normalized_query,
            query_policy_id=DOCUMENT_QUERY_POLICY_ID,
            index_manifest_ids=(manifest.index_manifest_id,),
            candidate_hits=hits,
            selected_node_ids=selected_node_ids,
            analysis_unit_id=analysis_unit_id,
            context_manifest_id=context_manifest_id,
        )
        projection.save_query_record(query_record)
        return QueryDocumentRetrievalResult(
            status="complete",
            retrieval_query_id=query_record.retrieval_query_id,
            representation_id=command.representation_id,
            index_manifest_ids=(manifest.index_manifest_id,),
            hits=hits,
            selected_node_ids=selected_node_ids,
            analysis_unit_id=analysis_unit_id,
            context_manifest_id=context_manifest_id,
            context_manifest_rendered_input=rendered_input,
        )
    except DocumentRetrievalError as exc:
        return QueryDocumentRetrievalResult(
            status="failed",
            retrieval_query_id=None,
            representation_id=command.representation_id,
            index_manifest_ids=(),
            hits=(),
            selected_node_ids=(),
            analysis_unit_id=None,
            context_manifest_id=None,
            context_manifest_rendered_input=None,
            failure=exc.code,
        )


def build_document_retrieval_units(
    bundle: DocumentRepresentationBundle, representation_digest: str
) -> tuple[DocumentRetrievalUnit, ...]:
    logical = next(view for view in bundle.text_views if view.kind.value == "logical")
    eligible = tuple(
        node
        for node in sorted(bundle.nodes, key=lambda node: (node.order_index, node.id))
        if node.text_view_id == logical.id
        and node.node_type not in {"document", "furniture", "header", "footer"}
        and node.end_char > node.start_char
    )
    units: list[DocumentRetrievalUnit] = []
    for node in eligible:
        section_path = node.section_path
        text = logical.text[node.start_char : node.end_char]
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        fingerprint = document_retrieval_unit_fingerprint(
            source_snapshot_id=bundle.representation.input_blob_digest,
            representation_id=bundle.representation.id,
            node_ids=(node.id,),
            source_order=node.order_index,
            structural_role=node.node_type,
            section_path=section_path,
            source_page_numbers=node.source_page_numbers,
            original_text_digest=digest,
            unit_policy_id=DOCUMENT_UNIT_POLICY_ID,
        )
        units.append(
            DocumentRetrievalUnit(
                retrieval_unit_id=deterministic_document_retrieval_unit_id(fingerprint),
                source_snapshot_id=bundle.representation.input_blob_digest,
                representation_id=bundle.representation.id,
                node_ids=(node.id,),
                source_order=node.order_index,
                structural_role=node.node_type,
                section_path=section_path,
                source_page_numbers=node.source_page_numbers,
                original_text_digest=digest,
                unit_fingerprint=fingerprint,
            )
        )
    return tuple(units)


def build_document_exact_lexical_representation(
    unit: DocumentRetrievalUnit,
    bundle: DocumentRepresentationBundle,
    representation_digest: str,
) -> DocumentExactLexicalRepresentation:
    node = next(node for node in bundle.nodes if node.id == unit.node_ids[0])
    view = next(view for view in bundle.text_views if view.id == node.text_view_id)
    body = view.text[node.start_char : node.end_char]
    title = next(
        (
            view.text[candidate.start_char : candidate.end_char]
            for candidate in sorted(bundle.nodes, key=lambda candidate: candidate.order_index)
            if candidate.node_type == "heading" and candidate.text_view_id == view.id
        ),
        bundle.representation.document_id,
    )
    exact_fields = {
        "body_nfc": normalize_exact_text(body),
        "body_casefold": normalize_exact_text(body).casefold(),
        "source_title_nfc": normalize_exact_text(title),
        "heading_path_nfc": normalize_exact_text(" / ".join(unit.section_path)),
    }
    lexical_fields = {
        "body": body,
        "heading_path": " / ".join(unit.section_path),
        "source_title": title,
        "structural_role": unit.structural_role,
    }
    field_digests = {
        name: hashlib.sha256(value.encode("utf-8")).hexdigest()
        for name, value in {**exact_fields, **lexical_fields}.items()
    }
    fingerprint = document_exact_lexical_representation_fingerprint(
        retrieval_unit_id=unit.retrieval_unit_id,
        source_snapshot_id=unit.source_snapshot_id,
        source_fingerprint=representation_digest,
        projection_policy_id=DOCUMENT_PROJECTION_POLICY_ID,
        projection_builder_version=DOCUMENT_PROJECTION_BUILDER_VERSION,
        exact_fields=exact_fields,
        lexical_fields=lexical_fields,
        field_digests=field_digests,
    )
    return DocumentExactLexicalRepresentation(
        retrieval_representation_id=deterministic_retrieval_representation_id(fingerprint),
        retrieval_unit_id=unit.retrieval_unit_id,
        source_snapshot_id=unit.source_snapshot_id,
        source_fingerprint=representation_digest,
        projection_builder_version=DOCUMENT_PROJECTION_BUILDER_VERSION,
        exact_fields=exact_fields,
        lexical_fields=lexical_fields,
        field_digests=field_digests,
        representation_fingerprint=fingerprint,
    )


def _load_acceptable_bundle(
    representation_id: str, ledger_repository: ContextPlanningLedger
) -> tuple[DocumentRepresentationBundle, str]:
    bundle = ledger_repository.get_document_representation_bundle(representation_id)
    if bundle is None:
        raise DocumentRetrievalError(
            RetrievalFailureCode.REPRESENTATION_NOT_FOUND, "Representation not found."
        )
    if bundle.quality_report.analyzability is not RepresentationAnalyzability.ACCEPTABLE:
        raise DocumentRetrievalError(
            RetrievalFailureCode.REPRESENTATION_NOT_ACCEPTABLE,
            "Document retrieval requires an acceptable representation.",
        )
    digest = canonical_representation_digest(
        bundle.representation,
        text_views=bundle.text_views,
        nodes=bundle.nodes,
        edges=bundle.edges,
        source_regions=bundle.source_regions,
        quality_report=bundle.quality_report,
        tables=bundle.tables,
        table_fragments=bundle.table_fragments,
        table_rows=bundle.table_rows,
        table_cells=bundle.table_cells,
        table_annotations=bundle.table_annotations,
        references=bundle.references,
        source_selectors=bundle.source_selectors,
    )
    if digest != bundle.representation.canonical_output_digest:
        raise DocumentRetrievalError(
            RetrievalFailureCode.INDEX_CORRUPT, "Representation digest is corrupt."
        )
    return bundle, digest


def _index_manifest(
    bundle: DocumentRepresentationBundle,
    representation_digest: str,
    units: tuple[DocumentRetrievalUnit, ...],
    representations: tuple[DocumentExactLexicalRepresentation, ...],
) -> RetrievalIndexManifest:
    content_fingerprint = _digest(
        {
            "representation_digest": representation_digest,
            "unit_fingerprints": tuple(unit.unit_fingerprint for unit in units),
            "representation_fingerprints": tuple(
                representation.representation_fingerprint for representation in representations
            ),
        }
    )
    config_digest = _digest({"fts5_tokenizer": "unicode61", "bm25": "default"})
    manifest_id = f"rim_{content_fingerprint[:24]}"
    return RetrievalIndexManifest(
        index_manifest_id=manifest_id,
        channels=(RetrievalChannel.EXACT, RetrievalChannel.LEXICAL),
        source_snapshot_id=bundle.representation.input_blob_digest,
        representation_id=bundle.representation.id,
        representation_digest=representation_digest,
        unit_policy_id=DOCUMENT_UNIT_POLICY_ID,
        projection_policy_id=DOCUMENT_PROJECTION_POLICY_ID,
        query_policy_compatibility=DOCUMENT_QUERY_POLICY_ID,
        adapter_identity="sqlite_document_retrieval_fts5_v1",
        adapter_configuration_digest=config_digest,
        unit_count=len(units),
        representation_count=len(representations),
        content_fingerprint=content_fingerprint,
        publication_status="complete",
        published_at=datetime.now(UTC),
    )


def _validate_manifest(
    manifest: RetrievalIndexManifest,
    bundle: DocumentRepresentationBundle,
    representation_digest: str,
    expected_index_manifest_id: str | None,
) -> None:
    if (
        expected_index_manifest_id is not None
        and manifest.index_manifest_id != expected_index_manifest_id
    ):
        raise DocumentRetrievalError(
            RetrievalFailureCode.INDEX_STALE, "Requested index manifest is not current."
        )
    if manifest.publication_status != "complete":
        raise DocumentRetrievalError(
            RetrievalFailureCode.INDEX_INCOMPLETE, "Index is not complete."
        )
    if (
        manifest.representation_digest != representation_digest
        or manifest.source_snapshot_id != bundle.representation.input_blob_digest
    ):
        raise DocumentRetrievalError(
            RetrievalFailureCode.INDEX_STALE, "Index does not match authoritative source."
        )


def _rank_hits(
    exact: tuple[ChannelCandidate, ...],
    lexical: tuple[ChannelCandidate, ...],
    units: dict[str, DocumentRetrievalUnit],
    manifest_id: str,
    maximum_hits: int,
) -> tuple[RetrievalHit, ...]:
    observations: dict[str, list[RetrievalChannelObservation]] = {}
    for candidate in (*exact, *lexical):
        if candidate.retrieval_unit_id not in units:
            raise DocumentRetrievalError(
                RetrievalFailureCode.INDEX_CORRUPT, "Index references an unknown unit."
            )
        observations.setdefault(candidate.retrieval_unit_id, []).append(
            RetrievalChannelObservation(
                channel=candidate.channel,
                channel_rank=candidate.channel_rank,
                raw_score=candidate.raw_score,
                matched_field=candidate.matched_field,
                matched_literal_digest=candidate.matched_literal_digest,
            )
        )
    def sort_key(unit_id: str) -> tuple[int, int, int, str]:
        unit = units[unit_id]
        channel_rows = observations[unit_id]
        exact_row = next(
            (row for row in channel_rows if row.channel is RetrievalChannel.EXACT), None
        )
        lexical_row = next(
            (row for row in channel_rows if row.channel is RetrievalChannel.LEXICAL), None
        )
        return (
            0 if exact_row is not None else 1,
            exact_row.channel_rank
            if exact_row is not None
            else lexical_row.channel_rank
            if lexical_row
            else 0,
            unit.source_order,
            unit_id,
        )
    ordered = sorted(observations, key=sort_key)[:maximum_hits]
    return tuple(
        RetrievalHit(
            retrieval_unit_id=unit_id,
            authoritative_node_ids=units[unit_id].node_ids,
            original_text_digest=units[unit_id].original_text_digest,
            index_manifest_id=manifest_id,
            channel_observations=tuple(
                sorted(observations[unit_id], key=lambda row: (row.channel.value, row.channel_rank))
            ),
            final_rank=rank,
            selected=True,
            selection_reason=(
                "exact_before_lexical" if any(
                    row.channel is RetrievalChannel.EXACT for row in observations[unit_id]
                ) else "lexical_fallback"
            ),
        )
        for rank, unit_id in enumerate(ordered, start=1)
    )


def _validate_hit_sources(
    hits: tuple[RetrievalHit, ...],
    units: dict[str, DocumentRetrievalUnit],
    bundle: DocumentRepresentationBundle,
) -> None:
    nodes = {node.id: node for node in bundle.nodes}
    views = {view.id: view for view in bundle.text_views}
    for hit in hits:
        unit = units[hit.retrieval_unit_id]
        for node_id in hit.authoritative_node_ids:
            node = nodes.get(node_id)
            if node is None:
                raise DocumentRetrievalError(
                    RetrievalFailureCode.HIT_SOURCE_MISSING, "Hit node is missing."
                )
            text = views[node.text_view_id].text[node.start_char : node.end_char]
            if hashlib.sha256(text.encode("utf-8")).hexdigest() != unit.original_text_digest:
                raise DocumentRetrievalError(
                    RetrievalFailureCode.HIT_DIGEST_MISMATCH, "Hit source digest changed."
                )


def _context_profile(profile_id: str) -> ContextModelProfile:
    if profile_id != "retrieval-validation-v1":
        raise DocumentRetrievalError(
            RetrievalFailureCode.CONTEXT_PLANNING_FAILED,
            "Unknown retrieval context profile.",
        )
    return ContextModelProfile(profile_id, 16384, 512, 128)


def _query_id(representation_id: str, query_text: str, manifest_id: str) -> str:
    return f"rqr_{_digest((representation_id, query_text, manifest_id))[:24]}"


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()
