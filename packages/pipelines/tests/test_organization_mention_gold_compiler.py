from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[3]


def _module() -> Any:
    path = ROOT / "scripts/organization_mention_gold_compiler.py"
    spec = importlib.util.spec_from_file_location("organization_mention_gold_compiler_test", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_reviewed_packet_compiles_to_exact_disjoint_machine_gold() -> None:
    module = _module()
    catalog = module.compile_held_out_catalog(verify_fixture_bytes=False)

    assert catalog["paragraph_count"] == 50
    assert catalog["literal_gold_count"] == 150
    assert catalog["resolved_reference_count"] == 5
    assert catalog["development_overlap_count"] == 0
    assert len(catalog["segments"]) > 50
    assert sum(len(segment["gold_mentions"]) for segment in catalog["segments"]) == 150
    for segment in catalog["segments"]:
        for mention in segment["gold_mentions"]:
            assert segment["source_text"][mention["start"] : mention["end"]] == mention["text"]
            assert (
                segment["authoritative_text"][
                    mention["authoritative_start"] : mention["authoritative_end"]
                ]
                == mention["authoritative_text"]
            )
            assert " ".join(mention["authoritative_text"].split()) == mention["text"]


def test_longer_gold_reserves_nested_alias_characters_and_repeats_use_source_order() -> None:
    catalog = _module().compile_held_out_catalog(verify_fixture_bytes=False)
    ho_026 = [segment for segment in catalog["segments"] if segment["case_ids"] == ["HO-026"]]
    mentions = [mention for segment in ho_026 for mention in segment["gold_mentions"]]
    full = next(mention for mention in mentions if mention["text"] == "U.S. AISI")
    short = [mention for mention in mentions if mention["text"] == "AISI"]

    assert len(short) == 3
    assert all(
        not (
            mention["paragraph_start"] >= full["paragraph_start"]
            and mention["paragraph_end"] <= full["paragraph_end"]
        )
        for mention in short
    )
    assert [mention["paragraph_start"] for mention in short] == sorted(
        mention["paragraph_start"] for mention in short
    )


def test_resolved_reference_gold_binds_discontinuous_source_components_but_is_unscored() -> None:
    catalog = _module().compile_held_out_catalog(verify_fixture_bytes=False)
    united_states = next(
        item
        for item in catalog["resolved_references"]
        if item["expected_organization_name"] == "United States AISI"
    )

    assert united_states["scoring_status"] == "excluded_reference_resolution_gold"
    assert [item["text"] for item in united_states["source_components"]] == [
        "AISIs",
        "United States",
    ]
    assert len({item["paragraph_start"] for item in united_states["source_components"]}) == 2


def test_catalog_compilation_is_byte_deterministic() -> None:
    module = _module()
    first = module.canonical_catalog_json(
        module.compile_held_out_catalog(verify_fixture_bytes=False)
    )
    second = module.canonical_catalog_json(
        module.compile_held_out_catalog(verify_fixture_bytes=False)
    )

    assert first == second


def test_catalog_compiler_rejects_unresolvable_gold(tmp_path: Path) -> None:
    module = _module()
    packet = module.DEFAULT_PACKET.read_text(encoding="utf-8")
    invalid = packet.replace("- World Economic Forum", "- absent literal", 1)
    path = tmp_path / "invalid.md"
    path.write_text(invalid, encoding="utf-8")

    with pytest.raises(ValueError, match="eligible source occurrences"):
        module.compile_held_out_catalog(path, verify_fixture_bytes=False)
