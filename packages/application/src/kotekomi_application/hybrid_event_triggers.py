"""Source-bound Event trigger contracts and deterministic candidate selection."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from enum import StrEnum
from typing import Annotated, Literal, Self, cast

from kotekomi_domain.models import JsonValue
from pydantic import BaseModel, ConfigDict, Field, model_validator

from kotekomi_application.extraction_stage_trace import (
    ExtractionStageTrace,
    validate_extraction_stage_trace_chain,
)
from kotekomi_application.hybrid_event_trigger_model_output import EventHeadAnswerValue
from kotekomi_application.linguistic_analysis import (
    LinguisticAnalysis,
    LinguisticToken,
    UniversalPartOfSpeech,
)
from kotekomi_application.nominalization_analysis import NominalizationAnalysis
from kotekomi_application.source_occurrences import SourceOccurrence

HYBRID_EVENT_TRIGGER_POLICY_ID = "hybrid_event_trigger_v18"
EVENT_HEAD_CANDIDATE_POLICY_ID = "stanza_verb_qanom_noun_v1"
QANOM_CANDIDATE_THRESHOLD = 0.45
_NON_PREDICATE_VERB_DEPENDENCIES = frozenset({"amod", "case"})
_EXPRESSION_BOUNDARY_PUNCTUATION = frozenset({",", ";", ":", ".", "!", "?"})
_SHA256 = r"^[a-f0-9]{64}$"
_OPEN_LABEL = r"^[a-z][a-z0-9]*(?:_[a-z0-9]+){0,3}$"


class HybridEventTriggerStatus(StrEnum):
    """Terminal status for one trigger Preview."""

    COMPLETE = "complete"
    PARTIAL = "partial"
    BLOCKED = "blocked"


class TriggerDecisionDispositionValue(StrEnum):
    """Deterministic outcome for one source-bound final decision."""

    ACCEPTED = "accepted"
    REJECTED = "rejected"


class EventHeadCandidateDispositionValue(StrEnum):
    """Deterministic inclusion result for one SourceOccurrence."""

    INCLUDED = "included"
    EXCLUDED = "excluded"
    UNMAPPED = "unmapped"


class EventSemanticRoute(StrEnum):
    """One bounded semantic question used by the event-routing policy."""

    VERB_ROLE = "verb_role"
    VERB_SIMILARITY = "verb_similarity"
    NOUN_INVENTORY = "noun_inventory"
    NOUN_DEPENDENT_KIND = "noun_dependent_kind"
    NOUN_MEDIA_ARTIFACT = "noun_media_artifact"
    NOUN_GOVERNOR_DISTINCT = "noun_governor_distinct"
    NOUN_REACTION = "noun_reaction"
    NOUN_STANDING = "noun_standing"


class EventRoutingAnswerValue(StrEnum):
    """Finite model-visible answers, interpreted only with their route."""

    EVENT = "E"
    STANDING = "S"
    HELPER = "H"
    YES = "Y"
    NO = "N"


class EventHeadCandidate(BaseModel):
    """One exact SourceOccurrence selected by the pinned candidate policy."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    occurrence_id: Annotated[str, Field(pattern=r"^o[1-9][0-9]*$")]
    text: Annotated[str, Field(min_length=1)]
    start: Annotated[int, Field(ge=0)]
    end: Annotated[int, Field(gt=0)]
    linguistic_token_id: Annotated[str, Field(pattern=r"^t[1-9][0-9]*$")]
    sentence_id: Annotated[str, Field(pattern=r"^s[1-9][0-9]*$")]
    lemma: Annotated[str, Field(min_length=1)]
    part_of_speech: UniversalPartOfSpeech
    dependency_relation: Annotated[str, Field(min_length=1)]
    dependency_head_token_id: Annotated[str, Field(pattern=r"^t[1-9][0-9]*$")] | None
    lexical_nominalization_candidate: bool | None = None
    nominalization_probability: Annotated[float, Field(ge=0.0, le=1.0)] | None = None

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if self.end <= self.start or self.end - self.start != len(self.text):
            raise ValueError("EventHeadCandidate range does not match its text.")
        if self.part_of_speech not in {
            UniversalPartOfSpeech.NOUN,
            UniversalPartOfSpeech.VERB,
        }:
            raise ValueError("EventHeadCandidate requires a predicate part of speech.")
        has_nominal_evidence = self.lexical_nominalization_candidate is not None
        if has_nominal_evidence != (self.nominalization_probability is not None):
            raise ValueError("EventHeadCandidate nominal evidence must be complete.")
        if (self.part_of_speech is UniversalPartOfSpeech.NOUN) != has_nominal_evidence:
            raise ValueError("Only a noun EventHeadCandidate requires QANom evidence.")
        return self


