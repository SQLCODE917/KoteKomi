"""HP-3 orchestration over immutable HP-2 and HP-1 Preview evidence."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Protocol, cast

from kotekomi_domain import DocumentRepresentationBundle, ExtractionTask, ModelRun

from kotekomi_application.context_planning import (
    PARAGRAPH_SEGMENT_V2,
    ContextPlanningLedger,
    load_context_manifest,
    paragraph_source_segments,
)
from kotekomi_application.extraction_stage_trace import (
    ExtractionStageStatus,
    ExtractionStageTrace,
    build_extraction_stage_trace,
)
from kotekomi_application.hybrid_document_references import (
    canonical_hybrid_reference_preview_bytes,
    hybrid_reference_preview_from_bytes,
)
from kotekomi_application.hybrid_entity_grounding import (
    HYBRID_ENTITY_GROUNDING_POLICY_ID,
    EntityGroundingEligibility,
    EntityLinkEvidence,
    EntityLinkingPort,
    HybridEntityGroundingPreview,
    build_entity_linking_inputs,
    build_hybrid_entity_grounding_preview_record,
    canonical_hybrid_entity_grounding_preview_bytes,
    entity_grounding_terminal_status,
    entity_link_evidence_id,
    evaluate_entity_grounding_eligibility,
    hybrid_entity_grounding_preview_sha256,
    run_recorded_entity_linking,
)
from kotekomi_application.hybrid_mention_interpretation import (
    HybridExtractionPreview,
    HybridPreviewStatus,
    canonical_hybrid_extraction_preview_bytes,
    hybrid_extraction_preview_from_bytes,
    hybrid_source_segment_id,
)


class HybridEntityGroundingLedger(ContextPlanningLedger, Protocol):
    def get_document_representation_bundle(
        self, record_id: str
    ) -> DocumentRepresentationBundle | None: ...

    def save_extraction_task(self, record: ExtractionTask) -> None: ...

    def save_model_run(self, record: ModelRun) -> None: ...


class HybridEntityGroundingArchive(Protocol):
    def read_hybrid_reference_preview(self, preview_id: str) -> bytes: ...

    def read_hybrid_extraction_preview(self, preview_id: str) -> bytes: ...

    def put_model_run_output(
        self, model_run_id: str, payload: bytes, expected_digest: str
    ) -> object: ...

    def put_hybrid_entity_grounding_preview(
        self,
        preview: HybridEntityGroundingPreview,
        payload: bytes,
        expected_sha256: str,
    ) -> object: ...


@dataclass(frozen=True)
class HybridEntityGroundingCommand:
    parent_preview_id: str


@dataclass(frozen=True)
class HybridEntityGroundingResult:
    preview: HybridEntityGroundingPreview
    sha256: str
    archive_path: str


def run_hybrid_entity_grounding_preview(
    *,
    command: HybridEntityGroundingCommand,
    ledger: HybridEntityGroundingLedger,
    archive: HybridEntityGroundingArchive,
    linker: EntityLinkingPort,
) -> HybridEntityGroundingResult:
    """Validate parent lineage, run eligible batches, and publish one HP-3 Preview."""
    reference_payload = archive.read_hybrid_reference_preview(command.parent_preview_id)
    references = hybrid_reference_preview_from_bytes(reference_payload)
    if references.id != command.parent_preview_id:
        raise ValueError("HP-3 parent Preview identity does not match its Archive path.")
    if canonical_hybrid_reference_preview_bytes(references) != reference_payload:
        raise ValueError("HP-3 parent Preview does not use canonical encoding.")
    reference_sha256 = hashlib.sha256(reference_payload).hexdigest()

    mention_payload = archive.read_hybrid_extraction_preview(references.parent_preview_id)
    mentions = hybrid_extraction_preview_from_bytes(mention_payload)
    if mentions.id != references.parent_preview_id:
        raise ValueError("HP-3 HP-1 Preview identity does not match HP-2 lineage.")
    if canonical_hybrid_extraction_preview_bytes(mentions) != mention_payload:
        raise ValueError("HP-3 HP-1 Preview does not use canonical encoding.")
    mention_sha256 = hashlib.sha256(mention_payload).hexdigest()
    if mention_sha256 != references.parent_preview_sha256:
        raise ValueError("HP-3 HP-1 Preview digest does not match HP-2 lineage.")
    if mentions.terminal_status is HybridPreviewStatus.BLOCKED:
        raise ValueError("HP-3 cannot consume a blocked HP-1 Preview.")

    bundle = ledger.get_document_representation_bundle(mentions.representation_id)
    if bundle is None:
        raise ValueError("HP-3 parent Preview references a missing representation.")
    manifest = load_context_manifest(
        mentions.context_manifest_id,
        cast(ContextPlanningLedger, ledger),
        verified_bundle=bundle,
    )
    if manifest.representation_id != mentions.representation_id:
        raise ValueError("HP-3 ContextManifest representation lineage drifted.")
    source_text_by_id = _validated_source_segments(bundle, mentions)
    base_eligibility = evaluate_entity_grounding_eligibility(mentions, references)
    candidate_by_id = {item.id: item for item in mentions.candidates}

    eligibility: list[EntityGroundingEligibility] = []
    eligibility_trace_by_candidate: dict[str, ExtractionStageTrace] = {}
    traces: list[ExtractionStageTrace] = []
    for decision in base_eligibility:
        candidate = candidate_by_id[decision.candidate_id]
        source_text = source_text_by_id[candidate.source_segment_id]
        trace = build_extraction_stage_trace(
            trace_run_id=f"entity_grounding:{references.id}:{candidate.id}",
            ordinal=0,
            stage_id="entity_grounding_eligibility",
            stage_version=HYBRID_ENTITY_GROUNDING_POLICY_ID,
            producer_id="kotekomi_application",
            source_segment_id=candidate.source_segment_id,
            source_text_sha256=hashlib.sha256(source_text.encode()).hexdigest(),
            input_record_ids=tuple(
                sorted(
                    (
                        mentions.id,
                        references.id,
                        candidate.id,
                        *(
                            (decision.reference_decision_id,)
                            if decision.reference_decision_id
                            else ()
                        ),
                    )
                )
            ),
            configuration={"policy_id": HYBRID_ENTITY_GROUNDING_POLICY_ID},
            input_payload={
                "candidate_id": candidate.id,
                "text": candidate.text,
                "start": candidate.start,
                "end": candidate.end,
            },
            output_payload={"status": decision.status.value, "reason": decision.reason.value},
            status=ExtractionStageStatus.COMPLETED,
        )
        traced = decision.model_copy(update={"trace_id": trace.id})
        eligibility.append(traced)
        eligibility_trace_by_candidate[candidate.id] = trace
        traces.append(trace)

    requests = build_entity_linking_inputs(
        eligibility=tuple(eligibility),
        candidates=mentions.candidates,
        source_text_by_id=source_text_by_id,
    )

    extraction_task_ids: list[str] = []
    model_run_ids: list[str] = []
    link_evidence: list[EntityLinkEvidence] = []
    diagnostics: list[str] = []
    successful_batches = 0
    for request in requests:
        source_segment_id = request.source_segment_id
        source_text = request.source_text
        ordered_candidates = tuple(candidate_by_id[item.candidate_id] for item in request.mentions)
        outcome = run_recorded_entity_linking(
            representation_id=mentions.representation_id,
            context_manifest_id=manifest.id,
            context_manifest_digest=manifest.manifest_digest,
            context_manifest_payload={
                "id": manifest.id,
                "manifest_digest": manifest.manifest_digest,
                "representation_id": manifest.representation_id,
                "source_segment_id": source_segment_id,
                "source_text_sha256": request.source_text_sha256,
            },
            request=request,
            linker=linker,
            ledger=ledger,
            archive=archive,
        )
        extraction_task_ids.append(outcome.extraction_task.id)
        model_run_ids.append(outcome.model_run.id)
        if outcome.batch is None:
            diagnostic = (
                f"{source_segment_id}:{outcome.model_run.status.value}:"
                f"{outcome.model_run.error_code or 'unknown'}"
            )
            diagnostics.append(diagnostic)
            for candidate in ordered_candidates:
                parent_trace = eligibility_trace_by_candidate[candidate.id]
                traces.append(
                    build_extraction_stage_trace(
                        trace_run_id=parent_trace.trace_run_id,
                        ordinal=1,
                        stage_id="entity_linking",
                        stage_version=linker.identity.model_revision,
                        producer_id=linker.identity.producer_id,
                        source_segment_id=source_segment_id,
                        source_text_sha256=request.source_text_sha256,
                        parent_trace_ids=(parent_trace.id,),
                        input_record_ids=tuple(sorted((candidate.id, outcome.extraction_task.id))),
                        execution_record_ids=(
                            outcome.extraction_task.id,
                            outcome.model_run.id,
                        ),
                        configuration={
                            "policy_id": HYBRID_ENTITY_GROUNDING_POLICY_ID,
                            "resource_manifest_sha256": linker.identity.resource_manifest_sha256,
                        },
                        input_payload={
                            "candidate_id": candidate.id,
                            "text": candidate.text,
                        },
                        output_payload={"model_run_status": outcome.model_run.status.value},
                        status=ExtractionStageStatus.BLOCKED,
                        diagnostics=(diagnostic,),
                    )
                )
            continue
        successful_batches += 1
        evidence_by_candidate = {item.candidate_id: item for item in outcome.batch.evidences}
        for candidate in ordered_candidates:
            model_evidence = evidence_by_candidate[candidate.id]
            parent_trace = eligibility_trace_by_candidate[candidate.id]
            evidence_id = entity_link_evidence_id(
                candidate_id=candidate.id,
                source_segment_id=source_segment_id,
                source_text_sha256=request.source_text_sha256,
                text=candidate.text,
                start=candidate.start,
                end=candidate.end,
                extraction_task_id=outcome.extraction_task.id,
                model_run_id=outcome.model_run.id,
                candidates=model_evidence.candidates,
            )
            trace = build_extraction_stage_trace(
                trace_run_id=parent_trace.trace_run_id,
                ordinal=1,
                stage_id="entity_linking",
                stage_version=linker.identity.model_revision,
                producer_id=linker.identity.producer_id,
                source_segment_id=source_segment_id,
                source_text_sha256=request.source_text_sha256,
                parent_trace_ids=(parent_trace.id,),
                input_record_ids=tuple(sorted((candidate.id, outcome.extraction_task.id))),
                execution_record_ids=(outcome.extraction_task.id, outcome.model_run.id),
                configuration={
                    "policy_id": HYBRID_ENTITY_GROUNDING_POLICY_ID,
                    "resource_manifest_sha256": linker.identity.resource_manifest_sha256,
                },
                input_payload={
                    "candidate_id": candidate.id,
                    "text": candidate.text,
                    "start": candidate.start,
                    "end": candidate.end,
                    "source_text": source_text,
                },
                output_payload={
                    "evidence_id": evidence_id,
                    "candidates": [
                        item.model_dump(mode="json") for item in model_evidence.candidates
                    ],
                },
                status=ExtractionStageStatus.COMPLETED,
            )
            traces.append(trace)
            link_evidence.append(
                EntityLinkEvidence(
                    id=evidence_id,
                    candidate_id=candidate.id,
                    source_segment_id=source_segment_id,
                    source_text_sha256=request.source_text_sha256,
                    text=candidate.text,
                    start=candidate.start,
                    end=candidate.end,
                    candidates=model_evidence.candidates,
                    extraction_task_id=outcome.extraction_task.id,
                    model_run_id=outcome.model_run.id,
                    trace_id=trace.id,
                )
            )

    terminal = entity_grounding_terminal_status(
        parent_status=mentions.terminal_status,
        required_batches=len(requests),
        successful_batches=successful_batches,
    )
    preview = build_hybrid_entity_grounding_preview_record(
        parent_preview_id=references.id,
        parent_preview_sha256=reference_sha256,
        mention_preview_id=mentions.id,
        mention_preview_sha256=mention_sha256,
        representation_id=mentions.representation_id,
        eligibility=tuple(eligibility),
        link_evidence=tuple(link_evidence),
        extraction_task_ids=tuple(sorted(extraction_task_ids)),
        model_run_ids=tuple(sorted(model_run_ids)),
        traces=tuple(
            sorted(
                traces, key=lambda item: (item.source_segment_id, item.trace_run_id, item.ordinal)
            )
        ),
        terminal_status=terminal,
        diagnostics=tuple(sorted(diagnostics)),
    )
    payload = canonical_hybrid_entity_grounding_preview_bytes(preview)
    digest = hybrid_entity_grounding_preview_sha256(preview)
    archive.put_hybrid_entity_grounding_preview(preview, payload, digest)
    return HybridEntityGroundingResult(
        preview=preview,
        sha256=digest,
        archive_path=f"extraction/entity-grounding-previews/{preview.id}.json",
    )


def _validated_source_segments(
    bundle: DocumentRepresentationBundle,
    parent: HybridExtractionPreview,
) -> dict[str, str]:
    preview = parent
    node = next((item for item in bundle.nodes if item.id == preview.paragraph_node_id), None)
    if node is None or node.node_type != "paragraph":
        raise ValueError("HP-3 parent paragraph is missing from the accepted representation.")
    view = next((item for item in bundle.text_views if item.id == node.text_view_id), None)
    if view is None:
        raise ValueError("HP-3 parent paragraph TextView is missing.")
    paragraph = view.text[node.start_char : node.end_char]
    segments = paragraph_source_segments(paragraph, PARAGRAPH_SEGMENT_V2)
    source_text_by_id = {
        hybrid_source_segment_id(bundle.representation.id, node.id, item): item.exact_text
        for item in segments
    }
    for candidate in preview.candidates:
        source_text = source_text_by_id.get(candidate.source_segment_id)
        if source_text is None:
            raise ValueError("HP-3 cannot reconstruct a parent SourceSegment.")
        if hashlib.sha256(source_text.encode()).hexdigest() != candidate.source_text_sha256:
            raise ValueError("HP-3 MentionCandidate source digest drifted.")
        if (
            candidate.end > len(source_text)
            or source_text[candidate.start : candidate.end] != candidate.text
        ):
            raise ValueError("HP-3 MentionCandidate does not match source characters.")
    return source_text_by_id
