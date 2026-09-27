#!/usr/bin/env python3
"""Run the R2 trigger-containment candidate split and Gold correction.

This runner (1) pins the frozen Proposition Gold, trigger Gold, connection Gold,
and Stanza runtime by SHA-256, (2) derives the 187-candidate universe and emits
one corrected Attachment Gold file, and (3) re-scores the R1 Route Decisions
against the corrected Gold by projecting each decision onto its source span.

The candidate ID is span-derived everywhere in R2: ``trigger_containment_candidate_id``
hashes only ``source_text_sha256:start:end``.  The R1 router keys its decisions by a
lineage-aware candidate ID, so the re-score reconciles the two by projecting each R1
decision back to its exact source span and re-keying it to the R2 span ID.  A decision
whose span is missing from the 187-candidate universe is carried unchanged and recorded
in an explicit per-partition ``off_universe_candidate_ids`` census rather than dropped.

R2 executes no model and writes no canonical state.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Literal, cast

import run_competitive_attachment_edge_filter_experiment as cea14
from kotekomi_application import (
    AttachmentRouteDecision,
    CorrectedAttachmentGold,
    CorrectionPartitionReport,
    build_correction_partition_report,
    build_trigger_containment_correction_report,
)
from kotekomi_application.competitive_event_attachment import (
    CompetitiveAttachmentGoldDecision,
    CompetitiveAttachmentMatrix,
)
from kotekomi_application.deterministic_dependency_path_attachment_router import (
    AttachmentRouteReport,
)
from kotekomi_pipelines.deterministic_dependency_path_attachment_router import (
    attachment_gold_sets,
)
from kotekomi_pipelines.event_trigger_stage_local import TriggerGoldCatalog
from kotekomi_pipelines.source_grounded_proposition_stage_local import (
    PropositionGoldCatalog,
    PropositionGoldEvent,
    PropositionGoldFragmentRequirement,
    load_proposition_gold_catalog,
)
from kotekomi_pipelines.trigger_containment_candidate_split import (
    CORRECTED_CATALOG_ID,
    build_candidate_universe,
    correct_attachment_gold,
    corrected_gold_file_bytes,
    render_trigger_containment_correction_review,
    trigger_containment_candidate_id,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROPOSITION_GOLD = REPOSITORY_ROOT / "docs/hsq-source-grounded-proposition-gold-v1.json"
DEFAULT_TRIGGER_GOLD = REPOSITORY_ROOT / "docs/hsq-event-trigger-gold-v1.json"
DEFAULT_CONNECTION_GOLD = REPOSITORY_ROOT / "docs/hsq-event-entity-connection-gold-v2.json"
DEFAULT_STANZA_LOCK = (
    REPOSITORY_ROOT / "packages/adapters/src/kotekomi_adapters/stanza-model-lock.json"
)
TDD_PATH = (
    REPOSITORY_ROOT / "docs/2026-09-24-trigger-containment-candidate-split-and-gold-correction.md"
)

_PINNED_PROPOSITION_GOLD_SHA256 = "f496ab64e6590de05b1bc07ef069335fae6a7094b009b2fae3ca02cc627e54b0"
_PINNED_TRIGGER_GOLD_SHA256 = "844eb564fb953e8d202f211469465f29f6de95dd811c033506f616cf425fe83f"
_PINNED_CONNECTION_GOLD_SHA256 = "afb3b25a421913b8d6b1c29eda90ee681d3bbf71719f7e0377a626bfc6067294"
_PINNED_STANZA_LOCK_SHA256 = "4e66da09e0da1b3daef940ac8bec68d814b99d9fb10538e371548c9914d87bb3"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gold", type=Path, default=DEFAULT_PROPOSITION_GOLD)
    parser.add_argument("--trigger-gold", type=Path, default=DEFAULT_TRIGGER_GOLD)
    parser.add_argument("--connection-gold", type=Path, default=DEFAULT_CONNECTION_GOLD)
    parser.add_argument("--stanza-lock", type=Path, default=DEFAULT_STANZA_LOCK)
    parser.add_argument("--development-root", type=Path, required=True)
    parser.add_argument("--validation-root", type=Path, required=True)
    parser.add_argument("--route-report", type=Path, required=True)
    parser.add_argument("--run-root", type=Path, required=True)
    return _run(parser.parse_args())


def _run(args: argparse.Namespace) -> int:
    root = args.run_root.resolve()
    if root.exists() and any(root.iterdir()):
        raise ValueError("R2 requires an absent or empty run root.")
    root.mkdir(parents=True, exist_ok=True)
    _verify_pinned_digests(
        gold=args.gold.resolve(),
        trigger_gold=args.trigger_gold.resolve(),
        connection_gold=args.connection_gold.resolve(),
        stanza_lock=args.stanza_lock.resolve(),
    )
    catalog = load_proposition_gold_catalog(args.gold.resolve(), repository_root=REPOSITORY_ROOT)
    if catalog.review_status.value != "approved":
        raise ValueError("R2 requires approved Proposition Gold.")
    trigger_gold = TriggerGoldCatalog.model_validate_json(args.trigger_gold.read_bytes())

    corrected = correct_attachment_gold(
        catalog=catalog,
        trigger_gold=trigger_gold,
        source_catalog_sha256=_sha_file(args.gold.resolve()),
    )
    corrected_bytes = corrected_gold_file_bytes(catalog=catalog, corrected=corrected)
    corrected_path = root / f"{CORRECTED_CATALOG_ID}.json"

    route_report = AttachmentRouteReport.model_validate_json(args.route_report.read_bytes())
    development_root = args.development_root.resolve()
    validation_root = args.validation_root.resolve()
    cea14.validate_competitive_attachment_phase_evidence(
        development_root, expected_phase="development"
    )
    cea14.validate_competitive_attachment_phase_evidence(
        validation_root, expected_phase="validation"
    )
    development_partition, validation_partition = route_report.partitions
    development = _load_route_partition(
        "development",
        development_partition.decisions,
        development_root,
        catalog,
        corrected,
    )
    validation = _load_route_partition(
        "validation",
        validation_partition.decisions,
        validation_root,
        catalog,
        corrected,
    )
    report = build_trigger_containment_correction_report(
        development=development,
        validation=validation,
        corrected_gold_sha256=_sha_bytes(corrected_bytes),
    )
    report_path = root / "report.json"
    review_path = root / "comparison-review.md"
    _write_json(report_path, report.model_dump(mode="json"))
    review_path.write_text(
        render_trigger_containment_correction_review(corrected=corrected, report=report),
        encoding="utf-8",
    )
    corrected_path.write_bytes(corrected_bytes)

    _write_json(
        root / "run.json",
        {
            "schema_version": "trigger_containment_candidate_split_run_v1",
            "status": "complete",
            "result_fingerprint": report.result_fingerprint,
            "model_execution_count": report.model_execution_count,
            "canonical_write_count": report.canonical_write_count,
            "inputs": {
                "tdd": _sha_file(TDD_PATH),
                "proposition_gold": _sha_file(args.gold.resolve()),
                "trigger_gold": _sha_file(args.trigger_gold.resolve()),
                "connection_gold": _sha_file(args.connection_gold.resolve()),
                "stanza_lock": _sha_file(args.stanza_lock.resolve()),
                "route_report": _sha_file(args.route_report.resolve()),
                "development_phase": _phase_digests(development_root),
                "validation_phase": _phase_digests(validation_root),
            },
            "outputs": {
                "corrected_gold": _sha_bytes(corrected_bytes),
                "report": _sha_file(report_path),
                "review": _sha_file(review_path),
            },
        },
    )
    _write_json(
        root / "status.json",
        {
            "schema_version": "trigger_containment_candidate_split_status_v1",
            "status": "complete",
            "result_fingerprint": report.result_fingerprint,
            "corrected_gold": str(corrected_path),
            "corrected_gold_sha256": _sha_bytes(corrected_bytes),
            "report": str(report_path),
            "review": str(review_path),
        },
    )
    print(
        json.dumps(
            {
                "status": "complete",
                "run_root": str(root),
                "corrected_gold": str(corrected_path),
                "report": str(report_path),
                "review": str(review_path),
                "changed_candidate_count": report.changed_candidate_count,
                "result_fingerprint": report.result_fingerprint,
                "model_execution_count": report.model_execution_count,
                "canonical_write_count": report.canonical_write_count,
            },
            sort_keys=True,
        )
    )
    return 0


def _verify_pinned_digests(
    *,
    gold: Path,
    trigger_gold: Path,
    connection_gold: Path,
    stanza_lock: Path,
) -> None:
    for path, pinned in (
        (gold, _PINNED_PROPOSITION_GOLD_SHA256),
        (trigger_gold, _PINNED_TRIGGER_GOLD_SHA256),
        (connection_gold, _PINNED_CONNECTION_GOLD_SHA256),
        (stanza_lock, _PINNED_STANZA_LOCK_SHA256),
    ):
        if _sha_file(path) != pinned:
            raise ValueError(f"R2 frozen evidence drifted from its pinned digest: {path}.")


def _span_by_r1_id(
    matrices: tuple[CompetitiveAttachmentMatrix, ...],
) -> dict[str, tuple[str, int, int]]:
    """Map every R1 candidate ID to its source span (source digest, start, end)."""
    result: dict[str, tuple[str, int, int]] = {}
    for matrix in matrices:
        for candidate in matrix.candidates:
            span = (candidate.source_text_sha256, candidate.start, candidate.end)
            prior = result.get(candidate.id)
            if prior is not None and prior != span:
                raise ValueError("R1 candidate ID repeats with a different source span.")
            result[candidate.id] = span
    return result


def _rekey_decision(
    decision: AttachmentRouteDecision,
    span_id: str,
) -> AttachmentRouteDecision:
    return decision.model_copy(update={"candidate_id": span_id})


def _contains_temporal_fragment(start: int, end: int, event: PropositionGoldEvent) -> bool:
    return any(
        PropositionGoldFragmentRequirement.TEMPORAL in fragment.requirements
        and start >= fragment.start
        and end <= fragment.end
        for fragment in event.fragments
    )


def _load_route_partition(
    phase: Literal["development", "validation"],
    route_decisions: tuple[AttachmentRouteDecision, ...],
    root: Path,
    catalog: PropositionGoldCatalog,
    corrected: CorrectedAttachmentGold,
) -> CorrectionPartitionReport:
    matrices = _load_matrices(root / "matrices.json")
    oracle = _load_oracle(root / "oracle.json")
    bindings = _load_bindings(root / "gold-bindings.json")

    span_by_r1_id = _span_by_r1_id(matrices)
    universe = {item.candidate_id for item in build_candidate_universe(catalog)}
    gold_by_tge = {event.event_id: event for event in catalog.events}
    gold_by_sge = {
        bindings[item.event_id]: item for item in catalog.events if item.event_id in bindings
    }
    before_gold = attachment_gold_sets(oracle)

    decisions: list[AttachmentRouteDecision] = []
    off_universe: list[str] = []
    before_attachment: dict[str, tuple[str, ...]] = {}
    before_mixed: dict[str, bool] = {}
    before_temporal: dict[str, bool] = {}
    for decision in route_decisions:
        span = span_by_r1_id.get(decision.candidate_id)
        if span is None:
            raise ValueError(f"R1 route decision lacks a matrix span: {decision.candidate_id}.")
        span_id = trigger_containment_candidate_id(*span)
        if span_id not in universe:
            off_universe.append(span_id)
            continue
        decisions.append(_rekey_decision(decision, span_id))
        sge_ids = before_gold.get(decision.candidate_id, ())
        before_attachment[span_id] = sge_ids
        before_mixed[span_id] = len(sge_ids) > 1
        before_temporal[span_id] = any(
            sge in gold_by_sge and _contains_temporal_fragment(span[1], span[2], gold_by_sge[sge])
            for sge in sge_ids
        )

    after_attachment: dict[str, tuple[str, ...]] = {}
    after_mixed: dict[str, bool] = {}
    after_temporal: dict[str, bool] = {}
    for label in corrected.corrected_labels:
        after_attachment[label.candidate_id] = label.gold_event_ids
        after_mixed[label.candidate_id] = len(label.gold_event_ids) > 1
        after_temporal[label.candidate_id] = any(
            _contains_temporal_fragment(
                label.source_range.start, label.source_range.end, gold_by_tge[event_id]
            )
            for event_id in label.gold_event_ids
        )

    return build_correction_partition_report(
        partition_role=phase,
        decisions=tuple(decisions),
        before_attachment=before_attachment,
        before_mixed=before_mixed,
        before_temporal=before_temporal,
        after_attachment=after_attachment,
        after_mixed=after_mixed,
        after_temporal=after_temporal,
        off_universe_candidate_ids=tuple(sorted(off_universe)),
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


def _sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
