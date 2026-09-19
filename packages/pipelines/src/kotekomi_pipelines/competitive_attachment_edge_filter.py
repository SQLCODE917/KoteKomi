"""Deterministic preparation and evaluation for the CEA-1.4 Edge Filter."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from typing import Literal

from kotekomi_application import (
    AttachmentComparisonRange,
    AttachmentEdgeFilterArmResult,
    AttachmentEdgeFilterDecision,
    AttachmentEdgeFilterDecisionStatus,
    AttachmentEdgeFilterDiagnosticCatalog,
    AttachmentEdgeFilterOutcome,
    AttachmentEdgeFilterPhaseReport,
    AttachmentMetricSnapshot,
    AttachmentPoolArm,
    AttachmentPoolEdge,
    AttachmentProposalOrigin,
    AttachmentSourceRange,
    AttachmentSyntaxObservation,
    CompetitiveAttachmentMatrix,
    CompetitiveAttachmentPhaseReport,
    FilteredAttachmentSet,
    PropositionFragmentReason,
    attachment_pool_edge_id,
    attachment_syntax_policies,
    build_attachment_edge_filter_task,
    build_filtered_attachment_set,
    syntax_policy_supports,
)
from kotekomi_application.competitive_attachment_edge_filter import (
    AttachmentEdgeFilterTask,
)

from kotekomi_pipelines.source_grounded_proposition_stage_local import (
    PropositionGoldEvent,
    PropositionGoldFragmentRequirement,
)

type AttachmentPredictions = dict[str, tuple[str, ...]]

_ARM_POLICY_ID = {
    AttachmentPoolArm.PATH_1_PLUS_COMPLEMENT: "path_1_plus_complement",
    AttachmentPoolArm.PATH_3_PLUS_COMPLEMENT: "path_3_plus_complement",
    AttachmentPoolArm.PATH_UNBOUNDED_PLUS_COMPLEMENT: ("path_unbounded_plus_complement"),
}
_EXPECTED_MAXIMUM_POOL_SIZE = {"development": 490, "validation": 257}
_DIAGNOSTIC_CATEGORIES = (
    "qwen_false_positive",
    "syntax_only_true",
    "syntax_only_false",
    "shared_fragment",
    "shared_entity",
    "gold_none",
    "repeated_occurrence",
    "attribution",
    "temporal",
    "long_dependency_path",
)


def build_attachment_pool_edges(
    *,
    phase: Literal["development", "validation"],
    matrices: tuple[CompetitiveAttachmentMatrix, ...],
    qwen_report: CompetitiveAttachmentPhaseReport,
    syntax_observations: tuple[AttachmentSyntaxObservation, ...],
    expected_candidate_count: int | None = None,
    expected_maximum_pool_size: int | None = None,
) -> tuple[AttachmentPoolEdge, ...]:
    """Build the Gold-free Qwen/syntax Maximum Pool from frozen evidence."""
    candidates = {
        candidate.id: (matrix, candidate) for matrix in matrices for candidate in matrix.candidates
    }
    options = {
        (matrix.source_segment_id, option.source_grounded_event_id): option
        for matrix in matrices
        for option in matrix.event_options
    }
    qwen: set[tuple[str, str]] = {
        (case.candidate_id, event_id)
        for case in qwen_report.cases
        for event_id in case.competitive_event_ids
    }
    if {case.candidate_id for case in qwen_report.cases} != set(candidates):
        raise ValueError("Edge Filter Qwen report Candidate inventory drifted.")
    selected_policies = {
        policy.policy_id: policy
        for policy in attachment_syntax_policies()
        if policy.policy_id in set(_ARM_POLICY_ID.values())
    }
    syntax_arms: dict[tuple[str, str], set[AttachmentPoolArm]] = defaultdict(set)
    for observation in syntax_observations:
        key = (observation.candidate_id, observation.source_grounded_event_id)
        if observation.candidate_id not in candidates:
            raise ValueError("Edge Filter syntax references a foreign Candidate.")
        for arm, policy_id in _ARM_POLICY_ID.items():
            if syntax_policy_supports(observation, selected_policies[policy_id]):
                syntax_arms[key].add(arm)
    maximum = qwen | set(syntax_arms)
    result: list[AttachmentPoolEdge] = []
    for candidate_id, event_id in sorted(maximum):
        matrix, candidate = candidates[candidate_id]
        option = options[(matrix.source_segment_id, event_id)]
        origins = tuple(
            origin
            for origin, included in (
                (AttachmentProposalOrigin.QWEN, (candidate_id, event_id) in qwen),
                (AttachmentProposalOrigin.SYNTAX, (candidate_id, event_id) in syntax_arms),
            )
            if included
        )
        arms = tuple(
            arm for arm in AttachmentPoolArm if arm in syntax_arms[(candidate_id, event_id)]
        )
        values = {
            "phase": phase,
            "source_segment_id": matrix.source_segment_id,
            "source_text_sha256": matrix.source_text_sha256,
            "candidate_id": candidate_id,
            "source_grounded_event_id": event_id,
            "candidate_start": candidate.start,
            "candidate_end": candidate.end,
            "event_start": option.start,
            "event_end": option.end,
        }
        result.append(
            AttachmentPoolEdge(
                id=attachment_pool_edge_id(**values),
                phase=phase,
                source_segment_id=matrix.source_segment_id,
                source_text_sha256=matrix.source_text_sha256,
                candidate_id=candidate_id,
                source_grounded_event_id=event_id,
                candidate_range=AttachmentSourceRange(
                    start=candidate.start,
                    end=candidate.end,
                    text=candidate.text,
                ),
                event_range=AttachmentSourceRange(
                    start=option.start,
                    end=option.end,
                    text=option.text,
                ),
                origins=origins,
                syntax_arms=arms,
            )
        )
    edges = tuple(
        sorted(
            result,
            key=lambda item: (
                item.source_text_sha256,
                item.candidate_range.start,
                item.candidate_range.end,
                item.event_range.start,
                item.event_range.end,
            ),
        )
    )
    _validate_pool_inventory(
        phase,
        matrices,
        edges,
        expected_candidate_count=(
            expected_candidate_count
            if expected_candidate_count is not None
            else (162 if phase == "development" else 179)
        ),
        expected_maximum_pool_size=(
            expected_maximum_pool_size
            if expected_maximum_pool_size is not None
            else _EXPECTED_MAXIMUM_POOL_SIZE[phase]
        ),
    )
    return edges


def build_attachment_edge_filter_tasks(
    *,
    matrices: tuple[CompetitiveAttachmentMatrix, ...],
    source_text_by_digest: dict[str, str],
    edges: tuple[AttachmentPoolEdge, ...],
) -> tuple[AttachmentEdgeFilterTask, ...]:
    """Create one source-exact task for every Maximum Pool Edge."""
    candidate_by_id = {
        candidate.id: candidate for matrix in matrices for candidate in matrix.candidates
    }
    options_by_segment = {matrix.source_segment_id: matrix.event_options for matrix in matrices}
    tasks = tuple(
        build_attachment_edge_filter_task(
            source_text=source_text_by_digest[edge.source_text_sha256],
            edge=edge,
            candidate=candidate_by_id[edge.candidate_id],
            event_options=options_by_segment[edge.source_segment_id],
        )
        for edge in edges
    )
    if len({item.task_id for item in tasks}) != len(edges):
        raise ValueError("Edge Filter task inventory is not one-to-one with Pool Edges.")
    return tasks


def normalized_attachment_gold_sets(
    *,
    original_gold: AttachmentPredictions,
    normalization_changes: dict[str, tuple[str, ...]],
) -> AttachmentPredictions:
    """Apply only the three reviewed CEA-1.3 evaluation-range changes."""
    if not set(normalization_changes) <= set(original_gold):
        raise ValueError("Normalized Gold references a foreign Candidate.")
    return {
        candidate_id: tuple(sorted(normalization_changes.get(candidate_id, event_ids)))
        for candidate_id, event_ids in original_gold.items()
    }


def build_attachment_edge_filter_diagnostic_catalog(
    *,
    tasks: tuple[AttachmentEdgeFilterTask, ...],
    gold_sets: AttachmentPredictions,
    source_text_by_digest: dict[str, str],
    gold_by_event_id: dict[str, PropositionGoldEvent],
) -> AttachmentEdgeFilterDiagnosticCatalog:
    """Select sixteen development edges spanning the declared failure classes."""
    tasks_by_candidate: dict[str, list[AttachmentEdgeFilterTask]] = defaultdict(list)
    for task in tasks:
        tasks_by_candidate[task.edge.candidate_id].append(task)
    mixed_candidate_ids = tuple(
        candidate_id
        for candidate_id, candidate_tasks in tasks_by_candidate.items()
        if not gold_sets[candidate_id]
        and any(AttachmentProposalOrigin.QWEN in task.edge.origins for task in candidate_tasks)
        and any(task.edge.origins == (AttachmentProposalOrigin.SYNTAX,) for task in candidate_tasks)
    )
    if not mixed_candidate_ids:
        raise ValueError("Edge Filter diagnostic lacks a mixed-candidate failure shape.")
    mixed_candidate_id = min(
        mixed_candidate_ids,
        key=lambda candidate_id: (
            len(tasks_by_candidate[candidate_id][0].candidate.text),
            tasks_by_candidate[candidate_id][0].edge.source_text_sha256,
            tasks_by_candidate[candidate_id][0].candidate.start,
            candidate_id,
        ),
    )
    categories = {
        task.task_id: _diagnostic_categories(
            task,
            gold_sets=gold_sets,
            source_text=source_text_by_digest[task.edge.source_text_sha256],
            gold_by_event_id=gold_by_event_id,
        )
        for task in tasks
    }
    selected: list[AttachmentEdgeFilterTask] = []
    selected_ids: set[str] = set()
    segment_counts: dict[str, int] = defaultdict(int)
    answer_counts: dict[str, int] = defaultdict(int)

    def expected_answer(task: AttachmentEdgeFilterTask) -> str:
        return (
            "Y" if task.edge.source_grounded_event_id in gold_sets[task.edge.candidate_id] else "N"
        )

    def selection_key(
        task: AttachmentEdgeFilterTask,
    ) -> tuple[int, int, str, int, int, int, str]:
        return (
            segment_counts[task.edge.source_segment_id],
            answer_counts[expected_answer(task)],
            task.edge.source_text_sha256,
            task.candidate.start,
            task.candidate.end,
            task.edge.event_range.start,
            task.task_id,
        )

    def category_selection_key(
        task: AttachmentEdgeFilterTask,
        category: str,
    ) -> tuple[int, int, int, int, int, str, int, int, int, str]:
        mixed_candidate_priority = int(
            category in {"qwen_false_positive", "syntax_only_false"}
            and task.edge.candidate_id != mixed_candidate_id
        )
        syntax_rescue_priority = int(
            category == "shared_entity"
            and not (
                task.edge.origins == (AttachmentProposalOrigin.SYNTAX,)
                and AttachmentPoolArm.PATH_1_PLUS_COMPLEMENT not in task.edge.syntax_arms
            )
        )
        shared_event_set_size = len(task.event_options) if category == "shared_entity" else 0
        return (
            mixed_candidate_priority,
            syntax_rescue_priority,
            shared_event_set_size,
            *selection_key(task),
        )

    def add(task: AttachmentEdgeFilterTask) -> None:
        selected.append(task)
        selected_ids.add(task.task_id)
        segment_counts[task.edge.source_segment_id] += 1
        answer_counts[expected_answer(task)] += 1

    for category in _DIAGNOSTIC_CATEGORIES:
        matches = tuple(
            task
            for task in tasks
            if task.task_id not in selected_ids and category in categories[task.task_id]
        )
        if not matches:
            raise ValueError(f"Edge Filter diagnostic cannot cover {category}.")
        add(min(matches, key=lambda task: category_selection_key(task, category)))

    available_segments = tuple(sorted({task.edge.source_segment_id for task in tasks}))
    if len(available_segments) != 6:
        raise ValueError("Edge Filter diagnostic requires six development SourceSegments.")
    for source_segment_id in available_segments:
        if segment_counts[source_segment_id]:
            continue
        matches = tuple(
            task
            for task in tasks
            if task.task_id not in selected_ids and task.edge.source_segment_id == source_segment_id
        )
        if not matches:
            raise ValueError("Edge Filter diagnostic cannot cover every SourceSegment.")
        add(min(matches, key=selection_key))

    while len(selected) < 16:
        required_answer = "Y" if answer_counts["Y"] < answer_counts["N"] else "N"
        if answer_counts[required_answer] == 8:
            required_answer = "N" if required_answer == "Y" else "Y"
        matches = tuple(
            task
            for task in tasks
            if task.task_id not in selected_ids and expected_answer(task) == required_answer
        )
        if not matches:
            raise ValueError("Edge Filter diagnostic cannot balance Y and N decisions.")
        add(min(matches, key=selection_key))
    if len(selected) != 16 or answer_counts != {"Y": 8, "N": 8}:
        raise ValueError("Edge Filter diagnostic requires eight Y and eight N decisions.")
    selected_tasks = tuple(
        sorted(
            selected,
            key=lambda task: (
                task.edge.source_text_sha256,
                task.candidate.start,
                task.edge.event_range.start,
            ),
        )
    )
    coverage = {task.task_id: tuple(sorted(categories[task.task_id])) for task in selected_tasks}
    payload = {
        "tasks": [item.model_dump(mode="json") for item in selected_tasks],
        "coverage_by_task_id": coverage,
    }
    return AttachmentEdgeFilterDiagnosticCatalog(
        tasks=selected_tasks,
        coverage_by_task_id=coverage,
        catalog_sha256=_sha(payload),
    )


def build_attachment_edge_filter_phase_report(
    *,
    phase: Literal["development", "validation"],
    matrices: tuple[CompetitiveAttachmentMatrix, ...],
    edges: tuple[AttachmentPoolEdge, ...],
    decisions: tuple[AttachmentEdgeFilterDecision, ...],
    gold_sets: AttachmentPredictions,
    comparisons: dict[str, AttachmentComparisonRange],
    gold_by_event_id: dict[str, PropositionGoldEvent],
    source_text_by_digest: dict[str, str],
    entity_occurrences_by_event: dict[str, tuple[tuple[int, int], ...]],
    competitive_qwen_metrics: AttachmentMetricSnapshot,
    cea13_primary_metrics: AttachmentMetricSnapshot,
    oracle_ceiling_metrics: AttachmentMetricSnapshot,
    frozen_selected_arm: AttachmentPoolArm | None = None,
) -> AttachmentEdgeFilterPhaseReport:
    """Evaluate all nested arms from one shared Maximum Pool decision set."""
    if len(decisions) != len(edges):
        raise ValueError("Edge Filter phase requires one decision per Maximum Pool Edge.")
    decisions_by_edge = {item.edge_id: item for item in decisions}
    if set(decisions_by_edge) != {item.id for item in edges}:
        raise ValueError("Edge Filter decisions do not cover the Maximum Pool exactly.")
    candidate_ids = tuple(
        sorted(candidate.id for matrix in matrices for candidate in matrix.candidates)
    )
    if set(candidate_ids) != set(gold_sets):
        raise ValueError("Edge Filter Gold does not cover every Candidate.")
    filtered_sets: list[FilteredAttachmentSet] = []
    arm_results: list[AttachmentEdgeFilterArmResult] = []
    edges_by_candidate: dict[str, list[AttachmentPoolEdge]] = defaultdict(list)
    for edge in edges:
        edges_by_candidate[edge.candidate_id].append(edge)
    for arm in AttachmentPoolArm:
        sets = tuple(
            build_filtered_attachment_set(
                phase=phase,
                arm=arm,
                candidate_id=candidate_id,
                edges=tuple(edges_by_candidate[candidate_id]),
                decisions_by_edge_id=decisions_by_edge,
            )
            for candidate_id in candidate_ids
        )
        filtered_sets.extend(sets)
        raw = _pool_predictions(candidate_ids, edges, arm)
        filtered = {item.candidate_id: item.retained_event_ids for item in sets}
        unresolved = {item.candidate_id for item in sets if item.unresolved_event_ids}
        raw_metrics = _measure_predictions(
            matrices=matrices,
            gold_sets=gold_sets,
            predicted_sets=raw,
            comparisons=comparisons,
            gold_by_event_id=gold_by_event_id,
            source_text_by_digest=source_text_by_digest,
            entity_occurrences_by_event=entity_occurrences_by_event,
            unresolved_candidate_ids=set(),
        )
        filtered_metrics = _measure_predictions(
            matrices=matrices,
            gold_sets=gold_sets,
            predicted_sets=filtered,
            comparisons=comparisons,
            gold_by_event_id=gold_by_event_id,
            source_text_by_digest=source_text_by_digest,
            entity_occurrences_by_event=entity_occurrences_by_event,
            unresolved_candidate_ids=unresolved,
        )
        arm_edges = tuple(
            edge
            for edge in edges
            if AttachmentProposalOrigin.QWEN in edge.origins or arm in edge.syntax_arms
        )
        arm_decisions = tuple(decisions_by_edge[item.id] for item in arm_edges)
        arm_results.append(
            AttachmentEdgeFilterArmResult(
                phase=phase,
                arm=arm,
                raw_pool_metrics=raw_metrics,
                filtered_metrics=filtered_metrics,
                edge_count=len(arm_edges),
                retained_edge_count=sum(item.retained for item in arm_decisions),
                rejected_edge_count=sum(
                    item.status is AttachmentEdgeFilterDecisionStatus.COMPLETE and not item.retained
                    for item in arm_decisions
                ),
                unresolved_edge_count=sum(item.unresolved for item in arm_decisions),
                pool_gap_count=sum(not item.pool_edge_ids for item in sets),
            )
        )
    arms = tuple(arm_results)
    all_filtered_sets = tuple(filtered_sets)
    selected = frozen_selected_arm or select_attachment_pool_arm(arms)
    invalid_output_count = sum(
        item.status is AttachmentEdgeFilterDecisionStatus.INVALID_OUTPUT for item in decisions
    )
    blocked_count = sum(
        item.status is AttachmentEdgeFilterDecisionStatus.INPUT_BLOCKED for item in decisions
    )
    failed_count = sum(
        item.status is AttachmentEdgeFilterDecisionStatus.MODEL_FAILED for item in decisions
    )
    draft: dict[str, object] = {
        "phase": phase,
        "candidate_count": len(candidate_ids),
        "maximum_pool_edge_count": len(edges),
        "task_count": len(decisions),
        "competitive_qwen_metrics": competitive_qwen_metrics.model_dump(mode="json"),
        "cea13_primary_metrics": cea13_primary_metrics.model_dump(mode="json"),
        "oracle_ceiling_metrics": oracle_ceiling_metrics.model_dump(mode="json"),
        "decisions": [item.model_dump(mode="json") for item in decisions],
        "filtered_sets": [item.model_dump(mode="json") for item in all_filtered_sets],
        "arms": [item.model_dump(mode="json") for item in arms],
        "selected_arm": selected.value,
        "invalid_output_count": invalid_output_count,
        "blocked_count": blocked_count,
        "failed_count": failed_count,
    }
    return AttachmentEdgeFilterPhaseReport(
        phase=phase,
        candidate_count=len(candidate_ids),
        maximum_pool_edge_count=len(edges),
        task_count=len(decisions),
        competitive_qwen_metrics=competitive_qwen_metrics,
        cea13_primary_metrics=cea13_primary_metrics,
        oracle_ceiling_metrics=oracle_ceiling_metrics,
        decisions=decisions,
        filtered_sets=all_filtered_sets,
        arms=arms,
        selected_arm=selected,
        invalid_output_count=invalid_output_count,
        blocked_count=blocked_count,
        failed_count=failed_count,
        result_fingerprint=_sha(draft),
    )


def select_attachment_pool_arm(
    arms: tuple[AttachmentEdgeFilterArmResult, ...],
) -> AttachmentPoolArm:
    """Select exact accuracy, then edge F1, leakage, then narrower pool."""
    if tuple(item.arm for item in arms) != tuple(AttachmentPoolArm):
        raise ValueError("Edge Filter arm selection requires all canonical arms.")
    return max(
        arms,
        key=lambda item: (
            item.filtered_metrics.exact_set_accuracy,
            item.filtered_metrics.edge_f1,
            -item.filtered_metrics.sibling_event_leakage_count,
            -item.edge_count,
        ),
    ).arm


def measure_attachment_edge_filter_predictions(
    *,
    matrices: tuple[CompetitiveAttachmentMatrix, ...],
    gold_sets: AttachmentPredictions,
    predicted_sets: AttachmentPredictions,
    comparisons: dict[str, AttachmentComparisonRange],
    gold_by_event_id: dict[str, PropositionGoldEvent],
    source_text_by_digest: dict[str, str],
    entity_occurrences_by_event: dict[str, tuple[tuple[int, int], ...]],
    unresolved_candidate_ids: set[str] | None = None,
) -> AttachmentMetricSnapshot:
    """Measure one externally constructed occurrence-specific prediction inventory."""
    return _measure_predictions(
        matrices=matrices,
        gold_sets=gold_sets,
        predicted_sets=predicted_sets,
        comparisons=comparisons,
        gold_by_event_id=gold_by_event_id,
        source_text_by_digest=source_text_by_digest,
        entity_occurrences_by_event=entity_occurrences_by_event,
        unresolved_candidate_ids=unresolved_candidate_ids or set(),
    )


def attachment_edge_filter_outcome(
    development: AttachmentEdgeFilterPhaseReport,
    validation: AttachmentEdgeFilterPhaseReport,
) -> AttachmentEdgeFilterOutcome:
    """Apply the predeclared two-phase safety gates."""
    selected = development.selected_arm
    if validation.selected_arm is not selected:
        raise ValueError("Validation did not preserve the frozen development arm.")
    phase_results = tuple(
        next(item for item in phase.arms if item.arm is selected)
        for phase in (development, validation)
    )
    improvements: list[bool] = []
    safety: list[bool] = []
    for phase, result in zip((development, validation), phase_results, strict=True):
        candidate = result.filtered_metrics
        baseline = phase.competitive_qwen_metrics
        improvements.append(
            candidate.exact_set_accuracy > baseline.exact_set_accuracy
            and candidate.edge_precision > baseline.edge_precision
            and candidate.sibling_event_leakage_count < baseline.sibling_event_leakage_count
        )
        safety.append(
            candidate.entity_recall >= baseline.entity_recall
            and candidate.qualification_recall >= baseline.qualification_recall
            and candidate.shared_fragment_recall >= baseline.shared_fragment_recall
            and candidate.character_recall >= baseline.character_recall
            and candidate.none_accuracy >= baseline.none_accuracy
            and phase.invalid_output_count == 0
            and phase.blocked_count == 0
            and phase.failed_count == 0
            and result.unresolved_edge_count == 0
        )
    if all(improvements) and all(safety):
        return AttachmentEdgeFilterOutcome.SUPPORTED
    if any(improvements) or any(safety):
        return AttachmentEdgeFilterOutcome.MIXED
    return AttachmentEdgeFilterOutcome.FALSIFIED


def attachment_edge_filter_summary(
    development: AttachmentEdgeFilterPhaseReport,
    validation: AttachmentEdgeFilterPhaseReport,
    outcome: AttachmentEdgeFilterOutcome,
) -> dict[str, object]:
    """Return one bounded machine-readable CEA-1.4 summary."""
    return {
        "schema_version": "attachment_edge_filter_summary_v1",
        "status": "complete",
        "outcome": outcome.value,
        "selected_arm": development.selected_arm.value,
        "development": _phase_summary(development),
        "validation": _phase_summary(validation),
        "validation_interpretation": "diagnostic_only",
        "production_integration": "not_activated",
        "proposed_change_count": 0,
        "accepted_ledger_change_count": 0,
    }


def render_attachment_edge_filter_review(
    *,
    phase: AttachmentEdgeFilterPhaseReport,
    tasks_by_edge_id: dict[str, AttachmentEdgeFilterTask],
) -> str:
    """Render exact data in, raw decision mapping, and expected Gold outcome."""
    lines = [
        f"# CEA-1.4 {phase.phase.title()} Edge Filter Review",
        "",
        f"Selected Pool Arm: `{phase.selected_arm.value}`",
        "",
    ]
    for decision in phase.decisions:
        task = tasks_by_edge_id[decision.edge_id]
        target_text = next(
            item.text for item in task.event_options if item.label == task.target_event_label
        )
        decision_text = decision.answer.value if decision.answer else decision.status.value
        lines.extend(
            (
                f"## {task.task_id}",
                "",
                f"> {task.source_text}",
                "",
                f"Candidate: `{task.candidate.text}`",
                "",
                f"Target Event: `{target_text}`",
                "",
                f"Exact model input fingerprint: `{task.task_fingerprint}`",
                "",
                f"Decision: `{decision_text}`",
                "",
                f"Retained: `{str(decision.retained).lower()}`",
                "",
                f"Trace: `{decision.trace_id or 'none'}`",
                "",
            )
        )
    lines.extend(("## Pool Arm Metrics", ""))
    for arm in phase.arms:
        metrics = arm.filtered_metrics
        lines.extend(
            (
                f"### {arm.arm.value}",
                "",
                f"Edges: `{arm.edge_count}`",
                "",
                f"Exact-set accuracy: `{metrics.exact_set_accuracy:.6f}`",
                "",
                f"Edge precision / recall / F1: `{metrics.edge_precision:.6f}` / "
                f"`{metrics.edge_recall:.6f}` / `{metrics.edge_f1:.6f}`",
                "",
                f"Sibling leakage: `{metrics.sibling_event_leakage_count}`",
                "",
                f"Pool gaps: `{arm.pool_gap_count}`",
                "",
            )
        )
    return "\n".join(lines).rstrip() + "\n"


def _validate_pool_inventory(
    phase: Literal["development", "validation"],
    matrices: tuple[CompetitiveAttachmentMatrix, ...],
    edges: tuple[AttachmentPoolEdge, ...],
    *,
    expected_candidate_count: int,
    expected_maximum_pool_size: int,
) -> None:
    observed_candidates = sum(len(item.candidates) for item in matrices)
    if observed_candidates != expected_candidate_count:
        raise ValueError(f"Edge Filter {phase} Candidate inventory drifted: {observed_candidates}.")
    if len(edges) != expected_maximum_pool_size:
        raise ValueError(f"Edge Filter {phase} Maximum Pool size drifted: {len(edges)}.")
    by_arm = {
        arm: sum(
            AttachmentProposalOrigin.QWEN in edge.origins or arm in edge.syntax_arms
            for edge in edges
        )
        for arm in AttachmentPoolArm
    }
    values = tuple(by_arm.values())
    if values != tuple(sorted(values)):
        raise ValueError("Edge Filter Pool Arms are not nested.")


def _pool_predictions(
    candidate_ids: tuple[str, ...],
    edges: tuple[AttachmentPoolEdge, ...],
    arm: AttachmentPoolArm,
) -> AttachmentPredictions:
    result: dict[str, set[str]] = {item: set() for item in candidate_ids}
    for edge in edges:
        if AttachmentProposalOrigin.QWEN in edge.origins or arm in edge.syntax_arms:
            result[edge.candidate_id].add(edge.source_grounded_event_id)
    return {key: tuple(sorted(value)) for key, value in result.items()}


def _diagnostic_categories(
    task: AttachmentEdgeFilterTask,
    *,
    gold_sets: AttachmentPredictions,
    source_text: str,
    gold_by_event_id: dict[str, PropositionGoldEvent],
) -> set[str]:
    edge = task.edge
    gold = set(gold_sets[edge.candidate_id])
    categories: set[str] = set()
    is_gold = edge.source_grounded_event_id in gold
    qwen = AttachmentProposalOrigin.QWEN in edge.origins
    syntax_only = edge.origins == (AttachmentProposalOrigin.SYNTAX,)
    if qwen and not is_gold:
        categories.add("qwen_false_positive")
    if syntax_only:
        categories.add("syntax_only_true" if is_gold else "syntax_only_false")
    if len(gold) > 1 and is_gold:
        categories.add("shared_fragment")
        if PropositionFragmentReason.ENTITY_OCCURRENCE in task.candidate.reasons:
            categories.add("shared_entity")
    if not gold:
        categories.add("gold_none")
    if source_text.count(task.candidate.text) > 1:
        categories.add("repeated_occurrence")
    if (
        AttachmentPoolArm.PATH_UNBOUNDED_PLUS_COMPLEMENT in edge.syntax_arms
        and AttachmentPoolArm.PATH_3_PLUS_COMPLEMENT not in edge.syntax_arms
    ):
        categories.add("long_dependency_path")
    event = gold_by_event_id[edge.source_grounded_event_id]
    candidate_positions = _positions(
        source_text,
        ((task.candidate.start, task.candidate.end),),
    )
    for fragment in event.fragments:
        fragment_positions = _positions(source_text, ((fragment.start, fragment.end),))
        if not candidate_positions or not candidate_positions <= fragment_positions:
            continue
        if PropositionGoldFragmentRequirement.ATTRIBUTION in fragment.requirements:
            categories.add("attribution")
        if PropositionGoldFragmentRequirement.TEMPORAL in fragment.requirements:
            categories.add("temporal")
    return categories


def _measure_predictions(
    *,
    matrices: tuple[CompetitiveAttachmentMatrix, ...],
    gold_sets: AttachmentPredictions,
    predicted_sets: AttachmentPredictions,
    comparisons: dict[str, AttachmentComparisonRange],
    gold_by_event_id: dict[str, PropositionGoldEvent],
    source_text_by_digest: dict[str, str],
    entity_occurrences_by_event: dict[str, tuple[tuple[int, int], ...]],
    unresolved_candidate_ids: set[str],
) -> AttachmentMetricSnapshot:
    if set(gold_sets) != set(predicted_sets) or set(gold_sets) != set(comparisons):
        raise ValueError("Edge Filter metrics require complete Candidate inventories.")
    tp = fp = fn = leakage = exact = 0
    shared_total = shared_matched = none_total = none_correct = 0
    for candidate_id, gold_ids in gold_sets.items():
        gold = set(gold_ids)
        predicted = set(predicted_sets[candidate_id])
        exact += candidate_id not in unresolved_candidate_ids and gold == predicted
        tp += len(gold & predicted)
        fp += len(predicted - gold)
        fn += len(gold - predicted)
        if gold:
            leakage += len(predicted - gold)
        else:
            none_total += 1
            none_correct += candidate_id not in unresolved_candidate_ids and not predicted
        if len(gold) > 1:
            shared_total += len(gold)
            shared_matched += len(gold & predicted)
    candidate_by_id = {
        candidate.id: candidate for matrix in matrices for candidate in matrix.candidates
    }
    phase_event_ids = tuple(
        sorted(
            {
                option.source_grounded_event_id
                for matrix in matrices
                for option in matrix.event_options
            }
        )
    )
    character_tp = character_fp = character_fn = exact_events = 0
    entity_total = entity_matched = qualification_total = qualification_matched = 0
    for event_id in phase_event_ids:
        gold_event = gold_by_event_id[event_id]
        source = source_text_by_digest[gold_event.source_text_sha256]
        required = _positions(
            source,
            tuple((item.start, item.end) for item in gold_event.fragments),
        )
        selected = _positions(
            source,
            tuple(
                (
                    comparisons[candidate_id].comparison_start,
                    comparisons[candidate_id].comparison_end,
                )
                for candidate_id, candidate in candidate_by_id.items()
                if event_id in predicted_sets[candidate_id]
                and candidate.source_text_sha256 == gold_event.source_text_sha256
                and comparisons[candidate_id].comparison_start
                < comparisons[candidate_id].comparison_end
            ),
        )
        character_tp += len(required & selected)
        character_fp += len(selected - required)
        character_fn += len(required - selected)
        exact_events += selected == required
        qualifications = tuple(
            item
            for item in gold_event.fragments
            if any(
                requirement is not PropositionGoldFragmentRequirement.CORE_EVENT
                for requirement in item.requirements
            )
        )
        qualification_total += len(qualifications)
        qualification_matched += sum(
            _positions(source, ((item.start, item.end),)) <= selected for item in qualifications
        )
        occurrences = entity_occurrences_by_event.get(event_id, ())
        entity_total += len(occurrences)
        entity_matched += sum(
            _positions(source, (occurrence,)) <= selected for occurrence in occurrences
        )
    precision = _ratio(tp, tp + fp)
    recall = _ratio(tp, tp + fn)
    character_precision = _ratio(character_tp, character_tp + character_fp)
    character_recall = _ratio(character_tp, character_tp + character_fn)
    return AttachmentMetricSnapshot(
        candidate_count=len(gold_sets),
        event_count=len(phase_event_ids),
        exact_set_count=exact,
        exact_set_accuracy=_ratio(exact, len(gold_sets)),
        true_positive_edge_count=tp,
        false_positive_edge_count=fp,
        false_negative_edge_count=fn,
        edge_precision=precision,
        edge_recall=recall,
        edge_f1=_f1(precision, recall),
        sibling_event_leakage_count=leakage,
        shared_gold_edge_count=shared_total,
        shared_matched_edge_count=shared_matched,
        shared_fragment_recall=_ratio(shared_matched, shared_total),
        none_case_count=none_total,
        none_correct_count=none_correct,
        none_accuracy=_ratio(none_correct, none_total),
        exact_event_count=exact_events,
        character_precision=character_precision,
        character_recall=character_recall,
        character_f1=_f1(character_precision, character_recall),
        entity_gold_edge_count=entity_total,
        entity_matched_edge_count=entity_matched,
        entity_recall=_ratio(entity_matched, entity_total),
        qualification_gold_edge_count=qualification_total,
        qualification_matched_edge_count=qualification_matched,
        qualification_recall=_ratio(qualification_matched, qualification_total),
        anchor_gap_count=0,
    )


def _positions(source: str, ranges: tuple[tuple[int, int], ...]) -> set[int]:
    result: set[int] = set()
    for start, end in ranges:
        if not (0 <= start <= end <= len(source)):
            raise ValueError("Edge Filter comparison range leaves its SourceSegment.")
        result.update(index for index in range(start, end) if not source[index].isspace())
    return result


def _phase_summary(phase: AttachmentEdgeFilterPhaseReport) -> dict[str, object]:
    selected = next(item for item in phase.arms if item.arm is phase.selected_arm)
    return {
        "candidate_count": phase.candidate_count,
        "maximum_pool_edge_count": phase.maximum_pool_edge_count,
        "selected_arm": phase.selected_arm.value,
        "competitive_qwen": phase.competitive_qwen_metrics.model_dump(mode="json"),
        "filtered": selected.filtered_metrics.model_dump(mode="json"),
        "unresolved_edge_count": selected.unresolved_edge_count,
        "pool_gap_count": selected.pool_gap_count,
        "invalid_output_count": phase.invalid_output_count,
        "blocked_count": phase.blocked_count,
        "failed_count": phase.failed_count,
    }


def _ratio(numerator: int, denominator: int) -> float:
    return 1.0 if denominator == 0 else numerator / denominator


def _f1(precision: float, recall: float) -> float:
    return 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)


def _sha(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
