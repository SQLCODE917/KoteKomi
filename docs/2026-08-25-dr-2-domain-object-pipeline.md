# DR-2 Domain Object Pipeline

- Status: Reference note
- Program: `derived-retrieval`
- Describes: implemented DR-2 semantic document retrieval
- Contract source: `docs/2026-08-21-context-enriched-document-semantic-retrieval.md`
- Historical successor: `docs/2026-08-21-dr2-semantic-retrieval-calibration.md`

## Purpose

This note names the records and transformations that DR-2 adds to the DR-1 document plane.
This note does not change the accepted DR-2 contract or its preserved historical binding.

DR-2 adds a semantic channel beside DR-1 exact and lexical channels.
DR-2 does not create a second source-evidence path.
DR-2 does not make an embedding, a vector, or rendered embedding text authoritative.

## Authority Chain

```text
Archive PDF bytes
    -> Source and Document
    -> accepted DocumentRepresentationBundle
    -> authoritative DocumentNode
    -> DocumentRetrievalUnit
    -> DocumentSemanticRepresentation
    -> rendered embedding input and SemanticVectorRecord
    -> semantic RetrievalIndexManifest and SQLite vector row
    -> semantic RetrievalHit
    -> authoritative DocumentNode IDs
    -> AnalysisUnit
    -> ContextManifest with original authoritative text
```

The `DocumentRepresentationBundle` and its `DocumentNode` records remain the authority chain.
The semantic route leaves that chain at the rendered embedding input.
The route returns to the authority chain only through the `DocumentRetrievalUnit` references.

## DR-1 Inputs

DR-2 consumes the following existing DR-1 objects.

| Input | Owner | DR-2 use |
| --- | --- | --- |
| `Source` | Domain Core | Identifies the captured external source behind the archived PDF. |
| `Document` | Domain Core | Identifies the local archived document for that source. |
| `DocumentRepresentationBundle` | Domain Core | Supplies one accepted, pinned document representation and source snapshot. |
| `DocumentRepresentation` | Inside the bundle | Binds the bundle to `representation_id`, `document_id`, and the archived input digest. |
| Logical `TextView` | Inside the bundle | Supplies the original text addressed by each eligible node. |
| `DocumentNode` | Inside the bundle | Supplies the authoritative focal node, parent chain, structural role, section path, source order, and page references. |
| `DocumentRetrievalUnit` | Domain Core | Defines the one searchable focal node that a semantic result can return. |
| `AnalysisUnit` and `ContextManifest` | Application Layer | Receive selected authoritative node IDs and construct model context. |

DR-2 receives the accepted `DocumentRepresentationBundle` by explicit `representation_id`.
The Application Layer reloads the bundle and verifies its representation digest before it builds or queries a semantic index.
The Application Layer rebuilds `DocumentRetrievalUnit` records from that bundle with the DR-1 unit policy.

A `DocumentRetrievalUnit` is the direct semantic input record.
It identifies exactly one focal `DocumentNode` through `node_ids`.
It retains the source snapshot, representation ID, parent node ID, ancestor node IDs, structural role, section path, page numbers, source order, and original-text digest.
DR-2 does not use `DocumentExactLexicalRepresentation` as semantic input.
DR-1 exact and lexical representations and DR-2 semantic representations are parallel projections of the same retrieval unit.

```text
accepted DocumentRepresentationBundle
    -> DocumentRetrievalUnit
          -> DocumentExactLexicalRepresentation  [DR-1]
          -> DocumentSemanticRepresentation       [DR-2]
```

## DR-2 Build Transformations

| Step | Input | Transform owner | Output | Authority status |
| --- | --- | --- | --- | --- |
| 1 | `DocumentRepresentationBundle` | Application Layer | eligible `DocumentRetrievalUnit` records | Derived records that bind to authoritative nodes. |
| 2 | `DocumentRetrievalUnit` and bundle | Semantic renderer | rendered document embedding input | Derived execution state. |
| 3 | rendered document embedding input | Application Layer | `DocumentSemanticRepresentation` | Derived recipe with reproducibility digests. |
| 4 | rendered document embedding input and `EmbeddingProfile` | `EmbeddingPort` | `EmbeddingBatch` with `EmbeddingModelIdentity` and vectors | Derived Adapter result. |
| 5 | returned vector | Application Layer | normalized `SemanticVectorRecord` | Derived execution state with a vector-byte digest. |
| 6 | units, semantic representations, vectors, and model identity | Application Layer and SQLite Adapter | semantic `RetrievalIndexManifest` and SQLite vector rows | Rebuildable derived index state. |

The semantic renderer uses only the retrieval unit and authoritative bundle fields.
The renderer writes a document prefix, source title, full section path, structural role, and focal node text.
The renderer normalizes Unicode to NFC and line endings to LF.
The renderer records the UTF-8 digest of the exact string it sends to `EmbeddingPort`.

`DocumentSemanticRepresentation` is the DR-2 concrete semantic `RetrievalRepresentation`.
It records the retrieval unit ID, source snapshot ID, representation digest, projection policy, builder version, renderer policy, rendered-input digest, and representation fingerprint.
It does not store rendered text or a vector.

`EmbeddingProfile`, `EmbeddingBatch`, and `SemanticVectorRecord` are Application Layer DTOs.
They are not authoritative Domain Core records.
`EmbeddingModelIdentity` is a Domain Core record that pins the Adapter ID, model ID, model digest, vector dimension, and configuration digest.

