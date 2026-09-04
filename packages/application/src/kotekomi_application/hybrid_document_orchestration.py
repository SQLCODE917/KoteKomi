"""HP-8 document scope, immutable checkpoints, coverage, and closure."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal, Protocol, cast

from kotekomi_domain import (
    AnalysisItemAttempt,
    AnalysisRun,
    AnalysisRunState,
    DocumentRepresentationBundle,
    IngestionChangeSet,
    IngestionChangeSetOrigin,
    IngestionRun,
    PlannedAnalysisItem,
)
from kotekomi_domain.models import JsonValue
from pydantic import BaseModel, ConfigDict, Field, model_validator

from kotekomi_application.analysis_coverage import (
    AnalysisCoverageLedger,
    freeze_analysis_plan,
    load_frozen_analysis_plan,
)
from kotekomi_application.context_planning import (
    AnalysisUnitPlanningInput,
    plan_analysis_units,
)
from kotekomi_application.hybrid_atomic_claims import (
    canonical_hybrid_atomic_claim_preview_bytes,
    hybrid_atomic_claim_preview_from_bytes,
)
from kotekomi_application.hybrid_document_references import (
    canonical_hybrid_reference_preview_bytes,
    hybrid_reference_preview_from_bytes,
)
from kotekomi_application.hybrid_entity_grounding import (
    canonical_hybrid_entity_grounding_preview_bytes,
    hybrid_entity_grounding_preview_from_bytes,
)
from kotekomi_application.hybrid_event_frames import (
    canonical_hybrid_event_frame_preview_bytes,
    hybrid_event_frame_preview_from_bytes,
)
from kotekomi_application.hybrid_event_semantics import (
    canonical_hybrid_event_semantics_preview_bytes,
    hybrid_event_semantics_preview_from_bytes,
)
from kotekomi_application.hybrid_mention_interpretation import (
    canonical_hybrid_extraction_preview_bytes,
    hybrid_extraction_preview_from_bytes,
)
from kotekomi_application.hybrid_proposed_changes import (
    HybridProposalArchive,
    HybridProposalLedger,
    HybridProposalPlan,
    canonical_hybrid_proposal_plan_bytes,
    hybrid_proposal_plan_from_bytes,
    load_hybrid_proposal_plan,
    submit_hybrid_proposal_plan,
)
from kotekomi_application.ingestion_runs import (
    CompleteIngestionRunCapturedInput,
    IngestionRunRepository,
    complete_ingestion_run_as_captured,
)

HYBRID_DOCUMENT_POLICY_ID = "hybrid_document_pipeline_v1"
HYBRID_DOCUMENT_TASK_TYPE = "hybrid_document_paragraph"
_HASH_ID_LENGTH = 24
_SHA256 = r"^[a-f0-9]{64}$"


class HybridStageId(StrEnum):
    HP1_MENTIONS = "hp1_mentions"
    HP2_REFERENCES = "hp2_references"
    HP3_GROUNDING = "hp3_grounding"
    HP4_EVENT_FRAMES = "hp4_event_frames"
    HP5_ATOMIC_CLAIMS = "hp5_atomic_claims"
    HP6_EVENT_SEMANTICS = "hp6_event_semantics"
    HP7_PROPOSAL_PLAN = "hp7_proposal_plan"


HYBRID_STAGE_ORDER = tuple(HybridStageId)


class HybridStageDisposition(StrEnum):
    CREATED = "created"
    REUSED = "reused"
    NOT_RUN = "not_run"


class HybridParagraphStatus(StrEnum):
    COMPLETE = "complete"
    GAP = "gap"


class HybridDocumentCoverageStatus(StrEnum):
    COMPLETE = "complete"
    COMPLETE_WITH_GAPS = "complete_with_gaps"


class HybridPolicyPin(BaseModel):
    """One named byte or policy digest that affects HP-1 through HP-7."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    kind: Literal["prompt", "schema", "ontology", "policy"]
    identity: Annotated[str, Field(min_length=1)]
    sha256: Annotated[str, Field(pattern=_SHA256)]


class HybridParagraphWork(BaseModel):
    """One immutable paragraph selected by the document policy."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    ordinal: Annotated[int, Field(ge=0)]
    analysis_unit_id: Annotated[str, Field(min_length=1)]
    analysis_unit_fingerprint: Annotated[str, Field(pattern=_SHA256)]
    paragraph_node_id: Annotated[str, Field(min_length=1)]
    source_text_sha256: Annotated[str, Field(pattern=_SHA256)]
    input_fingerprint: Annotated[str, Field(pattern=_SHA256)]


class HybridPipelinePolicyManifest(BaseModel):
    """Pinned document scope and configuration for one HP-8 run."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["hybrid_pipeline_policy_manifest_v1"] = (
        "hybrid_pipeline_policy_manifest_v1"
    )
    id: Annotated[str, Field(pattern=r"^hpm_[a-f0-9]{24}$")]
    policy_id: Literal["hybrid_document_pipeline_v1"] = HYBRID_DOCUMENT_POLICY_ID
    policy_digest: Annotated[str, Field(pattern=_SHA256)]
    representation_id: Annotated[str, Field(min_length=1)]
    frozen_analysis_plan_id: Annotated[str, Field(min_length=1)]
    frozen_analysis_plan_sha256: Annotated[str, Field(pattern=_SHA256)]
    selected_node_count: Annotated[int, Field(ge=0)]
    excluded_node_count: Annotated[int, Field(ge=0)]
    model_identity: dict[str, JsonValue]
    generation_parameters: dict[str, JsonValue]
    mention_proposer_identity: dict[str, JsonValue]
    entity_linker_identity: dict[str, JsonValue]
    pins: tuple[HybridPolicyPin, ...]
    work_items: tuple[HybridParagraphWork, ...]

    @model_validator(mode="after")
    def validate_contract(self) -> HybridPipelinePolicyManifest:
        if self.selected_node_count != len(self.work_items):
            raise ValueError("Hybrid policy selected-node count does not match its work.")
        if tuple(item.ordinal for item in self.work_items) != tuple(range(len(self.work_items))):
            raise ValueError("Hybrid paragraph work must use contiguous source order.")
        _distinct(
            "Hybrid paragraph node IDs", tuple(item.paragraph_node_id for item in self.work_items)
        )
        _distinct(
            "Hybrid AnalysisUnit IDs", tuple(item.analysis_unit_id for item in self.work_items)
        )
        if tuple(sorted(self.pins, key=lambda item: (item.kind, item.identity))) != self.pins:
            raise ValueError("Hybrid policy pins must use canonical order.")
        _ordered_distinct(
            "Hybrid policy pin identities",
            tuple(f"{item.kind}:{item.identity}" for item in self.pins),
        )
        policy_payload = _policy_payload(self)
        if self.policy_digest != _digest(policy_payload):
            raise ValueError("Hybrid policy digest does not match its pinned inputs.")
        for item in self.work_items:
            if item.input_fingerprint != _work_fingerprint(self.policy_digest, item):
                raise ValueError("Hybrid Paragraph Work fingerprint does not match its inputs.")
        if self.id != _content_id("hpm", self.model_dump(mode="json", exclude={"id"})):
            raise ValueError("Hybrid policy identity does not match its contents.")
        return self


