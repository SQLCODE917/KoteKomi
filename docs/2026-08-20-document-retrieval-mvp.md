# DR-1: Document Retrieval MVP

- Status: Proposed
- Program: `derived-retrieval`
- Deliverable ID: `DR-1`
- Depends on: implemented `docs/2026-08-13-live-source-walking-skeleton.md` on `main`
- Program envelope: `docs/2026-07-11-derived-document-retrieval.md`
- Canonical suite: `dr-1-v1`

## Context and problem

The deposited-source walking skeleton can archive a local PDF, establish stable Source and Document identity, create an acceptable `DocumentRepresentationBundle`, persist it, reload it by `representation_id`, and reuse canonical records for identical bytes.

KoteKomi does not yet provide a public retrieval path that searches the accepted representation and turns selected source nodes into a ContextPlanner input. Users and later retrieval planes need a small working baseline before semantic retrieval, hierarchical expansion, Ledger discovery, graph traversal, or cross-plane orchestration are designed.

The MVP must prove this complete path:

```text
accepted DocumentRepresentationBundle
    -> document RetrievalUnits
    -> exact and lexical RetrievalRepresentations
    -> published derived indexes
    -> document RetrievalHits
    -> selected authoritative node IDs
    -> retrieval-selected AnalysisUnit
    -> existing ContextPlanner
    -> ContextManifest containing original source text
```

## Goals

1. Build deterministic document-plane retrieval units from one pinned acceptable representation.
2. Formalize the first concrete `RetrievalRepresentation` payload.
3. Provide exact literal and lexical search channels.
4. Preserve exact identifier and quotation precedence.
5. Record complete index and query provenance.
6. Resolve every hit to original authoritative `DocumentNode` identities.
7. Feed selected node identities through the existing ContextPlanner.
8. Produce a `ContextManifest` containing original node text, not normalized index text.
9. Add deterministic `test-ingest` and `test-query` harness commands for the canonical untracked PDF scenario.
10. Leave a working exact-plus-lexical default that later slices can enrich without replacing the architecture.

## Non-goals

DR-1 does not implement:

- embeddings or a vector backend;
- `embedding_text` or an embedding recipe;
- generated contextualization or generated retrieval questions;
- semantic retrieval;
- reranking or reciprocal-rank fusion;
- parent-child retrieval or automatic parent expansion;
- Ledger-plane retrieval;
- Knowledge-Graph retrieval;
- cross-plane orchestration;
- answer generation as an acceptance dependency;
- ingestion or PDF-parser redesign.

## Contract ownership

DR-1 owns:

```text
retrieval.document_unit.v1
retrieval.document_exact_lexical_representation.v1
retrieval.document_index_manifest.v1
retrieval.document_query.v1
retrieval.document_hit.v1
retrieval.document_exact_before_lexical_policy.v1
retrieval.canonical_scenario_runner.v1
```

DR-1 extends:

```text
analysis_unit creation from externally selected focus_node_ids
ContextPlanner invocation through the existing Application boundary
harness scenario and evidence execution
```

DR-1 consumes:

```text
DocumentRepresentationBundle
DocumentNode
representation acceptance and analyzability state
Archive and Ledger identities
ContextPlanner
ContextManifest
source add-file public Pipeline command
```

DR-1 supersedes no implemented retrieval contract.

## Requirements

### R1. Pinned authoritative input

Every build and query is scoped to one explicit `representation_id`. The representation must:

- exist;
- reload as a complete `DocumentRepresentationBundle`;
- have acceptable analyzability under the selected policy;
- match the expected representation digest or source snapshot when supplied.

The builder must not read the staged file in `raw/`, invoke a PDF parser, or infer an unpinned latest representation.

### R2. Document retrieval units

DR-1 uses one eligible logical analysis node per retrieval unit. This keeps the first unit policy simple and testable.

Eligible nodes:

- belong to the logical analysis view;
- carry original source text;
- are analysis-bearing node types such as heading, paragraph, list item, table, or footnote when the representation marks them as logical content;
- are not display-only duplicates, page furniture, headers, footers, or excluded parser artifacts.

Each unit preserves its authoritative node identity. DR-1 does not merge adjacent nodes or invent fixed-token chunks.

