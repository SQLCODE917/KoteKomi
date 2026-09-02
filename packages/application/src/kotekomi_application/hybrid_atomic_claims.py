"""Typed HP-5 atomic-claim and ontology-validation evidence contracts."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from enum import StrEnum
from typing import Annotated, Literal, Self, cast

from kotekomi_domain import HybridEventStructuralPredicate
from kotekomi_domain.models import JsonValue
from pydantic import BaseModel, ConfigDict, Field, model_validator

from kotekomi_application.extraction_stage_trace import (
    ExtractionStageTrace,
    validate_extraction_stage_trace_chain,
)

HYBRID_ATOMIC_CLAIM_POLICY_ID = "hybrid_atomic_claim_v1"
_SHA256 = r"^[a-f0-9]{64}$"
_ID = r"^[a-z]+_[a-f0-9]{24}$"


class AtomicClaimObjectKind(StrEnum):
    LITERAL = "literal"
    MENTION_CANDIDATE = "mention_candidate"
    SOURCE = "source"


class OntologyValidationStatus(StrEnum):
    CONFORMANT = "conformant"
    NONCONFORMANT = "nonconformant"


class HybridAtomicClaimStatus(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    BLOCKED = "blocked"


class EventSubjectDraft(BaseModel):
    """One derived event subject corresponding exactly to one HP-4 frame."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: Annotated[str, Field(pattern=r"^esd_[a-f0-9]{24}$")]
    parent_preview_id: Annotated[str, Field(pattern=r"^hep_[a-f0-9]{24}$")]
    frame_id: Annotated[str, Field(pattern=r"^efd_[a-f0-9]{24}$")]
    trigger_id: Annotated[str, Field(pattern=r"^etd_[a-f0-9]{24}$")]

    @model_validator(mode="after")
    def validate_identity(self) -> Self:
        if self.id != event_subject_draft_id(
            self.parent_preview_id, self.frame_id, self.trigger_id
        ):
            raise ValueError("EventSubjectDraft ID does not match its source frame.")
        return self


class AtomicClaimDraft(BaseModel):
    """One event-first structural claim backed by one authoritative EvidenceTarget."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: Annotated[str, Field(pattern=r"^acd_[a-f0-9]{24}$")]
    frame_id: Annotated[str, Field(pattern=r"^efd_[a-f0-9]{24}$")]
    event_subject_id: Annotated[str, Field(pattern=r"^esd_[a-f0-9]{24}$")]
    predicate: HybridEventStructuralPredicate
    object_kind: AtomicClaimObjectKind
    object_reference_id: Annotated[str, Field(min_length=1)] | None = None
    object_value: Annotated[str, Field(min_length=1)] | None = None
    role_label: Annotated[str, Field(min_length=1)] | None = None
    evidence_target_id: Annotated[str, Field(pattern=r"^etg_[a-f0-9]{24}$")]
    evidence_validation_attempt_id: Annotated[str, Field(pattern=r"^eva_[a-f0-9]{24}$")]
    source_trace_ids: tuple[Annotated[str, Field(pattern=r"^xst_[a-f0-9]{24}$")], ...]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if (self.object_reference_id is None) == (self.object_value is None):
            raise ValueError("AtomicClaimDraft requires exactly one reference or literal object.")
        if self.object_kind is AtomicClaimObjectKind.LITERAL:
            if self.object_value is None:
                raise ValueError("A literal AtomicClaimDraft requires object_value.")
        elif self.object_reference_id is None:
            raise ValueError("A reference AtomicClaimDraft requires object_reference_id.")
        if self.predicate is HybridEventStructuralPredicate.HAS_ARGUMENT:
            if self.object_kind is not AtomicClaimObjectKind.MENTION_CANDIDATE:
                raise ValueError("has_argument requires a MentionCandidate reference.")
            if self.role_label is None:
                raise ValueError("has_argument requires a proposed role label.")
        elif self.role_label is not None:
            raise ValueError("Only has_argument can carry a proposed role label.")
        _ordered_distinct("source trace IDs", self.source_trace_ids)
        if not self.source_trace_ids:
            raise ValueError("AtomicClaimDraft requires source trace lineage.")
        if self.id != atomic_claim_draft_id(
            frame_id=self.frame_id,
            event_subject_id=self.event_subject_id,
            predicate=self.predicate,
            object_kind=self.object_kind,
            object_reference_id=self.object_reference_id,
            object_value=self.object_value,
            role_label=self.role_label,
            evidence_target_id=self.evidence_target_id,
            evidence_validation_attempt_id=self.evidence_validation_attempt_id,
            source_trace_ids=self.source_trace_ids,
        ):
            raise ValueError("AtomicClaimDraft ID does not match its contents.")
        return self


class OntologyValidationFinding(BaseModel):
    """One lossless exact-conformance finding over a proposed frame or claim."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    code: Literal[
        "unmapped_event_type",
        "unmapped_argument_role",
        "attribution_support_missing",
    ]
    frame_id: Annotated[str, Field(pattern=r"^efd_[a-f0-9]{24}$")]
    claim_id: Annotated[str, Field(pattern=r"^acd_[a-f0-9]{24}$")] | None = None
    field_path: Annotated[str, Field(min_length=1)]
    proposed_value: Annotated[str, Field(min_length=1)]


