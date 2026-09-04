"""HP-7 deterministic proposal planning over immutable HP-6 evidence."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal, Protocol, Self, cast

from kotekomi_domain import (
    HYBRID_EVENT_SEMANTICS_V1,
    Actor,
    AssertionType,
    AttributionBasis,
    Document,
    DocumentRepresentationBundle,
    EpistemicScope,
    Event,
    EvidenceNecessity,
    EvidencePolarity,
    EvidenceTarget,
    EvidenceValidationAttempt,
    HybridEventStructuralPredicate,
    Organization,
    ProposedAssertion,
    ProposedChange,
    ProvenanceActivity,
    ReviewStatus,
    Source,
    SourceAuthority,
    UpperRole,
)
from kotekomi_domain.models import JsonValue
from pydantic import BaseModel, ConfigDict, Field, model_validator

from kotekomi_application.extraction_stage_trace import (
    ExtractionStageStatus,
    ExtractionStageTrace,
    build_extraction_stage_trace,
    validate_extraction_stage_trace_chain,
)
from kotekomi_application.hybrid_atomic_claim_preview import load_hybrid_atomic_claim_preview
from kotekomi_application.hybrid_document_references import (
    HybridReferencePreview,
    ReferenceStatus,
    canonical_hybrid_reference_preview_bytes,
    hybrid_reference_preview_from_bytes,
)
from kotekomi_application.hybrid_event_frame_preview import load_hybrid_event_frame_preview
from kotekomi_application.hybrid_event_semantics import (
    EventArgumentAssignmentDraft,
    EventArgumentTargetDraft,
    EventSemanticDraft,
    HybridEventSemanticsPreview,
    SemanticCoverageGap,
    SemanticCoverageGapCode,
    SemanticStatement,
    SemanticSupportJudgment,
    SupportOutcome,
    canonical_hybrid_event_semantics_preview_bytes,
)
from kotekomi_application.hybrid_event_semantics_preview import (
    HybridEventSemanticsArchive,
    HybridEventSemanticsLedger,
    load_hybrid_event_semantics_preview,
)
from kotekomi_application.hybrid_mention_interpretation import (
    ContextualKind,
    DiscourseRole,
    HybridExtractionPreview,
    MentionCandidate,
    Referentiality,
    canonical_hybrid_extraction_preview_bytes,
    hybrid_extraction_preview_from_bytes,
)

HYBRID_PROPOSAL_POLICY_ID = "hybrid_proposed_change_v1"
HYBRID_PROPOSAL_ACTIVITY_TYPE = "hybrid_proposal_batch_submitted"
HYBRID_PROPOSAL_AGENT = "kotekomi_application"
_SHA256 = r"^[a-f0-9]{64}$"


class ProposalDisposition(StrEnum):
    PROPOSED = "proposed"
    HELD = "held"


class ProposalAdmissionReason(StrEnum):
    MISSING_GOVERNED_ATTRIBUTION = "missing_governed_attribution"
    MISSING_REQUIRED_ROLE = "missing_required_role"
    MISSING_SUPPORT_JUDGMENT = "missing_support_judgment"
    NON_DIRECT_SUPPORT = "non_direct_support"
    REPEATED_SUPPORT_JUDGMENT = "repeated_support_judgment"
    TARGET_EVENT_HELD = "target_event_held"
    UNMAPPED_FRAME = "unmapped_frame"


_HARD_GAP_REASONS = {
    SemanticCoverageGapCode.MISSING_GOVERNED_ATTRIBUTION: (
        ProposalAdmissionReason.MISSING_GOVERNED_ATTRIBUTION
    ),
    SemanticCoverageGapCode.MISSING_REQUIRED_ROLE: ProposalAdmissionReason.MISSING_REQUIRED_ROLE,
    SemanticCoverageGapCode.UNMAPPED_FRAME: ProposalAdmissionReason.UNMAPPED_FRAME,
}


class PlannedProposedChange(BaseModel):
    """One deterministic ProposedChange body before operational timestamps."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: Annotated[str, Field(pattern=r"^pcg_[a-f0-9]{24}$")]
    proposed_json: dict[str, JsonValue]
    source_id: Annotated[str, Field(min_length=1)]
    document_id: Annotated[str, Field(min_length=1)]
    provenance_activity_id: Annotated[str, Field(pattern=r"^prv_[a-f0-9]{24}$")]

    @model_validator(mode="after")
    def validate_identity(self) -> Self:
        expected = _id(
            "pcg",
            self.provenance_activity_id,
            _canonical_json(self.proposed_json),
        )
        if self.id != expected:
            raise ValueError("PlannedProposedChange ID does not match its body.")
        return self


