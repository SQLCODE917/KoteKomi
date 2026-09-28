"""Parser-constituent candidate generation for the R3 deliverable (Pipeline layer).

This Pipeline composes the model-free Application Layer inventory builder against
the frozen Proposition Gold, trigger Gold, connection Gold, and pinned Stanza
dependency runtime.  It re-derives the corrected Gold with the R2 splitter, builds
one Constituent Candidate Inventory per Event, measures Boundary Fidelity and the
Constituent Pool Ceiling per partition, renders one finite selection task per
Event, scores each finite selection against the corrected Gold Attachment Set, and
emits one sealed report with zero canonical writes and zero ProposedChanges.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from kotekomi_application import (
    BoundaryFidelityPartitionCensus,
    ConstituentCandidateInventory,
    ConstituentSelectionAnswer,
    ConstituentSelectionCensus,
    ConstituentSelectionReport,
    ConstituentSelectionTask,
    CorrectedAttachmentGold,
    EventEntityLinguisticToken,
    GoldFragmentRef,
    build_boundary_fidelity_census,
    build_constituent_candidate_inventory,
    build_constituent_selection_census,
    build_constituent_selection_report,
    corrected_gold_attachment_spans,
    render_constituent_selection_task,
)

from kotekomi_pipelines.event_trigger_stage_local import TriggerGoldCatalog
from kotekomi_pipelines.source_grounded_proposition_stage_local import (
    PropositionGoldCatalog,
    PropositionGoldEvent,
)
from kotekomi_pipelines.trigger_containment_candidate_split import correct_attachment_gold

PINNED_PROPOSITION_GOLD_SHA256 = "f496ab64e6590de05b1bc07ef069335fae6a7094b009b2fae3ca02cc627e54b0"
PINNED_TRIGGER_GOLD_SHA256 = "844eb564fb953e8d202f211469465f29f6de95dd811c033506f616cf425fe83f"
PINNED_CONNECTION_GOLD_SHA256 = "afb3b25a421913b8d6b1c29eda90ee681d3bbf71719f7e0377a626bfc6067294"
PINNED_STANZA_LOCK_SHA256 = "4e66da09e0da1b3daef940ac8bec68d814b99d9fb10538e371548c9914d87bb3"


def verify_frozen_evidence_digests(
    *,
    proposition_gold: Path,
    trigger_gold: Path,
    connection_gold: Path,
    stanza_lock: Path,
) -> None:
    """Reject any R3 frozen evidence that drifted from its pinned SHA-256 digest."""
    for path, pinned in (
        (proposition_gold, PINNED_PROPOSITION_GOLD_SHA256),
        (trigger_gold, PINNED_TRIGGER_GOLD_SHA256),
        (connection_gold, PINNED_CONNECTION_GOLD_SHA256),
        (stanza_lock, PINNED_STANZA_LOCK_SHA256),
    ):
        if _sha256_file(path) != pinned:
            raise ValueError(f"R3 frozen evidence drifted from its pinned digest: {path}.")


def rederive_corrected_attachment_gold(
    *,
    catalog: PropositionGoldCatalog,
    trigger_gold: TriggerGoldCatalog,
    source_catalog_sha256: str,
) -> CorrectedAttachmentGold:
    """Re-derive the corrected Gold byte-identically with the R2 splitter."""
    return correct_attachment_gold(
        catalog=catalog,
        trigger_gold=trigger_gold,
        source_catalog_sha256=source_catalog_sha256,
    )


@dataclass(frozen=True)
class EventConstituentContract:
    """One Event's authoritative source, dependency tokens, and trigger expression."""

    event_id: str
    phase: Literal["development", "validation"]
    source_text_sha256: str
    source_text: str
    event_literal: str
    event_expression_start: int
    event_expression_end: int
    tokens: tuple[EventEntityLinguisticToken, ...]


def derive_event_constituent_contracts(
    *,
    catalog: PropositionGoldCatalog,
    tokens_by_digest: Mapping[str, tuple[EventEntityLinguisticToken, ...]],
    expressions_by_event: Mapping[str, tuple[int, int]],
    literals_by_event: Mapping[str, str],
) -> tuple[EventConstituentContract, ...]:
    """Derive one dependency-bound contract per Event, in canonical Event order."""
    contracts: list[EventConstituentContract] = []
    for event in sorted(catalog.events, key=lambda item: item.event_id):
        expression = expressions_by_event[event.event_id]
        contracts.append(
            EventConstituentContract(
                event_id=event.event_id,
                phase=event.phase,
                source_text_sha256=event.source_text_sha256,
                source_text=event.source_text,
                event_literal=literals_by_event[event.event_id],
                event_expression_start=expression[0],
                event_expression_end=expression[1],
                tokens=tokens_by_digest[event.source_text_sha256],
            )
        )
    return tuple(contracts)


