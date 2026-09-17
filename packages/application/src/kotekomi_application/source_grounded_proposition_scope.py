"""Source-exact proposition-scope contracts and deterministic construction."""

from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from kotekomi_application.event_entity_connections import (
    EventEntityConnectionCandidate,
    EventEntityLinguisticEvidence,
    EventEntityLinguisticToken,
)
from kotekomi_application.hybrid_event_semantics import SourceGroundedEventDraft
from kotekomi_application.hybrid_event_triggers import EventTriggerDraft

_ID = r"^[a-z]+_[a-f0-9]{24}$"
_SHA256 = r"^[a-f0-9]{64}$"


class PropositionFragmentReason(StrEnum):
    """Deterministic evidence that proposed one exact source fragment."""

    EVENT_EXPRESSION = "event_expression"
    ENTITY_OCCURRENCE = "entity_occurrence"
    PREDICATE_DEPENDENT = "predicate_dependent"
    GOVERNING_CONTEXT = "governing_context"
    CLAUSE_LOCAL_CONSTITUENT = "clause_local_constituent"


class PropositionFragmentRoute(StrEnum):
    """Owner of one proposition-fragment membership decision."""

    DETERMINISTIC_REQUIRED = "deterministic_required"
    MODEL_JUDGMENT = "model_judgment"


class PropositionFragmentDisposition(StrEnum):
    """Terminal treatment of one proposition Fragment Candidate."""

    INCLUDED = "included"
    EXCLUDED = "excluded"
    UNRESOLVED = "unresolved"


class PropositionScopeStatus(StrEnum):
    """Terminal state of one Source-Grounded Proposition Scope."""

    COMPLETE = "complete"
    PARTIAL = "partial"


class PropositionFragmentTaskInputStatus(StrEnum):
    """Whether one exact occurrence can be named without inline source markers."""

    READY = "ready"
    OCCURRENCE_AMBIGUOUS = "occurrence_ambiguous"


class PropositionFragmentTaskInput(BaseModel):
    """Typed model-visible input for one proposition-fragment judgment."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["proposition_fragment_task_input_v1"] = (
        "proposition_fragment_task_input_v1"
    )
    candidate_id: Annotated[str, Field(pattern=r"^pfc_[a-f0-9]{24}$")]
    source_text_sha256: Annotated[str, Field(pattern=_SHA256)]
    status: PropositionFragmentTaskInputStatus
    event_occurrence_count: Annotated[int, Field(ge=1)]
    candidate_occurrence_count: Annotated[int, Field(ge=1)]
    rendered_input: str | None
    rendered_input_sha256: Annotated[str, Field(pattern=_SHA256)] | None
    reason_code: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]*$")] | None

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        unique = self.event_occurrence_count == 1 and self.candidate_occurrence_count == 1
        if self.status is PropositionFragmentTaskInputStatus.READY:
            if not unique or self.rendered_input is None or self.rendered_input_sha256 is None:
                raise ValueError(
                    "A ready proposition task input requires unique exact occurrences."
                )
            if self.reason_code is not None:
                raise ValueError("A ready proposition task input cannot have a failure reason.")
            if (
                hashlib.sha256(self.rendered_input.encode()).hexdigest()
                != self.rendered_input_sha256
            ):
                raise ValueError("Proposition task input digest does not match its rendered text.")
        else:
            if unique:
                raise ValueError("An ambiguous proposition task input requires repeated text.")
            if self.rendered_input is not None or self.rendered_input_sha256 is not None:
                raise ValueError("An ambiguous proposition task input cannot render model input.")
            if self.reason_code is None:
                raise ValueError("An ambiguous proposition task input requires a reason code.")
        return self


class PropositionFragmentCandidate(BaseModel):
    """One exact source range offered for proposition membership judgment."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: Annotated[str, Field(pattern=r"^pfc_[a-f0-9]{24}$")]
    source_grounded_event_id: Annotated[str, Field(pattern=r"^sge_[a-f0-9]{24}$")]
    event_trigger_id: Annotated[str, Field(pattern=_ID)]
    source_segment_id: Annotated[str, Field(min_length=1)]
    source_text_sha256: Annotated[str, Field(pattern=_SHA256)]
    start: Annotated[int, Field(ge=0)]
    end: Annotated[int, Field(gt=0)]
    text: Annotated[str, Field(min_length=1)]
    reasons: tuple[PropositionFragmentReason, ...]
    linguistic_token_ids: tuple[Annotated[str, Field(pattern=r"^t[1-9][0-9]*$")], ...]
    source_record_ids: tuple[Annotated[str, Field(min_length=1)], ...]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if self.end - self.start != len(self.text):
            raise ValueError("Proposition Fragment Candidate range does not match its text.")
        if self.reasons != tuple(sorted(set(self.reasons), key=lambda item: item.value)):
            raise ValueError("Proposition Fragment Candidate reasons must be ordered and distinct.")
        if not self.reasons:
            raise ValueError("Proposition Fragment Candidate requires one proposal reason.")
        _ordered_distinct("Fragment Candidate linguistic tokens", self.linguistic_token_ids)
        _ordered_distinct("Fragment Candidate source records", self.source_record_ids)
        expected = proposition_fragment_candidate_id(
            source_grounded_event_id=self.source_grounded_event_id,
            event_trigger_id=self.event_trigger_id,
            source_segment_id=self.source_segment_id,
            source_text_sha256=self.source_text_sha256,
            start=self.start,
            end=self.end,
            text=self.text,
            reasons=self.reasons,
            linguistic_token_ids=self.linguistic_token_ids,
            source_record_ids=self.source_record_ids,
        )
        if self.id != expected:
            raise ValueError("Proposition Fragment Candidate ID does not match its evidence.")
        return self


