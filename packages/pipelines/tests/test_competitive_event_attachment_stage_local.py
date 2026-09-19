from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from kotekomi_application import (
    CompetitiveAttachmentAnswer,
    CompetitiveAttachmentAnswerKind,
    CompetitiveAttachmentDecision,
    CompetitiveAttachmentDecisionStatus,
    CompetitiveAttachmentEventOption,
    CompetitiveAttachmentMatrix,
    PropositionFragmentReason,
    build_competitive_attachment_decision,
    competitive_attachment_candidate_id,
    competitive_attachment_event_option_id,
    competitive_attachment_matrix_id,
    complete_competitive_attachment_matrix,
)
from kotekomi_application.competitive_event_attachment import (
    CompetitiveAttachmentCandidate,
)
from kotekomi_pipelines.competitive_event_attachment_stage_local import (
    CompetitiveAttachmentBaselineDecision,
    CompetitiveAttachmentBaselineDisposition,
    CompetitiveAttachmentBaselineEventResult,
    CompetitiveAttachmentDiagnosticApproval,
    build_competitive_attachment_oracle,
    build_competitive_attachment_phase_report,
    compare_competitive_attachment_reports,
    load_prompt_v3_baseline,
    reconstruct_prompt_v3_baseline,
    validate_competitive_attachment_diagnostic_approval,
)
from kotekomi_pipelines.source_grounded_proposition_stage_local import (
    PropositionGoldCatalog,
    PropositionGoldEvent,
    PropositionGoldFragment,
    PropositionGoldFragmentRequirement,
    PropositionGoldReviewStatus,
)

SOURCE = "Actor stated claim."
DIGEST = hashlib.sha256(SOURCE.encode()).hexdigest()
EVENT_ONE = "sge_" + "1" * 24
EVENT_TWO = "sge_" + "2" * 24


def test_oracle_preserves_shared_and_none_occurrences_and_complete_coverage() -> None:
    matrix = attachment_matrix_fixture()
    catalog = _catalog()

    oracle, preflight = build_competitive_attachment_oracle(
        catalog=catalog,
        phase="development",
        matrices=(matrix,),
        source_grounded_event_by_gold_id={"TGE-001": EVENT_ONE, "TGE-002": EVENT_TWO},
    )

    decisions = {item.candidate_id: item for item in oracle[matrix.id]}
    actor = next(item for item in matrix.candidates if item.text == "Actor")
    overreach = next(item for item in matrix.candidates if item.text == "stated claim")
    assert decisions[actor.id].source_grounded_event_ids == (EVENT_ONE, EVENT_TWO)
    assert decisions[overreach.id].source_grounded_event_ids == ()
    assert preflight.passed is True
    assert preflight.shared_gold_candidate_count == 1
    assert preflight.empty_gold_candidate_count == 1


