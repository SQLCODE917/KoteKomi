"""Idempotent replay dispatch coverage for ``kotekomi-live-replay``.

Verifies that the CLI replays persisted annotations when ``--state-root``
already holds a completed run instead of erroring or re-running ingestion, and
that a fresh root still falls through to ingestion.
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import TextIO

import pytest
from kotekomi_application.ingestion_inspection import (
    HybridParagraphProgress,
    HybridParagraphStageProgress,
    ParagraphInput,
)
from kotekomi_pipelines.replay_reader.live import create_inspection_session, main
from kotekomi_pipelines.replay_reader.transport import load_paragraph_inputs


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
    presenter = create_inspection_session(Path("unused.db"), stream=stream)
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


@pytest.mark.parametrize("delay", ["-1", "nan", "inf"])
def test_invalid_delay_is_rejected(delay: str) -> None:
    with pytest.raises(SystemExit) as excinfo:
        main(["--delay", delay])
    assert excinfo.value.code == 2


def test_presentation_error_preserves_last_valid_annotations() -> None:
    from kotekomi_application.ingestion_inspection import ParagraphSnapshot

    from packages.application.tests.test_hybrid_document_references import (
        _bundle,  # pyright: ignore[reportPrivateUsage]
        _parent_preview,  # pyright: ignore[reportPrivateUsage]
    )

    text = "Acme acted."
    bundle = _bundle((text,))
    parent = _parent_preview(bundle, paragraph_index=0, candidate_texts=("Acme",))
    node = next(item for item in bundle.nodes if item.id == parent.paragraph_node_id)
    snapshots: list[ParagraphSnapshot] = []
    presenter = create_inspection_session(Path("unused.db"), on_snapshot=snapshots.append)
    paragraph = ParagraphInput(
        0,
        text,
        bundle.representation.id,
        node.id,
        node.start_char,
        "complete",
        (),
        {"hp1_mentions": parent, "hp3_grounding": object()},
        bundle,
    )
    presenter.replay_stored((paragraph,), None)
    assert presenter.presentation_failed
    assert (
        snapshots[-1].error
        == "Presentation error: hp3_grounding output is not a HybridEntityGroundingPreview."
    )
    assert snapshots[-1].profile.mentions[0].span.text == "Acme"
    assert snapshots[-1].profile.present_stages == frozenset({"hp1_mentions"})


@pytest.mark.parametrize(
    "interactive,plain,expected_tui",
    [(True, False, True), (True, True, False), (False, False, False)],
)
def test_both_stored_commands_share_output_selection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    interactive: bool,
    plain: bool,
    expected_tui: bool,
) -> None:
    from kotekomi_adapters.extraction_view.tui import ReplayApp
    from kotekomi_pipelines.replay_reader import live, transport

    (tmp_path / "kotekomi.db").touch()
    (tmp_path / "archive").mkdir()
    paragraphs = (ParagraphInput(0, "Source text.", "rep_1", "node_1", 0, "complete", (), {}),)
    calls: list[ReplayApp] = []

    def load(
        ledger_path: Path, archive_path: Path, *, ingestion_run_id: str | None = None
    ) -> tuple[ParagraphInput, ...]:
        return paragraphs

    def run(app: ReplayApp) -> int:
        assert app.mode == "replay"
        calls.append(app)
        return 0

    def is_interactive(stream: TextIO) -> bool:
        return interactive

    monkeypatch.setattr(live, "_is_interactive", is_interactive)
    monkeypatch.setattr(live, "load_paragraph_inputs", load)
    monkeypatch.setattr(transport, "load_paragraph_inputs", load)
    monkeypatch.setattr(ReplayApp, "run", run)
    args = ["--state-root", str(tmp_path)] + (["--plain"] if plain else [])
    assert live.main(args) == transport.main(args) == 0
    assert len(calls) == (2 if expected_tui else 0)
    output = capsys.readouterr().out
    assert ("Source text." in output) == (not expected_tui)
    assert "\033" not in output


@pytest.fixture
def multiple_ingestion_root(tmp_path: Path) -> Path:
    """Two distinct, current-schema coverage reports in a real Ledger and Archive."""
    from kotekomi_pipelines.cli import ingest_user_file

    config = tmp_path / "kotekomi.toml"
    config.write_text(
        f'ledger_path = "{tmp_path}/kotekomi.db"\n'
        f'archive_path = "{tmp_path}/archive"\nruntime_profile = "fixture"\n'
        '[processing]\nrepresentation_policy_version = "deposited-source-v1"\n'
    )
    for name in ("first", "second"):
        source = tmp_path / f"{name}.md"
        source.write_text(f"# {name}\n\nAcme acted.\n")
        assert (
            ingest_user_file(
                config_path=config,
                source_file_path=source,
                source_url=f"https://example.test/{name}",
                stdout=io.StringIO(),
                stderr=io.StringIO(),
            )
            == 0
        )
    reports = tuple((tmp_path / "archive/extraction/document-coverage").glob("*.json"))
    assert len(reports) == 2
    return tmp_path


@pytest.mark.parametrize("older", [False, True])
def test_multiple_reports_resolve_through_selected_ingestion_run(
    multiple_ingestion_root: Path, monkeypatch: pytest.MonkeyPatch, older: bool
) -> None:
    from kotekomi_adapters import LocalArchiveStore, sqlite_ledger_transaction

    root = multiple_ingestion_root
    with sqlite_ledger_transaction(root / "kotekomi.db") as ledger:
        runs = ledger.list_ingestion_runs()
        selected = runs[1 if older else 0]
        assert selected.ingestion_change_set_id is not None
        change_set = ledger.get_ingestion_change_set(selected.ingestion_change_set_id)
        assert change_set is not None
        report_id = LocalArchiveStore(
            root / "archive"
        ).find_hybrid_document_coverage_report_by_sha256(change_set.coverage_report_digest)
    reads: list[str] = []
    read_report = LocalArchiveStore.read_hybrid_document_coverage_report

    def read(archive: LocalArchiveStore, record_id: str) -> bytes:
        reads.append(record_id)
        return read_report(archive, record_id)

    monkeypatch.setattr(LocalArchiveStore, "read_hybrid_document_coverage_report", read)
    inputs = load_paragraph_inputs(
        root / "kotekomi.db",
        root / "archive",
        ingestion_run_id=selected.id if older else None,
    )
    assert inputs == ()  # Markdown ingestion has no Hybrid paragraph scope.
    assert reads and set(reads) == {report_id}


@pytest.mark.parametrize("command", ["replay", "live-replay"])
def test_invalid_selected_evidence_is_a_clean_cli_error_without_older_fallback(
    multiple_ingestion_root: Path, capsys: pytest.CaptureFixture[str], command: str
) -> None:
    from kotekomi_adapters import LocalArchiveStore, sqlite_ledger_transaction
    from kotekomi_pipelines.replay_reader import live, transport

    root = multiple_ingestion_root
    with sqlite_ledger_transaction(root / "kotekomi.db") as ledger:
        selected = ledger.list_ingestion_runs()[0]
        assert selected.ingestion_change_set_id is not None
        change_set = ledger.get_ingestion_change_set(selected.ingestion_change_set_id)
        assert change_set is not None
        report_id = LocalArchiveStore(
            root / "archive"
        ).find_hybrid_document_coverage_report_by_sha256(change_set.coverage_report_digest)
    report_path = root / f"archive/extraction/document-coverage/{report_id}.json"
    report_path.write_bytes(report_path.read_bytes() + b" ")  # Negative fixture: wrong digest.
    run = transport.main if command == "replay" else live.main
    with pytest.raises(SystemExit) as error:
        run(["--state-root", str(root), "--plain"])
    message = capsys.readouterr().err + str(error.value)
    assert "cannot replay" in message
    assert selected.id in message
    assert "coverage report is missing" in message
    assert "Traceback" not in message


@pytest.mark.parametrize("command", ["replay", "live-replay"])
def test_explicit_missing_run_is_a_clean_cli_error(
    multiple_ingestion_root: Path, capsys: pytest.CaptureFixture[str], command: str
) -> None:
    from kotekomi_pipelines.replay_reader import live, transport

    run = transport.main if command == "replay" else live.main
    with pytest.raises(SystemExit) as error:
        run(
            [
                "--state-root",
                str(multiple_ingestion_root),
                "--ingestion-run",
                "igr_missing",
                "--plain",
            ]
        )
    message = capsys.readouterr().err + str(error.value)
    assert "IngestionRun not found: igr_missing" in message
    assert "Traceback" not in message


def test_ingestion_run_selection_requires_existing_state(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as error:
        main(["--state-root", str(tmp_path / "missing"), "--ingestion-run", "igr_selected"])
    assert error.value.code == 2
    assert "--ingestion-run requires an existing --state-root" in capsys.readouterr().err


def test_injected_ingestion_streams_keep_failure_output_off_global_stdout(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from kotekomi_pipelines.cli import ingest_user_file

    config = tmp_path / "kotekomi.toml"
    config.write_text(
        f'ledger_path = "{tmp_path}/state.db"\n'
        f'archive_path = "{tmp_path}/archive"\nruntime_profile = "fixture"\n'
        '[processing]\nrepresentation_policy_version = "deposited-source-v1"\n'
    )
    out, err = io.StringIO(), io.StringIO()
    code = ingest_user_file(
        config_path=config,
        source_file_path=tmp_path / "missing.txt",
        source_url="https://example.test/source",
        stdout=out,
        stderr=err,
    )
    assert code == 1
    assert out.getvalue().startswith("Ingestion run: igr_")
    assert "not found" in err.getvalue()
    assert capsys.readouterr() == ("", "")


def test_fresh_tui_keeps_mode_when_textual_captures_stdout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from collections.abc import Callable, Generator
    from contextlib import contextmanager, redirect_stdout

    from kotekomi_adapters.extraction_view.tui import (
        MessageStream,
        ReplayApp,
        StatusChanged,
    )
    from kotekomi_application import HybridStageId
    from kotekomi_application.ingestion_inspection import ParagraphSnapshot
    from kotekomi_domain import DocumentRepresentationBundle
    from kotekomi_pipelines.replay_reader import live
    from textual.message import Message

    from packages.application.tests.test_hybrid_document_references import (
        _bundle,  # pyright: ignore[reportPrivateUsage]
        _parent_preview,  # pyright: ignore[reportPrivateUsage]
    )

    bundle = _bundle(("Acme acted.",))
    parent = _parent_preview(bundle, paragraph_index=0, candidate_texts=("Acme",))
    snapshots: list[ParagraphSnapshot] = []
    messages: list[Message] = []

    class BundleLedger:
        def get_document_representation_bundle(
            self, record_id: str
        ) -> DocumentRepresentationBundle:
            assert record_id == bundle.representation.id
            return bundle

    @contextmanager
    def transaction(path: Path) -> Generator[BundleLedger, None, None]:
        yield BundleLedger()

    def is_interactive(stream: TextIO) -> bool:
        return not isinstance(stream, io.StringIO)

    def fake_ingest(
        *,
        config_path: Path,
        source_file_path: Path,
        source_url: str,
        stage_progress: Callable[[HybridParagraphStageProgress], None],
        paragraph_progress: Callable[[HybridParagraphProgress], None],
        stdout: TextIO,
        stderr: TextIO,
    ) -> int:
        stdout.write("Ingestion run: igr_fixture\n")
        stage_progress(
            HybridParagraphStageProgress(
                0, 1, bundle.representation.id, parent.paragraph_node_id, None, None, False
            )
        )
        stage_progress(
            HybridParagraphStageProgress(
                0,
                1,
                bundle.representation.id,
                parent.paragraph_node_id,
                HybridStageId.HP1_MENTIONS,
                parent,
                False,
            )
        )
        paragraph_progress(HybridParagraphProgress(0, 1, "complete", False))
        return 0

    def post(message: Message) -> bool:
        messages.append(message)
        return True

    class InlineProcess:
        def __init__(
            self,
            *,
            config_path: str,
            source_path: str,
            source_url: str,
            ledger_path: str,
            paragraph_ordinal: int | None,
            worker: object,
            on_stopped: object,
        ) -> None:
            self.config_path = Path(config_path)
            self.source_path = Path(source_path)
            self.source_url = source_url
            self.ledger_path = Path(ledger_path)

        def cancel(self) -> None:
            raise AssertionError("This completed fixture must not be cancelled.")

        def run(
            self, publish: Callable[[ParagraphSnapshot], None], out: TextIO, err: TextIO
        ) -> int:
            from kotekomi_application.inspection_session import InspectionSession

            presenter = InspectionSession(BundleLedger(), on_snapshot=publish)
            return fake_ingest(
                config_path=self.config_path,
                source_file_path=self.source_path,
                source_url=self.source_url,
                stage_progress=presenter.on_stage_progress,
                paragraph_progress=presenter.on_paragraph_progress,
                stdout=out,
                stderr=err,
            )

    def run(app: ReplayApp) -> int:
        assert app.mode == "ingestion"
        with redirect_stdout(io.StringIO()):
            return app.operation(
                snapshots.append, MessageStream(post), MessageStream(post, is_error=True)
            )

    monkeypatch.setattr(live, "_is_interactive", is_interactive)
    monkeypatch.setattr(live, "sqlite_ledger_transaction", transaction)
    monkeypatch.setattr(live, "ingest_user_file", fake_ingest)
    monkeypatch.setattr(live, "IngestionProcess", InlineProcess)
    monkeypatch.setattr(ReplayApp, "run", run)
    config = tmp_path / "source.toml"
    config.write_text(
        f'ledger_path = "{tmp_path}/original.db"\n'
        f'archive_path = "{tmp_path}/original-archive"\n'
        'runtime_profile = "fixture"\n'
    )
    assert (
        live.main(
            [
                "--config",
                str(config),
                "--source",
                str(tmp_path / "source.md"),
                "--url",
                "https://example.test/source",
                "--state-root",
                str(tmp_path / "new-state"),
            ]
        )
        == 0
    )
    assert snapshots[-1].profile.mentions[0].span.text == "Acme"
    assert [message.text for message in messages if isinstance(message, StatusChanged)] == [
        "Ingestion run: igr_fixture"
    ]


@pytest.fixture
def paragraph_cli_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Path, ParagraphInput]:
    from collections.abc import Generator
    from contextlib import contextmanager
    from typing import cast

    from kotekomi_application.ingestion_inspection_reader import (
        InspectionLedger,
        InspectParagraphInput,
        load_inspection_paragraph,
    )
    from kotekomi_application.ingestion_observability import IngestionObservabilityArchive
    from kotekomi_pipelines import cli

    from packages.application.tests.test_ingestion_inspection import ScopedLedger, closed_fixture

    ledger, archive = closed_fixture()

    @contextmanager
    def transaction(path: Path) -> Generator[ScopedLedger, None, None]:
        assert path == tmp_path / "kotekomi.db"
        yield ledger

    def archive_store(path: Path) -> IngestionObservabilityArchive:
        assert path == tmp_path / "archive"
        return cast(IngestionObservabilityArchive, archive)

    monkeypatch.setattr(cli, "sqlite_ledger_transaction", transaction)
    monkeypatch.setattr(cli, "LocalArchiveStore", archive_store)
    (tmp_path / "kotekomi.toml").write_text(
        f'ledger_path = "{tmp_path}/kotekomi.db"\narchive_path = "{tmp_path}/archive"\n'
        '[processing]\nrepresentation_policy_version = "deposited-source-v1"\n'
    )
    paragraph = load_inspection_paragraph(
        InspectParagraphInput(
            ingestion_run_id=ledger.run.id, paragraph_node_id="nod_first", state_root=str(tmp_path)
        ),
        cast(InspectionLedger, ledger),
        cast(IngestionObservabilityArchive, archive),
    )
    return tmp_path, paragraph


def test_paragraph_cli_returns_compact_summary_and_typed_phase(
    paragraph_cli_root: tuple[Path, ParagraphInput], capsys: pytest.CaptureFixture[str]
) -> None:
    import json

    from kotekomi_application.ingestion_debug_summary import DebugSummary
    from kotekomi_pipelines.cli import main as cli_main

    root, paragraph = paragraph_cli_root
    assert paragraph.context
    arguments = [
        "--config",
        str(root / "kotekomi.toml"),
        "ingestions",
        "paragraph",
        paragraph.context.ingestion_run_id,
        "--node",
        paragraph.paragraph_node_id,
        "--format",
        "json",
    ]
    assert cli_main(arguments) == 0
    output = capsys.readouterr()
    summary = DebugSummary.model_validate_json(output.out)
    assert summary.source.text == paragraph.text and summary.context == paragraph.context
    assert output.err == ""
    assert cli_main(arguments + ["--phase", "hp1_mentions"]) == 0
    phase = json.loads(capsys.readouterr().out)
    assert phase["binding"] == "receipt"
    assert phase["evidence"]["id"] == next(
        a.output_id for a in paragraph.artifacts if a.stage == "hp1_mentions"
    )
    assert cli_main(arguments + ["--phase", "hp1_mentions", "--record-id", "missing"]) == 1
    output = capsys.readouterr()
    assert output.out == "" and "does not belong" in output.err


def test_paragraph_cli_rejects_unscoped_selector_cleanly(
    paragraph_cli_root: tuple[Path, ParagraphInput], capsys: pytest.CaptureFixture[str]
) -> None:
    from kotekomi_pipelines.cli import main as cli_main

    root, paragraph = paragraph_cli_root
    assert paragraph.context
    assert (
        cli_main(
            [
                "--config",
                str(root / "kotekomi.toml"),
                "ingestions",
                "paragraph",
                paragraph.context.ingestion_run_id,
                "--node",
                paragraph.paragraph_node_id,
                "--trace-id",
                "missing",
            ]
        )
        == 1
    )
    output = capsys.readouterr()
    assert output.out == "" and "require --phase" in output.err
