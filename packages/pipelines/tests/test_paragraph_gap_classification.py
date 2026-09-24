from __future__ import annotations

import pytest
from kotekomi_application import (
    HybridParagraphStageRecord,
    HybridStageDisposition,
    HybridStageId,
)
from kotekomi_pipelines.current_hybrid_evaluation import (
    HybridParagraphGapBreakdown,
    HybridParagraphGapClass,
    classify_hybrid_paragraph_gap,
)


def test_classify_an_all_complete_paragraph() -> None:
    assert (
        classify_hybrid_paragraph_gap(_stages())
        is HybridParagraphGapClass.COMPLETE
    )


def test_classify_hp1_partial_wins_over_hp3_and_hp10() -> None:
    assert (
        classify_hybrid_paragraph_gap(_stages(hp1="partial", hp3="partial", hp10="partial"))
        is HybridParagraphGapClass.PROPOSAL_REJECTED
    )


def test_classify_hp3_partial_with_a_complete_hp1() -> None:
    assert (
        classify_hybrid_paragraph_gap(_stages(hp3="partial"))
        is HybridParagraphGapClass.INHERITED_PARTIAL
    )


def test_classify_hp10_partial_boundary_held_by_line_rejection() -> None:
    assert (
        classify_hybrid_paragraph_gap(
            _stages(
                hp10="partial",
                hp10_diagnostics=("standing_fact_line_rejected:seg_a:1:literal",),
            )
        )
        is HybridParagraphGapClass.BOUNDARY_HELD
    )


def test_classify_hp10_partial_boundary_held_by_non_route_reason() -> None:
    assert (
        classify_hybrid_paragraph_gap(
            _stages(
                hp10="partial",
                hp10_diagnostics=(
                    "held_standing_facts:1",
                    "standing_fact_held:sfd_a:relation_overlaps_mention",
                ),
            )
        )
        is HybridParagraphGapClass.BOUNDARY_HELD
    )


def test_classify_hp10_partial_boundary_held_beats_route() -> None:
    assert (
        classify_hybrid_paragraph_gap(
            _stages(
                hp10="partial",
                hp10_diagnostics=(
                    "standing_fact_held:sfd_a:event_route_required",
                    "standing_fact_held:sfd_b:proposition_not_source_ordered",
                ),
            )
        )
        is HybridParagraphGapClass.BOUNDARY_HELD
    )


def test_classify_hp10_partial_routed() -> None:
    assert (
        classify_hybrid_paragraph_gap(
            _stages(
                hp10="partial",
                hp10_diagnostics=("standing_fact_held:sfd_a:event_route_required",),
            )
        )
        is HybridParagraphGapClass.ROUTED
    )


def test_classify_hp10_partial_held_without_reason() -> None:
    assert (
        classify_hybrid_paragraph_gap(
            _stages(hp10="partial", hp10_diagnostics=("held_standing_facts:2",))
        )
        is HybridParagraphGapClass.HELD
    )


def test_classify_hp10_partial_held_for_complete_propositions() -> None:
    assert (
        classify_hybrid_paragraph_gap(
            _stages(
                hp10="partial",
                hp10_diagnostics=("standing_fact_held:sfd_a:complete_proposition_held",),
            )
        )
        is HybridParagraphGapClass.HELD
    )


def test_classify_raises_on_a_not_run_stage() -> None:
    stages = _stages()
    stages = (
        stages[0].model_copy(update={"disposition": HybridStageDisposition.NOT_RUN}),
    ) + stages[1:]

    with pytest.raises(ValueError, match="not-run"):
        classify_hybrid_paragraph_gap(stages)


def test_classify_raises_on_a_blocked_terminal_status() -> None:
    stages = _stages(hp1="blocked")

    with pytest.raises(ValueError, match="terminal status"):
        classify_hybrid_paragraph_gap(stages)


def test_breakdown_from_classes() -> None:
    breakdown = HybridParagraphGapBreakdown.from_classes(
        (
            HybridParagraphGapClass.COMPLETE,
            HybridParagraphGapClass.COMPLETE,
            HybridParagraphGapClass.PROPOSAL_REJECTED,
            HybridParagraphGapClass.BOUNDARY_HELD,
            HybridParagraphGapClass.ROUTED,
        )
    )

    assert breakdown.model_dump(mode="json") == {
        "proposal_rejected": 1,
        "boundary_held": 1,
        "routed": 1,
        "held": 0,
        "inherited_partial": 0,
    }
    assert breakdown.total == 3


def _stages(
    *,
    hp1: str = "complete",
    hp3: str = "complete",
    hp10: str = "complete",
    hp10_diagnostics: tuple[str, ...] = (),
) -> tuple[HybridParagraphStageRecord, ...]:
    overrides = {
        HybridStageId.HP1_MENTIONS: hp1,
        HybridStageId.HP3_GROUNDING: hp3,
        HybridStageId.HP10_STANDING_FACTS: hp10,
    }
    return tuple(
        _stage(
            stage_id,
            overrides.get(stage_id, "complete"),
            hp10_diagnostics if stage_id is HybridStageId.HP10_STANDING_FACTS else (),
        )
        for stage_id in HybridStageId
    )


def _stage(
    stage_id: HybridStageId,
    terminal_status: str,
    diagnostics: tuple[str, ...] = (),
) -> HybridParagraphStageRecord:
    return HybridParagraphStageRecord(
        stage_id=stage_id,
        disposition=HybridStageDisposition.CREATED,
        output_id=f"out_{stage_id.value}",
        output_sha256="a" * 64,
        terminal_status=terminal_status,
        diagnostics=diagnostics,
    )