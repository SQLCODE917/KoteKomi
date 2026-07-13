# Recommended TDD 4 PDF fixture set

Yes. The strongest corpus combines:

1. **Small, controlled PDFs committed to the repository** for exact assertions.
2. **Real-world external PDFs** for parser realism.
3. **Mutated parser outputs** for conditions that no PDF can directly encode, especially invalid coordinates.

Do not make CI depend on live URLs. Download an approved fixture once, record its SHA-256 and license/provenance, and test the pinned bytes.

## Fixture matrix

| Requirement                               | Recommended fixture                                                                                                                                                                                                                                                                                                                                                                    | What it should prove                                                                                                                                                                                                                                                                                                                  |
| ----------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Multi-column reading order                | [NIST-hosted double-column sample PDF](https://www.nist.gov/document/8x11doublesamplepdf)                                                                                                                                                                                                                                                                                              | Full-width title and abstract precede the columns; each column is read top-to-bottom without line interleaving; tables spanning both columns remain coherent. The document visibly contains two-column body content, page furniture, footnotes, references, and a full-width table.                                                   |
| Repeated headers and footers              | [NIST-hosted double-column sample PDF](https://www.nist.gov/document/8x11doublesamplepdf)                                                                                                                                                                                                                                                                                              | Repeated running headers, copyright text, and page numbers remain represented but are typed as page furniture and excluded from body text.                                                                                                                                                                                            |
| Rotated pages                             | [OCRmyPDF `cardinal.pdf`](https://raw.githubusercontent.com/ocrmypdf/OCRmyPDF/main/tests/resources/cardinal.pdf) and [`rotated_skew.pdf`](https://raw.githubusercontent.com/ocrmypdf/OCRmyPDF/main/tests/resources/rotated_skew.pdf)                                                                                                                                                   | `cardinal.pdf` contains copies at the four cardinal orientations; `rotated_skew.pdf` combines page rotation and skew. These are compact tests for orientation decisions and coordinate transformations. ([GitHub][1])                                                                                                                 |
| Scanned PDFs and OCR                      | [OCRmyPDF `linn.pdf`](https://raw.githubusercontent.com/ocrmypdf/OCRmyPDF/main/tests/resources/linn.pdf), with [`linn.txt`](https://raw.githubusercontent.com/ocrmypdf/OCRmyPDF/main/tests/resources/linn.txt) as expected text; harder case: [`c02-22.pdf`](https://raw.githubusercontent.com/ocrmypdf/OCRmyPDF/main/tests/resources/c02-22.pdf)                                      | `linn.pdf` is an image-based two-column OCR fixture with a supplied text reference. `c02-22.pdf` adds obscure typography and illustrations. ([GitHub][1])                                                                                                                                                                             |
| Mixed born-digital/scanned document       | **Generate a KoteKomi fixture** from a project-authored born-digital page plus `linn.pdf`; use [OCRmyPDF `multipage.pdf`](https://raw.githubusercontent.com/ocrmypdf/OCRmyPDF/main/tests/resources/multipage.pdf) as a secondary stress case                                                                                                                                           | Exact page-level ground truth: born-digital pages must not be OCRed, image-only pages must be OCRed, and every page must retain its processing decision and provenance. OCRmyPDF’s heterogeneous six-page fixture exercises different page-processing paths, but a controlled composite gives much stronger assertions. ([GitHub][2]) |
| Merged cells                              | [Cumberland County “PDF Test Document”](https://www.cumberlandcountypa.gov/DocumentCenter/View/30588/PDF-Conversion-Test---Native-ODT)                                                                                                                                                                                                                                                 | Its first table has a left-side “Headers” cell spanning several rows, normal rows, a caption, and surrounding figure/text content. It is a useful compact real-world rowspan fixture.                                                                                                                                                 |
| Multilevel and spanning table headers     | [Texas HHS “Complex Tables with Spanning Headers”](https://accessibility.hhs.texas.gov/docs/processes/EditingTagsToFixComplexTables.pdf)                                                                                                                                                                                                                                               | The example includes multiple column headers and row-header cells spanning several rows. It is an excellent visual stress case for header ancestry and row/column spans.                                                                                                                                                              |
| Cross-page tables                         | [NIST SRM 2259 Certificate of Analysis](https://tsapps.nist.gov/srmext/certificates/2259.pdf)                                                                                                                                                                                                                                                                                          | Table 1 starts on page 2 and continues through pages 3 and 4, repeating its headers and using explicit continuation labels. It is a clean, short, born-digital cross-page-table specimen.                                                                                                                                             |
| Footnotes and cross-references            | [NIST-hosted double-column sample](https://www.nist.gov/document/8x11doublesamplepdf) and [NIST SRM 2259](https://tsapps.nist.gov/srmext/certificates/2259.pdf)                                                                                                                                                                                                                        | The first includes ordinary footnotes, a table footnote, references, figures, and tables; the second has table markers `(a)` and `(b)` connected to explanatory notes and numbered references.                                                                                                                                        |
| Fonts without usable Unicode mappings     | [TrueType no-mapping PDF](https://raw.githubusercontent.com/ocrmypdf/OCRmyPDF/main/tests/resources/truetype_font_nomapping.pdf), [Type 3 no-mapping PDF](https://raw.githubusercontent.com/ocrmypdf/OCRmyPDF/main/tests/resources/type3_font_nomapping.pdf), and [text rendered as vector curves](https://raw.githubusercontent.com/ocrmypdf/OCRmyPDF/main/tests/resources/vector.pdf) | The first two intentionally lack usable character mapping; the third has visible text represented as curves rather than fonts. These test the difference between visual text and trustworthy extractable text. ([GitHub][1])                                                                                                          |
| Encrypted PDF                             | [PDF.js `issue15893_reduced.pdf`](https://raw.githubusercontent.com/mozilla/pdf.js/master/test/pdfs/issue15893_reduced.pdf), password `test`                                                                                                                                                                                                                                           | The PDF.js test manifest explicitly identifies this as a password-protected regression document. Use it as an independent conformance case, but generate a project-owned encrypted fixture as the canonical CI test. ([GitHub][3])                                                                                                    |
| Corrupt PDFs                              | [OCRmyPDF `invalid.pdf`](https://raw.githubusercontent.com/ocrmypdf/OCRmyPDF/main/tests/resources/invalid.pdf), [`kcs.pdf`](https://raw.githubusercontent.com/ocrmypdf/OCRmyPDF/main/tests/resources/kcs.pdf), and [`overlay.pdf`](https://raw.githubusercontent.com/ocrmypdf/OCRmyPDF/main/tests/resources/overlay.pdf)                                                               | These respectively exercise a PDF header followed almost immediately by EOF, an invalid table of contents, and content-stream parsing errors. The OCRmyPDF resource documentation warns that some invalid files can crash viewers, so treat these as byte fixtures rather than documents for casual opening. ([GitHub][1])            |
| Fuzzed corrupt PDFs                       | [PDF.js Ghostscript fuzz case](https://raw.githubusercontent.com/mozilla/pdf.js/master/test/pdfs/GHOSTSCRIPT-698804-1-fuzzed.pdf) and [PDFBox fuzz case](https://raw.githubusercontent.com/mozilla/pdf.js/master/test/pdfs/PDFBOX-3148-2-fuzzed.pdf)                                                                                                                                   | Secondary parser-hardening cases after the controlled corruption fixtures pass. ([GitHub][4])                                                                                                                                                                                                                                         |
| Invalid or conflicting parser coordinates | **No external PDF is appropriate. Use a known-good PDF and mutate the parser result.**                                                                                                                                                                                                                                                                                                 | Coordinate corruption is a property of parser output, not necessarily of source PDF bytes. The authoritative test must inject impossible or contradictory regions and verify fail-closed validation.                                                                                                                                  |

---

# Controlled fixtures that KoteKomi should generate

Several requirements are better served by generated PDFs than by finding accidental examples online.

## 1. `mixed_born_digital_scan_v1.pdf`

Build a three-page document:

```text
Page 1:
    project-authored born-digital text
    embedded Unicode mapping
    no raster body image

Page 2:
    image-only OCR page derived from linn.pdf

Page 3:
    project-authored born-digital text with one small decorative image
```

Required assertions:

```text
Page 1:
    OCR decision = not_required
    embedded text preserved exactly

Page 2:
    OCR decision = required
    OCR representation and confidence recorded
    text compared with linn.txt

Page 3:
    OCR decision = not_required
    decorative image does not trigger whole-page OCR

Entire document:
    exactly three page-processing records
    page 2 alone has OCR provenance
    representation preserves page order
    retry reuses canonical artifacts
```

This is a better selective-OCR test than an uncontrolled real-world document because the expected decision for every page is known beforehand.

## 2. `complex_table_v1.pdf`

Generate one project-owned table with an exact canonical cell graph:

```text
                       Measurements
             2024                        2025
          Q1      Q2                  Q1      Q2

Region A  10      11
Region A  12      13
Region B  20      21                  22      23
```

Include deliberately:

* one top header spanning four columns;
* two second-level headers spanning two columns each;
* leaf headers `Q1` and `Q2`;
* one row header spanning two rows;
* one multiline cell;
* one empty cell;
* one table footnote;
* a caption and nearby body paragraph.

The expected table model should be checked cell-by-cell:

```yaml
cell:
  row:
  column:
  row_span:
  column_span:
  text:
  row_header_ancestry:
  column_header_ancestry:
  source_region:
```

Use the Cumberland and Texas HHS PDFs as independent realism tests, but make this generated PDF the hard correctness gate. The HHS document itself explains why irregular tables need explicit span and header relationships. ([Texas HHS Accessibility Center][5])

For later breadth testing, PubTables-1M is a useful benchmark source because it contains detailed header and location annotations for a very large collection of scientific tables. It is too large and indirect to replace the small canonical unit fixture. ([Microsoft][6])

## 3. `encrypted_aes256_v1.pdf`

Encrypt a small project-owned source fixture deterministically with:

```text
user password: test
owner password: a fixed fixture-only value
encryption: AES-256
```

Test three separate paths:

```text
no password
    → BLOCKED / password_required

wrong password
    → BLOCKED / invalid_password

correct password
    → processing permitted
    → decrypted interpretation tied to the archived encrypted bytes
```

The password must never appear in:

* ledger payloads;
* model context;
* logs;
* provenance error messages;
* coverage reports.

Use the PDF.js password fixture only as an independent compatibility case.

## 4. Controlled corruption variants

Generate mutations from one project-owned valid PDF:

```text
corrupt_truncated_v1.pdf
    final bytes and xref removed

corrupt_bad_xref_v1.pdf
    object offsets changed

corrupt_bad_stream_length_v1.pdf
    content-stream length disagrees with bytes

corrupt_missing_page_tree_v1.pdf
    page-tree reference missing
```

For each one, pin the precise mutation program and resulting SHA-256. Do not manually edit opaque bytes and commit an unexplained artifact.

The required outcome should be one of:

```text
recoverable:
    parser emits an explicit degraded quality report
    repair behavior and repaired interpretation are versioned

unrecoverable:
    typed processing failure
    no acceptable representation
```

It must never be:

```text
uncaught crash
process hang
silent page omission
partial representation reported as complete
```

---

# Invalid and conflicting coordinates need parser-output mutation tests

A PDF cannot guarantee that a parser will return invalid coordinates. Test this at the adapter/Application boundary using a known-good PDF—preferably the R1 press release—and a parser wrapper that mutates one valid bundle at a time.

Required mutations:

```text
negative x0 or y0
x1 < x0
y1 < y0
coordinates beyond MediaBox
coordinates inside MediaBox but outside CropBox
non-finite coordinate
page number outside the page inventory
region assigned to the wrong representation
region assigned to a node from another page
top-left coordinates declared as bottom-left coordinates
rotation applied twice
region/text range disagreement
duplicate contradictory regions for one node
reading-order self-edge
reading-order cycle
parent node from a different representation
```

Every case should prove:

```text
bundle validation fails
failure stage identifies representation validation
no representation children are partially committed
no acceptable quality report is created
ProcessingAttempt receives a failed outcome
raw PDF bytes remain archived
retry with unmodified output succeeds
```

This is more authoritative than hoping to find a malformed PDF that happens to make one parser emit bad geometry.

---

# The fixture set I would commit first

Subject to license review, this is a practical first package:

```text
external/or_pinned:
    nist_double_column_sample.pdf
    nist_srm_2259.pdf
    cumberland_pdf_test_document.pdf
    texas_hhs_complex_spanning_headers.pdf

third_party_regression:
    cardinal.pdf
    rotated_skew.pdf
    linn.pdf
    linn.txt
    c02-22.pdf
    truetype_font_nomapping.pdf
    type3_font_nomapping.pdf
    vector.pdf
    invalid.pdf
    kcs.pdf
    overlay.pdf

generated_by_kotekomi:
    mixed_born_digital_scan_v1.pdf
    complex_table_v1.pdf
    encrypted_aes256_v1.pdf
    corrupt_truncated_v1.pdf
    corrupt_bad_xref_v1.pdf
    corrupt_bad_stream_length_v1.pdf
    corrupt_missing_page_tree_v1.pdf
```

The OCRmyPDF repository publishes per-file licensing metadata. In particular, its resource metadata marks `c02-22.pdf` and `multipage.pdf` as public domain, the `linn`/rotation family under GFDL-or-CC-BY-SA terms, its synthetic invalid/font fixtures under CC BY-SA 4.0, `overlay.pdf` under MIT, and `vector.pdf` under MIT. Preserve the applicable attribution and license alongside every vendored fixture. ([GitHub][7])

The NIST-hosted double-column document visibly carries American Institute of Physics copyright, so keep that as an external conformance fixture unless redistribution rights are established.  Public accessibility of a PDF URL should never be treated as automatic permission to commit it to the repository.

---

# Fixture manifest

Every file should have a machine-readable manifest such as:

```yaml
fixture_id: pdf_cross_page_table_nist_srm2259
source_url: https://tsapps.nist.gov/srmext/certificates/2259.pdf
sha256: <pinned digest>
media_type: application/pdf
license_disposition: external_conformance_only

expected:
  page_count: 4
  encryption: none
  extraction_mode: embedded_text
  table_count: 1
  logical_cross_page_tables: 1
  table_fragments:
    - page: 2
    - page: 3
    - page: 4
  repeated_table_headers: true
  table_footnotes: true

must_not:
  - represent continued fragments as unrelated tables
  - include repeated column headers as data rows
  - lose source page regions
  - omit any page from coverage
```

Also record:

```text
downloaded_at
source SHA-256
local SHA-256
license and attribution
expected parser disposition
expected page inventory
gold text, nodes, cells, and regions
fixture-generator version for generated files
```

That converts the PDFs from an informal folder of interesting documents into an auditable gold corpus for **TDD 4 — `docs/2026-07-11-pdf-document-ingestion.md`**.

[1]: https://github.com/ocrmypdf/OCRmyPDF/tree/main/tests/resources "OCRmyPDF/tests/resources at main · ocrmypdf/OCRmyPDF · GitHub"
[2]: https://github.com/ocrmypdf/OCRmyPDF/issues/1316?utm_source=chatgpt.com "[Bug]: test_semfree fails with ghostscript 10.03.0+ #1316"
[3]: https://github.com/mozilla/pdf.js/blob/master/test/test_manifest.json "pdf.js/test/test_manifest.json at master · mozilla/pdf.js · GitHub"
[4]: https://github.com/mozilla/pdf.js/blob/master/test/pdfs/GHOSTSCRIPT-698804-1-fuzzed.pdf "pdf.js/test/pdfs/GHOSTSCRIPT-698804-1-fuzzed.pdf at master · mozilla/pdf.js · GitHub"
[5]: https://accessibility.hhs.texas.gov/docs/processes/EditingTagsToFixComplexTables.pdf "PDF Remediation: Complex Tables with Spanning Headers"
[6]: https://www.microsoft.com/en-us/research/publication/pubtables-1m/?utm_source=chatgpt.com "PubTables-1M: Towards comprehensive table extraction ..."
[7]: https://github.com/ocrmypdf/OCRmyPDF/blob/main/REUSE.toml?utm_source=chatgpt.com "OCRmyPDF/REUSE.toml at main"

