from kotekomi_devtools.tdd_scorecards import score_metrics


def test_scorecard_penalizes_missing_evidence_and_zero_planned_checks() -> None:
    result = score_metrics(
        {
            "task_id": "t",
            "primary_tdd_path": "t.md",
            "tdd_paths": ["t.md"],
            "tdd_sha256": "a" * 64,
            "implementation_run_id": "t-run-001",
            "status": "partial",
            "receipt_missing_count": 0,
            "digest_mismatch_count": 0,
            "missing_evidence_count": 2,
            "planned_check_count": 0,
            "verified_check_count": 0,
            "repair_count": 0,
            "failed_check_count": 0,
            "candidate_lifecycle_ready": True,
            "main_lifecycle_ready": True,
            "candidate_ci_conclusion": "success",
            "main_ci_conclusion": "success",
            "branch_cleanup_complete": True,
            "budget_violation_count": 0,
            "protected_artifact_violation_count": 0,
        }
    )
    assert result["score_dimensions"]["verification_completeness"] == 100
    assert result["score_dimensions"]["evidence_confidence"] == 70
