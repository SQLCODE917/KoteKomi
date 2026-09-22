from __future__ import annotations

import hashlib
import json
from base64 import b64encode
from pathlib import Path

import pytest
from kotekomi_application import (
    AttachmentEdgeFilterAnswerValue,
    AttachmentEdgeFilterDecision,
    AttachmentEdgeFilterDecisionStatus,
    AttachmentEdgeFilterTask,
    AttachmentEvidenceReference,
    AttachmentLocalModelVariant,
    AttachmentNestedTransferCatalog,
    AttachmentNestedTransferDecision,
    AttachmentNestedTransferObservation,
    AttachmentNestedTransferReport,
    AttachmentNestedTransferSelectorCatalog,
    AttachmentNestedTransferSubmission,
    attachment_nested_event_ownership_model_task_input,
)
from kotekomi_pipelines.competitive_attachment_local_model_swap import (
    build_attachment_local_model_swap_preflight,
    build_attachment_local_model_swap_report,
    map_lm_studio_model_artifact,
)
from kotekomi_pipelines.competitive_attachment_nested_event_transfer import (
    build_attachment_nested_transfer_catalog,
    build_attachment_nested_transfer_report,
)

ROOT = Path(__file__).resolve().parents[3]
SELECTORS = ROOT / "docs/cea123-nested-event-transfer-catalog-v1.json"
SOURCE_CATALOG = ROOT / "docs/organization-mention-held-out-gold-v1.json"
PROMPT = ROOT / "prompts/competitive_attachment_nested_event_ownership_v1.md"


def test_preflight_locks_model_specific_transport_allowances() -> None:
    evidence = AttachmentEvidenceReference(
        label="fixture",
        path="/tmp/fixture",
        sha256="a" * 64,
    )

    preflight = build_attachment_local_model_swap_preflight(
        inputs=(evidence,),
        baseline_root="/tmp/baseline",
        baseline_report=evidence,
        blind_review_response=evidence,
        semantic_prompt=evidence,
    )

    assert preflight.comparator_effective_max_output_tokens == 2
    assert preflight.challenger_effective_max_output_tokens == 16


def test_lm_studio_model_metadata_maps_exact_loaded_qwen3_variant() -> None:
    artifact = map_lm_studio_model_artifact(
        payload=_metadata("Q6_K"),
        configured_instance_id="qwen3-14b-q6-k-nonthinking",
        variant=AttachmentLocalModelVariant.Q6_K,
        estimated_total_memory_gib=13.5,
        readiness_evidence_sha256="c" * 64,
        fallback_reason=None,
    )

    assert artifact.model_key == "lmstudio-community/qwen3-14b-gguf"
    assert artifact.quantization == "Q6_K"
    assert artifact.loaded_instance_id == "qwen3-14b-q6-k-nonthinking"
    assert artifact.context_length == 16_384


def test_lm_studio_model_metadata_rejects_wrong_quantization() -> None:
    with pytest.raises(ValueError, match="does not match"):
        map_lm_studio_model_artifact(
            payload=_metadata("Q5_K_M"),
            configured_instance_id="qwen3-14b-q6-k-nonthinking",
            variant=AttachmentLocalModelVariant.Q6_K,
            estimated_total_memory_gib=13.5,
            readiness_evidence_sha256="c" * 64,
            fallback_reason=None,
        )


def test_lm_studio_model_metadata_requires_exact_loaded_instance() -> None:
    with pytest.raises(ValueError, match="one configured model instance"):
        map_lm_studio_model_artifact(
            payload=_metadata("Q6_K"),
            configured_instance_id="another-instance",
            variant=AttachmentLocalModelVariant.Q6_K,
            estimated_total_memory_gib=13.5,
            readiness_evidence_sha256="c" * 64,
            fallback_reason=None,
        )


