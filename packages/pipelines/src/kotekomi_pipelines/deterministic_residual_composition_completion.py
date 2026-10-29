"""R19 deterministic residual composition completion Pipeline.

The Pipeline seals one inspectable report per residual. Each record combines the
generated selection, the frozen R17 selection signal, the production composition
result, the constructed Assertion, the evidence support check, and the supporting
source spans. R19 executes zero models, writes zero canonical state, and records
zero ProposedChanges.
"""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from typing import Annotated, Literal, Self

from kotekomi_application import (
    AssertionConstructionOutcome,
    AssertionConstructionStatus,
    AttachmentSourceRange,
    DeterministicResidualCompositionOutcome,
    DeterministicResidualCompositionStatus,
    ReferencePolicyRecord,
)
from kotekomi_application.evidence_targets import (
    EvidenceTargetLedger,
    validate_evidence_target_record,
)
from kotekomi_domain import Assertion
from pydantic import BaseModel, ConfigDict, Field, model_validator

_SHA256 = r"^[a-f0-9]{64}$"
_EVENT_ID = r"^(TGE|AHE)-[0-9]{3}$"


class ResidualTerminalStatus(StrEnum):
    """Terminal status of one residual through the production path."""

    CLOSED = "closed"
    BLOCKED = "blocked"


class ResidualClosureRecord(BaseModel):
    """One residual's full production record with separate measurements."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    event_id: Annotated[str, Field(pattern=_EVENT_ID)]
    terminal_status: ResidualTerminalStatus
    r17_selection_signal: Literal["met", "unmet", "not_applicable"]
    composition_status: DeterministicResidualCompositionStatus
    composition_hold_reason: Annotated[str, Field(min_length=1)] | None = None
    assertion_status: AssertionConstructionStatus
    assertion: Assertion | None = None
    block_reason: Annotated[str, Field(min_length=1)] | None = None
    evidence_supported: bool
    supporting_subject_span: AttachmentSourceRange | None = None
    supporting_object_span: AttachmentSourceRange | None = None

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if self.terminal_status is ResidualTerminalStatus.CLOSED:
            if self.composition_status is not DeterministicResidualCompositionStatus.COMPOSED:
                raise ValueError("A closed residual requires composed selection and composition.")
            if self.r17_selection_signal != "met":
                raise ValueError("A closed residual requires the R17 selection signal met.")
            if (
                self.assertion is None
                or self.assertion_status is not AssertionConstructionStatus.CONSTRUCTED
            ):
                raise ValueError("A closed residual requires a constructed Assertion.")
            if not self.evidence_supported:
                raise ValueError("A closed residual requires supported evidence.")
            if self.block_reason is not None:
                raise ValueError("A closed residual cannot carry a block reason.")
        elif self.block_reason is None:
            raise ValueError("A blocked residual requires one block reason.")
        return self


class DeterministicResidualCompositionReport(BaseModel):
    """One sealed R19 production report with zero executions and zero writes."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["r19_residual_composition_report_v1"] = (
        "r19_residual_composition_report_v1"
    )
    report_id: Annotated[str, Field(min_length=1)]
    residuals: tuple[ResidualClosureRecord, ...]
    model_execution_count: Literal[0]
    canonical_write_count: Literal[0]
    proposed_change_count: Literal[0]
    result_fingerprint: Annotated[str, Field(pattern=_SHA256)]

    @model_validator(mode="after")
    def validate_distinctness(self) -> Self:
        event_ids = tuple(item.event_id for item in self.residuals)
        if tuple(sorted(set(event_ids))) != event_ids:
            raise ValueError("Report residuals must be ordered and distinct.")
        return self


