from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest
from kotekomi_application import (
    EntityInvolvementAnswerValue,
    EntityInvolvementJudgment,
    EventEntityCandidateGap,
    EventEntityCandidateGapReason,
    EventEntityCandidateSelection,
    EventEntityConnectionDecision,
    EventEntityConnectionDisposition,
    EventEntityConnectionDraft,
    EventEntityConnectionPreview,
    EventEntityConnectionPreviewStatus,
    EventEntityDenotationDecision,
    EventEntityDenotationRule,
    EventEntityGapDependency,
    EventEntityGapDependencyRule,
    EventEntityKind,
    EventEntityLinguisticEvidence,
    EventEntityLinguisticToken,
    EventEntityMentionInput,
    EventEntitySourceSpan,
    EventTriggerDraft,
    build_entity_involvement_judgment,
    build_event_entity_candidate_routes,
    build_event_entity_connection_candidates,
    build_event_entity_connection_preview,
    build_extraction_stage_trace,
    build_source_grounded_event_draft,
    decide_event_entity_connection,
)
from kotekomi_application.extraction_stage_trace import ExtractionStageStatus
from kotekomi_application.hybrid_event_triggers import event_trigger_id
from kotekomi_pipelines.event_entity_connection_stage_local import (
    ConnectionGoldEntity,
    ConnectionGoldEvent,
    ConnectionGoldExcludedExpression,
    ConnectionGoldExpectedGap,
    ConnectionGoldSourceOccurrence,
    EventEntityCaseEvaluation,
    EventEntityExperimentInput,
    EventEntityGoldDisposition,
    EventEntityOccurrenceEvaluation,
    EventEntityOccurrenceScore,
    build_event_entity_phase_report,
    evaluate_event_entity_candidate_availability,
    evaluate_event_entity_case,
    event_entity_candidate_signature,
    event_entity_preparation_status,
    load_connection_gold_catalog,
    render_connection_gold_review,
    validate_equal_event_entity_candidate_inventories,
)

ROOT = Path(__file__).resolve().parents[3]
GOLD = ROOT / "docs" / "hsq-event-entity-connection-gold-v2.json"


