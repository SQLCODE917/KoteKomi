"""HP-10 source-bound standing-fact proposal planning."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal, Protocol, Self, cast

from kotekomi_domain import (
    Actor,
    AssertionType,
    AttributionBasis,
    Document,
    DocumentRepresentationBundle,
    EpistemicScope,
    EvidenceNecessity,
    EvidencePolarity,
    EvidenceTarget,
    EvidenceValidationAttempt,
    EvidenceValidationAttemptStatus,
    ModelRunStatus,
    Organization,
    ProposedAssertion,
    Source,
    SourceAuthority,
    StandingFactQualificationOutcome,
    canonical_evidence_target_digest,
)
from kotekomi_domain.models import JsonValue
from pydantic import BaseModel, ConfigDict, Field, model_validator

from kotekomi_application.context_planning import (
    HYBRID_MENTION_EVIDENCE_SELECTION_V1,
    PARAGRAPH_SEGMENT_V3,
    ContextManifest,
    ContextManifestInput,
    ContextManifestStatus,
    ContextModelProfile,
    ContextTokenizer,
    RetrievalSelectionAnalysisUnitInput,
    SourceSegment,
    build_context_manifest,
    create_analysis_unit_from_retrieval_selection,
    derive_source_copy_view,
    paragraph_source_segments,
    verify_context_manifest,
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
    validate_extraction_stage_trace_chain,
)
from kotekomi_application.hybrid_document_references import (
    HybridReferencePreview,
    ReferenceStatus,
    canonical_hybrid_reference_preview_bytes,
    hybrid_reference_preview_from_bytes,
)
from kotekomi_application.hybrid_event_semantics_preview import (
    HybridEventSemanticsLedger,
    load_hybrid_event_semantics_preview,
)
from kotekomi_application.hybrid_event_trigger_preview import (
    load_hybrid_event_trigger_preview,
    source_occurrences,
)
from kotekomi_application.hybrid_mention_boundary_adjudication import (
    effective_mention_candidate_ids,
)
from kotekomi_application.hybrid_mention_interpretation import (
    ContextualKind,
    DiscourseRole,
    HybridExtractionPreview,
    MentionCandidate,
    MentionInterpretation,
    Referentiality,
    canonical_hybrid_extraction_preview_bytes,
    hybrid_extraction_preview_from_bytes,
    hybrid_source_segment_id,
)
from kotekomi_application.hybrid_proposed_changes import (
    HybridProposalArchive,
    HybridProposalLedger,
    HybridProposalPlan,
    PlannedProposedChange,
    canonical_hybrid_proposal_plan_bytes,
    load_hybrid_proposal_plan,
    validate_planned_proposed_changes,
)
from kotekomi_application.hybrid_standing_fact_model_output import (
    StandingFactObjectKind,
    StandingFactProposal,
    StandingFactProposalBatch,
    parse_standing_fact_output,
    standing_fact_schema_bytes,
)
from kotekomi_application.hybrid_standing_fact_qualification_model_output import (
    StandingFactQualificationOutput,
    parse_standing_fact_qualification_output,
    standing_fact_qualification_schema_bytes,
)
from kotekomi_application.semantic_proposition import (
    CompleteProposition,
    NaturalLanguageInferenceInput,
    NaturalLanguageInferencePort,
    NliObservation,
    PropositionDecision,
    PropositionDisposition,
    PropositionKind,
    build_complete_proposition,
    build_nli_observation,
    build_proposition_decision,
)
from kotekomi_application.source_occurrences import SourceOccurrence
from kotekomi_application.staged_model_extraction import (
    BoundedExtractionInput,
    ExecutionSetting,
    ModelExecutionSpec,
    ModelRunIdFactory,
    ModelTaskRuntime,
    PinnedTaskSchema,
    StagedExtractionLedger,
    TaskSchemaRegistry,
    run_bounded_extraction,
)

HYBRID_STANDING_FACT_POLICY_ID = "hybrid_standing_fact_v6"
HYBRID_STANDING_FACT_SCHEMA_ID = "hybrid_standing_fact_text_v3"
HYBRID_STANDING_FACT_PROMPT_ID = "hybrid_standing_fact_task_v3"
HYBRID_STANDING_FACT_QUALIFICATION_SCHEMA_ID = "standing_fact_qualification_text_v1"
HYBRID_STANDING_FACT_QUALIFICATION_PROMPT_ID = "hybrid_standing_fact_qualification_v1"
HYBRID_STANDING_FACT_EVIDENCE_VALIDATOR = "hybrid_standing_fact_evidence_v1"
HYBRID_STANDING_FACT_ACTIVITY_TYPE = "hybrid_standing_fact_batch_planned"
HYBRID_STANDING_FACT_NLI_ENTAILMENT_THRESHOLD = 0.5
_SHA256 = r"^[a-f0-9]{64}$"


class StandingFactDisposition(StrEnum):
    PROPOSED = "proposed"
    HELD = "held"


class StandingFactHoldReason(StrEnum):
    COMPLETE_PROPOSITION_HELD = "complete_proposition_held"
    EVENT_ROUTE_REQUIRED = "event_route_required"
    INCOMPLETE_OR_WRONG_ARGUMENTS = "incomplete_or_wrong_arguments"
    UNKNOWN_SUBJECT = "unknown_subject"
    UNKNOWN_ENTITY_OBJECT = "unknown_entity_object"
    SELF_RELATION = "self_relation"
    LITERAL_NOT_IN_SOURCE = "literal_not_in_source"
    PROPOSITION_NOT_SOURCE_ORDERED = "proposition_not_source_ordered"
    QUALIFICATION_AMBIGUOUS = "qualification_ambiguous"
    QUALIFICATION_MISSING = "qualification_missing"
    RELATION_OVERLAPS_MENTION = "relation_overlaps_mention"
    SEMANTICALLY_UNSUPPORTED = "semantically_unsupported"
    SOURCE_SPAN_MISMATCH = "source_span_mismatch"


class StandingFactPlanStatus(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"


class StandingFactObjectMapping(StrEnum):
    """How KoteKomi mapped a fallible literal selector to authoritative characters."""

    EXACT_SELECTOR = "exact_selector"
    COMPLETED_POST_RELATION = "completed_post_relation"


class StandingFactDraft(BaseModel):
    """One parsed model proposal with deterministic source mapping."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: Annotated[str, Field(pattern=r"^sfd_[a-f0-9]{24}$")]
    source_segment_id: Annotated[str, Field(min_length=1)]
    subject_label: Annotated[str, Field(min_length=1)]
    subject_candidate_id: str | None = None
    subject_text: Annotated[str, Field(min_length=1)] | None = None
    subject_start: Annotated[int, Field(ge=0)] | None = None
    subject_end: Annotated[int, Field(gt=0)] | None = None
    relation_label: Annotated[str, Field(min_length=1, max_length=160)]
    relation_start: Annotated[int, Field(ge=0)]
    relation_end: Annotated[int, Field(gt=0)]
    object_kind: StandingFactObjectKind
    object_selector: Annotated[
        str,
        Field(pattern=r"^(?:c[1-9][0-9]*|o[1-9][0-9]*(?:-o[1-9][0-9]*)?)$"),
    ]
    object_mapping: StandingFactObjectMapping
    object_text: Annotated[str, Field(min_length=1)]
    object_start: Annotated[int, Field(ge=0)] | None = None
    object_end: Annotated[int, Field(gt=0)] | None = None
    object_candidate_id: str | None = None
    extraction_task_id: Annotated[str, Field(min_length=1)]
    model_run_id: Annotated[str, Field(min_length=1)]

    @model_validator(mode="after")
    def validate_identity(self) -> Self:
        if self.relation_end - self.relation_start != len(self.relation_label):
            raise ValueError("StandingFactDraft relation range does not match its text.")
        subject_values = (self.subject_text, self.subject_start, self.subject_end)
        if self.subject_candidate_id is None:
            if any(value is not None for value in subject_values):
                raise ValueError("An unresolved Standing Fact subject cannot have a source span.")
        elif self.subject_text is None or self.subject_start is None or self.subject_end is None:
            raise ValueError("A resolved Standing Fact subject requires its exact source span.")
        elif self.subject_end - self.subject_start != len(self.subject_text):
            raise ValueError("StandingFactDraft subject range does not match its text.")
        if self.object_kind is StandingFactObjectKind.LITERAL and self.object_candidate_id:
            raise ValueError("A literal Standing Fact cannot name an object candidate.")
        if (
            self.object_kind is StandingFactObjectKind.LITERAL
            and not self.object_selector.startswith("o")
        ):
            raise ValueError("A literal Standing Fact requires a source-occurrence selector.")
        if (
            self.object_kind is StandingFactObjectKind.ENTITY
            and not self.object_selector.startswith("c")
        ):
            raise ValueError("An entity Standing Fact requires a candidate selector.")
        object_values = (self.object_start, self.object_end)
        if self.object_kind is StandingFactObjectKind.LITERAL:
            if any(value is None for value in object_values):
                raise ValueError("A literal Standing Fact requires an exact source span.")
        elif self.object_candidate_id is None:
            if any(value is not None for value in object_values):
                raise ValueError("An unresolved entity object cannot have a source span.")
        elif any(value is None for value in object_values):
            raise ValueError("A resolved entity object requires its exact source span.")
        if (
            self.object_start is not None
            and self.object_end is not None
            and self.object_end - self.object_start != len(self.object_text)
        ):
            raise ValueError("StandingFactDraft object range does not match its text.")
        expected = _id(
            "sfd",
            self.source_segment_id,
            self.subject_label,
            self.subject_candidate_id or "",
            self.subject_text or "",
            str(self.subject_start) if self.subject_start is not None else "",
            str(self.subject_end) if self.subject_end is not None else "",
            self.relation_label,
            str(self.relation_start),
            str(self.relation_end),
            self.object_kind.value,
            self.object_selector,
            self.object_mapping.value,
            self.object_text,
            str(self.object_start) if self.object_start is not None else "",
            str(self.object_end) if self.object_end is not None else "",
            self.object_candidate_id or "",
            self.extraction_task_id,
            self.model_run_id,
        )
        if self.id != expected:
            raise ValueError("StandingFactDraft ID does not match its contents.")
        return self


