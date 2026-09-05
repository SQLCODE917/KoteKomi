from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[3]


def _module(name: str) -> Any:
    scripts_path = str(ROOT / "scripts")
    if scripts_path not in sys.path:
        sys.path.insert(0, scripts_path)
    path = ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"{name}_org_r2_test", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_catalog_rebuilds_all_preserved_candidates_and_excludes_boundary_cases() -> None:
    org_r1 = _module("organization_boundary_reconciliation_evaluation")
    org_r2 = _module("organization_semantic_qualification_evaluation")
    report, catalog = _proposal_report()
    boundary = org_r1.evaluate_boundary_reconciliation(
        report,
        catalog,
        phase="development",
        proposal_report_sha256="a" * 64,
        catalog_sha256="b" * 64,
    )

    result = org_r2.build_qualification_catalog(
        boundary,
        phase="development",
        boundary_evaluation_sha256="c" * 64,
    )

    assert result["source_count"] == 1
    assert result["candidate_count"] == 2
    candidates = result["candidates"]
    ordered = sorted(candidates, key=lambda item: item["candidate"]["end"])
    assert [
        (item["candidate"]["text"], item["gold_classification"]["eligibility"]) for item in ordered
    ] == [
        ("Anthropic", "exact_gold"),
        ("Anthropic's", "boundary_case"),
    ]
    assert all(
        item["candidate"]["boundary_rule_id"] == "terminal_possessive_suffix_v1"
        for item in candidates
    )


def test_catalog_rejects_candidate_drift_between_repetitions() -> None:
    org_r1 = _module("organization_boundary_reconciliation_evaluation")
    org_r2 = _module("organization_semantic_qualification_evaluation")
    report, catalog = _proposal_report()
    boundary = org_r1.evaluate_boundary_reconciliation(
        report,
        catalog,
        phase="development",
        proposal_report_sha256="a" * 64,
        catalog_sha256="b" * 64,
    )
    boundary["runs"][1]["segments"][0]["fused_candidates"][0]["text"] = "Anthropi"

    with pytest.raises(ValueError, match="Source characters|drifted"):
        org_r2.build_qualification_catalog(
            boundary,
            phase="development",
            boundary_evaluation_sha256="c" * 64,
        )


def test_scoring_keeps_invalid_execution_and_ambiguity_distinct() -> None:
    org_r1 = _module("organization_boundary_reconciliation_evaluation")
    org_r2 = _module("organization_semantic_qualification_evaluation")
    report, gold = _proposal_report()
    boundary = org_r1.evaluate_boundary_reconciliation(
        report,
        gold,
        phase="development",
        proposal_report_sha256="a" * 64,
        catalog_sha256="b" * 64,
    )
    catalog = org_r2.build_qualification_catalog(
        boundary,
        phase="development",
        boundary_evaluation_sha256="c" * 64,
    )
    exact = next(
        item
        for item in catalog["candidates"]
        if item["gold_classification"]["eligibility"] == "exact_gold"
    )
    executions = (
        _execution(exact["candidate"]["id"], "qwen", 1, "completed", "organization"),
        _execution(exact["candidate"]["id"], "qwen", 2, "completed", "ambiguous"),
        _execution(exact["candidate"]["id"], "qwen", 3, "invalid_output", None),
    )

    result = org_r2.score_qualification_executions(catalog, executions)

    assert result["counts"]["correct_count"] == 1
    assert result["counts"]["wrong_count"] == 1
    assert result["counts"]["execution_status:invalid_output"] == 1
    assert result["coverage"] == 0.5
    assert result["exact_accuracy"] == 0.5
    assert result["decisive_accuracy"] == 1.0
    assert result["organization_precision"] == 1.0
    assert result["organization_recall"] == 1.0
    assert result["organization_f1"] == 1.0
    assert result["runtime_availability"] == 1.0
    assert result["valid_output_rate"] == 0.666667
    assert result["exact_label_stability"] == 0.0
    assert len(result["review_records"]) == 2
    assert result["review_records"][0]["source"]["source_text"] == "Anthropic's policy changed."


def test_execution_resume_conflict_and_held_out_seal(tmp_path: Path) -> None:
    module = _module("organization_semantic_qualification_evaluation")
    execution = _execution("qfc_1", "qwen", 1, "completed", "organization")
    path = tmp_path / "executions-qwen.jsonl"

    assert module.append_execution_record(path, execution)
    assert not module.append_execution_record(path, execution)
    conflicting = {**execution, "judgment": "not_organization"}
    with pytest.raises(ValueError, match="conflicts"):
        module.append_execution_record(path, conflicting)

    for name in ("inputs.jsonl", "metrics.json"):
        (tmp_path / name).write_text("{}\n", encoding="utf-8")
    manifest = module.seal_bundle(
        tmp_path,
        phase="held_out",
        expected_files=("inputs.jsonl", "metrics.json"),
    )
    assert manifest["status"] == "complete"
    with pytest.raises(FileExistsError, match="sealed"):
        module.seal_bundle(
            tmp_path,
            phase="held_out",
            expected_files=("inputs.jsonl", "metrics.json"),
        )


