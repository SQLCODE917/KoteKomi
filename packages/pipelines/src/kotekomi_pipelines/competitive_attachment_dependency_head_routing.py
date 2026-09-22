"""Model-free dependency-head routing for CEA-1.18."""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Literal, cast

from kotekomi_application import (
    AttachmentBinaryMetrics,
    AttachmentEvidenceReference,
    AttachmentHeadRoute,
    AttachmentHeadRoutingCase,
    AttachmentHeadRoutingPhase,
    AttachmentHeadRoutingReport,
    AttachmentResidualTransferPhaseReport,
    AttachmentResidualTransferReport,
    PredicateArgumentToken,
    attachment_candidate_root_evidence,
    attachment_head_routing_fingerprint,
    attachment_syntax_is_head_aligned,
    build_attachment_syntax_observation,
    classify_dependency_head_routing_outcome,
)

from kotekomi_pipelines.event_entity_connection_stage_local import (
    EventEntityExperimentInput,
)


def build_dependency_head_routing_phase(
    *,
    transfer: AttachmentResidualTransferPhaseReport,
    inputs: tuple[EventEntityExperimentInput, ...],
) -> AttachmentHeadRoutingPhase:
    """Route one frozen phase from exact CEA-1 dependency evidence."""
    by_event_id = {item.event.id: item for item in inputs}
    if len(by_event_id) != len(inputs):
        raise ValueError("Dependency-head phase contains duplicate Event inputs.")
    cases: list[AttachmentHeadRoutingCase] = []
    for transfer_case in sorted(transfer.cases, key=lambda item: item.task.id):
        task = transfer_case.task.edge_filter_task
        event_id = task.edge.source_grounded_event_id
        prepared = by_event_id.get(event_id)
        if prepared is None:
            raise ValueError(f"Dependency-head phase lacks Event input {event_id}.")
        if prepared.source_text != task.source_text:
            raise ValueError("Dependency-head Event input SourceSegment drifted.")
        event = next(
            (
                item
                for item in task.event_options
                if item.source_grounded_event_id == event_id
                and item.label == task.target_event_label
            ),
            None,
        )
        if event is None:
            raise ValueError("Dependency-head task lacks its exact Target Event option.")
        syntax = build_attachment_syntax_observation(
            phase=transfer.phase,
            source_text=task.source_text,
            candidate=task.candidate,
            event=event,
            event_head_start=prepared.trigger.head_start,
            event_head_end=prepared.trigger.head_end,
            event_head_text=prepared.trigger.head_text,
            linguistic_evidence=prepared.linguistic_evidence,
        )
        root_evidence = attachment_candidate_root_evidence(
            task.candidate,
            prepared.linguistic_evidence,
        )
        roots = root_evidence.roots
        route = (
            AttachmentHeadRoute.STRUCTURAL
            if attachment_syntax_is_head_aligned(syntax, roots)
            else AttachmentHeadRoute.SEMANTIC
        )
        baseline = cast(
            tuple[Literal["Y", "N"], Literal["Y", "N"]],
            transfer_case.threshold_answers,
        )
        routed = cast(
            tuple[Literal["Y", "N"], Literal["Y", "N"]],
            ("Y", "Y") if route is AttachmentHeadRoute.STRUCTURAL else baseline,
        )
        expected = transfer_case.gold.expected_answer
        baseline_correct = all(item == expected for item in baseline)
        routed_correct = all(item == expected for item in routed)
        cases.append(
            AttachmentHeadRoutingCase(
                transfer_case=transfer_case,
                syntax=syntax,
                candidate_root_evidence=root_evidence,
                baseline_answers=baseline,
                route=route,
                routed_answers=routed,
                baseline_correct=baseline_correct,
                routed_correct=routed_correct,
                recovered=not baseline_correct and routed_correct,
                regressed=baseline_correct and not routed_correct,
            )
        )
    values = tuple(cases)
    structural = tuple(item for item in values if item.route is AttachmentHeadRoute.STRUCTURAL)
    semantic = tuple(item for item in values if item.route is AttachmentHeadRoute.SEMANTIC)
    return AttachmentHeadRoutingPhase(
        phase=transfer.phase,
        cases=values,
        baseline_metrics=(
            _metrics(values, 0, routed=False),
            _metrics(values, 1, routed=False),
        ),
        routed_metrics=(
            _metrics(values, 0, routed=True),
            _metrics(values, 1, routed=True),
        ),
        head_aligned_count=len(structural),
        semantic_count=len(semantic),
        head_aligned_positive_count=sum(
            item.transfer_case.gold.expected_answer == "Y" for item in structural
        ),
        head_aligned_negative_count=sum(
            item.transfer_case.gold.expected_answer == "N" for item in structural
        ),
        semantic_positive_count=sum(
            item.transfer_case.gold.expected_answer == "Y" for item in semantic
        ),
        semantic_negative_count=sum(
            item.transfer_case.gold.expected_answer == "N" for item in semantic
        ),
        recovered_count=sum(item.recovered for item in values),
        regressed_count=sum(item.regressed for item in values),
    )


