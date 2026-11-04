"""ISC-01: every fresh-ingestion interface persists the same composition outcomes.

The deterministic fixtures supply analyzer and model output only.
Ingestion, composition, persistence, and replay run through production code.
"""

# pyright: reportPrivateUsage=false

from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path
from typing import Any, cast

import pytest
from kotekomi_adapters.composition_outcome_store import CompositionOutcomeStore
from kotekomi_application import (
    LinguisticAnalysis,
    LinguisticAnalysisInput,
    LinguisticToken,
    UniversalPartOfSpeech,
)
from kotekomi_application.ingestion_execution import IngestionProcessRequest
from kotekomi_application.ingestion_inspection import ParagraphSnapshot
from kotekomi_application.source_occurrences import source_occurrences
from kotekomi_pipelines import cli
from kotekomi_pipelines.hybrid_document_ingestion import _FixtureLinguisticAnalyzer
from kotekomi_pipelines.replay_reader import live
from kotekomi_pipelines.replay_reader.ingestion_worker import run_ingestion_worker
from kotekomi_pipelines.replay_reader.transport import load_paragraph_inputs

PDF_FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "adapters"
    / "tests"
    / "fixtures"
    / "pdf"
    / "2025-community-health-improvement-plan-press-release.pdf"
)
SOURCE_URL = "https://example.test/pdf"
VERB = "share"
SUBJECT = "HealthyJoCo"
OBJECT = "Plan"


class _ChosenAnalyzer:
    """Deterministic analyzer: one verb root with a subject and an object."""

    def __init__(self) -> None:
        self._fallback = _FixtureLinguisticAnalyzer()

    def analyze(self, request: LinguisticAnalysisInput) -> LinguisticAnalysis:
        occurrences = source_occurrences(request.source_text)
        texts = {occurrence.text for occurrence in occurrences}
        if VERB not in texts or SUBJECT not in texts:
            return self._fallback.analyze(request)
        verb_id = next(
            f"t{index}"
            for index, occurrence in enumerate(occurrences, start=1)
            if occurrence.text == VERB
        )
        tokens: list[LinguisticToken] = []
        for index, occurrence in enumerate(occurrences, start=1):
            token_id = f"t{index}"
            if token_id == verb_id:
                part, relation, head = UniversalPartOfSpeech.VERB, "root", None
            elif occurrence.text == SUBJECT:
                part, relation, head = UniversalPartOfSpeech.PROPER_NOUN, "nsubj", verb_id
            elif occurrence.text == OBJECT:
                part, relation, head = UniversalPartOfSpeech.PROPER_NOUN, "obj", verb_id
            else:
                part, relation, head = UniversalPartOfSpeech.PROPER_NOUN, "dep", verb_id
            tokens.append(
                LinguisticToken(
                    token_id=token_id,
                    sentence_id="s1",
                    text=occurrence.text,
                    start=occurrence.start,
                    end=occurrence.end,
                    lemma=occurrence.text.casefold(),
                    part_of_speech=part,
                    dependency_relation=relation,
                    head_token_id=head,
                )
            )
        return LinguisticAnalysis(
            source_text_sha256=hashlib.sha256(request.source_text.encode()).hexdigest(),
            producer_id="isc01-analyzer",
            model_id="isc01-analyzer-model",
            model_version="1",
            resource_identity="e" * 64,
            tokens=tuple(tokens),
        )


