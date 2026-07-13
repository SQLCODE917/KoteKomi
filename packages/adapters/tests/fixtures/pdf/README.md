# PDF adapter fixture corpus

This directory contains byte-pinned inputs for the PDF ingestion requirements in
`docs/2026-07-11-pdf-document-ingestion.md`. Fixtures are grouped by the parser
capability they exercise. `manifest.json` is the authoritative inventory of
source URLs, SHA-256 digests, sizes, requirement coverage, passwords, and safety
classification.

Do not casually open files under `corrupt/`. They are intentionally invalid or
fuzzed parser inputs. Tests should copy their bytes into an isolated temporary
directory and assert a typed failure. Hash and magic-byte checks are safe.

The canonical mixed fixture has exact page-level ground truth:

- `mixed/kotekomi-born-digital-plus-linn.pdf`, page 1: project-authored embedded
  text; OCR must not run.
- `mixed/kotekomi-born-digital-plus-linn.pdf`, page 2: the image-only
  `ocr/ocrmypdf-linn.pdf`; OCR must run and can be compared with
  `ocr/ocrmypdf-linn.txt`.

The canonical encryption fixture is
`encrypted/kotekomi-encrypted-password-test.pdf`, password `test`. The PDF.js
case is retained as an independent damaged-file conformance input because the
upstream manifest declares a password but qpdf 11.9.0 reconstructs its damaged
cross-reference table and reports it as unencrypted.

Regenerate only the project-owned mixed and encrypted fixtures with:

```sh
python3 packages/adapters/tests/fixtures/pdf/generate_project_fixtures.py
```

The generator is pinned to qpdf 11.9.0 and uses deterministic test-only
encryption options. Never copy those encryption settings into production code.

Invalid or conflicting coordinates are not represented by another PDF. That
test must mutate a known-good parser result and verify that representation
validation fails closed.
