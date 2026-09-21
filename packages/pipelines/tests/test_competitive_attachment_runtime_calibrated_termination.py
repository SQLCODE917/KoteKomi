from __future__ import annotations

from types import SimpleNamespace
from typing import cast

import pytest
from kotekomi_application import (
    AttachmentCalibratedTerminationPreflight,
    ExecutionSetting,
    attachment_edge_filter_generation_parameters,
)
from kotekomi_pipelines.competitive_attachment_runtime_calibrated_termination import (
    build_calibrated_termination_report,
)


def test_edge_filter_can_request_two_output_tokens() -> None:
    settings = (
        ExecutionSetting("max_output_tokens", 512),
        ExecutionSetting("seed", 17),
        ExecutionSetting("temperature", 0),
        ExecutionSetting("top_logprobs", 10),
    )

    effective = attachment_edge_filter_generation_parameters(
        settings,
        effective_max_output_tokens=2,
    )

    assert {item.key: item.value for item in effective}["max_output_tokens"] == 2


def test_report_rejects_missing_repetition_observations() -> None:
    preflight = cast(AttachmentCalibratedTerminationPreflight, SimpleNamespace(tasks=()))

    with pytest.raises(ValueError, match="both repetitions"):
        build_calibrated_termination_report(
            inputs=(),
            preflight=preflight,
            observations=(),
        )