class StandingFactRelationSpan(BaseModel):
    """One deterministic standing relation reconstructed from source occurrences."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    start: Annotated[int, Field(ge=0)]
    end: Annotated[int, Field(gt=0)]
    text: Annotated[str, Field(min_length=1)]

    @model_validator(mode="after")
    def validate_range(self) -> Self:
        if self.end <= self.start or self.end - self.start != len(self.text):
            raise ValueError("StandingFactRelationSpan range does not match its text.")
        return self


class StandingFactQualification(BaseModel):
    """One fallible Qwen classification of a complete standing proposition."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: Annotated[str, Field(pattern=r"^sfq_[a-f0-9]{24}$")]
    draft_id: Annotated[str, Field(pattern=r"^sfd_[a-f0-9]{24}$")]
    proposition_id: Annotated[str, Field(pattern=r"^cpr_[a-f0-9]{24}$")]
    outcome: StandingFactQualificationOutcome
    reason: Annotated[str, Field(min_length=1)]
    extraction_task_id: Annotated[str, Field(min_length=1)]
    model_run_id: Annotated[str, Field(min_length=1)]

    @model_validator(mode="after")
    def validate_identity(self) -> Self:
        if self.reason != self.reason.strip() or "\n" in self.reason or "\r" in self.reason:
            raise ValueError("Standing Fact qualification reason must be one trimmed line.")
        expected = _id(
            "sfq",
            self.draft_id,
            self.proposition_id,
            self.outcome.value,
            self.reason,
            self.extraction_task_id,
            self.model_run_id,
        )
        if self.id != expected:
            raise ValueError("StandingFactQualification ID does not match its contents.")
        return self


class StandingFactDecision(BaseModel):
    """One deterministic admission decision for one StandingFactDraft."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: Annotated[str, Field(pattern=r"^sfdc_[a-f0-9]{24}$")]
    draft_id: Annotated[str, Field(pattern=r"^sfd_[a-f0-9]{24}$")]
    disposition: StandingFactDisposition
    qualification_id: Annotated[str, Field(pattern=r"^sfq_[a-f0-9]{24}$")] | None = None
    proposition_decision_id: Annotated[str, Field(pattern=r"^pdc_[a-f0-9]{24}$")] | None = None
    reason_codes: tuple[StandingFactHoldReason, ...] = ()
    proposed_change_ids: tuple[Annotated[str, Field(pattern=r"^pcg_[a-f0-9]{24}$")], ...] = ()

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        _ordered_distinct("Standing Fact reason codes", tuple(x.value for x in self.reason_codes))
        _ordered_distinct("Standing Fact ProposedChange IDs", self.proposed_change_ids)
        if self.disposition is StandingFactDisposition.PROPOSED:
            if (
                self.reason_codes
                or not self.proposed_change_ids
                or self.qualification_id is None
                or self.proposition_decision_id is None
            ):
                raise ValueError("A proposed Standing Fact requires semantic evidence and changes.")
        elif not self.reason_codes or self.proposed_change_ids:
            raise ValueError("A held Standing Fact requires reasons and no changes.")
        expected = _id(
            "sfdc",
            self.draft_id,
            self.disposition.value,
            self.qualification_id or "",
            self.proposition_decision_id or "",
            *(x.value for x in self.reason_codes),
            *self.proposed_change_ids,
        )
        if self.id != expected:
            raise ValueError("StandingFactDecision ID does not match its contents.")
        return self


class StandingFactPlan(BaseModel):
    """Immutable combined event and standing-fact paragraph proposal plan."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["standing_fact_plan_v6"] = "standing_fact_plan_v6"
    id: Annotated[str, Field(pattern=r"^sfp_[a-f0-9]{24}$")]
    parent_plan_id: Annotated[str, Field(pattern=r"^hpp_[a-f0-9]{24}$")]
    parent_plan_sha256: Annotated[str, Field(pattern=_SHA256)]
    mention_preview_id: Annotated[str, Field(pattern=r"^hxp_[a-f0-9]{24}$")]
    mention_preview_sha256: Annotated[str, Field(pattern=_SHA256)]
    reference_preview_id: Annotated[str, Field(pattern=r"^hrp_[a-f0-9]{24}$")]
    reference_preview_sha256: Annotated[str, Field(pattern=_SHA256)]
    representation_id: Annotated[str, Field(min_length=1)]
    paragraph_node_id: Annotated[str, Field(min_length=1)]
    context_manifest_id: str | None = None
    qualification_context_manifest_id: str | None = None
    policy_id: Literal["hybrid_standing_fact_v6"] = HYBRID_STANDING_FACT_POLICY_ID
    provenance_activity_id: Annotated[str, Field(pattern=r"^prv_[a-f0-9]{24}$")]
    drafts: tuple[StandingFactDraft, ...] = ()
    propositions: tuple[CompleteProposition, ...] = ()
    qualifications: tuple[StandingFactQualification, ...] = ()
    nli_observations: tuple[NliObservation, ...] = ()
    proposition_decisions: tuple[PropositionDecision, ...] = ()
    decisions: tuple[StandingFactDecision, ...] = ()
    extraction_task_ids: tuple[Annotated[str, Field(min_length=1)], ...] = ()
    model_run_ids: tuple[Annotated[str, Field(min_length=1)], ...] = ()
    traces: tuple[ExtractionStageTrace, ...] = ()
    proposed_changes: tuple[PlannedProposedChange, ...] = ()
    terminal_status: StandingFactPlanStatus
    diagnostics: tuple[Annotated[str, Field(min_length=1)], ...] = ()

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        for label, values in (
            ("Standing Fact draft IDs", tuple(x.id for x in self.drafts)),
            ("Standing Fact proposition IDs", tuple(x.id for x in self.propositions)),
            ("Standing Fact qualification IDs", tuple(x.id for x in self.qualifications)),
            ("Standing Fact NLI observation IDs", tuple(x.id for x in self.nli_observations)),
            (
                "Standing Fact proposition decision IDs",
                tuple(x.id for x in self.proposition_decisions),
            ),
            ("Standing Fact decision IDs", tuple(x.id for x in self.decisions)),
            ("Standing Fact task IDs", self.extraction_task_ids),
            ("Standing Fact ModelRun IDs", self.model_run_ids),
            ("Standing Fact trace IDs", tuple(x.id for x in self.traces)),
            ("Standing Fact ProposedChange IDs", tuple(x.id for x in self.proposed_changes)),
            ("Standing Fact diagnostics", self.diagnostics),
        ):
            _ordered_distinct(label, values)
        if len(self.extraction_task_ids) != len(self.model_run_ids):
            raise ValueError("Every Standing Fact task requires one ModelRun.")
        trace_execution_ids = {item for trace in self.traces for item in trace.execution_record_ids}
        if not set(self.extraction_task_ids).issubset(trace_execution_ids):
            raise ValueError("Every Standing Fact task requires stage trace evidence.")
        if {x.draft_id for x in self.decisions} != {x.id for x in self.drafts}:
            raise ValueError("Standing Fact decisions must cover every mapped draft.")
        if len(self.decisions) != len(self.drafts):
            raise ValueError("Each Standing Fact draft requires exactly one decision.")
        proposition_by_draft = {item.subject_record_id: item for item in self.propositions}
        qualification_by_id = {item.id: item for item in self.qualifications}
        proposition_decision_by_id = {item.id: item for item in self.proposition_decisions}
        for decision in self.decisions:
            if decision.qualification_id is None and decision.proposition_decision_id is None:
                continue
            qualification = qualification_by_id.get(decision.qualification_id or "")
            proposition_decision = proposition_decision_by_id.get(
                decision.proposition_decision_id or ""
            )
            proposition = proposition_by_draft.get(decision.draft_id)
            if (
                qualification is None
                or proposition_decision is None
                or proposition is None
                or qualification.draft_id != decision.draft_id
                or qualification.proposition_id != proposition.id
                or proposition_decision.proposition_id != proposition.id
            ):
                raise ValueError("Standing Fact decision semantic evidence does not match.")
        planned_ids = {x.id for x in self.proposed_changes}
        if any(not set(x.proposed_change_ids).issubset(planned_ids) for x in self.decisions):
            raise ValueError("Standing Fact decision references an unknown ProposedChange.")
        if any(
            x.provenance_activity_id != self.provenance_activity_id for x in self.proposed_changes
        ):
            raise ValueError("Standing Fact changes must share one provenance activity.")
        traces_by_run: dict[str, list[ExtractionStageTrace]] = defaultdict(list)
        for trace in self.traces:
            traces_by_run[trace.trace_run_id].append(trace)
        for traces in traces_by_run.values():
            validate_extraction_stage_trace_chain(
                tuple(sorted(traces, key=lambda item: item.ordinal))
            )
        if self.terminal_status is StandingFactPlanStatus.COMPLETE and self.diagnostics:
            raise ValueError("A complete Standing Fact Plan cannot record diagnostics.")
        if self.id != _content_id("sfp", self.model_dump(mode="json", exclude={"id"})):
            raise ValueError("StandingFactPlan ID does not match its contents.")
        return self


class HybridStandingFactLedger(
    HybridProposalLedger,
    StagedExtractionLedger,
    EvidenceTargetLedger,
    Protocol,
):
    pass


class HybridStandingFactArchive(HybridProposalArchive, Protocol):
    def put_standing_fact_plan(
        self,
        plan: StandingFactPlan,
        payload: bytes,
        expected_sha256: str,
    ) -> object: ...

    def read_standing_fact_plan(self, plan_id: str) -> bytes: ...


@dataclass(frozen=True)
class HybridStandingFactCommand:
    parent_plan_id: str
    model_profile: ContextModelProfile
    generation_parameters: tuple[ExecutionSetting, ...]
    recorded_at: datetime


@dataclass(frozen=True)
class HybridStandingFactResult:
    plan: StandingFactPlan
    sha256: str
    archive_path: str


@dataclass(frozen=True)
class _EligibleMention:
    label: str
    candidate: MentionCandidate
    interpretation: MentionInterpretation
    display_name: str
    identity_key: str
    record_type: Literal["Actor", "Organization"]


@dataclass(frozen=True)
class _SourceContext:
    parent_plan: HybridProposalPlan
    mentions: HybridExtractionPreview
    references: HybridReferencePreview
    bundle: DocumentRepresentationBundle
    document: Document
    source: Source
    paragraph_text: str
    segments: tuple[SourceSegment, ...]
    segment_ids: dict[str, str]
    event_trigger_ranges: dict[str, tuple[tuple[int, int, str], ...]]