class HybridParagraphStageRecord(BaseModel):
    """One stage disposition retained by a Paragraph Receipt."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    stage_id: HybridStageId
    disposition: HybridStageDisposition
    output_id: str | None = None
    output_sha256: Annotated[str, Field(pattern=_SHA256)] | None = None
    terminal_status: str | None = None
    diagnostics: tuple[Annotated[str, Field(min_length=1)], ...] = ()

    @model_validator(mode="after")
    def validate_contract(self) -> HybridParagraphStageRecord:
        has_output = self.output_id is not None
        if has_output != (self.output_sha256 is not None) or has_output != (
            self.terminal_status is not None
        ):
            raise ValueError("A stage output requires identity, digest, and terminal status.")
        if self.disposition is HybridStageDisposition.NOT_RUN:
            if has_output or not self.diagnostics:
                raise ValueError("A not-run stage requires only a terminal diagnostic.")
        elif not has_output:
            raise ValueError("An executed stage requires output evidence.")
        _ordered_distinct("Hybrid stage diagnostics", self.diagnostics)
        return self


class HybridParagraphReceipt(BaseModel):
    """One immutable terminal checkpoint for one Paragraph Work item."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["hybrid_paragraph_receipt_v1"] = "hybrid_paragraph_receipt_v1"
    id: Annotated[str, Field(pattern=r"^hpr_[a-f0-9]{24}$")]
    policy_manifest_id: Annotated[str, Field(pattern=r"^hpm_[a-f0-9]{24}$")]
    policy_manifest_sha256: Annotated[str, Field(pattern=_SHA256)]
    representation_id: Annotated[str, Field(min_length=1)]
    paragraph_node_id: Annotated[str, Field(min_length=1)]
    analysis_unit_id: Annotated[str, Field(min_length=1)]
    input_fingerprint: Annotated[str, Field(pattern=_SHA256)]
    context_manifest_id: Annotated[str, Field(min_length=1)]
    status: HybridParagraphStatus
    stages: tuple[HybridParagraphStageRecord, ...]
    proposed_change_ids: tuple[Annotated[str, Field(min_length=1)], ...] = ()
    gap_reasons: tuple[Annotated[str, Field(min_length=1)], ...] = ()

    @model_validator(mode="after")
    def validate_contract(self) -> HybridParagraphReceipt:
        if tuple(item.stage_id for item in self.stages) != HYBRID_STAGE_ORDER:
            raise ValueError("Paragraph Receipt must record every HP stage in order.")
        _ordered_distinct("Paragraph Receipt ProposedChange IDs", self.proposed_change_ids)
        _ordered_distinct("Paragraph Receipt gap reasons", self.gap_reasons)
        if self.status is HybridParagraphStatus.COMPLETE and self.gap_reasons:
            raise ValueError("A complete Paragraph Receipt cannot record gaps.")
        if self.status is HybridParagraphStatus.GAP and not self.gap_reasons:
            raise ValueError("A gap Paragraph Receipt requires a reason.")
        if self.id != _receipt_id(self.input_fingerprint):
            raise ValueError("Paragraph Receipt identity does not match its work fingerprint.")
        return self


