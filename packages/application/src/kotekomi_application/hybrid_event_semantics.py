"""Typed HP-6 governed event semantics and source-support evidence."""

from __future__ import annotations

import hashlib
import json
import re
from enum import StrEnum
from typing import Annotated, Literal, Self, cast

from kotekomi_domain import HYBRID_EVENT_SEMANTICS_V1, SemanticArgumentTargetKind, UpperRole
from kotekomi_domain.models import JsonValue
from pydantic import BaseModel, ConfigDict, Field, model_validator

from kotekomi_application.extraction_stage_trace import ExtractionStageTrace

HYBRID_EVENT_SEMANTICS_POLICY_ID = "hybrid_event_semantics_v1"
HYBRID_EVENT_NORMALIZATION_PROMPT_ID = "hybrid_event_normalization_v1"
HYBRID_EVENT_NORMALIZATION_SCHEMA_ID = "hybrid_event_normalization_text_v1"
HYBRID_EVENT_ROLE_COMPLETION_PROMPT_ID = "hybrid_event_role_completion_v1"
HYBRID_EVENT_ROLE_COMPLETION_SCHEMA_ID = "hybrid_event_role_completion_text_v1"
HYBRID_SEMANTIC_SUPPORT_PROMPT_ID = "hybrid_semantic_support_v1"
HYBRID_SEMANTIC_SUPPORT_SCHEMA_ID = "hybrid_semantic_support_text_v1"
_SHA256 = r"^[a-f0-9]{64}$"