@dataclass(frozen=True)
class _TaskObservation:
    segment: SourceSegment
    segment_id: str
    candidates: tuple[_EligibleMention, ...]
    source_occurrences: tuple[SourceOccurrence, ...]
    extraction_task_id: str
    model_run_id: str
    model_status: ModelRunStatus
    raw_output_sha256: str | None
    abstention_reason: str | None
    batch: StandingFactProposalBatch | None


@dataclass(frozen=True)
class _MappingRejection:
    proposal: StandingFactProposal
    reason: str


@dataclass(frozen=True)
class _QualificationObservation:
    draft: StandingFactDraft
    proposition: CompleteProposition
    source_text: str
    extraction_task_id: str
    model_run_id: str
    model_status: ModelRunStatus
    raw_output_sha256: str | None
    qualification: StandingFactQualification | None
    nli_observation: NliObservation | None
    proposition_decision: PropositionDecision | None
    nli_error: str | None


class _StandingFactSchemaRegistry:
    def resolve(self, schema_id: str) -> PinnedTaskSchema:
        if schema_id == HYBRID_STANDING_FACT_SCHEMA_ID:
            return PinnedTaskSchema(
                schema_id,
                standing_fact_schema_bytes(),
                schema_id,
                parse_standing_fact_output,
            )
        if schema_id == HYBRID_STANDING_FACT_QUALIFICATION_SCHEMA_ID:
            return PinnedTaskSchema(
                schema_id,
                standing_fact_qualification_schema_bytes(),
                schema_id,
                parse_standing_fact_qualification_output,
            )
        raise ValueError(f"Unsupported Standing Fact schema: {schema_id}")


def run_hybrid_standing_fact_plan(
    *,
    command: HybridStandingFactCommand,
    ledger: HybridStandingFactLedger,
    archive: HybridStandingFactArchive,
    model_runtime: ModelTaskRuntime,
    model_run_id_factory: ModelRunIdFactory,
    tokenizer: ContextTokenizer,
    prompt_bytes: bytes,
    qualification_prompt_bytes: bytes,
    nli_runtime: NaturalLanguageInferencePort,
) -> HybridStandingFactResult:
    """Propose paragraph-local standing facts without writing accepted state."""
    context = _load_context(command.parent_plan_id, ledger, archive)
    candidates_by_segment = _eligible_candidates(context)
    registry: TaskSchemaRegistry = _StandingFactSchemaRegistry()
    schema = registry.resolve(HYBRID_STANDING_FACT_SCHEMA_ID)
    manifest = (
        _build_manifest(
            context,
            command.model_profile,
            prompt_bytes,
            schema,
            ledger,
            tokenizer,
            prompt_id=HYBRID_STANDING_FACT_PROMPT_ID,
            task_type="hybrid_standing_fact_proposal",
        )
        if candidates_by_segment
        else None
    )
    qualification_schema = registry.resolve(HYBRID_STANDING_FACT_QUALIFICATION_SCHEMA_ID)
    observations: list[_TaskObservation] = []
    for segment in context.segments:
        segment_id = context.segment_ids[segment.label]
        candidates = candidates_by_segment.get(segment_id, ())
        if not candidates:
            continue
        assert manifest is not None
        occurrences = source_occurrences(derive_source_copy_view(segment.exact_text))
        task_input = _task_input(segment, candidates, occurrences)
        outcome = run_bounded_extraction(
            BoundedExtractionInput(
                source_id=context.source.id,
                document_id=context.document.id,
                representation_id=context.bundle.representation.id,
                context_manifest_id=manifest.id,
                prompt_bytes=prompt_bytes,
                execution_spec=_execution_spec(
                    manifest,
                    model_runtime,
                    command.generation_parameters,
                    schema,
                    task_input,
                ),
                validator_version="hybrid_standing_fact_output_v3",
                task_type="hybrid_standing_fact_proposal",
                input_candidate_ids=tuple(x.candidate.id for x in candidates),
                task_local_input=task_input,
            ),
            ledger,
            archive,
            model_runtime,
            model_run_id_factory,
            tokenizer,
            registry,
        )
        observations.append(
            _TaskObservation(
                segment,
                segment_id,
                candidates,
                occurrences,
                outcome.extraction_task.id,
                outcome.model_run.id,
                outcome.model_run.status,
                outcome.model_run.output_digest,
                outcome.model_run.abstention_reason,
                outcome.standing_fact_proposals,
            )
        )

    mapped_drafts: list[StandingFactDraft] = []
    mapping_diagnostics: list[str] = []
    mapping_rejections_by_run: dict[str, list[_MappingRejection]] = defaultdict(list)
    for observation in observations:
        if observation.batch is None:
            continue
        for proposal in observation.batch.proposals:
            try:
                mapped_drafts.append(_draft(observation, proposal))
            except ValueError as error:
                mapping_rejections_by_run[observation.model_run_id].append(
                    _MappingRejection(proposal, str(error))
                )
                mapping_diagnostics.append(
                    f"standing_fact_relation_rejected:{observation.segment_id}:"
                    f"{proposal.relation_selector}:{error}"
                )
    drafts = tuple(sorted(mapped_drafts, key=lambda item: item.id))
    decisions: list[StandingFactDecision] = []
    evidence_by_segment: dict[str, tuple[EvidenceTarget, EvidenceValidationAttempt]] = {}
    candidates_by_id = {
        item.candidate.id: item for values in candidates_by_segment.values() for item in values
    }
    deterministic_reasons = {
        draft.id: _hold_reasons(draft, context, candidates_by_segment) for draft in drafts
    }
    eligible_drafts = tuple(draft for draft in drafts if not deterministic_reasons[draft.id])
    qualification_manifest = (
        _build_manifest(
            context,
            command.model_profile,
            qualification_prompt_bytes,
            qualification_schema,
            ledger,
            tokenizer,
            prompt_id=HYBRID_STANDING_FACT_QUALIFICATION_PROMPT_ID,
            task_type="hybrid_standing_fact_qualification",
        )
        if eligible_drafts
        else None
    )
    qualification_observations: list[_QualificationObservation] = []
    for draft in eligible_drafts:
        evidence = evidence_by_segment.get(draft.source_segment_id)
        if evidence is None:
            evidence = _prepare_segment_evidence(
                context,
                draft.source_segment_id,
                command.recorded_at,
                ledger,
            )
            evidence_by_segment[draft.source_segment_id] = evidence
        segment = _segment_by_id(context, draft.source_segment_id)
        proposition = build_standing_fact_proposition(
            draft,
            segment.exact_text,
            evidence[0].id,
        )
        assert qualification_manifest is not None
        task_input = _qualification_task_input(segment.exact_text, proposition)
        outcome = run_bounded_extraction(
            BoundedExtractionInput(
                source_id=context.source.id,
                document_id=context.document.id,
                representation_id=context.bundle.representation.id,
                context_manifest_id=qualification_manifest.id,
                prompt_bytes=qualification_prompt_bytes,
                execution_spec=_execution_spec(
                    qualification_manifest,
                    model_runtime,
                    command.generation_parameters,
                    qualification_schema,
                    task_input,
                ),
                validator_version="standing_fact_qualification_output_v1",
                task_type="hybrid_standing_fact_qualification",
                input_candidate_ids=(draft.id,),
                task_local_input=task_input,
            ),
            ledger,
            archive,
            model_runtime,
            model_run_id_factory,
            tokenizer,
            registry,
        )
        parsed = outcome.standing_fact_qualification
        qualification = (
            _qualification_record(
                draft,
                proposition,
                parsed,
                outcome.extraction_task.id,
                outcome.model_run.id,
            )
            if parsed is not None and outcome.model_run.status is ModelRunStatus.SUCCEEDED
            else None
        )
        nli_observation: NliObservation | None = None
        proposition_decision: PropositionDecision | None = None
        nli_error: str | None = None
        if qualification is not None:
            try:
                execution = nli_runtime.classify(
                    NaturalLanguageInferenceInput(
                        premise=segment.exact_text,
                        hypothesis=proposition.text,
                    )
                )
                nli_observation = build_nli_observation(
                    proposition_id=proposition.id,
                    premise=segment.exact_text,
                    hypothesis=proposition.text,
                    execution=execution,
                )
            except (OSError, RuntimeError, ValueError) as error:
                nli_observation = None
                nli_error = f"{type(error).__name__}: {error}"
            proposition_decision = build_proposition_decision(
                proposition_id=proposition.id,
                qwen_judgment_id=_qualification_judgment_id(qualification),
                nli_observation=nli_observation,
                qwen_directly_supported=(
                    qualification.outcome
                    is StandingFactQualificationOutcome.SUPPORTED_STANDING_FACT
                ),
                entailment_threshold=HYBRID_STANDING_FACT_NLI_ENTAILMENT_THRESHOLD,
            )
        qualification_observations.append(
            _QualificationObservation(
                draft,
                proposition,
                segment.exact_text,
                outcome.extraction_task.id,
                outcome.model_run.id,
                outcome.model_run.status,
                outcome.model_run.output_digest,
                qualification,
                nli_observation,
                proposition_decision,
                nli_error,
            )
        )
    qualification_by_draft = {item.draft.id: item for item in qualification_observations}
    provenance_id = _id(
        "prv",
        HYBRID_STANDING_FACT_ACTIVITY_TYPE,
        context.parent_plan.id,
        *(x.model_run_id for x in observations),
        *(x.id for x in drafts),
        *(x.model_run_id for x in qualification_observations),
        *(x.proposition.id for x in qualification_observations),
        *(x.qualification.id for x in qualification_observations if x.qualification is not None),
        *(
            x.nli_observation.id
            for x in qualification_observations
            if x.nli_observation is not None
        ),
        *(
            x.proposition_decision.id
            for x in qualification_observations
            if x.proposition_decision is not None
        ),
    )
    changes_by_record_id = _rewrapped_parent_changes(context.parent_plan, provenance_id)
    for draft in drafts:
        semantic = qualification_by_draft.get(draft.id)
        semantic_reasons = (
            () if deterministic_reasons[draft.id] else _semantic_hold_reasons(semantic)
        )
        reasons = tuple(
            sorted(
                {
                    *deterministic_reasons[draft.id],
                    *semantic_reasons,
                },
                key=lambda item: item.value,
            )
        )
        proposal_ids: tuple[str, ...] = ()
        if not reasons:
            evidence = evidence_by_segment.get(draft.source_segment_id)
            if evidence is None:
                evidence = _prepare_segment_evidence(
                    context,
                    draft.source_segment_id,
                    command.recorded_at,
                    ledger,
                )
                evidence_by_segment[draft.source_segment_id] = evidence
            new_changes = _standing_fact_changes(
                draft=draft,
                candidates_by_id=candidates_by_id,
                evidence=evidence,
                context=context,
                provenance_activity_id=provenance_id,
                existing_record_ids=set(changes_by_record_id),
            )
            for record_id, change in new_changes.items():
                prior = changes_by_record_id.get(record_id)
                if prior is not None and prior.proposed_json != change.proposed_json:
                    raise ValueError("HP-10 produced conflicting proposal bodies for one record.")
                changes_by_record_id.setdefault(record_id, change)
            proposal_ids = tuple(sorted(change.id for change in new_changes.values()))
        disposition = StandingFactDisposition.HELD if reasons else StandingFactDisposition.PROPOSED
        qualification_id = (
            semantic.qualification.id
            if semantic is not None and semantic.qualification is not None
            else None
        )
        proposition_decision_id = (
            semantic.proposition_decision.id
            if semantic is not None and semantic.proposition_decision is not None
            else None
        )
        decisions.append(
            StandingFactDecision(
                id=_decision_id(
                    draft.id,
                    disposition,
                    qualification_id,
                    proposition_decision_id,
                    reasons,
                    proposal_ids,
                ),
                draft_id=draft.id,
                disposition=disposition,
                qualification_id=qualification_id,
                proposition_decision_id=proposition_decision_id,
                reason_codes=reasons,
                proposed_change_ids=proposal_ids,
            )
        )

    diagnostics = tuple(sorted({*_diagnostics(observations, decisions), *mapping_diagnostics}))
    proposal_traces = tuple(
        sorted(
            (
                _trace(
                    item,
                    drafts,
                    tuple(decisions),
                    tuple(mapping_rejections_by_run[item.model_run_id]),
                    prompt_bytes,
                    schema,
                )
                for item in observations
            ),
            key=lambda item: item.id,
        )
    )
    qualification_traces = tuple(
        trace
        for item in qualification_observations
        for trace in _qualification_traces(
            item,
            qualification_prompt_bytes,
            qualification_schema,
        )
    )
    traces = tuple(sorted((*proposal_traces, *qualification_traces), key=lambda item: item.id))
    changes = tuple(sorted(changes_by_record_id.values(), key=lambda item: item.id))
    validate_planned_proposed_changes(changes, ledger, error_label="HP-10")
    plan = _build_plan(
        context=context,
        manifest=manifest,
        provenance_activity_id=provenance_id,
        drafts=drafts,
        propositions=tuple(
            sorted(
                (item.proposition for item in qualification_observations),
                key=lambda item: item.id,
            )
        ),
        qualifications=tuple(
            sorted(
                (
                    item.qualification
                    for item in qualification_observations
                    if item.qualification is not None
                ),
                key=lambda item: item.id,
            )
        ),
        nli_observations=tuple(
            sorted(
                (
                    item.nli_observation
                    for item in qualification_observations
                    if item.nli_observation is not None
                ),
                key=lambda item: item.id,
            )
        ),
        proposition_decisions=tuple(
            sorted(
                (
                    item.proposition_decision
                    for item in qualification_observations
                    if item.proposition_decision is not None
                ),
                key=lambda item: item.id,
            )
        ),
        decisions=tuple(sorted(decisions, key=lambda item: item.id)),
        observations=tuple(observations),
        qualification_observations=tuple(qualification_observations),
        traces=traces,
        proposed_changes=changes,
        diagnostics=diagnostics,
        qualification_manifest=qualification_manifest,
    )
    payload = canonical_standing_fact_plan_bytes(plan)
    digest = hashlib.sha256(payload).hexdigest()
    archive.put_standing_fact_plan(plan, payload, digest)
    return HybridStandingFactResult(
        plan,
        digest,
        f"extraction/standing-fact-plans/{plan.id}.json",
    )


