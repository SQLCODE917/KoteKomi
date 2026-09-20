"""Typed CEA-1.6 evidence for occurrence-level attachment rule audits."""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from kotekomi_application.competitive_attachment_edge_filter import AttachmentPoolEdge
from kotekomi_application.competitive_attachment_edge_filter_calibration import (
    AttachmentCalibrationDiagnosticOutcome,
)
from kotekomi_application.competitive_attachment_review_verification import (
    AttachmentEvidenceReference,
)

_SHA256 = r"^[a-f0-9]{64}$"
_AUDIT_INPUT_LABELS = (
    "calibration_diagnostic_catalog",
    "calibration_run",
    "calibration_v8_report",
    "calibration_v9_report",
    "development_oracle",
    "development_pool",
    "development_tasks",
    "proposition_gold",
    "selection_report",
    "validation_oracle",
    "validation_pool",
    "validation_tasks",
)


class AttachmentMeasurementRuleAnswer(StrEnum):
    """One deterministic R1-strict decision for a Maximum Pool Edge."""

    RETAIN = "retain"
    REJECT = "reject"


class AttachmentMeasurementOutcome(StrEnum):
    """Safety result for one deterministic attachment rule."""

    SAFE = "safe"
    UNSAFE = "unsafe"


class AttachmentMeasurementControlKind(StrEnum):
    """Gold polarity of one successor diagnostic control."""

    POSITIVE = "positive"
    NEGATIVE = "negative"


class AttachmentMeasurementPackageStatus(StrEnum):
    """Lifecycle stage of one CEA-1.6 evidence package."""

    AWAITING_SECOND_OPINION = "awaiting_second_opinion"
    REVIEW_RECORDED = "review_recorded"
    COMPLETE = "complete"


class AttachmentReviewClaimVerdict(StrEnum):
    """Independent verification result for one material review claim."""

    CONFIRMED = "confirmed"
    PARTLY_CONFIRMED = "partly_confirmed"
    FALSIFIED = "falsified"
    NOT_TESTABLE = "not_testable"


class AttachmentMeasurementDecision(BaseModel):
    """One source-exact R1-strict decision scored against Attachment Gold."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["attachment_measurement_decision_v1"] = (
        "attachment_measurement_decision_v1"
    )
    phase: Literal["development", "validation"]
    edge: AttachmentPoolEdge
    source_text: Annotated[str, Field(min_length=1)]
    expected_answer: Literal["Y", "N"]
    rule_answer: AttachmentMeasurementRuleAnswer
    gold_positive_loss: bool
    gold_negative_removal: bool

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if self.edge.phase != self.phase:
            raise ValueError("Attachment measurement decision contains a foreign phase Edge.")
        if hashlib.sha256(self.source_text.encode()).hexdigest() != self.edge.source_text_sha256:
            raise ValueError("Attachment measurement decision source digest drifted.")
        for source_range in (self.edge.candidate_range, self.edge.event_range):
            if self.source_text[source_range.start : source_range.end] != source_range.text:
                raise ValueError("Attachment measurement decision range is not source-exact.")
        fires = _properly_contains(self.edge)
        expected_rule_answer = (
            AttachmentMeasurementRuleAnswer.REJECT
            if fires
            else AttachmentMeasurementRuleAnswer.RETAIN
        )
        if self.rule_answer is not expected_rule_answer:
            raise ValueError("Attachment measurement rule answer drifted from R1-strict.")
        if self.gold_positive_loss != (fires and self.expected_answer == "Y"):
            raise ValueError("Attachment measurement Gold-positive loss drifted.")
        if self.gold_negative_removal != (fires and self.expected_answer == "N"):
            raise ValueError("Attachment measurement Gold-negative removal drifted.")
        return self


class AttachmentMeasurementPhaseReport(BaseModel):
    """One complete development or validation R1-strict audit."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["attachment_measurement_phase_report_v1"] = (
        "attachment_measurement_phase_report_v1"
    )
    phase: Literal["development", "validation"]
    decisions: tuple[AttachmentMeasurementDecision, ...]
    pool_edge_count: Annotated[int, Field(ge=1)]
    rule_firing_count: Annotated[int, Field(ge=0)]
    gold_negative_removal_count: Annotated[int, Field(ge=0)]
    gold_positive_loss_count: Annotated[int, Field(ge=0)]
    result_fingerprint: Annotated[str, Field(pattern=_SHA256)]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if not self.decisions or any(item.phase != self.phase for item in self.decisions):
            raise ValueError("Attachment measurement phase contains invalid decisions.")
        edge_ids = tuple(item.edge.id for item in self.decisions)
        if len(set(edge_ids)) != len(edge_ids):
            raise ValueError("Attachment measurement decisions must identify distinct Edges.")
        expected = (
            len(self.decisions),
            sum(
                item.rule_answer is AttachmentMeasurementRuleAnswer.REJECT
                for item in self.decisions
            ),
            sum(item.gold_negative_removal for item in self.decisions),
            sum(item.gold_positive_loss for item in self.decisions),
        )
        observed = (
            self.pool_edge_count,
            self.rule_firing_count,
            self.gold_negative_removal_count,
            self.gold_positive_loss_count,
        )
        if observed != expected:
            raise ValueError("Attachment measurement phase counts drifted from its decisions.")
        _validate_fingerprint(self)
        return self


