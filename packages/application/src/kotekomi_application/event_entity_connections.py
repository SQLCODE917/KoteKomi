"""Source-grounded Event-entity connection experiment contracts."""

from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from enum import StrEnum
from typing import Annotated, Literal, Self, cast

from kotekomi_domain.models import JsonValue
from pydantic import BaseModel, ConfigDict, Field, model_validator

from kotekomi_application.context_planning import derive_source_copy_view
from kotekomi_application.event_entity_connection_model_output import (
    EntityInvolvementAnswerValue,
)
from kotekomi_application.extraction_stage_trace import (
    ExtractionStageStatus,
    ExtractionStageTrace,
    validate_extraction_stage_trace_chain,
)
from kotekomi_application.hybrid_document_references import (
    HybridReferencePreview,
    ReferenceDecision,
    ReferenceSpan,
    ReferenceStatus,
)
from kotekomi_application.hybrid_entity_grounding import (
    EntityLinkEvidence,
    HybridEntityGroundingPreview,
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
    MentionObservation,
    Referentiality,
)

EVENT_ENTITY_CONNECTION_POLICY_ID = "event_entity_connection_contrastive_v6"
EVENT_ENTITY_INVOLVEMENT_SCHEMA_ID = "event_entity_involvement_vector_text_v1"
SOURCE_BOUND_ACTOR_GROUP_ROLE_HEADS = frozenset({"officials", "representatives"})
STRONG_PERSON_OBSERVATION_PRODUCER_PREFIXES = ("gliner:",)
STRONG_ORGANIZATION_OBSERVATION_PRODUCER_PREFIXES = ("gliner:",)
REFINED_PERSON_MENTION_TYPES = frozenset({"PER", "PERSON"})
REFINED_ORGANIZATION_MENTION_TYPES = frozenset({"ORG", "ORGANIZATION"})
WIKIDATA_ORGANIZATION_CLASS_ID = "Q43229"
PERSON_SPECIALIST_COMPATIBLE_KINDS = frozenset(
    {
        ContextualKind.PERSON,
        ContextualKind.GOVERNMENT,
        ContextualKind.UNCLEAR,
    }
)
ORGANIZATION_SPECIALIST_COMPATIBLE_KINDS = frozenset(
    {
        ContextualKind.ORGANIZATION,
        ContextualKind.GOVERNMENT,
        ContextualKind.GEOPOLITICAL_ENTITY,
        ContextualKind.INITIATIVE,
        ContextualKind.POLICY,
        ContextualKind.PROJECT,
        ContextualKind.PUBLICATION,
        ContextualKind.UNCLEAR,
    }
)
REFERENCE_MARKERS = frozenset(
    {
        "he",
        "her",
        "hers",
        "him",
        "his",
        "it",
        "its",
        "she",
        "their",
        "theirs",
        "them",
        "they",
        "whose",
    }
)

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


class EventEntityCandidateRouteKind(StrEnum):
    """Who has the appropriate capability to decide one candidate."""

    DETERMINISTIC_NOT_CONNECTED = "deterministic_not_connected"
    MODEL_JUDGMENT = "model_judgment"


class EventEntityCandidateRouteReason(StrEnum):
    """Finite reasons for routing one exact Event-entity occurrence pair."""

    DIFFERENT_LINGUISTIC_SENTENCE = "different_linguistic_sentence"
    SEMANTIC_JUDGMENT_REQUIRED = "semantic_judgment_required"


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


class EventEntityGapDependencyRule(StrEnum):
    """Deterministic evidence that one segment-level gap affects one Event."""

    EXPRESSION_OVERLAP = "event_expression_overlap_v1"
    ADJACENT_POSSESSIVE = "adjacent_possessive_event_v1"
    ADJACENT_REFERENCE = "adjacent_reference_event_v1"


class EventEntityGapDependency(BaseModel):
    """One explicit dependency from a source gap to one exact Event occurrence."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: Annotated[str, Field(pattern=r"^egd_[a-f0-9]{24}$")]
    gap_id: Annotated[str, Field(pattern=r"^ecg_[a-f0-9]{24}$")]
    source_grounded_event_id: Annotated[str, Field(pattern=r"^sge_[a-f0-9]{24}$")]
    event_mention_id: Annotated[str, Field(pattern=r"^evm_[A-Za-z0-9][A-Za-z0-9_-]*$")]
    event_expression_start: Annotated[int, Field(ge=0)]
    event_expression_end: Annotated[int, Field(gt=0)]
    rule_id: EventEntityGapDependencyRule

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if self.event_expression_end <= self.event_expression_start:
            raise ValueError("Event gap dependency requires a valid Event range.")
        expected = _id(
            "egd",
            self.gap_id,
            self.source_grounded_event_id,
            self.event_mention_id,
            str(self.event_expression_start),
            str(self.event_expression_end),
            self.rule_id.value,
        )
        if self.id != expected:
            raise ValueError("Event gap dependency ID does not match its evidence.")
        return self


class EventEntityDenotationRule(StrEnum):
    """KoteKomi-owned rules that establish one source expression's entity kind."""

    SPECIALIST_PERSON_EVIDENCE = "specialist_person_evidence_v1"
    SPECIALIST_ORGANIZATION_EVIDENCE = "specialist_organization_evidence_v1"
    EXTERNAL_ORGANIZATION_CLASS = "external_organization_class_v1"
    MODEL_CONTEXTUAL_KIND = "model_contextual_kind_v1"
    SOURCE_BOUND_ACTOR_GROUP = "source_bound_actor_group_v1"
    KNOWN_NAME_RECURRENCE = "known_name_recurrence_v1"
    RESOLVED_REFERENCE = "resolved_reference_v1"


class EventEntityDenotationDecision(BaseModel):
    """One auditable entity-kind decision over an exact mention occurrence."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: Annotated[str, Field(pattern=r"^edd_[a-f0-9]{24}$")]
    mention_candidate_id: Annotated[str, Field(pattern=_ID)]
    entity_kind: EventEntityKind
    entity_name: Annotated[str, Field(min_length=1)]
    rule_id: EventEntityDenotationRule
    source_evidence_ids: tuple[Annotated[str, Field(pattern=_ID)], ...]
    mention_interpretation_id: Annotated[str, Field(pattern=_ID)] | None = None
    diagnostics: tuple[Annotated[str, Field(min_length=1)], ...] = ()

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        _ordered_distinct("denotation source evidence IDs", self.source_evidence_ids)
        _ordered_distinct("denotation diagnostics", self.diagnostics)
        if not self.source_evidence_ids:
            raise ValueError("Event entity denotation requires source evidence.")
        if (
            self.rule_id is EventEntityDenotationRule.MODEL_CONTEXTUAL_KIND
            and self.mention_interpretation_id is None
        ):
            raise ValueError("A model-based denotation requires its interpretation evidence.")
        expected = _id(
            "edd",
            self.mention_candidate_id,
            self.entity_kind.value,
            self.entity_name,
            self.rule_id.value,
            self.mention_interpretation_id or "",
            *self.source_evidence_ids,
            *self.diagnostics,
        )
        if self.id != expected:
            raise ValueError("Event entity denotation ID does not match its evidence.")
        return self


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


class EventEntityLinguisticToken(BaseModel):
    """One validated token copied from the upstream linguistic-analysis trace."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    token_id: Annotated[str, Field(pattern=r"^t[1-9][0-9]*$")]
    sentence_id: Annotated[str, Field(pattern=r"^s[1-9][0-9]*$")]
    text: Annotated[str, Field(min_length=1)]
    start: Annotated[int, Field(ge=0)]
    end: Annotated[int, Field(gt=0)]
    lemma: Annotated[str, Field(min_length=1)]
    part_of_speech: Annotated[str, Field(min_length=1)]
    dependency_relation: Annotated[str, Field(min_length=1)]
    head_token_id: Annotated[str, Field(pattern=r"^t[1-9][0-9]*$")] | None = None

    @model_validator(mode="after")
    def validate_token(self) -> Self:
        if self.end - self.start != len(self.text):
            raise ValueError("Event entity linguistic-token range does not match its text.")
        return self


