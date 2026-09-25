"""ANSI in-place live replay of HP-8 stage annotations.

Runs the public Hybrid Pipeline ingestion exactly once over the canonical
source and redraws each paragraph's HP-1..HP-10 annotations in place as each
stage completes. The document representation bundle is loaded from the isolated
Ledger once (lazily, on the first paragraph event) and cached for the run.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
import time
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

from kotekomi_adapters import sqlite_ledger_transaction
from kotekomi_domain import DocumentNode, TextView

from kotekomi_pipelines.cli import ingest_user_file
from kotekomi_pipelines.config import PipelineConfig, load_config
from kotekomi_pipelines.hybrid_document_ingestion import HybridParagraphStageProgress
from kotekomi_pipelines.replay_reader.model import STAGE_ORDER, build_profile
from kotekomi_pipelines.replay_reader.render import render_live_block
from kotekomi_pipelines.replay_reader.transport import ParagraphInput, load_paragraph_inputs
from kotekomi_pipelines.replay_reader.tui import render_tui_block


def _is_interactive(stream: TextIO) -> bool:
    try:
        return bool(stream.isatty())
    except (AttributeError, OSError):
        return False


def _terminal_width() -> int:
    try:
        width = shutil.get_terminal_size().columns
    except (AttributeError, OSError, ValueError):
        return 80
    return width if width > 0 else 80


def _height(frame: str) -> int:
    """Number of terminal rows a frame occupies (newline count + 1)."""
    return frame.count("\n") + 1


@dataclass(frozen=True)
class _ParagraphMeta:
    text: str
    representation_id: str
    paragraph_node_id: str
    node_start_char: int


class LiveReplayPresenter:
    """Accumulate stage outputs and redraw one paragraph block in place."""

    def __init__(
        self,
        ledger_path: Path,
        *,
        stream: TextIO,
        select_ordinal: int | None = None,
        delay: float = 0.0,
        tui: bool = True,
    ) -> None:
        self._ledger_path = ledger_path
        self._stream = stream
        self._select_ordinal = select_ordinal
        self._delay = delay
        self._interactive = _is_interactive(stream)
        self._tui = tui and self._interactive
        self._width = _terminal_width()
        self._nodes: dict[str, DocumentNode] = {}
        self._text_views: dict[str, TextView] = {}
        self._outputs: dict[int, dict[str, object]] = {}
        self._active_ordinal: int | None = None
        self._active_height = 0

    def on_stage_progress(self, event: HybridParagraphStageProgress) -> None:
        if self._select_ordinal is not None and event.ordinal != self._select_ordinal:
            return
        if event.finished:
            if self._active_ordinal == event.ordinal:
                self._set_inactive()
            return
        meta = self._meta(event.representation_id, event.paragraph_node_id)
        outputs = self._outputs.setdefault(event.ordinal, {})
        if event.stage_id is not None and event.stage_output is not None:
            outputs[event.stage_id.value] = event.stage_output
        frame = self._frame(meta, outputs, event.ordinal, event.total)
        if self._active_ordinal == event.ordinal:
            self._update(frame)
        else:
            self._start(frame, event.ordinal)
        if self._delay > 0:
            time.sleep(self._delay)

    def _meta(self, representation_id: str, paragraph_node_id: str) -> _ParagraphMeta:
        if paragraph_node_id not in self._nodes:
            with sqlite_ledger_transaction(self._ledger_path) as ledger:
                bundle = ledger.get_document_representation_bundle(representation_id)
            if bundle is None:
                raise ValueError("paragraph references a missing document representation.")
            self._nodes = {node.id: node for node in bundle.nodes}
            self._text_views = {view.id: view for view in bundle.text_views}
        node = self._nodes[paragraph_node_id]
        view = self._text_views[node.text_view_id]
        return _ParagraphMeta(
            text=view.text[node.start_char : node.end_char],
            representation_id=representation_id,
            paragraph_node_id=paragraph_node_id,
            node_start_char=node.start_char,
        )

    def _frame(
        self,
        meta: _ParagraphMeta,
        outputs: dict[str, object],
        ordinal: int,
        total: int,
    ) -> str:
        heading = f"paragraph {ordinal + 1}/{total}"
        completed = frozenset(outputs)
        try:
            profile = build_profile(
                text=meta.text,
                representation_id=meta.representation_id,
                paragraph_node_id=meta.paragraph_node_id,
                node_start_char=meta.node_start_char,
                stage_outputs=outputs,
            )
            if self._tui:
                return render_tui_block(
                    profile,
                    completed_stages=completed,
                    width=self._width,
                    ordinal=ordinal,
                    total=total,
                )
            block = render_live_block(profile, completed)
        except Exception as error:  # rendering must never abort canonical ingestion
            block = f"stages: {' '.join(sorted(outputs))}\n\n{meta.text}\n\n[render error: {error}]"
        return f"{heading}\n\n{block}"

    def _start(self, frame: str, ordinal: int) -> None:
        self._stream.write(frame + "\n")
        self._stream.flush()
        self._active_ordinal = ordinal
        self._active_height = _height(frame)

    def _update(self, frame: str) -> None:
        height = _height(frame)
        if not self._interactive:
            self._stream.write(frame + "\n")
            self._stream.flush()
            self._active_height = height
            return
        if self._active_height > 0:
            self._stream.write(f"\033[{self._active_height}A")
        self._stream.write("\033[J")
        self._stream.write(frame + "\n")
        self._stream.flush()
        self._active_height = height

    def _set_inactive(self) -> None:
        self._active_ordinal = None
        self._active_height = 0

    def replay_stored(
        self,
        paragraphs: Sequence[ParagraphInput],
        select_ordinal: int | None,
    ) -> None:
        """Reveal persisted stage outputs for already-ingested paragraphs.

        Mirrors the live ingestion reveal without re-running the model: each
        paragraph's stored stage outputs are added in canonical stage order and
        redrawn in place exactly like :meth:`on_stage_progress`.
        """
        total = len(paragraphs)
        for paragraph in paragraphs:
            if select_ordinal is not None and paragraph.ordinal != select_ordinal:
                continue
            meta = _ParagraphMeta(
                text=paragraph.text,
                representation_id=paragraph.representation_id,
                paragraph_node_id=paragraph.paragraph_node_id,
                node_start_char=paragraph.node_start_char,
            )
            ordered = [stage for stage in STAGE_ORDER if stage in paragraph.stage_outputs]
            outputs: dict[str, object] = {}
            if not ordered:
                frame = self._frame(meta, outputs, paragraph.ordinal, total)
                self._start(frame, paragraph.ordinal)
                self._set_inactive()
                continue
            for stage in ordered:
                outputs[stage] = paragraph.stage_outputs[stage]
                frame = self._frame(meta, outputs, paragraph.ordinal, total)
                if self._active_ordinal == paragraph.ordinal:
                    self._update(frame)
                else:
                    self._start(frame, paragraph.ordinal)
                if self._delay > 0:
                    time.sleep(self._delay)
            self._set_inactive()


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
        paragraphs = load_paragraph_inputs(ledger_path, archive_path)
    except (OSError, ValueError) as error:
        raise SystemExit(f"cannot replay existing state root {state_root}: {error}") from error

    select_ordinal = None if args.paragraph is None else args.paragraph - 1
    if select_ordinal is not None and not any(
        paragraph.ordinal == select_ordinal for paragraph in paragraphs
    ):
        raise SystemExit(f"no paragraph with ordinal {select_ordinal}")

    presenter = LiveReplayPresenter(
        ledger_path,
        stream=sys.stdout,
        delay=args.delay,
        tui=not args.plain,
    )
    presenter.replay_stored(paragraphs, select_ordinal)
    return 0


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
        "--paragraph",
        type=int,
        default=None,
        help="one-based paragraph ordinal to replay; omit to replay all paragraphs",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.0,
        help="seconds to pause after each stage redraw",
    )
    parser.add_argument(
        "--plain",
        action="store_true",
        help="disable the ANSI TUI and keep the plain live block even on a terminal",
    )
    args = parser.parse_args(argv)

    if args.paragraph is not None and args.paragraph < 1:
        parser.error("--paragraph must be >= 1")

    if args.state_root is not None:
        state_root = args.state_root.resolve()
        if state_root.exists():
            return _replay_existing(state_root, args)
    else:
        state_root = None

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
        presenter = LiveReplayPresenter(
            ledger_path,
            stream=sys.stdout,
            select_ordinal=select_ordinal,
            delay=args.delay,
            tui=not args.plain,
        )
        return ingest_user_file(
            config_path=config_path,
            source_file_path=source,
            source_url=args.url,
            stage_progress=presenter.on_stage_progress,
        )
    finally:
        if temporary is not None:
            temporary.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
