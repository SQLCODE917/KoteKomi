"""Focused tests for the model-free R19 source-grounded deterministic selector."""

from __future__ import annotations

from pathlib import Path

import pytest
from kotekomi_application import (
    ReferencePolicyRecord,
    SourceGroundedSelectionStatus,
    frozen_semantic_selection_contract,
    load_reference_policy_records,
    select_source_grounded_constituents,
)

DATA_DIR = Path(__file__).resolve().parents[3] / "data/r17-semantic-selection-contract"

#: The R19 deterministic selector's expected selected set per residual and regression
#: Event. These match the §5 regression table and the R17 reviewed Reference policy;
#: they are asserted, never substituted into the selector.
_EXPECTED_SELECTED_SETS: dict[str, tuple[str, ...]] = {
    "AHE-022": ("C1", "C3"),
    "AHE-051": ("C3",),
    "AHE-901": ("C1", "C2"),
    "AHE-902": ("C1",),
    "AHE-903": ("C1", "C4"),
    "AHE-904": ("C1", "C2", "C3"),
    "AHE-905": ("C3", "C4"),
    "AHE-906": ("C4", "C6"),
    "AHE-907": ("C1", "C2"),
    "AHE-908": (),
    "AHE-909": ("C1", "C2"),
}


@pytest.fixture(scope="module")
def policy_records() -> tuple[ReferencePolicyRecord, ...]:
    contract = frozen_semantic_selection_contract(directory=DATA_DIR)
    return load_reference_policy_records(contract=contract, directory=DATA_DIR)


@pytest.mark.parametrize("event_id", sorted(_EXPECTED_SELECTED_SETS))
def test_selector_matches_reference_selected_set(
    policy_records: tuple[ReferencePolicyRecord, ...], event_id: str
) -> None:
    """The selector derives each reviewed Reference selected set without reading it."""
    record = next(item for item in policy_records if item.event_id == event_id)
    result = select_source_grounded_constituents(
        event_id=record.event_id,
        source_text=record.source_text,
        inventory=record.inventory,
        trigger_head_start=record.frame.trigger.start,
        trigger_head_end=record.frame.trigger.end,
        tokens=record.composition_tokens,
    )

    expected_labels = _EXPECTED_SELECTED_SETS[event_id]
    if not expected_labels:
        assert result.status is SourceGroundedSelectionStatus.EMPTY
        assert result.answer is not None
        assert result.answer.selected_label_indexes == ()
        assert result.realized_roles == ()
        return

    assert result.status is SourceGroundedSelectionStatus.SELECTED
    assert result.answer is not None
    selected = tuple(f"C{ordinal}" for ordinal in result.answer.selected_label_indexes)
    assert selected == expected_labels


def test_selector_never_substitutes_reference_set(
    policy_records: tuple[ReferencePolicyRecord, ...],
) -> None:
    """The selector transfers no reviewed values: changing them cannot redirect it."""
    record = next(item for item in policy_records if item.event_id == "AHE-022")
    result = select_source_grounded_constituents(
        event_id=record.event_id,
        source_text=record.source_text,
        inventory=record.inventory,
        trigger_head_start=record.frame.trigger.start,
        trigger_head_end=record.frame.trigger.end,
        tokens=record.composition_tokens,
    )
    assert result.answer is not None
    assert tuple(result.answer.selected_label_indexes) == (1, 3)
    # The selector signature accepts no Reference selected set or expected range.
    assert result.realized_roles and all(role.conjuncts for role in result.realized_roles)
