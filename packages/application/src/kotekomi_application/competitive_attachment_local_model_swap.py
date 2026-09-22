"""Typed evidence for the CEA-1.24 local model swap experiment."""

from __future__ import annotations

import hashlib
import json
import re
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from kotekomi_application.competitive_attachment_nested_event_transfer import (
    AttachmentNestedTransferEvaluation,
)
from kotekomi_application.competitive_attachment_review_verification import (
    AttachmentEvidenceReference,
)

_SHA256 = r"^[a-f0-9]{64}$"


class AttachmentLocalModelVariant(StrEnum):
    """One allowed Qwen3-14B quantization."""

    Q6_K = "q6_k"
    Q5_K_M = "q5_k_m"


class AttachmentLocalModelSwapOutcome(StrEnum):
    """Terminal interpretation of the CEA-1.24 model swap."""

    SUPPORTED = "supported"
    MIXED = "mixed"
    FALSIFIED = "falsified"
    INCONCLUSIVE = "inconclusive"


class AttachmentLocalModelSwapTransition(StrEnum):
    """One exact Baseline-to-Challenger case transition."""

    CORRECTED = "corrected"
    REGRESSED = "regressed"
    UNCHANGED_CORRECT = "unchanged_correct"
    UNCHANGED_INCORRECT = "unchanged_incorrect"
    UNRESOLVED = "unresolved"


class AttachmentLocalModelReadiness(BaseModel):
    """One machine-readable LM Studio memory and guardrail decision."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["attachment_local_model_readiness_v1"] = (
        "attachment_local_model_readiness_v1"
    )
    status: Literal["ready_for_load"]
    variant: AttachmentLocalModelVariant
    download_status: Literal[0]
    estimate_status: Literal[0]
    estimated_total_memory_gib: Annotated[float, Field(gt=0.0, le=18.0)]
    resource_guardrail_allows_load: Literal[True]
    run_root: Annotated[str, Field(min_length=1)]
    model_key: Annotated[str, Field(min_length=1)]
    load_key: Annotated[str, Field(min_length=1)]
    download_log: Annotated[str, Field(min_length=1)]
    inventory: Annotated[str, Field(min_length=1)]
    estimate_log: Annotated[str, Field(min_length=1)]


class AttachmentLocalModelPrimaryRejection(BaseModel):
    """The preserved Q6_K estimate that authorizes a Q5_K_M fallback."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["attachment_local_model_readiness_v1"] = (
        "attachment_local_model_readiness_v1"
    )
    status: Literal["q6_rejected"]
    variant: Literal[AttachmentLocalModelVariant.Q6_K]
    download_status: Literal[0]
    estimate_status: int
    estimated_total_memory_gib: Annotated[float, Field(gt=0.0)]
    resource_guardrail_allows_load: bool
    run_root: Annotated[str, Field(min_length=1)]
    model_key: Annotated[str, Field(min_length=1)]
    load_key: Annotated[str, Field(min_length=1)]
    download_log: Annotated[str, Field(min_length=1)]
    inventory: Annotated[str, Field(min_length=1)]
    estimate_log: Annotated[str, Field(min_length=1)]

    @model_validator(mode="after")
    def validate_rejection(self) -> Self:
        if (
            self.estimate_status == 0
            and self.estimated_total_memory_gib <= 18.0
            and self.resource_guardrail_allows_load
        ):
            raise ValueError("A passing Q6_K estimate cannot authorize the fallback.")
        return self


