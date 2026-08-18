from __future__ import annotations

import hashlib
from pathlib import Path

from kotekomi_devtools.feature_branch_reconciliation import reconciliation_tag_message


def test_reconciliation_tag_message_is_canonical_json(tmp_path: Path) -> None:
    ci_result = tmp_path / "main-ci.json"
    ci_result.write_text('{"schema_version":1,"conclusion":"success","head_sha":"f"}\n')

    message = reconciliation_tag_message("task", "task-run-001", "m", "f", ci_result)

    assert message == (
        '{"final_main_commit":"f","implementation_run_id":"task-run-001",'
        f'"main_ci_sha256":"{hashlib.sha256(ci_result.read_bytes()).hexdigest()}",'
        '"outcome":"completed","promotion_commit":"m","schema_version":1,"task_id":"task"}\n'
    )
