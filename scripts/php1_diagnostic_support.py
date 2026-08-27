"""Shared isolated execution support for PHP-1 diagnostics."""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from contextlib import redirect_stdout
from dataclasses import dataclass, field
from io import StringIO
from pathlib import Path
from typing import Any

from kotekomi_adapters import LocalArchiveStore, sqlite_ledger_transaction
from kotekomi_application import (
    PARAGRAPH_HYPOTHESIS_EVIDENCE_SELECTION_V1,
    PARAGRAPH_SEGMENT_V3,
    AnalysisUnitPlanningInput,
    BoundedExtractionInput,
    ContextManifestInput,
    ContextManifestStatus,
    ContextModelProfile,
    ExecutionSetting,
    HypothesisVerifierSpec,
    ModelExecutionSpec,
    ModelTaskRequest,
    ModelTaskResponse,
    ParagraphHypothesisTaskSchemaRegistry,
    Uuid4ModelRunIdFactory,
    build_context_manifest,
    model_execution_spec_digest,
    paragraph_source_segments,
    plan_analysis_units,
    run_bounded_extraction,
    source_copy_view,
)
from kotekomi_pipelines.cli import main
from kotekomi_pipelines.config import load_config
from kotekomi_pipelines.model_runtime import build_model_task_runtime

ROOT = Path(__file__).resolve().parents[1]
PROMPT_ID = "paragraph_hypothesis_segment_v3"
PROMPT_PATH = ROOT / "prompts" / "paragraph_hypothesis_segment_v3.md"
VERIFIER_PROMPT_ID = "paragraph_hypothesis_faithfulness_v1"
VERIFIER_PROMPT_PATH = ROOT / "prompts" / "paragraph_hypothesis_faithfulness_v1.md"
ANALYSIS_POLICY_ID = "segment_local_hypothesis_v1"
RENDERER_VERSION = "paragraph_hypothesis_segment_context_v3"


@dataclass(frozen=True)
class Php1DiagnosticCase:
    case_id: str
    relative_path: str
    source_url: str
    anchor: str
    metadata: dict[str, str] = field(default_factory=lambda: {})


@dataclass(frozen=True)
class Php1Expectation:
    expectation_id: str
    case_ids: tuple[str, ...]
    fixture_path: str
    paragraph_anchor: str
    source_segment_anchor: str
    subject_text: str
    object_text: str
    relationship_shape: str

    @property
    def target_identity(self) -> tuple[str, str, str, str]:
        return (
            self.fixture_path,
            source_copy_view(self.source_segment_anchor),
            source_copy_view(self.subject_text),
            source_copy_view(self.object_text),
        )


@dataclass(frozen=True)
class _ResolvedSegment:
    fixture_path: str
    representation_id: str
    paragraph_node_id: str
    paragraph_text: str
    source_segment_label: str
    unit: Any

    @property
    def key(self) -> tuple[str, str, str]:
        return (self.fixture_path, self.paragraph_node_id, self.source_segment_label)


class DiagnosticTokenizer:
    tokenizer_id = "lm_studio_whitespace_v1"

    def count_tokens(self, rendered_input: bytes) -> int:
        return len(rendered_input.decode("utf-8").split())


def evaluate_eight_claim_limit(
    raw_output: str | None, provisional_eligibility: str
) -> dict[str, int | str]:
    """Measure the PHP-1 limit without changing production validation."""
    if provisional_eligibility != "eligible":
        return {"state": "not_applicable", "excess_claim_line_count": 0}
    if raw_output is None:
        return {"state": "not_measurable", "excess_claim_line_count": 0}
    lines = raw_output.splitlines()
    if not lines or any(not line or line != line.strip() for line in lines):
        return {"state": "not_measurable", "excess_claim_line_count": 0}
    if not all(_has_claim_shape(line) for line in lines):
        return {"state": "not_measurable", "excess_claim_line_count": 0}
    return {
        "state": "measured",
        "excess_claim_line_count": max(0, len(lines) - 8),
    }


def _has_claim_shape(line: str) -> bool:
    if not line.startswith("claim: "):
        return False
    parts = line.removeprefix("claim: ").split(" | ")
    return len(parts) == 4 and all(part and part == part.strip() for part in parts)


