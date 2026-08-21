# DR-3: Document Hybrid Activation

- Status: Accepted
- Program: `derived-retrieval`
- Deliverable ID: `DR-3`
- Depends on: `docs/2026-08-20-document-retrieval-mvp.md` and
  `docs/2026-08-21-context-enriched-document-semantic-retrieval.md`
- Canonical suite: `dr-3-v1`

## Context & Problem

DR-1 provides exact and lexical document retrieval.
DR-2 provides an explicit semantic document retrieval channel.
An operator must currently choose the DR-1 path or the DR-2 path.
The normal document query path does not yet use all three channels.

**Glossary**

- A **hybrid query** is the normal document query path that applies the DR-3 policy.
- An **exact guard** is the policy branch that selects one exact candidate without other channels.
- A **fusion score** is the deterministic sum of reciprocal channel ranks for one candidate.
- A **consulted channel** is a channel that the Application Layer called for one query.

### Primary end-to-end flow

1. An operator builds the current document indexes with a configured embedding profile.
2. An operator submits a document query without a channel option.
3. The Application Layer checks the exact index for one candidate.
4. The Application Layer selects that candidate when the exact guard succeeds.
5. The Application Layer otherwise fuses exact, lexical, and semantic candidates.
6. The Application Layer sends selected authoritative node IDs to `ContextPlanner`.

## Goals

- A user submits one normal document query without choosing a retrieval channel.
- A unique exact literal retains deterministic precedence.
- A non-unique literal and a paraphrase use exact, lexical, and semantic evidence together.
- A reviewer can inspect each channel observation and the hybrid selection decision.
- A query fails explicitly when the required derived indexes are not ready.

## Requirements

### Hybrid policy requirements

- HP-01: The Application Layer identifies the hybrid policy as
  `document_exact_lexical_semantic_rrf60_v1`.
- HP-02: The Application Layer first obtains exact candidates for every hybrid query.
- HP-03: The Application Layer selects one exact candidate when the exact index returns one
  candidate.
- HP-04: The exact guard records `unique_exact_guard` as the selection reason.
- HP-05: The exact guard consults only the exact channel.
- HP-06: The exact guard does not call the Embedding Port.
- HP-07: The Application Layer obtains exact, lexical, and semantic candidates when the exact
  index returns zero or multiple candidates.
- HP-08: The Application Layer deduplicates fusion candidates by `retrieval_unit_id`.
- HP-09: The Application Layer adds `1 / (60 + channel_rank)` for each candidate observation.
- HP-10: The Application Layer orders fusion candidates by descending fusion score.
- HP-11: The Application Layer breaks equal fusion scores by source order and then retrieval
  unit ID.
- HP-12: The Application Layer applies `maximum_hits` after it orders fusion candidates.
- HP-13: The Application Layer records `rrf60_fusion` as the selection reason for fusion
  candidates.
- HP-14: The Application Layer retains each channel's native rank and raw score.
- HP-15: The Application Layer does not interpret a native score or fusion score as evidence
  confidence.

### Index readiness requirements

- IR-01: The normal build command builds exact/lexical and semantic manifests.
- IR-02: The normal query command requires a current exact/lexical manifest and semantic
  manifest.
- IR-03: Both manifests must identify the same representation ID, representation digest, source
  snapshot, and unit policy.
- IR-04: The semantic manifest must match the configured embedding profile and model identity.
- IR-05: The Pipeline returns `hybrid_profile_unavailable` when the configured profile is absent.
- IR-06: The Pipeline returns the existing typed index failure when either manifest is missing,
  stale, incomplete, or corrupt.
- IR-07: The normal query command does not build or rebuild an index.

### Provenance requirements

- PR-01: Each `RetrievalChannelObservation` identifies the manifest that produced it.
- PR-02: A `RetrievalHit` records its optional fusion score.
- PR-03: A `RetrievalQueryRecord` records its consulted channels and all consulted manifest IDs.
- PR-04: A fusion query record contains every considered candidate.
- PR-05: A fusion query record marks only the first `maximum_hits` candidates as selected.
- PR-06: A query result exposes the query policy, consulted channels, candidate observations,
  selected node IDs, and ContextManifest identity.
- PR-07: Every selected hit resolves to authoritative `DocumentNode` IDs and its original-text
  digest.

### Pipeline requirements

- PL-01: The configuration file stores the normal profile at
  `[document_retrieval].default_embedding_profile`.
- PL-02: The Pipeline rejects a default profile ID that does not name an embedding profile.
- PL-03: `kotekomi retrieval build-document` without `--channel` uses the normal profile and
  builds both manifests.
- PL-04: `kotekomi retrieval query` without `--channel` runs the hybrid query.
- PL-05: `--channel exact-lexical` runs the DR-1 diagnostic path.
- PL-06: `--channel semantic --embedding-profile <profile-id>` runs the DR-2 diagnostic path.
- PL-07: Diagnostic channels do not change normal hybrid behavior.

### Context requirements

- CT-01: The Application Layer sends only selected authoritative node IDs to `ContextPlanner`.
- CT-02: `ContextPlanner` remains the only component that creates a `ContextManifest`.
- CT-03: A resulting `ContextManifest` contains original authoritative text.
- CT-04: A resulting `ContextManifest` excludes exact fields, lexical fields, rendered embedding
  text, vectors, and fusion scores.

### Canonical scenario requirements