class OntologyValidationReport(BaseModel):
    """Complete exact ontology-conformance result for one HP-4 frame."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: Annotated[str, Field(pattern=r"^ovr_[a-f0-9]{24}$")]
    frame_id: Annotated[str, Field(pattern=r"^efd_[a-f0-9]{24}$")]
    ontology_slice_id: Literal["hybrid_event_core_v1"]
    ontology_slice_sha256: Annotated[str, Field(pattern=_SHA256)]
    claim_ids: tuple[Annotated[str, Field(pattern=r"^acd_[a-f0-9]{24}$")], ...]
    status: OntologyValidationStatus
    findings: tuple[OntologyValidationFinding, ...] = ()

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        _ordered_distinct("report claim IDs", self.claim_ids)
        if self.status is OntologyValidationStatus.CONFORMANT and self.findings:
            raise ValueError("A conformant ontology report cannot contain findings.")
        if self.status is OntologyValidationStatus.NONCONFORMANT and not self.findings:
            raise ValueError("A nonconformant ontology report requires findings.")
        if tuple(sorted(self.findings, key=_finding_key)) != self.findings:
            raise ValueError("Ontology findings must use canonical order.")
        if any(item.frame_id != self.frame_id for item in self.findings):
            raise ValueError("Ontology findings must belong to their report frame.")
        if any(
            item.claim_id is not None and item.claim_id not in self.claim_ids
            for item in self.findings
        ):
            raise ValueError("Ontology finding references an unknown claim.")
        if self.id != ontology_validation_report_id(
            frame_id=self.frame_id,
            ontology_slice_id=self.ontology_slice_id,
            ontology_slice_sha256=self.ontology_slice_sha256,
            claim_ids=self.claim_ids,
            status=self.status,
            findings=self.findings,
        ):
            raise ValueError("OntologyValidationReport ID does not match its contents.")
        return self


class HybridAtomicClaimPreview(BaseModel):
    """Immutable derived HP-5 evidence for one terminal HP-4 Preview."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["hybrid_atomic_claim_preview_v1"] = "hybrid_atomic_claim_preview_v1"
    id: Annotated[str, Field(pattern=r"^hcp_[a-f0-9]{24}$")]
    parent_preview_id: Annotated[str, Field(pattern=r"^hep_[a-f0-9]{24}$")]
    parent_preview_sha256: Annotated[str, Field(pattern=_SHA256)]
    grounding_preview_id: Annotated[str, Field(pattern=r"^hgp_[a-f0-9]{24}$")]
    grounding_preview_sha256: Annotated[str, Field(pattern=_SHA256)]
    reference_preview_id: Annotated[str, Field(pattern=r"^hrp_[a-f0-9]{24}$")]
    reference_preview_sha256: Annotated[str, Field(pattern=_SHA256)]
    mention_preview_id: Annotated[str, Field(pattern=r"^hxp_[a-f0-9]{24}$")]
    mention_preview_sha256: Annotated[str, Field(pattern=_SHA256)]
    representation_id: Annotated[str, Field(min_length=1)]
    paragraph_node_id: Annotated[str, Field(min_length=1)]
    policy_id: Literal["hybrid_atomic_claim_v1"] = HYBRID_ATOMIC_CLAIM_POLICY_ID
    ontology_slice_id: Literal["hybrid_event_core_v1"]
    ontology_slice_sha256: Annotated[str, Field(pattern=_SHA256)]
    event_subjects: tuple[EventSubjectDraft, ...] = ()
    atomic_claims: tuple[AtomicClaimDraft, ...] = ()
    ontology_reports: tuple[OntologyValidationReport, ...] = ()
    evidence_target_ids: tuple[Annotated[str, Field(pattern=r"^etg_[a-f0-9]{24}$")], ...] = ()
    evidence_validation_attempt_ids: tuple[
        Annotated[str, Field(pattern=r"^eva_[a-f0-9]{24}$")], ...
    ] = ()
    traces: tuple[ExtractionStageTrace, ...] = ()
    terminal_status: HybridAtomicClaimStatus
    diagnostics: tuple[Annotated[str, Field(min_length=1)], ...] = ()

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        for label, values in (
            ("evidence target IDs", self.evidence_target_ids),
            ("evidence validation attempt IDs", self.evidence_validation_attempt_ids),
            ("diagnostics", self.diagnostics),
        ):
            _ordered_distinct(label, values)
        if (
            tuple(sorted(self.event_subjects, key=lambda item: item.frame_id))
            != self.event_subjects
        ):
            raise ValueError("Event subjects must use frame order.")
        if tuple(sorted(self.atomic_claims, key=atomic_claim_sort_key)) != self.atomic_claims:
            raise ValueError("Atomic claims must use canonical order.")
        if (
            tuple(sorted(self.ontology_reports, key=lambda item: item.frame_id))
            != self.ontology_reports
        ):
            raise ValueError("Ontology reports must use frame order.")
        subject_by_frame = {item.frame_id: item for item in self.event_subjects}
        if len(subject_by_frame) != len(self.event_subjects):
            raise ValueError("HybridAtomicClaimPreview repeats an event subject.")
        if any(
            claim.frame_id not in subject_by_frame
            or claim.event_subject_id != subject_by_frame[claim.frame_id].id
            for claim in self.atomic_claims
        ):
            raise ValueError("AtomicClaimDraft references an unknown event subject.")
        if {item.frame_id for item in self.ontology_reports} != set(subject_by_frame):
            raise ValueError("Every event subject requires one ontology report.")
        claim_ids = {item.id for item in self.atomic_claims}
        if any(
            set(report.claim_ids)
            != {c.id for c in self.atomic_claims if c.frame_id == report.frame_id}
            for report in self.ontology_reports
        ):
            raise ValueError("Ontology report claim coverage is incomplete.")
        if claim_ids and not self.evidence_target_ids:
            raise ValueError("Atomic claims require EvidenceTarget identities.")
        if {item.evidence_target_id for item in self.atomic_claims} != set(
            self.evidence_target_ids
        ):
            raise ValueError("Preview EvidenceTarget coverage is incomplete.")
        if {item.evidence_validation_attempt_id for item in self.atomic_claims} != set(
            self.evidence_validation_attempt_ids
        ):
            raise ValueError("Preview evidence validation coverage is incomplete.")
        traces_by_run: dict[str, list[ExtractionStageTrace]] = defaultdict(list)
        for trace in self.traces:
            traces_by_run[trace.trace_run_id].append(trace)
        if len({item.id for item in self.traces}) != len(self.traces):
            raise ValueError("HybridAtomicClaimPreview repeats a trace.")
        for trace_run in traces_by_run.values():
            validate_extraction_stage_trace_chain(tuple(trace_run))
        if self.event_subjects and len(self.traces) != 2 * len(self.event_subjects):
            raise ValueError("Each event subject requires construction and validation traces.")
        expected_trace_runs = {f"hp5:{item.frame_id}" for item in self.event_subjects}
        if set(traces_by_run) != expected_trace_runs:
            raise ValueError("HP-5 trace runs must correspond exactly to event subjects.")
        for trace_run in traces_by_run.values():
            ordered = sorted(trace_run, key=lambda item: item.ordinal)
            if [item.stage_id for item in ordered] != [
                "hybrid_atomic_claim_construction",
                "hybrid_ontology_validation",
            ]:
                raise ValueError("HP-5 trace stages are incomplete or out of order.")
        if self.terminal_status is HybridAtomicClaimStatus.PARTIAL and not self.diagnostics:
            raise ValueError("A partial HP-5 Preview requires a diagnostic.")
        if self.terminal_status is HybridAtomicClaimStatus.BLOCKED:
            if self.event_subjects or not self.diagnostics:
                raise ValueError("A blocked HP-5 Preview requires diagnostics and no subjects.")
        if self.id != _preview_id(self.model_dump(mode="json", exclude={"id"})):
            raise ValueError("HybridAtomicClaimPreview ID does not match its contents.")
        return self


