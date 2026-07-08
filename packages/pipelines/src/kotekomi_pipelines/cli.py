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
    GraphConnectionMiningInput,
    JsonValue,
    ReviewProposedChangeInput,
    SourceFileIngestInput,
    add_source_from_file,
    approve_proposed_change,
    edit_proposed_change,
    initialize_ledger,
    mine_graph_connections,
    project_ledger_graph,
    propose_assertions_for_document,
    reject_proposed_change,
)

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


if __name__ == "__main__":
    sys.exit(main())
