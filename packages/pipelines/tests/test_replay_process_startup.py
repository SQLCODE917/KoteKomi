"""Cold-start the interactive worker without earlier multiprocessing calls."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def test_first_spawn_inside_textual_completes(tmp_path: Path) -> None:
    script = tmp_path / "cold_start.py"
    script.write_text(
        """\
import sys
from pathlib import Path

from kotekomi_adapters.extraction_view.execution import IngestionProcess, send_event
from kotekomi_adapters.extraction_view.tui import ReplayApp
from kotekomi_application.ingestion_execution import FinishedEvent


def worker(request, connection):
    send_event(connection, FinishedEvent(code=0))
    connection.close()


if __name__ == "__main__":
    root = Path(sys.argv[1])
    process = IngestionProcess(
        config_path=str(root / "kotekomi.toml"),
        source_path=str(root / "source.pdf"),
        source_url="https://example.test/source",
        ledger_path=str(root / "kotekomi.db"),
        paragraph_ordinal=None,
        worker=worker,
        on_stopped=lambda run_id, interrupted: None,
    )
    app = ReplayApp(process.run, mode="ingestion", cancel=process.cancel)

    async def finish(pilot):
        for _ in range(100):
            if app.finished:
                break
            await pilot.pause(0.05)
        assert app.finished, "worker failed to finish"
        assert app.operation_code == 0, str(app._status_lines)
        await pilot.press("q")

    assert app.run(headless=True, auto_pilot=finish) == 0
    assert process.process is None
    print("cold-start passed")
""",
        encoding="utf-8",
    )
    result = subprocess.run(
        [sys.executable, str(script), str(tmp_path)],
        env={**os.environ, "TERM": "xterm-256color"},
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "cold-start passed" in result.stdout
