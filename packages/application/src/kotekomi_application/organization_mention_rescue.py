"""Monotonic source-valid Organization candidate fusion for PHP-1 diagnostics."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from dataclasses import dataclass
from itertools import combinations

from kotekomi_application.organization_mention_qualification import (
    MentionProposalObservation,
    fuse_mention_proposals,
    parenthetical_organization_alias,
)


@dataclass(frozen=True)
class MonotonicMentionCandidate:
    id: str
    source_segment_id: str
    source_text_digest: str
    text: str
    start: int
    end: int
    proposer_ids: tuple[str, ...]
    baseline: bool
    rescue: bool


@dataclass(frozen=True)
class MonotonicCandidateGroup:
    id: str
    preferred_text: str
    mention_candidate_ids: tuple[str, ...]
    baseline: bool
    rescue: bool


@dataclass(frozen=True)
class MonotonicCandidatePair:
    id: str
    source_segment_id: str
    first_group_id: str
    first_candidate_text: str
    second_group_id: str
    second_candidate_text: str
    requires_new_judgment: bool


@dataclass(frozen=True)
class MonotonicCandidatePairExclusion:
    first_group_id: str
    second_group_id: str
    reason: str


@dataclass(frozen=True)
class MonotonicCandidateFusion:
    mention_candidates: tuple[MonotonicMentionCandidate, ...]
    candidate_groups: tuple[MonotonicCandidateGroup, ...]
    candidate_pairs: tuple[MonotonicCandidatePair, ...]
    pair_exclusions: tuple[MonotonicCandidatePairExclusion, ...]


def fuse_monotonic_organization_candidates(
    *,
    source_text: str,
    source_segment_id: str,
    baseline_observations: tuple[MentionProposalObservation, ...],
    rescue_observations: tuple[MentionProposalObservation, ...],
) -> MonotonicCandidateFusion:
    """Retain baseline spans and add rescue spans without asserting Organization status."""
    baseline_spans = {(item.start, item.end, item.text) for item in baseline_observations}
    source_text_digest = hashlib.sha256(source_text.encode("utf-8")).hexdigest()
    candidates = fuse_mention_proposals(
        source_text,
        source_segment_id,
        baseline_observations + rescue_observations,
    )
    mention_candidates = tuple(
        MonotonicMentionCandidate(
            id=_id("mmc", source_segment_id, str(candidate.start), str(candidate.end)),
            source_segment_id=source_segment_id,
            source_text_digest=source_text_digest,
            text=candidate.text,
            start=candidate.start,
            end=candidate.end,
            proposer_ids=tuple(
                sorted({observation.proposer_id for observation in candidate.observations})
            ),
            baseline=(candidate.start, candidate.end, candidate.text) in baseline_spans,
            rescue=(candidate.start, candidate.end, candidate.text) not in baseline_spans,
        )
        for candidate in candidates
    )
    candidate_groups = _candidate_groups(source_segment_id, mention_candidates)
    mention_by_id = {mention.id: mention for mention in mention_candidates}
    ordered_groups = sorted(
        candidate_groups,
        key=lambda group: min(
            (mention_by_id[item].start, mention_by_id[item].end)
            for item in group.mention_candidate_ids
        ),
    )
    pairs: list[MonotonicCandidatePair] = []
    exclusions: list[MonotonicCandidatePairExclusion] = []
    for first, second in combinations(ordered_groups, 2):
        if _groups_overlap(first, second, mention_by_id):
            exclusions.append(
                MonotonicCandidatePairExclusion(
                    first.id,
                    second.id,
                    "overlapping_source_spans",
                )
            )
            continue
        first_mention = min(
            (mention_by_id[item] for item in first.mention_candidate_ids),
            key=lambda item: (item.start, item.end, item.text),
        )
        second_mention = min(
            (mention_by_id[item] for item in second.mention_candidate_ids),
            key=lambda item: (item.start, item.end, item.text),
        )
        pairs.append(
            MonotonicCandidatePair(
                _id("mcp", source_segment_id, first.id, second.id),
                source_segment_id,
                first.id,
                first_mention.text,
                second.id,
                second_mention.text,
                not (first.baseline and second.baseline),
            )
        )
    return MonotonicCandidateFusion(
        mention_candidates,
        candidate_groups,
        tuple(pairs),
        tuple(exclusions),
    )


def _candidate_groups(
    source_segment_id: str,
    mentions: tuple[MonotonicMentionCandidate, ...],
) -> tuple[MonotonicCandidateGroup, ...]:
    expanded_by_alias: dict[str, set[str]] = defaultdict(set)
    declarations: dict[str, tuple[str, str]] = {}
    for mention in mentions:
        parsed = parenthetical_organization_alias(mention.text)
        if parsed is None:
            continue
        expanded, alias, matches = parsed
        if matches:
            expanded_by_alias[_name_key(alias)].add(_name_key(expanded))
            declarations[mention.id] = (expanded, alias)
    aliases = {
        alias: next(iter(expanded))
        for alias, expanded in expanded_by_alias.items()
        if len(expanded) == 1
    }
    grouped: dict[str, list[MonotonicMentionCandidate]] = defaultdict(list)
    preferred: dict[str, str] = {}
    for mention in mentions:
        declaration = declarations.get(mention.id)
        if declaration is not None:
            expanded, _alias = declaration
            key = _name_key(expanded)
            preferred[key] = expanded
        else:
            key = aliases.get(_name_key(mention.text), _name_key(mention.text))
        grouped[key].append(mention)
    return tuple(
        MonotonicCandidateGroup(
            _id("mcg", source_segment_id, key),
            preferred.get(
                key,
                sorted(
                    (mention.text for mention in values),
                    key=lambda item: (-len(item), item),
                )[0],
            ),
            tuple(sorted(mention.id for mention in values)),
            any(mention.baseline for mention in values),
            any(mention.rescue for mention in values),
        )
        for key, values in sorted(grouped.items())
    )


def _groups_overlap(
    first: MonotonicCandidateGroup,
    second: MonotonicCandidateGroup,
    mentions: dict[str, MonotonicMentionCandidate],
) -> bool:
    return any(
        max(mentions[first_id].start, mentions[second_id].start)
        < min(mentions[first_id].end, mentions[second_id].end)
        for first_id in first.mention_candidate_ids
        for second_id in second.mention_candidate_ids
    )


def _name_key(value: str) -> str:
    return " ".join(value.casefold().split())


def _id(prefix: str, *parts: str) -> str:
    identity_bytes = chr(31).join(parts).encode("utf-8")
    return f"{prefix}_{hashlib.sha256(identity_bytes).hexdigest()[:24]}"
