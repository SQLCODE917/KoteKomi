"""Canonical serialization for deterministic application-owned record boundaries."""

from __future__ import annotations

import json

from pydantic import BaseModel


def canonical_record_json(record: BaseModel) -> str:
    return json.dumps(
        record.model_dump(mode="json"), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
