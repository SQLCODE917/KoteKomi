import hashlib
import json
from pathlib import Path
from typing import Literal, NotRequired, TypedDict, cast

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "pdf"


class FixtureEntry(TypedDict):
    path: str
    kind: Literal["pdf", "text"]
    origin: Literal["downloaded", "generated"]
    source_url: NotRequired[str]
    generator: NotRequired[str]
    generated_from: NotRequired[list[str]]
    password: NotRequired[str]
    declared_password: NotRequired[str]
    sha256: str
    size_bytes: int
    requirements: list[str]
    safety: str
    note: NotRequired[str]


class NonFileTest(TypedDict):
    requirement: str
    fixture: str
    method: str


class FixtureManifest(TypedDict):
    schema_version: int
    requirement_classes: list[str]
    fixtures: list[FixtureEntry]
    non_file_tests: list[NonFileTest]
    upstream_notices: dict[str, str]


def _load_manifest() -> FixtureManifest:
    return cast(
        FixtureManifest,
        json.loads((FIXTURE_ROOT / "manifest.json").read_text(encoding="utf-8")),
    )


def test_pdf_fixture_manifest_pins_every_fixture_byte() -> None:
    manifest = _load_manifest()
    assert manifest["schema_version"] == 1

    paths = [entry["path"] for entry in manifest["fixtures"]]
    assert len(paths) == len(set(paths))

    for entry in manifest["fixtures"]:
        relative_path = Path(entry["path"])
        assert not relative_path.is_absolute()
        assert ".." not in relative_path.parts
        fixture = FIXTURE_ROOT / relative_path
        contents = fixture.read_bytes()
        assert len(contents) == entry["size_bytes"], entry["path"]
        assert hashlib.sha256(contents).hexdigest() == entry["sha256"], entry["path"]
        if entry["kind"] == "pdf":
            assert contents.startswith(b"%PDF-"), entry["path"]
        else:
            contents.decode("utf-8")


def test_pdf_fixture_manifest_covers_every_file_backed_requirement() -> None:
    manifest = _load_manifest()
    covered_requirements = {
        requirement
        for entry in manifest["fixtures"]
        for requirement in entry["requirements"]
    }

    assert covered_requirements == set(manifest["requirement_classes"])


def test_pdf_fixture_manifest_makes_negative_fixture_safety_explicit() -> None:
    manifest = _load_manifest()
    corrupt_entries = [
        entry for entry in manifest["fixtures"] if entry["path"].startswith("corrupt/")
    ]

    assert corrupt_entries
    assert all(
        entry["safety"] == "intentionally_malformed_do_not_open"
        for entry in corrupt_entries
    )
    assert all(
        entry["path"].startswith("corrupt/")
        for entry in manifest["fixtures"]
        if entry["safety"] == "intentionally_malformed_do_not_open"
    )


def test_pdf_fixture_manifest_uses_project_owned_canonical_mixed_and_encrypted_inputs() -> None:
    manifest = _load_manifest()
    entries_by_path = {entry["path"]: entry for entry in manifest["fixtures"]}

    mixed = entries_by_path["mixed/kotekomi-born-digital-plus-linn.pdf"]
    assert mixed["origin"] == "generated"
    assert mixed.get("generated_from") == [
        "mixed/kotekomi-born-digital-page.pdf",
        "ocr/ocrmypdf-linn.pdf",
    ]

    encrypted = entries_by_path["encrypted/kotekomi-encrypted-password-test.pdf"]
    assert encrypted["origin"] == "generated"
    assert encrypted.get("password") == "test"
    assert encrypted["safety"] == "encrypted_requires_password"


def test_invalid_coordinate_requirement_is_a_parser_result_mutation() -> None:
    manifest = _load_manifest()

    assert manifest["non_file_tests"] == [
        {
            "requirement": "invalid_or_conflicting_parser_coordinates",
            "fixture": "layout/nist-8x11-double-column-sample.pdf",
            "method": (
                "Mutate the known-good parser result to inject impossible or contradictory "
                "regions; do not encode parser-output corruption in source PDF bytes."
            ),
        }
    ]
