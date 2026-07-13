# TDD: PDF Document Ingestion

- **Status:** Accepted
- **Implementation status:** GREEN — integrated gold matrix passed 2026-07-13
- **Parent:** [Authoritative Document Ingestion Program](2026-07-11-authoritative-document-ingestion-program.md)
- **Depends on:** [Source Capture](2026-07-11-source-capture-and-document-versioning.md), [Representations](2026-07-11-versioned-document-representations.md), [Evidence Targets](2026-07-11-replayable-evidence-targets.md)

## 1. Context and problem

PDF preserves page appearance, not necessarily logical reading order. Real documents may combine embedded text, scanned pages, multiple columns, repeated furniture, rotations, tables, figures, footnotes, malformed fonts, and security restrictions. A successful file-open operation is not proof that the extracted representation is analyzable or evidence-safe.

## 2. Goals

- Ingest born-digital, scanned, and mixed PDFs without losing the original bytes.
- Produce a canonical structured representation with logical text and source coordinates.
- Use OCR selectively and record it as a separate transformation.
- Preserve tables, captions, footnotes, headings, reading order, and page geometry.
- Detect extraction defects before model analysis.
- Make parser selection, fallback, and quality outcomes reproducible.
- Support reviewer navigation from evidence to rendered page regions.

## 3. Non-goals and forbidden approaches

This TDD does not guarantee perfect visual reconstruction or semantic understanding of every figure.

Forbidden:

- treating `pdftotext`-style flat output as sufficient for all PDFs;
- OCRing every page unconditionally or replacing original bytes with an OCR result;
- silently dropping pages, text blocks, headers, footers, tables, captions, or footnotes;
- accepting invalid or unknown reading order without a degraded/blocked quality result;
- flattening tables without structural cells and header relationships;
- inventing text for unreadable regions;
- accepting encrypted or malformed input as successfully analyzed when content was inaccessible.

## 4. Requirements

1. Preflight records file hash, media validation, page count, encryption state, page sizes, rotations, embedded-text coverage, image coverage, suspicious glyph rate, and parser warnings.
2. The pipeline selects an extraction path by versioned policy rather than filename alone.
3. Born-digital pages prefer embedded text and layout extraction.
4. OCR is invoked only for pages or documents whose policy signals require it.
5. OCR input, output PDF or sidecar, engine/version, language set, settings, and confidence are archived as transformation artifacts.
6. The canonical adapter emits text views, structural nodes, page regions, reading order, table structure, captions, figures, footnotes, and furniture classifications where present.
7. Repeated headers/footers remain represented even when excluded from the analysis view.
8. Every page has a terminal extraction status and quality metrics.
9. Quality policy selects an analyzable representation, marks it degraded, or blocks downstream analysis.
10. Reviewer tooling can render the archived page and overlay an evidence region without rerunning the parser.
11. Parser and OCR failures produce typed errors with no partial representation published as complete.
12. Tool binaries/models/configurations are pinned by version or digest.

## 5. Invariants

- Original PDF bytes are immutable and always retrievable.
- An OCR-derived artifact is never confused with the received source artifact.
- Reported page numbers and coordinates use an explicit, stable coordinate convention.
- Every extracted node with a source region lies within an existing page boundary.
- No page is omitted from the quality report.
- Logical text retains a deterministic mapping to source nodes and regions.
- Table cells maintain row/column-span and header ancestry needed for interpretation.
- A blocked representation cannot enter context planning.
- Rerunning pinned tools and policy over the same artifacts yields the same canonical representation digest or a declared nondeterminism failure.

## 6. Proposed architecture

```text
PdfIngestUseCase
  ├── PdfPreflightAdapter
  ├── PdfExtractionPolicy
  ├── PrimaryPdfParserAdapter
  ├── SelectiveOcrAdapter
  ├── CanonicalRepresentationAdapter
  ├── RepresentationValidator
  ├── PdfQualityPolicy
  └── PageRenderStore
```

A Docling-class parser is the default candidate because it exposes hierarchy, layout, tables, pictures, and provenance. OCRmyPDF-class tooling may supply selective OCR. The domain contract remains tool-neutral.

## 7. Data model and interfaces

```yaml
PdfPreflightReport:
  report_id:
  document_id:
  pdf_standard_or_version:
  page_count:
  encrypted:
  permissions:
  per_page_metrics:
  global_issues:
  preflight_tool:
  tool_version:

PdfPageExtractionStatus:
  page_index:
  path: embedded | ocr | mixed | inaccessible
  extracted_character_count:
  image_coverage:
  glyph_issue_count:
  rotation_applied:
  warnings:
  status: acceptable | degraded | blocked

PdfTransformationArtifact:
  artifact_id:
  input_blob_id:
  output_blob_id:
  activity_type: repair | render | ocr
  tool_identity:
  configuration_digest:
  page_scope:

PdfIngestOutcome:
  document_id:
  preflight_report_id:
  representation_ids:
  selected_representation_id:
  analyzability:
  blocking_reasons:
```