class AttachmentLocalModelArtifact(BaseModel):
    """The exact loaded Qwen3-14B artifact used by the Challenger Model."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["attachment_local_model_artifact_v1"] = (
        "attachment_local_model_artifact_v1"
    )
    variant: AttachmentLocalModelVariant
    model_key: Annotated[str, Field(min_length=1)]
    display_name: Annotated[str, Field(min_length=1)]
    architecture: Annotated[str, Field(min_length=1)]
    quantization: Annotated[str, Field(min_length=1)]
    bits_per_weight: Annotated[float, Field(gt=0.0, le=16.0)]
    size_bytes: Annotated[int, Field(gt=0)]
    params_string: Annotated[str, Field(min_length=1)]
    format: Annotated[str, Field(min_length=1)]
    loaded_instance_id: Annotated[str, Field(min_length=1)]
    context_length: Annotated[int, Field(ge=16_384)]
    max_context_length: Annotated[int, Field(ge=16_384)]
    estimated_total_memory_gib: Annotated[float, Field(gt=0.0, le=18.0)]
    resource_guardrail_allows_load: Literal[True]
    readiness_evidence_sha256: Annotated[str, Field(pattern=_SHA256)]
    fallback_reason: Annotated[str, Field(min_length=1)] | None = None
    metadata_sha256: Annotated[str, Field(pattern=_SHA256)]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        expected_quantization = {
            AttachmentLocalModelVariant.Q6_K: "Q6_K",
            AttachmentLocalModelVariant.Q5_K_M: "Q5_K_M",
        }[self.variant]
        if self.quantization != expected_quantization:
            raise ValueError("Local model quantization does not match its declared variant.")
        if self.architecture != "qwen3":
            raise ValueError("The Challenger architecture must be qwen3.")
        if self.format != "gguf":
            raise ValueError("The Challenger artifact must use GGUF format.")
        if self.context_length != 16_384:
            raise ValueError("The Challenger context must match the 16384-token Baseline.")
        if self.variant is AttachmentLocalModelVariant.Q6_K and self.fallback_reason is not None:
            raise ValueError("The Primary Variant cannot record a fallback reason.")
        if self.variant is AttachmentLocalModelVariant.Q5_K_M and self.fallback_reason is None:
            raise ValueError("The Fallback Variant requires the Primary Variant failure reason.")
        identity = f"{self.model_key} {self.display_name}".casefold()
        if "qwen3" not in identity or "14b" not in identity.replace(" ", ""):
            raise ValueError("The Challenger artifact must identify Qwen3-14B.")
        if (
            re.fullmatch(r"14(?:\.[0-9]+)?b", self.params_string.casefold().replace(" ", ""))
            is None
        ):
            raise ValueError("The Challenger parameter description must identify 14B.")
        return self


class AttachmentLocalModelOutputCalibration(BaseModel):
    """One byte-exact Qwen3 output-transport calibration result."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["qwen3_exact_output_probe_v1"] = "qwen3_exact_output_probe_v1"
    input_sha256: Annotated[str, Field(pattern=_SHA256)]
    status: Literal["completed"]
    output_texts: tuple[Literal["Y", "N", "U"], ...]
    output_token_count: Literal[1]
    reasoning_token_count: Literal[0]

    @model_validator(mode="after")
    def validate_output(self) -> Self:
        if len(self.output_texts) != 1:
            raise ValueError("Output calibration requires one exact answer.")
        return self


class AttachmentLocalModelSwapPreflight(BaseModel):
    """Immutable CEA-1.23 bindings before Challenger execution."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["attachment_local_model_swap_preflight_v1"] = (
        "attachment_local_model_swap_preflight_v1"
    )
    inputs: tuple[AttachmentEvidenceReference, ...]
    baseline_root: Annotated[str, Field(min_length=1)]
    baseline_report: AttachmentEvidenceReference
    blind_review_response: AttachmentEvidenceReference
    semantic_prompt: AttachmentEvidenceReference
    case_count: Literal[20]
    primary_variant: Literal[AttachmentLocalModelVariant.Q6_K] = AttachmentLocalModelVariant.Q6_K
    fallback_variant: Literal[AttachmentLocalModelVariant.Q5_K_M] = (
        AttachmentLocalModelVariant.Q5_K_M
    )
    nonthinking_control: Literal["/no_think"] = "/no_think"
    comparator_effective_max_output_tokens: Literal[2] = 2
    challenger_effective_max_output_tokens: Literal[16] = 16
    result_fingerprint: Annotated[str, Field(pattern=_SHA256)]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if self.result_fingerprint != attachment_local_model_swap_preflight_fingerprint(self):
            raise ValueError("Local model swap preflight fingerprint drifted.")
        return self


class AttachmentLocalModelSwapCase(BaseModel):
    """One occurrence-level context correction and model comparison."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    case_id: Annotated[str, Field(pattern=r"^ntc_[a-f0-9]{24}$")]
    historical_baseline: AttachmentNestedTransferEvaluation
    comparator_baseline: AttachmentNestedTransferEvaluation
    challenger: AttachmentNestedTransferEvaluation
    context_transition: AttachmentLocalModelSwapTransition
    model_transition: AttachmentLocalModelSwapTransition

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        evaluations = (
            self.historical_baseline,
            self.comparator_baseline,
            self.challenger,
        )
        if any(item.case.id != self.case_id for item in evaluations):
            raise ValueError("Local model swap case contains a foreign evaluation.")
        if any(item.case != evaluations[0].case for item in evaluations[1:]):
            raise ValueError("Local model swap changed the source-exact case.")
        if any(item.expected != evaluations[0].expected for item in evaluations[1:]):
            raise ValueError("Local model swap changed the blind Gold decision.")
        expected = (
            attachment_local_model_swap_transition(
                self.historical_baseline,
                self.comparator_baseline,
            ),
            attachment_local_model_swap_transition(
                self.comparator_baseline,
                self.challenger,
            ),
        )
        if (self.context_transition, self.model_transition) != expected:
            raise ValueError("Local model swap transitions drifted.")
        return self