def test_evaluator_detects_occurrence_edges_and_improved_proposition_scope() -> None:
    matrix = attachment_matrix_fixture()
    catalog = _catalog()
    oracle, _ = build_competitive_attachment_oracle(
        catalog=catalog,
        phase="development",
        matrices=(matrix,),
        source_grounded_event_by_gold_id={"TGE-001": EVENT_ONE, "TGE-002": EVENT_TWO},
    )
    gold_by_candidate = {item.candidate_id: item for item in oracle[matrix.id]}
    answers: list[CompetitiveAttachmentDecision] = []
    baseline: list[CompetitiveAttachmentBaselineDecision] = []
    for ordinal, candidate in enumerate(matrix.candidates, start=1):
        gold = gold_by_candidate[candidate.id].source_grounded_event_ids
        labels = tuple(
            option.label
            for option in matrix.event_options
            if option.source_grounded_event_id in gold
        )
        answer = (
            CompetitiveAttachmentAnswer(CompetitiveAttachmentAnswerKind.ATTACHED, labels)
            if labels
            else CompetitiveAttachmentAnswer(CompetitiveAttachmentAnswerKind.NONE)
        )
        answers.append(
            build_competitive_attachment_decision(
                candidate=candidate,
                event_options=matrix.event_options,
                status=CompetitiveAttachmentDecisionStatus.COMPLETE,
                answer=answer,
                extraction_task_id=f"ext_{ordinal}",
                model_run_id=f"mrn_{ordinal}",
                trace_id=f"xst_{ordinal:024x}",
                raw_output=(",".join(labels) if labels else "NONE").encode(),
                diagnostic_code=None,
            )
        )
        baseline_events = (EVENT_ONE, EVENT_TWO) if candidate.text == "claim" else gold
        baseline.append(_baseline(candidate.id, baseline_events))
    terminal = complete_competitive_attachment_matrix(matrix, tuple(answers))

    report = build_competitive_attachment_phase_report(
        catalog=catalog,
        catalog_sha256="a" * 64,
        phase="development",
        repetition=1,
        matrices=(terminal,),
        gold_by_matrix=oracle,
        baseline_by_matrix={matrix.id: tuple(baseline)},
        source_grounded_event_by_gold_id={"TGE-001": EVENT_ONE, "TGE-002": EVENT_TWO},
        entity_occurrences_by_gold_event={
            "TGE-001": ((0, 5),),
            "TGE-002": ((0, 5),),
        },
        model_execution_count=len(matrix.candidates),
        input_token_count=100,
        output_token_count=10,
        elapsed_milliseconds=20,
    )

    assert report.metrics.competitive_exact_set_accuracy == 1.0
    assert report.metrics.competitive_sibling_event_leakage_count == 0
    assert report.metrics.baseline_sibling_event_leakage_count == 1
    assert report.metrics.competitive_character_recall == 1.0
    assert report.metrics.competitive_entity_recall == 1.0
    assert report.accepted_ledger_change_count == 0


def test_evaluator_detects_equal_text_occurrence_swaps_hidden_by_identity_summary() -> None:
    matrix, catalog = _repeated_occurrence_fixture()
    oracle, preflight = build_competitive_attachment_oracle(
        catalog=catalog,
        phase="development",
        matrices=(matrix,),
        source_grounded_event_by_gold_id={"TGE-001": EVENT_ONE, "TGE-002": EVENT_TWO},
    )
    assert preflight.passed is True
    first, second = matrix.candidates
    label_by_event = {item.source_grounded_event_id: item.label for item in matrix.event_options}
    decisions = tuple(
        build_competitive_attachment_decision(
            candidate=candidate,
            event_options=matrix.event_options,
            status=CompetitiveAttachmentDecisionStatus.COMPLETE,
            answer=CompetitiveAttachmentAnswer(
                CompetitiveAttachmentAnswerKind.ATTACHED,
                (label_by_event[predicted_event],),
            ),
            extraction_task_id=f"ext_swap_{ordinal}",
            model_run_id=f"mrn_swap_{ordinal}",
            trace_id=f"xst_{ordinal + 20:024x}",
            raw_output=label_by_event[predicted_event].encode(),
            diagnostic_code=None,
        )
        for ordinal, (candidate, predicted_event) in enumerate(
            ((first, EVENT_TWO), (second, EVENT_ONE)), start=1
        )
    )
    terminal = complete_competitive_attachment_matrix(matrix, decisions)
    baseline = (
        _baseline(first.id, (EVENT_ONE,)),
        _baseline(second.id, (EVENT_TWO,)),
    )

    report = build_competitive_attachment_phase_report(
        catalog=catalog,
        catalog_sha256="b" * 64,
        phase="development",
        repetition=1,
        matrices=(terminal,),
        gold_by_matrix=oracle,
        baseline_by_matrix={matrix.id: baseline},
        source_grounded_event_by_gold_id={"TGE-001": EVENT_ONE, "TGE-002": EVENT_TWO},
        entity_occurrences_by_gold_event={
            "TGE-001": ((first.start, first.end),),
            "TGE-002": ((second.start, second.end),),
        },
        model_execution_count=2,
        input_token_count=20,
        output_token_count=2,
        elapsed_milliseconds=10,
    )

    gold_identity_pairs = {
        (candidate.text, event_id)
        for candidate, gold in zip(matrix.candidates, oracle[matrix.id], strict=True)
        for event_id in gold.source_grounded_event_ids
    }
    predicted_identity_pairs = {
        (candidate.text, edge.source_grounded_event_id)
        for candidate, decision in zip(matrix.candidates, decisions, strict=True)
        for edge in decision.edges
    }
    assert predicted_identity_pairs == gold_identity_pairs
    assert report.metrics.edge_precision == 0.0
    assert report.metrics.edge_recall == 0.0
    assert report.metrics.competitive_exact_set_accuracy == 0.0
    assert sum(item.false_positive_edge_count for item in report.cases) == 2
    assert sum(item.false_negative_edge_count for item in report.cases) == 2