class PropositionFragmentDecision(BaseModel):
    """One deterministic disposition for one Fragment Candidate."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: Annotated[str, Field(pattern=r"^pfd_[a-f0-9]{24}$")]
    candidate_id: Annotated[str, Field(pattern=r"^pfc_[a-f0-9]{24}$")]
    route: PropositionFragmentRoute
    disposition: PropositionFragmentDisposition
    reason_code: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]*$")]
    extraction_task_id: Annotated[str, Field(min_length=1)] | None = None
    model_run_id: Annotated[str, Field(min_length=1)] | None = None
    trace_id: Annotated[str, Field(pattern=r"^xst_[a-f0-9]{24}$")] | None = None

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        execution_values = (self.extraction_task_id, self.model_run_id, self.trace_id)
        if self.route is PropositionFragmentRoute.DETERMINISTIC_REQUIRED:
            if self.disposition is not PropositionFragmentDisposition.INCLUDED:
                raise ValueError("A required proposition fragment must be included.")
            if any(value is not None for value in execution_values):
                raise ValueError("A deterministic proposition decision cannot name model evidence.")
        elif any(value is None for value in execution_values):
            raise ValueError("A model proposition decision requires complete execution lineage.")
        expected = proposition_fragment_decision_id(
            candidate_id=self.candidate_id,
            route=self.route,
            disposition=self.disposition,
            reason_code=self.reason_code,
            extraction_task_id=self.extraction_task_id,
            model_run_id=self.model_run_id,
            trace_id=self.trace_id,
        )
        if self.id != expected:
            raise ValueError("Proposition Fragment Decision ID does not match its evidence.")
        return self


class SourceGroundedPropositionFragment(BaseModel):
    """One selected exact range in a Source-Grounded Proposition Scope."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: Annotated[str, Field(pattern=r"^spf_[a-f0-9]{24}$")]
    source_segment_id: Annotated[str, Field(min_length=1)]
    source_text_sha256: Annotated[str, Field(pattern=_SHA256)]
    start: Annotated[int, Field(ge=0)]
    end: Annotated[int, Field(gt=0)]
    text: Annotated[str, Field(min_length=1)]
    contributing_candidate_ids: tuple[Annotated[str, Field(pattern=r"^pfc_[a-f0-9]{24}$")], ...]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if self.end - self.start != len(self.text):
            raise ValueError("Source-Grounded Proposition Fragment range does not match its text.")
        _ordered_distinct(
            "Proposition Fragment contributing candidates",
            self.contributing_candidate_ids,
        )
        if not self.contributing_candidate_ids:
            raise ValueError("Source-Grounded Proposition Fragment requires candidate evidence.")
        expected = source_grounded_proposition_fragment_id(
            source_segment_id=self.source_segment_id,
            source_text_sha256=self.source_text_sha256,
            start=self.start,
            end=self.end,
            text=self.text,
            contributing_candidate_ids=self.contributing_candidate_ids,
        )
        if self.id != expected:
            raise ValueError("Source-Grounded Proposition Fragment ID drifted from its evidence.")
        return self