class ProposalAdmissionDecision(BaseModel):
    """One deterministic disposition for one HP-6 event."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: Annotated[str, Field(pattern=r"^pad_[a-f0-9]{24}$")]
    event_semantic_id: Annotated[str, Field(pattern=r"^esn_[a-f0-9]{24}$")]
    disposition: ProposalDisposition
    reason_codes: tuple[ProposalAdmissionReason, ...] = ()
    advisory_gap_ids: tuple[Annotated[str, Field(pattern=r"^scg_[a-f0-9]{24}$")], ...] = ()
    statement_ids: tuple[Annotated[str, Field(pattern=r"^sst_[a-f0-9]{24}$")], ...] = ()
    judgment_ids: tuple[Annotated[str, Field(pattern=r"^spj_[a-f0-9]{24}$")], ...] = ()
    model_run_ids: tuple[Annotated[str, Field(min_length=1)], ...] = ()
    source_trace_ids: tuple[Annotated[str, Field(pattern=r"^xst_[a-f0-9]{24}$")], ...] = ()
    proposed_change_ids: tuple[Annotated[str, Field(pattern=r"^pcg_[a-f0-9]{24}$")], ...] = ()

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        for label, values in (
            ("reason codes", tuple(item.value for item in self.reason_codes)),
            ("advisory gap IDs", self.advisory_gap_ids),
            ("statement IDs", self.statement_ids),
            ("judgment IDs", self.judgment_ids),
            ("model run IDs", self.model_run_ids),
            ("source trace IDs", self.source_trace_ids),
            ("ProposedChange IDs", self.proposed_change_ids),
        ):
            _ordered_distinct(label, values)
        if self.disposition is ProposalDisposition.PROPOSED:
            if self.reason_codes or not self.proposed_change_ids:
                raise ValueError("A proposed admission requires changes and no hold reason.")
        elif not self.reason_codes or self.proposed_change_ids:
            raise ValueError("A held admission requires reasons and no changes.")
        expected = _id(
            "pad",
            self.event_semantic_id,
            self.disposition.value,
            *(item.value for item in self.reason_codes),
            *self.advisory_gap_ids,
            *self.statement_ids,
            *self.judgment_ids,
            *self.model_run_ids,
            *self.source_trace_ids,
            *self.proposed_change_ids,
        )
        if self.id != expected:
            raise ValueError("ProposalAdmissionDecision ID does not match its contents.")
        return self


class HybridProposalPlan(BaseModel):
    """Immutable derived HP-7 data-in/data-out plan."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["hybrid_proposal_plan_v1"] = "hybrid_proposal_plan_v1"
    id: Annotated[str, Field(pattern=r"^hpp_[a-f0-9]{24}$")]
    parent_preview_id: Annotated[str, Field(pattern=r"^hsp_[a-f0-9]{24}$")]
    parent_preview_sha256: Annotated[str, Field(pattern=_SHA256)]
    representation_id: Annotated[str, Field(min_length=1)]
    paragraph_node_id: Annotated[str, Field(min_length=1)]
    policy_id: Literal["hybrid_proposed_change_v1"] = HYBRID_PROPOSAL_POLICY_ID
    provenance_activity_id: Annotated[str, Field(pattern=r"^prv_[a-f0-9]{24}$")]
    decisions: tuple[ProposalAdmissionDecision, ...]
    proposed_changes: tuple[PlannedProposedChange, ...] = ()
    traces: tuple[ExtractionStageTrace, ...]
    diagnostics: tuple[Annotated[str, Field(min_length=1)], ...] = ()

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        _distinct("decision IDs", tuple(item.id for item in self.decisions))
        _ordered_distinct(
            "planned ProposedChange IDs",
            tuple(item.id for item in self.proposed_changes),
        )
        _ordered_distinct("diagnostics", self.diagnostics)
        if len(self.decisions) != len(self.traces):
            raise ValueError("Every HP-7 admission decision requires one stage trace.")
        planned_ids = {item.id for item in self.proposed_changes}
        decision_ids = {
            item_id for decision in self.decisions for item_id in decision.proposed_change_ids
        }
        if planned_ids != decision_ids:
            raise ValueError("HP-7 decisions and planned ProposedChanges disagree.")
        if any(
            item.provenance_activity_id != self.provenance_activity_id
            for item in self.proposed_changes
        ):
            raise ValueError("HP-7 planned changes must share one provenance activity.")
        for trace in self.traces:
            validate_extraction_stage_trace_chain((trace,))
        if self.id != _plan_id(self.model_dump(mode="json", exclude={"id"})):
            raise ValueError("HybridProposalPlan ID does not match its contents.")
        return self


class HybridProposalLedger(Protocol):
    def get_source(self, record_id: str) -> Source | None: ...

    def get_document(self, record_id: str) -> Document | None: ...

    def get_document_representation_bundle(
        self, record_id: str
    ) -> DocumentRepresentationBundle | None: ...

    def get_evidence_target(self, record_id: str) -> EvidenceTarget | None: ...

    def get_evidence_validation_attempt(
        self, record_id: str
    ) -> EvidenceValidationAttempt | None: ...

    def get_actor(self, record_id: str) -> Actor | None: ...

    def get_organization(self, record_id: str) -> Organization | None: ...

    def get_event(self, record_id: str) -> Event | None: ...

    def get_proposed_change(self, record_id: str) -> ProposedChange | None: ...

    def get_provenance_activity(self, record_id: str) -> ProvenanceActivity | None: ...

    def commit_hybrid_proposal_batch(
        self,
        *,
        provenance_activity: ProvenanceActivity,
        proposed_changes: tuple[ProposedChange, ...],
    ) -> None: ...


class HybridProposalArchive(HybridEventSemanticsArchive, Protocol):
    def put_hybrid_proposal_plan(
        self,
        plan: HybridProposalPlan,
        payload: bytes,
        expected_sha256: str,
    ) -> object: ...

    def read_hybrid_proposal_plan(self, plan_id: str) -> bytes: ...


@dataclass(frozen=True)
class HybridProposalResult:
    plan: HybridProposalPlan
    sha256: str
    archive_path: str
    publication_disposition: str


@dataclass(frozen=True)
class _Lineage:
    preview: HybridEventSemanticsPreview
    hp5_preview_id: str
    hp4_preview_id: str
    hp3_preview_id: str
    mentions: HybridExtractionPreview
    references: HybridReferencePreview
    source_id: str
    document_id: str
    evidence_by_id: dict[str, EvidenceTarget]
    attempt_by_evidence_id: dict[str, EvidenceValidationAttempt]


@dataclass(frozen=True)
class _TypedTarget:
    record_type: Literal["Actor", "Organization"]
    record_id: str
    record_json: dict[str, JsonValue]
    source_target: EvidenceTarget


def build_hybrid_proposal_plan_record(
    *,
    parent_preview_id: str,
    parent_preview_sha256: str,
    representation_id: str,
    paragraph_node_id: str,
    provenance_activity_id: str,
    decisions: tuple[ProposalAdmissionDecision, ...] = (),
    proposed_changes: tuple[PlannedProposedChange, ...] = (),
    traces: tuple[ExtractionStageTrace, ...] = (),
    diagnostics: tuple[str, ...] = (),
) -> HybridProposalPlan:
    """Construct one content-addressed Plan from already validated components."""
    identity_payload: dict[str, JsonValue] = {
        "schema_version": "hybrid_proposal_plan_v1",
        "parent_preview_id": parent_preview_id,
        "parent_preview_sha256": parent_preview_sha256,
        "representation_id": representation_id,
        "paragraph_node_id": paragraph_node_id,
        "policy_id": HYBRID_PROPOSAL_POLICY_ID,
        "provenance_activity_id": provenance_activity_id,
        "decisions": [cast(JsonValue, item.model_dump(mode="json")) for item in decisions],
        "proposed_changes": [
            cast(JsonValue, item.model_dump(mode="json")) for item in proposed_changes
        ],
        "traces": [cast(JsonValue, item.model_dump(mode="json")) for item in traces],
        "diagnostics": list(diagnostics),
    }
    return HybridProposalPlan.model_validate(
        {
            **identity_payload,
            "id": _plan_id(identity_payload),
            "decisions": decisions,
            "proposed_changes": proposed_changes,
            "traces": traces,
            "diagnostics": diagnostics,
        }
    )