def test_comparison_requires_both_phase_improvement_and_stability() -> None:
    report = phase_report_fixture()
    validation = report.model_copy(update={"phase": "validation", "repetition": 1})

    result = compare_competitive_attachment_reports(
        (
            report,
            report.model_copy(update={"repetition": 2}),
            report.model_copy(update={"repetition": 3}),
        ),
        validation,
        development_report_sha256s=("1" * 64, "2" * 64, "3" * 64),
        validation_report_sha256="4" * 64,
    )

    assert result.outcome == "supported"
    assert result.production_integration == "not_activated"


def test_diagnostic_approval_binds_invariant_execution_contract() -> None:
    approval = CompetitiveAttachmentDiagnosticApproval(
        reviewer="DSerbarinov",
        diagnostic_result_sha256="a" * 64,
        diagnostic_review_sha256="b" * 64,
        prompt_sha256="c" * 64,
        execution_contract_sha256="d" * 64,
    )

    result = validate_competitive_attachment_diagnostic_approval(
        approval.model_dump(mode="json"),
        expected_prompt_sha256="c" * 64,
        expected_execution_contract_sha256="d" * 64,
    )

    assert result == approval


def test_diagnostic_approval_rejects_changed_execution_contract() -> None:
    approval = CompetitiveAttachmentDiagnosticApproval(
        reviewer="DSerbarinov",
        diagnostic_result_sha256="a" * 64,
        diagnostic_review_sha256="b" * 64,
        prompt_sha256="c" * 64,
        execution_contract_sha256="d" * 64,
    )

    with pytest.raises(ValueError, match="approved a different execution contract"):
        validate_competitive_attachment_diagnostic_approval(
            approval.model_dump(mode="json"),
            expected_prompt_sha256="c" * 64,
            expected_execution_contract_sha256="e" * 64,
        )


def test_baseline_import_rejects_changed_report_digest_before_model_use(tmp_path: Path) -> None:
    (tmp_path / "run.json").write_text(
        json.dumps(
            {
                "schema_version": "source_grounded_proposition_experiment_run_v1",
                "status": "finalized",
                "phase": "development",
                "gold_sha256": "a" * 64,
                "prompt_sha256": "b" * 64,
            }
        )
    )
    (tmp_path / "report.json").write_text("{}")
    (tmp_path / "manifest.json").write_text(json.dumps({"report_sha256": "c" * 64}))

    with pytest.raises(ValueError, match="report digest drifted"):
        load_prompt_v3_baseline(
            run_root=tmp_path,
            phase="development",
            matrices=(attachment_matrix_fixture(),),
            gold_event_to_source_grounded_event={
                "TGE-001": EVENT_ONE,
                "TGE-002": EVENT_TWO,
            },
            expected_gold_sha256="a" * 64,
            expected_prompt_sha256="b" * 64,
        )


def test_baseline_reconstruction_preserves_unresolved_and_missing_results() -> None:
    matrix = attachment_matrix_fixture()
    first, second = matrix.candidates[:2]
    first_parent = first.parent_candidate_ids[0]
    second_parent = second.parent_candidate_ids[0]

    baseline = reconstruct_prompt_v3_baseline(
        matrices=(matrix,),
        record_by_source_grounded_event_id={
            EVENT_ONE: {
                "candidates": [{"id": first_parent}, {"id": second_parent}],
                "decisions": [
                    {
                        "id": "pfd_" + "1" * 24,
                        "candidate_id": first_parent,
                        "disposition": "unresolved",
                        "reason_code": "invalid_model_output",
                    },
                    {
                        "id": "pfd_" + "2" * 24,
                        "candidate_id": second_parent,
                        "disposition": "included",
                        "reason_code": "model_included",
                    },
                ],
            },
            EVENT_TWO: {"candidates": [], "decisions": []},
        },
    )

    by_candidate = {item.candidate_id: item for item in baseline[matrix.id]}
    assert by_candidate[first.id].attached_event_ids == ()
    assert by_candidate[first.id].unresolved_event_ids == (EVENT_ONE, EVENT_TWO)
    assert tuple(item.disposition for item in by_candidate[first.id].event_results) == (
        CompetitiveAttachmentBaselineDisposition.UNRESOLVED,
        CompetitiveAttachmentBaselineDisposition.MISSING,
    )
    assert by_candidate[second.id].attached_event_ids == (EVENT_ONE,)
    assert by_candidate[second.id].unresolved_event_ids == (EVENT_TWO,)


