"""The recomposition command writes to the path the operator supplies.

The command is a thin runner: this file replaces the Ledger transaction and the
recomposition use case, then checks the documented `--out` behavior.
"""

from __future__ import annotations

import importlib.util
import json
from contextlib import contextmanager
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from kotekomi_application import EventCompositionRecord, EventCompositionStatus

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "recompose_ingested_event.py"
_SHA = "a" * 64


def _script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("recompose_ingested_event", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _request(tmp_path: Path) -> Path:
    from kotekomi_application import (
        ConstituentCandidateInventory,
        ParserConstituent,
        SourceRange,
        parser_constituent_id,
    )
    from kotekomi_domain import AssertionType, AttributionBasis, SourceAuthority
    from kotekomi_pipelines.ingestion_composition_command import RecompositionRequest

    request = RecompositionRequest(
        event_id="AHE-001",
        source_text="Alpha support",
        source_text_sha256=_SHA,
        inventory=ConstituentCandidateInventory(
            event_id="AHE-001",
            source_text_sha256=_SHA,
            constituents=(
                ParserConstituent(
                    constituent_id=parser_constituent_id(_SHA, 0, 5),
                    event_id="AHE-001",
                    source_text_sha256=_SHA,
                    constituent_range=SourceRange(start=0, end=5, text="Alpha"),
                    token_ids=("t1",),
                ),
            ),
        ),
        trigger_head_start=0,
        trigger_head_end=1,
        tokens=(),
        representation_id="rep_1",
        text_view_id="view_1",
        predicate_by_label={"support": "supports"},
        identity_by_entity={},
        assertion_type=AssertionType.REPORTED_OBSERVATION,
        source_authority=SourceAuthority.SECONDARY,
        attribution_basis=AttributionBasis.DIRECT_DOCUMENT,
        source_id="src_1",
        evidence_target_id="etg_1",
    )
    path = tmp_path / "request.json"
    path.write_text(request.model_dump_json(), encoding="utf-8")
    return path


def _record() -> EventCompositionRecord:
    return EventCompositionRecord(
        event_id="AHE-001",
        source_text_sha256=_SHA,
        status=EventCompositionStatus.HELD,
        hold_reason="assertion_inputs_unavailable",
    )


def test_out_argument_selects_the_output_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _script()

    @contextmanager
    def transaction(_path: Path) -> Any:
        yield object()

    monkeypatch.setattr(module, "sqlite_ledger_transaction", transaction)

    def recompose(_request: Any, _repository: Any) -> EventCompositionRecord:
        return _record()

    monkeypatch.setattr(module, "run_recomposition", recompose)
    custom = tmp_path / "custom-report.json"

    code = module.main(
        [
            "--request",
            str(_request(tmp_path)),
            "--ledger",
            str(tmp_path / "kotekomi.db"),
            "--out",
            str(custom),
        ]
    )

    assert code == 0
    assert custom.is_file()
    assert not (tmp_path / "AHE-001.json").exists()
    assert json.loads(custom.read_text())["event_id"] == "AHE-001"


def test_default_output_lands_in_the_replay_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _script()

    @contextmanager
    def transaction(_path: Path) -> Any:
        yield object()

    monkeypatch.setattr(module, "sqlite_ledger_transaction", transaction)

    def recompose(_request: Any, _repository: Any) -> EventCompositionRecord:
        return _record()

    monkeypatch.setattr(module, "run_recomposition", recompose)

    code = module.main(
        [
            "--request",
            str(_request(tmp_path)),
            "--ledger",
            str(tmp_path / "state" / "kotekomi.db"),
        ]
    )

    assert code == 0
    assert (tmp_path / "state" / "composition-outcomes" / "AHE-001.json").is_file()