class HybridDocumentCoverageRecord(BaseModel):
    """One reconciled Paragraph Work result."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    ordinal: Annotated[int, Field(ge=0)]
    paragraph_node_id: Annotated[str, Field(min_length=1)]
    input_fingerprint: Annotated[str, Field(pattern=_SHA256)]
    receipt_id: Annotated[str, Field(pattern=r"^hpr_[a-f0-9]{24}$")]
    receipt_sha256: Annotated[str, Field(pattern=_SHA256)]
    status: HybridParagraphStatus
    proposed_change_ids: tuple[Annotated[str, Field(min_length=1)], ...] = ()
    gap_reasons: tuple[Annotated[str, Field(min_length=1)], ...] = ()


class HybridDocumentCoverageReport(BaseModel):
    """Immutable complete reconciliation for one Hybrid Pipeline Policy."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["hybrid_document_coverage_report_v1"] = (
        "hybrid_document_coverage_report_v1"
    )
    id: Annotated[str, Field(pattern=r"^hdc_[a-f0-9]{24}$")]
    policy_manifest_id: Annotated[str, Field(pattern=r"^hpm_[a-f0-9]{24}$")]
    policy_manifest_sha256: Annotated[str, Field(pattern=_SHA256)]
    representation_id: Annotated[str, Field(min_length=1)]
    status: HybridDocumentCoverageStatus
    required_paragraph_count: Annotated[int, Field(ge=0)]
    complete_paragraph_count: Annotated[int, Field(ge=0)]
    gap_paragraph_count: Annotated[int, Field(ge=0)]
    records: tuple[HybridDocumentCoverageRecord, ...]
    proposed_change_ids: tuple[Annotated[str, Field(min_length=1)], ...] = ()

    @model_validator(mode="after")
    def validate_contract(self) -> HybridDocumentCoverageReport:
        if self.required_paragraph_count != len(self.records):
            raise ValueError("Hybrid coverage count does not match its records.")
        if tuple(item.ordinal for item in self.records) != tuple(range(len(self.records))):
            raise ValueError("Hybrid coverage records must use contiguous source order.")
        complete_count = sum(item.status is HybridParagraphStatus.COMPLETE for item in self.records)
        gap_count = sum(item.status is HybridParagraphStatus.GAP for item in self.records)
        if (complete_count, gap_count) != (
            self.complete_paragraph_count,
            self.gap_paragraph_count,
        ):
            raise ValueError("Hybrid coverage status counts do not match its records.")
        expected_status = (
            HybridDocumentCoverageStatus.COMPLETE_WITH_GAPS
            if gap_count
            else HybridDocumentCoverageStatus.COMPLETE
        )
        if self.status is not expected_status:
            raise ValueError("Hybrid coverage terminal status does not match its records.")
        expected_proposals = tuple(
            sorted({item for record in self.records for item in record.proposed_change_ids})
        )
        if self.proposed_change_ids != expected_proposals:
            raise ValueError("Hybrid coverage ProposedChange union is invalid.")
        if self.id != _content_id("hdc", self.model_dump(mode="json", exclude={"id"})):
            raise ValueError("Hybrid coverage identity does not match its contents.")
        return self


class HybridDocumentArchive(HybridProposalArchive, Protocol):
    def put_hybrid_pipeline_policy_manifest(
        self,
        manifest: HybridPipelinePolicyManifest,
        payload: bytes,
        expected_sha256: str,
    ) -> object: ...

    def read_hybrid_pipeline_policy_manifest(self, manifest_id: str) -> bytes: ...

    def put_hybrid_paragraph_receipt(
        self,
        receipt: HybridParagraphReceipt,
        payload: bytes,
        expected_sha256: str,
    ) -> object: ...

    def read_hybrid_paragraph_receipt(self, receipt_id: str) -> bytes: ...

    def put_hybrid_document_coverage_report(
        self,
        report: HybridDocumentCoverageReport,
        payload: bytes,
        expected_sha256: str,
    ) -> object: ...

    def read_hybrid_document_coverage_report(self, report_id: str) -> bytes: ...


class HybridDocumentLedger(AnalysisCoverageLedger, HybridProposalLedger, Protocol):
    def save_ingestion_change_set(self, record: IngestionChangeSet) -> None: ...

    def get_ingestion_change_set(self, record_id: str) -> IngestionChangeSet | None: ...

    def get_ingestion_run(self, record_id: str) -> IngestionRun | None: ...

    def complete_ingestion_run_if_running(self, record: IngestionRun) -> bool: ...


@dataclass(frozen=True)
class HybridPolicyManifestInput:
    representation_id: str
    model_identity: dict[str, JsonValue]
    generation_parameters: dict[str, JsonValue]
    mention_proposer_identity: dict[str, JsonValue]
    entity_linker_identity: dict[str, JsonValue]
    pins: tuple[HybridPolicyPin, ...]


@dataclass(frozen=True)
class HybridDocumentPlan:
    manifest: HybridPipelinePolicyManifest
    sha256: str
    archive_path: str


@dataclass(frozen=True)
class HybridDocumentClosureInput:
    ingestion_run_id: str
    source_id: str
    document_id: str
    representation_id: str
    capture_provenance_activity_id: str
    normalized_source_url: str
    report_id: str
    analysis_origin: IngestionChangeSetOrigin
    closed_at: datetime


@dataclass(frozen=True)
class HybridDocumentClosureResult:
    ingestion_run: IngestionRun
    analysis_run: AnalysisRun
    change_set: IngestionChangeSet
    report: HybridDocumentCoverageReport


