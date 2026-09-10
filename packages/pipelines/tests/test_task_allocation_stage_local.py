from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest
from kotekomi_application import (
    ContextualKind,
    DiscourseRole,
    HybridPreviewStatus,
    MentionProposal,
    Referentiality,
    build_hybrid_extraction_preview,
)
from kotekomi_application.extraction_stage_trace import (
    ExtractionStageStatus,
    build_extraction_stage_trace,
)
from kotekomi_application.hybrid_mention_interpretation import (
    MentionInterpretationDraft,
    fuse_mention_observations,
    observation_from_proposal,
    reconcile_mention_boundaries,
    resolve_mention_interpretation,
)
from kotekomi_pipelines.task_allocation_stage_local import (
    evaluate_stage_local_case,
    load_stage_local_inputs,
)

ROOT = Path(__file__).resolve().parents[3]
SPLIT = ROOT / "docs" / "hsq-stage-local-split-v2.json"
HISTORICAL_SPLIT = ROOT / "docs" / "hsq-stage-local-split-v1.json"


def test_stage_local_split_loads_twenty_development_and_twenty_validation_items() -> None:
    split, inputs = load_stage_local_inputs(SPLIT, repository_root=ROOT)

    assert len(split.development_item_ids) == 20
    assert len(split.validation_item_ids) == 20
    assert sum(item.phase == "development" for item in inputs) == 20
    assert sum(item.phase == "validation" for item in inputs) == 20
    development_sha = {item.source_text_sha256 for item in inputs if item.phase == "development"}
    validation_sha = {item.source_text_sha256 for item in inputs if item.phase == "validation"}
    assert development_sha.isdisjoint(validation_sha)


def test_stage_local_evaluator_correction_preserves_gold_and_accepts_source_boundary() -> None:
    _, corrected_inputs = load_stage_local_inputs(SPLIT, repository_root=ROOT)
    _, historical_inputs = load_stage_local_inputs(HISTORICAL_SPLIT, repository_root=ROOT)

    corrected = next(item for item in corrected_inputs if item.item.item_id == "ANT-14")
    historical = next(item for item in historical_inputs if item.item.item_id == "ANT-14")

    assert historical.item.expected_references[0].antecedent_text == "Sacks"
    assert historical.expected_references[0].accepted_antecedent_texts == ("Sacks",)
    assert corrected.item.expected_references[0].antecedent_text == "Sacks"
    assert corrected.expected_references[0].accepted_antecedent_texts == ("David  Sacks",)


def test_stage_local_split_rejects_source_segment_leakage(tmp_path: Path) -> None:
    value = json.loads(SPLIT.read_bytes())
    development = value["development_item_ids"]
    validation = value["validation_item_ids"]
    development[development.index("AMO-03")] = "AMO-01"
    validation[validation.index("AMO-01")] = "AMO-03"
    path = tmp_path / "leaking-split.json"
    path.write_text(json.dumps(value), encoding="utf-8")

    with pytest.raises(ValueError, match="leakage"):
        load_stage_local_inputs(path, repository_root=ROOT)


def test_stage_local_split_rejects_evaluator_correction_pin_drift(tmp_path: Path) -> None:
    value = json.loads(SPLIT.read_bytes())
    value["evaluator_corrections"]["sha256"] = "0" * 64
    path = tmp_path / "drifted-correction-split.json"
    path.write_text(json.dumps(value), encoding="utf-8")

    with pytest.raises(ValueError, match="evaluator-correction pin drifted"):
        load_stage_local_inputs(path, repository_root=ROOT)


def test_stage_local_evaluation_names_mention_proposal_as_the_first_failure() -> None:
    _, inputs = load_stage_local_inputs(SPLIT, repository_root=ROOT)
    stage_input = next(item for item in inputs if item.item.item_id == "ANT-02")
    preview = build_hybrid_extraction_preview(
        representation_id="rep_empty",
        paragraph_node_id="nod_empty",
        context_manifest_id="ctx_empty",
        ontology_card_sha256="a" * 64,
        terminal_status=HybridPreviewStatus.COMPLETE,
    )

    result = evaluate_stage_local_case(stage_input, preview, None)

    assert result.first_failed_stage == "mention_proposal"
    assert result.checks[0].actual == []


