import json
import subprocess
from pathlib import Path

import pytest
from kotekomi_devtools.evidence_catalog import (
    EvidenceError,
    canonical_relative,
    index_record,
    read_index,
    validated_entries,
    write_canonical_record,
)


def _git(repo: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments], cwd=repo, text=True, capture_output=True, check=True
    )
    return result.stdout.strip()


def _repository_manifest(repo: Path, value: str = "one") -> Path:
    path = repo / ".agent/tasks/t.toml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                'task_id = "t"',
                'tdd_path = "docs/t.md"',
                'tdd_sha256 = "' + "a" * 64 + '"',
                f'value = "{value}"',
                "",
            ]
        )
    )
    return path


def _pinned_manifest_run(
    root: Path, repo: Path, monkeypatch: pytest.MonkeyPatch
) -> str:
    subprocess.run(["git", "init", "-b", "main", str(repo)], check=True, capture_output=True)
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    _repository_manifest(repo)
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "specification")
    revision = _git(repo, "rev-parse", "HEAD")
    monkeypatch.chdir(repo)
    index_record(
        root,
        "t",
        "t-run-001",
        phase="spec",
        evidence_type="task_manifest",
        subject_id="manifest",
        path_scope="repo",
        relative_path=".agent/tasks/t.toml",
        producer_command="test",
    )
    write_canonical_record(
        root,
        "t",
        "t-run-001",
        phase="spec",
        evidence_type="specification_revision",
        subject_id="specification",
        payload={
            "schema_version": 1,
            "specification_revision": revision,
            "manifest_sha256": "a" * 64,
            "diagnostics": [],
        },
        producer_command="test",
    )
    return revision


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


def test_reader_uses_pinned_revision_for_repository_scoped_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "state"
    repo = tmp_path / "repo"
    _pinned_manifest_run(root, repo, monkeypatch)
    _repository_manifest(repo, "current-checkout-change")

    entries = validated_entries(root, "t", "t-run-001")

    assert [entry["evidence_type"] for entry in entries] == [
        "specification_revision",
        "task_manifest",
    ]


def test_reader_blocks_repository_scoped_evidence_without_a_specification_revision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "state"
    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.chdir(repo)
    _repository_manifest(repo)
    index_record(
        root,
        "t",
        "t-run-001",
        phase="spec",
        evidence_type="task_manifest",
        subject_id="manifest",
        path_scope="repo",
        relative_path=".agent/tasks/t.toml",
        producer_command="test",
    )

    with pytest.raises(EvidenceError, match="specification revision evidence is missing"):
        validated_entries(root, "t", "t-run-001")


def test_reader_blocks_repository_evidence_missing_from_the_pinned_revision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "state"
    repo = tmp_path / "repo"
    _pinned_manifest_run(root, repo, monkeypatch)
    specification_path = (
        root / "experiments/t/runs/t-run-001/git/specification-revision.json"
    )
    write_canonical_record(
        root,
        "t",
        "t-run-001",
        phase="spec",
        evidence_type="specification_revision",
        subject_id="specification",
        payload={
            "schema_version": 1,
            "specification_revision": "0" * 40,
            "manifest_sha256": "a" * 64,
            "diagnostics": [],
        },
        producer_command="test",
    )
    assert specification_path.is_file()

    with pytest.raises(EvidenceError, match="pinned repository evidence is unavailable"):
        validated_entries(root, "t", "t-run-001")


def test_reader_blocks_repository_evidence_with_a_pinned_digest_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "state"
    repo = tmp_path / "repo"
    _pinned_manifest_run(root, repo, monkeypatch)
    _repository_manifest(repo, "incoherent-indexed-bytes")
    index_record(
        root,
        "t",
        "t-run-001",
        phase="spec",
        evidence_type="task_manifest",
        subject_id="manifest",
        path_scope="repo",
        relative_path=".agent/tasks/t.toml",
        producer_command="test",
    )

    with pytest.raises(EvidenceError, match="evidence digest mismatch"):
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


def test_reader_requires_supersession_fields_for_superseded_task_result(tmp_path: Path) -> None:
    root = tmp_path / "state"
    relative = "experiments/t/runs/t-run-001/results/task-result.json"
    path = root / relative
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "outcome": "superseded",
                "tag": "kotekomi/tasks/t/result",
                "target_commit": "a" * 40,
                "tag_message_sha256": "b" * 64,
                "diagnostics": [],
            }
        )
    )
    index_record(
        root,
        "t",
        "t-run-001",
        phase="complete",
        evidence_type="task_result",
        subject_id="result",
        path_scope="state",
        relative_path=relative,
        producer_command="test",
    )

    with pytest.raises(EvidenceError, match="superseded task-result fields missing"):
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


def test_task_result_has_one_canonical_complete_path() -> None:
    scope, path = canonical_relative("task_result", "task", "task-run-001", "result")
    assert (scope, path) == (
        "state",
        "experiments/task/runs/task-run-001/results/task-result.json",
    )
