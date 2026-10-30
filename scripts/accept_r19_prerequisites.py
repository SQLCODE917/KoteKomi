#!/usr/bin/env python3
"""Accept the R19 prerequisite Actor and EvidenceTarget records (reviewed).

This acceptance is one deterministic, auditable operation. It validates each
EvidenceTarget signature against the archived representation before saving, then
saves the Actor, the two EvidenceTargets, one succeeded EvidenceValidationAttempt
per target, and one ProvenanceActivity per accepted record. It is idempotent.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from kotekomi_adapters.sqlite_ledger import sqlite_ledger_transaction
from kotekomi_application.evidence_targets import validate_evidence_target_record
from kotekomi_domain import (
    Actor,
    EvidenceTarget,
    EvidenceValidationAttempt,
    EvidenceValidationAttemptStatus,
    ProvenanceActivity,
    canonical_evidence_target_digest,
)

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "data" / "kotekomi.db"
NOW = datetime(2026, 10, 29, tzinfo=UTC)

SOURCE_ID = "src_d97195ee5c8ced32c0cd41b0"
DOCUMENT_ID = "doc_eaaad11a475988142cad48d7"
REPRESENTATION_ID = "rep_82b32b975fbbd7dd75627fb3"
TEXT_VIEW_ID = "tvw_82b32b975fbbd7dd75627fb3_logical"
TEXT_VIEW_DIGEST = "7fcd6f4d104813254de2a930d009d74ce7920925af03195414aad58be872e9c2"
AHE_022_NODE = "nod_82b32b975fbbd7dd75627fb3_0013"
AHE_051_NODE = "nod_82b32b975fbbd7dd75627fb3_0028"


def _archived_slice(start: int, end: int) -> str:
    with sqlite_ledger_transaction(LEDGER) as ledger:
        bundle = ledger.get_document_representation_bundle(REPRESENTATION_ID)
        if bundle is None:
            raise ValueError("R19 acceptance missing the archived representation.")
        view = next(view for view in bundle.text_views if view.id == TEXT_VIEW_ID)
        return view.text[start:end]


def _evidence_target(record_id: str, start: int, end: int, node_id: str) -> EvidenceTarget:
    return EvidenceTarget(
        id=record_id,
        source_id=SOURCE_ID,
        document_id=DOCUMENT_ID,
        representation_id=REPRESENTATION_ID,
        text_view_id=TEXT_VIEW_ID,
        text_view_digest=TEXT_VIEW_DIGEST,
        start_char=start,
        end_char=end,
        exact_text=_archived_slice(start, end),
        normalization_policy="utf8_identity_v1",
        prefix_text="",
        suffix_text="",
        node_ids=(node_id,),
        created_at=NOW,
    )


def main() -> int:
    actor = Actor(id="act_david_sacks", name="David Sacks", role_names=("Sacks",))
    etg_022 = _evidence_target("etg_ahe_022", 4682, 4966, AHE_022_NODE)
    etg_051 = _evidence_target("etg_ahe_051", 9992, 10029, AHE_051_NODE)

    with sqlite_ledger_transaction(LEDGER) as ledger:
        validate_evidence_target_record(etg_022, ledger)
        validate_evidence_target_record(etg_051, ledger)

        new_ids: list[str] = []
        if ledger.get_actor(actor.id) is None:
            ledger.save_actor(actor)
            ledger.save_provenance_activity(
                ProvenanceActivity(
                    id="prv_r19_accept_sacks",
                    activity_type="accept_actor",
                    agent="kotekomi_agent",
                    output_ids=(actor.id,),
                    occurred_at=NOW,
                )
            )
            new_ids.append(actor.id)

        for target, attempt_id, provenance_id in (
            (etg_022, "eva_ahe_022", "prv_r19_accept_etg_ahe_022"),
            (etg_051, "eva_ahe_051", "prv_r19_accept_etg_ahe_051"),
        ):
            if ledger.get_evidence_target(target.id) is None:
                ledger.save_evidence_target(target)
                ledger.save_evidence_validation_attempt(
                    EvidenceValidationAttempt(
                        id=attempt_id,
                        evidence_target_id=target.id,
                        target_digest=canonical_evidence_target_digest(target),
                        validator_version="r19_acceptance_v1",
                        status=EvidenceValidationAttemptStatus.SUCCEEDED,
                        attempted_at=NOW,
                    )
                )
                ledger.save_provenance_activity(
                    ProvenanceActivity(
                        id=provenance_id,
                        activity_type="accept_evidence_target",
                        agent="kotekomi_agent",
                        input_ids=(SOURCE_ID, DOCUMENT_ID),
                        output_ids=(target.id,),
                        occurred_at=NOW,
                    )
                )
                new_ids.append(target.id)

    print("accepted", sorted(new_ids))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
