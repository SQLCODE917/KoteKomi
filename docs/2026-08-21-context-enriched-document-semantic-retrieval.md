# DR-2: Context-Enriched Document Semantic Retrieval

- Status: Accepted
- Program: `derived-retrieval`
- Deliverable ID: `DR-2`
- Depends on: completed `docs/2026-08-21-authoritative-document-hierarchy-for-dr1.md`
- Program envelope: `docs/2026-07-11-derived-document-retrieval.md`
- Canonical suite: `dr-2-v1`

## Context & Problem

DR-1 provides exact and lexical retrieval over an acceptable `DocumentRepresentationBundle`.
DR-1H preserves the full authoritative heading ancestry that `ContextPlanner` requires.
Users cannot yet find an authoritative node when their query uses different words from the source.

**Glossary**

- An **embedding profile** identifies one local embedding Adapter, model, and input limit.
- An **embedding vector** is one derived numeric representation of one rendered string.
- A **semantic representation** records how KoteKomi renders one `DocumentRetrievalUnit`.
- The representation records the embedding model inputs by digest.
- A **semantic manifest** identifies one complete published semantic index.
- A **semantic query** is a document-plane query that selects only the `semantic` channel.

### Primary end-to-end flow

1. An operator selects an embedding profile and builds a semantic manifest.
2. The Application Layer renders each unit with authoritative structural context.
3. The embedding Adapter returns one vector for each rendered string.
4. The SQLite Adapter publishes the vectors and semantic manifest atomically.
5. An operator runs a semantic query and receives authoritative `DocumentNode` identifiers.
6. `ContextPlanner` creates a `ContextManifest` from those identifiers.

## Goals

- A user can find authoritative document text through a semantic paraphrase.
- A user can select semantic retrieval without changing the DR-1 default query behavior.
- A user can inspect the model, renderer, index, candidates, and context for one semantic query.
- A user can delete and rebuild semantic retrieval state without losing source knowledge.
- A user receives original source text in every resulting `ContextManifest`.

## Requirements

### Semantic representation requirements

- SR-01: The Application Layer builds semantic representations from accepted retrieval units.
- SR-02: The renderer writes source title, full section path, structural role, and node text.
- SR-03: The renderer uses NFC normalization and LF line-ending normalization.
- SR-04: The renderer uses UTF-8 bytes for every recorded digest.
- SR-05: The renderer prepends `search_document: ` before it sends a document string to the Adapter.
- SR-06: The query renderer prepends `search_query: ` before it sends a query string to the Adapter.
- SR-07: A semantic representation records unit identity and source fingerprint.
- SR-08: A semantic representation records renderer policy and input digests.
- SR-09: A semantic representation does not persist rendered text or vectors as canonical state.
- SR-10: The Application Layer returns `semantic_input_too_large` above the profile character limit.
- SR-11: The failure identifies the `DocumentRetrievalUnit` and the embedding profile.

### Embedding Adapter requirements

- EA-01: The Application Layer defines an `EmbeddingPort` that accepts ordered UTF-8 strings.
- EA-02: The Port returns one ordered vector for each input string.
- EA-03: The Port returns an `EmbeddingModelIdentity` for every successful call.
- EA-04: `EmbeddingModelIdentity` contains adapter ID, model ID, model digest, and vector dimension.
- EA-05: `EmbeddingModelIdentity` contains the embedding configuration digest.
- EA-06: The LM Studio Adapter uses `http://127.0.0.1:1234/v1/embeddings`.
- EA-07: The llama-server Adapter uses its OpenAI-compatible embeddings endpoint.
- EA-08: The Ollama Adapter uses its `/api/embed` endpoint.
- EA-09: Each Adapter rejects unordered and malformed vector responses.
- EA-10: Each Adapter rejects non-finite, zero, and dimension-inconsistent vectors.
- EA-11: Each Adapter reports model absence and mismatch as typed failures.
- EA-12: Each Adapter reports transport failure as a typed failure.
- EA-13: The Application Layer stores vectors as normalized IEEE-754 float32 values.
- EA-14: The Application Layer records the vector-byte digest after normalization.

### Semantic index requirements

- SI-01: The SQLite Adapter stores semantic vectors only as derived state.
- SI-02: A semantic manifest has exactly the `semantic` channel.
- SI-03: A semantic manifest identifies one representation, renderer policy, and embedding profile.
- SI-04: A semantic manifest identifies model identity and content fingerprint.
- SI-05: The Adapter validates every vector before it publishes a semantic manifest.
- SI-06: The Adapter hides an incomplete semantic manifest from queries.
- SI-07: The Adapter rejects stale, corrupt, profile-incompatible, and model-incompatible manifests.
- SI-08: The Adapter ranks vectors by descending cosine similarity.
- SI-09: The Adapter breaks equal scores by source order and then retrieval unit ID.
- SI-10: A semantic manifest does not replace the DR-1 exact-and-lexical manifest.