def test_stage_local_evaluation_accepts_source_bound_focus_mention() -> None:
    _, inputs = load_stage_local_inputs(SPLIT, repository_root=ROOT)
    stage_input = next(item for item in inputs if item.item.item_id == "ANT-02")
    source_segment_id = "seg_stage_local"
    start = stage_input.source_text.index("Anthropic")
    observation_trace = build_extraction_stage_trace(
        trace_run_id="stage_local",
        ordinal=0,
        stage_id="mention_proposal",
        stage_version="v1",
        producer_id="qwen2.5-fixture",
        source_segment_id=source_segment_id,
        source_text_sha256=stage_input.source_text_sha256,
        configuration={},
        input_payload={"source_text": stage_input.source_text},
        output_payload={},
        status=ExtractionStageStatus.COMPLETED,
    )
    observation = observation_from_proposal(
        proposal=MentionProposal(
            "s1",
            "Anthropic",
            start,
            start + len("Anthropic"),
            ("organization",),
        ),
        source_segment_id=source_segment_id,
        producer_id="qwen2.5-fixture",
        execution_record_id="mrn_fixture",
    )
    candidate = fuse_mention_observations(
        source_segments={source_segment_id: stage_input.source_text},
        observations=(observation,),
    )[0]
    decisions, _ = reconcile_mention_boundaries(
        source_segments={source_segment_id: stage_input.source_text},
        observations=(observation,),
        candidates=(candidate,),
    )
    boundary_trace = build_extraction_stage_trace(
        trace_run_id="stage_local",
        ordinal=1,
        stage_id="mention_boundary_reconciliation",
        stage_version="v1",
        producer_id="kotekomi_application",
        source_segment_id=source_segment_id,
        source_text_sha256=stage_input.source_text_sha256,
        configuration={},
        parent_trace_ids=(observation_trace.id,),
        input_payload={"candidate_id": candidate.id},
        output_payload={"decision_id": decisions[0].id},
        status=ExtractionStageStatus.COMPLETED,
    )
    interpretation_trace = build_extraction_stage_trace(
        trace_run_id="stage_local",
        ordinal=2,
        stage_id="mention_interpretation",
        stage_version="v1",
        producer_id="qwen2.5-fixture",
        source_segment_id=source_segment_id,
        source_text_sha256=stage_input.source_text_sha256,
        configuration={},
        parent_trace_ids=(boundary_trace.id,),
        input_record_ids=(candidate.id,),
        execution_record_ids=("ext_fixture", "mrn_fixture"),
        input_payload={"candidate": "c1"},
        output_payload={},
        status=ExtractionStageStatus.COMPLETED,
    )
    interpretation = resolve_mention_interpretation(
        draft=MentionInterpretationDraft(
            "c1",
            Referentiality.SPECIFIC_ENTITY,
            ContextualKind.ORGANIZATION,
            DiscourseRole.ACTOR,
            "s1",
        ),
        candidate_labels={"c1": candidate},
        source_segment_ids={"s1": source_segment_id},
        model_run_id="mrn_fixture",
        trace_id=interpretation_trace.id,
    )
    preview = build_hybrid_extraction_preview(
        representation_id="rep_stage_local",
        paragraph_node_id="nod_stage_local",
        context_manifest_id="ctx_stage_local",
        ontology_card_sha256=hashlib.sha256(b"ontology").hexdigest(),
        observations=(observation,),
        candidates=(candidate,),
        boundary_decisions=decisions,
        interpretations=(interpretation,),
        extraction_task_ids=("ext_fixture",),
        model_run_ids=("mrn_fixture",),
        traces=(observation_trace, boundary_trace, interpretation_trace),
        terminal_status=HybridPreviewStatus.COMPLETE,
    )

    result = evaluate_stage_local_case(stage_input, preview, None)

    assert result.passed is True
    assert result.first_failed_stage is None


def test_validation_runner_pins_contract_and_detects_changed_stage_evidence(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "kotekomi.toml"
    config_path.write_text(
        f'''ledger_path = "{(tmp_path / "ledger.db").as_posix()}"
archive_path = "{(tmp_path / "archive").as_posix()}"
runtime_profile = "fixture"

[processing]
representation_policy_version = "deposited-source-v1"
''',
        encoding="utf-8",
    )
    run_root = tmp_path / "validation"
    runner = ROOT / "scripts" / "run_hsq7_stage_local.py"
    common = ["--phase", "validation", "--run-root", str(run_root)]
    diagnostics = ["AMO-08", "ANT-01", "ANT-14", "ANT-16"]

    _run_stage_local(
        runner,
        "prepare",
        *common,
        *(argument for item_id in diagnostics for argument in ("--item-id", item_id)),
    )
    _run_stage_local(runner, "run-mentions", *common, "--config", str(config_path))
    _run_stage_local(runner, "run-references", *common, "--config", str(config_path))
    _run_stage_local(runner, "finalize", *common)

    metadata = json.loads((run_root / "run.json").read_bytes())
    experiment = metadata["experiment"]
    assert metadata["item_ids"] == diagnostics
    report = json.loads((run_root / "report.json").read_bytes())
    assert report["item_count"] == 4
    assert [item["item_id"] for item in report["cases"]] == sorted(diagnostics)
    assert experiment["changed_hypotheses"] == [
        "h8_semantic_boundary_adjudication",
    ]
    assert experiment["parent_experiment_id"] == ("hsq7_stage_local_pretrigger_occurrence_ids_v3")
    assert experiment["prompt_sha256"]
    assert experiment["schema_sha256"]
    assert experiment["policy_sha256"]
    assert experiment["evaluator_correction_sha256"]
    mention_path = next((run_root / "mentions").glob("*.json"))
    mention_path.write_bytes(mention_path.read_bytes() + b" ")

    rerun = subprocess.run(
        [sys.executable, str(runner), "finalize", *common],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert rerun.returncode != 0
    assert "changed after finalization" in rerun.stderr


def _run_stage_local(runner: Path, command: str, *arguments: str) -> None:
    subprocess.run(
        [sys.executable, str(runner), command, *arguments],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
