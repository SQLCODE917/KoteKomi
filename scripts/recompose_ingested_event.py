#!/usr/bin/env python3
"""Recompose one ingested Event's source-grounded outcome (R20 explicit recomposition).

Approval does not recompose automatically. Run this command after an identity
occurrence is accepted to recompose the Event and persist its composition record.

Usage:
    uv run python scripts/recompose_ingested_event.py \
        --request request.json --ledger data/kotekomi.db --out composition.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from kotekomi_adapters.sqlite_ledger import sqlite_ledger_transaction
from kotekomi_pipelines.ingestion_composition_command import (
    RecompositionRequest,
    run_recomposition,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Recompose one ingested Event after identity approval."
    )
    parser.add_argument("--request", required=True, help="JSON RecompositionRequest file.")
    parser.add_argument("--ledger", required=True, help="SQLite Ledger path.")
    parser.add_argument("--out", required=True, help="Output EventCompositionRecord JSON.")
    args = parser.parse_args()

    request = RecompositionRequest.model_validate_json(Path(args.request).read_bytes())
    with sqlite_ledger_transaction(Path(args.ledger)) as repository:
        record = run_recomposition(request, repository)

    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(record.model_dump_json(indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "event_id": record.event_id,
                "status": record.status.value,
                "hold_reason": record.hold_reason,
                "out": str(output),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
