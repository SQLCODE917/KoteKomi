"""Deterministic dependency-path attachment routing for the R1 deliverable.

The router maps one Attachment Candidate to exactly one Route Decision
(``attached``, ``not-attached``, or ``model-review``) without invoking a model
and without reading Attachment Gold.  It reuses the pinned dependency evidence
from :class:`AttachmentSyntaxObservation` and the canonical bounded syntax
policies from :mod:`kotekomi_application.competitive_attachment_selection`.

Routing rules, applied in order:

1. NONE rule -- a candidate with no dependency path to any Event in its
   Competing Event Set routes ``not-attached``.
2. Distance-one rule -- a candidate structurally supported at dependency
   distance one against an Event routes ``attached`` under policy ``path_1``.
3. Complement rule -- a candidate inside a direct governed complement subtree
   of a reporting Event routes ``attached`` under
   ``path_unbounded_plus_complement``.
4. Every remaining candidate routes ``model-review``.

Gold enters only the report-level accounting (net counts, the NONE
confusion matrix, the error-class census, and the oracle ceilings) after the
route decisions are fixed, which the package contract permits.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from kotekomi_application.competitive_attachment_review_verification import (
    AttachmentSyntaxObservation,
)
from kotekomi_application.competitive_attachment_selection import (
    AttachmentOracleCeilingKind,
    AttachmentSyntaxPolicy,
    governed_complement_scope_supports,
    syntax_policy_supports,
)
from kotekomi_application.event_entity_predicate_arguments import (
    PredicateArgumentHypothesis,
)

_SHA256 = r"^[a-f0-9]{64}$"
type _EventId = Annotated[str, Field(pattern=r"^sge_[a-f0-9]{24}$")]
type _CandidateId = Annotated[str, Field(pattern=r"^cac_[a-f0-9]{24}$")]

# The two bounded syntax policies the deterministic route is allowed to select.
_ROUTE_PATH_POLICY = AttachmentSyntaxPolicy(
    policy_id="path_1",
    maximum_path_length=1,
    governed_complement_scope=False,
)
_ROUTE_COMPLEMENT_POLICY_ID = "path_unbounded_plus_complement"


class AttachmentPartitionRole(StrEnum):
    """The declared role of one frozen Source-Grounded Proposition partition."""

    DEVELOPMENT = "development"
    VALIDATION = "validation"
    HELD_OUT = "held_out"


class AttachmentRouteKind(StrEnum):
    """One model-free Route Decision assigned to an Attachment Candidate."""

    ATTACHED = "attached"
    NOT_ATTACHED = "not_attached"
    MODEL_REVIEW = "model_review"


class AttachmentNoneClassification(StrEnum):
    """Gold-derived label for one ``not-attached`` Route Decision."""

    TRUE_NONE = "true_none"
    FALSE_NONE = "false_none"


class AttachmentErrorClass(StrEnum):
    """One counted error class from the post-routing census."""

    NONE = "none"
    MIXED = "mixed"
    TEMPORAL = "temporal"


class AttachmentRouteDecision(BaseModel):
    """One model-free Route Decision plus the Events that decision allows."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    candidate_id: _CandidateId
    partition_role: AttachmentPartitionRole
    informing_partition: Literal["development", "validation"] | None
    route_kind: AttachmentRouteKind
    allowed_event_ids: tuple[_EventId, ...]
    selected_policy: Annotated[
        str,
        Field(pattern=r"^path_(?:1|unbounded_plus_complement)$"),
    ] | None
    path_1_supported: bool
    trigger_containment: bool

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if self.allowed_event_ids != tuple(
            sorted(self.allowed_event_ids)
        ) or len(set(self.allowed_event_ids)) != len(self.allowed_event_ids):
            raise ValueError("Route decision Event IDs must be ordered and distinct.")
        if self.route_kind is AttachmentRouteKind.ATTACHED:
            if not self.allowed_event_ids or self.selected_policy is None:
                raise ValueError("An attached decision requires allowed Events and a policy.")
        elif self.route_kind in (
            AttachmentRouteKind.NOT_ATTACHED,
            AttachmentRouteKind.MODEL_REVIEW,
        ):
            if self.allowed_event_ids or self.selected_policy is not None:
                raise ValueError(
                    "A non-attached decision must not name allowed Events or a policy."
                )
        if self.partition_role is AttachmentPartitionRole.HELD_OUT:
            if self.informing_partition is not None:
                raise ValueError("The held-out partition never informs a route decision.")
        elif self.informing_partition != self.partition_role.value:
            raise ValueError("Route decision informing partition drifted from its role.")
        return self