def build_dependency_head_routing_report(
    *,
    inputs: tuple[AttachmentEvidenceReference, ...],
    predecessor: AttachmentResidualTransferReport,
    development_inputs: tuple[EventEntityExperimentInput, ...],
    validation_inputs: tuple[EventEntityExperimentInput, ...],
) -> AttachmentHeadRoutingReport:
    """Build one complete model-free CEA-1.18 report."""
    development = build_dependency_head_routing_phase(
        transfer=predecessor.development,
        inputs=development_inputs,
    )
    validation = build_dependency_head_routing_phase(
        transfer=predecessor.validation,
        inputs=validation_inputs,
    )
    structural = development.head_aligned_count + validation.head_aligned_count
    semantic = development.semantic_count + validation.semantic_count
    outcome = classify_dependency_head_routing_outcome(
        development,
        validation,
    )
    draft = AttachmentHeadRoutingReport.model_construct(
        inputs=tuple(sorted(inputs, key=lambda item: item.label)),
        predecessor_result_fingerprint=predecessor.result_fingerprint,
        development=development,
        validation=validation,
        outcome=outcome,
        structural_route_count=structural,
        semantic_route_count=semantic,
        projected_model_call_reduction=structural / 17,
        result_fingerprint="0" * 64,
    )
    return AttachmentHeadRoutingReport(
        **draft.model_dump(exclude={"result_fingerprint"}),
        result_fingerprint=attachment_head_routing_fingerprint(draft),
    )


def render_dependency_head_routing_review(report: AttachmentHeadRoutingReport) -> str:
    """Render exact data-in, route evidence, and data-out for every case."""
    negative_count = (
        report.development.head_aligned_negative_count
        + report.validation.head_aligned_negative_count
    )
    lines = [
        "# CEA-1.18 Dependency-Head Residual Routing Review",
        "",
        f"Outcome: `{report.outcome.value}`",
        "",
        f"Structural Routes: `{report.structural_route_count}`",
        "",
        f"Semantic Routes: `{report.semantic_route_count}`",
        "",
        f"Projected Qwen call reduction: `{report.projected_model_call_reduction}`",
        "",
        _phase_summary(report.development),
        "",
        _phase_summary(report.validation),
        "",
        f"Head-Aligned Gold-negative coverage: `{negative_count}`",
        "",
    ]
    for phase in (report.development, report.validation):
        for case in phase.cases:
            task = case.transfer_case.task.edge_filter_task
            anchor = case.syntax.event_anchor
            roots = case.candidate_root_evidence.roots
            lines.extend(
                [
                    f"## {phase.phase} — {case.transfer_case.task.id}",
                    "",
                    "Exact SourceSegment:",
                    "",
                    "~~~~text",
                    task.source_text,
                    "~~~~",
                    "",
                    f"Candidate: `{json.dumps(task.candidate.text, ensure_ascii=False)}`",
                    "",
                    f"Event: `{json.dumps(task.edge.event_range.text, ensure_ascii=False)}`",
                    "",
                    f"Expected answer: `{case.transfer_case.gold.expected_answer}`",
                    "",
                    "Candidate Roots:",
                    "",
                    *(
                        [f"- {_token_line(item)}" for item in roots]
                        or ["- none; dependency gap retained"]
                    ),
                    "",
                    "Event Anchor:",
                    "",
                    f"- {_token_line(anchor) if anchor is not None else 'none'}",
                    "",
                    f"Dependency hypothesis: `{case.syntax.hypothesis.value}`",
                    "",
                    "Dependency gap: "
                    f"`{case.syntax.gap_code.value if case.syntax.gap_code else 'none'}`",
                    "",
                    "Dependency path:",
                    "",
                    *(
                        [
                            "- "
                            f"`{item.from_token_id}` -> `{item.to_token_id}` "
                            f"via `{item.dependency_relation}` ({item.direction.value})"
                            for item in case.syntax.path_steps
                        ]
                        or ["- none"]
                    ),
                    "",
                    f"CEA-1.17 baseline answers: `{case.baseline_answers}`",
                    "",
                    f"Route: `{case.route.value}`",
                    "",
                    f"Routed answers: `{case.routed_answers}`",
                    "",
                    f"Evaluation: `{'correct' if case.routed_correct else 'wrong'}`",
                    "",
                    f"Recovery: `{case.recovered}`; regression: `{case.regressed}`",
                    "",
                ]
            )
    return "\n".join(lines).rstrip() + "\n"


