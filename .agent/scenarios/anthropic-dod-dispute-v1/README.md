# Canonical retrieval scenario: `anthropic-dod-dispute-v1`

This directory contains the committed validation contract for the untracked local PDF:

```text
raw/Anthropic–United_States_Department_of_Defense_dispute.pdf
```

Source identity and attribution use:

```text
https://en.wikipedia.org/wiki/Anthropic%E2%80%93United_States_Department_of_Defense_dispute
```

## Rules

1. Keep the PDF ignored and untracked.
2. Do not download or regenerate the page during validation.
3. Lock the exact existing local bytes once with an explicit operator action.
4. Refuse a different digest after the scenario is locked.
5. Create a new scenario version for intentionally different bytes.
6. Execute the public deposited-source Pipeline command for ingestion.
7. Execute public retrieval build and query commands for retrieval validation.
8. Treat query records and ContextManifests as the mandatory oracle. LLM prose is optional.
9. Add future immutable query packs and cumulative suites without rewriting closed packs.
10. Run the DR-5 Ledger plane with its public commands and canonical verifier; it does not use Harness state.

## First local run

```bash
uv run kotekomi-agent test-ingest anthropic-dod-dispute-v1 --lock-fixture
uv run kotekomi-agent test-query anthropic-dod-dispute-v1 --suite dr-1-v1
```

`--lock-fixture` computes the SHA-256 and page count from the local file, updates `scenario.json` deterministically, and then performs normal ingest validation. It must refuse to replace an existing lock.

## Later runs

```bash
uv run kotekomi-agent test-ingest anthropic-dod-dispute-v1
uv run kotekomi-agent test-query anthropic-dod-dispute-v1 --suite dr-1-v1
```

## Committed inputs

- `scenario.json`: local path, source URL, lock state, and contract paths.
- `ingest-expectations.json`: authoritative-ingest acceptance anchors.
- `queries/base-v1.jsonl`: shared smoke query pack.
- `queries/dr-1-document-exact-lexical-v1.jsonl`: DR-1 cases.
- `suites/dr-1-v1.json`: cumulative DR-1 execution contract.

Harness receipts are generated evidence. They are not edited into these scenario inputs by hand.

## DR-5 local run

```bash
uv run python scripts/verify_dr5_canonical.py
```

`ledger-seed-v1.json` declares accepted Ledger records tied to an authoritative text anchor.
`queries/dr-5-ledger-v1.jsonl` and `suites/dr-5-v1.json` are the immutable Ledger retrieval oracle.

## DR-6 local run

```bash
uv run python scripts/verify_dr6_canonical.py
```

`queries/dr-6-knowledge-graph-v1.jsonl` and `suites/dr-6-v1.json` define exact and lexical Graph seed cases.

## DR-6.1A local run

```bash
uv run python scripts/verify_dr6_1_canonical.py
```

`queries/dr-6-1-evidence-graph-v1.jsonl` defines Relationship explanations that trace to validated EvidenceTargets.

## DR-6.1B local run

```bash
uv run python scripts/verify_dr6_1b_canonical.py
```

The verifier deposits the same locked local bytes under the primary source URL and the
declared test reprint URL. It then proposes and reviews an exact-byte republication
relation, and verifies that the evidence graph shows one reviewed lineage cluster while
keeping original source context for both Documents.

## DR-6.1C local run

```bash
uv run python scripts/verify_dr6_1c_canonical.py
```

The verifier deposits the locked local PDF through the public source Pipeline.
It then creates two reviewed PDF-backed Assertions at fixed UTC review times.
The as-of explanation returns the earlier accepted Assertion.
The current explanation returns the reviewed successor.
Both ContextManifests retain original PDF text and authoritative DocumentNode IDs.