### R3. Explicit derived representation

Each document retrieval unit produces one `DocumentExactLexicalRepresentation`. The representation contains only reproducible exact and lexical fields and their digests. It does not become an evidence record.

### R4. Exact channel

The exact channel performs deterministic contiguous-literal matching over normalized exact-search fields. It must handle identifiers, names, dates, acronyms, and quoted phrases without tokenization loss.

Exact normalization is:

1. Unicode NFC normalization;
2. line-ending normalization to LF;
3. every run of Unicode whitespace replaced by one ASCII space;
4. leading and trailing whitespace removed.

Original case and punctuation remain available. Matching may use a separately derived case-folded field, but the query record must state which exact field matched.

An exact result means the normalized query occurs contiguously in an exact-search field. It does not mean the query equals the whole node.

### R5. Lexical channel

The lexical channel uses a SQLite FTS5 projection over named fields:

```text
body
heading_path
source_title
structural_role
```

The Adapter may add internal fields required by FTS5. Those fields remain derived implementation state.

Lexical ranking uses the Adapter's pinned BM25 configuration. Raw BM25 values and channel rank are preserved. The raw score is not normalized into evidence confidence.

### R6. Deterministic document policy

The default DR-1 policy is:

```text
document_exact_before_lexical_v1
```

Rules:

1. Run exact and lexical channels for the same normalized query.
2. Deduplicate by `retrieval_unit_id`.
3. Order exact hits before lexical-only hits.
4. Preserve the best channel rank for each hit and retain all channel observations in the query record.
5. Within the exact group, order by exact match class, then deterministic source order, then `retrieval_unit_id`.
6. Within the lexical-only group, order by lexical rank, then deterministic source order, then `retrieval_unit_id`.
7. A unique exact literal match must rank first.
8. No reranker or learned fusion participates.

### R7. Atomic index publication

An index build creates unpublished derived state, validates counts and fingerprints, and publishes one complete manifest atomically. Queries see either the previous complete manifest or the new complete manifest, never a partially built projection.

A stale, corrupt, incomplete, or source-incompatible manifest produces a typed failure.

### R8. Hit resolution

Every selected hit carries:

- `retrieval_unit_id`;
- `representation_id`;
- authoritative `node_id` values;
- original text digest;
- plane and channel observations;
- index manifest identity.

Before ContextPlanner invocation, the Application layer reloads the authoritative nodes and verifies the recorded digest. Index text is never treated as the source of evidence.

### R9. ContextPlanner bridge

The query Application use case creates a retrieval-selected `AnalysisUnit` or equivalent existing input object with the selected authoritative `focus_node_ids`. It invokes the existing ContextPlanner public boundary.

Search logic must not be inserted into ContextPlanner's structural candidate expansion. ContextPlanner continues to own dependency resolution, token budgeting, deterministic packing, and rendering.

The resulting `ContextManifest` must render original authoritative node text. Exact normalization and FTS fields must not appear as evidence unless identical text independently comes from authoritative nodes.

### R10. Query provenance

Every query persists or returns a `RetrievalQueryRecord` that contains:

- original query text;
- normalized query text;
- `representation_id` and source snapshot identity;
- unit, projection, index, and query policy identities;
- consulted index manifests;
- exact and lexical candidate observations;
- raw scores where a channel supplies them;
- channel ranks;
- deduplication decisions;
- final selected rank and reason;
- rejected candidates and reason where bounded by the query policy;
- authoritative node references;
- analysis unit identity;
- ContextManifest identity;
- typed failure information.

### R11. Disposable derived state

Deleting the DR-1 exact and lexical projections must delete no authoritative Source, Document, representation, node, Ledger record, or Archive blob. A rebuild from the same representation and pinned policies must reproduce the same unit, representation, and content fingerprints and the same deterministic query ordering.

### R12. Canonical scenario

DR-1 implements the repository-local harness commands:

```bash
uv run kotekomi-agent test-ingest anthropic-dod-dispute-v1 --lock-fixture
uv run kotekomi-agent test-ingest anthropic-dod-dispute-v1
uv run kotekomi-agent test-query anthropic-dod-dispute-v1 --suite dr-1-v1
```