class AttachmentNoneDecision(BaseModel):
    """One classified ``not-attached`` decision and its Gold-derived flags."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    candidate_id: _CandidateId
    none_classification: AttachmentNoneClassification
    trigger_containment: bool
    gold_temporal: bool

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if self.none_classification is AttachmentNoneClassification.TRUE_NONE and (
            self.gold_temporal
        ):
            raise ValueError("A true-NONE decision cannot contain a temporal Gold fragment.")
        return self


class NoneConfusionMatrix(BaseModel):
    """Two-by-two Syntax-Empty against Gold-NONE count for one partition."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    partition_role: Literal["development", "validation"]
    syntax_empty_gold_none: Annotated[int, Field(ge=0)]
    syntax_empty_gold_attached: Annotated[int, Field(ge=0)]
    syntax_reachable_gold_none: Annotated[int, Field(ge=0)]
    syntax_reachable_gold_attached: Annotated[int, Field(ge=0)]
    false_none_rate: Annotated[float, Field(ge=0, le=1)]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        denominator = self.syntax_empty_gold_none + self.syntax_empty_gold_attached
        expected = 1.0 if denominator == 0 else self.syntax_empty_gold_attached / denominator
        if self.false_none_rate != expected:
            raise ValueError("None confusion matrix false-NONE rate drifted from its counts.")
        return self


class AttachmentRouteErrorCensus(BaseModel):
    """Post-routing error-class counts and flagged candidate lists."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    partition_role: Literal["development", "validation"]
    none_count: Annotated[int, Field(ge=0)]
    mixed_count: Annotated[int, Field(ge=0)]
    temporal_count: Annotated[int, Field(ge=0)]
    mixed_attached_candidate_ids: tuple[_CandidateId, ...]
    false_none_temporal_candidate_ids: tuple[_CandidateId, ...]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        _ordered_distinct("mixed attached candidate IDs", self.mixed_attached_candidate_ids)
        _ordered_distinct(
            "false-NONE temporal candidate IDs",
            self.false_none_temporal_candidate_ids,
        )
        return self


class AttachmentRouteCeiling(BaseModel):
    """One Gold-dependent, non-deployable upper bound over a dependency distance."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    partition_role: Literal["development", "validation"]
    kind: AttachmentOracleCeilingKind
    policy_id: Annotated[str, Field(min_length=1)]
    reachable_count: Annotated[int, Field(ge=0)]
    gold_count: Annotated[int, Field(ge=0)]
    ceiling: Annotated[float, Field(ge=0, le=1)]
    deployable: Literal[False] = False

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        expected = 1.0 if self.gold_count == 0 else self.reachable_count / self.gold_count
        if self.ceiling != expected:
            raise ValueError("Route ceiling value drifted from its reachable and Gold counts.")
        return self


class AttachmentRoutePartitionReport(BaseModel):
    """One partition of route decisions, net counts, and error census."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    partition_role: Literal["development", "validation"]
    decisions: tuple[AttachmentRouteDecision, ...]
    none_confusion_matrix: NoneConfusionMatrix
    none_decisions: tuple[AttachmentNoneDecision, ...]
    error_census: AttachmentRouteErrorCensus
    exact_set_count: Annotated[int, Field(ge=0)]
    exact_set_score: Annotated[float, Field(ge=0, le=1)]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if tuple(sorted(self.decisions, key=lambda item: item.candidate_id)) != self.decisions:
            raise ValueError("Partition report decisions must use canonical candidate order.")
        if any(item.partition_role.value != self.partition_role for item in self.decisions):
            raise ValueError("Partition report contains a foreign route decision.")
        total = (
            self.none_confusion_matrix.syntax_empty_gold_none
            + self.none_confusion_matrix.syntax_empty_gold_attached
            + self.none_confusion_matrix.syntax_reachable_gold_none
            + self.none_confusion_matrix.syntax_reachable_gold_attached
        )
        if total != len(self.decisions):
            raise ValueError("None confusion matrix does not account for every decision.")
        if self.none_confusion_matrix.partition_role != self.partition_role:
            raise ValueError("None confusion matrix partition role drifted.")
        if self.error_census.partition_role != self.partition_role:
            raise ValueError("Error census partition role drifted.")
        resolved_count = sum(
            item.route_kind is not AttachmentRouteKind.MODEL_REVIEW for item in self.decisions
        )
        if self.exact_set_count > resolved_count:
            raise ValueError("Exact-set count exceeds the resolved decision count.")
        expected_score = 1.0 if resolved_count == 0 else self.exact_set_count / resolved_count
        if self.exact_set_score != expected_score:
            raise ValueError("Partition exact-set score drifted from its count.")
        return self


class AttachmentRouteReport(BaseModel):
    """Complete R1 route report with evidence-budget counters and fingerprint."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["attachment_route_report_v1"] = "attachment_route_report_v1"
    partitions: tuple[AttachmentRoutePartitionReport, AttachmentRoutePartitionReport]
    ceilings: tuple[AttachmentRouteCeiling, ...]
    model_execution_count: Literal[0] = 0
    canonical_write_count: Literal[0] = 0
    result_fingerprint: Annotated[str, Field(pattern=_SHA256)]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if tuple(item.partition_role for item in self.partitions) != (
            "development",
            "validation",
        ):
            raise ValueError("Route report requires development then validation partitions.")
        if any(
            item.partition_role not in {"development", "validation"}
            for item in self.ceilings
        ):
            raise ValueError("Route report contains a held-out or foreign ceiling.")
        if self.result_fingerprint != attachment_route_report_fingerprint(self):
            raise ValueError("Route report fingerprint drifted.")
        return self


