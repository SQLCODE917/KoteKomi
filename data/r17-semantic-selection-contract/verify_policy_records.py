"""Verify operator-adopted R17 policies and fixtures without freezing the contract."""

import hashlib
import json
from pathlib import Path
from typing import Any, cast

from kotekomi_application.calibrated_residual_ownership import EventFrame
from kotekomi_application.corrective_reselection_execution import (
    parse_corrective_reselection_answer,
)
from kotekomi_application.decontextualization_composition import (
    DecontextualizationEntityRef,
    build_decontextualized_proposition,
)
from kotekomi_application.event_entity_connections import EventEntityLinguisticToken
from kotekomi_application.parser_constituent_candidate_generation import (
    ConstituentCandidateInventory,
    ConstituentSelectionAnswer,
    ConstituentSelectionTask,
)
from kotekomi_application.residual_selection_failure_closure import (
    CorrectiveSelectionTask,
    ResidualClosureRoute,
    build_corrective_selection_task,
)
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[2]
DIRECTORY = Path(__file__).resolve().parent
ADOPTED_STATUS = "human_adopted_and_reviewed_pending_contract_freeze"


def canonical(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def digest(value: object) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def typed[T: BaseModel](model: type[T], value: object) -> T:
    return model.model_validate_json(canonical(value))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def load(name: str) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads((DIRECTORY / name).read_text()))


def verify_handle(handle: dict[str, str]) -> Path:
    path = (ROOT / handle["path"]).resolve()
    require(path.is_relative_to(ROOT), "Input handle escapes the repository")
    require(
        hashlib.sha256(path.read_bytes()).hexdigest() == handle["sha256"],
        f"File digest drift: {path}",
    )
    return path