def diagnostic_segment_status(
    model_run_status: str,
    proposed_change_count: int,
    outcome_metadata: dict[str, Any],
) -> str:
    """Expose verifier rejection separately from successful candidate publication."""
    if model_run_status != "succeeded":
        return model_run_status
    if (
        proposed_change_count == 0
        and int(outcome_metadata.get("faithfulness_rejected_claim_count", 0)) > 0
    ):
        return "faithfulness_rejected"
    return "complete"


def diagnostic_case_status(segment_statuses: set[str]) -> str:
    """Return one visible case result from all of its sentence outcomes."""
    if "complete" in segment_statuses:
        return "complete"
    if "invalid_output" in segment_statuses:
        return "invalid_output"
    if "faithfulness_rejected" in segment_statuses:
        return "faithfulness_rejected"
    if segment_statuses == {"abstained"}:
        return "abstained"
    return "context_not_ready"


class RecordingRuntime:
    """Records a task response without changing the ModelTaskRuntime contract."""

    def __init__(self, delegate: Any) -> None:
        self._delegate = delegate
        self.responses: list[ModelTaskResponse] = []

    @property
    def configured_identity(self) -> Any:
        return self._delegate.configured_identity

    @property
    def task_deadline_seconds(self) -> float:
        return self._delegate.task_deadline_seconds

    def check_readiness(self) -> Any:
        return self._delegate.check_readiness()

    def run_model_task(self, task: ModelTaskRequest) -> ModelTaskResponse:
        response = self._delegate.run_model_task(task)
        self.responses.append(response)
        return response


def run_cases(
    config_path: Path | None,
    cases: tuple[Php1DiagnosticCase, ...],
    *,
    representation_policy_version: str,
    include_raw_output: bool,
    expectations: tuple[Php1Expectation, ...] = (),
) -> dict[str, Any]:
    _progress({"event": "run_started", "case_count": len(cases)})
    missing = [case.case_id for case in cases if not (ROOT / case.relative_path).is_file()]
    if missing:
        _progress({"event": "run_completed", "status": "fixture_missing"})
        return {
            "status": "fixture_missing",
            "cases": [{"case_id": case_id, "status": "fixture_missing"} for case_id in missing],
        }
    with tempfile.TemporaryDirectory(prefix="kotekomi-php1-") as temporary:
        root = Path(temporary)
        ledger_path = root / "ledger.sqlite"
        archive_path = root / "archive"
        ingest_config = root / "ingest.toml"
        ingest_config.write_text(
            f'[processing]\nrepresentation_policy_version = "{representation_policy_version}"\n',
            encoding="utf-8",
        )
        _ledger_init(ledger_path, archive_path)
        representations: dict[str, str] = {}
        sources = {(case.relative_path, case.source_url) for case in cases}
        for relative_path, source_url in sorted(sources):
            _progress({"event": "source_ingest_started", "path": relative_path})
            output = _source_add(
                ingest_config, ledger_path, archive_path, ROOT / relative_path, source_url
            )
            representations[relative_path] = str(output["representation_id"])
            _progress({"event": "source_ingest_completed", "path": relative_path})
        config = load_config(
            config_path=config_path,
            ledger_path_override=ledger_path,
            archive_path_override=archive_path,
        )
        runtime = RecordingRuntime(build_model_task_runtime(config.model_execution))
        if not runtime.check_readiness().ready:
            _progress({"event": "run_completed", "status": "runtime_unavailable"})
            return {"status": "runtime_unavailable", "cases": []}
        archive = LocalArchiveStore(archive_path)
        schema = ParagraphHypothesisTaskSchemaRegistry().resolve("paragraph_hypothesis_text_v1")
        prompt = PROMPT_PATH.read_bytes()
        verifier_prompt = VERIFIER_PROMPT_PATH.read_bytes()
        tokenizer = DiagnosticTokenizer()
        with sqlite_ledger_transaction(ledger_path) as ledger:
            bundles = {
                path: _required_bundle(ledger, representation_id)
                for path, representation_id in representations.items()
            }
            units_by_node: dict[tuple[str, str], tuple[Any, ...]] = {}
            case_plans: dict[str, tuple[_ResolvedSegment, ...]] = {}
            case_selection_results: dict[str, dict[str, Any]] = {}
            planned_segments: dict[tuple[str, str, str], _ResolvedSegment] = {}
            for case in cases:
                selection = _resolve_case_segments(
                    case,
                    representations[case.relative_path],
                    bundles[case.relative_path],
                    ledger,
                    units_by_node,
                )
                if isinstance(selection, dict):
                    case_selection_results[case.case_id] = selection
                    continue
                case_plans[case.case_id] = selection
                planned_segments.update({plan.key: plan for plan in selection})

            expectation_resolutions = {
                expectation.expectation_id: _resolve_expectation(
                    expectation,
                    representations[expectation.fixture_path],
                    bundles[expectation.fixture_path],
                    ledger,
                    units_by_node,
                )
                for expectation in expectations
            }
            for resolution in expectation_resolutions.values():
                plan = resolution.get("plan")
                if isinstance(plan, _ResolvedSegment):
                    planned_segments[plan.key] = plan

            segment_results: dict[tuple[str, str, str], dict[str, Any]] = {}
            for key, plan in sorted(planned_segments.items()):
                _progress(
                    {
                        "event": "source_segment_started",
                        "fixture_path": plan.fixture_path,
                        "paragraph_node_id": plan.paragraph_node_id,
                        "source_segment_label": plan.source_segment_label,
                    }
                )
                segment_results[key] = _run_segment(
                    plan,
                    ledger,
                    archive,
                    config,
                    runtime,
                    schema,
                    prompt,
                    verifier_prompt,
                    tokenizer,
                    include_raw_output,
                )

            results: list[dict[str, Any]] = []
            for case in cases:
                _progress({"event": "case_started", "case_id": case.case_id})
                selection_result = case_selection_results.get(case.case_id)
                if selection_result is not None:
                    result = {"case_id": case.case_id, **case.metadata, **selection_result}
                else:
                    result = _case_result_from_segments(
                        case,
                        case_plans[case.case_id],
                        segment_results,
                        include_raw_output,
                    )
                results.append(result)
                _progress(
                    {
                        "event": "case_completed",
                        "case_id": case.case_id,
                        "status": result["status"],
                    }
                )
            target_report = (
                _target_report(expectations, expectation_resolutions, segment_results)
                if expectations
                else None
            )
    summary: dict[str, Any] = {"status": "completed", "cases": results}
    if target_report is not None:
        summary["target_report"] = target_report
    _progress({"event": "run_completed", "status": summary["status"]})
    return summary