def _install_fixtures(monkeypatch: pytest.MonkeyPatch) -> None:
    from kotekomi_application import ModelTaskResponse
    from kotekomi_pipelines.hybrid_document_ingestion import _RuntimeResources
    from kotekomi_pipelines.model_runtime import FixtureModelTaskRuntime

    analyzer = _ChosenAnalyzer()
    monkeypatch.setattr(_RuntimeResources, "linguistic_analyzer", property(lambda self: analyzer))
    original = FixtureModelTaskRuntime.run_model_task

    def patched(self: Any, task: Any) -> ModelTaskResponse:
        response = original(self, task)
        schema = task.execution_spec.schema_id
        rendered = task.rendered_input
        chosen: bytes | None = None
        if schema == "event_verb_role_text_v1" and VERB.encode() in rendered:
            chosen = b"E"
        elif schema == "event_binary_semantic_text_v1" and b"standing similarity" in rendered:
            chosen = b"N"
        elif schema == "event_binary_semantic_text_v1":
            chosen = b"Y"
        if chosen is None:
            return response
        return ModelTaskResponse(raw_output=chosen, execution_receipt=response.execution_receipt)

    monkeypatch.setattr(FixtureModelTaskRuntime, "run_model_task", patched)


def _config(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    config_path = root / "kotekomi.toml"
    config_path.write_text(
        f'ledger_path = "{(root / "state" / "kotekomi.db").as_posix()}"\n'
        f'archive_path = "{(root / "state" / "archive").as_posix()}"\n'
        'runtime_profile = "fixture"\n'
        "[processing]\n"
        'representation_policy_version = "deposited-source-v1"\n',
        encoding="utf-8",
    )
    return config_path


class _RecordingConnection:
    """Transport stand-in that records the worker's event frames."""

    def __init__(self) -> None:
        self.frames: list[bytes] = []

    def send_bytes(self, payload: bytes) -> None:
        self.frames.append(payload)

    def close(self) -> None:
        return None

    def code(self) -> int:
        for frame in self.frames:
            payload = json.loads(frame)
            if payload["kind"] == "finished":
                return int(payload["code"])
        raise AssertionError("the worker reported no terminal frame")

    def snapshots(self) -> list[ParagraphSnapshot]:
        from kotekomi_adapters.extraction_view.execution import _EVENT_ADAPTER
        from kotekomi_application.ingestion_execution import ParagraphEvent

        snapshots: list[ParagraphSnapshot] = []
        for frame in self.frames:
            event = _EVENT_ADAPTER.validate_json(frame)
            if isinstance(event, ParagraphEvent):
                snapshots.append(event.snapshot)
        return snapshots


def _run_cli(root: Path) -> int:
    return cli.main(
        ["--config", str(_config(root)), "ingest", str(PDF_FIXTURE), "--url", SOURCE_URL]
    )


def _run_plain_live(root: Path) -> int:
    return live.main(
        [
            "--config",
            str(_config(root)),
            "--source",
            str(PDF_FIXTURE),
            "--url",
            SOURCE_URL,
            "--state-root",
            str(root / "state"),
            "--plain",
        ]
    )


def _run_worker(root: Path, monkeypatch: pytest.MonkeyPatch) -> _RecordingConnection:
    state = root / "state"
    # Session setup belongs to the spawned worker; in-process it is a no-op shim.
    monkeypatch.setattr(os, "setsid", lambda: None)
    connection = _RecordingConnection()
    run_ingestion_worker(
        IngestionProcessRequest(
            config_path=str(_config(root)),
            source_path=str(PDF_FIXTURE),
            source_url=SOURCE_URL,
            ledger_path=str(state / "kotekomi.db"),
            ingestion_run_id="igr_isc01_worker",
            paragraph_ordinal=None,
        ),
        cast("Any", connection),
    )
    return connection


def _composition_outcomes(
    root: Path,
) -> list[tuple[str, str | None, str | None, str | None, str | None]]:
    """Return Event composition semantics without assigned IDs or timestamps."""
    outcomes_dir = root / "state" / "composition-outcomes"
    if not outcomes_dir.exists():
        return []
    outcomes = [
        (
            record.status.value,
            record.hold_reason,
            record.relation_label,
            record.subject_text,
            record.object_text,
        )
        for record in CompositionOutcomeStore(outcomes_dir).load_all()
    ]
    return sorted(outcomes, key=lambda item: tuple(str(part) for part in item))


def _extraction_outcomes(root: Path) -> list[tuple[str, tuple[str, ...]]]:
    """Return paragraph coverage and Event presence without assigned IDs."""
    paragraphs = load_paragraph_inputs(root / "state" / "kotekomi.db", root / "state" / "archive")
    return [
        (
            paragraph.status,
            tuple(sorted(event.trigger_label for event in _profile(paragraph).events)),
        )
        for paragraph in paragraphs
    ]


def _profile(paragraph: Any) -> Any:
    from kotekomi_application.ingestion_inspection import build_profile

    return build_profile(
        text=paragraph.text,
        representation_id=paragraph.representation_id,
        paragraph_node_id=paragraph.paragraph_node_id,
        node_start_char=paragraph.node_start_char,
        stage_outputs=paragraph.stage_outputs,
        bundle=paragraph.bundle,
    )


def test_ingestion_extraction_is_interface_independent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Characterization: extraction outcomes already match across interfaces."""
    _install_fixtures(monkeypatch)
    roots = {name: tmp_path / name for name in ("cli", "plain", "worker")}

    assert _run_cli(roots["cli"]) == 0
    assert _run_plain_live(roots["plain"]) == 0
    assert _run_worker(roots["worker"], monkeypatch).code() == 0

    baseline = _extraction_outcomes(roots["cli"])
    assert baseline
    assert _extraction_outcomes(roots["plain"]) == baseline
    assert _extraction_outcomes(roots["worker"]) == baseline


def test_all_fresh_interfaces_persist_the_same_composition_outcomes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ISC-01-A/B: presentation mode must not change persisted composition."""
    _install_fixtures(monkeypatch)
    roots = {name: tmp_path / name for name in ("cli", "plain", "worker")}

    assert _run_cli(roots["cli"]) == 0
    assert _run_plain_live(roots["plain"]) == 0
    assert _run_worker(roots["worker"], monkeypatch).code() == 0

    baseline = _composition_outcomes(roots["worker"])
    assert baseline, "the Textual worker already persists composition outcomes"
    assert _composition_outcomes(roots["cli"]) == baseline
    assert _composition_outcomes(roots["plain"]) == baseline


def test_live_session_receives_final_composition_outcomes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ISC-01-C: the live screen sees final outcomes without reopening replay."""
    _install_fixtures(monkeypatch)
    connection = _run_worker(tmp_path / "worker", monkeypatch)

    event_snapshots = [s for s in connection.snapshots() if s.profile.events]
    assert event_snapshots, "the chosen paragraph must realize an Event"
    latest = event_snapshots[-1]
    assert latest.profile.composition, (
        "the last published snapshot for an Event paragraph must carry composition outcomes"
    )
    statuses = {annotation.status for annotation in latest.profile.composition}
    assert statuses <= {"held", "composed"}


def test_stored_replay_starts_no_ingestion(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """ISC-01-D: stored replay stays read-only and starts no ingestion."""
    _install_fixtures(monkeypatch)
    root = tmp_path / "plain"
    assert _run_plain_live(root) == 0
    state = root / "state"
    before = sorted(path.name for path in state.iterdir())
    run_count = _ingestion_run_count(state / "kotekomi.db")

    assert live.main(["--state-root", str(state), "--plain"]) == 0

    assert sorted(path.name for path in state.iterdir()) == before
    assert _ingestion_run_count(state / "kotekomi.db") == run_count


def _ingestion_run_count(ledger_path: Path) -> int:
    from kotekomi_adapters import sqlite_ledger_transaction

    with sqlite_ledger_transaction(ledger_path) as repository:
        return len(repository.list_ingestion_runs())


def test_failure_reports_on_the_error_stream_only(tmp_path: Path) -> None:
    """Characterization: a missing source reports on the error stream."""
    out, err = io.StringIO(), io.StringIO()
    code = cli.ingest_user_file(
        config_path=_config(tmp_path),
        source_file_path=tmp_path / "missing.txt",
        source_url=SOURCE_URL,
        stdout=out,
        stderr=err,
    )
    assert code == 1
    assert "not found" in err.getvalue()