class EventEntityLinguisticEvidence(BaseModel):
    """Typed specialist evidence used only to route Event-entity candidates."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    trace_id: Annotated[str, Field(pattern=r"^xst_[a-f0-9]{24}$")]
    source_segment_id: Annotated[str, Field(min_length=1)]
    source_text_sha256: Annotated[str, Field(pattern=_SHA256)]
    producer_id: Annotated[str, Field(min_length=1)]
    model_id: Annotated[str, Field(min_length=1)]
    model_version: Annotated[str, Field(min_length=1)]
    resource_identity: Annotated[str, Field(pattern=_SHA256)]
    tokens: tuple[EventEntityLinguisticToken, ...]

    @model_validator(mode="after")
    def validate_evidence(self) -> Self:
        token_ids = tuple(item.token_id for item in self.tokens)
        if token_ids != tuple(f"t{ordinal}" for ordinal in range(1, len(token_ids) + 1)):
            raise ValueError("Event entity linguistic tokens must be complete and ordered.")
        token_id_set = set(token_ids)
        if any(
            item.head_token_id is not None and item.head_token_id not in token_id_set
            for item in self.tokens
        ):
            raise ValueError("Event entity linguistic token references an unavailable head.")
        if any(
            item.head_token_id is not None
            and next(
                token for token in self.tokens if token.token_id == item.head_token_id
            ).sentence_id
            != item.sentence_id
            for item in self.tokens
        ):
            raise ValueError("Event entity linguistic dependency crosses a sentence boundary.")
        return self


class EventEntityMentionInput(BaseModel):
    """One KoteKomi-resolved entity mention used to construct candidates."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    entity_identity: Annotated[str, Field(min_length=1)]
    entity_kind: EventEntityKind
    entity_name: Annotated[str, Field(min_length=1)]
    denotation_decision_id: Annotated[str, Field(pattern=r"^edd_[a-f0-9]{24}$")]
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
    denotation_decisions: tuple[EventEntityDenotationDecision, ...]
    gaps: tuple[EventEntityCandidateGap, ...]
    gap_dependencies: tuple[EventEntityGapDependency, ...]

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
        overlapping_ids = set(mention_ids) & set(gap_ids)
        if overlapping_ids:
            joined = ", ".join(sorted(overlapping_ids))
            raise ValueError("One upstream mention cannot be both selected and a gap: " + joined)
        dependency_by_gap = {item.gap_id: item for item in self.gap_dependencies}
        if len(dependency_by_gap) != len(self.gap_dependencies):
            raise ValueError("Event entity selection repeats one gap dependency.")
        if set(dependency_by_gap) != {item.id for item in self.gaps}:
            raise ValueError("Every selected Event gap requires one explicit dependency.")
        decision_by_id = {item.id: item for item in self.denotation_decisions}
        if len(decision_by_id) != len(self.denotation_decisions):
            raise ValueError("Event entity selection repeats a denotation decision.")
        if {item.denotation_decision_id for item in self.mentions} != set(decision_by_id):
            raise ValueError("Every selected mention requires one denotation decision.")
        if any(
            decision_by_id[item.denotation_decision_id].mention_candidate_id
            != item.source_span.mention_candidate_id
            or decision_by_id[item.denotation_decision_id].entity_kind is not item.entity_kind
            or decision_by_id[item.denotation_decision_id].entity_name != item.entity_name
            for item in self.mentions
        ):
            raise ValueError("Selected mention denotation drifted from its decision.")
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
    denotation_decision_id: Annotated[str, Field(pattern=r"^edd_[a-f0-9]{24}$")]
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
            denotation_decision_id=self.denotation_decision_id,
        )
        if self.id != expected:
            raise ValueError("Event entity candidate ID does not match its evidence.")
        return self


class EventEntityCandidateRoute(BaseModel):
    """One auditable allocation of a candidate to deterministic logic or Qwen."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: Annotated[str, Field(pattern=r"^ecr_[a-f0-9]{24}$")]
    candidate_id: Annotated[str, Field(pattern=r"^eec_[a-f0-9]{24}$")]
    route: EventEntityCandidateRouteKind
    reason: EventEntityCandidateRouteReason
    linguistic_trace_id: Annotated[str, Field(pattern=r"^xst_[a-f0-9]{24}$")]
    event_sentence_id: Annotated[str, Field(pattern=r"^s[1-9][0-9]*$")]
    entity_sentence_id: Annotated[str, Field(pattern=r"^s[1-9][0-9]*$")]

    @model_validator(mode="after")
    def validate_route(self) -> Self:
        if self.reason is EventEntityCandidateRouteReason.DIFFERENT_LINGUISTIC_SENTENCE:
            if (
                self.route is not EventEntityCandidateRouteKind.DETERMINISTIC_NOT_CONNECTED
                or self.event_sentence_id == self.entity_sentence_id
            ):
                raise ValueError("A cross-sentence route does not match its evidence.")
        elif (
            self.route is not EventEntityCandidateRouteKind.MODEL_JUDGMENT
            or self.event_sentence_id != self.entity_sentence_id
        ):
            raise ValueError("A semantic-judgment route does not match its evidence.")
        expected = _id(
            "ecr",
            self.candidate_id,
            self.route.value,
            self.reason.value,
            self.linguistic_trace_id,
            self.event_sentence_id,
            self.entity_sentence_id,
        )
        if self.id != expected:
            raise ValueError("Event entity candidate route ID does not match its evidence.")
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
    route_id: Annotated[str, Field(pattern=r"^ecr_[a-f0-9]{24}$")]
    judgment_id: Annotated[str, Field(pattern=r"^eij_[a-f0-9]{24}$")] | None = None
    disposition: EventEntityConnectionDisposition
    reason_code: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]*$")]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        expected = _id(
            "ecd",
            self.candidate_id,
            self.route_id,
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


class EventEntityIdentityConnection(BaseModel):
    """Deterministic identity-level projection over occurrence decisions."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: Annotated[str, Field(pattern=r"^eic_[a-f0-9]{24}$")]
    source_grounded_event_id: Annotated[str, Field(pattern=r"^sge_[a-f0-9]{24}$")]
    entity_identity: Annotated[str, Field(min_length=1)]
    entity_kind: EventEntityKind
    entity_name: Annotated[str, Field(min_length=1)]
    occurrence_candidate_ids: tuple[Annotated[str, Field(pattern=r"^eec_[a-f0-9]{24}$")], ...]
    connected_candidate_ids: tuple[Annotated[str, Field(pattern=r"^eec_[a-f0-9]{24}$")], ...]
    not_connected_candidate_ids: tuple[Annotated[str, Field(pattern=r"^eec_[a-f0-9]{24}$")], ...]
    unresolved_candidate_ids: tuple[Annotated[str, Field(pattern=r"^eec_[a-f0-9]{24}$")], ...]
    disposition: EventEntityConnectionDisposition

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        for label, values in (
            ("identity occurrence candidate IDs", self.occurrence_candidate_ids),
            ("identity connected candidate IDs", self.connected_candidate_ids),
            ("identity not-connected candidate IDs", self.not_connected_candidate_ids),
            ("identity unresolved candidate IDs", self.unresolved_candidate_ids),
        ):
            _ordered_distinct(label, values)
        partition = (
            set(self.connected_candidate_ids)
            | set(self.not_connected_candidate_ids)
            | set(self.unresolved_candidate_ids)
        )
        if partition != set(self.occurrence_candidate_ids):
            raise ValueError("Identity connection decisions do not partition its occurrences.")
        if (
            set(self.connected_candidate_ids) & set(self.not_connected_candidate_ids)
            or set(self.connected_candidate_ids) & set(self.unresolved_candidate_ids)
            or set(self.not_connected_candidate_ids) & set(self.unresolved_candidate_ids)
        ):
            raise ValueError("One occurrence cannot have multiple identity dispositions.")
        expected_disposition = (
            EventEntityConnectionDisposition.CONNECTED
            if self.connected_candidate_ids
            else (
                EventEntityConnectionDisposition.UNRESOLVED
                if self.unresolved_candidate_ids
                else EventEntityConnectionDisposition.NOT_CONNECTED
            )
        )
        if self.disposition is not expected_disposition:
            raise ValueError("Identity connection disposition does not match occurrence evidence.")
        expected = _id(
            "eic",
            self.source_grounded_event_id,
            self.entity_identity,
            self.entity_kind.value,
            self.entity_name,
            self.disposition.value,
            *self.occurrence_candidate_ids,
            *self.connected_candidate_ids,
            *self.not_connected_candidate_ids,
            *self.unresolved_candidate_ids,
        )
        if self.id != expected:
            raise ValueError("Identity connection ID does not match occurrence evidence.")
        return self


