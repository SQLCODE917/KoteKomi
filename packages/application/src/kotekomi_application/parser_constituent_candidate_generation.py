"""Parser-constituent candidate generation for the R3 deliverable.

The inventory builder derives the R3 clause-local contiguous token groups plus
one Token sub-span per dependency token and one Head phrase projection per
governing head, all source-exact and drawn from the pinned Stanza dependency
tree.
It never reads Gold while deriving constituents and never invents source
characters.  The fidelity census compares every corrected Gold fragment
against an Event inventory by exact span and reports the Constituent Pool
Ceiling per partition.

The selection renderer names every constituent with one stable label and never
sends a candidate boundary to the model.  The selection parser accepts a finite
multi-label answer only: a subset of the named labels or the exact ``NONE``
token.  Invalid answers are rejected, never repaired.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from kotekomi_application.competitive_attachment_review_verification import (
    AttachmentSourceRange,
)
from kotekomi_application.event_entity_connections import EventEntityLinguisticToken
from kotekomi_application.trigger_containment_candidate_split import CorrectedAttachmentGold

_SHA256 = r"^[a-f0-9]{64}$"
type _EventId = Annotated[str, Field(pattern=r"^TGE-[0-9]{3}$")]
type _ConstituentId = Annotated[str, Field(pattern=r"^pct_[a-f0-9]{24}$")]
type _FragmentId = Annotated[str, Field(pattern=r"^PGF-TGE-[0-9]{3}-[0-9]{2}$")]

_DETACHED_CLAUSE_RELATIONS = frozenset({"acl", "acl:relcl", "advcl", "parataxis"})


class ParserConstituent(BaseModel):
    """One parser-derived, source-exact candidate over one Event SourceSegment."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    constituent_id: _ConstituentId
    event_id: _EventId
    source_text_sha256: Annotated[str, Field(pattern=_SHA256)]
    constituent_range: AttachmentSourceRange
    token_ids: tuple[Annotated[str, Field(pattern=r"^t[1-9][0-9]*$")], ...]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if not self.token_ids:
            raise ValueError("A Parser Constituent requires one dependency token.")
        if self.token_ids != tuple(sorted(set(self.token_ids), key=_token_ordinal)):
            raise ValueError("Parser Constituent token IDs must be ordered and distinct.")
        expected = parser_constituent_id(
            self.source_text_sha256, self.constituent_range.start, self.constituent_range.end
        )
        if self.constituent_id != expected:
            raise ValueError("Parser Constituent ID does not match its exact span.")
        return self


class ConstituentCandidateInventory(BaseModel):
    """The ordered Parser Constituent list proposed for one Event."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    event_id: _EventId
    source_text_sha256: Annotated[str, Field(pattern=_SHA256)]
    constituents: tuple[ParserConstituent, ...]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if not self.constituents:
            raise ValueError("A Constituent Candidate Inventory requires one constituent.")
        if any(item.event_id != self.event_id for item in self.constituents):
            raise ValueError("Inventory contains a constituent for a different Event.")
        if any(item.source_text_sha256 != self.source_text_sha256 for item in self.constituents):
            raise ValueError("Inventory contains a constituent for a different source.")
        spans = [item.constituent_range for item in self.constituents]
        if spans != sorted(spans, key=lambda item: (item.start, item.end)):
            raise ValueError("Inventory constituents must use source order.")
        if len({(item.start, item.end) for item in spans}) != len(spans):
            raise ValueError("Inventory constituents must be distinct by exact span.")
        return self


class ConstituentSelectionStatus(StrEnum):
    """Terminal parse state of one model Constituent Selection."""

    SELECTED = "selected"
    NONE = "none"
    REJECTED = "rejected"


class ConstituentSelectionTask(BaseModel):
    """One rendered finite selection task over a whole SourceSegment inventory."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    event_id: _EventId
    source_text_sha256: Annotated[str, Field(pattern=_SHA256)]
    source_text: Annotated[str, Field(min_length=1)]
    constituent_labels: tuple[Annotated[str, Field(pattern=r"^C[1-9][0-9]*$")], ...]
    rendered_input: Annotated[str, Field(min_length=1)]
    rendered_input_sha256: Annotated[str, Field(pattern=_SHA256)]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if hashlib.sha256(self.source_text.encode()).hexdigest() != self.source_text_sha256:
            raise ValueError("Constituent Selection Task source digest does not match its text.")
        if hashlib.sha256(self.rendered_input.encode()).hexdigest() != self.rendered_input_sha256:
            raise ValueError("Constituent Selection Task rendered digest does not match.")
        if self.constituent_labels != tuple(
            f"C{ordinal}" for ordinal in range(1, len(self.constituent_labels) + 1)
        ):
            raise ValueError("Constituent labels must be ordered and complete.")
        return self


