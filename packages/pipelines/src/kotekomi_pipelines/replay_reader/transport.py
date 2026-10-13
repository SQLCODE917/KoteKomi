"""Command-line transport for the replay reader.

Reads the same isolated state root the HP-8 verifier produces and hands the
persisted stage outputs to the pure model and render layers. Read-only: this
module never opens the Ledger or Archive for writing.
"""

from __future__ import annotations

import argparse
import math
import sqlite3
from pathlib import Path

from kotekomi_adapters import LocalArchiveStore, sqlite_ledger_transaction
from kotekomi_application import (
    ListIngestionHistoryInput,
    hybrid_document_coverage_report_from_bytes,
    list_ingestion_history,
)
from kotekomi_application.ingestion_inspection import ParagraphInput
from kotekomi_application.ingestion_inspection_reader import (
    InspectParagraphInput,
    load_inspection_paragraph,
)


def load_paragraph_inputs(
    ledger_path: Path, archive_path: Path, *, ingestion_run_id: str | None = None
) -> tuple[ParagraphInput, ...]:
    archive = LocalArchiveStore(archive_path)
    with sqlite_ledger_transaction(ledger_path) as ledger:
        if ingestion_run_id is None:
            history = list_ingestion_history(ListIngestionHistoryInput(limit=1), ledger)
            if not history.entries:
                raise ValueError("The Ledger contains no IngestionRuns to replay.")
            ingestion_run_id = history.entries[0].ingestion_run_id
        run = ledger.get_ingestion_run(ingestion_run_id)
        if run is None:
            raise ValueError(f"IngestionRun not found: {ingestion_run_id}")
        if run.ingestion_change_set_id is None:
            raise ValueError(
                f"IngestionRun {ingestion_run_id} has no completed Hybrid coverage report."
            )
        change_set = ledger.get_ingestion_change_set(run.ingestion_change_set_id)
        if change_set is None:
            raise ValueError("Missing IngestionChangeSet.")
        report_id = archive.find_hybrid_document_coverage_report_by_sha256(
            change_set.coverage_report_digest
        )
        if report_id is None:
            raise ValueError(
                f"IngestionRun {ingestion_run_id}: coverage report is missing from the Archive."
            )
        report = hybrid_document_coverage_report_from_bytes(
            archive.read_hybrid_document_coverage_report(report_id)
        )
        return tuple(
            load_inspection_paragraph(
                InspectParagraphInput(
                    ingestion_run_id=ingestion_run_id,
                    paragraph_node_id=r.paragraph_node_id,
                    state_root=str(ledger_path.parent),
                ),
                ledger,
                archive,
            )
            for r in report.records
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="kotekomi-replay",
        description="Replay persisted HP-8 state as per-paragraph stage annotations.",
    )
    parser.add_argument("--state-root", type=Path, required=True)
    parser.add_argument(
        "--ingestion-run",
        default=None,
        help="IngestionRun ID to replay; defaults to the latest run in Ledger history",
    )
    parser.add_argument(
        "--paragraph",
        type=int,
        default=None,
        help="one-based paragraph ordinal to render; omit to render all paragraphs",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.0,
        help="seconds between stored phase results",
    )
    parser.add_argument("--plain", action="store_true", help="use ANSI-free source-attached output")
    args = parser.parse_args(argv)
    if not math.isfinite(args.delay) or args.delay < 0:
        parser.error("--delay must be finite and >= 0")
    ledger_path = (args.state_root / "kotekomi.db").resolve()
    archive_path = (args.state_root / "archive").resolve()
    if not ledger_path.exists() or not archive_path.exists():
        parser.error(f"state root is missing kotekomi.db or archive/: {args.state_root}")
    try:
        inputs = load_paragraph_inputs(
            ledger_path, archive_path, ingestion_run_id=args.ingestion_run
        )
    except (OSError, ValueError, sqlite3.Error) as error:
        parser.error(f"cannot replay state root {args.state_root}: {error}")
    if args.paragraph is not None:
        if args.paragraph < 1:
            parser.error("--paragraph must be >= 1")
        selected = [item for item in inputs if item.ordinal + 1 == args.paragraph]
        if not selected:
            raise SystemExit(f"no paragraph with ordinal {args.paragraph - 1}")
    from kotekomi_pipelines.replay_reader.live import replay_paragraphs

    return replay_paragraphs(
        inputs,
        None if args.paragraph is None else args.paragraph - 1,
        plain=args.plain,
        delay=args.delay,
        ledger_path=ledger_path,
    )