- CS-01: DR-3 adds v3 retrieval query case and suite schemas.
- CS-02: DR-3 leaves v1 and v2 schemas, query packs, and suites unchanged.
- CS-03: The `dr-3-v1` suite runs base, DR-1, DR-2, and DR-3 query packs.
- CS-04: The suite uses the pinned `semantic-validation-v1` profile.
- CS-05: The suite proves unique exact precedence through the hybrid command.
- CS-06: The suite proves a non-unique exact query records all three channel observations.
- CS-07: The suite proves semantic paraphrase anchors remain selected through the hybrid command.
- CS-08: The suite proves deterministic rebuild equivalence for both manifests, candidate order,
  selected nodes, and ContextManifests.

## Proposed Architecture

The Pipeline owns configuration and command selection.
The Application Layer owns the exact guard and rank fusion policy.
The SQLite Adapter returns candidate observations from derived indexes.
The embedding Adapter returns semantic query vectors.
`ContextPlanner` owns context construction.

```text
operator -> Pipeline -> Application Layer -> SQLite Adapter
                                  |              |
                                  |              v
                                  |       exact and lexical candidates
                                  v
                           Embedding Adapter
                                  |
                                  v
                           semantic candidates
                                  |
                                  v
                            ContextPlanner
```

## Key Interactions

```text
operator -> Pipeline: retrieval query
Pipeline -> Application Layer: hybrid query command
Application Layer -> SQLite Adapter: exact candidates
Application Layer -> Embedding Adapter: query vector when exact guard fails
Application Layer -> SQLite Adapter: lexical and semantic candidates
Application Layer -> ContextPlanner: selected node IDs
ContextPlanner -> Pipeline: ContextManifest
Pipeline -> operator: query record and authoritative nodes
```

## Data Model

`RetrievalChannelObservation` adds a required `index_manifest_id`.
`RetrievalHit` replaces its single manifest ID with channel observation manifest IDs.
`RetrievalHit` adds an optional `fusion_score`.
`RetrievalQueryRecord` adds `consulted_channels`.
The existing exact/lexical and semantic manifests remain separate derived records.
DR-3 does not create a hybrid index manifest.

## APIs / Interfaces

The Application Layer adds a hybrid query command and result DTO.
The hybrid command requires a representation ID, query text, maximum hits, context profile, and
embedding profile.
The hybrid result exposes the hybrid policy ID and consulted channels.
The Pipeline resolves the embedding profile from `document_retrieval.default_embedding_profile`
for the normal commands.
The diagnostic semantic command continues to require an explicit embedding profile.

## Behavior & Domain Rules

The normal build command fails before it publishes either manifest when the configured profile is
unavailable.
The normal query command fails before it returns candidates when either manifest does not match
the pinned representation.
The Application Layer retains the exact guard result even when lexical or semantic retrieval
would return a different candidate.
The Application Layer records every fusion candidate before it marks selected candidates.
The Application Layer passes only selected authoritative node IDs across the ContextPlanner
boundary.
Deleting either derived manifest loses no authoritative source knowledge.
Rebuilding the same pinned inputs produces equivalent hybrid query behavior.

## Acceptance Criteria

- AC-HP-01: Application fake-Port tests prove the exact guard returns one exact candidate without
  an embedding call.
- AC-HP-02: Application fake-Port tests prove zero and multiple exact candidates invoke all
  fusion channels.
- AC-HP-03: Application tests prove RRF-60 arithmetic, deduplication, equal-score ordering, and
  post-fusion selection cutoff.
- AC-IR-01: Pipeline and Adapter tests prove missing, stale, incomplete, corrupt, and
  profile-incompatible manifests fail explicitly.
- AC-PR-01: Domain tests prove each channel observation identifies its manifest and fusion hits
  record valid scores.
- AC-PR-02: Query-record tests prove every fusion candidate, consulted channel, selection
  decision, and manifest is inspectable.
- AC-PL-01: Pipeline tests prove unqualified build and query commands use the configured normal
  profile.
- AC-PL-02: Pipeline tests prove diagnostic channel commands remain isolated.
- AC-CT-01: Application tests prove only authoritative node IDs enter `ContextPlanner`.
- AC-CT-02: Context tests prove derived retrieval material does not enter a `ContextManifest`.
- AC-CS-01: Schema tests prove v1 and v2 scenario assets remain unchanged and v3 assets validate.
- AC-CS-02: Canonical `test-ingest` and `test-query --suite dr-3-v1` pass with the locked PDF
  and pinned profile.
- AC-CS-03: The canonical rebuild check preserves hybrid candidate order, selected node IDs, and
  ContextManifest identities.
- AC-CS-04: Formatting, lint, type checks, repository tests, Harness receipts, receipt-chain
  checks, and post-merge main CI pass.

## Reference Implementations

- DR-1 query policy: `packages/application/src/kotekomi_application/document_retrieval.py`.
- DR-2 semantic profile: `packages/pipelines/src/kotekomi_pipelines/config.py`.
- SQLite candidate queries: `packages/adapters/src/kotekomi_adapters/sqlite_document_retrieval.py`.
- Canonical scenario runner: `packages/devtools/src/kotekomi_devtools/retrieval_scenarios.py`.

## Constraints and Halt Conditions

DR-3 stops if the normal query path requires generated text, a reranker, or a new retrieval plane.
DR-3 stops if `ContextPlanner` receives derived retrieval material.
DR-3 stops if a semantic profile cannot identify its pinned model artifact.
DR-3 stops if a test requires a score to represent evidence confidence.