def build_hybrid_proposal_plan(
    preview_id: str,
    ledger: HybridProposalLedger,
    archive: HybridProposalArchive,
) -> HybridProposalPlan:
    """Build one deterministic plan without changing proposal or accepted state."""
    lineage = _load_lineage(preview_id, ledger, archive)
    preview = lineage.preview
    provenance_id = _id("prv", HYBRID_PROPOSAL_ACTIVITY_TYPE, preview.id)
    event_ids = {
        item.event_subject_id: _id("evt", preview.id, item.id) for item in preview.semantic_events
    }
    reasons_by_event = _admission_reasons(preview)
    changed = True
    while changed:
        changed = False
        for event in preview.semantic_events:
            for assignment in _event_assignments(preview, event):
                target = _target(preview, assignment.target_id)
                if target.kind.value != "event_subject" or target.reference_id is None:
                    continue
                if (
                    target.reference_id not in event_ids
                    or reasons_by_event.get(target.reference_id)
                ) and (
                    ProposalAdmissionReason.TARGET_EVENT_HELD
                    not in reasons_by_event[event.event_subject_id]
                ):
                    reasons_by_event[event.event_subject_id].add(
                        ProposalAdmissionReason.TARGET_EVENT_HELD
                    )
                    changed = True

    planned_by_id: dict[str, PlannedProposedChange] = {}
    decisions: list[ProposalAdmissionDecision] = []
    traces: list[ExtractionStageTrace] = []
    for event in preview.semantic_events:
        gaps = _event_gaps(preview, event)
        statements = _event_statements(preview, event)
        judgments = _event_judgments(preview, statements)
        reasons = tuple(
            sorted(reasons_by_event[event.event_subject_id], key=lambda item: item.value)
        )
        event_changes: tuple[PlannedProposedChange, ...] = ()
        if not reasons:
            event_changes = _build_event_changes(
                lineage=lineage,
                event=event,
                event_ids=event_ids,
                provenance_activity_id=provenance_id,
            )
            for item in event_changes:
                existing = planned_by_id.get(item.id)
                if existing is not None and existing != item:
                    raise ValueError("HP-7 produced conflicting bodies for one proposal identity.")
                planned_by_id[item.id] = item
        advisory_ids = tuple(sorted(item.id for item in gaps if item.code not in _HARD_GAP_REASONS))
        proposal_ids = tuple(sorted(item.id for item in event_changes))
        source_trace_ids, model_run_ids = _event_execution_lineage(
            preview,
            event,
            _event_assignments(preview, event),
            statements,
            judgments,
        )
        disposition = ProposalDisposition.HELD if reasons else ProposalDisposition.PROPOSED
        decision = ProposalAdmissionDecision(
            id=_decision_id(
                event=event,
                disposition=disposition,
                reasons=reasons,
                advisory_gap_ids=advisory_ids,
                statements=statements,
                judgments=judgments,
                model_run_ids=model_run_ids,
                source_trace_ids=source_trace_ids,
                proposal_ids=proposal_ids,
            ),
            event_semantic_id=event.id,
            disposition=disposition,
            reason_codes=reasons,
            advisory_gap_ids=advisory_ids,
            statement_ids=tuple(sorted(item.id for item in statements)),
            judgment_ids=tuple(sorted(item.id for item in judgments)),
            model_run_ids=model_run_ids,
            source_trace_ids=source_trace_ids,
            proposed_change_ids=proposal_ids,
        )
        decisions.append(decision)
        support_target = lineage.evidence_by_id[event.support_evidence_target_id]
        traces.append(
            build_extraction_stage_trace(
                trace_run_id=f"hp7:{preview.id}:{event.id}",
                ordinal=0,
                stage_id="hybrid_proposal_admission",
                stage_version=HYBRID_PROPOSAL_POLICY_ID,
                producer_id="kotekomi_application",
                source_segment_id=_event_source_segment_id(preview, event),
                source_text_sha256=hashlib.sha256(support_target.exact_text.encode()).hexdigest(),
                configuration=cast(
                    dict[str, JsonValue],
                    {
                        "hard_gap_codes": sorted(item.value for item in _HARD_GAP_REASONS),
                        "required_support": SupportOutcome.DIRECTLY_SUPPORTED.value,
                    },
                ),
                input_payload={
                    "event": cast(JsonValue, event.model_dump(mode="json")),
                    "gaps": [cast(JsonValue, item.model_dump(mode="json")) for item in gaps],
                    "statements": [
                        cast(JsonValue, item.model_dump(mode="json")) for item in statements
                    ],
                    "judgments": [
                        cast(JsonValue, item.model_dump(mode="json")) for item in judgments
                    ],
                },
                output_payload={
                    "decision": cast(JsonValue, decision.model_dump(mode="json")),
                    "proposed_changes": [
                        cast(JsonValue, item.model_dump(mode="json")) for item in event_changes
                    ],
                },
                status=(
                    ExtractionStageStatus.REJECTED if reasons else ExtractionStageStatus.COMPLETED
                ),
                input_record_ids=tuple(
                    sorted(
                        {
                            event.id,
                            *(item.id for item in gaps),
                            *(item.id for item in statements),
                            *(item.id for item in judgments),
                        }
                    )
                ),
                execution_record_ids=model_run_ids,
                diagnostics=tuple(item.value for item in reasons),
            )
        )
    proposed_changes = tuple(sorted(planned_by_id.values(), key=lambda item: item.id))
    decisions_tuple = tuple(decisions)
    traces_tuple = tuple(traces)
    materialized_subject_ids = {item.event_subject_id for item in preview.semantic_events}
    diagnostics = tuple(
        sorted(
            f"unmaterialized_event_subject:{item.event_subject_id}:{item.code.value}:{item.id}"
            for item in preview.gaps
            if item.event_subject_id not in materialized_subject_ids
        )
    )
    return build_hybrid_proposal_plan_record(
        parent_preview_id=preview.id,
        parent_preview_sha256=hashlib.sha256(
            canonical_hybrid_event_semantics_preview_bytes(preview)
        ).hexdigest(),
        representation_id=preview.representation_id,
        paragraph_node_id=preview.paragraph_node_id,
        provenance_activity_id=provenance_id,
        decisions=decisions_tuple,
        proposed_changes=proposed_changes,
        traces=traces_tuple,
        diagnostics=diagnostics,
    )