def test_qwen_runner_retains_exact_input_output_and_model_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from kotekomi_application import (
        ModelExecutionReceipt,
        ModelIdentitySnapshot,
        ModelInputInspectionRequest,
        ModelInputMeasurement,
        ModelRuntimeStatus,
        ModelTaskRequest,
        ModelTaskResponse,
        generation_parameters_digest,
        model_identity_snapshot_digest,
    )
    from kotekomi_pipelines.config import ModelExecutionConfig

    org_r1 = _module("organization_boundary_reconciliation_evaluation")
    evaluator = _module("organization_semantic_qualification_evaluation")
    runner = _module("run_organization_semantic_qualification")
    report, gold = _proposal_report()
    boundary = org_r1.evaluate_boundary_reconciliation(
        report,
        gold,
        phase="development",
        proposal_report_sha256="a" * 64,
        catalog_sha256="b" * 64,
    )
    catalog = evaluator.build_qualification_catalog(
        boundary,
        phase="development",
        boundary_evaluation_sha256="c" * 64,
    )
    records = tuple(
        sorted(
            (
                *({"record_type": "source", **item} for item in catalog["sources"]),
                *({"record_type": "candidate", **item} for item in catalog["candidates"]),
            ),
            key=lambda item: item["id"],
        )
    )
    evaluator.write_canonical_jsonl(tmp_path / "inputs.jsonl", records)
    (tmp_path / "run.json").write_text(
        evaluator.canonical_json({"phase": "development"}) + "\n",
        encoding="utf-8",
    )

    class FakeRuntime:
        def __init__(self) -> None:
            self.requests: list[ModelTaskRequest] = []
            self.configured_identity = ModelIdentitySnapshot(
                name="qwen2.5-14b-instruct",
                weights_digest=None,
                runtime="lm_studio",
                tokenizer_id="fixture_whitespace_tokenizer_v1",
            )
            self.task_deadline_seconds = 300.0

        @property
        def tokenizer_id(self) -> str:
            return self.configured_identity.tokenizer_id

        def count_tokens(self, rendered_input: bytes) -> int:
            return len(rendered_input.decode("utf-8").split())

        def inspect_model_input(
            self, request: ModelInputInspectionRequest
        ) -> ModelInputMeasurement:
            return ModelInputMeasurement(
                model_identity_digest=model_identity_snapshot_digest(request.model_identity),
                runtime_identity=self.configured_identity.runtime,
                model_instance_id=self.configured_identity.name,
                tokenizer_id=self.tokenizer_id,
                prompt_template_identity="fixture_no_prompt_template_v1",
                logical_input_digest=request.logical_input_digest,
                formatted_input_digest=request.logical_input_digest,
                formatted_input_token_count=self.count_tokens(request.logical_input),
                loaded_context_limit=65_536,
            )

        def check_readiness(self) -> ModelRuntimeStatus:
            return ModelRuntimeStatus(
                adapter="lm_studio",
                endpoint="http://127.0.0.1:1234/v1",
                model="qwen2.5-14b-instruct",
                reachable=True,
                model_available=True,
                model_state="available",
                idle_slots=None,
                total_slots=None,
                ready=True,
            )

        def run_model_task(self, task: ModelTaskRequest) -> ModelTaskResponse:
            self.requests.append(task)
            return ModelTaskResponse(
                raw_output=b"organization",
                execution_receipt=ModelExecutionReceipt(
                    model_identity_digest=model_identity_snapshot_digest(
                        task.execution_spec.model_identity
                    ),
                    generation_parameters_digest=generation_parameters_digest(
                        task.execution_spec.generation_parameters
                    ),
                    rendered_input_digest=hashlib.sha256(task.rendered_input).hexdigest(),
                    input_token_count=task.input_admission.formatted_input_token_count,
                    output_token_count=1,
                ),
                first_response_event_milliseconds=None,
            )

    runtime = FakeRuntime()
    built_configs: list[ModelExecutionConfig] = []

    def build_runtime(config: ModelExecutionConfig) -> FakeRuntime:
        built_configs.append(config)
        return runtime

    def fake_load_config(**_values: object) -> SimpleNamespace:
        return SimpleNamespace(
            model_execution=ModelExecutionConfig(
                adapter="lm_studio",
                endpoint="http://127.0.0.1:1234/v1",
                model="qwen2.5-14b-instruct",
                timeout_seconds=300,
                context_tokens=16384,
                max_output_tokens=2048,
                profile_name="lm-studio",
            )
        )

    monkeypatch.setattr(runner, "load_config", fake_load_config)
    monkeypatch.setattr(runner, "build_model_task_runtime", build_runtime)

    result = runner.run_qwen(output_dir=tmp_path, config_path=None)

    executions = [
        json.loads(line) for line in (tmp_path / "executions-qwen.jsonl").read_text().splitlines()
    ]
    assert result == {"status": "completed", "written": 6, "retained": 6}
    assert built_configs[0].max_output_tokens == 16
    assert len(runtime.requests) == 6
    assert all(item["execution_status"] == "completed" for item in executions)
    assert all(item["judgment"] == "organization" for item in executions)
    assert all(item["output"]["raw_output"] == "organization" for item in executions)
    assert all(item["output"]["model_run"]["status"] == "succeeded" for item in executions)
    first_input = executions[0]["input"]
    assert first_input["source_text"] == "Anthropic's policy changed."
    assert first_input["candidate"]["text"] in first_input["rendered_input"]
    assert first_input["source_text"] in first_input["rendered_input"]