def attachment_observation_has_path(observation: AttachmentSyntaxObservation) -> bool:
    """Return whether one observation carries a dependency path to its Event."""
    if observation.own_event_expression:
        return True
    return observation.hypothesis is not PredicateArgumentHypothesis.DIAGNOSTIC_GAP and (
        observation.hypothesis is not PredicateArgumentHypothesis.DIFFERENT_SENTENCE
    )


def attachment_candidate_is_syntax_empty(
    observations: tuple[AttachmentSyntaxObservation, ...],
) -> bool:
    """Return whether a candidate reaches no Event through any dependency path."""
    return not any(attachment_observation_has_path(item) for item in observations)


def attachment_distance_one_event_ids(
    observations: tuple[AttachmentSyntaxObservation, ...],
) -> tuple[str, ...]:
    """Return the ordered Event IDs a candidate reaches at dependency distance one."""
    return tuple(
        sorted(
            {
                observation.source_grounded_event_id
                for observation in observations
                if syntax_policy_supports(observation, _ROUTE_PATH_POLICY)
            }
        )
    )


def attachment_complement_event_ids(
    observations: tuple[AttachmentSyntaxObservation, ...],
) -> tuple[str, ...]:
    """Return the ordered Event IDs a candidate reaches through a governed complement."""
    return tuple(
        sorted(
            {
                observation.source_grounded_event_id
                for observation in observations
                if governed_complement_scope_supports(observation)
            }
        )
    )


def build_attachment_route_decision(
    *,
    candidate_id: str,
    partition_role: AttachmentPartitionRole,
    observations: tuple[AttachmentSyntaxObservation, ...],
    trigger_containment: bool = False,
) -> AttachmentRouteDecision:
    """Compute one model-free Route Decision for a candidate without reading Gold."""
    if partition_role is AttachmentPartitionRole.HELD_OUT:
        raise ValueError("The held-out partition is reserved and never routed.")
    if not observations:
        raise ValueError("Route decision requires at least one competing Event observation.")
    if any(item.candidate_id != candidate_id for item in observations):
        raise ValueError("Route decision observations reference a foreign candidate.")
    if any(item.phase != partition_role.value for item in observations):
        raise ValueError("Route decision observations drifted from their partition phase.")
    event_ids = tuple(observation.source_grounded_event_id for observation in observations)
    if len(set(event_ids)) != len(event_ids):
        raise ValueError("Route decision competing Event IDs must be distinct.")

    path_1_ids = attachment_distance_one_event_ids(observations)
    complement_ids = attachment_complement_event_ids(observations)

    if attachment_candidate_is_syntax_empty(observations):
        route_kind = AttachmentRouteKind.NOT_ATTACHED
        selected_policy = None
        allowed = ()
    elif path_1_ids:
        route_kind = AttachmentRouteKind.ATTACHED
        selected_policy = _ROUTE_PATH_POLICY.policy_id
        allowed = path_1_ids
    elif complement_ids:
        route_kind = AttachmentRouteKind.ATTACHED
        selected_policy = _ROUTE_COMPLEMENT_POLICY_ID
        allowed = complement_ids
    else:
        route_kind = AttachmentRouteKind.MODEL_REVIEW
        selected_policy = None
        allowed = ()

    return AttachmentRouteDecision(
        candidate_id=candidate_id,
        partition_role=partition_role,
        informing_partition=partition_role.value,
        route_kind=route_kind,
        allowed_event_ids=allowed,
        selected_policy=selected_policy,
        path_1_supported=bool(path_1_ids),
        trigger_containment=trigger_containment,
    )


