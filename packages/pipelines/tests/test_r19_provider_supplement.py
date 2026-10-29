"""Focused tests for the R19 provider supplement schema and gated loader."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from kotekomi_pipelines.r19_provider_supplement import (
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


def test_loads_proposed_supplement_and_reports_unresolved_references() -> None:
    supplement = load_r19_provider_supplement(SUPPLEMENT, repository_root=ROOT)

    assert supplement.review_status == "proposed"
    assert [item.residual_event_id for item in supplement.event_bindings] == [
        "AHE-022",
        "AHE-051",
    ]
    assert supplement.event_bindings[0].provider_event_id == "TGE-018"
    unresolved = unresolved_references(supplement)
    assert any("EGE-019" in item for item in unresolved)
    assert any("EGE-020" in item for item in unresolved)
    assert any("evidence_target_id" in item for item in unresolved)


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


def test_rejects_unresolved_required_references() -> None:
    supplement = load_r19_provider_supplement(SUPPLEMENT, repository_root=ROOT)

    with pytest.raises(ValueError, match="unresolved required references"):
        require_resolved_closure(supplement)
