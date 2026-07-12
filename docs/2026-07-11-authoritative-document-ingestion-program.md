# TDD: Authoritative Document Ingestion Program

- **Status:** Accepted
- **Scope:** Integration of PDF and structured-news ingestion into the authoritative KoteKomi evidence pipeline
- **Child TDDs:** 12

## 1. Context and problem

KoteKomi currently proves its epistemic workflow with small text fixtures. Production sources introduce three coupled problems:

1. A document is structured and non-linear. A claim may depend on a heading, definition, table header, footnote, or earlier section that is outside the local paragraph.
2. A complete PDF or long article may exceed the extraction model's context window.
3. Every accepted assertion must remain traceable to the exact source occurrence and to every transformation and model decision that produced it.

A conventional “extract text, split into chunks, run RAG” pipeline is insufficient. Chunks are retrieval views, not source records; summaries are navigation aids, not evidence; and model output is a proposal, never accepted state.

This TDD defines how the child deliverables compose into one authoritative, auditable system.

## 2. Goals

The program SHALL:

- ingest PDFs and authorized Reuters/AP or other structured-news payloads;
- preserve immutable source bytes, captures, versions, parser outputs, and model runs;
- represent document structure and deterministic cross-references explicitly;
- generate bounded, reproducible model contexts without silently dropping required context;
- extract atomic candidate claims in stages and ground them to exact source locations;
- record coverage, abstentions, errors, corrections, withdrawals, and retry history;
- distinguish independent corroboration from syndicated or derived copies;
- rebuild search indexes, summaries, graph projections, and weights from authoritative records;
- preserve KoteKomi's review and `ProposedChange` acceptance boundary.

## 3. Non-goals and forbidden approaches

This program does not define a universal ontology, a source-truth oracle, or a single confidence formula.

The following are forbidden:

- overwriting an earlier source version, parser representation, model run, or review outcome;
- treating a generated summary, embedding, retrieval score, or graph weight as source evidence;
- accepting an assertion whose evidence cannot be replayed to one exact source occurrence;
- allowing a model to allocate canonical IDs or write accepted ledger state;
- truncating required context to fit a token budget without an explicit blocked result;
- counting syndicated copies as independent corroboration;
- reporting an analysis run as complete while any planned unit is missing a terminal status;
- silently changing historical evidence anchors after a parser or tokenizer upgrade;
- scraping or bypassing access controls for licensed news content.

## 4. Shared invariants

1. **Immutability:** new bytes, parser settings, model settings, corrections, and reviewer decisions create new records.
2. **Authority boundary:** raw captures and processing artifacts record what was received and done; only accepted ledger records state KoteKomi's reviewed epistemic position.
3. **Replayability:** an accepted source-backed assertion resolves through an evidence link to a representation, text view, exact selector set, and immutable source version.
4. **Determinism:** canonical IDs, hashes, planning order, validation, acceptance writes, and derived rebuilds are application-owned.
5. **Context disclosure:** every model run records the exact rendered input, included nodes, exclusion reasons, tokenizer, prompt, schema, model identity, and parameters.
6. **Coverage honesty:** no planned analysis unit disappears because it produced no proposal or encountered an error.
7. **Derived-state isolation:** search indexes, embeddings, summaries, communities, projected edges, and scores can be deleted and rebuilt without information loss.
8. **Lineage-aware corroboration:** independence is evaluated over source-lineage clusters, not document or URL count.
9. **Temporal clarity:** publication, capture, valid, and ledger transaction times remain distinct.
10. **Fail closed:** ambiguity in identity, evidence resolution, required context, rights, or validation prevents acceptance rather than being guessed away.

## 5. End-to-end architecture

```text
external source
    │
    ▼
Capture Archive ──► Source + immutable Document version
    │
    ▼
Versioned Document Representation
(nodes, text views, regions, tables, links, quality)
    │
    ▼
Analysis Plan ──► deterministic Context Manifests
    │
    ▼
Staged Local-Model Tasks
(mentions → references → claims → grounding → consolidation)
    │
    ▼
Validated Candidate Records ──► ProposedChange review boundary
    │                                      │
    │ rejected / revised                   ▼ accepted
    └──────────────────────────────► Authoritative Ledger
                                             │
                                             ▼
                              Rebuildable retrieval and graph views
```