def render_dependency_head_routing_handoff(
    report: AttachmentHeadRoutingReport,
    *,
    package_files: Sequence[AttachmentEvidenceReference],
    source_repository_url: str,
    source_revision: str,
) -> str:
    """Render a self-contained CEA-1.18 independent-review handoff."""
    negative_count = (
        report.development.head_aligned_negative_count
        + report.validation.head_aligned_negative_count
    )
    coverage_note = (
        "Treat zero Head-Aligned Gold-negative coverage as a production blocker even if the "
        "registered hypothesis is supported."
        if negative_count == 0
        else "Inspect every Head-Aligned Gold-negative decision before production integration."
    )
    return "\n".join(
        [
            "# CEA-1.18 Dependency-Head Residual Routing Handoff",
            "",
            "Independently verify whether exact Candidate/Event head alignment provides a "
            "sound bounded Structural Route.",
            "",
            "The experiment reuses seventeen frozen CEA-1.17 cases and invokes no model.",
            "",
            "The Structural Route maps a Candidate to `Y` only when the Candidate has one "
            "dependency root and that token is the Event Anchor.",
            "",
            "Every other case preserves the two frozen CEA-1.17 threshold decisions.",
            "",
            f"The sealed inventory contains `{negative_count}` Head-Aligned Gold-negative cases.",
            "",
            coverage_note,
            "",
            render_dependency_head_routing_review(report).rstrip(),
            "",
            "## Package files",
            "",
            *[
                f"- `{item.label}`: `{item.path}` (`sha256:{item.sha256}`)"
                for item in sorted(package_files, key=lambda item: item.label)
            ],
            "",
            f"Source repository: {source_repository_url}",
            "",
            f"Source revision: `{source_revision}`",
            "",
            f"Result fingerprint: `{report.result_fingerprint}`",
            "",
        ]
    )


def _metrics(
    cases: tuple[AttachmentHeadRoutingCase, ...],
    repetition: int,
    *,
    routed: bool,
) -> AttachmentBinaryMetrics:
    tp = fp = tn = false_negative = 0
    for case in cases:
        observed = case.routed_answers[repetition] if routed else case.baseline_answers[repetition]
        expected = case.transfer_case.gold.expected_answer
        if expected == "Y" and observed == "Y":
            tp += 1
        elif expected == "Y":
            false_negative += 1
        elif observed == "Y":
            fp += 1
        else:
            tn += 1
    sensitivity = _ratio(tp, tp + false_negative)
    precision = _ratio(tp, tp + fp)
    return AttachmentBinaryMetrics(
        true_positive_count=tp,
        false_positive_count=fp,
        true_negative_count=tn,
        false_negative_count=false_negative,
        sensitivity=sensitivity,
        specificity=_ratio(tn, tn + fp),
        precision=precision,
        f1=_ratio(2 * precision * sensitivity, precision + sensitivity),
        accuracy=_ratio(tp + tn, len(cases)),
    )


def _phase_summary(phase: AttachmentHeadRoutingPhase) -> str:
    baseline = tuple(item.accuracy for item in phase.baseline_metrics)
    routed = tuple(item.accuracy for item in phase.routed_metrics)
    return (
        f"{phase.phase.title()} accuracy: baseline `{baseline}`; routed `{routed}`; "
        f"recoveries `{phase.recovered_count}`; regressions `{phase.regressed_count}`"
    )


def _token_line(token: PredicateArgumentToken | None) -> str:
    if token is None:
        return "none"
    return (
        f"`{token.token_id}` `{json.dumps(token.text, ensure_ascii=False)}` "
        f"`[{token.start},{token.end})` head `{token.head_token_id}` "
        f"relation `{token.dependency_relation}`"
    )


def _ratio(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 0.0
