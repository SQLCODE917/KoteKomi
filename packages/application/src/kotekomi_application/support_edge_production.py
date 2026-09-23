"""Deterministic model-free ``supports`` ArgumentEdge production.

D2 of the Event Attribution Production Wiring package. The producer converts one reviewed,
accepted source-support decision into one ``supports`` ArgumentEdge that connects an
evidence-carrying Assertion to the accepted Assertion it supports.

The producer is model-free and creates no accepted intelligence beyond the edge and its
ProvenanceActivity.

Endpoint roles are the caller's invariant. This producer only requires both endpoints to be
accepted Assertions; it does not inspect ``epistemic_scope``, ``attributed_to_id``, or
``assertion_type``. The caller binds the evidence-carrying Assertion to ``from_assertion_id``
and the supported Assertion to ``to_assertion_id``.

``rationale`` is an explicit producer input bound to ``SemanticSupportJudgment.reason`` and is
written to the edge. ``confidence`` is an explicit producer input bound to the NLI
``entailment_score`` and is written to the edge. The pinned support decision and the judgment
and NLI observation identifiers are recorded in ``ProvenanceActivity.input_ids`` for
traceability.

A missing or non-accepted endpoint raises a typed ``SupportEdgeError`` and writes nothing.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol

from kotekomi_domain import (
    ArgumentEdge,
    ArgumentEdgeRelation,
    Assertion,
    ProvenanceActivity,
)
from kotekomi_domain.models import is_accepted_status

SUPPORT_EDGE_ACTIVITY_TYPE = "support_edge_production"
SUPPORT_EDGE_AGENT = "kotekomi_application.support_edge_production"


class SupportEdgeFailureCode(StrEnum):
    """Typed reason that one supports edge could not be produced."""

    FROM_ASSERTION_MISSING = "from_assertion_missing"
    FROM_ASSERTION_NOT_ACCEPTED = "from_assertion_not_accepted"
    TO_ASSERTION_MISSING = "to_assertion_missing"
    TO_ASSERTION_NOT_ACCEPTED = "to_assertion_not_accepted"


class SupportEdgeError(ValueError):
    """A deterministic supports-edge production failure that writes nothing."""

    def __init__(self, code: SupportEdgeFailureCode, message: str) -> None:
        super().__init__(message)
        self.code = code


class SupportEdgeLedger(Protocol):
    """The narrow Ledger surface the supports producer needs."""

    def get_assertion(self, record_id: str) -> Assertion | None: ...
    def save_argument_edge(self, record: ArgumentEdge) -> None: ...
    def save_provenance_activity(self, record: ProvenanceActivity) -> None: ...


@dataclass(frozen=True)
class ProduceSupportEdgeInput:
    """One explicit, fully pinned supports-edge production request."""

    from_assertion_id: str
    to_assertion_id: str
    rationale: str
    confidence: float
    evidence_target_ids: tuple[str, ...]
    support_decision_id: str
    support_judgment_id: str
    nli_observation_id: str
    occurred_at: datetime

    def __post_init__(self) -> None:
        for label, value in (
            ("From Assertion ID", self.from_assertion_id),
            ("To Assertion ID", self.to_assertion_id),
            ("support decision ID", self.support_decision_id),
            ("support judgment ID", self.support_judgment_id),
            ("NLI observation ID", self.nli_observation_id),
        ):
            if not value or value != value.strip():
                raise ValueError(f"Support edge {label} must be a non-empty trimmed string.")
        if self.rationale != self.rationale.strip():
            raise ValueError("Support edge rationale must be a non-empty trimmed string.")
        if "\n" in self.rationale or "\r" in self.rationale:
            raise ValueError("Support edge rationale must be one line.")
        if not math.isfinite(self.confidence) or self.confidence < 0 or self.confidence > 1:
            raise ValueError("Support edge confidence must be a finite probability.")
        if not self.evidence_target_ids:
            raise ValueError("Support edge requires at least one evidence target ID.")


@dataclass(frozen=True)
class SupportEdgeProductionResult:
    argument_edge: ArgumentEdge
    provenance_activity: ProvenanceActivity


def support_argument_edge_id(
    *,
    from_assertion_id: str,
    to_assertion_id: str,
    rationale: str,
    confidence: float,
    evidence_target_ids: tuple[str, ...],
    support_decision_id: str,
) -> str:
    """Derive one deterministic supports edge identity from its full contract."""
    return _digest_id(
        "arg",
        "supports",
        from_assertion_id,
        to_assertion_id,
        rationale,
        format(confidence, ".8f"),
        *evidence_target_ids,
        support_decision_id,
    )


def support_edge_provenance_activity_id(
    *,
    argument_edge_id: str,
    support_decision_id: str,
) -> str:
    """Derive one deterministic provenance identity from the produced edge and decision."""
    return _digest_id("prv", "support_edge", argument_edge_id, support_decision_id)


def produce_support_edge(
    *,
    production_input: ProduceSupportEdgeInput,
    ledger: SupportEdgeLedger,
) -> SupportEdgeProductionResult:
    """Produce one ``supports`` ArgumentEdge and its ProvenanceActivity, or fail fast.

    Both endpoints must exist as accepted Assertions. The producer writes the edge and its
    ProvenanceActivity only after both endpoints and the full contract validate.
    """
    from_assertion = ledger.get_assertion(production_input.from_assertion_id)
    if from_assertion is None:
        raise SupportEdgeError(
            SupportEdgeFailureCode.FROM_ASSERTION_MISSING,
            "Supports edge requires an evidence-carrying Assertion.",
        )
    if not is_accepted_status(from_assertion.status):
        raise SupportEdgeError(
            SupportEdgeFailureCode.FROM_ASSERTION_NOT_ACCEPTED,
            "Supports edge requires an accepted evidence-carrying Assertion.",
        )

    to_assertion = ledger.get_assertion(production_input.to_assertion_id)
    if to_assertion is None:
        raise SupportEdgeError(
            SupportEdgeFailureCode.TO_ASSERTION_MISSING,
            "Supports edge requires a supported Assertion.",
        )
    if not is_accepted_status(to_assertion.status):
        raise SupportEdgeError(
            SupportEdgeFailureCode.TO_ASSERTION_NOT_ACCEPTED,
            "Supports edge requires an accepted supported Assertion.",
        )

    edge = ArgumentEdge(
        id=support_argument_edge_id(
            from_assertion_id=production_input.from_assertion_id,
            to_assertion_id=production_input.to_assertion_id,
            rationale=production_input.rationale,
            confidence=production_input.confidence,
            evidence_target_ids=production_input.evidence_target_ids,
            support_decision_id=production_input.support_decision_id,
        ),
        from_assertion_id=production_input.from_assertion_id,
        to_assertion_id=production_input.to_assertion_id,
        relation=ArgumentEdgeRelation.SUPPORTS,
        rationale=production_input.rationale,
        evidence_target_ids=production_input.evidence_target_ids,
        confidence=production_input.confidence,
        created_at=production_input.occurred_at,
    )
    activity = ProvenanceActivity(
        id=support_edge_provenance_activity_id(
            argument_edge_id=edge.id,
            support_decision_id=production_input.support_decision_id,
        ),
        activity_type=SUPPORT_EDGE_ACTIVITY_TYPE,
        agent=SUPPORT_EDGE_AGENT,
        input_ids=tuple(
            sorted(
                {
                    production_input.from_assertion_id,
                    production_input.to_assertion_id,
                    production_input.support_decision_id,
                    production_input.support_judgment_id,
                    production_input.nli_observation_id,
                    *production_input.evidence_target_ids,
                }
            )
        ),
        output_ids=(edge.id,),
        occurred_at=production_input.occurred_at,
    )
    ledger.save_argument_edge(edge)
    ledger.save_provenance_activity(activity)
    return SupportEdgeProductionResult(argument_edge=edge, provenance_activity=activity)


def _digest_id(prefix: str, *parts: str) -> str:
    payload = "\x1f".join((prefix, *parts)).encode()
    return f"{prefix}_{hashlib.sha256(payload).hexdigest()[:24]}"
