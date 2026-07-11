# Recommended next implementation

Implement a single recovery milestone named:

> **R0 — Authoritative Commit Boundary**

Do **not** add more Docling layout mapping, OCR, context planning, or news adapters until R0 is complete.

Its purpose is to establish one trustworthy transaction boundary for:

```text
capture
→ immutable document version
→ immutable parser representation
→ replayable evidence
→ evidence-gated assertion acceptance
```

That is the smallest implementation that closes the four release blockers without building additional features on unsafe persistence semantics.

I rechecked the repository: `main` still ends at commit `2e854e0`. One additional issue should be included in R0 immediately: `REQUIRED_LEDGER_TABLES` contains the new ingestion tables, but the sole `001_create_ledger.sql` migration does not create them. Since the initializer verifies the required table set after applying migrations, a fresh ledger will fail initialization by inspection. Add an additive migration; do not edit the already-applied `001` migration. ([GitHub][1])

---

## R0 should be delivered as four small PRs

```text
R0-A  Ledger repair and immutable commit semantics
  ↓
R0-B  Stable source identity and document revisioning
  ↓
R0-C  Deterministic representation identity and atomic bundle commit
  ↓
R0-D  Atomic evidence-gated assertion acceptance
  ↓
Proof  One end-to-end authoritative fixture
```

Each PR should leave `main` working. The recovery milestone itself is complete only when the final proof passes.

---

# Final proof before returning to PDF feature work

R0 should end with one deliberately small authoritative vertical slice. Use the existing text representation first, because this test is proving the trust boundary, not PDF layout quality.

```text
1. Capture a local text source under an explicit stable source key.
2. Commit RawBlob, SourceCapture, Source, and Document.
3. Commit a deterministic representation bundle.
4. Create a pinned evidence target for one exact occurrence.
5. Validate and fully replay the target.
6. Review a source-backed assertion proposal.
7. Atomically accept the assertion and direct-support link.
8. Close the database.
9. Reopen it.
10. Navigate assertion → link → evidence → text view → representation
    → document → capture → raw bytes.
11. Recompute every relevant digest.
12. Confirm every identity and selector still agrees.
```

Then mutate one item at each layer in separate tests:

```text
raw byte
parser configuration
representation node text
text-view digest
evidence offset
evidence prefix
evidence role
idempotency input
```

Every mutation must either produce a new versioned artifact or a typed failure. None may alter accepted history.

That single fixture demonstrates the program’s core invariant:

> An accepted claim can be replayed to one exact source occurrence through immutable, versioned artifacts.

The integration TDD expressly requires validated direct support, unique replay, preserved corrections, deterministic identities, and failure on parser upgrades that would otherwise change historical evidence. ([GitHub][8])

---

# What comes immediately after R0

Once R0 is green, resume PDF ingestion with **one born-digital press-release fixture**, not the entire PDF matrix.

The first PDF success slice should produce:

```text
page dimensions
logical text view
document root
paragraph nodes
source regions for those paragraphs
deterministic reading order
acceptable quality report
one replayable evidence target
one accepted assertion
```

OCR, tables, footnotes, multi-column ambiguity, and malformed PDFs should follow as separate vertical slices.

The current Docling adapter is correctly blocked until canonical layout nodes and regions exist, so preserving that fail-closed behavior while R0 is implemented is the right choice. ([GitHub][6])

# Decision summary

The exact next commit sequence should therefore be:

```text
1. Add migration 002 and make ingestion artifacts insert-or-identical.
2. Implement capture_source with stable Source identity and revision conflicts.
3. Introduce deterministic representation fingerprints and atomic bundle commit.
4. Make assertion acceptance atomically create and require validated direct-support links.
5. Prove the complete chain with one restart-safe text fixture.
6. Resume the first real PDF success slice.
```

The first PR—**migration repair plus immutable commit semantics**—is the correct immediate implementation. Everything else depends on being able to trust that an already-persisted source or representation cannot be silently replaced.

[1]: https://github.com/SQLCODE917/KoteKomi/commits/main "Commits · SQLCODE917/KoteKomi · GitHub"
[2]: https://raw.githubusercontent.com/SQLCODE917/KoteKomi/main/packages/adapters/src/kotekomi_adapters/sqlite_ledger.py "raw.githubusercontent.com"
[3]: https://raw.githubusercontent.com/SQLCODE917/KoteKomi/main/packages/application/src/kotekomi_application/evidence_targets.py "raw.githubusercontent.com"
[4]: https://raw.githubusercontent.com/SQLCODE917/KoteKomi/main/packages/application/src/kotekomi_application/source_file_ingest.py "raw.githubusercontent.com"
[5]: https://raw.githubusercontent.com/SQLCODE917/KoteKomi/main/docs/2026-07-11-source-capture-and-document-versioning.md "raw.githubusercontent.com"
[6]: https://raw.githubusercontent.com/SQLCODE917/KoteKomi/main/packages/adapters/src/kotekomi_adapters/docling_pdf_parser.py "raw.githubusercontent.com"
[7]: https://raw.githubusercontent.com/SQLCODE917/KoteKomi/main/packages/domain/src/kotekomi_domain/models.py "raw.githubusercontent.com"
[8]: https://raw.githubusercontent.com/SQLCODE917/KoteKomi/main/docs/2026-07-11-authoritative-document-ingestion-program.md "raw.githubusercontent.com"

