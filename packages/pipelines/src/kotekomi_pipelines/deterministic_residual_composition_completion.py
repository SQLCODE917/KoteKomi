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
from collections.abc import Callable
from enum import StrEnum
from typing import Annotated, Literal, Self

from kotekomi_application import (
    AssertionBlockReason,
    AssertionConstructionInputs,
    AssertionConstructionOutcome,
    AssertionConstructionStatus,
    AttachmentSourceRange,
    DeterministicResidualCompositionOutcome,
    DeterministicResidualCompositionStatus,
    ReferencePolicyRecord,
    complete_deterministic_residual_composition,
    construct_inspectable_assertion,
)
from kotekomi_application.event_entity_reference_provider import (
    EventEntityReferenceProvider,
)
from kotekomi_application.evidence_targets import (
    EvidenceTargetLedger,
    validate_evidence_target_record,
)
from kotekomi_application.ports import LedgerRepository
from kotekomi_domain import Assertion, AssertionType, AttributionBasis, SourceAuthority
from pydantic import BaseModel, ConfigDict, Field, model_validator

from kotekomi_pipelines.r19_provider_supplement import (
    R19ProviderSupplement,
    require_approved_supplement,
    require_resolved_closure,
)

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
    composition_status: DeterministicResidualCompositionStatus | None = None
    composition_hold_reason: Annotated[str, Field(min_length=1)] | None = None
    assertion_status: AssertionConstructionStatus | None = None
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
    if _strip_whitespace(target.exact_text) != _strip_whitespace(source_text):
        return False
    try:
        validate_evidence_target_record(target, repository)
    except ValueError:
        return False
    return True


def _strip_whitespace(value: str) -> str:
    return "".join(char for char in value if not char.isspace())


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


def run_deterministic_residual_composition(
    *,
    report_id: str,
    supplement: R19ProviderSupplement,
    policy_records: tuple[ReferencePolicyRecord, ...],
    closure_ledger: LedgerRepository,
    evidence_ledger: EvidenceTargetLedger,
    build_provider: Callable[[str, str, str], EventEntityReferenceProvider],
) -> DeterministicResidualCompositionReport:
    """Run the gated R19 production path over every residual Event.

    The approval and resolved-closure gates run first. When either fails, every
    residual records the same typed block reason and no composition runs. When
    both pass, each Event composes, scores, constructs, and validates evidence.
    """
    gate_reason = _gate_reason(supplement, closure_ledger)
    predicate_by_label = {
        item.relation_label: item.predicate for item in supplement.predicate_mappings
    }
    identity_by_entity = {
        item.entity_id: resolved
        for item in supplement.identity_mappings
        if (resolved := item.actor_id or item.organization_id) is not None
    }
    evidence_by_event = {item.event_id: item for item in supplement.event_evidence}

    records: list[ResidualClosureRecord] = []
    for policy in sorted(policy_records, key=lambda item: item.event_id):
        if gate_reason is not None:
            records.append(_gate_blocked(policy.event_id, gate_reason))
            continue
        records.append(
            _close_one(
                policy,
                predicate_by_label=predicate_by_label,
                identity_by_entity=identity_by_entity,
                evidence=evidence_by_event[policy.event_id],
                evidence_ledger=evidence_ledger,
                build_provider=build_provider,
            )
        )
    return build_deterministic_residual_composition_report(
        report_id=report_id,
        residuals=tuple(records),
    )


def _gate_reason(
    supplement: R19ProviderSupplement,
    closure_ledger: LedgerRepository,
) -> str | None:
    try:
        require_approved_supplement(supplement)
    except ValueError:
        return "supplement_unapproved"
    try:
        require_resolved_closure(supplement, closure_ledger)
    except ValueError:
        return "unresolved_references"
    return None


def _gate_blocked(event_id: str, block_reason: str) -> ResidualClosureRecord:
    return ResidualClosureRecord(
        event_id=event_id,
        terminal_status=ResidualTerminalStatus.BLOCKED,
        r17_selection_signal="not_applicable",
        block_reason=block_reason,
        evidence_supported=False,
    )


def _close_one(
    policy: ReferencePolicyRecord,
    *,
    predicate_by_label: dict[str, str],
    identity_by_entity: dict[str, str],
    evidence: object,
    evidence_ledger: EvidenceTargetLedger,
    build_provider: Callable[[str, str, str], EventEntityReferenceProvider],
) -> ResidualClosureRecord:
    provider = build_provider(
        policy.event_id, policy.source_text, policy.input_binding.source_sha256
    )
    composition = complete_deterministic_residual_composition(
        event_id=policy.event_id,
        source_text=policy.source_text,
        source_text_sha256=policy.input_binding.source_sha256,
        inventory=policy.inventory,
        trigger_head_start=policy.frame.trigger.start,
        trigger_head_end=policy.frame.trigger.end,
        tokens=policy.composition_tokens,
        provider=provider,
    )

    assertion: AssertionConstructionOutcome
    if (
        composition.status is DeterministicResidualCompositionStatus.COMPOSED
        and composition.proposition is not None
    ):
        source_id = _str_field(evidence, "source_id")
        evidence_target_id = _str_field(evidence, "evidence_target_id")
        inputs = AssertionConstructionInputs(
            predicate_by_label=predicate_by_label,
            identity_by_entity=identity_by_entity,
            assertion_type=AssertionType.REPORTED_OBSERVATION,
            source_authority=SourceAuthority(_str_field(evidence, "source_authority")),
            attribution_basis=AttributionBasis(_str_field(evidence, "attribution_basis")),
            source_id=source_id,
            evidence_target_id=evidence_target_id,
        )
        assertion = construct_inspectable_assertion(composition.proposition, inputs)
        evidence_supported = verify_evidence_support(
            evidence_ledger,
            source_id=source_id,
            evidence_target_id=evidence_target_id,
            source_text=policy.source_text,
        )
    else:
        assertion = AssertionConstructionOutcome(
            event_id=policy.event_id,
            status=AssertionConstructionStatus.BLOCKED,
            block_reason=AssertionBlockReason.PROPOSITION_REQUIRED,
        )
        evidence_supported = False

    return close_residual(
        event_id=policy.event_id,
        policy_record=policy,
        composition=composition,
        assertion=assertion,
        evidence_supported=evidence_supported,
    )


def _str_field(record: object, field: str) -> str:
    value = getattr(record, field)
    if value is None:
        raise ValueError(f"Resolved supplement field {field} is missing.")
    return str(value)
