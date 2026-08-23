"""Derived document-plane exact and lexical retrieval use cases."""

from __future__ import annotations

import hashlib
import json
import math
import re
import struct
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Protocol

from kotekomi_domain import (
    DocumentExactLexicalRepresentation,
    DocumentNode,
    DocumentRepresentationBundle,
    DocumentRetrievalUnit,
    DocumentSemanticRepresentation,
    EmbeddingModelIdentity,
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
    document_semantic_representation_fingerprint,
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

DOCUMENT_UNIT_POLICY_ID = "document_node_hierarchy_unit_v2"
DOCUMENT_PROJECTION_POLICY_ID = "document_exact_lexical_projection_v1"
DOCUMENT_QUERY_POLICY_ID = "document_exact_before_lexical_v1"
DOCUMENT_PROJECTION_BUILDER_VERSION = "dr1_document_projection_v1"
DOCUMENT_SEMANTIC_PROJECTION_POLICY_ID = "document_semantic_projection_v1"
DOCUMENT_SEMANTIC_QUERY_POLICY_ID = "document_semantic_v1"
DOCUMENT_SEMANTIC_BUILDER_VERSION = "dr2_document_semantic_v1"
DOCUMENT_SEMANTIC_RENDERER_POLICY_ID = "document_structural_context_v1"
DOCUMENT_HYBRID_QUERY_POLICY_ID = "document_exact_lexical_semantic_rrf60_v1"
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
    SEMANTIC_INPUT_TOO_LARGE = "semantic_input_too_large"
    EMBEDDING_PROFILE_MISMATCH = "embedding_profile_mismatch"
    EMBEDDING_RESPONSE_INVALID = "embedding_response_invalid"


class DocumentRetrievalError(ValueError):
    def __init__(self, code: RetrievalFailureCode, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class BuildDocumentRetrievalProjectionCommand:
    representation_id: str
    expected_representation_digest: str | None = None


@dataclass(frozen=True)
class EmbeddingProfile:
    """Local, pinned configuration for one derived embedding build/query boundary."""

    profile_id: str
    adapter_id: str
    endpoint: str
    model_id: str
    model_path: str
    model_digest: str
    expected_vector_dimension: int
    maximum_rendered_characters: int
    timeout_seconds: float = 300.0


@dataclass(frozen=True)
class EmbeddingBatch:
    model_identity: EmbeddingModelIdentity
    vectors: tuple[tuple[float, ...], ...]


@dataclass(frozen=True)
class SemanticVectorRecord:
    retrieval_unit_id: str
    vector: bytes
    vector_digest: str


@dataclass(frozen=True)
class BuildDocumentSemanticProjectionCommand:
    representation_id: str
    embedding_profile: EmbeddingProfile
    expected_representation_digest: str | None = None


@dataclass(frozen=True)
class QueryDocumentRetrievalCommand:
    representation_id: str
    query_text: str
    maximum_hits: int
    context_profile_id: str
    expected_index_manifest_id: str | None = None


@dataclass(frozen=True)
class QueryDocumentSemanticRetrievalCommand:
    representation_id: str
    query_text: str
    maximum_hits: int
    context_profile_id: str
    embedding_profile: EmbeddingProfile
    expected_index_manifest_id: str | None = None


@dataclass(frozen=True)
class QueryDocumentHybridRetrievalCommand:
    representation_id: str
    query_text: str
    maximum_hits: int
    context_profile_id: str
    embedding_profile: EmbeddingProfile


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
    embedding_profile_id: str | None = None
    embedding_model_identity: EmbeddingModelIdentity | None = None


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
    embedding_profile_id: str | None = None
    embedding_model_identity: EmbeddingModelIdentity | None = None
    query_policy_id: str | None = None
    consulted_channels: tuple[RetrievalChannel, ...] = ()


@dataclass(frozen=True)
class ProjectionBuildInput:
    manifest: RetrievalIndexManifest
    units: tuple[DocumentRetrievalUnit, ...]
    representations: tuple[DocumentExactLexicalRepresentation, ...]


@dataclass(frozen=True)
class SemanticProjectionBuildInput:
    manifest: RetrievalIndexManifest
    units: tuple[DocumentRetrievalUnit, ...]
    representations: tuple[DocumentSemanticRepresentation, ...]
    vectors: tuple[SemanticVectorRecord, ...]


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


class EmbeddingPort(Protocol):
    def embed(self, profile: EmbeddingProfile, inputs: tuple[str, ...]) -> EmbeddingBatch: ...


class DocumentSemanticProjectionPort(Protocol):
    def publish_semantic(
        self, build: SemanticProjectionBuildInput
    ) -> tuple[RetrievalIndexManifest, bool]: ...

    def get_complete_semantic_manifest(
        self, representation_id: str, profile_id: str
    ) -> RetrievalIndexManifest | None: ...

    def semantic_candidates(
        self, manifest: RetrievalIndexManifest, query_vector: bytes
    ) -> tuple[ChannelCandidate, ...]: ...

    def delete_semantic_projection(self, representation_id: str, profile_id: str) -> None: ...

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


def build_document_semantic_projection(
    command: BuildDocumentSemanticProjectionCommand,
    *,
    ledger_repository: ContextPlanningLedger,
    projection: DocumentSemanticProjectionPort,
    embedding: EmbeddingPort,
) -> BuildDocumentRetrievalProjectionResult:
    """Build one disposable semantic index from a pinned authoritative bundle."""
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
        rendered = tuple(render_document_semantic_input(unit, bundle) for unit in units)
        for unit, value in zip(units, rendered, strict=True):
            if len(value) > command.embedding_profile.maximum_rendered_characters:
                raise DocumentRetrievalError(
                    RetrievalFailureCode.SEMANTIC_INPUT_TOO_LARGE,
                    "Semantic input exceeds the configured character limit for "
                    f"unit {unit.retrieval_unit_id} and profile "
                    f"{command.embedding_profile.profile_id}.",
                )
        batch = embedding.embed(command.embedding_profile, rendered)
        _validate_embedding_batch(batch, command.embedding_profile, len(rendered))
        vectors = tuple(
            _normalized_vector_record(unit.retrieval_unit_id, vector)
            for unit, vector in zip(units, batch.vectors, strict=True)
        )
        representations = tuple(
            build_document_semantic_representation(unit, representation_digest, value)
            for unit, value in zip(units, rendered, strict=True)
        )
        manifest = _semantic_index_manifest(
            bundle,
            representation_digest,
            units,
            representations,
            vectors,
            batch.model_identity,
            command.embedding_profile,
        )
        published, reused = projection.publish_semantic(
            SemanticProjectionBuildInput(
                manifest=manifest,
                units=units,
                representations=representations,
                vectors=vectors,
            )
        )
        return BuildDocumentRetrievalProjectionResult(
            status="complete",
            representation_id=command.representation_id,
            index_manifest_id=published.index_manifest_id,
            unit_count=len(units),
            representation_count=len(representations),
            content_fingerprint=published.content_fingerprint,
            reused_existing_manifest=reused,
            embedding_profile_id=command.embedding_profile.profile_id,
            embedding_model_identity=batch.model_identity,
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


def _ensure_exact_lexical_projection(
    representation_id: str,
    ledger_repository: ContextPlanningLedger,
    projection: DocumentRetrievalProjectionPort,
) -> None:
    bundle, representation_digest = _load_acceptable_bundle(representation_id, ledger_repository)
    manifest = projection.get_complete_manifest(representation_id)
    if manifest is not None:
        try:
            _validate_manifest(manifest, bundle, representation_digest, None)
            return
        except DocumentRetrievalError as exc:
            if exc.code is not RetrievalFailureCode.INDEX_STALE:
                raise
    result = build_document_retrieval_projection(
        BuildDocumentRetrievalProjectionCommand(representation_id),
        ledger_repository=ledger_repository,
        projection=projection,
    )
    if result.status != "complete":
        raise DocumentRetrievalError(
            result.failure or RetrievalFailureCode.INDEX_CORRUPT,
            "Document exact-lexical projection readiness failed.",
        )


def _ensure_semantic_projection(
    representation_id: str,
    embedding_profile: EmbeddingProfile,
    ledger_repository: ContextPlanningLedger,
    projection: DocumentSemanticProjectionPort,
    embedding: EmbeddingPort,
) -> None:
    bundle, representation_digest = _load_acceptable_bundle(representation_id, ledger_repository)
    manifest = projection.get_complete_semantic_manifest(
        representation_id, embedding_profile.profile_id
    )
    if manifest is not None:
        try:
            _validate_semantic_manifest(
                manifest, bundle, representation_digest, None, embedding_profile
            )
            return
        except DocumentRetrievalError as exc:
            if exc.code is not RetrievalFailureCode.INDEX_STALE:
                raise
    result = build_document_semantic_projection(
        BuildDocumentSemanticProjectionCommand(representation_id, embedding_profile),
        ledger_repository=ledger_repository,
        projection=projection,
        embedding=embedding,
    )
    if result.status != "complete":
        raise DocumentRetrievalError(
            result.failure or RetrievalFailureCode.INDEX_CORRUPT,
            "Document semantic projection readiness failed.",
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
        _ensure_exact_lexical_projection(command.representation_id, ledger_repository, projection)
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
            consulted_channels=(RetrievalChannel.EXACT, RetrievalChannel.LEXICAL),
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
            query_policy_id=DOCUMENT_QUERY_POLICY_ID,
            consulted_channels=(RetrievalChannel.EXACT, RetrievalChannel.LEXICAL),
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


def query_document_semantic_retrieval(
    command: QueryDocumentSemanticRetrievalCommand,
    *,
    ledger_repository: ContextPlanningLedger,
    projection: DocumentSemanticProjectionPort,
    embedding: EmbeddingPort,
    tokenizer: ContextTokenizer,
) -> QueryDocumentRetrievalResult:
    """Run semantic document retrieval and delegate context construction to ContextPlanner."""
    try:
        if command.maximum_hits <= 0:
            raise DocumentRetrievalError(
                RetrievalFailureCode.QUERY_EMPTY, "maximum_hits must be positive."
            )
        normalized_query = normalize_semantic_text(command.query_text)
        if not normalized_query:
            raise DocumentRetrievalError(
                RetrievalFailureCode.QUERY_EMPTY, "Retrieval query is empty."
            )
        semantic_query_input = _semantic_query_input(normalized_query)
        if len(semantic_query_input) > command.embedding_profile.maximum_rendered_characters:
            raise DocumentRetrievalError(
                RetrievalFailureCode.SEMANTIC_INPUT_TOO_LARGE,
                "Semantic query exceeds the configured character limit for "
                f"profile {command.embedding_profile.profile_id}.",
            )
        _ensure_semantic_projection(
            command.representation_id,
            command.embedding_profile,
            ledger_repository,
            projection,
            embedding,
        )
        bundle, representation_digest = _load_acceptable_bundle(
            command.representation_id, ledger_repository
        )
        manifest = projection.get_complete_semantic_manifest(
            command.representation_id, command.embedding_profile.profile_id
        )
        if manifest is None:
            raise DocumentRetrievalError(
                RetrievalFailureCode.INDEX_NOT_FOUND, "No complete semantic retrieval index exists."
            )
        _validate_semantic_manifest(
            manifest,
            bundle,
            representation_digest,
            command.expected_index_manifest_id,
            command.embedding_profile,
        )
        batch = embedding.embed(command.embedding_profile, (semantic_query_input,))
        _validate_embedding_batch(batch, command.embedding_profile, 1)
        query_vector = _normalized_vector_record("semantic-query", batch.vectors[0]).vector
        units = {
            unit.retrieval_unit_id: unit
            for unit in build_document_retrieval_units(bundle, representation_digest)
        }
        candidates = projection.semantic_candidates(manifest, query_vector)
        hits = _rank_semantic_hits(
            candidates, units, manifest.index_manifest_id, command.maximum_hits
        )
        _validate_hit_sources(hits, units, bundle)
        selected_node_ids = tuple(
            node_id for hit in hits if hit.selected for node_id in hit.authoritative_node_ids
        )
        analysis_unit_id, context_manifest_id, rendered_input = _build_retrieval_context(
            command.representation_id,
            selected_node_ids,
            command.context_profile_id,
            ledger_repository,
            tokenizer,
        )
        query_record = RetrievalQueryRecord(
            retrieval_query_id=_query_id(
                command.representation_id, command.query_text, manifest.index_manifest_id
            ),
            representation_id=command.representation_id,
            source_snapshot_id=manifest.source_snapshot_id,
            query_text=command.query_text,
            normalized_query_text=normalized_query,
            query_policy_id=DOCUMENT_SEMANTIC_QUERY_POLICY_ID,
            index_manifest_ids=(manifest.index_manifest_id,),
            consulted_channels=(RetrievalChannel.SEMANTIC,),
            embedding_profile_id=command.embedding_profile.profile_id,
            embedding_model_identity=batch.model_identity,
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
            embedding_profile_id=command.embedding_profile.profile_id,
            embedding_model_identity=batch.model_identity,
            query_policy_id=DOCUMENT_SEMANTIC_QUERY_POLICY_ID,
            consulted_channels=(RetrievalChannel.SEMANTIC,),
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


def query_document_hybrid_retrieval(
    command: QueryDocumentHybridRetrievalCommand,
    *,
    ledger_repository: ContextPlanningLedger,
    exact_lexical_projection: DocumentRetrievalProjectionPort,
    semantic_projection: DocumentSemanticProjectionPort,
    embedding: EmbeddingPort,
    tokenizer: ContextTokenizer,
) -> QueryDocumentRetrievalResult:
    """Run the mandatory document policy and delegate context construction."""
    try:
        if command.maximum_hits <= 0:
            raise DocumentRetrievalError(
                RetrievalFailureCode.QUERY_EMPTY, "maximum_hits must be positive."
            )
        normalized_exact = normalize_exact_text(command.query_text)
        normalized_semantic = normalize_semantic_text(command.query_text)
        if not normalized_exact or not normalized_semantic:
            raise DocumentRetrievalError(
                RetrievalFailureCode.QUERY_EMPTY, "Retrieval query is empty."
            )
        _ensure_exact_lexical_projection(
            command.representation_id, ledger_repository, exact_lexical_projection
        )
        _ensure_semantic_projection(
            command.representation_id,
            command.embedding_profile,
            ledger_repository,
            semantic_projection,
            embedding,
        )
        bundle, representation_digest = _load_acceptable_bundle(
            command.representation_id, ledger_repository
        )
        exact_manifest = exact_lexical_projection.get_complete_manifest(command.representation_id)
        semantic_manifest = semantic_projection.get_complete_semantic_manifest(
            command.representation_id, command.embedding_profile.profile_id
        )
        if exact_manifest is None or semantic_manifest is None:
            raise DocumentRetrievalError(
                RetrievalFailureCode.INDEX_NOT_FOUND,
                "Hybrid retrieval requires complete exact/lexical and semantic indexes.",
            )
        _validate_manifest(exact_manifest, bundle, representation_digest, None)
        _validate_semantic_manifest(
            semantic_manifest,
            bundle,
            representation_digest,
            None,
            command.embedding_profile,
        )
        if exact_manifest.unit_policy_id != semantic_manifest.unit_policy_id:
            raise DocumentRetrievalError(
                RetrievalFailureCode.INDEX_STALE,
                "Hybrid retrieval indexes use different retrieval unit policies.",
            )
        units = {
            unit.retrieval_unit_id: unit
            for unit in build_document_retrieval_units(bundle, representation_digest)
        }
        exact = exact_lexical_projection.exact_candidates(exact_manifest, normalized_exact)
        if len(exact) == 1:
            hits = _rank_exact_guard_hit(exact[0], units, exact_manifest.index_manifest_id)
            consulted = (RetrievalChannel.EXACT,)
            consulted_manifest_ids = (exact_manifest.index_manifest_id,)
            model_identity: EmbeddingModelIdentity | None = None
            profile_id: str | None = None
        else:
            semantic_input = _semantic_query_input(normalized_semantic)
            if len(semantic_input) > command.embedding_profile.maximum_rendered_characters:
                raise DocumentRetrievalError(
                    RetrievalFailureCode.SEMANTIC_INPUT_TOO_LARGE,
                    "Semantic query exceeds the configured character limit for "
                    f"profile {command.embedding_profile.profile_id}.",
                )
            batch = embedding.embed(command.embedding_profile, (semantic_input,))
            _validate_embedding_batch(batch, command.embedding_profile, 1)
            query_vector = _normalized_vector_record("semantic-query", batch.vectors[0]).vector
            lexical = exact_lexical_projection.lexical_candidates(
                exact_manifest, command.query_text
            )
            semantic = semantic_projection.semantic_candidates(semantic_manifest, query_vector)
            hits = _rank_hybrid_hits(
                exact,
                lexical,
                semantic,
                units,
                exact_manifest.index_manifest_id,
                semantic_manifest.index_manifest_id,
                command.maximum_hits,
            )
            consulted = (
                RetrievalChannel.EXACT,
                RetrievalChannel.LEXICAL,
                RetrievalChannel.SEMANTIC,
            )
            consulted_manifest_ids = (
                exact_manifest.index_manifest_id,
                semantic_manifest.index_manifest_id,
            )
            model_identity = batch.model_identity
            profile_id = command.embedding_profile.profile_id
        _validate_hit_sources(hits, units, bundle)
        selected_node_ids = tuple(
            node_id for hit in hits if hit.selected for node_id in hit.authoritative_node_ids
        )
        analysis_unit_id, context_manifest_id, rendered_input = _build_retrieval_context(
            command.representation_id,
            selected_node_ids,
            command.context_profile_id,
            ledger_repository,
            tokenizer,
        )
        query_record = RetrievalQueryRecord(
            retrieval_query_id=_hybrid_query_id(
                command.representation_id, command.query_text, consulted_manifest_ids
            ),
            representation_id=command.representation_id,
            source_snapshot_id=exact_manifest.source_snapshot_id,
            query_text=command.query_text,
            normalized_query_text=normalized_exact,
            query_policy_id=DOCUMENT_HYBRID_QUERY_POLICY_ID,
            index_manifest_ids=consulted_manifest_ids,
            consulted_channels=consulted,
            embedding_profile_id=profile_id,
            embedding_model_identity=model_identity,
            candidate_hits=hits,
            selected_node_ids=selected_node_ids,
            analysis_unit_id=analysis_unit_id,
            context_manifest_id=context_manifest_id,
        )
        exact_lexical_projection.save_query_record(query_record)
        return QueryDocumentRetrievalResult(
            status="complete",
            retrieval_query_id=query_record.retrieval_query_id,
            representation_id=command.representation_id,
            index_manifest_ids=consulted_manifest_ids,
            hits=hits,
            selected_node_ids=selected_node_ids,
            analysis_unit_id=analysis_unit_id,
            context_manifest_id=context_manifest_id,
            context_manifest_rendered_input=rendered_input,
            embedding_profile_id=profile_id,
            embedding_model_identity=model_identity,
            query_policy_id=DOCUMENT_HYBRID_QUERY_POLICY_ID,
            consulted_channels=consulted,
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
    nodes_by_id = {node.id: node for node in bundle.nodes}
    eligible = tuple(
        node
        for node in sorted(bundle.nodes, key=lambda node: (node.order_index, node.id))
        if node.text_view_id == logical.id
        and node.node_type not in {"document", "furniture", "header", "footer"}
        and node.end_char > node.start_char
    )
    units: list[DocumentRetrievalUnit] = []
    for node in eligible:
        ancestor_node_ids = _ancestor_node_ids(node.id, nodes_by_id)
        parent_node_id = ancestor_node_ids[-1]
        section_path = node.section_path
        text = logical.text[node.start_char : node.end_char]
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        fingerprint = document_retrieval_unit_fingerprint(
            source_snapshot_id=bundle.representation.input_blob_digest,
            representation_id=bundle.representation.id,
            node_ids=(node.id,),
            parent_node_id=parent_node_id,
            ancestor_node_ids=ancestor_node_ids,
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
                parent_node_id=parent_node_id,
                ancestor_node_ids=ancestor_node_ids,
                source_order=node.order_index,
                structural_role=node.node_type,
                section_path=section_path,
                source_page_numbers=node.source_page_numbers,
                original_text_digest=digest,
                unit_fingerprint=fingerprint,
            )
        )
    return tuple(units)


def _ancestor_node_ids(node_id: str, nodes_by_id: dict[str, DocumentNode]) -> tuple[str, ...]:
    """Return an authoritative node's root-to-parent chain."""
    node = nodes_by_id.get(node_id)
    if node is None:
        raise ValueError(f"Document retrieval references missing node: {node_id}")
    parent_id = node.parent_node_id
    ancestors: list[str] = []
    while parent_id is not None:
        parent = nodes_by_id.get(parent_id)
        if parent is None:
            raise ValueError(f"Document retrieval references missing parent node: {parent_id}")
        ancestors.append(parent.id)
        parent_id = parent.parent_node_id
    if not ancestors:
        raise ValueError("Document retrieval units require a non-root DocumentNode.")
    return tuple(reversed(ancestors))


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


def normalize_semantic_text(value: str) -> str:
    """Normalize only Unicode form and line endings for reproducible semantic input."""
    return unicodedata.normalize("NFC", value).replace("\r\n", "\n").replace("\r", "\n")


def render_document_semantic_input(
    unit: DocumentRetrievalUnit, bundle: DocumentRepresentationBundle
) -> str:
    """Render one derived embedding input from authoritative fields only."""
    node = next(node for node in bundle.nodes if node.id == unit.node_ids[0])
    view = next(view for view in bundle.text_views if view.id == node.text_view_id)
    title = next(
        (
            view.text[candidate.start_char : candidate.end_char]
            for candidate in sorted(bundle.nodes, key=lambda candidate: candidate.order_index)
            if candidate.node_type == "heading" and candidate.text_view_id == view.id
        ),
        bundle.representation.document_id,
    )
    body = view.text[node.start_char : node.end_char]
    return normalize_semantic_text(
        "search_document: "
        f"Source title: {title}\n"
        f"Section path: {' / '.join(unit.section_path)}\n"
        f"Structural role: {unit.structural_role}\n\n"
        f"{body}"
    )


def build_document_semantic_representation(
    unit: DocumentRetrievalUnit, representation_digest: str, rendered_input: str
) -> DocumentSemanticRepresentation:
    input_digest = hashlib.sha256(rendered_input.encode("utf-8")).hexdigest()
    fingerprint = document_semantic_representation_fingerprint(
        retrieval_unit_id=unit.retrieval_unit_id,
        source_snapshot_id=unit.source_snapshot_id,
        source_fingerprint=representation_digest,
        projection_policy_id=DOCUMENT_SEMANTIC_PROJECTION_POLICY_ID,
        projection_builder_version=DOCUMENT_SEMANTIC_BUILDER_VERSION,
        renderer_policy_id=DOCUMENT_SEMANTIC_RENDERER_POLICY_ID,
        embedding_input_digest=input_digest,
    )
    return DocumentSemanticRepresentation(
        retrieval_representation_id=deterministic_retrieval_representation_id(fingerprint),
        retrieval_unit_id=unit.retrieval_unit_id,
        source_snapshot_id=unit.source_snapshot_id,
        source_fingerprint=representation_digest,
        projection_builder_version=DOCUMENT_SEMANTIC_BUILDER_VERSION,
        renderer_policy_id=DOCUMENT_SEMANTIC_RENDERER_POLICY_ID,
        embedding_input_digest=input_digest,
        representation_fingerprint=fingerprint,
    )


def _semantic_query_input(query_text: str) -> str:
    return f"search_query: {query_text}"


def _validate_embedding_batch(
    batch: EmbeddingBatch, profile: EmbeddingProfile, input_count: int
) -> None:
    identity = batch.model_identity
    if (
        identity.adapter_id != profile.adapter_id
        or identity.model_id != profile.model_id
        or identity.model_digest != profile.model_digest
        or identity.vector_dimension != profile.expected_vector_dimension
        or identity.configuration_digest != embedding_profile_configuration_digest(profile)
    ):
        raise DocumentRetrievalError(
            RetrievalFailureCode.EMBEDDING_PROFILE_MISMATCH,
            "Embedding Adapter identity does not match the selected embedding profile.",
        )
    if len(batch.vectors) != input_count:
        raise DocumentRetrievalError(
            RetrievalFailureCode.EMBEDDING_RESPONSE_INVALID,
            "Embedding Adapter returned a vector count different from the input count.",
        )
    for vector in batch.vectors:
        if len(vector) != profile.expected_vector_dimension:
            raise DocumentRetrievalError(
                RetrievalFailureCode.EMBEDDING_RESPONSE_INVALID,
                "Embedding Adapter returned a vector with the wrong dimension.",
            )
        if not all(math.isfinite(component) for component in vector) or not any(vector):
            raise DocumentRetrievalError(
                RetrievalFailureCode.EMBEDDING_RESPONSE_INVALID,
                "Embedding Adapter returned a non-finite or zero vector.",
            )


def _normalized_vector_record(
    retrieval_unit_id: str, vector: tuple[float, ...]
) -> SemanticVectorRecord:
    norm = math.sqrt(sum(component * component for component in vector))
    if not math.isfinite(norm) or norm == 0:
        raise DocumentRetrievalError(
            RetrievalFailureCode.EMBEDDING_RESPONSE_INVALID,
            "Embedding Adapter returned a non-normalizable vector.",
        )
    packed = struct.pack(f"<{len(vector)}f", *(component / norm for component in vector))
    normalized = struct.unpack(f"<{len(vector)}f", packed)
    if not all(math.isfinite(component) for component in normalized) or not any(normalized):
        raise DocumentRetrievalError(
            RetrievalFailureCode.EMBEDDING_RESPONSE_INVALID,
            "Embedding Adapter vector cannot be represented as normalized float32.",
        )
    return SemanticVectorRecord(
        retrieval_unit_id=retrieval_unit_id,
        vector=packed,
        vector_digest=hashlib.sha256(packed).hexdigest(),
    )


def _semantic_index_manifest(
    bundle: DocumentRepresentationBundle,
    representation_digest: str,
    units: tuple[DocumentRetrievalUnit, ...],
    representations: tuple[DocumentSemanticRepresentation, ...],
    vectors: tuple[SemanticVectorRecord, ...],
    model_identity: EmbeddingModelIdentity,
    profile: EmbeddingProfile,
) -> RetrievalIndexManifest:
    content_fingerprint = _digest(
        {
            "representation_digest": representation_digest,
            "embedding_profile_id": profile.profile_id,
            "model_identity": model_identity.model_dump(mode="json"),
            "representation_fingerprints": tuple(
                representation.representation_fingerprint for representation in representations
            ),
            "vector_digests": tuple(vector.vector_digest for vector in vectors),
        }
    )
    config_digest = embedding_profile_configuration_digest(profile)
    return RetrievalIndexManifest(
        index_manifest_id=f"rim_{content_fingerprint[:24]}",
        channels=(RetrievalChannel.SEMANTIC,),
        source_snapshot_id=bundle.representation.input_blob_digest,
        representation_id=bundle.representation.id,
        representation_digest=representation_digest,
        unit_policy_id=DOCUMENT_UNIT_POLICY_ID,
        projection_policy_id=DOCUMENT_SEMANTIC_PROJECTION_POLICY_ID,
        query_policy_compatibility=DOCUMENT_SEMANTIC_QUERY_POLICY_ID,
        adapter_identity="sqlite_document_retrieval_semantic_v1",
        adapter_configuration_digest=config_digest,
        embedding_profile_id=profile.profile_id,
        embedding_model_identity=model_identity,
        unit_count=len(units),
        representation_count=len(representations),
        content_fingerprint=content_fingerprint,
        publication_status="complete",
        published_at=datetime.now(UTC),
    )


def embedding_profile_configuration_digest(profile: EmbeddingProfile) -> str:
    """Return the pinned, non-secret configuration identity for one local embedder."""
    return _digest(
        {
            "profile_id": profile.profile_id,
            "adapter_id": profile.adapter_id,
            "endpoint": profile.endpoint,
            "model_id": profile.model_id,
            "model_digest": profile.model_digest,
            "expected_vector_dimension": profile.expected_vector_dimension,
            "maximum_rendered_characters": profile.maximum_rendered_characters,
            "renderer_policy_id": DOCUMENT_SEMANTIC_RENDERER_POLICY_ID,
        }
    )


def _validate_semantic_manifest(
    manifest: RetrievalIndexManifest,
    bundle: DocumentRepresentationBundle,
    representation_digest: str,
    expected_index_manifest_id: str | None,
    profile: EmbeddingProfile,
) -> None:
    _validate_manifest(manifest, bundle, representation_digest, expected_index_manifest_id)
    identity = manifest.embedding_model_identity
    if (
        manifest.channels != (RetrievalChannel.SEMANTIC,)
        or identity is None
        or identity.adapter_id != profile.adapter_id
        or identity.model_id != profile.model_id
        or identity.model_digest != profile.model_digest
        or identity.vector_dimension != profile.expected_vector_dimension
    ):
        raise DocumentRetrievalError(
            RetrievalFailureCode.INDEX_STALE,
            "Semantic index does not match the selected embedding profile.",
        )


def _rank_semantic_hits(
    candidates: tuple[ChannelCandidate, ...],
    units: dict[str, DocumentRetrievalUnit],
    manifest_id: str,
    maximum_hits: int,
) -> tuple[RetrievalHit, ...]:
    hits: list[RetrievalHit] = []
    for candidate in candidates[:maximum_hits]:
        unit = units.get(candidate.retrieval_unit_id)
        if unit is None or candidate.channel is not RetrievalChannel.SEMANTIC:
            raise DocumentRetrievalError(
                RetrievalFailureCode.INDEX_CORRUPT, "Semantic index references an unknown unit."
            )
        hits.append(
            RetrievalHit(
                retrieval_unit_id=unit.retrieval_unit_id,
                authoritative_node_ids=unit.node_ids,
                original_text_digest=unit.original_text_digest,
                channel_observations=(
                    RetrievalChannelObservation(
                        channel=RetrievalChannel.SEMANTIC,
                        index_manifest_id=manifest_id,
                        channel_rank=candidate.channel_rank,
                        raw_score=candidate.raw_score,
                        matched_field="cosine_similarity",
                    ),
                ),
                final_rank=len(hits) + 1,
                selected=True,
                selection_reason="semantic_cosine_similarity",
            )
        )
    return tuple(hits)


def _rank_exact_guard_hit(
    candidate: ChannelCandidate,
    units: dict[str, DocumentRetrievalUnit],
    manifest_id: str,
) -> tuple[RetrievalHit, ...]:
    unit = units.get(candidate.retrieval_unit_id)
    if unit is None or candidate.channel is not RetrievalChannel.EXACT:
        raise DocumentRetrievalError(
            RetrievalFailureCode.INDEX_CORRUPT, "Exact index references an unknown unit."
        )
    return (
        RetrievalHit(
            retrieval_unit_id=unit.retrieval_unit_id,
            authoritative_node_ids=unit.node_ids,
            original_text_digest=unit.original_text_digest,
            channel_observations=(
                RetrievalChannelObservation(
                    channel=RetrievalChannel.EXACT,
                    index_manifest_id=manifest_id,
                    channel_rank=candidate.channel_rank,
                    raw_score=candidate.raw_score,
                    matched_field=candidate.matched_field,
                    matched_literal_digest=candidate.matched_literal_digest,
                ),
            ),
            final_rank=1,
            selected=True,
            selection_reason="unique_exact_guard",
        ),
    )


def _rank_hybrid_hits(
    exact: tuple[ChannelCandidate, ...],
    lexical: tuple[ChannelCandidate, ...],
    semantic: tuple[ChannelCandidate, ...],
    units: dict[str, DocumentRetrievalUnit],
    exact_manifest_id: str,
    semantic_manifest_id: str,
    maximum_hits: int,
) -> tuple[RetrievalHit, ...]:
    observations: dict[str, list[RetrievalChannelObservation]] = {}
    for candidate in (*exact, *lexical, *semantic):
        unit = units.get(candidate.retrieval_unit_id)
        if unit is None:
            raise DocumentRetrievalError(
                RetrievalFailureCode.INDEX_CORRUPT, "Hybrid index references an unknown unit."
            )
        manifest_id = (
            semantic_manifest_id
            if candidate.channel is RetrievalChannel.SEMANTIC
            else exact_manifest_id
        )
        observations.setdefault(candidate.retrieval_unit_id, []).append(
            RetrievalChannelObservation(
                channel=candidate.channel,
                index_manifest_id=manifest_id,
                channel_rank=candidate.channel_rank,
                raw_score=candidate.raw_score,
                matched_field=candidate.matched_field,
                matched_literal_digest=candidate.matched_literal_digest,
            )
        )

    def sort_key(unit_id: str) -> tuple[float, int, str]:
        score = sum(1.0 / (60 + row.channel_rank) for row in observations[unit_id])
        unit = units[unit_id]
        return (-score, unit.source_order, unit_id)

    ordered = sorted(observations, key=sort_key)
    return tuple(
        RetrievalHit(
            retrieval_unit_id=unit_id,
            authoritative_node_ids=units[unit_id].node_ids,
            original_text_digest=units[unit_id].original_text_digest,
            channel_observations=tuple(
                sorted(observations[unit_id], key=lambda row: row.channel.value)
            ),
            final_rank=rank,
            selected=rank <= maximum_hits,
            selection_reason="rrf60_fusion",
            fusion_score=-sort_key(unit_id)[0],
        )
        for rank, unit_id in enumerate(ordered, start=1)
    )


def _build_retrieval_context(
    representation_id: str,
    selected_node_ids: tuple[str, ...],
    context_profile_id: str,
    ledger_repository: ContextPlanningLedger,
    tokenizer: ContextTokenizer,
) -> tuple[str | None, str | None, bytes | None]:
    if not selected_node_ids:
        return None, None, None
    try:
        unit = create_analysis_unit_from_retrieval_selection(
            RetrievalSelectionAnalysisUnitInput(
                representation_id=representation_id,
                focus_node_ids=selected_node_ids,
                policy_id=RETRIEVAL_CONTEXT_PLANNER_POLICY_ID,
            ),
            ledger_repository,
        )
        outcome = build_context_manifest(
            ContextManifestInput(
                analysis_unit=unit,
                model_profile=_context_profile(context_profile_id),
                prompt_id="retrieval-validation-prompt-v1",
                prompt_bytes=b"Use only the supplied original source evidence.",
                schema_id="retrieval-validation-schema-v1",
                schema_bytes=b'{"type":"object"}',
                renderer_version="retrieval-validation-renderer-v1",
            ),
            ledger_repository,
            tokenizer,
        )
        return unit.id, outcome.manifest.id, outcome.manifest.rendered_input
    except ValueError as exc:
        raise DocumentRetrievalError(
            RetrievalFailureCode.CONTEXT_PLANNING_FAILED, str(exc)
        ) from exc


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
    if manifest.unit_policy_id != DOCUMENT_UNIT_POLICY_ID:
        raise DocumentRetrievalError(
            RetrievalFailureCode.INDEX_STALE,
            "Index does not match the current document retrieval-unit policy.",
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
                index_manifest_id=manifest_id,
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
            channel_observations=tuple(
                sorted(observations[unit_id], key=lambda row: (row.channel.value, row.channel_rank))
            ),
            final_rank=rank,
            selected=True,
            selection_reason=(
                "exact_before_lexical"
                if any(row.channel is RetrievalChannel.EXACT for row in observations[unit_id])
                else "lexical_fallback"
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


def _hybrid_query_id(representation_id: str, query_text: str, manifest_ids: tuple[str, ...]) -> str:
    digest = _digest((representation_id, query_text, DOCUMENT_HYBRID_QUERY_POLICY_ID, manifest_ids))
    return f"rqr_{digest[:24]}"


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()