def classify_none_decision(
    gold_event_ids: tuple[str, ...],
) -> AttachmentNoneClassification:
    """Label one ``not-attached`` decision true-NONE or false-NONE from Gold."""
    return (
        AttachmentNoneClassification.TRUE_NONE
        if not gold_event_ids
        else AttachmentNoneClassification.FALSE_NONE
    )


def build_none_decisions(
    *,
    decisions: tuple[AttachmentRouteDecision, ...],
    gold_attachment: Mapping[str, tuple[str, ...]],
    gold_temporal: Mapping[str, bool],
) -> tuple[AttachmentNoneDecision, ...]:
    """Classify every ``not-attached`` decision against Gold."""
    result: list[AttachmentNoneDecision] = []
    for decision in decisions:
        if decision.route_kind is not AttachmentRouteKind.NOT_ATTACHED:
            continue
        gold_ids = tuple(sorted(gold_attachment.get(decision.candidate_id, ())))
        result.append(
            AttachmentNoneDecision(
                candidate_id=decision.candidate_id,
                none_classification=classify_none_decision(gold_ids),
                trigger_containment=decision.trigger_containment,
                gold_temporal=bool(gold_temporal.get(decision.candidate_id, False)),
            )
        )
    return tuple(result)


def build_none_confusion_matrix(
    *,
    partition_role: Literal["development", "validation"],
    decisions: tuple[AttachmentRouteDecision, ...],
    gold_attachment: Mapping[str, tuple[str, ...]],
) -> NoneConfusionMatrix:
    """Compute the two-by-two Syntax-Empty against Gold-NONE counts."""
    empty_gold_none = 0
    empty_gold_attached = 0
    reachable_gold_none = 0
    reachable_gold_attached = 0
    for decision in decisions:
        gold_empty = not gold_attachment.get(decision.candidate_id, ())
        if decision.route_kind is AttachmentRouteKind.NOT_ATTACHED:
            if gold_empty:
                empty_gold_none += 1
            else:
                empty_gold_attached += 1
        elif gold_empty:
            reachable_gold_none += 1
        else:
            reachable_gold_attached += 1
    denominator = empty_gold_none + empty_gold_attached
    return NoneConfusionMatrix(
        partition_role=partition_role,
        syntax_empty_gold_none=empty_gold_none,
        syntax_empty_gold_attached=empty_gold_attached,
        syntax_reachable_gold_none=reachable_gold_none,
        syntax_reachable_gold_attached=reachable_gold_attached,
        false_none_rate=1.0 if denominator == 0 else empty_gold_attached / denominator,
    )


def classify_error_class(
    *,
    gold_is_empty: bool,
    gold_mixed: bool,
    gold_temporal: bool,
) -> AttachmentErrorClass | None:
    """Classify one candidate's Gold into exactly one counted error class."""
    if gold_is_empty:
        return AttachmentErrorClass.NONE
    if gold_temporal:
        return AttachmentErrorClass.TEMPORAL
    if gold_mixed:
        return AttachmentErrorClass.MIXED
    return None


def build_error_census(
    *,
    partition_role: Literal["development", "validation"],
    decisions: tuple[AttachmentRouteDecision, ...],
    gold_attachment: Mapping[str, tuple[str, ...]],
    gold_mixed: Mapping[str, bool],
    gold_temporal: Mapping[str, bool],
) -> AttachmentRouteErrorCensus:
    """Count the ``none``, ``mixed``, and ``temporal`` classes and flag error lists."""
    none_count = 0
    mixed_count = 0
    temporal_count = 0
    mixed_attached: list[str] = []
    false_none_temporal: list[str] = []
    for decision in decisions:
        gold_empty = not gold_attachment.get(decision.candidate_id, ())
        error_class = classify_error_class(
            gold_is_empty=gold_empty,
            gold_mixed=bool(gold_mixed.get(decision.candidate_id, False)),
            gold_temporal=bool(gold_temporal.get(decision.candidate_id, False)),
        )
        if error_class is AttachmentErrorClass.NONE:
            none_count += 1
        elif error_class is AttachmentErrorClass.MIXED:
            mixed_count += 1
        elif error_class is AttachmentErrorClass.TEMPORAL:
            temporal_count += 1
        if error_class is AttachmentErrorClass.MIXED and (
            decision.route_kind is AttachmentRouteKind.ATTACHED
        ):
            mixed_attached.append(decision.candidate_id)
        if (
            decision.route_kind is AttachmentRouteKind.NOT_ATTACHED
            and not gold_empty
            and bool(gold_temporal.get(decision.candidate_id, False))
        ):
            false_none_temporal.append(decision.candidate_id)
    return AttachmentRouteErrorCensus(
        partition_role=partition_role,
        none_count=none_count,
        mixed_count=mixed_count,
        temporal_count=temporal_count,
        mixed_attached_candidate_ids=tuple(sorted(mixed_attached)),
        false_none_temporal_candidate_ids=tuple(sorted(false_none_temporal)),
    )


