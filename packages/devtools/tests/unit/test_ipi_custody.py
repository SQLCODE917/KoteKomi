"""Reserved custody validation and sealing."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from kotekomi_devtools.ipi_custody import (
    CustodyError,
    fill_text_digests,
    manifest_summary,
    seal,
    text_digest,
    validate_manifest,
)
from kotekomi_devtools.ipi_measurement import load_approved_manifest

SOURCE = "raw/241030_Allen_Safety_Network.pdf"
SOURCE_SHA = "a" * 64


def _inspected(*, excluded: bool = False, inspected: tuple[str, ...] = ()) -> dict[str, Any]:
    return {
        "record": "ipi-inspected-material-v1",
        "sources": [
            {
                "path": SOURCE,
                "sha256": SOURCE_SHA,
                "used_by_partition": "reserved",
                "excluded_from_reserved": excluded,
                "inspected_paragraph_sha256": list(inspected),
            }
        ],
    }


def _reader(path: Path) -> str:
    return (
        "opening context\nreserved passage 1\nreserved passage 2\nreserved passage 3\n"
        "reserved passage 4\nreserved passage 5\nreserved passage 6\nclosing context"
    )


def _missing_reader(path: Path) -> str:
    return "a different document"


def _manifest(texts: list[str], kinds: list[str]) -> dict[str, Any]:
    statements = [
        {
            "reference_id": f"R-RES-{index:02d}",
            "kind": kind,
            "statement": "A reserved statement.",
            "required_content": "participants and relation",
            "admissible_omissions": "none",
            "in_scope_rationale": "an atomic meaning.",
        }
        for index, kind in enumerate(kinds, 1)
    ]
    passages = [
        {
            "passage_id": f"RES-{index:02d}",
            "source_path": SOURCE,
            "source_sha256": SOURCE_SHA,
            "page": index,
            "text": text,
            "text_sha256": text_digest(text),
            "context_before": "opening context",
            "context_after": "closing context",
            "statements": [statements[index - 1]],
        }
        for index, text in enumerate(texts, 1)
    ]
    return {
        "record": "ipi-reserved-manifest-v1",
        "revision": "7dc9a44",
        "reviewer": "reviewer",
        "sealed_on": "2026-11-06",
        "attempt_budget_seconds": 300,
        "passages": passages,
    }


def _well_formed() -> dict[str, Any]:
    return _manifest(
        [f"reserved passage {index}" for index in range(1, 7)],
        [
            "straightforward",
            "straightforward",
            "qualified",
            "qualified",
            "qualified",
            "straightforward",
        ],
    )


def test_valid_manifest_seals_with_a_reviewable_summary(tmp_path: Path) -> None:
    manifest = validate_manifest(_well_formed(), _inspected(), _reader)
    summary = manifest_summary(manifest)
    assert summary["passage_count"] == 6
    assert summary["straightforward_statement_count"] == 3
    path, digest = seal(tmp_path / "custody", _well_formed(), _inspected(), _reader)
    assert path.exists()
    assert len(digest) == 64
    assert "reserved passage" not in json.dumps(summary)


def test_a_passage_outside_its_declared_source_is_rejected() -> None:
    with pytest.raises(CustodyError, match="does not appear"):
        validate_manifest(_well_formed(), _inspected(), _missing_reader)


def test_a_statement_without_text_is_rejected() -> None:
    payload = _well_formed()
    payload["passages"][0]["statements"][0]["statement"] = ""
    with pytest.raises(CustodyError, match="statement"):
        validate_manifest(payload, _inspected(), _reader)


def test_missing_surrounding_context_is_rejected() -> None:
    payload = _well_formed()
    payload["passages"][2]["context_after"] = ""
    with pytest.raises(CustodyError, match="context_after"):
        validate_manifest(payload, _inspected(), _reader)


def test_excluded_source_cannot_supply_a_reserved_passage() -> None:
    with pytest.raises(CustodyError, match="excluded"):
        validate_manifest(_well_formed(), _inspected(excluded=True), _reader)


def test_inspected_paragraph_cannot_become_reserved() -> None:
    inspected_digest = text_digest("reserved passage 3")
    with pytest.raises(CustodyError, match="inspected-material"):
        validate_manifest(_well_formed(), _inspected(inspected=(inspected_digest,)), _reader)


def test_partition_requires_six_passages() -> None:
    payload = _well_formed()
    payload["passages"] = payload["passages"][:5]
    with pytest.raises(CustodyError, match="six|6"):
        validate_manifest(payload, _inspected(), _reader)


def test_partition_requires_two_qualified_statements() -> None:
    payload = _manifest(
        [f"reserved passage {index}" for index in range(1, 7)],
        ["straightforward"] * 5 + ["qualified"],
    )
    with pytest.raises(CustodyError, match="qualified"):
        validate_manifest(payload, _inspected(), _reader)


def test_a_sealed_partition_cannot_be_resealed(tmp_path: Path) -> None:
    seal(tmp_path / "custody", _well_formed(), _inspected(), _reader)
    with pytest.raises(CustodyError, match="already exists"):
        seal(tmp_path / "custody", _well_formed(), _inspected(), _reader)


def test_a_sealed_reserved_manifest_can_be_used_as_the_comparison_manifest(
    tmp_path: Path,
) -> None:
    payload = _well_formed()
    seal(tmp_path / "custody", payload, _inspected(), _reader)
    approved = load_approved_manifest(tmp_path / "custody" / "reserved-manifest.json")
    assert approved.attempt_budget_seconds == 300
    assert len(approved.reference_ids) == 6


def test_a_reserved_manifest_without_a_budget_is_rejected() -> None:
    payload = _well_formed()
    payload["attempt_budget_seconds"] = 0
    with pytest.raises(CustodyError, match="attempt budget"):
        validate_manifest(payload, _inspected(), _reader)
    payload = _well_formed()
    for row in payload["passages"]:
        assert isinstance(row, dict)
        row["text_sha256"] = ""
    filled = fill_text_digests(payload)
    assert [row["text_sha256"] for row in filled["passages"]] == [
        text_digest(f"reserved passage {index}") for index in range(1, 7)
    ]
