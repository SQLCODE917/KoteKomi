"""Source-grounded Event-entity connection experiment contracts."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from enum import StrEnum
from typing import Annotated, Literal, Self, cast

from kotekomi_domain.models import JsonValue
from pydantic import BaseModel, ConfigDict, Field, model_validator

from kotekomi_application.event_entity_connection_model_output import (
    EntityInvolvementAnswerValue,
)
from kotekomi_application.extraction_stage_trace import (
    ExtractionStageTrace,
    validate_extraction_stage_trace_chain,
)
from kotekomi_application.hybrid_document_references import (
    HybridReferencePreview,
    ReferenceDecision,
    ReferenceSpan,
    ReferenceStatus,
)
from kotekomi_application.hybrid_event_semantics import SourceGroundedEventDraft
from kotekomi_application.hybrid_mention_boundary_adjudication import (
    effective_mention_candidate_ids,
    unresolved_mention_candidate_ids,
)
from kotekomi_application.hybrid_mention_interpretation import (
    ContextualKind,
    HybridExtractionPreview,
    MentionCandidate,
    MentionInterpretation,
    Referentiality,
)

EVENT_ENTITY_CONNECTION_POLICY_ID = "event_entity_connection_pairwise_v1"
EVENT_ENTITY_INVOLVEMENT_SCHEMA_ID = "event_entity_involvement_text_v1"

_ID = r"^[a-z]+_[a-f0-9]{24}$"
_SHA256 = r"^[a-f0-9]{64}$"


class EventEntityKind(StrEnum):
    """Entity kinds admitted by the first connection experiment."""

    ACTOR = "actor"
    ORGANIZATION = "organization"


class EventEntityConnectionDisposition(StrEnum):
    """KoteKomi's terminal treatment of one Event-entity candidate."""

    CONNECTED = "connected"
    NOT_CONNECTED = "not_connected"
    UNRESOLVED = "unresolved"


class EventEntityConnectionPreviewStatus(StrEnum):
    """Terminal state of one Event-entity connection Preview."""

    COMPLETE = "complete"
    PARTIAL = "partial"


class EventEntityCandidateGapReason(StrEnum):
    """Why one upstream mention cannot become an experiment candidate."""

    BOUNDARY_AMBIGUOUS = "boundary_ambiguous"
    INTERPRETATION_MISSING = "interpretation_missing"
    ENTITY_KIND_AMBIGUOUS = "entity_kind_ambiguous"
    REFERENCE_AMBIGUOUS = "reference_ambiguous"
    REFERENCE_UNRESOLVED = "reference_unresolved"
    REFERENCE_ANTECEDENT_MISSING = "reference_antecedent_missing"


class EventEntitySourceSpan(BaseModel):
    """One exact source span retained as derived connection evidence."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: Annotated[str, Field(pattern=r"^ees_[a-f0-9]{24}$")]
    source_segment_id: Annotated[str, Field(min_length=1)]
    source_text_sha256: Annotated[str, Field(pattern=_SHA256)]
    start: Annotated[int, Field(ge=0)]
    end: Annotated[int, Field(gt=0)]
    text: Annotated[str, Field(min_length=1)]
    mention_candidate_id: Annotated[str, Field(pattern=_ID)]
    reference_decision_id: Annotated[str, Field(pattern=r"^rfd_[a-f0-9]{24}$")] | None = None

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if self.end - self.start != len(self.text):
            raise ValueError("Event entity source range does not match its text.")
        expected = _id(
            "ees",
            self.source_segment_id,
            self.source_text_sha256,
            str(self.start),
            str(self.end),
            self.text,
            self.mention_candidate_id,
            self.reference_decision_id or "",
        )
        if self.id != expected:
            raise ValueError("Event entity source span ID does not match its evidence.")
        return self


class EventEntityMentionInput(BaseModel):
    """One KoteKomi-resolved entity mention used to construct candidates."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    entity_identity: Annotated[str, Field(min_length=1)]
    entity_kind: EventEntityKind
    entity_name: Annotated[str, Field(min_length=1)]
    source_span: EventEntitySourceSpan
    resolved_antecedent_span: ReferenceSpan | None = None


