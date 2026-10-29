"""Focused tests for the R19 residual composition completion Pipeline."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
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
from kotekomi_application.evidence_targets import EvidenceTargetLedger
from kotekomi_domain import (
    Document,
    DocumentNode,
    DocumentRepresentation,
    DocumentRepresentationBundle,
    EvidenceTarget,
    ParseQualityReport,
    RepresentationAnalyzability,
    TextView,
    TextViewKind,
    canonical_representation_digest,
)
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
_DOC_ID = "doc_eaaad11a475988142cad48d7"
_REP_ID = "rep_r19"
_TVW_ID = "tvw_r19"
_NOD_ID = "nod_r19"
_NOW = datetime(2026, 1, 1, tzinfo=UTC)
_AHE_051_TEXT = "[45] The April order is not final."


class _EvidenceRepository:
    def __init__(
        self,
        target: EvidenceTarget | None,
        bundle: DocumentRepresentationBundle | None,
        document: Document | None,
    ) -> None:
        self._target = target
        self._bundle = bundle
        self._document = document

    def get_evidence_target(self, record_id: str):
        return self._target

    def get_document_representation_bundle(self, record_id: str):
        return self._bundle

    def get_document(self, record_id: str):
        return self._document


def _repository(
    target: EvidenceTarget | None,
    bundle: DocumentRepresentationBundle | None,
    document: Document | None,
) -> EvidenceTargetLedger:
    return cast(
        EvidenceTargetLedger,
        _EvidenceRepository(target=target, bundle=bundle, document=document),
    )


def _bundle(text: str) -> DocumentRepresentationBundle:
    text_view = TextView(
        id=_TVW_ID,
        representation_id=_REP_ID,
        kind=TextViewKind.LOGICAL,
        content_digest=hashlib.sha256(text.encode()).hexdigest(),
        text=text,
        normalization_policy="utf8_identity_v1",
    )
    node = DocumentNode(
        id=_NOD_ID,
        representation_id=_REP_ID,
        node_type="document",
        order_index=0,
        text_view_id=_TVW_ID,
        start_char=0,
        end_char=len(text),
    )
    quality_report = ParseQualityReport(
        id="pqr_r19",
        representation_id=_REP_ID,
        metric_values={"text_char_count": len(text)},
        analyzability=RepresentationAnalyzability.ACCEPTABLE,
    )
    template = DocumentRepresentation(
        id=_REP_ID,
        document_id=_DOC_ID,
        parser_name="test",
        parser_version="1",
        parser_config_digest="a" * 64,
        processing_task_fingerprint_id="ptf_fixture",
        input_blob_digest="b" * 64,
        canonical_output_digest="0" * 64,
        created_at=_NOW,
    )
    representation = template.model_copy(
        update={
            "canonical_output_digest": canonical_representation_digest(
                template,
                text_views=(text_view,),
                nodes=(node,),
                edges=(),
                source_regions=(),
                quality_report=quality_report,
            )
        }
    )
    return DocumentRepresentationBundle(
        representation=representation,
        text_views=(text_view,),
        nodes=(node,),
        quality_report=quality_report,
    )


def _target(text: str, *, start: int, end: int) -> EvidenceTarget:
    return EvidenceTarget(
        id="etg_r19",
        source_id=_SOURCE_ID,
        document_id=_DOC_ID,
        representation_id=_REP_ID,
        text_view_id=_TVW_ID,
        text_view_digest=hashlib.sha256(text.encode()).hexdigest(),
        start_char=start,
        end_char=end,
        exact_text=text,
        prefix_text="",
        suffix_text="",
        node_ids=(_NOD_ID,),
        normalization_policy="utf8_identity_v1",
    )


def _document() -> Document:
    return Document(id=_DOC_ID, source_id=_SOURCE_ID, content_sha256="c" * 64)


@pytest.fixture(scope="module")
def policy_records() -> tuple[ReferencePolicyRecord, ...]:
    contract = frozen_semantic_selection_contract(directory=DATA_DIR)
    return load_reference_policy_records(contract=contract, directory=DATA_DIR)


def test_evidence_support_replays_archived_span() -> None:
    text = _AHE_051_TEXT
    assert verify_evidence_support(
        _repository(_target(text, start=0, end=len(text)), _bundle(text), _document()),
        source_id=_SOURCE_ID,
        evidence_target_id="etg_r19",
        source_text=text,
    )


def test_evidence_support_rejects_correct_text_with_wrong_coordinates() -> None:
    text = _AHE_051_TEXT
    assert not verify_evidence_support(
        _repository(_target(text, start=0, end=len(text) - 1), _bundle(text), _document()),
        source_id=_SOURCE_ID,
        evidence_target_id="etg_r19",
        source_text=text,
    )


def test_evidence_support_rejects_wrong_exact_span() -> None:
    text = _AHE_051_TEXT
    assert not verify_evidence_support(
        _repository(_target("different text", start=0, end=13), _bundle(text), _document()),
        source_id=_SOURCE_ID,
        evidence_target_id="etg_r19",
        source_text=text,
    )


def test_evidence_support_rejects_wrong_source_relationship() -> None:
    text = _AHE_051_TEXT
    target = _target(text, start=0, end=len(text)).model_copy(update={"source_id": "src_other"})
    assert not verify_evidence_support(
        _repository(target, _bundle(text), _document()),
        source_id=_SOURCE_ID,
        evidence_target_id="etg_r19",
        source_text=text,
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


def test_closed_record_rejects_unmet_selection() -> None:
    from pydantic import ValidationError

    text = _AHE_051_TEXT
    target = _target(text, start=0, end=len(text))
    evidence = verify_evidence_support(
        _repository(target, _bundle(text), _document()),
        source_id=_SOURCE_ID,
        evidence_target_id="etg_r19",
        source_text=text,
    )
    assert evidence
    with pytest.raises(ValidationError, match="selection signal met"):
        ResidualClosureRecord(
            event_id="AHE-051",
            terminal_status=ResidualTerminalStatus.CLOSED,
            r17_selection_signal="unmet",
            composition_status=DeterministicResidualCompositionStatus.COMPOSED,
            assertion_status=AssertionConstructionStatus.CONSTRUCTED,
            evidence_supported=True,
        )
