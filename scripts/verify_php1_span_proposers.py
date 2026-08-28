"""Run the PHP-1 H2.1 Qwen2.5 and GLiNER exact-span comparison."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
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
from kotekomi_application import (
    OrganizationMentionProposalInput,
    propose_validated_organization_mentions,
)
from php1_diagnostic_support import (
    MODEL_ELIGIBLE,
    ROOT,
    load_packet_source_segments,
    run_qwen_mentions_for_packet,
)
from php1_span_proposer_evaluation import (
    HUMAN_REVIEWED_STATUS,
    REPETITIONS,
    attach_authoritative_proposal_ranges,
    load_and_validate_catalog,
    load_and_validate_mention_policy,
    normalize_qwen_segment,
    proposer_report,
    render_review_report,
)
from verify_php1_packet import packet_cases

CATALOG_PATH = ROOT / "docs/php1-organization-mention-gold-v1.json"
POLICY_PATH = ROOT / "docs/php1-named-organization-mention-policy-v1.json"


def _progress(event: dict[str, Any]) -> None:
    print(json.dumps(event, sort_keys=True), file=sys.stderr, flush=True)


def run(config_path: Path | None = None) -> dict[str, Any]:
    cases = packet_cases()
    _progress({"event": "source_segments_started", "case_count": len(cases)})
    source_result = load_packet_source_segments(cases)
    if source_result["status"] != "completed":
        return source_result
    policy = load_and_validate_mention_policy(POLICY_PATH)
    catalog = load_and_validate_catalog(CATALOG_PATH, source_result)
    source_segments = cast(list[dict[str, Any]], source_result["segments"])
    _progress({"event": "catalog_validated", "source_segment_count": len(source_segments)})

    try:
        gliner = GlinerOrganizationMentionProposer()
    except Exception as exc:
        return {"status": "gliner_unavailable", "diagnostics": [str(exc)]}
    first_source = str(source_segments[0]["source_text"])
    propose_validated_organization_mentions(
        OrganizationMentionProposalInput(first_source),
        gliner,
    )
    gliner_runs: list[dict[str, Any]] = []
    for repetition in range(1, REPETITIONS + 1):
        _progress({"event": "gliner_run_started", "repetition": repetition})
        results: list[dict[str, Any]] = []
        for segment in source_segments:
            source_text = str(segment["source_text"])
            if segment["model_eligibility"] == MODEL_ELIGIBLE:
                batch = propose_validated_organization_mentions(
                    OrganizationMentionProposalInput(source_text),
                    gliner,
                )
                proposals = attach_authoritative_proposal_ranges(
                    [
                        {
                            "text": item.text,
                            "start": item.start,
                            "end": item.end,
                            "score": item.score,
                        }
                        for item in batch.proposals
                    ],
                    segment,
                )
                latency_milliseconds = batch.inference_elapsed_milliseconds
                status = "complete"
            else:
                proposals = []
                latency_milliseconds = None
                status = str(segment["model_eligibility"])
            results.append(
                {
                    "fixture_path": segment["fixture_path"],
                    "paragraph_node_id": segment["paragraph_node_id"],
                    "source_segment_label": segment["source_segment_label"],
                    "source_text_sha256": segment["source_text_sha256"],
                    "source_text": source_text,
                    "status": status,
                    "model_eligibility": segment["model_eligibility"],
                    "latency_milliseconds": latency_milliseconds,
                    "proposals": proposals,
                }
            )
        gliner_runs.append({"repetition": repetition, "segments": results})
        _progress({"event": "gliner_run_completed", "repetition": repetition})

    _progress({"event": "qwen_runs_started", "repetitions": REPETITIONS})
    qwen_result = run_qwen_mentions_for_packet(config_path, cases, repetitions=REPETITIONS)
    if qwen_result["status"] != "completed":
        return qwen_result
    source_by_key = {
        (
            str(segment["fixture_path"]),
            str(segment["source_text_sha256"]),
            str(segment["source_segment_label"]),
        ): segment
        for segment in source_segments
    }
    qwen_runs = [
        {
            "repetition": int(run_value["repetition"]),
            "segments": [
                normalize_qwen_segment(
                    {
                        **segment,
                        **source_by_key[
                            (
                                str(segment["fixture_path"]),
                                str(segment["source_text_sha256"]),
                                str(segment["source_segment_label"]),
                            )
                        ],
                    }
                )
                for segment in cast(list[dict[str, Any]], run_value["segments"])
            ],
        }
        for run_value in cast(list[dict[str, Any]], qwen_result["runs"])
    ]
    gliner_identity = {
        "package": "gliner",
        "package_version": GLINER_PACKAGE_VERSION,
        "model_id": GLINER_MODEL_ID,
        "model_revision": GLINER_MODEL_REVISION,
        "label": GLINER_LABEL,
        "threshold": GLINER_THRESHOLD,
        "device": GLINER_DEVICE,
        "quantized": False,
    }
    result = {
        "status": "completed",
        "schema_version": "php1_span_proposer_comparison_v1",
        "annotation_policy_id": policy["policy_id"],
        "annotation_policy_sha256": hashlib.sha256(POLICY_PATH.read_bytes()).hexdigest(),
        "annotation_status": HUMAN_REVIEWED_STATUS,
        "catalog_path": str(CATALOG_PATH.relative_to(ROOT)),
        "catalog_sha256": hashlib.sha256(CATALOG_PATH.read_bytes()).hexdigest(),
        "catalog": list(catalog),
        "gold_mention_count": sum(len(item["gold_mentions"]) for item in catalog),
        "source_segment_count": len(source_segments),
        "case_count": len(cases),
        "repetitions": REPETITIONS,
        "representations": {
            path: next(
                str(item["representation_id"])
                for item in source_segments
                if item["fixture_path"] == path
            )
            for path in sorted({str(item["fixture_path"]) for item in source_segments})
        },
        "proposers": [
            proposer_report(
                "qwen2.5-h2-mention-v1",
                cast(dict[str, Any], qwen_result["model_identity"]),
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
    _progress({"event": "comparison_completed", "status": result["status"]})
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--review-report", type=Path, required=True)
    arguments = parser.parse_args()
    result = run(arguments.config)
    arguments.output.write_text(
        json.dumps(result, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if result["status"] == "completed":
        arguments.review_report.write_text(
            render_review_report(
                result,
                tuple(cast(list[dict[str, Any]], result["catalog"])),
            ),
            encoding="utf-8",
        )
    print(
        json.dumps(
            {
                "status": result["status"],
                "output": str(arguments.output),
                "review_report": str(arguments.review_report),
            },
            sort_keys=True,
        )
    )
    if result["status"] != "completed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
