"""Evaluate deterministic Organization mention boundary reconciliation."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from typing import Any, cast

from kotekomi_application import (
    ExtractionStageStatus,
    MentionBoundaryDecisionStatus,
    MentionProposalObservation,
    build_extraction_stage_trace,
    canonical_boundary_reconciliation_json,
    extraction_stage_trace_to_json,
    fuse_mention_proposals,
    organization_mention_text_schema_bytes,
    reconcile_organization_mention_boundaries,
    validate_extraction_stage_trace_chain,
)
from kotekomi_domain.models import JsonValue

ROOT = Path(__file__).resolve().parents[1]
PROMPT_PATH = ROOT / "prompts/paragraph_organization_mention_v1.md"
REPORT_SCHEMA_VERSION = "organization_boundary_reconciliation_evaluation_v1"
PROPOSAL_SCHEMA_VERSION = "php1_span_proposer_comparison_v1"
REPETITIONS = 3


def evaluate_boundary_reconciliation(
    proposal_report: dict[str, Any],
    catalog: dict[str, Any],
    *,
    phase: str,
    proposal_report_sha256: str,
    catalog_sha256: str,
) -> dict[str, Any]:
    """Evaluate one pinned proposal report without rerunning either proposer."""
    if phase not in {"development", "held_out"}:
        raise ValueError("Boundary evaluation phase must be development or held_out.")
    _validate_sha256(proposal_report_sha256, "proposal report")
    _validate_sha256(catalog_sha256, "catalog")
    if proposal_report.get("status") != "completed":
        raise ValueError("Boundary evaluation requires a completed proposal report.")
    if proposal_report.get("schema_version") != PROPOSAL_SCHEMA_VERSION:
        raise ValueError("Boundary proposal report schema does not match the contract.")
    if proposal_report.get("repetitions") != REPETITIONS:
        raise ValueError("Boundary proposal evidence requires exactly three repetitions.")
    catalog_segments = _catalog_segments(catalog)
    proposer_by_id = {
        str(proposer["proposer_id"]): proposer
        for proposer in cast(list[dict[str, Any]], proposal_report.get("proposers", []))
    }
    required_proposers = {"qwen2.5-h2-mention-v1", "gliner-medium-v2.1"}
    if set(proposer_by_id) != required_proposers:
        raise ValueError("Boundary evaluation requires the pinned Qwen and GLiNER proposers.")
    prompt_bytes = PROMPT_PATH.read_bytes()
    prompt_sha256 = hashlib.sha256(prompt_bytes).hexdigest()
    prompt_text = prompt_bytes.decode("utf-8")
    run_maps = {
        proposer_id: _proposer_run_maps(proposer, catalog_segments)
        for proposer_id, proposer in proposer_by_id.items()
    }
    runs: list[dict[str, Any]] = []
    totals = Counter[str]()
    for repetition in range(1, REPETITIONS + 1):
        segment_results: list[dict[str, Any]] = []
        for key in sorted(catalog_segments):
            gold = catalog_segments[key]
            qwen = run_maps["qwen2.5-h2-mention-v1"][repetition][key]
            gliner = run_maps["gliner-medium-v2.1"][repetition][key]
            source_text = _validate_shared_source(gold, qwen, gliner)
            if qwen.get("prompt_digest") != prompt_sha256:
                raise ValueError(
                    "Pinned Qwen proposal prompt digest does not match the exact prompt bytes."
                )
            source_segment_id = str(
                gold.get("source_segment_id")
                or _id("src", key[0], key[1], key[2], str(gold["source_text_sha256"]))
            )
            observations = _proposal_observations(qwen, "qwen2.5-h2-mention-v1") + (
                _proposal_observations(gliner, "gliner-medium-v2.1")
            )
            rendered_qwen_input = _render_qwen_input(
                prompt_bytes,
                organization_mention_text_schema_bytes(),
                key[2],
                source_text,
            )
            candidates = fuse_mention_proposals(source_text, source_segment_id, observations)
            reconciliation = reconcile_organization_mention_boundaries(
                source_text=source_text,
                source_segment_id=source_segment_id,
                candidates=candidates,
            )
            traces = _stage_traces(
                repetition=repetition,
                source_segment_id=source_segment_id,
                source_text_sha256=str(gold["source_text_sha256"]),
                proposal_report_sha256=proposal_report_sha256,
                qwen_identity=cast(
                    dict[str, Any], proposer_by_id["qwen2.5-h2-mention-v1"]["identity"]
                ),
                gliner_identity=cast(
                    dict[str, Any], proposer_by_id["gliner-medium-v2.1"]["identity"]
                ),
                prompt_text=prompt_text,
                rendered_qwen_input=rendered_qwen_input,
                qwen=qwen,
                gliner=gliner,
                candidates=candidates,
                reconciliation_json=canonical_boundary_reconciliation_json(reconciliation),
            )
            outcome = _score_segment(
                cast(list[dict[str, Any]], gold["gold_mentions"]),
                qwen,
                gliner,
                candidates,
                reconciliation,
            )
            totals.update(cast(dict[str, int], outcome["counts"]))
            segment_results.append(
                {
                    "fixture_path": key[0],
                    "paragraph_node_id": key[1],
                    "source_segment_label": key[2],
                    "source_segment_id": source_segment_id,
                    "source_text": source_text,
                    "source_text_sha256": gold["source_text_sha256"],
                    "gold_mentions": gold["gold_mentions"],
                    "qwen": {
                        "prompt_text": prompt_text,
                        "prompt_sha256": prompt_sha256,
                        "rendered_input": rendered_qwen_input,
                        "model_identity": proposer_by_id["qwen2.5-h2-mention-v1"]["identity"],
                        "result": qwen,
                    },
                    "gliner": {
                        "rendered_source_text": source_text,
                        "effective_configuration": proposer_by_id["gliner-medium-v2.1"]["identity"],
                        "result": gliner,
                    },
                    "fused_candidates": [asdict(candidate) for candidate in candidates],
                    "reconciliation": json.loads(
                        canonical_boundary_reconciliation_json(reconciliation)
                    ),
                    "outcome": outcome,
                    "stage_traces": [extraction_stage_trace_to_json(trace) for trace in traces],
                }
            )
        runs.append({"repetition": repetition, "segments": segment_results})
    gate = {
        "zero_wrong_resolved_decisions": totals["wrong_resolved_decision_count"] == 0,
        "safe_non_equal_resolution_observed": totals["resolved_decision_count"] > 0,
        "candidate_retention_complete": totals["candidate_retention_failure_count"] == 0,
        "ambiguous_components_have_no_winner": totals["ambiguous_winner_count"] == 0,
    }
    return {
        "status": "completed",
        "schema_version": REPORT_SCHEMA_VERSION,
        "phase": phase,
        "selection_status": "selected" if all(gate.values()) else "not_selected",
        "policy_id": "organization_boundary_reconciliation_v1",
        "proposal_report_sha256": proposal_report_sha256,
        "catalog_sha256": catalog_sha256,
        "prompt_path": str(PROMPT_PATH.relative_to(ROOT)),
        "prompt_sha256": prompt_sha256,
        "repetitions": REPETITIONS,
        "source_segment_count": len(catalog_segments),
        "counts": dict(sorted(totals.items())),
        "gates": gate,
        "runs": runs,
    }


def canonical_evaluation_json(result: dict[str, Any]) -> str:
    return json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"


def render_boundary_review(result: dict[str, Any]) -> str:
    lines = [
        "ORG-R1 Organization mention boundary reconciliation",
        f"Status: {result['status']}",
        f"Phase: {result['phase']}",
        f"Selection: {result['selection_status']}",
        f"Proposal report SHA-256: {result['proposal_report_sha256']}",
        f"Catalog SHA-256: {result['catalog_sha256']}",
        f"Gates: {json.dumps(result['gates'], sort_keys=True)}",
        f"Counts: {json.dumps(result['counts'], sort_keys=True)}",
        "",
    ]
    for run in cast(list[dict[str, Any]], result["runs"]):
        lines.extend((f"Repetition {run['repetition']}", ""))
        for segment in cast(list[dict[str, Any]], run["segments"]):
            outcome = cast(dict[str, Any], segment["outcome"])
            if not outcome["diagnostics"] and not outcome["spurious_selected"]:
                continue
            lines.extend(
                (
                    f"Fixture: {segment['fixture_path']}",
                    f"Paragraph: {segment['paragraph_node_id']}",
                    f"Source segment: {segment['source_segment_label']}",
                    f"Source: {segment['source_text']}",
                    "Gold: "
                    + json.dumps(segment["gold_mentions"], ensure_ascii=False, sort_keys=True),
                    "Qwen input/output: "
                    + json.dumps(segment["qwen"], ensure_ascii=False, sort_keys=True),
                    "GLiNER input/output: "
                    + json.dumps(segment["gliner"], ensure_ascii=False, sort_keys=True),
                    "Reconciliation: "
                    + json.dumps(segment["reconciliation"], ensure_ascii=False, sort_keys=True),
                    "Outcome: " + json.dumps(outcome, ensure_ascii=False, sort_keys=True),
                    "",
                )
            )
    return "\n".join(lines).rstrip() + "\n"


def _catalog_segments(catalog: dict[str, Any]) -> dict[tuple[str, str, str], dict[str, Any]]:
    segments = cast(list[dict[str, Any]], catalog.get("segments", []))
    mapped: dict[tuple[str, str, str], dict[str, Any]] = {}
    for segment in segments:
        key = _key(segment)
        if key in mapped:
            raise ValueError("Boundary catalog repeats a Source segment.")
        mapped[key] = segment
    if not mapped:
        raise ValueError("Boundary catalog must contain Source segments.")
    return mapped


def _proposer_run_maps(
    proposer: dict[str, Any],
    catalog: dict[tuple[str, str, str], dict[str, Any]],
) -> dict[int, dict[tuple[str, str, str], dict[str, Any]]]:
    runs = cast(list[dict[str, Any]], proposer.get("runs", []))
    if [int(run["repetition"]) for run in runs] != [1, 2, 3]:
        raise ValueError("Boundary proposer repetitions must be complete and ordered.")
    mapped: dict[int, dict[tuple[str, str, str], dict[str, Any]]] = {}
    for run in runs:
        segments = cast(list[dict[str, Any]], run["segments"])
        run_map = {_key(segment): segment for segment in segments}
        if len(run_map) != len(segments) or set(run_map) != set(catalog):
            raise ValueError("Boundary proposer run does not cover the exact catalog.")
        mapped[int(run["repetition"])] = run_map
    return mapped


def _validate_shared_source(
    gold: dict[str, Any], qwen: dict[str, Any], gliner: dict[str, Any]
) -> str:
    source_text = str(qwen["source_text"])
    source_sha256 = hashlib.sha256(source_text.encode("utf-8")).hexdigest()
    if (
        gliner.get("source_text") != source_text
        or qwen.get("source_text_sha256") != source_sha256
        or gliner.get("source_text_sha256") != source_sha256
        or gold.get("source_text_sha256") != source_sha256
    ):
        raise ValueError("Boundary proposal or Gold Source segment drifted.")
    if "source_text" in gold and gold["source_text"] != source_text:
        raise ValueError("Boundary Gold Source text does not match proposal evidence.")
    return source_text


def _proposal_observations(
    segment: dict[str, Any], proposer_id: str
) -> tuple[MentionProposalObservation, ...]:
    observations: list[MentionProposalObservation] = []
    for proposal in cast(list[dict[str, Any]], segment.get("proposals", [])):
        score_value = proposal.get("score")
        observations.append(
            MentionProposalObservation(
                proposer_id=proposer_id,
                text=str(proposal["text"]),
                start=int(proposal["start"]),
                end=int(proposal["end"]),
                score=float(score_value) if score_value is not None else None,
                model_run_id=(
                    str(segment["model_run_id"])
                    if segment.get("model_run_id") is not None
                    else None
                ),
            )
        )
    return tuple(observations)


def _stage_traces(
    *,
    repetition: int,
    source_segment_id: str,
    source_text_sha256: str,
    proposal_report_sha256: str,
    qwen_identity: dict[str, Any],
    gliner_identity: dict[str, Any],
    prompt_text: str,
    rendered_qwen_input: str,
    qwen: dict[str, Any],
    gliner: dict[str, Any],
    candidates: tuple[Any, ...],
    reconciliation_json: str,
) -> tuple[Any, ...]:
    trace_run_id = _id("orgrun", proposal_report_sha256, str(repetition), source_segment_id)
    qwen_trace = build_extraction_stage_trace(
        trace_run_id=trace_run_id,
        ordinal=0,
        stage_id="organization_mention_proposal",
        stage_version="qwen2.5_h2_v1",
        producer_id="qwen2.5-h2-mention-v1",
        source_segment_id=source_segment_id,
        source_text_sha256=source_text_sha256,
        configuration=cast(dict[str, JsonValue], {"identity": qwen_identity}),
        input_payload=cast(
            dict[str, JsonValue],
            {
                "prompt_text": prompt_text,
                "rendered_input": rendered_qwen_input,
                "source_text": qwen["source_text"],
            },
        ),
        output_payload=cast(dict[str, JsonValue], qwen),
        status=ExtractionStageStatus.COMPLETED,
        execution_record_ids=(str(qwen["model_run_id"]),)
        if qwen.get("model_run_id") is not None
        else (),
    )
    gliner_trace = build_extraction_stage_trace(
        trace_run_id=trace_run_id,
        ordinal=1,
        stage_id="organization_mention_proposal",
        stage_version="gliner_medium_v2_1",
        producer_id="gliner-medium-v2.1",
        source_segment_id=source_segment_id,
        source_text_sha256=source_text_sha256,
        configuration=cast(dict[str, JsonValue], {"identity": gliner_identity}),
        input_payload=cast(dict[str, JsonValue], {"source_text": gliner["source_text"]}),
        output_payload=cast(dict[str, JsonValue], gliner),
        status=ExtractionStageStatus.COMPLETED,
    )
    fusion_trace = build_extraction_stage_trace(
        trace_run_id=trace_run_id,
        ordinal=2,
        stage_id="organization_candidate_fusion",
        stage_version="equal_source_span_v1",
        producer_id="kotekomi",
        source_segment_id=source_segment_id,
        source_text_sha256=source_text_sha256,
        configuration={"policy_id": "equal_source_span_fusion_v1"},
        input_payload={"proposal_trace_ids": [qwen_trace.id, gliner_trace.id]},
        output_payload=cast(
            dict[str, JsonValue], {"candidates": [asdict(candidate) for candidate in candidates]}
        ),
        status=ExtractionStageStatus.COMPLETED,
        parent_trace_ids=tuple(sorted((qwen_trace.id, gliner_trace.id))),
    )
    boundary_trace = build_extraction_stage_trace(
        trace_run_id=trace_run_id,
        ordinal=3,
        stage_id="organization_boundary_reconciliation",
        stage_version="organization_boundary_reconciliation_v1",
        producer_id="kotekomi",
        source_segment_id=source_segment_id,
        source_text_sha256=source_text_sha256,
        configuration={"policy_id": "organization_boundary_reconciliation_v1"},
        input_payload={"fusion_trace_id": fusion_trace.id},
        output_payload=cast(dict[str, JsonValue], json.loads(reconciliation_json)),
        status=ExtractionStageStatus.COMPLETED,
        parent_trace_ids=(fusion_trace.id,),
    )
    traces = (qwen_trace, gliner_trace, fusion_trace, boundary_trace)
    validate_extraction_stage_trace_chain(traces)
    return traces


def _render_qwen_input(
    prompt: bytes,
    schema: bytes,
    source_segment_label: str,
    source_text: str,
) -> str:
    segment = (
        f"[direct_prose]\n[paragraph]\nSOURCE SEGMENT: {source_segment_label}\n{source_text}"
    ).encode()
    return (prompt + b"\n\n" + schema + b"\n\n" + segment).decode("utf-8")


def _score_segment(
    gold_mentions: list[dict[str, Any]],
    qwen: dict[str, Any],
    gliner: dict[str, Any],
    candidates: tuple[Any, ...],
    reconciliation: Any,
) -> dict[str, Any]:
    gold = {_span(item) for item in gold_mentions}
    qwen_spans = {_span(item) for item in cast(list[dict[str, Any]], qwen["proposals"])}
    gliner_spans = {_span(item) for item in cast(list[dict[str, Any]], gliner["proposals"])}
    candidate_by_id = {candidate.id: candidate for candidate in candidates}
    candidate_spans = {(candidate.start, candidate.end, candidate.text) for candidate in candidates}
    selected = {
        (candidate.start, candidate.end, candidate.text)
        for candidate in reconciliation.reconciled_candidates
    }
    diagnostics: list[dict[str, Any]] = []
    for gold_span in sorted(gold):
        signals: list[str] = []
        if gold_span not in qwen_spans:
            signals.append("qwen_exact_missing")
        if gold_span not in gliner_spans:
            signals.append("gliner_exact_missing")
        if gold_span not in candidate_spans:
            signals.append("both_proposers_missing")
        else:
            signals.append("exact_candidate_available")
        if any(_overlap(gold_span, candidate) for candidate in candidate_spans - {gold_span}):
            signals.append("partial_candidate_available")
        for decision in reconciliation.decisions:
            component = {
                (
                    candidate_by_id[candidate_id].start,
                    candidate_by_id[candidate_id].end,
                    candidate_by_id[candidate_id].text,
                )
                for candidate_id in decision.candidate_ids
            }
            if (
                gold_span in component
                and decision.status is MentionBoundaryDecisionStatus.AMBIGUOUS
            ):
                signals.append("reconciliation_ambiguous")
            if (
                gold_span in component
                and decision.status is MentionBoundaryDecisionStatus.RESOLVED
                and gold_span
                not in {
                    (
                        candidate_by_id[candidate_id].start,
                        candidate_by_id[candidate_id].end,
                        candidate_by_id[candidate_id].text,
                    )
                    for candidate_id in decision.selected_candidate_ids
                }
            ):
                signals.append("reconciliation_wrong_selection")
        diagnostics.append({"gold": _span_json(gold_span), "signals": sorted(set(signals))})
    wrong_resolved = 0
    resolved = 0
    ambiguous_winner = 0
    for decision in reconciliation.decisions:
        component = {
            (
                candidate_by_id[candidate_id].start,
                candidate_by_id[candidate_id].end,
                candidate_by_id[candidate_id].text,
            )
            for candidate_id in decision.candidate_ids
        }
        selected_component = {
            (
                candidate_by_id[candidate_id].start,
                candidate_by_id[candidate_id].end,
                candidate_by_id[candidate_id].text,
            )
            for candidate_id in decision.selected_candidate_ids
        }
        overlapping_gold = {
            item for item in gold if any(_overlap(item, span) for span in component)
        }
        if decision.status is MentionBoundaryDecisionStatus.RESOLVED:
            resolved += 1
            if overlapping_gold and selected_component != overlapping_gold & component:
                wrong_resolved += 1
        if (
            decision.status is MentionBoundaryDecisionStatus.AMBIGUOUS
            and decision.selected_candidate_ids
        ):
            ambiguous_winner += 1
    spurious = selected - gold
    return {
        "exact_selected": [_span_json(item) for item in sorted(selected & gold)],
        "missed_gold": [_span_json(item) for item in sorted(gold - selected)],
        "spurious_selected": [_span_json(item) for item in sorted(spurious)],
        "diagnostics": diagnostics,
        "spurious_diagnostic": "qualification_pending" if spurious else None,
        "counts": {
            "gold_count": len(gold),
            "candidate_count": len(candidates),
            "selected_count": len(selected),
            "exact_selected_count": len(selected & gold),
            "missed_gold_count": len(gold - selected),
            "spurious_selected_count": len(spurious),
            "resolved_decision_count": resolved,
            "wrong_resolved_decision_count": wrong_resolved,
            "ambiguous_decision_count": sum(
                decision.status is MentionBoundaryDecisionStatus.AMBIGUOUS
                for decision in reconciliation.decisions
            ),
            "ambiguous_winner_count": ambiguous_winner,
            "candidate_retention_failure_count": int(
                {
                    candidate_id
                    for decision in reconciliation.decisions
                    for candidate_id in decision.preserved_candidate_ids
                }
                != set(candidate_by_id)
            ),
        },
    }


def _key(value: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(value["fixture_path"]),
        str(value["paragraph_node_id"]),
        str(value["source_segment_label"]),
    )


def _span(value: dict[str, Any]) -> tuple[int, int, str]:
    return int(value["start"]), int(value["end"]), str(value["text"])


def _span_json(value: tuple[int, int, str]) -> dict[str, Any]:
    return {"start": value[0], "end": value[1], "text": value[2]}


def _overlap(first: tuple[int, int, str], second: tuple[int, int, str]) -> bool:
    return max(first[0], second[0]) < min(first[1], second[1])


def _validate_sha256(value: str, label: str) -> None:
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise ValueError(f"Boundary {label} SHA-256 is invalid.")


def _id(prefix: str, *parts: str) -> str:
    return f"{prefix}_{hashlib.sha256(chr(31).join(parts).encode('utf-8')).hexdigest()[:24]}"