Archive and ledger writes use existing KoteKomi ports or explicit extensions to them. Pipelines orchestrate use cases; adapters implement external parsing, storage, model, and provider behavior.

## 6. Integrated processing contract

For each captured source item, the system SHALL execute or explicitly record the inability to execute these stages:

1. persist the raw payload and retrieval envelope;
2. resolve stable `Source` identity and immutable `Document` version;
3. create one or more versioned document representations;
4. validate representation quality and select the analysis representation;
5. freeze the set of analysis units;
6. create a deterministic context manifest for each model task;
7. run staged extraction and preserve every attempt;
8. validate model references against the manifest and representation;
9. ground candidate claims to replayable evidence targets;
10. consolidate candidates without destroying disagreements or provenance;
11. create `ProposedChange` records for review;
12. record terminal coverage for every planned unit;
13. update accepted ledger state only through the existing review boundary;
14. rebuild derived retrieval and graph projections from authoritative inputs.

A stage may stop downstream work, but it SHALL emit a typed terminal or blocked result with enough detail to diagnose and retry it.

## 7. Deliverable map and order

| Order | Deliverable | Depends on | Integration exit signal |
|---:|---|---|---|
| 1 | [Source capture and document versioning](2026-07-11-source-capture-and-document-versioning.md) | existing archive/ledger | repeated capture, correction, and conflict scenarios are lossless |
| 2 | [Versioned document representations](2026-07-11-versioned-document-representations.md) | 1 | exact text and structure resolve within a pinned representation |
| 3 | [Replayable evidence targets](2026-07-11-replayable-evidence-targets.md) | 1–2 | accepted evidence uniquely replays and selector disagreement fails closed |
| 4 | [PDF document ingestion](2026-07-11-pdf-document-ingestion.md) | 1–3 | required PDF fixture classes produce quality-scored representations |
| 5 | [Structured news ingestion](2026-07-11-structured-news-ingestion.md) | 1–3 | provider version/update semantics and rights survive ingestion |
| 6 | [Deterministic context planning](2026-07-11-deterministic-context-planning.md) | 2 | contexts are bounded, reproducible, and dependency-complete or blocked |
| 7 | [Staged model extraction](2026-07-11-staged-model-extraction.md) | 3, 6 | bounded tasks produce validated, grounded candidate records only |
| 8 | [Analysis coverage and recovery](2026-07-11-analysis-coverage-and-recovery.md) | 4–7 | every planned unit has a terminal status and interrupted runs resume safely |
| 9 | [Source lineage and independence](2026-07-11-source-lineage-and-independence.md) | 1, 5, 7 | revisions and syndication do not inflate independent support |
| 10 | [Derived document retrieval](2026-07-11-derived-document-retrieval.md) | 2, 6, 8 | indexes rebuild deterministically and return original evidence nodes |
| 11 | [Evidence-weighted graph projections](2026-07-11-evidence-weighted-graph-projections.md) | 3, 8–10 | every projected score is reproducible and contribution-explainable |
| 12 | [Ingestion evaluation and release gates](2026-07-11-ingestion-evaluation-and-release-gates.md) | all | the integrated corpus, fault matrix, and hard gates pass |

A child TDD may ship independently only when its fixture workflow satisfies its current
contract without compatibility paths.

## 8. Key integration interactions

### Long PDF with a distant definition

The parser records the definition and its use as separate nodes. The context planner includes the focus paragraph, ancestor headings, and the referenced definition. The model sees labeled node references. The grounded claim links direct evidence to the focus and definition evidence to the earlier node. Acceptance fails if either required selector no longer resolves.

### Provider correction

A later provider payload creates a new capture and immutable `Document`, plus an explicit correction relation to the earlier version. Earlier assertions and evidence remain reproducible. Current-state projections may prefer the correction, but history and the earlier reporting event remain inspectable.

### Parser or model failure

The attempt, input fingerprint, logs or error code, and affected analysis units are preserved. No partial model batch crosses into proposals. Coverage remains incomplete or failed. A retry creates a new attempt and reuses only artifacts whose fingerprints are still valid.

