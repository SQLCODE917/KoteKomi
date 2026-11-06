"""Reserved custody validation and sealing."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from kotekomi_devtools.ipi_custody import (
    CustodyError,
    fill_text_digests,
    manifest_summary,
    seal,
    text_digest,
    validate_manifest,
)

SOURCE = "raw/241030_Allen_Safety_Network.pdf"
SOURCE_SHA = "a" * 64


def _inspected(*, excluded: bool = False, inspected: tuple[str, ...] = ()) -> dict[str, object]:
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


def _manifest(texts: list[str], kinds: list[str]) -> dict[str, object]:
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
            "context_before": "",
            "context_after": "",
            "statements": [statements[index - 1]],
        }
        for index, text in enumerate(texts, 1)
    ]
    return {
        "record": "ipi-reserved-manifest-v1",
        "revision": "7dc9a44",
        "reviewer": "reviewer",
        "sealed_on": "2026-11-06",
        "passages": passages,
    }


def _well_formed() -> dict[str, object]:
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
    manifest = validate_manifest(_well_formed(), _inspected())
    summary = manifest_summary(manifest)
    assert summary["passage_count"] == 6
    assert summary["straightforward_statement_count"] == 3
    path, digest = seal(tmp_path / "custody", _well_formed(), _inspected())
    assert path.exists()
    assert len(digest) == 64
    assert "reserved passage" not in json.dumps(summary)


def test_excluded_source_cannot_supply_a_reserved_passage() -> None:
    with pytest.raises(CustodyError, match="excluded"):
        validate_manifest(_well_formed(), _inspected(excluded=True))


def test_inspected_paragraph_cannot_become_reserved() -> None:
    payload = _well_formed()
    inspected_digest = text_digest("reserved passage 3")
    with pytest.raises(CustodyError, match="inspected-material"):
        validate_manifest(payload, _inspected(inspected=(inspected_digest,)))


def test_partition_requires_six_passages() -> None:
    payload = _well_formed()
    payload["passages"] = payload["passages"][:5]
    with pytest.raises(CustodyError, match="six|6"):
        validate_manifest(payload, _inspected())


def test_partition_requires_two_qualified_statements() -> None:
    payload = _manifest(
        [f"reserved passage {index}" for index in range(1, 7)],
        ["straightforward"] * 5 + ["qualified"],
    )
    with pytest.raises(CustodyError, match="qualified"):
        validate_manifest(payload, _inspected())


def test_a_sealed_partition_cannot_be_resealed(tmp_path: Path) -> None:
    seal(tmp_path / "custody", _well_formed(), _inspected())
    with pytest.raises(CustodyError, match="already exists"):
        seal(tmp_path / "custody", _well_formed(), _inspected())


def test_fill_text_digests_computes_each_passage_digest() -> None:
    payload = _well_formed()
    for row in payload["passages"]:
        row["text_sha256"] = ""
    filled = fill_text_digests(payload)
    assert [row["text_sha256"] for row in filled["passages"]] == [
        text_digest(f"reserved passage {index}") for index in range(1, 7)
    ]