class ConstituentSelectionAnswer(BaseModel):
    """One parsed finite model answer over a Constituent Selection Task."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    event_id: _EventId
    status: ConstituentSelectionStatus
    selected_label_indexes: tuple[Annotated[int, Field(ge=1)], ...]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if self.status is ConstituentSelectionStatus.SELECTED and not self.selected_label_indexes:
            raise ValueError("A selected answer requires one label index.")
        if self.status is not ConstituentSelectionStatus.SELECTED and self.selected_label_indexes:
            raise ValueError("A non-selected answer must carry no label indexes.")
        if self.selected_label_indexes != tuple(sorted(set(self.selected_label_indexes))):
            raise ValueError("Selected label indexes must be ordered and distinct.")
        return self


def parser_constituent_id(source_text_sha256: str, start: int, end: int) -> str:
    """Return one deterministic constituent ID for an exact source span."""
    value = f"{source_text_sha256}:{start}:{end}".encode()
    return "pct_" + hashlib.sha256(value).hexdigest()[:24]


def _token_ordinal(token_id: str) -> int:
    return int(token_id.lstrip("t"))


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


def _contiguous_token_groups(
    source_text: str,
    tokens: tuple[EventEntityLinguisticToken, ...],
) -> tuple[tuple[EventEntityLinguisticToken, ...], ...]:
    groups: list[list[EventEntityLinguisticToken]] = []
    for token in sorted(tokens, key=lambda item: (item.start, item.end)):
        if not groups or source_text[groups[-1][-1].end : token.start].strip():
            groups.append([token])
        else:
            groups[-1].append(token)
    return tuple(tuple(group) for group in groups)


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


def _clause_local_constituent_spans(
    *,
    source_text: str,
    tokens: tuple[EventEntityLinguisticToken, ...],
) -> tuple[tuple[int, int], ...]:
    children: dict[str, list[EventEntityLinguisticToken]] = {}
    for token in tokens:
        if token.head_token_id is not None:
            children.setdefault(token.head_token_id, []).append(token)
    by_sentence: dict[str, list[EventEntityLinguisticToken]] = {}
    for token in tokens:
        by_sentence.setdefault(token.sentence_id, []).append(token)
    spans: dict[tuple[int, int], None] = {}
    for sentence_id, sentence_tokens in by_sentence.items():
        ids = {item.token_id for item in sentence_tokens}
        roots = [
            item
            for item in sentence_tokens
            if item.head_token_id is None or item.head_token_id not in ids
        ]
        for root in roots:
            subtree = _subtree_tokens(root, children, sentence_id=sentence_id)
            detached = _detached_modifier_roots(root, subtree, children, source_text=source_text)
            blocked: set[str] = set()
            for boundary in detached:
                blocked.update(
                    item.token_id
                    for item in _subtree_tokens(boundary, children, sentence_id=sentence_id)
                )
            pruned = tuple(item for item in subtree if item.token_id not in blocked)
            for group in _contiguous_token_groups(source_text, pruned):
                if group:
                    spans[(group[0].start, group[-1].end)] = None
            for boundary in detached:
                boundary_subtree = _subtree_tokens(boundary, children, sentence_id=sentence_id)
                for group in _contiguous_token_groups(source_text, boundary_subtree):
                    if group:
                        spans[(group[0].start, group[-1].end)] = None
    return tuple(sorted(spans))


def _token_sub_span_spans(
    tokens: tuple[EventEntityLinguisticToken, ...],
) -> tuple[tuple[int, int], ...]:
    """Derive one exact Token sub-span per dependency token."""
    return tuple((token.start, token.end) for token in tokens)


def _head_phrase_projection_spans(
    *,
    source_text: str,
    tokens: tuple[EventEntityLinguisticToken, ...],
) -> tuple[tuple[int, int], ...]:
    """Derive one Head phrase projection per governing head, never crossing a
    Detached clause."""
    children: dict[str, list[EventEntityLinguisticToken]] = {}
    for token in tokens:
        if token.head_token_id is not None:
            children.setdefault(token.head_token_id, []).append(token)
    by_id = {token.token_id: token for token in tokens}
    spans: dict[tuple[int, int], None] = {}
    for head_id in sorted(children, key=_token_ordinal):
        head = by_id.get(head_id)
        if head is None:
            continue
        subtree = _subtree_tokens(head, children, sentence_id=head.sentence_id)
        detached = _detached_modifier_roots(head, subtree, children, source_text=source_text)
        blocked: set[str] = set()
        for boundary in detached:
            blocked.update(
                item.token_id
                for item in _subtree_tokens(boundary, children, sentence_id=head.sentence_id)
            )
        pruned = tuple(item for item in subtree if item.token_id not in blocked)
        for group in _contiguous_token_groups(source_text, pruned):
            if group:
                spans[(group[0].start, group[-1].end)] = None
    return tuple(sorted(spans))


def build_constituent_candidate_inventory(
    *,
    source_text: str,
    event_id: str,
    tokens: tuple[EventEntityLinguisticToken, ...],
    event_expression_start: int,
    event_expression_end: int,
) -> ConstituentCandidateInventory:
    """Derive one Event inventory without reading Gold."""
    source_text_sha256 = hashlib.sha256(source_text.encode()).hexdigest()
    if not tokens:
        raise ValueError("Constituent derivation requires dependency tokens.")
    if tuple(item.token_id for item in tokens) != tuple(
        f"t{ordinal}" for ordinal in range(1, len(tokens) + 1)
    ):
        raise ValueError("Dependency tokens must be complete and ordered.")
    if not (0 <= event_expression_start < event_expression_end <= len(source_text)):
        raise ValueError("Event expression range leaves its SourceSegment.")
    if not source_text[event_expression_start:event_expression_end].strip():
        raise ValueError("Event expression cannot be whitespace-only.")
    for token in tokens:
        if token.start < 0 or token.end > len(source_text) or token.start >= token.end:
            raise ValueError("Dependency token leaves its SourceSegment.")
        if source_text[token.start : token.end] != token.text:
            raise ValueError("Dependency token does not match exact source characters.")

    spans = set(_clause_local_constituent_spans(source_text=source_text, tokens=tokens))
    spans.add((event_expression_start, event_expression_end))
    spans.update(_token_sub_span_spans(tokens))
    spans.update(_head_phrase_projection_spans(source_text=source_text, tokens=tokens))

    constituents: list[ParserConstituent] = []
    for start, end in sorted(spans):
        text = source_text[start:end]
        if not text.strip():
            continue
        token_ids = tuple(
            item.token_id for item in tokens if item.start >= start and item.end <= end
        )
        constituents.append(
            ParserConstituent(
                constituent_id=parser_constituent_id(source_text_sha256, start, end),
                event_id=event_id,
                source_text_sha256=source_text_sha256,
                constituent_range=AttachmentSourceRange(start=start, end=end, text=text),
                token_ids=token_ids,
            )
        )
    return ConstituentCandidateInventory(
        event_id=event_id,
        source_text_sha256=source_text_sha256,
        constituents=tuple(constituents),
    )


class GoldFragmentRef(BaseModel):
    """One corrected Gold fragment measured for exact coverage."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    fragment_id: _FragmentId
    start: Annotated[int, Field(ge=0)]
    end: Annotated[int, Field(gt=0)]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if self.end <= self.start:
            raise ValueError("Gold Fragment reference requires an ordered range.")
        return self


