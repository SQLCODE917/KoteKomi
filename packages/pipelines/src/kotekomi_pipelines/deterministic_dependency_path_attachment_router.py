"""Deterministic dependency-path attachment routing for the R1 deliverable.

This Pipeline composes the model-free Application Layer router against the
frozen forty-Event phase split and the pinned Stanza dependency evidence.  It
never executes a model and never changes canonical state.

The router maps one Attachment Candidate to exactly one Route Decision
(``attached``, ``not-attached``, or ``model-review``) without invoking a model.
The Pipeline then compares every Route Decision with Gold at the exact
occurrence, computes the NONE confusion matrix and the diagnostic ceilings, and
computes the error-class census.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

from kotekomi_application import (
    AttachmentOracleCeilingKind,
    AttachmentPartitionRole,
    AttachmentRouteCeiling,
    AttachmentRouteDecision,
    AttachmentRoutePartitionReport,
    AttachmentRouteReport,
    AttachmentSyntaxObservation,
    AttachmentSyntaxPolicy,
    CompetitiveAttachmentGoldDecision,
    CompetitiveAttachmentMatrix,
    attachment_syntax_policies,
    build_attachment_route_decision,
    build_attachment_syntax_observation,
    build_route_ceiling,
    build_route_partition_report,
    syntax_policy_supports,
)

from kotekomi_pipelines.event_entity_connection_stage_local import (
    EventEntityExperimentInput,
)

_CANDIDATE_SOURCE_POLICY_IDS = ("path_3", "path_unbounded")
_PER_EDGE_POLICY_IDS = ("path_1", "path_2", "path_3", "path_4", "path_unbounded")


def attachment_gold_sets(
    oracle: Mapping[str, tuple[CompetitiveAttachmentGoldDecision, ...]],
) -> dict[str, tuple[str, ...]]:
    """Flatten the CEA-1 phase oracle into one Gold Attachment Set per candidate."""
    result: dict[str, tuple[str, ...]] = {}
    for decisions in oracle.values():
        for decision in decisions:
            if decision.candidate_id in result:
                raise ValueError("Gold oracle repeats a candidate across matrices.")
            result[decision.candidate_id] = tuple(sorted(decision.source_grounded_event_ids))
    return result


def build_attachment_route_observations(
    *,
    phase: Literal["development", "validation"],
    matrices: tuple[CompetitiveAttachmentMatrix, ...],
    inputs: tuple[EventEntityExperimentInput, ...],
) -> tuple[AttachmentSyntaxObservation, ...]:
    """Map every candidate and competing Event to pinned Stanza dependency evidence."""
    by_event_id = {item.event.id: item for item in inputs}
    if len(by_event_id) != len(inputs):
        raise ValueError("R1 phase contains duplicate Event inputs.")
    source_by_digest = {item.event.source_text_sha256: item.source_text for item in inputs}
    observations: list[AttachmentSyntaxObservation] = []
    for matrix in sorted(matrices, key=lambda item: item.id):
        source_text = source_by_digest.get(matrix.source_text_sha256)
        if source_text is None:
            raise ValueError("R1 phase lacks the SourceSegment for one matrix.")
        for candidate in matrix.candidates:
            for option in matrix.event_options:
                prepared = by_event_id.get(option.source_grounded_event_id)
                if prepared is None:
                    raise ValueError(
                        f"R1 phase lacks pinned Event input {option.source_grounded_event_id}."
                    )
                observations.append(
                    build_attachment_syntax_observation(
                        phase=phase,
                        source_text=source_text,
                        candidate=candidate,
                        event=option,
                        event_head_start=prepared.trigger.head_start,
                        event_head_end=prepared.trigger.head_end,
                        event_head_text=prepared.trigger.head_text,
                        linguistic_evidence=prepared.linguistic_evidence,
                    )
                )
    return tuple(observations)


def build_attachment_route_phase(
    *,
    phase: Literal["development", "validation"],
    observations: tuple[AttachmentSyntaxObservation, ...],
    gold_attachment: Mapping[str, tuple[str, ...]],
    gold_mixed: Mapping[str, bool],
    gold_temporal: Mapping[str, bool],
) -> AttachmentRoutePartitionReport:
    """Compute every Route Decision for one partition and its Gold accounting."""
    role = (
        AttachmentPartitionRole.DEVELOPMENT
        if phase == "development"
        else AttachmentPartitionRole.VALIDATION
    )
    by_candidate: dict[str, list[AttachmentSyntaxObservation]] = {}
    for observation in observations:
        if observation.phase != phase:
            raise ValueError("R1 partition contains a foreign-phase observation.")
        by_candidate.setdefault(observation.candidate_id, []).append(observation)
    decisions: list[AttachmentRouteDecision] = []
    for candidate_id in sorted(by_candidate):
        candidate_observations = tuple(
            sorted(by_candidate[candidate_id], key=lambda item: item.source_grounded_event_id)
        )
        decisions.append(
            build_attachment_route_decision(
                candidate_id=candidate_id,
                partition_role=role,
                observations=candidate_observations,
                trigger_containment=_candidate_contains_foreign_trigger(
                    candidate_observations
                ),
            )
        )
    return build_route_partition_report(
        partition_role=phase,
        decisions=tuple(decisions),
        gold_attachment=gold_attachment,
        gold_mixed=gold_mixed,
        gold_temporal=gold_temporal,
    )


def build_attachment_route_ceilings(
    *,
    partition_role: Literal["development", "validation"],
    observations: tuple[AttachmentSyntaxObservation, ...],
    gold_attachment: Mapping[str, tuple[str, ...]],
) -> tuple[AttachmentRouteCeiling, ...]:
    """Compute every Gold-dependent diagnostic ceiling for one partition."""
    policy_by_id = {policy.policy_id: policy for policy in attachment_syntax_policies()}
    candidate_ids = tuple(sorted(gold_attachment))
    _validate_ceiling_inventory(
        candidate_ids=candidate_ids,
        observations=observations,
    )
    ceilings: list[AttachmentRouteCeiling] = []
    for kind in (
        AttachmentOracleCeilingKind.CANDIDATE_SOURCE,
        AttachmentOracleCeilingKind.PER_EDGE,
    ):
        policy_ids = (
            _CANDIDATE_SOURCE_POLICY_IDS
            if kind is AttachmentOracleCeilingKind.CANDIDATE_SOURCE
            else _PER_EDGE_POLICY_IDS
        )
        for policy_id in policy_ids:
            predictions = _syntax_predictions(
                candidate_ids=candidate_ids,
                observations=observations,
                policy=policy_by_id[policy_id],
            )
            ceilings.append(
                _build_route_ceiling(
                    partition_role=partition_role,
                    kind=kind,
                    policy_id=policy_id,
                    predictions=predictions,
                    gold_attachment=gold_attachment,
                )
            )
    return tuple(ceilings)


def render_dependency_path_attachment_route_review(report: AttachmentRouteReport) -> str:
    """Render every Route Decision, NONE matrix, census, and ceiling."""
    lines = [
        "# R1 Deterministic Dependency-Path Attachment Router Review",
        "",
        "The router assigns one model-free Route Decision per candidate, in order:",
        "",
        "- `NONE` rule -> `not-attached`",
        "- distance-one `path_1` -> `attached`",
        "- governed complement -> `attached`",
        "- every remaining candidate -> `model-review`",
        "",
        f"Model executions: `{report.model_execution_count}`",
        "",
        f"Canonical writes: `{report.canonical_write_count}`",
        "",
    ]
    for partition in report.partitions:
        lines.extend(_render_partition(partition))
    lines.extend(["## Ceilings", ""])
    for ceiling in report.ceilings:
        lines.append(
            f"- `{ceiling.partition_role}` `{ceiling.kind.value}` "
            f"`{ceiling.policy_id}` reachable `{ceiling.reachable_count}` "
            f"gold `{ceiling.gold_count}` ceiling `{ceiling.ceiling:.6f}`"
        )
    lines.extend(["", f"Result fingerprint: `{report.result_fingerprint}`", ""])
    return "\n".join(lines)


def _render_partition(partition: AttachmentRoutePartitionReport) -> list[str]:
    matrix = partition.none_confusion_matrix
    census = partition.error_census
    lines: list[str] = [
        f"## {partition.partition_role.title()} partition",
        "",
        "NONE confusion matrix: "
        f"`{matrix.syntax_empty_gold_none}` empty-NONE, "
        f"`{matrix.syntax_empty_gold_attached}` empty-attached, "
        f"`{matrix.syntax_reachable_gold_none}` reachable-NONE, "
        f"`{matrix.syntax_reachable_gold_attached}` reachable-attached; "
        f"false-NONE rate `{matrix.false_none_rate:.6f}`",
        "",
        "Error census: "
        f"none `{census.none_count}`, mixed `{census.mixed_count}`, "
        f"temporal `{census.temporal_count}`.",
        "",
        f"Mixed attached candidates: `{_join(census.mixed_attached_candidate_ids)}`.",
        "",
        f"False-NONE temporal candidates: `{_join(census.false_none_temporal_candidate_ids)}`.",
        "",
        f"Exact-set count: `{partition.exact_set_count}`; "
        f"exact-set score `{partition.exact_set_score:.6f}`.",
        "",
    ]
    for decision in partition.decisions:
        lines.extend(
            [
                f"- `{decision.candidate_id}` -> `{decision.route_kind.value}`; "
                f"policy `{decision.selected_policy or 'none'}`; "
                f"allowed `{_join(decision.allowed_event_ids)}`; "
                f"path_1 `{decision.path_1_supported}`; "
                f"trigger-containment `{decision.trigger_containment}`",
            ]
        )
    lines.append("")
    return lines


def _candidate_contains_foreign_trigger(
    observations: tuple[AttachmentSyntaxObservation, ...],
) -> bool:
    """Return whether a candidate range strictly contains a foreign Event trigger."""
    return any(
        observation.candidate_range.start <= observation.event_range.start
        and observation.event_range.end <= observation.candidate_range.end
        and not observation.own_event_expression
        for observation in observations
    )


def _validate_ceiling_inventory(
    *,
    candidate_ids: tuple[str, ...],
    observations: tuple[AttachmentSyntaxObservation, ...],
) -> None:
    observed = {observation.candidate_id for observation in observations}
    if observed != set(candidate_ids):
        raise ValueError("R1 ceiling inventory drifted from the Gold candidate set.")


def _syntax_predictions(
    *,
    candidate_ids: tuple[str, ...],
    observations: tuple[AttachmentSyntaxObservation, ...],
    policy: AttachmentSyntaxPolicy,
) -> dict[str, tuple[str, ...]]:
    """Return the Event IDs each candidate reaches under one bounded policy."""
    result: dict[str, set[str]] = {candidate_id: set() for candidate_id in candidate_ids}
    for observation in observations:
        if observation.candidate_id not in result:
            raise ValueError("Route ceiling references a foreign candidate.")
        if syntax_policy_supports(observation, policy):
            result[observation.candidate_id].add(observation.source_grounded_event_id)
    return {candidate_id: tuple(sorted(events)) for candidate_id, events in result.items()}


def _build_route_ceiling(
    *,
    partition_role: Literal["development", "validation"],
    kind: AttachmentOracleCeilingKind,
    policy_id: str,
    predictions: dict[str, tuple[str, ...]],
    gold_attachment: Mapping[str, tuple[str, ...]],
) -> AttachmentRouteCeiling:
    """Compute one ceiling's reachable and Gold counts from its policy prediction."""
    if kind is AttachmentOracleCeilingKind.CANDIDATE_SOURCE:
        reachable_count = sum(
            bool(set(predictions[candidate_id]) & set(gold_attachment.get(candidate_id, ())))
            for candidate_id in predictions
        )
        gold_count = sum(
            bool(gold_attachment.get(candidate_id, ())) for candidate_id in predictions
        )
    else:
        reachable_count = sum(
            len(set(predictions[candidate_id]) & set(gold_attachment.get(candidate_id, ())))
            for candidate_id in predictions
        )
        gold_count = sum(len(gold_attachment.get(candidate_id, ())) for candidate_id in predictions)
    return build_route_ceiling(
        partition_role=partition_role,
        kind=kind,
        policy_id=policy_id,
        reachable_count=reachable_count,
        gold_count=gold_count,
    )


def _join(values: tuple[str, ...]) -> str:
    return ", ".join(values) if values else "none"