def event_subject_draft_id(parent_preview_id: str, frame_id: str, trigger_id: str) -> str:
    return _id("esd", parent_preview_id, frame_id, trigger_id)


def atomic_claim_draft_id(
    *,
    frame_id: str,
    event_subject_id: str,
    predicate: HybridEventStructuralPredicate,
    object_kind: AtomicClaimObjectKind,
    object_reference_id: str | None,
    object_value: str | None,
    role_label: str | None,
    evidence_target_id: str,
    evidence_validation_attempt_id: str,
    source_trace_ids: tuple[str, ...],
) -> str:
    return _id(
        "acd",
        frame_id,
        event_subject_id,
        predicate.value,
        object_kind.value,
        object_reference_id or "",
        object_value or "",
        role_label or "",
        evidence_target_id,
        evidence_validation_attempt_id,
        *source_trace_ids,
    )


def ontology_validation_report_id(
    *,
    frame_id: str,
    ontology_slice_id: str,
    ontology_slice_sha256: str,
    claim_ids: tuple[str, ...],
    status: OntologyValidationStatus,
    findings: tuple[OntologyValidationFinding, ...],
) -> str:
    return _id(
        "ovr",
        frame_id,
        ontology_slice_id,
        ontology_slice_sha256,
        *claim_ids,
        status.value,
        *(_canonical_json(item.model_dump(mode="json")) for item in findings),
    )