class BoundaryFidelityPartitionCensus(BaseModel):
    """Coverage of corrected Gold fragments by one parser inventory."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    partition_role: Literal["development", "validation"]
    covered_fragment_ids: tuple[_FragmentId, ...]
    missed_fragments: tuple[GoldFragmentRef, ...]
    pool_ceiling: Annotated[float, Field(ge=0.0, le=1.0)]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if self.covered_fragment_ids != tuple(sorted(set(self.covered_fragment_ids))):
            raise ValueError("Covered fragment IDs must be ordered and distinct.")
        if self.missed_fragments != tuple(
            sorted(self.missed_fragments, key=lambda item: item.fragment_id)
        ):
            raise ValueError("Missed fragments must use fragment ID order.")
        if set(self.covered_fragment_ids) & {item.fragment_id for item in self.missed_fragments}:
            raise ValueError("A fragment cannot be both covered and missed.")
        total = len(self.covered_fragment_ids) + len(self.missed_fragments)
        expected = (len(self.covered_fragment_ids) / total) if total else 1.0
        if abs(self.pool_ceiling - expected) > 1e-12:
            raise ValueError("Constituent Pool Ceiling drifted from coverage.")
        return self


def build_boundary_fidelity_census(
    *,
    partition_role: Literal["development", "validation"],
    inventories: dict[str, ConstituentCandidateInventory],
    gold_fragments: dict[str, tuple[GoldFragmentRef, ...]],
) -> BoundaryFidelityPartitionCensus:
    """Classify every corrected Gold fragment as covered or missed by exact span."""
    if set(inventories) != set(gold_fragments):
        raise ValueError("Fidelity census requires one inventory per Gold Event.")
    covered: list[str] = []
    missed: list[GoldFragmentRef] = []
    for event_id, fragments in gold_fragments.items():
        spans = {
            (item.constituent_range.start, item.constituent_range.end)
            for item in inventories[event_id].constituents
        }
        for fragment in fragments:
            if (fragment.start, fragment.end) in spans:
                covered.append(fragment.fragment_id)
            else:
                missed.append(fragment)
    total = len(covered) + len(missed)
    ceiling = (len(covered) / total) if total else 1.0
    return BoundaryFidelityPartitionCensus(
        partition_role=partition_role,
        covered_fragment_ids=tuple(sorted(covered)),
        missed_fragments=tuple(sorted(missed, key=lambda item: item.fragment_id)),
        pool_ceiling=ceiling,
    )


def constituent_selection_labels(
    inventory: ConstituentCandidateInventory,
) -> tuple[str, ...]:
    """Return the ordered ``C1..C<n>`` labels for one inventory."""
    return tuple(f"C{ordinal}" for ordinal in range(1, len(inventory.constituents) + 1))


def render_constituent_selection_task(
    *,
    inventory: ConstituentCandidateInventory,
    source_text: str,
    event_literal: str,
) -> ConstituentSelectionTask:
    """Render one finite selection task without exposing a candidate boundary."""
    if hashlib.sha256(source_text.encode()).hexdigest() != inventory.source_text_sha256:
        raise ValueError("Selection renderer source digest does not match the inventory.")
    if source_text.count(event_literal) != 1:
        raise ValueError("Selection renderer requires one unique Event literal.")
    labels = constituent_selection_labels(inventory)
    lines = [
        "Return a comma-separated subset of the Candidate labels, or NONE.",
        f"Event: {event_literal}",
        "Passage:",
        source_text,
        "Candidates:",
    ]
    for label, constituent in zip(labels, inventory.constituents, strict=True):
        lines.append(f"{label}: {constituent.constituent_range.text}")
    rendered = "\n".join(lines)
    return ConstituentSelectionTask(
        event_id=inventory.event_id,
        source_text_sha256=inventory.source_text_sha256,
        source_text=source_text,
        constituent_labels=labels,
        rendered_input=rendered,
        rendered_input_sha256=hashlib.sha256(rendered.encode()).hexdigest(),
    )


def parse_constituent_selection_answer(
    *,
    raw_answer: str,
    task: ConstituentSelectionTask,
) -> ConstituentSelectionAnswer:
    """Parse one finite model answer into a subset, NONE, or a rejection."""
    return parse_constituent_selection_answer_labels(
        event_id=task.event_id,
        raw_answer=raw_answer,
        constituent_labels=task.constituent_labels,
    )


def parse_constituent_selection_answer_labels(
    *,
    event_id: str,
    raw_answer: str,
    constituent_labels: tuple[str, ...],
) -> ConstituentSelectionAnswer:
    """Parse one finite answer against an ordered constituent label set."""
    tokens = tuple(item.strip() for item in raw_answer.split(",") if item.strip())
    if tokens == ("NONE",):
        return ConstituentSelectionAnswer(
            event_id=event_id,
            status=ConstituentSelectionStatus.NONE,
            selected_label_indexes=(),
        )
    valid = set(constituent_labels)
    if not tokens or any(item not in valid for item in tokens):
        return ConstituentSelectionAnswer(
            event_id=event_id,
            status=ConstituentSelectionStatus.REJECTED,
            selected_label_indexes=(),
        )
    indexes = tuple(sorted({constituent_labels.index(item) + 1 for item in tokens}))
    return ConstituentSelectionAnswer(
        event_id=event_id,
        status=ConstituentSelectionStatus.SELECTED,
        selected_label_indexes=indexes,
    )


def parse_constituent_selection_answers(
    *,
    answers: Mapping[str, str],
    inventories_by_event: Mapping[str, ConstituentCandidateInventory],
) -> tuple[ConstituentSelectionAnswer, ...]:
    """Parse raw ``answers.jsonl`` records into typed selection answers.

    ``answers`` maps one ``event_id`` to its raw finite answer string.  Each
    inventory supplies the ordered constituent labels the parser validates
    against.  Every inventory Event must be answered exactly once.
    """
    if set(answers) != set(inventories_by_event):
        raise ValueError("R3 answers.jsonl must cover every inventory Event exactly once.")
    parsed: list[ConstituentSelectionAnswer] = []
    for event_id in sorted(inventories_by_event):
        inventory = inventories_by_event[event_id]
        parsed.append(
            parse_constituent_selection_answer_labels(
                event_id=event_id,
                raw_answer=answers[event_id],
                constituent_labels=constituent_selection_labels(inventory),
            )
        )
    return tuple(parsed)


def selected_constituent_spans(
    *,
    answer: ConstituentSelectionAnswer,
    inventory: ConstituentCandidateInventory,
) -> tuple[AttachmentSourceRange, ...]:
    """Return the exact spans one parsed answer selects."""
    if answer.status is not ConstituentSelectionStatus.SELECTED:
        return ()
    return tuple(
        inventory.constituents[index - 1].constituent_range
        for index in answer.selected_label_indexes
    )


def corrected_gold_attachment_spans(
    corrected: CorrectedAttachmentGold,
) -> dict[str, tuple[tuple[int, int], ...]]:
    """Return every Event's corrected Gold Attachment Set as ordered exact spans."""
    spans_by_event: dict[str, set[tuple[int, int]]] = {}
    for label in corrected.corrected_labels:
        span = (label.source_range.start, label.source_range.end)
        for event_id in label.gold_event_ids:
            spans_by_event.setdefault(event_id, set()).add(span)
    return {event_id: tuple(sorted(spans)) for event_id, spans in sorted(spans_by_event.items())}


