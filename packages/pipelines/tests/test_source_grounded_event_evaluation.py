from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from kotekomi_application import (
    SourceGroundedEventDraft,
    build_source_grounded_event_draft,
    derive_source_copy_view,
)
from kotekomi_application.hybrid_event_triggers import EventTriggerDraft, event_trigger_id
from kotekomi_application.source_occurrences import source_occurrences
from kotekomi_domain import EvidenceTarget
from kotekomi_pipelines.event_trigger_stage_local import TriggerGoldEvent, TriggerGoldSegment
from kotekomi_pipelines.source_grounded_event_evaluation import (
    SourceGroundedEventSegmentEvaluation,
    build_source_grounded_event_evaluation_report,
    evaluate_source_grounded_event_segment,
    load_source_grounded_event_gold,
)

ROOT = Path(__file__).resolve().parents[3]
GOLD = ROOT / "docs" / "hsq-source-grounded-event-gold-v1.json"
NOW = datetime(2026, 9, 12, tzinfo=UTC)


def test_source_grounded_gold_covers_trigger_gold_and_preserves_review_partition() -> None:
    catalog, trigger_gold = load_source_grounded_event_gold(
        GOLD,
        repository_root=ROOT,
    )

    assert len(catalog.items) == sum(len(item.events) for item in trigger_gold.segments) == 87
    assert {item.phase for item in catalog.items} == {"development", "validation"}
    rejected = [item for item in catalog.items if item.expected_review_outcome == "rejected"]
    assert [item.event_id for item in rejected] == ["TGE-010", "TGE-020", "TGE-033"]
    assert "anticipated temporal reference" in rejected[0].rationale
    assert "embedded under Amodei's decision" in rejected[1].rationale
    assert "compound modifier" in rejected[2].rationale
    motion = next(
        event
        for segment in trigger_gold.segments
        for event in segment.events
        if event.event_id == "TGE-086"
    )
    assert {
        (item.start_occurrence_id, item.end_occurrence_id)
        for item in motion.accepted_expression_ranges
    } == {("o20", "o20"), ("o20", "o25")}


def test_source_grounded_gold_rejects_parent_digest_drift(tmp_path: Path) -> None:
    value = json.loads(GOLD.read_bytes())
    value["trigger_gold_sha256"] = "0" * 64
    changed = tmp_path / "changed.json"
    changed.write_text(json.dumps(value), encoding="utf-8")

    with pytest.raises(ValueError, match="parent digest drifted"):
        load_source_grounded_event_gold(changed, repository_root=ROOT)


def test_source_grounded_evaluation_checks_exact_name_and_all_evidence() -> None:
    catalog, trigger_gold = load_source_grounded_event_gold(
        GOLD,
        repository_root=ROOT,
    )
    segment = trigger_gold.segments[0]
    trigger, source_event, evidence = _grounded_fixture(segment)
    review_items = {item.event_id: item for item in catalog.items}

    result = evaluate_source_grounded_event_segment(
        gold_segment=segment,
        review_items=review_items,
        triggers=(trigger,),
        source_events=(source_event,),
        evidence_by_id=evidence,
    )

    assert result.passed is True
    assert result.grounded_event_ids == (segment.events[0].event_id,)
    assert result.missing_event_ids == ()
    assert result.extra_source_grounded_event_ids == ()
    assert result.incorrectly_grounded_event_ids == ()

    invalid_evidence = dict(evidence)
    head_id = source_event.mention.head_evidence_target_id
    invalid_evidence[head_id] = invalid_evidence[head_id].model_copy(
        update={"document_id": "doc_other"}
    )
    invalid = evaluate_source_grounded_event_segment(
        gold_segment=segment,
        review_items=review_items,
        triggers=(trigger,),
        source_events=(source_event,),
        evidence_by_id=invalid_evidence,
    )

    assert invalid.passed is False
    assert invalid.incorrectly_grounded_event_ids == (segment.events[0].event_id,)


def test_source_grounded_evaluation_accounts_for_duplicate_observed_events() -> None:
    catalog, trigger_gold = load_source_grounded_event_gold(
        GOLD,
        repository_root=ROOT,
    )
    segment = trigger_gold.segments[0]
    trigger, source_event, evidence = _grounded_fixture(segment)
    duplicate = build_source_grounded_event_draft(
        event_subject_id="esd_" + "5" * 24,
        trigger_id=trigger.id,
        source_segment_id=trigger.source_segment_id,
        source_text_sha256=trigger.source_text_sha256,
        expression_text=trigger.text,
        head_text=trigger.head_text,
        head_evidence_target_id=source_event.mention.head_evidence_target_id,
        expression_evidence_target_id=source_event.mention.expression_evidence_target_id,
        support_evidence_target_id=source_event.mention.support_evidence_target_id,
    )

    result = evaluate_source_grounded_event_segment(
        gold_segment=segment,
        review_items={item.event_id: item for item in catalog.items},
        triggers=(trigger,),
        source_events=(source_event, duplicate),
        evidence_by_id=evidence,
    )

    assert result.passed is False
    assert result.observed_event_count == 2
    assert result.grounded_event_ids == (segment.events[0].event_id,)
    assert result.extra_source_grounded_event_ids == (max(source_event.id, duplicate.id),)


