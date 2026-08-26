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
    PARAGRAPH_SEGMENT_V2,
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
    plan_analysis_units,
    run_bounded_extraction,
)
from kotekomi_pipelines.cli import main
from kotekomi_pipelines.config import load_config
from kotekomi_pipelines.model_runtime import build_model_task_runtime

ROOT = Path(__file__).resolve().parents[1]
PROMPT_ID = "paragraph_hypothesis_segment_v2"
PROMPT_PATH = ROOT / "prompts" / "paragraph_hypothesis_segment_v2.md"
VERIFIER_PROMPT_ID = "paragraph_hypothesis_faithfulness_v1"
VERIFIER_PROMPT_PATH = ROOT / "prompts" / "paragraph_hypothesis_faithfulness_v1.md"
ANALYSIS_POLICY_ID = "segment_local_hypothesis_v1"
RENDERER_VERSION = "paragraph_hypothesis_segment_context_v2"


@dataclass(frozen=True)
class Php1DiagnosticCase:
    case_id: str
    relative_path: str
    source_url: str
    anchor: str
    metadata: dict[str, str] = field(default_factory=lambda: {})


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
        results: list[dict[str, Any]] = []
        with sqlite_ledger_transaction(ledger_path) as ledger:
            for case in cases:
                _progress({"event": "case_started", "case_id": case.case_id})
                result = _run_case(
                    case,
                    representations[case.relative_path],
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
                results.append(result)
                _progress(
                    {
                        "event": "case_completed",
                        "case_id": case.case_id,
                        "status": result["status"],
                    }
                )
    summary = {"status": "completed", "cases": results}
    _progress({"event": "run_completed", "status": summary["status"]})
    return summary


def _run_case(
    case: Php1DiagnosticCase,
    representation_id: str,
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
    bundle = ledger.get_document_representation_bundle(representation_id)
    if bundle is None:
        raise ValueError("PHP-1 diagnostic representation is missing.")
    selected = _paragraph_for_anchor(bundle, case.anchor)
    result: dict[str, Any] = {"case_id": case.case_id, **case.metadata}
    if selected is None:
        return {**result, "status": "selection_missing", "anchor": case.anchor}
    node_id, paragraph_text = selected
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
    if not units:
        return {**result, "status": "selection_missing", "anchor": case.anchor}
    document = ledger.get_document(bundle.representation.document_id)
    if document is None:
        raise ValueError("PHP-1 diagnostic Document is missing.")
    segment_results: list[dict[str, Any]] = []
    for unit in units:
        manifest = build_context_manifest(
            ContextManifestInput(
                unit,
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
                PARAGRAPH_SEGMENT_V2,
            ),
            ledger,
            tokenizer,
        ).manifest
        if manifest.status is not ContextManifestStatus.READY:
            segment_results.append(
                {"source_segment_label": unit.source_segment_label, "status": "context_not_ready"}
            )
            continue
        spec = ModelExecutionSpec(
            config.model_execution.profile_name or "lm-studio",
            runtime.configured_identity,
            (ExecutionSetting("max_output_tokens", config.model_execution.max_output_tokens),),
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
                representation_id,
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
        segment_results.append(
            {
                "source_segment_label": unit.source_segment_label,
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
            }
        )
    statuses = {item["status"] for item in segment_results}
    status = diagnostic_case_status(statuses)
    limit_records = tuple(
        evaluate_eight_claim_limit(
            item["raw_output"],
            str(case.metadata.get("provisional_eligibility", "")),
        )
        for item in segment_results
    )
    measurable = tuple(record for record in limit_records if record["state"] == "measured")
    return {
        **result,
        "status": status,
        "node_id": node_id,
        "paragraph_text": paragraph_text if include_raw_output else None,
        "segments": segment_results,
        "eight_claim_evaluation": {
            "state": "measured" if measurable else limit_records[0]["state"],
            "excess_claim_line_count": sum(
                int(record["excess_claim_line_count"]) for record in measurable
            ),
        },
    }


def _paragraph_for_anchor(bundle: Any, anchor: str) -> tuple[str, str] | None:
    text_views = {item.id: item.text for item in bundle.text_views}
    for node in bundle.nodes:
        if node.node_type != "paragraph":
            continue
        text = text_views[node.text_view_id][node.start_char : node.end_char]
        if _anchor_matches(text, anchor):
            return node.id, text
    return None


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