def test_model_swap_report_recomputes_occurrence_transitions(tmp_path: Path) -> None:
    catalog = _catalog()
    submission = _submission(catalog)
    historical = _transfer_report(
        tmp_path=tmp_path,
        label="historical",
        catalog=catalog,
        submission=submission,
        correct_through=15,
    )
    comparator = _transfer_report(
        tmp_path=tmp_path,
        label="comparator",
        catalog=catalog,
        submission=submission,
        correct_through=16,
    )
    challenger = _transfer_report(
        tmp_path=tmp_path,
        label="challenger",
        catalog=catalog,
        submission=submission,
        correct_through=18,
    )
    evidence = AttachmentEvidenceReference(label="fixture", path="/tmp/fixture", sha256="a" * 64)

    report = build_attachment_local_model_swap_report(
        inputs=(evidence,),
        preflight=evidence,
        output_calibration=evidence,
        model_artifact=map_lm_studio_model_artifact(
            payload=_metadata("Q6_K"),
            configured_instance_id="qwen3-14b-q6-k-nonthinking",
            variant=AttachmentLocalModelVariant.Q6_K,
            estimated_total_memory_gib=13.5,
            readiness_evidence_sha256="c" * 64,
            fallback_reason=None,
        ),
        historical_baseline=historical,
        comparator_baseline=comparator,
        challenger=challenger,
        comparator_effective_max_output_tokens=2,
        challenger_effective_max_output_tokens=16,
    )

    assert report.historical_baseline_correct_count == 15
    assert report.comparator_baseline_correct_count == 16
    assert report.challenger_correct_count == 18
    assert report.output_calibration == evidence
    assert report.comparator_effective_max_output_tokens == 2
    assert report.challenger_effective_max_output_tokens == 16
    assert len(report.context_corrected_case_ids) == 1
    assert report.context_regressed_case_ids == ()
    assert len(report.corrected_case_ids) == 2
    assert report.regressed_case_ids == ()


def test_model_swap_report_rejects_more_than_terminal_nonthinking_change(
    tmp_path: Path,
) -> None:
    catalog = _catalog()
    submission = _submission(catalog)
    comparator = _transfer_report(
        tmp_path=tmp_path,
        label="comparator",
        catalog=catalog,
        submission=submission,
        correct_through=16,
    )
    challenger = _transfer_report(
        tmp_path=tmp_path,
        label="challenger",
        catalog=catalog,
        submission=submission,
        correct_through=18,
    )
    first = challenger.evaluations[0]
    changed_observation = first.observation.model_copy(update={"exact_model_input": "changed"})
    changed_first = first.model_copy(update={"observation": changed_observation})
    changed_challenger = challenger.model_copy(
        update={"evaluations": (changed_first, *challenger.evaluations[1:])}
    )
    evidence = AttachmentEvidenceReference(label="fixture", path="/tmp/fixture", sha256="a" * 64)

    with pytest.raises(ValueError, match="changed more than"):
        build_attachment_local_model_swap_report(
            inputs=(evidence,),
            preflight=evidence,
            output_calibration=evidence,
            model_artifact=map_lm_studio_model_artifact(
                payload=_metadata("Q6_K"),
                configured_instance_id="qwen3-14b-q6-k-nonthinking",
                variant=AttachmentLocalModelVariant.Q6_K,
                estimated_total_memory_gib=13.5,
                readiness_evidence_sha256="c" * 64,
                fallback_reason=None,
            ),
            historical_baseline=comparator,
            comparator_baseline=comparator,
            challenger=changed_challenger,
            comparator_effective_max_output_tokens=2,
            challenger_effective_max_output_tokens=16,
        )


def _metadata(quantization: str) -> dict[str, object]:
    return {
        "models": [
            {
                "type": "llm",
                "publisher": "lmstudio-community",
                "key": "lmstudio-community/qwen3-14b-gguf",
                "display_name": "Qwen3 14B",
                "architecture": "qwen3",
                "quantization": {"name": quantization, "bits_per_weight": 6.5},
                "size_bytes": 12_100_000_000,
                "params_string": "14B",
                "loaded_instances": [
                    {
                        "id": "qwen3-14b-q6-k-nonthinking",
                        "config": {"context_length": 16_384},
                    }
                ],
                "max_context_length": 32768,
                "format": "gguf",
            }
        ]
    }


