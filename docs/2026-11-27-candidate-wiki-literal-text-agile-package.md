# Candidate Wiki Literal Text

Status: Implementation authorized; UAT pending.

## Operator outcome

The operator reads original Source punctuation and record labels in Candidate Wiki pages.
Generated links remain usable and citation JSON remains unchanged.
The [TDD](2026-11-27-preserve-candidate-wiki-literal-text.md) owns the rendering contract.

## Selection and evidence

The public exporter currently renders `*literal*` as emphasis and backtick-delimited text as code.
The inspected typed fixture establishes a bounded presentation defect after the plan exists.
Correct presentation escaping has a direct observable result and requires no fresh ingestion.
This is a synthetic rendering regression; it does not establish extraction accuracy.
Broader ontology, link-destination, and identifier-format changes are outside this increment.

## Development and completion

1. Retain the failing regression against the specification commit.
2. Implement the bounded correction and run generated checks through the authorized job runner.
3. Review the exact candidate through PR comments and request revisions if needed.
4. Produce the independent Harness receipt and successful exact-head PR CI evidence.
5. Ask the operator to inspect the rendered example and accept UAT before merge.

The package permits two implementation approaches, with ordinary debugging within each approach.
Use existing renderer tests and one rendered example; create no new measurement framework.
The Spymaster experiment separately records delivery counts, job completions, and interventions.
Job notifications and green checks do not constitute human acceptance.
