from __future__ import annotations

from pathlib import Path

from kotekomi_devtools.candidate_verifier import CandidateVerificationResult, verify_candidate
from pytest import MonkeyPatch


def test_verify_candidate_rejects_unknown_profile_before_git_lookup(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    result = verify_candidate(
        Path(".agent/tasks/task.toml"),
        base_revision="base",
        specification_revision="specification",
        candidate_revision="candidate",
        profile="unknown",
    )

    assert result.exit_code == 2
    assert result.as_json()["diagnostics"] == [
        {
            "code": "profile_invalid",
            "location": "/profile",
            "rule": "known_verification_profile",
        }
    ]


def test_invalid_result_has_no_receipt_reference() -> None:
    result = CandidateVerificationResult(
        "invalid",
        None,
        "portable-local",
        None,
        None,
        None,
        None,
        None,
        (),
    )

    assert result.exit_code == 2
    assert result.as_json()["receipt_path"] is None