class AttachmentMeasurementAuditReport(BaseModel):
    """Complete CEA-1.6 audit against normalized occurrence-level Gold."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["attachment_measurement_audit_report_v1"] = (
        "attachment_measurement_audit_report_v1"
    )
    inputs: tuple[AttachmentEvidenceReference, ...]
    v8_outcome: AttachmentCalibrationDiagnosticOutcome
    v9_outcome: AttachmentCalibrationDiagnosticOutcome
    development: AttachmentMeasurementPhaseReport
    validation: AttachmentMeasurementPhaseReport
    combined_rule_firing_count: Annotated[int, Field(ge=0)]
    combined_gold_negative_removal_count: Annotated[int, Field(ge=0)]
    combined_gold_positive_loss_count: Annotated[int, Field(ge=0)]
    outcome: AttachmentMeasurementOutcome
    production_integration: Literal["not_activated"] = "not_activated"
    model_execution_count: Literal[0] = 0
    proposed_change_count: Literal[0] = 0
    accepted_ledger_change_count: Literal[0] = 0
    result_fingerprint: Annotated[str, Field(pattern=_SHA256)]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        labels = tuple(item.label for item in self.inputs)
        if labels != _AUDIT_INPUT_LABELS:
            raise ValueError("Attachment measurement input inventory drifted.")
        if (
            self.v8_outcome is not AttachmentCalibrationDiagnosticOutcome.NOT_SEPARABLE
            or self.v9_outcome is not AttachmentCalibrationDiagnosticOutcome.NOT_SEPARABLE
        ):
            raise ValueError("CEA-1.6 requires both sealed Prompt Arms to be not separable.")
        if self.development.phase != "development" or self.validation.phase != "validation":
            raise ValueError("Attachment measurement phase order is invalid.")
        phase_counts = (
            self.development.pool_edge_count,
            self.development.rule_firing_count,
            self.development.gold_negative_removal_count,
            self.development.gold_positive_loss_count,
            self.validation.pool_edge_count,
            self.validation.rule_firing_count,
            self.validation.gold_negative_removal_count,
            self.validation.gold_positive_loss_count,
        )
        if phase_counts != (490, 22, 15, 7, 257, 9, 4, 5):
            raise ValueError("CEA-1.6 frozen R1-strict phase counts drifted.")
        combined = (
            self.combined_rule_firing_count,
            self.combined_gold_negative_removal_count,
            self.combined_gold_positive_loss_count,
        )
        expected_combined = (
            self.development.rule_firing_count + self.validation.rule_firing_count,
            self.development.gold_negative_removal_count
            + self.validation.gold_negative_removal_count,
            self.development.gold_positive_loss_count + self.validation.gold_positive_loss_count,
        )
        if combined != expected_combined or combined != (31, 19, 12):
            raise ValueError("CEA-1.6 combined R1-strict counts drifted.")
        expected_outcome = (
            AttachmentMeasurementOutcome.UNSAFE
            if self.combined_gold_positive_loss_count
            else AttachmentMeasurementOutcome.SAFE
        )
        if self.outcome is not expected_outcome:
            raise ValueError("Attachment measurement outcome drifted from Gold-positive losses.")
        _validate_fingerprint(self)
        return self


class AttachmentMeasurementControl(BaseModel):
    """One development Pool Edge retained as a successor diagnostic control."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: Annotated[str, Field(pattern=r"^amc_[a-f0-9]{24}$")]
    kind: AttachmentMeasurementControlKind
    decision: AttachmentMeasurementDecision

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if self.decision.phase != "development":
            raise ValueError("Attachment measurement controls must come from development.")
        if self.decision.rule_answer is not AttachmentMeasurementRuleAnswer.REJECT:
            raise ValueError("Attachment measurement controls must exercise R1-strict.")
        expected_kind = (
            AttachmentMeasurementControlKind.POSITIVE
            if self.decision.expected_answer == "Y"
            else AttachmentMeasurementControlKind.NEGATIVE
        )
        if self.kind is not expected_kind:
            raise ValueError("Attachment measurement control kind drifted from Gold.")
        if self.id != _identifier("amc", self.decision.edge.id):
            raise ValueError("Attachment measurement control ID drifted.")
        return self


