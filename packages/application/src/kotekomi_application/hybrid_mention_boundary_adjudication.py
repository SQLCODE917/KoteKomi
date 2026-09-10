"""Bounded semantic judgments over preserved mention-boundary candidates."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Annotated, Literal, Protocol, Self, cast

from kotekomi_domain.models import JsonValue
from pydantic import BaseModel, ConfigDict, Field, model_validator

HYBRID_MENTION_BOUNDARY_ADJUDICATION_SCHEMA_ID = "hybrid_mention_boundary_adjudication_text_v1"
HYBRID_MENTION_BOUNDARY_ADJUDICATION_POLICY_ID = "hybrid_mention_boundary_adjudication_v2"
MAX_BOUNDARY_ADJUDICATION_CANDIDATES = 8

_ID_PATTERN = r"^[a-z]+_[a-f0-9]{24}$"
_SHA256_PATTERN = r"^[a-f0-9]{64}$"
_CANDIDATE_LABEL_PATTERN = re.compile(r"c[1-9][0-9]*")


class BoundaryCandidateJudgmentValue(StrEnum):
    """One model-visible semantic boundary choice."""

    COMPLETE = "complete"
    INCOMPLETE = "incomplete"
    UNCLEAR = "unclear"


class MentionBoundaryCandidateStatus(StrEnum):
    """One mapped terminal state for a preserved candidate."""

    COMPLETE = "complete"
    INCOMPLETE = "incomplete"
    UNCLEAR = "unclear"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True)
class BoundaryCandidateJudgment:
    """One parsed model judgment with its exact output-line location."""

    candidate_label: str
    judgment: BoundaryCandidateJudgmentValue
    line_number: int
    line: str


@dataclass(frozen=True)
class BoundaryCandidateJudgmentLineRejection:
    """One independently rejected model-output line."""

    line_number: int
    line: str
    code: str


@dataclass(frozen=True)
class BoundaryCandidateJudgmentBatch:
    """Valid model judgments and independently retained line rejections."""

    judgments: tuple[BoundaryCandidateJudgment, ...]
    rejections: tuple[BoundaryCandidateJudgmentLineRejection, ...] = ()


class MentionBoundaryAdjudicationLineRejection(BaseModel):
    """One source-preserving rejected line in mapped adjudication evidence."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    line_number: Annotated[int, Field(gt=0)]
    line: str
    code: Annotated[str, Field(min_length=1)]


class MentionBoundaryAdjudicationJudgment(BaseModel):
    """One task-local judgment mapped to a preserved MentionCandidate."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    candidate_id: Annotated[str, Field(pattern=_ID_PATTERN)]
    status: MentionBoundaryCandidateStatus


class MentionBoundaryAdjudication(BaseModel):
    """Derived evidence for one ambiguous overlap component."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["mention_boundary_adjudication_v1"] = "mention_boundary_adjudication_v1"
    id: Annotated[str, Field(pattern=r"^mba_[a-f0-9]{24}$")]
    boundary_decision_id: Annotated[str, Field(pattern=r"^mbd_[a-f0-9]{24}$")]
    source_segment_id: Annotated[str, Field(min_length=1)]
    source_text_sha256: Annotated[str, Field(pattern=_SHA256_PATTERN)]
    judgments: tuple[MentionBoundaryAdjudicationJudgment, ...]
    rejected_lines: tuple[MentionBoundaryAdjudicationLineRejection, ...] = ()
    extraction_task_id: Annotated[str, Field(min_length=1)]
    model_run_id: Annotated[str, Field(min_length=1)]
    trace_id: Annotated[str, Field(pattern=r"^xst_[a-f0-9]{24}$")]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        candidate_ids = tuple(item.candidate_id for item in self.judgments)
        if not candidate_ids or len(set(candidate_ids)) != len(candidate_ids):
            raise ValueError(
                "MentionBoundaryAdjudication judgments must be non-empty and distinct."
            )
        line_numbers = tuple(item.line_number for item in self.rejected_lines)
        if tuple(sorted(line_numbers)) != line_numbers:
            raise ValueError("MentionBoundaryAdjudication rejected lines must use output order.")
        if self.id != _adjudication_id(self.model_dump(mode="json", exclude={"id"})):
            raise ValueError("MentionBoundaryAdjudication ID does not match its contents.")
        return self


class BoundaryDecisionView(Protocol):
    """Minimum deterministic decision shape used by effective-candidate routing."""

    id: str
    candidate_ids: tuple[str, ...]
    selected_candidate_ids: tuple[str, ...]


