from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[3]


def _module() -> Any:
    path = ROOT / "scripts/verify_organization_held_out_packet.py"
    spec = importlib.util.spec_from_file_location("verify_organization_held_out_packet_test", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_held_out_packet_is_source_bound_disjoint_and_human_reviewed() -> None:
    result = _module().validate_held_out_packet(verify_fixture_bytes=False)

    assert result["status"] == "complete"
    assert result["entry_count"] == 50
    assert result["annotated_count"] == 50
    assert result["unannotated_count"] == 0
    assert result["literal_gold_count"] == 150
    assert result["resolved_gold_count"] == 5
    assert result["development_overlap_count"] == 0
    assert sorted(result["fixture_counts"].values()) == [7, 8, 35]
    assert "negative_control" in result["selection_conditions"]


def test_held_out_packet_rejects_mixed_none_and_nonliteral_gold(tmp_path: Path) -> None:
    module = _module()
    packet = module.DEFAULT_PACKET.read_text(encoding="utf-8")
    invalid = packet.replace(
        "### Gold Organization Mentions\n\n-",
        "### Gold Organization Mentions\n\n- None\n- invented organization",
        1,
    )
    path = tmp_path / "invalid.md"
    path.write_text(invalid, encoding="utf-8")

    with pytest.raises(ValueError, match="cannot mix None"):
        module.validate_held_out_packet(path, verify_fixture_bytes=False)


def test_held_out_packet_requires_notes_for_resolved_organization(tmp_path: Path) -> None:
    module = _module()
    packet = module.DEFAULT_PACKET.read_text(encoding="utf-8")
    invalid = packet.replace(
        "- Anthropic\n\n### Reviewer notes",
        "- resolved: name <= Anthropic | Anthropic\n\n### Reviewer notes",
        1,
    )
    path = tmp_path / "invalid.md"
    path.write_text(invalid, encoding="utf-8")

    with pytest.raises(ValueError, match="requires Reviewer notes"):
        module.validate_held_out_packet(path, verify_fixture_bytes=False)


def test_held_out_packet_requires_exact_source_components_for_resolved_gold(
    tmp_path: Path,
) -> None:
    module = _module()
    packet = module.DEFAULT_PACKET.read_text(encoding="utf-8")
    invalid = packet.replace(
        "resolved: United States AISI <= AISIs | United States",
        "resolved: United States AISI",
        1,
    )
    path = tmp_path / "invalid.md"
    path.write_text(invalid, encoding="utf-8")

    with pytest.raises(ValueError, match="must declare exact source components"):
        module.validate_held_out_packet(path, verify_fixture_bytes=False)