class AttachmentMeasurementControlCatalog(BaseModel):
    """Gold-balanced successor controls for the next attachment experiment."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["attachment_measurement_control_catalog_v1"] = (
        "attachment_measurement_control_catalog_v1"
    )
    predecessor_catalog: AttachmentEvidenceReference
    controls: tuple[AttachmentMeasurementControl, ...]
    result_fingerprint: Annotated[str, Field(pattern=_SHA256)]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        ids = tuple(item.id for item in self.controls)
        if ids != tuple(sorted(ids)) or len(set(ids)) != len(ids):
            raise ValueError("Attachment measurement controls must be ordered and distinct.")
        positive_count = sum(
            item.kind is AttachmentMeasurementControlKind.POSITIVE for item in self.controls
        )
        if positive_count < 2:
            raise ValueError("Attachment measurement controls require two positive controls.")
        if not any(
            item.kind is AttachmentMeasurementControlKind.NEGATIVE
            and "Palantir" in item.decision.edge.candidate_range.text
            and "Amazon Web Services" in item.decision.edge.candidate_range.text
            for item in self.controls
        ):
            raise ValueError("Attachment measurement controls require the mixed Palantir case.")
        _validate_fingerprint(self)
        return self


class AttachmentSecondOpinionReceipt(BaseModel):
    """Digest binding for one successful human-run Claude review."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["attachment_second_opinion_receipt_v1"] = (
        "attachment_second_opinion_receipt_v1"
    )
    handoff: AttachmentEvidenceReference
    review: AttachmentEvidenceReference
    stderr_log: AttachmentEvidenceReference
    claude_status: AttachmentEvidenceReference
    exit_code: Literal[0] = 0
    review_byte_count: Annotated[int, Field(gt=0)]
    result_fingerprint: Annotated[str, Field(pattern=_SHA256)]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        _validate_fingerprint(self)
        return self


class AttachmentReviewClaimVerification(BaseModel):
    """Evidence-backed verification of one material second-opinion claim."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    claim_id: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]*$")]
    claim_text: Annotated[str, Field(min_length=1)]
    verdict: AttachmentReviewClaimVerdict
    evidence: tuple[AttachmentEvidenceReference, ...]
    rationale: Annotated[str, Field(min_length=1)]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        labels = tuple(item.label for item in self.evidence)
        if not labels or labels != tuple(sorted(labels)) or len(set(labels)) != len(labels):
            raise ValueError("Review claim evidence must be non-empty, ordered, and distinct.")
        return self


class AttachmentReviewVerification(BaseModel):
    """Human assertion that every material review claim received evidence-backed review."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["attachment_review_verification_v1"] = (
        "attachment_review_verification_v1"
    )
    reviewer: Annotated[str, Field(min_length=1)]
    review_sha256: Annotated[str, Field(pattern=_SHA256)]
    review_fully_covered: Literal[True]
    claims: tuple[AttachmentReviewClaimVerification, ...]
    result_fingerprint: Annotated[str, Field(pattern=_SHA256)]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        identifiers = tuple(item.claim_id for item in self.claims)
        if not identifiers or identifiers != tuple(sorted(identifiers)):
            raise ValueError("Review claim verifications must be non-empty and ordered.")
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("Review claim verification IDs must be distinct.")
        _validate_fingerprint(self)
        return self


