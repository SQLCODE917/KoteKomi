# Authoritative Document Hierarchy for DR-1

- Status: Proposed
- Program: `derived-retrieval`
- Deliverable ID: `DR-1H`
- Depends on: `docs/2026-08-20-document-retrieval-mvp.md`
- Program envelope: `docs/2026-07-11-derived-document-retrieval.md`
- Canonical scenario: `anthropic-dod-dispute-v1`

## Context & Problem

KoteKomi stores a `DocumentRepresentationBundle` as the authoritative record of a deposited PDF.
DR-1 turns authoritative `DocumentNode` identifiers into a `ContextManifest` through `ContextPlanner`.
The current PDF parser can lose a heading relationship at a page boundary.
The current PDF parser can also choose visual reading order over a direct Docling heading parent.
`ContextPlanner` cannot include a complete authoritative heading chain when the representation loses that chain.
The locked scenario also contains expectations that do not match the accepted representation of its pinned PDF.

**Glossary**

- An **authoritative parent** is a `DocumentNode.parent_node_id` in an accepted representation.
- A **heading chain** is the ordered outermost-to-innermost set of heading ancestors for one focus node.
- A **source heading parent** is the direct heading parent that Docling exposes while it iterates its document tree.
- A **visual parent** is the heading parent that the parser derives from ordered layout geometry.
- A **scenario assertion** is one committed ingest or query expectation for the locked canonical PDF.

### Primary end-to-end flow

1. The source add-file Pipeline creates an accepted representation from the locked PDF.
2. The parser preserves each source heading parent and page-spanning heading chain in its `DocumentNode` records.
3. Document retrieval returns authoritative focus node identifiers for a locked scenario query.
4. `ContextPlanner` adds the complete heading chain for each focus node as required context.
5. `ContextPlanner` writes a `ContextManifest` or records `required_context_exceeds_budget` with all required exclusions.
6. The scenario runner validates the selected node path and the resulting original-text context.

## Goals

- The accepted representation preserves the heading relationships that Docling supplies for the locked PDF.
- `ContextPlanner` includes every authoritative heading ancestor of a retrieved focus node.
- `ContextPlanner` records every required context exclusion when the token budget cannot fit the heading chain.
- The locked scenario asserts only facts present in the accepted representation.
- The scenario runner proves that a fresh ingest and a rebuilt derived index produce the same DR-1 observations.

## Requirements

### PDF parser requirements

- PD-01: The parser preserves an open heading stack across a page boundary.
- PD-02: The parser uses a source heading parent for a non-heading node when Docling supplies that parent.
- PD-03: The parser uses a visual parent only when Docling supplies no source heading parent.
- PD-04: The parser creates a paragraph for a heading-shaped item whose text has no alphanumeric character.
- PD-05: The parser writes every selected parent as the authoritative `parent_node_id` and derives `section_path` from that relationship.
- PD-06: The parser fails the representation build when it cannot resolve a declared source heading parent.

### ContextPlanner requirements

- CP-01: `ContextPlanner` derives a focus node heading chain only from authoritative parent relationships.
- CP-02: `ContextPlanner` orders each heading chain from the outermost heading to the innermost heading.
- CP-03: `ContextPlanner` marks every heading-chain candidate as required context.
- CP-04: `ContextPlanner` retains every required exclusion in `ContextManifest` diagnostics when the token budget cannot fit all required candidates.
- CP-05: `ContextPlanner` reports `required_context_exceeds_budget` when any required candidate is excluded.
- CP-06: `ContextPlanner` excludes document roots and furniture nodes from definition candidates.

### Scenario runner requirements

- SR-01: `test-ingest` replaces only its deterministic scenario state root before its first ingest.
- SR-02: `test-ingest` performs its second ingest in that same fresh state root.
- SR-03: `test-ingest` records reuse of canonical source and representation records during its second ingest.
- SR-04: `test-query` validates an expected section path against the selected authoritative node.
- SR-05: `test-query` validates each expected heading against the resulting `ContextManifest` text.
- SR-06: `test-query` deletes the derived document index through a public product command before its rebuild check.
- SR-07: `test-query` compares observable hit order, selected authoritative nodes, and rendered context across the original and rebuilt indexes.

### Scenario assertion requirements

- SA-01: The ingest contract does not require the title text with a Unicode en dash.
- SA-02: The directive query expects `Background` and `Artificial intelligence in the U.S. military`.
- SA-03: The district docket query expects `Anthropic PBC v. Department of War`.
- SA-04: The appeal docket query expects `Anthropic PBC v. United States Department of War`.
- SA-05: The preliminary-injunction query expects the selected CourtListener list item under `References`.
- SA-06: The scenario does not infer `Lawsuits` as a parent where the accepted representation has no such relationship.

## Proposed Architecture

The Docling PDF Adapter owns source and visual hierarchy interpretation.
The Application Layer owns context candidate selection and budget results.
The scenario runner owns canonical scenario setup and observation comparison.
The document retrieval Adapter remains a disposable derived index.

