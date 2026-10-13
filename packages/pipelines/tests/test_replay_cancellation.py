"""Bounded real-process cancellation and durable interruption records."""

from __future__ import annotations

import io
import os
import signal
import subprocess
import sys
from multiprocessing.connection import Connection
from pathlib import Path
from threading import Event, Thread
from time import monotonic
from typing import TextIO

import pytest
from kotekomi_adapters import sqlite_ledger_transaction
from kotekomi_adapters.extraction_view.execution import IngestionProcess, send_event
from kotekomi_adapters.extraction_view.tui import ReplayApp, StatusChanged
from kotekomi_application import StartIngestionRunInput, UtcIngestionRunClock, start_ingestion_run
from kotekomi_application.ingestion_execution import (
    AssignedIngestionRunIdFactory,
    FinishedEvent,
    IngestionProcessRequest,
    ParagraphEvent,
    StoppedExecutionInput,
    TextEvent,
    finalize_inspection_execution,
)
from kotekomi_application.ingestion_inspection import ParagraphInput, ParagraphSnapshot
from kotekomi_domain import IngestionFailureCode, IngestionFailureStage, IngestionRunStatus
from kotekomi_pipelines.cli import ingest_user_file
from textual.pilot import Pilot

from packages.pipelines.tests.test_replay_reader import example_profile


def start_worker_run(request: IngestionProcessRequest) -> None:
    with sqlite_ledger_transaction(Path(request.ledger_path)) as ledger:
        start_ingestion_run(
            StartIngestionRunInput(request.source_path, "source.md", request.source_url),
            ledger,
            AssignedIngestionRunIdFactory(request.ingestion_run_id),
            UtcIngestionRunClock(),
        )


def blocked_worker(request: IngestionProcessRequest, connection: Connection) -> None:
    """Synthetic blocked runtime with one committed run and an open SQLite write."""
    if os.name == "posix":
        os.setsid()
    start_worker_run(request)
    with sqlite_ledger_transaction(Path(request.ledger_path)) as ledger:
        start_ingestion_run(
            StartIngestionRunInput(request.source_path, "source.md", request.source_url),
            ledger,
            AssignedIngestionRunIdFactory(request.ingestion_run_id + "_uncommitted"),
            UtcIngestionRunClock(),
        )
        if os.name == "posix":
            signal.signal(signal.SIGTERM, signal.SIG_IGN)  # Prove bounded escalation to SIGKILL.
        send_event(connection, TextEvent(text="blocked", is_error=False))
        Event().wait()


def worker_with_descendant(request: IngestionProcessRequest, connection: Connection) -> None:
    os.setsid()
    start_worker_run(request)
    marker = Path(request.ledger_path).parent / "descendant-pid"
    script = (
        "import signal,time\nsignal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
        "print('ready', flush=True)\ntime.sleep(30)\n"
    )
    child = subprocess.Popen([sys.executable, "-c", script], stdout=subprocess.PIPE, text=True)
    assert child.stdout is not None and child.stdout.readline().strip() == "ready"
    marker.write_text(str(child.pid))
    send_event(connection, TextEvent(text="blocked", is_error=False))
    Event().wait()


def snapshot_worker(request: IngestionProcessRequest, connection: Connection) -> None:
    send_event(connection, ParagraphEvent(snapshot=ParagraphSnapshot(0, 1, example_profile())))
    send_event(connection, TextEvent(text="fixture status", is_error=False))
    send_event(connection, FinishedEvent(code=7))
    connection.close()


def terminal_failure_worker(request: IngestionProcessRequest, connection: Connection) -> None:
    start_worker_run(request)
    send_event(connection, TextEvent(text="Unexpected runtime failure", is_error=True))
    send_event(connection, FinishedEvent(code=1))
    connection.close()


@pytest.fixture
def process_root(tmp_path: Path) -> Path:
    config = tmp_path / "kotekomi.toml"
    config.write_text(
        f'ledger_path = "{tmp_path}/kotekomi.db"\n'
        f'archive_path = "{tmp_path}/archive"\nruntime_profile = "fixture"\n'
        '[processing]\nrepresentation_policy_version = "deposited-source-v1"\n'
    )
    source = tmp_path / "source.md"
    source.write_text("# Source\n\nA coherent deposited fixture.\n")
    # Leave actual committed capture and coverage evidence to prove cancellation preserves it.
    assert (
        ingest_user_file(
            config_path=config,
            source_file_path=source,
            source_url="https://example.test/source",
            stdout=io.StringIO(),
            stderr=io.StringIO(),
        )
        == 0
    )
    return tmp_path