def build_event_inventories(
    contracts: tuple[EventConstituentContract, ...],
) -> tuple[ConstituentCandidateInventory, ...]:
    """Derive one Constituent Candidate Inventory per Event, in canonical Event order."""
    return tuple(
        build_constituent_candidate_inventory(
            source_text=contract.source_text,
            event_id=contract.event_id,
            tokens=contract.tokens,
            event_expression_start=contract.event_expression_start,
            event_expression_end=contract.event_expression_end,
        )
        for contract in contracts
    )


def inventory_lookup(
    inventories: tuple[ConstituentCandidateInventory, ...],
) -> dict[str, ConstituentCandidateInventory]:
    """Index one ordered inventory tuple by Event ID."""
    return {item.event_id: item for item in inventories}


def gold_fragment_refs_by_event(
    catalog: PropositionGoldCatalog,
) -> dict[str, tuple[GoldFragmentRef, ...]]:
    """Return every corrected Gold fragment reference keyed by its Event ID."""
    return {
        event.event_id: tuple(
            GoldFragmentRef(
                fragment_id=fragment.fragment_id, start=fragment.start, end=fragment.end
            )
            for fragment in event.fragments
        )
        for event in catalog.events
    }


def build_partition_fidelity_censuses(
    *,
    catalog: PropositionGoldCatalog,
    inventories: Mapping[str, ConstituentCandidateInventory],
) -> tuple[BoundaryFidelityPartitionCensus, BoundaryFidelityPartitionCensus]:
    """Measure Boundary Fidelity and the Constituent Pool Ceiling per partition."""
    development, validation = _events_by_phase(catalog)
    return (
        _fidelity_partition(
            partition_role="development", events=development, inventories=inventories
        ),
        _fidelity_partition(
            partition_role="validation", events=validation, inventories=inventories
        ),
    )


def render_event_selection_tasks(
    *,
    contracts: tuple[EventConstituentContract, ...],
    inventories: Mapping[str, ConstituentCandidateInventory],
) -> tuple[ConstituentSelectionTask, ...]:
    """Render one finite selection task per Event with stable, boundary-free labels."""
    return tuple(
        render_constituent_selection_task(
            inventory=inventories[contract.event_id],
            source_text=contract.source_text,
            event_literal=contract.event_literal,
        )
        for contract in contracts
    )


def build_partition_selection_censuses(
    *,
    catalog: PropositionGoldCatalog,
    inventories: Mapping[str, ConstituentCandidateInventory],
    answers: Mapping[str, ConstituentSelectionAnswer],
    corrected: CorrectedAttachmentGold,
) -> tuple[ConstituentSelectionCensus, ConstituentSelectionCensus]:
    """Score every Event's finite selection against the corrected Gold Attachment Set."""
    gold_attachment_spans = corrected_gold_attachment_spans(corrected)
    development, validation = _events_by_phase(catalog)
    return (
        _selection_partition(
            partition_role="development",
            events=development,
            inventories=inventories,
            answers=answers,
            gold_attachment_spans=gold_attachment_spans,
        ),
        _selection_partition(
            partition_role="validation",
            events=validation,
            inventories=inventories,
            answers=answers,
            gold_attachment_spans=gold_attachment_spans,
        ),
    )


def build_r3_constituent_selection_report(
    *,
    catalog: PropositionGoldCatalog,
    inventories: Mapping[str, ConstituentCandidateInventory],
    answers: Mapping[str, ConstituentSelectionAnswer],
    corrected: CorrectedAttachmentGold,
    corrected_gold_sha256: str,
    model_execution_count: int,
) -> ConstituentSelectionReport:
    """Assemble the sealed R3 report with fidelity and selection censuses."""
    development_fidelity, validation_fidelity = build_partition_fidelity_censuses(
        catalog=catalog, inventories=inventories
    )
    development_selection, validation_selection = build_partition_selection_censuses(
        catalog=catalog,
        inventories=inventories,
        answers=answers,
        corrected=corrected,
    )
    return build_constituent_selection_report(
        development_fidelity=development_fidelity,
        validation_fidelity=validation_fidelity,
        development_selection=development_selection,
        validation_selection=validation_selection,
        corrected_gold_sha256=corrected_gold_sha256,
        model_execution_count=model_execution_count,
    )