def _transfer_report(
    *,
    tmp_path: Path,
    label: str,
    catalog: AttachmentNestedTransferCatalog,
    submission: AttachmentNestedTransferSubmission,
    correct_through: int,
) -> AttachmentNestedTransferReport:
    evidence = tmp_path / f"{label}.json"
    evidence.write_text("{}\n", encoding="utf-8")
    expected = {item.case_id: item.answer for item in submission.decisions}
    observations = tuple(
        _observation(
            case_id=case.id,
            task_id=case.task.task_id,
            edge_id=case.task.edge.id,
            answer=(
                expected[case.id]
                if index <= correct_through
                else ("N" if expected[case.id] == "Y" else "Y")
            ),
            evidence=evidence,
            exact_model_input=_exact_model_input(case.task, label),
        )
        for index, case in enumerate(catalog.cases, start=1)
    )
    return build_attachment_nested_transfer_report(
        inputs=(_reference(label, evidence),),
        catalog=catalog,
        submission=submission,
        observations=observations,
    )


def _exact_model_input(task: AttachmentEdgeFilterTask, label: str) -> str:
    if label == "historical":
        return "historical re-segmented input"
    semantic = attachment_nested_event_ownership_model_task_input(task).decode()
    exact = f"[direct_prose]\n[paragraph]\n{task.source_text}\n\n[task]\n{semantic}"
    return exact + "\n/no_think\n" if label == "challenger" else exact


def _catalog() -> AttachmentNestedTransferCatalog:
    selectors = AttachmentNestedTransferSelectorCatalog.model_validate_json(SELECTORS.read_bytes())
    return build_attachment_nested_transfer_catalog(
        selector_catalog=selectors,
        source_catalog=json.loads(SOURCE_CATALOG.read_text(encoding="utf-8")),
        inputs=(
            _reference("selectors", SELECTORS),
            _reference("source_catalog", SOURCE_CATALOG),
        ),
        prompt=_reference("prompt", PROMPT),
    )


def _submission(catalog: AttachmentNestedTransferCatalog) -> AttachmentNestedTransferSubmission:
    return AttachmentNestedTransferSubmission(
        reviewer="blind reviewer",
        decisions=tuple(
            AttachmentNestedTransferDecision(
                case_id=case.id,
                answer="Y" if index <= 12 else "N",
                rationale="The exact source decides this ownership.",
            )
            for index, case in enumerate(catalog.cases, start=1)
        ),
    )


def _observation(
    *,
    case_id: str,
    task_id: str,
    edge_id: str,
    answer: str,
    evidence: Path,
    exact_model_input: str,
) -> AttachmentNestedTransferObservation:
    raw = answer.encode()
    typed_answer = AttachmentEdgeFilterAnswerValue(answer)
    return AttachmentNestedTransferObservation(
        case_id=case_id,
        decision=AttachmentEdgeFilterDecision(
            task_id=task_id,
            edge_id=edge_id,
            status=AttachmentEdgeFilterDecisionStatus.COMPLETE,
            answer=typed_answer,
            retained=typed_answer is AttachmentEdgeFilterAnswerValue.YES,
            unresolved=False,
            extraction_task_id="ext_fixture",
            model_run_id="mrun_fixture",
            trace_id="xtr_fixture",
            raw_output_sha256=hashlib.sha256(raw).hexdigest(),
            diagnostic_code=None,
        ),
        execution_record=_reference(f"execution_{case_id}", evidence),
        exact_model_input=exact_model_input,
        raw_output_base64=b64encode(raw).decode(),
        model_identity_digest="b" * 64,
        elapsed_milliseconds=1,
        runtime_invoked=True,
    )


def _reference(label: str, path: Path) -> AttachmentEvidenceReference:
    return AttachmentEvidenceReference(
        label=label,
        path=str(path.resolve()),
        sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
    )
