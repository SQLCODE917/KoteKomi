# Preserve multiline Source quotations

The operator can read Source paragraphs and line breaks in Candidate Wiki quotations.
The current exporter flattens them while citation JSON preserves the original text.
The [TDD](2026-11-27-preserve-multiline-source-quotations.md) defines the presentation change.

Use the ordinary PR workflow: implement, run focused and fast checks, review, pass PR CI, and request UAT.
The operator authorized this feature and retains UAT acceptance and merge.
Update this package and its TDD on the same branch when implementation reveals a correction within this outcome.

Use the existing typed renderer fixture and a before/after rendered page.
This demonstrates presentation behavior, not ingestion or extraction quality.