The first form is an explicit one-time lock operation for the untracked canonical PDF. It refuses to replace an existing lock. Normal validation uses the latter two commands in order.

The commands read committed inputs under:

```text
.agent/scenarios/anthropic-dod-dispute-v1/
```

They do not import product packages into `packages/devtools`. They invoke public product commands through argument arrays and capture deterministic machine-readable results.

## Proposed architecture

### Package responsibilities

#### Domain

Define immutable values and records with no Adapter dependencies:

```text
RetrievalPlane
RetrievalChannel
DocumentRetrievalUnit
DocumentExactLexicalRepresentation
RetrievalIndexManifest
RetrievalHit
RetrievalChannelObservation
RetrievalQueryRecord
retrieval-specific typed failures
```

#### Application

Define Ports and use cases:

```text
LoadDocumentRepresentationPort
DocumentRetrievalProjectionPort
DocumentRetrievalQueryPort
RetrievalQueryRecordPort
BuildDocumentRetrievalProjection
QueryDocumentRetrieval
BuildContextFromRetrievalSelection
```

The Application layer validates authoritative identity and digest relationships before and after Adapter calls.

#### Adapters

Implement SQLite exact and FTS5 derived projections. The Adapter owns SQL, FTS5 details, atomic publication, corruption checks, and backend-native scores. It does not own query intent, evidence authority, or ContextPlanner policy.

#### Pipelines

Expose stable public CLI commands and construct Dependencies. CLI code must not contain retrieval ranking logic.

#### Devtools harness

Load scenario and suite contracts, verify fixture locks, execute the public Pipeline CLI, validate receipts, and report deterministic evidence. Devtools must not import Domain, Application, Adapter, or Pipeline Python modules.

## Key interactions

### Projection build

```text
caller
  -> BuildDocumentRetrievalProjection(representation_id)
  -> load accepted DocumentRepresentationBundle
  -> DocumentRetrievalUnitBuilder
  -> DocumentExactLexicalRepresentationBuilder
  -> projection Adapter begins unpublished build
  -> write exact rows and FTS5 rows
  -> validate counts and content fingerprint
  -> atomically publish RetrievalIndexManifest
  -> return build result
```

A repeated build with identical source and policy inputs may return the existing complete manifest. It must not create semantically duplicate published manifests without an explicit reason.

### Query and context

```text
caller
  -> QueryDocumentRetrieval(representation_id, query)
  -> resolve compatible published manifest
  -> exact channel
  -> lexical channel
  -> document_exact_before_lexical_v1
  -> selected RetrievalHits
  -> reload and verify original DocumentNodes
  -> create retrieval-selected AnalysisUnit
  -> ContextPlanner
  -> ContextManifest
  -> RetrievalQueryRecord
  -> query result
```

### Canonical `test-ingest`

```text
load scenario.json
  -> verify schema
  -> locate raw/Anthropic–United_States_Department_of_Defense_dispute.pdf
  -> require or create explicit fixture lock
  -> refuse network
  -> create isolated Archive and Ledger
  -> invoke public source add-file CLI
  -> verify ingest expectations
  -> restart public application boundary
  -> reload representation
  -> ingest identical bytes again
  -> verify canonical reuse
  -> emit harness receipt
```

The ingest receipt becomes the pinned input to `test-query`. `test-query` must not search for a latest representation.

### Canonical `test-query`

```text
load scenario and dr-1-v1 suite
  -> verify current ingest receipt and fixture lock
  -> invoke public retrieval build command
  -> invoke public retrieval query command for every JSONL case
  -> validate RetrievalQueryRecords
  -> validate ContextManifests
  -> delete and rebuild projection in an isolated verification phase
  -> rerun deterministic equivalence cases
  -> emit harness receipt
```

## Data model

### `DocumentRetrievalUnit`

```text
retrieval_unit_id
plane = DOCUMENT
source_snapshot_id
representation_id
node_ids
source_order
structural_role
section_path
source_page_numbers
original_text_digest
unit_policy_id = document_node_unit_v1
unit_fingerprint
```

Rules:

- `node_ids` contains exactly one node in DR-1.
- IDs derive deterministically from the source snapshot, node identity, and unit-policy identity.
- Source order comes from the accepted representation, not index row insertion order.
- `section_path` aids search and diagnostics but does not replace authoritative heading nodes in context.

### `DocumentExactLexicalRepresentation`

```text
retrieval_representation_id
retrieval_unit_id
plane = DOCUMENT
source_snapshot_id
source_fingerprint
projection_policy_id = document_exact_lexical_projection_v1
projection_builder_version
exact_fields
lexical_fields
field_digests
representation_fingerprint
```

Recommended DR-1 payload:

```text
exact_fields
    body_nfc
    body_casefold
    source_title_nfc
    heading_path_nfc

lexical_fields
    body
    heading_path
    source_title
    structural_role
```

The record does not contain backend row IDs, FTS internal tokens, or authoritative evidence text beyond reproducible derived fields.

### `RetrievalIndexManifest`

```text
index_manifest_id
plane = DOCUMENT
channels = [EXACT, LEXICAL]
source_snapshot_id
representation_id
representation_digest
unit_policy_id
projection_policy_id
query_policy_compatibility
adapter_identity
adapter_configuration_digest
unit_count
representation_count
content_fingerprint
publication_status
created_at
published_at?
```

### `RetrievalChannelObservation`

```text
channel
raw_score?
channel_rank
matched_field?
matched_literal_digest?
```

### `RetrievalHit`

```text
retrieval_unit_id
plane = DOCUMENT
authoritative_node_ids
original_text_digest
index_manifest_id
channel_observations
final_rank
selected
selection_reason
```

### `RetrievalQueryRecord`

```text
retrieval_query_id
representation_id
source_snapshot_id
query_text
normalized_query_text
query_policy_id
index_manifest_ids
candidate_hits
selected_node_ids
analysis_unit_id
context_manifest_id
failure?
created_at
```

## APIs and interfaces

Names may follow repository naming conventions, but the public behavior is fixed by this TDD.

### Application commands

```python
@dataclass(frozen=True)
class BuildDocumentRetrievalProjectionCommand:
    representation_id: str
    expected_representation_digest: str | None = None


@dataclass(frozen=True)
class QueryDocumentRetrievalCommand:
    representation_id: str
    query_text: str
    maximum_hits: int
    context_profile_id: str
    expected_index_manifest_id: str | None = None
```

### Application results

Build result includes:

```text
status
representation_id
index_manifest_id
unit_count
representation_count
content_fingerprint
reused_existing_manifest
failure?
```

Query result includes:

```text
status
retrieval_query_id
representation_id
index_manifest_ids
hits
selected_node_ids
analysis_unit_id
context_manifest_id
failure?
```

### Public Pipeline CLI

```bash
uv run kotekomi retrieval build-document \
  --representation-id <representation-id> \
  --format json

uv run kotekomi retrieval query \
  --representation-id <representation-id> \
  --query <query-text> \
  --maximum-hits 10 \
  --context-profile retrieval-validation-v1 \
  --format json
```

All machine-readable commands write one deterministic JSON result to standard output. Diagnostics go to standard error. Exit status and typed result status must agree.

### Devtools CLI

```bash
uv run kotekomi-agent test-ingest <scenario-id> [--lock-fixture]
uv run kotekomi-agent test-query <scenario-id> --suite <suite-id>
```

`test-ingest` and `test-query` are evidence-producing harness operations. They save full stdout and stderr, validate machine-readable payloads, create canonical receipts through existing deterministic harness functions, and report the receipt identity.

## Behavior and domain rules

### Query normalization

The query retains both original and normalized forms. The exact channel uses the exact normalization defined in R4. The lexical Adapter applies its pinned FTS5 tokenizer and query escaping policy. The query record stores the policy identity, not only the final query string.

Empty or normalization-empty queries fail with `retrieval_query_empty`.

### Exact precedence

A unique exact literal match ranks first even if FTS5 returns another unit with a better native BM25 value. Exact precedence is a query-policy rule, not a conversion of BM25 into a comparable confidence score.

### Selection size

The public query accepts a bounded positive `maximum_hits`. The Application policy may select fewer hits when fewer valid candidates exist. DR-1 does not automatically broaden the query or synthesize alternatives.

