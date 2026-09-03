from __future__ import annotations

import hashlib
from dataclasses import replace
from datetime import UTC, datetime
from typing import cast

import pytest
from kotekomi_application import (
    HYBRID_STAGE_ORDER,
    HybridDocumentArchive,
    HybridDocumentCoverageReport,
    HybridDocumentCoverageStatus,
    HybridDocumentLedger,
    HybridDocumentPlan,
    HybridParagraphStageRecord,
    HybridParagraphStatus,
    HybridPipelinePolicyManifest,
    HybridPolicyManifestInput,
    HybridPolicyPin,
    HybridStageDisposition,
    HybridStageId,
    build_hybrid_document_coverage_report,
    build_hybrid_paragraph_receipt,
    canonical_hybrid_document_coverage_report_bytes,
    canonical_hybrid_pipeline_policy_manifest_bytes,
    hybrid_pipeline_policy_manifest_from_bytes,
    plan_hybrid_document,
    validate_hybrid_paragraph_receipt,
)
from kotekomi_domain import (
    AnalysisPlanArtifact,
    AnalysisUnitArtifact,
    DocumentNode,
    DocumentRepresentation,
    DocumentRepresentationBundle,
    ParseQualityReport,
    RepresentationAnalyzability,
    TextView,
    TextViewKind,
    canonical_representation_digest,
)

NOW = datetime(2026, 9, 3, tzinfo=UTC)
TEXT = "Second paragraph.\nFirst paragraph."


class _PlanningLedger:
    def __init__(self, bundle: DocumentRepresentationBundle | None = None) -> None:
        self.bundle = bundle or _bundle()
        self.analysis_units: dict[str, AnalysisUnitArtifact] = {}
        self.analysis_plans: dict[str, AnalysisPlanArtifact] = {}

    def get_document_representation_bundle(
        self, record_id: str
    ) -> DocumentRepresentationBundle | None:
        return self.bundle if record_id == self.bundle.representation.id else None

    def save_analysis_unit_artifact(self, record: AnalysisUnitArtifact) -> None:
        self.analysis_units[record.id] = record

    def get_analysis_unit_artifact(self, record_id: str) -> AnalysisUnitArtifact | None:
        return self.analysis_units.get(record_id)

    def save_analysis_plan_artifact(self, record: AnalysisPlanArtifact) -> None:
        self.analysis_plans[record.id] = record

    def get_analysis_plan_artifact(self, record_id: str) -> AnalysisPlanArtifact | None:
        return self.analysis_plans.get(record_id)


class _PlanningArchive:
    def __init__(self) -> None:
        self.manifests: dict[str, bytes] = {}
        self.receipts: dict[str, bytes] = {}
        self.reports: dict[str, bytes] = {}

    def put_hybrid_pipeline_policy_manifest(
        self,
        manifest: HybridPipelinePolicyManifest,
        payload: bytes,
        expected_sha256: str,
    ) -> object:
        record_id = manifest.id
        assert hashlib.sha256(payload).hexdigest() == expected_sha256
        prior = self.manifests.setdefault(record_id, payload)
        if prior != payload:
            raise ValueError("immutable conflict")
        return object()

    def read_hybrid_pipeline_policy_manifest(self, manifest_id: str) -> bytes:
        return self.manifests[manifest_id]

    def read_hybrid_paragraph_receipt(self, receipt_id: str) -> bytes:
        try:
            return self.receipts[receipt_id]
        except KeyError as error:
            raise FileNotFoundError(receipt_id) from error

    def put_hybrid_document_coverage_report(
        self,
        report: HybridDocumentCoverageReport,
        payload: bytes,
        expected_sha256: str,
    ) -> object:
        record_id = report.id
        assert hashlib.sha256(payload).hexdigest() == expected_sha256
        prior = self.reports.setdefault(record_id, payload)
        if prior != payload:
            raise ValueError("immutable conflict")
        return object()

    def read_hybrid_document_coverage_report(self, report_id: str) -> bytes:
        return self.reports[report_id]


def test_hybrid_document_plan_selects_every_paragraph_in_reading_order() -> None:
    ledger = _PlanningLedger()
    archive = _PlanningArchive()

    result = _plan(_policy_input(), ledger, archive)

    assert result.manifest.selected_node_count == 2
    assert result.manifest.excluded_node_count == 1
    assert tuple(item.paragraph_node_id for item in result.manifest.work_items) == (
        "nod_first",
        "nod_second",
    )
    assert tuple(item.ordinal for item in result.manifest.work_items) == (0, 1)
    assert (
        hybrid_pipeline_policy_manifest_from_bytes(archive.manifests[result.manifest.id])
        == result.manifest
    )