def load_standing_fact_plan(
    plan_id: str,
    ledger: HybridStandingFactLedger,
    archive: HybridStandingFactArchive,
) -> StandingFactPlan:
    payload = archive.read_standing_fact_plan(plan_id)
    plan = standing_fact_plan_from_bytes(payload)
    if plan.id != plan_id:
        raise ValueError("Standing Fact Plan identity does not match its path.")
    parent = load_hybrid_proposal_plan(plan.parent_plan_id, ledger, archive)
    if (
        hashlib.sha256(canonical_hybrid_proposal_plan_bytes(parent)).hexdigest()
        != plan.parent_plan_sha256
    ):
        raise ValueError("Standing Fact Plan parent digest is stale.")
    context = _load_context(plan.parent_plan_id, ledger, archive)
    if (
        context.mentions.id != plan.mention_preview_id
        or hashlib.sha256(canonical_hybrid_extraction_preview_bytes(context.mentions)).hexdigest()
        != plan.mention_preview_sha256
        or context.references.id != plan.reference_preview_id
        or hashlib.sha256(canonical_hybrid_reference_preview_bytes(context.references)).hexdigest()
        != plan.reference_preview_sha256
    ):
        raise ValueError("Standing Fact Plan mention or reference lineage is stale.")
    validate_planned_proposed_changes(plan.proposed_changes, ledger, error_label="HP-10")
    return plan


def canonical_standing_fact_plan_bytes(plan: StandingFactPlan) -> bytes:
    return (_canonical_json(plan.model_dump(mode="json")) + "\n").encode()


def standing_fact_plan_from_bytes(payload: bytes) -> StandingFactPlan:
    try:
        plan = StandingFactPlan.model_validate_json(payload)
    except (ValueError, json.JSONDecodeError) as error:
        raise ValueError("Standing Fact Plan is not valid JSON.") from error
    if canonical_standing_fact_plan_bytes(plan) != payload:
        raise ValueError("Standing Fact Plan does not use canonical encoding.")
    return plan


def _load_context(
    parent_plan_id: str,
    ledger: HybridStandingFactLedger,
    archive: HybridStandingFactArchive,
) -> _SourceContext:
    parent = load_hybrid_proposal_plan(parent_plan_id, ledger, archive)
    replay_ledger = cast(HybridEventSemanticsLedger, ledger)
    hp6 = load_hybrid_event_semantics_preview(parent.parent_preview_id, replay_ledger, archive)
    hp4 = load_hybrid_event_trigger_preview(hp6.parent_preview_id, archive)
    mention_payload = archive.read_hybrid_extraction_preview(hp4.mention_preview_id)
    mentions = hybrid_extraction_preview_from_bytes(mention_payload)
    if (
        canonical_hybrid_extraction_preview_bytes(mentions) != mention_payload
        or hashlib.sha256(mention_payload).hexdigest() != hp4.mention_preview_sha256
    ):
        raise ValueError("HP-10 HP-1 lineage does not match its pinned bytes.")
    reference_payload = archive.read_hybrid_reference_preview(hp4.reference_preview_id)
    references = hybrid_reference_preview_from_bytes(reference_payload)
    if (
        canonical_hybrid_reference_preview_bytes(references) != reference_payload
        or hashlib.sha256(reference_payload).hexdigest() != hp4.reference_preview_sha256
    ):
        raise ValueError("HP-10 HP-2 lineage does not match its pinned bytes.")
    bundle = ledger.get_document_representation_bundle(parent.representation_id)
    if bundle is None:
        raise ValueError("HP-10 authoritative DocumentRepresentationBundle is missing.")
    document = ledger.get_document(bundle.representation.document_id)
    if document is None:
        raise ValueError("HP-10 authoritative Document is missing.")
    source = ledger.get_source(document.source_id)
    if source is None:
        raise ValueError("HP-10 authoritative Source is missing.")
    node = next((x for x in bundle.nodes if x.id == parent.paragraph_node_id), None)
    if node is None or node.node_type != "paragraph":
        raise ValueError("HP-10 parent paragraph is missing or invalid.")
    view = next((x for x in bundle.text_views if x.id == node.text_view_id), None)
    if view is None:
        raise ValueError("HP-10 paragraph TextView is missing.")
    paragraph_text = view.text[node.start_char : node.end_char]
    segments = paragraph_source_segments(paragraph_text, PARAGRAPH_SEGMENT_V3)
    segment_ids = {
        segment.label: hybrid_source_segment_id(parent.representation_id, node.id, segment)
        for segment in segments
    }
    candidate_segment_ids = {x.source_segment_id for x in mentions.candidates}
    if not candidate_segment_ids.issubset(segment_ids.values()):
        raise ValueError("HP-10 MentionCandidate references an unknown SourceSegment.")
    event_trigger_ranges: dict[str, list[tuple[int, int, str]]] = defaultdict(list)
    for trigger in hp4.triggers:
        event_trigger_ranges[trigger.source_segment_id].append(
            (trigger.start, trigger.end, trigger.id)
        )
    return _SourceContext(
        parent,
        mentions,
        references,
        bundle,
        document,
        source,
        paragraph_text,
        segments,
        segment_ids,
        {segment_id: tuple(sorted(values)) for segment_id, values in event_trigger_ranges.items()},
    )