```text
Docling PDF Adapter
        |
        v
DocumentRepresentationBundle
        |
        +--> Document Retrieval Adapter --> RetrievalHit
        |                                     |
        v                                     v
ContextPlanner <--------------------- focus_node_ids
        |
        v
ContextManifest
        |
        v
Scenario runner
```

## Key Interactions

```text
test-query -> public retrieval command: build index
test-query -> public retrieval command: run query suite
public retrieval command -> ContextPlanner: selected node identifiers
ContextPlanner -> DocumentRepresentationBundle: authoritative parents and text
ContextPlanner -> test-query: ContextManifest
test-query -> public retrieval command: rebuild index
test-query -> public retrieval command: rerun query suite
test-query -> receipt: equivalent observations
```

## Data Model

`DocumentNode.parent_node_id` remains the only authoritative parent relationship.
`DocumentNode.section_path` remains a derived representation field from that parent relationship.
`ContextManifest` retains required context exclusions and their reason codes.
The successor creates no retrieval record type and no persistent compatibility record.

## APIs / Interfaces

The public Pipeline command for document-index building accepts a `--rebuild` option.
The option deletes only the selected disposable document index before the command rebuilds it.
The command does not delete an Archive blob, Ledger record, accepted representation, or `DocumentNode`.

The scenario runner invokes public product commands through argument arrays.
The scenario runner does not import a product package.

## Behavior & Domain Rules

The parser preserves a source heading parent even when visual layout order differs from the source tree.
The parser uses the visual parent only as a fallback for an item without a source heading parent.
The parser does not invent a section relationship from text, geometry, or retrieval metadata.

`ContextPlanner` loads each focus node and follows `parent_node_id` until it reaches the document root.
`ContextPlanner` includes each heading in that route once.
`ContextPlanner` does not use a nearest-preceding-heading rule for retrieval focus nodes.
`ContextPlanner` blocks the context result when required candidates exceed the budget.
`ContextPlanner` retains the excluded candidates and `required_context_exceeds_budget` in the result.

The scenario runner starts a fresh isolated Archive and Ledger for each ingest invocation.
The scenario runner uses its second ingest only to prove idempotence within that invocation.
The scenario runner does not reuse an earlier representation with the same fixture digest.

The accepted Docling representation is the scenario source of truth.
The scenario does not compare Docling text against Poppler text as an acceptance gate.
Poppler diagnostics remain outside this successor's acceptance path.

## Acceptance Criteria

- AC-PD-01: Adapter tests prove a heading chain crosses a page boundary without losing its parent.
- AC-PD-02: Adapter tests prove a Docling source heading parent wins over reordered visual layout.
- AC-PD-03: Adapter tests prove punctuation-only heading text becomes a paragraph.
- AC-PD-04: Adapter tests prove an unresolved declared source heading parent fails explicitly.
- AC-CP-01: Application tests prove `ContextPlanner` emits the complete outermost-to-innermost heading chain.
- AC-CP-02: Application tests prove a budget failure retains every required exclusion and its reason.
- AC-CP-03: Application tests prove roots and furniture do not become definition candidates.
- AC-SR-01: Scenario-runner tests prove each ingest invocation starts from a fresh deterministic root.
- AC-SR-02: Scenario-runner tests prove the second ingest reuses canonical records.
- AC-SR-03: Scenario-runner tests prove selected-node section paths and manifest headings use authoritative nodes.
- AC-SR-04: Scenario-runner tests prove derived index deletion and rebuild use only the public Pipeline command.
- AC-SR-05: Scenario-runner tests prove rebuild equivalence compares hits, selected nodes, and rendered context.
- AC-SA-01: The locked scenario passes with the corrected ingest and query assertions.
- AC-DR1-01: `test-ingest anthropic-dod-dispute-v1` passes with the locked local PDF.
- AC-DR1-02: `test-query anthropic-dod-dispute-v1 --suite dr-1-v1` passes and reports rebuild equivalence.
- AC-DR1-03: Focused parser, application, retrieval, Pipeline, and scenario tests pass.
- AC-DR1-04: Repository formatting, lint, type, and test checks pass.

## Reference Implementations

- Parser hierarchy: `packages/adapters/src/kotekomi_adapters/docling_pdf_parser.py`.
- Context packing: `packages/application/src/kotekomi_application/context_planning.py`.
- Public retrieval command: `packages/pipelines/src/kotekomi_pipelines/cli.py`.
- Scenario command boundary: `packages/devtools/src/kotekomi_devtools/retrieval_scenarios.py`.
- Derived index rebuild: `packages/adapters/src/kotekomi_adapters/sqlite_document_retrieval.py`.

## Constraints and Halt Conditions

Stop when the implementation must infer a missing source heading relationship.
Stop when the implementation needs to modify the locked PDF.
Stop when a change adds semantic, Ledger-plane, graph-plane, or prompt-construction behavior.
Stop when a change turns Poppler diagnostics into a cross-parser equality gate.
Leave the existing PDF-table fixture failures outside this successor unless they prevent the acceptance criteria above.
