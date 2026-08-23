"""Pipeline composition for reviewed exact-byte source lineage proposals."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from kotekomi_adapters import sqlite_ledger_transaction
from kotekomi_application import (
    ProposeVerbatimRepublicationInput,
    propose_verbatim_republication,
)

from kotekomi_pipelines.config import PipelineConfig


def propose_verbatim_republication_relation(
    *,
    config: PipelineConfig,
    document_ids: tuple[str, ...],
    proposer: str,
    rationale: str,
    output_format: str,
) -> int:
    if len(document_ids) != 2:
        raise ValueError("Verbatim republication requires exactly two --document-id values.")
    with sqlite_ledger_transaction(config.ledger_path) as ledger_repository:
        result = propose_verbatim_republication(
            ProposeVerbatimRepublicationInput(
                document_ids=(document_ids[0], document_ids[1]),
                proposer=proposer,
                rationale=rationale,
                proposed_at=datetime.now(UTC),
            ),
            ledger_repository,
        )
    payload = {
        "status": result.status,
        "proposed_change_id": result.proposed_change_id,
        "source_lineage_relation_id": result.source_lineage_relation_id,
        "failure": result.failure.value if result.failure is not None else None,
    }
    if output_format == "json":
        print(json.dumps(payload, sort_keys=True))
    else:
        for key, value in payload.items():
            print(f"{key}: {value}")
    return 0 if result.status != "failed" else 1
