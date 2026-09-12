#!/usr/bin/env python3
"""Verify source-grounded Events from one pinned document coverage report."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from kotekomi_adapters import LocalArchiveStore, sqlite_ledger_transaction
from kotekomi_application import (
    PARAGRAPH_SEGMENT_V3,
    HybridStageId,
    SourceGroundedEventDraft,
    hybrid_document_coverage_report_from_bytes,
    hybrid_paragraph_receipt_from_bytes,
    load_hybrid_event_semantics_preview,
    load_hybrid_event_trigger_preview,
    paragraph_source_segments,
)
from kotekomi_application.hybrid_event_triggers import EventTriggerDraft
from kotekomi_domain import EvidenceTarget
from kotekomi_pipelines.config import load_config
from kotekomi_pipelines.source_grounded_event_evaluation import (
    evaluate_source_grounded_event_corpus,
    load_source_grounded_event_gold,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GOLD = REPOSITORY_ROOT / "docs" / "hsq-source-grounded-event-gold-v1.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--coverage-report-id", required=True)
    parser.add_argument("--gold", type=Path, default=DEFAULT_GOLD)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    config = load_config(
        config_path=args.config,
        ledger_path_override=None,
        archive_path_override=None,
    )
    archive = LocalArchiveStore(config.archive_path)
    coverage_payload = archive.read_hybrid_document_coverage_report(args.coverage_report_id)
    coverage = hybrid_document_coverage_report_from_bytes(coverage_payload)
    gold_path = args.gold.resolve()
    catalog, trigger_gold = load_source_grounded_event_gold(
        gold_path,
        repository_root=REPOSITORY_ROOT,
    )

    segment_counts: Counter[str] = Counter()
    triggers_by_digest: dict[str, dict[str, EventTriggerDraft]] = {}
    events_by_digest: dict[str, dict[str, SourceGroundedEventDraft]] = {}
    evidence_by_id: dict[str, EvidenceTarget] = {}
    with sqlite_ledger_transaction(config.ledger_path) as ledger:
        bundle = ledger.get_document_representation_bundle(coverage.representation_id)
        if bundle is None:
            raise ValueError("Coverage report references a missing representation.")
        node_by_id = {item.id: item for item in bundle.nodes}
        text_view_by_id = {item.id: item for item in bundle.text_views}
        for coverage_record in coverage.records:
            receipt_payload = archive.read_hybrid_paragraph_receipt(coverage_record.receipt_id)
            if hashlib.sha256(receipt_payload).hexdigest() != coverage_record.receipt_sha256:
                raise ValueError("Coverage report references a changed paragraph receipt.")
            receipt = hybrid_paragraph_receipt_from_bytes(receipt_payload)
            stage = next(
                item
                for item in receipt.stages
                if item.stage_id is HybridStageId.HP6_EVENT_SEMANTICS
            )
            if stage.output_id is None:
                continue
            preview_payload = archive.read_hybrid_event_semantics_preview(stage.output_id)
            if hashlib.sha256(preview_payload).hexdigest() != stage.output_sha256:
                raise ValueError("Paragraph receipt references changed Event evidence.")
            preview = load_hybrid_event_semantics_preview(stage.output_id, ledger, archive)
            if (
                preview.representation_id != coverage.representation_id
                or preview.paragraph_node_id != coverage_record.paragraph_node_id
            ):
                raise ValueError("Event Preview does not belong to its paragraph receipt.")
            parent = load_hybrid_event_trigger_preview(preview.parent_preview_id, archive)
            node = node_by_id[preview.paragraph_node_id]
            text_view = text_view_by_id[node.text_view_id]
            paragraph_text = text_view.text[node.start_char : node.end_char]
            for segment in paragraph_source_segments(paragraph_text, PARAGRAPH_SEGMENT_V3):
                segment_counts[hashlib.sha256(segment.exact_text.encode()).hexdigest()] += 1
            for trigger in parent.triggers:
                _add_exact(
                    triggers_by_digest.setdefault(trigger.source_text_sha256, {}),
                    trigger.id,
                    trigger,
                )
            for source_event in preview.source_grounded_events:
                _add_exact(
                    events_by_digest.setdefault(source_event.source_text_sha256, {}),
                    source_event.id,
                    source_event,
                )
                for target_id in (
                    source_event.mention.head_evidence_target_id,
                    source_event.mention.expression_evidence_target_id,
                    source_event.mention.support_evidence_target_id,
                ):
                    target = ledger.get_evidence_target(target_id)
                    if target is None:
                        raise ValueError("Source-grounded Event evidence is missing.")
                    _add_exact(evidence_by_id, target.id, target)

    report = evaluate_source_grounded_event_corpus(
        catalog=catalog,
        trigger_gold=trigger_gold,
        catalog_sha256=hashlib.sha256(gold_path.read_bytes()).hexdigest(),
        coverage_report_id=coverage.id,
        coverage_report_sha256=hashlib.sha256(coverage_payload).hexdigest(),
        representation_id=coverage.representation_id,
        source_segment_observation_counts=segment_counts,
        triggers_by_source_text_sha256={
            digest: tuple(sorted(items.values(), key=lambda item: item.id))
            for digest, items in triggers_by_digest.items()
        },
        source_events_by_source_text_sha256={
            digest: tuple(sorted(items.values(), key=lambda item: item.id))
            for digest, items in events_by_digest.items()
        },
        evidence_by_id=evidence_by_id,
    )
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            report.model_dump(mode="json"),
            allow_nan=False,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "expected_event_count": report.expected_event_count,
                "grounded_event_count": report.grounded_event_count,
                "incorrectly_grounded_event_count": report.incorrectly_grounded_event_count,
                "missing_event_count": report.missing_event_count,
                "extra_event_count": report.extra_event_count,
                "passed": report.passed,
                "report": str(output),
            },
            sort_keys=True,
        )
    )
    return 0 if report.passed else 1


def _add_exact[T](records: dict[str, T], record_id: str, record: T) -> None:
    existing = records.get(record_id)
    if existing is not None and existing != record:
        raise ValueError(f"Conflicting immutable record: {record_id}")
    records[record_id] = record


if __name__ == "__main__":
    raise SystemExit(main())
