from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from kotekomi_application import (
    EntityInvolvementAnswerValue,
    EventEntityCandidateSelection,
    EventEntityConnectionPreview,
    EventEntityConnectionPreviewStatus,
    EventEntityKind,
    EventEntityMentionInput,
    EventEntitySourceSpan,
    build_entity_involvement_judgment,
    build_event_entity_connection_candidates,
    build_event_entity_connection_preview,
    build_extraction_stage_trace,
    build_source_grounded_event_draft,
    decide_event_entity_connection,
)
from kotekomi_application.extraction_stage_trace import ExtractionStageStatus
from kotekomi_pipelines.event_entity_connection_stage_local import (
    ConnectionGoldEntity,
    ConnectionGoldEvent,
    ConnectionGoldExcludedExpression,
    EventEntityCaseEvaluation,
    EventEntityExperimentInput,
    build_event_entity_phase_report,
    evaluate_event_entity_candidate_availability,
    evaluate_event_entity_case,
    event_entity_preparation_status,
    load_connection_gold_catalog,
    render_connection_gold_review,
)

ROOT = Path(__file__).resolve().parents[3]
GOLD = ROOT / "docs" / "hsq-event-entity-connection-gold-v1.json"


def test_connection_gold_binds_approved_events_and_rejects_unapproved_catalog(
    tmp_path: Path,
) -> None:
    catalog, grounded, triggers = load_connection_gold_catalog(
        GOLD,
        repository_root=ROOT,
        require_approved=False,
    )

    assert catalog.review_status == "approved"
    assert sum(item.phase == "development" for item in catalog.events) == 20
    assert sum(item.phase == "validation" for item in catalog.events) == 20
    assert len(
        {item.entity_id for event in catalog.events for item in event.expected_entities}
    ) == sum(len(event.expected_entities) for event in catalog.events)
    assert {
        item.exclusion_id
        for event in catalog.events
        for item in event.excluded_actor_organization_expressions
    } == {"EGX-001", "EGX-002"}
    assert "TGE-010" not in {item.event_id for item in catalog.events}
    assert "TGE-020" not in {item.event_id for item in catalog.events}
    assert "TGE-054" in {item.event_id for item in catalog.events}
    assert "TGE-060" in {item.event_id for item in catalog.events}
    assert {item.event_id for item in catalog.events}.issubset(
        {item.event_id for item in grounded.items if item.expected_review_outcome == "approved"}
    )
    assert {item.event_id for item in catalog.events}.issubset(
        {item.event_id for segment in triggers.segments for item in segment.events}
    )
    approved_catalog, _, _ = load_connection_gold_catalog(
        GOLD,
        repository_root=ROOT,
        require_approved=True,
    )
    assert approved_catalog.review_status == "approved"

    unapproved = catalog.model_dump(mode="json")
    unapproved["review_status"] = "proposed"
    unapproved_path = tmp_path / "unapproved.json"
    unapproved_path.write_text(json.dumps(unapproved), encoding="utf-8")
    with pytest.raises(ValueError, match="human approval"):
        load_connection_gold_catalog(
            unapproved_path,
            repository_root=ROOT,
            require_approved=True,
        )


def test_connection_gold_rejects_parent_digest_drift(tmp_path: Path) -> None:
    value = json.loads(GOLD.read_bytes())
    value["source_grounded_gold_sha256"] = "0" * 64
    changed = tmp_path / "changed.json"
    changed.write_text(json.dumps(value), encoding="utf-8")

    with pytest.raises(ValueError, match="source-grounded Gold digest drifted"):
        load_connection_gold_catalog(
            changed,
            repository_root=ROOT,
            require_approved=False,
        )


def test_connection_gold_rejects_an_unobserved_accepted_source_expression(
    tmp_path: Path,
) -> None:
    value = json.loads(GOLD.read_bytes())
    value["events"][0]["expected_entities"][0]["accepted_source_texts"].append(
        "name absent from the exact SourceSegment"
    )
    changed = tmp_path / "changed.json"
    changed.write_text(json.dumps(value), encoding="utf-8")

    with pytest.raises(ValueError, match="accepted source expression is absent"):
        load_connection_gold_catalog(
            changed,
            repository_root=ROOT,
            require_approved=False,
        )


def test_connection_gold_review_contains_exact_source_and_every_expected_entity() -> None:
    catalog, _, triggers = load_connection_gold_catalog(
        GOLD,
        repository_root=ROOT,
        require_approved=False,
    )

    rendered = render_connection_gold_review(catalog, triggers)

    assert (
        "Accepted source expressions must exist byte-for-byte in the Event's exact SourceSegment."
        in rendered
    )
    assert all(item.event_meaning in rendered for item in catalog.events)
    assert all(
        item.canonical_name in rendered
        for event in catalog.events
        for item in event.expected_entities
    )
    assert rendered.count("Event review: `approved`") == 40
    assert "EGX-001 — not Actor/Organization — event" in rendered