def answer_fixture_body(observation: dict[str, Any]) -> dict[str, Any]:
    return {
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


def main() -> None:
    document = load("reference_policy_records.json")
    require(
        document["schema_version"] == "r17_reference_policy_records_v1", "Unknown policy format"
    )
    require(document["status"] == ADOPTED_STATUS, "Missing operator adoption")
    require(
        document["acceptance_evidence"] is False, "Unfrozen records cannot be acceptance evidence"
    )
    require(document["contract_version"] is None, "Policy adoption cannot claim a frozen contract")
    verify_handle(document["contract_spec"])
    approval_handle = document["human_approval"]
    approval = json.loads(verify_handle(approval_handle).read_text())
    verify_handle(approval["reviewed_contract_spec"])
    require(
        approval["schema_version"] == "r17_operator_review_attestation_v1",
        "Unknown approval format",
    )
    require(approval["status"] == "approved", "Missing human approval")
    require(
        approval["approval_source"] == "explicit_user_message_in_current_conversation",
        "Missing approval source",
    )
    require(bool(approval["approval_statement"]), "Missing human approval statement")
    require(approval["review_mode"] == "operator_self_review", "Review mode differs")
    require(approval["human_identity"] == "repository_operator", "Operator identity differs")
    require(
        approval["review_commit"] is None and approval["commit_status"] == "pending_commit",
        "Unrecorded review commit",
    )
    require(
        approval["contract_freeze_status"] == "pending", "Adoption cannot claim contract freeze"
    )
    approved_policies = {item["record_id"]: item for item in approval["approved_policies"]}
    approved_answers = {
        item["observation_id"]: item for item in approval["approved_answer_fixtures"]
    }
    records = document["records"]
    require(
        len(approved_policies) == len(approval["approved_policies"]) == len(records),
        "Approval policy coverage differs",
    )
    by_event = {record["event_id"]: record for record in records}
    require(
        len(records) == len(by_event) == document["record_count"],
        "Duplicate or missing policy records",
    )
    manifest = load("task_manifest.json")
    require(manifest["schema_version"] == "r17_task_manifest_v1", "Unknown task manifest format")
    require(
        manifest["status"] == ADOPTED_STATUS and manifest["human_approval"] == approval_handle,
        "Task adoption differs",
    )
    require(
        manifest["acceptance_evidence"] is False, "Unfrozen tasks cannot be acceptance evidence"
    )
    require(
        digest(manifest["tasks"]) == approval["approved_task_bindings_sha256"],
        "Approved task binding drift",
    )
    tasks = {task["event_id"]: task for task in manifest["tasks"]}
    require(
        len(tasks) == len(manifest["tasks"]) and tasks.keys() == by_event.keys(),
        "Task coverage drift",
    )
    inputs: dict[str, tuple[ConstituentSelectionTask, ResidualClosureRoute, dict[str, Any]]] = {}
    observed_document = load("observed_answers.json")
    require(
        observed_document["schema_version"] == "r17_observed_answers_v1", "Unknown answer format"
    )
    require(
        observed_document["status"] == ADOPTED_STATUS
        and observed_document["human_approval"] == approval_handle,
        "Answer adoption differs",
    )
    require(
        observed_document["acceptance_evidence"] is False, "Answer fixtures cannot claim acceptance"
    )
    observed = observed_document["observations"]
    require(
        len(approved_answers) == len(approval["approved_answer_fixtures"]) == len(observed),
        "Answer approval coverage differs",
    )
    require(
        len({item["observation_id"] for item in observed}) == len(observed),
        "Duplicate observations",
    )
    observed_ids = {item["event_id"] for item in observed}
    require(observed_ids == by_event.keys(), "Observation coverage drift")

    for event_id, record in by_event.items():
        require(record["acceptance_evidence"] is False, f"Unfrozen acceptance claim: {event_id}")
        require(record["status"] == ADOPTED_STATUS, "Unexpected policy status")
        approved_policy = approved_policies[record["record_id"]]
        require(
            approved_policy["event_id"] == event_id
            and approved_policy["policy_body_sha256"] == record["policy_body_sha256"]
            and approved_policy["input_binding"] == record["input_binding"],
            "Approved policy content differs",
        )
        adoption = record["human_adoption"]
        review = record["human_review"]
        require(adoption["author_identity"] == approval["human_identity"], "Human author differs")
        require(review["reviewer_identity"] == approval["human_identity"], "Human reviewer differs")
        require(
            adoption["evidence"] == review["evidence"] == approval_handle,
            "Human evidence binding differs",
        )
        require(review["review_mode"] == "operator_self_review", "Policy review mode differs")
        require(review["review_date"] == approval["recorded_at"][:10], "Policy review date differs")
        require(review["review_commit"] is None, "Policy invents a review commit")
        require(
            adoption["adopted_policy_body_sha256"]
            == review["reviewed_policy_body_sha256"]
            == record["policy_body_sha256"],
            "Human policy digest differs",
        )
        require(
            adoption["adopted_input_sha256"]
            == review["reviewed_input_sha256"]
            == record["input_binding"]["input_file"]["sha256"],
            "Human input digest differs",
        )
        body = record["policy_body"]
        require(digest(body) == record["policy_body_sha256"], f"Policy body drift: {event_id}")
        binding = record["input_binding"]
        path = verify_handle(binding["input_file"])
        require(
            tasks[event_id]["input_file"] == binding["input_file"], "Task input binding differs"
        )
        raw = json.loads(path.read_text())
        require(raw["event_id"] == event_id, "Input Event differs")
        task = typed(ConstituentSelectionTask, raw["selection_task"])
        inventory = typed(ConstituentCandidateInventory, raw["candidate_inventory"])
        frame = typed(EventFrame, raw["event_frame"])
        require(
            task.event_id == inventory.event_id == frame.event_id == event_id,
            "Typed Event references differ",
        )
        require(task.source_text == raw["source_text"], "Source text differs from task")
        require(
            task.source_text_sha256 == raw["source_text_sha256"] == binding["source_sha256"],
            "Source digest differs",
        )
        require(
            digest(raw["candidate_inventory"]) == binding["candidate_pool_sha256"],
            "Pool digest differs",
        )
        require(digest(raw["selection_task"]) == binding["task_sha256"], "Task digest differs")
        require(
            len(task.constituent_labels) == len(inventory.constituents), "Pool label count differs"
        )
        route = ResidualClosureRoute(raw["frozen_task_route"])
        require(
            route.value
            == binding["frozen_route"]
            == body["task_route"]
            == tasks[event_id]["frozen_route"],
            "Route binding differs",
        )
        corrective = typed(CorrectiveSelectionTask, raw["corrective_task"])
        require(
            corrective == build_corrective_selection_task(task=task, route=route),
            "Corrective task differs",
        )
        require(
            digest(raw["corrective_task"]) == tasks[event_id]["corrective_task_sha256"],
            "Corrective digest differs",
        )
        for provenance in raw["provenance"]:
            verify_handle(provenance)
        if raw["origin"] == "historical_diagnostic":
            historic = json.loads(
                (
                    ROOT / "data/r16-corrective-reselection-execution-runs/run-001/tasks.json"
                ).read_text()
            )
            historical_task = next(item for item in historic if item["event_id"] == event_id)
            require(
                typed(CorrectiveSelectionTask, historical_task) == corrective,
                "Historical route or task drift",
            )
        for item in inventory.constituents:
            rng = item.constituent_range
            require(
                task.source_text[rng.start : rng.end] == rng.text, "Candidate source offset drift"
            )
        require(
            [item["label"] for item in body["candidate_decisions"]]
            == list(task.constituent_labels),
            "Incomplete candidate decisions",
        )
        require(
            [
                item["label"]
                for item in body["candidate_decisions"]
                if item["classification"] == "selected"
            ]
            == body["expected_selected_set"],
            "Candidate decisions disagree with selection",
        )
        for role in body["expected_source_ranges"]:
            rng = role["expected_source_range"]
            require(
                task.source_text[rng["start"] : rng["end"]] == rng["text"],
                "Expected source range drift",
            )
            covering = [
                f"C{i}"
                for i, candidate in enumerate(inventory.constituents, 1)
                if candidate.constituent_range.start <= rng["start"]
                and rng["end"] <= candidate.constituent_range.end
            ]
            require(covering == role["covering_candidate_labels"], "Coverage labels differ")
            require(
                role["boundary_coverage"] == ("met" if covering else "gap"),
                "Coverage judgment differs",
            )
            label = role["canonical_candidate_label"]
            require(
                label is None or label in covering,
                "Canonical candidate does not cover its expected range",
            )
        selected = body["expected_selected_set"]
        expected = parse_corrective_reselection_answer(
            ",".join(selected) if selected else "NONE", task, route
        )
        require(expected.status.value != "rejected", "Route cannot express the reference set")
        tokens = tuple(
            typed(EventEntityLinguisticToken, item) for item in raw["composition_inputs"]["tokens"]
        )
        token_ids = {token.token_id for token in tokens}
        require(len(token_ids) == len(tokens), "Duplicate token IDs")
        for token in tokens:
            require(
                task.source_text[token.start : token.end] == token.text, "Token source offset drift"
            )
            require(
                token.head_token_id is None or token.head_token_id in token_ids,
                "Missing dependency head",
            )
        for item in inventory.constituents:
            require(set(item.token_ids) <= token_ids, "Constituent references missing tokens")
        entities = tuple(
            typed(DecontextualizationEntityRef, item)
            for item in raw["composition_inputs"]["entities"]
        )
        for item in entities:
            for occurrence in item.accepted_source_occurrences:
                require(
                    task.source_text[occurrence.start : occurrence.end] == occurrence.text,
                    "Entity occurrence drift",
                )
        result = build_decontextualized_proposition(
            event_id=event_id,
            source_text=task.source_text,
            source_text_sha256=task.source_text_sha256,
            inventory=inventory,
            answer=expected,
            trigger_head_start=frame.trigger.start,
            trigger_head_end=frame.trigger.end,
            tokens=tokens,
            entities=entities,
        )
        require(
            result.model_dump(mode="json") == raw["current_r4_composition_probe"]["result"],
            "Shared R4 composition probe drift",
        )
        inputs[event_id] = (task, route, body)

    for observation in observed:
        task, route, body = inputs[observation["event_id"]]
        require(observation["status"] == ADOPTED_STATUS, "Answer fixture lacks adoption")
        require(
            digest(answer_fixture_body(observation))
            == observation["fixture_body_sha256"]
            == approved_answers[observation["observation_id"]]["fixture_body_sha256"],
            "Approved answer fixture content differs",
        )
        review = observation["human_review"]
        require(
            review["reviewer_identity"] == approval["human_identity"]
            and review["review_mode"] == "operator_self_review",
            "Answer reviewer differs",
        )
        require(review["evidence"] == approval_handle, "Answer review evidence differs")
        require(
            review["reviewed_fixture_body_sha256"] == observation["fixture_body_sha256"],
            "Answer review digest differs",
        )
        require(
            review["review_date"] == approval["recorded_at"][:10]
            and review["review_commit"] is None,
            "Answer review date or commit differs",
        )
        require(observation["acceptance_evidence"] is False, "Observation claims acceptance")
        require(
            observation["route"] == route.value, "Observed answer route differs from frozen task"
        )
        raw_response = observation["raw_response"]
        require(
            hashlib.sha256(raw_response.encode()).hexdigest() == observation["raw_response_sha256"],
            "Raw response digest differs",
        )
        if observation["source_run_artifact"] is not None:
            require(
                verify_handle(observation["source_run_artifact"]).read_text() == raw_response,
                "Archived response differs",
            )
        actual = parse_corrective_reselection_answer(raw_response, task, route)
        require(
            actual == typed(ConstituentSelectionAnswer, observation["parsed_answer"]),
            "Stored strict parse differs",
        )
        signals = observation["expected_signals"]
        selected = [f"C{i}" for i in actual.selected_label_indexes]
        require(
            signals["answer_grammar"]
            == ("invalid" if actual.status.value == "rejected" else "valid"),
            "Grammar profile differs",
        )
        semantic = (
            "not_applicable"
            if actual.status.value == "rejected"
            else ("met" if selected == body["expected_selected_set"] else "unmet")
        )
        require(
            signals["semantic_selection"] == semantic,
            "Selection profile differs from adopted policy",
        )
        coverage = (
            "gap"
            if any(role["boundary_coverage"] == "gap" for role in body["expected_source_ranges"])
            else "met"
        )
        require(signals["boundary_coverage"] == coverage, "Coverage profile differs")
        abstention = (
            "not_applicable"
            if actual.status.value != "none"
            else ("justified" if body["none_policy"]["justified"] else "unjustified")
        )
        require(signals["abstention_correctness"] == abstention, "Abstention profile differs")
        require(
            signals["composition_readiness"] == body["composition_readiness"]["value"],
            "Readiness depends on observed answer",
        )

    roles = {
        role["role"]
        for record in records
        for role in record["policy_body"]["expected_source_ranges"]
    }
    require(
        roles == {"subject", "object", "time", "place", "polarity", "modality"},
        "Role coverage differs",
    )
    checksums_path = DIRECTORY / "checksums.json"
    if checksums_path.exists():
        for handle in load("checksums.json")["files"]:
            verify_handle(handle)
    print(
        json.dumps(
            {
                "status": "mechanically_valid_human_adopted_policy_records",
                "policy_records": len(records),
                "answer_fixtures": len(observed),
                "selectable_roles": sorted(roles),
                "acceptance_evidence": False,
                "human_review_status": "approved",
                "contract_freeze_status": "pending",
                "model_execution_count": 0,
                "canonical_write_count": 0,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