class HybridEventSemanticsStatus(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    BLOCKED = "blocked"


class SemanticCoverageGapCode(StrEnum):
    MISSING_GOVERNED_ATTRIBUTION = "missing_governed_attribution"
    MISSING_REQUIRED_ROLE = "missing_required_role"
    OMITTED_PARENT_ARGUMENT = "omitted_parent_argument"
    OMITTED_PARENT_QUALIFIER = "omitted_parent_qualifier"
    PARENT_ATTRIBUTION_DISAGREEMENT = "parent_attribution_disagreement"
    UNSUPPORTED_QUALIFIER_PROPOSAL = "unsupported_qualifier_proposal"
    UNMAPPED_FRAME = "unmapped_frame"


class SemanticStatementKind(StrEnum):
    ARGUMENT = "argument"
    ATTRIBUTION = "attribution"
    FRAME = "frame"
    MODALITY = "modality"
    POLARITY = "polarity"
    QUALIFIER = "qualifier"


class SupportOutcome(StrEnum):
    DIRECTLY_SUPPORTED = "directly_supported"
    PARTIALLY_SUPPORTED = "partially_supported"
    UNSUPPORTED = "unsupported"
    CONTRADICTED = "contradicted"
    AMBIGUOUS = "ambiguous"


class EventAttributionKind(StrEnum):
    MENTION_CANDIDATE = "mention_candidate"
    SOURCE_NARRATOR = "source_narrator"
    SOURCE_SPAN = "source_span"
    UNRESOLVED = "unresolved"


class EventArgumentTargetDraft(BaseModel):
    """One exact source-backed target admitted by a governed frame role."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: Annotated[str, Field(pattern=r"^sat_[a-f0-9]{24}$")]
    kind: SemanticArgumentTargetKind
    reference_id: Annotated[str, Field(min_length=1)] | None = None
    source_segment_id: Annotated[str, Field(min_length=1)]
    text: Annotated[str, Field(min_length=1)]
    start: Annotated[int, Field(ge=0)]
    end: Annotated[int, Field(gt=0)]
    evidence_target_id: Annotated[str, Field(pattern=r"^etg_[a-f0-9]{24}$")]
    evidence_validation_attempt_id: Annotated[str, Field(pattern=r"^eva_[a-f0-9]{24}$")]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if self.end - self.start != len(self.text):
            raise ValueError("Semantic target range does not match its text.")
        if self.kind is SemanticArgumentTargetKind.SOURCE_SPAN:
            if self.reference_id is not None:
                raise ValueError("A source-span target cannot name a parent reference.")
        elif self.reference_id is None:
            raise ValueError("A referenced semantic target requires a parent reference.")
        if self.id != event_argument_target_draft_id(
            kind=self.kind,
            reference_id=self.reference_id,
            source_segment_id=self.source_segment_id,
            text=self.text,
            start=self.start,
            end=self.end,
            evidence_target_id=self.evidence_target_id,
            evidence_validation_attempt_id=self.evidence_validation_attempt_id,
        ):
            raise ValueError("EventArgumentTargetDraft ID does not match its contents.")
        return self


class EventArgumentAssignmentDraft(BaseModel):
    """One governed and source-backed role assignment for an event."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: Annotated[str, Field(pattern=r"^saa_[a-f0-9]{24}$")]
    event_subject_id: Annotated[str, Field(pattern=r"^esd_[a-f0-9]{24}$")]
    frame_id: Annotated[str, Field(min_length=1)]
    target_id: Annotated[str, Field(pattern=r"^sat_[a-f0-9]{24}$")]
    frame_role_id: Annotated[str, Field(min_length=1)]
    upper_role: UpperRole
    proposed_role_labels: tuple[Annotated[str, Field(min_length=1)], ...] = ()
    support_evidence_target_id: Annotated[str, Field(pattern=r"^etg_[a-f0-9]{24}$")]
    source_trace_ids: tuple[Annotated[str, Field(pattern=r"^xst_[a-f0-9]{24}$")], ...]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if self.frame_role_id.split(".", maxsplit=1)[0] != self.frame_id:
            raise ValueError("Frame role does not belong to the assignment frame.")
        _ordered_distinct("proposed role labels", self.proposed_role_labels)
        _ordered_distinct("assignment trace IDs", self.source_trace_ids)
        if not self.source_trace_ids:
            raise ValueError("Role assignment requires source trace lineage.")
        if self.id != event_argument_assignment_draft_id(
            event_subject_id=self.event_subject_id,
            frame_id=self.frame_id,
            target_id=self.target_id,
            frame_role_id=self.frame_role_id,
            upper_role=self.upper_role,
            proposed_role_labels=self.proposed_role_labels,
            support_evidence_target_id=self.support_evidence_target_id,
            source_trace_ids=self.source_trace_ids,
        ):
            raise ValueError("EventArgumentAssignmentDraft ID does not match its contents.")
        return self


class SemanticQualifierDraft(BaseModel):
    """One exact time or place qualifier for a governed event."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: Annotated[str, Field(pattern=r"^sqd_[a-f0-9]{24}$")]
    event_subject_id: Annotated[str, Field(pattern=r"^esd_[a-f0-9]{24}$")]
    kind: Literal["place", "time"]
    source_segment_id: Annotated[str, Field(min_length=1)]
    text: Annotated[str, Field(min_length=1)]
    start: Annotated[int, Field(ge=0)]
    end: Annotated[int, Field(gt=0)]
    evidence_target_id: Annotated[str, Field(pattern=r"^etg_[a-f0-9]{24}$")]
    evidence_validation_attempt_id: Annotated[str, Field(pattern=r"^eva_[a-f0-9]{24}$")]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if self.end - self.start != len(self.text):
            raise ValueError("Semantic qualifier range does not match its text.")
        expected = _id(
            "sqd",
            self.event_subject_id,
            self.kind,
            self.source_segment_id,
            self.text,
            str(self.start),
            str(self.end),
            self.evidence_target_id,
            self.evidence_validation_attempt_id,
        )
        if self.id != expected:
            raise ValueError("SemanticQualifierDraft ID does not match its contents.")
        return self


class EventSemanticDraft(BaseModel):
    """One governed interpretation of one source-grounded event subject."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: Annotated[str, Field(pattern=r"^esn_[a-f0-9]{24}$")]
    event_subject_id: Annotated[str, Field(pattern=r"^esd_[a-f0-9]{24}$")]
    trigger_id: Annotated[str, Field(pattern=r"^etd_[a-f0-9]{24}$")]
    trigger_text: Annotated[str, Field(min_length=1)]
    frame_id: Annotated[str, Field(min_length=1)]
    proposed_event_label: Annotated[str, Field(min_length=1)]
    argument_assignment_ids: tuple[Annotated[str, Field(pattern=r"^saa_[a-f0-9]{24}$")], ...]
    qualifier_ids: tuple[Annotated[str, Field(pattern=r"^sqd_[a-f0-9]{24}$")], ...] = ()
    polarity: Literal["affirmed", "negated"]
    modality: Literal["actual", "planned", "possible", "uncertain", "recommended", "hypothetical"]
    attribution_kind: EventAttributionKind
    attribution_target_id: Annotated[str, Field(pattern=r"^sat_[a-f0-9]{24}$")] | None = None
    support_evidence_target_id: Annotated[str, Field(pattern=r"^etg_[a-f0-9]{24}$")]
    normalization_task_id: Annotated[str, Field(min_length=1)]
    normalization_model_run_id: Annotated[str, Field(min_length=1)]
    normalization_trace_id: Annotated[str, Field(pattern=r"^xst_[a-f0-9]{24}$")]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        _ordered_distinct("argument assignment IDs", self.argument_assignment_ids)
        _ordered_distinct("qualifier IDs", self.qualifier_ids)
        if self.attribution_kind in {
            EventAttributionKind.SOURCE_NARRATOR,
            EventAttributionKind.UNRESOLVED,
        }:
            if self.attribution_target_id is not None:
                raise ValueError("Untargeted attribution cannot name a target.")
        elif self.attribution_target_id is None:
            raise ValueError("Target attribution requires a semantic target.")
        if self.id != event_semantic_draft_id(
            event_subject_id=self.event_subject_id,
            trigger_id=self.trigger_id,
            trigger_text=self.trigger_text,
            frame_id=self.frame_id,
            proposed_event_label=self.proposed_event_label,
            argument_assignment_ids=self.argument_assignment_ids,
            qualifier_ids=self.qualifier_ids,
            polarity=self.polarity,
            modality=self.modality,
            attribution_kind=self.attribution_kind,
            attribution_target_id=self.attribution_target_id,
            support_evidence_target_id=self.support_evidence_target_id,
            normalization_task_id=self.normalization_task_id,
            normalization_model_run_id=self.normalization_model_run_id,
            normalization_trace_id=self.normalization_trace_id,
        ):
            raise ValueError("EventSemanticDraft ID does not match its contents.")
        return self


class SemanticCoverageGap(BaseModel):
    """One explicit absence or unresolved component in semantic construction."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: Annotated[str, Field(pattern=r"^scg_[a-f0-9]{24}$")]
    event_subject_id: Annotated[str, Field(pattern=r"^esd_[a-f0-9]{24}$")]
    code: SemanticCoverageGapCode
    field_value: Annotated[str, Field(min_length=1)]
    detail: Annotated[str, Field(min_length=1)]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        expected = _id("scg", self.event_subject_id, self.code.value, self.field_value, self.detail)
        if self.id != expected:
            raise ValueError("SemanticCoverageGap ID does not match its contents.")
        return self


class SemanticStatement(BaseModel):
    """One deterministic governed statement submitted for independent support review."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: Annotated[str, Field(pattern=r"^sst_[a-f0-9]{24}$")]
    event_semantic_id: Annotated[str, Field(pattern=r"^esn_[a-f0-9]{24}$")]
    kind: SemanticStatementKind
    subject_record_id: Annotated[str, Field(min_length=1)]
    text: Annotated[str, Field(min_length=1)]
    governed_definition: Annotated[str, Field(min_length=1)]
    evidence_target_id: Annotated[str, Field(pattern=r"^etg_[a-f0-9]{24}$")]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        expected = _id(
            "sst",
            self.event_semantic_id,
            self.kind.value,
            self.subject_record_id,
            self.text,
            self.governed_definition,
            self.evidence_target_id,
        )
        if self.id != expected:
            raise ValueError("SemanticStatement ID does not match its contents.")
        return self


class SemanticSupportJudgment(BaseModel):
    """One untrusted independent judgment over a governed SemanticStatement."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: Annotated[str, Field(pattern=r"^spj_[a-f0-9]{24}$")]
    statement_id: Annotated[str, Field(pattern=r"^sst_[a-f0-9]{24}$")]
    evidence_target_id: Annotated[str, Field(pattern=r"^etg_[a-f0-9]{24}$")]
    outcome: SupportOutcome
    reason: Annotated[str, Field(min_length=1)]
    extraction_task_id: Annotated[str, Field(min_length=1)]
    model_run_id: Annotated[str, Field(min_length=1)]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if self.reason != self.reason.strip() or "\n" in self.reason or "\r" in self.reason:
            raise ValueError("Semantic support reason must be one trimmed line.")
        expected = semantic_support_judgment_id(
            statement_id=self.statement_id,
            evidence_target_id=self.evidence_target_id,
            outcome=self.outcome,
            reason=self.reason,
            extraction_task_id=self.extraction_task_id,
            model_run_id=self.model_run_id,
        )
        if self.id != expected:
            raise ValueError("SemanticSupportJudgment ID does not match its contents.")
        return self


class HybridEventSemanticsPreview(BaseModel):
    """Immutable derived HP-6 evidence for one terminal HP-5 Preview."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["hybrid_event_semantics_preview_v1"] = (
        "hybrid_event_semantics_preview_v1"
    )
    id: Annotated[str, Field(pattern=r"^hsp_[a-f0-9]{24}$")]
    parent_preview_id: Annotated[str, Field(pattern=r"^hcp_[a-f0-9]{24}$")]
    parent_preview_sha256: Annotated[str, Field(pattern=_SHA256)]
    representation_id: Annotated[str, Field(min_length=1)]
    paragraph_node_id: Annotated[str, Field(min_length=1)]
    ontology_profile_id: Literal["hybrid_event_semantics_v1"]
    ontology_profile_sha256: Annotated[str, Field(pattern=_SHA256)]
    normalization_prompt_sha256: Annotated[str, Field(pattern=_SHA256)]
    normalization_schema_sha256: Annotated[str, Field(pattern=_SHA256)]
    role_completion_prompt_sha256: Annotated[str, Field(pattern=_SHA256)]
    role_completion_schema_sha256: Annotated[str, Field(pattern=_SHA256)]
    support_prompt_sha256: Annotated[str, Field(pattern=_SHA256)]
    support_schema_sha256: Annotated[str, Field(pattern=_SHA256)]
    semantic_events: tuple[EventSemanticDraft, ...] = ()
    targets: tuple[EventArgumentTargetDraft, ...] = ()
    assignments: tuple[EventArgumentAssignmentDraft, ...] = ()
    qualifiers: tuple[SemanticQualifierDraft, ...] = ()
    gaps: tuple[SemanticCoverageGap, ...] = ()
    statements: tuple[SemanticStatement, ...] = ()
    judgments: tuple[SemanticSupportJudgment, ...] = ()
    evidence_target_ids: tuple[Annotated[str, Field(pattern=r"^etg_[a-f0-9]{24}$")], ...] = ()
    evidence_validation_attempt_ids: tuple[
        Annotated[str, Field(pattern=r"^eva_[a-f0-9]{24}$")], ...
    ] = ()
    extraction_task_ids: tuple[Annotated[str, Field(min_length=1)], ...] = ()
    model_run_ids: tuple[Annotated[str, Field(min_length=1)], ...] = ()
    traces: tuple[ExtractionStageTrace, ...] = ()
    terminal_status: HybridEventSemanticsStatus
    diagnostics: tuple[Annotated[str, Field(min_length=1)], ...] = ()

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        for label, values in (
            ("semantic event IDs", tuple(item.id for item in self.semantic_events)),
            ("target IDs", tuple(item.id for item in self.targets)),
            ("assignment IDs", tuple(item.id for item in self.assignments)),
            ("qualifier IDs", tuple(item.id for item in self.qualifiers)),
            ("gap IDs", tuple(item.id for item in self.gaps)),
            ("statement IDs", tuple(item.id for item in self.statements)),
            ("judgment IDs", tuple(item.id for item in self.judgments)),
            ("evidence target IDs", self.evidence_target_ids),
            ("evidence validation attempt IDs", self.evidence_validation_attempt_ids),
            ("extraction task IDs", self.extraction_task_ids),
            ("model run IDs", self.model_run_ids),
            ("trace IDs", tuple(item.id for item in self.traces)),
            ("diagnostics", self.diagnostics),
        ):
            _ordered_distinct(label, values)
        if len(self.extraction_task_ids) != len(self.model_run_ids):
            raise ValueError("HP-6 task and ModelRun coverage must match.")
        assignment_ids = {item.id for item in self.assignments}
        qualifier_ids = {item.id for item in self.qualifiers}
        target_ids = {item.id for item in self.targets}
        if any(
            not set(item.argument_assignment_ids).issubset(assignment_ids)
            or not set(item.qualifier_ids).issubset(qualifier_ids)
            for item in self.semantic_events
        ):
            raise ValueError("EventSemanticDraft references unknown semantic components.")
        if any(item.target_id not in target_ids for item in self.assignments):
            raise ValueError("Role assignment references an unknown semantic target.")
        if any(
            item.attribution_target_id is not None and item.attribution_target_id not in target_ids
            for item in self.semantic_events
        ):
            raise ValueError("Event attribution references an unknown semantic target.")
        statement_ids = {item.id for item in self.statements}
        if any(item.statement_id not in statement_ids for item in self.judgments):
            raise ValueError("Support judgment references an unknown SemanticStatement.")
        _validate_preview_references(self)
        if (
            self.terminal_status is HybridEventSemanticsStatus.PARTIAL
            and not self.gaps
            and not self.diagnostics
        ):
            raise ValueError("A partial HP-6 Preview requires a typed gap or diagnostic.")
        if self.terminal_status is HybridEventSemanticsStatus.BLOCKED:
            if (
                self.semantic_events
                or self.targets
                or self.assignments
                or self.qualifiers
                or self.gaps
                or self.statements
                or self.judgments
                or self.evidence_target_ids
                or self.evidence_validation_attempt_ids
                or self.extraction_task_ids
                or self.model_run_ids
                or self.traces
                or not self.diagnostics
            ):
                raise ValueError("A blocked HP-6 Preview requires only diagnostics.")
        if self.id != _preview_id(self.model_dump(mode="json", exclude={"id"})):
            raise ValueError("HybridEventSemanticsPreview ID does not match its contents.")
        return self