def _required_bundle(ledger: Any, representation_id: str) -> Any:
    bundle = ledger.get_document_representation_bundle(representation_id)
    if bundle is None:
        raise ValueError("PHP-1 diagnostic representation is missing.")
    return bundle


def _units_for_node(
    representation_id: str,
    node_id: str,
    ledger: Any,
    cache: dict[tuple[str, str], tuple[Any, ...]],
) -> tuple[Any, ...]:
    key = (representation_id, node_id)
    cached = cache.get(key)
    if cached is not None:
        return cached
    units = tuple(
        item
        for item in plan_analysis_units(
            AnalysisUnitPlanningInput(
                representation_id,
                ANALYSIS_POLICY_ID,
                "claim_extraction",
                focus_node_types=("paragraph",),
            ),
            ledger,
        ).units
        if item.focus_node_ids == (node_id,)
    )
    cache[key] = units
    return units


def _resolve_case_segments(
    case: Php1DiagnosticCase,
    representation_id: str,
    bundle: Any,
    ledger: Any,
    units_by_node: dict[tuple[str, str], tuple[Any, ...]],
) -> tuple[_ResolvedSegment, ...] | dict[str, Any]:
    selected = _first_paragraph_for_anchor(bundle, case.anchor)
    if selected is None:
        return {"status": "selection_missing", "anchor": case.anchor}
    node_id, paragraph_text = selected
    units = _units_for_node(representation_id, node_id, ledger, units_by_node)
    if not units:
        return {"status": "selection_missing", "anchor": case.anchor}
    return tuple(
        _ResolvedSegment(
            case.relative_path,
            representation_id,
            node_id,
            paragraph_text,
            str(unit.source_segment_label),
            unit,
        )
        for unit in units
    )


