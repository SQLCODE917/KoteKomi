"""Narrow, read-only paragraph evidence inspection through Ledger and Archive Ports."""

from __future__ import annotations

import hashlib
from dataclasses import replace
from typing import Literal, Protocol, cast

from kotekomi_domain import IngestionChangeSet, IngestionRun
from kotekomi_domain.models import JsonValue
from pydantic import BaseModel, ConfigDict, model_validator

from kotekomi_application.hybrid_document_orchestration import (
    HybridDocumentLedger,
    HybridStageId,
    hybrid_document_coverage_report_from_bytes,
    hybrid_paragraph_receipt_from_bytes,
    hybrid_pipeline_policy_manifest_from_bytes,
    read_hybrid_stage_output,
    validate_hybrid_paragraph_receipt,
)
from kotekomi_application.hybrid_document_references import HybridReferencePreview
from kotekomi_application.hybrid_entity_grounding import HybridEntityGroundingPreview
from kotekomi_application.ingestion_debug_summary import (
    DebugSummary,
    SnapshotOperation,
    build_debug_summary,
)
from kotekomi_application.ingestion_inspection import (
    ArtifactHandle,
    InspectionContext,
    ParagraphInput,
    build_profile,
)
from kotekomi_application.ingestion_observability import (
    IngestionLinkageLedger,
    IngestionObservabilityArchive,
    require_ingestion_analysis,
    require_ingestion_change_set,
)


class InspectionLedger(HybridDocumentLedger, IngestionLinkageLedger, Protocol):
    def get_ingestion_run(self, record_id: str) -> IngestionRun | None: ...
    def get_ingestion_change_set(self, record_id: str) -> IngestionChangeSet | None: ...


class InspectParagraphInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    ingestion_run_id: str
    paragraph_node_id: str
    state_root: str
    phase: HybridStageId | None = None
    record_id: str | None = None
    trace_id: str | None = None
    artifact_id: str | None = None
    artifact_sha256: str | None = None

    @model_validator(mode="after")
    def selectors(self) -> InspectParagraphInput:
        if (self.record_id or self.trace_id or self.artifact_id) and self.phase is None:
            raise ValueError("Record, trace and artifact selectors require --phase.")
        if self.record_id and self.trace_id:
            raise ValueError("Record and trace selectors are mutually exclusive.")
        if (self.artifact_id is None) != (self.artifact_sha256 is None):
            raise ValueError("An explicit artifact requires its SHA-256 digest.")
        return self