def test_runner_refuses_completed_held_out_before_rewriting_files(tmp_path: Path) -> None:
    runner = _module("run_organization_semantic_qualification")
    (tmp_path / "run.json").write_text('{"phase":"held_out"}\n', encoding="utf-8")
    (tmp_path / "inputs.jsonl").write_text("", encoding="utf-8")
    (tmp_path / "manifest.json").write_text("sealed\n", encoding="utf-8")

    with pytest.raises(FileExistsError, match="sealed"):
        runner.finalize(tmp_path)

    assert (tmp_path / "manifest.json").read_text(encoding="utf-8") == "sealed\n"


def test_refined_runner_records_typed_blocked_worker_result(tmp_path: Path) -> None:
    runner = _module("run_organization_semantic_qualification")
    (tmp_path / "run.json").write_text('{"phase":"development"}\n', encoding="utf-8")
    (tmp_path / "inputs.jsonl").write_text("", encoding="utf-8")

    result = runner.run_refined(
        output_dir=tmp_path,
        python_executable=Path("/missing/refined/python"),
        data_dir=Path("/missing/refined/resources"),
    )

    assert result["status"] == "blocked"
    assert result["failure"] == "worker_unavailable"
    assert json.loads((tmp_path / "refined-blocked.json").read_text()) == result