class EventEntityCandidateGap(BaseModel):
    """One source-bound upstream ambiguity excluded from model judgment."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: Annotated[str, Field(pattern=r"^ecg_[a-f0-9]{24}$")]
    source_segment_id: Annotated[str, Field(min_length=1)]
    source_text_sha256: Annotated[str, Field(pattern=_SHA256)]
    mention_candidate_id: Annotated[str, Field(pattern=_ID)]
    mention_start: Annotated[int, Field(ge=0)]
    mention_end: Annotated[int, Field(gt=0)]
    mention_text: Annotated[str, Field(min_length=1)]
    reason: EventEntityCandidateGapReason
    reference_decision_id: Annotated[str, Field(pattern=r"^rfd_[a-f0-9]{24}$")] | None = None

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if self.mention_end - self.mention_start != len(self.mention_text):
            raise ValueError("Event entity gap range does not match its text.")
        expected = _id(
            "ecg",
            self.source_segment_id,
            self.source_text_sha256,
            self.mention_candidate_id,
            str(self.mention_start),
            str(self.mention_end),
            self.mention_text,
            self.reason.value,
            self.reference_decision_id or "",
        )
        if self.id != expected:
            raise ValueError("Event entity gap ID does not match its evidence.")
        return self


class EventEntityCandidateSelection(BaseModel):
    """Complete deterministic result before pairwise semantic judgment."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    mentions: tuple[EventEntityMentionInput, ...]
    gaps: tuple[EventEntityCandidateGap, ...]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if (
            tuple(
                sorted(
                    self.mentions,
                    key=lambda item: (
                        item.source_span.start,
                        item.source_span.end,
                        item.source_span.mention_candidate_id,
                    ),
                )
            )
            != self.mentions
        ):
            raise ValueError("Event entity selected mentions must use source order.")
        if (
            tuple(
                sorted(
                    self.gaps,
                    key=lambda item: (
                        item.mention_start,
                        item.mention_end,
                        item.mention_candidate_id,
                    ),
                )
            )
            != self.gaps
        ):
            raise ValueError("Event entity candidate gaps must use source order.")
        mention_ids = tuple(item.source_span.mention_candidate_id for item in self.mentions)
        gap_ids = tuple(item.mention_candidate_id for item in self.gaps)
        if len(set(mention_ids)) != len(mention_ids) or len(set(gap_ids)) != len(gap_ids):
            raise ValueError("Event entity candidate selection repeats an upstream mention.")
        if set(mention_ids) & set(gap_ids):
            raise ValueError("One upstream mention cannot be both selected and a gap.")
        return self


class EventEntityConnectionCandidate(BaseModel):
    """One source-bound Event and entity pair owned by KoteKomi."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: Annotated[str, Field(pattern=r"^eec_[a-f0-9]{24}$")]
    source_grounded_event_id: Annotated[str, Field(pattern=r"^sge_[a-f0-9]{24}$")]
    event_mention_id: Annotated[str, Field(pattern=r"^evm_[A-Za-z0-9][A-Za-z0-9_-]*$")]
    source_segment_id: Annotated[str, Field(min_length=1)]
    source_text_sha256: Annotated[str, Field(pattern=_SHA256)]
    event_expression_text: Annotated[str, Field(min_length=1)]
    event_expression_evidence_target_id: Annotated[str, Field(pattern=r"^etg_[a-f0-9]{24}$")]
    support_evidence_target_id: Annotated[str, Field(pattern=r"^etg_[a-f0-9]{24}$")]
    entity_identity: Annotated[str, Field(min_length=1)]
    entity_kind: EventEntityKind
    entity_name: Annotated[str, Field(min_length=1)]
    primary_source_span_id: Annotated[str, Field(pattern=r"^ees_[a-f0-9]{24}$")]
    source_spans: tuple[EventEntitySourceSpan, ...]
    resolved_antecedent_spans: tuple[ReferenceSpan, ...] = ()
    reference_decision_ids: tuple[Annotated[str, Field(pattern=r"^rfd_[a-f0-9]{24}$")], ...] = ()

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        for label, values in (
            ("source span IDs", tuple(item.id for item in self.source_spans)),
            (
                "resolved antecedent span IDs",
                tuple(item.id for item in self.resolved_antecedent_spans),
            ),
            ("reference decision IDs", self.reference_decision_ids),
        ):
            _ordered_distinct(label, values)
        if not self.source_spans:
            raise ValueError("Event entity candidate requires source mention evidence.")
        if (
            tuple(
                sorted(
                    self.source_spans,
                    key=lambda item: (item.start, item.end, item.mention_candidate_id),
                )
            )
            != self.source_spans
        ):
            raise ValueError("Event entity source spans must use source order.")
        if any(
            item.source_segment_id != self.source_segment_id
            or item.source_text_sha256 != self.source_text_sha256
            for item in self.source_spans
        ):
            raise ValueError("Event entity source spans do not share the Event source.")
        if self.primary_source_span_id not in {item.id for item in self.source_spans}:
            raise ValueError("Primary entity source span is absent from candidate evidence.")
        mention_candidate_ids = tuple(item.mention_candidate_id for item in self.source_spans)
        expected = event_entity_connection_candidate_id(
            source_grounded_event_id=self.source_grounded_event_id,
            event_mention_id=self.event_mention_id,
            entity_identity=self.entity_identity,
            entity_kind=self.entity_kind,
            mention_candidate_ids=mention_candidate_ids,
            reference_decision_ids=self.reference_decision_ids,
        )
        if self.id != expected:
            raise ValueError("Event entity candidate ID does not match its evidence.")
        return self


class EntityInvolvementJudgment(BaseModel):
    """One finite semantic answer bound to a KoteKomi-owned candidate."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: Annotated[str, Field(pattern=r"^eij_[a-f0-9]{24}$")]
    candidate_id: Annotated[str, Field(pattern=r"^eec_[a-f0-9]{24}$")]
    answer: EntityInvolvementAnswerValue
    extraction_task_id: Annotated[str, Field(min_length=1)]
    model_run_id: Annotated[str, Field(min_length=1)]
    trace_id: Annotated[str, Field(pattern=r"^xst_[a-f0-9]{24}$")]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        expected = _id(
            "eij",
            self.candidate_id,
            self.answer.value,
            self.extraction_task_id,
            self.model_run_id,
            self.trace_id,
        )
        if self.id != expected:
            raise ValueError("Entity involvement judgment ID does not match its evidence.")
        return self