def _resolve_expectation(
    expectation: Php1Expectation,
    representation_id: str,
    bundle: Any,
    ledger: Any,
    units_by_node: dict[tuple[str, str], tuple[Any, ...]],
) -> dict[str, Any]:
    paragraphs = _paragraphs_for_anchor(bundle, expectation.paragraph_anchor)
    if len(paragraphs) != 1:
        return {
            "resolution_status": "unresolved",
            "diagnostics": ["paragraph_anchor_not_unique"],
        }
    node_id, paragraph_text = paragraphs[0]
    segments = tuple(
        segment
        for segment in paragraph_source_segments(paragraph_text, PARAGRAPH_SEGMENT_V3)
        if _anchor_matches(segment.exact_text, expectation.source_segment_anchor)
    )
    if len(segments) != 1:
        return {
            "resolution_status": "unresolved",
            "diagnostics": ["source_segment_anchor_not_unique"],
        }
    units = _units_for_node(representation_id, node_id, ledger, units_by_node)
    source_segment = segments[0]
    matching_units = tuple(
        unit for unit in units if unit.source_segment_label == source_segment.label
    )
    if len(matching_units) != 1:
        return {
            "resolution_status": "unresolved",
            "diagnostics": ["source_segment_unit_not_unique"],
        }
    return {
        "resolution_status": "resolved",
        "diagnostics": [],
        "plan": _ResolvedSegment(
            expectation.fixture_path,
            representation_id,
            node_id,
            paragraph_text,
            source_segment.label,
            matching_units[0],
        ),
    }


def _run_segment(
    plan: _ResolvedSegment,
    ledger: Any,
    archive: LocalArchiveStore,
    config: Any,
    runtime: RecordingRuntime,
    schema: Any,
    prompt: bytes,
    verifier_prompt: bytes,
    tokenizer: DiagnosticTokenizer,
    include_raw_output: bool,
) -> dict[str, Any]:
    bundle = _required_bundle(ledger, plan.representation_id)
    document = ledger.get_document(bundle.representation.document_id)
    if document is None:
        raise ValueError("PHP-1 diagnostic Document is missing.")
    manifest = build_context_manifest(
        ContextManifestInput(
            plan.unit,
            ContextModelProfile(
                config.model_execution.profile_name or "lm-studio",
                config.model_execution.context_tokens,
                config.model_execution.max_output_tokens,
                256,
            ),
            PROMPT_ID,
            prompt,
            schema.schema_id,
            schema.canonical_schema_bytes,
            RENDERER_VERSION,
            PARAGRAPH_HYPOTHESIS_EVIDENCE_SELECTION_V1,
            PARAGRAPH_SEGMENT_V3,
        ),
        ledger,
        tokenizer,
    ).manifest
    if manifest.status is not ContextManifestStatus.READY:
        return {
            "source_segment_label": plan.source_segment_label,
            "status": "context_not_ready",
            "model_run_id": None,
            "proposed_change_ids": [],
            "verified_hypotheses": [],
            "prompt_digest": hashlib.sha256(prompt).hexdigest(),
            "schema_digest": schema.digest,
            "execution_spec_digest": None,
        }
    spec = ModelExecutionSpec(
        config.model_execution.profile_name or "lm-studio",
        runtime.configured_identity,
        (
            ExecutionSetting("max_output_tokens", config.model_execution.max_output_tokens),
            ExecutionSetting("seed", 17),
            ExecutionSetting("temperature", 0),
        ),
        PROMPT_ID,
        hashlib.sha256(prompt).hexdigest(),
        schema.schema_id,
        schema.digest,
        manifest.id,
        manifest.manifest_digest,
        manifest.rendered_input_digest,
        schema.output_contract_version,
    )
    response_count = len(runtime.responses)
    outcome = run_bounded_extraction(
        BoundedExtractionInput(
            document.source_id,
            document.id,
            plan.representation_id,
            manifest.id,
            prompt,
            spec,
            "paragraph_hypothesis_validator_v1",
            HypothesisVerifierSpec(VERIFIER_PROMPT_ID, verifier_prompt),
        ),
        ledger,
        archive,
        runtime,
        Uuid4ModelRunIdFactory(),
        tokenizer,
        ParagraphHypothesisTaskSchemaRegistry(),
    )
    responses = runtime.responses[response_count:]
    raw_output = (
        responses[0].raw_output.decode("utf-8", errors="replace")
        if include_raw_output and responses
        else None
    )
    verifier_raw_outputs = (
        [response.raw_output.decode("utf-8", errors="replace") for response in responses[1:]]
        if include_raw_output
        else []
    )
    proposed_change_ids = (
        list(outcome.proposed_change_batch.proposed_change_ids_by_local_id.values())
        if outcome.proposed_change_batch
        else []
    )
    outcome_metadata = outcome.model_run.outcome_metadata
    return {
        "source_segment_label": plan.source_segment_label,
        "status": diagnostic_segment_status(
            outcome.model_run.status.value,
            len(proposed_change_ids),
            outcome_metadata,
        ),
        "model_run_id": outcome.model_run.id,
        "raw_output": raw_output,
        "verifier_raw_outputs": verifier_raw_outputs,
        "error_code": outcome.model_run.error_code,
        "error_message": outcome.model_run.error_message,
        "abstention_reason": outcome.model_run.abstention_reason,
        "execution_diagnostics": outcome.model_run.execution_diagnostics,
        "proposed_change_ids": proposed_change_ids,
        "faithfulness_accepted_claim_count": outcome_metadata.get(
            "faithfulness_accepted_claim_count", 0
        ),
        "faithfulness_rejected_claim_count": outcome_metadata.get(
            "faithfulness_rejected_claim_count", 0
        ),
        "verified_hypotheses": [
            {
                "subject_text": item.hypothesis.subject,
                "relation_text": item.hypothesis.relation,
                "object_text": item.hypothesis.object_value,
                "proposed_change_id": item.proposed_change_id,
            }
            for item in outcome.verified_hypotheses
        ],
        "prompt_digest": spec.prompt_digest,
        "schema_digest": spec.schema_digest,
        "execution_spec_digest": model_execution_spec_digest(spec),
    }


