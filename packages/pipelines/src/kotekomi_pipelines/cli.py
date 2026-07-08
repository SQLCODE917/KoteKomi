"""KoteKomi command-line entrypoint."""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

from kotekomi_adapters import (
    FixtureModelRuntime,
    LocalArchiveStore,
    SQLiteLedgerInitializer,
    sqlite_ledger_transaction,
)
from kotekomi_application import (
    AssertionProposalInput,
    SourceFileIngestInput,
    add_source_from_file,
    initialize_ledger,
    propose_assertions_for_document,
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


if __name__ == "__main__":
    sys.exit(main())
