"""KoteKomi command-line entrypoint."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from kotekomi_adapters import (
    FixtureModelRuntime,
    LocalArchiveStore,
    NetworkXGraphAnalyzer,
    SQLiteLedgerInitializer,
    sqlite_ledger_transaction,
)
from kotekomi_application import (
    AssertionProposalInput,
    BriefingGenerationInput,
    GraphConnectionMiningInput,
    JsonValue,
    ReviewEditableRecordExportInput,
    ReviewPacket,
    ReviewPacketInput,
    ReviewProposedChangeInput,
    ReviewQueueInput,
    ReviewReadinessInput,
    ReviewReadinessStatus,
    SourceFileIngestInput,
    add_source_from_file,
    approve_proposed_change,
    cleanup_created_briefing_archive_object,
    cleanup_created_source_archive_objects,
    edit_proposed_change,
    export_review_editable_record,
    generate_briefing,
    get_review_packet,
    get_review_readiness,
    initialize_ledger,
    list_review_queue,
    mine_graph_connections,
    project_ledger_graph,
    propose_assertions_for_document,
    reject_proposed_change,
    review_packet_to_json,
    review_queue_result_to_json,
    review_readiness_to_json,
)
from kotekomi_briefing import MarkdownBriefingRenderer
from kotekomi_domain import ReviewStatus

from kotekomi_pipelines.config import PipelineConfig, load_config


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

    if args.command == "source" and args.source_command == "add-file":
        config = load_config(
            config_path=args.config,
            ledger_path_override=args.ledger_path,
            archive_path_override=args.archive_path,
        )
        return add_source_file(config, args.path)

    if args.command == "source" and args.source_command == "propose-assertions":
        config = load_config(
            config_path=args.config,
            ledger_path_override=args.ledger_path,
            archive_path_override=args.archive_path,
        )
        return propose_source_assertions(
            config=config,
            document_id=args.document_id,
            model_output_fixture_path=args.model_output_fixture,
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

    if args.command == "graph" and args.graph_command == "project":
        config = load_config(
            config_path=args.config,
            ledger_path_override=args.ledger_path,
            archive_path_override=None,
        )
        return project_graph(config=config)

    if args.command == "graph" and args.graph_command == "mine":
        config = load_config(
            config_path=args.config,
            ledger_path_override=args.ledger_path,
            archive_path_override=None,
        )
        return mine_graph(config=config)

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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="kotekomi")
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Path to kotekomi.toml.",
    )
    subparsers = parser.add_subparsers(dest="command")

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
    add_file_parser.add_argument("--ledger-path", type=Path, default=None)
    add_file_parser.add_argument("--archive-path", type=Path, default=None)

    propose_assertions_parser = source_subparsers.add_parser(
        "propose-assertions",
        help="Create ProposedChange records for a Document through a model runtime.",
    )
    propose_assertions_parser.add_argument("--document-id", required=True)
    propose_assertions_parser.add_argument("--model-output-fixture", type=Path, required=True)
    propose_assertions_parser.add_argument("--ledger-path", type=Path, default=None)
    propose_assertions_parser.add_argument("--archive-path", type=Path, default=None)

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

    graph_parser = subparsers.add_parser("graph", help="Graph projection commands.")
    graph_subparsers = graph_parser.add_subparsers(dest="graph_command")
    project_parser = graph_subparsers.add_parser(
        "project",
        help="Project accepted Ledger records into a graph.",
    )
    project_parser.add_argument("--ledger-path", type=Path, default=None)
    mine_parser = graph_subparsers.add_parser(
        "mine",
        help="Mine graph connections into pending ProposedChange records.",
    )
    mine_parser.add_argument("--ledger-path", type=Path, default=None)

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


def add_source_file(config: PipelineConfig, source_file_path: Path) -> int:
    raw_bytes = source_file_path.read_bytes()
    archive_store = LocalArchiveStore(config.archive_path)
    archive_store.initialize()
    result = None
    try:
        with sqlite_ledger_transaction(config.ledger_path) as ledger_repository:
            result = add_source_from_file(
                SourceFileIngestInput(
                    local_file_path=str(source_file_path),
                    filename=source_file_path.name,
                    raw_bytes=raw_bytes,
                    ingested_at=datetime.now(UTC),
                ),
                archive_store,
                ledger_repository,
            )
    except Exception:
        if result is not None and result.created:
            cleanup_created_source_archive_objects(
                archive_store=archive_store,
                raw_path=result.raw_path,
                extracted_text_path=result.extracted_text_path,
            )
        raise
    status = "created" if result.created else "already_exists"
    print(f"Source {status}: {result.source_id}")
    print(f"Document: {result.document_id}")
    print(f"ProvenanceActivity: {result.provenance_activity_id}")
    print(f"Raw path: {result.raw_path}")
    print(f"Extracted text path: {result.extracted_text_path}")
    return 0


def propose_source_assertions(
    *,
    config: PipelineConfig,
    document_id: str,
    model_output_fixture_path: Path,
) -> int:
    archive_store = LocalArchiveStore(config.archive_path)
    model_runtime = FixtureModelRuntime(model_output_fixture_path)
    with sqlite_ledger_transaction(config.ledger_path) as ledger_repository:
        result = propose_assertions_for_document(
            AssertionProposalInput(
                document_id=document_id,
                proposed_at=datetime.now(UTC),
            ),
            archive_store,
            ledger_repository,
            model_runtime,
        )

    print(f"Document: {result.document_id}")
    print(f"Source: {result.source_id}")
    print(f"ProvenanceActivity: {result.provenance_activity_id}")
    print(f"ProposedChanges: {len(result.proposed_change_ids)}")
    for proposed_change_id in result.proposed_change_ids:
        print(f"ProposedChange: {proposed_change_id}")
    return 0


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
        "ProposedChange | Status | RecordType | StableLabel | Source | Document | "
        "Model | Created"
    )
    for item in result.items:
        print(
            f"{item.proposed_change_id} | {item.review_status.value} | {item.record_type} | "
            f"{item.stable_label} | {item.source_id or '-'} | {item.document_id or '-'} | "
            f"{item.model_name or '-'} | {item.created_at.isoformat()}"
        )
    return 0


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


def _review_readiness_text(status: ReviewReadinessStatus) -> str:
    lines = [
        f"Review required: {_bool_text(status.review_required)}",
        f"Pending ProposedChanges: {status.pending_count}",
        f"Pending references: {status.pending_reference_count}",
        f"Missing references: {status.missing_reference_count}",
        f"Can project graph: {_bool_text(status.can_project_graph)}",
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


def project_graph(*, config: PipelineConfig) -> int:
    graph_analyzer = NetworkXGraphAnalyzer()
    with sqlite_ledger_transaction(config.ledger_path) as ledger_repository:
        projection = project_ledger_graph(ledger_repository, graph_analyzer)

    print(f"Graph nodes: {len(projection.nodes)}")
    print(f"Graph edges: {len(projection.edges)}")
    return 0


def mine_graph(*, config: PipelineConfig) -> int:
    graph_analyzer = NetworkXGraphAnalyzer()
    with sqlite_ledger_transaction(config.ledger_path) as ledger_repository:
        result = mine_graph_connections(
            GraphConnectionMiningInput(mined_at=datetime.now(UTC)),
            ledger_repository,
            graph_analyzer,
        )

    print(f"Candidates: {result.candidate_count}")
    print(f"ProposedChanges: {len(result.proposed_change_ids)}")
    if result.provenance_activity_id is None:
        print("ProvenanceActivity: none")
    else:
        print(f"ProvenanceActivity: {result.provenance_activity_id}")
    for proposed_change_id in result.proposed_change_ids:
        print(f"ProposedChange: {proposed_change_id}")
    return 0


def generate_markdown_briefing(
    *,
    config: PipelineConfig,
    title: str,
    previous_briefing_id: str | None,
) -> int:
    archive_store = LocalArchiveStore(config.archive_path)
    archive_store.initialize()
    renderer = MarkdownBriefingRenderer()
    result = None
    try:
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
    except Exception:
        if result is not None:
            cleanup_created_briefing_archive_object(
                archive_store=archive_store,
                markdown_path=result.markdown_path,
                citation_registry_path=result.citation_registry_path,
            )
        raise

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
    print(f"EvidenceSpans: {result.evidence_span_count}")
    print(f"Analytic inferences: {result.analytic_inference_count}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