def test_connection_gold_binds_events_and_requires_approval_for_validation(
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
    assert (
        sum(len(item.expected_entities) for item in catalog.events if item.phase == "development")
        == 47
    )
    assert (
        sum(len(item.expected_entities) for item in catalog.events if item.phase == "validation")
        == 43
    )
    assert len(
        {item.entity_id for event in catalog.events for item in event.expected_entities}
    ) == sum(len(event.expected_entities) for event in catalog.events)
    assert {
        item.exclusion_id
        for event in catalog.events
        for item in event.excluded_actor_organization_expressions
    } == {"EGX-001", "EGX-002"}
    assert all(not item.expected_candidate_gaps for item in catalog.events)
    hiring = next(item for item in catalog.events if item.event_id == "TGE-022")
    amodei = next(item for item in hiring.expected_entities if item.canonical_name == "Amodei")
    assert {
        (item.start, item.end, item.source_text) for item in amodei.accepted_source_occurrences
    } == {
        (13, 19, "Amodei"),
        (100, 103, "his"),
    }
    assert "TGE-010" not in {item.event_id for item in catalog.events}
    assert "TGE-012" not in {item.event_id for item in catalog.events}
    assert "TGE-020" not in {item.event_id for item in catalog.events}
    assert "TGE-021" not in {item.event_id for item in catalog.events}
    assert "TGE-024" not in {item.event_id for item in catalog.events}
    assert "TGE-029" not in {item.event_id for item in catalog.events}
    assert "TGE-031" not in {item.event_id for item in catalog.events}
    assert {"TGE-064", "TGE-069", "TGE-078", "TGE-085"} <= {
        item.event_id for item in catalog.events
    }
    assert "TGE-054" in {item.event_id for item in catalog.events}
    services = next(item for item in catalog.events if item.event_id == "TGE-055")
    assert services.event_meaning == (
        "Palantir and Amazon Web Services offered services with FedRAMP authorization."
    )
    assert {item.canonical_name for item in services.expected_entities} == {
        "Amazon Web Services",
        "FedRAMP",
        "Palantir",
    }
    fedramp = next(item for item in services.expected_entities if item.canonical_name == "FedRAMP")
    assert {
        (item.start, item.end, item.source_text) for item in fedramp.accepted_source_occurrences
    } == {(126, 133, "FedRAMP")}
    threat = next(item for item in catalog.events if item.event_id == "TGE-078")
    assert {item.canonical_name for item in threat.expected_entities} == {
        "Anthropic",
        "Department of Defense",
    }
    department = next(
        item for item in threat.expected_entities if item.canonical_name == "Department of Defense"
    )
    assert {
        (item.start, item.end, item.source_text) for item in department.accepted_source_occurrences
    } == {
        (47, 72, "the Department of Defense"),
        (51, 72, "Department of Defense"),
        (114, 129, "the  department"),
    }
    conflict = next(item for item in catalog.events if item.event_id == "TGE-064")
    assert {item.canonical_name for item in conflict.expected_entities} == {
        "Anthropic",
        "Trump administration",
    }
    opposition = next(item for item in catalog.events if item.event_id == "TGE-069")
    assert {item.canonical_name for item in opposition.expected_entities} == {
        "Anthropic representatives",
        "Anthropic",
        "Reuters",
    }
    denial = next(item for item in catalog.events if item.event_id == "TGE-085")
    assert {item.canonical_name for item in denial.expected_entities} == {
        "Anthropic",
        "Court of Appeals for the D.C. Circuit",
    }
    publication = next(item for item in catalog.events if item.event_id == "TGE-007")
    assert publication.event_meaning == (
        "The following month, Amodei wrote an op-ed in The New York Times."
    )
    assert {item.canonical_name for item in publication.expected_entities} == {
        "Amodei",
        "The New York Times",
    }
    attributed_statement = next(item for item in catalog.events if item.event_id == "TGE-025")
    assert attributed_statement.event_meaning == (
        'In October 2025, Sacks stated that Anthropic was "running a sophisticated regulatory '
        'capture strategy based on fearmongering."'
    )
    assert {item.canonical_name for item in attributed_statement.expected_entities} == {
        "Anthropic",
        "Sacks",
    }
    sacks = next(
        item for item in attributed_statement.expected_entities if item.canonical_name == "Sacks"
    )
    assert {
        (item.start, item.end, item.source_text) for item in sacks.accepted_source_occurrences
    } == {(22, 27, "Sacks")}
    assert "TGE-060" in {item.event_id for item in catalog.events}
    assert {item.event_id for item in catalog.events}.issubset(
        {item.event_id for item in grounded.items if item.expected_review_outcome == "approved"}
    )
    assert {item.event_id for item in catalog.events}.issubset(
        {item.event_id for segment in triggers.segments for item in segment.events}
    )
    approved, _, _ = load_connection_gold_catalog(
        GOLD,
        repository_root=ROOT,
        require_approved=True,
    )
    assert approved == catalog
    proposed_value = json.loads(GOLD.read_bytes())
    proposed_value["review_status"] = "proposed"
    proposed = tmp_path / "proposed.json"
    proposed.write_text(json.dumps(proposed_value), encoding="utf-8")
    with pytest.raises(ValueError, match="human approval"):
        load_connection_gold_catalog(
            proposed,
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


def test_connection_gold_rejects_event_meaning_drift(tmp_path: Path) -> None:
    value = json.loads(GOLD.read_bytes())
    statement = next(item for item in value["events"] if item["event_id"] == "TGE-025")
    statement["event_meaning"] = "Anthropic was running a regulatory capture strategy."
    changed = tmp_path / "changed.json"
    changed.write_text(json.dumps(value), encoding="utf-8")

    with pytest.raises(ValueError, match="Event meaning drifted from Trigger Gold"):
        load_connection_gold_catalog(
            changed,
            repository_root=ROOT,
            require_approved=False,
        )


def test_connection_gold_rejects_an_unobserved_accepted_source_occurrence(
    tmp_path: Path,
) -> None:
    value = json.loads(GOLD.read_bytes())
    occurrence = value["events"][0]["expected_entities"][0]["accepted_source_occurrences"][0]
    occurrence["start"] = 1
    occurrence["end"] = 10
    occurrence["source_text"] = "Anthropic"
    changed = tmp_path / "changed.json"
    changed.write_text(json.dumps(value), encoding="utf-8")

    with pytest.raises(ValueError, match="source occurrence does not replay"):
        load_connection_gold_catalog(
            changed,
            repository_root=ROOT,
            require_approved=False,
        )


def test_connection_gold_rejects_an_expected_gap_at_the_wrong_occurrence(
    tmp_path: Path,
) -> None:
    value = json.loads(GOLD.read_bytes())
    hiring = next(item for item in value["events"] if item["event_id"] == "TGE-022")
    hiring["expected_candidate_gaps"] = [
        {
            "gap_id": "EGG-900",
            "start": 101,
            "end": 104,
            "source_text": "his",
            "reason": "reference_ambiguous",
            "rationale": "Synthetic wrong-range expected gap.",
        }
    ]
    changed = tmp_path / "changed.json"
    changed.write_text(json.dumps(value), encoding="utf-8")

    with pytest.raises(ValueError, match="does not replay"):
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
        "Accepted source occurrences must replay byte-for-byte at their recorded ranges in the "
        "Event's exact SourceSegment." in rendered
    )
    assert all(item.event_meaning in rendered for item in catalog.events)
    assert all(
        item.canonical_name in rendered
        for event in catalog.events
        for item in event.expected_entities
    )
    assert rendered.count("Event review: `approved`") == 40
    assert "EGX-001 — not Actor/Organization — event" in rendered
    assert "Expected typed candidate gaps:\n\n- None." in rendered


def test_connection_gold_treats_official_groups_as_source_bound_actors() -> None:
    catalog, _, _ = load_connection_gold_catalog(
        GOLD,
        repository_root=ROOT,
        require_approved=False,
    )
    entities_by_event = {
        event.event_id: {item.canonical_name: item for item in event.expected_entities}
        for event in catalog.events
    }

    for event_id in ("TGE-005", "TGE-006", "TGE-039", "TGE-051"):
        officials = entities_by_event[event_id]["Trump officials"]
        assert officials.entity_kind == EventEntityKind.ACTOR

    biden_officials = entities_by_event["TGE-022"]["Biden officials"]
    assert biden_officials.entity_kind == EventEntityKind.ACTOR
    assert biden_officials.accepted_source_occurrences == (
        ConnectionGoldSourceOccurrence(
            start=117,
            end=133,
            source_text="Biden  officials",
        ),
    )


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


def test_connection_evaluator_scores_exact_occurrences_and_preserves_unresolved() -> None:
    gold, prepared, connected = _fixture_result(EntityInvolvementAnswerValue.YES)

    positive = evaluate_event_entity_case(gold, prepared, connected)

    assert len(positive.occurrences) == 1
    assert positive.occurrences[0].expected_entity_ids == ("EGE-900",)
    assert positive.occurrences[0].strict_score is EventEntityOccurrenceScore.TRUE_POSITIVE
    assert positive.occurrences[0].unresolved is False

    _, _, unresolved_preview = _fixture_result(EntityInvolvementAnswerValue.UNCERTAIN)
    unresolved = evaluate_event_entity_case(gold, prepared, unresolved_preview)

    assert unresolved.occurrences[0].strict_score is EventEntityOccurrenceScore.FALSE_NEGATIVE
    assert unresolved.occurrences[0].unresolved is True
    assert unresolved.unresolved_candidate_ids == (unresolved.occurrences[0].candidate_id,)

    negative_gold = gold.model_copy(update={"expected_entities": ()})
    false_positive = evaluate_event_entity_case(negative_gold, prepared, connected)

    assert false_positive.occurrences[0].expected_entity_ids == ()
    assert false_positive.occurrences[0].strict_score is EventEntityOccurrenceScore.FALSE_POSITIVE


@pytest.mark.parametrize(
    ("repeat_exact_range", "expected_pass", "expected_extra_count"),
    ((True, True, 0), (False, False, 1)),
)
def test_connection_evaluator_distinguishes_duplicate_evidence_from_a_repeated_name(
    repeat_exact_range: bool,
    expected_pass: bool,
    expected_extra_count: int,
) -> None:
    gold, prepared, original_preview = _fixture_result(EntityInvolvementAnswerValue.YES)
    original_mention = prepared.candidate_selection.mentions[0]
    original_denotation = prepared.candidate_selection.denotation_decisions[0]
    second_mention_id = "mnc_" + "9" * 24
    second_start = (
        original_mention.source_span.start
        if repeat_exact_range
        else prepared.source_text.rindex("Anthropic")
    )
    second_end = second_start + len(original_mention.source_span.text)
    second_span_values = (
        prepared.event.source_segment_id,
        prepared.event.source_text_sha256,
        str(second_start),
        str(second_end),
        original_mention.source_span.text,
        second_mention_id,
        "",
    )
    second_span = EventEntitySourceSpan(
        id="ees_" + hashlib.sha256(chr(31).join(second_span_values).encode()).hexdigest()[:24],
        source_segment_id=prepared.event.source_segment_id,
        source_text_sha256=prepared.event.source_text_sha256,
        start=second_start,
        end=second_end,
        text=original_mention.source_span.text,
        mention_candidate_id=second_mention_id,
    )
    second_evidence_id = "mob_" + "a" * 24
    second_interpretation_id = "mit_" + "b" * 24
    second_denotation_values = (
        second_mention_id,
        EventEntityKind.ORGANIZATION.value,
        "Anthropic",
        EventEntityDenotationRule.MODEL_CONTEXTUAL_KIND.value,
        second_interpretation_id,
        second_evidence_id,
    )
    second_denotation = EventEntityDenotationDecision(
        id="edd_"
        + hashlib.sha256(chr(31).join(second_denotation_values).encode()).hexdigest()[:24],
        mention_candidate_id=second_mention_id,
        entity_kind=EventEntityKind.ORGANIZATION,
        entity_name="Anthropic",
        rule_id=EventEntityDenotationRule.MODEL_CONTEXTUAL_KIND,
        source_evidence_ids=(second_evidence_id,),
        mention_interpretation_id=second_interpretation_id,
    )
    selection = EventEntityCandidateSelection(
        mentions=(
            original_mention,
            EventEntityMentionInput(
                entity_identity=original_mention.entity_identity,
                entity_kind=EventEntityKind.ORGANIZATION,
                entity_name="Anthropic",
                denotation_decision_id=second_denotation.id,
                source_span=second_span,
            ),
        ),
        denotation_decisions=(original_denotation, second_denotation),
        gaps=(),
        gap_dependencies=(),
    )
    prepared = prepared.model_copy(update={"candidate_selection": selection})
    candidates = build_event_entity_connection_candidates(
        prepared.event,
        selection.mentions,
        source_text=prepared.source_text,
    )
    routes = build_event_entity_candidate_routes(
        source_text=prepared.source_text,
        candidates=candidates,
        linguistic_evidence=prepared.linguistic_evidence,
    )
    extraction_task_id = "ext_duplicate_inventory"
    model_run_id = "mrn_duplicate_inventory"
    trace = build_extraction_stage_trace(
        trace_run_id="connection_duplicate_fixture",
        ordinal=0,
        stage_id="event_entity_involvement",
        stage_version="fixture_v1",
        producer_id="fixture",
        source_segment_id=prepared.event.source_segment_id,
        source_text_sha256=prepared.event.source_text_sha256,
        input_record_ids=tuple(
            sorted(
                {
                    prepared.event.id,
                    *(candidate.id for candidate in candidates),
                    *(candidate.primary_source_span_id for candidate in candidates),
                }
            )
        ),
        execution_record_ids=(extraction_task_id, model_run_id),
        configuration={},
        input_payload={
            "source_text": prepared.source_text,
            "candidates": [candidate.model_dump(mode="json") for candidate in candidates],
        },
        output_payload={"answers": "Y" * len(candidates)},
        status=ExtractionStageStatus.COMPLETED,
    )
    judgments: list[EntityInvolvementJudgment] = []
    decisions: list[EventEntityConnectionDecision] = []
    drafts: list[EventEntityConnectionDraft] = []
    for candidate, route in zip(candidates, routes, strict=True):
        judgment = build_entity_involvement_judgment(
            candidate_id=candidate.id,
            answer=EntityInvolvementAnswerValue.YES,
            extraction_task_id=extraction_task_id,
            model_run_id=model_run_id,
            trace_id=trace.id,
        )
        decision, draft = decide_event_entity_connection(candidate, route, judgment)
        assert draft is not None
        judgments.append(judgment)
        decisions.append(decision)
        drafts.append(draft)
    preview = build_event_entity_connection_preview(
        parent_preview_id=original_preview.parent_preview_id,
        parent_preview_sha256=original_preview.parent_preview_sha256,
        denotation_decisions=selection.denotation_decisions,
        candidate_gaps=(),
        gap_dependencies=(),
        candidates=candidates,
        routes=routes,
        judgments=tuple(judgments),
        decisions=tuple(decisions),
        drafts=tuple(drafts),
        traces=(trace,),
        extraction_task_ids=(extraction_task_id,),
        model_run_ids=(model_run_id,),
        terminal_status=EventEntityConnectionPreviewStatus.COMPLETE,
        diagnostics=(),
    )

    evaluation = evaluate_event_entity_case(gold, prepared, preview)

    assert evaluation.passed is expected_pass
    assert len(evaluation.extra_draft_ids) == expected_extra_count
    assert evaluation.semantic_result == ("organization:Anthropic",)
    assert len(preview.identity_connections) == 1
    assert preview.identity_connections[0].connected_candidate_ids == tuple(
        sorted(item.id for item in candidates)
    )


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
                    accepted_source_occurrences=(
                        ConnectionGoldSourceOccurrence(
                            start=21,
                            end=29,
                            source_text="Stargate",
                        ),
                    ),
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
                    start=0,
                    end=9,
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


def test_reviewed_reference_gap_is_visible_without_blocking_other_event_evidence() -> None:
    gold, prepared, preview = _fixture_result(EntityInvolvementAnswerValue.YES)
    source = prepared.source_text
    gap_start = source.index("criticized")
    gap_end = gap_start + len("criticized")
    mention_id = "mnc_" + "9" * 24
    gap_values = (
        prepared.event.source_segment_id,
        prepared.event.source_text_sha256,
        mention_id,
        str(gap_start),
        str(gap_end),
        "criticized",
        EventEntityCandidateGapReason.REFERENCE_AMBIGUOUS.value,
        "",
    )
    gap = EventEntityCandidateGap(
        id="ecg_" + hashlib.sha256(chr(31).join(gap_values).encode()).hexdigest()[:24],
        source_segment_id=prepared.event.source_segment_id,
        source_text_sha256=prepared.event.source_text_sha256,
        mention_candidate_id=mention_id,
        mention_start=gap_start,
        mention_end=gap_end,
        mention_text="criticized",
        reason=EventEntityCandidateGapReason.REFERENCE_AMBIGUOUS,
    )
    expression_start = source.index(prepared.event.expression_text)
    expression_end = expression_start + len(prepared.event.expression_text)
    dependency_values = (
        gap.id,
        prepared.event.id,
        prepared.event.mention.id,
        str(expression_start),
        str(expression_end),
        EventEntityGapDependencyRule.EXPRESSION_OVERLAP.value,
    )
    dependency = EventEntityGapDependency(
        id="egd_" + hashlib.sha256(chr(31).join(dependency_values).encode()).hexdigest()[:24],
        gap_id=gap.id,
        source_grounded_event_id=prepared.event.id,
        event_mention_id=prepared.event.mention.id,
        event_expression_start=expression_start,
        event_expression_end=expression_end,
        rule_id=EventEntityGapDependencyRule.EXPRESSION_OVERLAP,
    )
    selection = EventEntityCandidateSelection(
        mentions=prepared.candidate_selection.mentions,
        denotation_decisions=prepared.candidate_selection.denotation_decisions,
        gaps=(gap,),
        gap_dependencies=(dependency,),
    )
    prepared_with_gap = prepared.model_copy(update={"candidate_selection": selection})
    expected_gap = ConnectionGoldExpectedGap(
        gap_id="EGG-900",
        start=gap_start,
        end=gap_end,
        source_text="criticized",
        reason=EventEntityCandidateGapReason.REFERENCE_AMBIGUOUS,
        rationale="Synthetic reviewed ambiguity.",
    )
    gold_with_gap = gold.model_copy(update={"expected_candidate_gaps": (expected_gap,)})
    preview_with_gap = build_event_entity_connection_preview(
        parent_preview_id=preview.parent_preview_id,
        parent_preview_sha256=preview.parent_preview_sha256,
        denotation_decisions=preview.denotation_decisions,
        candidate_gaps=(gap,),
        gap_dependencies=(dependency,),
        candidates=preview.candidates,
        routes=preview.routes,
        judgments=preview.judgments,
        decisions=preview.decisions,
        drafts=preview.drafts,
        traces=preview.traces,
        extraction_task_ids=preview.extraction_task_ids,
        model_run_ids=preview.model_run_ids,
        terminal_status=EventEntityConnectionPreviewStatus.PARTIAL,
        diagnostics=(f"candidate_gap:{gap.id}:{gap.reason.value}",),
    )

    preflight = evaluate_event_entity_candidate_availability(
        gold_with_gap,
        prepared_with_gap,
    )
    evaluation = evaluate_event_entity_case(
        gold_with_gap,
        prepared_with_gap,
        preview_with_gap,
    )

    assert preflight.passed is True
    assert preflight.matched_expected_gap_ids == ("EGG-900",)
    assert preflight.unexpected_candidate_gap_ids == ()
    assert evaluation.passed is True
    assert evaluation.matched_expected_gap_ids == ("EGG-900",)
    assert evaluation.unexpected_candidate_gap_ids == ()

    unexpected = evaluate_event_entity_candidate_availability(
        gold,
        prepared_with_gap,
    )
    assert unexpected.passed is False
    assert unexpected.unexpected_candidate_gap_ids == (gap.id,)


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
            occurrences=_perfect_occurrences(event),
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
            expected_gap_ids=tuple(item.gap_id for item in event.expected_candidate_gaps),
            matched_expected_gap_ids=tuple(item.gap_id for item in event.expected_candidate_gaps),
            missing_expected_gap_ids=(),
            candidate_gap_ids=tuple(
                f"ecg_{index:024x}"
                for index, _ in enumerate(event.expected_candidate_gaps, start=1)
            ),
            unexpected_candidate_gap_ids=(),
            violated_exclusion_ids=(),
            candidate_count=len(event.expected_entities),
            model_execution_count=1,
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
    assert first.schema_version == "hsq_event_entity_connection_report_v2"
    assert first.occurrence_count == first.expected_entity_count
    assert first.strict_metrics.true_positive_count == first.expected_entity_count
    assert first.strict_metrics.false_positive_count == 0
    assert first.strict_metrics.false_negative_count == 0
    assert first.strict_metrics.precision == 1.0
    assert first.strict_metrics.recall == 1.0
    assert first.connected_sensitivity_metrics == first.strict_metrics
    assert first.result_fingerprint == second.result_fingerprint
    assert first.proposed_change_count == 0
    assert first.accepted_ledger_change_count == 0
    validate_equal_event_entity_candidate_inventories((first, second))

    changed_inventory = second.model_copy(update={"candidate_inventory_sha256": "f" * 64})
    with pytest.raises(ValueError, match="different candidate inventories"):
        validate_equal_event_entity_candidate_inventories((first, changed_inventory))


def _perfect_occurrences(
    event: ConnectionGoldEvent,
) -> tuple[EventEntityOccurrenceEvaluation, ...]:
    occurrences: list[EventEntityOccurrenceEvaluation] = []
    for entity in event.expected_entities:
        source = entity.accepted_source_occurrences[0]
        candidate_id = (
            "eec_"
            + hashlib.sha256(f"{event.event_id}:{entity.entity_id}".encode()).hexdigest()[:24]
        )
        identity = f"{entity.entity_kind.value}:{entity.canonical_name}"
        signature = event_entity_candidate_signature(
            event_id=event.event_id,
            candidate_id=candidate_id,
            entity_identity=identity,
            entity_kind=entity.entity_kind,
            entity_name=entity.canonical_name,
            source_text_sha256=event.source_text_sha256,
            source_start=source.start,
            source_end=source.end,
            source_text=source.source_text,
        )
        occurrences.append(
            EventEntityOccurrenceEvaluation(
                event_id=event.event_id,
                candidate_id=candidate_id,
                candidate_signature=signature,
                entity_identity=identity,
                entity_kind=entity.entity_kind,
                entity_name=entity.canonical_name,
                source_text_sha256=event.source_text_sha256,
                source_start=source.start,
                source_end=source.end,
                source_text=source.source_text,
                expected_entity_ids=(entity.entity_id,),
                gold_disposition=EventEntityGoldDisposition.POSITIVE,
                observed_disposition=EventEntityConnectionDisposition.CONNECTED,
                strict_score=EventEntityOccurrenceScore.TRUE_POSITIVE,
                unresolved=False,
            )
        )
    return tuple(sorted(occurrences, key=lambda item: item.candidate_id))


def _fixture_result(
    answer: EntityInvolvementAnswerValue,
) -> tuple[ConnectionGoldEvent, EventEntityExperimentInput, EventEntityConnectionPreview]:
    source = "Anthropic criticized Stargate while Anthropic observed."
    source_digest = hashlib.sha256(source.encode()).hexdigest()
    trigger_start = source.index("criticized")
    trigger_end = trigger_start + len("criticized")
    trigger_trace_id = "xst_" + "8" * 24
    trigger = EventTriggerDraft(
        id=event_trigger_id(
            source_segment_id="seg_connection_fixture",
            source_text_sha256=source_digest,
            start=trigger_start,
            end=trigger_end,
            text="criticized",
            head_start=trigger_start,
            head_end=trigger_end,
            head_text="criticized",
            event_type_label="criticism",
            extraction_task_id="ext_trigger_fixture",
            model_run_id="mrn_trigger_fixture",
            trace_id=trigger_trace_id,
        ),
        source_segment_id="seg_connection_fixture",
        source_text_sha256=source_digest,
        start=trigger_start,
        end=trigger_end,
        text="criticized",
        head_start=trigger_start,
        head_end=trigger_end,
        head_text="criticized",
        event_type_label="criticism",
        extraction_task_id="ext_trigger_fixture",
        model_run_id="mrn_trigger_fixture",
        trace_id=trigger_trace_id,
    )
    event = build_source_grounded_event_draft(
        event_subject_id="esd_" + "1" * 24,
        trigger_id=trigger.id,
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
    source_evidence_id = "mob_" + "7" * 24
    interpretation_id = "mit_" + "8" * 24
    denotation_values = (
        mention_id,
        EventEntityKind.ORGANIZATION.value,
        "Anthropic",
        EventEntityDenotationRule.MODEL_CONTEXTUAL_KIND.value,
        interpretation_id,
        source_evidence_id,
    )
    denotation = EventEntityDenotationDecision(
        id="edd_" + hashlib.sha256(chr(31).join(denotation_values).encode()).hexdigest()[:24],
        mention_candidate_id=mention_id,
        entity_kind=EventEntityKind.ORGANIZATION,
        entity_name="Anthropic",
        rule_id=EventEntityDenotationRule.MODEL_CONTEXTUAL_KIND,
        source_evidence_ids=(source_evidence_id,),
        mention_interpretation_id=interpretation_id,
    )
    selection = EventEntityCandidateSelection(
        mentions=(
            EventEntityMentionInput(
                entity_identity="organization:anthropic",
                entity_kind=EventEntityKind.ORGANIZATION,
                entity_name="Anthropic",
                denotation_decision_id=denotation.id,
                source_span=source_span,
            ),
        ),
        denotation_decisions=(denotation,),
        gaps=(),
        gap_dependencies=(),
    )
    linguistic_evidence = _linguistic_evidence(source, event.source_segment_id)
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
        trigger=trigger,
        event=event,
        candidate_selection=selection,
        linguistic_evidence=linguistic_evidence,
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
    route = build_event_entity_candidate_routes(
        source_text=source,
        candidates=(candidate,),
        linguistic_evidence=linguistic_evidence,
    )[0]
    decision, draft = decide_event_entity_connection(candidate, route, judgment)
    preview = build_event_entity_connection_preview(
        parent_preview_id=prepared.event_semantics_preview_id,
        parent_preview_sha256=prepared.event_semantics_preview_sha256,
        denotation_decisions=(denotation,),
        candidate_gaps=(),
        gap_dependencies=(),
        candidates=(candidate,),
        routes=(route,),
        judgments=(judgment,),
        decisions=(decision,),
        drafts=(draft,) if draft is not None else (),
        traces=(trace,),
        extraction_task_ids=("ext_connection_fixture",),
        model_run_ids=("mrn_connection_fixture",),
        terminal_status=(
            EventEntityConnectionPreviewStatus.PARTIAL
            if answer is EntityInvolvementAnswerValue.UNCERTAIN
            else EventEntityConnectionPreviewStatus.COMPLETE
        ),
        diagnostics=("model_uncertain",)
        if answer is EntityInvolvementAnswerValue.UNCERTAIN
        else (),
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
                accepted_source_occurrences=(
                    ConnectionGoldSourceOccurrence(
                        start=0,
                        end=9,
                        source_text="Anthropic",
                    ),
                ),
                rationale="Anthropic performs the criticism.",
            ),
        ),
        review_rationale="Synthetic evaluator fixture.",
    )
    return gold, prepared, preview