def plan_hybrid_document(
    input: HybridPolicyManifestInput,
    ledger: HybridDocumentLedger,
    archive: HybridDocumentArchive,
) -> HybridDocumentPlan:
    """Freeze every paragraph and publish one pinned Hybrid Pipeline Policy."""
    bundle = _require_bundle(input.representation_id, ledger)
    analysis_plan = plan_analysis_units(
        AnalysisUnitPlanningInput(
            representation_id=input.representation_id,
            policy_id=HYBRID_DOCUMENT_POLICY_ID,
            task_type=HYBRID_DOCUMENT_TASK_TYPE,
            max_focus_nodes_per_unit=1,
            focus_node_types=("paragraph",),
        ),
        ledger,
    )
    frozen = freeze_analysis_plan(analysis_plan, ledger)
    paragraphs = tuple(
        item
        for item in sorted(bundle.nodes, key=lambda node: (node.order_index, node.id))
        if item.node_type == "paragraph"
    )
    if len(paragraphs) != len(frozen.units) or any(
        unit.focus_node_ids != (paragraph.id,)
        for unit, paragraph in zip(frozen.units, paragraphs, strict=True)
    ):
        raise ValueError("Hybrid document plan does not match the paragraph scope.")
    base = {
        "schema_version": "hybrid_pipeline_policy_manifest_v1",
        "policy_id": HYBRID_DOCUMENT_POLICY_ID,
        "representation_id": input.representation_id,
        "frozen_analysis_plan_id": frozen.id,
        "frozen_analysis_plan_sha256": frozen.plan_digest,
        "selected_node_count": len(paragraphs),
        "excluded_node_count": len(bundle.nodes) - len(paragraphs),
        "model_identity": input.model_identity,
        "generation_parameters": input.generation_parameters,
        "mention_proposer_identity": input.mention_proposer_identity,
        "entity_linker_identity": input.entity_linker_identity,
        "pins": [item.model_dump(mode="json") for item in input.pins],
    }
    policy_digest = _digest(base)
    works: list[HybridParagraphWork] = []
    for ordinal, (unit, paragraph) in enumerate(zip(frozen.units, paragraphs, strict=True)):
        text_view = next(item for item in bundle.text_views if item.id == paragraph.text_view_id)
        text_digest = hashlib.sha256(
            text_view.text[paragraph.start_char : paragraph.end_char].encode()
        ).hexdigest()
        partial = HybridParagraphWork(
            ordinal=ordinal,
            analysis_unit_id=unit.id,
            analysis_unit_fingerprint=unit.fingerprint,
            paragraph_node_id=paragraph.id,
            source_text_sha256=text_digest,
            input_fingerprint="0" * 64,
        )
        works.append(
            partial.model_copy(
                update={"input_fingerprint": _work_fingerprint(policy_digest, partial)}
            )
        )
    payload = {
        **base,
        "policy_digest": policy_digest,
        "work_items": [item.model_dump(mode="json") for item in works],
    }
    manifest = HybridPipelinePolicyManifest.model_validate_json(
        _canonical_json({**payload, "id": _content_id("hpm", payload)})
    )
    canonical = canonical_hybrid_pipeline_policy_manifest_bytes(manifest)
    digest = hashlib.sha256(canonical).hexdigest()
    archive.put_hybrid_pipeline_policy_manifest(manifest, canonical, digest)
    return HybridDocumentPlan(
        manifest,
        digest,
        f"extraction/document-policies/{manifest.id}.json",
    )


def build_hybrid_paragraph_receipt(
    *,
    manifest: HybridPipelinePolicyManifest,
    work: HybridParagraphWork,
    context_manifest_id: str,
    stages: tuple[HybridParagraphStageRecord, ...],
    proposed_change_ids: tuple[str, ...] = (),
) -> HybridParagraphReceipt:
    """Construct one terminal receipt from exact HP stage results."""
    if work not in manifest.work_items:
        raise ValueError("Paragraph Receipt work is outside the Hybrid Pipeline Policy.")
    gap_reasons = tuple(
        sorted(
            {
                f"{stage.stage_id.value}:{stage.terminal_status}"
                for stage in stages
                if stage.disposition is not HybridStageDisposition.NOT_RUN
                and stage.terminal_status != "complete"
            }
            | {
                f"{stage.stage_id.value}:{diagnostic}"
                for stage in stages
                for diagnostic in stage.diagnostics
                if stage.disposition is HybridStageDisposition.NOT_RUN
            }
        )
    )
    manifest_bytes = canonical_hybrid_pipeline_policy_manifest_bytes(manifest)
    return HybridParagraphReceipt(
        id=_receipt_id(work.input_fingerprint),
        policy_manifest_id=manifest.id,
        policy_manifest_sha256=hashlib.sha256(manifest_bytes).hexdigest(),
        representation_id=manifest.representation_id,
        paragraph_node_id=work.paragraph_node_id,
        analysis_unit_id=work.analysis_unit_id,
        input_fingerprint=work.input_fingerprint,
        context_manifest_id=context_manifest_id,
        status=HybridParagraphStatus.GAP if gap_reasons else HybridParagraphStatus.COMPLETE,
        stages=stages,
        proposed_change_ids=tuple(sorted(set(proposed_change_ids))),
        gap_reasons=gap_reasons,
    )


def publish_hybrid_paragraph_receipt(
    receipt: HybridParagraphReceipt,
    archive: HybridDocumentArchive,
) -> tuple[str, str]:
    payload = canonical_hybrid_paragraph_receipt_bytes(receipt)
    digest = hashlib.sha256(payload).hexdigest()
    archive.put_hybrid_paragraph_receipt(receipt, payload, digest)
    return digest, f"extraction/paragraph-receipts/{receipt.id}.json"


def load_reusable_hybrid_paragraph_receipt(
    *,
    manifest: HybridPipelinePolicyManifest,
    work: HybridParagraphWork,
    ledger: HybridDocumentLedger,
    archive: HybridDocumentArchive,
) -> HybridParagraphReceipt | None:
    """Return a fully replayed checkpoint or report that no checkpoint exists."""
    try:
        payload = archive.read_hybrid_paragraph_receipt(_receipt_id(work.input_fingerprint))
    except FileNotFoundError:
        return None
    receipt = hybrid_paragraph_receipt_from_bytes(payload)
    validate_hybrid_paragraph_receipt(receipt, manifest, work, ledger, archive)
    return receipt