def _validate_preview_references(preview: HybridEventSemanticsPreview) -> None:
    events = {item.id: item for item in preview.semantic_events}
    assignments = {item.id: item for item in preview.assignments}
    targets = {item.id: item for item in preview.targets}
    qualifiers = {item.id: item for item in preview.qualifiers}
    statements = {item.id: item for item in preview.statements}
    traces = {item.id: item for item in preview.traces}
    evidence_target_ids = set(preview.evidence_target_ids)
    attempt_ids = set(preview.evidence_validation_attempt_ids)
    task_ids = set(preview.extraction_task_ids)
    run_ids = set(preview.model_run_ids)
    frame_by_id = {item.id: item for item in HYBRID_EVENT_SEMANTICS_V1.frames}

    referenced_assignment_ids: set[str] = set()
    referenced_qualifier_ids: set[str] = set()
    for event in events.values():
        frame = frame_by_id.get(event.frame_id)
        if frame is None:
            raise ValueError("EventSemanticDraft references an unknown governed frame.")
        event_assignments = tuple(assignments[item] for item in event.argument_assignment_ids)
        event_qualifiers = tuple(qualifiers[item] for item in event.qualifier_ids)
        if any(
            item.event_subject_id != event.event_subject_id
            or item.frame_id != event.frame_id
            or item.support_evidence_target_id != event.support_evidence_target_id
            for item in event_assignments
        ):
            raise ValueError("EventSemanticDraft contains an assignment from another event.")
        if any(item.event_subject_id != event.event_subject_id for item in event_qualifiers):
            raise ValueError("EventSemanticDraft contains a qualifier from another event.")
        if (
            event.normalization_task_id not in task_ids
            or event.normalization_model_run_id not in run_ids
        ):
            raise ValueError("EventSemanticDraft references unknown normalization execution.")
        if event.normalization_trace_id not in traces:
            raise ValueError("EventSemanticDraft references an unknown normalization trace.")
        if event.attribution_target_id is not None:
            attribution_target = targets[event.attribution_target_id]
            if event.attribution_kind.value != attribution_target.kind.value:
                raise ValueError("EventSemanticDraft attribution kind does not match its target.")
        referenced_assignment_ids.update(event.argument_assignment_ids)
        referenced_qualifier_ids.update(event.qualifier_ids)

        frame_roles = {item.id: item for item in frame.roles}
        for assignment in event_assignments:
            role = frame_roles.get(assignment.frame_role_id)
            target = targets[assignment.target_id]
            if (
                role is None
                or assignment.upper_role is not role.upper_role
                or target.kind not in role.allowed_target_kinds
            ):
                raise ValueError("Role assignment does not conform to the governed frame.")

    if referenced_assignment_ids != set(assignments):
        raise ValueError("HP-6 Preview contains an unreferenced role assignment.")
    if referenced_qualifier_ids != set(qualifiers):
        raise ValueError("HP-6 Preview contains an unreferenced qualifier.")
    if {item.target_id for item in assignments.values()} != set(targets):
        raise ValueError("HP-6 Preview contains an unreferenced semantic target.")

    for statement in statements.values():
        event = events.get(statement.event_semantic_id)
        if event is None or statement.evidence_target_id != event.support_evidence_target_id:
            raise ValueError("SemanticStatement does not match its event evidence.")
        if statement.kind is SemanticStatementKind.ARGUMENT:
            valid_subject = statement.subject_record_id in event.argument_assignment_ids
        elif statement.kind is SemanticStatementKind.QUALIFIER:
            valid_subject = statement.subject_record_id in event.qualifier_ids
        else:
            valid_subject = statement.subject_record_id == event.id
        if not valid_subject:
            raise ValueError("SemanticStatement references an invalid subject record.")

    judged_statement_ids: set[str] = set()
    for judgment in preview.judgments:
        statement = statements[judgment.statement_id]
        if judgment.statement_id in judged_statement_ids:
            raise ValueError("HP-6 Preview repeats a judgment for one SemanticStatement.")
        if judgment.evidence_target_id != statement.evidence_target_id:
            raise ValueError("SemanticSupportJudgment does not match statement evidence.")
        if judgment.extraction_task_id not in task_ids or judgment.model_run_id not in run_ids:
            raise ValueError("SemanticSupportJudgment references unknown execution evidence.")
        judged_statement_ids.add(judgment.statement_id)

    required_evidence_ids = {
        *(item.support_evidence_target_id for item in events.values()),
        *(item.support_evidence_target_id for item in assignments.values()),
        *(item.evidence_target_id for item in targets.values()),
        *(item.evidence_target_id for item in qualifiers.values()),
        *(item.evidence_target_id for item in statements.values()),
    }
    if not required_evidence_ids.issubset(evidence_target_ids):
        raise ValueError("HP-6 Preview omits referenced EvidenceTarget records.")
    required_attempt_ids = {
        *(item.evidence_validation_attempt_id for item in targets.values()),
        *(item.evidence_validation_attempt_id for item in qualifiers.values()),
    }
    if not required_attempt_ids.issubset(attempt_ids):
        raise ValueError("HP-6 Preview omits referenced evidence validation attempts.")
    if preview.terminal_status is HybridEventSemanticsStatus.COMPLETE:
        if preview.gaps or preview.diagnostics or judged_statement_ids != set(statements):
            raise ValueError("A complete HP-6 Preview requires gap-free fully judged semantics.")


