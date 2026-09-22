from __future__ import annotations

from typing import Literal

import pytest
from kotekomi_application import AttachmentGoldAuthority, AttachmentStructuralSafetyReport
from kotekomi_pipelines.competitive_attachment_structural_route_safety import (
    select_attachment_effective_gold,
    validate_attachment_structural_safety_frozen_inventory,
)


@pytest.mark.parametrize(
    ("original", "reviewed", "expected"),
    (
        ("N", "Y", ("Y", AttachmentGoldAuthority.REVIEWED, True)),
        ("Y", "Y", ("Y", AttachmentGoldAuthority.REVIEWED, False)),
        ("N", None, ("N", AttachmentGoldAuthority.ORIGINAL, False)),
    ),
)
def test_effective_gold_uses_the_exact_reviewed_answer(
    original: Literal["Y", "N"],
    reviewed: Literal["Y", "N"] | None,
    expected: tuple[Literal["Y", "N"], AttachmentGoldAuthority, bool],
) -> None:
    assert (
        select_attachment_effective_gold(
            original=original,
            reviewed=reviewed,
        )
        == expected
    )


def test_frozen_inventory_validation_rejects_drift() -> None:
    report = AttachmentStructuralSafetyReport.model_construct(
        total_edge_count=934,
        head_aligned_count=58,
        gold_conflict_count=3,
        foreign_event_exclusion_count=5,
        eligible_count=53,
    )

    with pytest.raises(ValueError, match="frozen inventory counts drifted"):
        validate_attachment_structural_safety_frozen_inventory(report)
