"""HP-5 deterministic atomization over immutable HP-4 event-frame evidence."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, cast

from kotekomi_domain import (
    HYBRID_EVENT_CORE_V1,
    Document,
    DocumentRepresentationBundle,
    EvidenceTarget,
    EvidenceValidationAttempt,
    EvidenceValidationAttemptStatus,
    HybridEventStructuralPredicate,
    canonical_evidence_target_digest,
    hybrid_event_ontology_slice_sha256,
)
from kotekomi_domain.models import JsonValue

from kotekomi_application.context_planning import (
    PARAGRAPH_SEGMENT_V3,
    SourceSegment,
    paragraph_source_segments,
)
from kotekomi_application.evidence_targets import (
    EvidenceTargetLedger,
    validate_evidence_target_record,
    verify_evidence_target,
)
from kotekomi_application.extraction_stage_trace import (
    ExtractionStageStatus,
    ExtractionStageTrace,
    build_extraction_stage_trace,
)
from kotekomi_application.hybrid_atomic_claims import (
    AtomicClaimDraft,
    AtomicClaimObjectKind,
    EventSubjectDraft,
    HybridAtomicClaimPreview,
    HybridAtomicClaimStatus,
    OntologyValidationFinding,
    OntologyValidationReport,
    OntologyValidationStatus,
    atomic_claim_draft_id,
    atomic_claim_sort_key,
    build_hybrid_atomic_claim_preview,
    canonical_hybrid_atomic_claim_preview_bytes,
    event_subject_draft_id,
    hybrid_atomic_claim_preview_from_bytes,
    hybrid_atomic_claim_preview_sha256,
    ontology_validation_report_id,
)
from kotekomi_application.hybrid_event_frame_preview import (
    HybridEventFrameArchive,
    load_hybrid_event_frame_preview,
)
from kotekomi_application.hybrid_event_frames import (
    EventFrameDraft,
    EventQualifierKind,
    EventTriggerDraft,
    HybridEventFramePreview,
    HybridEventFrameStatus,
    canonical_hybrid_event_frame_preview_bytes,
)
from kotekomi_application.hybrid_mention_interpretation import (
    HybridExtractionPreview,
    canonical_hybrid_extraction_preview_bytes,
    hybrid_extraction_preview_from_bytes,
    hybrid_source_segment_id,
)

HYBRID_ATOMIC_CLAIM_EVIDENCE_VALIDATOR = "hybrid_atomic_claim_evidence_v1"


class HybridAtomicClaimLedger(EvidenceTargetLedger, Protocol):
    def get_document_representation_bundle(
        self, record_id: str
    ) -> DocumentRepresentationBundle | None: ...

    def get_document(self, record_id: str) -> Document | None: ...


class HybridAtomicClaimArchive(HybridEventFrameArchive, Protocol):
    def put_hybrid_atomic_claim_preview(
        self,
        preview: HybridAtomicClaimPreview,
        payload: bytes,
        expected_sha256: str,
    ) -> object: ...

    def read_hybrid_atomic_claim_preview(self, preview_id: str) -> bytes: ...


@dataclass(frozen=True)
class HybridAtomicClaimCommand:
    parent_preview_id: str
    recorded_at: datetime


@dataclass(frozen=True)
class HybridAtomicClaimResult:
    preview: HybridAtomicClaimPreview
    sha256: str
    archive_path: str


@dataclass(frozen=True)
class _SourceContext:
    parent: HybridEventFramePreview
    mentions: HybridExtractionPreview
    bundle: DocumentRepresentationBundle
    document: Document
    paragraph_text: str
    source_segments: dict[str, SourceSegment]


def load_hybrid_atomic_claim_preview(
    preview_id: str,
    ledger: HybridAtomicClaimLedger,
    archive: HybridAtomicClaimArchive,
) -> HybridAtomicClaimPreview:
    """Reload canonical HP-5 evidence and replay its complete source lineage."""
    payload = archive.read_hybrid_atomic_claim_preview(preview_id)
    preview = hybrid_atomic_claim_preview_from_bytes(payload)
    if preview.id != preview_id or canonical_hybrid_atomic_claim_preview_bytes(preview) != payload:
        raise ValueError("HP-5 Preview identity or canonical encoding is invalid.")
    parent = load_hybrid_event_frame_preview(preview.parent_preview_id, archive)
    parent_payload = canonical_hybrid_event_frame_preview_bytes(parent)
    if (
        hashlib.sha256(parent_payload).hexdigest() != preview.parent_preview_sha256
        or parent.parent_preview_id != preview.grounding_preview_id
        or parent.parent_preview_sha256 != preview.grounding_preview_sha256
        or parent.reference_preview_id != preview.reference_preview_id
        or parent.reference_preview_sha256 != preview.reference_preview_sha256
        or parent.mention_preview_id != preview.mention_preview_id
        or parent.mention_preview_sha256 != preview.mention_preview_sha256
        or parent.representation_id != preview.representation_id
        or parent.paragraph_node_id != preview.paragraph_node_id
    ):
        raise ValueError("HP-5 parent lineage does not match its pinned identities.")
    bundle = ledger.get_document_representation_bundle(preview.representation_id)
    if bundle is None:
        raise ValueError("HP-5 authoritative DocumentRepresentationBundle is missing.")
    if ledger.get_document(bundle.representation.document_id) is None:
        raise ValueError("HP-5 authoritative Document is missing.")
    if not any(item.id == preview.paragraph_node_id for item in bundle.nodes):
        raise ValueError("HP-5 authoritative paragraph node is missing.")
    if (
        preview.ontology_slice_id != HYBRID_EVENT_CORE_V1.id
        or preview.ontology_slice_sha256 != hybrid_event_ontology_slice_sha256()
    ):
        raise ValueError("HP-5 ontology slice is stale or unavailable.")
    attempts: dict[str, EvidenceValidationAttempt] = {}
    for attempt_id in preview.evidence_validation_attempt_ids:
        attempt = ledger.get_evidence_validation_attempt(attempt_id)
        if attempt is None:
            raise ValueError("HP-5 Preview references a missing evidence validation attempt.")
        if attempt.evidence_target_id in attempts:
            raise ValueError("HP-5 Preview repeats validation for one EvidenceTarget.")
        attempts[attempt.evidence_target_id] = attempt
    for target_id in preview.evidence_target_ids:
        target = ledger.get_evidence_target(target_id)
        attempt = attempts.get(target_id)
        if target is None or attempt is None:
            raise ValueError("HP-5 Preview references missing evidence validation records.")
        replay = verify_evidence_target(target, attempt, ledger)
        if not replay.valid:
            raise ValueError(f"HP-5 EvidenceTarget replay failed: {replay.error_message}")
    return preview


def run_hybrid_atomic_claim_preview(
    *,
    command: HybridAtomicClaimCommand,
    ledger: HybridAtomicClaimLedger,
    archive: HybridAtomicClaimArchive,
) -> HybridAtomicClaimResult:
    """Atomize every valid HP-4 frame and publish one immutable HP-5 Preview."""
    context = _load_context(command.parent_preview_id, ledger, archive)
    target_by_segment, attempt_by_segment = _prepare_evidence(context, command.recorded_at, ledger)
    candidate_ids = {item.id for item in context.mentions.candidates}
    interpretation_trace_by_candidate = {
        item.candidate_id: item.trace_id for item in context.mentions.interpretations
    }
    trigger_by_id = {item.id: item for item in context.parent.triggers}
    subjects: list[EventSubjectDraft] = []
    claims: list[AtomicClaimDraft] = []
    reports: list[OntologyValidationReport] = []
    traces: list[ExtractionStageTrace] = []
    for frame in context.parent.frames:
        trigger = trigger_by_id[frame.trigger_id]
        subject = EventSubjectDraft(
            id=event_subject_draft_id(context.parent.id, frame.id, trigger.id),
            parent_preview_id=context.parent.id,
            frame_id=frame.id,
            trigger_id=trigger.id,
        )
        frame_claims = _atomize_frame(
            context=context,
            frame=frame,
            trigger=trigger,
            subject=subject,
            target_by_segment=target_by_segment,
            attempt_by_segment=attempt_by_segment,
            candidate_ids=candidate_ids,
            interpretation_trace_by_candidate=interpretation_trace_by_candidate,
        )
        report = _validate_frame(frame, trigger, frame_claims)
        construction_trace, validation_trace = _build_traces(
            context=context,
            frame=frame,
            trigger=trigger,
            subject=subject,
            claims=frame_claims,
            report=report,
            target_by_segment=target_by_segment,
            attempt_by_segment=attempt_by_segment,
        )
        subjects.append(subject)
        claims.extend(frame_claims)
        reports.append(report)
        traces.extend((construction_trace, validation_trace))
    status, diagnostics = _terminal_status(context.parent)
    ordered_claims = tuple(sorted(claims, key=atomic_claim_sort_key))
    evidence_pairs = sorted(
        {
            (claim.evidence_target_id, claim.evidence_validation_attempt_id)
            for claim in ordered_claims
        }
    )
    preview = build_hybrid_atomic_claim_preview(
        parent_preview_id=context.parent.id,
        parent_preview_sha256=hashlib.sha256(
            canonical_hybrid_event_frame_preview_bytes(context.parent)
        ).hexdigest(),
        grounding_preview_id=context.parent.parent_preview_id,
        grounding_preview_sha256=context.parent.parent_preview_sha256,
        reference_preview_id=context.parent.reference_preview_id,
        reference_preview_sha256=context.parent.reference_preview_sha256,
        mention_preview_id=context.parent.mention_preview_id,
        mention_preview_sha256=context.parent.mention_preview_sha256,
        representation_id=context.parent.representation_id,
        paragraph_node_id=context.parent.paragraph_node_id,
        ontology_slice_id=HYBRID_EVENT_CORE_V1.id,
        ontology_slice_sha256=hybrid_event_ontology_slice_sha256(),
        event_subjects=tuple(sorted(subjects, key=lambda item: item.frame_id)),
        atomic_claims=ordered_claims,
        ontology_reports=tuple(sorted(reports, key=lambda item: item.frame_id)),
        evidence_target_ids=tuple(sorted(item[0] for item in evidence_pairs)),
        evidence_validation_attempt_ids=tuple(sorted(item[1] for item in evidence_pairs)),
        traces=tuple(sorted(traces, key=lambda item: (item.trace_run_id, item.ordinal))),
        terminal_status=status,
        diagnostics=diagnostics,
    )
    for segment_id in sorted(target_by_segment):
        target = target_by_segment[segment_id]
        attempt = attempt_by_segment[segment_id]
        _save_or_verify_evidence(target, attempt, ledger)
    digest = hybrid_atomic_claim_preview_sha256(preview)
    return HybridAtomicClaimResult(
        preview,
        digest,
        f"extraction/atomic-claim-previews/{preview.id}.json",
    )


def publish_hybrid_atomic_claim_preview(
    result: HybridAtomicClaimResult,
    archive: HybridAtomicClaimArchive,
) -> None:
    """Publish a prepared Preview only after its Ledger transaction commits."""
    payload = canonical_hybrid_atomic_claim_preview_bytes(result.preview)
    if hashlib.sha256(payload).hexdigest() != result.sha256:
        raise ValueError("HP-5 result digest changed before Archive publication.")
    archive.put_hybrid_atomic_claim_preview(result.preview, payload, result.sha256)


def _load_context(
    parent_id: str,
    ledger: HybridAtomicClaimLedger,
    archive: HybridAtomicClaimArchive,
) -> _SourceContext:
    parent = load_hybrid_event_frame_preview(parent_id, archive)
    mention_payload = archive.read_hybrid_extraction_preview(parent.mention_preview_id)
    mentions = hybrid_extraction_preview_from_bytes(mention_payload)
    if (
        canonical_hybrid_extraction_preview_bytes(mentions) != mention_payload
        or hashlib.sha256(mention_payload).hexdigest() != parent.mention_preview_sha256
    ):
        raise ValueError("HP-5 mention evidence does not match its pinned digest.")
    bundle = ledger.get_document_representation_bundle(parent.representation_id)
    if bundle is None:
        raise ValueError("HP-5 DocumentRepresentationBundle is missing.")
    document = ledger.get_document(bundle.representation.document_id)
    if document is None:
        raise ValueError("HP-5 source Document is missing.")
    node = next((item for item in bundle.nodes if item.id == parent.paragraph_node_id), None)
    if node is None or node.node_type != "paragraph":
        raise ValueError("HP-5 paragraph node is missing or not a paragraph.")
    text_view = next((item for item in bundle.text_views if item.id == node.text_view_id), None)
    if text_view is None:
        raise ValueError("HP-5 paragraph TextView is missing.")
    paragraph_text = text_view.text[node.start_char : node.end_char]
    source_segments = {
        hybrid_source_segment_id(bundle.representation.id, node.id, segment): segment
        for segment in paragraph_source_segments(paragraph_text, PARAGRAPH_SEGMENT_V3)
    }
    used_segment_ids = (
        {trigger.source_segment_id for trigger in parent.triggers}
        | {argument.support_segment_id for frame in parent.frames for argument in frame.arguments}
        | {qualifier.source_segment_id for frame in parent.frames for qualifier in frame.qualifiers}
    )
    if not used_segment_ids.issubset(source_segments):
        raise ValueError("HP-5 frame evidence references an unknown authoritative SourceSegment.")
    candidate_ids = {item.id for item in mentions.candidates}
    used_candidate_ids = {
        argument.candidate_id for frame in parent.frames for argument in frame.arguments
    } | {item for frame in parent.frames for item in frame.attribution_candidate_ids}
    if not used_candidate_ids.issubset(candidate_ids):
        raise ValueError("HP-5 frame evidence references an unknown MentionCandidate.")
    return _SourceContext(parent, mentions, bundle, document, paragraph_text, source_segments)


def _prepare_evidence(
    context: _SourceContext,
    recorded_at: datetime,
    ledger: HybridAtomicClaimLedger,
) -> tuple[dict[str, EvidenceTarget], dict[str, EvidenceValidationAttempt]]:
    node = next(
        item for item in context.bundle.nodes if item.id == context.parent.paragraph_node_id
    )
    text_view = next(item for item in context.bundle.text_views if item.id == node.text_view_id)
    trigger_by_id = {item.id: item for item in context.parent.triggers}
    used_segment_ids = (
        {trigger_by_id[frame.trigger_id].source_segment_id for frame in context.parent.frames}
        | {
            argument.support_segment_id
            for frame in context.parent.frames
            for argument in frame.arguments
        }
        | {
            qualifier.source_segment_id
            for frame in context.parent.frames
            for qualifier in frame.qualifiers
        }
    )
    targets: dict[str, EvidenceTarget] = {}
    attempts: dict[str, EvidenceValidationAttempt] = {}
    for segment_id in sorted(used_segment_ids):
        segment = context.source_segments[segment_id]
        start = node.start_char + segment.start_char
        end = node.start_char + segment.end_char
        target_id = _id(
            "etg",
            context.bundle.representation.id,
            text_view.id,
            segment_id,
            str(start),
            str(end),
            segment.exact_text,
        )
        target = EvidenceTarget(
            id=target_id,
            source_id=context.document.source_id,
            document_id=context.document.id,
            representation_id=context.bundle.representation.id,
            text_view_id=text_view.id,
            text_view_digest=text_view.content_digest,
            start_char=start,
            end_char=end,
            exact_text=segment.exact_text,
            normalization_policy=text_view.normalization_policy,
            prefix_text=text_view.text[max(0, start - 32) : start],
            suffix_text=text_view.text[end : min(len(text_view.text), end + 32)],
            node_ids=(node.id,),
            pdf_region_ids=node.source_region_ids,
            created_at=recorded_at,
        )
        existing = ledger.get_evidence_target(target.id)
        if existing is not None:
            if _without_time(existing) != _without_time(target):
                raise ValueError("HP-5 conflicts with an existing EvidenceTarget.")
            target = existing
        validate_evidence_target_record(target, ledger)
        attempt_id = _id("eva", target.id, HYBRID_ATOMIC_CLAIM_EVIDENCE_VALIDATOR)
        attempt = EvidenceValidationAttempt(
            id=attempt_id,
            evidence_target_id=target.id,
            target_digest=canonical_evidence_target_digest(target),
            validator_version=HYBRID_ATOMIC_CLAIM_EVIDENCE_VALIDATOR,
            status=EvidenceValidationAttemptStatus.SUCCEEDED,
            attempted_at=recorded_at,
        )
        existing_attempt = ledger.get_evidence_validation_attempt(attempt.id)
        if existing_attempt is not None:
            if _without_time(existing_attempt) != _without_time(attempt):
                raise ValueError("HP-5 conflicts with an existing evidence validation attempt.")
            attempt = existing_attempt
        targets[segment_id] = target
        attempts[segment_id] = attempt
    return targets, attempts


def _atomize_frame(
    *,
    context: _SourceContext,
    frame: EventFrameDraft,
    trigger: EventTriggerDraft,
    subject: EventSubjectDraft,
    target_by_segment: dict[str, EvidenceTarget],
    attempt_by_segment: dict[str, EvidenceValidationAttempt],
    candidate_ids: set[str],
    interpretation_trace_by_candidate: dict[str, str],
) -> tuple[AtomicClaimDraft, ...]:
    base_traces = tuple(sorted({frame.trace_id, trigger.trace_id}))
    claims: list[AtomicClaimDraft] = []

    def literal(
        predicate: HybridEventStructuralPredicate,
        value: str,
        segment_id: str,
    ) -> None:
        claims.append(
            _claim(
                frame,
                subject,
                predicate,
                AtomicClaimObjectKind.LITERAL,
                None,
                value,
                None,
                target_by_segment[segment_id],
                attempt_by_segment[segment_id],
                base_traces,
            )
        )

    literal(
        HybridEventStructuralPredicate.HAS_EVENT_TYPE,
        trigger.event_type_label,
        trigger.source_segment_id,
    )
    for argument in frame.arguments:
        if argument.candidate_id not in candidate_ids:
            raise ValueError("HP-5 cannot atomize an unknown MentionCandidate.")
        argument_traces = tuple(
            sorted(
                {
                    *base_traces,
                    *(
                        (interpretation_trace_by_candidate[argument.candidate_id],)
                        if argument.candidate_id in interpretation_trace_by_candidate
                        else ()
                    ),
                }
            )
        )
        claims.append(
            _claim(
                frame,
                subject,
                HybridEventStructuralPredicate.HAS_ARGUMENT,
                AtomicClaimObjectKind.MENTION_CANDIDATE,
                argument.candidate_id,
                None,
                argument.role_label,
                target_by_segment[argument.support_segment_id],
                attempt_by_segment[argument.support_segment_id],
                argument_traces,
            )
        )
    for qualifier in frame.qualifiers:
        predicate = (
            HybridEventStructuralPredicate.HAS_TIME
            if qualifier.kind is EventQualifierKind.TIME
            else HybridEventStructuralPredicate.HAS_PLACE
        )
        literal(predicate, qualifier.text, qualifier.source_segment_id)
    literal(
        HybridEventStructuralPredicate.HAS_POLARITY, frame.polarity.value, trigger.source_segment_id
    )
    literal(
        HybridEventStructuralPredicate.HAS_MODALITY, frame.modality.value, trigger.source_segment_id
    )
    if frame.source_narrator_attribution:
        claims.append(
            _claim(
                frame,
                subject,
                HybridEventStructuralPredicate.ACCORDING_TO,
                AtomicClaimObjectKind.SOURCE,
                context.document.source_id,
                None,
                None,
                target_by_segment[trigger.source_segment_id],
                attempt_by_segment[trigger.source_segment_id],
                base_traces,
            )
        )
    return tuple(sorted(claims, key=atomic_claim_sort_key))


def _claim(
    frame: EventFrameDraft,
    subject: EventSubjectDraft,
    predicate: HybridEventStructuralPredicate,
    object_kind: AtomicClaimObjectKind,
    object_reference_id: str | None,
    object_value: str | None,
    role_label: str | None,
    target: EvidenceTarget,
    attempt: EvidenceValidationAttempt,
    source_trace_ids: tuple[str, ...],
) -> AtomicClaimDraft:
    claim_id = atomic_claim_draft_id(
        frame_id=frame.id,
        event_subject_id=subject.id,
        predicate=predicate,
        object_kind=object_kind,
        object_reference_id=object_reference_id,
        object_value=object_value,
        role_label=role_label,
        evidence_target_id=target.id,
        evidence_validation_attempt_id=attempt.id,
        source_trace_ids=source_trace_ids,
    )
    return AtomicClaimDraft(
        id=claim_id,
        frame_id=frame.id,
        event_subject_id=subject.id,
        predicate=predicate,
        object_kind=object_kind,
        object_reference_id=object_reference_id,
        object_value=object_value,
        role_label=role_label,
        evidence_target_id=target.id,
        evidence_validation_attempt_id=attempt.id,
        source_trace_ids=source_trace_ids,
    )


def _validate_frame(
    frame: EventFrameDraft,
    trigger: EventTriggerDraft,
    claims: tuple[AtomicClaimDraft, ...],
) -> OntologyValidationReport:
    findings: list[OntologyValidationFinding] = []
    event_claim = next(
        item for item in claims if item.predicate is HybridEventStructuralPredicate.HAS_EVENT_TYPE
    )
    if trigger.event_type_label not in HYBRID_EVENT_CORE_V1.core_event_labels:
        findings.append(
            OntologyValidationFinding(
                code="unmapped_event_type",
                frame_id=frame.id,
                claim_id=event_claim.id,
                field_path="trigger.event_type_label",
                proposed_value=trigger.event_type_label,
            )
        )
    argument_claim_by_identity = {
        (item.object_reference_id, item.role_label): item
        for item in claims
        if item.predicate is HybridEventStructuralPredicate.HAS_ARGUMENT
    }
    for index, argument in enumerate(frame.arguments):
        claim = argument_claim_by_identity[(argument.candidate_id, argument.role_label)]
        if argument.role_label not in HYBRID_EVENT_CORE_V1.core_role_labels:
            findings.append(
                OntologyValidationFinding(
                    code="unmapped_argument_role",
                    frame_id=frame.id,
                    claim_id=claim.id,
                    field_path=f"arguments[{index}].role_label",
                    proposed_value=argument.role_label,
                )
            )
    for index, candidate_id in enumerate(frame.attribution_candidate_ids):
        findings.append(
            OntologyValidationFinding(
                code="attribution_support_missing",
                frame_id=frame.id,
                field_path=f"attribution_candidate_ids[{index}]",
                proposed_value=candidate_id,
            )
        )
    ordered_findings = tuple(
        sorted(
            findings,
            key=lambda item: (
                item.code,
                item.field_path,
                item.proposed_value,
                item.claim_id or "",
            ),
        )
    )
    status = (
        OntologyValidationStatus.NONCONFORMANT
        if ordered_findings
        else OntologyValidationStatus.CONFORMANT
    )
    claim_ids = tuple(sorted(item.id for item in claims))
    ontology_digest = hybrid_event_ontology_slice_sha256()
    report_id = ontology_validation_report_id(
        frame_id=frame.id,
        ontology_slice_id=HYBRID_EVENT_CORE_V1.id,
        ontology_slice_sha256=ontology_digest,
        claim_ids=claim_ids,
        status=status,
        findings=ordered_findings,
    )
    return OntologyValidationReport(
        id=report_id,
        frame_id=frame.id,
        ontology_slice_id=HYBRID_EVENT_CORE_V1.id,
        ontology_slice_sha256=ontology_digest,
        claim_ids=claim_ids,
        status=status,
        findings=ordered_findings,
    )


def _build_traces(
    *,
    context: _SourceContext,
    frame: EventFrameDraft,
    trigger: EventTriggerDraft,
    subject: EventSubjectDraft,
    claims: tuple[AtomicClaimDraft, ...],
    report: OntologyValidationReport,
    target_by_segment: dict[str, EvidenceTarget],
    attempt_by_segment: dict[str, EvidenceValidationAttempt],
) -> tuple[ExtractionStageTrace, ExtractionStageTrace]:
    segment = context.source_segments[trigger.source_segment_id]
    frame_segment_ids = {
        trigger.source_segment_id,
        *(item.support_segment_id for item in frame.arguments),
        *(item.source_segment_id for item in frame.qualifiers),
    }
    source_records = {
        segment_id: {
            "source_segment_id": segment_id,
            "start_char": item.start_char,
            "end_char": item.end_char,
            "exact_text": item.exact_text,
        }
        for segment_id, item in sorted(context.source_segments.items())
        if segment_id in frame_segment_ids
    }
    construction = build_extraction_stage_trace(
        trace_run_id=f"hp5:{frame.id}",
        ordinal=0,
        stage_id="hybrid_atomic_claim_construction",
        stage_version="1",
        producer_id="kotekomi:deterministic",
        source_segment_id=trigger.source_segment_id,
        source_text_sha256=hashlib.sha256(segment.exact_text.encode()).hexdigest(),
        configuration={"policy_id": "hybrid_atomic_claim_v1"},
        input_payload=cast(
            dict[str, JsonValue],
            {
                "frame": frame.model_dump(mode="json"),
                "trigger": trigger.model_dump(mode="json"),
                "source_segments": source_records,
            },
        ),
        output_payload=cast(
            dict[str, JsonValue],
            {
                "event_subject": subject.model_dump(mode="json"),
                "claims": [item.model_dump(mode="json") for item in claims],
                "evidence_targets": [
                    target_by_segment[item].model_dump(mode="json", exclude={"created_at"})
                    for item in sorted(frame_segment_ids)
                ],
                "evidence_validation_attempts": [
                    attempt_by_segment[item].model_dump(mode="json", exclude={"attempted_at"})
                    for item in sorted(frame_segment_ids)
                ],
            },
        ),
        status=ExtractionStageStatus.COMPLETED,
        input_record_ids=tuple(sorted({context.parent.id, frame.id, trigger.id})),
    )
    validation = build_extraction_stage_trace(
        trace_run_id=f"hp5:{frame.id}",
        ordinal=1,
        stage_id="hybrid_ontology_validation",
        stage_version="1",
        producer_id="kotekomi:deterministic",
        source_segment_id=trigger.source_segment_id,
        source_text_sha256=hashlib.sha256(segment.exact_text.encode()).hexdigest(),
        configuration={
            "ontology_slice_id": HYBRID_EVENT_CORE_V1.id,
            "ontology_slice_sha256": hybrid_event_ontology_slice_sha256(),
        },
        input_payload=cast(
            dict[str, JsonValue],
            {
                "ontology_slice": HYBRID_EVENT_CORE_V1.model_dump(mode="json"),
                "claims": [item.model_dump(mode="json") for item in claims],
            },
        ),
        output_payload=cast(dict[str, JsonValue], {"report": report.model_dump(mode="json")}),
        status=ExtractionStageStatus.COMPLETED,
        parent_trace_ids=(construction.id,),
        input_record_ids=tuple(sorted(item.id for item in claims)),
    )
    return construction, validation


def _save_or_verify_evidence(
    target: EvidenceTarget,
    attempt: EvidenceValidationAttempt,
    ledger: HybridAtomicClaimLedger,
) -> None:
    existing_target = ledger.get_evidence_target(target.id)
    if existing_target is None:
        ledger.save_evidence_target(target)
    elif _without_time(existing_target) != _without_time(target):
        raise ValueError("HP-5 EvidenceTarget changed before persistence.")
    existing_attempt = ledger.get_evidence_validation_attempt(attempt.id)
    if existing_attempt is None:
        ledger.save_evidence_validation_attempt(attempt)
    elif _without_time(existing_attempt) != _without_time(attempt):
        raise ValueError("HP-5 validation attempt changed before persistence.")
    replay = verify_evidence_target(target, attempt, ledger)
    if not replay.valid:
        raise ValueError(f"HP-5 EvidenceTarget failed replay: {replay.error_message}")


def _terminal_status(
    parent: HybridEventFramePreview,
) -> tuple[HybridAtomicClaimStatus, tuple[str, ...]]:
    if parent.terminal_status is HybridEventFrameStatus.COMPLETE:
        return HybridAtomicClaimStatus.COMPLETE, ()
    if parent.frames:
        return HybridAtomicClaimStatus.PARTIAL, (f"hp4_status:{parent.terminal_status.value}",)
    return HybridAtomicClaimStatus.BLOCKED, (
        f"hp4_status:{parent.terminal_status.value}",
        "no_valid_event_frames",
    )


def _without_time(
    record: EvidenceTarget | EvidenceValidationAttempt,
) -> dict[str, JsonValue]:
    return cast(
        dict[str, JsonValue],
        record.model_dump(mode="json", exclude={"created_at", "attempted_at"}),
    )


def _id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("\x1f".join(parts).encode()).hexdigest()
    return f"{prefix}_{digest[:24]}"
