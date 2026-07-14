Yes. **The row you pasted is now historical rather than the next action.**

**TDD 4 — `docs/2026-07-11-pdf-document-ingestion.md` is complete and should remain a permanent regression gate.** The next primary deliverable in the accepted program sequence is **TDD 5 — `docs/2026-07-11-structured-news-ingestion.md`**. The governing program explicitly places structured-news ingestion immediately after PDF ingestion, with the exit signal that provider version/update semantics and rights survive ingestion. ([GitHub][1])

The corrected plan row is:

| Next order | TDD                                                        | Responsibility                                                                                                                                                                                                                                    |
| ---------: | ---------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
|          1 | **TDD 5 — `docs/2026-07-11-structured-news-ingestion.md`** | Implement the second source family: provider-native news packages, stable item/version identity, immutable updates/corrections/withdrawals, rights and embargo enforcement, structured representations, and a permitted generic-article fallback. |

The former row becomes:

| Status       | TDD                                                     | Result                                                                                                                                                                             |
| ------------ | ------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Complete** | **TDD 4 — `docs/2026-07-11-pdf-document-ingestion.md`** | The PDF source family and its page, OCR, rotation, structure, table, quality, evidence-overlay, failure, coverage, and replay contracts are now permanent regression requirements. |

# Recommended TDD 5 implementation plan

The existing TDD remains suitable. It already defines the intended architecture, precedence rules, provider-neutral adapter boundary, revision handling, rights requirements, and completion gates. It should be implemented rather than replaced. ([GitHub][2])

I would deliver it through seven vertical milestones.

## N1 — Provider-neutral news contract

Establish the common semantic output of every news adapter:

```text
authorized payload + delivery envelope
→ ProviderIdentity
→ ProviderNewsItem
→ NewsRevisionDecision
→ authoritative capture request
→ canonical news representation
```

The provider-neutral item should preserve, when available:

```text
provider namespace
provider item ID
provider version
provider-native status
first-published and updated timestamps
headline and alternate headlines
bylines
dateline
language
subjects and locations
ordered body elements
media references
rights
embargo
distribution scope
raw provider metadata
```

Adapters own wire-format interpretation. Application code must continue to own:

* stable KoteKomi IDs;
* immutable `Source`, `Document`, and capture records;
* revision validation;
* representation fingerprints;
* evidence and acceptance boundaries.

The first milestone is complete only when adapter output has deterministic canonical serialization and can be validated without network access. That is already an explicit TDD correctness criterion. ([GitHub][2])

## N2 — NewsML-G2/NITF authoritative vertical slice

Start with a rights-safe, synthetic NewsML-G2 fixture rather than beginning with Reuters- or AP-specific code.

Prove:

```text
NewsML-G2 package
→ archived raw package and envelope
→ stable provider item identity
→ exact provider version
→ ordered structured body elements
→ canonical DocumentRepresentation
→ replayable text/node evidence
→ restart
```

The representation should retain provider structure rather than flattening everything into article text:

```text
headline
subtitle
byline
dateline
paragraph
quote
list
caption
media reference
provider metadata
```

NewsML-G2 is the best first implementation because it exercises the standards-based path that the TDD explicitly places above HTML and generic extraction. ([GitHub][2])

## N3 — Immutable revision-chain semantics

Add a complete synthetic provider chain:

```text
original
→ update
→ correction
→ clarification
→ withdrawal/kill
```

Required behavior:

* one stable logical `Source`;
* one immutable `Document` per materially distinct provider version;
* provider version and status preserved verbatim;
* normalized generic revision relation stored separately;
* earlier documents and evidence remain replayable;
* current-state selection prefers the applicable later version without deleting history;
* identical retries are idempotent;
* different bytes under the same provider item/version fail closed.

Do not infer revision meaning merely from changed timestamps. Provider-native status and version semantics must participate in the decision. The TDD explicitly forbids reducing correction or kill behavior to a timestamp change. ([GitHub][2])

## N4 — Rights, embargo, and distribution policy

Make rights metadata operational rather than descriptive.

A versioned policy should govern at least:

```text
archive retention
body-text visibility
logging
diagnostics
public fixture eligibility
exports
search indexing
embedding generation
model-context use
reviewer access
derived graph publication
```

Decisive tests should prove:

```text
embargoed content:
    archived when authorized
    not exported or publicly indexed before release

restricted body:
    IDs, hashes, and bounded metadata may appear in diagnostics
    article text does not

expired or missing entitlement:
    typed blocked result
    no fabricated empty Document

withdrawn item:
    retained historically
    excluded from current-provider projection according to policy
```

Rights and embargo metadata must travel with every capture and revision, and the TDD treats leakage into logs, exports, or derived indexes as a failure condition. ([GitHub][2])

## N5 — Permitted generic HTML article fallback

Implement the weaker-provenance web route only after the provider-native path is authoritative.