class InspectParagraphResult(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    summary: DebugSummary | None = None
    evidence: dict[str, JsonValue] | None = None
    binding: Literal["receipt", "explicit_artifact"] = "receipt"


_RECORD_FIELDS: dict[str, tuple[str, ...]] = {
    "hp1_mentions": (
        "observations",
        "candidates",
        "boundary_decisions",
        "boundary_adjudications",
        "interpretations",
        "traces",
    ),
    "hp2_references": (
        "reference_decisions",
        "alias_declarations",
        "semantic_antecedent_spans",
        "traces",
    ),
    "hp3_grounding": ("eligibility", "link_evidence", "traces"),
    "hp4_event_triggers": ("triggers", "traces"),
    "hp6_event_semantics": (
        "source_grounded_events",
        "event_type_assignments",
        "semantic_events",
        "targets",
        "assignments",
        "qualifiers",
        "gaps",
        "statements",
        "judgments",
        "propositions",
        "nli_observations",
        "proposition_decisions",
        "traces",
    ),
    "hp7_proposal_plan": ("decisions", "proposed_changes", "traces"),
    "hp10_standing_facts": (
        "drafts",
        "propositions",
        "qualifications",
        "nli_observations",
        "proposition_decisions",
        "decisions",
        "proposed_changes",
        "traces",
    ),
}


def select_stage_record(
    output: object, phase: HybridStageId, record_id: str
) -> dict[str, JsonValue]:
    for field in _RECORD_FIELDS[phase.value]:
        members = cast(tuple[object, ...], getattr(output, field, ()))
        for record in members:
            if getattr(record, "id", None) != record_id:
                continue
            if isinstance(record, BaseModel):
                return cast(dict[str, JsonValue], record.model_dump(mode="json"))
            raise ValueError("Unsupported stage record type.")
    if isinstance(output, HybridReferencePreview):
        nested_spans = tuple(
            s for d in output.alias_declarations for s in (d.expanded_span, d.alias_span)
        ) + tuple(d.reference_span for d in output.reference_decisions)
        for span in nested_spans:
            if span.id == record_id:
                return cast(dict[str, JsonValue], span.model_dump(mode="json"))
    raise ValueError(f"Record does not belong to the requested phase: {record_id}")


def load_inspection_paragraph(
    input: InspectParagraphInput, ledger: InspectionLedger, archive: IngestionObservabilityArchive
) -> ParagraphInput:
    run = ledger.get_ingestion_run(input.ingestion_run_id)
    if run is None:
        raise ValueError(f"IngestionRun not found: {input.ingestion_run_id}")
    if run.ingestion_change_set_id is None:
        raise ValueError(
            "No completed receipt yet; use --phase --artifact-id --sha256 from the copied handle."
        )
    analysis = require_ingestion_analysis(run, ledger)
    change_set = require_ingestion_change_set(run, analysis, ledger)
    report_id = archive.find_hybrid_document_coverage_report_by_sha256(
        change_set.coverage_report_digest
    )
    if report_id is None:
        raise ValueError("Ingestion coverage report is missing from the Archive.")
    raw = archive.read_hybrid_document_coverage_report(report_id)
    if hashlib.sha256(raw).hexdigest() != change_set.coverage_report_digest:
        raise ValueError("Coverage report digest mismatch.")
    report = hybrid_document_coverage_report_from_bytes(raw)
    if report.id != report_id or report.representation_id != change_set.representation_id:
        raise ValueError("Coverage report source identity is invalid.")
    coverage = next(
        (r for r in report.records if r.paragraph_node_id == input.paragraph_node_id), None
    )
    if coverage is None:
        raise ValueError("Paragraph does not belong to this ingestion.")
    raw_receipt = archive.read_hybrid_paragraph_receipt(coverage.receipt_id)
    if hashlib.sha256(raw_receipt).hexdigest() != coverage.receipt_sha256:
        raise ValueError("Paragraph receipt digest does not match coverage.")
    receipt = hybrid_paragraph_receipt_from_bytes(raw_receipt)
    manifest_raw = archive.read_hybrid_pipeline_policy_manifest(report.policy_manifest_id)
    if hashlib.sha256(manifest_raw).hexdigest() != report.policy_manifest_sha256:
        raise ValueError("Coverage policy digest mismatch.")
    manifest = hybrid_pipeline_policy_manifest_from_bytes(manifest_raw)
    if (
        manifest.id != report.policy_manifest_id
        or receipt.id != coverage.receipt_id
        or receipt.status != coverage.status
    ):
        raise ValueError("Coverage receipt or manifest identity mismatch.")
    work = next(
        (w for w in manifest.work_items if w.paragraph_node_id == input.paragraph_node_id), None
    )
    if work is None:
        raise ValueError("Paragraph does not belong to the policy manifest.")
    validate_hybrid_paragraph_receipt(receipt, manifest, work, ledger, archive)
    bundle = ledger.get_document_representation_bundle(report.representation_id)
    if bundle is None:
        raise ValueError("Missing source representation.")
    node = next(n for n in bundle.nodes if n.id == input.paragraph_node_id)
    view = next(v for v in bundle.text_views if v.id == node.text_view_id)
    outputs: dict[str, object] = {}
    artifacts: list[ArtifactHandle] = []
    for stage in receipt.stages:
        if stage.output_id is None:
            continue
        payload, parsed = read_hybrid_stage_output(stage.stage_id, stage.output_id, archive)
        outputs[stage.stage_id.value] = parsed
        artifacts.append(
            ArtifactHandle(
                stage.stage_id.value,
                stage.output_id,
                "archive/" + archive.ingestion_evidence_path(stage.stage_id.value, stage.output_id),
                hashlib.sha256(payload).hexdigest(),
            )
        )
    return ParagraphInput(
        coverage.ordinal,
        view.text[node.start_char : node.end_char],
        report.representation_id,
        node.id,
        node.start_char,
        receipt.status.value,
        receipt.gap_reasons,
        outputs,
        bundle,
        InspectionContext(run.id, input.state_root, receipt.id, manifest.id, report.id),
        tuple(artifacts),
        tuple((s.stage_id.value, s.terminal_status or "not run") for s in receipt.stages),
        tuple((s.stage_id.value, s.diagnostics) for s in receipt.stages),
        receipt.stages,
    )


def inspect_ingestion_paragraph(
    input: InspectParagraphInput, ledger: InspectionLedger, archive: IngestionObservabilityArchive
) -> InspectParagraphResult:
    if input.artifact_id is not None:
        assert input.phase is not None
        run = ledger.get_ingestion_run(input.ingestion_run_id)
        if run is None:
            raise ValueError("IngestionRun not found.")
        raw, output = read_hybrid_stage_output(input.phase, input.artifact_id, archive)
        if getattr(output, "id", None) != input.artifact_id:
            raise ValueError("Explicit artifact identity mismatch.")
        if hashlib.sha256(raw).hexdigest() != input.artifact_sha256:
            raise ValueError("Explicit artifact digest mismatch.")
        paragraph_node_id = getattr(output, "paragraph_node_id", None)
        if paragraph_node_id is None and isinstance(output, HybridEntityGroundingPreview):
            parent_raw, parent = read_hybrid_stage_output(
                HybridStageId.HP1_MENTIONS, output.mention_preview_id, archive
            )
            if hashlib.sha256(parent_raw).hexdigest() != output.mention_preview_sha256:
                raise ValueError("Grounding mention evidence digest mismatch.")
            paragraph_node_id = getattr(parent, "paragraph_node_id", None)
        if paragraph_node_id != input.paragraph_node_id:
            raise ValueError("Artifact belongs to another paragraph.")
        representation_id = getattr(output, "representation_id", None)
        if not isinstance(representation_id, str):
            raise ValueError("Artifact source identity is missing.")
        bundle = ledger.get_document_representation_bundle(representation_id)
        if bundle is None or not any(
            n.id == input.paragraph_node_id and n.node_type == "paragraph" for n in bundle.nodes
        ):
            raise ValueError("Artifact authoritative source is missing.")
        binding = "explicit_artifact"
    else:
        paragraph = load_inspection_paragraph(input, ledger, archive)
        if input.phase is None:
            profile = build_profile(
                text=paragraph.text,
                representation_id=paragraph.representation_id,
                paragraph_node_id=paragraph.paragraph_node_id,
                node_start_char=paragraph.node_start_char,
                stage_outputs=paragraph.stage_outputs,
                bundle=paragraph.bundle,
            )
            profile = replace(
                profile,
                artifacts=paragraph.artifacts,
                stage_statuses=paragraph.phase_states,
                phase_diagnostics=paragraph.phase_diagnostics,
            )
            return InspectParagraphResult(
                summary=build_debug_summary(
                    profile,
                    ordinal=paragraph.ordinal,
                    paragraph_status=paragraph.status,
                    operation=SnapshotOperation(mode="replay", status="complete", exit_code=0),
                    visible_stages=tuple(s.value for s in HybridStageId),
                    selected_key=None,
                    context=paragraph.context,
                )
            )
        output = paragraph.stage_outputs.get(input.phase.value)
        if output is None:
            if input.record_id is not None or input.trace_id is not None:
                raise ValueError("Requested phase did not produce an artifact.")
            recorded = next((s for s in paragraph.phase_records if s.stage_id == input.phase), None)
            if recorded is None:
                raise ValueError("Requested phase has no receipt record.")
            return InspectParagraphResult(
                evidence=cast(dict[str, JsonValue], recorded.model_dump(mode="json"))
            )
        binding = "receipt"
    assert input.phase is not None
    if input.trace_id is not None:
        traces = cast(tuple[BaseModel, ...], getattr(output, "traces", ()))
        trace = next((t for t in traces if getattr(t, "id", None) == input.trace_id), None)
        if trace is None:
            raise ValueError("Trace does not belong to the requested phase.")
        evidence = cast(dict[str, JsonValue], trace.model_dump(mode="json"))
    elif input.record_id is not None:
        evidence = select_stage_record(output, input.phase, input.record_id)
    elif isinstance(output, BaseModel):
        evidence = cast(dict[str, JsonValue], output.model_dump(mode="json"))
    else:
        raise ValueError("Unsupported phase output.")
    return InspectParagraphResult(evidence=evidence, binding=binding)
