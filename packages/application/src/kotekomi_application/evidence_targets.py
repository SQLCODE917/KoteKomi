"""Replayable EvidenceSpan validation and Assertion evidence-link use cases."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from kotekomi_domain import (
    Assertion,
    AssertionEvidenceLink,
    AssertionEvidenceRole,
    Document,
    DocumentNode,
    DocumentRepresentationBundle,
    EvidenceNecessity,
    EvidencePolarity,
    EvidenceReanchoringRelation,
    EvidenceSpan,
    EvidenceValidationStatus,
    ProvenanceActivity,
    canonical_evidence_target_digest,
    canonical_representation_digest,
)

HASH_ID_LENGTH = 24


class EvidenceTargetLedger(Protocol):
    def get_evidence_span(self, record_id: str) -> EvidenceSpan | None: ...
    def save_evidence_span(self, record: EvidenceSpan) -> None: ...
    def get_document_representation_bundle(
        self, record_id: str
    ) -> DocumentRepresentationBundle | None: ...
    def get_document(self, record_id: str) -> Document | None: ...


class AssertionEvidenceLinkLedger(EvidenceTargetLedger, Protocol):
    def get_assertion(self, record_id: str) -> Assertion | None: ...
    def get_provenance_activity(self, record_id: str) -> ProvenanceActivity | None: ...
    def get_assertion_evidence_link(self, record_id: str) -> AssertionEvidenceLink | None: ...
    def save_assertion_evidence_link(self, record: AssertionEvidenceLink) -> None: ...


class EvidenceReanchoringLedger(EvidenceTargetLedger, Protocol):
    def get_provenance_activity(self, record_id: str) -> ProvenanceActivity | None: ...
    def save_evidence_reanchoring_relation(self, record: EvidenceReanchoringRelation) -> None: ...


@dataclass(frozen=True)
class EvidenceValidationInput:
    evidence_span_id: str
    validator_version: str
    validated_at: datetime


@dataclass(frozen=True)
class EvidenceValidationResult:
    evidence_span: EvidenceSpan
    valid: bool
    error_message: str | None = None


@dataclass(frozen=True)
class EvidenceReplayResult:
    evidence_span: EvidenceSpan
    valid: bool
    error_message: str | None = None


@dataclass(frozen=True)
class LinkAssertionEvidenceInput:
    assertion_id: str
    evidence_span_id: str
    role: AssertionEvidenceRole
    polarity: EvidencePolarity
    necessity: EvidenceNecessity
    provenance_id: str
    linked_at: datetime


@dataclass(frozen=True)
class ReanchorEvidenceInput:
    earlier_evidence_span_id: str
    later_evidence_span_id: str
    provenance_id: str
    basis: str
    recorded_at: datetime


@dataclass(frozen=True)
class ReanchoringOutcome:
    relation: EvidenceReanchoringRelation


def validate_evidence_target(
    validation_input: EvidenceValidationInput,
    ledger_repository: EvidenceTargetLedger,
) -> EvidenceValidationResult:
    evidence_span = ledger_repository.get_evidence_span(validation_input.evidence_span_id)
    if evidence_span is None:
        raise ValueError(f"EvidenceSpan not found: {validation_input.evidence_span_id}")
    if evidence_span.validation_status is EvidenceValidationStatus.VALIDATED:
        if evidence_span.target_digest != canonical_evidence_target_digest(evidence_span):
            return EvidenceValidationResult(
                evidence_span=evidence_span,
                valid=False,
                error_message=(
                    "Validated EvidenceSpan target_digest no longer matches its selectors."
                ),
            )
        return EvidenceValidationResult(evidence_span=evidence_span, valid=True)
    try:
        _validate_evidence_target(evidence_span, ledger_repository)
    except ValueError as exc:
        failed = evidence_span.model_copy(
            update={
                "validation_status": EvidenceValidationStatus.FAILED,
                "validator_version": validation_input.validator_version,
                "validated_at": validation_input.validated_at,
            }
        )
        ledger_repository.save_evidence_span(failed)
        return EvidenceValidationResult(evidence_span=failed, valid=False, error_message=str(exc))

    validated = evidence_span.model_copy(
        update={
            "validation_status": EvidenceValidationStatus.VALIDATED,
            "validator_version": validation_input.validator_version,
            "validated_at": validation_input.validated_at,
            "target_digest": canonical_evidence_target_digest(evidence_span),
        }
    )
    ledger_repository.save_evidence_span(validated)
    return EvidenceValidationResult(evidence_span=validated, valid=True)


def verify_evidence_target(
    evidence_span: EvidenceSpan, ledger_repository: EvidenceTargetLedger
) -> EvidenceReplayResult:
    """Replay every selector against the pinned representation without mutating state."""
    if evidence_span.validation_status is not EvidenceValidationStatus.VALIDATED:
        return EvidenceReplayResult(evidence_span, False, "EvidenceSpan is not validated.")
    if evidence_span.target_digest != canonical_evidence_target_digest(evidence_span):
        return EvidenceReplayResult(evidence_span, False, "EvidenceSpan target_digest is stale.")
    try:
        _validate_evidence_target(evidence_span, ledger_repository)
    except ValueError as exc:
        return EvidenceReplayResult(evidence_span, False, str(exc))
    return EvidenceReplayResult(evidence_span, True)


def link_assertion_evidence(
    link_input: LinkAssertionEvidenceInput,
    ledger_repository: AssertionEvidenceLinkLedger,
) -> AssertionEvidenceLink:
    assertion = ledger_repository.get_assertion(link_input.assertion_id)
    if assertion is None:
        raise ValueError(f"Assertion not found: {link_input.assertion_id}")
    evidence_span = ledger_repository.get_evidence_span(link_input.evidence_span_id)
    if evidence_span is None:
        raise ValueError(f"EvidenceSpan not found: {link_input.evidence_span_id}")
    if evidence_span.validation_status is not EvidenceValidationStatus.VALIDATED:
        raise ValueError("AssertionEvidenceLink requires a validated EvidenceSpan.")
    if evidence_span.source_id not in assertion.source_ids:
        raise ValueError("AssertionEvidenceLink EvidenceSpan source must belong to the Assertion.")
    if ledger_repository.get_provenance_activity(link_input.provenance_id) is None:
        raise ValueError(
            "AssertionEvidenceLink references missing ProvenanceActivity: "
            f"{link_input.provenance_id}"
        )
    link_id = deterministic_assertion_evidence_link_id(
        assertion_id=assertion.id,
        evidence_span_id=evidence_span.id,
        role=link_input.role,
        polarity=link_input.polarity,
        necessity=link_input.necessity,
    )
    existing = ledger_repository.get_assertion_evidence_link(link_id)
    if existing is not None:
        return existing
    link = AssertionEvidenceLink(
        id=link_id,
        assertion_id=assertion.id,
        evidence_span_id=evidence_span.id,
        role=link_input.role,
        polarity=link_input.polarity,
        necessity=link_input.necessity,
        provenance_id=link_input.provenance_id,
        created_at=link_input.linked_at,
    )
    ledger_repository.save_assertion_evidence_link(link)
    return link


def reanchor_evidence(
    reanchor_input: ReanchorEvidenceInput,
    ledger_repository: EvidenceReanchoringLedger,
) -> ReanchoringOutcome:
    earlier = ledger_repository.get_evidence_span(reanchor_input.earlier_evidence_span_id)
    later = ledger_repository.get_evidence_span(reanchor_input.later_evidence_span_id)
    if earlier is None or later is None:
        raise ValueError("Evidence reanchoring requires both the earlier and later EvidenceSpan.")
    if earlier.validation_status is not EvidenceValidationStatus.VALIDATED:
        raise ValueError("Evidence reanchoring requires a validated earlier EvidenceSpan.")
    if later.validation_status is not EvidenceValidationStatus.VALIDATED:
        raise ValueError("Evidence reanchoring requires a validated later EvidenceSpan.")
    if ledger_repository.get_provenance_activity(reanchor_input.provenance_id) is None:
        raise ValueError(
            "Evidence reanchoring references missing ProvenanceActivity: "
            f"{reanchor_input.provenance_id}"
        )
    relation = EvidenceReanchoringRelation(
        id=deterministic_evidence_reanchoring_relation_id(
            earlier_evidence_span_id=earlier.id,
            later_evidence_span_id=later.id,
        ),
        earlier_evidence_span_id=earlier.id,
        later_evidence_span_id=later.id,
        provenance_id=reanchor_input.provenance_id,
        basis=reanchor_input.basis,
        recorded_at=reanchor_input.recorded_at,
    )
    ledger_repository.save_evidence_reanchoring_relation(relation)
    return ReanchoringOutcome(relation=relation)


def deterministic_assertion_evidence_link_id(
    *,
    assertion_id: str,
    evidence_span_id: str,
    role: AssertionEvidenceRole,
    polarity: EvidencePolarity,
    necessity: EvidenceNecessity,
) -> str:
    value = f"{assertion_id}:{evidence_span_id}:{role}:{polarity}:{necessity}"
    return f"ael_{hashlib.sha256(value.encode()).hexdigest()[:HASH_ID_LENGTH]}"


def deterministic_evidence_reanchoring_relation_id(
    *, earlier_evidence_span_id: str, later_evidence_span_id: str
) -> str:
    value = f"{earlier_evidence_span_id}:{later_evidence_span_id}"
    return f"erl_{hashlib.sha256(value.encode()).hexdigest()[:HASH_ID_LENGTH]}"


def _validate_evidence_target(
    evidence_span: EvidenceSpan,
    ledger_repository: EvidenceTargetLedger,
) -> None:
    if evidence_span.representation_id is None:
        raise ValueError("EvidenceSpan is unpinned and cannot be validated.")
    bundle = ledger_repository.get_document_representation_bundle(evidence_span.representation_id)
    if bundle is None:
        raise ValueError("EvidenceSpan references a missing DocumentRepresentation.")
    actual_output_digest = canonical_representation_digest(
        bundle.representation,
        text_views=bundle.text_views,
        nodes=bundle.nodes,
        edges=bundle.edges,
        source_regions=bundle.source_regions,
        quality_report=bundle.quality_report,
    )
    if bundle.representation.canonical_output_digest != actual_output_digest:
        raise ValueError("DocumentRepresentation canonical_output_digest is corrupted.")
    if bundle.representation.document_id != evidence_span.document_id:
        raise ValueError("EvidenceSpan Document does not match its DocumentRepresentation.")
    document = ledger_repository.get_document(evidence_span.document_id)
    if document is None:
        raise ValueError("EvidenceSpan references a missing Document.")
    if document.source_id != evidence_span.source_id:
        raise ValueError("EvidenceSpan Source does not match its Document.")
    if evidence_span.text_view_id is None or evidence_span.text_view_digest is None:
        raise ValueError("EvidenceSpan is missing its TextView selector.")
    text_view = next(
        (view for view in bundle.text_views if view.id == evidence_span.text_view_id), None
    )
    if text_view is None:
        raise ValueError("EvidenceSpan references a missing TextView.")
    if text_view.content_digest != evidence_span.text_view_digest:
        raise ValueError("EvidenceSpan TextView digest is stale.")
    if evidence_span.start_char is None or evidence_span.end_char is None:
        raise ValueError("EvidenceSpan is missing its position selector.")
    if evidence_span.end_char > len(text_view.text):
        raise ValueError("EvidenceSpan position selector lies outside its TextView.")
    if (
        text_view.text[evidence_span.start_char : evidence_span.end_char]
        != evidence_span.exact_text
    ):
        raise ValueError("EvidenceSpan exact_text does not match its position selector.")
    prefix_start = evidence_span.start_char - len(evidence_span.prefix_text)
    if (
        prefix_start < 0
        or text_view.text[prefix_start : evidence_span.start_char] != evidence_span.prefix_text
    ):
        raise ValueError("EvidenceSpan prefix selector does not match its TextView.")
    suffix_end = evidence_span.end_char + len(evidence_span.suffix_text)
    if text_view.text[evidence_span.end_char : suffix_end] != evidence_span.suffix_text:
        raise ValueError("EvidenceSpan suffix selector does not match its TextView.")
    if not evidence_span.node_ids:
        raise ValueError("EvidenceSpan requires at least one structural node selector.")
    nodes = {node.id: node for node in bundle.nodes}
    selected_nodes: list[DocumentNode] = []
    for node_id in evidence_span.node_ids:
        node = nodes.get(node_id)
        if node is None or node.text_view_id != evidence_span.text_view_id:
            raise ValueError("EvidenceSpan node selector does not match its TextView.")
        if node.start_char > evidence_span.start_char or node.end_char < evidence_span.end_char:
            raise ValueError("EvidenceSpan node selector does not contain the selected occurrence.")
        selected_nodes.append(node)
    source_region_ids = {region.id for region in bundle.source_regions}
    if not set(evidence_span.pdf_region_ids).issubset(source_region_ids):
        raise ValueError("EvidenceSpan PDF region selector is missing from its representation.")
    selected_node_region_ids = {
        region_id for node in selected_nodes for region_id in node.source_region_ids
    }
    if evidence_span.pdf_region_ids and not set(evidence_span.pdf_region_ids).issubset(
        selected_node_region_ids
    ):
        raise ValueError("EvidenceSpan region selectors do not match its node selectors.")
    if evidence_span.dom_selector is not None or evidence_span.table_selector is not None:
        raise ValueError(
            "DOM and table evidence selectors are not yet represented by this parser output."
        )
