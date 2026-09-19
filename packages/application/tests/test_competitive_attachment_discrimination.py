from __future__ import annotations

import pytest
from kotekomi_application import (
    CompetitiveAttachmentFailureShape,
    attachment_set_is_prefix,
    attachment_set_jaccard,
    competitive_attachment_failure_shape,
)


@pytest.mark.parametrize(
    ("gold", "predicted", "expected"),
    (
        (("sge_a",), (), CompetitiveAttachmentFailureShape.COMPLETE_OMISSION),
        (
            ("sge_a", "sge_b"),
            ("sge_a",),
            CompetitiveAttachmentFailureShape.UNDER_ATTACHMENT,
        ),
        ((), ("sge_a",), CompetitiveAttachmentFailureShape.FALSE_POSITIVE_NONE),
        (
            ("sge_a",),
            ("sge_a", "sge_b"),
            CompetitiveAttachmentFailureShape.OVER_ATTACHMENT,
        ),
        (
            ("sge_a",),
            ("sge_b",),
            CompetitiveAttachmentFailureShape.WRONG_SET_SUBSTITUTION,
        ),
    ),
)
def test_failure_shape_preserves_exact_set_relation(
    gold: tuple[str, ...],
    predicted: tuple[str, ...],
    expected: CompetitiveAttachmentFailureShape,
) -> None:
    assert competitive_attachment_failure_shape(gold, predicted) is expected


def test_failure_shape_rejects_an_exact_attachment_set() -> None:
    with pytest.raises(ValueError, match="exact Attachment Set"):
        competitive_attachment_failure_shape(("sge_a",), ("sge_a",))


def test_jaccard_treats_two_empty_attachment_sets_as_exact() -> None:
    assert attachment_set_jaccard((), ()) == 1.0
    assert attachment_set_jaccard(("sge_a", "sge_b"), ("sge_b", "sge_c")) == 1 / 3


def test_prefix_observation_is_set_based_against_canonical_event_order() -> None:
    canonical = ("sge_a", "sge_b", "sge_c")

    assert attachment_set_is_prefix(("sge_b", "sge_a"), canonical) is True
    assert attachment_set_is_prefix(("sge_a", "sge_c"), canonical) is False
    assert attachment_set_is_prefix((), canonical) is False
