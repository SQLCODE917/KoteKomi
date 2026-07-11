"""Deterministic semantic identity for immutable Document representations."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Protocol

from kotekomi_domain import DocumentRepresentationBundle


@dataclass(frozen=True)
class RepresentationFingerprintInput:
    document_id: str
    input_blob_digest: str
    parser_name: str
    parser_version: str
    parser_config_digest: str
    code_revision: str
    representation_schema_version: str


class BundleCommitDisposition(StrEnum):
    CREATED = "created"
    REUSED = "reused"


@dataclass(frozen=True)
class BundleCommitOutcome:
    disposition: BundleCommitDisposition
    representation_id: str


class DocumentRepresentationBundleLedger(Protocol):
    def commit_document_representation_bundle(
        self, bundle: DocumentRepresentationBundle
    ) -> BundleCommitOutcome: ...


def deterministic_representation_id(fingerprint: RepresentationFingerprintInput) -> str:
    canonical = json.dumps(
        asdict(fingerprint), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return f"rep_{hashlib.sha256(canonical.encode()).hexdigest()[:24]}"
