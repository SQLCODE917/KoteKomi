"""IPI measurement records, validation, and route decision.

The package fixes one small result format for operator measurements. This module
validates that format and computes the declared measures and acceptance route
deterministically. It stores nothing and reads no product state.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

PARTITIONS = ("development", "reserved")
CONDITIONS = ("baseline", "final")
OUTCOMES = ("usable", "incorrect", "hold", "timeout", "not_attempted")
STAGES = (
    "paragraph_discovery",
    "mentions",
    "grounding",
    "event_discovery",
    "selection",
    "composition",
    "review",
    "proposal",
    "replay",
    "none",
)
CRITERIA = (
    "participants",
    "relation",
    "essential_complements",
    "polarity_modality",
    "attribution",
    "required_time_place",
    "identity_decisions",
    "evidence_replay",
    "proposal_state",
    "replay_visibility",
)


class MeasurementError(ValueError):
    """A measurement record breaks the fixed result format."""


@dataclass(frozen=True)
class StatementResult:
    """One reference statement's measured outcome in one condition."""

    reference_id: str
    outcome: str
    first_blocking_stage: str
    active_seconds: int
    waiting_seconds: int
    corrections: int
    command_retries: int = 0
    hold_reason: str | None = None
    failing_criterion: str | None = None
    event_id: str | None = None
    assertion_id: str | None = None
    proposal_id: str | None = None
    notes: str = ""


@dataclass(frozen=True)
class ConditionResult:
    """One condition's complete statement results."""

    partition: str
    condition: str
    revision: str
    operator: str
    root: str
    statements: tuple[StatementResult, ...]
    setup_waiting_seconds: int = 0
    waiting_time_accepted: bool = False


@dataclass(frozen=True)
class Measures:
    """The declared measures of one condition."""

    reference_count: int
    usable_count: int
    active_seconds: int
    waiting_seconds: int
    setup_waiting_seconds: int
    total_waiting_seconds: int
    corrections: int
    command_retries: int
    review_cost_seconds: float | None
    coverage: float

    def as_json(self) -> dict[str, Any]:
        return {
            "reference_count": self.reference_count,
            "usable_count": self.usable_count,
            "active_seconds": self.active_seconds,
            "waiting_seconds": self.waiting_seconds,
            "setup_waiting_seconds": self.setup_waiting_seconds,
            "total_waiting_seconds": self.total_waiting_seconds,
            "corrections": self.corrections,
            "command_retries": self.command_retries,
            "review_cost_seconds": self.review_cost_seconds,
            "coverage": round(self.coverage, 4),
        }


@dataclass(frozen=True)
class RouteDecision:
    """The declared acceptance routes and their outcome."""

    partition: str
    capability_route: bool
    effort_route: bool
    passed: bool
    non_regression_passed: bool
    waiting_time_passed: bool
    budget_passed: bool
    regressions: tuple[str, ...]
    incomplete_reference_ids: tuple[str, ...]
    notes: tuple[str, ...]

    def as_json(self) -> dict[str, Any]:
        return {
            "partition": self.partition,
            "capability_route": self.capability_route,
            "effort_route": self.effort_route,
            "non_regression_passed": self.non_regression_passed,
            "waiting_time_passed": self.waiting_time_passed,
            "budget_passed": self.budget_passed,
            "passed": self.passed,
            "regressions": list(self.regressions),
            "incomplete_reference_ids": list(self.incomplete_reference_ids),
            "notes": list(self.notes),
        }