class ConstituentSelectionCensus(BaseModel):
    """One partition's finite selections scored against the corrected Gold Attachment Set."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    partition_role: Literal["development", "validation"]
    event_count: Annotated[int, Field(ge=0)]
    selected_event_count: Annotated[int, Field(ge=0)]
    none_event_count: Annotated[int, Field(ge=0)]
    rejected_event_count: Annotated[int, Field(ge=0)]
    exact_attachment_count: Annotated[int, Field(ge=0)]
    gold_attachment_span_count: Annotated[int, Field(ge=0)]
    false_positive_span_count: Annotated[int, Field(ge=0)]
    false_negative_span_count: Annotated[int, Field(ge=0)]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if self.event_count != (
            self.selected_event_count + self.none_event_count + self.rejected_event_count
        ):
            raise ValueError("Selection census Event counts drifted.")
        return self


class ConstituentSelectionReport(BaseModel):
    """Complete R3 report: both fidelity censuses, both selection censuses, one fingerprint."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["constituent_selection_report_v1"] = "constituent_selection_report_v1"
    development_fidelity: BoundaryFidelityPartitionCensus
    validation_fidelity: BoundaryFidelityPartitionCensus
    development_selection: ConstituentSelectionCensus
    validation_selection: ConstituentSelectionCensus
    corrected_gold_sha256: Annotated[str, Field(pattern=_SHA256)]
    model_execution_count: Annotated[int, Field(ge=0)]
    canonical_write_count: Literal[0] = 0
    proposed_change_count: Literal[0] = 0
    result_fingerprint: Annotated[str, Field(pattern=_SHA256)]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if self.development_fidelity.partition_role != "development":
            raise ValueError("Development fidelity census role drifted.")
        if self.validation_fidelity.partition_role != "validation":
            raise ValueError("Validation fidelity census role drifted.")
        if self.development_selection.partition_role != "development":
            raise ValueError("Development selection census role drifted.")
        if self.validation_selection.partition_role != "validation":
            raise ValueError("Validation selection census role drifted.")
        if self.result_fingerprint != constituent_selection_report_fingerprint(self):
            raise ValueError("Constituent Selection Report fingerprint drifted.")
        return self