def test_source_grounded_report_preserves_both_gold_partitions() -> None:
    catalog, trigger_gold = load_source_grounded_event_gold(
        GOLD,
        repository_root=ROOT,
    )
    review_items = {item.event_id: item for item in catalog.items}
    evaluations: list[SourceGroundedEventSegmentEvaluation] = []
    for segment in trigger_gold.segments:
        grounded = tuple(_grounded_fixture_for_event(segment, item) for item in segment.events)
        evaluations.append(
            evaluate_source_grounded_event_segment(
                gold_segment=segment,
                review_items=review_items,
                triggers=tuple(item[0] for item in grounded),
                source_events=tuple(item[1] for item in grounded),
                evidence_by_id={
                    target_id: target
                    for _, _, evidence in grounded
                    for target_id, target in evidence.items()
                },
            )
        )

    report = build_source_grounded_event_evaluation_report(
        catalog=catalog,
        trigger_gold=trigger_gold,
        catalog_sha256=hashlib.sha256(GOLD.read_bytes()).hexdigest(),
        coverage_report_id="hdc_" + "1" * 24,
        coverage_report_sha256="2" * 64,
        representation_id="rep_fixture",
        segments=tuple(evaluations),
    )

    assert report.passed is True
    assert report.segment_count == 26
    assert report.expected_event_count == report.observed_event_count == 87
    assert report.grounded_event_count == 87
    assert report.coverage_report_id == "hdc_" + "1" * 24
    assert report.coverage_report_sha256 == "2" * 64
    assert report.approved_review_event_count == 84
    assert report.rejected_review_event_count == 3
    assert [item.phase for item in report.phase_evaluations] == [
        "development",
        "validation",
    ]


def test_gold_result_requires_one_observed_authoritative_segment() -> None:
    catalog, trigger_gold = load_source_grounded_event_gold(
        GOLD,
        repository_root=ROOT,
    )
    segment = trigger_gold.segments[0]
    grounded = tuple(_grounded_fixture_for_event(segment, item) for item in segment.events)

    result = evaluate_source_grounded_event_segment(
        gold_segment=segment,
        review_items={item.event_id: item for item in catalog.items},
        triggers=tuple(item[0] for item in grounded),
        source_events=tuple(item[1] for item in grounded),
        evidence_by_id={
            target_id: target
            for _, _, evidence in grounded
            for target_id, target in evidence.items()
        },
        source_segment_observation_count=0,
    )

    assert result.expected_event_count == result.observed_event_count == len(segment.events)
    assert result.missing_event_ids == ()
    assert result.passed is False


def _grounded_fixture(
    segment: TriggerGoldSegment,
) -> tuple[EventTriggerDraft, SourceGroundedEventDraft, dict[str, EvidenceTarget]]:
    return _grounded_fixture_for_event(segment, segment.events[0])


def _grounded_fixture_for_event(
    segment: TriggerGoldSegment,
    expected: TriggerGoldEvent,
) -> tuple[EventTriggerDraft, SourceGroundedEventDraft, dict[str, EvidenceTarget]]:
    source_copy = derive_source_copy_view(segment.source_text)
    occurrences = {item.occurrence_id: item for item in source_occurrences(source_copy.text)}
    expression_range = expected.accepted_expression_ranges[0]
    start, end = source_copy.authoritative_range(
        occurrences[expression_range.start_occurrence_id].start,
        occurrences[expression_range.end_occurrence_id].end,
    )
    head_start, head_end = source_copy.authoritative_range(
        occurrences[expected.head_occurrence_id].start,
        occurrences[expected.head_occurrence_id].end,
    )
    expression = segment.source_text[start:end]
    head = segment.source_text[head_start:head_end]
    trigger_id = event_trigger_id(
        source_segment_id="seg_fixture",
        source_text_sha256=segment.source_text_sha256,
        start=start,
        end=end,
        text=expression,
        head_start=head_start,
        head_end=head_end,
        head_text=head,
        event_type_label="source_expression",
        extraction_task_id="ext_fixture",
        model_run_id="mrn_fixture",
        trace_id="xst_" + "a" * 24,
    )
    trigger = EventTriggerDraft(
        id=trigger_id,
        source_segment_id="seg_fixture",
        source_text_sha256=segment.source_text_sha256,
        start=start,
        end=end,
        text=expression,
        head_start=head_start,
        head_end=head_end,
        head_text=head,
        event_type_label="source_expression",
        extraction_task_id="ext_fixture",
        model_run_id="mrn_fixture",
        trace_id="xst_" + "a" * 24,
    )
    offset = 100
    support = _evidence(
        _fixture_id("etg", segment.source_text_sha256, "support"),
        offset,
        segment.source_text,
    )
    expression_target = _evidence(
        _fixture_id("etg", expected.event_id, "expression"),
        offset + start,
        expression,
    )
    head_target = _evidence(
        _fixture_id("etg", expected.event_id, "head"),
        offset + head_start,
        head,
    )
    source_event = build_source_grounded_event_draft(
        event_subject_id=_fixture_id("esd", expected.event_id),
        trigger_id=trigger.id,
        source_segment_id=trigger.source_segment_id,
        source_text_sha256=trigger.source_text_sha256,
        expression_text=trigger.text,
        head_text=trigger.head_text,
        head_evidence_target_id=head_target.id,
        expression_evidence_target_id=expression_target.id,
        support_evidence_target_id=support.id,
    )
    return (
        trigger,
        source_event,
        {item.id: item for item in (support, expression_target, head_target)},
    )


def _evidence(identifier: str, start: int, text: str) -> EvidenceTarget:
    return EvidenceTarget(
        id=identifier,
        source_id="src_fixture",
        document_id="doc_fixture",
        representation_id="rep_fixture",
        text_view_id="tvw_fixture",
        text_view_digest=hashlib.sha256(b"fixture TextView").hexdigest(),
        start_char=start,
        end_char=start + len(text),
        exact_text=text,
        normalization_policy="utf8_identity_v1",
        node_ids=("nod_fixture",),
        created_at=NOW,
    )


def _fixture_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("\x1f".join(parts).encode()).hexdigest()
    return f"{prefix}_{digest[:24]}"