def _mapping(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise MeasurementError("Each result record must be a JSON object.")
    return cast("dict[str, Any]", value)


def _require(mapping: object, key: str, kind: type) -> Any:
    view = _mapping(mapping)
    if key not in view:
        raise MeasurementError(f"Result row is missing {key}.")
    value = view[key]
    if kind is int:
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise MeasurementError(f"Result row field {key} must be a non-negative integer.")
        return value
    if not isinstance(value, kind):
        raise MeasurementError(f"Result row field {key} has the wrong type.")
    return value


def _optional_text(mapping: object, key: str) -> str | None:
    value = _mapping(mapping).get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise MeasurementError(f"Result row field {key} must be text or null.")
    return value


def _parse_statement(row: object) -> StatementResult:
    view = _mapping(row)
    reference_id = _require(view, "reference_id", str)
    outcome = _require(view, "outcome", str)
    if outcome not in OUTCOMES:
        raise MeasurementError(f"Unknown outcome {outcome!r}.")
    stage = view.get("first_blocking_stage")
    if stage not in STAGES:
        raise MeasurementError(f"Unknown first_blocking_stage {stage!r}.")
    statement = StatementResult(
        reference_id=reference_id,
        outcome=outcome,
        first_blocking_stage=stage,
        active_seconds=_require(row, "active_seconds", int),
        waiting_seconds=_require(row, "waiting_seconds", int),
        corrections=_require(row, "corrections", int),
        command_retries=_require(row, "command_retries", int),
        hold_reason=_optional_text(row, "hold_reason"),
        failing_criterion=_optional_text(row, "failing_criterion"),
        event_id=_optional_text(row, "event_id"),
        assertion_id=_optional_text(row, "assertion_id"),
        proposal_id=_optional_text(row, "proposal_id"),
        notes=_optional_text(row, "notes") or "",
    )
    _check_statement(statement)
    return statement


def _check_statement(statement: StatementResult) -> None:
    if statement.outcome == "not_attempted":
        if (
            statement.active_seconds
            or statement.waiting_seconds
            or statement.corrections
            or statement.command_retries
        ):
            raise MeasurementError(
                f"{statement.reference_id}: a not-attempted row records no effort."
            )
        return
    if statement.active_seconds <= 0:
        raise MeasurementError(f"{statement.reference_id}: attempted rows require active seconds.")
    if statement.outcome == "usable":
        if not statement.assertion_id or not statement.proposal_id:
            raise MeasurementError(
                f"{statement.reference_id}: a usable row names its Assertion and ProposedChange."
            )
        if statement.failing_criterion is not None:
            raise MeasurementError(f"{statement.reference_id}: a usable row fails no criterion.")
    if statement.outcome == "incorrect" and statement.failing_criterion not in CRITERIA:
        raise MeasurementError(
            f"{statement.reference_id}: an incorrect row names its failing criterion."
        )
    if statement.outcome == "hold" and not statement.hold_reason:
        raise MeasurementError(f"{statement.reference_id}: a held row names its hold reason.")


def load_condition_result(path: Path) -> ConditionResult:
    """Load and validate one condition result file."""
    try:
        payload: object = json.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise MeasurementError(f"Cannot read {path}: {error}") from error
    except json.JSONDecodeError as error:
        raise MeasurementError(f"{path} is not valid JSON: {error}") from error
    document = _mapping(payload)
    partition = _require(document, "partition", str)
    condition = _require(document, "condition", str)
    if partition not in PARTITIONS:
        raise MeasurementError(f"Unknown partition {partition!r}.")
    if condition not in CONDITIONS:
        raise MeasurementError(f"Unknown condition {condition!r}.")
    rows = document.get("statements")
    if not isinstance(rows, list) or not rows:
        raise MeasurementError("A condition result contains at least one statement row.")
    statements = tuple(_parse_statement(row) for row in cast("list[object]", rows))
    identifiers = [statement.reference_id for statement in statements]
    if len(set(identifiers)) != len(identifiers):
        raise MeasurementError("Reference statements are unique within one condition.")
    setup_waiting = document.get("setup_waiting_seconds", 0)
    if not isinstance(setup_waiting, int) or isinstance(setup_waiting, bool) or setup_waiting < 0:
        raise MeasurementError("setup_waiting_seconds must be a non-negative integer.")
    accepted = document.get("waiting_time_accepted", False)
    if not isinstance(accepted, bool):
        raise MeasurementError("waiting_time_accepted must be true or false.")
    return ConditionResult(
        partition=partition,
        condition=condition,
        revision=_require(document, "revision", str),
        operator=_require(document, "operator", str),
        root=_require(document, "root", str),
        statements=statements,
        setup_waiting_seconds=setup_waiting,
        waiting_time_accepted=accepted,
    )


@dataclass(frozen=True)
class ApprovedManifest:
    """The approved manifest the comparison must follow."""

    status: str
    reviewer: str
    approved_on: str
    attempt_budget_seconds: int
    reference_ids: tuple[str, ...]


def load_approved_manifest(path: Path) -> ApprovedManifest:
    """Load an approved development or sealed reserved manifest.

    The development manifest must record `status: approved`.
    The sealed reserved manifest is written only by the custody command after
    validation, so its existence records the reviewer's decision.
    """
    try:
        payload: object = json.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise MeasurementError(f"Cannot read {path}: {error}") from error
    except json.JSONDecodeError as error:
        raise MeasurementError(f"{path} is not valid JSON: {error}") from error
    document = _mapping(payload)
    record = document.get("record")
    if record == "ipi-development-manifest-v1":
        if document.get("status") != "approved":
            raise MeasurementError(
                "The development manifest is not approved; record the human decision first."
            )
        approved_on = _require(document, "approved_on", str)
    elif record == "ipi-reserved-manifest-v1":
        approved_on = _require(document, "sealed_on", str)
    else:
        raise MeasurementError("The measurement manifest has the wrong record name.")
    budget = document.get("attempt_budget_seconds")
    if not isinstance(budget, int) or isinstance(budget, bool) or budget <= 0:
        raise MeasurementError("The manifest requires a positive attempt budget in seconds.")
    reference_ids: list[str] = []
    passages = document.get("passages")
    if not isinstance(passages, list) or not passages:
        raise MeasurementError("The manifest requires at least one passage.")
    for passage in cast("list[object]", passages):
        entry = _mapping(passage)
        statements = entry.get("statements")
        if not isinstance(statements, list) or not statements:
            raise MeasurementError("Every manifest passage carries at least one statement.")
        for statement in cast("list[object]", statements):
            item = _mapping(statement)
            reference_ids.append(_require(item, "reference_id", str))
    if len(set(reference_ids)) != len(reference_ids):
        raise MeasurementError("Manifest reference identifiers are unique.")
    return ApprovedManifest(
        status="approved",
        reviewer=_require(document, "reviewer", str),
        approved_on=approved_on,
        attempt_budget_seconds=budget,
        reference_ids=tuple(reference_ids),
    )


def _require_complete_reference_set(
    result: ConditionResult, manifest: ApprovedManifest, label: str
) -> None:
    expected = set(manifest.reference_ids)
    observed = [statement.reference_id for statement in result.statements]
    if len(observed) != len(manifest.reference_ids):
        raise MeasurementError(
            f"The {label} condition records {len(observed)} statements; "
            f"the approved manifest fixes {len(manifest.reference_ids)}."
        )
    missing = expected - set(observed)
    added = set(observed) - expected
    if missing:
        raise MeasurementError(
            f"The {label} condition omits approved references: {', '.join(sorted(missing))}."
        )
    if added:
        raise MeasurementError(
            f"The {label} condition adds unapproved references: {', '.join(sorted(added))}."
        )


def _require_attempt_budget(
    result: ConditionResult, manifest: ApprovedManifest, label: str
) -> None:
    for statement in result.statements:
        if statement.outcome == "not_attempted":
            continue
        if statement.active_seconds > manifest.attempt_budget_seconds:
            raise MeasurementError(
                f"{label} {statement.reference_id}: active seconds exceed the approved "
                f"{manifest.attempt_budget_seconds}-second attempt budget."
            )


def measure(result: ConditionResult) -> Measures:
    """Compute the declared measures for one condition."""
    usable = sum(1 for item in result.statements if item.outcome == "usable")
    active = sum(item.active_seconds for item in result.statements)
    waiting = sum(item.waiting_seconds for item in result.statements)
    corrections = sum(item.corrections for item in result.statements)
    count = len(result.statements)
    return Measures(
        reference_count=count,
        usable_count=usable,
        active_seconds=active,
        waiting_seconds=waiting,
        setup_waiting_seconds=result.setup_waiting_seconds,
        total_waiting_seconds=waiting + result.setup_waiting_seconds,
        corrections=corrections,
        command_retries=sum(item.command_retries for item in result.statements),
        review_cost_seconds=None if usable == 0 else active / usable,
        coverage=0.0 if count == 0 else usable / count,
    )


def compare(
    baseline: ConditionResult, final: ConditionResult, manifest: ApprovedManifest
) -> RouteDecision:
    """Decide the declared acceptance route for one partition under the approved manifest."""
    if baseline.partition != final.partition:
        raise MeasurementError("Both conditions must measure the same partition.")
    if baseline.condition != "baseline" or final.condition != "final":
        raise MeasurementError("The comparison requires one baseline and one final condition.")
    _require_complete_reference_set(baseline, manifest, "baseline")
    _require_complete_reference_set(final, manifest, "final")
    _require_attempt_budget(baseline, manifest, "baseline")
    _require_attempt_budget(final, manifest, "final")
    baseline_measures = measure(baseline)
    final_measures = measure(final)
    final_usable = {item.reference_id for item in final.statements if item.outcome == "usable"}
    regressions = tuple(
        item.reference_id
        for item in baseline.statements
        if item.outcome == "usable" and item.reference_id not in final_usable
    )
    incomplete = tuple(
        sorted(
            {
                item.reference_id
                for item in (*baseline.statements, *final.statements)
                if item.outcome == "not_attempted"
            }
        )
    )
    notes: list[str] = []
    non_regression = not regressions
    budget_passed = True
    if incomplete:
        notes.append(
            "Not-attempted statements make the measurement incomplete: "
            + ", ".join(incomplete)
            + "."
        )
    if baseline_measures.usable_count == 0:
        baseline_budget = manifest.attempt_budget_seconds * len(manifest.reference_ids)
        budget_passed = final_measures.active_seconds <= baseline_budget
        capability = final_measures.usable_count >= 2 and budget_passed
        effort = False
        notes.append("Baseline usable coverage is zero, so only the capability route applies.")
        notes.append(
            f"Final active effort {final_measures.active_seconds}s against the "
            f"{baseline_budget}s baseline attempt budget."
        )
    else:
        baseline_cost = baseline_measures.review_cost_seconds
        final_cost = final_measures.review_cost_seconds
        assert baseline_cost is not None
        capability = (
            final_measures.usable_count - baseline_measures.usable_count >= 2
            and final_cost is not None
            and final_cost <= baseline_cost
        )
        effort = (
            final_measures.coverage >= baseline_measures.coverage
            and final_measures.usable_count >= 3
            and final_cost is not None
            and final_cost <= baseline_cost * 0.75
        )
    waiting_passed = True
    if baseline_measures.total_waiting_seconds > 0:
        ratio = final_measures.total_waiting_seconds / baseline_measures.total_waiting_seconds
        if ratio > 1.2:
            waiting_passed = final.waiting_time_accepted
            acceptance = "recorded" if final.waiting_time_accepted else "missing"
            notes.append(
                f"Waiting time rose by {(ratio - 1.0) * 100:.1f} percent; "
                f"operator acceptance is {acceptance}."
            )
    if regressions:
        notes.append("Usable reference statements were lost: " + ", ".join(regressions) + ".")
    return RouteDecision(
        partition=baseline.partition,
        capability_route=capability,
        effort_route=effort,
        passed=(capability or effort)
        and non_regression
        and waiting_passed
        and budget_passed
        and not incomplete,
        non_regression_passed=non_regression,
        waiting_time_passed=waiting_passed,
        budget_passed=budget_passed,
        regressions=regressions,
        incomplete_reference_ids=incomplete,
        notes=tuple(notes),
    )