### Query and context requirements

- QC-01: The public retrieval query command accepts `--channel semantic`.
- QC-02: A semantic query requires an explicit `--embedding-profile`.
- QC-03: A query without `--channel` preserves the DR-1 exact-and-lexical default.
- QC-04: A semantic `RetrievalHit` records channel, native score, rank, and semantic manifest ID.
- QC-05: A semantic hit resolves to original `DocumentNode` IDs and its original-text digest.
- QC-06: The Application Layer passes selected node IDs to the existing ContextPlanner boundary.
- QC-07: `ContextPlanner` remains the only component that creates a `ContextManifest`.
- QC-08: A `ContextManifest` contains original authoritative text, not rendered strings or vectors.
- QC-09: A `RetrievalQueryRecord` records profile, model identity, manifest, candidates, and nodes.

### Canonical scenario requirements

- CS-01: DR-2 adds v2 schemas for retrieval query cases and retrieval query suites.
- CS-02: DR-2 leaves every closed v1 schema, query pack, and query suite unchanged.
- CS-03: The v2 case schema accepts `semantic_paraphrase` and the `semantic` channel.
- CS-04: The scenario runner validates v1 and v2 query cases with their matching schemas.
- CS-05: `dr-2-v1` runs base, DR-1, and DR-2 query packs in that order.
- CS-06: `dr-2-v1` requires the `semantic-validation-v1` embedding profile.
- CS-07: The reference profile uses LM Studio on macOS.
- CS-08: The reference profile uses `http://127.0.0.1:1234/v1`.
- CS-09: The profile uses `text-embedding-nomic-embed-text-v1.5` with 768 dimensions.
- CS-10: The profile pins the local model digest before it builds a semantic manifest.
- CS-11: The DR-2 query pack contains four required paraphrase cases.
- CS-12: Each required case excludes its expected anchor text from its query text.
- CS-13: Each required case selects an expected authoritative node at rank three or better.
- CS-14: Each required case creates a `ContextManifest` with its required original-text anchor.
- CS-15: The runner returns `semantic_profile_unavailable` when the profile is absent.
- CS-16: The scenario runner rebuilds the semantic manifest through a public product command.
- CS-17: The rebuild check compares vector digests, selected node IDs, hit order, and context.

## Proposed Architecture

The Application Layer owns semantic rendering, profile validation, and query selection.
The embedding Adapters translate local runtime protocols into `EmbeddingPort` results.
The SQLite Adapter owns derived vector storage and cosine ranking.
The existing ContextPlanner owns structural context selection and packing.

```text
DocumentRepresentationBundle
        |
        v
DocumentRetrievalUnit --> Semantic renderer --> EmbeddingPort
                                                   |
                                                   v
                                      SQLite semantic index
                                                   |
Semantic query --> Application Layer --> RetrievalHit
                                            |
                                            v
                                      ContextPlanner
                                            |
                                            v
                                      ContextManifest
```

## Key Interactions

```text
operator -> Pipeline: build document index with semantic channel and profile
Pipeline -> Application Layer: build semantic manifest
Application Layer -> EmbeddingPort: embed rendered document strings
EmbeddingPort -> SQLite Adapter: vectors and semantic manifest
SQLite Adapter -> Application Layer: published semantic manifest

operator -> Pipeline: query with semantic channel and profile
Pipeline -> Application Layer: semantic query
Application Layer -> EmbeddingPort: embed rendered query string
Application Layer -> SQLite Adapter: cosine candidates
Application Layer -> ContextPlanner: selected authoritative node IDs
ContextPlanner -> Pipeline: ContextManifest
```

## Data Model

`RetrievalChannel` adds `semantic`.
`RetrievalIndexManifest` accepts a semantic-only manifest with one `EmbeddingModelIdentity`.
`DocumentSemanticRepresentation` records one unit, a source fingerprint, and renderer input digests.
`DocumentSemanticRepresentation` does not contain a rendered string or vector.
`EmbeddingProfile` is local Pipeline configuration and is not a Ledger record.
`EmbeddingProfile` contains profile ID, Adapter ID, endpoint, model ID, and model path.
`EmbeddingProfile` contains the model digest.
`EmbeddingProfile` contains the expected vector dimension.
`EmbeddingProfile` contains a maximum normalized rendered-character count.
`RetrievalQueryRecord` preserves native similarity scores.
`RetrievalQueryRecord` does not treat similarity scores as evidence confidence.

## APIs / Interfaces

