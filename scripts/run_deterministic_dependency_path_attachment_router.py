#!/usr/bin/env python3
"""Run the model-free R1 deterministic dependency-path attachment router."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, cast

import run_competitive_attachment_edge_filter_experiment as cea14
from kotekomi_application import (
    AttachmentRouteCeiling,
    AttachmentRoutePartitionReport,
    CompetitiveAttachmentGoldDecision,
    CompetitiveAttachmentMatrix,
    build_attachment_route_report,
)
from kotekomi_pipelines.deterministic_dependency_path_attachment_router import (
    attachment_gold_sets,
    build_attachment_route_ceilings,
    build_attachment_route_observations,
    build_attachment_route_phase,
    render_dependency_path_attachment_route_review,
)
from kotekomi_pipelines.event_entity_connection_stage_local import (
    EventEntityExperimentInput,
)
from kotekomi_pipelines.source_grounded_proposition_stage_local import (
    PropositionGoldCatalog,
    PropositionGoldEvent,
    PropositionGoldFragmentRequirement,
    load_proposition_gold_catalog,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GOLD = REPOSITORY_ROOT / "docs/hsq-source-grounded-proposition-gold-v1.json"
STANZA_LOCK = REPOSITORY_ROOT / "packages/adapters/src/kotekomi_adapters/stanza-model-lock.json"
TDD_PATH = REPOSITORY_ROOT / "docs/2026-09-24-deterministic-dependency-path-attachment-router.md"

_Phase = Literal["development", "validation"]
_PINNED_PROPOSITION_GOLD_SHA256 = (
    "f496ab64e6590de05b1bc07ef069335fae6a7094b009b2fae3ca02cc627e54b0"
)
_PINNED_STANZA_LOCK_SHA256 = "4e66da09e0da1b3daef940ac8bec68d814b99d9fb10538e371548c9914d87bb3"


@dataclass(frozen=True)
class _PhaseEvidence:
    root: Path
    inputs: tuple[EventEntityExperimentInput, ...]
    matrices: tuple[CompetitiveAttachmentMatrix, ...]
    oracle: dict[str, tuple[CompetitiveAttachmentGoldDecision, ...]]
    bindings: dict[str, str]


@dataclass(frozen=True)
class _PartitionBuild:
    report: AttachmentRoutePartitionReport
    ceilings: tuple[AttachmentRouteCeiling, ...]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--development-root", type=Path, required=True)
    parser.add_argument("--validation-root", type=Path, required=True)
    parser.add_argument("--gold", type=Path, default=DEFAULT_GOLD)
    parser.add_argument("--run-root", type=Path, required=True)
    return _run(parser.parse_args())


def _run(args: argparse.Namespace) -> int:
    root = args.run_root.resolve()
    if root.exists() and any(root.iterdir()):
        raise ValueError("R1 requires an absent or empty run root.")
    root.mkdir(parents=True, exist_ok=True)
    development_root = args.development_root.resolve()
    validation_root = args.validation_root.resolve()
    cea14.validate_competitive_attachment_phase_evidence(
        development_root, expected_phase="development"
    )
    cea14.validate_competitive_attachment_phase_evidence(
        validation_root, expected_phase="validation"
    )
    _verify_pinned_digests(args.gold.resolve())
    catalog = load_proposition_gold_catalog(args.gold.resolve(), repository_root=REPOSITORY_ROOT)
    if catalog.review_status.value != "approved":
        raise ValueError("R1 requires approved Proposition Gold.")
    development = _load_phase("development", development_root)
    validation = _load_phase("validation", validation_root)
    gold_by_sge = _gold_by_source_grounded_event(
        catalog, development.bindings, validation.bindings
    )
    development_build = _build_partition("development", development, catalog, gold_by_sge)
    validation_build = _build_partition("validation", validation, catalog, gold_by_sge)
    report = build_attachment_route_report(
        development=development_build.report,
        validation=validation_build.report,
        ceilings=(*development_build.ceilings, *validation_build.ceilings),
    )
    report_path = root / "report.json"
    review_path = root / "comparison-review.md"
    _write_json(report_path, report.model_dump(mode="json"))
    review_path.write_text(render_dependency_path_attachment_route_review(report), encoding="utf-8")
    input_bindings = _input_bindings(
        gold=args.gold.resolve(),
        development=development_root,
        validation=validation_root,
    )
    run_metadata = {
        "schema_version": "deterministic_dependency_path_attachment_router_run_v1",
        "status": "complete",
        "result_fingerprint": report.result_fingerprint,
        "model_execution_count": report.model_execution_count,
        "canonical_write_count": report.canonical_write_count,
        "inputs": input_bindings,
        "outputs": {
            "report": _file_digest(report_path),
            "review": _file_digest(review_path),
        },
    }
    _write_json(root / "run.json", run_metadata)
    _write_json(
        root / "status.json",
        {
            "schema_version": "deterministic_dependency_path_attachment_router_status_v1",
            "status": "complete",
            "result_fingerprint": report.result_fingerprint,
            "report": str(report_path),
            "report_sha256": _sha_file(report_path),
            "review": str(review_path),
            "review_sha256": _sha_file(review_path),
        },
    )
    print(
        json.dumps(
            {
                "status": "complete",
                "run_root": str(root),
                "report": str(report_path),
                "review": str(review_path),
                "result_fingerprint": report.result_fingerprint,
                "model_execution_count": report.model_execution_count,
                "canonical_write_count": report.canonical_write_count,
            },
            sort_keys=True,
        )
    )
    return 0


def _build_partition(
    phase: _Phase,
    evidence: _PhaseEvidence,
    catalog: PropositionGoldCatalog,
    gold_by_sge: dict[str, PropositionGoldEvent],
) -> _PartitionBuild:
    del catalog
    gold_attachment = attachment_gold_sets(evidence.oracle)
    gold_mixed = {cid: len(ids) > 1 for cid, ids in gold_attachment.items()}
    gold_temporal = _gold_temporal_flags(evidence.matrices, gold_by_sge, gold_attachment)
    observations = build_attachment_route_observations(
        phase=phase, matrices=evidence.matrices, inputs=evidence.inputs
    )
    partition_report = build_attachment_route_phase(
        phase=phase,
        observations=observations,
        gold_attachment=gold_attachment,
        gold_mixed=gold_mixed,
        gold_temporal=gold_temporal,
    )
    ceilings = build_attachment_route_ceilings(
        partition_role=phase,
        observations=observations,
        gold_attachment=gold_attachment,
    )
    return _PartitionBuild(report=partition_report, ceilings=ceilings)


def _load_phase(phase: _Phase, root: Path) -> _PhaseEvidence:
    return _PhaseEvidence(
        root=root,
        inputs=_load_inputs(root / "inputs.jsonl"),
        matrices=_load_matrices(root / "matrices.json"),
        oracle=_load_oracle(root / "oracle.json"),
        bindings=_load_bindings(root / "gold-bindings.json"),
    )


def _load_inputs(path: Path) -> tuple[EventEntityExperimentInput, ...]:
    return tuple(
        EventEntityExperimentInput.model_validate_json(line)
        for line in path.read_bytes().splitlines()
        if line
    )


def _load_matrices(path: Path) -> tuple[CompetitiveAttachmentMatrix, ...]:
    value = json.loads(path.read_bytes())
    if not isinstance(value, list):
        raise ValueError("R1 matrix evidence must be a JSON array.")
    return tuple(
        CompetitiveAttachmentMatrix.model_validate_json(_canonical_json(item))
        for item in cast(list[object], value)
    )


def _load_oracle(path: Path) -> dict[str, tuple[CompetitiveAttachmentGoldDecision, ...]]:
    value = _read_json(path)
    return {
        str(matrix_id): tuple(
            CompetitiveAttachmentGoldDecision.model_validate_json(_canonical_json(item))
            for item in cast(list[object], decisions)
        )
        for matrix_id, decisions in value.items()
    }


def _load_bindings(path: Path) -> dict[str, str]:
    return {str(key): str(value) for key, value in _read_json(path).items()}


def _gold_by_source_grounded_event(
    catalog: PropositionGoldCatalog,
    development_bindings: dict[str, str],
    validation_bindings: dict[str, str],
) -> dict[str, PropositionGoldEvent]:
    bindings = {**development_bindings, **validation_bindings}
    if set(bindings) != {item.event_id for item in catalog.events}:
        raise ValueError("R1 Gold bindings do not cover forty Events.")
    return {bindings[item.event_id]: item for item in catalog.events}


def _gold_temporal_flags(
    matrices: tuple[CompetitiveAttachmentMatrix, ...],
    gold_by_sge: dict[str, PropositionGoldEvent],
    gold_attachment: dict[str, tuple[str, ...]],
) -> dict[str, bool]:
    candidate_by_id = {
        candidate.id: candidate for matrix in matrices for candidate in matrix.candidates
    }
    result: dict[str, bool] = {}
    for candidate_id, event_ids in gold_attachment.items():
        candidate = candidate_by_id[candidate_id]
        result[candidate_id] = any(
            event_id in gold_by_sge
            and _contains_temporal_fragment(
                candidate.start, candidate.end, gold_by_sge[event_id]
            )
            for event_id in event_ids
        )
    return result


def _contains_temporal_fragment(
    start: int, end: int, event: PropositionGoldEvent
) -> bool:
    return any(
        PropositionGoldFragmentRequirement.TEMPORAL in fragment.requirements
        and start >= fragment.start
        and end <= fragment.end
        for fragment in event.fragments
    )


def _verify_pinned_digests(gold: Path) -> None:
    if _sha_file(gold) != _PINNED_PROPOSITION_GOLD_SHA256:
        raise ValueError("R1 Proposition Gold digest drifted from the frozen evidence.")
    if _sha_file(STANZA_LOCK) != _PINNED_STANZA_LOCK_SHA256:
        raise ValueError("R1 Stanza lock digest drifted from the frozen evidence.")


def _input_bindings(*, gold: Path, development: Path, validation: Path) -> dict[str, object]:
    return {
        "tdd": _file_digest(TDD_PATH),
        "proposition_gold": _file_digest(gold),
        "stanza_lock": _file_digest(STANZA_LOCK),
        "development": _phase_digests(development),
        "validation": _phase_digests(validation),
    }


def _phase_digests(root: Path) -> dict[str, str]:
    return {
        name: _sha_file(root / filename)
        for name, filename in (
            ("run", "run.json"),
            ("report", "report.json"),
            ("manifest", "manifest.json"),
            ("inputs", "inputs.jsonl"),
            ("matrices", "matrices.json"),
            ("oracle", "oracle.json"),
            ("gold_bindings", "gold-bindings.json"),
            ("canonical_state", "canonical-state.json"),
        )
    }


def _file_digest(path: Path) -> str:
    resolved = path.resolve()
    if not resolved.is_file():
        raise ValueError(f"R1 evidence file is missing: {resolved}.")
    return _sha_file(resolved)


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(
            value, allow_nan=False, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        + "\n",
        encoding="utf-8",
    )


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_bytes())
    if not isinstance(value, dict):
        raise ValueError(f"Expected one JSON object: {path}.")
    return cast(dict[str, Any], value)


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value, allow_nan=False, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()


def _sha_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
