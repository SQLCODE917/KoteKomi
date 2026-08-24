"""KoteKomi command-line entrypoint."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import sqlite3
import sys
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from kotekomi_adapters import (
    DoclingPdfParser,
    DoclingPdfParserConfig,
    GenericArticleAdapter,
    LlamaServerEmbeddingAdapter,
    LMStudioEmbeddingAdapter,
    LocalArchiveStore,
    NewsMLG2Adapter,
    OllamaEmbeddingAdapter,
    SQLiteDocumentRetrievalAdapter,
    SQLiteKnowledgeGraphRetrievalAdapter,
    SQLiteLedgerInitializer,
    SQLiteLedgerRetrievalAdapter,
    sqlite_ledger_transaction,
)
from kotekomi_application import (
    CROSS_PLANE_QUERY_POLICY_ID,
    AuthoritativeCaptureOutcome,
    AuthoritativeCaptureRequest,
    AuthoritativePdfCaptureOutcome,
    AuthoritativePdfCaptureRequest,
    BriefingGenerationInput,
    BuildDocumentRetrievalProjectionCommand,
    BuildDocumentRetrievalProjectionResult,
    BuildDocumentSemanticProjectionCommand,
    BuildEvidenceGraphProjectionCommand,
    BuildKnowledgeGraphProjectionCommand,
    BuildLedgerRetrievalProjectionCommand,
    CompleteIngestionRunCapturedInput,
    CompleteIngestionRunErrorInput,
    EmbeddingPort,
    EmbeddingProfile,
    ExplainEvidenceGraphRelationshipCommand,
    JsonValue,
    LedgerRetrievalFilters,
    ModelRuntimeStatus,
    NewsDeliveryEnvelope,
    NewsIngestInput,
    NewsIngestStatus,
    PipelineCommandPlan,
    PipelineNextStep,
    PipelineRunNextResult,
    PipelineStatus,
    PipelineStatusInput,
    QueryCrossPlaneCommand,
    QueryDocumentHybridRetrievalCommand,
    QueryDocumentRetrievalCommand,
    QueryDocumentSemanticRetrievalCommand,
    QueryKnowledgeGraphCommand,
    QueryLedgerRetrievalCommand,
    ReviewDrainInput,
    ReviewDrainResult,
    ReviewDrainStoppedReason,
    ReviewEditableRecordExportInput,
    ReviewNextDecision,
    ReviewNextDecisionInput,
    ReviewNextDecisionResult,
    ReviewNextInput,
    ReviewNextResult,
    ReviewPacket,
    ReviewPacketInput,
    ReviewProposedChangeInput,
    ReviewQueueInput,
    ReviewReadinessInput,
    ReviewReadinessStatus,
    StartIngestionRunInput,
    UtcIngestionRunClock,
    UtcProcessingClock,
    Uuid4IngestionRunIdFactory,
    Uuid4ProcessingAttemptIdFactory,
    approve_proposed_change,
    build_document_retrieval_projection,
    build_document_semantic_projection,
    build_evidence_graph_projection,
    build_knowledge_graph_projection,
    build_ledger_retrieval_projection,
    commit_authoritative_capture,
    commit_authoritative_pdf_capture,
    complete_ingestion_run_as_captured,
    complete_ingestion_run_as_error,
    edit_proposed_change,
    explain_evidence_graph_relationship,
    export_review_editable_record,
    generate_briefing,
    get_pipeline_next,
    get_pipeline_status,
    get_review_next,
    get_review_packet,
    get_review_readiness,
    ingest_structured_news,
    initialize_ledger,
    list_ingestion_runs,
    list_review_queue,
    model_runtime_status_to_json,
    normalize_source_url,
    pipeline_next_to_json,
    pipeline_status_to_json,
    query_cross_plane,
    query_document_hybrid_retrieval,
    query_document_retrieval,
    query_document_semantic_retrieval,
    query_knowledge_graph,
    query_ledger_retrieval,
    reject_proposed_change,
    review_drain_result_to_json,
    review_next_decision_result_to_json,
    review_next_result_to_json,
    review_packet_to_json,
    review_queue_result_to_json,
    review_readiness_to_json,
    run_next_result_to_json,
    run_review_drain,
    run_review_next_decision,
    start_ingestion_run,
)
from kotekomi_briefing import MarkdownBriefingRenderer
from kotekomi_domain import (
    AssertionStatus,
    DocumentRepresentationBundle,
    EvidenceGraphViewKind,
    IngestionFailureCode,
    IngestionFailureStage,
    IngestionRun,
    IngestionRunStatus,
    LedgerRetrievalRecordType,
    ReviewStatus,
)

from kotekomi_pipelines.config import (
    MODEL_RUNTIME_ADAPTERS,
    PipelineConfig,
    ProcessingConfig,
    ProcessingConfigurationError,
    initialize_user_processing_config,
    load_config,
    load_processing_config,
    load_processing_storage_config,
)
from kotekomi_pipelines.managed_llama_server import (
    ManagedLlamaServerConfig,
    get_managed_llama_server_status,
    install_managed_llama_server,
    uninstall_managed_llama_server,
)
from kotekomi_pipelines.model_runtime import build_model_runtime_readiness
from kotekomi_pipelines.source_lineage import propose_verbatim_republication_relation


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "ledger" and args.ledger_command == "init":
        config = load_config(
            config_path=args.config,
            ledger_path_override=args.ledger_path,
            archive_path_override=args.archive_path,
        )
        return init_ledger(config)

    if args.command == "init":
        return initialize_user_environment(
            config_path=args.config,
            ledger_path_override=args.ledger_path,
            archive_path_override=args.archive_path,
        )

    if args.command == "ingest":
        return ingest_user_file(
            config_path=args.config,
            source_file_path=args.path,
            source_url=args.url,
        )

    if args.command == "ingestions" and args.ingestions_command == "list":
        return list_user_ingestion_history(config_path=args.config)

    if args.command == "retrieval" and args.retrieval_command == "build-document":
        if args.embedding_profile is not None and args.channel != "semantic":
            parser.error("--embedding-profile requires --channel semantic.")
        config = load_config(
            config_path=args.config,
            ledger_path_override=args.ledger_path,
            archive_path_override=None,
        )
        return build_document_retrieval_index(
            ledger_path=config.ledger_path,
            representation_id=args.representation_id,
            output_format=args.output_format,
            rebuild=args.rebuild,
            channel=args.channel,
            embedding_profile=(
                _embedding_profile(config, args.embedding_profile)
                if args.channel == "semantic"
                else _normal_embedding_profile(config)
                if args.channel is None
                else None
            ),
        )

    if args.command == "retrieval" and args.retrieval_command == "query":
        if args.embedding_profile is not None and args.channel != "semantic":
            parser.error("--embedding-profile requires --channel semantic.")
        config = load_config(
            config_path=args.config,
            ledger_path_override=args.ledger_path,
            archive_path_override=None,
        )
        return query_document_retrieval_index(
            ledger_path=config.ledger_path,
            representation_id=args.representation_id,
            query=args.query,
            maximum_hits=args.maximum_hits,
            context_profile=args.context_profile,
            output_format=args.output_format,
            channel=args.channel,
            embedding_profile=(
                _embedding_profile(config, args.embedding_profile)
                if args.channel == "semantic"
                else _normal_embedding_profile(config)
                if args.channel is None
                else None
            ),
        )

    if args.command == "retrieval" and args.retrieval_command == "build-ledger":
        config = load_config(
            config_path=args.config,
            ledger_path_override=args.ledger_path,
            archive_path_override=None,
        )
        return build_ledger_retrieval_index(
            ledger_path=config.ledger_path,
            output_format=args.output_format,
            rebuild=args.rebuild,
        )

    if args.command == "retrieval" and args.retrieval_command == "query-ledger":
        config = load_config(
            config_path=args.config,
            ledger_path_override=args.ledger_path,
            archive_path_override=None,
        )
        return query_ledger_retrieval_index(
            ledger_path=config.ledger_path,
            query=args.query or "",
            record_id=args.record_id,
            record_type=args.record_type,
            assertion_statuses=tuple(args.assertion_status),
            subject_id=args.subject_id,
            predicate=args.predicate,
            policy=args.policy,
            maximum_hits=args.maximum_hits,
            context_profile=args.context_profile,
            output_format=args.output_format,
        )

    if args.command == "retrieval" and args.retrieval_command == "build-graph":
        config = load_config(
            config_path=args.config,
            ledger_path_override=args.ledger_path,
            archive_path_override=None,
        )
        return build_knowledge_graph_retrieval_index(
            ledger_path=config.ledger_path,
            output_format=args.output_format,
            rebuild=args.rebuild,
        )

    if args.command == "retrieval" and args.retrieval_command == "query-graph":
        config = load_config(
            config_path=args.config,
            ledger_path_override=args.ledger_path,
            archive_path_override=None,
        )
        return query_knowledge_graph_retrieval_index(
            ledger_path=config.ledger_path,
            seed=args.seed,
            maximum_hops=args.maximum_hops,
            maximum_hits=args.maximum_hits,
            context_profile=args.context_profile,
            output_format=args.output_format,
        )

    if args.command == "retrieval" and args.retrieval_command == "query-cross-plane":
        config = load_config(
            config_path=args.config,
            ledger_path_override=args.ledger_path,
            archive_path_override=None,
        )
        return query_cross_plane_retrieval_index(
            ledger_path=config.ledger_path,
            query=args.query,
            output_format=args.output_format,
        )

    if args.command == "retrieval" and args.retrieval_command == "build-graph-evidence":
        config = load_config(
            config_path=args.config,
            ledger_path_override=args.ledger_path,
            archive_path_override=None,
        )
        return build_evidence_graph_projection_index(
            ledger_path=config.ledger_path,
            output_format=args.output_format,
            rebuild=args.rebuild,
            as_of=args.as_of,
        )

    if args.command == "retrieval" and args.retrieval_command == "explain-graph-relationship":
        config = load_config(
            config_path=args.config,
            ledger_path_override=args.ledger_path,
            archive_path_override=None,
        )
        return explain_evidence_graph_relationship_index(
            ledger_path=config.ledger_path,
            relationship_id=args.relationship_id,
            context_profile=args.context_profile,
            output_format=args.output_format,
            as_of=args.as_of,
        )

    if args.command == "source" and args.source_command == "add-file":
        config = load_processing_config(
            config_path=args.config,
            ledger_path_override=args.ledger_path,
            archive_path_override=args.archive_path,
        )
        return add_source_file(config, args.path, args.source_url, args.output_format)

    if args.command == "lineage" and args.lineage_command == "propose-verbatim-republication":
        config = load_config(
            config_path=args.config,
            ledger_path_override=args.ledger_path,
            archive_path_override=None,
        )
        return propose_verbatim_republication_relation(
            config=config,
            document_ids=tuple(args.document_id),
            proposer=args.proposer,
            rationale=args.rationale,
            output_format=args.output_format,
        )

    if args.command == "source" and args.source_command == "add-news":
        config = load_processing_config(
            config_path=args.config,
            ledger_path_override=args.ledger_path,
            archive_path_override=args.archive_path,
        )
        return add_structured_news(
            config=config,
            payload_path=args.payload,
            envelope_path=args.envelope,
            adapter_name=args.adapter,
            media_type=args.media_type,
            output_format=args.output_format,
        )

    if args.command == "model" and args.model_command == "status":
        config = _load_model_config(
            config_path=args.config,
            ledger_path_override=None,
            archive_path_override=None,
            runtime_profile=args.runtime_profile,
            model_runtime_adapter=args.model_runtime,
            model_endpoint=args.model_endpoint,
            model_name=args.model_name,
            model_timeout_seconds=args.model_timeout_seconds,
            model_context_tokens=args.model_context_tokens,
            model_max_output_tokens=args.model_max_output_tokens,
        )
        return show_model_runtime_status(config=config, output_format=args.output_format)

    if args.command == "model" and args.model_command == "server":
        return manage_model_server(
            server_command=args.server_command,
            llama_server_path=getattr(args, "llama_server_path", None),
            output_format=args.output_format,
        )

    if args.command == "review" and args.review_command == "approve":
        config = load_config(
            config_path=args.config,
            ledger_path_override=args.ledger_path,
            archive_path_override=None,
        )
        return approve_reviewed_proposed_change(
            config=config,
            proposed_change_id=args.proposed_change_id,
            reviewer=args.reviewer,
        )

    if args.command == "review" and args.review_command == "list":
        config = load_config(
            config_path=args.config,
            ledger_path_override=args.ledger_path,
            archive_path_override=None,
        )
        return list_reviewed_proposed_changes(
            config=config,
            review_status=args.review_status,
            record_type=args.record_type,
            source_id=args.source_id,
            document_id=args.document_id,
            output_format=args.output_format,
        )

    if args.command == "review" and args.review_command == "next":
        config = load_config(
            config_path=args.config,
            ledger_path_override=args.ledger_path,
            archive_path_override=None,
        )
        return show_next_reviewed_proposed_change(
            config=config,
            record_type=args.record_type,
            source_id=args.source_id,
            document_id=args.document_id,
            output_format=args.output_format,
        )

    if args.command == "review" and args.review_command == "run-next":
        config = load_config(
            config_path=args.config,
            ledger_path_override=args.ledger_path,
            archive_path_override=None,
        )
        return run_next_review_decision(
            config=config,
            decision=args.decision,
            reviewer=args.reviewer,
            record_type=args.record_type,
            source_id=args.source_id,
            document_id=args.document_id,
            reason=args.reason,
            accepted_record_json_path=args.accepted_record_json,
            dry_run=args.dry_run,
            output_format=args.output_format,
        )

    if args.command == "review" and args.review_command == "drain":
        config = load_config(
            config_path=args.config,
            ledger_path_override=args.ledger_path,
            archive_path_override=None,
        )
        return drain_review_queue(
            config=config,
            decision=args.decision,
            reviewer=args.reviewer,
            record_type=args.record_type,
            source_id=args.source_id,
            document_id=args.document_id,
            reason=args.reason,
            accepted_record_json_path=args.accepted_record_json,
            limit=args.limit,
            dry_run=args.dry_run,
            output_format=args.output_format,
        )

    if args.command == "review" and args.review_command == "show":
        config = load_config(
            config_path=args.config,
            ledger_path_override=args.ledger_path,
            archive_path_override=None,
        )
        return show_reviewed_proposed_change(
            config=config,
            proposed_change_id=args.proposed_change_id,
            output_format=args.output_format,
        )

    if args.command == "review" and args.review_command == "status":
        config = load_config(
            config_path=args.config,
            ledger_path_override=args.ledger_path,
            archive_path_override=None,
        )
        return show_review_readiness(
            config=config,
            record_type=args.record_type,
            source_id=args.source_id,
            document_id=args.document_id,
            output_format=args.output_format,
        )

    if args.command == "review" and args.review_command == "export":
        config = load_config(
            config_path=args.config,
            ledger_path_override=args.ledger_path,
            archive_path_override=None,
        )
        return export_reviewed_proposed_change(
            config=config,
            proposed_change_id=args.proposed_change_id,
            output_path=args.output,
        )

    if args.command == "review" and args.review_command == "reject":
        config = load_config(
            config_path=args.config,
            ledger_path_override=args.ledger_path,
            archive_path_override=None,
        )
        return reject_reviewed_proposed_change(
            config=config,
            proposed_change_id=args.proposed_change_id,
            reviewer=args.reviewer,
            reason=args.reason,
        )

    if args.command == "review" and args.review_command == "edit":
        config = load_config(
            config_path=args.config,
            ledger_path_override=args.ledger_path,
            archive_path_override=None,
        )
        return edit_reviewed_proposed_change(
            config=config,
            proposed_change_id=args.proposed_change_id,
            reviewer=args.reviewer,
            accepted_record_json_path=args.accepted_record_json,
        )

    if args.command == "pipeline" and args.pipeline_command == "status":
        config = _load_model_config(
            config_path=args.config,
            ledger_path_override=args.ledger_path,
            archive_path_override=args.archive_path,
            runtime_profile=args.runtime_profile,
            model_runtime_adapter=args.model_runtime,
            model_endpoint=args.model_endpoint,
            model_name=args.model_name,
            model_timeout_seconds=args.model_timeout_seconds,
            model_context_tokens=args.model_context_tokens,
            model_max_output_tokens=args.model_max_output_tokens,
        )
        return show_pipeline_status(
            config=config,
            output_format=args.output_format,
            source_file_path=args.source_file_path,
            source_url=args.source_url,
            model_output_fixture_path=args.model_output_fixture,
            document_id=args.document_id,
            briefing_title=args.briefing_title,
        )

    if args.command == "pipeline" and args.pipeline_command == "next":
        config = _load_model_config(
            config_path=args.config,
            ledger_path_override=args.ledger_path,
            archive_path_override=args.archive_path,
            runtime_profile=args.runtime_profile,
            model_runtime_adapter=args.model_runtime,
            model_endpoint=args.model_endpoint,
            model_name=args.model_name,
            model_timeout_seconds=args.model_timeout_seconds,
            model_context_tokens=args.model_context_tokens,
            model_max_output_tokens=args.model_max_output_tokens,
        )
        return show_pipeline_next(
            config=config,
            output_format=args.output_format,
            source_file_path=args.source_file_path,
            source_url=args.source_url,
            model_output_fixture_path=args.model_output_fixture,
            document_id=args.document_id,
            briefing_title=args.briefing_title,
        )

    if args.command == "pipeline" and args.pipeline_command == "run-next":
        config = _load_model_config(
            config_path=args.config,
            ledger_path_override=args.ledger_path,
            archive_path_override=args.archive_path,
            runtime_profile=args.runtime_profile,
            model_runtime_adapter=args.model_runtime,
            model_endpoint=args.model_endpoint,
            model_name=args.model_name,
            model_timeout_seconds=args.model_timeout_seconds,
            model_context_tokens=args.model_context_tokens,
            model_max_output_tokens=args.model_max_output_tokens,
        )
        return run_pipeline_next(
            config=config,
            output_format=args.output_format,
            dry_run=args.dry_run,
            source_file_path=args.source_file_path,
            source_url=args.source_url,
            model_output_fixture_path=args.model_output_fixture,
            document_id=args.document_id,
            briefing_title=args.briefing_title,
        )

    if args.command == "briefing" and args.briefing_command == "generate":
        config = load_config(
            config_path=args.config,
            ledger_path_override=args.ledger_path,
            archive_path_override=args.archive_path,
        )
        return generate_markdown_briefing(
            config=config,
            title=args.title,
            previous_briefing_id=args.previous_briefing_id,
        )

    parser.print_help()
    return 2


def entrypoint() -> None:
    raise SystemExit(main())


def _load_model_config(
    *,
    config_path: Path | None,
    ledger_path_override: Path | None,
    archive_path_override: Path | None,
    runtime_profile: str | None,
    model_runtime_adapter: str | None,
    model_endpoint: str | None,
    model_name: str | None,
    model_timeout_seconds: float | None,
    model_context_tokens: int | None,
    model_max_output_tokens: int | None,
) -> PipelineConfig:
    return load_config(
        config_path=config_path,
        ledger_path_override=ledger_path_override,
        archive_path_override=archive_path_override,
        runtime_profile_override=runtime_profile,
        model_runtime_adapter_override=model_runtime_adapter,
        model_endpoint_override=model_endpoint,
        model_name_override=model_name,
        model_timeout_seconds_override=model_timeout_seconds,
        model_context_tokens_override=model_context_tokens,
        model_max_output_tokens_override=model_max_output_tokens,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="kotekomi")
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Path to kotekomi.toml.",
    )
    subparsers = parser.add_subparsers(dest="command")

    ingest_parser = subparsers.add_parser("ingest", help="Ingest one deposited file for review.")
    ingest_parser.add_argument("path", type=Path)
    ingest_parser.add_argument("--url", required=True)

    ingestions_parser = subparsers.add_parser("ingestions", help="User ingestion history.")
    ingestions_subparsers = ingestions_parser.add_subparsers(dest="ingestions_command")
    ingestions_subparsers.add_parser("list", help="List admitted ingestion attempts.")

    init_parser = subparsers.add_parser(
        "init", help="Create the local user configuration and initialize storage."
    )
    init_parser.add_argument("--ledger-path", type=Path, default=None)
    init_parser.add_argument("--archive-path", type=Path, default=None)

    ledger_parser = subparsers.add_parser("ledger", help="Ledger commands.")
    ledger_subparsers = ledger_parser.add_subparsers(dest="ledger_command")
    init_parser = ledger_subparsers.add_parser("init", help="Create or migrate the Ledger.")
    init_parser.add_argument("--ledger-path", type=Path, default=None)
    init_parser.add_argument("--archive-path", type=Path, default=None)

    source_parser = subparsers.add_parser("source", help="Source commands.")
    source_subparsers = source_parser.add_subparsers(dest="source_command")
    add_file_parser = source_subparsers.add_parser(
        "add-file",
        help="Add a local file as a Source.",
    )
    add_file_parser.add_argument("path", type=Path)
    add_file_parser.add_argument("--source-url", required=True)
    add_file_parser.add_argument(
        "--format", dest="output_format", choices=("text", "json"), default="text"
    )
    add_file_parser.add_argument("--ledger-path", type=Path, default=None)
    add_file_parser.add_argument("--archive-path", type=Path, default=None)
    add_news_parser = source_subparsers.add_parser(
        "add-news",
        help="Add a recorded structured-news payload and delivery envelope.",
    )
    add_news_parser.add_argument("--payload", type=Path, required=True)
    add_news_parser.add_argument("--envelope", type=Path, required=True)
    add_news_parser.add_argument(
        "--adapter", choices=("newsml-g2", "generic-article"), required=True
    )
    add_news_parser.add_argument("--media-type", default=None)
    add_news_parser.add_argument(
        "--format", dest="output_format", choices=("text", "json"), default="text"
    )
    add_news_parser.add_argument("--ledger-path", type=Path, default=None)
    add_news_parser.add_argument("--archive-path", type=Path, default=None)

    retrieval_parser = subparsers.add_parser("retrieval", help="Derived retrieval commands.")
    retrieval_subparsers = retrieval_parser.add_subparsers(dest="retrieval_command")
    retrieval_build_parser = retrieval_subparsers.add_parser(
        "build-document", help="Build a disposable document retrieval projection."
    )
    retrieval_build_parser.add_argument("--representation-id", required=True)
    retrieval_build_parser.add_argument(
        "--channel", choices=("exact-lexical", "semantic"), default=None
    )
    retrieval_build_parser.add_argument("--embedding-profile", default=None)
    retrieval_build_parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Delete the disposable projection before rebuilding it from authoritative state.",
    )
    retrieval_build_parser.add_argument(
        "--format", dest="output_format", choices=("text", "json"), default="text"
    )
    retrieval_build_parser.add_argument("--ledger-path", type=Path, default=None)
    retrieval_query_parser = retrieval_subparsers.add_parser(
        "query", help="Retrieve document nodes and construct authoritative context."
    )
    retrieval_query_parser.add_argument("--representation-id", required=True)
    retrieval_query_parser.add_argument("--query", required=True)
    retrieval_query_parser.add_argument("--maximum-hits", required=True, type=int)
    retrieval_query_parser.add_argument("--context-profile", required=True)
    retrieval_query_parser.add_argument(
        "--channel", choices=("exact-lexical", "semantic"), default=None
    )
    retrieval_query_parser.add_argument("--embedding-profile", default=None)
    retrieval_query_parser.add_argument(
        "--format", dest="output_format", choices=("text", "json"), default="text"
    )
    retrieval_query_parser.add_argument("--ledger-path", type=Path, default=None)
    retrieval_ledger_build_parser = retrieval_subparsers.add_parser(
        "build-ledger", help="Build a disposable Ledger retrieval projection."
    )
    retrieval_ledger_build_parser.add_argument("--rebuild", action="store_true")
    retrieval_ledger_build_parser.add_argument(
        "--format", dest="output_format", choices=("text", "json"), default="text"
    )
    retrieval_ledger_build_parser.add_argument("--ledger-path", type=Path, default=None)
    retrieval_ledger_query_parser = retrieval_subparsers.add_parser(
        "query-ledger", help="Retrieve accepted Ledger records and authoritative context."
    )
    retrieval_ledger_query_parser.add_argument("--query", default=None)
    retrieval_ledger_query_parser.add_argument("--record-id", default=None)
    retrieval_ledger_query_parser.add_argument(
        "--record-type", choices=("assertion", "relationship", "outcome"), default=None
    )
    retrieval_ledger_query_parser.add_argument("--assertion-status", action="append", default=[])
    retrieval_ledger_query_parser.add_argument("--subject-id", default=None)
    retrieval_ledger_query_parser.add_argument("--predicate", default=None)
    retrieval_ledger_query_parser.add_argument(
        "--policy",
        choices=("current-relevance", "current-latest", "audit-history"),
        default="current-relevance",
    )
    retrieval_ledger_query_parser.add_argument("--maximum-hits", required=True, type=int)
    retrieval_ledger_query_parser.add_argument("--context-profile", required=True)
    retrieval_ledger_query_parser.add_argument(
        "--format", dest="output_format", choices=("text", "json"), default="text"
    )
    retrieval_ledger_query_parser.add_argument("--ledger-path", type=Path, default=None)
    retrieval_graph_build_parser = retrieval_subparsers.add_parser(
        "build-graph", help="Build a disposable Knowledge-Graph retrieval projection."
    )
    retrieval_graph_build_parser.add_argument("--rebuild", action="store_true")
    retrieval_graph_build_parser.add_argument(
        "--format", dest="output_format", choices=("text", "json"), default="text"
    )
    retrieval_graph_build_parser.add_argument("--ledger-path", type=Path, default=None)
    retrieval_graph_query_parser = retrieval_subparsers.add_parser(
        "query-graph", help="Traverse current accepted Ledger knowledge from a name phrase."
    )
    retrieval_graph_query_parser.add_argument("--seed", required=True)
    retrieval_graph_query_parser.add_argument("--maximum-hops", type=int, choices=(1, 2), default=2)
    retrieval_graph_query_parser.add_argument("--maximum-hits", required=True, type=int)
    retrieval_graph_query_parser.add_argument("--context-profile", required=True)
    retrieval_graph_query_parser.add_argument(
        "--format", dest="output_format", choices=("text", "json"), default="text"
    )
    retrieval_graph_query_parser.add_argument("--ledger-path", type=Path, default=None)
    retrieval_cross_plane_query_parser = retrieval_subparsers.add_parser(
        "query-cross-plane",
        help="Run the named Ledger-to-Graph evidence retrieval policy.",
    )
    retrieval_cross_plane_query_parser.add_argument("--query", required=True)
    retrieval_cross_plane_query_parser.add_argument(
        "--format", dest="output_format", choices=("text", "json"), default="text"
    )
    retrieval_cross_plane_query_parser.add_argument("--ledger-path", type=Path, default=None)
    retrieval_evidence_graph_build_parser = retrieval_subparsers.add_parser(
        "build-graph-evidence",
        help="Build a disposable evidence-linked Relationship graph projection.",
    )
    retrieval_evidence_graph_build_parser.add_argument("--rebuild", action="store_true")
    retrieval_evidence_graph_build_parser.add_argument("--as-of", type=_parse_utc_timestamp)
    retrieval_evidence_graph_build_parser.add_argument(
        "--format", dest="output_format", choices=("text", "json"), default="text"
    )
    retrieval_evidence_graph_build_parser.add_argument("--ledger-path", type=Path, default=None)
    retrieval_evidence_graph_explain_parser = retrieval_subparsers.add_parser(
        "explain-graph-relationship",
        help="Explain one Relationship through accepted Assertions and source evidence.",
    )
    retrieval_evidence_graph_explain_parser.add_argument("--relationship-id", required=True)
    retrieval_evidence_graph_explain_parser.add_argument("--as-of", type=_parse_utc_timestamp)
    retrieval_evidence_graph_explain_parser.add_argument("--context-profile", required=True)
    retrieval_evidence_graph_explain_parser.add_argument(
        "--format", dest="output_format", choices=("text", "json"), default="text"
    )
    retrieval_evidence_graph_explain_parser.add_argument("--ledger-path", type=Path, default=None)

    lineage_parser = subparsers.add_parser(
        "lineage", help="Reviewed cross-source lineage commands."
    )
    lineage_subparsers = lineage_parser.add_subparsers(dest="lineage_command", required=True)
    lineage_propose_parser = lineage_subparsers.add_parser(
        "propose-verbatim-republication",
        help="Propose an exact-byte relation between two source Documents for review.",
    )
    lineage_propose_parser.add_argument("--document-id", action="append", required=True)
    lineage_propose_parser.add_argument("--proposer", required=True)
    lineage_propose_parser.add_argument("--rationale", required=True)
    lineage_propose_parser.add_argument(
        "--format", dest="output_format", choices=("text", "json"), default="text"
    )
    lineage_propose_parser.add_argument("--ledger-path", type=Path, default=None)

    model_parser = subparsers.add_parser("model", help="Local model runtime commands.")
    model_subparsers = model_parser.add_subparsers(dest="model_command")
    model_status_parser = model_subparsers.add_parser(
        "status",
        help="Check configured model runtime readiness.",
    )
    model_status_parser.add_argument(
        "--format",
        dest="output_format",
        choices=("text", "json"),
        default="text",
    )
    _add_model_runtime_arguments(model_status_parser, include_fixture=False)

    model_server_parser = model_subparsers.add_parser(
        "server",
        help="Manage the current user's shared llama-server LaunchAgent.",
    )
    model_server_subparsers = model_server_parser.add_subparsers(
        dest="server_command", required=True
    )
    model_server_install_parser = model_server_subparsers.add_parser(
        "install",
        help="Install and start the shared local llama-server router.",
    )
    model_server_install_parser.add_argument("--llama-server-path", type=Path, required=True)
    model_server_status_parser = model_server_subparsers.add_parser(
        "status",
        help="Show shared llama-server LaunchAgent state.",
    )
    model_server_uninstall_parser = model_server_subparsers.add_parser(
        "uninstall",
        help="Stop and remove the shared local llama-server router.",
    )
    for server_parser in (
        model_server_install_parser,
        model_server_status_parser,
        model_server_uninstall_parser,
    ):
        server_parser.add_argument(
            "--format",
            dest="output_format",
            choices=("text", "json"),
            default="text",
        )

    review_parser = subparsers.add_parser("review", help="ProposedChange review commands.")
    review_subparsers = review_parser.add_subparsers(dest="review_command")
    list_parser = review_subparsers.add_parser(
        "list",
        help="List ProposedChange records awaiting review.",
    )
    list_parser.add_argument("--review-status", default=ReviewStatus.PENDING.value)
    list_parser.add_argument("--record-type", default=None)
    list_parser.add_argument("--source-id", default=None)
    list_parser.add_argument("--document-id", default=None)
    list_parser.add_argument(
        "--format",
        dest="output_format",
        choices=("text", "json"),
        default="text",
    )
    list_parser.add_argument("--ledger-path", type=Path, default=None)
    next_parser = review_subparsers.add_parser(
        "next",
        help="Show the next ProposedChange review packet.",
    )
    next_parser.add_argument("--record-type", default=None)
    next_parser.add_argument("--source-id", default=None)
    next_parser.add_argument("--document-id", default=None)
    next_parser.add_argument(
        "--format",
        dest="output_format",
        choices=("text", "json"),
        default="text",
    )
    next_parser.add_argument("--ledger-path", type=Path, default=None)
    run_next_review_parser = review_subparsers.add_parser(
        "run-next",
        help="Apply one explicit decision to the next ProposedChange.",
    )
    run_next_review_parser.add_argument(
        "--decision",
        choices=tuple(decision.value for decision in ReviewNextDecision),
        required=True,
    )
    run_next_review_parser.add_argument("--reviewer", required=True)
    run_next_review_parser.add_argument("--record-type", default=None)
    run_next_review_parser.add_argument("--source-id", default=None)
    run_next_review_parser.add_argument("--document-id", default=None)
    run_next_review_parser.add_argument("--reason", default=None)
    run_next_review_parser.add_argument("--accepted-record-json", type=Path, default=None)
    run_next_review_parser.add_argument("--dry-run", action="store_true")
    run_next_review_parser.add_argument(
        "--format",
        dest="output_format",
        choices=("text", "json"),
        default="text",
    )
    run_next_review_parser.add_argument("--ledger-path", type=Path, default=None)
    drain_review_parser = review_subparsers.add_parser(
        "drain",
        help="Apply one explicit decision repeatedly to the Review Queue.",
    )
    drain_review_parser.add_argument(
        "--decision",
        choices=tuple(decision.value for decision in ReviewNextDecision),
        required=True,
    )
    drain_review_parser.add_argument("--reviewer", required=True)
    drain_review_parser.add_argument("--record-type", default=None)
    drain_review_parser.add_argument("--source-id", default=None)
    drain_review_parser.add_argument("--document-id", default=None)
    drain_review_parser.add_argument("--reason", default=None)
    drain_review_parser.add_argument("--accepted-record-json", type=Path, default=None)
    drain_review_parser.add_argument("--limit", type=int, default=None)
    drain_review_parser.add_argument("--dry-run", action="store_true")
    drain_review_parser.add_argument(
        "--format",
        dest="output_format",
        choices=("text", "json"),
        default="text",
    )
    drain_review_parser.add_argument("--ledger-path", type=Path, default=None)
    show_parser = review_subparsers.add_parser(
        "show",
        help="Show one ProposedChange review packet.",
    )
    show_parser.add_argument("--proposed-change-id", required=True)
    show_parser.add_argument(
        "--format",
        dest="output_format",
        choices=("text", "json"),
        default="text",
    )
    show_parser.add_argument("--ledger-path", type=Path, default=None)
    status_parser = review_subparsers.add_parser(
        "status",
        help="Show review readiness for agents and humans.",
    )
    status_parser.add_argument("--record-type", default=None)
    status_parser.add_argument("--source-id", default=None)
    status_parser.add_argument("--document-id", default=None)
    status_parser.add_argument(
        "--format",
        dest="output_format",
        choices=("text", "json"),
        default="text",
    )
    status_parser.add_argument("--ledger-path", type=Path, default=None)
    export_parser = review_subparsers.add_parser(
        "export",
        help="Export editable ProposedChange record JSON.",
    )
    export_parser.add_argument("--proposed-change-id", required=True)
    export_parser.add_argument("--output", type=Path, required=True)
    export_parser.add_argument("--ledger-path", type=Path, default=None)
    approve_parser = review_subparsers.add_parser(
        "approve",
        help="Approve one pending ProposedChange.",
    )
    approve_parser.add_argument("--proposed-change-id", required=True)
    approve_parser.add_argument("--reviewer", required=True)
    approve_parser.add_argument("--ledger-path", type=Path, default=None)
    reject_parser = review_subparsers.add_parser(
        "reject",
        help="Reject one pending ProposedChange.",
    )
    reject_parser.add_argument("--proposed-change-id", required=True)
    reject_parser.add_argument("--reviewer", required=True)
    reject_parser.add_argument("--reason", required=True)
    reject_parser.add_argument("--ledger-path", type=Path, default=None)
    edit_parser = review_subparsers.add_parser(
        "edit",
        help="Approve one pending ProposedChange with corrected accepted record JSON.",
    )
    edit_parser.add_argument("--proposed-change-id", required=True)
    edit_parser.add_argument("--reviewer", required=True)
    edit_parser.add_argument("--accepted-record-json", type=Path, required=True)
    edit_parser.add_argument("--ledger-path", type=Path, default=None)

    pipeline_parser = subparsers.add_parser(
        "pipeline",
        help="Pipeline readiness and next-step commands.",
    )
    pipeline_subparsers = pipeline_parser.add_subparsers(dest="pipeline_command")
    pipeline_status_parser = pipeline_subparsers.add_parser(
        "status",
        help="Show current Pipeline readiness.",
    )
    pipeline_status_parser.add_argument(
        "--format",
        dest="output_format",
        choices=("text", "json"),
        default="text",
    )
    pipeline_status_parser.add_argument("--ledger-path", type=Path, default=None)
    pipeline_status_parser.add_argument("--archive-path", type=Path, default=None)
    pipeline_status_parser.add_argument("--source-file-path", type=Path, default=None)
    pipeline_status_parser.add_argument("--source-url", default=None)
    _add_model_runtime_arguments(pipeline_status_parser, include_fixture=True)
    pipeline_status_parser.add_argument("--document-id", default=None)
    pipeline_status_parser.add_argument("--briefing-title", default=None)
    pipeline_next_parser = pipeline_subparsers.add_parser(
        "next",
        help="Show the next recommended Pipeline command.",
    )
    pipeline_next_parser.add_argument(
        "--format",
        dest="output_format",
        choices=("text", "json"),
        default="text",
    )
    pipeline_next_parser.add_argument("--ledger-path", type=Path, default=None)
    pipeline_next_parser.add_argument("--archive-path", type=Path, default=None)
    pipeline_next_parser.add_argument("--source-file-path", type=Path, default=None)
    pipeline_next_parser.add_argument("--source-url", default=None)
    _add_model_runtime_arguments(pipeline_next_parser, include_fixture=True)
    pipeline_next_parser.add_argument("--document-id", default=None)
    pipeline_next_parser.add_argument("--briefing-title", default=None)
    pipeline_run_next_parser = pipeline_subparsers.add_parser(
        "run-next",
        help="Execute the next ready Pipeline command.",
    )
    pipeline_run_next_parser.add_argument(
        "--format",
        dest="output_format",
        choices=("text", "json"),
        default="text",
    )
    pipeline_run_next_parser.add_argument("--dry-run", action="store_true")
    pipeline_run_next_parser.add_argument("--ledger-path", type=Path, default=None)
    pipeline_run_next_parser.add_argument("--archive-path", type=Path, default=None)
    pipeline_run_next_parser.add_argument("--source-file-path", type=Path, default=None)
    pipeline_run_next_parser.add_argument("--source-url", default=None)
    _add_model_runtime_arguments(pipeline_run_next_parser, include_fixture=True)
    pipeline_run_next_parser.add_argument("--document-id", default=None)
    pipeline_run_next_parser.add_argument("--briefing-title", default=None)

    briefing_parser = subparsers.add_parser("briefing", help="Briefing commands.")
    briefing_subparsers = briefing_parser.add_subparsers(dest="briefing_command")
    generate_parser = briefing_subparsers.add_parser(
        "generate",
        help="Generate a Markdown Briefing from accepted Ledger state.",
    )
    generate_parser.add_argument("--title", required=True)
    generate_parser.add_argument("--previous-briefing-id", default=None)
    generate_parser.add_argument("--ledger-path", type=Path, default=None)
    generate_parser.add_argument("--archive-path", type=Path, default=None)

    return parser


def _add_model_runtime_arguments(
    parser: argparse.ArgumentParser,
    *,
    include_fixture: bool,
) -> None:
    choices = MODEL_RUNTIME_ADAPTERS if include_fixture else ("llama_server", "ollama")
    parser.add_argument("--runtime-profile", default=None)
    parser.add_argument("--model-runtime", choices=choices, default=None)
    parser.add_argument("--model-endpoint", default=None)
    parser.add_argument("--model-name", default=None)
    parser.add_argument("--model-timeout-seconds", type=float, default=None)
    parser.add_argument("--model-context-tokens", type=int, default=None)
    parser.add_argument("--model-max-output-tokens", type=int, default=None)
    if include_fixture:
        parser.add_argument("--model-output-fixture", type=Path, default=None)


def init_ledger(config: PipelineConfig) -> int:
    config.archive_path.mkdir(parents=True, exist_ok=True)
    result = initialize_ledger(SQLiteLedgerInitializer(config.ledger_path))
    if result.applied_migrations:
        migrations = ", ".join(result.applied_migrations)
    else:
        migrations = "none"
    print(f"Ledger initialized: {result.ledger_path}")
    print(f"Archive path ready: {config.archive_path}")
    print(f"Applied migrations: {migrations}")
    return 0


def initialize_user_environment(
    *,
    config_path: Path | None,
    ledger_path_override: Path | None,
    archive_path_override: Path | None,
) -> int:
    """Create or validate the user config, then initialize its local storage."""
    try:
        config_file, config, created = initialize_user_processing_config(
            config_path=config_path,
            ledger_path_override=ledger_path_override,
            archive_path_override=archive_path_override,
        )
        config.storage.archive_path.mkdir(parents=True, exist_ok=True)
        result = initialize_ledger(SQLiteLedgerInitializer(config.storage.ledger_path))
    except ProcessingConfigurationError as error:
        print(str(error), file=sys.stderr)
        return 1
    except (OSError, sqlite3.Error) as error:
        print(f"Unable to initialize KoteKomi storage: {error}", file=sys.stderr)
        return 1
    action = "Created" if created else "Using"
    migrations = ", ".join(result.applied_migrations) if result.applied_migrations else "none"
    print(f"{action} configuration: {config_file}")
    print(f"Ledger initialized: {result.ledger_path}")
    print(f"Archive path ready: {config.storage.archive_path}")
    print(f"Applied migrations: {migrations}")
    return 0


class _RetrievalValidationTokenizer:
    tokenizer_id = "retrieval_validation_whitespace_v1"

    def count_tokens(self, rendered_input: bytes) -> int:
        return len(rendered_input.decode("utf-8").split())


def _retrieval_index_path(ledger_path: Path) -> Path:
    return ledger_path.with_suffix(".retrieval.sqlite")


def build_document_retrieval_index(
    *,
    ledger_path: Path,
    representation_id: str,
    output_format: str,
    rebuild: bool = False,
    channel: str | None = None,
    embedding_profile: EmbeddingProfile | None = None,
) -> int:
    projection = SQLiteDocumentRetrievalAdapter(_retrieval_index_path(ledger_path))
    try:
        if channel == "semantic":
            if embedding_profile is None:
                return _print_retrieval_payload(
                    {"status": "failed", "failure": "semantic_profile_unavailable"}, output_format
                )
            profile = embedding_profile
            if rebuild:
                projection.delete_semantic_projection(representation_id, profile.profile_id)
            with sqlite_ledger_transaction(ledger_path) as ledger_repository:
                result = build_document_semantic_projection(
                    BuildDocumentSemanticProjectionCommand(
                        representation_id=representation_id, embedding_profile=profile
                    ),
                    ledger_repository=ledger_repository,
                    projection=projection,
                    embedding=_embedding_adapter(profile.adapter_id),
                )
            payload = _retrieval_build_payload(result)
        elif channel == "exact-lexical":
            if rebuild:
                projection.delete_projection(representation_id)
            with sqlite_ledger_transaction(ledger_path) as ledger_repository:
                result = build_document_retrieval_projection(
                    BuildDocumentRetrievalProjectionCommand(representation_id=representation_id),
                    ledger_repository=ledger_repository,
                    projection=projection,
                )
            payload = _retrieval_build_payload(result)
        else:
            if embedding_profile is None:
                return _print_retrieval_payload(
                    {"status": "failed", "failure": "hybrid_profile_unavailable"}, output_format
                )
            profile = embedding_profile
            if rebuild:
                projection.delete_projection(representation_id)
                projection.delete_semantic_projection(representation_id, profile.profile_id)
            with sqlite_ledger_transaction(ledger_path) as ledger_repository:
                exact_result = build_document_retrieval_projection(
                    BuildDocumentRetrievalProjectionCommand(representation_id=representation_id),
                    ledger_repository=ledger_repository,
                    projection=projection,
                )
                semantic_result = build_document_semantic_projection(
                    BuildDocumentSemanticProjectionCommand(
                        representation_id=representation_id, embedding_profile=profile
                    ),
                    ledger_repository=ledger_repository,
                    projection=projection,
                    embedding=_embedding_adapter(profile.adapter_id),
                )
            payload = {
                "status": (
                    "complete"
                    if exact_result.status == "complete" and semantic_result.status == "complete"
                    else "failed"
                ),
                "representation_id": representation_id,
                "index_manifest_ids": [
                    exact_result.index_manifest_id,
                    semantic_result.index_manifest_id,
                ],
                "unit_count": exact_result.unit_count,
                "representation_count": exact_result.representation_count,
                "failure": next(
                    (
                        item.failure.value
                        for item in (exact_result, semantic_result)
                        if item.failure is not None
                    ),
                    None,
                ),
                "embedding_profile_id": semantic_result.embedding_profile_id,
                "embedding_model_identity": (
                    semantic_result.embedding_model_identity.model_dump(mode="json")
                    if semantic_result.embedding_model_identity is not None
                    else None
                ),
            }
    finally:
        projection.close()
    return _print_retrieval_payload(payload, output_format)


def _retrieval_build_payload(result: BuildDocumentRetrievalProjectionResult) -> dict[str, object]:
    return {
        "status": result.status,
        "representation_id": result.representation_id,
        "index_manifest_id": result.index_manifest_id,
        "unit_count": result.unit_count,
        "representation_count": result.representation_count,
        "content_fingerprint": result.content_fingerprint,
        "reused_existing_manifest": result.reused_existing_manifest,
        "failure": result.failure.value if result.failure is not None else None,
        "embedding_profile_id": result.embedding_profile_id,
        "embedding_model_identity": (
            result.embedding_model_identity.model_dump(mode="json")
            if result.embedding_model_identity is not None
            else None
        ),
    }


def build_ledger_retrieval_index(*, ledger_path: Path, output_format: str, rebuild: bool) -> int:
    projection = SQLiteLedgerRetrievalAdapter(_retrieval_index_path(ledger_path))
    try:
        if rebuild:
            projection.delete_projection()
        with sqlite_ledger_transaction(ledger_path) as ledger_repository:
            result = build_ledger_retrieval_projection(
                BuildLedgerRetrievalProjectionCommand(),
                ledger_repository=ledger_repository,
                projection=projection,
            )
    finally:
        projection.close()
    return _print_retrieval_payload(
        {
            "status": result.status,
            "index_manifest_id": result.index_manifest_id,
            "unit_count": result.unit_count,
            "representation_count": result.representation_count,
            "content_fingerprint": result.content_fingerprint,
            "reused_existing_manifest": result.reused_existing_manifest,
            "failure": result.failure.value if result.failure is not None else None,
        },
        output_format,
    )


def query_ledger_retrieval_index(
    *,
    ledger_path: Path,
    query: str,
    record_id: str | None,
    record_type: str | None,
    assertion_statuses: tuple[str, ...],
    subject_id: str | None,
    predicate: str | None,
    policy: str,
    maximum_hits: int,
    context_profile: str,
    output_format: str,
) -> int:
    policy_ids = {
        "current-relevance": "ledger_current_relevance_v1",
        "current-latest": "ledger_current_latest_v1",
        "audit-history": "ledger_audit_history_v1",
    }
    try:
        filters = LedgerRetrievalFilters(
            record_id=record_id,
            record_type=LedgerRetrievalRecordType(record_type) if record_type is not None else None,
            assertion_statuses=tuple(AssertionStatus(item) for item in assertion_statuses),
            subject_id=subject_id,
            predicate=predicate,
        )
    except ValueError:
        return _print_retrieval_payload(
            {"status": "failed", "failure": "ledger_retrieval_invalid_filter"}, output_format
        )
    projection = SQLiteLedgerRetrievalAdapter(_retrieval_index_path(ledger_path))
    try:
        with sqlite_ledger_transaction(ledger_path) as ledger_repository:
            result = query_ledger_retrieval(
                QueryLedgerRetrievalCommand(
                    query_text=query,
                    filters=filters,
                    policy_id=policy_ids[policy],
                    maximum_hits=maximum_hits,
                    context_profile_id=context_profile,
                ),
                ledger_repository=ledger_repository,
                projection=projection,
                tokenizer=_RetrievalValidationTokenizer(),
            )
    finally:
        projection.close()
    return _print_retrieval_payload(
        {
            "status": result.status,
            "retrieval_query_id": result.retrieval_query_id,
            "index_manifest_id": result.index_manifest_id,
            "hits": [item.model_dump(mode="json") for item in result.hits],
            "selected_record_ids": list(result.selected_record_ids),
            "context_results": [item.model_dump(mode="json") for item in result.context_results],
            "failure": result.failure.value if result.failure is not None else None,
            "query_policy_id": result.query_policy_id,
        },
        output_format,
    )


def _knowledge_graph_index_path(ledger_path: Path) -> Path:
    return ledger_path.with_suffix(".knowledge-graph.sqlite")


def build_knowledge_graph_retrieval_index(
    *, ledger_path: Path, output_format: str, rebuild: bool
) -> int:
    projection = SQLiteKnowledgeGraphRetrievalAdapter(_knowledge_graph_index_path(ledger_path))
    try:
        if rebuild:
            projection.delete_projection()
        with sqlite_ledger_transaction(ledger_path) as ledger_repository:
            result = build_knowledge_graph_projection(
                BuildKnowledgeGraphProjectionCommand(),
                ledger_repository=ledger_repository,
                projection=projection,
            )
    finally:
        projection.close()
    return _print_retrieval_payload(
        {
            "status": result.status,
            "index_manifest_id": result.index_manifest_id,
            "unit_count": result.unit_count,
            "node_count": result.node_count,
            "edge_count": result.edge_count,
            "content_fingerprint": result.content_fingerprint,
            "reused_existing_manifest": result.reused_existing_manifest,
            "failure": result.failure.value if result.failure is not None else None,
        },
        output_format,
    )


def query_knowledge_graph_retrieval_index(
    *,
    ledger_path: Path,
    seed: str,
    maximum_hops: int,
    maximum_hits: int,
    context_profile: str,
    output_format: str,
) -> int:
    projection = SQLiteKnowledgeGraphRetrievalAdapter(_knowledge_graph_index_path(ledger_path))
    try:
        with sqlite_ledger_transaction(ledger_path) as ledger_repository:
            result = query_knowledge_graph(
                QueryKnowledgeGraphCommand(
                    seed_text=seed,
                    maximum_hops=maximum_hops,
                    maximum_hits=maximum_hits,
                    context_profile_id=context_profile,
                ),
                ledger_repository=ledger_repository,
                projection=projection,
                tokenizer=_RetrievalValidationTokenizer(),
            )
    finally:
        projection.close()
    return _print_retrieval_payload(
        {
            "status": result.status,
            "retrieval_query_id": result.retrieval_query_id,
            "index_manifest_id": result.index_manifest_id,
            "seed_candidates": [item.model_dump(mode="json") for item in result.seed_candidates],
            "hits": [item.model_dump(mode="json") for item in result.hits],
            "selected_record_ids": list(result.selected_record_ids),
            "context_results": [item.model_dump(mode="json") for item in result.context_results],
            "failure": result.failure.value if result.failure is not None else None,
            "query_policy_id": result.query_policy_id,
        },
        output_format,
    )


def query_cross_plane_retrieval_index(*, ledger_path: Path, query: str, output_format: str) -> int:
    ledger_projection = SQLiteLedgerRetrievalAdapter(_retrieval_index_path(ledger_path))
    graph_projection = SQLiteKnowledgeGraphRetrievalAdapter(
        _knowledge_graph_index_path(ledger_path)
    )
    try:
        with sqlite_ledger_transaction(ledger_path) as ledger_repository:
            result = query_cross_plane(
                QueryCrossPlaneCommand(query_text=query, policy_id=CROSS_PLANE_QUERY_POLICY_ID),
                ledger_repository=ledger_repository,
                ledger_projection=ledger_projection,
                graph_projection=graph_projection,
                tokenizer=_RetrievalValidationTokenizer(),
            )
    finally:
        ledger_projection.close()
        graph_projection.close()
    return _print_retrieval_payload(
        {
            "status": result.status,
            "cross_plane_query_id": result.cross_plane_query_id,
            "policy_id": CROSS_PLANE_QUERY_POLICY_ID,
            "transitions": [item.model_dump(mode="json") for item in result.transitions],
            "selected_record_ids": list(result.selected_record_ids),
            "terminal_evidence_target_ids": list(result.terminal_evidence_target_ids),
            "context_results": [item.model_dump(mode="json") for item in result.context_results],
            "failure": result.failure.value if result.failure is not None else None,
        },
        output_format,
    )


def build_evidence_graph_projection_index(
    *, ledger_path: Path, output_format: str, rebuild: bool, as_of: datetime | None
) -> int:
    projection = SQLiteKnowledgeGraphRetrievalAdapter(_knowledge_graph_index_path(ledger_path))
    try:
        if rebuild:
            projection.delete_evidence_graph_projection(
                EvidenceGraphViewKind.AS_OF if as_of is not None else EvidenceGraphViewKind.CURRENT,
                as_of,
            )
        with sqlite_ledger_transaction(ledger_path) as ledger_repository:
            result = build_evidence_graph_projection(
                BuildEvidenceGraphProjectionCommand(as_of=as_of),
                ledger_repository=ledger_repository,
                projection=projection,
            )
    finally:
        projection.close()
    return _print_retrieval_payload(
        {
            "status": result.status,
            "projection_manifest_id": result.projection_manifest_id,
            "edge_count": result.edge_count,
            "contribution_count": result.contribution_count,
            "lineage_cluster_count": result.lineage_cluster_count,
            "dimension_count": result.dimension_count,
            "score_count": result.score_count,
            "content_fingerprint": result.content_fingerprint,
            "reused_existing_manifest": result.reused_existing_manifest,
            "view_kind": result.view_kind.value,
            "as_of": result.as_of.isoformat() if result.as_of is not None else None,
            "failure": result.failure.value if result.failure is not None else None,
        },
        output_format,
    )


def explain_evidence_graph_relationship_index(
    *,
    ledger_path: Path,
    relationship_id: str,
    context_profile: str,
    output_format: str,
    as_of: datetime | None,
) -> int:
    projection = SQLiteKnowledgeGraphRetrievalAdapter(_knowledge_graph_index_path(ledger_path))
    try:
        with sqlite_ledger_transaction(ledger_path) as ledger_repository:
            result = explain_evidence_graph_relationship(
                ExplainEvidenceGraphRelationshipCommand(
                    relationship_id=relationship_id,
                    context_profile_id=context_profile,
                    as_of=as_of,
                ),
                ledger_repository=ledger_repository,
                projection=projection,
                tokenizer=_RetrievalValidationTokenizer(),
            )
    finally:
        projection.close()
    return _print_retrieval_payload(
        {
            "status": result.status,
            "explanation_id": result.explanation_id,
            "projection_manifest_id": result.projection_manifest_id,
            "edge": result.edge.model_dump(mode="json") if result.edge is not None else None,
            "contributions": [item.model_dump(mode="json") for item in result.contributions],
            "lineage_clusters": [item.model_dump(mode="json") for item in result.lineage_clusters],
            "dimensions": [item.model_dump(mode="json") for item in result.dimensions],
            "score": result.score.model_dump(mode="json") if result.score is not None else None,
            "raw_document_count": result.raw_document_count,
            "lineage_cluster_count": result.lineage_cluster_count,
            "context_results": [item.model_dump(mode="json") for item in result.context_results],
            "failure": result.failure.value if result.failure is not None else None,
            "policy_id": result.policy_id,
            "view_kind": result.view_kind.value,
            "as_of": result.as_of.isoformat() if result.as_of is not None else None,
        },
        output_format,
    )


def _parse_utc_timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("--as-of must be an RFC 3339 UTC timestamp.") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != UTC.utcoffset(parsed):
        raise argparse.ArgumentTypeError("--as-of must use a UTC offset.")
    return parsed.astimezone(UTC)


def query_document_retrieval_index(
    *,
    ledger_path: Path,
    representation_id: str,
    query: str,
    maximum_hits: int,
    context_profile: str,
    output_format: str,
    channel: str | None = None,
    embedding_profile: EmbeddingProfile | None = None,
) -> int:
    projection = SQLiteDocumentRetrievalAdapter(_retrieval_index_path(ledger_path))
    try:
        with sqlite_ledger_transaction(ledger_path) as ledger_repository:
            if channel == "semantic":
                if embedding_profile is None:
                    return _print_retrieval_payload(
                        {"status": "failed", "failure": "semantic_profile_unavailable"},
                        output_format,
                    )
                profile = embedding_profile
                result = query_document_semantic_retrieval(
                    QueryDocumentSemanticRetrievalCommand(
                        representation_id=representation_id,
                        query_text=query,
                        maximum_hits=maximum_hits,
                        context_profile_id=context_profile,
                        embedding_profile=profile,
                    ),
                    ledger_repository=ledger_repository,
                    projection=projection,
                    embedding=_embedding_adapter(profile.adapter_id),
                    tokenizer=_RetrievalValidationTokenizer(),
                )
            elif channel == "exact-lexical":
                result = query_document_retrieval(
                    QueryDocumentRetrievalCommand(
                        representation_id=representation_id,
                        query_text=query,
                        maximum_hits=maximum_hits,
                        context_profile_id=context_profile,
                    ),
                    ledger_repository=ledger_repository,
                    projection=projection,
                    tokenizer=_RetrievalValidationTokenizer(),
                )
            else:
                if embedding_profile is None:
                    return _print_retrieval_payload(
                        {"status": "failed", "failure": "hybrid_profile_unavailable"},
                        output_format,
                    )
                profile = embedding_profile
                result = query_document_hybrid_retrieval(
                    QueryDocumentHybridRetrievalCommand(
                        representation_id=representation_id,
                        query_text=query,
                        maximum_hits=maximum_hits,
                        context_profile_id=context_profile,
                        embedding_profile=profile,
                    ),
                    ledger_repository=ledger_repository,
                    exact_lexical_projection=projection,
                    semantic_projection=projection,
                    embedding=_embedding_adapter(profile.adapter_id),
                    tokenizer=_RetrievalValidationTokenizer(),
                )
            bundle = ledger_repository.get_document_representation_bundle(representation_id)
    finally:
        projection.close()
    authoritative_nodes = _retrieval_authoritative_nodes(result.selected_node_ids, bundle)
    payload = {
        "status": result.status,
        "retrieval_query_id": result.retrieval_query_id,
        "representation_id": result.representation_id,
        "index_manifest_ids": list(result.index_manifest_ids),
        "hits": [hit.model_dump(mode="json") for hit in result.hits],
        "selected_node_ids": list(result.selected_node_ids),
        "analysis_unit_id": result.analysis_unit_id,
        "context_manifest_id": result.context_manifest_id,
        "context_manifest_rendered_input": (
            result.context_manifest_rendered_input.decode("utf-8")
            if result.context_manifest_rendered_input is not None
            else None
        ),
        "authoritative_nodes": authoritative_nodes,
        "failure": result.failure.value if result.failure is not None else None,
        "embedding_profile_id": result.embedding_profile_id,
        "embedding_model_identity": (
            result.embedding_model_identity.model_dump(mode="json")
            if result.embedding_model_identity is not None
            else None
        ),
        "query_policy_id": result.query_policy_id,
        "consulted_channels": [channel.value for channel in result.consulted_channels],
    }
    return _print_retrieval_payload(payload, output_format)


def _embedding_profile(config: PipelineConfig, profile_id: str | None) -> EmbeddingProfile | None:
    if profile_id is None:
        return None
    return config.embedding_profiles.get(profile_id)


def _normal_embedding_profile(config: PipelineConfig) -> EmbeddingProfile | None:
    profile_id = config.document_retrieval_embedding_profile_id
    return config.embedding_profiles.get(profile_id) if profile_id is not None else None


def _embedding_adapter(adapter_id: str) -> EmbeddingPort:
    if adapter_id == "lm_studio":
        return LMStudioEmbeddingAdapter()
    if adapter_id == "llama_server":
        return LlamaServerEmbeddingAdapter()
    if adapter_id == "ollama":
        return OllamaEmbeddingAdapter()
    raise ValueError(f"Unsupported embedding Adapter: {adapter_id}.")


def _retrieval_authoritative_nodes(
    selected_node_ids: tuple[str, ...], bundle: DocumentRepresentationBundle | None
) -> list[dict[str, object]]:
    if bundle is None:
        return []
    nodes = {node.id: node for node in bundle.nodes}
    text_views = {view.id: view for view in bundle.text_views}
    result: list[dict[str, object]] = []
    for node_id in selected_node_ids:
        node = nodes.get(node_id)
        if node is None:
            continue
        text_view = text_views[node.text_view_id]
        result.append(
            {
                "node_id": node.id,
                "node_type": node.node_type,
                "section_path": list(node.section_path),
                "text": text_view.text[node.start_char : node.end_char],
            }
        )
    return result


def _print_retrieval_payload(payload: Mapping[str, object], output_format: str) -> int:
    if output_format == "json":
        print(json.dumps(payload, sort_keys=True))
    else:
        print(f"Retrieval {payload['status']}")
        print(json.dumps(payload, sort_keys=True, indent=2))
    return 0 if payload["status"] == "complete" else 1


def add_source_file(
    config: ProcessingConfig,
    source_file_path: Path,
    source_url: str,
    output_format: str,
) -> int:
    source_url = normalize_source_url(source_url)
    raw_bytes = source_file_path.read_bytes()
    payload: dict[str, JsonValue]
    archive_store = LocalArchiveStore(config.storage.archive_path)
    archive_store.initialize()
    with sqlite_ledger_transaction(config.storage.ledger_path) as ledger_repository:
        if source_file_path.suffix.lower() == ".pdf":
            result = commit_authoritative_pdf_capture(
                AuthoritativePdfCaptureRequest(
                    local_file_path=str(source_file_path),
                    filename=source_file_path.name,
                    raw_bytes=raw_bytes,
                    source_url=source_url,
                    ingested_at=datetime.now(UTC),
                    build_identity=config.build_identity,
                ),
                archive_store,
                ledger_repository,
                DoclingPdfParser(DoclingPdfParserConfig()),
                Uuid4ProcessingAttemptIdFactory(),
            )
            status = (
                "failed"
                if result.failed
                else "blocked"
                if result.blocking_reasons
                else "created"
                if result.created
                else "reused"
            )
            payload = {
                "status": status,
                "source_id": result.source_id,
                "document_id": result.document_id,
                "raw_path": result.raw_path,
                "representation_id": result.representation_id,
                "provenance_activity_id": result.provenance_activity_id,
                "blocking_reasons": list(result.blocking_reasons),
            }
        else:
            result = commit_authoritative_capture(
                AuthoritativeCaptureRequest(
                    local_file_path=str(source_file_path),
                    filename=source_file_path.name,
                    raw_bytes=raw_bytes,
                    ingested_at=datetime.now(UTC),
                    build_identity=config.build_identity,
                    source_url=source_url,
                ),
                archive_store,
                ledger_repository,
                Uuid4ProcessingAttemptIdFactory(),
            )
            payload = {
                "status": "created" if result.created else "reused",
                "source_id": result.source_id,
                "document_id": result.document_id,
                "raw_path": result.raw_path,
                "representation_id": result.representation_id,
                "provenance_activity_id": result.provenance_activity_id,
                "blocking_reasons": [],
            }
    if output_format == "json":
        print(json.dumps(payload, sort_keys=True))
        return 0
    print(f"Source {payload['status']}: {payload['source_id']}")
    print(f"Document: {payload['document_id']}")
    if payload["provenance_activity_id"] is not None:
        print(f"ProvenanceActivity: {payload['provenance_activity_id']}")
    print(f"Raw path: {payload['raw_path']}")
    blocking_reasons = cast(list[str], payload["blocking_reasons"])
    if blocking_reasons:
        print(f"Blockers: {', '.join(blocking_reasons)}")
    return 0


def ingest_user_file(*, config_path: Path | None, source_file_path: Path, source_url: str) -> int:
    """Run the CIR-1 user ingress path without exposing canonical identities."""
    try:
        config = load_processing_config(
            config_path=config_path,
            ledger_path_override=None,
            archive_path_override=None,
        )
        SQLiteLedgerInitializer(config.storage.ledger_path).initialize()
    except ProcessingConfigurationError as error:
        print(str(error), file=sys.stderr)
        return 1
    except (OSError, sqlite3.Error) as error:
        print(f"Unable to open KoteKomi storage: {error}", file=sys.stderr)
        return 1

    display_filename = source_file_path.name
    if not display_filename:
        print("The requested path must identify a file.", file=sys.stderr)
        return 2

    try:
        with sqlite_ledger_transaction(config.storage.ledger_path) as repository:
            run = start_ingestion_run(
                input=StartIngestionRunInput(
                    requested_path=str(source_file_path),
                    display_filename=display_filename,
                    requested_source_url=source_url,
                ),
                repository=repository,
                id_factory=Uuid4IngestionRunIdFactory(),
                clock=UtcIngestionRunClock(),
            )
    except (OSError, ValueError):
        print("Unable to start the ingestion run.", file=sys.stderr)
        return 1

    archive_store = LocalArchiveStore(config.storage.archive_path)
    try:
        archive_store.initialize()
    except OSError:
        return _record_user_ingestion_error(
            config=config,
            run=run,
            failure_stage=IngestionFailureStage.ARCHIVE,
            failure_code=IngestionFailureCode.ARCHIVE_INITIALIZATION_FAILED,
            safe_failure_message="Unable to initialize the local Archive.",
        )

    if source_file_path.suffix.lower() not in {".pdf", ".md", ".txt"}:
        return _record_user_ingestion_error(
            config=config,
            run=run,
            failure_stage=IngestionFailureStage.SOURCE_VALIDATION,
            failure_code=IngestionFailureCode.UNSUPPORTED_FILE_TYPE,
            safe_failure_message="The deposited file type is not supported.",
        )
    try:
        normalized_source_url = normalize_source_url(source_url)
    except ValueError:
        return _record_user_ingestion_error(
            config=config,
            run=run,
            failure_stage=IngestionFailureStage.SOURCE_VALIDATION,
            failure_code=IngestionFailureCode.SOURCE_URL_INVALID,
            safe_failure_message="The Source URL must be an absolute HTTPS URL.",
        )
    try:
        raw_bytes = source_file_path.read_bytes()
    except FileNotFoundError:
        return _record_user_ingestion_error(
            config=config,
            run=run,
            failure_stage=IngestionFailureStage.SOURCE_VALIDATION,
            failure_code=IngestionFailureCode.FILE_NOT_FOUND,
            safe_failure_message="The requested deposited file was not found.",
            normalized_source_url=normalized_source_url,
        )
    except OSError:
        return _record_user_ingestion_error(
            config=config,
            run=run,
            failure_stage=IngestionFailureStage.SOURCE_CAPTURE,
            failure_code=IngestionFailureCode.SOURCE_CAPTURE_FAILED,
            safe_failure_message="The deposited file could not be read.",
            normalized_source_url=normalized_source_url,
        )

    text_capture_result: AuthoritativeCaptureOutcome | None = None
    pdf_capture_result: AuthoritativePdfCaptureOutcome | None = None
    try:
        with sqlite_ledger_transaction(config.storage.ledger_path) as repository:
            if source_file_path.suffix.lower() == ".pdf":
                pdf_capture_result = commit_authoritative_pdf_capture(
                    AuthoritativePdfCaptureRequest(
                        local_file_path=str(source_file_path),
                        filename=display_filename,
                        raw_bytes=raw_bytes,
                        source_url=normalized_source_url,
                        ingested_at=datetime.now(UTC),
                        build_identity=config.build_identity,
                    ),
                    archive_store,
                    repository,
                    DoclingPdfParser(DoclingPdfParserConfig()),
                    Uuid4ProcessingAttemptIdFactory(),
                )
            else:
                text_capture_result = commit_authoritative_capture(
                    AuthoritativeCaptureRequest(
                        local_file_path=str(source_file_path),
                        filename=display_filename,
                        raw_bytes=raw_bytes,
                        ingested_at=datetime.now(UTC),
                        build_identity=config.build_identity,
                        source_url=normalized_source_url,
                    ),
                    archive_store,
                    repository,
                    Uuid4ProcessingAttemptIdFactory(),
                )
    except Exception:
        return _record_user_ingestion_error(
            config=config,
            run=run,
            failure_stage=IngestionFailureStage.SOURCE_CAPTURE,
            failure_code=IngestionFailureCode.SOURCE_CAPTURE_FAILED,
            safe_failure_message="The deposited source could not be captured.",
            normalized_source_url=normalized_source_url,
        )

    if pdf_capture_result is not None and (
        pdf_capture_result.failed or pdf_capture_result.blocking_reasons
    ):
        return _record_user_ingestion_error(
            config=config,
            run=run,
            failure_stage=IngestionFailureStage.DOCUMENT_REPRESENTATION,
            failure_code=(
                IngestionFailureCode.DOCUMENT_REPRESENTATION_FAILED
                if pdf_capture_result.failed
                else IngestionFailureCode.DOCUMENT_REPRESENTATION_BLOCKED
            ),
            safe_failure_message=(
                "The deposited PDF representation failed."
                if pdf_capture_result.failed
                else "The deposited PDF representation is blocked."
            ),
            normalized_source_url=normalized_source_url,
            source_id=pdf_capture_result.source_id,
            document_id=pdf_capture_result.document_id,
            representation_id=pdf_capture_result.representation_id,
            provenance_activity_id=pdf_capture_result.provenance_activity_id,
        )

    if pdf_capture_result is not None:
        if (
            pdf_capture_result.representation_id is None
            or pdf_capture_result.provenance_activity_id is None
        ):
            return _record_user_ingestion_error(
                config=config,
                run=run,
                failure_stage=IngestionFailureStage.DOCUMENT_REPRESENTATION,
                failure_code=IngestionFailureCode.DOCUMENT_REPRESENTATION_FAILED,
                safe_failure_message="The deposited PDF representation is incomplete.",
                normalized_source_url=normalized_source_url,
                source_id=pdf_capture_result.source_id,
                document_id=pdf_capture_result.document_id,
            )
        source_id = pdf_capture_result.source_id
        document_id = pdf_capture_result.document_id
        representation_id = pdf_capture_result.representation_id
        provenance_activity_id = pdf_capture_result.provenance_activity_id
    elif text_capture_result is not None:
        source_id = text_capture_result.source_id
        document_id = text_capture_result.document_id
        representation_id = text_capture_result.representation_id
        provenance_activity_id = text_capture_result.provenance_activity_id
    else:
        return _record_user_ingestion_error(
            config=config,
            run=run,
            failure_stage=IngestionFailureStage.SOURCE_CAPTURE,
            failure_code=IngestionFailureCode.SOURCE_CAPTURE_FAILED,
            safe_failure_message="The deposited source did not produce a capture result.",
            normalized_source_url=normalized_source_url,
        )

    try:
        with sqlite_ledger_transaction(config.storage.ledger_path) as repository:
            captured = complete_ingestion_run_as_captured(
                input=CompleteIngestionRunCapturedInput(
                    ingestion_run_id=run.id,
                    normalized_source_url=normalized_source_url,
                    source_id=source_id,
                    document_id=document_id,
                    representation_id=representation_id,
                    provenance_activity_id=provenance_activity_id,
                ),
                repository=repository,
                clock=UtcIngestionRunClock(),
            )
    except (OSError, ValueError):
        print("Unable to persist the ingestion result.", file=sys.stderr)
        return 1
    print(_user_ingestion_row(captured))
    return 0


def list_user_ingestion_history(*, config_path: Path | None) -> int:
    try:
        config = load_processing_storage_config(
            config_path=config_path,
            ledger_path_override=None,
            archive_path_override=None,
        )
        SQLiteLedgerInitializer(config.storage.ledger_path).initialize()
        with sqlite_ledger_transaction(config.storage.ledger_path) as repository:
            runs = list_ingestion_runs(repository)
    except ProcessingConfigurationError as error:
        print(str(error), file=sys.stderr)
        return 1
    except (OSError, sqlite3.Error) as error:
        print(f"Unable to open KoteKomi storage: {error}", file=sys.stderr)
        return 1
    for run in runs:
        print(_user_ingestion_row(run))
    return 0


def _record_user_ingestion_error(
    *,
    config: ProcessingConfig,
    run: IngestionRun,
    failure_stage: IngestionFailureStage,
    failure_code: IngestionFailureCode,
    safe_failure_message: str,
    normalized_source_url: str | None = None,
    source_id: str | None = None,
    document_id: str | None = None,
    representation_id: str | None = None,
    provenance_activity_id: str | None = None,
) -> int:
    try:
        with sqlite_ledger_transaction(config.storage.ledger_path) as repository:
            complete_ingestion_run_as_error(
                input=CompleteIngestionRunErrorInput(
                    ingestion_run_id=run.id,
                    failure_stage=failure_stage,
                    failure_code=failure_code,
                    safe_failure_message=safe_failure_message,
                    normalized_source_url=normalized_source_url,
                    source_id=source_id,
                    document_id=document_id,
                    representation_id=representation_id,
                    provenance_activity_id=provenance_activity_id,
                ),
                repository=repository,
                clock=UtcIngestionRunClock(),
            )
    except (OSError, ValueError):
        print("Unable to persist the ingestion failure.", file=sys.stderr)
        return 1
    print(safe_failure_message, file=sys.stderr)
    return 1


def _user_ingestion_row(run: IngestionRun) -> str:
    status = {
        IngestionRunStatus.RUNNING: "[RUNNING]",
        IngestionRunStatus.CAPTURED: "[CAPTURED]",
        IngestionRunStatus.ERROR: "[ERROR]",
    }[run.status]
    timestamp = run.started_at.astimezone(UTC).strftime("%Y-%m-%dT%H:%M")
    return f"{run.display_filename}\t{status}\t{timestamp}"


def add_structured_news(
    *,
    config: ProcessingConfig,
    payload_path: Path,
    envelope_path: Path,
    adapter_name: str,
    media_type: str | None,
    output_format: str,
) -> int:
    payload = payload_path.read_bytes()
    envelope_bytes = envelope_path.read_bytes()
    envelope_value = json.loads(envelope_bytes)
    if not isinstance(envelope_value, dict):
        raise ValueError("Structured-news envelope must be one JSON object.")
    safe_metadata = cast(dict[str, JsonValue], envelope_value)
    adapter = NewsMLG2Adapter() if adapter_name == "newsml-g2" else GenericArticleAdapter()
    resolved_media_type = media_type or (
        "application/newsml+xml" if adapter_name == "newsml-g2" else "text/html"
    )
    now = datetime.now(UTC)
    payload_digest = hashlib.sha256(payload).hexdigest()
    archive = LocalArchiveStore(config.storage.archive_path)
    archive.initialize()
    with sqlite_ledger_transaction(config.storage.ledger_path) as repository:
        outcome = ingest_structured_news(
            NewsIngestInput(
                delivery=NewsDeliveryEnvelope(
                    payload=payload,
                    media_type=resolved_media_type,
                    envelope_bytes=envelope_bytes,
                    envelope_media_type="application/json",
                    retrieval_method="recorded_local_export",
                    requested_uri=str(payload_path),
                    canonical_uri=None,
                    response_status=200,
                    safe_metadata=safe_metadata,
                ),
                captured_at=now,
                transaction_time=now,
                idempotency_key=f"news-{payload_digest}",
                build_identity=config.build_identity,
            ),
            repository,
            archive,
            adapter,
            Uuid4ProcessingAttemptIdFactory(),
            UtcProcessingClock(),
        )
    value = {
        "status": outcome.status.value,
        "source_id": outcome.source_id,
        "document_id": outcome.document_id,
        "representation_id": outcome.representation_id,
        "processing_attempt_id": outcome.processing_attempt_id,
        "rights_profile_id": outcome.rights_profile_id,
        "revision_classification_id": outcome.revision_classification_id,
        "blocking_code": outcome.blocking_code,
        "failure_code": outcome.failure_code,
    }
    if output_format == "json":
        print(json.dumps(value, indent=2, sort_keys=True))
    else:
        print(f"Structured news: {outcome.status.value}")
        print(f"Source: {outcome.source_id or '-'}")
        print(f"Document: {outcome.document_id or '-'}")
        print(f"Representation: {outcome.representation_id or '-'}")
        if outcome.blocking_code:
            print(f"Blocked: {outcome.blocking_code}")
        if outcome.failure_code:
            print(f"Failed: {outcome.failure_code}")
    if outcome.status in {NewsIngestStatus.CREATED, NewsIngestStatus.REUSED}:
        return 0
    return 2 if outcome.status is NewsIngestStatus.BLOCKED else 1


def show_model_runtime_status(*, config: PipelineConfig, output_format: str) -> int:
    runtime = build_model_runtime_readiness(config.model_execution)
    status = runtime.check_readiness()
    if output_format == "json":
        print(json.dumps(model_runtime_status_to_json(status), indent=2, sort_keys=True))
    else:
        print(_model_runtime_status_text(status))
    return 0 if status.ready else 2


def list_reviewed_proposed_changes(
    *,
    config: PipelineConfig,
    review_status: str,
    record_type: str | None,
    source_id: str | None,
    document_id: str | None,
    output_format: str,
) -> int:
    with sqlite_ledger_transaction(config.ledger_path) as ledger_repository:
        result = list_review_queue(
            ReviewQueueInput(
                review_status=ReviewStatus(review_status),
                record_type=record_type,
                source_id=source_id,
                document_id=document_id,
            ),
            ledger_repository,
        )

    if output_format == "json":
        print(json.dumps(review_queue_result_to_json(result), indent=2, sort_keys=True))
        return 0

    print(f"Review Queue: {len(result.items)}")
    print(
        "ProposedChange | Status | RecordType | StableLabel | Source | Document | Model | Created"
    )
    for item in result.items:
        print(
            f"{item.proposed_change_id} | {item.review_status.value} | {item.record_type} | "
            f"{item.stable_label} | {item.source_id or '-'} | {item.document_id or '-'} | "
            f"{item.model_name or '-'} | {item.created_at.isoformat()}"
        )
    return 0


def show_next_reviewed_proposed_change(
    *,
    config: PipelineConfig,
    record_type: str | None,
    source_id: str | None,
    document_id: str | None,
    output_format: str,
) -> int:
    with sqlite_ledger_transaction(config.ledger_path) as ledger_repository:
        result = get_review_next(
            ReviewNextInput(
                record_type=record_type,
                source_id=source_id,
                document_id=document_id,
            ),
            ledger_repository,
        )

    if output_format == "json":
        print(json.dumps(review_next_result_to_json(result), indent=2, sort_keys=True))
        return 0

    print(_review_next_text(result))
    return 0


def run_next_review_decision(
    *,
    config: PipelineConfig,
    decision: str,
    reviewer: str,
    record_type: str | None,
    source_id: str | None,
    document_id: str | None,
    reason: str | None,
    accepted_record_json_path: Path | None,
    dry_run: bool,
    output_format: str,
) -> int:
    accepted_record_json: dict[str, JsonValue] | None = None
    if accepted_record_json_path is not None:
        accepted_record_json = read_json_object(accepted_record_json_path)
    with sqlite_ledger_transaction(config.ledger_path) as ledger_repository:
        result = run_review_next_decision(
            ReviewNextDecisionInput(
                decision=ReviewNextDecision(decision),
                reviewer=reviewer,
                reviewed_at=datetime.now(UTC),
                record_type=record_type,
                source_id=source_id,
                document_id=document_id,
                reason=reason,
                accepted_record_json=accepted_record_json,
                dry_run=dry_run,
            ),
            ledger_repository,
        )

    if output_format == "json":
        print(json.dumps(review_next_decision_result_to_json(result), indent=2, sort_keys=True))
        return 0

    print(_review_next_decision_text(result))
    return 0


def drain_review_queue(
    *,
    config: PipelineConfig,
    decision: str,
    reviewer: str,
    record_type: str | None,
    source_id: str | None,
    document_id: str | None,
    reason: str | None,
    accepted_record_json_path: Path | None,
    limit: int | None,
    dry_run: bool,
    output_format: str,
) -> int:
    accepted_record_json: dict[str, JsonValue] | None = None
    if accepted_record_json_path is not None:
        accepted_record_json = read_json_object(accepted_record_json_path)
    drain_input = ReviewDrainInput(
        decision=ReviewNextDecision(decision),
        reviewer=reviewer,
        reviewed_at=datetime.now(UTC),
        record_type=record_type,
        source_id=source_id,
        document_id=document_id,
        reason=reason,
        accepted_record_json=accepted_record_json,
        limit=limit,
        dry_run=dry_run,
    )
    if dry_run:
        with sqlite_ledger_transaction(config.ledger_path) as ledger_repository:
            result = run_review_drain(drain_input, ledger_repository)
    else:
        result = _drain_review_queue_with_item_transactions(config, drain_input)

    if output_format == "json":
        print(json.dumps(review_drain_result_to_json(result), indent=2, sort_keys=True))
        return 0

    print(_review_drain_text(result))
    return 0


def _drain_review_queue_with_item_transactions(
    config: PipelineConfig,
    drain_input: ReviewDrainInput,
) -> ReviewDrainResult:
    item_results: list[ReviewNextDecisionResult] = []
    while drain_input.limit is None or len(item_results) < drain_input.limit:
        try:
            with sqlite_ledger_transaction(config.ledger_path) as ledger_repository:
                item_result = run_review_next_decision(
                    ReviewNextDecisionInput(
                        decision=drain_input.decision,
                        reviewer=drain_input.reviewer,
                        reviewed_at=drain_input.reviewed_at,
                        record_type=drain_input.record_type,
                        source_id=drain_input.source_id,
                        document_id=drain_input.document_id,
                        reason=drain_input.reason,
                        accepted_record_json=drain_input.accepted_record_json,
                    ),
                    ledger_repository,
                )
        except ValueError as error:
            return ReviewDrainResult(
                decision=drain_input.decision,
                attempted_count=len(item_results) + 1,
                executed_count=sum(1 for result in item_results if result.executed),
                dry_run=False,
                stopped_reason=ReviewDrainStoppedReason.VALIDATION_FAILED,
                item_results=tuple(item_results),
                error_message=str(error),
            )
        if not item_result.has_next:
            return ReviewDrainResult(
                decision=drain_input.decision,
                attempted_count=len(item_results),
                executed_count=sum(1 for result in item_results if result.executed),
                dry_run=False,
                stopped_reason=ReviewDrainStoppedReason.QUEUE_EMPTY,
                item_results=tuple(item_results),
            )
        item_results.append(item_result)

    return ReviewDrainResult(
        decision=drain_input.decision,
        attempted_count=len(item_results),
        executed_count=sum(1 for result in item_results if result.executed),
        dry_run=False,
        stopped_reason=ReviewDrainStoppedReason.LIMIT_REACHED,
        item_results=tuple(item_results),
    )


def show_reviewed_proposed_change(
    *,
    config: PipelineConfig,
    proposed_change_id: str,
    output_format: str,
) -> int:
    with sqlite_ledger_transaction(config.ledger_path) as ledger_repository:
        packet = get_review_packet(
            ReviewPacketInput(proposed_change_id=proposed_change_id),
            ledger_repository,
        )
    if output_format == "json":
        print(json.dumps(review_packet_to_json(packet), indent=2, sort_keys=True))
        return 0
    print(_review_packet_text(packet))
    return 0


def show_review_readiness(
    *,
    config: PipelineConfig,
    record_type: str | None,
    source_id: str | None,
    document_id: str | None,
    output_format: str,
) -> int:
    with sqlite_ledger_transaction(config.ledger_path) as ledger_repository:
        status = get_review_readiness(
            ReviewReadinessInput(
                record_type=record_type,
                source_id=source_id,
                document_id=document_id,
            ),
            ledger_repository,
        )
    if output_format == "json":
        print(json.dumps(review_readiness_to_json(status), indent=2, sort_keys=True))
        return 0
    print(_review_readiness_text(status))
    return 0


def show_pipeline_status(
    *,
    config: PipelineConfig,
    output_format: str,
    source_file_path: Path | None,
    source_url: str | None,
    model_output_fixture_path: Path | None,
    document_id: str | None,
    briefing_title: str | None,
) -> int:
    with sqlite_ledger_transaction(config.ledger_path) as ledger_repository:
        status = get_pipeline_status(
            _pipeline_status_input(
                config=config,
                source_file_path=source_file_path,
                source_url=source_url,
                model_output_fixture_path=model_output_fixture_path,
                document_id=document_id,
                briefing_title=briefing_title,
            ),
            ledger_repository,
        )
    if output_format == "json":
        print(json.dumps(pipeline_status_to_json(status), indent=2, sort_keys=True))
        return 0
    print(_pipeline_status_text(status))
    return 0


def show_pipeline_next(
    *,
    config: PipelineConfig,
    output_format: str,
    source_file_path: Path | None,
    source_url: str | None,
    model_output_fixture_path: Path | None,
    document_id: str | None,
    briefing_title: str | None,
) -> int:
    with sqlite_ledger_transaction(config.ledger_path) as ledger_repository:
        next_step = get_pipeline_next(
            _pipeline_status_input(
                config=config,
                source_file_path=source_file_path,
                source_url=source_url,
                model_output_fixture_path=model_output_fixture_path,
                document_id=document_id,
                briefing_title=briefing_title,
            ),
            ledger_repository,
        )
    if output_format == "json":
        print(json.dumps(pipeline_next_to_json(next_step), indent=2, sort_keys=True))
        return 0
    print(_pipeline_next_text(next_step))
    return 0


def run_pipeline_next(
    *,
    config: PipelineConfig,
    output_format: str,
    dry_run: bool,
    source_file_path: Path | None,
    source_url: str | None,
    model_output_fixture_path: Path | None,
    document_id: str | None,
    briefing_title: str | None,
) -> int:
    pipeline_input = _pipeline_status_input(
        config=config,
        source_file_path=source_file_path,
        source_url=source_url,
        model_output_fixture_path=model_output_fixture_path,
        document_id=document_id,
        briefing_title=briefing_title,
    )
    with sqlite_ledger_transaction(config.ledger_path) as ledger_repository:
        next_step = get_pipeline_next(pipeline_input, ledger_repository)

    result = _run_next_step(next_step, dry_run=dry_run)
    if output_format == "json":
        print(json.dumps(run_next_result_to_json(result), indent=2, sort_keys=True))
    else:
        print(_pipeline_run_next_text(result))
    return result.exit_code


def _run_next_step(
    next_step: PipelineNextStep,
    *,
    dry_run: bool,
) -> PipelineRunNextResult:
    command_plan = next_step.command_plan
    if command_plan.command is None:
        return PipelineRunNextResult(
            stage=next_step.stage,
            command=next_step.command,
            command_plan=command_plan,
            ready_to_execute=command_plan.ready_to_execute,
            executed=False,
            dry_run=dry_run,
            exit_code=0,
            stdout_lines=(),
            stderr_lines=(),
            reason=next_step.reason,
        )
    if not command_plan.ready_to_execute:
        return PipelineRunNextResult(
            stage=next_step.stage,
            command=next_step.command,
            command_plan=command_plan,
            ready_to_execute=False,
            executed=False,
            dry_run=dry_run,
            exit_code=2,
            stdout_lines=(),
            stderr_lines=(),
            reason=next_step.reason,
        )
    if dry_run:
        return PipelineRunNextResult(
            stage=next_step.stage,
            command=next_step.command,
            command_plan=command_plan,
            ready_to_execute=True,
            executed=False,
            dry_run=True,
            exit_code=0,
            stdout_lines=(),
            stderr_lines=(),
            reason=next_step.reason,
        )

    exit_code, stdout_lines, stderr_lines = _dispatch_planned_argv(command_plan.argv)
    return PipelineRunNextResult(
        stage=next_step.stage,
        command=next_step.command,
        command_plan=command_plan,
        ready_to_execute=True,
        executed=True,
        dry_run=False,
        exit_code=exit_code,
        stdout_lines=stdout_lines,
        stderr_lines=stderr_lines,
        reason=next_step.reason,
    )


def _dispatch_planned_argv(argv: tuple[str, ...]) -> tuple[int, tuple[str, ...], tuple[str, ...]]:
    stdout_buffer = io.StringIO()
    stderr_buffer = io.StringIO()
    with contextlib.redirect_stdout(stdout_buffer), contextlib.redirect_stderr(stderr_buffer):
        exit_code = main(list(argv))
    return (
        exit_code,
        tuple(stdout_buffer.getvalue().splitlines()),
        tuple(stderr_buffer.getvalue().splitlines()),
    )


def _pipeline_status_input(
    *,
    config: PipelineConfig,
    source_file_path: Path | None,
    source_url: str | None,
    model_output_fixture_path: Path | None,
    document_id: str | None,
    briefing_title: str | None,
) -> PipelineStatusInput:
    return PipelineStatusInput(
        ledger_path=str(config.ledger_path),
        archive_path=str(config.archive_path),
        source_file_path=_optional_resolved_path(source_file_path),
        source_url=source_url,
        model_runtime_adapter=config.model_execution.adapter,
        model_endpoint=config.model_execution.endpoint,
        model_name=config.model_execution.model,
        model_timeout_seconds=config.model_execution.timeout_seconds,
        model_context_tokens=config.model_execution.context_tokens,
        model_max_output_tokens=config.model_execution.max_output_tokens,
        model_output_fixture_path=_optional_resolved_path(model_output_fixture_path),
        document_id=document_id,
        briefing_title=briefing_title,
    )


def _optional_resolved_path(path: Path | None) -> str | None:
    if path is None:
        return None
    return str(path.resolve())


def export_reviewed_proposed_change(
    *,
    config: PipelineConfig,
    proposed_change_id: str,
    output_path: Path,
) -> int:
    with sqlite_ledger_transaction(config.ledger_path) as ledger_repository:
        result = export_review_editable_record(
            ReviewEditableRecordExportInput(proposed_change_id=proposed_change_id),
            ledger_repository,
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result.record_json, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"ProposedChange: {result.proposed_change_id}")
    print(f"Record type: {result.record_type}")
    print(f"Stable label: {result.stable_label}")
    print(f"Editable record JSON: {output_path}")
    return 0


def _review_packet_text(packet: ReviewPacket) -> str:
    lines = [
        f"ProposedChange: {packet.proposed_change_id}",
        f"Review status: {packet.review_status.value}",
        f"Record type: {packet.record_type}",
        f"Stable label: {packet.stable_label}",
        f"Source: {packet.metadata.source_id or '-'}",
        f"Document: {packet.metadata.document_id or '-'}",
        f"Model: {packet.metadata.model_name or '-'}",
        f"Prompt: {packet.metadata.prompt_id or '-'}",
        f"ProvenanceActivity: {packet.metadata.provenance_activity_id or '-'}",
        f"Created: {packet.metadata.created_at.isoformat()}",
        f"Updated: {packet.metadata.updated_at.isoformat()}",
    ]
    if packet.assertion_context is not None:
        assertion_context = packet.assertion_context
        lines.extend(
            [
                "",
                "Assertion context:",
                f"  Epistemic scope: {assertion_context.epistemic_scope}",
                f"  Source authority: {assertion_context.source_authority}",
                f"  Attribution basis: {assertion_context.attribution_basis}",
                "  Source report confidence: "
                f"{_optional_float(assertion_context.source_report_confidence)}",
                "  Extraction confidence: "
                f"{_optional_float(assertion_context.extraction_confidence)}",
                "  World truth confidence: "
                f"{_optional_float(assertion_context.world_truth_confidence)}",
                f"  Causal confidence: {_optional_float(assertion_context.causal_confidence)}",
            ]
        )
    lines.append("")
    lines.append("Evidence:")
    if packet.evidence_contexts:
        for index, evidence in enumerate(packet.evidence_contexts, start=1):
            lines.extend(
                [
                    f"  {index}. Source: {evidence.source_id}",
                    f"     Source title: {evidence.source_title or '-'}",
                    f"     Document: {evidence.document_id}",
                    f"     Selector: {evidence.selector_type}",
                    f"     Location: {json.dumps(evidence.location, sort_keys=True)}",
                    f"     Prefix: {evidence.prefix_text}",
                    f"     Exact: {evidence.exact_text}",
                    f"     Suffix: {evidence.suffix_text}",
                ]
            )
    else:
        lines.append("  none")
    lines.append("")
    lines.append("References:")
    if packet.reference_contexts:
        for reference in packet.reference_contexts:
            lines.append(
                f"  {reference.referenced_type}: {reference.referenced_id} "
                f"({reference.resolution_status.value})"
            )
    else:
        lines.append("  none")
    lines.append("")
    lines.append("Proposed record JSON:")
    lines.append(json.dumps(packet.proposed_record_json, indent=2, sort_keys=True))
    return "\n".join(lines)


def _review_next_text(result: ReviewNextResult) -> str:
    if not result.has_next:
        return "Next review packet: none"
    if result.packet is None:
        raise ValueError("ReviewNextResult has_next=true without packet")
    lines = [
        f"Next ProposedChange: {result.packet.proposed_change_id}",
        f"Record type: {result.packet.record_type}",
        f"Stable label: {result.packet.stable_label}",
        "",
        _review_packet_text(result.packet),
        "",
        "Review action plans:",
    ]
    for action_plan in result.action_plans:
        lines.append(
            f"  {action_plan.action}: {action_plan.command} "
            f"(ready: {_bool_text(action_plan.ready_to_execute)})"
        )
        if action_plan.missing_inputs:
            for missing_input in action_plan.missing_inputs:
                lines.append(
                    f"    missing {missing_input.name} ({missing_input.kind}): "
                    f"{missing_input.description}"
                )
        else:
            lines.append("    missing inputs: none")
    return "\n".join(lines)


def _review_next_decision_text(result: ReviewNextDecisionResult) -> str:
    lines = [
        f"Decision: {result.decision.value}",
        f"Has next: {_bool_text(result.has_next)}",
        f"Executed: {_bool_text(result.executed)}",
        f"Dry run: {_bool_text(result.dry_run)}",
    ]
    if result.packet is not None:
        lines.extend(
            [
                f"ProposedChange: {result.packet.proposed_change_id}",
                f"Record type: {result.packet.record_type}",
                f"Stable label: {result.packet.stable_label}",
            ]
        )
    else:
        lines.append("ProposedChange: none")
    if result.review_result is not None:
        lines.extend(
            [
                f"Review status: {result.review_result.review_status.value}",
                f"ProvenanceActivity: {result.review_result.provenance_activity_id}",
                f"Accepted record type: {result.review_result.accepted_record_type or '-'}",
                f"Accepted record: {result.review_result.accepted_record_id or '-'}",
            ]
        )
    return "\n".join(lines)


def _review_drain_text(result: ReviewDrainResult) -> str:
    lines = [
        f"Decision: {result.decision.value}",
        f"Attempted: {result.attempted_count}",
        f"Executed: {result.executed_count}",
        f"Dry run: {_bool_text(result.dry_run)}",
        f"Stopped reason: {result.stopped_reason.value}",
    ]
    if result.error_message is not None:
        lines.append(f"Error: {result.error_message}")
    lines.append("Items:")
    if result.item_results:
        for item_result in result.item_results:
            if item_result.item is None:
                continue
            status = (
                item_result.review_result.review_status.value
                if item_result.review_result is not None
                else "not_executed"
            )
            lines.append(
                f"  {item_result.item.proposed_change_id} | "
                f"{item_result.item.record_type} | {item_result.item.stable_label} | {status}"
            )
    else:
        lines.append("  none")
    return "\n".join(lines)


def _review_readiness_text(status: ReviewReadinessStatus) -> str:
    lines = [
        f"Review required: {_bool_text(status.review_required)}",
        f"Pending ProposedChanges: {status.pending_count}",
        f"Pending references: {status.pending_reference_count}",
        f"Missing references: {status.missing_reference_count}",
        f"Can build graph retrieval: {_bool_text(status.can_build_graph_retrieval)}",
        f"Can generate Briefing: {_bool_text(status.can_generate_briefing)}",
        f"Next recommended command: {status.next_recommended_command}",
        "Pending record types:",
    ]
    if status.pending_record_type_counts:
        for record_type, count in status.pending_record_type_counts.items():
            lines.append(f"  {record_type}: {count}")
    else:
        lines.append("  none")
    lines.append("Blockers:")
    if status.blockers:
        for blocker in status.blockers:
            lines.append(
                f"  {blocker.proposed_change_id} | {blocker.record_type} | "
                f"{blocker.stable_label} | {blocker.referenced_type}: "
                f"{blocker.referenced_id} ({blocker.resolution_status.value})"
            )
    else:
        lines.append("  none")
    return "\n".join(lines)


def _model_runtime_status_text(status: ModelRuntimeStatus) -> str:
    lines = [
        f"Model runtime: {status.adapter}",
        f"Endpoint: {status.endpoint}",
        f"Model: {status.model}",
        f"Reachable: {_bool_text(status.reachable)}",
        f"Model available: {_bool_text(status.model_available)}",
        f"Model state: {status.model_state or 'unknown'}",
        f"Idle slots: {_slot_count_text(status.idle_slots, status.total_slots)}",
        f"Ready: {_bool_text(status.ready)}",
    ]
    if status.error_code is not None:
        lines.append(f"Error code: {status.error_code}")
    if status.error_message is not None:
        lines.append(f"Error: {status.error_message}")
    return "\n".join(lines)


def manage_model_server(
    *,
    server_command: str,
    llama_server_path: Path | None,
    output_format: str,
) -> int:
    home_path = Path.home()
    if server_command == "install":
        if llama_server_path is None:
            raise ValueError("model server install requires --llama-server-path.")
        agent_path = install_managed_llama_server(
            ManagedLlamaServerConfig(
                executable_path=llama_server_path.resolve(),
                home_path=home_path,
            )
        )
        _write_model_server_result(
            {"action": "installed", "agent_path": str(agent_path)}, output_format
        )
        return 0
    if server_command == "status":
        status = get_managed_llama_server_status(home_path=home_path)
        _write_model_server_result(
            {
                "installed": status.installed,
                "loaded": status.loaded,
                "path_guarded": status.path_guarded,
                "agent_path": str(status.agent_path),
            },
            output_format,
        )
        return 0
    if server_command == "uninstall":
        agent_path = uninstall_managed_llama_server(home_path=home_path)
        _write_model_server_result(
            {"action": "uninstalled", "agent_path": str(agent_path)}, output_format
        )
        return 0
    raise ValueError(f"Unsupported model server command: {server_command}")


def _write_model_server_result(result: dict[str, object], output_format: str) -> None:
    if output_format == "json":
        print(json.dumps(result, indent=2, sort_keys=True))
        return
    for key, value in result.items():
        print(f"{key}: {value}")


def _slot_count_text(idle_slots: int | None, total_slots: int | None) -> str:
    if idle_slots is None or total_slots is None:
        return "not reported"
    return f"{idle_slots}/{total_slots}"


def _pipeline_status_text(status: PipelineStatus) -> str:
    command_plan = status.next_command_plan
    lines = [
        f"Pipeline stage: {status.stage.value}",
        f"Next command: {status.next_command or 'none'}",
        f"Command plan ready: {_bool_text(command_plan.ready_to_execute)}",
        f"Review required: {_bool_text(status.review_required)}",
        f"Pending ProposedChanges: {status.pending_count}",
        f"Missing references: {status.missing_reference_count}",
        "Counts:",
        f"  Sources: {status.source_count}",
        f"  Documents: {status.document_count}",
        f"  Accepted Assertions: {status.accepted_assertion_count}",
        f"  Relationships: {status.relationship_count}",
        f"  Outcomes: {status.outcome_count}",
        f"  ArgumentEdges: {status.argument_edge_count}",
        f"  Briefings: {status.briefing_count}",
        "Safe commands:",
    ]
    if status.safe_commands:
        lines.extend(f"  {command}" for command in status.safe_commands)
    else:
        lines.append("  none")
    lines.append("Blocked commands:")
    if status.blocked_commands:
        lines.extend(f"  {command}" for command in status.blocked_commands)
    else:
        lines.append("  none")
    lines.append("Candidate Documents:")
    if status.candidate_document_ids:
        lines.extend(f"  {document_id}" for document_id in status.candidate_document_ids)
    else:
        lines.append("  none")
    lines.append("Command plan argv:")
    if command_plan.argv:
        lines.append(f"  {' '.join(command_plan.argv)}")
    else:
        lines.append("  none")
    lines.extend(_missing_inputs_text(command_plan))
    lines.append("Blockers:")
    if status.blockers:
        lines.extend(
            f"  {blocker.command} | {blocker.blocker_type}: {blocker.blocker_id} | {blocker.reason}"
            for blocker in status.blockers
        )
    else:
        lines.append("  none")
    return "\n".join(lines)


def _pipeline_next_text(next_step: PipelineNextStep) -> str:
    command_plan = next_step.command_plan
    lines = [
        f"Pipeline stage: {next_step.stage.value}",
        f"Next command: {next_step.command or 'none'}",
        f"Command plan ready: {_bool_text(command_plan.ready_to_execute)}",
        f"Reason: {next_step.reason}",
        f"Requires human review: {_bool_text(next_step.requires_human_review)}",
        f"Blocked: {_bool_text(next_step.blocked)}",
        "Command plan argv:",
    ]
    if command_plan.argv:
        lines.append(f"  {' '.join(command_plan.argv)}")
    else:
        lines.append("  none")
    lines.extend(_missing_inputs_text(command_plan))
    lines.append(
        "Blockers:",
    )
    if next_step.blockers:
        lines.extend(
            f"  {blocker.command} | {blocker.blocker_type}: {blocker.blocker_id} | {blocker.reason}"
            for blocker in next_step.blockers
        )
    else:
        lines.append("  none")
    return "\n".join(lines)


def _pipeline_run_next_text(result: PipelineRunNextResult) -> str:
    lines = [
        f"Pipeline stage: {result.stage.value}",
        f"Command: {result.command or 'none'}",
        f"Ready to execute: {_bool_text(result.ready_to_execute)}",
        f"Executed: {_bool_text(result.executed)}",
        f"Dry run: {_bool_text(result.dry_run)}",
        f"Exit code: {result.exit_code}",
        f"Reason: {result.reason}",
        "Command plan argv:",
    ]
    if result.command_plan.argv:
        lines.append(f"  {' '.join(result.command_plan.argv)}")
    else:
        lines.append("  none")
    lines.extend(_missing_inputs_text(result.command_plan))
    lines.append("Captured stdout:")
    if result.stdout_lines:
        lines.extend(f"  {line}" for line in result.stdout_lines)
    else:
        lines.append("  none")
    lines.append("Captured stderr:")
    if result.stderr_lines:
        lines.extend(f"  {line}" for line in result.stderr_lines)
    else:
        lines.append("  none")
    lines.append("Blockers:")
    if result.command_plan.blockers:
        lines.extend(
            f"  {blocker.command} | {blocker.blocker_type}: {blocker.blocker_id} | {blocker.reason}"
            for blocker in result.command_plan.blockers
        )
    else:
        lines.append("  none")
    return "\n".join(lines)


def _missing_inputs_text(command_plan: PipelineCommandPlan) -> list[str]:
    lines = ["Missing inputs:"]
    if not command_plan.missing_inputs:
        lines.append("  none")
        return lines
    for missing_input in command_plan.missing_inputs:
        if missing_input.allowed_values:
            allowed_values = ", ".join(missing_input.allowed_values)
            lines.append(
                f"  {missing_input.name} ({missing_input.kind}): "
                f"{missing_input.description} Allowed: {allowed_values}"
            )
        else:
            lines.append(
                f"  {missing_input.name} ({missing_input.kind}): {missing_input.description}"
            )
    return lines


def _bool_text(value: bool) -> str:
    return "yes" if value else "no"


def _optional_float(value: float | None) -> str:
    if value is None:
        return "-"
    return str(value)


def approve_reviewed_proposed_change(
    *,
    config: PipelineConfig,
    proposed_change_id: str,
    reviewer: str,
) -> int:
    with sqlite_ledger_transaction(config.ledger_path) as ledger_repository:
        result = approve_proposed_change(
            ReviewProposedChangeInput(
                proposed_change_id=proposed_change_id,
                reviewer=reviewer,
                reviewed_at=datetime.now(UTC),
            ),
            ledger_repository,
        )

    print(f"ProposedChange: {result.proposed_change_id}")
    print(f"Review status: {result.review_status}")
    print(f"ProvenanceActivity: {result.provenance_activity_id}")
    print(f"Accepted record type: {result.accepted_record_type}")
    print(f"Accepted record: {result.accepted_record_id}")
    return 0


def reject_reviewed_proposed_change(
    *,
    config: PipelineConfig,
    proposed_change_id: str,
    reviewer: str,
    reason: str,
) -> int:
    with sqlite_ledger_transaction(config.ledger_path) as ledger_repository:
        result = reject_proposed_change(
            ReviewProposedChangeInput(
                proposed_change_id=proposed_change_id,
                reviewer=reviewer,
                reviewed_at=datetime.now(UTC),
                reason=reason,
            ),
            ledger_repository,
        )

    print(f"ProposedChange: {result.proposed_change_id}")
    print(f"Review status: {result.review_status}")
    print(f"ProvenanceActivity: {result.provenance_activity_id}")
    return 0


def edit_reviewed_proposed_change(
    *,
    config: PipelineConfig,
    proposed_change_id: str,
    reviewer: str,
    accepted_record_json_path: Path,
) -> int:
    accepted_record_json = read_json_object(accepted_record_json_path)
    with sqlite_ledger_transaction(config.ledger_path) as ledger_repository:
        result = edit_proposed_change(
            ReviewProposedChangeInput(
                proposed_change_id=proposed_change_id,
                reviewer=reviewer,
                reviewed_at=datetime.now(UTC),
                accepted_record_json=accepted_record_json,
            ),
            ledger_repository,
        )

    print(f"ProposedChange: {result.proposed_change_id}")
    print(f"Review status: {result.review_status}")
    print(f"ProvenanceActivity: {result.provenance_activity_id}")
    print(f"Accepted record type: {result.accepted_record_type}")
    print(f"Accepted record: {result.accepted_record_id}")
    return 0


def read_json_object(path: Path) -> dict[str, JsonValue]:
    payload: object = json.loads(path.read_text(encoding="utf-8"))
    converted = _json_value(payload, "accepted record JSON")
    if not isinstance(converted, dict):
        raise ValueError(f"JSON file must contain an object: {path}")
    return cast(dict[str, JsonValue], converted)


def _json_value(value: object, context: str) -> JsonValue:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, list):
        return [_json_value(item, f"{context}[]") for item in cast(list[object], value)]
    if isinstance(value, dict):
        result: dict[str, JsonValue] = {}
        for key, item in cast(dict[object, object], value).items():
            if not isinstance(key, str):
                raise ValueError(f"{context} contains a non-string key.")
            result[key] = _json_value(item, f"{context}.{key}")
        return result
    raise ValueError(f"{context} contains a non-JSON value.")


def generate_markdown_briefing(
    *,
    config: PipelineConfig,
    title: str,
    previous_briefing_id: str | None,
) -> int:
    archive_store = LocalArchiveStore(config.archive_path)
    archive_store.initialize()
    renderer = MarkdownBriefingRenderer()
    with sqlite_ledger_transaction(config.ledger_path) as ledger_repository:
        result = generate_briefing(
            BriefingGenerationInput(
                title=title,
                previous_briefing_id=previous_briefing_id,
                generated_at=datetime.now(UTC),
            ),
            ledger_repository,
            archive_store,
            renderer,
        )

    print(f"Briefing: {result.briefing_id}")
    print(f"ProvenanceActivity: {result.provenance_activity_id}")
    print(f"Markdown path: {result.markdown_path}")
    print(f"Citations path: {result.citation_registry_path}")
    print(f"Entities: {result.entity_count}")
    print(f"Actors: {result.actor_count}")
    print(f"Organizations: {result.organization_count}")
    print(f"Places: {result.place_count}")
    print(f"Events: {result.event_count}")
    print(f"Sources: {result.source_count}")
    print(f"Documents: {result.document_count}")
    print(f"Assertions: {result.assertion_count}")
    print(f"Relationships: {result.relationship_count}")
    print(f"Outcomes: {result.outcome_count}")
    print(f"ArgumentEdges: {result.argument_edge_count}")
    print(f"EvidenceTargets: {result.evidence_target_count}")
    print(f"Analytic inferences: {result.analytic_inference_count}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