def publish_hybrid_proposal_plan(
    plan: HybridProposalPlan,
    archive: HybridProposalArchive,
) -> tuple[str, str]:
    payload = canonical_hybrid_proposal_plan_bytes(plan)
    digest = hashlib.sha256(payload).hexdigest()
    archive.put_hybrid_proposal_plan(plan, payload, digest)
    return digest, f"extraction/proposal-plans/{plan.id}.json"


def submit_hybrid_proposal_plan(
    plan: HybridProposalPlan,
    *,
    submitted_at: datetime,
    ledger: HybridProposalLedger,
) -> str:
    """Atomically publish a new pending batch or prove exact prior publication."""
    return submit_planned_proposal_batch(
        proposed_changes=plan.proposed_changes,
        provenance_activity_id=plan.provenance_activity_id,
        activity_type=HYBRID_PROPOSAL_ACTIVITY_TYPE,
        input_ids=(plan.parent_preview_id,),
        submitted_at=submitted_at,
        ledger=ledger,
        error_label="HP-7",
    )


def submit_planned_proposal_batch(
    *,
    proposed_changes: tuple[PlannedProposedChange, ...],
    provenance_activity_id: str,
    activity_type: str,
    input_ids: tuple[str, ...],
    submitted_at: datetime,
    ledger: HybridProposalLedger,
    error_label: str,
) -> str:
    """Atomically publish a validated proposal batch or prove exact prior publication."""
    validate_planned_proposed_changes(proposed_changes, ledger, error_label=error_label)
    existing_activity = ledger.get_provenance_activity(provenance_activity_id)
    existing_changes = tuple(
        item
        for planned in proposed_changes
        if (item := ledger.get_proposed_change(planned.id)) is not None
    )
    if existing_activity is not None or existing_changes:
        if existing_activity is None or len(existing_changes) != len(proposed_changes):
            raise ValueError(f"{error_label} found a partially published proposal batch.")
        _validate_existing_publication(
            proposed_changes=proposed_changes,
            provenance_activity_id=provenance_activity_id,
            activity_type=activity_type,
            input_ids=input_ids,
            activity=existing_activity,
            changes=existing_changes,
            error_label=error_label,
        )
        return "reused"
    activity = ProvenanceActivity(
        id=provenance_activity_id,
        activity_type=activity_type,
        agent=HYBRID_PROPOSAL_AGENT,
        input_ids=input_ids,
        output_ids=tuple(item.id for item in proposed_changes),
        occurred_at=submitted_at,
    )
    changes = tuple(
        ProposedChange(
            id=item.id,
            review_status=ReviewStatus.PENDING,
            proposed_json=item.proposed_json,
            source_id=item.source_id,
            document_id=item.document_id,
            provenance_activity_id=item.provenance_activity_id,
            created_at=submitted_at,
            updated_at=submitted_at,
        )
        for item in proposed_changes
    )
    ledger.commit_hybrid_proposal_batch(
        provenance_activity=activity,
        proposed_changes=changes,
    )
    return "created"


def validate_planned_proposed_changes(
    proposed_changes: tuple[PlannedProposedChange, ...],
    ledger: HybridProposalLedger,
    *,
    error_label: str = "Proposal batch",
) -> None:
    """Validate typed proposal bodies and all planned-or-accepted references."""
    planned_records: dict[str, str] = {}
    for change in proposed_changes:
        record_type = change.proposed_json.get("record_type")
        record = change.proposed_json.get("record")
        if not isinstance(record_type, str) or not isinstance(record, dict):
            raise ValueError(f"{error_label} proposal is missing its typed record body.")
        record_id = record.get("id")
        if not isinstance(record_id, str) or not record_id:
            raise ValueError(f"{error_label} proposal record is missing its identity.")
        if record_id in planned_records:
            raise ValueError(f"{error_label} repeats one record identity.")
        planned_records[record_id] = record_type
    for change in proposed_changes:
        record_type = cast(str, change.proposed_json["record_type"])
        record = cast(dict[str, JsonValue], change.proposed_json["record"])
        if record_type == "Actor":
            Actor.model_validate_json(_canonical_json(record))
        elif record_type == "Organization":
            Organization.model_validate_json(_canonical_json(record))
        elif record_type == "Event":
            event = Event.model_validate_json(_canonical_json(record))
            for actor_id in event.participant_actor_ids:
                _require_planned_or_accepted(
                    actor_id,
                    "Actor",
                    planned_records,
                    ledger.get_actor,
                    error_label,
                )
            for organization_id in event.participant_organization_ids:
                _require_planned_or_accepted(
                    organization_id,
                    "Organization",
                    planned_records,
                    ledger.get_organization,
                    error_label,
                )
        elif record_type == "Assertion":
            assertion = ProposedAssertion.model_validate_json(_canonical_json(record))
            _require_entity_reference(
                assertion.subject_entity_id,
                planned_records,
                ledger,
                error_label,
            )
            if assertion.object_entity_id is not None:
                _require_entity_reference(
                    assertion.object_entity_id,
                    planned_records,
                    ledger,
                    error_label,
                )
            if any(
                ledger.get_evidence_target(item) is None for item in assertion.evidence_target_ids
            ):
                raise ValueError(f"{error_label} Assertion references missing source evidence.")
        else:
            raise ValueError(f"{error_label} does not support record type: {record_type}")


def _require_entity_reference(
    record_id: str,
    planned_records: dict[str, str],
    ledger: HybridProposalLedger,
    error_label: str,
) -> None:
    if record_id.startswith("act_"):
        _require_planned_or_accepted(
            record_id,
            "Actor",
            planned_records,
            ledger.get_actor,
            error_label,
        )
    elif record_id.startswith("org_"):
        _require_planned_or_accepted(
            record_id,
            "Organization",
            planned_records,
            ledger.get_organization,
            error_label,
        )
    elif record_id.startswith("evt_"):
        _require_planned_or_accepted(
            record_id,
            "Event",
            planned_records,
            ledger.get_event,
            error_label,
        )
    else:
        raise ValueError(
            f"{error_label} Assertion uses an unsupported entity identity: {record_id}"
        )