class EventHeadCandidateDisposition(BaseModel):
    """Auditable candidate-policy result for one SourceOccurrence."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    occurrence_id: Annotated[str, Field(pattern=r"^o[1-9][0-9]*$")]
    disposition: EventHeadCandidateDispositionValue
    reason_code: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]*$")]
    linguistic_token_id: Annotated[str, Field(pattern=r"^t[1-9][0-9]*$")] | None = None
    part_of_speech: UniversalPartOfSpeech | None = None

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        has_annotation = self.linguistic_token_id is not None
        if has_annotation != (self.part_of_speech is not None):
            raise ValueError("Candidate disposition linguistic annotation must be complete.")
        if self.disposition is EventHeadCandidateDispositionValue.UNMAPPED and has_annotation:
            raise ValueError("An unmapped candidate disposition has no linguistic annotation.")
        if (
            self.disposition is not EventHeadCandidateDispositionValue.UNMAPPED
            and not has_annotation
        ):
            raise ValueError("A mapped candidate disposition requires linguistic annotation.")
        return self


class EventHeadCandidateSelection(BaseModel):
    """Complete candidate policy result for one SourceOccurrence catalog."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    policy_id: Literal["stanza_verb_qanom_noun_v1"] = EVENT_HEAD_CANDIDATE_POLICY_ID
    candidates: tuple[EventHeadCandidate, ...]
    dispositions: tuple[EventHeadCandidateDisposition, ...]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        disposition_ids = tuple(item.occurrence_id for item in self.dispositions)
        if len(set(disposition_ids)) != len(disposition_ids):
            raise ValueError("Candidate selection repeats a SourceOccurrence disposition.")
        included_ids = tuple(
            item.occurrence_id
            for item in self.dispositions
            if item.disposition is EventHeadCandidateDispositionValue.INCLUDED
        )
        if tuple(item.occurrence_id for item in self.candidates) != included_ids:
            raise ValueError("Candidate selection does not match its included dispositions.")
        return self


class EventRoutingJudgment(BaseModel):
    """One validated bounded answer bound to KoteKomi-owned source evidence."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    occurrence_id: Annotated[str, Field(pattern=r"^o[1-9][0-9]*$")]
    route: EventSemanticRoute
    answer: EventRoutingAnswerValue
    extraction_task_id: Annotated[str, Field(min_length=1)]
    model_run_id: Annotated[str, Field(min_length=1)]

    @model_validator(mode="after")
    def validate_answer_for_route(self) -> Self:
        if self.route is EventSemanticRoute.VERB_ROLE:
            allowed = {
                EventRoutingAnswerValue.EVENT,
                EventRoutingAnswerValue.STANDING,
                EventRoutingAnswerValue.HELPER,
            }
        elif self.route is EventSemanticRoute.NOUN_INVENTORY:
            allowed = {EventRoutingAnswerValue.EVENT, EventRoutingAnswerValue.NO}
        else:
            allowed = {EventRoutingAnswerValue.YES, EventRoutingAnswerValue.NO}
        if self.answer not in allowed:
            raise ValueError("Event routing answer is invalid for its semantic route.")
        return self


class EventTriggerDecision(BaseModel):
    """One final deterministic Event decision and its primary model lineage."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    occurrence_id: Annotated[str, Field(pattern=r"^o[1-9][0-9]*$")]
    answer: EventHeadAnswerValue
    reason_code: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]*$")]
    extraction_task_id: Annotated[str, Field(min_length=1)]
    model_run_id: Annotated[str, Field(min_length=1)]