def event_argument_target_draft_id(
    *,
    kind: SemanticArgumentTargetKind,
    reference_id: str | None,
    source_segment_id: str,
    text: str,
    start: int,
    end: int,
    evidence_target_id: str,
    evidence_validation_attempt_id: str,
) -> str:
    return _id(
        "sat",
        kind.value,
        reference_id or "",
        source_segment_id,
        text,
        str(start),
        str(end),
        evidence_target_id,
        evidence_validation_attempt_id,
    )


def build_event_argument_target_draft(
    *,
    kind: SemanticArgumentTargetKind,
    reference_id: str | None,
    source_segment_id: str,
    text: str,
    start: int,
    end: int,
    evidence_target_id: str,
    evidence_validation_attempt_id: str,
) -> EventArgumentTargetDraft:
    """Construct one target whose identity is wholly derived by KoteKomi."""
    return EventArgumentTargetDraft(
        id=event_argument_target_draft_id(
            kind=kind,
            reference_id=reference_id,
            source_segment_id=source_segment_id,
            text=text,
            start=start,
            end=end,
            evidence_target_id=evidence_target_id,
            evidence_validation_attempt_id=evidence_validation_attempt_id,
        ),
        kind=kind,
        reference_id=reference_id,
        source_segment_id=source_segment_id,
        text=text,
        start=start,
        end=end,
        evidence_target_id=evidence_target_id,
        evidence_validation_attempt_id=evidence_validation_attempt_id,
    )


