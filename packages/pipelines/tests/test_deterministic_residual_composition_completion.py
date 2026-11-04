"""Focused tests for the R19 residual composition completion Pipeline."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import pytest
from kotekomi_application import (
    AssertionConstructionStatus,
    DecontextualizationExclusion,
    EventEntityReferences,
    ReferencePolicyRecord,
    SourceRange,
    frozen_semantic_selection_contract,
    load_reference_policy_records,
)
from kotekomi_application.deterministic_residual_composition_completion import (
    DeterministicResidualCompositionStatus,
)
from kotekomi_application.evidence_targets import EvidenceTargetLedger
from kotekomi_application.ports import LedgerRepository
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
    load_deterministic_residual_composition_report,
    r17_selection_signal,
    run_deterministic_residual_composition,
    verify_deterministic_residual_composition_report,
    verify_evidence_support,
)
from kotekomi_pipelines.r19_provider_supplement import (
    R19ProviderSupplement,
    SupplementEventBinding,
    SupplementEventEvidence,
    SupplementFileBinding,
    SupplementInputBinding,
    SupplementPredicateMapping,
    SupplementSubjectValueExclusion,
    SupplementTriggerSpan,
    load_r19_provider_supplement,
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


class _UnusedLedger:
    pass


def test_run_reports_gate_block_when_supplement_unapproved(
    policy_records: tuple[ReferencePolicyRecord, ...],
) -> None:
    supplement = load_r19_provider_supplement(
        ROOT / "docs" / "hsq-r19-provider-supplement-v1.json", repository_root=ROOT
    )
    proposed = supplement.model_copy(update={"review_status": "proposed"})
    unused = cast(LedgerRepository, _UnusedLedger())
    report = run_deterministic_residual_composition(
        report_id="r19-gate-fixture",
        supplement=proposed,
        policy_records=policy_records,
        closure_ledger=unused,
        evidence_ledger=cast(EvidenceTargetLedger, _UnusedLedger()),
        build_provider=lambda event_id, text, digest: (_ for _ in ()).throw(
            AssertionError("provider must not run")
        ),
    )

    assert report.residuals
    assert all(item.terminal_status is ResidualTerminalStatus.BLOCKED for item in report.residuals)
    assert all(item.block_reason == "supplement_unapproved" for item in report.residuals)
    assert all(item.r17_selection_signal == "not_applicable" for item in report.residuals)
    assert all(item.assertion is None for item in report.residuals)
    assert report.model_execution_count == 0
    assert report.canonical_write_count == 0
    assert report.proposed_change_count == 0


def test_report_fingerprint_rejects_tampering(tmp_path: Path) -> None:
    record = ResidualClosureRecord(
        event_id="AHE-051",
        terminal_status=ResidualTerminalStatus.BLOCKED,
        r17_selection_signal="not_applicable",
        block_reason="supplement_unapproved",
        evidence_supported=False,
    )
    report = build_deterministic_residual_composition_report(
        report_id="r19-tamper", residuals=(record,)
    )
    tampered = report.model_copy(
        deep=True,
        update={"residuals": (report.residuals[0].model_copy(update={"block_reason": "mutated"}),)},
    )
    with pytest.raises(ValueError, match="fingerprint"):
        verify_deterministic_residual_composition_report(tampered)

    path = tmp_path / "report.json"
    path.write_text(tampered.model_dump_json(), encoding="utf-8")
    with pytest.raises(ValueError, match="fingerprint"):
        load_deterministic_residual_composition_report(path)


class _ClosedLedger:
    def __init__(
        self,
        target: EvidenceTarget,
        bundle: DocumentRepresentationBundle,
        document: Document,
        source_id: str,
    ) -> None:
        self._target = target
        self._bundle = bundle
        self._document = document
        self._source_id = source_id

    def get_actor(self, record_id: str):
        return None

    def get_organization(self, record_id: str):
        return None

    def get_source(self, record_id: str):
        return object() if record_id == self._source_id else None

    def get_evidence_target(self, record_id: str):
        return self._target

    def get_document_representation_bundle(self, record_id: str):
        return self._bundle

    def get_document(self, record_id: str):
        return self._document


class _AprilOrderProvider:
    def resolve_references(
        self, event_id: str, source_text: str, source_text_sha256: str
    ) -> EventEntityReferences:
        del event_id, source_text, source_text_sha256
        return EventEntityReferences(
            entities=(),
            subject_value_authorizations=(
                DecontextualizationExclusion(
                    exclusion_id="EGX-900",
                    contextual_kind="non_entity_value",
                    source_range=SourceRange(start=5, end=20, text="The April order"),
                    rationale="A date-scoped nominal order, not an Actor or Organization.",
                ),
            ),
        )


def _resolved_ahe_051_supplement() -> R19ProviderSupplement:
    ahe_051_text = _AHE_051_TEXT
    return R19ProviderSupplement(
        supplement_id="hsq-r19-provider-supplement-fixture",
        review_status="approved",
        bound_connection_gold=SupplementFileBinding(
            path="docs/hsq-event-entity-connection-gold-v2.json", sha256="a" * 64
        ),
        bound_proposition_gold=SupplementFileBinding(
            path="docs/hsq-source-grounded-proposition-gold-v1.json", sha256="a" * 64
        ),
        residual_inputs=(
            SupplementInputBinding(
                event_id="AHE-051",
                input_path="data/r17-semantic-selection-contract/inputs/AHE-051.json",
                input_sha256="a" * 64,
                source_sha256=hashlib.sha256(ahe_051_text.encode()).hexdigest(),
            ),
        ),
        event_bindings=(
            SupplementEventBinding(
                residual_event_id="AHE-051",
                residual_source_sha256=hashlib.sha256(ahe_051_text.encode()).hexdigest(),
                residual_trigger=SupplementTriggerSpan(start=28, end=33, source_text="final"),
                binding_rationale="No Connection Gold Event; subject is a value.",
            ),
        ),
        event_evidence=(
            SupplementEventEvidence(
                event_id="AHE-051",
                source_authority="secondary",
                attribution_basis="direct_document",
                source_id=_SOURCE_ID,
                evidence_target_id="etg_r19",
                unresolved_reason=None,
            ),
        ),
        subject_value_exclusions=(
            SupplementSubjectValueExclusion(
                exclusion_id="EGX-900",
                event_id="AHE-051",
                start=5,
                end=20,
                source_text="The April order",
                contextual_kind="non_entity_value",
                rationale="A date-scoped nominal order, not an Actor or Organization.",
            ),
        ),
        identity_mappings=(),
        predicate_mappings=(
            SupplementPredicateMapping(
                relation_label="is", predicate="is", rationale="The TDD pins predicate is."
            ),
        ),
    )


def test_orchestration_closes_ahe_051_with_valid_evidence(
    policy_records: tuple[ReferencePolicyRecord, ...],
) -> None:
    record = next(item for item in policy_records if item.event_id == "AHE-051")
    text = _AHE_051_TEXT
    target = _target(text, start=0, end=len(text))
    ledger = _ClosedLedger(target, _bundle(text), _document(), _SOURCE_ID)

    report = run_deterministic_residual_composition(
        report_id="r19-closure-fixture",
        supplement=_resolved_ahe_051_supplement(),
        policy_records=(record,),
        closure_ledger=cast(LedgerRepository, ledger),
        evidence_ledger=cast(EvidenceTargetLedger, ledger),
        build_provider=lambda event_id, text_arg, digest: _AprilOrderProvider(),
    )

    residual = report.residuals[0]
    assert residual.terminal_status is ResidualTerminalStatus.CLOSED
    assert residual.r17_selection_signal == "met"
    assert residual.composition_status is DeterministicResidualCompositionStatus.COMPOSED
    assert residual.assertion is not None
    assert residual.assertion.predicate == "is"
    assert residual.assertion.subject_value == "The April order"
    assert residual.assertion.object_value == "final"
    assert residual.evidence_supported is True
    assert report.model_execution_count == 0
    assert report.canonical_write_count == 0
    assert report.proposed_change_count == 0