def test_changed_policy_pin_changes_every_paragraph_fingerprint() -> None:
    first = _plan(_policy_input(prompt_sha="a" * 64), _PlanningLedger(), _PlanningArchive())
    changed = _plan(_policy_input(prompt_sha="b" * 64), _PlanningLedger(), _PlanningArchive())

    assert first.manifest.policy_digest != changed.manifest.policy_digest
    assert tuple(item.input_fingerprint for item in first.manifest.work_items) != tuple(
        item.input_fingerprint for item in changed.manifest.work_items
    )


def test_each_policy_configuration_input_changes_every_paragraph_fingerprint() -> None:
    policy = _policy_input()
    baseline = _plan(policy, _PlanningLedger(), _PlanningArchive())
    changed_inputs = (
        replace(policy, model_identity={"name": "changed-model"}),
        replace(policy, generation_parameters={"temperature": 1}),
        replace(policy, mention_proposer_identity={"model": "changed-proposer"}),
        replace(policy, entity_linker_identity={"model": "changed-linker"}),
        replace(
            policy,
            pins=(HybridPolicyPin(kind="prompt", identity="fixture", sha256="b" * 64),),
        ),
    )

    for changed_input in changed_inputs:
        result = _plan(changed_input, _PlanningLedger(), _PlanningArchive())
        assert result.manifest.policy_digest != baseline.manifest.policy_digest
        assert tuple(item.input_fingerprint for item in result.manifest.work_items) != tuple(
            item.input_fingerprint for item in baseline.manifest.work_items
        )


def test_partial_stage_is_an_accounted_gap_but_held_hp7_diagnostic_is_not() -> None:
    plan = _plan(_policy_input(), _PlanningLedger(), _PlanningArchive())
    work = plan.manifest.work_items[0]
    stages = tuple(
        _stage(
            stage,
            terminal_status="partial" if stage is HybridStageId.HP3_GROUNDING else "complete",
            diagnostics=("held_events:1",) if stage is HybridStageId.HP7_PROPOSAL_PLAN else (),
        )
        for stage in HYBRID_STAGE_ORDER
    )

    partial = build_hybrid_paragraph_receipt(
        manifest=plan.manifest,
        work=work,
        context_manifest_id="ctx_fixture",
        stages=stages,
    )
    complete = build_hybrid_paragraph_receipt(
        manifest=plan.manifest,
        work=work,
        context_manifest_id="ctx_fixture",
        stages=tuple(
            _stage(
                stage,
                diagnostics=("held_events:1",) if stage is HybridStageId.HP7_PROPOSAL_PLAN else (),
            )
            for stage in HYBRID_STAGE_ORDER
        ),
    )

    assert partial.status is HybridParagraphStatus.GAP
    assert partial.gap_reasons == ("hp3_grounding:partial",)
    assert complete.status is HybridParagraphStatus.COMPLETE
    assert complete.gap_reasons == ()


def test_policy_manifest_rejects_noncanonical_and_tampered_bytes() -> None:
    result = _plan(_policy_input(), _PlanningLedger(), _PlanningArchive())
    canonical = canonical_hybrid_pipeline_policy_manifest_bytes(result.manifest)

    with pytest.raises(ValueError, match="canonical encoding"):
        hybrid_pipeline_policy_manifest_from_bytes(b" " + canonical)
    with pytest.raises(ValueError, match="identity does not match"):
        hybrid_pipeline_policy_manifest_from_bytes(
            canonical.replace(result.manifest.id.encode(), b"hpm_000000000000000000000000", 1)
        )


def test_document_coverage_requires_every_receipt() -> None:
    ledger = _PlanningLedger()
    archive = _PlanningArchive()
    plan = _plan(_policy_input(), ledger, archive)

    with pytest.raises(ValueError, match="missing paragraph 0"):
        build_hybrid_document_coverage_report(
            manifest=plan.manifest,
            ledger=cast(HybridDocumentLedger, ledger),
            archive=cast(HybridDocumentArchive, archive),
        )


def test_empty_document_produces_complete_empty_coverage() -> None:
    ledger = _PlanningLedger(_bundle(include_paragraphs=False))
    archive = _PlanningArchive()
    plan = _plan(_policy_input(), ledger, archive)

    report = build_hybrid_document_coverage_report(
        manifest=plan.manifest,
        ledger=cast(HybridDocumentLedger, ledger),
        archive=cast(HybridDocumentArchive, archive),
    )

    assert report.status is HybridDocumentCoverageStatus.COMPLETE
    assert report.required_paragraph_count == 0
    assert report.complete_paragraph_count == 0
    assert report.gap_paragraph_count == 0
    assert report.records == ()
    assert archive.reports[report.id] == canonical_hybrid_document_coverage_report_bytes(report)


