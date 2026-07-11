# TDD: Derived Document Retrieval

- **Status:** Accepted
- **Parent:** [Authoritative Document Ingestion Program](2026-07-11-authoritative-document-ingestion-program.md)
- **Depends on:** document representations, context planning, and analysis coverage

## 1. Context and problem

KoteKomi needs exact lookup, context discovery, and corpus navigation across large documents. A vector database alone is weak for names, identifiers, quoted phrases, dates, and acronyms, while generated summaries can hallucinate. Retrieval must be rebuildable, version-pinned, inspectable, and incapable of becoming authoritative evidence by accident.

## 2. Goals

- Provide mandatory lexical and exact retrieval over original representation nodes.
- Add optional embeddings, reranking, hierarchical summaries, and graph-assisted navigation as derived channels.
- Contextualize retrieval units without altering their source text.
- Preserve query, candidate, score, rank, index version, and selection history.
- Return original source nodes for evidence and model context.
- Detect stale indexes and rebuild them deterministically from authoritative artifacts.
- Measure retrieval quality against a gold query set.

## 3. Non-goals and forbidden approaches

This TDD does not make retrieval scores evidence or source-confidence measures.

Forbidden:

- using embeddings as the only retrieval path;
- indexing generated summaries as if they were source text;
- citing an embedding vector, community report, or contextual prefix as evidence;
- querying a mutable unversioned “latest” index during replay;
- hiding candidate scores or reranker decisions;
- accepting stale hits from superseded representations without explicit historical scope;
- storing source/evidence truth only inside an index.

## 4. Requirements

1. Lexical full-text search is available over original node text and selected metadata.
2. Exact lookup supports IDs, exact quotes, provider identifiers, names, acronyms, dates, and numeric strings.
3. Retrieval units reference representation/node IDs and do not duplicate authoritative source identity.
4. A contextualized retrieval view keeps original text and prefix/context fields separate.
5. Deterministic prefixes may include title, section path, publication metadata, table caption/headers, and explicit definitions.
6. Optional model-generated contextualization is labeled generated, versioned, and cannot serve as evidence.
7. Embedding indexes record model/digest, preprocessing, dimension, distance metric, source representation set, and build digest.
8. Rerankers and graph-assisted retrieval record model/policy version and complete candidate inputs.
9. Every query can produce a `RetrievalQueryRecord` with all candidates, methods, scores, ranks, and selected hits.
10. A hit is rejected or explicitly historical when its source representation is outside the query's pinned snapshot.
11. Index deletion and rebuild preserve authoritative state and produce equivalent exact/lexical results under pinned software.
12. Hierarchical summaries or communities navigate to original nodes and are never returned as final evidence targets.

## 5. Invariants

- Every retrieval hit resolves to an existing original representation node or an explicitly labeled generated navigation artifact.
- Original source text and contextual prefix are independently addressable.
- A query record identifies exact index manifests and policy versions.
- Index manifests commit to source snapshot, preprocessing, software, configuration, and output digest.
- Exact quoted-string lookup cannot be displaced by semantic similarity when an exact match exists.
- A generated artifact cannot satisfy evidence validation.
- Rebuilding an index never writes accepted ledger records.
- Deleted indexes are recoverable from archived/ledger inputs alone.

## 6. Proposed architecture

```text
Authoritative representations / accepted graph
              │
              ▼
RetrievalBuildUseCase
  ├── Exact/metadata index
  ├── Lexical FTS index
  ├── Optional embedding index
  ├── Optional summary/community store
  └── RetrievalIndexManifest
              │
              ▼
HybridRetrievalUseCase
  ├── candidate generation by channel
  ├── deterministic fusion/policy
  ├── optional pinned reranker
  └── RetrievalQueryRecord
```

SQLite FTS5 is a suitable initial lexical implementation; the domain contract remains backend-neutral.

## 7. Data model and interfaces

