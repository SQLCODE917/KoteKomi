"""Deterministic semantic identity for immutable Document representations."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class RepresentationFingerprintInput:
    document_id: str
    input_blob_digest: str
    parser_name: str
    parser_version: str
    parser_config_digest: str
    code_revision: str
    representation_schema_version: str


def deterministic_representation_id(fingerprint: RepresentationFingerprintInput) -> str:
    canonical = json.dumps(
        asdict(fingerprint), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return f"rep_{hashlib.sha256(canonical.encode()).hexdigest()[:24]}"
