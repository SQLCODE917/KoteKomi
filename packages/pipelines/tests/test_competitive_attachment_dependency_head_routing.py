from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

import pytest
from kotekomi_application import (
    AttachmentHeadRoute,
    AttachmentHeadRoutingOutcome,
    classify_dependency_head_routing_outcome,
)
from kotekomi_pipelines.competitive_attachment_dependency_head_routing import (
    render_dependency_head_routing_review,
)


@pytest.mark.parametrize(
    (
        "development_accuracy",
        "validation_baseline",
        "validation_accuracy",
        "expected",
    ),
    (
        (0.9, 5 / 7, 1.0, AttachmentHeadRoutingOutcome.SUPPORTED),
        (0.8, 5 / 7, 1.0, AttachmentHeadRoutingOutcome.MIXED),
        (0.9, 5 / 7, 5 / 7, AttachmentHeadRoutingOutcome.FALSIFIED),
    ),
)
def test_dependency_head_terminal_outcomes(
    development_accuracy: float,
    validation_baseline: float,
    validation_accuracy: float,
    expected: AttachmentHeadRoutingOutcome,
) -> None:
    development = _phase(
        baseline_accuracy=0.9,
        routed_accuracy=development_accuracy,
    )
    validation = _phase(
        baseline_accuracy=validation_baseline,
        routed_accuracy=validation_accuracy,
    )

    assert (
        classify_dependency_head_routing_outcome(
            development,
            validation,
        )
        is expected
    )


def test_head_aligned_gold_negative_falsifies_route() -> None:
    negative = SimpleNamespace(
        route=AttachmentHeadRoute.STRUCTURAL,
        transfer_case=SimpleNamespace(gold=SimpleNamespace(expected_answer="N")),
    )
    development = _phase(baseline_accuracy=0.9, routed_accuracy=0.9)
    validation = _phase(
        baseline_accuracy=5 / 7,
        routed_accuracy=1.0,
        cases=(negative,),
    )

    assert (
        classify_dependency_head_routing_outcome(
            development,
            validation,
        )
        is AttachmentHeadRoutingOutcome.FALSIFIED
    )


def test_review_derives_head_aligned_negative_coverage() -> None:
    metric = SimpleNamespace(accuracy=1.0)
    development = SimpleNamespace(
        phase="development",
        baseline_metrics=(metric, metric),
        routed_metrics=(metric, metric),
        recovered_count=0,
        regressed_count=0,
        head_aligned_negative_count=2,
        cases=(),
    )
    validation = SimpleNamespace(
        phase="validation",
        baseline_metrics=(metric, metric),
        routed_metrics=(metric, metric),
        recovered_count=0,
        regressed_count=0,
        head_aligned_negative_count=1,
        cases=(),
    )
    report = cast(
        Any,
        SimpleNamespace(
            outcome=AttachmentHeadRoutingOutcome.FALSIFIED,
            structural_route_count=3,
            semantic_route_count=0,
            projected_model_call_reduction=1.0,
            development=development,
            validation=validation,
        ),
    )

    rendered = render_dependency_head_routing_review(report)

    assert "Head-Aligned Gold-negative coverage: `3`" in rendered


def _phase(
    *,
    baseline_accuracy: float,
    routed_accuracy: float,
    cases: tuple[object, ...] = (),
) -> Any:
    baseline = SimpleNamespace(accuracy=baseline_accuracy, false_positive_count=0)
    routed = SimpleNamespace(accuracy=routed_accuracy, false_positive_count=0)
    return cast(
        Any,
        SimpleNamespace(
            cases=cases,
            baseline_metrics=(baseline, baseline),
            routed_metrics=(routed, routed),
        ),
    )