def parse_boundary_candidate_judgments(
    raw_output: bytes,
) -> BoundaryCandidateJudgmentBatch:
    """Parse each candidate judgment independently and preserve every rejected line."""
    try:
        text = raw_output.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError("Boundary adjudication output must be UTF-8 text.") from error
    lines = text.splitlines()
    if not lines:
        raise ValueError("Boundary adjudication output requires at least one line.")
    judgments_by_label: dict[str, list[BoundaryCandidateJudgment]] = {}
    rejections: list[BoundaryCandidateJudgmentLineRejection] = []
    for line_number, line in enumerate(lines, start=1):
        try:
            judgment = _parse_boundary_candidate_judgment(line_number, line)
        except ValueError as error:
            rejections.append(BoundaryCandidateJudgmentLineRejection(line_number, line, str(error)))
            continue
        judgments_by_label.setdefault(judgment.candidate_label, []).append(judgment)
    judgments: list[BoundaryCandidateJudgment] = []
    for grouped in judgments_by_label.values():
        if len(grouped) == 1:
            judgments.extend(grouped)
            continue
        rejections.extend(
            BoundaryCandidateJudgmentLineRejection(
                item.line_number,
                item.line,
                "duplicate_candidate_label",
            )
            for item in grouped
        )
    return BoundaryCandidateJudgmentBatch(
        tuple(sorted(judgments, key=lambda item: item.line_number)),
        tuple(sorted(rejections, key=lambda item: item.line_number)),
    )


def boundary_candidate_judgment_schema_bytes() -> bytes:
    """Return the pinned line-oriented output contract."""
    return b"<supplied cN> | <complete|incomplete|unclear>\n"


def build_mention_boundary_adjudication(**values: object) -> MentionBoundaryAdjudication:
    """Construct one canonical mapped adjudication record."""
    payload = dict(values)
    payload.setdefault("schema_version", "mention_boundary_adjudication_v1")
    payload.setdefault("rejected_lines", ())
    json_payload = cast(dict[str, JsonValue], _json_copy(payload))
    json_payload["id"] = _adjudication_id(json_payload)
    return MentionBoundaryAdjudication.model_validate_json(_canonical_json(json_payload))


def effective_mention_candidate_ids(
    boundary_decisions: tuple[BoundaryDecisionView, ...],
    adjudications: tuple[MentionBoundaryAdjudication, ...],
) -> tuple[str, ...]:
    """Derive the only candidate identity set that downstream stages can consume."""
    decision_ids = {item.id for item in boundary_decisions}
    adjudication_by_decision: dict[str, MentionBoundaryAdjudication] = {}
    effective = {
        candidate_id
        for decision in boundary_decisions
        for candidate_id in decision.selected_candidate_ids
    }
    for adjudication in adjudications:
        if adjudication.boundary_decision_id not in decision_ids:
            raise ValueError("Boundary adjudication references an unknown decision.")
        if adjudication.boundary_decision_id in adjudication_by_decision:
            raise ValueError("Boundary decision has more than one adjudication.")
        adjudication_by_decision[adjudication.boundary_decision_id] = adjudication
        effective.update(
            item.candidate_id
            for item in adjudication.judgments
            if item.status is MentionBoundaryCandidateStatus.COMPLETE
        )
    return tuple(sorted(effective))


def unresolved_mention_candidate_ids(
    boundary_decisions: tuple[BoundaryDecisionView, ...],
    adjudications: tuple[MentionBoundaryAdjudication, ...],
) -> tuple[str, ...]:
    """Derive candidates whose ambiguous boundary still lacks a terminal judgment."""
    adjudication_by_decision = {item.boundary_decision_id: item for item in adjudications}
    unresolved: set[str] = set()
    for decision in boundary_decisions:
        if decision.selected_candidate_ids:
            continue
        adjudication = adjudication_by_decision.get(decision.id)
        if adjudication is None:
            unresolved.update(decision.candidate_ids)
            continue
        unresolved.update(
            item.candidate_id
            for item in adjudication.judgments
            if item.status
            in {
                MentionBoundaryCandidateStatus.UNCLEAR,
                MentionBoundaryCandidateStatus.UNRESOLVED,
            }
        )
    return tuple(sorted(unresolved))


def _parse_boundary_candidate_judgment(
    line_number: int,
    line: str,
) -> BoundaryCandidateJudgment:
    if not line or line != line.strip():
        raise ValueError("untrimmed_or_empty_line")
    parts = line.split(" | ")
    if len(parts) != 2:
        raise ValueError("invalid_candidate_judgment_shape")
    if parts[0].startswith("candidate") and not parts[0].startswith("candidate: "):
        raise ValueError("invalid_candidate_judgment_shape")
    candidate_label = parts[0].removeprefix("candidate: ")
    if _CANDIDATE_LABEL_PATTERN.fullmatch(candidate_label) is None:
        raise ValueError("invalid_candidate_label")
    try:
        judgment = BoundaryCandidateJudgmentValue(parts[1])
    except ValueError as error:
        raise ValueError("invalid_candidate_judgment") from error
    return BoundaryCandidateJudgment(candidate_label, judgment, line_number, line)


def _adjudication_id(payload: dict[str, JsonValue]) -> str:
    return f"mba_{hashlib.sha256(_canonical_json(payload).encode()).hexdigest()[:24]}"


def _canonical_json(value: JsonValue) -> str:
    try:
        return json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as error:
        raise ValueError("Boundary adjudication values must be finite JSON values.") from error


def _json_copy(value: object) -> JsonValue:
    try:
        encoded = json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=_json_default,
        )
    except (TypeError, ValueError) as error:
        raise ValueError("Boundary adjudication values must be finite JSON values.") from error
    return cast(JsonValue, json.loads(encoded))


def _json_default(value: object) -> object:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, tuple):
        return list(cast(tuple[object, ...], value))
    raise TypeError(f"Unsupported boundary adjudication value: {type(value).__name__}")