class EventEntityConnectionDecision(BaseModel):
    """One deterministic disposition for an Event-entity candidate."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: Annotated[str, Field(pattern=r"^ecd_[a-f0-9]{24}$")]
    candidate_id: Annotated[str, Field(pattern=r"^eec_[a-f0-9]{24}$")]
    judgment_id: Annotated[str, Field(pattern=r"^eij_[a-f0-9]{24}$")] | None = None
    disposition: EventEntityConnectionDisposition
    reason_code: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]*$")]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if (
            self.judgment_id is None
            and self.disposition is not EventEntityConnectionDisposition.UNRESOLVED
        ):
            raise ValueError("A terminal connection decision requires a model judgment.")
        expected = _id(
            "ecd",
            self.candidate_id,
            self.judgment_id or "",
            self.disposition.value,
            self.reason_code,
        )
        if self.id != expected:
            raise ValueError("Event entity decision ID does not match its contents.")
        return self


class EventEntityConnectionDraft(BaseModel):
    """One positive source-grounded Event-to-entity connection."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: Annotated[str, Field(pattern=r"^eed_[a-f0-9]{24}$")]
    candidate_id: Annotated[str, Field(pattern=r"^eec_[a-f0-9]{24}$")]
    decision_id: Annotated[str, Field(pattern=r"^ecd_[a-f0-9]{24}$")]
    source_grounded_event_id: Annotated[str, Field(pattern=r"^sge_[a-f0-9]{24}$")]
    event_mention_id: Annotated[str, Field(pattern=r"^evm_[A-Za-z0-9][A-Za-z0-9_-]*$")]
    entity_identity: Annotated[str, Field(min_length=1)]
    entity_kind: EventEntityKind
    entity_name: Annotated[str, Field(min_length=1)]
    event_expression_evidence_target_id: Annotated[str, Field(pattern=r"^etg_[a-f0-9]{24}$")]
    entity_source_span_ids: tuple[Annotated[str, Field(pattern=r"^ees_[a-f0-9]{24}$")], ...]
    resolved_antecedent_span_ids: tuple[
        Annotated[str, Field(pattern=r"^rsp_[a-f0-9]{24}$")], ...
    ] = ()
    support_evidence_target_id: Annotated[str, Field(pattern=r"^etg_[a-f0-9]{24}$")]
    extraction_task_id: Annotated[str, Field(min_length=1)]
    model_run_id: Annotated[str, Field(min_length=1)]
    trace_id: Annotated[str, Field(pattern=r"^xst_[a-f0-9]{24}$")]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        _ordered_distinct("entity source span IDs", self.entity_source_span_ids)
        _ordered_distinct("resolved antecedent span IDs", self.resolved_antecedent_span_ids)
        if not self.entity_source_span_ids:
            raise ValueError("Event entity connection requires entity evidence.")
        expected = _id(
            "eed",
            self.candidate_id,
            self.decision_id,
            self.source_grounded_event_id,
            self.event_mention_id,
            self.entity_identity,
            self.entity_kind.value,
            self.event_expression_evidence_target_id,
            *self.entity_source_span_ids,
            *self.resolved_antecedent_span_ids,
            self.support_evidence_target_id,
            self.extraction_task_id,
            self.model_run_id,
            self.trace_id,
        )
        if self.id != expected:
            raise ValueError("Event entity connection draft ID does not match its evidence.")
        return self