def _require_planned_or_accepted(
    record_id: str,
    expected_type: str,
    planned_records: dict[str, str],
    accepted_lookup: Callable[[str], object | None],
    error_label: str,
) -> None:
    planned_type = planned_records.get(record_id)
    if planned_type is not None:
        if planned_type != expected_type:
            raise ValueError(f"{error_label} reference has the wrong record type.")
        return
    if accepted_lookup(record_id) is None:
        raise ValueError(f"{error_label} references missing {expected_type}: {record_id}")


def run_hybrid_proposal_submission(
    *,
    preview_id: str,
    submitted_at: datetime,
    ledger: HybridProposalLedger,
    archive: HybridProposalArchive,
) -> HybridProposalResult:
    plan = build_hybrid_proposal_plan(preview_id, ledger, archive)
    digest, archive_path = publish_hybrid_proposal_plan(plan, archive)
    disposition = submit_hybrid_proposal_plan(plan, submitted_at=submitted_at, ledger=ledger)
    return HybridProposalResult(plan, digest, archive_path, disposition)


def canonical_hybrid_proposal_plan_bytes(plan: HybridProposalPlan) -> bytes:
    return (_canonical_json(plan.model_dump(mode="json")) + "\n").encode()


def hybrid_proposal_plan_from_bytes(payload: bytes) -> HybridProposalPlan:
    try:
        plan = HybridProposalPlan.model_validate_json(payload)
    except (ValueError, json.JSONDecodeError) as error:
        raise ValueError("HybridProposalPlan is not valid JSON.") from error
    if canonical_hybrid_proposal_plan_bytes(plan) != payload:
        raise ValueError("HybridProposalPlan does not use canonical encoding.")
    return plan


def load_hybrid_proposal_plan(
    plan_id: str,
    ledger: HybridProposalLedger,
    archive: HybridProposalArchive,
) -> HybridProposalPlan:
    """Reload a canonical Plan and replay the parent and source evidence it records."""
    payload = archive.read_hybrid_proposal_plan(plan_id)
    plan = hybrid_proposal_plan_from_bytes(payload)
    if plan.id != plan_id or canonical_hybrid_proposal_plan_bytes(plan) != payload:
        raise ValueError("HP-7 Plan identity or canonical encoding is invalid.")
    rebuilt = build_hybrid_proposal_plan(plan.parent_preview_id, ledger, archive)
    if rebuilt != plan:
        raise ValueError("HP-7 Plan no longer matches its pinned parent evidence.")
    return plan


def _load_lineage(
    preview_id: str,
    ledger: HybridProposalLedger,
    archive: HybridProposalArchive,
) -> _Lineage:
    replay_ledger = cast(HybridEventSemanticsLedger, ledger)
    preview = load_hybrid_event_semantics_preview(preview_id, replay_ledger, archive)
    hp5 = load_hybrid_atomic_claim_preview(preview.parent_preview_id, replay_ledger, archive)
    hp4 = load_hybrid_event_frame_preview(hp5.parent_preview_id, archive)
    mention_payload = archive.read_hybrid_extraction_preview(hp5.mention_preview_id)
    mentions = hybrid_extraction_preview_from_bytes(mention_payload)
    if (
        mentions.id != hp5.mention_preview_id
        or canonical_hybrid_extraction_preview_bytes(mentions) != mention_payload
        or hashlib.sha256(mention_payload).hexdigest() != hp5.mention_preview_sha256
    ):
        raise ValueError("HP-7 HP-1 lineage does not match its pinned identity.")
    reference_payload = archive.read_hybrid_reference_preview(hp5.reference_preview_id)
    references = hybrid_reference_preview_from_bytes(reference_payload)
    if (
        references.id != hp5.reference_preview_id
        or canonical_hybrid_reference_preview_bytes(references) != reference_payload
        or hashlib.sha256(reference_payload).hexdigest() != hp5.reference_preview_sha256
    ):
        raise ValueError("HP-7 HP-2 lineage does not match its pinned identity.")
    bundle = ledger.get_document_representation_bundle(preview.representation_id)
    if bundle is None:
        raise ValueError("HP-7 authoritative DocumentRepresentationBundle is missing.")
    document = ledger.get_document(bundle.representation.document_id)
    if document is None:
        raise ValueError("HP-7 authoritative Document is missing.")
    source = ledger.get_source(document.source_id)
    if source is None:
        raise ValueError("HP-7 authoritative Source is missing.")
    evidence_by_id: dict[str, EvidenceTarget] = {}
    attempts_by_evidence_id: dict[str, list[EvidenceValidationAttempt]] = {}
    for target_id in preview.evidence_target_ids:
        target = ledger.get_evidence_target(target_id)
        if target is None:
            raise ValueError("HP-7 evidence target is missing.")
        evidence_by_id[target.id] = target
    for attempt_id in preview.evidence_validation_attempt_ids:
        attempt = ledger.get_evidence_validation_attempt(attempt_id)
        if attempt is None:
            raise ValueError("HP-7 evidence validation attempt is missing.")
        attempts_by_evidence_id.setdefault(attempt.evidence_target_id, []).append(attempt)
    attempt_by_evidence_id = {
        target_id: sorted(attempts, key=lambda item: item.id)[0]
        for target_id, attempts in attempts_by_evidence_id.items()
    }
    if not set(evidence_by_id).issubset(attempt_by_evidence_id):
        raise ValueError("HP-7 evidence validation coverage is incomplete.")
    return _Lineage(
        preview=preview,
        hp5_preview_id=hp5.id,
        hp4_preview_id=hp4.id,
        hp3_preview_id=hp4.parent_preview_id,
        mentions=mentions,
        references=references,
        source_id=source.id,
        document_id=document.id,
        evidence_by_id=evidence_by_id,
        attempt_by_evidence_id=attempt_by_evidence_id,
    )