class AttachmentMeasurementManifest(BaseModel):
    """Digest-closed CEA-1.6 evidence inventory."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["attachment_measurement_manifest_v1"] = (
        "attachment_measurement_manifest_v1"
    )
    status: AttachmentMeasurementPackageStatus
    tdd: AttachmentEvidenceReference
    inputs: tuple[AttachmentEvidenceReference, ...]
    outputs: tuple[AttachmentEvidenceReference, ...]
    audit_result_fingerprint: Annotated[str, Field(pattern=_SHA256)]
    second_opinion_receipt_fingerprint: Annotated[str, Field(pattern=_SHA256)] | None
    review_verification_fingerprint: Annotated[str, Field(pattern=_SHA256)] | None
    production_integration: Literal["not_activated"] = "not_activated"
    model_execution_count: Literal[0] = 0
    proposed_change_count: Literal[0] = 0
    accepted_ledger_change_count: Literal[0] = 0
    result_fingerprint: Annotated[str, Field(pattern=_SHA256)]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        for label, values in (("inputs", self.inputs), ("outputs", self.outputs)):
            labels = tuple(item.label for item in values)
            if labels != tuple(sorted(labels)) or len(set(labels)) != len(labels):
                raise ValueError(f"Attachment measurement {label} must be ordered and distinct.")
        complete = self.status is AttachmentMeasurementPackageStatus.COMPLETE
        if complete != (
            self.second_opinion_receipt_fingerprint is not None
            and self.review_verification_fingerprint is not None
        ):
            raise ValueError("Complete attachment measurement manifest requires review closure.")
        _validate_fingerprint(self)
        return self


class AttachmentMeasurementStatus(BaseModel):
    """Machine-readable lifecycle state for one CEA-1.6 package."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["attachment_measurement_status_v1"] = "attachment_measurement_status_v1"
    status: AttachmentMeasurementPackageStatus
    outcome: AttachmentMeasurementOutcome
    report_path: Annotated[str, Field(min_length=1)]
    controls_path: Annotated[str, Field(min_length=1)]
    handoff_path: Annotated[str, Field(min_length=1)]
    launcher_path: Annotated[str, Field(min_length=1)]
    manifest_path: Annotated[str, Field(min_length=1)]
    second_opinion_receipt_path: str | None = None
    review_verification_path: str | None = None

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        complete = self.status is AttachmentMeasurementPackageStatus.COMPLETE
        if complete != (
            self.second_opinion_receipt_path is not None
            and self.review_verification_path is not None
        ):
            raise ValueError("Complete attachment measurement status requires review closure.")
        if self.status is AttachmentMeasurementPackageStatus.AWAITING_SECOND_OPINION and (
            self.second_opinion_receipt_path is not None
            or self.review_verification_path is not None
        ):
            raise ValueError("Awaiting attachment measurement status cannot cite review closure.")
        return self


def attachment_measurement_fingerprint(value: BaseModel) -> str:
    """Return the canonical fingerprint for one CEA-1.6 DTO draft."""
    return _sha(value.model_dump(mode="json", exclude={"result_fingerprint"}))


def attachment_measurement_control_id(edge_id: str) -> str:
    """Return the stable control identity for one occurrence-specific Pool Edge."""
    return _identifier("amc", edge_id)


def _properly_contains(edge: AttachmentPoolEdge) -> bool:
    candidate = edge.candidate_range
    event = edge.event_range
    return (
        candidate.start <= event.start
        and candidate.end >= event.end
        and (candidate.start, candidate.end) != (event.start, event.end)
    )


type _FingerprintedMeasurement = (
    AttachmentMeasurementPhaseReport
    | AttachmentMeasurementAuditReport
    | AttachmentMeasurementControlCatalog
    | AttachmentSecondOpinionReceipt
    | AttachmentReviewVerification
    | AttachmentMeasurementManifest
)


def _validate_fingerprint(value: _FingerprintedMeasurement) -> None:
    if value.result_fingerprint != attachment_measurement_fingerprint(value):
        raise ValueError("Attachment measurement fingerprint drifted.")


def _identifier(prefix: str, value: str) -> str:
    return f"{prefix}_{hashlib.sha256(value.encode()).hexdigest()[:24]}"


def _sha(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
    return hashlib.sha256(encoded).hexdigest()