def validate_hybrid_paragraph_receipt(
    receipt: HybridParagraphReceipt,
    manifest: HybridPipelinePolicyManifest,
    work: HybridParagraphWork,
    ledger: HybridDocumentLedger,
    archive: HybridDocumentArchive,
) -> None:
    """Replay one receipt against policy, stage bytes, and authoritative source state."""
    manifest_payload = archive.read_hybrid_pipeline_policy_manifest(manifest.id)
    if (
        hybrid_pipeline_policy_manifest_from_bytes(manifest_payload) != manifest
        or hashlib.sha256(manifest_payload).hexdigest() != receipt.policy_manifest_sha256
    ):
        raise ValueError("Paragraph Receipt policy evidence does not match its digest.")
    if (
        receipt.policy_manifest_id != manifest.id
        or receipt.representation_id != manifest.representation_id
        or receipt.paragraph_node_id != work.paragraph_node_id
        or receipt.analysis_unit_id != work.analysis_unit_id
        or receipt.input_fingerprint != work.input_fingerprint
    ):
        raise ValueError("Paragraph Receipt does not match its planned work.")
    bundle = _require_bundle(receipt.representation_id, ledger)
    node = next((item for item in bundle.nodes if item.id == receipt.paragraph_node_id), None)
    if node is None or node.node_type != "paragraph":
        raise ValueError("Paragraph Receipt authoritative node is missing or invalid.")
    text_view = next(
        (item for item in bundle.text_views if item.id == node.text_view_id),
        None,
    )
    if text_view is None:
        raise ValueError("Paragraph Receipt authoritative text view is missing.")
    source_text_sha256 = hashlib.sha256(
        text_view.text[node.start_char : node.end_char].encode()
    ).hexdigest()
    if source_text_sha256 != work.source_text_sha256:
        raise ValueError("Paragraph Receipt authoritative text digest changed.")
    outputs: dict[HybridStageId, object] = {}
    for stage in receipt.stages:
        if stage.disposition is HybridStageDisposition.NOT_RUN:
            continue
        assert stage.output_id is not None and stage.output_sha256 is not None
        raw, parsed = read_hybrid_stage_output(stage.stage_id, stage.output_id, archive)
        if hashlib.sha256(raw).hexdigest() != stage.output_sha256:
            raise ValueError("Paragraph Receipt stage digest does not match Archive bytes.")
        parsed_id = getattr(parsed, "id", None)
        if parsed_id != stage.output_id:
            raise ValueError("Paragraph Receipt stage identity does not match Archive bytes.")
        parsed_status = getattr(parsed, "terminal_status", "complete")
        if getattr(parsed_status, "value", parsed_status) != stage.terminal_status:
            raise ValueError("Paragraph Receipt stage status does not match Archive bytes.")
        outputs[stage.stage_id] = parsed
    _validate_stage_lineage(receipt, outputs)
    hp7 = outputs.get(HybridStageId.HP7_PROPOSAL_PLAN)
    if isinstance(hp7, HybridProposalPlan):
        if load_hybrid_proposal_plan(hp7.id, ledger, archive) != hp7:
            raise ValueError("Paragraph Receipt HP-7 replay changed its Plan.")
        proposal_ids = tuple(sorted(item.id for item in hp7.proposed_changes))
        if receipt.proposed_change_ids != proposal_ids:
            raise ValueError("Paragraph Receipt ProposedChange IDs do not match HP-7.")
    elif receipt.proposed_change_ids:
        raise ValueError("Paragraph Receipt has proposals without an HP-7 Plan.")


def build_hybrid_document_coverage_report(
    *,
    manifest: HybridPipelinePolicyManifest,
    ledger: HybridDocumentLedger,
    archive: HybridDocumentArchive,
) -> HybridDocumentCoverageReport:
    """Require and reconcile one valid receipt for every planned paragraph."""
    report = _reconcile_hybrid_document_coverage_report(
        manifest=manifest,
        ledger=ledger,
        archive=archive,
    )
    canonical = canonical_hybrid_document_coverage_report_bytes(report)
    digest = hashlib.sha256(canonical).hexdigest()
    archive.put_hybrid_document_coverage_report(report, canonical, digest)
    return report


def _reconcile_hybrid_document_coverage_report(
    *,
    manifest: HybridPipelinePolicyManifest,
    ledger: HybridDocumentLedger,
    archive: HybridDocumentArchive,
) -> HybridDocumentCoverageReport:
    manifest_payload = archive.read_hybrid_pipeline_policy_manifest(manifest.id)
    if hybrid_pipeline_policy_manifest_from_bytes(manifest_payload) != manifest:
        raise ValueError("Hybrid document coverage policy evidence changed.")
    manifest_sha256 = hashlib.sha256(manifest_payload).hexdigest()
    records: list[HybridDocumentCoverageRecord] = []
    for work in manifest.work_items:
        receipt = load_reusable_hybrid_paragraph_receipt(
            manifest=manifest,
            work=work,
            ledger=ledger,
            archive=archive,
        )
        if receipt is None:
            raise ValueError(f"Hybrid document coverage is missing paragraph {work.ordinal}.")
        receipt_payload = archive.read_hybrid_paragraph_receipt(receipt.id)
        records.append(
            HybridDocumentCoverageRecord(
                ordinal=work.ordinal,
                paragraph_node_id=work.paragraph_node_id,
                input_fingerprint=work.input_fingerprint,
                receipt_id=receipt.id,
                receipt_sha256=hashlib.sha256(receipt_payload).hexdigest(),
                status=receipt.status,
                proposed_change_ids=receipt.proposed_change_ids,
                gap_reasons=receipt.gap_reasons,
            )
        )
    gap_count = sum(item.status is HybridParagraphStatus.GAP for item in records)
    payload: dict[str, JsonValue] = {
        "schema_version": "hybrid_document_coverage_report_v1",
        "policy_manifest_id": manifest.id,
        "policy_manifest_sha256": manifest_sha256,
        "representation_id": manifest.representation_id,
        "status": (
            HybridDocumentCoverageStatus.COMPLETE_WITH_GAPS.value
            if gap_count
            else HybridDocumentCoverageStatus.COMPLETE.value
        ),
        "required_paragraph_count": len(records),
        "complete_paragraph_count": len(records) - gap_count,
        "gap_paragraph_count": gap_count,
        "records": [item.model_dump(mode="json") for item in records],
        "proposed_change_ids": cast(
            JsonValue,
            sorted({item for record in records for item in record.proposed_change_ids}),
        ),
    }
    report = HybridDocumentCoverageReport.model_validate_json(
        _canonical_json({**payload, "id": _content_id("hdc", payload)})
    )
    return report


