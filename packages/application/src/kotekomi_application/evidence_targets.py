"""Replayable EvidenceTarget validation and Assertion evidence-link use cases."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from kotekomi_domain import (
    AssertionEvidenceRole,
    Document,
    DocumentNode,
    DocumentRepresentationBundle,
    EvidenceNecessity,
    EvidencePolarity,
    EvidenceReanchoringRelation,
    EvidenceTarget,
    EvidenceValidationAttempt,
    EvidenceValidationAttemptStatus,
    ProvenanceActivity,
    canonical_evidence_target_digest,
    canonical_representation_digest,
)

HASH_ID_LENGTH = 24


class EvidenceTargetReferenceLedger(Protocol):
    def get_document_representation_bundle(
        self, record_id: str
    ) -> DocumentRepresentationBundle | None: ...
    def get_document(self, record_id: str) -> Document | None: ...


class EvidenceTargetLedger(EvidenceTargetReferenceLedger, Protocol):
    def get_evidence_target(self, record_id: str) -> EvidenceTarget | None: ...
    def save_evidence_target(self, record: EvidenceTarget) -> None: ...
    def get_evidence_validation_attempt(
        self, record_id: str
    ) -> EvidenceValidationAttempt | None: ...
    def save_evidence_validation_attempt(self, record: EvidenceValidationAttempt) -> None: ...


class EvidenceReanchoringLedger(EvidenceTargetLedger, Protocol):
    def get_provenance_activity(self, record_id: str) -> ProvenanceActivity | None: ...
    def save_evidence_reanchoring_relation(self, record: EvidenceReanchoringRelation) -> None: ...


@dataclass(frozen=True)
class EvidenceValidationInput:
    evidence_target_id: str
    attempt_id: str
    validator_version: str
    validated_at: datetime


@dataclass(frozen=True)
class EvidenceValidationResult:
    evidence_target: EvidenceTarget
    attempt: EvidenceValidationAttempt
    valid: bool
    error_message: str | None = None


@dataclass(frozen=True)
class EvidenceReplayResult:
    evidence_target: EvidenceTarget
    attempt: EvidenceValidationAttempt
    valid: bool
    error_message: str | None = None


@dataclass(frozen=True)
class ReanchorEvidenceInput:
    earlier_evidence_target_id: str
    later_evidence_target_id: str
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
    evidence_target = ledger_repository.get_evidence_target(validation_input.evidence_target_id)
    if evidence_target is None:
        raise ValueError(f"EvidenceTarget not found: {validation_input.evidence_target_id}")
    if ledger_repository.get_evidence_validation_attempt(validation_input.attempt_id) is not None:
        raise ValueError(f"EvidenceValidationAttempt already exists: {validation_input.attempt_id}")
    target_digest = canonical_evidence_target_digest(evidence_target)
    try:
        _validate_evidence_target(evidence_target, ledger_repository)
    except ValueError as exc:
        attempt = EvidenceValidationAttempt(
            id=validation_input.attempt_id,
            evidence_target_id=evidence_target.id,
            target_digest=target_digest,
            validator_version=validation_input.validator_version,
            status=EvidenceValidationAttemptStatus.FAILED,
            error_message=str(exc),
            attempted_at=validation_input.validated_at,
        )
        ledger_repository.save_evidence_validation_attempt(attempt)
        return EvidenceValidationResult(
            evidence_target=evidence_target,
            attempt=attempt,
            valid=False,
            error_message=str(exc),
        )
    attempt = EvidenceValidationAttempt(
        id=validation_input.attempt_id,
        evidence_target_id=evidence_target.id,
        target_digest=target_digest,
        validator_version=validation_input.validator_version,
        status=EvidenceValidationAttemptStatus.SUCCEEDED,
        attempted_at=validation_input.validated_at,
    )
    ledger_repository.save_evidence_validation_attempt(attempt)
    return EvidenceValidationResult(evidence_target=evidence_target, attempt=attempt, valid=True)


def validate_evidence_target_record(
    evidence_target: EvidenceTarget,
    ledger_repository: EvidenceTargetReferenceLedger,
) -> None:
    """Fail fast when an unsaved immutable EvidenceTarget cannot be replayed."""
    _validate_evidence_target(evidence_target, ledger_repository)


def verify_evidence_target(
    evidence_target: EvidenceTarget,
    validation_attempt: EvidenceValidationAttempt,
    ledger_repository: EvidenceTargetLedger,
) -> EvidenceReplayResult:
    """Replay every selector against the pinned representation without mutating state."""
    if validation_attempt.evidence_target_id != evidence_target.id:
        return EvidenceReplayResult(
            evidence_target,
            validation_attempt,
            False,
            "EvidenceValidationAttempt belongs to a different EvidenceTarget.",
        )
    if validation_attempt.status is not EvidenceValidationAttemptStatus.SUCCEEDED:
        return EvidenceReplayResult(
            evidence_target,
            validation_attempt,
            False,
            "EvidenceValidationAttempt did not succeed.",
        )
    if validation_attempt.target_digest != canonical_evidence_target_digest(evidence_target):
        return EvidenceReplayResult(
            evidence_target,
            validation_attempt,
            False,
            "EvidenceValidationAttempt target_digest is stale.",
        )
    try:
        _validate_evidence_target(evidence_target, ledger_repository)
    except ValueError as exc:
        return EvidenceReplayResult(evidence_target, validation_attempt, False, str(exc))
    return EvidenceReplayResult(evidence_target, validation_attempt, True)


def reanchor_evidence(
    reanchor_input: ReanchorEvidenceInput,
    ledger_repository: EvidenceReanchoringLedger,
) -> ReanchoringOutcome:
    earlier = ledger_repository.get_evidence_target(reanchor_input.earlier_evidence_target_id)
    later = ledger_repository.get_evidence_target(reanchor_input.later_evidence_target_id)
    if earlier is None or later is None:
        raise ValueError("Evidence reanchoring requires both the earlier and later EvidenceTarget.")
    if ledger_repository.get_provenance_activity(reanchor_input.provenance_id) is None:
        raise ValueError(
            "Evidence reanchoring references missing ProvenanceActivity: "
            f"{reanchor_input.provenance_id}"
        )
    relation = EvidenceReanchoringRelation(
        id=deterministic_evidence_reanchoring_relation_id(
            earlier_evidence_target_id=earlier.id,
            later_evidence_target_id=later.id,
        ),
        earlier_evidence_target_id=earlier.id,
        later_evidence_target_id=later.id,
        provenance_id=reanchor_input.provenance_id,
        basis=reanchor_input.basis,
        recorded_at=reanchor_input.recorded_at,
    )
    ledger_repository.save_evidence_reanchoring_relation(relation)
    return ReanchoringOutcome(relation=relation)


def deterministic_assertion_evidence_link_id(
    *,
    assertion_id: str,
    evidence_target_id: str,
    validation_attempt_id: str,
    role: AssertionEvidenceRole,
    polarity: EvidencePolarity,
    necessity: EvidenceNecessity,
) -> str:
    value = (
        f"{assertion_id}:{evidence_target_id}:{validation_attempt_id}:{role}:{polarity}:{necessity}"
    )
    return f"ael_{hashlib.sha256(value.encode()).hexdigest()[:HASH_ID_LENGTH]}"


def deterministic_evidence_reanchoring_relation_id(
    *, earlier_evidence_target_id: str, later_evidence_target_id: str
) -> str:
    value = f"{earlier_evidence_target_id}:{later_evidence_target_id}"
    return f"erl_{hashlib.sha256(value.encode()).hexdigest()[:HASH_ID_LENGTH]}"


def _validate_evidence_target(
    evidence_target: EvidenceTarget,
    ledger_repository: EvidenceTargetReferenceLedger,
) -> None:
    bundle = ledger_repository.get_document_representation_bundle(evidence_target.representation_id)
    if bundle is None:
        raise ValueError("EvidenceTarget references a missing DocumentRepresentation.")
    actual_output_digest = canonical_representation_digest(
        bundle.representation,
        text_views=bundle.text_views,
        nodes=bundle.nodes,
        edges=bundle.edges,
        source_regions=bundle.source_regions,
        quality_report=bundle.quality_report,
        tables=bundle.tables,
        table_fragments=bundle.table_fragments,
        table_rows=bundle.table_rows,
        table_cells=bundle.table_cells,
        table_annotations=bundle.table_annotations,
        references=bundle.references,
        source_selectors=bundle.source_selectors,
    )
    if bundle.representation.canonical_output_digest != actual_output_digest:
        raise ValueError("DocumentRepresentation canonical_output_digest is corrupted.")
    if bundle.representation.document_id != evidence_target.document_id:
        raise ValueError("EvidenceTarget Document does not match its DocumentRepresentation.")
    document = ledger_repository.get_document(evidence_target.document_id)
    if document is None:
        raise ValueError("EvidenceTarget references a missing Document.")
    if document.source_id != evidence_target.source_id:
        raise ValueError("EvidenceTarget Source does not match its Document.")
    text_view = next(
        (view for view in bundle.text_views if view.id == evidence_target.text_view_id), None
    )
    if text_view is None:
        raise ValueError("EvidenceTarget references a missing TextView.")
    if text_view.content_digest != evidence_target.text_view_digest:
        raise ValueError("EvidenceTarget TextView digest is stale.")
    if evidence_target.end_char > len(text_view.text):
        raise ValueError("EvidenceTarget position selector lies outside its TextView.")
    if (
        text_view.text[evidence_target.start_char : evidence_target.end_char]
        != evidence_target.exact_text
    ):
        raise ValueError("EvidenceTarget exact_text does not match its position selector.")
    prefix_start = evidence_target.start_char - len(evidence_target.prefix_text)
    if (
        prefix_start < 0
        or text_view.text[prefix_start : evidence_target.start_char] != evidence_target.prefix_text
    ):
        raise ValueError("EvidenceTarget prefix selector does not match its TextView.")
    suffix_end = evidence_target.end_char + len(evidence_target.suffix_text)
    if text_view.text[evidence_target.end_char : suffix_end] != evidence_target.suffix_text:
        raise ValueError("EvidenceTarget suffix selector does not match its TextView.")
    if not evidence_target.node_ids:
        raise ValueError("EvidenceTarget requires at least one structural node selector.")
    nodes = {node.id: node for node in bundle.nodes}
    selected_nodes: list[DocumentNode] = []
    for node_id in evidence_target.node_ids:
        node = nodes.get(node_id)
        if node is None or node.text_view_id != evidence_target.text_view_id:
            raise ValueError("EvidenceTarget node selector does not match its TextView.")
        if evidence_target.table_selector is None and (
            node.start_char > evidence_target.start_char or node.end_char < evidence_target.end_char
        ):
            raise ValueError(
                "EvidenceTarget node selector does not contain the selected occurrence."
            )
        selected_nodes.append(node)
    if evidence_target.table_selector is not None:
        selector = evidence_target.table_selector
        table = next((item for item in bundle.tables if item.id == selector.table_id), None)
        cell = next((item for item in bundle.table_cells if item.id == selector.cell_id), None)
        if table is None or cell is None or cell.table_id != table.id or cell.node_id is None:
            raise ValueError("EvidenceTarget table selector references a missing table cell.")
        if (
            selector.row_header_cell_ids != cell.row_header_cell_ids
            or selector.column_header_cell_ids != cell.column_header_cell_ids
        ):
            raise ValueError("EvidenceTarget table selector header ancestry is incomplete.")
        cells = {item.id: item for item in bundle.table_cells}
        header_cells = tuple(
            cells.get(cell_id)
            for cell_id in (*cell.row_header_cell_ids, *cell.column_header_cell_ids)
        )
        if any(header is None or header.node_id is None for header in header_cells):
            raise ValueError("EvidenceTarget table selector header text is unavailable.")
        expected_node_ids = (
            cell.node_id,
            *(header.node_id for header in header_cells if header is not None),
        )
        if evidence_target.node_ids != expected_node_ids:
            raise ValueError("EvidenceTarget table selector nodes omit required header ancestry.")
        cell_node = nodes[cell.node_id]
        if (
            cell_node.start_char > evidence_target.start_char
            or cell_node.end_char < evidence_target.end_char
        ):
            raise ValueError("EvidenceTarget table cell does not contain the selected value.")
    source_region_ids = {region.id for region in bundle.source_regions}
    if not set(evidence_target.pdf_region_ids).issubset(source_region_ids):
        raise ValueError("EvidenceTarget PDF region selector is missing from its representation.")
    selected_node_region_ids = {
        region_id for node in selected_nodes for region_id in node.source_region_ids
    }
    if evidence_target.pdf_region_ids and not set(evidence_target.pdf_region_ids).issubset(
        selected_node_region_ids
    ):
        raise ValueError("EvidenceTarget region selectors do not match its node selectors.")
    if evidence_target.table_selector is not None and set(evidence_target.pdf_region_ids) != (
        selected_node_region_ids
    ):
        raise ValueError("EvidenceTarget table selector must retain every cell and header region.")
    if evidence_target.dom_selector is not None:
        selector_id = evidence_target.dom_selector.get("selector_id")
        if not isinstance(selector_id, str):
            raise ValueError("EvidenceTarget DOM selector requires selector_id.")
        selectors = {selector.id: selector for selector in bundle.source_selectors}
        selector = selectors.get(selector_id)
        if selector is None:
            raise ValueError("EvidenceTarget DOM selector is missing from its representation.")
        if selector.node_id not in evidence_target.node_ids:
            raise ValueError("EvidenceTarget DOM selector does not agree with its node selector.")
        expected_path = evidence_target.dom_selector.get("path")
        if expected_path != list(selector.path):
            raise ValueError("EvidenceTarget DOM selector path disagrees with its representation.")