class AttachmentLocalModelSwapReport(BaseModel):
    """The terminal CEA-1.24 model comparison report."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["attachment_local_model_swap_report_v1"] = (
        "attachment_local_model_swap_report_v1"
    )
    inputs: tuple[AttachmentEvidenceReference, ...]
    preflight: AttachmentEvidenceReference
    output_calibration: AttachmentEvidenceReference
    model_artifact: AttachmentLocalModelArtifact
    cases: tuple[AttachmentLocalModelSwapCase, ...]
    outcome: AttachmentLocalModelSwapOutcome
    case_count: Literal[20]
    historical_baseline_correct_count: Annotated[int, Field(ge=0, le=20)]
    comparator_baseline_correct_count: Annotated[int, Field(ge=0, le=20)]
    challenger_correct_count: Annotated[int, Field(ge=0, le=20)]
    historical_baseline_accuracy: Annotated[float, Field(ge=0.0, le=1.0)]
    comparator_baseline_accuracy: Annotated[float, Field(ge=0.0, le=1.0)]
    challenger_accuracy: Annotated[float, Field(ge=0.0, le=1.0)]
    accuracy_delta: Annotated[float, Field(ge=-1.0, le=1.0)]
    challenger_yes_recall: Annotated[float, Field(ge=0.0, le=1.0)]
    challenger_no_recall: Annotated[float, Field(ge=0.0, le=1.0)]
    context_corrected_case_ids: tuple[Annotated[str, Field(pattern=r"^ntc_[a-f0-9]{24}$")], ...]
    context_regressed_case_ids: tuple[Annotated[str, Field(pattern=r"^ntc_[a-f0-9]{24}$")], ...]
    corrected_case_ids: tuple[Annotated[str, Field(pattern=r"^ntc_[a-f0-9]{24}$")], ...]
    regressed_case_ids: tuple[Annotated[str, Field(pattern=r"^ntc_[a-f0-9]{24}$")], ...]
    unchanged_correct_case_ids: tuple[Annotated[str, Field(pattern=r"^ntc_[a-f0-9]{24}$")], ...]
    unchanged_incorrect_case_ids: tuple[Annotated[str, Field(pattern=r"^ntc_[a-f0-9]{24}$")], ...]
    unresolved_case_ids: tuple[Annotated[str, Field(pattern=r"^ntc_[a-f0-9]{24}$")], ...]
    comparator_baseline_model_elapsed_milliseconds: Annotated[int, Field(ge=0)]
    challenger_model_elapsed_milliseconds: Annotated[int, Field(ge=0)]
    challenger_model_identity_digests: tuple[Annotated[str, Field(pattern=_SHA256)], ...]
    comparator_effective_max_output_tokens: Literal[2]
    challenger_effective_max_output_tokens: Literal[16]
    proposed_change_count: Literal[0] = 0
    accepted_ledger_change_count: Literal[0] = 0
    production_integration: Literal["not_activated"] = "not_activated"
    result_fingerprint: Annotated[str, Field(pattern=_SHA256)]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if len(self.cases) != self.case_count:
            raise ValueError("Local model swap requires twenty cases.")
        if tuple(item.case_id for item in self.cases) != tuple(
            item.comparator_baseline.case.id for item in self.cases
        ):
            raise ValueError("Local model swap case order drifted.")
        context_groups = {
            transition: tuple(
                item.case_id for item in self.cases if item.context_transition is transition
            )
            for transition in AttachmentLocalModelSwapTransition
        }
        model_groups = {
            transition: tuple(
                item.case_id for item in self.cases if item.model_transition is transition
            )
            for transition in AttachmentLocalModelSwapTransition
        }
        expected_counts = (
            sum(item.historical_baseline.correct for item in self.cases),
            sum(item.comparator_baseline.correct for item in self.cases),
            sum(item.challenger.correct for item in self.cases),
        )
        expected_accuracy = (
            _ratio(expected_counts[0], self.case_count),
            _ratio(expected_counts[1], self.case_count),
            _ratio(expected_counts[2], self.case_count),
        )
        positives = tuple(item for item in self.cases if item.challenger.expected.answer == "Y")
        negatives = tuple(item for item in self.cases if item.challenger.expected.answer == "N")
        expected = (
            *expected_counts,
            *expected_accuracy,
            expected_accuracy[2] - expected_accuracy[1],
            _ratio(sum(item.challenger.correct for item in positives), len(positives)),
            _ratio(sum(item.challenger.correct for item in negatives), len(negatives)),
            context_groups[AttachmentLocalModelSwapTransition.CORRECTED],
            context_groups[AttachmentLocalModelSwapTransition.REGRESSED],
            model_groups[AttachmentLocalModelSwapTransition.CORRECTED],
            model_groups[AttachmentLocalModelSwapTransition.REGRESSED],
            model_groups[AttachmentLocalModelSwapTransition.UNCHANGED_CORRECT],
            model_groups[AttachmentLocalModelSwapTransition.UNCHANGED_INCORRECT],
            model_groups[AttachmentLocalModelSwapTransition.UNRESOLVED],
            sum(item.comparator_baseline.observation.elapsed_milliseconds for item in self.cases),
            sum(item.challenger.observation.elapsed_milliseconds for item in self.cases),
            tuple(
                sorted(
                    {
                        item.challenger.observation.model_identity_digest
                        for item in self.cases
                        if item.challenger.observation.model_identity_digest is not None
                    }
                )
            ),
        )
        observed = (
            self.historical_baseline_correct_count,
            self.comparator_baseline_correct_count,
            self.challenger_correct_count,
            self.historical_baseline_accuracy,
            self.comparator_baseline_accuracy,
            self.challenger_accuracy,
            self.accuracy_delta,
            self.challenger_yes_recall,
            self.challenger_no_recall,
            self.context_corrected_case_ids,
            self.context_regressed_case_ids,
            self.corrected_case_ids,
            self.regressed_case_ids,
            self.unchanged_correct_case_ids,
            self.unchanged_incorrect_case_ids,
            self.unresolved_case_ids,
            self.comparator_baseline_model_elapsed_milliseconds,
            self.challenger_model_elapsed_milliseconds,
            self.challenger_model_identity_digests,
        )
        if observed != expected:
            raise ValueError("Local model swap report metrics drifted.")
        if len(self.challenger_model_identity_digests) != 1:
            raise ValueError("Local model swap requires one Challenger model identity.")
        if self.outcome is not classify_attachment_local_model_swap_outcome(self.cases):
            raise ValueError("Local model swap outcome drifted.")
        if self.result_fingerprint != attachment_local_model_swap_fingerprint(self):
            raise ValueError("Local model swap report fingerprint drifted.")
        return self


def attachment_local_model_swap_transition(
    baseline: AttachmentNestedTransferEvaluation,
    challenger: AttachmentNestedTransferEvaluation,
) -> AttachmentLocalModelSwapTransition:
    """Classify one occurrence-level answer transition."""
    if not challenger.complete:
        return AttachmentLocalModelSwapTransition.UNRESOLVED
    if not baseline.correct and challenger.correct:
        return AttachmentLocalModelSwapTransition.CORRECTED
    if baseline.correct and not challenger.correct:
        return AttachmentLocalModelSwapTransition.REGRESSED
    if baseline.correct:
        return AttachmentLocalModelSwapTransition.UNCHANGED_CORRECT
    return AttachmentLocalModelSwapTransition.UNCHANGED_INCORRECT


def classify_attachment_local_model_swap_outcome(
    cases: tuple[AttachmentLocalModelSwapCase, ...],
) -> AttachmentLocalModelSwapOutcome:
    """Classify the Challenger result against the frozen Baseline."""
    if len(cases) != 20 or any(not item.challenger.complete for item in cases):
        return AttachmentLocalModelSwapOutcome.INCONCLUSIVE
    baseline_correct = sum(item.comparator_baseline.correct for item in cases)
    challenger_correct = sum(item.challenger.correct for item in cases)
    positives = tuple(item for item in cases if item.challenger.expected.answer == "Y")
    negatives = tuple(item for item in cases if item.challenger.expected.answer == "N")
    yes_recall = _ratio(sum(item.challenger.correct for item in positives), len(positives))
    no_recall = _ratio(sum(item.challenger.correct for item in negatives), len(negatives))
    corrected = sum(
        item.model_transition is AttachmentLocalModelSwapTransition.CORRECTED for item in cases
    )
    regressed = sum(
        item.model_transition is AttachmentLocalModelSwapTransition.REGRESSED for item in cases
    )
    if (
        challenger_correct >= 18
        and yes_recall >= 0.85
        and no_recall >= 0.85
        and challenger_correct > baseline_correct
        and corrected > regressed
    ):
        return AttachmentLocalModelSwapOutcome.SUPPORTED
    if challenger_correct > baseline_correct or (
        challenger_correct == baseline_correct and corrected > 0 and regressed > 0
    ):
        return AttachmentLocalModelSwapOutcome.MIXED
    return AttachmentLocalModelSwapOutcome.FALSIFIED


def attachment_local_model_swap_preflight_fingerprint(
    preflight: AttachmentLocalModelSwapPreflight,
) -> str:
    """Return the semantic preflight fingerprint."""
    return _fingerprint(preflight, "result_fingerprint")


def attachment_local_model_swap_fingerprint(report: AttachmentLocalModelSwapReport) -> str:
    """Return the semantic report fingerprint."""
    return _fingerprint(report, "result_fingerprint")


def _fingerprint(value: BaseModel, excluded: str) -> str:
    payload = value.model_dump(mode="json", exclude={excluded})
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0
