from __future__ import annotations

import hashlib

from kotekomi_application import (
    PropositionFragmentAnswerValue,
    PropositionFragmentTaskInput,
    PropositionFragmentTaskInputStatus,
)
from kotekomi_pipelines.proposition_input_format_stage_local import (
    PropositionInputFormatObservation,
    PropositionInputGoldClass,
    PropositionInputHypothesisOutcome,
    build_proposition_input_format_report,
)


def test_paired_report_scores_only_the_identical_unique_occurrence_subset() -> None:
    observations = (
        _ready_observation(1, PropositionInputGoldClass.COMPATIBLE, "N", "Y"),
        _ready_observation(2, PropositionInputGoldClass.COMPATIBLE, "Y", "Y"),
        _ready_observation(3, PropositionInputGoldClass.OVERREACHING, "Y", "N"),
        _ready_observation(4, PropositionInputGoldClass.OVERREACHING, "N", "N"),
        _ambiguous_observation(5),
    )

    report = build_proposition_input_format_report(
        baseline_run_sha256="a" * 64,
        prompt_sha256="b" * 64,
        observations=observations,
    )

    assert report.observation_count == 5
    assert report.eligible_candidate_count == 4
    assert report.excluded_ambiguous_candidate_count == 1
    assert report.baseline_metrics.accuracy == 0.5
    assert report.marker_free_metrics.accuracy == 1.0
    assert report.marker_free_metrics.true_positive_count == 2
    assert report.marker_free_metrics.true_negative_count == 2
    assert report.hypothesis_outcome is PropositionInputHypothesisOutcome.SUPPORTED
    assert sum(item.count for item in report.transitions) == 4


def _ready_observation(
    ordinal: int,
    gold_class: PropositionInputGoldClass,
    baseline: str,
    marker_free: str,
) -> PropositionInputFormatObservation:
    source = f"Actor{ordinal} criticized Plan{ordinal}."
    candidate = f"Actor{ordinal}"
    candidate_id = f"pfc_{ordinal:024x}"
    rendered = f"Passage:\n{source}\n\nEvent:\ncriticized\n\nCandidate:\n{candidate}\n"
    task = PropositionFragmentTaskInput(
        candidate_id=candidate_id,
        source_text_sha256=hashlib.sha256(source.encode()).hexdigest(),
        status=PropositionFragmentTaskInputStatus.READY,
        event_occurrence_count=1,
        candidate_occurrence_count=1,
        rendered_input=rendered,
        rendered_input_sha256=hashlib.sha256(rendered.encode()).hexdigest(),
        reason_code=None,
    )
    return PropositionInputFormatObservation(
        event_id=f"TGE-{ordinal:03d}",
        candidate_id=candidate_id,
        source_text=source,
        source_text_sha256=task.source_text_sha256,
        event_text="criticized",
        candidate_start=0,
        candidate_end=len(candidate),
        candidate_text=candidate,
        gold_class=gold_class,
        task_input=task,
        baseline_exact_model_input="baseline tagged input",
        baseline_raw_output=baseline,
        baseline_answer=PropositionFragmentAnswerValue(baseline),
        baseline_trace_id=f"xst_{ordinal:024x}",
        marker_free_exact_model_input="prompt\n\n[task]\n" + rendered,
        marker_free_raw_output=marker_free,
        marker_free_answer=PropositionFragmentAnswerValue(marker_free),
        marker_free_execution_status="completed",
        marker_free_trace_id=f"xst_{ordinal + 100:024x}",
        marker_free_model_run_id=f"mrn_{ordinal:032x}",
    )


def _ambiguous_observation(ordinal: int) -> PropositionInputFormatObservation:
    source = "Actor criticized Actor."
    candidate = "Actor"
    candidate_id = f"pfc_{ordinal:024x}"
    task = PropositionFragmentTaskInput(
        candidate_id=candidate_id,
        source_text_sha256=hashlib.sha256(source.encode()).hexdigest(),
        status=PropositionFragmentTaskInputStatus.OCCURRENCE_AMBIGUOUS,
        event_occurrence_count=1,
        candidate_occurrence_count=2,
        rendered_input=None,
        rendered_input_sha256=None,
        reason_code="candidate_occurrence_ambiguous",
    )
    return PropositionInputFormatObservation(
        event_id=f"TGE-{ordinal:03d}",
        candidate_id=candidate_id,
        source_text=source,
        source_text_sha256=task.source_text_sha256,
        event_text="criticized",
        candidate_start=0,
        candidate_end=len(candidate),
        candidate_text=candidate,
        gold_class=PropositionInputGoldClass.COMPATIBLE,
        task_input=task,
        baseline_exact_model_input="baseline tagged input",
        baseline_raw_output="Y",
        baseline_answer=PropositionFragmentAnswerValue.YES,
        baseline_trace_id=f"xst_{ordinal:024x}",
        marker_free_exact_model_input=None,
        marker_free_raw_output=None,
        marker_free_answer=None,
        marker_free_execution_status="not_run",
        marker_free_trace_id=f"xst_{ordinal + 100:024x}",
        marker_free_model_run_id=None,
    )