def _admission_reasons(
    preview: HybridEventSemanticsPreview,
) -> dict[str, set[ProposalAdmissionReason]]:
    reasons: dict[str, set[ProposalAdmissionReason]] = {
        item.event_subject_id: set() for item in preview.semantic_events
    }
    frame_by_id = {item.id: item for item in HYBRID_EVENT_SEMANTICS_V1.frames}
    for event in preview.semantic_events:
        frame = frame_by_id[event.frame_id]
        actual_roles = {item.frame_role_id for item in _event_assignments(preview, event)}
        if any(item.required and item.id not in actual_roles for item in frame.roles):
            reasons[event.event_subject_id].add(ProposalAdmissionReason.MISSING_REQUIRED_ROLE)
        for gap in _event_gaps(preview, event):
            if reason := _HARD_GAP_REASONS.get(gap.code):
                reasons[event.event_subject_id].add(reason)
        statements = _event_statements(preview, event)
        if not statements:
            reasons[event.event_subject_id].add(ProposalAdmissionReason.MISSING_SUPPORT_JUDGMENT)
        judgments_by_statement: dict[str, list[SemanticSupportJudgment]] = {}
        for judgment in preview.judgments:
            judgments_by_statement.setdefault(judgment.statement_id, []).append(judgment)
        for statement in statements:
            judgments = judgments_by_statement.get(statement.id, [])
            if not judgments:
                reasons[event.event_subject_id].add(
                    ProposalAdmissionReason.MISSING_SUPPORT_JUDGMENT
                )
            elif len(judgments) > 1:
                reasons[event.event_subject_id].add(
                    ProposalAdmissionReason.REPEATED_SUPPORT_JUDGMENT
                )
            elif judgments[0].outcome is not SupportOutcome.DIRECTLY_SUPPORTED:
                reasons[event.event_subject_id].add(ProposalAdmissionReason.NON_DIRECT_SUPPORT)
    return reasons


def _build_event_changes(
    *,
    lineage: _Lineage,
    event: EventSemanticDraft,
    event_ids: dict[str, str],
    provenance_activity_id: str,
) -> tuple[PlannedProposedChange, ...]:
    preview = lineage.preview
    event_id = event_ids[event.event_subject_id]
    support = lineage.evidence_by_id[event.support_evidence_target_id]
    assignments = _event_assignments(preview, event)
    typed_targets: dict[str, _TypedTarget] = {}
    participant_actor_ids: set[str] = set()
    participant_organization_ids: set[str] = set()
    for assignment in assignments:
        target = _target(preview, assignment.target_id)
        typed = _typed_target(lineage, target)
        if typed is None:
            continue
        typed_targets[target.id] = typed
        if assignment.upper_role in {UpperRole.AGENT, UpperRole.PARTICIPANT}:
            if typed.record_type == "Actor":
                participant_actor_ids.add(typed.record_id)
            else:
                participant_organization_ids.add(typed.record_id)
    lineage_json = _lineage_json(lineage, event)
    changes: list[PlannedProposedChange] = []
    for target_id, typed in sorted(
        typed_targets.items(), key=lambda item: (item[1].record_id, item[0])
    ):
        target = _target(preview, target_id)
        changes.append(
            _planned_change(
                provenance_activity_id=provenance_activity_id,
                source_id=lineage.source_id,
                document_id=lineage.document_id,
                proposed_json={
                    "record_type": typed.record_type,
                    "stable_label": typed.record_id,
                    "record": typed.record_json,
                    "evidence": _evidence_json(typed.source_target),
                    "hybrid_lineage": _typed_target_lineage_json(lineage, target),
                },
            )
        )
    event_record = Event(
        id=event_id,
        name=f"{event.trigger_text} [{event.frame_id}]",
        participant_actor_ids=tuple(sorted(participant_actor_ids)),
        participant_organization_ids=tuple(sorted(participant_organization_ids)),
    ).model_dump(mode="json", exclude={"created_at", "updated_at"})
    changes.append(
        _planned_change(
            provenance_activity_id=provenance_activity_id,
            source_id=lineage.source_id,
            document_id=lineage.document_id,
            proposed_json={
                "record_type": "Event",
                "stable_label": event_id,
                "record": cast(dict[str, JsonValue], event_record),
                "evidence": _evidence_json(support),
                "hybrid_lineage": lineage_json,
            },
        )
    )
    assertions = _proposed_assertions(
        lineage=lineage,
        event=event,
        event_id=event_id,
        event_ids=event_ids,
        typed_targets=typed_targets,
    )
    support_attempt = lineage.attempt_by_evidence_id[support.id]
    for assertion in assertions:
        changes.append(
            _planned_change(
                provenance_activity_id=provenance_activity_id,
                source_id=lineage.source_id,
                document_id=lineage.document_id,
                proposed_json={
                    "record_type": "Assertion",
                    "stable_label": assertion.id,
                    "record": cast(
                        dict[str, JsonValue], assertion.model_dump(mode="json", exclude_none=True)
                    ),
                    "evidence_links": [
                        {
                            "evidence_target_id": support.id,
                            "validation_attempt_id": support_attempt.id,
                            "role": "direct_support",
                            "polarity": EvidencePolarity.SUPPORTS.value,
                            "necessity": EvidenceNecessity.REQUIRED.value,
                        }
                    ],
                    "hybrid_lineage": lineage_json,
                },
            )
        )
    return tuple(sorted(changes, key=lambda item: item.id))


def _proposed_assertions(
    *,
    lineage: _Lineage,
    event: EventSemanticDraft,
    event_id: str,
    event_ids: dict[str, str],
    typed_targets: dict[str, _TypedTarget],
) -> tuple[ProposedAssertion, ...]:
    support_id = event.support_evidence_target_id
    assertions: list[ProposedAssertion] = []

    def add(
        relation: HybridEventStructuralPredicate,
        *,
        object_entity_id: str | None = None,
        object_value: JsonValue = None,
        qualifiers: dict[str, JsonValue] | None = None,
    ) -> None:
        object_identity = object_entity_id or _canonical_json(object_value)
        qualifier_values = qualifiers or {}
        assertion_id = _id(
            "ast",
            event_id,
            relation.value,
            object_identity,
            _canonical_json(qualifier_values),
            support_id,
        )
        assertions.append(
            ProposedAssertion(
                id=assertion_id,
                assertion_type=AssertionType.SOURCE_CLAIM,
                epistemic_scope=EpistemicScope.SOURCE_REPORT,
                subject_entity_id=event_id,
                relation_label=relation.value,
                object_entity_id=object_entity_id,
                object_value=object_value,
                source_authority=SourceAuthority.UNKNOWN,
                attribution_basis=AttributionBasis.REPORTED_BY_SOURCE,
                qualifiers=qualifier_values,
                source_ids=(lineage.source_id,),
                evidence_target_ids=(support_id,),
            )
        )

    add(HybridEventStructuralPredicate.HAS_EVENT_TYPE, object_value=event.frame_id)
    for assignment in _event_assignments(lineage.preview, event):
        target = _target(lineage.preview, assignment.target_id)
        typed = typed_targets.get(target.id)
        object_entity_id: str | None = None
        object_value: JsonValue = None
        if target.kind.value == "event_subject" and target.reference_id is not None:
            object_entity_id = event_ids[target.reference_id]
        elif typed is not None:
            object_entity_id = typed.record_id
        else:
            object_value = target.text
        add(
            HybridEventStructuralPredicate.HAS_ARGUMENT,
            object_entity_id=object_entity_id,
            object_value=object_value,
            qualifiers={
                "frame_role_id": assignment.frame_role_id,
                "upper_role": assignment.upper_role.value,
            },
        )
    qualifier_by_id = {item.id: item for item in lineage.preview.qualifiers}
    for qualifier_id in event.qualifier_ids:
        qualifier = qualifier_by_id[qualifier_id]
        add(
            HybridEventStructuralPredicate.HAS_TIME
            if qualifier.kind == "time"
            else HybridEventStructuralPredicate.HAS_PLACE,
            object_value=qualifier.text,
        )
    add(HybridEventStructuralPredicate.HAS_POLARITY, object_value=event.polarity)
    add(HybridEventStructuralPredicate.HAS_MODALITY, object_value=event.modality)
    if event.attribution_target_id is not None:
        target = _target(lineage.preview, event.attribution_target_id)
        typed = typed_targets.get(target.id)
        add(
            HybridEventStructuralPredicate.ACCORDING_TO,
            object_entity_id=typed.record_id if typed is not None else None,
            object_value=None if typed is not None else target.text,
        )
    return tuple(sorted(assertions, key=lambda item: item.id))


