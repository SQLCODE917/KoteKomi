"""Source-grounded qualification and identity grouping for Organization mentions."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from dataclasses import dataclass
from enum import StrEnum
from itertools import combinations

from kotekomi_application.document_aliases import parse_parenthetical_alias


class QualificationStatus(StrEnum):
    VALIDATED = "validated"
    REJECTED = "rejected"
    INVALID = "invalid"


class AliasDecisionStatus(StrEnum):
    RESOLVED = "resolved"
    AMBIGUOUS = "alias_ambiguous"
    NOT_ALIAS = "not_alias"


@dataclass(frozen=True)
class MentionProposalObservation:
    proposer_id: str
    text: str
    start: int
    end: int
    score: float | None = None
    model_run_id: str | None = None

    def __post_init__(self) -> None:
        if not self.proposer_id or not self.text:
            raise ValueError("Mention proposal observation identity must be complete.")
        if type(self.start) is not int or type(self.end) is not int:
            raise ValueError("Mention proposal observation positions must be integers.")
        if self.start < 0 or self.end <= self.start:
            raise ValueError("Mention proposal observation positions are invalid.")
        if self.score is not None and (
            type(self.score) is not float or not 0.0 <= self.score <= 1.0
        ):
            raise ValueError("Mention proposal observation score must be between zero and one.")


@dataclass(frozen=True)
class MentionCandidate:
    id: str
    source_segment_id: str
    source_text_digest: str
    text: str
    start: int
    end: int
    observations: tuple[MentionProposalObservation, ...]


@dataclass(frozen=True)
class ValidatedOrganizationMention:
    id: str
    representation_id: str
    source_segment_id: str
    source_text_digest: str
    text: str
    start: int
    end: int
    candidate_ids: tuple[str, ...]
    proposer_ids: tuple[str, ...]
    qualification_model_run_ids: tuple[str, ...]


@dataclass(frozen=True)
class OrganizationQualificationResult:
    candidate_id: str
    status: QualificationStatus
    returned_text: str | None
    diagnostics: tuple[str, ...]
    model_run_id: str | None
    mention: ValidatedOrganizationMention | None


@dataclass(frozen=True)
class AliasDecision:
    expression: str
    expanded_name: str | None
    alias: str | None
    status: AliasDecisionStatus


@dataclass(frozen=True)
class OrganizationIdentityCandidate:
    id: str
    representation_id: str
    preferred_name: str
    alias_names: tuple[str, ...]
    mention_ids: tuple[str, ...]


@dataclass(frozen=True)
class OrganizationIdentityResolution:
    identities: tuple[OrganizationIdentityCandidate, ...]
    alias_decisions: tuple[AliasDecision, ...]


@dataclass(frozen=True)
class QualifiedOrganizationPair:
    id: str
    source_segment_id: str
    first_identity_id: str
    first_organization_text: str
    second_identity_id: str
    second_organization_text: str


def fuse_mention_proposals(
    source_text: str,
    source_segment_id: str,
    observations: tuple[MentionProposalObservation, ...],
) -> tuple[MentionCandidate, ...]:
    """Validate source spans and combine observations for equal spans."""
    if not source_text or not source_segment_id:
        raise ValueError("Mention proposal fusion requires source text and segment identity.")
    source_digest = hashlib.sha256(source_text.encode()).hexdigest()
    grouped: dict[tuple[int, int, str], list[MentionProposalObservation]] = defaultdict(list)
    seen: set[tuple[str, int, int]] = set()
    for observation in observations:
        if observation.end > len(source_text):
            raise ValueError("Mention proposal observation exceeds the Source segment.")
        if source_text[observation.start : observation.end] != observation.text:
            raise ValueError("Mention proposal observation does not match source characters.")
        observation_key = (observation.proposer_id, observation.start, observation.end)
        if observation_key in seen:
            raise ValueError("Mention proposer repeats one source span.")
        seen.add(observation_key)
        grouped[(observation.start, observation.end, observation.text)].append(observation)
    return tuple(
        MentionCandidate(
            id=_id("mnc", source_segment_id, str(start), str(end), text),
            source_segment_id=source_segment_id,
            source_text_digest=source_digest,
            text=text,
            start=start,
            end=end,
            observations=tuple(
                sorted(
                    values,
                    key=lambda item: (
                        item.proposer_id,
                        item.model_run_id or "",
                        item.score if item.score is not None else -1.0,
                    ),
                )
            ),
        )
        for (start, end, text), values in sorted(grouped.items())
    )


def resolve_organization_qualification(
    *,
    representation_id: str,
    source_text: str,
    candidate: MentionCandidate,
    returned_text: str | None,
    rejected: bool,
    model_run_id: str | None,
) -> OrganizationQualificationResult:
    """Resolve one semantic judgment without accepting model-authored positions."""
    if hashlib.sha256(source_text.encode()).hexdigest() != candidate.source_text_digest:
        raise ValueError("Qualification Source segment digest does not match the candidate.")
    if rejected:
        if returned_text is not None:
            raise ValueError("Rejected qualification cannot return an Organization expression.")
        return OrganizationQualificationResult(
            candidate.id,
            QualificationStatus.REJECTED,
            None,
            (),
            model_run_id,
            None,
        )
    if not returned_text:
        return OrganizationQualificationResult(
            candidate.id,
            QualificationStatus.INVALID,
            returned_text,
            ("organization_expression_missing",),
            model_run_id,
            None,
        )
    occurrences = _occurrences(source_text, returned_text)
    containing = tuple(
        (start, end)
        for start, end in occurrences
        if start <= candidate.start and end >= candidate.end
    )
    if len(containing) != 1:
        diagnostic = (
            "organization_expression_not_candidate_bound"
            if not containing
            else "organization_expression_ambiguous"
        )
        return OrganizationQualificationResult(
            candidate.id,
            QualificationStatus.INVALID,
            returned_text,
            (diagnostic,),
            model_run_id,
            None,
        )
    start, end = containing[0]
    mention = ValidatedOrganizationMention(
        id=_id(
            "vom",
            representation_id,
            candidate.source_segment_id,
            str(start),
            str(end),
            returned_text,
        ),
        representation_id=representation_id,
        source_segment_id=candidate.source_segment_id,
        source_text_digest=candidate.source_text_digest,
        text=returned_text,
        start=start,
        end=end,
        candidate_ids=(candidate.id,),
        proposer_ids=tuple(sorted({item.proposer_id for item in candidate.observations})),
        qualification_model_run_ids=(model_run_id,) if model_run_id is not None else (),
    )
    return OrganizationQualificationResult(
        candidate.id,
        QualificationStatus.VALIDATED,
        returned_text,
        (),
        model_run_id,
        mention,
    )


def combine_validated_organization_mentions(
    mentions: tuple[ValidatedOrganizationMention, ...],
) -> tuple[ValidatedOrganizationMention, ...]:
    """Combine candidates that semantic qualification resolves to one source span."""
    grouped: dict[tuple[str, str, int, int, str], list[ValidatedOrganizationMention]] = defaultdict(
        list
    )
    for mention in mentions:
        grouped[
            (
                mention.representation_id,
                mention.source_segment_id,
                mention.start,
                mention.end,
                mention.text,
            )
        ].append(mention)
    combined: list[ValidatedOrganizationMention] = []
    for _key, values in sorted(grouped.items()):
        first = values[0]
        combined.append(
            ValidatedOrganizationMention(
                id=first.id,
                representation_id=first.representation_id,
                source_segment_id=first.source_segment_id,
                source_text_digest=first.source_text_digest,
                text=first.text,
                start=first.start,
                end=first.end,
                candidate_ids=tuple(
                    sorted({item for value in values for item in value.candidate_ids})
                ),
                proposer_ids=tuple(
                    sorted({item for value in values for item in value.proposer_ids})
                ),
                qualification_model_run_ids=tuple(
                    sorted({item for value in values for item in value.qualification_model_run_ids})
                ),
            )
        )
    return tuple(combined)


def resolve_document_organization_identities(
    representation_id: str,
    mentions: tuple[ValidatedOrganizationMention, ...],
) -> OrganizationIdentityResolution:
    """Group exact names and explicit initialisms inside one representation."""
    if any(mention.representation_id != representation_id for mention in mentions):
        raise ValueError("Organization identity resolution cannot cross representations.")
    declaration_values: list[tuple[ValidatedOrganizationMention, str, str, bool]] = []
    expanded_by_alias: dict[str, set[str]] = defaultdict(set)
    for mention in mentions:
        parsed = parenthetical_organization_alias(mention.text)
        if parsed is None:
            continue
        expanded, alias, matches = parsed
        declaration_values.append((mention, expanded, alias, matches))
        if matches:
            expanded_by_alias[_name_key(alias)].add(_name_key(expanded))
    ambiguous_aliases = {
        alias for alias, expanded_names in expanded_by_alias.items() if len(expanded_names) > 1
    }
    canonical_expanded_by_alias = {
        alias: next(iter(expanded_names))
        for alias, expanded_names in expanded_by_alias.items()
        if len(expanded_names) == 1
    }
    display_expanded = {
        _name_key(expanded): expanded
        for _, expanded, alias, matches in declaration_values
        if matches and _name_key(alias) not in ambiguous_aliases
    }
    group_key_by_mention: dict[str, str] = {}
    aliases_by_group: dict[str, set[str]] = defaultdict(set)
    decisions: list[AliasDecision] = []
    for mention, expanded, alias, matches in declaration_values:
        alias_key = _name_key(alias)
        if not matches:
            decisions.append(
                AliasDecision(mention.text, expanded, alias, AliasDecisionStatus.NOT_ALIAS)
            )
        elif alias_key in ambiguous_aliases:
            decisions.append(
                AliasDecision(mention.text, expanded, alias, AliasDecisionStatus.AMBIGUOUS)
            )
        else:
            group_key = _name_key(expanded)
            group_key_by_mention[mention.id] = group_key
            aliases_by_group[group_key].add(alias)
            decisions.append(
                AliasDecision(mention.text, expanded, alias, AliasDecisionStatus.RESOLVED)
            )
    for mention in mentions:
        if mention.id in group_key_by_mention:
            continue
        name_key = _name_key(mention.text)
        group_key_by_mention[mention.id] = canonical_expanded_by_alias.get(name_key, name_key)
    grouped: dict[str, list[ValidatedOrganizationMention]] = defaultdict(list)
    for mention in mentions:
        grouped[group_key_by_mention[mention.id]].append(mention)
    identities = tuple(
        OrganizationIdentityCandidate(
            id=_id("oic", representation_id, group_key),
            representation_id=representation_id,
            preferred_name=display_expanded.get(
                group_key,
                sorted((item.text for item in values), key=lambda item: (-len(item), item))[0],
            ),
            alias_names=tuple(
                sorted(aliases_by_group[group_key], key=lambda item: item.casefold())
            ),
            mention_ids=tuple(sorted(item.id for item in values)),
        )
        for group_key, values in sorted(grouped.items())
    )
    return OrganizationIdentityResolution(
        identities,
        tuple(sorted(decisions, key=lambda item: (item.expression, item.alias or ""))),
    )


def derive_qualified_organization_pairs(
    source_segment_id: str,
    mentions: tuple[ValidatedOrganizationMention, ...],
    identities: tuple[OrganizationIdentityCandidate, ...],
) -> tuple[QualifiedOrganizationPair, ...]:
    """Derive each source-local pair once after identity grouping."""
    mention_by_id = {mention.id: mention for mention in mentions}
    local: list[tuple[OrganizationIdentityCandidate, ValidatedOrganizationMention]] = []
    for identity in identities:
        local_mentions = sorted(
            (
                mention_by_id[mention_id]
                for mention_id in identity.mention_ids
                if mention_id in mention_by_id
                and mention_by_id[mention_id].source_segment_id == source_segment_id
            ),
            key=lambda item: (item.start, item.end, item.text),
        )
        if local_mentions:
            local.append((identity, local_mentions[0]))
    local.sort(key=lambda item: (item[1].start, item[1].end, item[0].id))
    return tuple(
        QualifiedOrganizationPair(
            id=_id("qop", source_segment_id, first.id, second.id),
            source_segment_id=source_segment_id,
            first_identity_id=first.id,
            first_organization_text=first_mention.text,
            second_identity_id=second.id,
            second_organization_text=second_mention.text,
        )
        for (first, first_mention), (second, second_mention) in combinations(local, 2)
    )


def parenthetical_organization_alias(text: str) -> tuple[str, str, bool] | None:
    """Parse one literal expanded-name and initialism declaration."""
    return parse_parenthetical_alias(text)


def _name_key(text: str) -> str:
    return " ".join(text.casefold().split())


def _occurrences(source_text: str, expression: str) -> tuple[tuple[int, int], ...]:
    values: list[tuple[int, int]] = []
    cursor = 0
    while True:
        start = source_text.find(expression, cursor)
        if start < 0:
            return tuple(values)
        end = start + len(expression)
        values.append((start, end))
        cursor = end


def _id(prefix: str, *parts: str) -> str:
    return f"{prefix}_{hashlib.sha256(chr(31).join(parts).encode()).hexdigest()[:24]}"