def close_hybrid_document_ingestion(
    input: HybridDocumentClosureInput,
    *,
    ledger: HybridDocumentLedger,
    archive: HybridDocumentArchive,
) -> HybridDocumentClosureResult:
    """Close one fully accounted HP-8 document inside the caller's transaction."""
    report = load_hybrid_document_coverage_report(input.report_id, ledger, archive)
    manifest = load_hybrid_pipeline_policy_manifest(report.policy_manifest_id, archive)
    if (
        report.representation_id != input.representation_id
        or manifest.representation_id != input.representation_id
    ):
        raise ValueError("HP-8 closure representation does not match its coverage.")
    ingestion_run = ledger.get_ingestion_run(input.ingestion_run_id)
    if ingestion_run is None:
        raise ValueError("HP-8 closure references a missing IngestionRun.")
    frozen = load_frozen_analysis_plan(manifest.frozen_analysis_plan_id, ledger)
    run_id = _content_id(
        "arn",
        {
            "coverage_report_id": report.id,
        },
    )
    state = (
        AnalysisRunState.COMPLETE_WITH_GAPS
        if report.status is HybridDocumentCoverageStatus.COMPLETE_WITH_GAPS
        else AnalysisRunState.COMPLETE
    )
    analysis_run = AnalysisRun(
        id=run_id,
        document_id=input.document_id,
        representation_id=input.representation_id,
        frozen_analysis_plan_id=frozen.id,
        coverage_policy_id=HYBRID_DOCUMENT_POLICY_ID,
        state=state,
        started_at=ingestion_run.started_at,
        completed_at=input.closed_at,
    )
    receipts = tuple(
        load_reusable_hybrid_paragraph_receipt(
            manifest=manifest,
            work=work,
            ledger=ledger,
            archive=archive,
        )
        for work in manifest.work_items
    )
    if any(item is None for item in receipts):
        raise ValueError("HP-8 closure lost one validated Paragraph Receipt.")
    typed_receipts = cast(tuple[HybridParagraphReceipt, ...], receipts)
    planned_items = tuple(
        PlannedAnalysisItem(
            id=_content_id(
                "pai",
                {
                    "analysis_run_id": run_id,
                    "analysis_unit_id": work.analysis_unit_id,
                },
            ),
            analysis_run_id=run_id,
            analysis_unit_id=work.analysis_unit_id,
            task_type=HYBRID_DOCUMENT_TASK_TYPE,
            required=True,
            dependencies=(),
            expected_manifest_id=receipt.context_manifest_id,
            input_fingerprint=work.input_fingerprint,
        )
        for work, receipt in zip(manifest.work_items, typed_receipts, strict=True)
    )
    existing_run = ledger.get_analysis_run(run_id)
    analysis_origin = input.analysis_origin
    if report.required_paragraph_count == 0:
        analysis_origin = (
            IngestionChangeSetOrigin.REUSED
            if existing_run is not None
            else IngestionChangeSetOrigin.EXECUTED
        )
    if existing_run is None:
        ledger.commit_analysis_run_scope(
            analysis_run=analysis_run,
            planned_items=planned_items,
        )
    else:
        expected_run = analysis_run.model_copy(
            update={
                "started_at": existing_run.started_at,
                "completed_at": existing_run.completed_at,
            }
        )
        existing_items = ledger.list_planned_items_for_analysis_run(run_id)
        if existing_run != expected_run or tuple(
            sorted(existing_items, key=lambda item: item.id)
        ) != tuple(sorted(planned_items, key=lambda item: item.id)):
            raise ValueError("Existing HP-8 AnalysisRun conflicts with document coverage.")
        analysis_run = existing_run
    _record_hybrid_analysis_attempts(
        planned_items=planned_items,
        receipts=typed_receipts,
        ledger=ledger,
        archive=archive,
    )
    for receipt in typed_receipts:
        stage = receipt.stages[-1]
        if stage.disposition is HybridStageDisposition.NOT_RUN:
            continue
        assert stage.output_id is not None
        plan = load_hybrid_proposal_plan(stage.output_id, ledger, archive)
        submit_hybrid_proposal_plan(plan, submitted_at=input.closed_at, ledger=ledger)
    change_set = _ingestion_change_set(input, analysis_run, report, analysis_origin)
    ledger.save_ingestion_change_set(change_set)
    captured = complete_ingestion_run_as_captured(
        CompleteIngestionRunCapturedInput(
            ingestion_run_id=input.ingestion_run_id,
            normalized_source_url=input.normalized_source_url,
            source_id=input.source_id,
            document_id=input.document_id,
            representation_id=input.representation_id,
            provenance_activity_id=input.capture_provenance_activity_id,
            analysis_run_id=analysis_run.id,
            ingestion_change_set_id=change_set.id,
        ),
        cast(IngestionRunRepository, ledger),
        _FixedClock(input.closed_at),
    )
    return HybridDocumentClosureResult(captured, analysis_run, change_set, report)


def load_hybrid_pipeline_policy_manifest(
    manifest_id: str,
    archive: HybridDocumentArchive,
) -> HybridPipelinePolicyManifest:
    payload = archive.read_hybrid_pipeline_policy_manifest(manifest_id)
    manifest = hybrid_pipeline_policy_manifest_from_bytes(payload)
    if manifest.id != manifest_id:
        raise ValueError("Stored Hybrid Pipeline Policy identity does not match its path.")
    return manifest


def load_hybrid_document_coverage_report(
    report_id: str,
    ledger: HybridDocumentLedger,
    archive: HybridDocumentArchive,
) -> HybridDocumentCoverageReport:
    payload = archive.read_hybrid_document_coverage_report(report_id)
    report = hybrid_document_coverage_report_from_bytes(payload)
    if report.id != report_id:
        raise ValueError("Stored Hybrid coverage identity does not match its path.")
    manifest = load_hybrid_pipeline_policy_manifest(report.policy_manifest_id, archive)
    rebuilt = _reconcile_hybrid_document_coverage_report(
        manifest=manifest,
        ledger=ledger,
        archive=archive,
    )
    if rebuilt != report:
        raise ValueError("Stored Hybrid coverage no longer matches its Paragraph Receipts.")
    return report


