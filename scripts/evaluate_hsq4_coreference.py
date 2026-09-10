"""Evaluate the pinned F-Coref Adapter against frozen source-span cases."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Annotated, Literal, Self

from kotekomi_adapters import (
    FCorefAdapter,
    FCorefConfig,
    FCorefModelResourceAdapter,
    fcoref_expected_resource_identity,
    fcoref_model_path,
    fcoref_python_path,
)
from kotekomi_application import (
    CoreferenceCaseEvaluation,
    CoreferenceGoldCase,
    CoreferenceGoldSpan,
    evaluate_coreference_proposer,
)
from pydantic import BaseModel, ConfigDict, Field, model_validator

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CATALOG = ROOT / "docs" / "hsq4-coreference-gold-v1.json"
WORKER_SCRIPT = ROOT / "scripts" / "fcoref_worker.py"


class _TextSelector(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    text: Annotated[str, Field(min_length=1)]
    occurrence: Annotated[int, Field(ge=1)]


class _CatalogCase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    case_id: Annotated[str, Field(min_length=1)]
    fixture_path: Annotated[str, Field(min_length=1)]
    representation_id: Annotated[str, Field(min_length=1)]
    paragraph_node_id: Annotated[str, Field(min_length=1)]
    source_text_sha256: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    source_text: Annotated[str, Field(min_length=1)]
    target: _TextSelector
    antecedent_candidates: tuple[_TextSelector, ...]
    expected_antecedents: tuple[_TextSelector, ...]

    @model_validator(mode="after")
    def validate_source(self) -> Self:
        if hashlib.sha256(self.source_text.encode()).hexdigest() != self.source_text_sha256:
            raise ValueError("Coreference Gold source digest does not match its text.")
        if not self.expected_antecedents:
            raise ValueError("Coreference Gold case requires at least one antecedent.")
        if not self.antecedent_candidates:
            raise ValueError("Coreference Gold case requires source candidate boundaries.")
        return self


class _Catalog(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["hsq4_coreference_gold_catalog_v2"]
    catalog_id: Annotated[str, Field(min_length=1)]
    annotation_status: Literal["frozen_human_reviewed_source_with_adjudicated_references"]
    source_packet: Literal["docs/2026-08-28-organization-mention-held-out-annotation-packet.md"]
    source_packet_sha256: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    cases: tuple[_CatalogCase, ...]

    @model_validator(mode="after")
    def validate_catalog(self) -> Self:
        if not self.cases:
            raise ValueError("Coreference Gold catalog must not be empty.")
        if len({item.case_id for item in self.cases}) != len(self.cases):
            raise ValueError("Coreference Gold case IDs must be distinct.")
        packet = ROOT / self.source_packet
        if hashlib.sha256(packet.read_bytes()).hexdigest() != self.source_packet_sha256:
            raise ValueError("Coreference Gold source packet has drifted.")
        return self


def load_catalog(path: Path) -> tuple[_Catalog, tuple[CoreferenceGoldCase, ...]]:
    """Validate human-readable selectors and compile exact half-open ranges."""
    catalog = _Catalog.model_validate_json(path.read_bytes())
    cases: list[CoreferenceGoldCase] = []
    for item in catalog.cases:
        target = _span(item.source_text, item.target)
        candidates = tuple(
            sorted(
                (_span(item.source_text, selector) for selector in item.antecedent_candidates),
                key=lambda value: (value.start, value.end),
            )
        )
        antecedents = tuple(
            sorted(
                (_span(item.source_text, selector) for selector in item.expected_antecedents),
                key=lambda value: (value.start, value.end),
            )
        )
        cases.append(
            CoreferenceGoldCase(
                case_id=item.case_id,
                source_segment_id=item.paragraph_node_id,
                source_text=item.source_text,
                target=target,
                antecedent_candidates=candidates,
                expected_antecedents=antecedents,
            )
        )
    return catalog, tuple(cases)


def evaluate(resource_root: Path, catalog_path: Path) -> dict[str, object]:
    """Run the production Adapter and preserve exact data-in/data-out evidence."""
    catalog_bytes = catalog_path.read_bytes()
    catalog, cases = load_catalog(catalog_path)
    readiness = FCorefModelResourceAdapter().inspect(resource_root)
    if readiness.status.value != "ready":
        raise RuntimeError(
            "F-Coref managed resources are not ready: " + "; ".join(readiness.diagnostics)
        )
    adapter = FCorefAdapter(
        FCorefConfig(
            python_executable=fcoref_python_path(resource_root),
            worker_script=WORKER_SCRIPT,
            model_directory=fcoref_model_path(resource_root),
            resource_identity=fcoref_expected_resource_identity(),
        )
    )
    try:
        report = evaluate_coreference_proposer(
            cases=cases,
            proposer=adapter,
            tokenizer=adapter,
        )
    finally:
        adapter.close()
    return {
        "schema_version": "hsq4_coreference_bakeoff_v2",
        "status": "passed" if report.zero_wrong_resolution_gate_passed else "failed",
        "catalog_id": catalog.catalog_id,
        "catalog_sha256": hashlib.sha256(catalog_bytes).hexdigest(),
        "resource_identity": fcoref_expected_resource_identity(),
        "metrics": {
            "model_id": report.model_id,
            "case_count": report.case_count,
            "exact_case_count": report.exact_case_count,
            "wrong_resolution_count": report.wrong_resolution_count,
            "true_positive_count": report.true_positive_count,
            "false_positive_count": report.false_positive_count,
            "false_negative_count": report.false_negative_count,
            "invalid_output_count": report.invalid_output_count,
            "resolved_count": report.resolved_count,
            "ambiguous_count": report.ambiguous_count,
            "unresolved_count": report.unresolved_count,
            "precision": report.precision,
            "recall": report.recall,
            "exact_span_validity": report.exact_span_validity,
            "elapsed_milliseconds": report.elapsed_milliseconds,
        },
        "gates": {
            "fcoref_model_identity": report.model_id == "biu-nlp/f-coref",
            "at_least_one_resolved_case": report.resolved_count > 0,
            "zero_wrong_resolutions": report.wrong_resolution_count == 0,
            "all_outputs_source_valid": report.invalid_output_count == 0,
            "production_eligible": report.zero_wrong_resolution_gate_passed,
        },
        "cases": [
            _case_payload(source, evaluation)
            for source, evaluation in zip(cases, report.evaluations, strict=True)
        ],
    }


def _case_payload(
    case: CoreferenceGoldCase,
    evaluation: CoreferenceCaseEvaluation,
) -> dict[str, object]:
    output: dict[str, object]
    if evaluation.result is None:
        output = {"status": "invalid", "error": evaluation.error}
    else:
        output = {
            "status": "completed",
            "raw_model_output": evaluation.result.trace.output["raw_output"],
            "observation": evaluation.result.observation.model_dump(mode="json"),
            "decision": evaluation.result.decision.model_dump(mode="json"),
            "stage_trace": evaluation.result.trace.model_dump(mode="json"),
        }
    return {
        "case_id": case.case_id,
        "input": {
            "source_segment_id": case.source_segment_id,
            "source_text": case.source_text,
            "target": {
                "start": case.target.start,
                "end": case.target.end,
                "text": evaluation.target_text,
            },
            "antecedent_candidates": [
                {
                    "start": span.start,
                    "end": span.end,
                    "text": case.source_text[span.start : span.end],
                }
                for span in case.antecedent_candidates
            ],
        },
        "expected": {
            "antecedent_spans": [
                {
                    "start": span.start,
                    "end": span.end,
                    "text": case.source_text[span.start : span.end],
                }
                for span in case.expected_antecedents
            ]
        },
        "actual": {"antecedent_texts": list(evaluation.actual_antecedents)},
        "output": output,
    }


def _span(source_text: str, selector: _TextSelector) -> CoreferenceGoldSpan:
    start = -1
    cursor = 0
    for _ in range(selector.occurrence):
        start = source_text.find(selector.text, cursor)
        if start < 0:
            raise ValueError(
                f"Coreference selector is absent: {selector.text!r} occurrence "
                f"{selector.occurrence}."
            )
        cursor = start + len(selector.text)
    return CoreferenceGoldSpan(start, start + len(selector.text))


def canonical_json(value: object) -> str:
    return (
        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--resource-root", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    try:
        report = evaluate(arguments.resource_root.resolve(), arguments.catalog.resolve())
    except (OSError, RuntimeError, ValueError) as error:
        print(json.dumps({"status": "blocked", "diagnostics": [str(error)]}, sort_keys=True))
        return 2
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(canonical_json(report), encoding="utf-8")
    print(
        json.dumps(
            {
                "status": report["status"],
                "output": str(arguments.output),
                "metrics": report["metrics"],
                "gates": report["gates"],
            },
            sort_keys=True,
        )
    )
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