def atomic_claim_sort_key(claim: AtomicClaimDraft) -> tuple[str, str, str, str]:
    return (
        claim.frame_id,
        claim.predicate.value,
        claim.object_reference_id or claim.object_value or "",
        claim.id,
    )


def build_hybrid_atomic_claim_preview(**values: object) -> HybridAtomicClaimPreview:
    payload = dict(values)
    payload.pop("id", None)
    payload.setdefault("schema_version", "hybrid_atomic_claim_preview_v1")
    payload.setdefault("policy_id", HYBRID_ATOMIC_CLAIM_POLICY_ID)
    for name in (
        "event_subjects",
        "atomic_claims",
        "ontology_reports",
        "evidence_target_ids",
        "evidence_validation_attempt_ids",
        "traces",
        "diagnostics",
    ):
        payload.setdefault(name, ())
    for name in ("event_subjects", "atomic_claims", "ontology_reports", "traces"):
        payload[name] = [
            item.model_dump(mode="json") for item in cast(tuple[BaseModel, ...], payload[name])
        ]
    normalized = cast(dict[str, JsonValue], json.loads(_canonical_json(payload)))
    normalized["id"] = _preview_id(normalized)
    return HybridAtomicClaimPreview.model_validate_json(_canonical_json(normalized))


def canonical_hybrid_atomic_claim_preview_bytes(preview: HybridAtomicClaimPreview) -> bytes:
    return _canonical_json(preview.model_dump(mode="json")).encode()


def hybrid_atomic_claim_preview_sha256(preview: HybridAtomicClaimPreview) -> str:
    return hashlib.sha256(canonical_hybrid_atomic_claim_preview_bytes(preview)).hexdigest()


def hybrid_atomic_claim_preview_from_bytes(payload: bytes) -> HybridAtomicClaimPreview:
    try:
        json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("HybridAtomicClaimPreview is not valid JSON.") from error
    preview = HybridAtomicClaimPreview.model_validate_json(payload)
    if canonical_hybrid_atomic_claim_preview_bytes(preview) != payload:
        raise ValueError("HybridAtomicClaimPreview does not use canonical encoding.")
    return preview


def _finding_key(finding: OntologyValidationFinding) -> tuple[str, str, str, str]:
    return (
        finding.code,
        finding.field_path,
        finding.proposed_value,
        finding.claim_id or "",
    )


def _id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("\x1f".join(parts).encode()).hexdigest()
    return f"{prefix}_{digest[:24]}"


def _preview_id(payload: dict[str, JsonValue]) -> str:
    digest = hashlib.sha256(_canonical_json(payload).encode()).hexdigest()
    return f"hcp_{digest[:24]}"


def _canonical_json(value: object) -> str:
    return json.dumps(
        value, allow_nan=False, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    )


def _ordered_distinct(label: str, values: tuple[str, ...]) -> None:
    if tuple(sorted(set(values))) != values:
        raise ValueError(f"HP-5 {label} must be ordered and distinct.")