class EventEntityConnectionPreview(BaseModel):
    """Complete derived evidence for one Event-entity connection experiment run."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["event_entity_connection_preview_v5"] = (
        "event_entity_connection_preview_v5"
    )
    id: Annotated[str, Field(pattern=r"^eep_[a-f0-9]{24}$")]
    parent_preview_id: Annotated[str, Field(min_length=1)]
    parent_preview_sha256: Annotated[str, Field(pattern=_SHA256)]
    policy_id: Literal["event_entity_connection_contrastive_v6"] = EVENT_ENTITY_CONNECTION_POLICY_ID
    denotation_decisions: tuple[EventEntityDenotationDecision, ...]
    candidate_gaps: tuple[EventEntityCandidateGap, ...]
    gap_dependencies: tuple[EventEntityGapDependency, ...]
    candidates: tuple[EventEntityConnectionCandidate, ...]
    routes: tuple[EventEntityCandidateRoute, ...]
    judgments: tuple[EntityInvolvementJudgment, ...]
    decisions: tuple[EventEntityConnectionDecision, ...]
    drafts: tuple[EventEntityConnectionDraft, ...]
    identity_connections: tuple[EventEntityIdentityConnection, ...]
    traces: tuple[ExtractionStageTrace, ...]
    extraction_task_ids: tuple[Annotated[str, Field(min_length=1)], ...]
    model_run_ids: tuple[Annotated[str, Field(min_length=1)], ...]
    terminal_status: EventEntityConnectionPreviewStatus
    diagnostics: tuple[Annotated[str, Field(min_length=1)], ...] = ()

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        for label, values in (
            ("candidate gap IDs", tuple(item.id for item in self.candidate_gaps)),
            ("denotation decision IDs", tuple(item.id for item in self.denotation_decisions)),
            ("gap dependency IDs", tuple(item.id for item in self.gap_dependencies)),
            ("candidate IDs", tuple(item.id for item in self.candidates)),
            ("candidate route IDs", tuple(item.id for item in self.routes)),
            ("judgment IDs", tuple(item.id for item in self.judgments)),
            ("decision IDs", tuple(item.id for item in self.decisions)),
            ("draft IDs", tuple(item.id for item in self.drafts)),
            ("identity connection IDs", tuple(item.id for item in self.identity_connections)),
            ("trace IDs", tuple(item.id for item in self.traces)),
            ("ExtractionTask IDs", self.extraction_task_ids),
            ("ModelRun IDs", self.model_run_ids),
            ("diagnostics", self.diagnostics),
        ):
            _ordered_distinct(label, values)
        candidate_ids = {item.id for item in self.candidates}
        denotation_ids = {item.id for item in self.denotation_decisions}
        if len(denotation_ids) != len(self.denotation_decisions):
            raise ValueError("Connection Preview repeats a denotation decision.")
        if {item.denotation_decision_id for item in self.candidates} != denotation_ids:
            raise ValueError("Connection Preview denotation evidence is incomplete.")
        gap_ids = {item.id for item in self.candidate_gaps}
        dependency_gap_ids = tuple(item.gap_id for item in self.gap_dependencies)
        if len(set(dependency_gap_ids)) != len(dependency_gap_ids):
            raise ValueError("Connection Preview repeats one gap dependency.")
        if set(dependency_gap_ids) != gap_ids:
            raise ValueError("Connection Preview gap dependencies are incomplete.")
        judgment_by_candidate = {item.candidate_id: item for item in self.judgments}
        route_by_candidate = {item.candidate_id: item for item in self.routes}
        decision_by_candidate = {item.candidate_id: item for item in self.decisions}
        if len(decision_by_candidate) != len(self.decisions):
            raise ValueError("Connection Preview repeats a candidate decision.")
        if len(judgment_by_candidate) != len(self.judgments):
            raise ValueError("Connection Preview repeats a candidate judgment.")
        if len(route_by_candidate) != len(self.routes):
            raise ValueError("Connection Preview repeats a candidate route.")
        if set(route_by_candidate) != candidate_ids:
            raise ValueError("Every Event entity candidate requires one route.")
        if set(decision_by_candidate) != candidate_ids:
            raise ValueError("Every Event entity candidate requires one decision.")
        if not set(judgment_by_candidate).issubset(candidate_ids):
            raise ValueError("Entity involvement judgment references an unknown candidate.")
        model_candidate_ids = {
            item.candidate_id
            for item in self.routes
            if item.route is EventEntityCandidateRouteKind.MODEL_JUDGMENT
        }
        if model_candidate_ids:
            if not (
                len(self.extraction_task_ids) == len(self.model_run_ids) == len(self.traces) == 1
            ):
                raise ValueError(
                    "One Event model inventory requires exactly one execution and trace."
                )
        elif self.extraction_task_ids or self.model_run_ids or self.traces:
            raise ValueError("A deterministic-only Event cannot contain model execution evidence.")
        if not set(judgment_by_candidate).issubset(model_candidate_ids):
            raise ValueError("A deterministic Event entity route cannot have a model judgment.")
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
        route_by_id = {item.id: item for item in self.routes}
        if any(
            item.route_id not in route_by_id
            or route_by_id[item.route_id].candidate_id != item.candidate_id
            or (
                item.judgment_id is not None
                and (
                    item.judgment_id not in judgment_by_id
                    or judgment_by_id[item.judgment_id].candidate_id != item.candidate_id
                )
            )
            for item in self.decisions
        ):
            raise ValueError("Connection decision route or judgment lineage is invalid.")
        for decision in self.decisions:
            route = route_by_id[decision.route_id]
            if route.route is EventEntityCandidateRouteKind.DETERMINISTIC_NOT_CONNECTED:
                if (
                    decision.judgment_id is not None
                    or decision.disposition is not EventEntityConnectionDisposition.NOT_CONNECTED
                    or decision.reason_code != route.reason.value
                ):
                    raise ValueError("A deterministic route has an invalid decision.")
            elif decision.judgment_id is None and (
                decision.disposition is not EventEntityConnectionDisposition.UNRESOLVED
                or decision.reason_code != "model_judgment_failed"
            ):
                raise ValueError("A model route without a judgment must remain unresolved.")
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
        if self.identity_connections != consolidate_event_entity_connections(
            self.candidates,
            self.decisions,
        ):
            raise ValueError("Identity connections drifted from occurrence decisions.")
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
    denotation_decision_id: str,
) -> str:
    """Derive one candidate identity from the complete Event and entity evidence."""
    return _id(
        "eec",
        source_grounded_event_id,
        event_mention_id,
        entity_identity,
        entity_kind.value,
        denotation_decision_id,
        *mention_candidate_ids,
        *reference_decision_ids,
    )


def build_event_entity_connection_candidates(
    event: SourceGroundedEventDraft,
    mentions: tuple[EventEntityMentionInput, ...],
    *,
    source_text: str,
) -> tuple[EventEntityConnectionCandidate, ...]:
    """Construct one Event-bound candidate for each exact entity occurrence."""
    if hashlib.sha256(source_text.encode()).hexdigest() != event.source_text_sha256:
        raise ValueError("Event entity SourceSegment digest does not match its Event.")
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
    candidates: list[EventEntityConnectionCandidate] = []
    for mention in sorted(
        mentions,
        key=lambda item: (
            item.source_span.start,
            item.source_span.end,
            item.source_span.mention_candidate_id,
        ),
    ):
        source_spans = (mention.source_span,)
        mention_ids = tuple(item.mention_candidate_id for item in source_spans)
        antecedent_spans = (
            (mention.resolved_antecedent_span,)
            if mention.resolved_antecedent_span is not None
            else ()
        )
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
            entity_identity=mention.entity_identity,
            entity_kind=mention.entity_kind,
            mention_candidate_ids=mention_ids,
            reference_decision_ids=reference_ids,
            denotation_decision_id=mention.denotation_decision_id,
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
                entity_identity=mention.entity_identity,
                entity_kind=mention.entity_kind,
                entity_name=mention.entity_name,
                denotation_decision_id=mention.denotation_decision_id,
                primary_source_span_id=mention.source_span.id,
                source_spans=source_spans,
                resolved_antecedent_spans=antecedent_spans,
                reference_decision_ids=reference_ids,
            )
        )
    return tuple(candidates)


def event_entity_linguistic_evidence_from_trace(
    trace: ExtractionStageTrace,
    *,
    source_text: str,
) -> EventEntityLinguisticEvidence:
    """Map one validated upstream Stanza trace into a narrow routing DTO."""
    source_digest = hashlib.sha256(source_text.encode()).hexdigest()
    if (
        trace.stage_id != "linguistic_analysis"
        or trace.status is not ExtractionStageStatus.COMPLETED
        or trace.source_text_sha256 != source_digest
    ):
        raise ValueError("Event entity routing requires matching completed linguistic evidence.")
    source_copy = derive_source_copy_view(source_text)
    if trace.input.get("source_copy_text") != source_copy.text:
        raise ValueError("Event entity linguistic input does not match the derived Source copy.")
    raw_tokens = trace.output.get("tokens")
    if not isinstance(raw_tokens, list) or not raw_tokens:
        raise ValueError("Event entity linguistic trace requires a nonempty token list.")
    parsed_tokens = tuple(
        EventEntityLinguisticToken.model_validate(cast(dict[str, object], item))
        for item in raw_tokens
        if isinstance(item, dict)
    )
    if len(parsed_tokens) != len(raw_tokens):
        raise ValueError("Event entity linguistic trace contains a non-object token.")
    output_digest = trace.output.get("source_text_sha256")
    if output_digest != hashlib.sha256(source_copy.text.encode()).hexdigest():
        raise ValueError("Event entity linguistic output does not match the derived Source copy.")
    if any(
        item.end > len(source_copy.text) or source_copy.text[item.start : item.end] != item.text
        for item in parsed_tokens
    ):
        raise ValueError("Event entity linguistic token does not match Source-copy characters.")
    tokens = tuple(
        EventEntityLinguisticToken.model_validate(
            {
                **item.model_dump(mode="python"),
                "start": source_copy.authoritative_range(item.start, item.end)[0],
                "end": source_copy.authoritative_range(item.start, item.end)[1],
            }
        )
        for item in parsed_tokens
    )
    if any(source_text[item.start : item.end] != item.text for item in tokens):
        raise ValueError("Event entity linguistic token does not map to authoritative characters.")
    configuration = trace.configuration
    model_id = configuration.get("model_id")
    model_version = configuration.get("model_version")
    resource_identity = configuration.get("resource_identity")
    if not all(isinstance(item, str) and item for item in (model_id, model_version)) or not (
        isinstance(resource_identity, str) and re.fullmatch(_SHA256, resource_identity)
    ):
        raise ValueError("Event entity linguistic trace model identity is incomplete.")
    return EventEntityLinguisticEvidence(
        trace_id=trace.id,
        source_segment_id=trace.source_segment_id,
        source_text_sha256=source_digest,
        producer_id=trace.producer_id,
        model_id=cast(str, model_id),
        model_version=cast(str, model_version),
        resource_identity=resource_identity,
        tokens=tokens,
    )


def build_event_entity_candidate_routes(
    *,
    source_text: str,
    candidates: tuple[EventEntityConnectionCandidate, ...],
    linguistic_evidence: EventEntityLinguisticEvidence,
) -> tuple[EventEntityCandidateRoute, ...]:
    """Allocate high-certainty structural negatives to KoteKomi and the rest to Qwen."""
    if hashlib.sha256(source_text.encode()).hexdigest() != linguistic_evidence.source_text_sha256:
        raise ValueError("Event entity routing source does not match linguistic evidence.")
    if any(
        candidate.source_segment_id != linguistic_evidence.source_segment_id
        or candidate.source_text_sha256 != linguistic_evidence.source_text_sha256
        for candidate in candidates
    ):
        raise ValueError("Event entity candidate does not match linguistic routing evidence.")
    if not candidates:
        return ()
    event_expression = candidates[0].event_expression_text
    if any(candidate.event_expression_text != event_expression for candidate in candidates):
        raise ValueError("Event entity routing candidates do not share one Event expression.")
    event_ranges = tuple(
        (match.start(), match.end())
        for match in re.finditer(re.escape(event_expression), source_text)
    )
    if len(event_ranges) != 1:
        raise ValueError("Event entity routing requires one exact Event expression occurrence.")
    event_sentence_id = _linguistic_sentence_id_for_range(
        linguistic_evidence.tokens,
        *event_ranges[0],
    )
    routes: list[EventEntityCandidateRoute] = []
    for candidate in candidates:
        span = next(
            item for item in candidate.source_spans if item.id == candidate.primary_source_span_id
        )
        entity_sentence_id = _linguistic_sentence_id_for_range(
            linguistic_evidence.tokens,
            span.start,
            span.end,
        )
        if entity_sentence_id != event_sentence_id:
            route = EventEntityCandidateRouteKind.DETERMINISTIC_NOT_CONNECTED
            reason = EventEntityCandidateRouteReason.DIFFERENT_LINGUISTIC_SENTENCE
        else:
            route = EventEntityCandidateRouteKind.MODEL_JUDGMENT
            reason = EventEntityCandidateRouteReason.SEMANTIC_JUDGMENT_REQUIRED
        route_values = (
            candidate.id,
            route.value,
            reason.value,
            linguistic_evidence.trace_id,
            event_sentence_id,
            entity_sentence_id,
        )
        routes.append(
            EventEntityCandidateRoute(
                id=_id("ecr", *route_values),
                candidate_id=candidate.id,
                route=route,
                reason=reason,
                linguistic_trace_id=linguistic_evidence.trace_id,
                event_sentence_id=event_sentence_id,
                entity_sentence_id=entity_sentence_id,
            )
        )
    return tuple(routes)


def consolidate_event_entity_connections(
    candidates: tuple[EventEntityConnectionCandidate, ...],
    decisions: tuple[EventEntityConnectionDecision, ...],
) -> tuple[EventEntityIdentityConnection, ...]:
    """Project occurrence decisions to identity level without discarding any decision."""
    candidate_by_id = {item.id: item for item in candidates}
    if len(candidate_by_id) != len(candidates):
        raise ValueError("Identity consolidation received repeated candidates.")
    decision_by_candidate = {item.candidate_id: item for item in decisions}
    if len(decision_by_candidate) != len(decisions):
        raise ValueError("Identity consolidation received repeated occurrence decisions.")
    if set(decision_by_candidate) != set(candidate_by_id):
        raise ValueError("Identity consolidation requires one decision per occurrence.")
    grouped: dict[
        tuple[str, str, EventEntityKind, str],
        list[tuple[EventEntityConnectionCandidate, EventEntityConnectionDecision]],
    ] = defaultdict(list)
    for candidate in candidates:
        grouped[
            (
                candidate.source_grounded_event_id,
                candidate.entity_identity,
                candidate.entity_kind,
                candidate.entity_name,
            )
        ].append((candidate, decision_by_candidate[candidate.id]))
    projections: list[EventEntityIdentityConnection] = []
    for (event_id, identity, kind, name), values in sorted(
        grouped.items(),
        key=lambda item: (item[0][0], item[0][2].value, item[0][1], item[0][3]),
    ):
        occurrence_ids = tuple(sorted(item[0].id for item in values))
        connected = tuple(
            sorted(
                candidate.id
                for candidate, decision in values
                if decision.disposition is EventEntityConnectionDisposition.CONNECTED
            )
        )
        not_connected = tuple(
            sorted(
                candidate.id
                for candidate, decision in values
                if decision.disposition is EventEntityConnectionDisposition.NOT_CONNECTED
            )
        )
        unresolved = tuple(
            sorted(
                candidate.id
                for candidate, decision in values
                if decision.disposition is EventEntityConnectionDisposition.UNRESOLVED
            )
        )
        disposition = (
            EventEntityConnectionDisposition.CONNECTED
            if connected
            else (
                EventEntityConnectionDisposition.UNRESOLVED
                if unresolved
                else EventEntityConnectionDisposition.NOT_CONNECTED
            )
        )
        identifier_values = (
            event_id,
            identity,
            kind.value,
            name,
            disposition.value,
            *occurrence_ids,
            *connected,
            *not_connected,
            *unresolved,
        )
        projections.append(
            EventEntityIdentityConnection(
                id=_id("eic", *identifier_values),
                source_grounded_event_id=event_id,
                entity_identity=identity,
                entity_kind=kind,
                entity_name=name,
                occurrence_candidate_ids=occurrence_ids,
                connected_candidate_ids=connected,
                not_connected_candidate_ids=not_connected,
                unresolved_candidate_ids=unresolved,
                disposition=disposition,
            )
        )
    return tuple(projections)


def select_event_entity_mentions(
    *,
    source_text: str,
    event: SourceGroundedEventDraft,
    mention_preview: HybridExtractionPreview,
    reference_preview: HybridReferencePreview,
    grounding_preview: HybridEntityGroundingPreview,
) -> EventEntityCandidateSelection:
    """Map effective upstream mention evidence into Actor and Organization inputs."""
    source_digest = hashlib.sha256(source_text.encode()).hexdigest()
    if source_digest != event.source_text_sha256:
        raise ValueError("Event entity selection SourceSegment does not match its Event.")
    if reference_preview.parent_preview_id != mention_preview.id:
        raise ValueError("Event entity reference evidence names another mention Preview.")
    if (
        grounding_preview.parent_preview_id != reference_preview.id
        or grounding_preview.mention_preview_id != mention_preview.id
    ):
        raise ValueError("Event entity grounding evidence names another upstream Preview.")
    references = {item.candidate_id: item for item in reference_preview.reference_decisions}
    interpretations = {item.candidate_id: item for item in mention_preview.interpretations}
    observations = {item.id: item for item in mention_preview.observations}
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
    monotonic_specialist_candidates = _monotonic_specialist_candidate_ids(
        candidates=mention_preview.candidates,
        interpretations=interpretations,
        observations=observations,
        reference_candidate_ids=set(references),
    )
    selected.update(monotonic_specialist_candidates)
    ambiguous.difference_update(monotonic_specialist_candidates)
    link_evidence = {item.candidate_id: item for item in grounding_preview.link_evidence}
    antecedents = _reference_spans(reference_preview)
    known_denotations = _known_entity_denotations(mention_preview, grounding_preview)
    mentions: list[EventEntityMentionInput] = []
    denotation_decisions: list[EventEntityDenotationDecision] = []
    gaps: list[EventEntityCandidateGap] = []
    gap_dependencies: list[EventEntityGapDependency] = []
    for candidate in mention_preview.candidates:
        if candidate.source_segment_id != event.source_segment_id:
            continue
        _validate_candidate_source(candidate, source_text, source_digest)
        reference = references.get(candidate.id)
        if candidate.id in ambiguous:
            _record_dependent_gap(
                gaps=gaps,
                dependencies=gap_dependencies,
                candidate=candidate,
                reason=EventEntityCandidateGapReason.BOUNDARY_AMBIGUOUS,
                reference=reference,
                event=event,
                source_text=source_text,
            )
            continue
        if candidate.id not in selected:
            continue
        interpretation = interpretations.get(candidate.id)
        if reference is not None and reference.status is ReferenceStatus.AMBIGUOUS:
            _record_dependent_gap(
                gaps=gaps,
                dependencies=gap_dependencies,
                candidate=candidate,
                reason=EventEntityCandidateGapReason.REFERENCE_AMBIGUOUS,
                reference=reference,
                event=event,
                source_text=source_text,
            )
            continue
        if reference is not None and reference.status is ReferenceStatus.UNRESOLVED:
            _record_dependent_gap(
                gaps=gaps,
                dependencies=gap_dependencies,
                candidate=candidate,
                reason=EventEntityCandidateGapReason.REFERENCE_UNRESOLVED,
                reference=reference,
                event=event,
                source_text=source_text,
            )
            continue
        if (
            interpretation is not None
            and interpretation.referentiality is Referentiality.GENERIC_CLASS
        ):
            continue
        resolved_antecedent: ReferenceSpan | None = None
        resolved_name = _trim_possessive(candidate.text)
        reference_id: str | None = None
        if interpretation is not None and interpretation.referentiality is Referentiality.ANAPHORIC:
            if reference is None:
                _record_dependent_gap(
                    gaps=gaps,
                    dependencies=gap_dependencies,
                    candidate=candidate,
                    reason=EventEntityCandidateGapReason.REFERENCE_UNRESOLVED,
                    reference=reference,
                    event=event,
                    source_text=source_text,
                )
                continue
            if len(reference.antecedent_span_ids) != 1:
                _record_dependent_gap(
                    gaps=gaps,
                    dependencies=gap_dependencies,
                    candidate=candidate,
                    reason=EventEntityCandidateGapReason.REFERENCE_ANTECEDENT_MISSING,
                    reference=reference,
                    event=event,
                    source_text=source_text,
                )
                continue
            resolved_antecedent = antecedents.get(reference.antecedent_span_ids[0])
            if resolved_antecedent is None:
                _record_dependent_gap(
                    gaps=gaps,
                    dependencies=gap_dependencies,
                    candidate=candidate,
                    reason=EventEntityCandidateGapReason.REFERENCE_ANTECEDENT_MISSING,
                    reference=reference,
                    event=event,
                    source_text=source_text,
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
            _record_dependent_gap(
                gaps=gaps,
                dependencies=gap_dependencies,
                candidate=candidate,
                reason=EventEntityCandidateGapReason.REFERENCE_ANTECEDENT_MISSING,
                reference=reference,
                event=event,
                source_text=source_text,
            )
            continue
        denotation = None
        if (
            reference is not None
            and reference.status is ReferenceStatus.RESOLVED
            and resolved_antecedent is not None
        ):
            denotation = _resolved_reference_denotation_decision(
                candidate=candidate,
                reference=reference,
                antecedent=resolved_antecedent,
                known_denotations=known_denotations,
            )
        if denotation is None:
            denotation = _event_entity_denotation_decision(
                candidate=candidate,
                resolved_name=resolved_name,
                interpretation=interpretation,
                observations=observations,
                link_evidence=link_evidence.get(candidate.id),
            )
        if denotation is None:
            if interpretation is None:
                _record_dependent_gap(
                    gaps=gaps,
                    dependencies=gap_dependencies,
                    candidate=candidate,
                    reason=EventEntityCandidateGapReason.INTERPRETATION_MISSING,
                    reference=reference,
                    event=event,
                    source_text=source_text,
                )
            elif interpretation.contextual_kind is ContextualKind.UNCLEAR:
                _record_dependent_gap(
                    gaps=gaps,
                    dependencies=gap_dependencies,
                    candidate=candidate,
                    reason=EventEntityCandidateGapReason.ENTITY_KIND_AMBIGUOUS,
                    reference=reference,
                    event=event,
                    source_text=source_text,
                )
            continue
        source_span = _source_span(candidate, reference_id)
        denotation_decisions.append(denotation)
        mentions.append(
            EventEntityMentionInput(
                entity_identity=_local_entity_identity(
                    denotation.entity_kind,
                    denotation.entity_name,
                ),
                entity_kind=denotation.entity_kind,
                entity_name=denotation.entity_name,
                denotation_decision_id=denotation.id,
                source_span=source_span,
                resolved_antecedent_span=resolved_antecedent,
            )
        )
    rescued_mentions, rescued_decisions = _coreference_name_rescues(
        source_text=source_text,
        event=event,
        mention_preview=mention_preview,
        reference_preview=reference_preview,
        grounding_preview=grounding_preview,
        existing_candidate_ids={item.source_span.mention_candidate_id for item in mentions},
    )
    mentions.extend(rescued_mentions)
    denotation_decisions.extend(rescued_decisions)
    group_mentions, group_decisions = _source_bound_actor_group_mentions(
        source_text=source_text,
        event=event,
        mentions=tuple(mentions),
        denotation_decisions=tuple(denotation_decisions),
    )
    group_ranges = {
        (item.source_span.start, item.source_span.end, item.source_span.text)
        for item in group_mentions
    }
    group_candidate_ids = {item.source_span.mention_candidate_id for item in group_mentions}
    mentions = [
        item
        for item in mentions
        if (item.source_span.start, item.source_span.end, item.source_span.text) not in group_ranges
    ]
    gaps = [item for item in gaps if item.mention_candidate_id not in group_candidate_ids]
    retained_gap_ids = {item.id for item in gaps}
    gap_dependencies = [item for item in gap_dependencies if item.gap_id in retained_gap_ids]
    mentions.extend(group_mentions)
    denotation_decisions.extend(group_decisions)
    ordered_mentions = tuple(
        sorted(
            mentions,
            key=lambda item: (
                item.source_span.start,
                item.source_span.end,
                item.source_span.mention_candidate_id,
            ),
        )
    )
    decision_by_id = {item.id: item for item in denotation_decisions}
    return EventEntityCandidateSelection(
        mentions=ordered_mentions,
        denotation_decisions=tuple(
            decision_by_id[item.denotation_decision_id] for item in ordered_mentions
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
        gap_dependencies=tuple(
            sorted(
                gap_dependencies,
                key=lambda item: (item.event_expression_start, item.gap_id),
            )
        ),
    )


def _event_entity_denotation_decision(
    *,
    candidate: MentionCandidate,
    resolved_name: str,
    interpretation: MentionInterpretation | None,
    observations: dict[str, MentionObservation],
    link_evidence: EntityLinkEvidence | None,
) -> EventEntityDenotationDecision | None:
    candidate_observations = tuple(
        observations[item] for item in candidate.observation_ids if item in observations
    )
    _validate_candidate_observations(candidate, candidate_observations)
    canonical_name = _canonical_entity_name(resolved_name)
    strong_person_observations = {
        item.id
        for item in candidate_observations
        if item.producer_id.startswith(STRONG_PERSON_OBSERVATION_PRODUCER_PREFIXES)
        and ContextualKind.PERSON in item.type_hints
        and not set(item.type_hints) & {ContextualKind.ORGANIZATION, ContextualKind.GOVERNMENT}
    }
    refined_person_evidence: set[str] = (
        {link_evidence.id}
        if link_evidence is not None
        and link_evidence.coarse_mention_type in REFINED_PERSON_MENTION_TYPES
        else set()
    )
    strong_person_evidence = tuple(
        sorted(strong_person_observations | refined_person_evidence)
        if strong_person_observations
        else ()
    )
    strong_organization_observations = {
        item.id
        for item in candidate_observations
        if item.producer_id.startswith(STRONG_ORGANIZATION_OBSERVATION_PRODUCER_PREFIXES)
        and set(item.type_hints) & {ContextualKind.ORGANIZATION, ContextualKind.GOVERNMENT}
        and ContextualKind.PERSON not in item.type_hints
    }
    refined_organization_evidence: set[str] = (
        {link_evidence.id}
        if link_evidence is not None
        and link_evidence.coarse_mention_type in REFINED_ORGANIZATION_MENTION_TYPES
        else set()
    )
    external_organization_class_evidence: set[str] = (
        {link_evidence.id}
        if link_evidence is not None
        and _has_exact_title_organization_class(candidate, link_evidence)
        else set()
    )
    strong_organization_evidence = tuple(
        sorted(
            strong_organization_observations
            | refined_organization_evidence
            | external_organization_class_evidence
        )
    )
    conflicting_collective_evidence = any(
        set(item.type_hints) & {ContextualKind.ORGANIZATION, ContextualKind.GOVERNMENT}
        for item in candidate_observations
    )
    person_context_compatible = (
        interpretation is None
        or interpretation.contextual_kind in PERSON_SPECIALIST_COMPATIBLE_KINDS
    )
    organization_context_compatible = (
        interpretation is None
        or interpretation.contextual_kind in ORGANIZATION_SPECIALIST_COMPATIBLE_KINDS
    )
    if (
        strong_person_evidence
        and person_context_compatible
        and not (conflicting_collective_evidence or strong_organization_evidence)
    ):
        diagnostics = (
            (f"model_contextual_kind_overridden:{interpretation.contextual_kind.value}",)
            if interpretation is not None
            and interpretation.contextual_kind is not ContextualKind.PERSON
            else ()
        )
        return _build_denotation_decision(
            mention_candidate_id=candidate.id,
            entity_kind=EventEntityKind.ACTOR,
            entity_name=canonical_name,
            rule_id=EventEntityDenotationRule.SPECIALIST_PERSON_EVIDENCE,
            source_evidence_ids=strong_person_evidence,
            interpretation=interpretation,
            diagnostics=diagnostics,
        )
    if (
        strong_organization_evidence
        and organization_context_compatible
        and not strong_person_evidence
    ):
        diagnostic_values: list[str] = []
        if interpretation is not None and interpretation.contextual_kind not in {
            ContextualKind.ORGANIZATION,
            ContextualKind.GOVERNMENT,
        }:
            diagnostic_values.append(
                f"model_contextual_kind_overridden:{interpretation.contextual_kind.value}"
            )
        if (
            external_organization_class_evidence
            and link_evidence is not None
            and link_evidence.linked_entity_classes is not None
        ):
            diagnostic_values.append(
                "external_organization_class:"
                f"{link_evidence.linked_entity_classes.wikidata_id}:"
                f"{WIKIDATA_ORGANIZATION_CLASS_ID}"
            )
        diagnostics = tuple(sorted(diagnostic_values))
        return _build_denotation_decision(
            mention_candidate_id=candidate.id,
            entity_kind=EventEntityKind.ORGANIZATION,
            entity_name=canonical_name,
            rule_id=(
                EventEntityDenotationRule.EXTERNAL_ORGANIZATION_CLASS
                if external_organization_class_evidence
                and not (strong_organization_observations or refined_organization_evidence)
                else EventEntityDenotationRule.SPECIALIST_ORGANIZATION_EVIDENCE
            ),
            source_evidence_ids=strong_organization_evidence,
            interpretation=interpretation,
            diagnostics=diagnostics,
        )
    if interpretation is None:
        return None
    kind = _event_entity_kind(interpretation)
    if kind is None:
        return None
    return _build_denotation_decision(
        mention_candidate_id=candidate.id,
        entity_kind=kind,
        entity_name=canonical_name,
        rule_id=EventEntityDenotationRule.MODEL_CONTEXTUAL_KIND,
        source_evidence_ids=candidate.observation_ids,
        interpretation=interpretation,
    )


def _has_exact_title_organization_class(
    candidate: MentionCandidate,
    link_evidence: EntityLinkEvidence,
) -> bool:
    class_evidence = link_evidence.linked_entity_classes
    if class_evidence is None or not link_evidence.candidates:
        return False
    top_candidate = link_evidence.candidates[0]
    if (
        top_candidate.wikidata_id != class_evidence.wikidata_id
        or top_candidate.wikipedia_title is None
        or _canonical_entity_name(top_candidate.wikipedia_title).casefold()
        != _canonical_entity_name(candidate.text).casefold()
    ):
        return False
    return any(item.class_id == WIKIDATA_ORGANIZATION_CLASS_ID for item in class_evidence.classes)


def _resolved_reference_denotation_decision(
    *,
    candidate: MentionCandidate,
    reference: ReferenceDecision,
    antecedent: ReferenceSpan,
    known_denotations: dict[str, tuple[tuple[EventEntityKind, str, tuple[str, ...]], ...]],
) -> EventEntityDenotationDecision | None:
    known = known_denotations.get(_normalized_entity_name(antecedent.text), ())
    kinds = {item[0] for item in known}
    if len(kinds) != 1:
        return None
    kind = next(iter(kinds))
    names = {item[1] for item in known if item[0] is kind}
    entity_name = min(names, key=lambda item: (len(item), item))
    source_evidence_ids = tuple(
        sorted(
            {
                reference.id,
                antecedent.id,
                *(evidence_id for item in known for evidence_id in item[2]),
            }
        )
    )
    return _build_denotation_decision(
        mention_candidate_id=candidate.id,
        entity_kind=kind,
        entity_name=entity_name,
        rule_id=EventEntityDenotationRule.RESOLVED_REFERENCE,
        source_evidence_ids=source_evidence_ids,
        interpretation=None,
        diagnostics=("unique_resolved_antecedent_denotation",),
    )


def _monotonic_specialist_candidate_ids(
    *,
    candidates: tuple[MentionCandidate, ...],
    interpretations: dict[str, MentionInterpretation],
    observations: dict[str, MentionObservation],
    reference_candidate_ids: set[str],
) -> set[str]:
    selected: set[str] = set()
    for candidate in candidates:
        if candidate.id in reference_candidate_ids:
            continue
        interpretation = interpretations.get(candidate.id)
        if interpretation is not None and interpretation.referentiality is Referentiality.ANAPHORIC:
            continue
        candidate_observations = tuple(
            observations[item] for item in candidate.observation_ids if item in observations
        )
        _validate_candidate_observations(candidate, candidate_observations)
        for observation in candidate_observations:
            if not observation.producer_id.startswith(
                STRONG_PERSON_OBSERVATION_PRODUCER_PREFIXES
                + STRONG_ORGANIZATION_OBSERVATION_PRODUCER_PREFIXES
            ):
                continue
            hints = set(observation.type_hints)
            if hints == {ContextualKind.PERSON} or (
                hints and hints <= {ContextualKind.ORGANIZATION, ContextualKind.GOVERNMENT}
            ):
                selected.add(candidate.id)
                break
    return selected


def _validate_candidate_observations(
    candidate: MentionCandidate,
    observations: tuple[MentionObservation, ...],
) -> None:
    if any(
        item.source_segment_id != candidate.source_segment_id
        or item.start != candidate.start
        or item.end != candidate.end
        or item.text != candidate.text
        for item in observations
    ):
        raise ValueError("MentionObservation does not match its MentionCandidate source span.")


def _build_denotation_decision(
    *,
    mention_candidate_id: str,
    entity_kind: EventEntityKind,
    entity_name: str,
    rule_id: EventEntityDenotationRule,
    source_evidence_ids: tuple[str, ...],
    interpretation: MentionInterpretation | None,
    diagnostics: tuple[str, ...] = (),
) -> EventEntityDenotationDecision:
    ordered_evidence = tuple(sorted(set(source_evidence_ids)))
    ordered_diagnostics = tuple(sorted(set(diagnostics)))
    interpretation_id = interpretation.id if interpretation is not None else None
    values = (
        mention_candidate_id,
        entity_kind.value,
        entity_name,
        rule_id.value,
        interpretation_id or "",
        *ordered_evidence,
        *ordered_diagnostics,
    )
    return EventEntityDenotationDecision(
        id=_id("edd", *values),
        mention_candidate_id=mention_candidate_id,
        entity_kind=entity_kind,
        entity_name=entity_name,
        rule_id=rule_id,
        source_evidence_ids=ordered_evidence,
        mention_interpretation_id=interpretation_id,
        diagnostics=ordered_diagnostics,
    )


def _coreference_name_rescues(
    *,
    source_text: str,
    event: SourceGroundedEventDraft,
    mention_preview: HybridExtractionPreview,
    reference_preview: HybridReferencePreview,
    grounding_preview: HybridEntityGroundingPreview,
    existing_candidate_ids: set[str],
) -> tuple[list[EventEntityMentionInput], list[EventEntityDenotationDecision]]:
    known = _known_entity_denotations(mention_preview, grounding_preview)
    if not known:
        return [], []
    source_digest = hashlib.sha256(source_text.encode()).hexdigest()
    evidence_by_span: dict[tuple[int, int, str], set[str]] = defaultdict(set)
    diagnostics_by_span: dict[tuple[int, int, str], set[str]] = defaultdict(set)
    for known_values in known.values():
        if len({item[0] for item in known_values}) != 1:
            continue
        for entity_name in sorted({item[1] for item in known_values}):
            pattern = _exact_entity_name_pattern(entity_name)
            for match in re.finditer(pattern, source_text):
                key = (match.start(), match.end(), match.group())
                evidence_by_span[key].update(
                    evidence_id for item in known_values for evidence_id in item[2]
                )
                diagnostics_by_span[key].add("exact_name_recurrence")
    for observation in reference_preview.coreference_observations:
        if (
            observation.source_segment_id != event.source_segment_id
            or observation.source_text_sha256 != source_digest
        ):
            continue
        for cluster in observation.clusters:
            if len(cluster) < 2:
                continue
            for span in cluster:
                if (
                    span.source_segment_id == event.source_segment_id
                    and span.end <= len(source_text)
                    and source_text[span.start : span.end] == span.text
                ):
                    key = (span.start, span.end, span.text)
                    evidence_by_span[key].add(observation.id)
                    diagnostics_by_span[key].add("coreference_cluster_exact_name_recurrence")
    rescued_mentions: list[EventEntityMentionInput] = []
    rescued_decisions: list[EventEntityDenotationDecision] = []
    for (start, end, text), coreference_evidence_ids in sorted(evidence_by_span.items()):
        normalized = _normalized_entity_name(text)
        known_values = known.get(normalized, ())
        kinds = {item[0] for item in known_values}
        if len(kinds) != 1:
            continue
        kind = next(iter(kinds))
        entity_name = min((item[1] for item in known_values), key=lambda item: (len(item), item))
        mention_candidate_id = _id(
            "mnc",
            event.source_segment_id,
            source_digest,
            str(start),
            str(end),
            text,
        )
        if mention_candidate_id in existing_candidate_ids:
            continue
        source_evidence_ids = tuple(
            sorted(
                coreference_evidence_ids
                | {evidence_id for item in known_values for evidence_id in item[2]}
            )
        )
        denotation = _build_denotation_decision(
            mention_candidate_id=mention_candidate_id,
            entity_kind=kind,
            entity_name=entity_name,
            rule_id=EventEntityDenotationRule.KNOWN_NAME_RECURRENCE,
            source_evidence_ids=source_evidence_ids,
            interpretation=None,
            diagnostics=tuple(sorted(diagnostics_by_span[(start, end, text)])),
        )
        source_span = _source_span_from_values(
            source_segment_id=event.source_segment_id,
            source_text_sha256=source_digest,
            start=start,
            end=end,
            text=text,
            mention_candidate_id=mention_candidate_id,
            reference_decision_id=None,
        )
        rescued_mentions.append(
            EventEntityMentionInput(
                entity_identity=_local_entity_identity(kind, entity_name),
                entity_kind=kind,
                entity_name=entity_name,
                denotation_decision_id=denotation.id,
                source_span=source_span,
            )
        )
        rescued_decisions.append(denotation)
        existing_candidate_ids.add(mention_candidate_id)
    return rescued_mentions, rescued_decisions


def _known_entity_denotations(
    mention_preview: HybridExtractionPreview,
    grounding_preview: HybridEntityGroundingPreview,
) -> dict[str, tuple[tuple[EventEntityKind, str, tuple[str, ...]], ...]]:
    selected = set(
        effective_mention_candidate_ids(
            mention_preview.boundary_decisions,
            mention_preview.boundary_adjudications,
        )
    )
    observations = {item.id: item for item in mention_preview.observations}
    interpretations = {item.candidate_id: item for item in mention_preview.interpretations}
    link_evidence = {item.candidate_id: item for item in grounding_preview.link_evidence}
    grouped: dict[str, list[tuple[EventEntityKind, str, tuple[str, ...]]]] = defaultdict(list)
    for candidate in mention_preview.candidates:
        if candidate.id not in selected:
            continue
        interpretation = interpretations.get(candidate.id)
        if (
            interpretation is None
            or interpretation.referentiality is not Referentiality.SPECIFIC_ENTITY
        ):
            continue
        name = _trim_possessive(candidate.text)
        denotation = _event_entity_denotation_decision(
            candidate=candidate,
            resolved_name=name,
            interpretation=interpretation,
            observations=observations,
            link_evidence=link_evidence.get(candidate.id),
        )
        if denotation is None or not name:
            continue
        grouped[_normalized_entity_name(name)].append(
            (denotation.entity_kind, name, (candidate.id, *denotation.source_evidence_ids))
        )
    return {
        key: tuple(sorted(values, key=lambda item: (item[0].value, item[1], item[2])))
        for key, values in grouped.items()
    }


def _source_bound_actor_group_mentions(
    *,
    source_text: str,
    event: SourceGroundedEventDraft,
    mentions: tuple[EventEntityMentionInput, ...],
    denotation_decisions: tuple[EventEntityDenotationDecision, ...],
) -> tuple[list[EventEntityMentionInput], list[EventEntityDenotationDecision]]:
    decision_by_id = {item.id: item for item in denotation_decisions}
    derived_ranges: set[tuple[int, int, str]] = set()
    source_digest = hashlib.sha256(source_text.encode()).hexdigest()
    derived_mentions: list[EventEntityMentionInput] = []
    derived_decisions: list[EventEntityDenotationDecision] = []
    for mention in mentions:
        match = re.match(r"\s+(?P<role>[A-Za-z]+)\b", source_text[mention.source_span.end :])
        if (
            match is None
            or match.group("role").casefold() not in SOURCE_BOUND_ACTOR_GROUP_ROLE_HEADS
        ):
            continue
        start = mention.source_span.start
        end = mention.source_span.end + match.end()
        text = source_text[start:end]
        if (start, end, text) in derived_ranges:
            continue
        entity_name = re.sub(r"\s+", " ", text).strip()
        mention_candidate_id = _id(
            "mnc",
            event.source_segment_id,
            source_digest,
            str(start),
            str(end),
            text,
        )
        parent_decision = decision_by_id[mention.denotation_decision_id]
        denotation = _build_denotation_decision(
            mention_candidate_id=mention_candidate_id,
            entity_kind=EventEntityKind.ACTOR,
            entity_name=entity_name,
            rule_id=EventEntityDenotationRule.SOURCE_BOUND_ACTOR_GROUP,
            source_evidence_ids=tuple(
                sorted(
                    {
                        parent_decision.id,
                        mention.source_span.mention_candidate_id,
                        *parent_decision.source_evidence_ids,
                    }
                )
            ),
            interpretation=None,
            diagnostics=("exact_named_agent_plus_plural_human_role",),
        )
        source_span = _source_span_from_values(
            source_segment_id=event.source_segment_id,
            source_text_sha256=source_digest,
            start=start,
            end=end,
            text=text,
            mention_candidate_id=mention_candidate_id,
            reference_decision_id=None,
        )
        derived_mentions.append(
            EventEntityMentionInput(
                entity_identity=_source_bound_actor_group_identity(source_span),
                entity_kind=EventEntityKind.ACTOR,
                entity_name=entity_name,
                denotation_decision_id=denotation.id,
                source_span=source_span,
            )
        )
        derived_decisions.append(denotation)
        derived_ranges.add((start, end, text))
    return derived_mentions, derived_decisions


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
    route: EventEntityCandidateRoute,
    judgment: EntityInvolvementJudgment | None,
) -> tuple[EventEntityConnectionDecision, EventEntityConnectionDraft | None]:
    """Map one finite answer into a deterministic disposition and optional draft."""
    if route.candidate_id != candidate.id:
        raise ValueError("Event entity route names another candidate.")
    if judgment is not None and judgment.candidate_id != candidate.id:
        raise ValueError("Entity involvement judgment names another candidate.")
    if route.route is EventEntityCandidateRouteKind.DETERMINISTIC_NOT_CONNECTED:
        if judgment is not None:
            raise ValueError("A deterministic Event entity route cannot carry a model judgment.")
        disposition = EventEntityConnectionDisposition.NOT_CONNECTED
        reason = route.reason.value
        judgment_id = None
    elif judgment is None:
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
        id=_id(
            "ecd",
            candidate.id,
            route.id,
            judgment_id or "",
            disposition.value,
            reason,
        ),
        candidate_id=candidate.id,
        route_id=route.id,
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
    candidates: tuple[EventEntityConnectionCandidate, ...],
) -> bytes:
    """Render one contrastive, source-marked, ID-free Event candidate inventory."""
    if not candidates:
        raise ValueError("Event entity task requires at least one model-routed candidate.")
    source_digest = hashlib.sha256(source_text.encode()).hexdigest()
    if any(item.source_text_sha256 != source_digest for item in candidates):
        raise ValueError("Event entity task SourceSegment digest does not match.")
    event_expression = candidates[0].event_expression_text
    if any(item.event_expression_text != event_expression for item in candidates):
        raise ValueError("Event entity task candidates do not share one Event expression.")
    event_ranges = tuple(
        (match.start(), match.end())
        for match in re.finditer(re.escape(event_expression), source_text)
    )
    if len(event_ranges) != 1:
        raise ValueError("Event entity task requires one exact Event expression occurrence.")
    event_start, event_end = event_ranges[0]
    lines = ["Ordered candidate inventory:"]
    for ordinal, candidate in enumerate(candidates, start=1):
        primary = next(
            item for item in candidate.source_spans if item.id == candidate.primary_source_span_id
        )
        if (
            primary.end > len(source_text)
            or source_text[primary.start : primary.end] != primary.text
        ):
            raise ValueError("Event entity task mention does not match source characters.")
        marked_source = _mark_event_entity_task_source(
            source_text=source_text,
            event_start=event_start,
            event_end=event_end,
            entity_start=primary.start,
            entity_end=primary.end,
        )
        lines.extend(
            (
                f"Candidate {ordinal} source passage as a JSON string:",
                json.dumps(marked_source, ensure_ascii=False),
            )
        )
        if candidate.resolved_antecedent_spans:
            lines.extend(
                (
                    f"Candidate {ordinal} resolved entity name as a JSON string:",
                    json.dumps(candidate.entity_name, ensure_ascii=False),
                )
            )
    lines.append(
        f"Return exactly {len(candidates)} answer characters in Candidate 1 through "
        f"Candidate {len(candidates)} order."
    )
    return ("\n".join(lines) + "\n").encode()


def _mark_event_entity_task_source(
    *,
    source_text: str,
    event_start: int,
    event_end: int,
    entity_start: int,
    entity_end: int,
) -> str:
    if not (
        0 <= event_start < event_end <= len(source_text)
        and 0 <= entity_start < entity_end <= len(source_text)
    ):
        raise ValueError("Event entity task target range is invalid.")
    if event_start < entity_start < event_end < entity_end or (
        entity_start < event_start < entity_end < event_end
    ):
        raise ValueError("Event entity task target ranges cross without containment.")
    if event_start <= entity_start and entity_end <= event_end:
        return (
            source_text[:event_start]
            + "<event>"
            + source_text[event_start:entity_start]
            + "<entity>"
            + source_text[entity_start:entity_end]
            + "</entity>"
            + source_text[entity_end:event_end]
            + "</event>"
            + source_text[event_end:]
        )
    if entity_start <= event_start and event_end <= entity_end:
        return (
            source_text[:entity_start]
            + "<entity>"
            + source_text[entity_start:event_start]
            + "<event>"
            + source_text[event_start:event_end]
            + "</event>"
            + source_text[event_end:entity_end]
            + "</entity>"
            + source_text[entity_end:]
        )
    if event_end <= entity_start:
        return (
            source_text[:event_start]
            + "<event>"
            + source_text[event_start:event_end]
            + "</event>"
            + source_text[event_end:entity_start]
            + "<entity>"
            + source_text[entity_start:entity_end]
            + "</entity>"
            + source_text[entity_end:]
        )
    return (
        source_text[:entity_start]
        + "<entity>"
        + source_text[entity_start:entity_end]
        + "</entity>"
        + source_text[entity_end:event_start]
        + "<event>"
        + source_text[event_start:event_end]
        + "</event>"
        + source_text[event_end:]
    )


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
    return _source_span_from_values(
        source_segment_id=candidate.source_segment_id,
        source_text_sha256=candidate.source_text_sha256,
        start=candidate.start,
        end=candidate.end,
        text=candidate.text,
        mention_candidate_id=candidate.id,
        reference_decision_id=reference_decision_id,
    )


def _source_span_from_values(
    *,
    source_segment_id: str,
    source_text_sha256: str,
    start: int,
    end: int,
    text: str,
    mention_candidate_id: str,
    reference_decision_id: str | None,
) -> EventEntitySourceSpan:
    values = (
        source_segment_id,
        source_text_sha256,
        str(start),
        str(end),
        text,
        mention_candidate_id,
        reference_decision_id or "",
    )
    return EventEntitySourceSpan(
        id=_id("ees", *values),
        source_segment_id=source_segment_id,
        source_text_sha256=source_text_sha256,
        start=start,
        end=end,
        text=text,
        mention_candidate_id=mention_candidate_id,
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


def _record_dependent_gap(
    *,
    gaps: list[EventEntityCandidateGap],
    dependencies: list[EventEntityGapDependency],
    candidate: MentionCandidate,
    reason: EventEntityCandidateGapReason,
    reference: ReferenceDecision | None,
    event: SourceGroundedEventDraft,
    source_text: str,
) -> None:
    gap = _candidate_gap(candidate, reason, reference)
    dependency = _event_gap_dependency(
        gap=gap,
        event=event,
        source_text=source_text,
    )
    if dependency is None:
        return
    gaps.append(gap)
    dependencies.append(dependency)


def _event_gap_dependency(
    *,
    gap: EventEntityCandidateGap,
    event: SourceGroundedEventDraft,
    source_text: str,
) -> EventEntityGapDependency | None:
    expression_ranges = tuple(
        (match.start(), match.end())
        for match in re.finditer(re.escape(event.expression_text), source_text)
    )
    if not expression_ranges:
        raise ValueError("Source-grounded Event expression is absent from its SourceSegment.")
    applicable: list[tuple[int, int, EventEntityGapDependencyRule]] = []
    for start, end in expression_ranges:
        if gap.mention_start < end and start < gap.mention_end:
            applicable.append((start, end, EventEntityGapDependencyRule.EXPRESSION_OVERLAP))
            continue
        between = source_text[gap.mention_end : start] if gap.mention_end <= start else ""
        if (
            gap.mention_text.casefold() in {"her", "his", "its", "their", "whose"}
            and between
            and not between.strip()
        ):
            applicable.append((start, end, EventEntityGapDependencyRule.ADJACENT_POSSESSIVE))
            continue
        after = source_text[end : gap.mention_start] if end <= gap.mention_start else ""
        if gap.mention_text.casefold() in REFERENCE_MARKERS and after and not after.strip():
            applicable.append((start, end, EventEntityGapDependencyRule.ADJACENT_REFERENCE))
    if not applicable:
        return None
    if len(applicable) != 1:
        raise ValueError("Event gap dependency cannot identify one exact Event expression.")
    start, end, rule = applicable[0]
    values = (
        gap.id,
        event.id,
        event.mention.id,
        str(start),
        str(end),
        rule.value,
    )
    return EventEntityGapDependency(
        id=_id("egd", *values),
        gap_id=gap.id,
        source_grounded_event_id=event.id,
        event_mention_id=event.mention.id,
        event_expression_start=start,
        event_expression_end=end,
        rule_id=rule,
    )


def _trim_possessive(value: str) -> str:
    stripped = value.strip()
    for suffix in ("'s", "’s"):
        if stripped.casefold().endswith(suffix):
            return stripped[: -len(suffix)].rstrip()
    return stripped


def _canonical_entity_name(value: str) -> str:
    return re.sub(r"\s+", " ", _trim_possessive(value)).strip()


def _normalized_entity_name(value: str) -> str:
    return _canonical_entity_name(value).casefold()


def _exact_entity_name_pattern(value: str) -> str:
    terms = tuple(item for item in re.split(r"\s+", value.strip()) if item)
    if not terms:
        raise ValueError("Entity name recurrence requires a non-empty name.")
    body = r"\s+".join(re.escape(item) for item in terms)
    return rf"(?<!\w){body}(?!\w)"


def _local_entity_identity(kind: EventEntityKind, name: str) -> str:
    normalized = _normalized_entity_name(name)
    return _id("lei", kind.value, normalized)


def _source_bound_actor_group_identity(source_span: EventEntitySourceSpan) -> str:
    return _id(
        "lei",
        "source_bound_actor_group",
        source_span.source_segment_id,
        source_span.source_text_sha256,
        str(source_span.start),
        str(source_span.end),
        source_span.text,
    )


def _linguistic_sentence_id_for_range(
    tokens: tuple[EventEntityLinguisticToken, ...],
    start: int,
    end: int,
) -> str:
    overlapping = tuple(item for item in tokens if item.start < end and start < item.end)
    if (
        not overlapping
        or min(item.start for item in overlapping) != start
        or max(item.end for item in overlapping) != end
    ):
        raise ValueError("Event entity range does not align with linguistic tokens.")
    sentence_ids = {item.sentence_id for item in overlapping}
    if len(sentence_ids) != 1:
        raise ValueError("Event entity range crosses a linguistic sentence boundary.")
    return next(iter(sentence_ids))


def build_event_entity_connection_preview(**values: object) -> EventEntityConnectionPreview:
    """Construct one content-addressed terminal experiment Preview."""
    payload = dict(values)
    payload.setdefault("schema_version", "event_entity_connection_preview_v5")
    payload.setdefault("policy_id", EVENT_ENTITY_CONNECTION_POLICY_ID)
    if "identity_connections" not in payload:
        candidates = tuple(cast(tuple[EventEntityConnectionCandidate, ...], payload["candidates"]))
        decisions = tuple(cast(tuple[EventEntityConnectionDecision, ...], payload["decisions"]))
        payload["identity_connections"] = consolidate_event_entity_connections(
            candidates,
            decisions,
        )
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