def _eligible_candidates(
    context: _SourceContext,
) -> dict[str, tuple[_EligibleMention, ...]]:
    selected = set(
        effective_mention_candidate_ids(
            context.mentions.boundary_decisions,
            context.mentions.boundary_adjudications,
        )
    )
    interpretation_by_id = {x.candidate_id: x for x in context.mentions.interpretations}
    reference_by_id = {x.candidate_id: x for x in context.references.reference_decisions}
    antecedent_by_id = {
        declaration.expanded_span.id: declaration.expanded_span.text
        for declaration in context.references.alias_declarations
    }
    antecedent_by_id.update(
        {span.id: span.text for span in context.references.semantic_antecedent_spans}
    )
    grouped: dict[str, list[_EligibleMention]] = {}
    for candidate in context.mentions.candidates:
        interpretation = interpretation_by_id.get(candidate.id)
        if candidate.id not in selected or interpretation is None:
            continue
        reference = reference_by_id.get(candidate.id)
        resolved_anaphor = (
            interpretation.referentiality is Referentiality.ANAPHORIC
            and reference is not None
            and reference.status is ReferenceStatus.RESOLVED
        )
        if (
            interpretation.referentiality is not Referentiality.SPECIFIC_ENTITY
            and not resolved_anaphor
        ):
            continue
        is_person = interpretation.contextual_kind is ContextualKind.PERSON
        is_organization = interpretation.contextual_kind in {
            ContextualKind.ORGANIZATION,
            ContextualKind.GOVERNMENT,
        } or (
            interpretation.contextual_kind is ContextualKind.GEOPOLITICAL_ENTITY
            and interpretation.discourse_role in {DiscourseRole.ACTOR, DiscourseRole.PARTICIPANT}
        )
        if not (is_person or is_organization):
            continue
        if reference is not None and reference.status is not ReferenceStatus.RESOLVED:
            continue
        name = candidate.text
        identity = candidate.id
        if reference is not None:
            antecedents = [antecedent_by_id[x] for x in reference.antecedent_span_ids]
            if len(antecedents) != 1:
                continue
            name = antecedents[0]
            identity = reference.antecedent_span_ids[0]
        values = grouped.setdefault(candidate.source_segment_id, [])
        values.append(
            _EligibleMention(
                label="",
                candidate=candidate,
                interpretation=interpretation,
                display_name=name,
                identity_key=identity,
                record_type="Actor" if is_person else "Organization",
            )
        )
    return {
        segment_id: tuple(
            item.__class__(
                f"c{index}",
                item.candidate,
                item.interpretation,
                item.display_name,
                item.identity_key,
                item.record_type,
            )
            for index, item in enumerate(
                sorted(values, key=lambda x: (x.candidate.start, x.candidate.end, x.candidate.id)),
                start=1,
            )
        )
        for segment_id, values in grouped.items()
    }


def _build_manifest(
    context: _SourceContext,
    profile: ContextModelProfile,
    prompt_bytes: bytes,
    schema: PinnedTaskSchema,
    ledger: HybridStandingFactLedger,
    tokenizer: ContextTokenizer,
    *,
    prompt_id: str,
    task_type: str,
) -> ContextManifest:
    unit = create_analysis_unit_from_retrieval_selection(
        RetrievalSelectionAnalysisUnitInput(
            representation_id=context.bundle.representation.id,
            focus_node_ids=(context.parent_plan.paragraph_node_id,),
            policy_id=HYBRID_STANDING_FACT_POLICY_ID,
            task_type=task_type,
        ),
        ledger,
    )
    planning = build_context_manifest(
        ContextManifestInput(
            analysis_unit=unit,
            model_profile=profile,
            prompt_id=prompt_id,
            prompt_bytes=prompt_bytes,
            schema_id=schema.schema_id,
            schema_bytes=schema.canonical_schema_bytes,
            renderer_version="hybrid_standing_fact_context_v3",
            evidence_selection_policy_id=HYBRID_MENTION_EVIDENCE_SELECTION_V1,
            source_segment_policy_id=PARAGRAPH_SEGMENT_V3,
        ),
        ledger,
        tokenizer,
    )
    if planning.manifest.status is not ContextManifestStatus.READY:
        raise ValueError(
            "HP-10 ContextManifest is not ready: "
            f"{planning.manifest.blocked_reason or planning.manifest.status.value}"
        )
    verify_context_manifest(
        planning.manifest.id,
        ledger,
        tokenizer,
        prompt_bytes,
        schema.canonical_schema_bytes,
    )
    return planning.manifest


def _execution_spec(
    manifest: ContextManifest,
    runtime: ModelTaskRuntime,
    generation: tuple[ExecutionSetting, ...],
    schema: PinnedTaskSchema,
    task_input: bytes,
) -> ModelExecutionSpec:
    rendered = manifest.rendered_input + b"\n\n[task]\n" + task_input
    return ModelExecutionSpec(
        model_profile_id=manifest.model_profile_id,
        model_identity=runtime.configured_identity,
        generation_parameters=generation,
        prompt_id=manifest.prompt_id,
        prompt_digest=manifest.prompt_digest,
        schema_id=schema.schema_id,
        schema_digest=schema.digest,
        context_manifest_id=manifest.id,
        context_manifest_digest=manifest.manifest_digest,
        rendered_input_digest=hashlib.sha256(rendered).hexdigest(),
        output_contract_version=schema.output_contract_version,
    )


def _task_input(
    segment: SourceSegment,
    candidates: tuple[_EligibleMention, ...],
    occurrences: tuple[SourceOccurrence, ...],
) -> bytes:
    lines = [
        "task: propose_standing_facts",
        f"target_source_segment: {segment.label}",
        f"source_segment_text_json: {json.dumps(segment.exact_text, ensure_ascii=False)}",
        "candidate_catalog:",
        "label | occurrence | exact_source_text | resolved_name | kind | role",
    ]
    lines.extend(
        " | ".join(
            (
                item.label,
                standing_fact_candidate_occurrence_selector(
                    item.candidate,
                    segment.exact_text,
                    occurrences,
                ),
                json.dumps(item.candidate.text, ensure_ascii=False),
                json.dumps(item.display_name, ensure_ascii=False),
                item.interpretation.contextual_kind.value,
                item.interpretation.discourse_role.value,
            )
        )
        for item in candidates
    )
    lines.append("word_catalog:")
    lines.extend(f"{item.occurrence_id} | {item.text}" for item in occurrences)
    return ("\n".join(lines) + "\n").encode()


def standing_fact_candidate_occurrence_selector(
    candidate: MentionCandidate,
    source_text: str,
    occurrences: tuple[SourceOccurrence, ...],
) -> str:
    """Locate one exact MentionCandidate in the model-visible occurrence catalog."""
    source_copy = derive_source_copy_view(source_text)
    if occurrences != source_occurrences(source_copy):
        raise ValueError("source_occurrence_catalog_drift")
    overlapping = tuple(
        item
        for item in occurrences
        if _ranges_overlap(
            (candidate.start, candidate.end),
            source_copy.authoritative_range(item.start, item.end),
        )
    )
    if not overlapping:
        raise ValueError("standing_fact_candidate_has_no_source_occurrence")
    first = overlapping[0].occurrence_id
    last = overlapping[-1].occurrence_id
    return first if first == last else f"{first}-{last}"


def _ranges_overlap(left: tuple[int, int], right: tuple[int, int]) -> bool:
    return left[0] < right[1] and right[0] < left[1]


def _draft(observation: _TaskObservation, proposal: StandingFactProposal) -> StandingFactDraft:
    return build_standing_fact_draft(
        source_segment_id=observation.segment_id,
        source_text=observation.segment.exact_text,
        occurrences=observation.source_occurrences,
        candidates_by_label={item.label: item.candidate for item in observation.candidates},
        proposal=proposal,
        extraction_task_id=observation.extraction_task_id,
        model_run_id=observation.model_run_id,
    )


def build_standing_fact_draft(
    *,
    source_segment_id: str,
    source_text: str,
    occurrences: tuple[SourceOccurrence, ...],
    candidates_by_label: Mapping[str, MentionCandidate],
    proposal: StandingFactProposal,
    extraction_task_id: str,
    model_run_id: str,
) -> StandingFactDraft:
    """Map one fallible local-label proposal to exact authoritative source spans."""
    subject = candidates_by_label.get(proposal.subject_label)
    object_candidate = (
        candidates_by_label.get(proposal.object_selector)
        if proposal.object_kind is StandingFactObjectKind.ENTITY
        else None
    )
    relation = resolve_standing_fact_relation(
        source_text,
        occurrences,
        proposal.relation_selector,
    )
    object_span = None
    if proposal.object_kind is StandingFactObjectKind.LITERAL:
        selected_object_span = _resolve_standing_fact_source_span(
            source_text,
            occurrences,
            proposal.object_selector,
        )
        object_span, object_mapping = _complete_post_relation_literal_object_span(
            source_text,
            relation,
            selected_object_span,
        )
    else:
        object_mapping = StandingFactObjectMapping.EXACT_SELECTOR
    object_text = (
        object_span.text
        if object_span is not None
        else object_candidate.text
        if object_candidate is not None
        else proposal.object_selector
    )
    identity_parts = (
        source_segment_id,
        proposal.subject_label,
        subject.id if subject else "",
        subject.text if subject else "",
        str(subject.start) if subject else "",
        str(subject.end) if subject else "",
        relation.text,
        str(relation.start),
        str(relation.end),
        proposal.object_kind.value,
        proposal.object_selector,
        object_mapping.value,
        object_text,
        (
            str(object_span.start)
            if object_span is not None
            else str(object_candidate.start)
            if object_candidate is not None
            else ""
        ),
        (
            str(object_span.end)
            if object_span is not None
            else str(object_candidate.end)
            if object_candidate is not None
            else ""
        ),
        object_candidate.id if object_candidate else "",
        extraction_task_id,
        model_run_id,
    )
    return StandingFactDraft(
        id=_id("sfd", *identity_parts),
        source_segment_id=source_segment_id,
        subject_label=proposal.subject_label,
        subject_candidate_id=subject.id if subject else None,
        subject_text=subject.text if subject else None,
        subject_start=subject.start if subject else None,
        subject_end=subject.end if subject else None,
        relation_label=relation.text,
        relation_start=relation.start,
        relation_end=relation.end,
        object_kind=proposal.object_kind,
        object_selector=proposal.object_selector,
        object_mapping=object_mapping,
        object_text=object_text,
        object_start=(
            object_span.start
            if object_span is not None
            else object_candidate.start
            if object_candidate is not None
            else None
        ),
        object_end=(
            object_span.end
            if object_span is not None
            else object_candidate.end
            if object_candidate is not None
            else None
        ),
        object_candidate_id=object_candidate.id if object_candidate else None,
        extraction_task_id=extraction_task_id,
        model_run_id=model_run_id,
    )


def resolve_standing_fact_relation(
    source_text: str,
    occurrences: tuple[SourceOccurrence, ...],
    relation_selector: str,
) -> StandingFactRelationSpan:
    """Map one supplied occurrence selector back to exact authoritative characters."""
    return _resolve_standing_fact_source_span(source_text, occurrences, relation_selector)