class EventEntityConnectionPreview(BaseModel):
    """Complete derived evidence for one Event-entity connection experiment run."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["event_entity_connection_preview_v1"] = (
        "event_entity_connection_preview_v1"
    )
    id: Annotated[str, Field(pattern=r"^eep_[a-f0-9]{24}$")]
    parent_preview_id: Annotated[str, Field(min_length=1)]
    parent_preview_sha256: Annotated[str, Field(pattern=_SHA256)]
    policy_id: Literal["event_entity_connection_pairwise_v1"] = EVENT_ENTITY_CONNECTION_POLICY_ID
    candidate_gaps: tuple[EventEntityCandidateGap, ...]
    candidates: tuple[EventEntityConnectionCandidate, ...]
    judgments: tuple[EntityInvolvementJudgment, ...]
    decisions: tuple[EventEntityConnectionDecision, ...]
    drafts: tuple[EventEntityConnectionDraft, ...]
    traces: tuple[ExtractionStageTrace, ...]
    extraction_task_ids: tuple[Annotated[str, Field(min_length=1)], ...]
    model_run_ids: tuple[Annotated[str, Field(min_length=1)], ...]
    terminal_status: EventEntityConnectionPreviewStatus
    diagnostics: tuple[Annotated[str, Field(min_length=1)], ...] = ()

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        for label, values in (
            ("candidate gap IDs", tuple(item.id for item in self.candidate_gaps)),
            ("candidate IDs", tuple(item.id for item in self.candidates)),
            ("judgment IDs", tuple(item.id for item in self.judgments)),
            ("decision IDs", tuple(item.id for item in self.decisions)),
            ("draft IDs", tuple(item.id for item in self.drafts)),
            ("trace IDs", tuple(item.id for item in self.traces)),
            ("ExtractionTask IDs", self.extraction_task_ids),
            ("ModelRun IDs", self.model_run_ids),
            ("diagnostics", self.diagnostics),
        ):
            _ordered_distinct(label, values)
        candidate_ids = {item.id for item in self.candidates}
        judgment_by_candidate = {item.candidate_id: item for item in self.judgments}
        decision_by_candidate = {item.candidate_id: item for item in self.decisions}
        if len(decision_by_candidate) != len(self.decisions):
            raise ValueError("Connection Preview repeats a candidate decision.")
        if len(judgment_by_candidate) != len(self.judgments):
            raise ValueError("Connection Preview repeats a candidate judgment.")
        if set(decision_by_candidate) != candidate_ids:
            raise ValueError("Every Event entity candidate requires one decision.")
        if not set(judgment_by_candidate).issubset(candidate_ids):
            raise ValueError("Entity involvement judgment references an unknown candidate.")
        connected = {
            item.id
            for item in self.decisions
            if item.disposition is EventEntityConnectionDisposition.CONNECTED
        }
        if {item.decision_id for item in self.drafts} != connected:
            raise ValueError("Connection drafts must match connected decisions.")
        candidate_by_id = {item.id: item for item in self.candidates}
        if any(item.candidate_id not in candidate_by_id for item in self.drafts):
            raise ValueError("Connection draft references an unknown candidate.")
        trace_ids = {item.id for item in self.traces}
        if any(
            item.trace_id not in trace_ids
            or item.extraction_task_id not in self.extraction_task_ids
            or item.model_run_id not in self.model_run_ids
            for item in self.judgments
        ):
            raise ValueError("Connection judgment execution lineage is incomplete.")
        judgment_by_id = {item.id: item for item in self.judgments}
        if any(
            item.judgment_id is not None
            and (
                item.judgment_id not in judgment_by_id
                or judgment_by_id[item.judgment_id].candidate_id != item.candidate_id
            )
            for item in self.decisions
        ):
            raise ValueError("Connection decision judgment lineage is invalid.")
        if any(
            item.trace_id not in trace_ids
            or item.extraction_task_id not in self.extraction_task_ids
            or item.model_run_id not in self.model_run_ids
            for item in self.drafts
        ):
            raise ValueError("Connection draft execution lineage is incomplete.")
        if any(
            item.entity_source_span_ids
            != tuple(span.id for span in candidate_by_id[item.candidate_id].source_spans)
            for item in self.drafts
        ):
            raise ValueError("Connection draft source evidence drifted from its candidate.")
        if any(
            item.resolved_antecedent_span_ids
            != tuple(
                span.id for span in candidate_by_id[item.candidate_id].resolved_antecedent_spans
            )
            for item in self.drafts
        ):
            raise ValueError("Connection draft antecedent evidence drifted from its candidate.")
        traced_execution_ids = {
            record_id for trace in self.traces for record_id in trace.execution_record_ids
        }
        if traced_execution_ids != set(self.extraction_task_ids) | set(self.model_run_ids):
            raise ValueError("Connection traces must cover every execution record.")
        traces_by_run: dict[str, list[ExtractionStageTrace]] = defaultdict(list)
        for trace in self.traces:
            traces_by_run[trace.trace_run_id].append(trace)
        for trace_run in traces_by_run.values():
            validate_extraction_stage_trace_chain(tuple(trace_run))
        incomplete = bool(self.candidate_gaps) or any(
            item.disposition is EventEntityConnectionDisposition.UNRESOLVED
            for item in self.decisions
        )
        expected_status = (
            EventEntityConnectionPreviewStatus.PARTIAL
            if incomplete
            else EventEntityConnectionPreviewStatus.COMPLETE
        )
        if self.terminal_status is not expected_status:
            raise ValueError("Connection Preview status does not match its decisions.")
        if (
            self.terminal_status is EventEntityConnectionPreviewStatus.PARTIAL
            and not self.diagnostics
        ):
            raise ValueError("A partial connection Preview requires diagnostics.")
        expected_id = _id(
            "eep",
            _canonical_json(self.model_dump(mode="json", exclude={"id"})),
        )
        if self.id != expected_id:
            raise ValueError("Connection Preview ID does not match its contents.")
        return self


def event_entity_connection_candidate_id(
    *,
    source_grounded_event_id: str,
    event_mention_id: str,
    entity_identity: str,
    entity_kind: EventEntityKind,
    mention_candidate_ids: tuple[str, ...],
    reference_decision_ids: tuple[str, ...],
) -> str:
    """Derive one candidate identity from the complete Event and entity evidence."""
    return _id(
        "eec",
        source_grounded_event_id,
        event_mention_id,
        entity_identity,
        entity_kind.value,
        *mention_candidate_ids,
        *reference_decision_ids,
    )


def build_event_entity_connection_candidates(
    event: SourceGroundedEventDraft,
    mentions: tuple[EventEntityMentionInput, ...],
    *,
    source_text: str,
) -> tuple[EventEntityConnectionCandidate, ...]:
    """Deduplicate source-valid entity mentions into Event-bound candidates."""
    if hashlib.sha256(source_text.encode()).hexdigest() != event.source_text_sha256:
        raise ValueError("Event entity SourceSegment digest does not match its Event.")
    grouped: dict[tuple[EventEntityKind, str], list[EventEntityMentionInput]] = defaultdict(list)
    for mention in mentions:
        source_span = mention.source_span
        if (
            source_span.source_segment_id != event.source_segment_id
            or source_span.source_text_sha256 != event.source_text_sha256
        ):
            raise ValueError("Event entity mention does not share the Event SourceSegment.")
        if (
            source_span.end > len(source_text)
            or source_text[source_span.start : source_span.end] != source_span.text
        ):
            raise ValueError("Event entity mention does not match source characters.")
        grouped[(mention.entity_kind, mention.entity_identity)].append(mention)
    candidates: list[EventEntityConnectionCandidate] = []
    for (kind, identity), values in sorted(
        grouped.items(), key=lambda item: (item[0][0].value, item[0][1])
    ):
        ordered = tuple(
            sorted(
                values,
                key=lambda item: (
                    item.source_span.start,
                    item.source_span.end,
                    item.source_span.mention_candidate_id,
                ),
            )
        )
        names = {item.entity_name for item in ordered}
        if len(names) != 1:
            raise ValueError("One entity identity cannot have conflicting resolved names.")
        primary = ordered[0]
        source_spans = tuple(item.source_span for item in ordered)
        mention_ids = tuple(item.mention_candidate_id for item in source_spans)
        antecedent_by_id = {
            item.resolved_antecedent_span.id: item.resolved_antecedent_span
            for item in ordered
            if item.resolved_antecedent_span is not None
        }
        antecedent_spans = tuple(antecedent_by_id[key] for key in sorted(antecedent_by_id))
        reference_ids = tuple(
            sorted(
                {
                    item.reference_decision_id
                    for item in source_spans
                    if item.reference_decision_id is not None
                }
            )
        )
        candidate_id = event_entity_connection_candidate_id(
            source_grounded_event_id=event.id,
            event_mention_id=event.mention.id,
            entity_identity=identity,
            entity_kind=kind,
            mention_candidate_ids=mention_ids,
            reference_decision_ids=reference_ids,
        )
        candidates.append(
            EventEntityConnectionCandidate(
                id=candidate_id,
                source_grounded_event_id=event.id,
                event_mention_id=event.mention.id,
                source_segment_id=event.source_segment_id,
                source_text_sha256=event.source_text_sha256,
                event_expression_text=event.expression_text,
                event_expression_evidence_target_id=event.mention.expression_evidence_target_id,
                support_evidence_target_id=event.mention.support_evidence_target_id,
                entity_identity=identity,
                entity_kind=kind,
                entity_name=primary.entity_name,
                primary_source_span_id=primary.source_span.id,
                source_spans=source_spans,
                resolved_antecedent_spans=antecedent_spans,
                reference_decision_ids=reference_ids,
            )
        )
    return tuple(candidates)


def select_event_entity_mentions(
    *,
    source_text: str,
    event: SourceGroundedEventDraft,
    mention_preview: HybridExtractionPreview,
    reference_preview: HybridReferencePreview,
) -> EventEntityCandidateSelection:
    """Map effective upstream mention evidence into Actor and Organization inputs."""
    source_digest = hashlib.sha256(source_text.encode()).hexdigest()
    if source_digest != event.source_text_sha256:
        raise ValueError("Event entity selection SourceSegment does not match its Event.")
    if reference_preview.parent_preview_id != mention_preview.id:
        raise ValueError("Event entity reference evidence names another mention Preview.")
    selected = set(
        effective_mention_candidate_ids(
            mention_preview.boundary_decisions,
            mention_preview.boundary_adjudications,
        )
    )
    ambiguous = set(
        unresolved_mention_candidate_ids(
            mention_preview.boundary_decisions,
            mention_preview.boundary_adjudications,
        )
    )
    interpretations = {item.candidate_id: item for item in mention_preview.interpretations}
    references = {item.candidate_id: item for item in reference_preview.reference_decisions}
    antecedents = _reference_spans(reference_preview)
    mentions: list[EventEntityMentionInput] = []
    gaps: list[EventEntityCandidateGap] = []
    for candidate in mention_preview.candidates:
        if candidate.source_segment_id != event.source_segment_id:
            continue
        _validate_candidate_source(candidate, source_text, source_digest)
        reference = references.get(candidate.id)
        if candidate.id in ambiguous:
            gaps.append(
                _candidate_gap(
                    candidate,
                    EventEntityCandidateGapReason.BOUNDARY_AMBIGUOUS,
                    reference,
                )
            )
            continue
        if candidate.id not in selected:
            continue
        interpretation = interpretations.get(candidate.id)
        if interpretation is None:
            gaps.append(
                _candidate_gap(
                    candidate,
                    EventEntityCandidateGapReason.INTERPRETATION_MISSING,
                    reference,
                )
            )
            continue
        kind = _event_entity_kind(interpretation)
        if kind is None:
            if interpretation.contextual_kind is ContextualKind.UNCLEAR:
                gaps.append(
                    _candidate_gap(
                        candidate,
                        EventEntityCandidateGapReason.ENTITY_KIND_AMBIGUOUS,
                        reference,
                    )
                )
            continue
        if interpretation.referentiality is Referentiality.GENERIC_CLASS:
            continue
        resolved_antecedent: ReferenceSpan | None = None
        resolved_name = _trim_possessive(candidate.text)
        reference_id: str | None = None
        if interpretation.referentiality is Referentiality.ANAPHORIC:
            if reference is None or reference.status is ReferenceStatus.UNRESOLVED:
                gaps.append(
                    _candidate_gap(
                        candidate,
                        EventEntityCandidateGapReason.REFERENCE_UNRESOLVED,
                        reference,
                    )
                )
                continue
            if reference.status is ReferenceStatus.AMBIGUOUS:
                gaps.append(
                    _candidate_gap(
                        candidate,
                        EventEntityCandidateGapReason.REFERENCE_AMBIGUOUS,
                        reference,
                    )
                )
                continue
            if len(reference.antecedent_span_ids) != 1:
                gaps.append(
                    _candidate_gap(
                        candidate,
                        EventEntityCandidateGapReason.REFERENCE_ANTECEDENT_MISSING,
                        reference,
                    )
                )
                continue
            resolved_antecedent = antecedents.get(reference.antecedent_span_ids[0])
            if resolved_antecedent is None:
                gaps.append(
                    _candidate_gap(
                        candidate,
                        EventEntityCandidateGapReason.REFERENCE_ANTECEDENT_MISSING,
                        reference,
                    )
                )
                continue
            resolved_name = _trim_possessive(resolved_antecedent.text)
            reference_id = reference.id
        elif reference is not None and reference.status is ReferenceStatus.RESOLVED:
            reference_id = reference.id
            if len(reference.antecedent_span_ids) == 1:
                resolved_antecedent = antecedents.get(reference.antecedent_span_ids[0])
                if resolved_antecedent is not None:
                    resolved_name = _trim_possessive(resolved_antecedent.text)
        if not resolved_name:
            gaps.append(
                _candidate_gap(
                    candidate,
                    EventEntityCandidateGapReason.REFERENCE_ANTECEDENT_MISSING,
                    reference,
                )
            )
            continue
        source_span = _source_span(candidate, reference_id)
        mentions.append(
            EventEntityMentionInput(
                entity_identity=_local_entity_identity(kind, resolved_name),
                entity_kind=kind,
                entity_name=resolved_name,
                source_span=source_span,
                resolved_antecedent_span=resolved_antecedent,
            )
        )
    return EventEntityCandidateSelection(
        mentions=tuple(
            sorted(
                mentions,
                key=lambda item: (
                    item.source_span.start,
                    item.source_span.end,
                    item.source_span.mention_candidate_id,
                ),
            )
        ),
        gaps=tuple(
            sorted(
                gaps,
                key=lambda item: (
                    item.mention_start,
                    item.mention_end,
                    item.mention_candidate_id,
                ),
            )
        ),
    )


def build_entity_involvement_judgment(
    *,
    candidate_id: str,
    answer: EntityInvolvementAnswerValue,
    extraction_task_id: str,
    model_run_id: str,
    trace_id: str,
) -> EntityInvolvementJudgment:
    """Bind one finite model answer to its KoteKomi-owned candidate."""
    return EntityInvolvementJudgment(
        id=_id("eij", candidate_id, answer.value, extraction_task_id, model_run_id, trace_id),
        candidate_id=candidate_id,
        answer=answer,
        extraction_task_id=extraction_task_id,
        model_run_id=model_run_id,
        trace_id=trace_id,
    )


def decide_event_entity_connection(
    candidate: EventEntityConnectionCandidate,
    judgment: EntityInvolvementJudgment | None,
) -> tuple[EventEntityConnectionDecision, EventEntityConnectionDraft | None]:
    """Map one finite answer into a deterministic disposition and optional draft."""
    if judgment is not None and judgment.candidate_id != candidate.id:
        raise ValueError("Entity involvement judgment names another candidate.")
    if judgment is None:
        disposition = EventEntityConnectionDisposition.UNRESOLVED
        reason = "model_judgment_failed"
        judgment_id = None
    elif judgment.answer is EntityInvolvementAnswerValue.YES:
        disposition = EventEntityConnectionDisposition.CONNECTED
        reason = "model_confirmed_involvement"
        judgment_id = judgment.id
    elif judgment.answer is EntityInvolvementAnswerValue.NO:
        disposition = EventEntityConnectionDisposition.NOT_CONNECTED
        reason = "model_rejected_involvement"
        judgment_id = judgment.id
    else:
        disposition = EventEntityConnectionDisposition.UNRESOLVED
        reason = "model_uncertain"
        judgment_id = judgment.id
    decision = EventEntityConnectionDecision(
        id=_id("ecd", candidate.id, judgment_id or "", disposition.value, reason),
        candidate_id=candidate.id,
        judgment_id=judgment_id,
        disposition=disposition,
        reason_code=reason,
    )
    if disposition is not EventEntityConnectionDisposition.CONNECTED:
        return decision, None
    assert judgment is not None
    draft_values = (
        candidate.id,
        decision.id,
        candidate.source_grounded_event_id,
        candidate.event_mention_id,
        candidate.entity_identity,
        candidate.entity_kind.value,
        candidate.event_expression_evidence_target_id,
        *(item.id for item in candidate.source_spans),
        *(item.id for item in candidate.resolved_antecedent_spans),
        candidate.support_evidence_target_id,
        judgment.extraction_task_id,
        judgment.model_run_id,
        judgment.trace_id,
    )
    return decision, EventEntityConnectionDraft(
        id=_id("eed", *draft_values),
        candidate_id=candidate.id,
        decision_id=decision.id,
        source_grounded_event_id=candidate.source_grounded_event_id,
        event_mention_id=candidate.event_mention_id,
        entity_identity=candidate.entity_identity,
        entity_kind=candidate.entity_kind,
        entity_name=candidate.entity_name,
        event_expression_evidence_target_id=candidate.event_expression_evidence_target_id,
        entity_source_span_ids=tuple(item.id for item in candidate.source_spans),
        resolved_antecedent_span_ids=tuple(item.id for item in candidate.resolved_antecedent_spans),
        support_evidence_target_id=candidate.support_evidence_target_id,
        extraction_task_id=judgment.extraction_task_id,
        model_run_id=judgment.model_run_id,
        trace_id=judgment.trace_id,
    )


def event_entity_model_task_input(
    source_text: str,
    candidate: EventEntityConnectionCandidate,
) -> bytes:
    """Render one ID-free Event-entity semantic question."""
    if hashlib.sha256(source_text.encode()).hexdigest() != candidate.source_text_sha256:
        raise ValueError("Event entity task SourceSegment digest does not match.")
    primary = next(
        item for item in candidate.source_spans if item.id == candidate.primary_source_span_id
    )
    if primary.end > len(source_text) or source_text[primary.start : primary.end] != primary.text:
        raise ValueError("Event entity task mention does not match source characters.")
    return (
        "\n".join(
            (
                "Source sentence as a JSON string:",
                json.dumps(source_text, ensure_ascii=False),
                "Marked event expression as a JSON string:",
                json.dumps(candidate.event_expression_text, ensure_ascii=False),
                "Marked entity expression as a JSON string:",
                json.dumps(primary.text, ensure_ascii=False),
                "Resolved entity name as a JSON string:",
                json.dumps(candidate.entity_name, ensure_ascii=False),
            )
        )
        + "\n"
    ).encode()


def _event_entity_kind(
    interpretation: MentionInterpretation,
) -> EventEntityKind | None:
    if interpretation.contextual_kind is ContextualKind.PERSON:
        return EventEntityKind.ACTOR
    if interpretation.contextual_kind in {
        ContextualKind.ORGANIZATION,
        ContextualKind.GOVERNMENT,
    }:
        return EventEntityKind.ORGANIZATION
    return None


def _reference_spans(preview: HybridReferencePreview) -> dict[str, ReferenceSpan]:
    values: dict[str, ReferenceSpan] = {item.id: item for item in preview.semantic_antecedent_spans}
    for declaration in preview.alias_declarations:
        for span in (declaration.expanded_span, declaration.alias_span):
            existing = values.get(span.id)
            if existing is not None and existing != span:
                raise ValueError("Reference evidence repeats one span with changed contents.")
            values[span.id] = span
    return values


def _validate_candidate_source(
    candidate: MentionCandidate,
    source_text: str,
    source_digest: str,
) -> None:
    if candidate.source_text_sha256 != source_digest:
        raise ValueError("MentionCandidate SourceSegment digest does not match.")
    if (
        candidate.end > len(source_text)
        or source_text[candidate.start : candidate.end] != candidate.text
    ):
        raise ValueError("MentionCandidate does not replay authoritative characters.")


def _source_span(
    candidate: MentionCandidate,
    reference_decision_id: str | None,
) -> EventEntitySourceSpan:
    values = (
        candidate.source_segment_id,
        candidate.source_text_sha256,
        str(candidate.start),
        str(candidate.end),
        candidate.text,
        candidate.id,
        reference_decision_id or "",
    )
    return EventEntitySourceSpan(
        id=_id("ees", *values),
        source_segment_id=candidate.source_segment_id,
        source_text_sha256=candidate.source_text_sha256,
        start=candidate.start,
        end=candidate.end,
        text=candidate.text,
        mention_candidate_id=candidate.id,
        reference_decision_id=reference_decision_id,
    )


def _candidate_gap(
    candidate: MentionCandidate,
    reason: EventEntityCandidateGapReason,
    reference: ReferenceDecision | None,
) -> EventEntityCandidateGap:
    values = (
        candidate.source_segment_id,
        candidate.source_text_sha256,
        candidate.id,
        str(candidate.start),
        str(candidate.end),
        candidate.text,
        reason.value,
        reference.id if reference is not None else "",
    )
    return EventEntityCandidateGap(
        id=_id("ecg", *values),
        source_segment_id=candidate.source_segment_id,
        source_text_sha256=candidate.source_text_sha256,
        mention_candidate_id=candidate.id,
        mention_start=candidate.start,
        mention_end=candidate.end,
        mention_text=candidate.text,
        reason=reason,
        reference_decision_id=reference.id if reference is not None else None,
    )


def _trim_possessive(value: str) -> str:
    stripped = value.strip()
    for suffix in ("'s", "’s"):
        if stripped.casefold().endswith(suffix):
            return stripped[: -len(suffix)].rstrip()
    return stripped


def _local_entity_identity(kind: EventEntityKind, name: str) -> str:
    normalized = " ".join(name.casefold().split())
    return _id("lei", kind.value, normalized)


def build_event_entity_connection_preview(**values: object) -> EventEntityConnectionPreview:
    """Construct one content-addressed terminal experiment Preview."""
    payload = dict(values)
    payload.setdefault("schema_version", "event_entity_connection_preview_v1")
    payload.setdefault("policy_id", EVENT_ENTITY_CONNECTION_POLICY_ID)
    json_payload = cast(dict[str, JsonValue], _json_copy(payload))
    json_payload["id"] = _id("eep", _canonical_json(json_payload))
    return EventEntityConnectionPreview.model_validate_json(_canonical_json(json_payload))


def canonical_event_entity_connection_preview_bytes(
    preview: EventEntityConnectionPreview,
) -> bytes:
    """Serialize one Preview through its declared contract."""
    return _canonical_json(preview.model_dump(mode="json")).encode()


def _ordered_distinct(label: str, values: tuple[str, ...]) -> None:
    if len(set(values)) != len(values):
        raise ValueError(f"{label} must be distinct.")


def _id(prefix: str, *values: str) -> str:
    digest = hashlib.sha256(chr(31).join(values).encode()).hexdigest()
    return f"{prefix}_{digest[:24]}"


def _json_copy(value: object) -> JsonValue:
    return cast(
        JsonValue,
        json.loads(json.dumps(value, ensure_ascii=False, default=_json_default)),
    )


def _json_default(value: object) -> object:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, tuple):
        return list(cast(tuple[object, ...], value))
    raise TypeError(f"Unsupported Event-entity value: {type(value).__name__}")


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
