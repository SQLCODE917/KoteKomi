"""Collect sealed Qwen2.5 and GLiNER proposal evidence for ORG-R1 held-out Gold."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any, cast

from kotekomi_adapters.gliner_organization_mention_proposer import (
    GLINER_DEVICE,
    GLINER_LABEL,
    GLINER_MODEL_ID,
    GLINER_MODEL_REVISION,
    GLINER_PACKAGE_VERSION,
    GLINER_THRESHOLD,
    GlinerOrganizationMentionProposer,
)
from kotekomi_adapters.model_resources import gliner_model_path
from kotekomi_application import (
    ExecutionSetting,
    ModelExecutionSpec,
    ModelInputAdmissionRequest,
    ModelTaskRequest,
    OrganizationMentionBatch,
    OrganizationMentionBatchAbstention,
    OrganizationMentionProposalInput,
    OrganizationMentionTaskSchemaRegistry,
    admit_model_input,
    propose_validated_organization_mentions,
)
from kotekomi_domain import ModelInputAdmissionStatus
from kotekomi_pipelines.config import load_config
from kotekomi_pipelines.model_runtime import build_model_task_runtime
from php1_diagnostic_support import (
    MODEL_ELIGIBLE,
    classify_source_segment_model_eligibility,
)
from php1_span_proposer_evaluation import REPETITIONS, proposer_report

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CATALOG = ROOT / "docs/organization-mention-held-out-gold-v1.json"
PROMPT_PATH = ROOT / "prompts/paragraph_organization_mention_v1.md"


def run(catalog_path: Path = DEFAULT_CATALOG, config_path: Path | None = None) -> dict[str, Any]:
    catalog_bytes = catalog_path.read_bytes()
    catalog_document = cast(dict[str, Any], json.loads(catalog_bytes))
    catalog = tuple(cast(list[dict[str, Any]], catalog_document["segments"]))
    prompt = PROMPT_PATH.read_bytes()
    prompt_digest = hashlib.sha256(prompt).hexdigest()
    schema = OrganizationMentionTaskSchemaRegistry().resolve("organization_mention_text_v1")
    config = load_config(
        config_path=config_path,
        ledger_path_override=None,
        archive_path_override=None,
    )
    runtime = build_model_task_runtime(config.model_execution)
    readiness = runtime.check_readiness()
    if not readiness.ready:
        return {"status": "qwen_unavailable", "runtime_status": asdict(readiness)}
    gliner = GlinerOrganizationMentionProposer(
        model_directory=gliner_model_path(config.model_resource_root)
    )
    if catalog:
        propose_validated_organization_mentions(
            OrganizationMentionProposalInput(str(catalog[0]["source_text"])), gliner
        )
    qwen_runs: list[dict[str, Any]] = []
    gliner_runs: list[dict[str, Any]] = []
    for repetition in range(1, REPETITIONS + 1):
        _progress("repetition_started", repetition=repetition)
        qwen_segments: list[dict[str, Any]] = []
        gliner_segments: list[dict[str, Any]] = []
        for index, segment in enumerate(catalog, start=1):
            source_text = str(segment["source_text"])
            key = {
                "fixture_path": segment["fixture_path"],
                "paragraph_node_id": segment["paragraph_node_id"],
                "source_segment_label": segment["source_segment_label"],
                "source_text_sha256": segment["source_text_sha256"],
                "source_text": source_text,
            }
            eligibility = classify_source_segment_model_eligibility(source_text)
            if eligibility == MODEL_ELIGIBLE:
                qwen_result = _qwen_proposals(
                    runtime,
                    config.model_execution,
                    prompt,
                    prompt_digest,
                    schema,
                    str(segment["source_segment_label"]),
                    source_text,
                    repetition,
                    str(segment["source_segment_id"]),
                )
                gliner_started = time.monotonic()
                batch = propose_validated_organization_mentions(
                    OrganizationMentionProposalInput(source_text), gliner
                )
                gliner_latency = round((time.monotonic() - gliner_started) * 1000)
                gliner_proposals = [
                    {
                        "text": proposal.text,
                        "start": proposal.start,
                        "end": proposal.end,
                        "score": proposal.score,
                    }
                    for proposal in batch.proposals
                ]
                gliner_status = "complete"
            else:
                qwen_result = {
                    "status": eligibility,
                    "model_eligibility": eligibility,
                    "latency_milliseconds": None,
                    "model_run_id": None,
                    "context_manifest_id": None,
                    "prompt_digest": prompt_digest,
                    "rendered_input": None,
                    "raw_output": None,
                    "execution_receipt": None,
                    "proposals": [],
                    "diagnostics": [eligibility],
                }
                gliner_latency = None
                gliner_proposals = []
                gliner_status = eligibility
            qwen_segments.append({**key, **qwen_result})
            gliner_segments.append(
                {
                    **key,
                    "status": gliner_status,
                    "model_eligibility": eligibility,
                    "latency_milliseconds": gliner_latency,
                    "proposals": gliner_proposals,
                }
            )
            if index % 10 == 0 or index == len(catalog):
                _progress(
                    "repetition_progress",
                    repetition=repetition,
                    completed=index,
                    total=len(catalog),
                )
        qwen_runs.append({"repetition": repetition, "segments": qwen_segments})
        gliner_runs.append({"repetition": repetition, "segments": gliner_segments})
        _progress("repetition_completed", repetition=repetition)
    identity = runtime.configured_identity
    qwen_identity = {
        "name": identity.name,
        "weights_digest": identity.weights_digest,
        "runtime": identity.runtime,
        "tokenizer_id": identity.tokenizer_id,
        "determinism_settings": [asdict(setting) for setting in identity.determinism_settings],
    }
    gliner_identity = {
        "package": "gliner",
        "package_version": GLINER_PACKAGE_VERSION,
        "model_id": GLINER_MODEL_ID,
        "model_revision": GLINER_MODEL_REVISION,
        "label": GLINER_LABEL,
        "threshold": GLINER_THRESHOLD,
        "device": GLINER_DEVICE,
        "quantized": False,
        "flat_ner": True,
        "multi_label": False,
    }
    return {
        "status": "completed",
        "schema_version": "php1_span_proposer_comparison_v1",
        "annotation_policy_id": catalog_document["annotation_policy_id"],
        "annotation_policy_sha256": hashlib.sha256(
            (ROOT / "docs/php1-named-organization-mention-policy-v1.json").read_bytes()
        ).hexdigest(),
        "annotation_status": catalog_document["annotation_status"],
        "catalog_path": str(catalog_path.relative_to(ROOT)),
        "catalog_sha256": hashlib.sha256(catalog_bytes).hexdigest(),
        "catalog": list(catalog),
        "gold_mention_count": sum(len(segment["gold_mentions"]) for segment in catalog),
        "source_segment_count": len(catalog),
        "case_count": int(catalog_document["paragraph_count"]),
        "repetitions": REPETITIONS,
        "representations": {
            path: sorted(
                {
                    str(segment["representation_id"])
                    for segment in catalog
                    if segment["fixture_path"] == path
                }
            )
            for path in sorted({str(segment["fixture_path"]) for segment in catalog})
        },
        "proposers": [
            proposer_report(
                "qwen2.5-h2-mention-v1",
                qwen_identity,
                catalog,
                qwen_runs,
                load_elapsed_milliseconds=None,
            ),
            proposer_report(
                "gliner-medium-v2.1",
                gliner_identity,
                catalog,
                gliner_runs,
                load_elapsed_milliseconds=gliner.load_elapsed_milliseconds,
            ),
        ],
    }


def render_qwen_input(
    prompt: bytes,
    schema: bytes,
    source_segment_label: str,
    source_text: str,
) -> bytes:
    segment = (
        f"[direct_prose]\n[paragraph]\nSOURCE SEGMENT: {source_segment_label}\n{source_text}"
    ).encode()
    return prompt + b"\n\n" + schema + b"\n\n" + segment


def parse_qwen_proposals(
    raw_output: bytes,
    source_segment_label: str,
    source_text: str,
    schema: Any,
) -> tuple[str, list[dict[str, Any]], list[str]]:
    try:
        parsed = schema.parse(raw_output)
    except ValueError as error:
        return "invalid_output", [], [str(error)]
    if isinstance(parsed, OrganizationMentionBatchAbstention):
        return "abstained", [], [f"abstention_reason:{parsed.reason}"]
    if not isinstance(parsed, OrganizationMentionBatch):
        raise TypeError("Organization mention schema returned an unsupported output type.")
    proposals: dict[tuple[int, int], dict[str, Any]] = {}
    for mention in parsed.mentions:
        if mention.source_segment_label != source_segment_label:
            return "invalid_output", [], ["source_segment_label_mismatch"]
        occurrences = _exact_occurrences(source_text, mention.organization_text)
        if not occurrences:
            return "invalid_output", [], ["organization_expression_not_in_source"]
        for start, end in occurrences:
            proposals[(start, end)] = {
                "text": mention.organization_text,
                "start": start,
                "end": end,
                "score": None,
            }
    return "complete", [proposals[key] for key in sorted(proposals)], []


def _qwen_proposals(
    runtime: Any,
    model_config: Any,
    prompt: bytes,
    prompt_digest: str,
    schema: Any,
    source_segment_label: str,
    source_text: str,
    repetition: int,
    source_segment_id: str,
) -> dict[str, Any]:
    rendered_input = render_qwen_input(
        prompt, schema.canonical_schema_bytes, source_segment_label, source_text
    )
    rendered_digest = hashlib.sha256(rendered_input).hexdigest()
    manifest_id = _id("ctx", source_segment_id, rendered_digest)
    spec = ModelExecutionSpec(
        model_profile_id=model_config.profile_name or "lm-studio",
        model_identity=runtime.configured_identity,
        generation_parameters=(
            ExecutionSetting("max_output_tokens", model_config.max_output_tokens),
            ExecutionSetting("seed", 17),
            ExecutionSetting("temperature", 0),
        ),
        prompt_id="paragraph_organization_mention_v1",
        prompt_digest=prompt_digest,
        schema_id=schema.schema_id,
        schema_digest=schema.digest,
        context_manifest_id=manifest_id,
        context_manifest_digest=hashlib.sha256(
            f"{manifest_id}:{rendered_digest}".encode()
        ).hexdigest(),
        rendered_input_digest=rendered_digest,
        output_contract_version=schema.output_contract_version,
    )
    model_run_id = _id("mrn", source_segment_id, str(repetition), rendered_digest)
    extraction_task_id = _id("ext", model_run_id)
    admission = admit_model_input(
        ModelInputAdmissionRequest(
            model_run_id=model_run_id,
            extraction_task_id=extraction_task_id,
            model_profile_id=spec.model_profile_id,
            model_identity=spec.model_identity,
            logical_input=rendered_input,
            configured_context_limit=model_config.context_tokens,
            reserved_output_tokens=model_config.max_output_tokens,
            safety_margin_tokens=256,
        ),
        runtime,
    )
    if admission.status is ModelInputAdmissionStatus.CONTEXT_BUDGET_BLOCKED:
        return {
            "status": "input_blocked",
            "model_eligibility": MODEL_ELIGIBLE,
            "latency_milliseconds": 0,
            "first_response_event_milliseconds": None,
            "model_run_id": model_run_id,
            "context_manifest_id": manifest_id,
            "prompt_digest": prompt_digest,
            "rendered_input": rendered_input.decode("utf-8"),
            "raw_output": None,
            "execution_receipt": None,
            "input_admission": admission.model_dump(mode="json"),
            "proposals": [],
            "diagnostics": [admission.blocked_reason],
        }
    task = ModelTaskRequest(
        extraction_task_id=extraction_task_id,
        task_fingerprint=hashlib.sha256(
            f"{source_segment_id}:{repetition}:{rendered_digest}".encode()
        ).hexdigest(),
        task_type="organization_mention_extraction",
        context_manifest_id=manifest_id,
        context_manifest_digest=spec.context_manifest_digest,
        rendered_input=rendered_input,
        rendered_input_digest=rendered_digest,
        execution_spec=spec,
        input_admission=admission,
    )
    started = time.monotonic()
    response = runtime.run_model_task(task)
    elapsed = round((time.monotonic() - started) * 1000)
    status, proposals, diagnostics = parse_qwen_proposals(
        response.raw_output, source_segment_label, source_text, schema
    )
    return {
        "status": status,
        "model_eligibility": MODEL_ELIGIBLE,
        "latency_milliseconds": elapsed,
        "first_response_event_milliseconds": response.first_response_event_milliseconds,
        "model_run_id": model_run_id,
        "context_manifest_id": manifest_id,
        "prompt_digest": prompt_digest,
        "rendered_input": rendered_input.decode("utf-8"),
        "raw_output": response.raw_output.decode("utf-8", errors="replace"),
        "execution_receipt": asdict(response.execution_receipt),
        "input_admission": admission.model_dump(mode="json"),
        "proposals": proposals,
        "diagnostics": diagnostics,
    }


def _exact_occurrences(source: str, expression: str) -> tuple[tuple[int, int], ...]:
    values: list[tuple[int, int]] = []
    cursor = 0
    while True:
        start = source.find(expression, cursor)
        if start < 0:
            return tuple(values)
        end = start + len(expression)
        values.append((start, end))
        cursor = end


def _id(prefix: str, *parts: str) -> str:
    return f"{prefix}_{hashlib.sha256(chr(31).join(parts).encode('utf-8')).hexdigest()[:24]}"


def _progress(event: str, **values: Any) -> None:
    print(json.dumps({"event": event, **values}, sort_keys=True), file=sys.stderr, flush=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    if arguments.output.exists():
        raise FileExistsError("Held-out proposer evidence cannot overwrite an existing file.")
    result = run(arguments.catalog, arguments.config)
    arguments.output.write_text(
        json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": result["status"], "output": str(arguments.output)}))
    return 0 if result["status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
