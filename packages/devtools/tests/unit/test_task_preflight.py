from __future__ import annotations

from kotekomi_devtools.task_preflight import preflight_task


def test_stage_one_path_diagnostics_are_complete_and_stably_sorted() -> None:
    result = preflight_task("~/")

    assert result.as_json()["diagnostics"] == [
        {
            "code": "task_preflight.manifest_path_violation",
            "location": "/manifest_path",
            "rule": "exact_file",
        },
        {
            "code": "task_preflight.manifest_path_violation",
            "location": "/manifest_path",
            "rule": "repository_relative_posix",
        },
    ]
