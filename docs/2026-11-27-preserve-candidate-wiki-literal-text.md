# Preserve Literal Candidate Wiki Text

Status: Authorized bounded correction for the Spymaster coordination validation.

## Context & Problem

An operator reads a Candidate Wiki page to inspect proposed intelligence and its exact Source text.
The Candidate Wiki is a derived Markdown export with structured citation and audit records.
The exporter currently escapes brackets, HTML controls, bars, and backslashes in text values.
It does not escape every Markdown control character.
The public renderer turns the Source text “The label is *literal* and `raw`.” into emphasis and code.
The rendered page therefore loses punctuation that belongs to the Source.
The observed failure is in Markdown rendering, after the typed Candidate Wiki plan exists.
The correction will preserve literal punctuation in Source text and record labels.
It delivers the fresh product increment of the authorized coordination experiment.

Primary end-to-end flow:

1. The operator exports a Candidate Wiki from an existing typed plan.
2. The exporter places Source text and record labels into Markdown pages as literal text.
3. A Markdown renderer displays their original punctuation.
4. The operator can still follow generated links and inspect unchanged citation records.

The operator authorized implementation and PR validation.
The operator retains UAT acceptance and merge decisions.

## Goals

- The operator sees the Source's punctuation instead of formatting introduced by that punctuation.
- The operator sees record labels faithfully within the page's existing presentation.
- Generated links, citations, and deterministic export behavior remain usable.

## Requirements

### Markdown exporter

- M-01: The exporter preserves literal emphasis, code, strikethrough, link, and HTML controls in text values.
- M-02: M-01 applies to Source quotations, Event labels, relationship labels, and generated link labels.
- M-03: The exporter retains its own headings, emphasis, links, and list structure.
- M-04: The exporter preserves citation JSON values and canonical record IDs exactly.
- M-05: Rendering the same plan twice produces identical files and manifest identity.
- M-06: Existing newline normalization remains unchanged.

### Regression verification

- V-01: Tests exercise `MarkdownCandidateWikiRenderer.render` with valid typed plan fixtures.
- V-02: Tests parse complete emitted pages and assert the visible text, not just an escaping helper.
- V-03: Tests cover `*literal*`, `**literal**`, `_literal_`, backtick-delimited text, and `~~literal~~`.
- V-04: Tests retain bracket, backslash, bar, ampersand, and HTML controls as literal values.
- V-05: Tests prove generated links remain links and input link syntax does not create a new link.
- V-06: The implementing agent retains a failing pre-change regression and a passing candidate result.

## Proposed Architecture

The exporter owns presentation escaping.
The Application Layer continues to provide the existing typed plan and citation registry.
A Markdown parser serves only as a test oracle for the emitted pages.
The correction changes no Ledger state, ontology rules, or public DTOs.

```text
Typed Candidate Wiki plan --> Markdown exporter --> Markdown pages --> reader
                                   |
                                   +--> unchanged citation/audit JSON
```

## Key Interactions

```text
Operator        Exporter           Markdown renderer
   | export plan    |                     |
   |--------------->| emit literal text   |
   |                |-------------------->|
   |<--------- page with original punctuation
```

## Data Model

The correction uses existing Candidate Wiki plan, page, presentation, and citation records.
It introduces no persisted records or schema changes.

## APIs / Interfaces

The public renderer and its inputs retain their current interfaces.
Tests can declare the already installed `markdown-it-py` parser as a direct development dependency.
The exporter adds no runtime dependency for escaping.

## Behavior & Domain Rules

M-01 applies to input text embedded in prose, quotations, emphasis, and link labels.
Generated link destinations retain their existing contract.
Internal code-formatted identifiers retain their existing contract.
The test parser enables strikethrough so V-03 covers the intended Markdown control.
V-02 proves a synthetic rendering regression from valid typed records.
It does not claim fresh ingestion accuracy or independent extraction capability.

## Acceptance Criteria

- AC-M: Full-page tests satisfy M-01 through M-06 for Source text and presentation labels.
- AC-V: The same regression fails before the production change and passes afterward.
- AC-controls: Existing Exporter tests and generated-link controls pass.
- Engineering verification runs the generated Harness plan, formatting, lint, type checks, and PR CI.
- Operational verification uses one implementing conversation, a bounded check job, and its PR completion report.
- Human UAT consists of reading a representative rendered page and confirming the retained punctuation and navigation.

## Reference Implementations

- Exporter: `packages/exporters/src/kotekomi_exporters/markdown_wiki.py`.
- Typed fixture and public renderer tests: `packages/exporters/tests/test_markdown_candidate_wiki.py`.
- Existing escaping requirement: `docs/2026-09-05-ontology-driven-candidate-wiki-projection.md`, OWP-REN-03.
- Deterministic export contract: `docs/2026-09-04-deterministic-candidate-wiki-mvp.md`.

## Constraints and Halt Conditions

Keep this correction within text presentation and its verification.
A change to citation meaning, canonical IDs, link destinations, or the public plan requires a separate decision.
Use at most two implementation approaches; ordinary debugging within the selected correction remains authorized.
Use existing tests and one retained example rather than creating an evaluation framework.
