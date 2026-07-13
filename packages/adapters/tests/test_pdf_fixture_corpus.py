import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Literal, NotRequired, TypedDict, cast

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "pdf"


class FixtureEntry(TypedDict):
    fixture_id: str
    path: str
    media_type: str
    origin: Literal["downloaded", "generated", "user_supplied"]
    source_url: NotRequired[str]
    source_sha256: NotRequired[str]
    local_sha256: str
    size_bytes: int
    generator_version: NotRequired[str]
    generated_from: NotRequired[list[str]]
    license_profile: str
    license_disposition: str
    expectation_profile: str
    gold_path: NotRequired[str]
    fixture_password: NotRequired[str]
    declared_password: NotRequired[str]
    requirements: list[str]
    availability: NotRequired[Literal["external_only"]]


class GoldArtifact(TypedDict):
    path: str
    sha256: str


class FixtureManifest(TypedDict):
    schema_version: int
    downloaded_at: str
    generator: dict[str, str]
    requirement_classes: list[str]
    license_profiles: dict[str, dict[str, str]]
    expectation_profiles: dict[str, dict[str, object]]
    fixtures: list[FixtureEntry]
    gold_artifacts: list[GoldArtifact]
    parser_output_mutations: list[str]


def _load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_manifest() -> FixtureManifest:
    return cast(FixtureManifest, _load_json(FIXTURE_ROOT / "manifest.json"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _pdf_page_count(path: Path, *, password: str | None = None) -> int:
    command = ["pdfinfo"]
    if password is not None:
        command.extend(("-upw", password))
    command.append(str(path))
    output = subprocess.run(command, check=True, capture_output=True, text=True).stdout
    pages_line = next(line for line in output.splitlines() if line.startswith("Pages:"))
    return int(pages_line.partition(":")[2].strip())


def test_pdf_fixture_manifest_pins_every_fixture_and_gold_artifact() -> None:
    manifest = _load_manifest()
    assert manifest["schema_version"] == 2

    paths = [entry["path"] for entry in manifest["fixtures"]]
    fixture_ids = [entry["fixture_id"] for entry in manifest["fixtures"]]
    assert len(paths) == len(set(paths))
    assert len(fixture_ids) == len(set(fixture_ids))

    for entry in manifest["fixtures"]:
        relative_path = Path(entry["path"])
        assert not relative_path.is_absolute()
        assert ".." not in relative_path.parts
        fixture = FIXTURE_ROOT / relative_path
        if entry.get("availability") == "external_only":
            assert entry["origin"] == "downloaded"
            assert entry["license_disposition"] == "external_conformance_only"
            assert not fixture.exists()
            assert entry.get("source_url")
            assert entry.get("source_sha256") == entry["local_sha256"]
            continue
        contents = fixture.read_bytes()
        assert len(contents) == entry["size_bytes"], entry["fixture_id"]
        assert hashlib.sha256(contents).hexdigest() == entry["local_sha256"], entry["fixture_id"]
        if entry["origin"] != "generated":
            assert entry.get("source_sha256") == entry["local_sha256"]
        if entry["media_type"] == "application/pdf":
            assert contents.startswith(b"%PDF-"), entry["fixture_id"]
        else:
            contents.decode("utf-8")

    for gold in manifest["gold_artifacts"]:
        assert _sha256(FIXTURE_ROOT / gold["path"]) == gold["sha256"]

    corpus_files = {
        path.relative_to(FIXTURE_ROOT).as_posix()
        for path in FIXTURE_ROOT.rglob("*")
        if path.is_file() and path.suffix in {".pdf", ".txt"}
    }
    committed_paths = {
        entry["path"]
        for entry in manifest["fixtures"]
        if entry.get("availability") != "external_only"
    }
    assert corpus_files == committed_paths


def test_manifest_resolves_license_and_gold_expectation_profiles() -> None:
    manifest = _load_manifest()
    covered_requirements = {
        requirement for entry in manifest["fixtures"] for requirement in entry["requirements"]
    }

    assert covered_requirements == set(manifest["requirement_classes"])
    assert all(
        entry["license_profile"] in manifest["license_profiles"]
        and entry["expectation_profile"] in manifest["expectation_profiles"]
        for entry in manifest["fixtures"]
    )
    entries = {entry["fixture_id"]: entry for entry in manifest["fixtures"]}
    assert entries["pdf_double_column_nist_aip"]["license_disposition"] == (
        "external_conformance_only"
    )
    assert entries["pdf_mixed_born_digital_scan_v1"].get("gold_path") == (
        "gold/mixed_born_digital_scan_v1.json"
    )
    assert entries["pdf_complex_table_v1"].get("gold_path") == "gold/complex_table_v1.json"
    assert entries["pdf_adversarial_columns_hierarchy_v1"].get("gold_path") == (
        "gold/adversarial_columns_hierarchy_v1.json"
    )


def test_project_fixture_generator_is_byte_reproducible(tmp_path: Path) -> None:
    first_root = tmp_path / "first"
    second_root = tmp_path / "second"
    generator = FIXTURE_ROOT / "generate_project_fixtures.py"
    for output_root in (first_root, second_root):
        subprocess.run(
            (sys.executable, generator, "--output-root", output_root),
            check=True,
        )

    generated_paths = (
        "mixed/mixed_born_digital_scan_v1.pdf",
        "tables/complex_table_v1.pdf",
        "layout/adversarial_columns_hierarchy_v1.pdf",
        "encrypted/encrypted_aes256_v1.pdf",
        "corrupt/generated/corrupt_truncated_v1.pdf",
        "corrupt/generated/corrupt_bad_xref_v1.pdf",
        "corrupt/generated/corrupt_bad_stream_length_v1.pdf",
        "corrupt/generated/corrupt_missing_page_tree_v1.pdf",
    )
    manifest_entries = {entry["path"]: entry for entry in _load_manifest()["fixtures"]}
    for relative_path in generated_paths:
        first = first_root / relative_path
        second = second_root / relative_path
        assert first.read_bytes() == second.read_bytes()
        assert _sha256(first) == manifest_entries[relative_path]["local_sha256"]


def test_mixed_fixture_has_exact_three_page_gold_contract() -> None:
    fixture = FIXTURE_ROOT / "mixed" / "mixed_born_digital_scan_v1.pdf"
    gold = cast(
        dict[str, object],
        _load_json(FIXTURE_ROOT / "gold" / "mixed_born_digital_scan_v1.json"),
    )
    page_processing = cast(list[dict[str, object]], gold["page_processing"])

    assert _pdf_page_count(fixture) == 3
    assert [page["page"] for page in page_processing] == [1, 2, 3]
    assert [page["ocr_decision"] for page in page_processing] == [
        "not_required",
        "required",
        "not_required",
    ]
    assert [page["ocr_provenance_required"] for page in page_processing] == [
        False,
        True,
        False,
    ]
    assert page_processing[2]["decorative_image_count"] == 1


def test_complex_table_gold_graph_has_exact_spans_ancestry_and_regions() -> None:
    fixture = FIXTURE_ROOT / "tables" / "complex_table_v1.pdf"
    gold = cast(
        dict[str, object],
        _load_json(FIXTURE_ROOT / "gold" / "complex_table_v1.json"),
    )
    cells = cast(list[dict[str, object]], gold["cells"])
    cells_by_id = {cast(str, cell["id"]): cell for cell in cells}

    assert _pdf_page_count(fixture) == 1
    assert len(cells) == 21
    assert cells_by_id["measurements"]["column_span"] == 4
    assert cells_by_id["year_2024"]["column_span"] == 2
    assert cells_by_id["year_2025"]["column_span"] == 2
    assert cells_by_id["region_a"]["row_span"] == 2
    assert cells_by_id["b_q1_2024"]["text"] == "20\nadjusted"
    assert cells_by_id["a_row1_q1_2025"]["text"] == ""
    assert cells_by_id["b_q2_2025"]["column_header_ancestry"] == [
        "measurements",
        "year_2025",
        "q2_2025",
    ]
    assert all(len(cast(list[object], cell["source_region"])) == 5 for cell in cells)


def test_adversarial_layout_fixture_pins_columns_furniture_hierarchy_and_rotation() -> None:
    fixture = FIXTURE_ROOT / "layout" / "adversarial_columns_hierarchy_v1.pdf"
    gold = cast(
        dict[str, object],
        _load_json(FIXTURE_ROOT / "gold" / "adversarial_columns_hierarchy_v1.json"),
    )
    pdfinfo = subprocess.run(
        ("pdfinfo", "-f", "1", "-l", "999999", "-box", fixture),
        check=True,
        capture_output=True,
        text=True,
    ).stdout

    assert _pdf_page_count(fixture) == gold["page_count"] == 3
    assert [int(rotation) for rotation in re.findall(r"Page\s+\d+ rot:\s+(\d+)", pdfinfo)] == gold[
        "page_rotations"
    ]
    logical_lines = cast(list[str], gold["logical_analysis_lines"])
    assert logical_lines.index("LEFT THREE follows left two.") < logical_lines.index(
        "RIGHT ONE begins the right narrative."
    )
    assert logical_lines.index("TWO C2 follows two C1.") < logical_lines.index(
        "THREE C1 begins column three."
    )
    assert len(cast(list[list[str]], gold["hierarchy"])) == 5


def test_aes256_fixture_requires_the_right_password_without_leaking_it() -> None:
    fixture = FIXTURE_ROOT / "encrypted" / "encrypted_aes256_v1.pdf"
    assert shutil.which("qpdf") is not None

    no_password = subprocess.run(
        ("qpdf", "--check", fixture.name),
        cwd=fixture.parent,
        capture_output=True,
        text=True,
    )
    wrong_password = subprocess.run(
        ("qpdf", "--password=wrong", "--check", fixture.name),
        cwd=fixture.parent,
        capture_output=True,
        text=True,
    )
    correct_password = subprocess.run(
        ("qpdf", "--password=test", "--check", fixture.name),
        cwd=fixture.parent,
        capture_output=True,
        text=True,
    )
    encryption = subprocess.run(
        ("qpdf", "--password=test", "--show-encryption", fixture.name),
        cwd=fixture.parent,
        capture_output=True,
        text=True,
    )

    assert no_password.returncode != 0
    assert wrong_password.returncode != 0
    assert correct_password.returncode == 0
    assert encryption.returncode == 0
    assert "R = 5" in encryption.stdout
    assert "stream encryption method: AESv3" in encryption.stdout
    assert "string encryption method: AESv3" in encryption.stdout
    assert "file encryption method: AESv3" in encryption.stdout
    assert "invalid password" in no_password.stderr
    assert "invalid password" in wrong_password.stderr
    assert "test" not in no_password.stderr + wrong_password.stderr + correct_password.stderr
    assert _pdf_page_count(fixture, password="test") == 1


def test_controlled_corruptions_are_precise_mutations_not_opaque_files() -> None:
    gold = cast(
        dict[str, object],
        _load_json(FIXTURE_ROOT / "gold" / "controlled_corruptions_v1.json"),
    )
    variants = cast(list[dict[str, str]], gold["variants"])

    assert len(variants) == 4
    for variant in variants:
        fixture = FIXTURE_ROOT / variant["path"]
        assert _sha256(fixture) == variant["sha256"]
        assert variant["mutation"]
        check = subprocess.run(
            ("qpdf", "--check", fixture),
            capture_output=True,
            text=True,
            timeout=10,
        )
        diagnostic = f"{check.stdout}\n{check.stderr}"
        assert check.returncode != 0 or "WARNING" in diagnostic
    assert (
        b"xref\n"
        not in (FIXTURE_ROOT / "corrupt" / "generated" / "corrupt_truncated_v1.pdf").read_bytes()
    )
    assert (
        b"/Pages 9 0 R"
        in (
            FIXTURE_ROOT / "corrupt" / "generated" / "corrupt_missing_page_tree_v1.pdf"
        ).read_bytes()
    )


def test_invalid_coordinate_cases_are_declared_as_parser_output_mutations() -> None:
    assert _load_manifest()["parser_output_mutations"] == [
        "negative_x0_or_y0",
        "x1_before_x0",
        "y1_before_y0",
        "beyond_media_box",
        "inside_media_box_outside_crop_box",
        "non_finite_coordinate",
        "page_outside_inventory",
        "wrong_representation",
        "node_region_page_disagreement",
        "wrong_coordinate_system",
        "rotation_applied_twice",
        "region_text_range_disagreement",
        "duplicate_contradictory_regions",
        "reading_order_self_edge",
        "reading_order_cycle",
        "parent_from_different_representation",
    ]
