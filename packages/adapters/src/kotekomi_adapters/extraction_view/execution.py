"""Supervise fresh TUI ingestion without changing the ingestion use cases."""

from __future__ import annotations

import multiprocessing
import os
import signal
from collections.abc import Callable
from io import StringIO
from multiprocessing.connection import Connection
from multiprocessing.process import BaseProcess
from pathlib import Path
from threading import Event, Lock
from typing import TextIO

from kotekomi_application.ingestion_execution import (
    IngestionProcessRequest,
    ParagraphEvent,
    ProcessEvent,
    TextEvent,
)
from kotekomi_application.ingestion_inspection import ParagraphSnapshot
from kotekomi_application.ingestion_runs import Uuid4IngestionRunIdFactory
from pydantic import TypeAdapter

from kotekomi_adapters import SQLiteLedgerInitializer

INTERRUPTED_EXIT_CODE = 130
_FRAME_LIMIT = 16 * 1024 * 1024


_EVENT_ADAPTER: TypeAdapter[ProcessEvent] = TypeAdapter(ProcessEvent)


def send_event(connection: Connection, event: ProcessEvent) -> None:
    payload = _EVENT_ADAPTER.dump_json(event)
    if len(payload) > _FRAME_LIMIT:
        raise ValueError("Ingestion progress frame exceeds its size limit.")
    connection.send_bytes(payload)


class ProcessOutput(StringIO):
    def __init__(self, connection: Connection, *, is_error: bool = False) -> None:
        super().__init__()
        self.connection = connection
        self.is_error = is_error
        self.pending = ""

    def write(self, text: str) -> int:
        self.pending += text
        while "\n" in self.pending:
            line, self.pending = self.pending.split("\n", 1)
            if line:
                send_event(self.connection, TextEvent(text=line, is_error=self.is_error))
        return len(text)

    def flush(self) -> None:
        if self.pending:
            send_event(self.connection, TextEvent(text=self.pending, is_error=self.is_error))
            self.pending = ""


class IngestionProcess:
    def __init__(
        self,
        *,
        config_path: str,
        source_path: str,
        source_url: str,
        ledger_path: str,
        paragraph_ordinal: int | None,
        worker: Callable[[IngestionProcessRequest, Connection], None],
        on_stopped: Callable[[str, bool], None],
    ) -> None:
        self.worker = worker
        self.on_stopped = on_stopped
        self.request = IngestionProcessRequest(
            config_path=config_path,
            source_path=source_path,
            source_url=source_url,
            ledger_path=ledger_path,
            ingestion_run_id=Uuid4IngestionRunIdFactory().new_ingestion_run_id(),
            paragraph_ordinal=paragraph_ordinal,
        )
        self.cancelled = Event()
        self.lock = Lock()
        self.process: BaseProcess | None = None
        self.group_id: int | None = None

    def cancel(self) -> None:
        self.cancelled.set()
        with self.lock:
            # A model call cannot reliably handle a graceful interrupt. Stop the
            # entire owned group together before reaping its leader.
            self._signal(signal.SIGKILL)

    def _signal(self, sig: signal.Signals) -> None:
        process = self.process
        if process is None or process.pid is None:
            return
        if os.name == "posix":
            try:
                if self.group_id is None and os.getpgid(process.pid) == process.pid:
                    self.group_id = process.pid
                if self.group_id is not None:
                    os.killpg(self.group_id, sig)
                    return
            except ProcessLookupError:
                return
        if process.is_alive():
            if sig == signal.SIGTERM:
                process.terminate()
            else:
                process.kill()

    def run(self, publish: Callable[[ParagraphSnapshot], None], out: TextIO, err: TextIO) -> int:
        context = multiprocessing.get_context("spawn")
        receive, send = context.Pipe(duplex=False)
        process = context.Process(target=self.worker, args=(self.request, send))
        terminal_received = False
        reported_code: int | None = None
        try:
            SQLiteLedgerInitializer(Path(self.request.ledger_path)).initialize()
            with self.lock:
                if self.cancelled.is_set():
                    return INTERRUPTED_EXIT_CODE
                self.process = process
                process.start()
            send.close()
            while not self.cancelled.is_set():
                if not receive.poll(0.05):
                    if not process.is_alive():
                        raise RuntimeError("Ingestion worker exited without a terminal result.")
                    continue
                event = _EVENT_ADAPTER.validate_json(receive.recv_bytes(_FRAME_LIMIT))
                if isinstance(event, ParagraphEvent):
                    publish(event.snapshot)
                elif isinstance(event, TextEvent):
                    stream = err if event.is_error else out
                    stream.write(event.text + "\n")
                else:
                    terminal_received = True
                    reported_code = event.code
                    return event.code
            return INTERRUPTED_EXIT_CODE
        except (EOFError, OSError) as error:
            if not self.cancelled.is_set():
                raise RuntimeError(
                    "Ingestion worker progress channel closed unexpectedly."
                ) from error
            return INTERRUPTED_EXIT_CODE
        finally:
            # Bounded cleanup; an explicit cancel already stopped the whole group.
            with self.lock:
                if self.process is not None and process.pid is not None:
                    if not terminal_received and not self.cancelled.is_set():
                        self._signal(signal.SIGTERM)
                    process.join(timeout=0.25)
                    if process.is_alive():
                        self._signal(signal.SIGKILL)
                        process.join(timeout=0.25)
                    if process.is_alive():
                        raise RuntimeError("Unable to reap the ingestion worker.")
                    self.process = None
                    process.close()
            receive.close()
            send.close()
            if self.cancelled.is_set() or reported_code != 0:
                self.on_stopped(self.request.ingestion_run_id, self.cancelled.is_set())
