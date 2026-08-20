# PDF Authoritative Backend Policy Withdrawal

- Status: Accepted
- Supersedes: `docs/2026-08-20-pdf-authoritative-backend-selection-successor.md`
- Depends on: `docs/2026-08-13-live-source-walking-skeleton.md`
- Enables: stable deposited-PDF ingestion without cross-parser text authority

## Context & Problem

KoteKomi stores a Docling-produced `DocumentRepresentationBundle` as authoritative PDF text and structure.

The prior backend-selection TDD selected `PyPdfiumDocumentBackend` because it preserved one en dash.

The supported PyPdfium backend changed heading classification and reading order for existing PDF fixtures.

The current Docling Parse backend retains the existing structure contract but normalizes some Unicode characters.

No installed supported Docling backend or configuration preserves the tested Unicode and retains the existing structure contract.

Poppler and qpdf inspect source bytes before Docling creates the authoritative representation.

They do not provide authoritative representation text.

Terms used by this TDD:

- **authoritative representation**: the accepted `DocumentRepresentationBundle` produced by Docling.
- **source diagnostics**: page, geometry, image, font, and glyph observations from Poppler and qpdf.
- **cross-parser text gate**: a rule that accepts or rejects a representation by comparing Docling text with text from another PDF parser.

### Primary end-to-end flow

1. A user adds a deposited PDF through `source add-file`.
2. Poppler and qpdf record source diagnostics.
3. `DoclingPdfParser` uses the current Docling Parse backend.
4. Docling creates one authoritative representation.
5. KoteKomi validates and stores that representation.

## Goals

- Keep one authoritative PDF text and structure producer.
- Retain source diagnostics for PDF routing and quality decisions.
- Remove cross-parser text gates from PDF ingestion.
- Preserve existing PDF structure and page-accounting behavior.
- Keep accepted representations immutable.

## Requirements

### DoclingPdfParser

- DP-01: `DoclingPdfParser` uses the current Docling Parse backend for embedded-text conversion.
- DP-02: `DoclingPdfParser` creates text and layout from one Docling backend result.
- DP-03: `DoclingPdfParser` reports existing typed failures when that backend cannot create a valid representation.

### Source diagnostics

- SD-01: PDF preflight retains source diagnostics for page inventory, page geometry, image coverage, font mapping, and suspicious glyphs.
- SD-02: The Application Layer uses existing source diagnostics to select embedded extraction or OCR.
- SD-03: Source diagnostics do not alter authoritative representation text or layout.

### Authority

- AU-01: KoteKomi does not compare text from Poppler, qpdf, or another PDF parser with Docling text to accept or reject a representation.
- AU-02: KoteKomi does not rewrite Docling text from source diagnostics.
- AU-03: Existing accepted representations remain immutable.

## Proposed Architecture

```text
deposited PDF bytes
    -> Poppler and qpdf source diagnostics
    -> Docling Parse backend
    -> DocumentRepresentationBundle
    -> Ledger and Archive
```

`DoclingPdfParser` owns authoritative representation construction.

The Application Layer owns extraction-path selection and accepted-state intent.

Poppler and qpdf provide source diagnostics only.

## Key Interactions

```text
user
    -> source add-file
    -> source diagnostics
    -> DoclingPdfParser
    -> validated DocumentRepresentationBundle
    -> atomic representation commit
```

The Pipeline reloads the stored representation after commit.

## Data Model

`PdfPagePreflight` continues to store source diagnostic values.

`DocumentRepresentationBundle` continues to store the Docling representation.

This TDD adds no record type or field.

## APIs / Interfaces

`source add-file` remains the public deposited-PDF entry point.

`DoclingPdfParser` remains the PDF parser Port implementation.

This TDD changes no public command or record shape.

## Behavior & Domain Rules

KoteKomi accepts a representation through existing structure and analyzability validation.

KoteKomi does not use independent parser text as an acceptance condition.

KoteKomi can report source diagnostic values in page-accounting records.

KoteKomi records the Docling parser version and configuration in representation provenance.

## Acceptance Criteria

- AC-DP-01: Existing born-digital, layout, table, OCR, page-accounting, and failure-matrix tests pass with the current Docling Parse backend.
- AC-SD-01: Adapter tests prove PDF preflight records source diagnostics before Docling conversion.
- AC-SD-02: Application tests prove source diagnostics select the existing embedded or OCR path.
- AC-AU-01: Tests prove no PDF acceptance path compares independent parser text with Docling text.
- AC-AU-02: Tests prove no PDF acceptance path rewrites Docling text from source diagnostics.
- AC-AU-03: Restart tests prove accepted representations remain unchanged.

## Reference Implementations

- PDF preflight and Docling conversion: `packages/adapters/src/kotekomi_adapters/docling_pdf_parser.py`.
- PDF path selection: `packages/application/src/kotekomi_application/pdf_ingest.py`.
- Deposited-source command: `packages/pipelines/src/kotekomi_pipelines/cli.py`.
- PDF page-accounting tests: `packages/adapters/tests/test_docling_pdf_r1a.py`.

## Constraints and Halt Conditions

Stop if implementation needs a second parser to supply authoritative text or layout.

Stop if implementation removes source diagnostics that select embedded extraction or OCR.

Stop if implementation changes accepted representation records.
