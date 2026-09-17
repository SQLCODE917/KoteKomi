#!/usr/bin/env python3
"""Re-score one preserved Event-entity run from typed execution evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, cast

from kotekomi_application import (
    EventEntityConnectionPreview,
    canonical_event_entity_connection_preview_bytes,
)
from kotekomi_domain import ModelRun
from kotekomi_pipelines.evaluation_contracts import EvaluationPhase
from kotekomi_pipelines.event_entity_connection_stage_local import (
    EventEntityCaseEvaluation,
    EventEntityPhaseReport,
    build_event_entity_phase_report,
    evaluate_event_entity_preview,
    load_connection_gold_catalog,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GOLD = REPOSITORY_ROOT / "docs" / "hsq-event-entity-connection-gold-v2.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gold", type=Path, default=DEFAULT_GOLD)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = verify_measurement(
        gold_path=args.gold.resolve(),
        run_root=args.run_root.resolve(),
    )
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = _canonical_json(report.model_dump(mode="json")) + "\n"
    output.write_text(payload, encoding="utf-8")
    EventEntityPhaseReport.model_validate_json(output.read_bytes())
    print(
        json.dumps(
            {
                "candidate_inventory_sha256": report.candidate_inventory_sha256,
                "occurrence_count": report.occurrence_count,
                "output": str(output),
                "phase": report.phase,
                "result_fingerprint": report.result_fingerprint,
                "schema_version": report.schema_version,
                "semantic_experiment_passed": report.passed,
                "strict_metrics": report.strict_metrics.model_dump(mode="json"),
                "unresolved_connection_count": report.unresolved_connection_count,
                "verified": True,
            },
            sort_keys=True,
        )
    )
    return 0


def verify_measurement(
    *,
    gold_path: Path,
    run_root: Path,
) -> EventEntityPhaseReport:
    """Build a current report without rerunning a model or accepting prior metrics."""
    gold_payload = gold_path.read_bytes()
    catalog, _, _ = load_connection_gold_catalog(
        gold_path,
        repository_root=REPOSITORY_ROOT,
        require_approved=True,
    )
    metadata = _object(_read_json(run_root / "run.json"), "run metadata")
    phase = cast(EvaluationPhase, _required_string(metadata, "phase"))
    if phase not in {"development", "validation"}:
        raise ValueError("Measurement run phase is invalid.")
    repetition = _required_int(metadata, "repetition")
    gold_by_id = {item.event_id: item for item in catalog.events if item.phase == phase}
    evaluations: list[EventEntityCaseEvaluation] = []
    elapsed = 0
    observed_event_ids: set[str] = set()
    for path in sorted((run_root / "events").glob("*.json")):
        record = _object(_read_json(path), "execution record")
        if record.get("schema_version") != "event_entity_connection_execution_v1":
            raise ValueError("Measurement execution record schema is invalid.")
        if record.get("accepted_ledger_change_count") != 0:
            raise ValueError("Measurement execution record changed accepted Ledger state.")
        event_id = _required_string(record, "gold_event_id")
        if event_id not in gold_by_id or event_id in observed_event_ids:
            raise ValueError("Measurement execution record has an unknown or repeated Event.")
        prepared = _object(record.get("prepared_input"), "prepared input")
        source_text = _required_string(prepared, "source_text")
        preview = EventEntityConnectionPreview.model_validate_json(
            _canonical_json(record.get("preview"))
        )
        expected_preview_sha256 = hashlib.sha256(
            canonical_event_entity_connection_preview_bytes(preview)
        ).hexdigest()
        if record.get("preview_sha256") != expected_preview_sha256:
            raise ValueError("Measurement execution Preview digest is invalid.")
        model_runs = tuple(
            ModelRun.model_validate_json(_canonical_json(item))
            for item in _array(record.get("model_runs"), "model runs")
        )
        if {item.id for item in model_runs} != set(preview.model_run_ids):
            raise ValueError("Measurement execution ModelRun evidence is incomplete.")
        for model_run in model_runs:
            elapsed += _required_int(
                model_run.execution_diagnostics,
                "elapsed_milliseconds",
            )
        evaluations.append(
            evaluate_event_entity_preview(
                gold_by_id[event_id],
                source_text=source_text,
                preview=preview,
            )
        )
        observed_event_ids.add(event_id)
    if observed_event_ids != set(gold_by_id):
        raise ValueError("Measurement run does not cover its complete Gold phase.")
    return build_event_entity_phase_report(
        catalog=catalog,
        catalog_sha256=hashlib.sha256(gold_payload).hexdigest(),
        phase=phase,
        repetition=repetition,
        evaluations=tuple(evaluations),
        model_elapsed_milliseconds=elapsed,
    )


def _read_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _object(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"Measurement {label} must be a JSON object.")
    raw = cast(dict[object, object], value)
    if not all(isinstance(key, str) for key in raw):
        raise ValueError(f"Measurement {label} keys must be strings.")
    return cast(dict[str, Any], raw)


def _array(value: object, label: str) -> list[object]:
    if not isinstance(value, list):
        raise ValueError(f"Measurement {label} must be a JSON array.")
    return cast(list[object], value)


def _required_string(value: dict[str, Any], key: str) -> str:
    observed = value.get(key)
    if not isinstance(observed, str) or not observed:
        raise ValueError(f"Measurement {key} must be a nonempty string.")
    return observed


def _required_int(value: dict[str, Any], key: str) -> int:
    observed = value.get(key)
    if not isinstance(observed, int) or isinstance(observed, bool) or observed < 0:
        raise ValueError(f"Measurement {key} must be a nonnegative integer.")
    return observed


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


if __name__ == "__main__":
    raise SystemExit(main())
