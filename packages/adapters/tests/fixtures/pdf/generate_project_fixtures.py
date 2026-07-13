"""Generate KoteKomi-owned PDF ingestion fixtures deterministically.

The encrypted document deliberately uses fixed fixture-only encryption inputs.
It is a parser fixture, not an example of production encryption.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

FIXTURE_ROOT = Path(__file__).resolve().parent
QPDF_VERSION = "qpdf version 11.9.0"
GENERATOR_VERSION = "kotekomi_pdf_fixture_generator_v3"


def _pdf_string(value: str) -> bytes:
    escaped = value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    return f"({escaped})".encode("ascii")


def _serialize_pdf(objects: tuple[bytes, ...], *, trailer_entries: bytes = b"") -> bytes:
    output = bytearray(b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for object_number, body in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{object_number} 0 obj\n".encode("ascii"))
        output.extend(body)
        output.extend(b"\nendobj\n")

    xref_offset = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    output.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R ".encode("ascii")
        + trailer_entries
        + (f">>\nstartxref\n{xref_offset}\n%%EOF\n").encode("ascii")
    )
    return bytes(output)


def _stream(contents: bytes) -> bytes:
    return (
        b"<< /Length "
        + str(len(contents)).encode("ascii")
        + b" >>\nstream\n"
        + contents
        + b"endstream"
    )


def _unicode_cmap() -> bytes:
    contents = b"""/CIDInit /ProcSet findresource begin