class TriggerDecisionDisposition(BaseModel):
    """Auditable reconciliation result for one final Event decision."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    occurrence_id: Annotated[str, Field(pattern=r"^o[1-9][0-9]*$")]
    answer: EventHeadAnswerValue
    disposition: TriggerDecisionDispositionValue
    reason_code: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]*$")]


class EventTriggerDraft(BaseModel):
    """One Event trigger mapped to exact authoritative SourceSegment characters."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: Annotated[str, Field(pattern=r"^etd_[a-f0-9]{24}$")]
    source_segment_id: Annotated[str, Field(min_length=1)]
    source_text_sha256: Annotated[str, Field(pattern=_SHA256)]
    start: Annotated[int, Field(ge=0)]
    end: Annotated[int, Field(gt=0)]
    text: Annotated[str, Field(min_length=1)]
    head_start: Annotated[int, Field(ge=0)]
    head_end: Annotated[int, Field(gt=0)]
    head_text: Annotated[str, Field(min_length=1)]
    event_type_label: Annotated[str, Field(pattern=_OPEN_LABEL)]
    extraction_task_id: Annotated[str, Field(min_length=1)]
    model_run_id: Annotated[str, Field(min_length=1)]
    trace_id: Annotated[str, Field(pattern=r"^xst_[a-f0-9]{24}$")]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if self.end <= self.start or self.end - self.start != len(self.text):
            raise ValueError("EventTriggerDraft range does not match its text.")
        if not (
            self.start <= self.head_start < self.head_end <= self.end
            and self.head_end - self.head_start == len(self.head_text)
        ):
            raise ValueError("EventTriggerDraft head range does not match its expression.")
        relative_head_start = self.head_start - self.start
        relative_head_end = self.head_end - self.start
        if self.text[relative_head_start:relative_head_end] != self.head_text:
            raise ValueError("EventTriggerDraft head text does not match its expression text.")
        expected = event_trigger_id(
            source_segment_id=self.source_segment_id,
            source_text_sha256=self.source_text_sha256,
            start=self.start,
            end=self.end,
            text=self.text,
            head_start=self.head_start,
            head_end=self.head_end,
            head_text=self.head_text,
            event_type_label=self.event_type_label,
            extraction_task_id=self.extraction_task_id,
            model_run_id=self.model_run_id,
            trace_id=self.trace_id,
        )
        if self.id != expected:
            raise ValueError("EventTriggerDraft ID does not match its evidence.")
        return self


