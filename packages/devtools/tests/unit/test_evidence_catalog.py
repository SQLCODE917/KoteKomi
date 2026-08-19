import json
from pathlib import Path

import pytest
from kotekomi_devtools.evidence_catalog import (
    EvidenceError,
    canonical_relative,
    index_record,
    read_index,
    validated_entries,
)


def test_index_orders_and_replaces_one_evidence_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    root = tmp_path / "state"
    record = root / "experiments/task/runs/task-run-001/lifecycle/candidate.json"
    record.parent.mkdir(parents=True)
    record.write_text('{"ready":true}\n')
    index_record(
        root,
        "task",
        "task-run-001",
        phase="candidate",
        evidence_type="candidate_lifecycle",
        subject_id="candidate",
        path_scope="state",
        relative_path="experiments/task/runs/task-run-001/lifecycle/candidate.json",
        producer_command="lifecycle-check",
    )
    record.write_text('{"ready":false}\n')
    index_record(
        root,
        "task",
        "task-run-001",
        phase="candidate",
        evidence_type="candidate_lifecycle",
        subject_id="candidate",
        path_scope="state",
        relative_path="experiments/task/runs/task-run-001/lifecycle/candidate.json",
        producer_command="lifecycle-check",
    )
    assert len(read_index(root, "task", "task-run-001")["entries"]) == 1
    events = [
        json.loads(line)
        for line in (root / "experiments/task/runs/task-run-001/evidence/events.jsonl")
        .read_text()
        .splitlines()
    ]
    assert events[0]["schema_version"] == 2
    assert events[0]["index_status"] == "ready"
    assert events[0]["evidence_outcome"] == "ready"
    assert events[0]["previous_sha256"] is None
    assert "status" not in events[0]
    assert events[1]["evidence_outcome"] == "not_ready"
    assert events[1]["previous_sha256"] == events[0]["sha256"]


@pytest.mark.parametrize(
    ("evidence_type", "phase", "payload", "outcome"),
    [
        ("candidate_lifecycle", "candidate", {"ready": True}, "ready"),
        ("run_check", "verification", {"status": "passed"}, "passed"),
        ("verify_checks", "verification", {"status": "ready"}, "passed"),
        ("candidate_ci", "candidate_ci", {"conclusion": "success"}, "success"),
        ("candidate_verification_receipt", "verification", {"outcome": "passed"}, "passed"),
    ],
)
def test_event_outcomes_are_normalized_by_evidence_type(
    tmp_path: Path,
    evidence_type: str,
    phase: str,
    payload: dict[str, object],
    outcome: str,
) -> None:
    root = tmp_path / "state"
    relative = f"experiments/task/runs/task-run-001/records/{evidence_type}.json"
    path = root / relative
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(payload))
    index_record(
        root,
        "task",
        "task-run-001",
        phase=phase,
        evidence_type=evidence_type,
        subject_id=evidence_type,
        path_scope="state",
        relative_path=relative,
        producer_command="test",
    )
    event = json.loads(
        (root / "experiments/task/runs/task-run-001/evidence/events.jsonl").read_text()
    )
    assert event["evidence_outcome"] == outcome


def test_unknown_evidence_type_blocks_event_creation(tmp_path: Path) -> None:
    root = tmp_path / "state"
    relative = "experiments/task/runs/task-run-001/records/unknown.json"
    path = root / relative
    path.parent.mkdir(parents=True)
    path.write_text("{}")
    with pytest.raises(EvidenceError, match="no event outcome rule"):
        index_record(
            root,
            "task",
            "task-run-001",
            phase="candidate",
            evidence_type="unknown",
            subject_id="unknown",
            path_scope="state",
            relative_path=relative,
            producer_command="test",
        )
    assert not (root / "experiments/task/runs/task-run-001/evidence/events.jsonl").exists()


def test_digest_mismatch_blocks_reader(tmp_path: Path) -> None:
    root = tmp_path / "state"
    path = root / "experiments/t/runs/t-run-001/ci/candidate.json"
    path.parent.mkdir(parents=True)
    path.write_text('{"conclusion":"success"}\n')
    index_record(
        root,
        "t",
        "t-run-001",
        phase="candidate_ci",
        evidence_type="candidate_ci",
        subject_id="candidate",
        path_scope="state",
        relative_path="experiments/t/runs/t-run-001/ci/candidate.json",
        producer_command="ci",
    )
    path.write_text('{"conclusion":"failure"}\n')
    with pytest.raises(EvidenceError, match="digest mismatch"):
        validated_entries(root, "t", "t-run-001")


def test_reader_requires_type_specific_trusted_fields(tmp_path: Path) -> None:
    root = tmp_path / "state"
    path = root / "experiments/t/runs/t-run-001/lifecycle/candidate.json"
    path.parent.mkdir(parents=True)
    path.write_text('{"ready":true}\n')
    index_record(
        root,
        "t",
        "t-run-001",
        phase="candidate",
        evidence_type="candidate_lifecycle",
        subject_id="candidate",
        path_scope="state",
        relative_path="experiments/t/runs/t-run-001/lifecycle/candidate.json",
        producer_command="lifecycle-check",
    )
    with pytest.raises(EvidenceError, match="diagnostics"):
        validated_entries(root, "t", "t-run-001")


def test_run_check_path_is_stable() -> None:
    scope, path = canonical_relative("run_check", "task", "task-run-001", "lint")
    assert scope == "state" and path.endswith(
        "/checks/run-checks/" + __import__("hashlib").sha256(b"lint").hexdigest()[:16] + ".json"
    )


def test_main_promotion_is_the_only_canonical_main_promotion_type() -> None:
    scope, path = canonical_relative("main_promotion", "task", "task-run-001", "main")
    assert (scope, path) == (
        "state",
        "experiments/task/runs/task-run-001/git/main-promotion.json",
    )
    with pytest.raises(EvidenceError, match="unknown evidence type"):
        canonical_relative("main_merge", "task", "task-run-001", "main")


def test_candidate_verification_receipts_use_profile_specific_canonical_paths() -> None:
    scope, path = canonical_relative(
        "candidate_verification_receipt", "task", "task-run-001", "portable-local"
    )
    assert (scope, path) == (
        "state",
        "experiments/task/runs/task-run-001/receipts/candidate-verification-portable-local.json",
    )
