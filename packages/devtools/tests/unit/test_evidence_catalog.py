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
    assert (
        len(
            (root / "experiments/task/runs/task-run-001/evidence/events.jsonl")
            .read_text()
            .splitlines()
        )
        == 2
    )


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
