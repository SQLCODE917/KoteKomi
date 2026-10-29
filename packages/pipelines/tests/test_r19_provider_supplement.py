"""Focused tests for the R19 provider supplement schema and gated loader."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest
from kotekomi_application.ports import LedgerRepository
from kotekomi_pipelines.r19_provider_supplement import (
    R19ProviderSupplement,
    load_r19_provider_supplement,
    require_approved_supplement,
    require_resolved_closure,
    unresolved_references,
)

ROOT = Path(__file__).resolve().parents[3]
SUPPLEMENT = ROOT / "docs" / "hsq-r19-provider-supplement-v1.json"


def _payload() -> dict[str, Any]:
    return json.loads(SUPPLEMENT.read_text(encoding="utf-8"))


def _write(directory: Path, payload: Any) -> Path:
    path = directory / "supplement.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


class _EmptyRepository:
    def get_actor(self, record_id: str):
        del record_id
        return None

    def get_organization(self, record_id: str):
        del record_id
        return None

    def get_source(self, record_id: str):
        del record_id
        return None

    def get_evidence_target(self, record_id: str):
        del record_id
        return None


def _empty_repository() -> LedgerRepository:
    return cast(LedgerRepository, _EmptyRepository())


def test_loads_proposed_supplement_and_reports_unresolved_references() -> None:
    supplement = load_r19_provider_supplement(SUPPLEMENT, repository_root=ROOT)

    assert supplement.review_status == "proposed"
    assert [item.residual_event_id for item in supplement.event_bindings] == [
        "AHE-022",
        "AHE-051",
    ]
    assert supplement.event_bindings[0].provider_event_id == "TGE-018"
    assert [item.entity_id for item in supplement.identity_mappings] == ["EGE-019"]
    unresolved = unresolved_references(supplement)
    assert any("EGE-019" in item for item in unresolved)
    assert sum("evidence_target_id" in item for item in unresolved) == 2


def test_unapproved_supplement_cannot_authorize_composition() -> None:
    supplement = load_r19_provider_supplement(SUPPLEMENT, repository_root=ROOT)

    with pytest.raises(ValueError, match="approved"):
        require_approved_supplement(supplement)


def test_rejects_connection_gold_digest_drift(tmp_path: Path) -> None:
    payload = _payload()
    payload["bound_connection_gold"]["sha256"] = "0" * 64

    with pytest.raises(ValueError, match="digest drifted"):
        load_r19_provider_supplement(_write(tmp_path, payload), repository_root=ROOT)


def test_rejects_residual_input_digest_drift(tmp_path: Path) -> None:
    payload = _payload()
    payload["residual_inputs"][0]["input_sha256"] = "0" * 64

    with pytest.raises(ValueError, match="residual input digest drifted"):
        load_r19_provider_supplement(_write(tmp_path, payload), repository_root=ROOT)


def test_rejects_unknown_provider_event_binding(tmp_path: Path) -> None:
    payload = _payload()
    payload["event_bindings"][0]["provider_event_id"] = "TGE-999"

    with pytest.raises(ValueError, match="unknown provider Event"):
        load_r19_provider_supplement(_write(tmp_path, payload), repository_root=ROOT)


def test_rejects_binding_source_digest_disagreement(tmp_path: Path) -> None:
    payload = _payload()
    payload["event_bindings"][0]["residual_source_sha256"] = "0" * 64

    with pytest.raises(ValueError, match="source digest disagrees"):
        load_r19_provider_supplement(_write(tmp_path, payload), repository_root=ROOT)


def test_rejects_binding_trigger_disagreement(tmp_path: Path) -> None:
    payload = _payload()
    payload["event_bindings"][0]["residual_trigger"] = {
        "start": 0,
        "end": 5,
        "source_text": "Sacks",
    }

    with pytest.raises(ValueError, match="trigger disagrees"):
        load_r19_provider_supplement(_write(tmp_path, payload), repository_root=ROOT)


def test_rejects_unresolved_required_references() -> None:
    supplement = load_r19_provider_supplement(SUPPLEMENT, repository_root=ROOT)

    with pytest.raises(ValueError, match="unresolved required references"):
        require_resolved_closure(supplement, _empty_repository())


def test_rejects_resolved_identity_that_does_not_exist() -> None:
    payload = _payload()
    payload["identity_mappings"][0]["actor_id"] = "act_sacks_fixture"
    payload["identity_mappings"][0]["unresolved_reason"] = None
    payload["event_evidence"][0]["evidence_target_id"] = "etg_fixture"
    payload["event_evidence"][0]["unresolved_reason"] = None
    payload["event_evidence"][1]["evidence_target_id"] = "etg_fixture_2"
    payload["event_evidence"][1]["unresolved_reason"] = None
    supplement = R19ProviderSupplement.model_validate_json(json.dumps(payload))

    with pytest.raises(ValueError, match="does not exist"):
        require_resolved_closure(supplement, _empty_repository())