def _linguistic_evidence(
    source_text: str,
    source_segment_id: str,
) -> EventEntityLinguisticEvidence:
    raw_tokens = tuple(
        (match.start(), match.end(), match.group())
        for match in re.finditer(r"\w+|[^\w\s]", source_text)
    )
    sentence_ordinal = 1
    sentence_root_id: str | None = None
    tokens: list[EventEntityLinguisticToken] = []
    for ordinal, (start, end, text) in enumerate(raw_tokens, start=1):
        token_id = f"t{ordinal}"
        if sentence_root_id is None:
            sentence_root_id = token_id
        tokens.append(
            EventEntityLinguisticToken(
                token_id=token_id,
                sentence_id=f"s{sentence_ordinal}",
                text=text,
                start=start,
                end=end,
                lemma=text.casefold(),
                part_of_speech="X",
                dependency_relation="root" if token_id == sentence_root_id else "dep",
                head_token_id=None if token_id == sentence_root_id else sentence_root_id,
            )
        )
        if text in {".", "!", "?"}:
            sentence_ordinal += 1
            sentence_root_id = None
    return EventEntityLinguisticEvidence(
        trace_id="xst_" + "9" * 24,
        source_segment_id=source_segment_id,
        source_text_sha256=hashlib.sha256(source_text.encode()).hexdigest(),
        producer_id="stanza:fixture",
        model_id="stanza-en",
        model_version="fixture",
        resource_identity="a" * 64,
        tokens=tuple(tokens),
    )
