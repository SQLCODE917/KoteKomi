"""Focused tests for the model-free R17 semantic selection contract."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest
from kotekomi_application import (
    EvaluationItem,
    FileHandle,
    ReferencePolicyRecord,
    ResidualClosureRoute,
    SemanticSelectionContract,
    SemanticSelectionReport,
    build_observed_answer,
    build_semantic_selection_report,
    compute_composition_readiness,
    content_digest,
    evaluate_selection,
    frozen_semantic_selection_contract,
    load_observed_answers,
    load_reference_policy_records,
    parse_corrective_reselection_answer,
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


def _approved_fixture_sha256(observation_id: str) -> str:
    approval = json.loads((DATA_DIR / "human_approval.json").read_text())
    return next(
        item["fixture_body_sha256"]
        for item in approval["approved_answer_fixtures"]
        if item["observation_id"] == observation_id
    )


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
    contract = frozen[0]
    record = _record(frozen, "AHE-901")
    assert compute_composition_readiness(policy_record=record) == "ready"
    stripped = record.model_copy(update={"composition_entities": ()})
    assert compute_composition_readiness(policy_record=stripped) == "not_ready"
    answers = load_observed_answers(contract=contract, directory=DATA_DIR, records=frozen[1])
    answer = next(item for item in answers if item.observation_id == "AHE-901-answer-01")
    original = {
        signal.name.value: signal.value
        for signal in evaluate_selection(
            contract=contract, policy_record=record, observed_answer=answer
        )
    }
    stripped_eval = {
        signal.name.value: signal.value
        for signal in evaluate_selection(
            contract=contract, policy_record=stripped, observed_answer=answer
        )
    }
    assert original["semantic_selection"] == "met"
    assert original["composition_readiness"] == "ready"
    assert stripped_eval["semantic_selection"] == "met"
    assert stripped_eval["composition_readiness"] == "not_ready"


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
    approval_evidence = FileHandle.model_validate(document["human_approval"])
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
            approval_evidence=approval_evidence,
            approved_fixture_body_sha256=_approved_fixture_sha256("AHE-022-answer-01"),
            root=DATA_DIR.parents[1],
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


def test_altered_historical_answer_is_rejected() -> None:
    document = json.loads((DATA_DIR / "observed_answers.json").read_text())
    approval_evidence = FileHandle.model_validate(document["human_approval"])
    observation = copy.deepcopy(
        next(
            item
            for item in document["observations"]
            if item["observation_id"] == "AHE-022-answer-01"
        )
    )
    observation["raw_response"] = "C1,C3"
    observation["raw_response_sha256"] = hashlib.sha256(b"C1,C3").hexdigest()
    # The raw response and its digest are refreshed while the reviewed fixture digest,
    # review digest, and archival handle stay original; the builder must reject it.
    records = load_reference_policy_records(
        contract=frozen_semantic_selection_contract(directory=DATA_DIR), directory=DATA_DIR
    )
    task = next(record.task for record in records if record.event_id == "AHE-022")
    with pytest.raises(ValueError, match="fixture digest"):
        build_observed_answer(
            observation=observation,
            task=task,
            frozen_route=ResidualClosureRoute(observation["route"]),
            approval_evidence=approval_evidence,
            approved_fixture_body_sha256=_approved_fixture_sha256("AHE-022-answer-01"),
            root=DATA_DIR.parents[1],
        )


def test_archived_response_must_match_raw_response() -> None:
    document = json.loads((DATA_DIR / "observed_answers.json").read_text())
    approval_evidence = FileHandle.model_validate(document["human_approval"])
    source = next(
        item for item in document["observations"] if item["observation_id"] == "AHE-022-answer-01"
    )
    records = load_reference_policy_records(
        contract=frozen_semantic_selection_contract(directory=DATA_DIR), directory=DATA_DIR
    )
    record = next(record for record in records if record.event_id == "AHE-022")
    root = DATA_DIR.parents[1]
    raw = "C1,C3"
    other = DATA_DIR / "inputs" / "AHE-051.json"
    observation = copy.deepcopy(source)
    observation["raw_response"] = raw
    observation["raw_response_sha256"] = hashlib.sha256(raw.encode()).hexdigest()
    observation["source_run_artifact"] = {
        "path": str(other.relative_to(root)),
        "sha256": hashlib.sha256(other.read_bytes()).hexdigest(),
    }
    observation["parsed_answer"] = parse_corrective_reselection_answer(
        raw, record.task, ResidualClosureRoute(observation["route"])
    ).model_dump(mode="json")
    # Keep the fixture digest and review digest consistent; only the archived bytes drift.
    observation["fixture_body_sha256"] = content_digest(
        {
            key: observation[key]
            for key in (
                "observation_id",
                "event_id",
                "route",
                "origin",
                "raw_response",
                "raw_response_sha256",
                "source_run_artifact",
                "parsed_answer",
                "note",
                "expected_signals",
            )
        }
    )
    observation["human_review"]["reviewed_fixture_body_sha256"] = observation["fixture_body_sha256"]
    with pytest.raises(ValueError, match="Archived response differs"):
        build_observed_answer(
            observation=observation,
            task=record.task,
            frozen_route=ResidualClosureRoute(observation["route"]),
            approval_evidence=approval_evidence,
            approved_fixture_body_sha256=_approved_fixture_sha256("AHE-022-answer-01"),
            root=root,
        )


def test_answer_review_evidence_binds_approval() -> None:
    document = json.loads((DATA_DIR / "observed_answers.json").read_text())
    approval_evidence = FileHandle.model_validate(document["human_approval"])
    observation = copy.deepcopy(
        next(
            item
            for item in document["observations"]
            if item["observation_id"] == "AHE-022-answer-01"
        )
    )
    observation["human_review"]["evidence"] = {"path": "other/approval.json", "sha256": "0" * 64}
    records = load_reference_policy_records(
        contract=frozen_semantic_selection_contract(directory=DATA_DIR), directory=DATA_DIR
    )
    task = next(record.task for record in records if record.event_id == "AHE-022")
    with pytest.raises(ValueError, match="approval binding"):
        build_observed_answer(
            observation=observation,
            task=task,
            frozen_route=ResidualClosureRoute(observation["route"]),
            approval_evidence=approval_evidence,
            approved_fixture_body_sha256=_approved_fixture_sha256("AHE-022-answer-01"),
            root=DATA_DIR.parents[1],
        )


def test_cross_event_evaluation_is_rejected(frozen: FrozenFixture) -> None:
    contract = frozen[0]
    by_event = {record.event_id: record for record in frozen[1]}
    answers = load_observed_answers(contract=contract, directory=DATA_DIR, records=frozen[1])
    by_oid = {answer.observation_id: answer for answer in answers}
    with pytest.raises(ValueError, match="Event differs"):
        evaluate_selection(
            contract=contract,
            policy_record=by_event["AHE-901"],
            observed_answer=by_oid["AHE-909-answer-01"],
        )


def test_binding_detects_decision_text_drift(frozen: FrozenFixture) -> None:
    contract = frozen[0]
    document = json.loads((DATA_DIR / "reference_policy_records.json").read_text())
    records = document["records"]
    with pytest.raises(ValueError, match="binding drifted"):
        verify_contract_binding(
            contract=contract.model_copy(update={"none_rule": "A changed NONE rule."}),
            records=records,
        )
    with pytest.raises(ValueError, match="binding drifted"):
        verify_contract_binding(
            contract=contract.model_copy(
                update={"canonical_boundary_rules": ("A changed boundary rule.",)}
            ),
            records=records,
        )


def test_answer_fixture_must_match_approved_digest() -> None:
    document = json.loads((DATA_DIR / "observed_answers.json").read_text())
    approval_evidence = FileHandle.model_validate(document["human_approval"])
    observation = copy.deepcopy(
        next(
            item
            for item in document["observations"]
            if item["observation_id"] == "AHE-022-answer-01"
        )
    )
    records = load_reference_policy_records(
        contract=frozen_semantic_selection_contract(directory=DATA_DIR), directory=DATA_DIR
    )
    record = next(record for record in records if record.event_id == "AHE-022")
    raw = "C1,C3"
    observation["raw_response"] = raw
    observation["raw_response_sha256"] = hashlib.sha256(raw.encode()).hexdigest()
    observation["source_run_artifact"] = None
    observation["parsed_answer"] = parse_corrective_reselection_answer(
        raw, record.task, ResidualClosureRoute(observation["route"])
    ).model_dump(mode="json")
    # Recompute the fixture and review digests so every internal digest is
    # self-consistent; only the operator-approved answer fixture still differs.
    observation["fixture_body_sha256"] = content_digest(
        {
            key: observation[key]
            for key in (
                "observation_id",
                "event_id",
                "route",
                "origin",
                "raw_response",
                "raw_response_sha256",
                "source_run_artifact",
                "parsed_answer",
                "note",
                "expected_signals",
            )
        }
    )
    observation["human_review"]["reviewed_fixture_body_sha256"] = observation["fixture_body_sha256"]
    with pytest.raises(ValueError, match="approved answer fixture"):
        build_observed_answer(
            observation=observation,
            task=record.task,
            frozen_route=ResidualClosureRoute(observation["route"]),
            approval_evidence=approval_evidence,
            approved_fixture_body_sha256=_approved_fixture_sha256("AHE-022-answer-01"),
            root=DATA_DIR.parents[1],
        )


def test_polarity_drift_changes_readiness_to_not_ready() -> None:
    contract = frozen_semantic_selection_contract(directory=DATA_DIR)
    records = load_reference_policy_records(contract=contract, directory=DATA_DIR)
    record = next(record for record in records if record.event_id == "AHE-903")
    assert compute_composition_readiness(policy_record=record) == "ready"
    drifted_tokens = tuple(
        token.model_copy(update={"dependency_relation": "advmod"}) if token.text == "not" else token
        for token in record.composition_tokens
    )
    drifted = record.model_copy(update={"composition_tokens": drifted_tokens})
    assert compute_composition_readiness(policy_record=drifted) == "not_ready"


def test_missing_object_changes_readiness_to_not_ready() -> None:
    contract = frozen_semantic_selection_contract(directory=DATA_DIR)
    records = load_reference_policy_records(contract=contract, directory=DATA_DIR)
    record = next(record for record in records if record.event_id == "AHE-901")
    assert compute_composition_readiness(policy_record=record) == "ready"
    drifted_tokens = tuple(
        token.model_copy(update={"dependency_relation": "dep"}) if token.text == "Tomas" else token
        for token in record.composition_tokens
    )
    drifted = record.model_copy(update={"composition_tokens": drifted_tokens})
    assert compute_composition_readiness(policy_record=drifted) == "not_ready"


def test_wrong_targeted_reporter_changes_readiness_to_not_ready() -> None:
    from kotekomi_application import AttachmentSourceRange

    contract = frozen_semantic_selection_contract(directory=DATA_DIR)
    records = load_reference_policy_records(contract=contract, directory=DATA_DIR)
    record = next(record for record in records if record.event_id == "AHE-905")
    assert compute_composition_readiness(policy_record=record) == "ready"
    requirements = record.proposition_requirements

    # Same attribution kind, but the reviewed reporter is swapped to another entity name.
    wrong_reporter = requirements.model_copy(
        update={"attribution": requirements.attribution.model_copy(update={"reporter": "Tomas"})}
    )
    assert (
        compute_composition_readiness(
            policy_record=record.model_copy(update={"proposition_requirements": wrong_reporter})
        )
        == "not_ready"
    )

    # Same attribution kind and reporter, but the reviewed carrier span is rewritten.
    wrong_carrier = requirements.model_copy(
        update={
            "attribution": requirements.attribution.model_copy(
                update={"reporting_carrier": AttachmentSourceRange(start=15, end=20, text="Tomas")}
            )
        }
    )
    assert (
        compute_composition_readiness(
            policy_record=record.model_copy(update={"proposition_requirements": wrong_carrier})
        )
        == "not_ready"
    )


def test_binding_detects_argument_roles_drift(monkeypatch: pytest.MonkeyPatch) -> None:
    import kotekomi_application.semantic_selection_contract as ssc

    contract = frozen_semantic_selection_contract(directory=DATA_DIR)
    document = json.loads((DATA_DIR / "reference_policy_records.json").read_text())
    records = document["records"]
    monkeypatch.setattr(ssc, "_ARGUMENT_ROLES", frozenset({"object", "time", "place"}))
    with pytest.raises(ValueError, match="binding drifted"):
        verify_contract_binding(contract=contract, records=records)
