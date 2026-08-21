from kotekomi_devtools.tdd_scorecards import score_metrics


def test_superseded_scorecard_has_no_implementation_quality_score() -> None:
    result = score_metrics(
        {
            "task_id": "t",
            "primary_tdd_path": "t.md",
            "tdd_paths": ["t.md"],
            "tdd_sha256": "a" * 64,
            "implementation_run_id": "t-run-001",
            "status": "superseded",
            "diagnostics": [],
        }
    )

    assert result["score_dimensions"] == {}
    assert result["overall_score"] is None
    assert result["ranking_eligible"] is False


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
            "repair_history_available": True,
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
    assert result["omitted_score_dimensions"] == []
    assert result["scored_weight_total"] == 1.0


def test_scorecard_omits_and_reweights_repair_dimensions_when_history_is_unavailable() -> None:
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
            "missing_evidence_count": 0,
            "planned_check_count": 0,
            "verified_check_count": 0,
            "repair_count": 0,
            "repair_history_available": False,
            "failed_check_count": 0,
            "candidate_lifecycle_ready": True,
            "main_lifecycle_ready": True,
            "candidate_ci_conclusion": "success",
            "main_ci_conclusion": "success",
            "branch_cleanup_complete": True,
            "budget_violation_count": 0,
            "protected_artifact_violation_count": 0,
            "diagnostics": [],
        }
    )
    assert result["omitted_score_dimensions"] == [
        "first_pass_effectiveness",
        "repair_efficiency",
    ]
    assert "first_pass_effectiveness" not in result["score_dimensions"]
    assert "repair_efficiency" not in result["score_dimensions"]
    assert result["scored_weight_total"] == 0.75
    assert result["provisional_overall_score"] == 100
    assert result["overall_score"] == 100
    assert "scorecard.repair_history_unavailable" in {
        item["code"] for item in result["diagnostics"]
    }