def build_constituent_selection_census(
    *,
    partition_role: Literal["development", "validation"],
    answers: Mapping[str, ConstituentSelectionAnswer],
    inventories: Mapping[str, ConstituentCandidateInventory],
    gold_attachment_spans: Mapping[str, tuple[tuple[int, int], ...]],
) -> ConstituentSelectionCensus:
    """Aggregate one partition's selections against the corrected Gold Attachment Set."""
    event_ids = tuple(sorted(answers))
    if set(answers) != set(inventories):
        raise ValueError("Selection census requires one inventory per answered Event.")
    for event_id in event_ids:
        if inventories[event_id].event_id != event_id or answers[event_id].event_id != event_id:
            raise ValueError("Selection census contains an Event ID mismatch.")
    exact_attachment_count = 0
    gold_attachment_span_count = 0
    false_positive_span_count = 0
    false_negative_span_count = 0
    selected_count = 0
    none_count = 0
    rejected_count = 0
    for event_id in event_ids:
        answer = answers[event_id]
        if answer.status is ConstituentSelectionStatus.SELECTED:
            selected_count += 1
        elif answer.status is ConstituentSelectionStatus.NONE:
            none_count += 1
        else:
            rejected_count += 1
        selected = {
            (item.start, item.end)
            for item in selected_constituent_spans(answer=answer, inventory=inventories[event_id])
        }
        gold = set(gold_attachment_spans.get(event_id, ()))
        gold_attachment_span_count += len(gold)
        exact_attachment_count += len(selected & gold)
        false_positive_span_count += len(selected - gold)
        false_negative_span_count += len(gold - selected)
    return ConstituentSelectionCensus(
        partition_role=partition_role,
        event_count=len(event_ids),
        selected_event_count=selected_count,
        none_event_count=none_count,
        rejected_event_count=rejected_count,
        exact_attachment_count=exact_attachment_count,
        gold_attachment_span_count=gold_attachment_span_count,
        false_positive_span_count=false_positive_span_count,
        false_negative_span_count=false_negative_span_count,
    )