def canonical_hybrid_pipeline_policy_manifest_bytes(
    manifest: HybridPipelinePolicyManifest,
) -> bytes:
    return (_canonical_json(manifest.model_dump(mode="json")) + "\n").encode()


def hybrid_pipeline_policy_manifest_from_bytes(payload: bytes) -> HybridPipelinePolicyManifest:
    return _parse_canonical(payload, HybridPipelinePolicyManifest, "Hybrid Pipeline Policy")


def canonical_hybrid_paragraph_receipt_bytes(receipt: HybridParagraphReceipt) -> bytes:
    return (_canonical_json(receipt.model_dump(mode="json")) + "\n").encode()


def hybrid_paragraph_receipt_from_bytes(payload: bytes) -> HybridParagraphReceipt:
    return _parse_canonical(payload, HybridParagraphReceipt, "Paragraph Receipt")


def canonical_hybrid_document_coverage_report_bytes(
    report: HybridDocumentCoverageReport,
) -> bytes:
    return (_canonical_json(report.model_dump(mode="json")) + "\n").encode()


def hybrid_document_coverage_report_from_bytes(payload: bytes) -> HybridDocumentCoverageReport:
    return _parse_canonical(payload, HybridDocumentCoverageReport, "Hybrid coverage report")


@dataclass(frozen=True)
class _FixedClock:
    value: datetime

    def now(self) -> datetime:
        return self.value


def _ingestion_change_set(
    input: HybridDocumentClosureInput,
    analysis_run: AnalysisRun,
    report: HybridDocumentCoverageReport,
    analysis_origin: IngestionChangeSetOrigin,
) -> IngestionChangeSet:
    payload = {
        "ingestion_run_id": input.ingestion_run_id,
        "analysis_run_id": analysis_run.id,
        "representation_id": input.representation_id,
        "coverage_report_digest": hashlib.sha256(
            canonical_hybrid_document_coverage_report_bytes(report)
        ).hexdigest(),
        "proposed_change_ids": list(report.proposed_change_ids),
        "analysis_origin": analysis_origin.value,
    }
    digest = _digest(payload)
    return IngestionChangeSet(
        id=f"ics_{digest[:_HASH_ID_LENGTH]}",
        ingestion_run_id=input.ingestion_run_id,
        analysis_run_id=analysis_run.id,
        representation_id=input.representation_id,
        coverage_report_digest=cast(str, payload["coverage_report_digest"]),
        proposed_change_ids=report.proposed_change_ids,
        analysis_origin=analysis_origin,
        closed_at=input.closed_at,
        change_set_digest=digest,
    )


def read_hybrid_stage_output(
    stage_id: HybridStageId,
    output_id: str,
    archive: HybridDocumentArchive,
) -> tuple[bytes, object]:
    if stage_id is HybridStageId.HP1_MENTIONS:
        raw = archive.read_hybrid_extraction_preview(output_id)
        parsed = hybrid_extraction_preview_from_bytes(raw)
        canonical = canonical_hybrid_extraction_preview_bytes(parsed)
    elif stage_id is HybridStageId.HP2_REFERENCES:
        raw = archive.read_hybrid_reference_preview(output_id)
        parsed = hybrid_reference_preview_from_bytes(raw)
        canonical = canonical_hybrid_reference_preview_bytes(parsed)
    elif stage_id is HybridStageId.HP3_GROUNDING:
        raw = archive.read_hybrid_entity_grounding_preview(output_id)
        parsed = hybrid_entity_grounding_preview_from_bytes(raw)
        canonical = canonical_hybrid_entity_grounding_preview_bytes(parsed)
    elif stage_id is HybridStageId.HP4_EVENT_FRAMES:
        raw = archive.read_hybrid_event_frame_preview(output_id)
        parsed = hybrid_event_frame_preview_from_bytes(raw)
        canonical = canonical_hybrid_event_frame_preview_bytes(parsed)
    elif stage_id is HybridStageId.HP5_ATOMIC_CLAIMS:
        raw = archive.read_hybrid_atomic_claim_preview(output_id)
        parsed = hybrid_atomic_claim_preview_from_bytes(raw)
        canonical = canonical_hybrid_atomic_claim_preview_bytes(parsed)
    elif stage_id is HybridStageId.HP6_EVENT_SEMANTICS:
        raw = archive.read_hybrid_event_semantics_preview(output_id)
        parsed = hybrid_event_semantics_preview_from_bytes(raw)
        canonical = canonical_hybrid_event_semantics_preview_bytes(parsed)
    else:
        raw = archive.read_hybrid_proposal_plan(output_id)
        parsed = hybrid_proposal_plan_from_bytes(raw)
        canonical = canonical_hybrid_proposal_plan_bytes(parsed)
    if canonical != raw:
        raise ValueError("Hybrid stage output does not use canonical encoding.")
    return raw, parsed