def event_argument_assignment_draft_id(
    *,
    event_subject_id: str,
    frame_id: str,
    target_id: str,
    frame_role_id: str,
    upper_role: UpperRole,
    proposed_role_labels: tuple[str, ...],
    support_evidence_target_id: str,
    source_trace_ids: tuple[str, ...],
) -> str:
    return _id(
        "saa",
        event_subject_id,
        frame_id,
        target_id,
        frame_role_id,
        upper_role.value,
        *proposed_role_labels,
        support_evidence_target_id,
        *source_trace_ids,
    )


def build_event_argument_assignment_draft(
    *,
    event_subject_id: str,
    frame_id: str,
    target_id: str,
    frame_role_id: str,
    upper_role: UpperRole,
    proposed_role_labels: tuple[str, ...],
    support_evidence_target_id: str,
    source_trace_ids: tuple[str, ...],
) -> EventArgumentAssignmentDraft:
    """Construct one governed assignment from validated components."""
    return EventArgumentAssignmentDraft(
        id=event_argument_assignment_draft_id(
            event_subject_id=event_subject_id,
            frame_id=frame_id,
            target_id=target_id,
            frame_role_id=frame_role_id,
            upper_role=upper_role,
            proposed_role_labels=proposed_role_labels,
            support_evidence_target_id=support_evidence_target_id,
            source_trace_ids=source_trace_ids,
        ),
        event_subject_id=event_subject_id,
        frame_id=frame_id,
        target_id=target_id,
        frame_role_id=frame_role_id,
        upper_role=upper_role,
        proposed_role_labels=proposed_role_labels,
        support_evidence_target_id=support_evidence_target_id,
        source_trace_ids=source_trace_ids,
    )