12 dict begin
begincmap
/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def
/CMapName /KoteKomiASCII def
/CMapType 2 def
1 begincodespacerange
<00> <7F>
endcodespacerange
1 beginbfrange
<00> <7F> <0000>
endbfrange
endcmap
CMapName currentdict /CMap defineresource pop
end
end
"""
    return _stream(contents)


def _authored_mixed_pages_pdf() -> bytes:
    page_one_lines = (
        "KoteKomi Mixed PDF Fixture",
        "This page is born-digital and must use embedded text.",
        "Page 2 is an image-only scan and must use OCR.",
        "Fixture ID: mixed_born_digital_scan_v1",
    )
    page_three_lines = (
        "KoteKomi Mixed PDF Fixture - Page 3",
        "This born-digital text must remain embedded text.",
        "The small blue square is decorative and must not trigger OCR.",
    )

    def text_stream(lines: tuple[str, ...], *, decorative_image: bool = False) -> bytes:
        commands = [b"BT", b"/F1 22 Tf", b"72 720 Td", _pdf_string(lines[0]) + b" Tj"]
        for line in lines[1:]:
            commands.extend((b"0 -36 Td", b"/F1 12 Tf", _pdf_string(line) + b" Tj"))
        commands.append(b"ET")
        if decorative_image:
            commands.extend((b"q", b"24 0 0 24 516 696 cm", b"/Im1 Do", b"Q"))
        return b"\n".join(commands) + b"\n"

    page_one = text_stream(page_one_lines)
    page_three = text_stream(page_three_lines, decorative_image=True)
    image = b"\x20\x80\xe0"
    image_object = (
        b"<< /Type /XObject /Subtype /Image /Width 1 /Height 1 "
        b"/ColorSpace /DeviceRGB /BitsPerComponent 8 /Length 3 >>\nstream\n"
        + image
        + b"\nendstream"
    )
    return _serialize_pdf(
        (
            b"<< /Type /Catalog /Pages 2 0 R >>",
            b"<< /Type /Pages /Kids [3 0 R 4 0 R] /Count 2 >>",
            (
                b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                b"/CropBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> "
                b"/Contents 7 0 R >>"
            ),
            (
                b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                b"/CropBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> "
                b"/XObject << /Im1 6 0 R >> >> /Contents 8 0 R >>"
            ),
            (
                b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica "
                b"/Encoding /WinAnsiEncoding /ToUnicode 9 0 R >>"
            ),
            image_object,
            _stream(page_one),
            _stream(page_three),
            _unicode_cmap(),
        )
    )


def _complex_table_pdf() -> bytes:
    commands = [
        b"BT /F1 16 Tf 72 690 Td (Table 1. Regional measurements) Tj ET",
        b"BT /F1 10 Tf 72 668 Td (See Table 1 for regional measurement context.) Tj ET",
        b"BT /F1 9 Tf 72 650 Td (Units: index points) Tj ET",
        b"0.8 w",
    ]
    for x in (72, 172, 252, 332, 412, 492):
        commands.append(f"{x} 620 m {x} 400 l S".encode("ascii"))
    for y in (620, 590, 560, 530, 490, 450, 400):
        commands.append(f"72 {y} m 492 {y} l S".encode("ascii"))

    labels = (
        (258, 600, "Measurements", 12),
        (210, 570, "2024", 11),
        (370, 570, "2025", 11),
        (198, 540, "Q1", 10),
        (278, 540, "Q2", 10),
        (358, 540, "Q1", 10),
        (438, 540, "Q2", 10),
        (92, 500, "Region A", 10),
        (198, 505, "10", 10),
        (278, 505, "11", 10),
        (198, 465, "12", 10),
        (278, 465, "13", 10),
        (92, 420, "Region B", 10),
        (190, 425, "20", 10),
        (185, 412, "adjusted", 7),
        (278, 425, "21", 10),
        (358, 425, "22", 10),
        (438, 425, "23(a)", 10),
    )

    for x, y, label, size in labels:
        commands.append(
            b"BT /F1 "
            + str(size).encode("ascii")
            + b" Tf "
            + f"{x} {y} Td ".encode("ascii")
            + _pdf_string(label)
            + b" Tj ET"
        )
    commands.append(
        b"BT /F1 9 Tf 72 375 Td "
        + _pdf_string(
            "(a): adjusted value. Note: blank 2025 cells for Region A are intentionally empty."
        )
        + b" Tj ET"
    )
    content = b"\n".join(commands) + b"\n"
    return _serialize_pdf(
        (
            b"<< /Type /Catalog /Pages 2 0 R >>",
            b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            (
                b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                b"/CropBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> "
                b"/Contents 5 0 R >>"
            ),
            (
                b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica "
                b"/Encoding /WinAnsiEncoding /ToUnicode 6 0 R >>"
            ),
            _stream(content),
            _unicode_cmap(),
        )
    )


def _adversarial_layout_pdf() -> bytes:
    """Three-page owned fixture whose stream order contradicts visual order."""

    def text(x: int, y: int, value: str, size: int = 11) -> bytes:
        return f"BT /F1 {size} Tf {x} {y} Td ".encode("ascii") + _pdf_string(value) + b" Tj ET"

    page_specs = (
        (
            (72, 28, "KoteKomi Layout Corpus - Page 1", 9),
            (330, 570, "RIGHT THREE follows right two.", 10),
            (54, 735, "Adversarial Two Column Page", 18),
            (54, 650, "LEFT ONE begins the left narrative.", 10),
            (330, 650, "RIGHT ONE begins the right narrative.", 10),
            (54, 570, "LEFT THREE follows left two.", 10),
            (54, 760, "KoteKomi Repeated Layout Header", 9),
            (330, 610, "RIGHT TWO follows right one.", 10),
            (54, 610, "LEFT TWO follows left one.", 10),
            (54, 700, "Two Column Reading Order", 14),
        ),
        (
            (54, 28, "KoteKomi Layout Corpus - Page 2", 9),
            (398, 630, "THREE C2 follows three C1.", 9),
            (54, 735, "Adversarial Three Column Page", 18),
            (226, 670, "TWO C1 begins column two.", 9),
            (54, 670, "ONE C1 begins column one.", 9),
            (398, 670, "THREE C1 begins column three.", 9),
            (54, 760, "KoteKomi Repeated Layout Header", 9),
            (226, 630, "TWO C2 follows two C1.", 9),
            (54, 630, "ONE C2 follows one C1.", 9),
            (54, 700, "Three Column Reading Order", 14),
            (78, 455, "a. Nested item Alpha One", 11),
            (54, 500, "1. Primary item Alpha", 11),
            (102, 420, "i. Deep item Alpha One A", 11),
            (78, 385, "b. Nested item Alpha Two", 11),
            (54, 350, "2. Primary item Beta", 11),
            (54, 540, "Nested List Hierarchy", 14),
        ),
    )
    page_one, page_two = (b"\n".join(text(*spec) for spec in page) + b"\n" for page in page_specs)

    def rotated_text(display_x: int, display_y: int, value: str, size: int) -> bytes:
        return (
            f"BT /F1 {size} Tf 0 1 -1 0 {display_y} {display_x} Tm ".encode("ascii")
            + _pdf_string(value)
            + b" Tj ET"
        )

    page_three = (
        b"\n".join(
            (
                rotated_text(54, 764, "KoteKomi Layout Corpus - Page 3", 9),
                rotated_text(54, 150, "ROTATED BODY remains inside canonical coordinates.", 11),
                rotated_text(54, 72, "Rotated Page Geometry", 18),
                rotated_text(54, 32, "KoteKomi Repeated Layout Header", 9),
            )
        )
        + b"\n"
    )
    return _serialize_pdf(
        (
            b"<< /Type /Catalog /Pages 2 0 R >>",
            b"<< /Type /Pages /Kids [3 0 R 4 0 R 5 0 R] /Count 3 >>",
            (
                b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                b"/CropBox [0 0 612 792] /Resources << /Font << /F1 6 0 R >> >> "
                b"/Contents 7 0 R >>"
            ),
            (
                b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                b"/CropBox [0 0 612 792] /Resources << /Font << /F1 6 0 R >> >> "
                b"/Contents 8 0 R >>"
            ),
            (
                b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 792 612] "
                b"/CropBox [0 0 792 612] /Rotate 90 "
                b"/Resources << /Font << /F1 6 0 R >> >> /Contents 9 0 R >>"
            ),
            (
                b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica "
                b"/Encoding /WinAnsiEncoding /ToUnicode 10 0 R >>"
            ),
            _stream(page_one),
            _stream(page_two),
            _stream(page_three),
            _unicode_cmap(),
        )
    )


def _valid_corruption_source_pdf() -> bytes:
    content = b"BT /F1 14 Tf 72 720 Td (KoteKomi controlled corruption source v1) Tj ET\n"
    return _serialize_pdf(
        (
            b"<< /Type /Catalog /Pages 2 0 R >>",
            b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            (
                b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>"
            ),
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
            _stream(content),
        )
    )


def _openssl_cipher(
    cipher: str,
    *,
    key: bytes,
    contents: bytes,
    initialization_vector: bytes | None = None,
) -> bytes:
    command = ["openssl", "enc", f"-{cipher}", "-K", key.hex(), "-nopad"]
    if initialization_vector is not None:
        command.extend(("-iv", initialization_vector.hex()))
    return subprocess.run(command, input=contents, check=True, capture_output=True).stdout


def _pkcs7(contents: bytes) -> bytes:
    padding_length = 16 - len(contents) % 16
    return contents + bytes((padding_length,)) * padding_length


def _deterministic_aes256_pdf() -> bytes:
    """Create a deterministic AES-256 revision-5 fixture with fixed test entropy."""

    user_password = b"test"
    owner_password = b"kotekomi-fixture-owner-v1"
    file_key = hashlib.sha256(b"kotekomi-pdf-fixture-file-key-v1").digest()
    user_validation_salt = hashlib.sha256(b"user-validation-salt-v1").digest()[:8]
    user_key_salt = hashlib.sha256(b"user-key-salt-v1").digest()[:8]
    owner_validation_salt = hashlib.sha256(b"owner-validation-salt-v1").digest()[:8]
    owner_key_salt = hashlib.sha256(b"owner-key-salt-v1").digest()[:8]
    zero_iv = bytes(16)

    user_hash = hashlib.sha256(user_password + user_validation_salt).digest()
    user_entry = user_hash + user_validation_salt + user_key_salt
    user_encryption_key = hashlib.sha256(user_password + user_key_salt).digest()
    user_encrypted_key = _openssl_cipher(
        "aes-256-cbc", key=user_encryption_key, contents=file_key, initialization_vector=zero_iv
    )

    owner_hash = hashlib.sha256(owner_password + owner_validation_salt + user_entry).digest()
    owner_entry = owner_hash + owner_validation_salt + owner_key_salt
    owner_encryption_key = hashlib.sha256(owner_password + owner_key_salt + user_entry).digest()
    owner_encrypted_key = _openssl_cipher(
        "aes-256-cbc", key=owner_encryption_key, contents=file_key, initialization_vector=zero_iv
    )

    permissions_plaintext = (
        (-4).to_bytes(4, "little", signed=True)
        + b"\xff\xff\xff\xff"
        + b"Tadb"
        + hashlib.sha256(b"permissions-random-v1").digest()[:4]
    )
    encrypted_permissions = _openssl_cipher(
        "aes-256-ecb", key=file_key, contents=permissions_plaintext
    )

    content = b"BT /F1 14 Tf 72 720 Td (KoteKomi AES-256 fixture v1) Tj ET\n"
    content_iv = hashlib.sha256(b"content-stream-iv-v1").digest()[:16]
    encrypted_content = content_iv + _openssl_cipher(
        "aes-256-cbc",
        key=file_key,
        contents=_pkcs7(content),
        initialization_vector=content_iv,
    )
    encryption_dictionary = (
        b"<< /Filter /Standard /V 5 /Length 256 /R 5 /P -4 "
        b"/EncryptMetadata true /O <"
        + owner_entry.hex().encode("ascii")
        + b"> /U <"
        + user_entry.hex().encode("ascii")
        + b"> /OE <"
        + owner_encrypted_key.hex().encode("ascii")
        + b"> /UE <"
        + user_encrypted_key.hex().encode("ascii")
        + b"> /Perms <"
        + encrypted_permissions.hex().encode("ascii")
        + b"> /CF << /StdCF << /AuthEvent /DocOpen /CFM /AESV3 /Length 32 >> >> "
        b"/StmF /StdCF /StrF /StdCF >>"
    )
    file_id = hashlib.sha256(b"kotekomi-encrypted-aes256-v1").digest()[:16].hex().encode("ascii")
    return _serialize_pdf(
        (
            b"<< /Type /Catalog /Pages 2 0 R >>",
            b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            (
                b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>"
            ),
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
            _stream(encrypted_content),
            encryption_dictionary,
        ),
        trailer_entries=b"/Encrypt 6 0 R /ID [<" + file_id + b"><" + file_id + b">] ",
    )


def _controlled_corruptions(valid_pdf: bytes) -> dict[str, bytes]:
    xref_offset = valid_pdf.index(b"xref\n")
    truncated = valid_pdf[:xref_offset]

    free_entry = b"0000000000 65535 f \n"
    first_entry = valid_pdf.index(free_entry, xref_offset) + len(free_entry)
    bad_xref = valid_pdf[:first_entry] + b"0000000001" + valid_pdf[first_entry + 10 :]

    length_match = re.search(rb"/Length (\d+)", valid_pdf)
    if length_match is None:
        raise RuntimeError("valid corruption source has no stream length")
    old_length = length_match.group(1)
    new_length = str(int(old_length) + 7).encode("ascii")
    if len(new_length) != len(old_length):
        raise RuntimeError("stream-length mutation changed token width")
    bad_stream_length = (
        valid_pdf[: length_match.start(1)] + new_length + valid_pdf[length_match.end(1) :]
    )

    missing_page_tree = valid_pdf.replace(b"/Pages 2 0 R", b"/Pages 9 0 R", 1)
    if missing_page_tree == valid_pdf:
        raise RuntimeError("page-tree mutation did not apply")
    return {
        "corrupt_truncated_v1.pdf": truncated,
        "corrupt_bad_xref_v1.pdf": bad_xref,
        "corrupt_bad_stream_length_v1.pdf": bad_stream_length,
        "corrupt_missing_page_tree_v1.pdf": missing_page_tree,
    }


def _run_qpdf(*arguments: str) -> None:
    subprocess.run(("qpdf", *arguments), check=True)


def _require_qpdf() -> None:
    qpdf = shutil.which("qpdf")
    if qpdf is None:
        raise RuntimeError("qpdf is required to generate project PDF fixtures")
    version_output = subprocess.run(
        (qpdf, "--version"), check=True, capture_output=True, text=True
    ).stdout.strip()
    version = version_output.splitlines()[0]
    if version != QPDF_VERSION:
        raise RuntimeError(f"expected {QPDF_VERSION!r}, found {version!r}")
    if shutil.which("openssl") is None:
        raise RuntimeError("OpenSSL is required to generate the AES-256 fixture")


def generate(output_root: Path) -> None:
    _require_qpdf()
    linn_pdf = FIXTURE_ROOT / "ocr" / "ocrmypdf-linn.pdf"
    if not linn_pdf.is_file():
        raise RuntimeError(f"missing pinned source fixture: {linn_pdf}")

    mixed_directory = output_root / "mixed"
    layout_directory = output_root / "layout"
    table_directory = output_root / "tables"
    encrypted_directory = output_root / "encrypted"
    corruption_directory = output_root / "corrupt" / "generated"
    for directory in (
        mixed_directory,
        layout_directory,
        table_directory,
        encrypted_directory,
        corruption_directory,
    ):
        directory.mkdir(parents=True, exist_ok=True)

    authored_pages = _authored_mixed_pages_pdf()
    complex_table = _complex_table_pdf()
    adversarial_layout = _adversarial_layout_pdf()
    encrypted_pdf = _deterministic_aes256_pdf()
    valid_corruption_source = _valid_corruption_source_pdf()

    with tempfile.TemporaryDirectory(prefix="kotekomi-pdf-fixtures-") as temporary:
        temporary_directory = Path(temporary)
        authored_path = temporary_directory / "authored-pages.pdf"
        authored_path.write_bytes(authored_pages)
        mixed_output = temporary_directory / "mixed_born_digital_scan_v1.pdf"

        _run_qpdf(
            "--empty",
            "--deterministic-id",
            "--pages",
            str(authored_path),
            "1",
            str(linn_pdf),
            "1",
            str(authored_path),
            "2",
            "--",
            str(mixed_output),
        )
        (mixed_directory / mixed_output.name).write_bytes(mixed_output.read_bytes())

    (table_directory / "complex_table_v1.pdf").write_bytes(complex_table)
    (layout_directory / "adversarial_columns_hierarchy_v1.pdf").write_bytes(adversarial_layout)
    (encrypted_directory / "encrypted_aes256_v1.pdf").write_bytes(encrypted_pdf)
    for filename, contents in _controlled_corruptions(valid_corruption_source).items():
        (corruption_directory / filename).write_bytes(contents)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=FIXTURE_ROOT)
    arguments = parser.parse_args()
    generate(arguments.output_root)


if __name__ == "__main__":
    main()
