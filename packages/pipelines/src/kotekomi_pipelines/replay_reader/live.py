"""Live ingestion and stored replay drivers for the layered extraction viewer.

The presenter validates phase results and emits UI-neutral paragraph snapshots.
Textual owns interactive screen updates; plain output uses the same annotations.
The representation bundle is loaded lazily and cached for the operation.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sqlite3
import sys
import tempfile
from collections.abc import Callable, Sequence
from pathlib import Path
from threading import Event
from typing import TextIO

from kotekomi_adapters import LocalArchiveStore
from kotekomi_adapters.extraction_view.execution import IngestionProcess
from kotekomi_adapters.extraction_view.render import render_live_block
from kotekomi_adapters.extraction_view.source import (
    InspectionArtifactLoader,
    InspectionSourceLoader,
)
from kotekomi_adapters.extraction_view.tui import ReplayApp
from kotekomi_adapters.sqlite_ledger import sqlite_ledger_transaction
from kotekomi_application.ingestion_execution import (
    StoppedExecutionInput,
    finalize_inspection_execution,
)
from kotekomi_application.ingestion_inspection import (
    InspectionContext,
    ParagraphInput,
    ParagraphSnapshot,
)
from kotekomi_application.ingestion_runs import UtcIngestionRunClock
from kotekomi_application.inspection_session import InspectionSession

from kotekomi_pipelines.cli import ingest_user_file
from kotekomi_pipelines.config import PipelineConfig, load_config
from kotekomi_pipelines.replay_reader.ingestion_worker import run_ingestion_worker
from kotekomi_pipelines.replay_reader.transport import load_paragraph_inputs


def _is_interactive(stream: TextIO) -> bool:
    return stream.isatty() and os.environ.get("TERM") != "dumb"


def create_inspection_session(
    ledger_path: Path,
    *,
    stream: TextIO | None = None,
    on_snapshot: Callable[[ParagraphSnapshot], None] | None = None,
    select_ordinal: int | None = None,
    context: InspectionContext | None = None,
) -> InspectionSession:
    def publish(snapshot: ParagraphSnapshot) -> None:
        if on_snapshot is not None:
            on_snapshot(snapshot)
        if stream is not None:
            stream.write(f"paragraph {snapshot.ordinal + 1}/{snapshot.total} · {snapshot.status}\n")
            stream.write(
                render_live_block(snapshot.profile, snapshot.profile.present_stages) + "\n"
            )
            if snapshot.error:
                stream.write(snapshot.error + "\n")

    archive = LocalArchiveStore(ledger_path.parent / "archive")
    return InspectionSession(
        InspectionSourceLoader(ledger_path),
        on_snapshot=publish,
        select_ordinal=select_ordinal,
        context=context,
        artifacts_port=InspectionArtifactLoader(archive),
    )


def replay_paragraphs(
    paragraphs: Sequence[ParagraphInput],
    select_ordinal: int | None,
    *,
    plain: bool,
    delay: float,
    ledger_path: Path,
) -> int:
    stop = Event()

    def operation(
        on_snapshot: Callable[[ParagraphSnapshot], None], out: TextIO | None = None
    ) -> int:
        presenter = create_inspection_session(ledger_path, stream=out, on_snapshot=on_snapshot)
        presenter.replay_stored(paragraphs, select_ordinal, delay, stop)
        return 130 if stop.is_set() else (1 if presenter.presentation_failed else 0)

    if plain or not _is_interactive(sys.stdout):
        return operation(lambda snapshot: None, sys.stdout)
    app = ReplayApp(
        lambda on_snapshot, out, err: operation(on_snapshot), mode="replay", cancel=stop.set
    )
    result = app.run()
    return app.operation_code if result is None else result


def _isolated_config(config: PipelineConfig, ledger: Path, archive: Path) -> str:
    runtime = config.model_execution
    lines = [
        f"ledger_path = {_toml(ledger)}",
        f"archive_path = {_toml(archive)}",
        'runtime_profile = "hp8-canonical"',
        "",
        "[processing]",
        'representation_policy_version = "deposited-source-v1"',
        "",
        "[runtime_profiles.hp8-canonical]",
        f"adapter = {_toml(runtime.adapter)}",
        f"endpoint = {_toml(runtime.endpoint)}",
        f"model = {_toml(runtime.model)}",
        f"timeout_seconds = {runtime.timeout_seconds}",
        f"context_tokens = {runtime.context_tokens}",
        f"max_output_tokens = {runtime.max_output_tokens}",
        "",
        "[model_resources]",
        f"root = {_toml(config.model_resource_root)}",
    ]
    linker = config.entity_linking
    lines.extend(
        (
            "",
            "[entity_linking]",
            f"adapter = {_toml(linker.adapter)}",
            f"timeout_seconds = {linker.timeout_seconds}",
        )
    )
    return "\n".join(lines) + "\n"


def _toml(value: object) -> str:
    return json.dumps(str(value), ensure_ascii=False)


def _replay_existing(state_root: Path, args: argparse.Namespace) -> int:
    ledger_path = state_root / "kotekomi.db"
    archive_path = state_root / "archive"
    if not ledger_path.exists() or not archive_path.exists():
        raise SystemExit(
            f"state root {state_root} exists but is not replayable "
            "(expected kotekomi.db and archive/)."
        )
    try:
        paragraphs = load_paragraph_inputs(
            ledger_path, archive_path, ingestion_run_id=args.ingestion_run
        )
    except (OSError, ValueError, sqlite3.Error) as error:
        raise SystemExit(f"cannot replay existing state root {state_root}: {error}") from error

    select_ordinal = None if args.paragraph is None else args.paragraph - 1
    if select_ordinal is not None and not any(
        paragraph.ordinal == select_ordinal for paragraph in paragraphs
    ):
        raise SystemExit(f"no paragraph with ordinal {select_ordinal}")

    return replay_paragraphs(
        paragraphs, select_ordinal, plain=args.plain, delay=args.delay, ledger_path=ledger_path
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="kotekomi-live-replay",
        description=(
            "Run canonical HP-8 ingestion once and replay stage annotations live, "
            "or replay previously persisted annotations when --state-root already "
            "holds a completed run."
        ),
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="pipeline config for ingestion; required unless replaying existing state",
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=None,
        help="source file for ingestion; required unless replaying existing state",
    )
    parser.add_argument(
        "--url",
        default=None,
        help="source URL for ingestion; required unless replaying existing state",
    )
    parser.add_argument(
        "--state-root",
        type=Path,
        default=None,
        help=(
            "isolated Ledger and Archive directory; if it already holds kotekomi.db "
            "and archive/, ingestion is skipped and persisted annotations are replayed"
        ),
    )
    parser.add_argument(
        "--ingestion-run",
        default=None,
        help="stored IngestionRun ID to replay; defaults to the latest run in Ledger history",
    )
    parser.add_argument(
        "--paragraph",
        type=int,
        default=None,
        help="one-based paragraph ordinal to replay; omit to replay all paragraphs",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.0,
        help="seconds between stored phase results; fresh ingestion updates immediately",
    )
    parser.add_argument(
        "--plain",
        action="store_true",
        help="use ANSI-free source-attached output instead of Textual",
    )
    args = parser.parse_args(argv)

    if not math.isfinite(args.delay) or args.delay < 0:
        parser.error("--delay must be finite and >= 0")
    if args.paragraph is not None and args.paragraph < 1:
        parser.error("--paragraph must be >= 1")

    if args.state_root is not None:
        state_root = args.state_root.resolve()
        if state_root.exists():
            return _replay_existing(state_root, args)
    else:
        state_root = None

    if args.ingestion_run is not None:
        parser.error("--ingestion-run requires an existing --state-root")

    if args.config is None or args.source is None or args.url is None:
        parser.error("--config, --source, and --url are required to run ingestion")

    source = args.source.resolve()
    configured = load_config(
        config_path=args.config,
        ledger_path_override=None,
        archive_path_override=None,
    )

    temporary: tempfile.TemporaryDirectory[str] | None = None
    if state_root is None:
        temporary = tempfile.TemporaryDirectory(prefix="kotekomi-live-replay-")
        root = Path(temporary.name)
    else:
        root = state_root
        root.mkdir(parents=True)

    try:
        ledger_path = root / "kotekomi.db"
        archive_path = root / "archive"
        config_path = root / "kotekomi.toml"
        config_path.write_text(
            _isolated_config(configured, ledger_path, archive_path),
            encoding="utf-8",
        )
        select_ordinal = None if args.paragraph is None else args.paragraph - 1
        use_plain = args.plain or not _is_interactive(sys.stdout)

        def ingest(
            on_snapshot: Callable[[ParagraphSnapshot], None], out: TextIO, err: TextIO
        ) -> int:
            presenter = create_inspection_session(
                ledger_path,
                stream=out if use_plain else None,
                on_snapshot=on_snapshot,
                select_ordinal=select_ordinal,
            )
            return ingest_user_file(
                config_path=config_path,
                source_file_path=source,
                source_url=args.url,
                stage_progress=presenter.on_stage_progress,
                paragraph_progress=presenter.on_paragraph_progress,
                stdout=out,
                stderr=err,
            )

        if use_plain:
            return ingest(lambda snapshot: None, sys.stdout, sys.stderr)

        def stopped(record_id: str, interrupted: bool) -> None:
            with sqlite_ledger_transaction(ledger_path) as ledger:
                finalize_inspection_execution(
                    StoppedExecutionInput(record_id, interrupted), ledger, UtcIngestionRunClock()
                )

        process = IngestionProcess(
            config_path=str(config_path),
            source_path=str(source),
            source_url=args.url,
            ledger_path=str(ledger_path),
            paragraph_ordinal=select_ordinal,
            worker=run_ingestion_worker,
            on_stopped=stopped,
        )
        app = ReplayApp(process.run, mode="ingestion", cancel=process.cancel)
        result = app.run()
        return app.operation_code if result is None else result
    finally:
        if temporary is not None:
            temporary.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
