"""Build and render CEA-1.24 local model swap evidence."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import cast

from kotekomi_application import (
    AttachmentEvidenceReference,
    AttachmentLocalModelArtifact,
    AttachmentLocalModelSwapCase,
    AttachmentLocalModelSwapPreflight,
    AttachmentLocalModelSwapReport,
    AttachmentLocalModelSwapTransition,
    AttachmentLocalModelVariant,
    AttachmentNestedTransferReport,
    attachment_local_model_swap_fingerprint,
    attachment_local_model_swap_preflight_fingerprint,
    attachment_local_model_swap_transition,
    classify_attachment_local_model_swap_outcome,
)


def build_attachment_local_model_swap_preflight(
    *,
    inputs: tuple[AttachmentEvidenceReference, ...],
    baseline_root: str,
    baseline_report: AttachmentEvidenceReference,
    blind_review_response: AttachmentEvidenceReference,
    semantic_prompt: AttachmentEvidenceReference,
) -> AttachmentLocalModelSwapPreflight:
    """Bind the immutable CEA-1.23 evidence before Challenger execution."""
    draft = AttachmentLocalModelSwapPreflight.model_construct(
        inputs=inputs,
        baseline_root=baseline_root,
        baseline_report=baseline_report,
        blind_review_response=blind_review_response,
        semantic_prompt=semantic_prompt,
        case_count=20,
        primary_variant=AttachmentLocalModelVariant.Q6_K,
        fallback_variant=AttachmentLocalModelVariant.Q5_K_M,
        nonthinking_control="/no_think",
        comparator_effective_max_output_tokens=2,
        challenger_effective_max_output_tokens=16,
        result_fingerprint="0" * 64,
    )
    return AttachmentLocalModelSwapPreflight(
        **draft.model_dump(exclude={"result_fingerprint"}),
        result_fingerprint=attachment_local_model_swap_preflight_fingerprint(draft),
    )


def map_lm_studio_model_artifact(
    *,
    payload: Mapping[str, object],
    configured_instance_id: str,
    variant: AttachmentLocalModelVariant,
    estimated_total_memory_gib: float,
    readiness_evidence_sha256: str,
    fallback_reason: str | None,
) -> AttachmentLocalModelArtifact:
    """Map one exact loaded LM Studio model into experiment evidence."""
    models = payload.get("models")
    if not isinstance(models, Sequence) or isinstance(models, (str, bytes)):
        raise ValueError("LM Studio model metadata requires a models array.")
    matches: list[tuple[Mapping[str, object], Mapping[str, object]]] = []
    for raw_model in cast(Sequence[object], models):
        if not isinstance(raw_model, Mapping):
            raise ValueError("LM Studio model metadata contains an invalid model.")
        model = cast(Mapping[str, object], raw_model)
        loaded = model.get("loaded_instances")
        if not isinstance(loaded, Sequence) or isinstance(loaded, (str, bytes)):
            raise ValueError("LM Studio model metadata requires loaded instances.")
        for raw_instance in cast(Sequence[object], loaded):
            if not isinstance(raw_instance, Mapping):
                raise ValueError("LM Studio model metadata contains an invalid instance.")
            instance = cast(Mapping[str, object], raw_instance)
            if instance.get("id") == configured_instance_id:
                matches.append((model, instance))
    if len(matches) != 1:
        raise ValueError("LM Studio metadata must identify one configured model instance.")
    model, instance = matches[0]
    quantization = _mapping(model, "quantization")
    config = _mapping(instance, "config")
    artifact = AttachmentLocalModelArtifact(
        variant=variant,
        model_key=_string(model, "key"),
        display_name=_string(model, "display_name"),
        architecture=_string(model, "architecture"),
        quantization=_string(quantization, "name"),
        bits_per_weight=_number(quantization, "bits_per_weight"),
        size_bytes=_integer(model, "size_bytes"),
        params_string=_string(model, "params_string"),
        format=_string(model, "format"),
        loaded_instance_id=_string(instance, "id"),
        context_length=_integer(config, "context_length"),
        max_context_length=_integer(model, "max_context_length"),
        estimated_total_memory_gib=estimated_total_memory_gib,
        resource_guardrail_allows_load=True,
        readiness_evidence_sha256=readiness_evidence_sha256,
        fallback_reason=fallback_reason,
        metadata_sha256=hashlib.sha256(_canonical(payload)).hexdigest(),
    )
    if artifact.loaded_instance_id != configured_instance_id:
        raise ValueError("Loaded model instance differs from the configured identifier.")
    return artifact


def build_attachment_local_model_swap_report(
    *,
    inputs: tuple[AttachmentEvidenceReference, ...],
    preflight: AttachmentEvidenceReference,
    output_calibration: AttachmentEvidenceReference,
    model_artifact: AttachmentLocalModelArtifact,
    historical_baseline: AttachmentNestedTransferReport,
    comparator_baseline: AttachmentNestedTransferReport,
    challenger: AttachmentNestedTransferReport,
    comparator_effective_max_output_tokens: int,
    challenger_effective_max_output_tokens: int,
) -> AttachmentLocalModelSwapReport:
    """Compare one Challenger with an exact-context Qwen2.5 comparator."""
    reports = (historical_baseline, comparator_baseline, challenger)
    if any(item.case_count != 20 for item in reports):
        raise ValueError("Local model swap requires three complete twenty-case reports.")
    _validate_exact_model_input_parity(comparator_baseline, challenger)
    cases = tuple(
        AttachmentLocalModelSwapCase(
            case_id=historical_item.case.id,
            historical_baseline=historical_item,
            comparator_baseline=comparator_item,
            challenger=challenger_item,
            context_transition=attachment_local_model_swap_transition(
                historical_item,
                comparator_item,
            ),
            model_transition=attachment_local_model_swap_transition(
                comparator_item,
                challenger_item,
            ),
        )
        for historical_item, comparator_item, challenger_item in zip(
            historical_baseline.evaluations,
            comparator_baseline.evaluations,
            challenger.evaluations,
            strict=True,
        )
    )
    context_groups = {
        transition: tuple(item.case_id for item in cases if item.context_transition is transition)
        for transition in AttachmentLocalModelSwapTransition
    }
    model_groups = {
        transition: tuple(item.case_id for item in cases if item.model_transition is transition)
        for transition in AttachmentLocalModelSwapTransition
    }
    draft = AttachmentLocalModelSwapReport.model_construct(
        inputs=inputs,
        preflight=preflight,
        output_calibration=output_calibration,
        model_artifact=model_artifact,
        cases=cases,
        outcome=classify_attachment_local_model_swap_outcome(cases),
        case_count=20,
        historical_baseline_correct_count=historical_baseline.correct_count,
        comparator_baseline_correct_count=comparator_baseline.correct_count,
        challenger_correct_count=challenger.correct_count,
        historical_baseline_accuracy=historical_baseline.accuracy,
        comparator_baseline_accuracy=comparator_baseline.accuracy,
        challenger_accuracy=challenger.accuracy,
        accuracy_delta=challenger.accuracy - comparator_baseline.accuracy,
        challenger_yes_recall=challenger.yes_recall,
        challenger_no_recall=challenger.no_recall,
        context_corrected_case_ids=context_groups[AttachmentLocalModelSwapTransition.CORRECTED],
        context_regressed_case_ids=context_groups[AttachmentLocalModelSwapTransition.REGRESSED],
        corrected_case_ids=model_groups[AttachmentLocalModelSwapTransition.CORRECTED],
        regressed_case_ids=model_groups[AttachmentLocalModelSwapTransition.REGRESSED],
        unchanged_correct_case_ids=model_groups[
            AttachmentLocalModelSwapTransition.UNCHANGED_CORRECT
        ],
        unchanged_incorrect_case_ids=model_groups[
            AttachmentLocalModelSwapTransition.UNCHANGED_INCORRECT
        ],
        unresolved_case_ids=model_groups[AttachmentLocalModelSwapTransition.UNRESOLVED],
        comparator_baseline_model_elapsed_milliseconds=(
            comparator_baseline.model_elapsed_milliseconds
        ),
        challenger_model_elapsed_milliseconds=challenger.model_elapsed_milliseconds,
        challenger_model_identity_digests=challenger.model_identity_digests,
        comparator_effective_max_output_tokens=comparator_effective_max_output_tokens,
        challenger_effective_max_output_tokens=challenger_effective_max_output_tokens,
        proposed_change_count=0,
        accepted_ledger_change_count=0,
        production_integration="not_activated",
        result_fingerprint="0" * 64,
    )
    return AttachmentLocalModelSwapReport(
        **draft.model_dump(exclude={"result_fingerprint"}),
        result_fingerprint=attachment_local_model_swap_fingerprint(draft),
    )


def render_attachment_local_model_swap_review(report: AttachmentLocalModelSwapReport) -> str:
    """Render one compact human-readable model comparison."""
    lines = [
        "# CEA-1.24 Local Model Swap Result",
        "",
        f"Outcome: `{report.outcome.value}`",
        "",
        f"Variant: `{report.model_artifact.variant.value}`",
        "",
        f"Model key: `{report.model_artifact.model_key}`",
        "",
        f"Quantization: `{report.model_artifact.quantization}`",
        "",
        f"Output calibration: `{report.output_calibration.path}`",
        "",
        f"Historical Baseline correct: `{report.historical_baseline_correct_count}` / `20`",
        "",
        f"Comparator Baseline correct: `{report.comparator_baseline_correct_count}` / `20`",
        "",
        f"Challenger correct: `{report.challenger_correct_count}` / `20`",
        "",
        f"Accuracy delta: `{report.accuracy_delta:.6f}`",
        "",
        f"Challenger Y recall: `{report.challenger_yes_recall:.6f}`",
        "",
        f"Challenger N recall: `{report.challenger_no_recall:.6f}`",
        "",
        "Effective output-token limits, Comparator / Challenger: "
        f"`{report.comparator_effective_max_output_tokens}` / "
        f"`{report.challenger_effective_max_output_tokens}`",
        "",
        f"Corrected / regressed: `{len(report.corrected_case_ids)}` / "
        f"`{len(report.regressed_case_ids)}`",
        "",
        "## Case comparisons",
    ]
    for item in report.cases:
        historical_answer = item.historical_baseline.observation.decision.answer
        comparator_answer = item.comparator_baseline.observation.decision.answer
        challenger_answer = item.challenger.observation.decision.answer
        lines.extend(
            [
                "",
                f"### {item.comparator_baseline.case.selector_id} — "
                f"context `{item.context_transition.value}`, model `{item.model_transition.value}`",
                "",
                f"> {item.comparator_baseline.case.task.source_text}",
                "",
                f"Candidate: {json.dumps(item.comparator_baseline.case.task.candidate.text)}",
                "",
                f"Target Event: {json.dumps(_target_text(item))}",
                "",
                f"Expected: `{item.comparator_baseline.expected.answer}`",
                "",
                "Historical Baseline: "
                f"`{historical_answer.value if historical_answer else 'unresolved'}`",
                "",
                "Comparator Baseline: "
                f"`{comparator_answer.value if comparator_answer else 'unresolved'}`",
                "",
                f"Challenger: `{challenger_answer.value if challenger_answer else 'unresolved'}`",
            ]
        )
    return "\n".join(lines) + "\n"


def _target_text(item: AttachmentLocalModelSwapCase) -> str:
    task = item.comparator_baseline.case.task
    return next(
        option.text for option in task.event_options if option.label == task.target_event_label
    )


def _validate_exact_model_input_parity(
    comparator: AttachmentNestedTransferReport,
    challenger: AttachmentNestedTransferReport,
) -> None:
    for comparator_item, challenger_item in zip(
        comparator.evaluations,
        challenger.evaluations,
        strict=True,
    ):
        source_text = comparator_item.case.task.source_text
        comparator_input = comparator_item.observation.exact_model_input
        context_copy = f"[direct_prose]\n[paragraph]\n{source_text}"
        task_copy = f"Passage:\n{source_text}\n"
        if (
            comparator_input.count(source_text) != 2
            or comparator_input.count(context_copy) != 1
            or comparator_input.count(task_copy) != 1
            or "SOURCE SEGMENT:" in comparator_input
        ):
            raise ValueError("Comparator Baseline does not preserve Exact Source Context.")
        expected = comparator_input + "\n/no_think\n"
        if challenger_item.observation.exact_model_input != expected:
            raise ValueError("Challenger changed more than the terminal Non-Thinking Control.")


def _mapping(value: Mapping[str, object], key: str) -> Mapping[str, object]:
    result = value.get(key)
    if not isinstance(result, Mapping):
        raise ValueError(f"LM Studio model metadata requires object {key}.")
    return cast(Mapping[str, object], result)


def _string(value: Mapping[str, object], key: str) -> str:
    result = value.get(key)
    if not isinstance(result, str) or not result:
        raise ValueError(f"LM Studio model metadata requires string {key}.")
    return result


def _integer(value: Mapping[str, object], key: str) -> int:
    result = value.get(key)
    if not isinstance(result, int) or isinstance(result, bool):
        raise ValueError(f"LM Studio model metadata requires integer {key}.")
    return result


def _number(value: Mapping[str, object], key: str) -> float:
    result = value.get(key)
    if not isinstance(result, (int, float)) or isinstance(result, bool):
        raise ValueError(f"LM Studio model metadata requires number {key}.")
    return float(result)


def _canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