def test_result_record_binds_both_sealed_manifests_idempotently(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner = _module("run_organization_semantic_qualification")
    docs = tmp_path / "docs"
    development = docs / "evaluations/org-r2/development"
    held_out = docs / "evaluations/org-r2/held-out"
    docs.mkdir(parents=True)
    (docs / "2026-08-31-organization-semantic-qualification-comparison.md").write_text(
        "accepted tdd\n",
        encoding="utf-8",
    )
    metrics: dict[str, Any] = {
        "candidate_count": 1,
        "producers": {"qwen": {}, "refined": {}},
    }
    org_r1_phases: dict[str, dict[str, str]] = {}
    for phase, directory in (("development", development), ("held_out", held_out)):
        directory.mkdir(parents=True)
        run = {
            "proposal_report_sha256": "a" * 64,
            "gold_catalog_sha256": "b" * 64,
            "boundary_evaluation_sha256": "c" * 64,
        }
        (directory / "run.json").write_text(json.dumps(run) + "\n", encoding="utf-8")
        org_r1_phases[phase] = {
            "proposal_report_sha256": "a" * 64,
            "catalog_sha256": "b" * 64,
            "reconciliation_report_sha256": "c" * 64,
        }
        metrics_path = directory / "metrics.json"
        metrics_path.write_text(json.dumps({"phase": phase, **metrics}) + "\n", encoding="utf-8")
        manifest = {
            "schema_version": "organization_qualification_bundle_manifest_v1",
            "phase": phase,
            "status": "complete",
            "files": [
                {
                    "path": "metrics.json",
                    "sha256": hashlib.sha256(metrics_path.read_bytes()).hexdigest(),
                    "record_count": 1,
                }
            ],
        }
        (directory / "manifest.json").write_text(json.dumps(manifest) + "\n", encoding="utf-8")
    org_r1_result = docs / "organization-boundary-reconciliation-result-v1.json"
    org_r1_result.write_text(
        json.dumps(
            {
                "policy_id": "organization_boundary_reconciliation_v1",
                "policy_freeze_commit": "d" * 40,
                **org_r1_phases,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(runner, "ROOT", tmp_path)

    def skip_lineage(_directory: Path, _phase: str) -> None:
        return None

    monkeypatch.setattr(runner, "_validate_bundle_lineage", skip_lineage)
    output = docs / "organization-semantic-qualification-result-v1.json"

    first = runner.write_result_record(
        development_dir=development,
        held_out_dir=held_out,
        org_r1_result_path=org_r1_result,
        output_path=output,
    )
    second = runner.write_result_record(
        development_dir=development,
        held_out_dir=held_out,
        org_r1_result_path=org_r1_result,
        output_path=output,
    )

    assert first == second
    assert (
        first["development"]["manifest_sha256"]
        == hashlib.sha256((development / "manifest.json").read_bytes()).hexdigest()
    )
    assert (
        first["held_out"]["manifest_sha256"]
        == hashlib.sha256((held_out / "manifest.json").read_bytes()).hexdigest()
    )

    (held_out / "metrics.json").write_text("tampered\n", encoding="utf-8")
    with pytest.raises(ValueError, match="digest mismatch"):
        runner.write_result_record(
            development_dir=development,
            held_out_dir=held_out,
            org_r1_result_path=org_r1_result,
            output_path=output,
        )


@pytest.mark.parametrize("phase", ("development", "held-out"))
def test_tracked_org_r2_bundle_retains_complete_lineage(phase: str) -> None:
    runner = _module("run_organization_semantic_qualification")

    runner._validate_bundle_lineage(ROOT / "docs/evaluations/org-r2" / phase, phase)


@pytest.mark.parametrize(
    ("status", "judgment", "eligibility", "expected", "evaluation"),
    [
        ("completed", "organization", "exact_gold", "organization", "correct"),
        (
            "completed",
            "ambiguous",
            "exact_gold",
            "organization",
            "incorrect abstention; Gold expects organization",
        ),
        (
            "completed",
            "organization",
            "disjoint_gold",
            "not_organization",
            "incorrect; Gold expects not_organization",
        ),
        (
            "invalid_output",
            None,
            "exact_gold",
            "organization",
            "not a semantic result: invalid_output",
        ),
        (
            "completed",
            "organization",
            "boundary_case",
            None,
            "not scored: non-exact Gold overlap is an ORG-R1 boundary case",
        ),
    ],
)
def test_compact_comparison_uses_gold_relative_evaluations(
    status: str,
    judgment: str | None,
    eligibility: str,
    expected: str | None,
    evaluation: str,
) -> None:
    runner = _module("run_organization_semantic_qualification")

    assert (
        runner._qualification_result_evaluation(
            {"execution_status": status, "judgment": judgment},
            {"eligibility": eligibility, "expected_judgment": expected},
        )
        == evaluation
    )


def _execution(
    candidate_id: str,
    producer_id: str,
    repetition: int,
    status: str,
    judgment: str | None,
) -> dict[str, Any]:
    return {
        "schema_version": "organization_qualification_execution_v1",
        "id": f"oqe_{producer_id}_{repetition}",
        "candidate_id": candidate_id,
        "producer_id": producer_id,
        "repetition": repetition,
        "execution_status": status,
        "judgment": judgment,
    }


def _proposal_report() -> tuple[dict[str, Any], dict[str, Any]]:
    source = "Anthropic's policy changed."
    digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
    prompt_digest = hashlib.sha256(
        (ROOT / "prompts/paragraph_organization_mention_v1.md").read_bytes()
    ).hexdigest()
    key = {
        "fixture_path": "raw/test.pdf",
        "paragraph_node_id": "nod_test",
        "source_segment_label": "s1",
        "source_text": source,
        "source_text_sha256": digest,
    }
    qwen = {
        **key,
        "status": "complete",
        "model_run_id": "mrn_test",
        "prompt_digest": prompt_digest,
        "raw_output": "mention: s1 | Anthropic",
        "proposals": [{"text": "Anthropic", "start": 0, "end": 9, "score": None}],
    }
    gliner = {
        **key,
        "status": "complete",
        "proposals": [{"text": "Anthropic's", "start": 0, "end": 11, "score": 0.9}],
    }
    report = {
        "status": "completed",
        "schema_version": "php1_span_proposer_comparison_v1",
        "repetitions": 3,
        "proposers": [
            {
                "proposer_id": "qwen2.5-h2-mention-v1",
                "identity": {"name": "qwen2.5-14b-instruct"},
                "runs": [
                    {"repetition": repetition, "segments": [qwen]} for repetition in range(1, 4)
                ],
            },
            {
                "proposer_id": "gliner-medium-v2.1",
                "identity": {"model_id": "gliner", "threshold": 0.5},
                "runs": [
                    {"repetition": repetition, "segments": [gliner]} for repetition in range(1, 4)
                ],
            },
        ],
    }
    catalog = {
        "segments": [
            {
                **key,
                "source_segment_id": "src_test",
                "gold_mentions": [{"text": "Anthropic", "start": 0, "end": 9}],
            }
        ]
    }
    return report, catalog