def _resolve_standing_fact_source_span(
    source_text: str,
    occurrences: tuple[SourceOccurrence, ...],
    selector: str,
) -> StandingFactRelationSpan:
    source_copy = derive_source_copy_view(source_text)
    if occurrences != source_occurrences(source_copy):
        raise ValueError("source_occurrence_catalog_drift")
    occurrence_by_id = {item.occurrence_id: item for item in occurrences}
    if len(occurrence_by_id) != len(occurrences):
        raise ValueError("duplicate_source_occurrence")
    start_id, separator, end_id = selector.partition("-")
    end_id = end_id if separator else start_id
    start_occurrence = occurrence_by_id.get(start_id)
    end_occurrence = occurrence_by_id.get(end_id)
    if start_occurrence is None or end_occurrence is None:
        raise ValueError("unknown_source_occurrence")
    occurrence_order = {item.occurrence_id: ordinal for ordinal, item in enumerate(occurrences)}
    if occurrence_order[start_id] > occurrence_order[end_id]:
        raise ValueError("reversed_source_occurrence_range")
    start, end = source_copy.authoritative_range(
        start_occurrence.start,
        end_occurrence.end,
    )
    return StandingFactRelationSpan(start=start, end=end, text=source_text[start:end])


def _complete_post_relation_literal_object_span(
    source_text: str,
    relation: StandingFactRelationSpan,
    selected_object: StandingFactRelationSpan,
) -> tuple[StandingFactRelationSpan, StandingFactObjectMapping]:
    """Complete a post-relation literal through its model-selected right boundary."""
    if selected_object.start <= relation.end:
        return selected_object, StandingFactObjectMapping.EXACT_SELECTOR
    start = relation.end
    while start < selected_object.start and source_text[start].isspace():
        start += 1
    omitted_prefix = source_text[start : selected_object.start]
    if not omitted_prefix or any(mark in omitted_prefix for mark in (";", ".", "!", "?")):
        return selected_object, StandingFactObjectMapping.EXACT_SELECTOR
    return (
        StandingFactRelationSpan(
            start=start,
            end=selected_object.end,
            text=source_text[start : selected_object.end],
        ),
        StandingFactObjectMapping.COMPLETED_POST_RELATION,
    )


def build_standing_fact_proposition(
    draft: StandingFactDraft,
    source_text: str,
    evidence_target_id: str,
) -> CompleteProposition:
    """Render one complete proposition from ordered authoritative source components."""
    reasons = standing_fact_source_hold_reasons(draft, source_text)
    if reasons:
        raise ValueError(
            "Standing Fact proposition is not source-renderable: "
            + ",".join(reason.value for reason in reasons)
        )
    assert draft.subject_start is not None
    assert draft.object_end is not None
    text = source_text[draft.subject_start : draft.object_end].strip()
    if text[-1] not in ".?!":
        text += "."
    return build_complete_proposition(
        kind=PropositionKind.STANDING_ASSERTION,
        subject_record_id=draft.id,
        text=text,
        evidence_target_id=evidence_target_id,
    )


def _qualification_task_input(source_text: str, proposition: CompleteProposition) -> bytes:
    return (
        "task: qualify_standing_fact\n"
        f"source_segment_text_json: {json.dumps(source_text, ensure_ascii=False)}\n"
        f"complete_proposition_json: {json.dumps(proposition.text, ensure_ascii=False)}\n"
    ).encode()


def _qualification_record(
    draft: StandingFactDraft,
    proposition: CompleteProposition,
    output: StandingFactQualificationOutput,
    extraction_task_id: str,
    model_run_id: str,
) -> StandingFactQualification:
    identifier = _id(
        "sfq",
        draft.id,
        proposition.id,
        output.outcome.value,
        output.reason,
        extraction_task_id,
        model_run_id,
    )
    return StandingFactQualification(
        id=identifier,
        draft_id=draft.id,
        proposition_id=proposition.id,
        outcome=output.outcome,
        reason=output.reason,
        extraction_task_id=extraction_task_id,
        model_run_id=model_run_id,
    )


def _qualification_judgment_id(qualification: StandingFactQualification) -> str:
    return _id("spj", "standing_fact_qualification", qualification.id)


def _semantic_hold_reasons(
    observation: _QualificationObservation | None,
) -> tuple[StandingFactHoldReason, ...]:
    if observation is None or observation.qualification is None:
        return (StandingFactHoldReason.QUALIFICATION_MISSING,)
    outcome = observation.qualification.outcome
    reasons: set[StandingFactHoldReason] = set()
    if outcome is StandingFactQualificationOutcome.EVENT_NOT_STANDING:
        reasons.add(StandingFactHoldReason.EVENT_ROUTE_REQUIRED)
    elif outcome is StandingFactQualificationOutcome.INCOMPLETE_OR_WRONG_ARGUMENTS:
        reasons.add(StandingFactHoldReason.INCOMPLETE_OR_WRONG_ARGUMENTS)
    elif outcome is StandingFactQualificationOutcome.UNSUPPORTED:
        reasons.add(StandingFactHoldReason.SEMANTICALLY_UNSUPPORTED)
    elif outcome is StandingFactQualificationOutcome.AMBIGUOUS:
        reasons.add(StandingFactHoldReason.QUALIFICATION_AMBIGUOUS)
    if outcome is StandingFactQualificationOutcome.SUPPORTED_STANDING_FACT and (
        observation.proposition_decision is None
        or observation.proposition_decision.disposition is not PropositionDisposition.SUPPORTED
    ):
        reasons.add(StandingFactHoldReason.COMPLETE_PROPOSITION_HELD)
    return tuple(sorted(reasons, key=lambda item: item.value))


def _hold_reasons(
    draft: StandingFactDraft,
    context: _SourceContext,
    candidates_by_segment: dict[str, tuple[_EligibleMention, ...]],
) -> tuple[StandingFactHoldReason, ...]:
    segment = _segment_by_id(context, draft.source_segment_id)
    return standing_fact_source_hold_reasons(
        draft,
        segment.exact_text,
        event_trigger_ranges=context.event_trigger_ranges.get(draft.source_segment_id, ()),
        mention_ranges=tuple(
            (item.candidate.start, item.candidate.end, item.candidate.id)
            for item in candidates_by_segment.get(draft.source_segment_id, ())
        ),
    )


def standing_fact_source_hold_reasons(
    draft: StandingFactDraft,
    source_text: str,
    *,
    event_trigger_ranges: tuple[tuple[int, int, str], ...] = (),
    mention_ranges: tuple[tuple[int, int, str], ...] = (),
) -> tuple[StandingFactHoldReason, ...]:
    """Apply only source and identity checks before independent semantic qualification."""
    reasons: set[StandingFactHoldReason] = set()
    if draft.subject_candidate_id is None:
        reasons.add(StandingFactHoldReason.UNKNOWN_SUBJECT)
    elif not _source_span_matches(
        source_text,
        draft.subject_start,
        draft.subject_end,
        draft.subject_text,
    ):
        reasons.add(StandingFactHoldReason.SOURCE_SPAN_MISMATCH)
    if not _source_span_matches(
        source_text,
        draft.relation_start,
        draft.relation_end,
        draft.relation_label,
    ):
        reasons.add(StandingFactHoldReason.SOURCE_SPAN_MISMATCH)
    if draft.object_kind is StandingFactObjectKind.ENTITY:
        if draft.object_candidate_id is None:
            reasons.add(StandingFactHoldReason.UNKNOWN_ENTITY_OBJECT)
        elif draft.object_candidate_id == draft.subject_candidate_id:
            reasons.add(StandingFactHoldReason.SELF_RELATION)
        elif not _source_span_matches(
            source_text,
            draft.object_start,
            draft.object_end,
            draft.object_text,
        ):
            reasons.add(StandingFactHoldReason.SOURCE_SPAN_MISMATCH)
    else:
        if draft.object_text not in source_text:
            reasons.add(StandingFactHoldReason.LITERAL_NOT_IN_SOURCE)
        elif not _source_span_matches(
            source_text,
            draft.object_start,
            draft.object_end,
            draft.object_text,
        ):
            reasons.add(StandingFactHoldReason.SOURCE_SPAN_MISMATCH)
    if (
        draft.subject_end is not None
        and draft.object_start is not None
        and not (
            draft.subject_end <= draft.relation_start and draft.relation_end <= draft.object_start
        )
    ):
        reasons.add(StandingFactHoldReason.PROPOSITION_NOT_SOURCE_ORDERED)
    if any(
        draft.relation_start < mention_end and mention_start < draft.relation_end
        for mention_start, mention_end, _ in mention_ranges
    ):
        reasons.add(StandingFactHoldReason.RELATION_OVERLAPS_MENTION)
    if any(
        draft.relation_start < trigger_end and trigger_start < draft.relation_end
        for trigger_start, trigger_end, _ in event_trigger_ranges
    ):
        reasons.add(StandingFactHoldReason.EVENT_ROUTE_REQUIRED)
    return tuple(sorted(reasons, key=lambda item: item.value))


def _source_span_matches(
    source_text: str,
    start: int | None,
    end: int | None,
    expected_text: str | None,
) -> bool:
    return (
        start is not None
        and end is not None
        and expected_text is not None
        and 0 <= start < end <= len(source_text)
        and source_text[start:end] == expected_text
    )


def _rewrapped_parent_changes(
    parent: HybridProposalPlan,
    provenance_id: str,
) -> dict[str, PlannedProposedChange]:
    changes: dict[str, PlannedProposedChange] = {}
    for old in parent.proposed_changes:
        proposed_json = cast(dict[str, JsonValue], json.loads(_canonical_json(old.proposed_json)))
        record = proposed_json.get("record")
        if not isinstance(record, dict) or not isinstance(record.get("id"), str):
            raise ValueError("HP-10 parent proposal lacks a typed record identity.")
        record_id = cast(str, record["id"])
        change = _planned_change(
            provenance_id,
            old.source_id,
            old.document_id,
            proposed_json,
        )
        prior = changes.get(record_id)
        if prior is not None and prior.proposed_json != change.proposed_json:
            raise ValueError("HP-10 parent repeats one record with conflicting bodies.")
        changes[record_id] = change
    return changes