def _typed_target(lineage: _Lineage, target: EventArgumentTargetDraft) -> _TypedTarget | None:
    if target.kind.value != "mention_candidate" or target.reference_id is None:
        return None
    candidates = {item.id: item for item in lineage.mentions.candidates}
    candidate = candidates.get(target.reference_id)
    if candidate is None:
        raise ValueError("HP-7 semantic target references an unknown MentionCandidate.")
    interpretations = [
        item for item in lineage.mentions.interpretations if item.candidate_id == candidate.id
    ]
    if len(interpretations) != 1:
        return None
    interpretation = interpretations[0]
    if interpretation.referentiality is not Referentiality.SPECIFIC_ENTITY:
        return None
    name, identity = _resolved_name(lineage.references, candidate)
    target_evidence = lineage.evidence_by_id[target.evidence_target_id]
    if interpretation.contextual_kind is ContextualKind.PERSON:
        record_id = _id("act", lineage.preview.representation_id, identity)
        record = Actor(id=record_id, name=name).model_dump(
            mode="json", exclude={"created_at", "updated_at"}
        )
        return _TypedTarget("Actor", record_id, cast(dict[str, JsonValue], record), target_evidence)
    is_organization = interpretation.contextual_kind in {
        ContextualKind.ORGANIZATION,
        ContextualKind.GOVERNMENT,
    } or (
        interpretation.contextual_kind is ContextualKind.GEOPOLITICAL_ENTITY
        and interpretation.discourse_role in {DiscourseRole.ACTOR, DiscourseRole.PARTICIPANT}
    )
    if not is_organization:
        return None
    record_id = _id("org", lineage.preview.representation_id, identity)
    organization_type = interpretation.contextual_kind.value
    record = Organization(
        id=record_id,
        name=name,
        organization_type=organization_type,
    ).model_dump(mode="json", exclude={"created_at", "updated_at"})
    return _TypedTarget(
        "Organization", record_id, cast(dict[str, JsonValue], record), target_evidence
    )


def _resolved_name(
    references: HybridReferencePreview,
    candidate: MentionCandidate,
) -> tuple[str, str]:
    decisions = [
        item for item in references.reference_decisions if item.candidate_id == candidate.id
    ]
    if len(decisions) == 1 and decisions[0].status is ReferenceStatus.RESOLVED:
        antecedent_ids = set(decisions[0].antecedent_span_ids)
        antecedents = [
            declaration.expanded_span
            for declaration in references.alias_declarations
            if declaration.expanded_span.id in antecedent_ids
        ]
        if len(antecedents) == 1:
            return antecedents[0].text, antecedents[0].id
    return candidate.text, candidate.id


def _lineage_json(lineage: _Lineage, event: EventSemanticDraft) -> dict[str, JsonValue]:
    statements = _event_statements(lineage.preview, event)
    judgments = _event_judgments(lineage.preview, statements)
    source_trace_ids, model_run_ids = _event_execution_lineage(
        lineage.preview,
        event,
        _event_assignments(lineage.preview, event),
        statements,
        judgments,
    )
    return cast(
        dict[str, JsonValue],
        {
            "hp1_preview_id": lineage.mentions.id,
            "hp2_preview_id": lineage.references.id,
            "hp3_preview_id": lineage.hp3_preview_id,
            "hp4_preview_id": lineage.hp4_preview_id,
            "hp5_preview_id": lineage.hp5_preview_id,
            "hp6_preview_id": lineage.preview.id,
            "hp6_event_semantic_id": event.id,
            "semantic_statement_ids": sorted(item.id for item in statements),
            "support_judgment_ids": sorted(item.id for item in judgments),
            "model_run_ids": list(model_run_ids),
            "source_trace_ids": list(source_trace_ids),
        },
    )


def _typed_target_lineage_json(
    lineage: _Lineage,
    target: EventArgumentTargetDraft,
) -> dict[str, JsonValue]:
    if target.reference_id is None:
        raise ValueError("HP-7 typed target is missing its MentionCandidate identity.")
    interpretations = [
        item
        for item in lineage.mentions.interpretations
        if item.candidate_id == target.reference_id
    ]
    reference_decisions = [
        item
        for item in lineage.references.reference_decisions
        if item.candidate_id == target.reference_id
    ]
    return cast(
        dict[str, JsonValue],
        {
            "hp1_preview_id": lineage.mentions.id,
            "hp2_preview_id": lineage.references.id,
            "hp3_preview_id": lineage.hp3_preview_id,
            "hp4_preview_id": lineage.hp4_preview_id,
            "hp5_preview_id": lineage.hp5_preview_id,
            "hp6_preview_id": lineage.preview.id,
            "mention_candidate_id": target.reference_id,
            "mention_interpretation_ids": sorted(item.id for item in interpretations),
            "reference_decision_ids": sorted(item.id for item in reference_decisions),
            "model_run_ids": sorted(item.model_run_id for item in interpretations),
            "source_trace_ids": sorted(
                {
                    *(item.trace_id for item in interpretations),
                    *(item.trace_id for item in reference_decisions),
                }
            ),
        },
    )