class HybridEventTriggerPreview(BaseModel):
    """Immutable derived evidence for one terminal event-trigger run."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["hybrid_event_trigger_preview_v14"] = "hybrid_event_trigger_preview_v14"
    id: Annotated[str, Field(pattern=r"^htp_[a-f0-9]{24}$")]
    parent_preview_id: Annotated[str, Field(pattern=r"^hgp_[a-f0-9]{24}$")]
    parent_preview_sha256: Annotated[str, Field(pattern=_SHA256)]
    reference_preview_id: Annotated[str, Field(pattern=r"^hrp_[a-f0-9]{24}$")]
    reference_preview_sha256: Annotated[str, Field(pattern=_SHA256)]
    mention_preview_id: Annotated[str, Field(pattern=r"^hxp_[a-f0-9]{24}$")]
    mention_preview_sha256: Annotated[str, Field(pattern=_SHA256)]
    representation_id: Annotated[str, Field(min_length=1)]
    paragraph_node_id: Annotated[str, Field(min_length=1)]
    context_manifest_ids: tuple[Annotated[str, Field(min_length=1)], ...]
    policy_id: Literal["hybrid_event_trigger_v18"] = HYBRID_EVENT_TRIGGER_POLICY_ID
    triggers: tuple[EventTriggerDraft, ...] = ()
    extraction_task_ids: tuple[Annotated[str, Field(min_length=1)], ...] = ()
    model_run_ids: tuple[Annotated[str, Field(min_length=1)], ...] = ()
    traces: tuple[ExtractionStageTrace, ...] = ()
    terminal_status: HybridEventTriggerStatus
    diagnostics: tuple[Annotated[str, Field(min_length=1)], ...] = ()

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        for label, values in (
            ("ContextManifest IDs", self.context_manifest_ids),
            ("ExtractionTask IDs", self.extraction_task_ids),
            ("ModelRun IDs", self.model_run_ids),
            ("diagnostics", self.diagnostics),
        ):
            _ordered_distinct(label, values)
        if len({item.id for item in self.triggers}) != len(self.triggers):
            raise ValueError("HybridEventTriggerPreview repeats a trigger.")
        if len(self.extraction_task_ids) != len(self.model_run_ids):
            raise ValueError("Event-trigger task and ModelRun coverage must match.")
        trace_ids = {item.id for item in self.traces}
        if len(trace_ids) != len(self.traces):
            raise ValueError("HybridEventTriggerPreview repeats a trace.")
        if any(item.trace_id not in trace_ids for item in self.triggers):
            raise ValueError("Event trigger trace lineage is missing.")
        execution_ids = set(self.extraction_task_ids) | set(self.model_run_ids)
        traced_execution_ids = {
            item for trace in self.traces for item in trace.execution_record_ids
        }
        if traced_execution_ids != execution_ids:
            raise ValueError("Event-trigger Preview must trace every execution record.")
        traces_by_run: dict[str, list[ExtractionStageTrace]] = defaultdict(list)
        for trace in self.traces:
            traces_by_run[trace.trace_run_id].append(trace)
        for trace_run in traces_by_run.values():
            validate_extraction_stage_trace_chain(tuple(trace_run))
        if self.terminal_status is HybridEventTriggerStatus.PARTIAL and not self.diagnostics:
            raise ValueError("A partial Event-trigger Preview requires a diagnostic.")
        if self.terminal_status is HybridEventTriggerStatus.BLOCKED:
            if self.triggers or not self.diagnostics:
                raise ValueError("A blocked Event-trigger Preview requires only diagnostics.")
        if self.id != _preview_id(self.model_dump(mode="json", exclude={"id"})):
            raise ValueError("HybridEventTriggerPreview ID does not match its contents.")
        return self


def event_trigger_id(
    *,
    source_segment_id: str,
    source_text_sha256: str,
    start: int,
    end: int,
    text: str,
    head_start: int,
    head_end: int,
    head_text: str,
    event_type_label: str,
    extraction_task_id: str,
    model_run_id: str,
    trace_id: str,
) -> str:
    return _id(
        "etd",
        source_segment_id,
        source_text_sha256,
        str(start),
        str(end),
        text,
        str(head_start),
        str(head_end),
        head_text,
        event_type_label,
        extraction_task_id,
        model_run_id,
        trace_id,
    )


def event_trigger_expression_range(
    candidate: EventHeadCandidate,
    source_text: str,
    tokens: tuple[LinguisticToken, ...],
) -> tuple[int, int]:
    """Derive one conservative exact Event expression around a selected head.

    Most selected heads are already complete expressions. A nominal Event head with one
    directly attached marked infinitival clause retains that clause up to the first strong
    punctuation boundary. This preserves source meaning such as ``decision to attend ...``
    while keeping the source-bound Stanza observation fallible and non-authoritative.
    """
    if (
        candidate.end > len(source_text)
        or source_text[candidate.start : candidate.end] != candidate.text
    ):
        raise ValueError("EventHeadCandidate does not match exact SourceCopy characters.")
    token_by_id = {item.token_id: item for item in tokens}
    if len(token_by_id) != len(tokens):
        raise ValueError("LinguisticToken IDs must be distinct for expression mapping.")
    head = token_by_id.get(candidate.linguistic_token_id)
    if (
        head is None
        or head.start != candidate.start
        or head.end != candidate.end
        or head.text != candidate.text
    ):
        raise ValueError("EventHeadCandidate linguistic token does not match its source head.")
    if candidate.part_of_speech is not UniversalPartOfSpeech.NOUN:
        return candidate.start, candidate.end

    direct_clauses = tuple(
        item
        for item in tokens
        if item.sentence_id == head.sentence_id
        and item.head_token_id == head.token_id
        and item.dependency_relation.casefold() == "acl"
        and any(
            marker.sentence_id == head.sentence_id
            and marker.head_token_id == item.token_id
            and marker.dependency_relation.casefold() == "mark"
            and marker.lemma.casefold() == "to"
            for marker in tokens
        )
    )
    if len(direct_clauses) != 1:
        return candidate.start, candidate.end

    clause = direct_clauses[0]
    punctuation_start = next(
        (
            item.start
            for item in tokens
            if item.sentence_id == head.sentence_id
            and item.start > clause.start
            and item.part_of_speech is UniversalPartOfSpeech.PUNCTUATION
            and item.text in _EXPRESSION_BOUNDARY_PUNCTUATION
        ),
        len(source_text),
    )
    descendant_ids = {clause.token_id}
    changed = True
    while changed:
        changed = False
        for item in tokens:
            if (
                item.sentence_id == head.sentence_id
                and item.start < punctuation_start
                and item.head_token_id in descendant_ids
                and item.token_id not in descendant_ids
            ):
                descendant_ids.add(item.token_id)
                changed = True
    expression_end = max(
        (
            item.end
            for item in tokens
            if item.token_id in descendant_ids and item.start < punctuation_start
        ),
        default=candidate.end,
    )
    if expression_end <= candidate.end:
        return candidate.start, candidate.end
    return candidate.start, expression_end


def select_event_head_candidates(
    source_text: str,
    occurrences: tuple[SourceOccurrence, ...],
    analysis: LinguisticAnalysis,
    nominalization_analysis: NominalizationAnalysis,
) -> EventHeadCandidateSelection:
    """Map specialist observations to exact source-owned candidate records."""
    source_digest = hashlib.sha256(source_text.encode()).hexdigest()
    if analysis.source_text_sha256 != source_digest:
        raise ValueError("LinguisticAnalysis source digest does not match the SourceCopy.")
    if nominalization_analysis.source_text_sha256 != source_digest:
        raise ValueError("NominalizationAnalysis source digest does not match the SourceCopy.")
    for token in analysis.tokens:
        if token.end > len(source_text) or source_text[token.start : token.end] != token.text:
            raise ValueError("LinguisticToken does not match exact SourceCopy characters.")
    tokens_by_range = {(item.start, item.end): item for item in analysis.tokens}
    if len(tokens_by_range) != len(analysis.tokens):
        raise ValueError("LinguisticAnalysis repeats one exact source range.")
    nominal_by_token = {
        item.linguistic_token_id: item for item in nominalization_analysis.candidates
    }
    if any(
        token_id not in {item.token_id for item in analysis.tokens} for token_id in nominal_by_token
    ):
        raise ValueError("NominalizationAnalysis references an unknown LinguisticToken.")

    candidates: list[EventHeadCandidate] = []
    dispositions: list[EventHeadCandidateDisposition] = []
    for occurrence in occurrences:
        if (
            occurrence.end > len(source_text)
            or source_text[occurrence.start : occurrence.end] != occurrence.text
        ):
            raise ValueError("SourceOccurrence does not match exact SourceCopy characters.")
        token = tokens_by_range.get((occurrence.start, occurrence.end))
        if token is None:
            dispositions.append(
                EventHeadCandidateDisposition(
                    occurrence_id=occurrence.occurrence_id,
                    disposition=EventHeadCandidateDispositionValue.UNMAPPED,
                    reason_code="linguistic_token_unmapped",
                )
            )
            continue
        include = False
        reason = "non_event_candidate"
        nominal = nominal_by_token.get(token.token_id)
        if token.part_of_speech is UniversalPartOfSpeech.VERB:
            if token.dependency_relation.casefold() in _NON_PREDICATE_VERB_DEPENDENCIES:
                reason = "non_predicate_verb_dependency"
            else:
                include = True
                reason = "stanza_predicate_verb"
        elif token.part_of_speech is UniversalPartOfSpeech.NOUN:
            if nominal is None:
                raise ValueError("QANom omitted a Stanza common noun.")
            if (
                nominal.lexical_candidate
                and nominal.nominalization_probability >= nominalization_analysis.threshold
            ):
                include = True
                reason = "qanom_nominalization_candidate"
            elif not nominal.lexical_candidate:
                reason = "qanom_lexical_filter_excluded"
            else:
                reason = "qanom_probability_below_threshold"
        disposition = (
            EventHeadCandidateDispositionValue.INCLUDED
            if include
            else EventHeadCandidateDispositionValue.EXCLUDED
        )
        dispositions.append(
            EventHeadCandidateDisposition(
                occurrence_id=occurrence.occurrence_id,
                disposition=disposition,
                reason_code=reason,
                linguistic_token_id=token.token_id,
                part_of_speech=token.part_of_speech,
            )
        )
        if include:
            candidates.append(
                EventHeadCandidate(
                    occurrence_id=occurrence.occurrence_id,
                    text=occurrence.text,
                    start=occurrence.start,
                    end=occurrence.end,
                    linguistic_token_id=token.token_id,
                    sentence_id=token.sentence_id,
                    lemma=token.lemma,
                    part_of_speech=token.part_of_speech,
                    dependency_relation=token.dependency_relation,
                    dependency_head_token_id=token.head_token_id,
                    lexical_nominalization_candidate=(
                        nominal.lexical_candidate if nominal is not None else None
                    ),
                    nominalization_probability=(
                        nominal.nominalization_probability if nominal is not None else None
                    ),
                )
            )
    return EventHeadCandidateSelection(
        candidates=tuple(candidates),
        dispositions=tuple(dispositions),
    )


def build_hybrid_event_trigger_preview(**values: object) -> HybridEventTriggerPreview:
    payload = dict(values)
    payload.pop("id", None)
    payload.setdefault("schema_version", "hybrid_event_trigger_preview_v14")
    payload.setdefault("policy_id", HYBRID_EVENT_TRIGGER_POLICY_ID)
    for name in (
        "context_manifest_ids",
        "triggers",
        "extraction_task_ids",
        "model_run_ids",
        "traces",
        "diagnostics",
    ):
        payload.setdefault(name, ())
    payload["triggers"] = [
        item.model_dump(mode="json")
        for item in cast(tuple[EventTriggerDraft, ...], payload["triggers"])
    ]
    payload["traces"] = [
        item.model_dump(mode="json")
        for item in cast(tuple[ExtractionStageTrace, ...], payload["traces"])
    ]
    normalized = cast(dict[str, JsonValue], json.loads(json.dumps(payload)))
    normalized["id"] = _preview_id(normalized)
    return HybridEventTriggerPreview.model_validate_json(_canonical_json(normalized))


def canonical_hybrid_event_trigger_preview_bytes(preview: HybridEventTriggerPreview) -> bytes:
    return _canonical_json(preview.model_dump(mode="json")).encode()


def hybrid_event_trigger_preview_sha256(preview: HybridEventTriggerPreview) -> str:
    return hashlib.sha256(canonical_hybrid_event_trigger_preview_bytes(preview)).hexdigest()


def hybrid_event_trigger_preview_from_bytes(payload: bytes) -> HybridEventTriggerPreview:
    try:
        json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("HybridEventTriggerPreview is not valid JSON.") from error
    preview = HybridEventTriggerPreview.model_validate_json(payload)
    if canonical_hybrid_event_trigger_preview_bytes(preview) != payload:
        raise ValueError("HybridEventTriggerPreview does not use canonical encoding.")
    return preview


def _ordered_distinct(label: str, values: tuple[str, ...]) -> None:
    if len(set(values)) != len(values):
        raise ValueError(f"{label} must be distinct.")
    if values != tuple(sorted(values)):
        raise ValueError(f"{label} must be ordered.")


def _preview_id(payload: dict[str, JsonValue]) -> str:
    return f"htp_{hashlib.sha256(_canonical_json(payload).encode()).hexdigest()[:24]}"


def _id(prefix: str, *parts: str) -> str:
    return f"{prefix}_{hashlib.sha256(chr(31).join(parts).encode()).hexdigest()[:24]}"


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
