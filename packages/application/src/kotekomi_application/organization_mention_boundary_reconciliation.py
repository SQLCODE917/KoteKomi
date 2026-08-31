"""Deterministic source-bound Organization mention boundary reconciliation."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from enum import StrEnum
from itertools import combinations

from kotekomi_application.organization_mention_qualification import (
    MentionCandidate,
    parenthetical_organization_alias,
)

ORGANIZATION_BOUNDARY_RECONCILIATION_POLICY_ID = "organization_boundary_reconciliation_v1"


class MentionBoundaryRelation(StrEnum):
    EQUAL = "equal"
    CONTAINS = "contains"
    CONTAINED_BY = "contained_by"
    CROSSING = "crossing"
    ADJACENT = "adjacent"
    DISJOINT = "disjoint"


class MentionBoundaryDecisionStatus(StrEnum):
    RESOLVED = "resolved"
    AMBIGUOUS = "ambiguous"
    UNCONTESTED = "uncontested"


@dataclass(frozen=True)
class MentionBoundaryRelationObservation:
    first_candidate_id: str
    second_candidate_id: str
    relation: MentionBoundaryRelation


@dataclass(frozen=True)
class MentionBoundaryDecision:
    id: str
    source_segment_id: str
    source_text_digest: str
    status: MentionBoundaryDecisionStatus
    rule_id: str
    candidate_ids: tuple[str, ...]
    selected_candidate_ids: tuple[str, ...]
    preserved_candidate_ids: tuple[str, ...]
    alias_evidence_candidate_ids: tuple[str, ...]
    relations: tuple[MentionBoundaryRelationObservation, ...]
    diagnostics: tuple[str, ...]


@dataclass(frozen=True)
class ReconciledMentionCandidate:
    id: str
    source_segment_id: str
    source_text_digest: str
    text: str
    start: int
    end: int
    source_candidate_ids: tuple[str, ...]
    proposer_ids: tuple[str, ...]
    decision_id: str
    boundary_status: MentionBoundaryDecisionStatus
    alias_evidence_candidate_ids: tuple[str, ...]


@dataclass(frozen=True)
class OrganizationBoundaryReconciliationResult:
    policy_id: str
    source_segment_id: str
    source_text_digest: str
    relations: tuple[MentionBoundaryRelationObservation, ...]
    decisions: tuple[MentionBoundaryDecision, ...]
    reconciled_candidates: tuple[ReconciledMentionCandidate, ...]


def mention_boundary_relation(
    first_start: int,
    first_end: int,
    second_start: int,
    second_end: int,
) -> MentionBoundaryRelation:
    """Classify two valid half-open source intervals."""
    _validate_interval(first_start, first_end)
    _validate_interval(second_start, second_end)
    if first_start == second_start and first_end == second_end:
        return MentionBoundaryRelation.EQUAL
    if first_start <= second_start and first_end >= second_end:
        return MentionBoundaryRelation.CONTAINS
    if second_start <= first_start and second_end >= first_end:
        return MentionBoundaryRelation.CONTAINED_BY
    if first_end == second_start or second_end == first_start:
        return MentionBoundaryRelation.ADJACENT
    if max(first_start, second_start) < min(first_end, second_end):
        return MentionBoundaryRelation.CROSSING
    return MentionBoundaryRelation.DISJOINT


def reconcile_organization_mention_boundaries(
    *,
    source_text: str,
    source_segment_id: str,
    candidates: tuple[MentionCandidate, ...],
) -> OrganizationBoundaryReconciliationResult:
    """Apply the ORG-R1 source-literal policy without semantic qualification."""
    if not source_text or not source_segment_id:
        raise ValueError("Boundary reconciliation requires source text and segment identity.")
    source_digest = hashlib.sha256(source_text.encode("utf-8")).hexdigest()
    ordered = tuple(sorted(candidates, key=_candidate_key))
    _validate_candidates(source_text, source_segment_id, source_digest, ordered)
    relations = tuple(
        MentionBoundaryRelationObservation(
            first.id,
            second.id,
            mention_boundary_relation(first.start, first.end, second.start, second.end),
        )
        for first, second in combinations(ordered, 2)
    )
    relation_by_pair = {
        frozenset((relation.first_candidate_id, relation.second_candidate_id)): relation
        for relation in relations
    }
    components = _overlap_components(ordered, relation_by_pair)
    decisions: list[MentionBoundaryDecision] = []
    reconciled: list[ReconciledMentionCandidate] = []
    by_id = {candidate.id: candidate for candidate in ordered}
    for component in components:
        component_relations = tuple(
            relation
            for relation in relations
            if relation.first_candidate_id in component
            and relation.second_candidate_id in component
        )
        decision = _component_decision(
            source_text,
            source_segment_id,
            source_digest,
            tuple(by_id[candidate_id] for candidate_id in component),
            component_relations,
        )
        decisions.append(decision)
        for candidate_id in decision.selected_candidate_ids:
            candidate = by_id[candidate_id]
            reconciled.append(
                ReconciledMentionCandidate(
                    id=_id("rmc", decision.id, candidate.id),
                    source_segment_id=source_segment_id,
                    source_text_digest=source_digest,
                    text=candidate.text,
                    start=candidate.start,
                    end=candidate.end,
                    source_candidate_ids=decision.candidate_ids,
                    proposer_ids=tuple(
                        sorted({observation.proposer_id for observation in candidate.observations})
                    ),
                    decision_id=decision.id,
                    boundary_status=decision.status,
                    alias_evidence_candidate_ids=decision.alias_evidence_candidate_ids,
                )
            )
    result = OrganizationBoundaryReconciliationResult(
        policy_id=ORGANIZATION_BOUNDARY_RECONCILIATION_POLICY_ID,
        source_segment_id=source_segment_id,
        source_text_digest=source_digest,
        relations=relations,
        decisions=tuple(decisions),
        reconciled_candidates=tuple(
            sorted(reconciled, key=lambda item: (item.start, item.end, item.id))
        ),
    )
    _validate_result_candidate_retention(result, ordered)
    return result


def canonical_boundary_reconciliation_json(
    result: OrganizationBoundaryReconciliationResult,
) -> str:
    """Serialize one reconciliation result canonically for diagnostic evidence."""
    return json.dumps(asdict(result), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _validate_interval(start: int, end: int) -> None:
    if type(start) is not int or type(end) is not int or start < 0 or end <= start:
        raise ValueError("Mention boundaries must be valid half-open integer intervals.")


def _validate_candidates(
    source_text: str,
    source_segment_id: str,
    source_digest: str,
    candidates: tuple[MentionCandidate, ...],
) -> None:
    identities: set[str] = set()
    spans: set[tuple[int, int]] = set()
    for candidate in candidates:
        _validate_interval(candidate.start, candidate.end)
        if candidate.id in identities:
            raise ValueError("Boundary reconciliation repeats a candidate identity.")
        identities.add(candidate.id)
        if candidate.source_segment_id != source_segment_id:
            raise ValueError("Mention candidate Source segment identity drifted.")
        if candidate.source_text_digest != source_digest:
            raise ValueError("Mention candidate Source digest drifted.")
        if (
            candidate.end > len(source_text)
            or source_text[candidate.start : candidate.end] != candidate.text
        ):
            raise ValueError("Mention candidate does not match authoritative source characters.")
        span = (candidate.start, candidate.end)
        if span in spans:
            raise ValueError("Equal Mention candidate spans must be fused before reconciliation.")
        spans.add(span)


def _overlap_components(
    candidates: tuple[MentionCandidate, ...],
    relations: dict[frozenset[str], MentionBoundaryRelationObservation],
) -> tuple[tuple[str, ...], ...]:
    adjacent: dict[str, set[str]] = {candidate.id: set() for candidate in candidates}
    for first, second in combinations(candidates, 2):
        relation = relations[frozenset((first.id, second.id))].relation
        if relation in {
            MentionBoundaryRelation.EQUAL,
            MentionBoundaryRelation.CONTAINS,
            MentionBoundaryRelation.CONTAINED_BY,
            MentionBoundaryRelation.CROSSING,
        }:
            adjacent[first.id].add(second.id)
            adjacent[second.id].add(first.id)
    candidate_by_id = {candidate.id: candidate for candidate in candidates}
    remaining = set(candidate_by_id)
    components: list[tuple[str, ...]] = []
    while remaining:
        seed = min(remaining, key=lambda item: _candidate_key(candidate_by_id[item]))
        stack = [seed]
        connected: set[str] = set()
        while stack:
            candidate_id = stack.pop()
            if candidate_id in connected:
                continue
            connected.add(candidate_id)
            stack.extend(sorted(adjacent[candidate_id] - connected))
        remaining -= connected
        components.append(
            tuple(sorted(connected, key=lambda item: _candidate_key(candidate_by_id[item])))
        )
    return tuple(components)


def _component_decision(
    source_text: str,
    source_segment_id: str,
    source_digest: str,
    candidates: tuple[MentionCandidate, ...],
    relations: tuple[MentionBoundaryRelationObservation, ...],
) -> MentionBoundaryDecision:
    candidate_ids = tuple(candidate.id for candidate in candidates)
    status = MentionBoundaryDecisionStatus.UNCONTESTED
    rule_id = "uncontested_source_span_v1"
    selected = candidate_ids
    aliases: tuple[str, ...] = ()
    diagnostics: tuple[str, ...] = ()
    if len(candidates) > 1:
        parenthetical = _parenthetical_selection(source_text, candidates)
        possessive = _possessive_selection(candidates)
        if parenthetical is not None:
            selected, aliases = parenthetical
            status = MentionBoundaryDecisionStatus.RESOLVED
            rule_id = "exact_parenthetical_alias_v1"
        elif possessive is not None:
            selected = (possessive,)
            status = MentionBoundaryDecisionStatus.RESOLVED
            rule_id = "terminal_possessive_suffix_v1"
        else:
            selected = ()
            status = MentionBoundaryDecisionStatus.AMBIGUOUS
            rule_id = "unresolved_overlap_v1"
            diagnostics = ("semantic_boundary_judgment_required",)
    decision_id = _id(
        "mbd",
        ORGANIZATION_BOUNDARY_RECONCILIATION_POLICY_ID,
        source_segment_id,
        source_digest,
        rule_id,
        *candidate_ids,
    )
    return MentionBoundaryDecision(
        id=decision_id,
        source_segment_id=source_segment_id,
        source_text_digest=source_digest,
        status=status,
        rule_id=rule_id,
        candidate_ids=candidate_ids,
        selected_candidate_ids=selected,
        preserved_candidate_ids=candidate_ids,
        alias_evidence_candidate_ids=aliases,
        relations=relations,
        diagnostics=diagnostics,
    )


def _parenthetical_selection(
    source_text: str,
    candidates: tuple[MentionCandidate, ...],
) -> tuple[tuple[str, ...], tuple[str, ...]] | None:
    outer_candidates: list[tuple[MentionCandidate, str, str]] = []
    for candidate in candidates:
        parsed = parenthetical_organization_alias(candidate.text)
        if parsed is not None and parsed[2]:
            outer_candidates.append((candidate, parsed[0], parsed[1]))
    if len(outer_candidates) != 1:
        return None
    outer, expanded, alias = outer_candidates[0]
    expanded_span = (outer.start, outer.start + len(expanded))
    alias_start = outer.start + len(expanded) + 2
    alias_span = (alias_start, alias_start + len(alias))
    if source_text[expanded_span[0] : expanded_span[1]] != expanded:
        return None
    if source_text[alias_span[0] : alias_span[1]] != alias:
        return None
    nested = tuple(candidate for candidate in candidates if candidate.id != outer.id)
    if not nested or any(
        (candidate.start, candidate.end) not in {expanded_span, alias_span} for candidate in nested
    ):
        return None
    alias_ids = tuple(
        candidate.id for candidate in nested if (candidate.start, candidate.end) == alias_span
    )
    return (outer.id,), alias_ids


def _possessive_selection(candidates: tuple[MentionCandidate, ...]) -> str | None:
    if len(candidates) != 2:
        return None
    for base, possessive in (candidates, tuple(reversed(candidates))):
        if (
            possessive.start == base.start
            and possessive.end == base.end + 2
            and possessive.text in {base.text + "'s", base.text + "’s"}
        ):
            return base.id
    return None


def _validate_result_candidate_retention(
    result: OrganizationBoundaryReconciliationResult,
    candidates: tuple[MentionCandidate, ...],
) -> None:
    expected = {candidate.id for candidate in candidates}
    observed = [
        candidate_id for decision in result.decisions for candidate_id in decision.candidate_ids
    ]
    preserved = [
        candidate_id
        for decision in result.decisions
        for candidate_id in decision.preserved_candidate_ids
    ]
    if len(observed) != len(set(observed)) or set(observed) != expected:
        raise RuntimeError("Boundary decisions do not partition all candidates exactly once.")
    if preserved != observed:
        raise RuntimeError("Boundary decisions do not preserve every source-valid candidate.")


def _candidate_key(candidate: MentionCandidate) -> tuple[int, int, str, str]:
    return candidate.start, candidate.end, candidate.text, candidate.id


def _id(prefix: str, *parts: str) -> str:
    return f"{prefix}_{hashlib.sha256(chr(31).join(parts).encode('utf-8')).hexdigest()[:24]}"