def test_connection_evaluator_requires_the_exact_complete_entity_inventory() -> None:
    gold, prepared, connected = _fixture_result(EntityInvolvementAnswerValue.YES)

    passed = evaluate_event_entity_case(gold, prepared, connected)

    assert passed.passed is True
    assert passed.candidate_available_entity_ids == ("EGE-900",)
    assert passed.candidate_missing_entity_ids == ()
    assert passed.matched_entity_ids == ("EGE-900",)
    assert passed.missing_entity_ids == ()
    assert passed.extra_draft_ids == ()
    assert passed.model_execution_count == 1

    _, _, rejected = _fixture_result(EntityInvolvementAnswerValue.NO)
    failed = evaluate_event_entity_case(gold, prepared, rejected)

    assert failed.passed is False
    assert failed.missing_entity_ids == ("EGE-900",)
    assert failed.false_negative_entity_ids == ("EGE-900",)
    assert failed.semantic_result == ()


def test_candidate_preflight_attributes_missing_gold_entities_to_upstream() -> None:
    gold, prepared, _ = _fixture_result(EntityInvolvementAnswerValue.YES)

    ready = evaluate_event_entity_candidate_availability(gold, prepared)

    assert ready.passed is True
    assert ready.available_entity_ids == ("EGE-900",)
    assert ready.missing_entity_ids == ()
    assert ready.candidate_count == 1
    assert "organization:Anthropic" in ready.candidate_inventory[0]

    missing_gold = gold.model_copy(
        update={
            "expected_entities": (
                *gold.expected_entities,
                ConnectionGoldEntity(
                    entity_id="EGE-901",
                    entity_kind=EventEntityKind.ORGANIZATION,
                    canonical_name="Stargate",
                    accepted_entity_names=("Stargate",),
                    accepted_source_texts=("Stargate",),
                    rationale="Stargate is the object of the criticism.",
                ),
            )
        }
    )

    blocked = evaluate_event_entity_candidate_availability(missing_gold, prepared)

    assert blocked.passed is False
    assert blocked.available_entity_ids == ("EGE-900",)
    assert blocked.missing_entity_ids == ("EGE-901",)

    exclusion_gold = gold.model_copy(
        update={
            "expected_entities": (),
            "excluded_actor_organization_expressions": (
                ConnectionGoldExcludedExpression(
                    exclusion_id="EGX-900",
                    source_text="Anthropic",
                    contextual_kind="event",
                    rationale="Synthetic contextual exclusion.",
                ),
            ),
        }
    )

    violated = evaluate_event_entity_candidate_availability(exclusion_gold, prepared)

    assert violated.passed is False
    assert violated.excluded_expression_ids == ("EGX-900",)
    assert violated.violated_exclusion_ids == ("EGX-900",)


def test_preparation_status_blocks_model_work_until_both_gates_pass() -> None:
    assert (
        event_entity_preparation_status(
            gold_review_status="proposed",
            preflight_passed=True,
        )
        == "gold_review_required"
    )
    assert (
        event_entity_preparation_status(
            gold_review_status="approved",
            preflight_passed=False,
        )
        == "upstream_blocked"
    )
    assert (
        event_entity_preparation_status(
            gold_review_status="approved",
            preflight_passed=True,
        )
        == "prepared"
    )


def test_phase_report_is_exact_stable_and_records_no_canonical_writes() -> None:
    catalog, _, _ = load_connection_gold_catalog(
        GOLD,
        repository_root=ROOT,
        require_approved=False,
    )
    evaluations = tuple(
        EventEntityCaseEvaluation(
            event_id=event.event_id,
            expected_entity_ids=tuple(item.entity_id for item in event.expected_entities),
            excluded_expression_ids=tuple(
                item.exclusion_id for item in event.excluded_actor_organization_expressions
            ),
            candidate_available_entity_ids=tuple(
                item.entity_id for item in event.expected_entities
            ),
            candidate_missing_entity_ids=(),
            matched_entity_ids=tuple(item.entity_id for item in event.expected_entities),
            missing_entity_ids=(),
            false_negative_entity_ids=(),
            extra_draft_ids=(),
            unresolved_candidate_ids=(),
            candidate_gap_ids=(),
            violated_exclusion_ids=(),
            candidate_count=len(event.expected_entities),
            model_execution_count=len(event.expected_entities),
            exact_source_mapping=True,
            semantic_result=tuple(
                sorted(
                    f"{item.entity_kind.value}:{item.canonical_name}"
                    for item in event.expected_entities
                )
            ),
            passed=True,
        )
        for event in catalog.events
        if event.phase == "development"
    )

    first = build_event_entity_phase_report(
        catalog=catalog,
        catalog_sha256=hashlib.sha256(GOLD.read_bytes()).hexdigest(),
        phase="development",
        repetition=1,
        evaluations=evaluations,
        model_elapsed_milliseconds=17,
    )
    second = build_event_entity_phase_report(
        catalog=catalog,
        catalog_sha256=hashlib.sha256(GOLD.read_bytes()).hexdigest(),
        phase="development",
        repetition=2,
        evaluations=tuple(reversed(evaluations)),
        model_elapsed_milliseconds=23,
    )

    assert first.passed is True
    assert first.result_fingerprint == second.result_fingerprint
    assert first.proposed_change_count == 0
    assert first.accepted_ledger_change_count == 0