def controller(root: Path) -> IngestionProcess:
    from kotekomi_pipelines.replay_reader.ingestion_worker import run_ingestion_worker

    def stopped(run_id: str, interrupted: bool) -> None:
        with sqlite_ledger_transaction(root / "kotekomi.db") as ledger:
            finalize_inspection_execution(
                StoppedExecutionInput(run_id, interrupted), ledger, UtcIngestionRunClock()
            )

    return IngestionProcess(
        config_path=str(root / "kotekomi.toml"),
        source_path=str(root / "source.md"),
        source_url="https://example.test/source",
        ledger_path=str(root / "kotekomi.db"),
        paragraph_ordinal=None,
        worker=run_ingestion_worker,
        on_stopped=stopped,
    )


def test_spawned_ingestion_finishes_with_assigned_run_identity(process_root: Path) -> None:
    process = controller(process_root)
    out, err = io.StringIO(), io.StringIO()
    assert process.run(lambda snapshot: None, out, err) == 0
    assert process.request.ingestion_run_id in out.getvalue()
    assert err.getvalue() == ""
    assert process.process is None
    with sqlite_ledger_transaction(process_root / "kotekomi.db") as ledger:
        run = ledger.get_ingestion_run(process.request.ingestion_run_id)
        assert run is not None and run.status is IngestionRunStatus.CAPTURED