def _case_result_from_segments(
    case: Php1DiagnosticCase,
    plans: tuple[_ResolvedSegment, ...],
    segment_results: dict[tuple[str, str, str], dict[str, Any]],
    include_raw_output: bool,
) -> dict[str, Any]:
    segments = [segment_results[plan.key] for plan in plans]
    statuses = {item["status"] for item in segments}
    status = diagnostic_case_status(statuses)
    limit_records = tuple(
        evaluate_eight_claim_limit(
            item["raw_output"],
            str(case.metadata.get("provisional_eligibility", "")),
        )
        for item in segments
    )
    measurable = tuple(record for record in limit_records if record["state"] == "measured")
    return {
        "case_id": case.case_id,
        **case.metadata,
        "status": status,
        "node_id": plans[0].paragraph_node_id,
        "paragraph_text": plans[0].paragraph_text if include_raw_output else None,
        "segments": segments,
        "eight_claim_evaluation": {
            "state": "measured" if measurable else limit_records[0]["state"],
            "excess_claim_line_count": sum(
                int(record["excess_claim_line_count"]) for record in measurable
            ),
        },
    }


def _target_report(
    expectations: tuple[Php1Expectation, ...],
    resolutions: dict[str, dict[str, Any]],
    segment_results: dict[tuple[str, str, str], dict[str, Any]],
) -> dict[str, Any]:
    target_results: list[dict[str, Any]] = []
    matched_hypotheses: set[tuple[tuple[str, str, str], str, str]] = set()
    for expectation in expectations:
        resolution = resolutions[expectation.expectation_id]
        diagnostics = list(resolution["diagnostics"])
        base = {
            "expectation_id": expectation.expectation_id,
            "case_ids": list(expectation.case_ids),
            "fixture_path": expectation.fixture_path,
            "relationship_shape": expectation.relationship_shape,
            "resolution_status": resolution["resolution_status"],
            "matched_model_run_ids": [],
            "matched_proposed_change_ids": [],
            "prompt_digest": None,
            "schema_digest": None,
            "execution_spec_digest": None,
        }
        plan = resolution.get("plan")
        if not isinstance(plan, _ResolvedSegment):
            target_results.append({**base, "target_status": None, "diagnostics": diagnostics})
            continue
        segment = segment_results[plan.key]
        base.update(
            {
                "paragraph_node_id": plan.paragraph_node_id,
                "source_segment_label": plan.source_segment_label,
                "prompt_digest": segment["prompt_digest"],
                "schema_digest": segment["schema_digest"],
                "execution_spec_digest": segment["execution_spec_digest"],
            }
        )
        matches = tuple(
            hypothesis
            for hypothesis in segment["verified_hypotheses"]
            if _hypothesis_matches_expectation(hypothesis, expectation)
        )
        if matches:
            for hypothesis in matches:
                matched_hypotheses.add(
                    (
                        plan.key,
                        str(hypothesis["subject_text"]),
                        str(hypothesis["object_text"]),
                    )
                )
            target_results.append(
                {
                    **base,
                    "target_status": "matched",
                    "matched_model_run_ids": [segment["model_run_id"]],
                    "matched_proposed_change_ids": sorted(
                        str(hypothesis["proposed_change_id"]) for hypothesis in matches
                    ),
                    "diagnostics": diagnostics,
                }
            )
            continue
        target_status = (
            "missing"
            if segment["status"] in {"complete", "abstained", "faithfulness_rejected"}
            else "blocked"
        )
        diagnostics.append(f"source_segment_status:{segment['status']}")
        target_results.append({**base, "target_status": target_status, "diagnostics": diagnostics})

    unexpected: list[dict[str, Any]] = []
    unexpected_keys: set[tuple[tuple[str, str, str], str, str, str]] = set()
    for key, segment in sorted(segment_results.items()):
        fixture_path, paragraph_node_id, source_segment_label = key
        for hypothesis in segment["verified_hypotheses"]:
            hypothesis_key = (
                key,
                str(hypothesis["subject_text"]),
                str(hypothesis["object_text"]),
            )
            if hypothesis_key in matched_hypotheses:
                continue
            unexpected_key = (
                key,
                str(hypothesis["subject_text"]),
                str(hypothesis["relation_text"]),
                str(hypothesis["object_text"]),
            )
            if unexpected_key in unexpected_keys:
                continue
            unexpected_keys.add(unexpected_key)
            unexpected.append(
                {
                    "source_fixture_path": fixture_path,
                    "paragraph_node_id": paragraph_node_id,
                    "source_segment_label": source_segment_label,
                    "subject_text": hypothesis["subject_text"],
                    "relation_text": hypothesis["relation_text"],
                    "object_text": hypothesis["object_text"],
                    "model_run_id": segment["model_run_id"],
                    "proposed_change_ids": [hypothesis["proposed_change_id"]],
                }
            )
    return {
        "target_results": target_results,
        "unexpected_hypotheses": unexpected,
    }