def _standing_fact_changes(
    *,
    draft: StandingFactDraft,
    candidates_by_id: dict[str, _EligibleMention],
    evidence: tuple[EvidenceTarget, EvidenceValidationAttempt],
    context: _SourceContext,
    provenance_activity_id: str,
    existing_record_ids: set[str],
) -> dict[str, PlannedProposedChange]:
    assert draft.subject_candidate_id is not None
    subject = candidates_by_id[draft.subject_candidate_id]
    subject_id = _entity_id(context.bundle.representation.id, subject)
    object_id: str | None = None
    object_candidate: _EligibleMention | None = None
    if draft.object_candidate_id is not None:
        object_candidate = candidates_by_id[draft.object_candidate_id]
        object_id = _entity_id(context.bundle.representation.id, object_candidate)
    target, attempt = evidence
    assertion = ProposedAssertion(
        id=_id(
            "ast",
            context.bundle.representation.id,
            subject_id,
            draft.relation_label,
            object_id or draft.object_text,
            target.id,
        ),
        assertion_type=AssertionType.SOURCE_CLAIM,
        epistemic_scope=EpistemicScope.SOURCE_REPORT,
        subject_entity_id=subject_id,
        relation_label=draft.relation_label,
        object_entity_id=object_id,
        object_value=(
            None if draft.object_kind is StandingFactObjectKind.ENTITY else draft.object_text
        ),
        source_authority=SourceAuthority.UNKNOWN,
        attribution_basis=AttributionBasis.REPORTED_BY_SOURCE,
        source_ids=(context.source.id,),
        evidence_target_ids=(target.id,),
    )
    additions: dict[str, PlannedProposedChange] = {}
    for candidate in (subject, *((object_candidate,) if object_candidate is not None else ())):
        record_id = _entity_id(context.bundle.representation.id, candidate)
        if record_id in existing_record_ids or record_id in additions:
            continue
        additions[record_id] = _entity_change(
            candidate,
            context,
            provenance_activity_id,
            draft,
        )
    assertion_json = cast(
        dict[str, JsonValue], assertion.model_dump(mode="json", exclude_none=True)
    )
    lineage = _lineage_json(draft, context)
    additions[assertion.id] = _planned_change(
        provenance_activity_id,
        context.source.id,
        context.document.id,
        {
            "record_type": "Assertion",
            "stable_label": assertion.id,
            "record": assertion_json,
            "evidence_links": [
                {
                    "evidence_target_id": target.id,
                    "validation_attempt_id": attempt.id,
                    "role": "direct_support",
                    "polarity": EvidencePolarity.SUPPORTS.value,
                    "necessity": EvidenceNecessity.REQUIRED.value,
                }
            ],
            "hybrid_lineage": lineage,
        },
    )
    return additions


def _entity_change(
    candidate: _EligibleMention,
    context: _SourceContext,
    provenance_id: str,
    draft: StandingFactDraft,
) -> PlannedProposedChange:
    record_id = _entity_id(context.bundle.representation.id, candidate)
    if candidate.record_type == "Actor":
        record = Actor(id=record_id, name=candidate.display_name)
    else:
        record = Organization(
            id=record_id,
            name=candidate.display_name,
            organization_type=candidate.interpretation.contextual_kind.value,
        )
    return _planned_change(
        provenance_id,
        context.source.id,
        context.document.id,
        {
            "record_type": candidate.record_type,
            "stable_label": record_id,
            "record": cast(
                dict[str, JsonValue],
                record.model_dump(mode="json", exclude={"created_at", "updated_at"}),
            ),
            "evidence": _candidate_evidence_json(candidate, context),
            "hybrid_lineage": {
                **_lineage_json(draft, context),
                "mention_candidate_id": candidate.candidate.id,
                "mention_interpretation_ids": [candidate.interpretation.id],
            },
        },
    )


def _prepare_segment_evidence(
    context: _SourceContext,
    segment_id: str,
    recorded_at: datetime,
    ledger: HybridStandingFactLedger,
) -> tuple[EvidenceTarget, EvidenceValidationAttempt]:
    segment = _segment_by_id(context, segment_id)
    node = next(x for x in context.bundle.nodes if x.id == context.parent_plan.paragraph_node_id)
    view = next(x for x in context.bundle.text_views if x.id == node.text_view_id)
    start = node.start_char + segment.start_char
    end = node.start_char + segment.end_char
    target = EvidenceTarget(
        id=_id(
            "etg",
            context.bundle.representation.id,
            view.id,
            segment_id,
            str(start),
            str(end),
            segment.exact_text,
        ),
        source_id=context.source.id,
        document_id=context.document.id,
        representation_id=context.bundle.representation.id,
        text_view_id=view.id,
        text_view_digest=view.content_digest,
        start_char=start,
        end_char=end,
        exact_text=segment.exact_text,
        normalization_policy=view.normalization_policy,
        prefix_text=view.text[max(0, start - 32) : start],
        suffix_text=view.text[end : min(len(view.text), end + 32)],
        node_ids=(node.id,),
        pdf_region_ids=node.source_region_ids,
        created_at=recorded_at,
    )
    existing = ledger.get_evidence_target(target.id)
    if existing is not None:
        if _without_time(existing) != _without_time(target):
            raise ValueError("HP-10 conflicts with an existing EvidenceTarget.")
        target = existing
    validate_evidence_target_record(target, ledger)
    attempt = EvidenceValidationAttempt(
        id=_id("eva", target.id, HYBRID_STANDING_FACT_EVIDENCE_VALIDATOR),
        evidence_target_id=target.id,
        target_digest=canonical_evidence_target_digest(target),
        validator_version=HYBRID_STANDING_FACT_EVIDENCE_VALIDATOR,
        status=EvidenceValidationAttemptStatus.SUCCEEDED,
        attempted_at=recorded_at,
    )
    existing_attempt = ledger.get_evidence_validation_attempt(attempt.id)
    if existing_attempt is not None:
        if _without_time(existing_attempt) != _without_time(attempt):
            raise ValueError("HP-10 conflicts with an EvidenceValidationAttempt.")
        attempt = existing_attempt
    if existing is None:
        ledger.save_evidence_target(target)
    if existing_attempt is None:
        ledger.save_evidence_validation_attempt(attempt)
    replay = verify_evidence_target(target, attempt, ledger)
    if not replay.valid:
        raise ValueError(f"HP-10 EvidenceTarget replay failed: {replay.error_message}")
    return target, attempt


def _trace(
    observation: _TaskObservation,
    drafts: tuple[StandingFactDraft, ...],
    decisions: tuple[StandingFactDecision, ...],
    mapping_rejections: tuple[_MappingRejection, ...],
    prompt_bytes: bytes,
    schema: PinnedTaskSchema,
) -> ExtractionStageTrace:
    selected_drafts = tuple(x for x in drafts if x.model_run_id == observation.model_run_id)
    selected_ids = {x.id for x in selected_drafts}
    selected_decisions = tuple(x for x in decisions if x.draft_id in selected_ids)
    batch = observation.batch
    status = (
        ExtractionStageStatus.COMPLETED
        if observation.model_status in {ModelRunStatus.SUCCEEDED, ModelRunStatus.ABSTAINED}
        else ExtractionStageStatus.FAILED
    )
    return build_extraction_stage_trace(
        trace_run_id=f"standing_fact:{observation.segment_id}",
        ordinal=0,
        stage_id="hybrid_standing_fact_proposal",
        stage_version=HYBRID_STANDING_FACT_POLICY_ID,
        producer_id="qwen2.5",
        source_segment_id=observation.segment_id,
        source_text_sha256=hashlib.sha256(observation.segment.exact_text.encode()).hexdigest(),
        input_record_ids=tuple(sorted(x.candidate.id for x in observation.candidates)),
        execution_record_ids=(observation.extraction_task_id, observation.model_run_id),
        configuration={
            "prompt_sha256": hashlib.sha256(prompt_bytes).hexdigest(),
            "schema_sha256": schema.digest,
        },
        input_payload={
            "rendered_task": _task_input(
                observation.segment,
                observation.candidates,
                observation.source_occurrences,
            ).decode(),
            "source_segment_text": observation.segment.exact_text,
            "candidate_catalog": [
                {
                    "label": x.label,
                    "candidate_id": x.candidate.id,
                    "occurrence_selector": standing_fact_candidate_occurrence_selector(
                        x.candidate,
                        observation.segment.exact_text,
                        observation.source_occurrences,
                    ),
                    "exact_text": x.candidate.text,
                    "display_name": x.display_name,
                    "contextual_kind": x.interpretation.contextual_kind.value,
                    "discourse_role": x.interpretation.discourse_role.value,
                }
                for x in observation.candidates
            ],
        },
        output_payload={
            "model_run_id": observation.model_run_id,
            "model_run_status": observation.model_status.value,
            "raw_output_sha256": observation.raw_output_sha256,
            "abstention_reason": observation.abstention_reason,
            "parsed_proposals": [
                {
                    "subject_label": x.subject_label,
                    "relation_selector": x.relation_selector,
                    "object_kind": x.object_kind.value,
                    "object_selector": x.object_selector,
                }
                for x in (batch.proposals if batch else ())
            ],
            "line_rejections": [
                {
                    "line_number": x.line_number,
                    "raw_line": x.raw_line,
                    "reason": x.reason,
                }
                for x in (batch.rejections if batch else ())
            ],
            "mapping_rejections": [
                {
                    "proposal": {
                        "subject_label": item.proposal.subject_label,
                        "relation_selector": item.proposal.relation_selector,
                        "object_kind": item.proposal.object_kind.value,
                        "object_selector": item.proposal.object_selector,
                    },
                    "reason": item.reason,
                }
                for item in mapping_rejections
            ],
            "mapped_drafts": [x.model_dump(mode="json") for x in selected_drafts],
            "decisions": [x.model_dump(mode="json") for x in selected_decisions],
        },
        status=status,
        diagnostics=(
            ()
            if status is ExtractionStageStatus.COMPLETED
            else (f"model_run_{observation.model_status.value}",)
        ),
    )


