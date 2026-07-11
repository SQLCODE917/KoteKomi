# TDD: Versioned Document Representations

- **Status:** Accepted
- **Parent:** [Authoritative Document Ingestion Program](2026-07-11-authoritative-document-ingestion-program.md)
- **Depends on:** [Source Capture and Document Versioning](2026-07-11-source-capture-and-document-versioning.md)

## 1. Context and problem

A `Document` preserves one immutable source revision, but parsers can produce different reading orders, text normalization, layout interpretation, tables, and coordinates. Evidence and model context must be pinned to a specific parser output rather than to mutable “extracted text.”

## 2. Goals

- Store every parser run as an immutable, versioned representation.
- Preserve logical text, display/verbatim text, structure, page regions, tables, and deterministic links.
- Allow multiple representations of the same `Document` without conflating node IDs or offsets.
- Measure representation quality and make analysis selection explicit.
- Provide a common intermediate representation for PDFs, structured news, HTML, and text fixtures.

## 3. Non-goals and forbidden approaches

This TDD does not choose claims or perform semantic entity resolution.

Forbidden:

- mutating a representation after parser output is committed;
- treating parser output as the original source bytes;
- assuming offsets are stable across parser versions or text views;
- flattening tables while discarding row/column header relationships;
- silently removing headers, footers, captions, or footnotes;
- letting parser-native object IDs escape as cross-representation canonical IDs.

## 4. Requirements

1. Each parser execution records input document, parser/version, configuration digest, code revision, and output digest.
2. A representation contains one or more named `TextView` records.
3. Structured nodes reference exact ranges in a text view and optional source regions.
4. Node parentage, sibling order, section path, and node type are explicit.
5. Deterministic structural/cross-reference edges are distinguishable from model-proposed edges.
6. Tables retain cells, spans, row/column headers, captions, and footnotes.
7. Parser quality metrics and issues are first-class records.
8. Representation selection for analysis is an explicit, versioned decision or policy result.
9. Every node and edge ID is scoped to one representation.
10. A representation can be serialized, hashed, loaded, and validated without the parser runtime.

## 5. Invariants

- A representation references exactly one immutable `Document`.
- A committed representation's canonical serialization matches its stored digest.
- Each text range is within one referenced `TextView` and resolves to the stored node text.
- The structural node graph has one document root, no parent cycle, and total deterministic sibling order.
- Source regions use a declared coordinate system and lie within their page or media bounds.
- Deterministic and proposed edges have distinct provenance.
- No node ID is interpreted without its `representation_id`.
- A parser rerun with changed version/config creates a new representation even when text looks identical.

## 6. Proposed architecture

```text
Document
  └── DocumentRepresentation
        ├── TextView[]
        ├── DocumentNode[]
        ├── DocumentEdge[]
        ├── SourceRegion[]
        └── ParseQualityReport
```

A representation adapter converts parser-native output into the canonical model. A domain validator verifies structure independently of the parser.

## 7. Data model and interfaces

```yaml
DocumentRepresentation:
  representation_id:
  document_id:
  parser_name:
  parser_version:
  parser_config_digest:
  code_revision:
  input_blob_digest:
  canonical_output_digest:
  created_at:

TextView:
  text_view_id:
  representation_id:
  kind: logical | display | verbatim | provider_body
  content_digest:
  text:
  normalization_policy:

DocumentNode:
  node_id:
  representation_id:
  parent_node_id:
  node_type:
  order_index:
  structural_path:
  section_path:
  text_view_id:
  start_char:
  end_char:
  source_region_ids:
  parser_confidence:

DocumentEdge:
  edge_id:
  representation_id:
  from_node_id:
  to_node_id:
  edge_type:
  provenance_kind: deterministic | parser | proposed | reviewed
  provenance_id:

ParseQualityReport:
  report_id:
  representation_id:
  metric_values:
  issues:
  analyzability: acceptable | degraded | blocked
```

Minimum node types: document, title, subtitle, byline, dateline, heading, paragraph, sentence, list, list_item, table, table_row, table_cell, caption, footnote, footnote_marker, figure, quote, header, footer, and page_number.

## 8. Key interactions and domain rules

### Parser upgrade

The upgrade creates a new representation. Existing evidence remains pinned to the earlier representation. Reanchoring is a separate, recorded activity and never rewrites the original target.

### Multiple text views

Logical reading-order text supports analysis. Display or verbatim views preserve source appearance. Transformations between views are explicit; offsets are never translated by assumption.

### Deterministic links

The adapter or post-processor may add `parent_of`, `follows`, `footnote_refers_to`, `caption_of`, table-header, explicit-definition, acronym, or explicit-cross-reference edges when mechanically supported. Ambiguous coreference is not mislabeled deterministic.

### Quality selection

A policy may select one acceptable representation or block analysis. The selection records candidate reports, policy version, chosen representation, and reason.

## 9. Compatibility and delivery

- Existing extracted fixture text becomes one logical `TextView` under a trivial text representation.
- Existing `Document.extracted_text_path` may remain a compatibility view until callers migrate.
- New code uses `representation_id` plus `text_view_id`, never a mutable “latest text” path.
- Storage format is implementation-defined, provided canonical serialization and validation are stable.

## 10. Completion gates

### Correctness criteria

- Every fixture node range reproduces its exact node text and stays within view bounds.
- Invalid ranges, parent cycles, duplicate sibling order, unknown parent IDs, and invalid regions are rejected.
- A parser/config change creates a distinct representation and does not alter prior node IDs or text.
- Table fixtures preserve value cells and all necessary row/column header links.
- Footnote markers resolve to the intended footnotes where the source expresses that relation.
- Canonical serialization produces the same digest across process restarts and supported platforms.
- A corrupted stored representation fails validation before analysis.

### Success criteria

- Plain text, structured-news, born-digital PDF, and OCR-backed PDF can be represented through the same domain interface.
- Review tooling can render a node in logical context and locate its original page/region where available.
- A quality policy can select, degrade, or block a representation with a machine-readable reason.
- Existing fixture proposal tests continue through the compatibility representation.

### Failure criteria

This deliverable is incomplete if:

- evidence or analysis uses unversioned extracted text;
- parser upgrades relocate existing evidence silently;
- a table value loses the headers needed to interpret it;
- malformed structure reaches context planning;
- “removed” furniture or footnotes cannot be recovered for review;
- representation choice is an implicit global latest-version lookup;
- parser confidence is treated as evidence truth.

## 11. References

- Docling document model: https://docling-project.github.io/docling/concepts/docling_document/
- Apache UIMA CAS views: https://uima.apache.org/d/uimaj-current/tug.html

## 12. Halt conditions

Stop and revise if a required source format cannot preserve exact text and source location in this model, or if canonical serialization cannot be made independent of parser object ordering.
