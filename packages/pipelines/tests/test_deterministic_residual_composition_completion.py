"""Focused tests for the R19 residual composition completion Pipeline."""

from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest
from kotekomi_application import (
    AssertionConstructionStatus,
    DeterministicResidualCompositionStatus,
    ReferencePolicyRecord,
    frozen_semantic_selection_contract,
    load_reference_policy_records,
)
from kotekomi_application.ports import LedgerRepository
from kotekomi_pipelines.deterministic_residual_composition_completion import (
    ResidualClosureRecord,
    ResidualTerminalStatus,
    build_deterministic_residual_composition_report,
    r17_selection_signal,
    verify_evidence_support,
)

ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = ROOT / "data/r17-semantic-selection-contract"

_SOURCE_ID = "src_d97195ee5c8ced32c0cd41b0"


class _Target:
    def __init__(self, source_id: str, exact_text: str, document_id: str) -> None:
        self.source_id = source_id
        self.exact_text = exact_text
        self.document_id = document_id


class _Document:
    def __init__(self, source_id: str, doc_id: str) -> None:
        self.id = doc_id
        self.source_id = source_id


class _FakeRepository:
    def __init__(
        self,
        *,
        source_id: str | None = _SOURCE_ID,
        target: _Target | None,
        document: _Document | None,
    ) -> None:
        self._source_id = source_id
        self._target = target
        self._document = document

    def get_source(self, record_id: str):
        if self._source_id is not None and record_id == self._source_id:
            return object()
        return None

    def get_evidence_target(self, record_id: str):
        return self._target

    def get_document(self, record_id: str):
        return self._document


def _repository(
    source_id: str | None, target: _Target | None, document: _Document | None
) -> LedgerRepository:
    return cast(
        LedgerRepository, _FakeRepository(source_id=source_id, target=target, document=document)
    )


@pytest.fixture(scope="module")
def policy_records() -> tuple[ReferencePolicyRecord, ...]:
    contract = frozen_semantic_selection_contract(directory=DATA_DIR)
    return load_reference_policy_records(contract=contract, directory=DATA_DIR)


def _ok_repository(text: str) -> LedgerRepository:
    target = _Target(_SOURCE_ID, text, "doc_eaaad11a475988142cad48d7")
    document = _Document(_SOURCE_ID, "doc_eaaad11a475988142cad48d7")
    return _repository(_SOURCE_ID, target, document)


def test_evidence_support_requires_document_and_exact_span() -> None:
    text = "[45] The April order is not final."
    assert verify_evidence_support(
        _ok_repository(text),
        source_id=_SOURCE_ID,
        evidence_target_id="etg_fixture",
        source_text=text,
    )


def test_evidence_support_rejects_wrong_exact_span() -> None:
    target = _Target(_SOURCE_ID, "different text", "doc_fixture")
    document = _Document(_SOURCE_ID, "doc_fixture")
    assert not verify_evidence_support(
        _repository(_SOURCE_ID, target, document),
        source_id=_SOURCE_ID,
        evidence_target_id="etg_fixture",
        source_text="[45] The April order is not final.",
    )


def test_evidence_support_rejects_wrong_source_relationship() -> None:
    target = _Target("src_other", "[45] The April order is not final.", "doc_fixture")
    document = _Document(_SOURCE_ID, "doc_fixture")
    assert not verify_evidence_support(
        _repository(_SOURCE_ID, target, document),
        source_id=_SOURCE_ID,
        evidence_target_id="etg_fixture",
        source_text="[45] The April order is not final.",
    )


def test_r17_selection_signal_separates_generated_from_reviewed(
    policy_records: tuple[ReferencePolicyRecord, ...],
) -> None:
    record = next(item for item in policy_records if item.event_id == "AHE-022")
    assert r17_selection_signal((1, 3), record) == "met"
    assert r17_selection_signal((1, 2, 3), record) == "unmet"


def test_report_seals_zero_writes_with_blocked_residual() -> None:
    record = ResidualClosureRecord(
        event_id="AHE-909",
        terminal_status=ResidualTerminalStatus.BLOCKED,
        r17_selection_signal="unmet",
        composition_status=DeterministicResidualCompositionStatus.COMPOSITION_HELD,
        assertion_status=AssertionConstructionStatus.BLOCKED,
        block_reason="subject_unavailable",
        evidence_supported=False,
    )
    report = build_deterministic_residual_composition_report(
        report_id="r19-fixture", residuals=(record,)
    )

    assert report.model_execution_count == 0
    assert report.canonical_write_count == 0
    assert report.proposed_change_count == 0
    assert report.result_fingerprint != "0" * 64
    assert len(report.result_fingerprint) == 64