def build_constituent_selection_report(
    *,
    development_fidelity: BoundaryFidelityPartitionCensus,
    validation_fidelity: BoundaryFidelityPartitionCensus,
    development_selection: ConstituentSelectionCensus,
    validation_selection: ConstituentSelectionCensus,
    corrected_gold_sha256: str,
    model_execution_count: int,
) -> ConstituentSelectionReport:
    """Assemble the complete R3 report and seal it with a semantic fingerprint."""
    draft = ConstituentSelectionReport.model_construct(
        development_fidelity=development_fidelity,
        validation_fidelity=validation_fidelity,
        development_selection=development_selection,
        validation_selection=validation_selection,
        corrected_gold_sha256=corrected_gold_sha256,
        model_execution_count=model_execution_count,
        result_fingerprint="0" * 64,
    )
    return ConstituentSelectionReport(
        **draft.model_dump(exclude={"result_fingerprint"}),
        result_fingerprint=constituent_selection_report_fingerprint(draft),
    )


def constituent_selection_report_fingerprint(value: BaseModel | dict[str, object]) -> str:
    """Return the semantic digest of one Constituent Selection Report."""
    if isinstance(value, BaseModel):
        payload: object = value.model_dump(mode="json", exclude={"result_fingerprint"})
    else:
        payload = {key: item for key, item in value.items() if key != "result_fingerprint"}
    return hashlib.sha256(
        json.dumps(
            payload,
            allow_nan=False,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
