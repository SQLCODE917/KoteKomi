"""Focused tests for the model-free R17 semantic selection contract."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from kotekomi_application import (
    EvaluationItem,
    ReferencePolicyRecord,
    ResidualClosureRoute,
    SemanticSelectionContract,
    SemanticSelectionReport,
    build_observed_answer,
    build_semantic_selection_report,
    evaluate_selection,
    frozen_semantic_selection_contract,
    load_observed_answers,
    load_reference_policy_records,
    semantic_selection_report_fingerprint,
    verify_contract_binding,
)

DATA_DIR = Path(__file__).resolve().parents[3] / "data/r17-semantic-selection-contract"


FrozenFixture = tuple[
    SemanticSelectionContract,
    tuple[ReferencePolicyRecord, ...],
    dict[str, dict[str, str]],
    SemanticSelectionReport,
]


@pytest.fixture(scope="module")
def frozen() -> FrozenFixture:
    contract = frozen_semantic_selection_contract(directory=DATA_DIR)
    records = load_reference_policy_records(contract=contract, directory=DATA_DIR)
    answers = load_observed_answers(contract=contract, directory=DATA_DIR, records=records)
    by_event = {record.event_id: record for record in records}
    signals: dict[str, dict[str, str]] = {}
    evaluations: list[EvaluationItem] = []
    for answer in answers:
        results = evaluate_selection(
            contract=contract,
            policy_record=by_event[answer.event_id],
            observed_answer=answer,
        )
        signals[answer.observation_id] = {result.name.value: result.value for result in results}
        evaluations.append(
            EvaluationItem(
                observation_id=answer.observation_id,
                event_id=answer.event_id,
                route=answer.route,
                signals=results,
            )
        )
    report = build_semantic_selection_report(
        contract=contract,
        policy_records=records,
        observed_answers=answers,
        evaluations=tuple(evaluations),
    )
    return contract, records, signals, report


def _signals(frozen: FrozenFixture, observation_id: str) -> dict[str, str]:
    return frozen[2][observation_id]


def _record(frozen: FrozenFixture, event_id: str) -> ReferencePolicyRecord:
    return {record.event_id: record for record in frozen[1]}[event_id]


def test_contract_version_is_one(frozen: FrozenFixture) -> None:
    assert frozen[0].version == 1


def test_contract_binding_detects_policy_drift(frozen: FrozenFixture) -> None:
    contract = frozen[0]
    document = json.loads((DATA_DIR / "reference_policy_records.json").read_text())
    drifted = copy.deepcopy(document["records"])
    drifted[0]["policy_body"]["expected_selected_set"] = ["C1"]
    with pytest.raises(ValueError):
        verify_contract_binding(contract=contract, records=drifted)


def test_policy_set_covers_diagnostic_roles_and_none(frozen: FrozenFixture) -> None:
    by_event = {record.event_id: record for record in frozen[1]}
    roles = {role.role for record in frozen[1] for role in record.expected_source_ranges}
    assert roles == {"subject", "object", "time", "place", "polarity", "modality"}
    assert {"AHE-022", "AHE-051"} <= set(by_event)
    assert by_event["AHE-908"].expected_selected_set == ()


def test_every_record_has_review_and_digests(frozen: FrozenFixture) -> None:
    for record in frozen[1]:
        assert record.author_identity == "repository_operator"
        assert record.reviewer_identity == "repository_operator"
        assert record.review_evidence.path.endswith("human_approval.json")
        assert record.policy_body_sha256
        assert record.input_binding.source_sha256
        assert record.input_binding.candidate_pool_sha256


def test_renderer_names_the_eligibility_rule(frozen: FrozenFixture) -> None:
    for record in frozen[1]:
        assert "Eligibility:" in record.task.rendered_input
        assert "Selectable roles" in record.task.rendered_input
        assert "never eligibility" in record.task.rendered_input


def test_select_all_fails_on_ineligible_pool(frozen: FrozenFixture) -> None:
    assert _signals(frozen, "AHE-022-answer-01")["semantic_selection"] == "unmet"


def test_select_all_passes_on_exact_pool(frozen: FrozenFixture) -> None:
    assert _signals(frozen, "AHE-901-answer-01")["semantic_selection"] == "met"


def test_nested_candidates_reduce_to_canonical(frozen: FrozenFixture) -> None:
    assert _record(frozen, "AHE-022").expected_selected_set == ("C1", "C3")


def test_matching_text_stays_distinct(frozen: FrozenFixture) -> None:
    assert _record(frozen, "AHE-907").expected_selected_set == ("C1", "C2")


def test_reporting_carrier_not_selected(frozen: FrozenFixture) -> None:
    assert _record(frozen, "AHE-905").expected_selected_set == ("C3", "C4")


def test_entity_removal_changes_readiness_not_selection(frozen: FrozenFixture) -> None:
    assert _record(frozen, "AHE-901").composition_readiness.value == "ready"
    assert _record(frozen, "AHE-909").composition_readiness.value == "not_ready"
    assert _signals(frozen, "AHE-901-answer-01")["semantic_selection"] == "met"
    assert _signals(frozen, "AHE-909-answer-01")["semantic_selection"] == "met"


def test_ahe051_pins_unjustified_none_and_c3_profile(frozen: FrozenFixture) -> None:
    assert _signals(frozen, "AHE-051-answer-01") == {
        "answer_grammar": "valid",
        "semantic_selection": "unmet",
        "boundary_coverage": "gap",
        "abstention_correctness": "unjustified",
        "composition_readiness": "not_ready",
    }
    assert _signals(frozen, "AHE-051-answer-02") == {
        "answer_grammar": "valid",
        "semantic_selection": "met",
        "boundary_coverage": "gap",
        "abstention_correctness": "not_applicable",
        "composition_readiness": "not_ready",
    }


def test_justified_none_distinct(frozen: FrozenFixture) -> None:
    assert _signals(frozen, "AHE-908-answer-01")["abstention_correctness"] == "justified"
    assert _signals(frozen, "AHE-908-answer-01")["semantic_selection"] == "met"


def test_malformed_output_suppresses_only_answer_bound_signals(frozen: FrozenFixture) -> None:
    assert _signals(frozen, "AHE-903-grammar-negative-03") == {
        "answer_grammar": "invalid",
        "semantic_selection": "not_applicable",
        "boundary_coverage": "met",
        "abstention_correctness": "not_applicable",
        "composition_readiness": "ready",
    }


def test_boundary_coverage_gap_vs_met(frozen: FrozenFixture) -> None:
    assert _signals(frozen, "AHE-051-answer-02")["boundary_coverage"] == "gap"
    assert _signals(frozen, "AHE-022-answer-02")["boundary_coverage"] == "met"


def test_five_signals_compute_independently(frozen: FrozenFixture) -> None:
    report = frozen[3]
    for item in report.evaluations:
        assert [signal.name.value for signal in item.signals] == [
            "answer_grammar",
            "semantic_selection",
            "boundary_coverage",
            "abstention_correctness",
            "composition_readiness",
        ]
    assert "score" not in report.model_dump(mode="json")


def test_route_mismatch_fails_fast() -> None:
    document = json.loads((DATA_DIR / "observed_answers.json").read_text())
    observation = next(
        item for item in document["observations"] if item["observation_id"] == "AHE-022-answer-01"
    )
    records = load_reference_policy_records(
        contract=frozen_semantic_selection_contract(directory=DATA_DIR),
        directory=DATA_DIR,
    )
    task = next(record.task for record in records if record.event_id == "AHE-022")
    with pytest.raises(ValueError, match="route differs"):
        build_observed_answer(
            observation=observation,
            task=task,
            frozen_route=ResidualClosureRoute.BEST_CHOICE_RESELECTION,
        )


def test_fixtures_preserve_route_limits(frozen: FrozenFixture) -> None:
    assert _signals(frozen, "AHE-022-answer-02")["answer_grammar"] == "valid"
    assert _signals(frozen, "AHE-903-grammar-negative-04")["answer_grammar"] == "invalid"
    assert _signals(frozen, "AHE-051-answer-02")["answer_grammar"] == "valid"
    assert _signals(frozen, "AHE-908-answer-01")["answer_grammar"] == "valid"


def test_report_is_sealed_deterministic(frozen: FrozenFixture) -> None:
    report = frozen[3]
    assert report.model_execution_count == 0
    assert report.canonical_write_count == 0
    assert report.proposed_change_count == 0
    assert report.evaluation_count == 26
    assert report.policy_record_count == 11
    assert report.observed_answer_count == 26
    assert semantic_selection_report_fingerprint(report) == report.result_fingerprint


def test_agent_draft_requires_human_review() -> None:
    document = json.loads((DATA_DIR / "reference_policy_records.json").read_text())
    for record in document["records"]:
        assert record["draft_author"].startswith("Codex")
        assert record["human_adoption"]["author_identity"] == "repository_operator"
        assert record["human_review"]["reviewer_identity"] == "repository_operator"