def _qualification_traces(
    observation: _QualificationObservation,
    prompt_bytes: bytes,
    schema: PinnedTaskSchema,
) -> tuple[ExtractionStageTrace, ExtractionStageTrace]:
    qualification = observation.qualification
    qwen_status = (
        ExtractionStageStatus.COMPLETED
        if qualification is not None and observation.model_status is ModelRunStatus.SUCCEEDED
        else ExtractionStageStatus.FAILED
    )
    qwen = build_extraction_stage_trace(
        trace_run_id=f"standing_fact_qualification:{observation.draft.id}",
        ordinal=0,
        stage_id="hybrid_standing_fact_qualification",
        stage_version="1",
        producer_id="qwen2.5",
        source_segment_id=observation.draft.source_segment_id,
        source_text_sha256=hashlib.sha256(observation.source_text.encode()).hexdigest(),
        input_record_ids=tuple(sorted((observation.draft.id, observation.proposition.id))),
        execution_record_ids=(observation.extraction_task_id, observation.model_run_id),
        configuration={
            "prompt_sha256": hashlib.sha256(prompt_bytes).hexdigest(),
            "schema_sha256": schema.digest,
        },
        input_payload={
            "source_text": observation.source_text,
            "complete_proposition": observation.proposition.model_dump(mode="json"),
            "rendered_task": _qualification_task_input(
                observation.source_text, observation.proposition
            ).decode(),
        },
        output_payload={
            "model_run_status": observation.model_status.value,
            "raw_output_sha256": observation.raw_output_sha256,
            "qualification": qualification.model_dump(mode="json") if qualification else None,
        },
        status=qwen_status,
        diagnostics=(
            () if qwen_status is ExtractionStageStatus.COMPLETED else ("missing_qualification",)
        ),
    )
    nli = observation.nli_observation
    proposition_decision = observation.proposition_decision
    nli_status = (
        ExtractionStageStatus.COMPLETED
        if nli is not None and proposition_decision is not None
        else ExtractionStageStatus.FAILED
    )
    challenger = build_extraction_stage_trace(
        trace_run_id=f"standing_fact_qualification:{observation.draft.id}",
        ordinal=1,
        stage_id="standing_fact_nli_challenge",
        stage_version="1",
        producer_id=nli.model_id if nli is not None else "deberta-nli",
        source_segment_id=observation.draft.source_segment_id,
        source_text_sha256=hashlib.sha256(observation.source_text.encode()).hexdigest(),
        parent_trace_ids=(qwen.id,),
        input_record_ids=(observation.proposition.id,),
        configuration={
            "entailment_threshold": HYBRID_STANDING_FACT_NLI_ENTAILMENT_THRESHOLD,
        },
        input_payload={
            "premise": observation.source_text,
            "hypothesis": observation.proposition.text,
        },
        output_payload={
            "nli_observation": nli.model_dump(mode="json") if nli else None,
            "nli_error": observation.nli_error,
            "proposition_decision": (
                proposition_decision.model_dump(mode="json")
                if proposition_decision is not None
                else None
            ),
        },
        status=nli_status,
        diagnostics=() if nli_status is ExtractionStageStatus.COMPLETED else ("nli_unavailable",),
    )
    return qwen, challenger


def _build_plan(
    *,
    context: _SourceContext,
    manifest: ContextManifest | None,
    provenance_activity_id: str,
    drafts: tuple[StandingFactDraft, ...],
    propositions: tuple[CompleteProposition, ...],
    qualifications: tuple[StandingFactQualification, ...],
    nli_observations: tuple[NliObservation, ...],
    proposition_decisions: tuple[PropositionDecision, ...],
    decisions: tuple[StandingFactDecision, ...],
    observations: tuple[_TaskObservation, ...],
    qualification_observations: tuple[_QualificationObservation, ...],
    traces: tuple[ExtractionStageTrace, ...],
    proposed_changes: tuple[PlannedProposedChange, ...],
    diagnostics: tuple[str, ...],
    qualification_manifest: ContextManifest | None,
) -> StandingFactPlan:
    extraction_task_ids = tuple(
        sorted(
            (
                *(x.extraction_task_id for x in observations),
                *(x.extraction_task_id for x in qualification_observations),
            )
        )
    )
    model_run_ids = tuple(
        sorted(
            (
                *(x.model_run_id for x in observations),
                *(x.model_run_id for x in qualification_observations),
            )
        )
    )
    payload = cast(
        dict[str, JsonValue],
        {
            "schema_version": "standing_fact_plan_v6",
            "parent_plan_id": context.parent_plan.id,
            "parent_plan_sha256": hashlib.sha256(
                canonical_hybrid_proposal_plan_bytes(context.parent_plan)
            ).hexdigest(),
            "mention_preview_id": context.mentions.id,
            "mention_preview_sha256": hashlib.sha256(
                canonical_hybrid_extraction_preview_bytes(context.mentions)
            ).hexdigest(),
            "reference_preview_id": context.references.id,
            "reference_preview_sha256": hashlib.sha256(
                canonical_hybrid_reference_preview_bytes(context.references)
            ).hexdigest(),
            "representation_id": context.bundle.representation.id,
            "paragraph_node_id": context.parent_plan.paragraph_node_id,
            "context_manifest_id": manifest.id if manifest else None,
            "qualification_context_manifest_id": (
                qualification_manifest.id if qualification_manifest else None
            ),
            "policy_id": HYBRID_STANDING_FACT_POLICY_ID,
            "provenance_activity_id": provenance_activity_id,
            "drafts": [cast(JsonValue, x.model_dump(mode="json")) for x in drafts],
            "propositions": [cast(JsonValue, x.model_dump(mode="json")) for x in propositions],
            "qualifications": [cast(JsonValue, x.model_dump(mode="json")) for x in qualifications],
            "nli_observations": [
                cast(JsonValue, x.model_dump(mode="json")) for x in nli_observations
            ],
            "proposition_decisions": [
                cast(JsonValue, x.model_dump(mode="json")) for x in proposition_decisions
            ],
            "decisions": [cast(JsonValue, x.model_dump(mode="json")) for x in decisions],
            "extraction_task_ids": list(extraction_task_ids),
            "model_run_ids": list(model_run_ids),
            "traces": [cast(JsonValue, x.model_dump(mode="json")) for x in traces],
            "proposed_changes": [
                cast(JsonValue, x.model_dump(mode="json")) for x in proposed_changes
            ],
            "terminal_status": (
                StandingFactPlanStatus.PARTIAL.value
                if diagnostics
                else StandingFactPlanStatus.COMPLETE.value
            ),
            "diagnostics": list(diagnostics),
        },
    )
    return StandingFactPlan.model_validate_json(
        _canonical_json({**payload, "id": _content_id("sfp", payload)})
    )


def _diagnostics(
    observations: list[_TaskObservation],
    decisions: list[StandingFactDecision],
) -> tuple[str, ...]:
    values = {
        f"standing_fact_task_failed:{x.segment_id}:{x.model_status.value}"
        for x in observations
        if x.model_status not in {ModelRunStatus.SUCCEEDED, ModelRunStatus.ABSTAINED}
    }
    values.update(
        f"standing_fact_line_rejected:{x.segment_id}:{rejection.line_number}:{rejection.reason}"
        for x in observations
        if x.batch is not None
        for rejection in x.batch.rejections
    )
    values.update(
        f"standing_fact_held:{x.draft_id}:{reason.value}"
        for x in decisions
        for reason in x.reason_codes
    )
    return tuple(sorted(values))


def _candidate_evidence_json(
    candidate: _EligibleMention,
    context: _SourceContext,
) -> dict[str, JsonValue]:
    segment = _segment_by_id(context, candidate.candidate.source_segment_id)
    node = next(x for x in context.bundle.nodes if x.id == context.parent_plan.paragraph_node_id)
    view = next(x for x in context.bundle.text_views if x.id == node.text_view_id)
    start = node.start_char + segment.start_char + candidate.candidate.start
    end = node.start_char + segment.start_char + candidate.candidate.end
    if view.text[start:end] != candidate.candidate.text:
        raise ValueError("HP-10 candidate evidence does not replay exact source characters.")
    return {
        "source_id": context.source.id,
        "document_id": context.document.id,
        "selector_type": "pinned_text",
        "exact_text": candidate.candidate.text,
        "prefix_text": view.text[max(0, start - 32) : start],
        "suffix_text": view.text[end : min(len(view.text), end + 32)],
        "location": {
            "representation_id": context.bundle.representation.id,
            "text_view_id": view.id,
            "start_char": start,
            "end_char": end,
            "node_ids": [node.id],
        },
    }


def _lineage_json(
    draft: StandingFactDraft,
    context: _SourceContext,
) -> dict[str, JsonValue]:
    return {
        "hp1_preview_id": context.mentions.id,
        "hp2_preview_id": context.references.id,
        "hp7_plan_id": context.parent_plan.id,
        "hp10_standing_fact_draft_id": draft.id,
        "source_segment_id": draft.source_segment_id,
        "model_run_ids": [draft.model_run_id],
        "extraction_task_ids": [draft.extraction_task_id],
    }


def _entity_id(representation_id: str, candidate: _EligibleMention) -> str:
    return _id(
        "act" if candidate.record_type == "Actor" else "org",
        representation_id,
        candidate.identity_key,
    )


def _segment_by_id(context: _SourceContext, segment_id: str) -> SourceSegment:
    by_id = {context.segment_ids[x.label]: x for x in context.segments}
    try:
        return by_id[segment_id]
    except KeyError as error:
        raise ValueError("HP-10 references an unknown SourceSegment.") from error


def _planned_change(
    provenance_id: str,
    source_id: str,
    document_id: str,
    proposed_json: dict[str, JsonValue],
) -> PlannedProposedChange:
    return PlannedProposedChange(
        id=_id("pcg", provenance_id, _canonical_json(proposed_json)),
        proposed_json=proposed_json,
        source_id=source_id,
        document_id=document_id,
        provenance_activity_id=provenance_id,
    )


def _decision_id(
    draft_id: str,
    disposition: StandingFactDisposition,
    qualification_id: str | None,
    proposition_decision_id: str | None,
    reasons: tuple[StandingFactHoldReason, ...],
    proposal_ids: tuple[str, ...],
) -> str:
    return _id(
        "sfdc",
        draft_id,
        disposition.value,
        qualification_id or "",
        proposition_decision_id or "",
        *(x.value for x in reasons),
        *proposal_ids,
    )


def _without_time(
    record: EvidenceTarget | EvidenceValidationAttempt,
) -> dict[str, JsonValue]:
    return cast(
        dict[str, JsonValue],
        record.model_dump(mode="json", exclude={"created_at", "attempted_at"}),
    )


def _content_id(prefix: str, payload: JsonValue) -> str:
    return _id(prefix, _canonical_json(payload))


def _id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("\x1f".join(parts).encode()).hexdigest()
    return f"{prefix}_{digest[:24]}"


def _canonical_json(value: JsonValue) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _ordered_distinct(label: str, values: tuple[str, ...]) -> None:
    if values != tuple(sorted(set(values))):
        raise ValueError(f"{label} must be ordered and distinct.")