def _hypothesis_matches_expectation(
    hypothesis: dict[str, Any], expectation: Php1Expectation
) -> bool:
    return source_copy_view(str(hypothesis["subject_text"])) == source_copy_view(
        expectation.subject_text
    ) and source_copy_view(str(hypothesis["object_text"])) == source_copy_view(
        expectation.object_text
    )


def _paragraphs_for_anchor(bundle: Any, anchor: str) -> tuple[tuple[str, str], ...]:
    text_views = {item.id: item.text for item in bundle.text_views}
    return tuple(
        (node.id, text_views[node.text_view_id][node.start_char : node.end_char])
        for node in bundle.nodes
        if node.node_type == "paragraph"
        and _anchor_matches(text_views[node.text_view_id][node.start_char : node.end_char], anchor)
    )


def _first_paragraph_for_anchor(bundle: Any, anchor: str) -> tuple[str, str] | None:
    paragraphs = _paragraphs_for_anchor(bundle, anchor)
    return paragraphs[0] if paragraphs else None


def _anchor_matches(text: str, anchor: str) -> bool:
    normalized_text = " ".join(text.split())
    cursor = 0
    for part in anchor.split("..."):
        normalized_part = " ".join(part.split())
        position = normalized_text.find(normalized_part, cursor)
        if position < 0:
            return False
        cursor = position + len(normalized_part)
    return True


def _progress(event: dict[str, Any]) -> None:
    print(json.dumps(event, sort_keys=True), file=sys.stderr, flush=True)


def _ledger_init(ledger_path: Path, archive_path: Path) -> None:
    with redirect_stdout(StringIO()):
        exit_code = main(
            [
                "ledger",
                "init",
                "--ledger-path",
                str(ledger_path),
                "--archive-path",
                str(archive_path),
            ]
        )
    if exit_code != 0:
        raise ValueError("PHP-1 diagnostic Ledger initialization failed.")


def _source_add(config: Path, ledger: Path, archive: Path, path: Path, url: str) -> dict[str, Any]:
    stream = StringIO()
    with redirect_stdout(stream):
        exit_code = main(
            [
                "--config",
                str(config),
                "source",
                "add-file",
                str(path),
                "--source-url",
                url,
                "--ledger-path",
                str(ledger),
                "--archive-path",
                str(archive),
                "--format",
                "json",
            ]
        )
    if exit_code != 0:
        raise ValueError(f"PHP-1 diagnostic could not ingest {path.name}.")
    return json.loads(stream.getvalue())