def test_unexpected_worker_failure_closes_its_running_ingestion_record(
    process_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from kotekomi_pipelines.replay_reader import ingestion_worker as ingestion_process

    monkeypatch.setattr(ingestion_process, "run_ingestion_worker", terminal_failure_worker)
    process = controller(process_root)
    out, err = io.StringIO(), io.StringIO()
    assert process.run(lambda snapshot: None, out, err) == 1
    assert err.getvalue() == "Unexpected runtime failure\n"
    with sqlite_ledger_transaction(process_root / "kotekomi.db") as ledger:
        run = ledger.get_ingestion_run(process.request.ingestion_run_id)
        assert run is not None and run.status is IngestionRunStatus.ERROR
        assert run.failure_code is IngestionFailureCode.AUTOMATIC_EXTRACTION_FAILED


@pytest.mark.parametrize("descendant", [False, True])
def test_cancellation_reaps_worker_preserves_evidence_and_records_interruption(
    process_root: Path, monkeypatch: pytest.MonkeyPatch, descendant: bool
) -> None:
    from kotekomi_pipelines.replay_reader import ingestion_worker as ingestion_process

    if descendant and os.name != "posix":
        pytest.skip("POSIX process groups are required for this descendant assertion.")
    monkeypatch.setattr(
        ingestion_process,
        "run_ingestion_worker",
        worker_with_descendant if descendant else blocked_worker,
    )
    process = controller(process_root)
    archived = {
        path: path.read_bytes() for path in (process_root / "archive").rglob("*") if path.is_file()
    }
    ready = Event()
    results: list[int] = []
    failures: list[Exception] = []

    class Output(io.StringIO):
        def write(self, text: str) -> int:
            if text == "blocked\n":
                ready.set()
            return super().write(text)

    def run_controller() -> None:
        try:
            results.append(process.run(lambda snapshot: None, Output(), io.StringIO()))
        except Exception as error:
            failures.append(error)

    thread = Thread(target=run_controller)
    thread.start()
    try:
        assert ready.wait(5)
        started = monotonic()
        process.cancel()
        thread.join(timeout=2)
        assert not thread.is_alive()
        assert monotonic() - started < 2
        assert failures == []
        assert results == [130]
        assert process.process is None
        with sqlite_ledger_transaction(process_root / "kotekomi.db") as ledger:
            run = ledger.get_ingestion_run(process.request.ingestion_run_id)
            assert run is not None and run.status is IngestionRunStatus.ERROR
            assert run.failure_stage is IngestionFailureStage.INTERRUPTION
            assert run.failure_code is IngestionFailureCode.USER_INTERRUPTED
            assert run.completed_at is not None
            assert (
                ledger.get_ingestion_run(process.request.ingestion_run_id + "_uncommitted") is None
            )
        assert all(path.read_bytes() == payload for path, payload in archived.items())
        if descendant:
            pid = (process_root / "descendant-pid").read_text()
            state = subprocess.run(
                ["ps", "-o", "stat=", "-p", pid], capture_output=True, text=True, check=False
            ).stdout.strip()
            assert not state or state.startswith("Z")  # Stopped; its new parent owns reaping.
    finally:
        process.cancel()
        thread.join(timeout=2)


def test_cancel_before_process_start_creates_no_run(process_root: Path) -> None:
    process = controller(process_root)
    process.cancel()
    assert process.run(lambda snapshot: None, io.StringIO(), io.StringIO()) == 130
    with sqlite_ledger_transaction(process_root / "kotekomi.db") as ledger:
        assert ledger.get_ingestion_run(process.request.ingestion_run_id) is None


def test_sync_tui_run_returns_to_caller_while_worker_was_blocked(
    process_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import asyncio

    from kotekomi_pipelines.replay_reader import ingestion_worker as ingestion_process

    monkeypatch.setattr(ingestion_process, "run_ingestion_worker", blocked_worker)
    process = controller(process_root)
    ready = Event()
    quit_times: list[float] = []

    class AppWithProgress(ReplayApp):
        def on_status_changed(self, event: StatusChanged) -> None:
            super().on_status_changed(event)
            if event.text == "blocked":
                ready.set()

    app = AppWithProgress(process.run, mode="ingestion", cancel=process.cancel)

    async def quit_when_started(pilot: Pilot[object]) -> None:
        assert await asyncio.to_thread(ready.wait, 5)
        quit_times.append(monotonic())
        await pilot.press("q")

    try:
        assert app.run(headless=True, auto_pilot=quit_when_started) == 130
    finally:
        process.cancel()
    assert monotonic() - quit_times[0] < 2
    assert process.process is None
    with sqlite_ledger_transaction(process_root / "kotekomi.db") as ledger:
        run = ledger.get_ingestion_run(process.request.ingestion_run_id)
        assert run is not None and run.failure_code is IngestionFailureCode.USER_INTERRUPTED


def test_process_channel_roundtrips_typed_phase_snapshot_and_exit_code(
    process_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from kotekomi_pipelines.replay_reader import ingestion_worker as ingestion_process

    monkeypatch.setattr(ingestion_process, "run_ingestion_worker", snapshot_worker)
    process = controller(process_root)
    snapshots: list[ParagraphSnapshot] = []
    out, err = io.StringIO(), io.StringIO()
    assert process.run(snapshots.append, out, err) == 7
    assert snapshots == [ParagraphSnapshot(0, 1, example_profile())]
    assert out.getvalue() == "fixture status\n"
    assert err.getvalue() == ""


def test_replay_quit_interrupts_a_long_delay_without_waiting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import asyncio

    from kotekomi_pipelines.replay_reader import live

    from packages.application.tests.test_hybrid_document_references import (
        _bundle,  # pyright: ignore[reportPrivateUsage]
        _parent_preview,  # pyright: ignore[reportPrivateUsage]
    )

    ready = Event()

    class DelayEvent(Event):
        def wait(self, timeout: float | None = None) -> bool:
            if timeout == 30:
                ready.set()
            return super().wait(timeout)

    bundle = _bundle(("Acme acted.",))
    preview = _parent_preview(bundle, paragraph_index=0, candidate_texts=("Acme",))
    paragraph = ParagraphInput(
        0,
        "Acme acted.",
        bundle.representation.id,
        preview.paragraph_node_id,
        0,
        "complete",
        (),
        {"hp1_mentions": preview},
        bundle,
    )
    quit_times: list[float] = []

    async def quit_during_delay(pilot: Pilot[object]) -> None:
        assert await asyncio.to_thread(ready.wait, 2)
        quit_times.append(monotonic())
        await pilot.press("q")

    original_run = ReplayApp.run

    def run(app: ReplayApp) -> int | None:
        return original_run(app, headless=True, auto_pilot=quit_during_delay)

    def is_interactive(stream: TextIO) -> bool:
        return True

    monkeypatch.setattr(live, "Event", DelayEvent)
    monkeypatch.setattr(live, "_is_interactive", is_interactive)
    monkeypatch.setattr(ReplayApp, "run", run)
    assert (
        live.replay_paragraphs(
            (paragraph,), None, plain=False, delay=30, ledger_path=Path("unused.db")
        )
        == 130
    )
    assert monotonic() - quit_times[0] < 2