def render_constituent_selection_review(
    *,
    report: ConstituentSelectionReport,
) -> str:
    """Render one Markdown review of the R3 censuses and Constituent Pool Ceilings."""
    development = report.development_fidelity
    validation = report.validation_fidelity
    development_selection = report.development_selection
    validation_selection = report.validation_selection
    lines = [
        "# R3 Parser-Constituent Candidate Generation",
        "",
        "Model executions: one finite selection per Event.",
        "Canonical writes: 0",
        "ProposedChanges: 0",
        "",
        "## Boundary fidelity and Constituent Pool Ceiling",
        "",
        "### development",
        "",
        f"- covered fragments: `{len(development.covered_fragment_ids)}`",
        f"- missed fragments: `{len(development.missed_fragments)}`",
        f"- pool ceiling: `{development.pool_ceiling:.6f}`",
        "",
        "### validation",
        "",
        f"- covered fragments: `{len(validation.covered_fragment_ids)}`",
        f"- missed fragments: `{len(validation.missed_fragments)}`",
        f"- pool ceiling: `{validation.pool_ceiling:.6f}`",
        "",
        "## Selection census (corrected Gold Attachment Set)",
        "",
        "### development",
        "",
        f"- selected Events: `{development_selection.selected_event_count}`",
        f"- NONE Events: `{development_selection.none_event_count}`",
        f"- rejected Events: `{development_selection.rejected_event_count}`",
        f"- exact attachments: `{development_selection.exact_attachment_count}`",
        f"- false positives: `{development_selection.false_positive_span_count}`",
        f"- false negatives: `{development_selection.false_negative_span_count}`",
        "",
        "### validation",
        "",
        f"- selected Events: `{validation_selection.selected_event_count}`",
        f"- NONE Events: `{validation_selection.none_event_count}`",
        f"- rejected Events: `{validation_selection.rejected_event_count}`",
        f"- exact attachments: `{validation_selection.exact_attachment_count}`",
        f"- false positives: `{validation_selection.false_positive_span_count}`",
        f"- false negatives: `{validation_selection.false_negative_span_count}`",
        "",
    ]
    return "\n".join(lines)


def _events_by_phase(
    catalog: PropositionGoldCatalog,
) -> tuple[tuple[PropositionGoldEvent, ...], tuple[PropositionGoldEvent, ...]]:
    development = tuple(event for event in catalog.events if event.phase == "development")
    validation = tuple(event for event in catalog.events if event.phase == "validation")
    return development, validation


def _fidelity_partition(
    *,
    partition_role: Literal["development", "validation"],
    events: tuple[PropositionGoldEvent, ...],
    inventories: Mapping[str, ConstituentCandidateInventory],
) -> BoundaryFidelityPartitionCensus:
    partition_inventories = {event.event_id: inventories[event.event_id] for event in events}
    partition_fragments = {
        event.event_id: tuple(
            GoldFragmentRef(
                fragment_id=fragment.fragment_id, start=fragment.start, end=fragment.end
            )
            for fragment in event.fragments
        )
        for event in events
    }
    return build_boundary_fidelity_census(
        partition_role=partition_role,
        inventories=partition_inventories,
        gold_fragments=partition_fragments,
    )


def _selection_partition(
    *,
    partition_role: Literal["development", "validation"],
    events: tuple[PropositionGoldEvent, ...],
    inventories: Mapping[str, ConstituentCandidateInventory],
    answers: Mapping[str, ConstituentSelectionAnswer],
    gold_attachment_spans: Mapping[str, tuple[tuple[int, int], ...]],
) -> ConstituentSelectionCensus:
    partition_inventories = {event.event_id: inventories[event.event_id] for event in events}
    partition_answers = {event.event_id: answers[event.event_id] for event in events}
    return build_constituent_selection_census(
        partition_role=partition_role,
        answers=partition_answers,
        inventories=partition_inventories,
        gold_attachment_spans=gold_attachment_spans,
    )


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()