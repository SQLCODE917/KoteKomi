# PDF adapter fixture corpus

This directory contains byte-pinned inputs for the PDF ingestion requirements in
`docs/2026-07-11-pdf-document-ingestion.md`. Fixtures are grouped by the parser
capability they exercise. `manifest.json` is the authoritative inventory of
source URLs, SHA-256 digests, sizes, requirement coverage, passwords, and safety
classification.

Do not casually open files under `corrupt/`. They are intentionally invalid or
fuzzed parser inputs. Tests should copy their bytes into an isolated temporary
directory and assert a typed failure. Hash and magic-byte checks are safe.

The canonical mixed fixture has exact page-level ground truth in
`gold/mixed_born_digital_scan_v1.json`:

- `mixed/mixed_born_digital_scan_v1.pdf`, page 1: project-authored embedded
  text; OCR must not run.
- `mixed/mixed_born_digital_scan_v1.pdf`, page 2: the image-only
  `ocr/ocrmypdf-linn.pdf`; OCR must run and can be compared with
  `ocr/ocrmypdf-linn.txt`.
- `mixed/mixed_born_digital_scan_v1.pdf`, page 3: project-authored embedded
  text and one decorative image; OCR must not run.

The canonical table fixture is `tables/complex_table_v1.pdf`; its exact cell,
span, ancestry, empty-cell, multiline-cell, footnote, and region graph is in
`gold/complex_table_v1.json`.

The canonical layout fixture is
`layout/adversarial_columns_hierarchy_v1.pdf`. Its PDF content streams are
deliberately scrambled relative to visual order. It contains two- and
three-column pages, repeated headers and footers, nested lists, section
hierarchy, and a `/Rotate 90` page. Exact logical/display order and hierarchy
are pinned in `gold/adversarial_columns_hierarchy_v1.json`.

The canonical encryption fixture is `encrypted/encrypted_aes256_v1.pdf`,
password `test`. It is deterministic AES-256 and uses fixed fixture-only entropy;
those settings are forbidden in production. The PDF.js
case is retained as an independent damaged-file conformance input because the
upstream manifest declares a password but qpdf 11.9.0 reconstructs its damaged
cross-reference table and reports it as unencrypted.

The four `corrupt/generated/` files are precise mutations of the same valid,
project-owned source. `gold/controlled_corruptions_v1.json` records the mutation
algorithm and resulting digest for each file.

Regenerate all project-owned mixed, table, encrypted, and corruption fixtures with:

```sh
python3 packages/adapters/tests/fixtures/pdf/generate_project_fixtures.py
```

The generator is pinned to qpdf 11.9.0 for page assembly and uses OpenSSL's
standard AES primitive for deterministic test-only PDF encryption. Never copy
its fixed keys, salts, or initialization vectors into production code.

Invalid or conflicting coordinates are not represented by another PDF.
`manifest.json` enumerates the required parser-result mutations; production-path
tests mutate a known-good bundle and require representation validation to fail
closed before any child is committed.

Entries marked `availability: external_only` pin independent conformance inputs
without redistributing them. Their source URL, source digest, expected size,
license disposition, and expectations remain reviewable in the manifest, but
they are deliberately absent from the committed corpus and are not required by
CI. This currently applies to the AIP double-column sample and the Cumberland
and Texas HHS documents pending redistribution-rights review.