def _planned_change(
    *,
    provenance_activity_id: str,
    source_id: str,
    document_id: str,
    proposed_json: dict[str, JsonValue],
) -> PlannedProposedChange:
    return PlannedProposedChange(
        id=_id("pcg", provenance_activity_id, _canonical_json(proposed_json)),
        proposed_json=proposed_json,
        source_id=source_id,
        document_id=document_id,
        provenance_activity_id=provenance_activity_id,
    )


def _evidence_json(target: EvidenceTarget) -> dict[str, JsonValue]:
    return {
        "source_id": target.source_id,
        "document_id": target.document_id,
        "selector_type": "pinned_text",
        "exact_text": target.exact_text,
        "prefix_text": target.prefix_text,
        "suffix_text": target.suffix_text,
        "location": {
            "representation_id": target.representation_id,
            "text_view_id": target.text_view_id,
            "start_char": target.start_char,
            "end_char": target.end_char,
            "node_ids": list(target.node_ids),
        },
    }


def _event_assignments(
    preview: HybridEventSemanticsPreview, event: EventSemanticDraft
) -> tuple[EventArgumentAssignmentDraft, ...]:
    by_id = {item.id: item for item in preview.assignments}
    return tuple(by_id[item] for item in event.argument_assignment_ids)


def _event_gaps(
    preview: HybridEventSemanticsPreview, event: EventSemanticDraft
) -> tuple[SemanticCoverageGap, ...]:
    return tuple(item for item in preview.gaps if item.event_subject_id == event.event_subject_id)


def _event_statements(
    preview: HybridEventSemanticsPreview, event: EventSemanticDraft
) -> tuple[SemanticStatement, ...]:
    return tuple(item for item in preview.statements if item.event_semantic_id == event.id)


def _event_judgments(
    preview: HybridEventSemanticsPreview,
    statements: tuple[SemanticStatement, ...],
) -> tuple[SemanticSupportJudgment, ...]:
    statement_ids = {item.id for item in statements}
    return tuple(item for item in preview.judgments if item.statement_id in statement_ids)


def _target(preview: HybridEventSemanticsPreview, target_id: str) -> EventArgumentTargetDraft:
    target = next((item for item in preview.targets if item.id == target_id), None)
    if target is None:
        raise ValueError("HP-7 references an unknown semantic target.")
    return target


def _event_execution_lineage(
    preview: HybridEventSemanticsPreview,
    event: EventSemanticDraft,
    assignments: tuple[EventArgumentAssignmentDraft, ...],
    statements: tuple[SemanticStatement, ...],
    judgments: tuple[SemanticSupportJudgment, ...],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Collect only the HP-6 traces and model runs that contributed to one event."""
    trace_ids = {event.normalization_trace_id}
    trace_ids.update(item for assignment in assignments for item in assignment.source_trace_ids)
    run_ids = {event.normalization_model_run_id}
    run_ids.update(item.model_run_id for item in judgments)
    statement_ids = {item.id for item in statements}
    for trace in preview.traces:
        if (
            trace.id in trace_ids
            or statement_ids.intersection(trace.input_record_ids)
            or run_ids.intersection(trace.execution_record_ids)
        ):
            trace_ids.add(trace.id)
            run_ids.update(
                item for item in trace.execution_record_ids if item in preview.model_run_ids
            )
    return tuple(sorted(trace_ids)), tuple(sorted(run_ids))


def _event_source_segment_id(
    preview: HybridEventSemanticsPreview, event: EventSemanticDraft
) -> str:
    assignments = _event_assignments(preview, event)
    if not assignments:
        return f"held:{event.event_subject_id}"
    return _target(preview, assignments[0].target_id).source_segment_id


def _decision_id(
    *,
    event: EventSemanticDraft,
    disposition: ProposalDisposition,
    reasons: tuple[ProposalAdmissionReason, ...],
    advisory_gap_ids: tuple[str, ...],
    statements: tuple[SemanticStatement, ...],
    judgments: tuple[SemanticSupportJudgment, ...],
    model_run_ids: tuple[str, ...],
    source_trace_ids: tuple[str, ...],
    proposal_ids: tuple[str, ...],
) -> str:
    return _id(
        "pad",
        event.id,
        disposition.value,
        *(item.value for item in reasons),
        *advisory_gap_ids,
        *(sorted(item.id for item in statements)),
        *(sorted(item.id for item in judgments)),
        *model_run_ids,
        *source_trace_ids,
        *proposal_ids,
    )


def _validate_existing_publication(
    *,
    proposed_changes: tuple[PlannedProposedChange, ...],
    provenance_activity_id: str,
    activity_type: str,
    input_ids: tuple[str, ...],
    activity: ProvenanceActivity,
    changes: tuple[ProposedChange, ...],
    error_label: str,
) -> None:
    if (
        activity.id != provenance_activity_id
        or activity.activity_type != activity_type
        or activity.agent != HYBRID_PROPOSAL_AGENT
        or activity.input_ids != input_ids
        or activity.output_ids != tuple(item.id for item in proposed_changes)
    ):
        raise ValueError(f"{error_label} existing provenance activity conflicts with its Plan.")
    actual = {item.id: item for item in changes}
    for planned in proposed_changes:
        existing = actual[planned.id]
        if (
            existing.proposed_json != planned.proposed_json
            or existing.source_id != planned.source_id
            or existing.document_id != planned.document_id
            or existing.provenance_activity_id != planned.provenance_activity_id
        ):
            raise ValueError(f"{error_label} existing ProposedChange conflicts with its Plan.")


def _plan_id(payload: dict[str, JsonValue]) -> str:
    return _id("hpp", _canonical_json(payload))


def _id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("\x1f".join(parts).encode()).hexdigest()
    return f"{prefix}_{digest[:24]}"


def _ordered_distinct(label: str, values: tuple[str, ...]) -> None:
    if values != tuple(sorted(set(values))):
        raise ValueError(f"HP-7 {label} must be ordered and distinct.")


def _distinct(label: str, values: tuple[str, ...]) -> None:
    if len(set(values)) != len(values):
        raise ValueError(f"HP-7 {label} must be distinct.")


def _canonical_json(value: JsonValue) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