Required operation:

```python
ingest_pdf(document_id, policy_id) -> PdfIngestOutcome
```

## 8. Key interactions and domain rules

### Mixed born-digital and scanned document

Preflight classifies pages independently. Embedded text is retained for usable pages; only deficient pages are OCRed. The final representation records each node's extraction path and confidence.

### Multi-column page

Reading order follows validated layout relationships, not raw PDF object order. A fixture with interleaved object order must produce coherent paragraphs or be marked blocked.

### Repeated furniture

Headers and footers are typed and retained. The analysis text view excludes them by explicit policy, while the display/verbatim view and page render preserve them.

### Table spanning pages

Continuation rows, repeated headers, captions, units, and footnotes remain linked. A value cell is not analysis-ready until its header ancestry can be determined or the table is flagged degraded.

### Unreadable or encrypted PDF

The raw file is captured. The outcome is `blocked` with page-level reasons. No empty “successful” representation and no model task are created.

## 9. Required fixture classes

The repository's redistributable corpus SHALL include at least:

- clean born-digital press release;
- image-only scan;
- mixed text/scan document;
- two- and three-column pages with adversarial object order;
- rotated pages;
- repeated headers, footers, and page numbers;
- nested lists and section hierarchy;
- table with merged and multi-level headers;
- table continued across pages;
- footnote reference crossing a page boundary;
- definition reused several pages later;
- malformed font mapping or replacement glyphs;
- truncated/corrupt PDF;
- encrypted PDF without credentials;
- deliberately invalid parser coordinates for validator tests.

## 10. Compatibility and delivery

- PDF ingestion is additive; existing text ingestion remains operational.
- Tool-specific output stays in the artifact archive and adapter package, not the domain API.
- Page rendering may be eager or lazy, but evidence review tests use archived/pinned rendering inputs.
- Deployment documentation identifies native dependencies and a deterministic container or lockfile strategy.

## 11. Completion gates

The authoritative sign-off artifact is
`packages/adapters/tests/fixtures/pdf/gold/integrated_gold_matrix_v1.json`. Its exact
fixture-class partition is executed by
`packages/adapters/tests/test_pdf_integrated_gold_matrix.py`. Every row crosses public capture
and PDF ingestion, authoritative preflight and page accounting, transformation selection,
canonical representation and quality policy, context planning or an explicit typed block,
evidence replay where applicable, run-scoped coverage, SQLite restart, and a deterministic
rerun. Rows execute in isolated processes so native parser state from one fixture cannot affect
another; each row performs both processing invocations and the restart proof within that one
isolated process.

### Correctness criteria

- All required fixture pages receive accurate terminal statuses and no page disappears.
- Extracted paragraph order matches the gold reading order or the representation is blocked.
- Text-node ranges and page regions pass representation validation.
- Selective OCR runs only on policy-selected pages and preserves non-OCR page provenance.
- Table gold fixtures retain all expected cells, spans, headers, captions, units, and footnotes.
- Evidence overlays identify the intended page regions for every gold evidence target.
- Corrupt, inaccessible, and invalid-coordinate fixtures fail closed with typed reasons.
- A parser/OCR crash cannot publish a complete representation or lose the raw PDF.

### Success criteria

- Every analyzable gold PDF reaches deterministic context planning without manual text repair.
- A reviewer can open any grounded PDF claim at its exact page/region and inspect its structural context.
- Reprocessing with pinned inputs produces the same canonical representation digest in CI.
- Quality reports distinguish acceptable, degraded, and blocked cases and drive downstream behavior.
- Mixed documents avoid full-document OCR while recovering the scanned pages required by the gold corpus.

### Failure criteria

This deliverable is incomplete if:

- successful ingestion can contain missing pages or unreported extraction errors;
- reading order corruption reaches the model as ordinary text;
- OCR output replaces the archived original;
- a table claim can be formed from a value stripped of its headers;
- parser coordinates are trusted without validation;
- reviewers need the live parser to locate accepted evidence;
- only clean, born-digital fixtures are tested.

## 12. References

- Docling document model: https://docling-project.github.io/docling/concepts/docling_document/
- OCRmyPDF advanced usage: https://ocrmypdf.readthedocs.io/en/latest/advanced.html

## 13. Halt conditions

Stop and revise when a mandatory PDF class cannot retain both logical content and reviewable source location, or when a required parser/OCR dependency cannot be pinned and reproduced in the supported deployment environment.