def attachment_matrix_fixture() -> CompetitiveAttachmentMatrix:
    options = tuple(
        _option(label, event_id, trigger_id, start, end)
        for label, event_id, trigger_id, start, end in (
            ("E1", EVENT_ONE, "etd_" + "1" * 24, 6, 12),
            ("E2", EVENT_TWO, "etd_" + "2" * 24, 13, 18),
        )
    )
    candidates = tuple(
        _candidate(start, end, ordinal)
        for ordinal, (start, end) in enumerate(((0, 5), (6, 12), (6, 18), (13, 18)), start=1)
    )
    matrix_id = competitive_attachment_matrix_id(
        source_segment_id="seg_fixture",
        source_text_sha256=DIGEST,
        candidate_ids=tuple(item.id for item in candidates),
        event_option_ids=tuple(item.id for item in options),
        decision_ids=(),
    )
    return CompetitiveAttachmentMatrix(
        id=matrix_id,
        source_segment_id="seg_fixture",
        source_text_sha256=DIGEST,
        candidates=candidates,
        event_options=options,
    )


def _candidate(start: int, end: int, ordinal: int) -> CompetitiveAttachmentCandidate:
    text = SOURCE[start:end]
    reasons = (PropositionFragmentReason.ENTITY_OCCURRENCE,)
    parent_ids = (f"pfc_{ordinal:024x}",)
    token_ids = (f"t{ordinal}",)
    record_ids = (f"record_{ordinal}",)
    candidate_id = competitive_attachment_candidate_id(
        source_segment_id="seg_fixture",
        source_text_sha256=DIGEST,
        start=start,
        end=end,
        text=text,
        reasons=reasons,
        parent_candidate_ids=parent_ids,
        linguistic_token_ids=token_ids,
        source_record_ids=record_ids,
    )
    return CompetitiveAttachmentCandidate(
        id=candidate_id,
        source_segment_id="seg_fixture",
        source_text_sha256=DIGEST,
        start=start,
        end=end,
        text=text,
        reasons=reasons,
        parent_candidate_ids=parent_ids,
        linguistic_token_ids=token_ids,
        source_record_ids=record_ids,
    )


def _option(
    label: str, event_id: str, trigger_id: str, start: int, end: int
) -> CompetitiveAttachmentEventOption:
    text = SOURCE[start:end]
    option_id = competitive_attachment_event_option_id(
        source_grounded_event_id=event_id,
        event_trigger_id=trigger_id,
        source_segment_id="seg_fixture",
        source_text_sha256=DIGEST,
        start=start,
        end=end,
        text=text,
    )
    return CompetitiveAttachmentEventOption(
        id=option_id,
        label=label,
        source_grounded_event_id=event_id,
        event_trigger_id=trigger_id,
        source_segment_id="seg_fixture",
        source_text_sha256=DIGEST,
        start=start,
        end=end,
        text=text,
    )