def build_semantic_qualifier_draft(
    *,
    event_subject_id: str,
    kind: Literal["place", "time"],
    source_segment_id: str,
    text: str,
    start: int,
    end: int,
    evidence_target_id: str,
    evidence_validation_attempt_id: str,
) -> SemanticQualifierDraft:
    """Construct one exact source qualifier."""
    identifier = _id(
        "sqd",
        event_subject_id,
        kind,
        source_segment_id,
        text,
        str(start),
        str(end),
        evidence_target_id,
        evidence_validation_attempt_id,
    )
    return SemanticQualifierDraft(
        id=identifier,
        event_subject_id=event_subject_id,
        kind=kind,
        source_segment_id=source_segment_id,
        text=text,
        start=start,
        end=end,
        evidence_target_id=evidence_target_id,
        evidence_validation_attempt_id=evidence_validation_attempt_id,
    )


def event_semantic_draft_id(
    *,
    event_subject_id: str,
    trigger_id: str,
    trigger_text: str,
    frame_id: str,
    proposed_event_label: str,
    argument_assignment_ids: tuple[str, ...],
    qualifier_ids: tuple[str, ...],
    polarity: Literal["affirmed", "negated"],
    modality: Literal["actual", "planned", "possible", "uncertain", "recommended", "hypothetical"],
    attribution_kind: EventAttributionKind,
    attribution_target_id: str | None,
    support_evidence_target_id: str,
    normalization_task_id: str,
    normalization_model_run_id: str,
    normalization_trace_id: str,
) -> str:
    return _id(
        "esn",
        event_subject_id,
        trigger_id,
        trigger_text,
        frame_id,
        proposed_event_label,
        *argument_assignment_ids,
        *qualifier_ids,
        polarity,
        modality,
        attribution_kind.value,
        attribution_target_id or "",
        support_evidence_target_id,
        normalization_task_id,
        normalization_model_run_id,
        normalization_trace_id,
    )


