# PDF Authoritative Backend Selection Successor

- Status: Accepted
- Supersedes: `docs/2026-08-20-pdf-authoritative-backend-selection.md`
- Depends on: `docs/2026-08-13-live-source-walking-skeleton.md`
- Enables: canonical DR-1 deposited-PDF validation

## Context & Problem

KoteKomi stores one Docling-produced `DocumentRepresentationBundle` as authoritative PDF text and structure.

The current default Docling backend converts the locked canonical title en dash to an ASCII hyphen.

The supported `PyPdfiumDocumentBackend` preserves that en dash on the same locked PDF.

KoteKomi must select one supported backend for every embedded-text PDF representation.

KoteKomi must not combine backend output or rewrite characters after parsing.

Terms used by this TDD:

- **authoritative backend**: the one Docling backend that supplies text and structure for an accepted PDF representation.
- **backend policy**: the pinned backend selection in `DoclingPdfParserConfig` and the parser configuration digest.

### Primary end-to-end flow

1. A user adds a deposited PDF through the public `source add-file` command.
2. `DoclingPdfParser` selects `PyPdfiumDocumentBackend` through its backend policy.
3. Docling creates text and layout from that one backend output.
4. KoteKomi validates and stores one immutable `DocumentRepresentationBundle`.
5. The public Pipeline reloads the stored representation with the backend policy in its provenance.

## Goals

- Preserve Unicode source characters that the selected backend exposes.
- Keep one authoritative PDF text and structure producer.
- Make backend selection visible in representation identity and provenance.
- Preserve existing PDF parsing, page-accounting, and restart guarantees.
- Unblock the locked canonical deposited-PDF scenario without text patching.

## Requirements

### Adapter backend policy

- AB-01: `DoclingPdfParser` uses `PyPdfiumDocumentBackend` for every embedded-text Docling conversion.
- AB-02: `DoclingPdfParserConfig` declares the backend policy with a fixed canonical value.
- AB-03: The parser configuration digest includes the backend policy.
- AB-04: The large-stack worker serializes and validates the backend policy.
- AB-05: The Adapter reports a typed parser failure when the selected backend cannot create a valid representation.

### Authority and persistence

- AP-01: The selected backend provides both authoritative text and authoritative layout items for one representation.
- AP-02: KoteKomi does not read Poppler, qpdf, or another backend text to modify that representation.
- AP-03: A changed backend policy creates a new representation identity.
- AP-04: Existing accepted representations remain immutable.

### Validation

- AV-01: The locked `anthropic-dod-dispute-v1` fixture persists the exact title `Anthropic–United States Department of Defense dispute`.
- AV-02: The canonical public ingestion path produces an acceptable representation and reuses it for identical bytes under the same backend policy.
- AV-03: Existing born-digital, layout, table, OCR, page-accounting, and failure-matrix tests pass with the selected backend.

## Proposed Architecture

```text
deposited PDF bytes
    -> Poppler and qpdf preflight
    -> DoclingPdfParser backend policy
    -> PyPdfiumDocumentBackend
    -> DocumentRepresentationBundle
    -> Ledger and Archive
```

The PDF preflight tools retain their source-inventory role.

`PyPdfiumDocumentBackend` becomes the only source of Docling text and layout for the representation.

`DoclingPdfParser` owns backend construction and backend-policy provenance.

The Application Layer continues to own representation acceptance and immutable commit intent.

## Key Interactions

```text
public source add-file
    -> DoclingPdfParser
    -> PyPdfiumDocumentBackend
    -> validated DocumentRepresentationBundle
    -> atomic representation commit
```

The Adapter uses the configured backend for every run.

The Adapter does not retry the same source through a second backend.

## Data Model

`DocumentRepresentation.parser_config_digest` already records the parser configuration.

This TDD adds the backend policy to that existing configuration input.

This TDD adds no new Ledger table, Archive object, or dual-backend record.

## APIs and Interfaces

`DoclingPdfParserConfig` exposes one backend policy value.

The policy value is fixed to the PyPdfium backend for this slice.

The worker request carries the same policy value.

## Behavior & Domain Rules

KoteKomi uses the selected backend for all new PDF representations after this change.

KoteKomi retains previous representations without replacement.

KoteKomi rejects a parser result that fails existing structural validation.

KoteKomi does not fall back to the former default backend.

KoteKomi does not select a backend by source name, source digest, or source content.

## Acceptance Criteria

- AC-AB-01: Adapter tests prove converter construction selects `PyPdfiumDocumentBackend`.
- AC-AB-02: Adapter tests prove the worker preserves the backend policy.
- AC-AB-03: Adapter tests prove backend-policy changes alter the processing identity.
- AC-AP-01: Adapter tests prove accepted representation text comes only from the selected backend result.
- AC-AP-02: Restart tests prove previous accepted representations remain unchanged.
- AC-AV-01: The locked canonical fixture retains the exact en-dash title in its persisted logical TextView.
- AC-AV-02: Public `source add-file` creates an acceptable canonical representation and reuses it on identical re-ingest.
- AC-AV-03: Existing PDF adapter and Pipeline verification suites pass.

## Reference Implementations

- Backend construction: `packages/adapters/src/kotekomi_adapters/docling_pdf_parser.py`.
- Parser identity: `packages/adapters/src/kotekomi_adapters/docling_pdf_parser.py`.
- Immutable representation identity: `docs/2026-07-11-R0-C-deterministic-representation-identity-and-atomic-bundle-commit.md`.
- Public deposited-source path: `packages/pipelines/src/kotekomi_pipelines/cli.py`.

## Constraints and Halt Conditions

Stop if `PyPdfiumDocumentBackend` fails the existing PDF structure or page-accounting contracts.

Stop if implementation requires per-source backend selection or cross-backend text merging.

Stop if the selected backend cannot run inside the existing deterministic worker boundary.
