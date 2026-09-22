from __future__ import annotations

import hashlib
from typing import Literal

import pytest
from kotekomi_application import (
    AttachmentExactSelfCase,
    AttachmentSelfRoutingOutcome,
    AttachmentSourceRange,
    classify_attachment_self_routing_outcome,
)


def test_equal_source_ranges_construct_exact_self_attachment() -> None:
    result = _case(candidate=(6, 14), event=(6, 14), original_gold="Y")

    assert result.answer == "Y"
    assert result.original_gold_correct is True


def test_unequal_source_ranges_cannot_enter_exact_self_inventory() -> None:
    with pytest.raises(ValueError, match="requires equal source ranges"):
        _case(candidate=(0, 14), event=(6, 14), original_gold="Y")


def test_original_negative_remains_a_constructible_falsifying_case() -> None:
    result = _case(candidate=(6, 14), event=(6, 14), original_gold="N")

    assert result.original_gold_correct is False


@pytest.mark.parametrize(
    ("negative_count", "routed_control_count", "expected"),
    (
        (0, 0, AttachmentSelfRoutingOutcome.SUPPORTED),
        (0, 1, AttachmentSelfRoutingOutcome.MIXED),
        (1, 0, AttachmentSelfRoutingOutcome.FALSIFIED),
        (1, 1, AttachmentSelfRoutingOutcome.FALSIFIED),
    ),
)
def test_exact_self_routing_terminal_outcomes(
    negative_count: int,
    routed_control_count: int,
    expected: AttachmentSelfRoutingOutcome,
) -> None:
    assert (
        classify_attachment_self_routing_outcome(
            exact_self_original_negative_count=negative_count,
            routed_reviewed_negative_control_count=routed_control_count,
        )
        is expected
    )


def _case(
    *,
    candidate: tuple[int, int],
    event: tuple[int, int],
    original_gold: Literal["Y", "N"],
) -> AttachmentExactSelfCase:
    source = "Alpha targeted Beta."
    return AttachmentExactSelfCase(
        phase="development",
        matrix_id="cam_" + "1" * 24,
        source_text=source,
        source_text_sha256=hashlib.sha256(source.encode()).hexdigest(),
        candidate_id="cac_" + "2" * 24,
        event_id="sge_" + "3" * 24,
        candidate_range=AttachmentSourceRange(
            start=candidate[0],
            end=candidate[1],
            text=source[candidate[0] : candidate[1]],
        ),
        event_range=AttachmentSourceRange(
            start=event[0],
            end=event[1],
            text=source[event[0] : event[1]],
        ),
        original_gold=original_gold,
        reviewed_gold=None,
        gold_conflict=False,
        original_gold_correct=original_gold == "Y",
    )