The semantic `RetrievalIndexManifest` uses exactly `RetrievalChannel.SEMANTIC`.
It records the source snapshot, representation ID and digest, unit policy, semantic projection policy, Adapter identity, Adapter configuration digest, embedding profile, model identity, content fingerprint, and publication state.
The SQLite Adapter publishes the manifest and its vector rows atomically.
The SQLite Adapter hides incomplete manifests from queries.

Deleting semantic rows and their semantic manifest removes only derived state.
The Archive bytes, `Source`, `Document`, accepted bundle, `DocumentNode`, and `DocumentRetrievalUnit` records remain sufficient to rebuild the semantic index.

## DR-2 Query Transformations

```text
query text
    -> normalized query text
    -> rendered semantic query input
    -> query vector
    -> SQLite semantic candidates
    -> RetrievalHit
    -> verified authoritative DocumentNode IDs
    -> AnalysisUnit
    -> ContextManifest
    -> RetrievalQueryRecord
```

| Step | Input | Transform owner | Output | Authority status |
| --- | --- | --- | --- | --- |
| 1 | operator query text and `EmbeddingProfile` | Application Layer | normalized query text and rendered query input | Derived execution state. |
| 2 | rendered query input | `EmbeddingPort` | one query vector and `EmbeddingModelIdentity` | Derived Adapter result. |
| 3 | query vector and complete semantic manifest | SQLite Adapter | ordered semantic candidates | Derived Adapter result. |
| 4 | candidate and rebuilt `DocumentRetrievalUnit` | Application Layer | semantic `RetrievalHit` | Derived query record that carries authoritative references. |
| 5 | `RetrievalHit` and accepted bundle | Application Layer | verified authoritative node IDs | Authority boundary. |
| 6 | selected node IDs | ContextPlanner | `AnalysisUnit` and `ContextManifest` | Existing DR-1 planning path. |
| 7 | query, manifest, hits, selection, and context identities | Application Layer | `RetrievalQueryRecord` | Derived audit record. |

The query renderer normalizes the query and prefixes it with `search_query: `.
The Application Layer validates the query vector against the selected `EmbeddingProfile`.
The SQLite Adapter ranks candidates by descending cosine similarity.
The SQLite Adapter breaks equal scores by source order and then retrieval unit ID.

The Application Layer maps each candidate `retrieval_unit_id` to a rebuilt `DocumentRetrievalUnit`.
The Application Layer creates a `RetrievalHit` with `plane = document` and a `semantic` channel observation.
The observation records the semantic manifest, raw cosine score, and channel rank.
The hit records the retrieval unit ID, authoritative node IDs, original-text digest, final rank, and selection reason.

Cosine similarity measures the selected backend's vector similarity.
It does not measure evidence quality, source authority, or world-truth confidence.

Before ContextPlanner runs, the Application Layer reloads each hit's focal node from the accepted bundle.
The Application Layer verifies that the hit node IDs and original-text digest match the rebuilt retrieval unit.
Rendered embedding text, query vectors, document vectors, and SQLite candidate rows end at this boundary.

`RetrievalSelectionAnalysisUnitInput` carries only the representation ID, selected authoritative focus node IDs, and retrieval policy to ContextPlanner.
ContextPlanner creates the `AnalysisUnit` and remains the only component that creates the `ContextManifest`.
ContextPlanner adds required heading ancestry, definitions, references, footnotes, table context, dependencies, and token-budget decisions.
The `ContextManifest` contains original authoritative text from the accepted bundle.

`RetrievalQueryRecord` audits the original and normalized query, source snapshot, query policy, semantic manifest, profile, model identity, candidates, scores, ranks, selected node IDs, `AnalysisUnit` ID, and `ContextManifest` ID.

## Object Classification

| Object | Created by | Stored as | Can supply evidence text? |
| --- | --- | --- | --- |
| `DocumentRepresentationBundle`, `TextView`, and `DocumentNode` | PDF ingestion | accepted Ledger state | Yes. |
| `DocumentRetrievalUnit` | DR-1 retrieval-unit builder | deterministic derived record | Only by resolving its node IDs back to the bundle. |
| `DocumentExactLexicalRepresentation` | DR-1 projection builder | rebuildable derived index state | No. |
| `DocumentSemanticRepresentation` | DR-2 semantic builder | rebuildable derived index state | No. |
| rendered embedding input | DR-2 semantic renderer | transient execution state | No. |
| `SemanticVectorRecord` and SQLite vector row | DR-2 build path | rebuildable derived index state | No. |
| `RetrievalIndexManifest` | DR-1 or DR-2 index builder | rebuildable derived index state | No. |
| `RetrievalHit` and `RetrievalQueryRecord` | retrieval query | derived audit state | No. |
| `AnalysisUnit` | ContextPlanner | planning state | Names authoritative focus nodes. |
| `ContextManifest` | ContextPlanner | planning state | Yes, through its selected authoritative nodes and rendered original text. |

## Boundary Rule

```text
semantic representation helps find evidence
authoritative DocumentNodes provide evidence
ContextPlanner selects evidence for model context
```

For example, a query about Anthropic's military-use restrictions can semantically match a retrieval unit that contains `all lawful purposes`.
DR-2 returns that unit's authoritative `DocumentNode` ID.
ContextPlanner then decides whether the node, its headings, and its required dependencies fit in the `ContextManifest`.