Use the documented precedence:

```text
1. provider-native feed/API package
2. NewsML-G2/NITF or equivalent
3. NewsArticle JSON-LD
4. semantic article HTML/DOM
5. versioned general main-text extraction
```

For a permitted HTML fixture, preserve:

* response envelope;
* canonical URI;
* retrieval and publication timestamps;
* JSON-LD when present;
* DOM-aware body structure;
* extraction strategy and version;
* explicit provenance-strength classification.

The fallback must never claim provider-native completeness, provider version semantics, or stronger identity than the available page supports. The TDD expressly requires that weaker guarantees remain explicit. ([GitHub][2])

## N6 — Recorded AP and Reuters conformance adapters

After the common and standards-based paths are stable, add separate provider adapters using:

* synthetic public fixtures with invented article bodies and realistic metadata/version chains; and
* authorized recorded payloads outside the public repository for production conformance.

The adapters should be thin wire-format translators into the provider-neutral contract. They must not:

* write directly to the ledger;
* allocate KoteKomi IDs;
* contain acceptance logic;
* scrape Reuters or AP public article pages;
* place licensed bodies in public tests or logs.

Production readiness for each provider should require:

```text
recorded authorized payload suite
provider identity/version tests
revision-status tests
rights-policy tests
read-only entitlement-gated smoke test
```

The TDD explicitly rejects claiming Reuters/AP support when only generic HTML extraction exists. ([GitHub][2])

## N7 — Integrated structured-news sign-off matrix

Create a gold matrix comparable to the completed PDF matrix.

At minimum:

```text
synthetic NewsML-G2 original
NewsML-G2 update
NewsML-G2 correction
NewsML-G2 clarification
NewsML-G2 withdrawal
generic JSON-LD article
generic semantic-HTML article
ambiguous provider identity
conflicting same-version bytes
embargoed item
rights-restricted item
expired credential response
rate-limit response
provider server error
authorized AP recorded item
authorized Reuters recorded item
```

Each applicable row should cross:

```text
payload capture
→ Source and immutable Document resolution
→ revision classification
→ rights decision
→ canonical representation
→ replayable evidence
→ context planning
→ bounded extraction fixture
→ run-scoped coverage
→ restart replay
```

The sign-off matrix must include mandatory outcomes for:

```text
success
idempotent reuse
update
correction
clarification
withdrawal
rights-blocked
embargo-blocked
identity conflict
provider failure
```

# First implementation PR

The best immediate PR is:

> **N1 — Provider-neutral news domain and adapter contract**

It should add only the common types, deterministic serialization, validation rules, rights-safe synthetic fixtures, and adapter conformance harness.

It should **not** begin with concrete Reuters/AP network clients. Doing so first would mix:

* provider-specific transport;
* identity rules;
* rights handling;
* revision classification;
* canonical representation mapping.

The neutral contract and NewsML-G2 vertical slice should establish those boundaries before provider-specific adapters arrive.

# Updated overall order

After completing **TDD 5 — `docs/2026-07-11-structured-news-ingestion.md`**, resume the accepted sequence:

1. **TDD 5 — `docs/2026-07-11-structured-news-ingestion.md`**
2. **TDD 6 — `docs/2026-07-11-deterministic-context-planning.md`**
3. **TDD 7 — `docs/2026-07-11-staged-model-extraction.md`**
4. **TDD 8 — `docs/2026-07-11-analysis-coverage-and-recovery.md`**
5. **TDD 9 — `docs/2026-07-11-source-lineage-and-independence.md`**
6. **TDD 10 — `docs/2026-07-11-derived-document-retrieval.md`**
7. **TDD 11 — `docs/2026-07-11-evidence-weighted-graph-projections.md`**
8. **TDD 12 — `docs/2026-07-11-ingestion-evaluation-and-release-gates.md`**

The dependency map confirms that **TDD 5** depends on the already-established capture, representation, and evidence foundations, while later lineage work depends on structured news being available. ([GitHub][1])

Throughout this work:

* **TDD 0 — `docs/2026-07-11-authoritative-document-ingestion-program.md`** remains the governing integration contract.
* **TDDs 1–4** remain permanent regression contracts.
* **TDD 12 — `docs/2026-07-11-ingestion-evaluation-and-release-gates.md`** should grow continuously with every new news fixture and failure scenario.

So the immediate planning statement is:

```text
TDD 4:
    complete; preserve as regression gate

Next:
    plan and implement TDD 5
    docs/2026-07-11-structured-news-ingestion.md
```

[1]: https://raw.githubusercontent.com/SQLCODE917/KoteKomi/main/docs/2026-07-11-authoritative-document-ingestion-program.md "raw.githubusercontent.com"
[2]: https://raw.githubusercontent.com/SQLCODE917/KoteKomi/main/docs/2026-07-11-structured-news-ingestion.md "raw.githubusercontent.com"