def _fixture_result(
    answer: EntityInvolvementAnswerValue,
) -> tuple[ConnectionGoldEvent, EventEntityExperimentInput, EventEntityConnectionPreview]:
    source = "Anthropic criticized Stargate."
    source_digest = hashlib.sha256(source.encode()).hexdigest()
    event = build_source_grounded_event_draft(
        event_subject_id="esd_" + "1" * 24,
        trigger_id="etd_" + "2" * 24,
        source_segment_id="seg_connection_fixture",
        source_text_sha256=source_digest,
        expression_text="criticized",
        head_text="criticized",
        head_evidence_target_id="etg_" + "1" * 24,
        expression_evidence_target_id="etg_" + "2" * 24,
        support_evidence_target_id="etg_" + "3" * 24,
    )
    mention_id = "mnc_" + "4" * 24
    span_values = (
        event.source_segment_id,
        source_digest,
        "0",
        str(len("Anthropic")),
        "Anthropic",
        mention_id,
        "",
    )
    source_span = EventEntitySourceSpan(
        id="ees_" + hashlib.sha256(chr(31).join(span_values).encode()).hexdigest()[:24],
        source_segment_id=event.source_segment_id,
        source_text_sha256=source_digest,
        start=0,
        end=len("Anthropic"),
        text="Anthropic",
        mention_candidate_id=mention_id,
    )
    selection = EventEntityCandidateSelection(
        mentions=(
            EventEntityMentionInput(
                entity_identity="organization:anthropic",
                entity_kind=EventEntityKind.ORGANIZATION,
                entity_name="Anthropic",
                source_span=source_span,
            ),
        ),
        gaps=(),
    )
    prepared = EventEntityExperimentInput(
        phase="development",
        gold_event_id="TGE-900",
        source_id="src_connection_fixture",
        document_id="doc_connection_fixture",
        representation_id="rep_connection_fixture",
        paragraph_node_id="nod_connection_fixture",
        source_segment_label="s1",
        source_text=source,
        event_semantics_preview_id="hsp_" + "5" * 24,
        event_semantics_preview_sha256="6" * 64,
        event=event,
        candidate_selection=selection,
    )
    candidate = build_event_entity_connection_candidates(
        event,
        selection.mentions,
        source_text=source,
    )[0]
    trace = build_extraction_stage_trace(
        trace_run_id="connection_fixture",
        ordinal=0,
        stage_id="event_entity_involvement",
        stage_version="fixture_v1",
        producer_id="fixture",
        source_segment_id=event.source_segment_id,
        source_text_sha256=source_digest,
        input_record_ids=tuple(sorted((event.id, candidate.id, mention_id))),
        execution_record_ids=("ext_connection_fixture", "mrn_connection_fixture"),
        configuration={},
        input_payload={"source_text": source},
        output_payload={"answer": answer.value},
        status=ExtractionStageStatus.COMPLETED,
    )
    judgment = build_entity_involvement_judgment(
        candidate_id=candidate.id,
        answer=answer,
        extraction_task_id="ext_connection_fixture",
        model_run_id="mrn_connection_fixture",
        trace_id=trace.id,
    )
    decision, draft = decide_event_entity_connection(candidate, judgment)
    preview = build_event_entity_connection_preview(
        parent_preview_id=prepared.event_semantics_preview_id,
        parent_preview_sha256=prepared.event_semantics_preview_sha256,
        candidate_gaps=(),
        candidates=(candidate,),
        judgments=(judgment,),
        decisions=(decision,),
        drafts=(draft,) if draft is not None else (),
        traces=(trace,),
        extraction_task_ids=("ext_connection_fixture",),
        model_run_ids=("mrn_connection_fixture",),
        terminal_status=EventEntityConnectionPreviewStatus.COMPLETE,
        diagnostics=(),
    )
    gold = ConnectionGoldEvent(
        event_id="TGE-900",
        phase="development",
        source_text_sha256=source_digest,
        event_meaning="Anthropic criticized Stargate.",
        expected_entities=(
            ConnectionGoldEntity(
                entity_id="EGE-900",
                entity_kind=EventEntityKind.ORGANIZATION,
                canonical_name="Anthropic",
                accepted_entity_names=("Anthropic",),
                accepted_source_texts=("Anthropic",),
                rationale="Anthropic performs the criticism.",
            ),
        ),
        review_rationale="Synthetic evaluator fixture.",
    )
    return gold, prepared, preview