### Context profile

The canonical suite uses a fixed `retrieval-validation-v1` context profile with pinned prompt/schema identity and token budget. This profile exists to exercise the real ContextPlanner deterministically. The retrieval result remains useful without invoking an LLM.

### Source ordering

Source order is derived from the accepted representation's logical reading order. Tie-breaking never depends on SQLite row order, wall-clock time, dictionary iteration, or random values.

### Rebuild equivalence

For the same authoritative snapshot and policies, rebuild equivalence requires:

- identical unit fingerprints;
- identical representation fingerprints;
- identical index content fingerprint;
- identical exact and lexical candidate order for the canonical required cases;
- identical selected authoritative node IDs;
- equivalent ContextManifest source segments under the pinned context profile.

Manifest IDs may differ only when repository identity rules intentionally include creation identity. Content fingerprints and observable results must remain equal.

### Failure types

At minimum, represent these failures explicitly:

```text
retrieval_representation_not_found
retrieval_representation_not_acceptable
retrieval_source_snapshot_mismatch
retrieval_index_not_found
retrieval_index_stale
retrieval_index_incomplete
retrieval_index_corrupt
retrieval_query_empty
retrieval_hit_source_missing
retrieval_hit_digest_mismatch
retrieval_context_planning_failed
fixture_missing
fixture_unlocked
fixture_digest_mismatch
scenario_schema_invalid
query_suite_invalid
canonical_ingest_failed
canonical_query_failed
```

Expected operator conditions must not appear as uncaught tracebacks.

## Canonical scenario assets

DR-1 consumes the committed assets:

```text
.agent/schemas/retrieval-scenario-v1.schema.json
.agent/schemas/retrieval-ingest-expectations-v1.schema.json
.agent/schemas/retrieval-query-case-v1.schema.json
.agent/schemas/retrieval-query-suite-v1.schema.json
.agent/scenarios/anthropic-dod-dispute-v1/scenario.json
.agent/scenarios/anthropic-dod-dispute-v1/ingest-expectations.json
.agent/scenarios/anthropic-dod-dispute-v1/queries/base-v1.jsonl
.agent/scenarios/anthropic-dod-dispute-v1/queries/dr-1-document-exact-lexical-v1.jsonl
.agent/scenarios/anthropic-dod-dispute-v1/suites/dr-1-v1.json
```

The local PDF is:

```text
raw/Anthropic–United_States_Department_of_Defense_dispute.pdf
```

It remains untracked. The scenario must never download the URL or replace the local bytes.

## Acceptance criteria

### Domain and Application

1. Unit IDs and fingerprints are deterministic for a pinned representation and policy.
2. Retrieval representations are deterministic and contain no backend-specific authority.
3. The Application layer rejects missing, unacceptable, stale, corrupt, and digest-incompatible inputs with typed failures.
4. Fake-Port tests prove projection build, exact precedence, lexical fallback, hit resolution, query recording, and ContextPlanner invocation without a production Adapter.
5. Search logic remains outside ContextPlanner structural candidate expansion.

### Adapter

6. SQLite exact and FTS5 Adapter contract tests cover build, publish, query, reuse, delete, rebuild, stale-manifest rejection, incomplete-build invisibility, and corruption detection.
7. FTS5 configuration and tokenizer identity are pinned in the manifest.
8. A query never observes an unpublished partial build.
9. Deleting the projection leaves authoritative stores unchanged.

### Public Pipeline

10. `retrieval build-document` builds or reuses a complete manifest and returns deterministic JSON.
11. `retrieval query` returns complete hit observations, selected authoritative node IDs, a query record identity, an analysis unit identity, and a ContextManifest identity.
12. Restarting the process and querying the same published manifest preserves observable results.

### Canonical `test-ingest`

13. Missing local PDF returns `fixture_missing`.
14. An unlocked scenario without `--lock-fixture` returns `fixture_unlocked`.
15. `--lock-fixture` computes the exact local SHA-256 and page count, writes them deterministically, and refuses to replace an existing lock.
16. A changed local PDF returns `fixture_digest_mismatch`.
17. No network operation occurs.
18. The command invokes the public `source add-file` path with the committed Wikipedia URL.
19. Required anchors, section headings, analyzability, restart reload, byte preservation, and idempotent re-ingest all pass.
20. The command emits a verified harness receipt whose payload pins the resulting representation identity and digest.