def build_event_semantic_draft(
    *,
    event_subject_id: str,
    trigger_id: str,
    trigger_text: str,
    frame_id: str,
    proposed_event_label: str,
    argument_assignment_ids: tuple[str, ...],
    qualifier_ids: tuple[str, ...],
    polarity: Literal["affirmed", "negated"],
    modality: Literal["actual", "planned", "possible", "uncertain", "recommended", "hypothetical"],
    attribution_kind: EventAttributionKind,
    attribution_target_id: str | None,
    support_evidence_target_id: str,
    normalization_task_id: str,
    normalization_model_run_id: str,
    normalization_trace_id: str,
) -> EventSemanticDraft:
    """Construct one governed event interpretation from derived components."""
    return EventSemanticDraft(
        id=event_semantic_draft_id(
            event_subject_id=event_subject_id,
            trigger_id=trigger_id,
            trigger_text=trigger_text,
            frame_id=frame_id,
            proposed_event_label=proposed_event_label,
            argument_assignment_ids=argument_assignment_ids,
            qualifier_ids=qualifier_ids,
            polarity=polarity,
            modality=modality,
            attribution_kind=attribution_kind,
            attribution_target_id=attribution_target_id,
            support_evidence_target_id=support_evidence_target_id,
            normalization_task_id=normalization_task_id,
            normalization_model_run_id=normalization_model_run_id,
            normalization_trace_id=normalization_trace_id,
        ),
        event_subject_id=event_subject_id,
        trigger_id=trigger_id,
        trigger_text=trigger_text,
        frame_id=frame_id,
        proposed_event_label=proposed_event_label,
        argument_assignment_ids=argument_assignment_ids,
        qualifier_ids=qualifier_ids,
        polarity=polarity,
        modality=modality,
        attribution_kind=attribution_kind,
        attribution_target_id=attribution_target_id,
        support_evidence_target_id=support_evidence_target_id,
        normalization_task_id=normalization_task_id,
        normalization_model_run_id=normalization_model_run_id,
        normalization_trace_id=normalization_trace_id,
    )


def build_semantic_coverage_gap(
    *,
    event_subject_id: str,
    code: SemanticCoverageGapCode,
    field_value: str,
    detail: str,
) -> SemanticCoverageGap:
    """Construct one explicit semantic coverage gap."""
    return SemanticCoverageGap(
        id=_id("scg", event_subject_id, code.value, field_value, detail),
        event_subject_id=event_subject_id,
        code=code,
        field_value=field_value,
        detail=detail,
    )


def build_semantic_statement(
    *,
    event_semantic_id: str,
    kind: SemanticStatementKind,
    subject_record_id: str,
    text: str,
    governed_definition: str,
    evidence_target_id: str,
) -> SemanticStatement:
    """Construct one deterministic readable statement for independent review."""
    return SemanticStatement(
        id=_id(
            "sst",
            event_semantic_id,
            kind.value,
            subject_record_id,
            text,
            governed_definition,
            evidence_target_id,
        ),
        event_semantic_id=event_semantic_id,
        kind=kind,
        subject_record_id=subject_record_id,
        text=text,
        governed_definition=governed_definition,
        evidence_target_id=evidence_target_id,
    )


