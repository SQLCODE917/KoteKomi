"""HP-7 deterministic proposal planning over immutable HP-6 evidence."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, Literal, Protocol, Self, cast

from kotekomi_domain import (
    Actor,
    Document,
    DocumentRepresentationBundle,
    Event,
    EvidenceTarget,
    EvidenceValidationAttempt,
    Organization,
    ProposedAssertion,
    ProposedChange,
    ProvenanceActivity,
    ReviewStatus,
    Source,
)
from kotekomi_domain.models import JsonValue
from pydantic import BaseModel, ConfigDict, Field, model_validator

from kotekomi_application.context_planning import (
    PARAGRAPH_SEGMENT_V2,
    paragraph_source_segments,
)
from kotekomi_application.extraction_stage_trace import (
    ExtractionStageStatus,
    ExtractionStageTrace,
    build_extraction_stage_trace,
    validate_extraction_stage_trace_chain,
)
from kotekomi_application.hybrid_document_references import (
    HybridReferencePreview,
    ReferenceStatus,
    canonical_hybrid_reference_preview_bytes,
    hybrid_reference_preview_from_bytes,
)
from kotekomi_application.hybrid_event_semantics import (
    HybridEventSemanticsPreview,
    SourceGroundedEventDraft,
    canonical_hybrid_event_semantics_preview_bytes,
)
from kotekomi_application.hybrid_event_semantics_preview import (
    HybridEventSemanticsArchive,
    HybridEventSemanticsLedger,
    load_hybrid_event_semantics_preview,
)
from kotekomi_application.hybrid_event_trigger_preview import load_hybrid_event_trigger_preview
from kotekomi_application.hybrid_event_triggers import HybridEventTriggerPreview
from kotekomi_application.hybrid_mention_boundary_adjudication import (
    effective_mention_candidate_ids,
)
from kotekomi_application.hybrid_mention_interpretation import (
    ContextualKind,
    DiscourseRole,
    HybridExtractionPreview,
    MentionCandidate,
    Referentiality,
    canonical_hybrid_extraction_preview_bytes,
    hybrid_extraction_preview_from_bytes,
    hybrid_source_segment_id,
)
from kotekomi_application.source_grounded_events import (
    build_source_grounded_event,
    load_event_mention_evidence,
    validate_source_grounded_event,
)

HYBRID_PROPOSAL_POLICY_ID = "hybrid_proposed_change_v2"
HYBRID_PROPOSAL_ACTIVITY_TYPE = "hybrid_proposal_batch_submitted"
HYBRID_PROPOSAL_AGENT = "kotekomi_application"
_SHA256 = r"^[a-f0-9]{64}$"


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
    """One deterministic proposal decision for one source-grounded Event."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: Annotated[str, Field(pattern=r"^pad_[a-f0-9]{24}$")]
    source_grounded_event_id: Annotated[str, Field(pattern=r"^sge_[a-f0-9]{24}$")]
    disposition: Literal["proposed"] = "proposed"
    advisory_gap_ids: tuple[Annotated[str, Field(pattern=r"^scg_[a-f0-9]{24}$")], ...] = ()
    model_run_ids: tuple[Annotated[str, Field(min_length=1)], ...] = ()
    source_trace_ids: tuple[Annotated[str, Field(pattern=r"^xst_[a-f0-9]{24}$")], ...] = ()
    proposed_change_ids: tuple[Annotated[str, Field(pattern=r"^pcg_[a-f0-9]{24}$")], ...] = ()

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        for label, values in (
            ("advisory gap IDs", self.advisory_gap_ids),
            ("model run IDs", self.model_run_ids),
            ("source trace IDs", self.source_trace_ids),
            ("ProposedChange IDs", self.proposed_change_ids),
        ):
            _ordered_distinct(label, values)
        if not self.proposed_change_ids:
            raise ValueError("A source-grounded Event proposal requires a change.")
        expected = _id(
            "pad",
            self.source_grounded_event_id,
            self.disposition,
            *self.advisory_gap_ids,
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

    schema_version: Literal["hybrid_proposal_plan_v2"] = "hybrid_proposal_plan_v2"
    id: Annotated[str, Field(pattern=r"^hpp_[a-f0-9]{24}$")]
    parent_preview_id: Annotated[str, Field(pattern=r"^hsp_[a-f0-9]{24}$")]
    parent_preview_sha256: Annotated[str, Field(pattern=_SHA256)]
    representation_id: Annotated[str, Field(min_length=1)]
    paragraph_node_id: Annotated[str, Field(min_length=1)]
    policy_id: Literal["hybrid_proposed_change_v2"] = HYBRID_PROPOSAL_POLICY_ID
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
        record_ids: list[str] = []
        for item in self.proposed_changes:
            record = item.proposed_json.get("record")
            if not isinstance(record, dict) or not isinstance(record.get("id"), str):
                raise ValueError("HP-7 planned change lacks a typed record identity.")
            record_ids.append(cast(str, record["id"]))
        _distinct("planned record identities", tuple(record_ids))
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
    hp4_preview_id: str
    triggers: HybridEventTriggerPreview
    hp3_preview_id: str
    mentions: HybridExtractionPreview
    references: HybridReferencePreview
    bundle: DocumentRepresentationBundle
    source_id: str
    document_id: str
    evidence_by_id: dict[str, EvidenceTarget]
    attempt_by_evidence_id: dict[str, EvidenceValidationAttempt]


@dataclass(frozen=True)
class _TypedTarget:
    record_type: Literal["Actor", "Organization"]
    record_id: str
    record_json: dict[str, JsonValue]


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
        "schema_version": "hybrid_proposal_plan_v2",
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
    provenance_id = _id("prv", HYBRID_PROPOSAL_ACTIVITY_TYPE, preview.parent_preview_id)
    planned_by_id: dict[str, PlannedProposedChange] = {}
    decisions: list[ProposalAdmissionDecision] = []
    traces: list[ExtractionStageTrace] = []
    trigger_by_id = {item.id: item for item in lineage.triggers.triggers}
    for source_event in preview.source_grounded_events:
        trigger = trigger_by_id[source_event.trigger_id]
        entity_changes = _build_source_named_entity_changes(
            lineage=lineage,
            source_segment_ids={source_event.source_segment_id},
            provenance_activity_id=provenance_id,
        )
        for entity_change in entity_changes:
            planned_by_id[entity_change.id] = entity_change
        event_change = _build_source_grounded_event_change(
            lineage=lineage,
            source_event=source_event,
            provenance_activity_id=provenance_id,
        )
        existing = planned_by_id.get(event_change.id)
        if existing is not None and existing != event_change:
            raise ValueError("HP-7 produced conflicting bodies for one proposal identity.")
        planned_by_id[event_change.id] = event_change
        advisory_ids = tuple(
            sorted(
                item.id
                for item in preview.gaps
                if item.event_subject_id == source_event.event_subject_id
            )
        )
        proposal_ids = tuple(sorted((event_change.id, *(item.id for item in entity_changes))))
        source_trace_ids = (trigger.trace_id,)
        model_run_ids = (trigger.model_run_id,)
        decision = ProposalAdmissionDecision(
            id=_decision_id(
                source_event=source_event,
                advisory_gap_ids=advisory_ids,
                model_run_ids=model_run_ids,
                source_trace_ids=source_trace_ids,
                proposal_ids=proposal_ids,
            ),
            source_grounded_event_id=source_event.id,
            advisory_gap_ids=advisory_ids,
            model_run_ids=model_run_ids,
            source_trace_ids=source_trace_ids,
            proposed_change_ids=proposal_ids,
        )
        decisions.append(decision)
        support_target = lineage.evidence_by_id[source_event.mention.support_evidence_target_id]
        traces.append(
            build_extraction_stage_trace(
                trace_run_id=f"hp7:{source_event.id}",
                ordinal=0,
                stage_id="source_grounded_event_proposal",
                stage_version=HYBRID_PROPOSAL_POLICY_ID,
                producer_id="kotekomi_application",
                source_segment_id=source_event.source_segment_id,
                source_text_sha256=hashlib.sha256(support_target.exact_text.encode()).hexdigest(),
                configuration=cast(
                    dict[str, JsonValue],
                    {
                        "classification_required": False,
                        "event_name_source": "expression_evidence_target",
                    },
                ),
                input_payload={
                    "source_grounded_event": cast(JsonValue, source_event.model_dump(mode="json")),
                },
                output_payload={
                    "decision": cast(JsonValue, decision.model_dump(mode="json")),
                    "proposed_changes": [
                        cast(JsonValue, item.model_dump(mode="json"))
                        for item in (event_change, *entity_changes)
                    ],
                },
                status=ExtractionStageStatus.COMPLETED,
                input_record_ids=(source_event.id,),
                execution_record_ids=model_run_ids,
                diagnostics=(),
            )
        )
    proposed_changes = tuple(sorted(planned_by_id.values(), key=lambda item: item.id))
    decisions_tuple = tuple(decisions)
    traces_tuple = tuple(traces)
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
        diagnostics=(),
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
            if event.mentions:
                mention_evidence = load_event_mention_evidence(
                    event,
                    ledger.get_evidence_target,
                )
                validate_source_grounded_event(event, mention_evidence)
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
    hp4 = load_hybrid_event_trigger_preview(preview.parent_preview_id, archive)
    mention_payload = archive.read_hybrid_extraction_preview(hp4.mention_preview_id)
    mentions = hybrid_extraction_preview_from_bytes(mention_payload)
    if (
        mentions.id != hp4.mention_preview_id
        or canonical_hybrid_extraction_preview_bytes(mentions) != mention_payload
        or hashlib.sha256(mention_payload).hexdigest() != hp4.mention_preview_sha256
    ):
        raise ValueError("HP-7 HP-1 lineage does not match its pinned identity.")
    reference_payload = archive.read_hybrid_reference_preview(hp4.reference_preview_id)
    references = hybrid_reference_preview_from_bytes(reference_payload)
    if (
        references.id != hp4.reference_preview_id
        or canonical_hybrid_reference_preview_bytes(references) != reference_payload
        or hashlib.sha256(reference_payload).hexdigest() != hp4.reference_preview_sha256
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
        hp4_preview_id=hp4.id,
        triggers=hp4,
        hp3_preview_id=hp4.parent_preview_id,
        mentions=mentions,
        references=references,
        bundle=bundle,
        source_id=source.id,
        document_id=document.id,
        evidence_by_id=evidence_by_id,
        attempt_by_evidence_id=attempt_by_evidence_id,
    )


def _build_source_grounded_event_change(
    *,
    lineage: _Lineage,
    source_event: SourceGroundedEventDraft,
    provenance_activity_id: str,
) -> PlannedProposedChange:
    event = build_source_grounded_event(source_event)
    evidence = {
        target_id: lineage.evidence_by_id[target_id]
        for target_id in (
            source_event.mention.head_evidence_target_id,
            source_event.mention.expression_evidence_target_id,
            source_event.mention.support_evidence_target_id,
        )
    }
    validate_source_grounded_event(event, evidence)
    support = evidence[source_event.mention.support_evidence_target_id]
    trigger = next(item for item in lineage.triggers.triggers if item.id == source_event.trigger_id)
    event_record = event.model_dump(mode="json", exclude={"created_at", "updated_at"})
    return _planned_change(
        provenance_activity_id=provenance_activity_id,
        source_id=lineage.source_id,
        document_id=lineage.document_id,
        proposed_json={
            "record_type": "Event",
            "stable_label": event.id,
            "record": cast(dict[str, JsonValue], event_record),
            "evidence": _evidence_json(support),
            "event_mention_evidence": {
                "head": _evidence_json(evidence[source_event.mention.head_evidence_target_id]),
                "expression": _evidence_json(
                    evidence[source_event.mention.expression_evidence_target_id]
                ),
                "support": _evidence_json(support),
            },
            "hybrid_lineage": {
                "hp1_preview_id": lineage.mentions.id,
                "hp2_preview_id": lineage.references.id,
                "hp3_preview_id": lineage.hp3_preview_id,
                "hp4_preview_id": lineage.hp4_preview_id,
                "source_grounded_event_id": source_event.id,
                "event_trigger_id": trigger.id,
                "model_run_ids": [trigger.model_run_id],
                "source_trace_ids": [trigger.trace_id],
            },
        },
    )


def _build_source_named_entity_changes(
    *,
    lineage: _Lineage,
    source_segment_ids: set[str],
    provenance_activity_id: str,
) -> tuple[PlannedProposedChange, ...]:
    selected_candidate_ids = set(
        effective_mention_candidate_ids(
            lineage.mentions.boundary_decisions,
            lineage.mentions.boundary_adjudications,
        )
    )
    typed_by_id: dict[str, _TypedTarget] = {}
    for candidate in lineage.mentions.candidates:
        if (
            candidate.source_segment_id not in source_segment_ids
            or candidate.id not in selected_candidate_ids
        ):
            continue
        typed = _typed_candidate(lineage, candidate.id)
        if typed is not None:
            typed_by_id[typed.record_id] = typed
    changes: list[PlannedProposedChange] = []
    for typed in sorted(typed_by_id.values(), key=lambda item: item.record_id):
        candidate_id = _canonical_candidate_id(lineage, typed.record_id)
        changes.append(
            _planned_change(
                provenance_activity_id=provenance_activity_id,
                source_id=lineage.source_id,
                document_id=lineage.document_id,
                proposed_json={
                    "record_type": typed.record_type,
                    "stable_label": typed.record_id,
                    "record": typed.record_json,
                    "evidence": _candidate_evidence_json(lineage, candidate_id),
                    "hybrid_lineage": _typed_candidate_lineage_json(
                        lineage,
                        candidate_id,
                    ),
                },
            )
        )
    return tuple(changes)


def _typed_candidate(
    lineage: _Lineage,
    candidate_id: str,
) -> _TypedTarget | None:
    candidates = {item.id: item for item in lineage.mentions.candidates}
    candidate = candidates.get(candidate_id)
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
    if interpretation.contextual_kind is ContextualKind.PERSON:
        record_id = _id("act", lineage.preview.representation_id, identity)
        record = Actor(id=record_id, name=name).model_dump(
            mode="json", exclude={"created_at", "updated_at"}
        )
        return _TypedTarget("Actor", record_id, cast(dict[str, JsonValue], record))
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
    return _TypedTarget("Organization", record_id, cast(dict[str, JsonValue], record))


def _canonical_candidate_id(lineage: _Lineage, record_id: str) -> str:
    matches: list[tuple[bool, int, str]] = []
    for ordinal, candidate in enumerate(lineage.mentions.candidates):
        typed = _typed_candidate(lineage, candidate.id)
        if typed is None or typed.record_id != record_id:
            continue
        resolved_name, _ = _resolved_name(lineage.references, candidate)
        matches.append((candidate.text != resolved_name, ordinal, candidate.id))
    if not matches:
        raise ValueError("HP-7 typed record has no source MentionCandidate.")
    return min(matches)[2]


def _candidate_evidence_json(
    lineage: _Lineage,
    candidate_id: str,
) -> dict[str, JsonValue]:
    candidate = next(
        (item for item in lineage.mentions.candidates if item.id == candidate_id),
        None,
    )
    if candidate is None:
        raise ValueError("HP-7 candidate evidence references an unknown MentionCandidate.")
    node = next(
        (item for item in lineage.bundle.nodes if item.id == lineage.preview.paragraph_node_id),
        None,
    )
    if node is None or node.node_type != "paragraph":
        raise ValueError("HP-7 candidate evidence paragraph is missing or invalid.")
    view = next(
        (item for item in lineage.bundle.text_views if item.id == node.text_view_id),
        None,
    )
    if view is None:
        raise ValueError("HP-7 candidate evidence TextView is missing.")
    paragraph_text = view.text[node.start_char : node.end_char]
    segments = paragraph_source_segments(paragraph_text, PARAGRAPH_SEGMENT_V2)
    segment = next(
        (
            item
            for item in segments
            if hybrid_source_segment_id(lineage.preview.representation_id, node.id, item)
            == candidate.source_segment_id
        ),
        None,
    )
    if segment is None:
        raise ValueError("HP-7 candidate evidence SourceSegment is missing.")
    start = node.start_char + segment.start_char + candidate.start
    end = node.start_char + segment.start_char + candidate.end
    if view.text[start:end] != candidate.text:
        raise ValueError("HP-7 candidate evidence does not replay exact source characters.")
    return {
        "source_id": lineage.source_id,
        "document_id": lineage.document_id,
        "selector_type": "pinned_text",
        "exact_text": candidate.text,
        "prefix_text": view.text[max(0, start - 32) : start],
        "suffix_text": view.text[end : min(len(view.text), end + 32)],
        "location": {
            "representation_id": lineage.preview.representation_id,
            "text_view_id": view.id,
            "start_char": start,
            "end_char": end,
            "node_ids": [node.id],
        },
    }


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
        antecedents.extend(
            span for span in references.semantic_antecedent_spans if span.id in antecedent_ids
        )
        if len(antecedents) == 1:
            return antecedents[0].text, antecedents[0].id
    return candidate.text, candidate.id


def _typed_candidate_lineage_json(
    lineage: _Lineage,
    candidate_id: str,
) -> dict[str, JsonValue]:
    interpretations = [
        item for item in lineage.mentions.interpretations if item.candidate_id == candidate_id
    ]
    reference_decisions = [
        item for item in lineage.references.reference_decisions if item.candidate_id == candidate_id
    ]
    return cast(
        dict[str, JsonValue],
        {
            "hp1_preview_id": lineage.mentions.id,
            "hp2_preview_id": lineage.references.id,
            "hp3_preview_id": lineage.hp3_preview_id,
            "hp4_preview_id": lineage.hp4_preview_id,
            "mention_candidate_id": candidate_id,
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


def _decision_id(
    *,
    source_event: SourceGroundedEventDraft,
    advisory_gap_ids: tuple[str, ...],
    model_run_ids: tuple[str, ...],
    source_trace_ids: tuple[str, ...],
    proposal_ids: tuple[str, ...],
) -> str:
    return _id(
        "pad",
        source_event.id,
        "proposed",
        *advisory_gap_ids,
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