### Canonical `test-query`

21. `test-query` consumes the verified ingest receipt rather than selecting a latest representation.
22. It invokes the public retrieval build and query commands, not Adapter internals.
23. Every required case in `base-v1.jsonl` and `dr-1-document-exact-lexical-v1.jsonl` passes.
24. Required unique exact cases rank first.
25. Required lexical cases place an expected authoritative node within their configured maximum rank.
26. Every required case produces a ContextManifest containing its required original-text anchor.
27. No ContextManifest presents normalized exact fields, FTS content, contextual prefixes, `embedding_text`, or generated navigation artifacts as evidence.
28. Every hit resolves to the pinned representation and passes original-text digest verification.
29. Deleting and rebuilding the projection reproduces content fingerprints and deterministic required-case results.
30. The query suite emits a verified harness receipt that references all query records, index manifests, and ContextManifests.

### Repository quality

31. Applicable formatting, lint, type, test, schema, readiness, scope, and receipt-chain checks pass.
32. No dead experimental path, compatibility facade, hidden network dependency, or second prompt-building subsystem remains.
33. The repository is clean after deterministic generated evidence is recorded through approved harness operations.

## Test plan

### Fast CI tests

- Domain value and fingerprint tests.
- Unit-builder tests over small project-owned representation fixtures.
- Application fake-Port tests.
- SQLite exact Adapter tests.
- SQLite FTS5 Adapter tests.
- atomic publication and rebuild tests.
- Pipeline CLI JSON contract tests.
- devtools scenario loader and JSONL validator tests using temporary project-owned files.
- ContextPlanner bridge tests with small accepted representations.

### Local canonical closeout

Run in order from repository root:

```bash
uv run kotekomi-agent test-ingest anthropic-dod-dispute-v1
uv run kotekomi-agent test-query anthropic-dod-dispute-v1 --suite dr-1-v1
```

For the first run only, replace the first command with:

```bash
uv run kotekomi-agent test-ingest anthropic-dod-dispute-v1 --lock-fixture
```

The final implementation receipt must include the canonical ingest and query receipt chain.

## Reference implementations

Use existing repository patterns and public seams:

- deposited-file ingestion in `packages/pipelines/src/kotekomi_pipelines/cli.py`;
- `DocumentRepresentationBundle` persistence and reload;
- node identities, section paths, source order, source pages, and text digests created by the Docling representation Adapter;
- ContextPlanner and `AnalysisUnit.focus_node_ids` in `packages/application/src/kotekomi_application/context_planning.py`;
- SQLite repository transaction and schema-management patterns;
- devtools subprocess, deterministic output, and receipt conventions;
- `docs/agent/writing-tdds.md` and `packages/devtools/AGENTS.md`.

## Constraints

- Product dependencies point inward.
- Devtools does not import product packages.
- The canonical validation path performs no network access.
- The PDF remains ignored and untracked.
- Retrieval indexes are derived and rebuildable.
- Original source text and authoritative IDs remain the evidence boundary.
- No future-plane schema is added merely for symmetry.

## Halt conditions

Stop and revise DR-1 if implementation would:

1. read `raw/` during retrieval build or query instead of loading the pinned representation;
2. treat exact or FTS rows as authoritative source text;
3. add search logic to ContextPlanner's structural expansion function;
4. bypass `AnalysisUnit` or the public ContextPlanner boundary with a second prompt builder;
5. normalize away the literals needed by the canonical exact cases;
6. compare BM25 and exact observations as if they shared a calibrated confidence scale;
7. expose a partial index to queries;
8. fetch Wikipedia during `test-ingest` or `test-query`;
9. silently modify a locked fixture digest;
10. require embeddings, Ledger records, graph state, or answer generation for the MVP to work;
11. make the untracked canonical PDF mandatory for ordinary CI;
12. ask an implementation agent to hand-edit roadmap status, task state, or verification receipts.