def semantic_support_judgment_id(
    *,
    statement_id: str,
    evidence_target_id: str,
    outcome: SupportOutcome,
    reason: str,
    extraction_task_id: str,
    model_run_id: str,
) -> str:
    return _id(
        "spj",
        statement_id,
        evidence_target_id,
        outcome.value,
        reason,
        extraction_task_id,
        model_run_id,
    )


def build_semantic_support_judgment(
    *,
    statement_id: str,
    evidence_target_id: str,
    outcome: SupportOutcome,
    reason: str,
    extraction_task_id: str,
    model_run_id: str,
) -> SemanticSupportJudgment:
    """Construct one model judgment without admitting it as accepted state."""
    return SemanticSupportJudgment(
        id=semantic_support_judgment_id(
            statement_id=statement_id,
            evidence_target_id=evidence_target_id,
            outcome=outcome,
            reason=reason,
            extraction_task_id=extraction_task_id,
            model_run_id=model_run_id,
        ),
        statement_id=statement_id,
        evidence_target_id=evidence_target_id,
        outcome=outcome,
        reason=reason,
        extraction_task_id=extraction_task_id,
        model_run_id=model_run_id,
    )


def resolve_unique_source_literal(source_text: str, proposed_literal: str) -> tuple[str, int]:
    """Resolve model wording to one exact authoritative span without changing words."""
    words = proposed_literal.split()
    if not words:
        raise ValueError("source_literal_not_unique")
    pattern = r"\s+".join(re.escape(word) for word in words)
    if words[0][0].isalnum():
        pattern = rf"(?<!\w){pattern}"
    if words[-1][-1].isalnum():
        pattern = rf"{pattern}(?!\w)"
    normalized_matches = tuple(re.finditer(pattern, source_text))
    if len(normalized_matches) != 1:
        raise ValueError("source_literal_not_unique")
    match = normalized_matches[0]
    return match.group(), match.start()


def build_hybrid_event_semantics_preview(**values: object) -> HybridEventSemanticsPreview:
    payload = dict(values)
    payload.pop("id", None)
    payload.setdefault("schema_version", "hybrid_event_semantics_preview_v1")
    for name in (
        "semantic_events",
        "targets",
        "assignments",
        "qualifiers",
        "gaps",
        "statements",
        "judgments",
        "evidence_target_ids",
        "evidence_validation_attempt_ids",
        "extraction_task_ids",
        "model_run_ids",
        "traces",
        "diagnostics",
    ):
        payload.setdefault(name, ())
    for name in (
        "semantic_events",
        "targets",
        "assignments",
        "qualifiers",
        "gaps",
        "statements",
        "judgments",
        "traces",
    ):
        payload[name] = [
            item.model_dump(mode="json") for item in cast(tuple[BaseModel, ...], payload[name])
        ]
    normalized = cast(dict[str, JsonValue], _json_copy(payload))
    normalized["id"] = _preview_id(normalized)
    return HybridEventSemanticsPreview.model_validate_json(_canonical_json(normalized))


def canonical_hybrid_event_semantics_preview_bytes(
    preview: HybridEventSemanticsPreview,
) -> bytes:
    return _canonical_json(preview.model_dump(mode="json")).encode()


def hybrid_event_semantics_preview_sha256(preview: HybridEventSemanticsPreview) -> str:
    return hashlib.sha256(canonical_hybrid_event_semantics_preview_bytes(preview)).hexdigest()


def hybrid_event_semantics_preview_from_bytes(payload: bytes) -> HybridEventSemanticsPreview:
    try:
        json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("HybridEventSemanticsPreview is not valid JSON.") from error
    preview = HybridEventSemanticsPreview.model_validate_json(payload)
    if canonical_hybrid_event_semantics_preview_bytes(preview) != payload:
        raise ValueError("HybridEventSemanticsPreview does not use canonical encoding.")
    return preview


def _preview_id(payload: dict[str, JsonValue]) -> str:
    return f"hsp_{hashlib.sha256(_canonical_json(payload).encode()).hexdigest()[:24]}"


def _id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("\x1f".join(parts).encode()).hexdigest()
    return f"{prefix}_{digest[:24]}"


def _ordered_distinct(label: str, values: tuple[object, ...]) -> None:
    if len(set(values)) != len(values):
        raise ValueError(f"HP-6 repeats {label}.")


def _canonical_json(value: JsonValue) -> str:
    return json.dumps(
        value, allow_nan=False, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )


def _json_copy(value: object) -> JsonValue:
    return cast(JsonValue, json.loads(json.dumps(value, allow_nan=False, ensure_ascii=False)))