class SourceGroundedPropositionScope(BaseModel):
    """Complete selected exact source meaning for one Event."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["source_grounded_proposition_scope_v1"] = (
        "source_grounded_proposition_scope_v1"
    )
    id: Annotated[str, Field(pattern=r"^sgp_[a-f0-9]{24}$")]
    source_grounded_event_id: Annotated[str, Field(pattern=r"^sge_[a-f0-9]{24}$")]
    event_trigger_id: Annotated[str, Field(pattern=_ID)]
    source_segment_id: Annotated[str, Field(min_length=1)]
    source_text_sha256: Annotated[str, Field(pattern=_SHA256)]
    candidate_ids: tuple[Annotated[str, Field(pattern=r"^pfc_[a-f0-9]{24}$")], ...]
    decision_ids: tuple[Annotated[str, Field(pattern=r"^pfd_[a-f0-9]{24}$")], ...]
    fragments: tuple[SourceGroundedPropositionFragment, ...]
    unresolved_candidate_ids: tuple[Annotated[str, Field(pattern=r"^pfc_[a-f0-9]{24}$")], ...]
    status: PropositionScopeStatus

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        _ordered_distinct("Proposition Scope candidates", self.candidate_ids)
        _ordered_distinct("Proposition Scope decisions", self.decision_ids)
        _ordered_distinct("Proposition Scope unresolved candidates", self.unresolved_candidate_ids)
        if len(self.candidate_ids) != len(self.decision_ids):
            raise ValueError("Proposition Scope requires one decision per candidate.")
        if tuple(sorted(self.fragments, key=lambda item: (item.start, item.end))) != self.fragments:
            raise ValueError("Proposition Scope fragments must use source order.")
        if any(
            previous.end > current.start
            for previous, current in zip(self.fragments, self.fragments[1:], strict=False)
        ):
            raise ValueError("Proposition Scope fragments must not overlap.")
        expected_status = (
            PropositionScopeStatus.PARTIAL
            if self.unresolved_candidate_ids
            else PropositionScopeStatus.COMPLETE
        )
        if self.status is not expected_status:
            raise ValueError("Proposition Scope status drifted from unresolved candidates.")
        expected = source_grounded_proposition_scope_id(
            source_grounded_event_id=self.source_grounded_event_id,
            event_trigger_id=self.event_trigger_id,
            source_segment_id=self.source_segment_id,
            source_text_sha256=self.source_text_sha256,
            candidate_ids=self.candidate_ids,
            decision_ids=self.decision_ids,
            fragment_ids=tuple(item.id for item in self.fragments),
            unresolved_candidate_ids=self.unresolved_candidate_ids,
            status=self.status,
        )
        if self.id != expected:
            raise ValueError("Source-Grounded Proposition Scope ID drifted from its evidence.")
        return self


def build_proposition_fragment_candidates(
    *,
    source_text: str,
    trigger: EventTriggerDraft,
    event: SourceGroundedEventDraft,
    linguistic_evidence: EventEntityLinguisticEvidence,
    entity_candidates: tuple[EventEntityConnectionCandidate, ...],
) -> tuple[PropositionFragmentCandidate, ...]:
    """Build exact phrase candidates without deciding proposition membership."""
    source_digest = hashlib.sha256(source_text.encode()).hexdigest()
    _validate_inputs(
        source_text=source_text,
        source_digest=source_digest,
        trigger=trigger,
        event=event,
        linguistic_evidence=linguistic_evidence,
        entity_candidates=entity_candidates,
    )
    tokens = linguistic_evidence.tokens
    token_by_id = {item.token_id: item for item in tokens}
    children: dict[str, list[EventEntityLinguisticToken]] = defaultdict(list)
    for token in tokens:
        if token.head_token_id is not None:
            children[token.head_token_id].append(token)
    head_matches = tuple(
        token
        for token in tokens
        if token.start == trigger.head_start and token.end == trigger.head_end
    )
    if len(head_matches) != 1:
        raise ValueError("Proposition candidate construction requires one exact Event head token.")
    head = head_matches[0]
    proposal_reasons: dict[tuple[int, int, str], set[PropositionFragmentReason]] = {}
    proposal_tokens: dict[tuple[int, int, str], set[str]] = {}
    proposal_records: dict[tuple[int, int, str], set[str]] = {}
    citation_token_ids = _citation_token_ids(source_text, tokens)

    def propose(
        start: int,
        end: int,
        reason: PropositionFragmentReason,
        token_ids: tuple[str, ...],
        record_ids: tuple[str, ...],
    ) -> None:
        if start < 0 or end > len(source_text) or start >= end:
            raise ValueError("Proposition candidate range leaves its SourceSegment.")
        text = source_text[start:end]
        if not text.strip():
            return
        key = (start, end, text)
        proposal_reasons.setdefault(key, set()).add(reason)
        proposal_tokens.setdefault(key, set()).update(token_ids)
        proposal_records.setdefault(key, set()).update(record_ids)

    def propose_subtree(
        root: EventEntityLinguisticToken,
        reason: PropositionFragmentReason,
        record_ids: tuple[str, ...],
    ) -> None:
        subtree = _subtree_tokens(root, children, sentence_id=head.sentence_id)
        propose(
            min(item.start for item in subtree),
            max(item.end for item in subtree),
            reason,
            tuple(item.token_id for item in subtree),
            record_ids,
        )
        full_range = (
            min(item.start for item in subtree),
            max(item.end for item in subtree),
        )
        for group in _clause_local_constituents(
            root,
            children,
            source_text=source_text,
            sentence_id=head.sentence_id,
            citation_token_ids=citation_token_ids,
        ):
            group_range = (
                min(item.start for item in group),
                max(item.end for item in group),
            )
            if group_range == full_range:
                continue
            propose(
                *group_range,
                PropositionFragmentReason.CLAUSE_LOCAL_CONSTITUENT,
                tuple(item.token_id for item in group),
                record_ids,
            )

    expression_tokens = _tokens_overlapping(tokens, trigger.start, trigger.end)
    propose(
        trigger.start,
        trigger.end,
        PropositionFragmentReason.EVENT_EXPRESSION,
        tuple(item.token_id for item in expression_tokens),
        (trigger.id, event.id),
    )
    for candidate in entity_candidates:
        primary = next(
            item for item in candidate.source_spans if item.id == candidate.primary_source_span_id
        )
        span_tokens = _tokens_overlapping(tokens, primary.start, primary.end)
        if not span_tokens or {item.sentence_id for item in span_tokens} != {head.sentence_id}:
            continue
        propose(
            primary.start,
            primary.end,
            PropositionFragmentReason.ENTITY_OCCURRENCE,
            tuple(item.token_id for item in span_tokens),
            (candidate.id, primary.id),
        )
    for child in children.get(head.token_id, ()):
        if child.sentence_id != head.sentence_id or child.dependency_relation == "punct":
            continue
        propose_subtree(
            child,
            PropositionFragmentReason.PREDICATE_DEPENDENT,
            (linguistic_evidence.trace_id,),
        )
    child_on_path = head
    while child_on_path.head_token_id is not None:
        parent = token_by_id[child_on_path.head_token_id]
        if parent.sentence_id != head.sentence_id:
            break
        propose(
            parent.start,
            parent.end,
            PropositionFragmentReason.GOVERNING_CONTEXT,
            (parent.token_id,),
            (linguistic_evidence.trace_id,),
        )
        for sibling in children.get(parent.token_id, ()):
            if (
                sibling.token_id == child_on_path.token_id
                or sibling.sentence_id != head.sentence_id
                or sibling.dependency_relation == "punct"
            ):
                continue
            propose_subtree(
                sibling,
                PropositionFragmentReason.GOVERNING_CONTEXT,
                (linguistic_evidence.trace_id,),
            )
        child_on_path = parent

    candidates: list[PropositionFragmentCandidate] = []
    for start, end, text in proposal_reasons:
        key = (start, end, text)
        reasons = tuple(sorted(proposal_reasons[key], key=lambda item: item.value))
        token_ids = tuple(sorted(proposal_tokens[key]))
        record_ids = tuple(sorted(proposal_records[key]))
        if (
            PropositionFragmentReason.EVENT_EXPRESSION not in reasons
            and start < trigger.end
            and trigger.start < end
        ):
            continue
        candidate_id = proposition_fragment_candidate_id(
            source_grounded_event_id=event.id,
            event_trigger_id=trigger.id,
            source_segment_id=event.source_segment_id,
            source_text_sha256=source_digest,
            start=start,
            end=end,
            text=text,
            reasons=reasons,
            linguistic_token_ids=token_ids,
            source_record_ids=record_ids,
        )
        candidates.append(
            PropositionFragmentCandidate(
                id=candidate_id,
                source_grounded_event_id=event.id,
                event_trigger_id=trigger.id,
                source_segment_id=event.source_segment_id,
                source_text_sha256=source_digest,
                start=start,
                end=end,
                text=text,
                reasons=reasons,
                linguistic_token_ids=token_ids,
                source_record_ids=record_ids,
            )
        )
    return tuple(sorted(candidates, key=lambda item: (item.start, item.end, item.id)))


def build_proposition_fragment_decision(
    *,
    candidate: PropositionFragmentCandidate,
    route: PropositionFragmentRoute,
    disposition: PropositionFragmentDisposition,
    reason_code: str,
    extraction_task_id: str | None = None,
    model_run_id: str | None = None,
    trace_id: str | None = None,
) -> PropositionFragmentDecision:
    """Construct one deterministic source-fragment decision."""
    return PropositionFragmentDecision(
        id=proposition_fragment_decision_id(
            candidate_id=candidate.id,
            route=route,
            disposition=disposition,
            reason_code=reason_code,
            extraction_task_id=extraction_task_id,
            model_run_id=model_run_id,
            trace_id=trace_id,
        ),
        candidate_id=candidate.id,
        route=route,
        disposition=disposition,
        reason_code=reason_code,
        extraction_task_id=extraction_task_id,
        model_run_id=model_run_id,
        trace_id=trace_id,
    )


def proposition_fragment_model_task_input(
    *,
    source_text: str,
    trigger: EventTriggerDraft,
    candidate: PropositionFragmentCandidate,
) -> bytes:
    """Render one exact candidate without exposing IDs or character offsets."""
    _validate_proposition_model_task_evidence(source_text, trigger, candidate)
    markers = (
        (trigger.start, "<event>"),
        (trigger.end, "</event>"),
        (candidate.start, "<candidate>"),
        (candidate.end, "</candidate>"),
    )
    rendered = source_text
    for position, marker in sorted(markers, key=lambda item: item[0], reverse=True):
        rendered = rendered[:position] + marker + rendered[position:]
    return (
        "SourceSegment with one Event expression and one candidate fragment marked:\n"
        f"<source>{rendered}</source>\n"
    ).encode()


def marker_free_proposition_fragment_model_task_input(
    *,
    source_text: str,
    trigger: EventTriggerDraft,
    candidate: PropositionFragmentCandidate,
) -> PropositionFragmentTaskInput:
    """Render an unmodified passage only when literal labels identify unique occurrences."""
    source_digest = _validate_proposition_model_task_evidence(source_text, trigger, candidate)
    event_occurrences = _literal_occurrence_count(source_text, trigger.text)
    candidate_occurrences = _literal_occurrence_count(source_text, candidate.text)
    if event_occurrences != 1 or candidate_occurrences != 1:
        if event_occurrences != 1 and candidate_occurrences != 1:
            reason_code = "event_and_candidate_occurrence_ambiguous"
        elif event_occurrences != 1:
            reason_code = "event_occurrence_ambiguous"
        else:
            reason_code = "candidate_occurrence_ambiguous"
        return PropositionFragmentTaskInput(
            candidate_id=candidate.id,
            source_text_sha256=source_digest,
            status=PropositionFragmentTaskInputStatus.OCCURRENCE_AMBIGUOUS,
            event_occurrence_count=event_occurrences,
            candidate_occurrence_count=candidate_occurrences,
            rendered_input=None,
            rendered_input_sha256=None,
            reason_code=reason_code,
        )
    rendered = (
        f"Passage:\n{source_text}\n\nEvent:\n{trigger.text}\n\nCandidate:\n{candidate.text}\n"
    )
    return PropositionFragmentTaskInput(
        candidate_id=candidate.id,
        source_text_sha256=source_digest,
        status=PropositionFragmentTaskInputStatus.READY,
        event_occurrence_count=event_occurrences,
        candidate_occurrence_count=candidate_occurrences,
        rendered_input=rendered,
        rendered_input_sha256=hashlib.sha256(rendered.encode()).hexdigest(),
        reason_code=None,
    )


def build_source_grounded_proposition_scope(
    *,
    source_text: str,
    event: SourceGroundedEventDraft,
    trigger: EventTriggerDraft,
    candidates: tuple[PropositionFragmentCandidate, ...],
    decisions: tuple[PropositionFragmentDecision, ...],
) -> SourceGroundedPropositionScope:
    """Merge included exact candidates into one auditable proposition scope."""
    source_digest = hashlib.sha256(source_text.encode()).hexdigest()
    if source_digest != event.source_text_sha256:
        raise ValueError("Proposition Scope source digest does not match its Event.")
    candidate_by_id = {item.id: item for item in candidates}
    decision_by_candidate = {item.candidate_id: item for item in decisions}
    if len(candidate_by_id) != len(candidates):
        raise ValueError("Proposition Scope repeats one Fragment Candidate.")
    if len(decision_by_candidate) != len(decisions) or set(decision_by_candidate) != set(
        candidate_by_id
    ):
        raise ValueError("Proposition Scope requires one decision per Fragment Candidate.")
    if any(
        item.source_grounded_event_id != event.id
        or item.event_trigger_id != trigger.id
        or item.source_segment_id != event.source_segment_id
        or item.source_text_sha256 != source_digest
        or source_text[item.start : item.end] != item.text
        for item in candidates
    ):
        raise ValueError("Proposition Scope candidate evidence does not match its source.")
    expression_candidates = tuple(
        item for item in candidates if PropositionFragmentReason.EVENT_EXPRESSION in item.reasons
    )
    if len(expression_candidates) != 1:
        raise ValueError("Proposition Scope requires one Event expression candidate.")
    expression_decision = decision_by_candidate[expression_candidates[0].id]
    if (
        expression_decision.route is not PropositionFragmentRoute.DETERMINISTIC_REQUIRED
        or expression_decision.disposition is not PropositionFragmentDisposition.INCLUDED
    ):
        raise ValueError("Proposition Scope must include its Event expression deterministically.")
    included = tuple(
        candidate_by_id[item.candidate_id]
        for item in decisions
        if item.disposition is PropositionFragmentDisposition.INCLUDED
    )
    fragments = _merge_included_candidates(source_text, included)
    unresolved = tuple(
        sorted(
            item.candidate_id
            for item in decisions
            if item.disposition is PropositionFragmentDisposition.UNRESOLVED
        )
    )
    status = PropositionScopeStatus.PARTIAL if unresolved else PropositionScopeStatus.COMPLETE
    candidate_ids = tuple(sorted(candidate_by_id))
    decision_ids = tuple(sorted(item.id for item in decisions))
    scope_id = source_grounded_proposition_scope_id(
        source_grounded_event_id=event.id,
        event_trigger_id=trigger.id,
        source_segment_id=event.source_segment_id,
        source_text_sha256=source_digest,
        candidate_ids=candidate_ids,
        decision_ids=decision_ids,
        fragment_ids=tuple(item.id for item in fragments),
        unresolved_candidate_ids=unresolved,
        status=status,
    )
    return SourceGroundedPropositionScope(
        id=scope_id,
        source_grounded_event_id=event.id,
        event_trigger_id=trigger.id,
        source_segment_id=event.source_segment_id,
        source_text_sha256=source_digest,
        candidate_ids=candidate_ids,
        decision_ids=decision_ids,
        fragments=fragments,
        unresolved_candidate_ids=unresolved,
        status=status,
    )


def proposition_fragment_candidate_id(
    *,
    source_grounded_event_id: str,
    event_trigger_id: str,
    source_segment_id: str,
    source_text_sha256: str,
    start: int,
    end: int,
    text: str,
    reasons: tuple[PropositionFragmentReason, ...],
    linguistic_token_ids: tuple[str, ...],
    source_record_ids: tuple[str, ...],
) -> str:
    return _id(
        "pfc",
        source_grounded_event_id,
        event_trigger_id,
        source_segment_id,
        source_text_sha256,
        str(start),
        str(end),
        text,
        *(item.value for item in reasons),
        *linguistic_token_ids,
        *source_record_ids,
    )


def proposition_fragment_decision_id(
    *,
    candidate_id: str,
    route: PropositionFragmentRoute,
    disposition: PropositionFragmentDisposition,
    reason_code: str,
    extraction_task_id: str | None,
    model_run_id: str | None,
    trace_id: str | None,
) -> str:
    return _id(
        "pfd",
        candidate_id,
        route.value,
        disposition.value,
        reason_code,
        extraction_task_id or "",
        model_run_id or "",
        trace_id or "",
    )


def source_grounded_proposition_fragment_id(
    *,
    source_segment_id: str,
    source_text_sha256: str,
    start: int,
    end: int,
    text: str,
    contributing_candidate_ids: tuple[str, ...],
) -> str:
    return _id(
        "spf",
        source_segment_id,
        source_text_sha256,
        str(start),
        str(end),
        text,
        *contributing_candidate_ids,
    )


def source_grounded_proposition_scope_id(
    *,
    source_grounded_event_id: str,
    event_trigger_id: str,
    source_segment_id: str,
    source_text_sha256: str,
    candidate_ids: tuple[str, ...],
    decision_ids: tuple[str, ...],
    fragment_ids: tuple[str, ...],
    unresolved_candidate_ids: tuple[str, ...],
    status: PropositionScopeStatus,
) -> str:
    return _id(
        "sgp",
        source_grounded_event_id,
        event_trigger_id,
        source_segment_id,
        source_text_sha256,
        status.value,
        *candidate_ids,
        *decision_ids,
        *fragment_ids,
        *unresolved_candidate_ids,
    )


def _validate_inputs(
    *,
    source_text: str,
    source_digest: str,
    trigger: EventTriggerDraft,
    event: SourceGroundedEventDraft,
    linguistic_evidence: EventEntityLinguisticEvidence,
    entity_candidates: tuple[EventEntityConnectionCandidate, ...],
) -> None:
    if source_digest != event.source_text_sha256:
        raise ValueError("Proposition candidate source digest does not match its Event.")
    if (
        trigger.id != event.trigger_id
        or trigger.source_segment_id != event.source_segment_id
        or trigger.source_text_sha256 != source_digest
        or source_text[trigger.start : trigger.end] != trigger.text
        or source_text[trigger.head_start : trigger.head_end] != trigger.head_text
    ):
        raise ValueError("Proposition candidate trigger does not match its Event source.")
    if (
        linguistic_evidence.source_segment_id != event.source_segment_id
        or linguistic_evidence.source_text_sha256 != source_digest
        or any(
            item.end > len(source_text) or source_text[item.start : item.end] != item.text
            for item in linguistic_evidence.tokens
        )
    ):
        raise ValueError("Proposition candidate linguistic evidence does not replay its source.")
    if any(
        item.source_grounded_event_id != event.id
        or item.source_segment_id != event.source_segment_id
        or item.source_text_sha256 != source_digest
        for item in entity_candidates
    ):
        raise ValueError("Proposition entity candidate belongs to another Event or source.")


def _validate_proposition_model_task_evidence(
    source_text: str,
    trigger: EventTriggerDraft,
    candidate: PropositionFragmentCandidate,
) -> str:
    source_digest = hashlib.sha256(source_text.encode()).hexdigest()
    if (
        candidate.event_trigger_id != trigger.id
        or candidate.source_segment_id != trigger.source_segment_id
        or candidate.source_text_sha256 != source_digest
        or trigger.source_text_sha256 != source_digest
        or source_text[candidate.start : candidate.end] != candidate.text
        or source_text[trigger.start : trigger.end] != trigger.text
    ):
        raise ValueError("Proposition model task evidence does not replay its source.")
    if candidate.start < trigger.end and trigger.start < candidate.end:
        raise ValueError(
            "A model-routed proposition candidate cannot overlap its Event expression."
        )
    return source_digest


def _literal_occurrence_count(source_text: str, literal: str) -> int:
    count = 0
    offset = 0
    while True:
        found = source_text.find(literal, offset)
        if found < 0:
            return count
        count += 1
        offset = found + 1


def _tokens_overlapping(
    tokens: tuple[EventEntityLinguisticToken, ...],
    start: int,
    end: int,
) -> tuple[EventEntityLinguisticToken, ...]:
    return tuple(item for item in tokens if item.start < end and start < item.end)


def _subtree_tokens(
    root: EventEntityLinguisticToken,
    children: dict[str, list[EventEntityLinguisticToken]],
    *,
    sentence_id: str,
) -> tuple[EventEntityLinguisticToken, ...]:
    found: dict[str, EventEntityLinguisticToken] = {}
    pending = [root]
    while pending:
        token = pending.pop()
        if token.token_id in found or token.sentence_id != sentence_id:
            continue
        found[token.token_id] = token
        pending.extend(children.get(token.token_id, ()))
    return tuple(sorted(found.values(), key=lambda item: (item.start, item.end)))


_DETACHED_CLAUSE_RELATIONS = frozenset({"acl", "acl:relcl", "advcl", "parataxis"})


def _citation_token_ids(
    source_text: str,
    tokens: tuple[EventEntityLinguisticToken, ...],
) -> frozenset[str]:
    ranges = tuple(
        (match.start(), match.end()) for match in re.finditer(r"\[[0-9]+\]", source_text)
    )
    return frozenset(
        token.token_id
        for token in tokens
        if any(start <= token.start and token.end <= end for start, end in ranges)
    )


def _clause_local_constituents(
    root: EventEntityLinguisticToken,
    children: dict[str, list[EventEntityLinguisticToken]],
    *,
    source_text: str,
    sentence_id: str,
    citation_token_ids: frozenset[str],
) -> tuple[tuple[EventEntityLinguisticToken, ...], ...]:
    subtree = _subtree_tokens(root, children, sentence_id=sentence_id)
    detached = _detached_modifier_roots(
        root,
        subtree,
        children,
        source_text=source_text,
    )
    groups = list(
        _contiguous_token_groups(
            source_text,
            _pruned_subtree_tokens(
                root,
                children,
                sentence_id=sentence_id,
                blocked_token_ids=frozenset(item.token_id for item in detached)
                | citation_token_ids,
            ),
        )
    )
    for boundary in detached:
        for child in children.get(boundary.token_id, ()):
            if child.sentence_id != sentence_id or child.dependency_relation == "punct":
                continue
            nested_detached = _detached_modifier_roots(
                child,
                _subtree_tokens(child, children, sentence_id=sentence_id),
                children,
                source_text=source_text,
            )
            groups.extend(
                _contiguous_token_groups(
                    source_text,
                    _pruned_subtree_tokens(
                        child,
                        children,
                        sentence_id=sentence_id,
                        blocked_token_ids=frozenset(item.token_id for item in nested_detached)
                        | citation_token_ids,
                    ),
                )
            )
    distinct: dict[tuple[int, int], tuple[EventEntityLinguisticToken, ...]] = {}
    for group in groups:
        bounded = _trim_leading_constituent_separator(group)
        if bounded:
            distinct[(bounded[0].start, bounded[-1].end)] = bounded
    return tuple(distinct[key] for key in sorted(distinct))


def _trim_leading_constituent_separator(
    tokens: tuple[EventEntityLinguisticToken, ...],
) -> tuple[EventEntityLinguisticToken, ...]:
    first = 0
    while (
        first < len(tokens)
        and tokens[first].part_of_speech == "PUNCT"
        and tokens[first].text in {",", ";", ":"}
    ):
        first += 1
    return tokens[first:]


def _detached_modifier_roots(
    root: EventEntityLinguisticToken,
    subtree: tuple[EventEntityLinguisticToken, ...],
    children: dict[str, list[EventEntityLinguisticToken]],
    *,
    source_text: str,
) -> tuple[EventEntityLinguisticToken, ...]:
    subtree_ids = {item.token_id for item in subtree}
    detached: list[EventEntityLinguisticToken] = []
    for token in subtree:
        if token.token_id == root.token_id:
            continue
        clause_child = any(
            child.token_id in subtree_ids and child.dependency_relation == "acl:relcl"
            for child in children.get(token.token_id, ())
        )
        preceded_by_comma = source_text[: token.start].rstrip().endswith(",")
        if token.dependency_relation in _DETACHED_CLAUSE_RELATIONS or (
            clause_child and preceded_by_comma
        ):
            detached.append(token)
    detached_ids = {item.token_id for item in detached}
    return tuple(item for item in detached if item.head_token_id not in detached_ids)


def _pruned_subtree_tokens(
    root: EventEntityLinguisticToken,
    children: dict[str, list[EventEntityLinguisticToken]],
    *,
    sentence_id: str,
    blocked_token_ids: frozenset[str],
) -> tuple[EventEntityLinguisticToken, ...]:
    found: dict[str, EventEntityLinguisticToken] = {}
    pending = [root]
    while pending:
        token = pending.pop()
        if (
            token.token_id in found
            or token.sentence_id != sentence_id
            or token.token_id in blocked_token_ids
        ):
            continue
        found[token.token_id] = token
        pending.extend(children.get(token.token_id, ()))
    return tuple(sorted(found.values(), key=lambda item: (item.start, item.end)))


def _contiguous_token_groups(
    source_text: str,
    tokens: tuple[EventEntityLinguisticToken, ...],
) -> tuple[tuple[EventEntityLinguisticToken, ...], ...]:
    groups: list[list[EventEntityLinguisticToken]] = []
    for token in tokens:
        if not groups or source_text[groups[-1][-1].end : token.start].strip():
            groups.append([token])
        else:
            groups[-1].append(token)
    return tuple(tuple(group) for group in groups)


def _merge_included_candidates(
    source_text: str,
    candidates: tuple[PropositionFragmentCandidate, ...],
) -> tuple[SourceGroundedPropositionFragment, ...]:
    if not candidates:
        raise ValueError("Proposition Scope requires one included Fragment Candidate.")
    ordered = sorted(candidates, key=lambda item: (item.start, item.end, item.id))
    groups: list[list[PropositionFragmentCandidate]] = []
    for candidate in ordered:
        if not groups or candidate.start >= max(item.end for item in groups[-1]):
            groups.append([candidate])
        else:
            groups[-1].append(candidate)
    fragments: list[SourceGroundedPropositionFragment] = []
    for group in groups:
        start = min(item.start for item in group)
        end = max(item.end for item in group)
        candidate_ids = tuple(sorted(item.id for item in group))
        text = source_text[start:end]
        fragment_id = source_grounded_proposition_fragment_id(
            source_segment_id=group[0].source_segment_id,
            source_text_sha256=group[0].source_text_sha256,
            start=start,
            end=end,
            text=text,
            contributing_candidate_ids=candidate_ids,
        )
        fragments.append(
            SourceGroundedPropositionFragment(
                id=fragment_id,
                source_segment_id=group[0].source_segment_id,
                source_text_sha256=group[0].source_text_sha256,
                start=start,
                end=end,
                text=text,
                contributing_candidate_ids=candidate_ids,
            )
        )
    return tuple(fragments)


def _ordered_distinct(label: str, values: tuple[str, ...]) -> None:
    if tuple(sorted(set(values))) != values:
        raise ValueError(f"{label} must be ordered and distinct.")


def _id(prefix: str, *parts: str) -> str:
    return f"{prefix}_{hashlib.sha256(chr(31).join(parts).encode()).hexdigest()[:24]}"
