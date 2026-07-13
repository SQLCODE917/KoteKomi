"""Generate the project-owned PDF fixtures from pinned local inputs.

The generated encrypted document deliberately uses qpdf's deterministic test
options. It is a parser fixture, not an example of production encryption.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

FIXTURE_ROOT = Path(__file__).resolve().parent
QPDF_VERSION = "qpdf version 11.9.0"


def _pdf_string(value: str) -> bytes:
    escaped = value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    return f"({escaped})".encode("ascii")


def _born_digital_pdf() -> bytes:
    lines = (
        "KoteKomi Mixed PDF Fixture",
        "This page is born-digital and must use embedded text.",
        "Page 2 is an image-only scan and must use OCR.",
        "Fixture ID: kotekomi-mixed-born-digital-scan-v1",
    )
    text_commands = [b"BT", b"/F1 24 Tf", b"72 720 Td", _pdf_string(lines[0]) + b" Tj"]
    for line in lines[1:]:
        text_commands.extend((b"0 -36 Td", b"/F1 12 Tf", _pdf_string(line) + b" Tj"))
    text_commands.append(b"ET")
    stream = b"\n".join(text_commands) + b"\n"

    objects = (
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>"
        ),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        (
            b"<< /Length "
            + str(len(stream)).encode("ascii")
            + b" >>\nstream\n"
            + stream
            + b"endstream"
        ),
    )

    output = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
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
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF\n"
        ).encode("ascii")
    )
    return bytes(output)


def _run_qpdf(*arguments: str) -> None:
    subprocess.run(("qpdf", *arguments), check=True)


def main() -> None:
    qpdf = shutil.which("qpdf")
    if qpdf is None:
        raise RuntimeError("qpdf is required to generate project PDF fixtures")
    version_output = subprocess.run(
        (qpdf, "--version"), check=True, capture_output=True, text=True
    ).stdout.strip()
    version = version_output.splitlines()[0]
    if version != QPDF_VERSION:
        raise RuntimeError(f"expected {QPDF_VERSION!r}, found {version!r}")

    linn_pdf = FIXTURE_ROOT / "ocr" / "ocrmypdf-linn.pdf"
    if not linn_pdf.is_file():
        raise RuntimeError(f"missing pinned source fixture: {linn_pdf}")

    mixed_directory = FIXTURE_ROOT / "mixed"
    encrypted_directory = FIXTURE_ROOT / "encrypted"
    mixed_directory.mkdir(parents=True, exist_ok=True)
    encrypted_directory.mkdir(parents=True, exist_ok=True)

    born_digital = mixed_directory / "kotekomi-born-digital-page.pdf"
    mixed = mixed_directory / "kotekomi-born-digital-plus-linn.pdf"
    encrypted = encrypted_directory / "kotekomi-encrypted-password-test.pdf"

    born_digital.write_bytes(_born_digital_pdf())
    with tempfile.TemporaryDirectory(prefix="kotekomi-pdf-fixtures-") as temporary:
        temporary_directory = Path(temporary)
        mixed_output = temporary_directory / mixed.name
        encrypted_output = temporary_directory / encrypted.name

        _run_qpdf(
            "--empty",
            "--deterministic-id",
            "--pages",
            str(born_digital),
            "1",
            str(linn_pdf),
            "1",
            "--",
            str(mixed_output),
        )
        _run_qpdf(
            "--static-id",
            "--static-aes-iv",
            "--encrypt",
            "test",
            "kotekomi-fixture-owner",
            "128",
            "--use-aes=y",
            "--",
            str(born_digital),
            str(encrypted_output),
        )
        mixed.write_bytes(mixed_output.read_bytes())
        encrypted.write_bytes(encrypted_output.read_bytes())


if __name__ == "__main__":
    main()