def build_route_ceiling(
    *,
    partition_role: Literal["development", "validation"],
    kind: AttachmentOracleCeilingKind,
    policy_id: str,
    reachable_count: int,
    gold_count: int,
) -> AttachmentRouteCeiling:
    """Build one Gold-dependent route ceiling from its recomputed counts."""
    return AttachmentRouteCeiling(
        partition_role=partition_role,
        kind=kind,
        policy_id=policy_id,
        reachable_count=reachable_count,
        gold_count=gold_count,
        ceiling=1.0 if gold_count == 0 else reachable_count / gold_count,
    )


def build_route_partition_report(
    *,
    partition_role: Literal["development", "validation"],
    decisions: tuple[AttachmentRouteDecision, ...],
    gold_attachment: Mapping[str, tuple[str, ...]],
    gold_mixed: Mapping[str, bool],
    gold_temporal: Mapping[str, bool],
) -> AttachmentRoutePartitionReport:
    """Assemble one partition's decisions, NONE accounting, census, and exact-set score."""
    ordered = tuple(sorted(decisions, key=lambda item: item.candidate_id))
    exact_set_count = 0
    for decision in ordered:
        gold_ids = tuple(sorted(gold_attachment.get(decision.candidate_id, ())))
        if decision.route_kind is not AttachmentRouteKind.MODEL_REVIEW and (
            decision.allowed_event_ids == gold_ids
        ):
            exact_set_count += 1
    resolved_count = sum(
        item.route_kind is not AttachmentRouteKind.MODEL_REVIEW for item in ordered
    )
    return AttachmentRoutePartitionReport(
        partition_role=partition_role,
        decisions=ordered,
        none_confusion_matrix=build_none_confusion_matrix(
            partition_role=partition_role,
            decisions=ordered,
            gold_attachment=gold_attachment,
        ),
        none_decisions=build_none_decisions(
            decisions=ordered,
            gold_attachment=gold_attachment,
            gold_temporal=gold_temporal,
        ),
        error_census=build_error_census(
            partition_role=partition_role,
            decisions=ordered,
            gold_attachment=gold_attachment,
            gold_mixed=gold_mixed,
            gold_temporal=gold_temporal,
        ),
        exact_set_count=exact_set_count,
        exact_set_score=1.0 if resolved_count == 0 else exact_set_count / resolved_count,
    )


def build_attachment_route_report(
    *,
    development: AttachmentRoutePartitionReport,
    validation: AttachmentRoutePartitionReport,
    ceilings: tuple[AttachmentRouteCeiling, ...],
) -> AttachmentRouteReport:
    """Assemble the complete R1 report and seal it with a semantic fingerprint."""
    if development.partition_role != "development":
        raise ValueError("Route report development partition role drifted.")
    if validation.partition_role != "validation":
        raise ValueError("Route report validation partition role drifted.")
    draft = AttachmentRouteReport.model_construct(
        partitions=(development, validation),
        ceilings=ceilings,
        result_fingerprint="0" * 64,
    )
    return AttachmentRouteReport(
        **draft.model_dump(exclude={"result_fingerprint"}),
        result_fingerprint=attachment_route_report_fingerprint(draft),
    )


def attachment_route_report_fingerprint(value: BaseModel | dict[str, object]) -> str:
    """Return the semantic digest of an R1 route report."""
    if isinstance(value, BaseModel):
        payload = value.model_dump(mode="json", exclude={"result_fingerprint"})
    else:
        payload = {key: item for key, item in value.items() if key != "result_fingerprint"}
    return hashlib.sha256(_canonical_json(payload)).hexdigest()


def _ordered_distinct(label: str, values: tuple[str, ...]) -> None:
    if values != tuple(sorted(values)) or len(set(values)) != len(values):
        raise ValueError(f"{label} must be ordered and distinct.")


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()