def _record_hybrid_analysis_attempts(
    *,
    planned_items: tuple[PlannedAnalysisItem, ...],
    receipts: tuple[HybridParagraphReceipt, ...],
    ledger: HybridDocumentLedger,
    archive: HybridDocumentArchive,
) -> None:
    memberships: list[tuple[PlannedAnalysisItem, HybridStageId, str]] = []
    for item, receipt in zip(planned_items, receipts, strict=True):
        for stage in receipt.stages:
            if stage.disposition is HybridStageDisposition.NOT_RUN:
                continue
            assert stage.output_id is not None
            _, output = read_hybrid_stage_output(stage.stage_id, stage.output_id, archive)
            raw_model_run_ids = getattr(output, "model_run_ids", ())
            if not isinstance(raw_model_run_ids, tuple):
                raise ValueError("Hybrid stage ModelRun references are invalid.")
            candidate_model_run_ids = cast(tuple[object, ...], raw_model_run_ids)
            if not all(isinstance(item, str) for item in candidate_model_run_ids):
                raise ValueError("Hybrid stage ModelRun references are invalid.")
            model_run_ids = tuple(cast(str, item) for item in candidate_model_run_ids)
            memberships.extend(
                (item, stage.stage_id, model_run_id) for model_run_id in model_run_ids
            )
    requested_ids = tuple(sorted({model_run_id for _, _, model_run_id in memberships}))
    found_ids = {run.id for run in ledger.list_model_runs_by_ids(requested_ids)}
    if found_ids != set(requested_ids):
        raise ValueError("Hybrid analysis membership references a missing ModelRun.")
    for item, stage_id, model_run_id in memberships:
        ledger.save_analysis_item_attempt(
            AnalysisItemAttempt(
                id=_content_id(
                    "aia",
                    {
                        "planned_item_id": item.id,
                        "model_run_id": model_run_id,
                        "execution_role": stage_id.value,
                    },
                ),
                planned_item_id=item.id,
                model_run_id=model_run_id,
                execution_role=stage_id.value,
            )
        )


def _validate_stage_lineage(
    receipt: HybridParagraphReceipt,
    outputs: dict[HybridStageId, object],
) -> None:
    hp1 = outputs.get(HybridStageId.HP1_MENTIONS)
    if hp1 is None:
        raise ValueError("Paragraph Receipt requires HP-1 evidence.")
    if (
        getattr(hp1, "representation_id", None) != receipt.representation_id
        or getattr(hp1, "paragraph_node_id", None) != receipt.paragraph_node_id
        or getattr(hp1, "context_manifest_id", None) != receipt.context_manifest_id
    ):
        raise ValueError("Paragraph Receipt HP-1 source binding is invalid.")
    previous = hp1
    for stage_id in HYBRID_STAGE_ORDER[1:]:
        current = outputs.get(stage_id)
        if current is None:
            following = HYBRID_STAGE_ORDER[stage_id_index(stage_id) + 1 :]
            if any(outputs.get(later) is not None for later in following):
                raise ValueError("Paragraph Receipt skips an executed stage.")
            break
        parent_id = getattr(current, "parent_preview_id", None)
        if parent_id != getattr(previous, "id", None):
            raise ValueError("Paragraph Receipt stage parent lineage is invalid.")
        if (
            getattr(current, "representation_id", receipt.representation_id)
            != receipt.representation_id
        ):
            raise ValueError("Paragraph Receipt stage representation is invalid.")
        if (
            getattr(current, "paragraph_node_id", receipt.paragraph_node_id)
            != receipt.paragraph_node_id
        ):
            raise ValueError("Paragraph Receipt stage paragraph is invalid.")
        previous = current


def stage_id_index(stage_id: HybridStageId) -> int:
    return HYBRID_STAGE_ORDER.index(stage_id)


def _policy_payload(manifest: HybridPipelinePolicyManifest) -> dict[str, JsonValue]:
    return {
        "schema_version": manifest.schema_version,
        "policy_id": manifest.policy_id,
        "representation_id": manifest.representation_id,
        "frozen_analysis_plan_id": manifest.frozen_analysis_plan_id,
        "frozen_analysis_plan_sha256": manifest.frozen_analysis_plan_sha256,
        "selected_node_count": manifest.selected_node_count,
        "excluded_node_count": manifest.excluded_node_count,
        "model_identity": cast(JsonValue, manifest.model_identity),
        "generation_parameters": cast(JsonValue, manifest.generation_parameters),
        "mention_proposer_identity": cast(JsonValue, manifest.mention_proposer_identity),
        "entity_linker_identity": cast(JsonValue, manifest.entity_linker_identity),
        "pins": [cast(JsonValue, item.model_dump(mode="json")) for item in manifest.pins],
    }


def _work_fingerprint(policy_digest: str, work: HybridParagraphWork) -> str:
    return _digest(
        {
            "policy_digest": policy_digest,
            "ordinal": work.ordinal,
            "analysis_unit_id": work.analysis_unit_id,
            "analysis_unit_fingerprint": work.analysis_unit_fingerprint,
            "paragraph_node_id": work.paragraph_node_id,
            "source_text_sha256": work.source_text_sha256,
        }
    )


def _require_bundle(
    representation_id: str,
    ledger: AnalysisCoverageLedger,
) -> DocumentRepresentationBundle:
    bundle = ledger.get_document_representation_bundle(representation_id)
    if bundle is None:
        raise ValueError("Hybrid document orchestration requires a representation.")
    return bundle


def _receipt_id(input_fingerprint: str) -> str:
    return f"hpr_{input_fingerprint[:_HASH_ID_LENGTH]}"


def _content_id(prefix: str, payload: object) -> str:
    return f"{prefix}_{_digest(payload)[:_HASH_ID_LENGTH]}"


def _digest(payload: object) -> str:
    return hashlib.sha256(_canonical_json(payload).encode()).hexdigest()


def _canonical_json(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _parse_canonical[T: BaseModel](payload: bytes, model: type[T], label: str) -> T:
    try:
        json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"{label} is not valid JSON.") from error
    try:
        parsed = model.model_validate_json(payload)
    except ValueError as error:
        raise ValueError(f"{label} failed contract validation: {error}") from error
    canonical = (_canonical_json(parsed.model_dump(mode="json")) + "\n").encode()
    if canonical != payload:
        raise ValueError(f"{label} does not use canonical encoding.")
    return parsed


def _ordered_distinct(label: str, values: tuple[str, ...]) -> None:
    if tuple(sorted(set(values))) != values:
        raise ValueError(f"{label} must be ordered and distinct.")


def _distinct(label: str, values: tuple[str, ...]) -> None:
    if len(set(values)) != len(values):
        raise ValueError(f"{label} must be distinct.")
