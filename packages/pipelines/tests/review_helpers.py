from collections.abc import Callable
from pathlib import Path

from kotekomi_domain import ProposedChange

REVIEW_RECORD_TYPE_ORDER = {
    "Organization": 0,
    "Actor": 1,
    "Event": 2,
    "EvidenceSpan": 3,
    "Assertion": 4,
    "Relationship": 5,
    "Outcome": 6,
    "ArgumentEdge": 7,
}


def proposed_changes_in_review_order(
    proposed_changes: tuple[ProposedChange, ...],
) -> tuple[ProposedChange, ...]:
    return tuple(
        sorted(
            proposed_changes,
            key=lambda change: (
                REVIEW_RECORD_TYPE_ORDER[record_type(change)],
                stable_label(change),
            ),
        )
    )


def approve_proposed_changes_in_review_order(
    *,
    ledger_path: Path,
    proposed_changes: tuple[ProposedChange, ...],
    main: Callable[[list[str]], int],
    review_approve_args: Callable[[Path, str], list[str]],
    clear_output: Callable[[], object],
) -> None:
    for proposed_change in proposed_changes_in_review_order(proposed_changes):
        assert main(review_approve_args(ledger_path, proposed_change.id)) == 0
        clear_output()


def record_type(proposed_change: ProposedChange) -> str:
    value = proposed_change.proposed_json["record_type"]
    assert isinstance(value, str)
    return value


def stable_label(proposed_change: ProposedChange) -> str:
    value = proposed_change.proposed_json["stable_label"]
    assert isinstance(value, str)
    return value