The Pipeline adds `--channel semantic` to document-index build and retrieval query commands.
The Pipeline requires `--embedding-profile <profile-id>` with the semantic channel.
The Pipeline leaves channel selection absent for the existing DR-1 exact-and-lexical behavior.

`EmbeddingPort` accepts one ordered batch of rendered strings and an `EmbeddingProfile`.
`EmbeddingPort` returns vectors in input order and one `EmbeddingModelIdentity`.
The Application Layer rejects an output count that differs from the input count.

The scenario runner accepts `--embedding-profile semantic-validation-v1` for `dr-2-v1`.
The scenario runner rejects another profile for that canonical suite.

## Behavior & Domain Rules

The Application Layer uses one separate semantic manifest per representation and embedding profile.
The Application Layer rejects a semantic query without a complete compatible semantic manifest.
The Application Layer does not build a semantic manifest during an exact-and-lexical query.
The Application Layer records model identity and vector digest before it publishes the manifest.
The SQLite Adapter deletes only semantic derived rows during a semantic rebuild.
The rebuild retains Archive bytes and Ledger records.
The rebuild retains accepted representations and `DocumentNode` records.
The Application Layer preserves the native cosine score in each semantic channel observation.
The Application Layer does not use semantic scores as evidence or world-truth confidence.

The DR-2 query pack contains these required cases.

| Query ID | Query text | Required anchor |
| --- | --- | --- |
| `dr2-risk` | Why did the Department of Defense consider Anthropic a risk? | `supply chain risk` |
| `dr2-investor` | Why did a Trump-linked venture firm withdraw its investment? | `1789 Capital` |
| `dr2-court` | What court order stopped the government? | `preliminary injunction` |
| `dr2-condition` | What military-use condition did Anthropic reject? | `all lawful purposes` |

## Acceptance Criteria

- AC-SR-01: Domain tests prove renderer bytes and representation identity from one pinned unit.
- AC-SR-02: Domain tests prove no semantic representation retains rendered text or vectors.
- AC-SR-03: Application tests prove oversized rendered input returns `semantic_input_too_large`.
- AC-EA-01: Fake-Port tests prove ordered vectors and model identity through build and query.
- AC-EA-02: Adapter tests prove LM Studio, llama-server, and Ollama response validation failures.
- AC-EA-03: Adapter tests prove non-finite, zero, mismatched, and unordered vectors fail explicitly.
- AC-SI-01: SQLite tests prove atomic publication, query invisibility, and corruption rejection.
- AC-SI-02: SQLite tests prove cosine order and deterministic tie order.
- AC-SI-03: SQLite tests prove semantic deletion leaves authoritative stores unchanged.
- AC-QC-01: Pipeline tests prove `--channel semantic` requires an explicit profile.
- AC-QC-02: Pipeline tests prove no channel preserves DR-1 exact-and-lexical behavior.
- AC-QC-03: Application tests prove semantic hits resolve to node IDs and invoke ContextPlanner.
- AC-QC-04: Context tests prove rendered semantic strings and vectors never enter a ContextManifest.
- AC-CS-01: Schema tests prove v1 scenario assets remain valid and immutable.
- AC-CS-02: Schema tests prove v2 semantic cases require semantic channel and paraphrase query kind.
- AC-CS-03: Canonical `dr-2-v1` passes each required paraphrase at rank three or better.
- AC-CS-04: Canonical rebuild checks prove equivalent vectors, hit order, nodes, and context.
- AC-CS-05: The receipt records profile, model identity, manifest, and query records.
- AC-CS-06: The receipt records every resulting ContextManifest.
- AC-CS-07: Formatting, lint, type, repository tests, and Harness receipts pass.
- AC-CS-08: Receipt-chain checks pass.

## Reference Implementations

- Retrieval contracts: `packages/application/src/kotekomi_application/document_retrieval.py`.
- SQLite derived index: `packages/adapters/src/kotekomi_adapters/sqlite_document_retrieval.py`.
- Local runtime HTTP validation: `packages/adapters/src/kotekomi_adapters/model_http.py`.
- LM Studio embeddings: `https://lmstudio.ai/docs/developer/openai-compat/embeddings`.
- Context handoff: `packages/application/src/kotekomi_application/context_planning.py`.
- Canonical scenario runner: `packages/devtools/src/kotekomi_devtools/retrieval_scenarios.py`.

## Constraints and Halt Conditions

DR-2 does not add contextual generation, reranking, or hybrid fusion.
DR-2 does not add Ledger retrieval, graph retrieval, or answer generation.
DR-2 does not send requests to `qwen3.8-27b-mlx-textonly`.
DR-2 stops if the reference profile cannot return one valid vector for each canonical input.
DR-2 stops if semantic retrieval requires ContextPlanner to consume derived text or vectors.
DR-3 owns default hybrid activation after DR-2 records semantic query evidence.