### Derived-system loss

Deleting the lexical index, embeddings, summaries, graph communities, or weighted projections does not remove source, evidence, proposal, review, or accepted ledger records. A rebuild recreates semantically equivalent derived output from pinned inputs and policies.

## 9. Greenfield contract alignment

- `.md` and `.txt` ingestion uses the same authoritative one-representation path as every
  other source type.
- `Document` remains the immutable content-version record; this program does not introduce a
  competing `DocumentVersion` synonym.
- Stable Source identity is independent of downloaded bytes; no content-hash aliases are
  retained.
- Every EvidenceTarget is created pinned and must pass replay through an immutable validation
  attempt before it can
  support acceptance.
- Source-backed Assertion proposals use explicit evidence-link specifications; no
  whole-document or unlinked proposal adapter remains.
- Schema changes replace superseded fields and Ports in the same change. Rollback never deletes
  archived inputs or accepted history.

## 10. Integrated completion gates

### Correctness criteria

The program is correct only when all of the following hold:

- every accepted source-backed assertion has at least one validated `direct_support` evidence link;
- every linked evidence target resolves to exactly one occurrence in its pinned representation and source version;
- all model-derived candidate fields are traceable to a completed model run and context manifest;
- all planned analysis units have terminal coverage records;
- corrections, withdrawals, and republications preserve prior versions and explicit lineage;
- deleting all derived stores and rebuilding them changes no authoritative record;
- an end-to-end replay from archived payload through proposal produces the same deterministic identities and validation outcomes for pinned tools and inputs;
- every child TDD's correctness criteria pass in the integrated system.

### Success criteria

A release candidate SHALL:

- ingest every mandatory gold-corpus document class defined by the evaluation TDD;
- produce reviewable, atomic, evidence-grounded claim proposals within the stated quality thresholds;
- resume cleanly after injected interruption at each pipeline boundary;
- expose a document-level coverage report and claim-level provenance trace;
- demonstrate a correction chain, a syndication cluster, and an independent corroboration case end to end;
- pass all hard release gates without waivers.

### Failure criteria

The program SHALL be considered incomplete when any of these can occur:

- an accepted assertion cites ambiguous, missing, stale, or generated text;
- required context is omitted while a task is reported successful;
- a parser/model upgrade changes historical evidence without a new representation/run;
- one failed unit disappears from coverage or a partial model batch enters review;
- a provider correction overwrites its predecessor;
- two captures with a conflicting idempotency identity are silently merged;
- syndicated copies increase the independent-source count;
- rights or embargo metadata is discarded or bypassed;
- a derived-store deletion causes authoritative information loss;
- only happy-path fixture tests pass while required real-format and fault-injection tests do not.

## 11. Cross-cutting requirements

- Structured logs include stable correlation IDs but never licensed article bodies or secrets by default.
- Storage writes are atomic at the artifact or proposal-batch boundary.
- Hashes use a named algorithm and canonical serialization.
- Schema, prompt, parser, tokenizer, model, policy, and code versions are recorded as data.
- Test fixtures are redistributable. Licensed provider content stays outside the repository.
- Operational commands expose machine-readable outcomes and non-zero exits for blocked or failed runs.

## 12. References

- KoteKomi: `docs/agent/writing-tdds.md`, `architecture.md`, `domain.md`, `pipelines.md`, and `testing.md`
- W3C Web Annotation Data Model: https://www.w3.org/TR/annotation-model/
- W3C PROV-O: https://www.w3.org/TR/prov-o/
- Docling document model: https://docling-project.github.io/docling/concepts/docling_document/
- IPTC NewsML-G2: https://iptc.org/std/NewsML-G2/specification/

## 13. Halt conditions

Stop implementation and revise this TDD when:

- a required capability cannot be expressed without weakening an invariant;
- a child deliverable requires a second authoritative record for the same concept;
- provider terms prohibit the proposed capture or test method;
- the evaluation corpus shows that a hard gate is unmeasurable or rewards an incorrect behavior;
- a migration would orphan accepted assertions or make historical evidence unreplayable.