def _repeated_occurrence_fixture() -> tuple[CompetitiveAttachmentMatrix, PropositionGoldCatalog]:
    source = "Alex criticized a plan; Alex praised the plan."
    digest = hashlib.sha256(source.encode()).hexdigest()
    first_start = source.index("Alex")
    second_start = source.index("Alex", first_start + 1)
    candidates = tuple(
        _custom_candidate(source, digest, start, ordinal)
        for ordinal, start in enumerate((first_start, second_start), start=1)
    )
    options = tuple(
        _custom_option(source, digest, label, event_id, trigger_id, text)
        for label, event_id, trigger_id, text in (
            ("E1", EVENT_ONE, "etd_" + "3" * 24, "criticized"),
            ("E2", EVENT_TWO, "etd_" + "4" * 24, "praised"),
        )
    )
    matrix_id = competitive_attachment_matrix_id(
        source_segment_id="seg_repeated_fixture",
        source_text_sha256=digest,
        candidate_ids=tuple(item.id for item in candidates),
        event_option_ids=tuple(item.id for item in options),
        decision_ids=(),
    )
    matrix = CompetitiveAttachmentMatrix(
        id=matrix_id,
        source_segment_id="seg_repeated_fixture",
        source_text_sha256=digest,
        candidates=candidates,
        event_options=options,
    )
    events = tuple(
        PropositionGoldEvent(
            event_id=event_id,
            phase="development",
            source_text_sha256=digest,
            source_text=source,
            event_meaning=meaning,
            fragments=(
                PropositionGoldFragment(
                    fragment_id=f"PGF-{event_id}-01",
                    start=start,
                    end=start + 4,
                    text="Alex",
                    requirements=(PropositionGoldFragmentRequirement.CORE_EVENT,),
                ),
            ),
            review_rationale="occurrence-swap fixture",
        )
        for event_id, meaning, start in (
            ("TGE-001", "The first Alex occurrence belongs to criticism.", first_start),
            ("TGE-002", "The second Alex occurrence belongs to praise.", second_start),
        )
    )
    catalog = PropositionGoldCatalog.model_construct(
        catalog_id="repeated-occurrence-fixture",
        review_status=PropositionGoldReviewStatus.APPROVED,
        connection_gold_path="connection.json",
        connection_gold_sha256="1" * 64,
        trigger_gold_path="trigger.json",
        trigger_gold_sha256="2" * 64,
        events=events,
    )
    return matrix, catalog


def _custom_candidate(
    source: str, digest: str, start: int, ordinal: int
) -> CompetitiveAttachmentCandidate:
    end = start + 4
    reasons = (PropositionFragmentReason.ENTITY_OCCURRENCE,)
    parent_ids = (f"pfc_{ordinal + 10:024x}",)
    token_ids = (f"t{ordinal + 10}",)
    record_ids = (f"record_repeat_{ordinal}",)
    candidate_id = competitive_attachment_candidate_id(
        source_segment_id="seg_repeated_fixture",
        source_text_sha256=digest,
        start=start,
        end=end,
        text=source[start:end],
        reasons=reasons,
        parent_candidate_ids=parent_ids,
        linguistic_token_ids=token_ids,
        source_record_ids=record_ids,
    )
    return CompetitiveAttachmentCandidate(
        id=candidate_id,
        source_segment_id="seg_repeated_fixture",
        source_text_sha256=digest,
        start=start,
        end=end,
        text=source[start:end],
        reasons=reasons,
        parent_candidate_ids=parent_ids,
        linguistic_token_ids=token_ids,
        source_record_ids=record_ids,
    )


def _custom_option(
    source: str,
    digest: str,
    label: str,
    event_id: str,
    trigger_id: str,
    text: str,
) -> CompetitiveAttachmentEventOption:
    start = source.index(text)
    end = start + len(text)
    option_id = competitive_attachment_event_option_id(
        source_grounded_event_id=event_id,
        event_trigger_id=trigger_id,
        source_segment_id="seg_repeated_fixture",
        source_text_sha256=digest,
        start=start,
        end=end,
        text=text,
    )
    return CompetitiveAttachmentEventOption(
        id=option_id,
        label=label,
        source_grounded_event_id=event_id,
        event_trigger_id=trigger_id,
        source_segment_id="seg_repeated_fixture",
        source_text_sha256=digest,
        start=start,
        end=end,
        text=text,
    )


def _catalog() -> PropositionGoldCatalog:
    events = (
        _gold("TGE-001", "Actor stated", ((0, 5), (6, 12))),
        _gold("TGE-002", "Actor claim", ((0, 5), (13, 18))),
    )
    return PropositionGoldCatalog.model_construct(
        catalog_id="fixture",
        review_status=PropositionGoldReviewStatus.APPROVED,
        connection_gold_path="connection.json",
        connection_gold_sha256="1" * 64,
        trigger_gold_path="trigger.json",
        trigger_gold_sha256="2" * 64,
        events=events,
    )