```yaml
RetrievalIndexManifest:
  index_manifest_id:
  index_type: exact | lexical | embedding | hierarchical | graph
  source_snapshot_id:
  representation_ids:
  accepted_graph_snapshot_id:
  software_identity:
  preprocessing_policy_id:
  model_identity:
  configuration_digest:
  output_digest:
  built_at:

RetrievalUnit:
  retrieval_unit_id:
  representation_id:
  node_ids:
  original_text_digest:
  deterministic_context:
  generated_context_artifact_id:

RetrievalQueryRecord:
  retrieval_query_id:
  query_text:
  query_filters:
  query_snapshot_id:
  index_manifest_ids:
  fusion_policy_id:
  reranker_id:
  candidates:
  selected_hits:
  created_at:

RetrievalHit:
  retrieval_unit_id:
  node_ids:
  method:
  raw_score:
  normalized_score:
  rank:
  selected:
  selection_reason:
```

Required operations:

```python
build_retrieval_index(command) -> RetrievalIndexManifest
search_documents(query) -> RetrievalResult
resolve_hit_to_nodes(hit_id) -> list[DocumentNode]
verify_index(manifest_id) -> IndexVerificationResult
```

## 8. Retrieval behavior

### Exact and lexical channel

The exact channel handles canonical/provider IDs and literal strings. The lexical channel uses token-aware full-text ranking and fields for title, section, body, table context, and metadata. Index-specific ranking is preserved, not mislabeled as probability.

### Contextualized units

A paragraph's indexed view may prepend its title/section path and explicit definitions. Those fields improve retrieval but the hit resolves to the paragraph and related original nodes. The prefix cannot be quoted as source text.

### Semantic channel

Embeddings add paraphrase recall. Their candidate list is fused under a versioned policy with lexical/exact hits. A changed embedding model or preprocessing creates a new index manifest.

### Hierarchical/global navigation

RAPTOR/GraphRAG-style summaries and communities may answer “where should analysis look?” They nominate original nodes for a subsequent evidence-bearing step. Generated global answers remain derived reports, not accepted assertions.

## 9. Staleness and recovery

- A new representation, accepted graph snapshot, preprocessing policy, or model invalidates affected derived manifests.
- Query execution refuses an invalid manifest unless historical replay explicitly requests it.
- Partial index builds remain unpublished.
- Rebuild compares manifest and deterministic exact/lexical checks before activation.
- Corrupt index files are disposable; source artifacts are never repaired from an index.

## 10. Compatibility and delivery

- Initial delivery requires exact lookup plus SQLite FTS5-style lexical retrieval.
- Embeddings, rerankers, and hierarchical navigation are optional enhancements but must obey the same manifest/query-record contract.
- Existing search callers may receive a compatibility result while new callers use explicit channels and provenance.
- Context planning stores the query record or selected-hit details inside its context manifest.

## 11. Completion gates

### Correctness criteria

- Every returned source hit resolves to valid pinned nodes whose text digest matches the indexed unit.
- Exact unique identifiers and exact unique quotes rank first in the gold query set.
- Stale representation/index combinations are rejected rather than silently queried.
- Deleting every retrieval store and rebuilding preserves exact results and deterministic lexical result order for pinned inputs.
- Generated summaries/prefixes fail evidence-selector validation by construction.
- Query records reconcile every selected hit to its candidate method, scores, rank, and policy.
- Corrupt or partial index builds cannot become active.

### Success criteria

- Gold retrieval achieves Recall@10 of at least 0.95 overall and 1.00 for exact identifiers/quotes.
- Context-planning gold cases recover the required distant source nodes through disclosed deterministic dependencies or recorded retrieval.
- Hybrid retrieval improves or preserves gold recall versus lexical-only without lowering exact-query correctness.
- Operators can reproduce a historical query from its pinned manifests and source snapshot.
- Index rebuild completes without touching archive or accepted ledger records.

### Failure criteria

This deliverable is incomplete if:

- vector similarity is the only search mechanism;
- a hit cannot be mapped back to original source nodes;
- generated summaries or prefixes can be accepted as evidence;
- replay uses whatever index happens to be current;
- stale/corrupt indexes return ordinary successful results;
- only top hits are stored while rejected candidates and selection policy disappear;
- retrieval quality is asserted without a labeled query set and measured thresholds.

## 12. References

- SQLite FTS5: https://www.sqlite.org/fts5.html
- RAPTOR: https://ar5iv.labs.arxiv.org/html/2401.18059
- Microsoft GraphRAG outputs: https://microsoft.github.io/graphrag/index/outputs/

## 13. Halt conditions

Stop and revise when a retrieval channel cannot expose stable source-node identities and complete query provenance, or when evaluation shows semantic fusion harms exact-query correctness.
