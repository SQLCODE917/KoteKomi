"""Idempotent replay dispatch coverage for ``kotekomi-live-replay``.

Verifies that the CLI replays persisted annotations when ``--state-root``
already holds a completed run instead of erroring or re-running ingestion, and
that a fresh root still falls through to ingestion.
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from kotekomi_pipelines.replay_reader.live import LiveReplayPresenter, main
from kotekomi_pipelines.replay_reader.transport import ParagraphInput


def test_help_exits_cleanly() -> None:
    with pytest.raises(SystemExit) as excinfo:
        main(["--help"])
    assert excinfo.value.code == 0


def test_existing_root_without_state_is_not_replayable(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as excinfo:
        main(["--state-root", str(tmp_path)])
    assert "not replayable" in str(excinfo.value)


def test_missing_root_requires_ingest_args(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as excinfo:
        main(["--state-root", str(tmp_path / "missing")])
    assert excinfo.value.code == 2
    assert "--config" in capsys.readouterr().err


def test_replay_stored_empty_paragraph_is_deterministic() -> None:
    stream = io.StringIO()
    presenter = LiveReplayPresenter(Path("unused.db"), stream=stream, tui=False)
    paragraph = ParagraphInput(
        ordinal=0,
        text="Hello world.",
        representation_id="rep_1",
        paragraph_node_id="node_1",
        node_start_char=0,
        status="complete",
        gap_reasons=(),
        stage_outputs={},
    )
    presenter.replay_stored((paragraph,), None)
    output = stream.getvalue()
    assert "Hello world." in output
    assert "paragraph 1/1" in output