def _gold(event_id: str, meaning: str, ranges: tuple[tuple[int, int], ...]) -> PropositionGoldEvent:
    fragments = tuple(
        PropositionGoldFragment(
            fragment_id=f"PGF-{event_id}-{ordinal:02d}",
            start=start,
            end=end,
            text=SOURCE[start:end],
            requirements=(PropositionGoldFragmentRequirement.CORE_EVENT,),
        )
        for ordinal, (start, end) in enumerate(ranges, start=1)
    )
    return PropositionGoldEvent(
        event_id=event_id,
        phase="development",
        source_text_sha256=DIGEST,
        source_text=SOURCE,
        event_meaning=meaning,
        fragments=fragments,
        review_rationale="fixture",
    )


def _baseline(
    candidate_id: str, attached: tuple[str, ...]
) -> CompetitiveAttachmentBaselineDecision:
    results = tuple(
        CompetitiveAttachmentBaselineEventResult(
            source_grounded_event_id=event_id,
            parent_candidate_id=f"pfc_{ordinal:024x}",
            disposition=(
                CompetitiveAttachmentBaselineDisposition.INCLUDED
                if event_id in attached
                else CompetitiveAttachmentBaselineDisposition.EXCLUDED
            ),
            reason_code="fixture",
            parent_decision_id=f"pfd_{ordinal:024x}",
        )
        for ordinal, event_id in enumerate((EVENT_ONE, EVENT_TWO), start=1)
    )
    return CompetitiveAttachmentBaselineDecision(
        candidate_id=candidate_id,
        event_results=results,
        attached_event_ids=tuple(
            item.source_grounded_event_id
            for item in results
            if item.disposition is CompetitiveAttachmentBaselineDisposition.INCLUDED
        ),
        unresolved_event_ids=(),
    )


def phase_report_fixture():  # type: ignore[no-untyped-def]
    matrix = attachment_matrix_fixture()
    catalog = _catalog()
    oracle, _ = build_competitive_attachment_oracle(
        catalog=catalog,
        phase="development",
        matrices=(matrix,),
        source_grounded_event_by_gold_id={"TGE-001": EVENT_ONE, "TGE-002": EVENT_TWO},
    )
    decisions = tuple(
        build_competitive_attachment_decision(
            candidate=candidate,
            event_options=matrix.event_options,
            status=CompetitiveAttachmentDecisionStatus.COMPLETE,
            answer=(
                CompetitiveAttachmentAnswer(
                    CompetitiveAttachmentAnswerKind.ATTACHED,
                    tuple(
                        option.label
                        for option in matrix.event_options
                        if option.source_grounded_event_id
                        in next(
                            item for item in oracle[matrix.id] if item.candidate_id == candidate.id
                        ).source_grounded_event_ids
                    ),
                )
                if next(
                    item for item in oracle[matrix.id] if item.candidate_id == candidate.id
                ).source_grounded_event_ids
                else CompetitiveAttachmentAnswer(CompetitiveAttachmentAnswerKind.NONE)
            ),
            extraction_task_id=f"ext_{ordinal}",
            model_run_id=f"mrn_{ordinal}",
            trace_id=f"xst_{ordinal:024x}",
            raw_output=b"fixture",
            diagnostic_code=None,
        )
        for ordinal, candidate in enumerate(matrix.candidates, start=1)
    )
    terminal = complete_competitive_attachment_matrix(matrix, decisions)
    baseline = tuple(_baseline(item.id, (EVENT_ONE, EVENT_TWO)) for item in matrix.candidates)
    return build_competitive_attachment_phase_report(
        catalog=catalog,
        catalog_sha256="a" * 64,
        phase="development",
        repetition=1,
        matrices=(terminal,),
        gold_by_matrix=oracle,
        baseline_by_matrix={matrix.id: baseline},
        source_grounded_event_by_gold_id={"TGE-001": EVENT_ONE, "TGE-002": EVENT_TWO},
        entity_occurrences_by_gold_event={"TGE-001": (), "TGE-002": ()},
        model_execution_count=4,
        input_token_count=100,
        output_token_count=10,
        elapsed_milliseconds=20,
    )