def test_receipt_replay_rejects_changed_authoritative_paragraph_characters() -> None:
    ledger = _PlanningLedger()
    archive = _PlanningArchive()
    plan = _plan(_policy_input(), ledger, archive)
    work = plan.manifest.work_items[0]
    stages = (
        _stage(HybridStageId.HP1_MENTIONS, terminal_status="blocked"),
        *(
            HybridParagraphStageRecord(
                stage_id=stage,
                disposition=HybridStageDisposition.NOT_RUN,
                diagnostics=("stopped_after:hp1_mentions:blocked",),
            )
            for stage in HYBRID_STAGE_ORDER[1:]
        ),
    )
    receipt = build_hybrid_paragraph_receipt(
        manifest=plan.manifest,
        work=work,
        context_manifest_id="ctx_fixture",
        stages=stages,
    )
    text_view = ledger.bundle.text_views[0]
    ledger.bundle = ledger.bundle.model_copy(
        update={
            "text_views": (
                text_view.model_copy(update={"text": text_view.text.replace("First", "Alter")}),
            )
        }
    )

    with pytest.raises(ValueError, match="authoritative text digest changed"):
        validate_hybrid_paragraph_receipt(
            receipt,
            plan.manifest,
            work,
            cast(HybridDocumentLedger, ledger),
            cast(HybridDocumentArchive, archive),
        )


def _policy_input(prompt_sha: str = "a" * 64) -> HybridPolicyManifestInput:
    return HybridPolicyManifestInput(
        representation_id="rep_hp8_fixture",
        model_identity={"name": "fixture"},
        generation_parameters={"temperature": 0},
        mention_proposer_identity={"model": "fixture"},
        entity_linker_identity={"model": "fixture"},
        pins=(HybridPolicyPin(kind="prompt", identity="fixture", sha256=prompt_sha),),
    )


def _plan(
    policy: HybridPolicyManifestInput,
    ledger: _PlanningLedger,
    archive: _PlanningArchive,
) -> HybridDocumentPlan:
    return plan_hybrid_document(
        policy,
        cast(HybridDocumentLedger, ledger),
        cast(HybridDocumentArchive, archive),
    )


def _stage(
    stage_id: HybridStageId,
    *,
    terminal_status: str = "complete",
    diagnostics: tuple[str, ...] = (),
) -> HybridParagraphStageRecord:
    return HybridParagraphStageRecord(
        stage_id=stage_id,
        disposition=HybridStageDisposition.CREATED,
        output_id=f"out_{stage_id.value}",
        output_sha256="a" * 64,
        terminal_status=terminal_status,
        diagnostics=diagnostics,
    )


def _bundle(*, include_paragraphs: bool = True) -> DocumentRepresentationBundle:
    representation_id = "rep_hp8_fixture"
    text_view = TextView(
        id="tvw_hp8_fixture",
        representation_id=representation_id,
        kind=TextViewKind.LOGICAL,
        content_digest=hashlib.sha256(TEXT.encode()).hexdigest(),
        text=TEXT,
        normalization_policy="utf8_identity_v1",
    )
    split = TEXT.index("\n")
    root = DocumentNode(
        id="nod_root",
        representation_id=representation_id,
        node_type="document",
        order_index=0,
        text_view_id=text_view.id,
        start_char=0,
        end_char=len(TEXT),
    )
    second = DocumentNode(
        id="nod_second",
        representation_id=representation_id,
        parent_node_id=root.id,
        node_type="paragraph",
        order_index=2,
        text_view_id=text_view.id,
        start_char=0,
        end_char=split,
    )
    first = DocumentNode(
        id="nod_first",
        representation_id=representation_id,
        parent_node_id=root.id,
        node_type="paragraph",
        order_index=1,
        text_view_id=text_view.id,
        start_char=split + 1,
        end_char=len(TEXT),
    )
    nodes = (root, second, first) if include_paragraphs else (root,)
    quality = ParseQualityReport(
        id="pqr_hp8_fixture",
        representation_id=representation_id,
        metric_values={"text_char_count": len(TEXT)},
        analyzability=RepresentationAnalyzability.ACCEPTABLE,
    )
    template = DocumentRepresentation(
        id=representation_id,
        document_id="doc_hp8_fixture",
        parser_name="fixture",
        parser_version="1",
        parser_config_digest="a" * 64,
        processing_task_fingerprint_id="ptf_hp8_fixture",
        input_blob_digest=hashlib.sha256(TEXT.encode()).hexdigest(),
        canonical_output_digest="0" * 64,
        created_at=NOW,
    )
    representation = template.model_copy(
        update={
            "canonical_output_digest": canonical_representation_digest(
                template,
                text_views=(text_view,),
                nodes=nodes,
                edges=(),
                source_regions=(),
                quality_report=quality,
            )
        }
    )
    return DocumentRepresentationBundle(
        representation=representation,
        text_views=(text_view,),
        nodes=nodes,
        quality_report=quality,
    )
