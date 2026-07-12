# R1-A — First analyzable PDF representation

Implement it in two vertical slices.

Use `packages/adapters/tests/fixtures/pdf/2025-community-health-improvement-plan-press-release.pdf` for R1-A.

The fixture SHA-256 is `510e8700c0afde7206599f9d0ebd8374b1034204f02e36066aec57d8054b43b7`.

Use one clean, born-digital press-release PDF and make the real Docling path produce:

```text
archived PDF bytes
→ preflight
→ page geometry
→ logical text view
→ document/heading/paragraph nodes
→ source regions
→ deterministic reading order
→ complete quality report
→ ACCEPTABLE representation
```

The exit gate should require exact text-to-node ranges, valid page regions, no missing pages, deterministic rerun digest, and reviewer navigation from a selected paragraph to its page coordinates.

Do not start OCR, tables, or multi-column fallback until this clean born-digital path is authoritative and replayable.

## R1-B — First accepted PDF-backed claim

Extend the same fixture through:

```text
accepted PDF representation
→ deterministic ContextManifest
→ one bounded fixture extraction task
→ task-local candidate references
→ exact quote + text offsets + node + PDF region
→ immutable EvidenceTarget
→ successful validation attempt
→ ProposedChange
→ reviewed Assertion + direct_support link
→ restart
→ replay to the original PDF page region
```

That will prove the first complete vertical path from real PDF bytes to an accepted, reviewable intelligence claim without weakening the architecture established by R0.1.

After that proof, expand PDF support in this order:

```text
multi-column reading order
selective OCR
mixed born-digital/scanned pages
tables with merged headers
footnotes and cross-references
rotated pages
encrypted and malformed PDFs
```
