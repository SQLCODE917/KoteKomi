from __future__ import annotations

from kotekomi_devtools.cli import _build_parser
from kotekomi_devtools.feature_branch_promotion import FeatureBranchResult


def test_promotion_and_completion_commands_require_one_canonical_run() -> None:
    parser = _build_parser()
    for command in (
        "promote-feature-branch",
        "complete-feature-branch",
        "abandon-feature-branch",
    ):
        arguments = parser.parse_args(
            [command, "--task-id", "feature-task", "--run", "feature-task-run-001"]
        )
        assert arguments.task_id == "feature-task"
        assert arguments.run == "feature-task-run-001"


def test_feature_branch_result_keeps_machine_output_explicit() -> None:
    result = FeatureBranchResult(0, {"schema_version": 1, "status": "promoted"})

    assert result.exit_code == 0
    assert result.payload == {"schema_version": 1, "status": "promoted"}