def report_fingerprint(report: DeterministicResidualCompositionReport) -> str:
    payload = report.model_dump(mode="json", exclude={"result_fingerprint"})
    return hashlib.sha256(
        json.dumps(payload, allow_nan=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def build_deterministic_residual_composition_report(
    *,
    report_id: str,
    residuals: tuple[ResidualClosureRecord, ...],
) -> DeterministicResidualCompositionReport:
    draft = DeterministicResidualCompositionReport.model_construct(
        schema_version="r19_residual_composition_report_v1",
        report_id=report_id,
        residuals=residuals,
        model_execution_count=0,
        canonical_write_count=0,
        proposed_change_count=0,
        result_fingerprint="0" * 64,
    )
    return DeterministicResidualCompositionReport(
        **draft.model_dump(exclude={"result_fingerprint"}),
        result_fingerprint=report_fingerprint(draft),
    )


def r17_selection_signal(
    selected_indexes: tuple[int, ...],
    policy_record: ReferencePolicyRecord,
) -> Literal["met", "unmet"]:
    """Apply the frozen R17 expected selected set to the generated selection."""
    selected_labels = tuple(f"C{index}" for index in selected_indexes)
    if selected_labels == policy_record.expected_selected_set:
        return "met"
    return "unmet"


def verify_evidence_support(
    repository: EvidenceTargetLedger,
    *,
    source_id: str,
    evidence_target_id: str,
    source_text: str,
) -> bool:
    """Verify one EvidenceTarget replays against the archived representation.

    A matching source_id or exact_text alone is insufficient. The target must
    resolve through the pinned DocumentRepresentation, text view, position
    selector, and structural selectors via the existing evidence-validation path.
    """
    target = repository.get_evidence_target(evidence_target_id)
    if target is None:
        return False
    if target.source_id != source_id:
        return False
    if target.exact_text != source_text:
        return False
    try:
        validate_evidence_target_record(target, repository)
    except ValueError:
        return False
    return True


def close_residual(
    *,
    event_id: str,
    policy_record: ReferencePolicyRecord,
    composition: DeterministicResidualCompositionOutcome,
    assertion: AssertionConstructionOutcome,
    evidence_supported: bool,
) -> ResidualClosureRecord:
    answer = composition.selection.answer
    selected_indexes = tuple(answer.selected_label_indexes) if answer is not None else ()
    r17_signal = r17_selection_signal(selected_indexes, policy_record)

    proposition = composition.proposition
    hold_reason = (
        proposition.hold_reason.value
        if proposition is not None and proposition.hold_reason is not None
        else None
    )
    assertion_ok = assertion.status is AssertionConstructionStatus.CONSTRUCTED

    if (
        composition.status is DeterministicResidualCompositionStatus.COMPOSED
        and r17_signal == "met"
        and assertion_ok
        and evidence_supported
    ):
        terminal = ResidualTerminalStatus.CLOSED
        block_reason = None
    else:
        terminal = ResidualTerminalStatus.BLOCKED
        block_reason = _block_reason(composition, assertion, evidence_supported)

    return ResidualClosureRecord(
        event_id=event_id,
        terminal_status=terminal,
        r17_selection_signal=r17_signal,
        composition_status=composition.status,
        composition_hold_reason=hold_reason,
        assertion_status=assertion.status,
        assertion=assertion.assertion,
        block_reason=block_reason,
        evidence_supported=evidence_supported,
        supporting_subject_span=(
            proposition.subject.exact_fragment
            if proposition is not None and proposition.subject is not None
            else None
        ),
        supporting_object_span=(
            proposition.object.exact_fragment
            if proposition is not None and proposition.object is not None
            else None
        ),
    )


def _block_reason(
    composition: DeterministicResidualCompositionOutcome,
    assertion: AssertionConstructionOutcome,
    evidence_supported: bool,
) -> str:
    if composition.status is DeterministicResidualCompositionStatus.SELECTION_GAP:
        return "selection_gap"
    if composition.status is DeterministicResidualCompositionStatus.COMPOSITION_HELD:
        proposition = composition.proposition
        if proposition is not None and proposition.hold_reason is not None:
            return proposition.hold_reason.value
        return "composition_held"
    if assertion.status is AssertionConstructionStatus.BLOCKED:
        if assertion.block_reason is not None:
            return assertion.block_reason.value
        return "assertion_blocked"
    if not evidence_supported:
        return "evidence_unsupported"
    return "blocked"
