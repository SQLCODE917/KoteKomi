# Derived Retrieval Program

- Status: Accepted
- Program ID: `derived-retrieval`
- Supersedes: the earlier monolithic Derived Document Retrieval TDD at this path
- Prerequisite: `docs/2026-08-13-live-source-walking-skeleton.md`, implemented on `main`
- First child deliverable: `docs/2026-08-20-document-retrieval-mvp.md`

## Context and problem

KoteKomi has an authoritative document-ingestion path. Deposited bytes are archived, a stable Source and Document are recorded, and an acceptable `DocumentRepresentationBundle` is persisted with original text, structure, source regions, and provenance.

Retrieval must now make that durable knowledge easy to find without becoming a second knowledge system. The implementation must remain useful after every increment. It must not require a complete design for embeddings, the Ledger plane, graph retrieval, reranking, and cross-plane orchestration before exact document search works.

This program replaces a single broad retrieval TDD with a stable program envelope and a sequence of independently shippable child TDDs. The program envelope fixes only architectural invariants. Each child TDD owns the smallest new contracts needed for one working vertical slice.

## Program statement

Retrieval structures are disposable search projections over authoritative knowledge.

```text
The vector database is not the knowledge base.

The chunks are not the knowledge base.

The contextual strings are not the knowledge base.

They are search projections over a durable knowledge artifact.
```

The same rule applies to lexical indexes, exact-search tables, generated retrieval questions, reranker features, graph navigation artifacts, scores, and rankings.

## Goals

1. Add retrieval incrementally while keeping a working end-to-end path after every child TDD.
2. Start with exact and lexical document retrieval over an already accepted representation.
3. Formalize `RetrievalUnit` and the missing intermediate contract `RetrievalRepresentation`.
4. Make every transformation from authoritative state to a backend index explicit and reproducible.
5. Support contextual embedding without treating contextualization as evidence.
6. Keep `embedding_text` as reproducible renderer output, never canonical state.
7. Distinguish the Document, Ledger, and Knowledge-Graph retrieval planes.
8. Keep retrieval-plane semantics separate from retrieval-channel mechanics.
9. Integrate retrieval through the existing ContextPlanner architecture.
10. Avoid a parallel RAG subsystem or a second prompt-construction path.
11. Validate every child TDD with the same locked canonical deposited PDF through public commands.
12. Preserve complete query, policy, index, selection, and context provenance.

## Non-goals

This program does not require the following decisions before their child deliverables begin:

- a vector database or embedding model;
- generated contextual sentences or generated retrieval questions;
- a reranker;
- one global fusion formula;
- semantic Ledger retrieval;
- semantic graph navigation;
- generated graph communities or reports;
- learned query planning;
- answer-generation evaluation as the primary retrieval oracle.

Future child TDDs must not be written in full merely because they are named in this program.

## Durable invariants

### Authority

The authoritative stores remain:

- accepted document representations and their archived source bytes;
- accepted Ledger records and their evidence links;
- accepted graph records where the graph is part of canonical knowledge.

Derived retrieval state may be deleted and rebuilt without losing knowledge.

### Explicit projection chain

The normal retrieval chain is:

```text
Authoritative knowledge
    -> RetrievalUnit
    -> RetrievalRepresentation
    -> backend-specific search projection
    -> RetrievalHit
    -> ContextPlanner candidate
    -> ContextManifest
```

No backend row or vector is allowed to bypass the authoritative identities carried by this chain.

### Contextual embedding without contextual evidence

A semantic representation may combine original text with deterministic or generated context to improve matching. A retrieval hit must still resolve to authoritative source nodes or accepted records. Synthetic contextual text is not returned as evidence unless the same text independently exists in authoritative state.

### ContextPlanner ownership

Retrieval answers this question:

> Which authoritative objects are candidates for this query?

ContextPlanner answers this question:

> Given these authoritative focus objects, which original content and structural dependencies fit in the model context?

Retrieval must not duplicate ContextPlanner dependency resolution, token budgeting, packing, or rendering. ContextPlanner remains the only component that produces the final `ContextManifest` supplied to a model.

### No RAG subsystem

The program may add retrieval Application use cases, Ports, Adapters, projections, policies, and query records. It must not introduce a top-level subsystem that owns ingestion, retrieval, context expansion, prompt construction, and model invocation as one opaque RAG service.

### Reproducibility

A retrieval projection must identify:

- the authoritative source snapshot;
- the unit-building policy;
- the representation-building policy;
- the builder version;
- the backend/index configuration;
- all model identities where models participate;
- stable fingerprints or digests of inputs and outputs.

A stale, incomplete, corrupt, or policy-incompatible projection must fail explicitly.

## Core concepts

### Retrieval plane

A retrieval plane is the semantic universe being searched.

```text
DOCUMENT
    Finds source material and evidence-bearing passages.

LEDGER
    Finds accepted concepts, entities, assertions, events, outcomes,
    relationships, and state.

KNOWLEDGE_GRAPH
    Finds paths, neighborhoods, dependencies, and navigation candidates.
```

The planes have different result meanings. Their rank-one results are not interchangeable answers.

### Retrieval channel

A retrieval channel is the mechanism used to discover candidates inside a plane.

Examples:

```text
EXACT
LEXICAL
SEMANTIC
STRUCTURED_FILTER
GRAPH_TRAVERSAL
HIERARCHY
```

Plane and channel are orthogonal:

```text
plane=document, channel=semantic
plane=ledger, channel=semantic
```

These results require different representations and policies even though both channels are called semantic.

### RetrievalUnit

A `RetrievalUnit` is a stable, derived description of what is searchable. It identifies authoritative objects and their structural role. It is not an arbitrary backend chunk and does not contain backend-specific vectors or scores.

The program-level contract is intentionally minimal:

```text
RetrievalUnit
    retrieval_unit_id
    plane
    source_snapshot_id
    authoritative_refs
    evidence_text_digest?
    structural_role
    parent_unit_id?
    unit_policy_id
    unit_fingerprint
```

Child TDDs may define plane-specific record types or payloads. They must not add speculative nullable fields for all future planes.

### RetrievalRepresentation

A `RetrievalRepresentation` is a reproducible derived projection of one `RetrievalUnit` under a named projection policy. It is the stable intermediate contract between semantic units and backend-specific indexes.

```text
RetrievalRepresentation
    retrieval_representation_id
    retrieval_unit_id
    plane
    source_snapshot_id
    source_fingerprint
    projection_policy_id
    projection_builder_version
    representation_fingerprint
    payload
```

`payload` is plane- and channel-specific. For the document exact/lexical MVP it may contain normalized exact-search fields and lexical fields. For semantic retrieval it may contain an embedding recipe and its input digests.

`embedding_text` is deliberately absent from canonical state. A deterministic renderer may materialize exact bytes for an embedding adapter. Those bytes are derived execution state. The renderer identity, source digests, contextualization artifact identities, and output digest are recorded so the bytes can be reproduced and verified.

### RetrievalIndexManifest

A `RetrievalIndexManifest` identifies one complete published projection:

```text
RetrievalIndexManifest
    index_manifest_id
    plane
    channels
    source_snapshot_id
    unit_policy_id
    projection_policy_id
    adapter_identity
    adapter_configuration_digest
    model_identity?
    unit_count
    representation_count
    content_fingerprint
    publication_status
```

An index is invisible to queries until it is complete and published atomically.

### RetrievalHit

A `RetrievalHit` is a query-time observation, not evidence confidence.

```text
RetrievalHit
    retrieval_unit_id
    plane
    channel
    authoritative_refs
    index_manifest_id
    raw_score?
    channel_rank
    fused_rank?
    selected
    selection_reason
```

Raw scores remain in their native channel scales. They are not probabilities and are not treated as confidence in the underlying assertion or evidence.

### RetrievalQueryRecord

A `RetrievalQueryRecord` preserves:

- normalized and original query text;
- source snapshot and representation identity;
- query policy identity;
- all consulted index manifests;
- every considered candidate and channel rank;
- deduplication and fusion decisions;
- selected authoritative references;
- any ContextPlanner analysis unit and resulting `ContextManifest` identity;
- typed failures and exclusions.

Historical records are not silently rewritten when policies change.

## Target flow

```text
                    AUTHORITATIVE KNOWLEDGE

        Document representations
                 |
        Accepted Ledger records
                 |
          Accepted graph
                 |
                 v
        RetrievalUnit builders
                 |
                 v
          RetrievalUnits by plane
                 |
                 v
   RetrievalRepresentation builders
                 |
       +---------+----------+
       |         |          |
       v         v          v
   DOCUMENT    LEDGER     KNOWLEDGE_GRAPH
    plane       plane          plane
       |         |              |
   exact       exact         traversal
   lexical     lexical       hierarchy
   semantic    filters       semantic later
       |         |              |
       +---------+--------------+
                 |
                 v
        plane-local policies
                 |
                 v
       cross-plane orchestration
                 |
                 v
      authoritative focus objects
                 |
                 v
           ContextPlanner
                 |
                 v
           ContextManifest
                 |
                 v
                LLM
```

Fusion happens within a plane before cross-plane orchestration. Cross-plane orchestration is role-aware. It must not place all result types in one undifferentiated global score list.

## ContextPlanner integration

The document-plane query path selects authoritative `DocumentNode` identities. It creates or nominates an `AnalysisUnit` whose `focus_node_ids` are those selected nodes. The existing ContextPlanner then resolves headings, definitions, references, footnotes, table context, dependencies, and token limits.

Retrieval search logic must not be inserted into ContextPlanner's structural candidate expansion. The search-to-focus bridge is a separate Application use case or collaborator.

Ledger and Knowledge-Graph plane results must ultimately nominate accepted authoritative records and, when evidence is required, resolve through evidence links to document nodes before source evidence enters a `ContextManifest`.

## Agile delivery map

Each child deliverable is one vertical, independently shippable, independently revertible TDD. Only one leaf TDD should be active for implementation at a time.

### DR-1 - Document Retrieval MVP

Working result: exact and lexical queries over a pinned acceptable document representation produce authoritative node hits and a `ContextManifest` through the existing ContextPlanner.

Document: `docs/2026-08-20-document-retrieval-mvp.md`

### DR-2 - Context-Enriched Document Semantic Retrieval

Working result: a semantic document channel embeds deterministic contextual representations while returning only original source evidence. The semantic channel is available explicitly but is not yet the default hybrid policy.

Document: `docs/2026-08-21-context-enriched-document-semantic-retrieval.md`

### DR-3 - Document Hybrid Activation

Working result: exact, lexical, and semantic document channels use a deterministic within-plane policy. Exact unique literals retain precedence. This separate activation slice protects the working default while DR-2 is evaluated.

Detailed TDD: write only after DR-2 evidence exists.

### DR-4 - Hierarchical Document Retrieval

Working result: small searchable units expose parent and structural ancestry to ContextPlanner without automatically dumping entire parents into model context.

Document: `docs/2026-08-22-hierarchical-document-retrieval.md`

### DR-5 - Ledger Retrieval Plane

Working result: exact, structured, and lexical discovery over accepted Ledger records can resolve through evidence links to original document nodes. Start without Ledger embeddings.

Document: `docs/2026-08-23-ledger-retrieval-plane.md`

Prerequisite: `docs/2026-08-23-assertion-evidence-basis-and-lineage.md`

### DR-6 - Knowledge-Graph Retrieval Plane

Working result: deterministic graph traversal nominates accepted records and source material. Navigation artifacts remain non-evidentiary. Start without graph embeddings or generated community reports.

Detailed TDD: write only after the Ledger plane and evidence-resolution path are stable.

### DR-7 - Cross-Plane Orchestration

Working result: a versioned query plan sequences Ledger discovery, graph expansion, document evidence retrieval, and ContextPlanner execution without one global score space.

Detailed TDD: write only after all three planes have working baselines.

## Canonical scenario validation

Every child TDD uses the canonical scenario:

```text
scenario_id: anthropic-dod-dispute-v1
local fixture: raw/Anthropic–United_States_Department_of_Defense_dispute.pdf
source URL: https://en.wikipedia.org/wiki/Anthropic%E2%80%93United_States_Department_of_Defense_dispute
```

The PDF remains ignored and untracked. The repository commits its scenario contract, expected anchors, immutable query packs, and cumulative suite definitions under:

```text
.agent/scenarios/anthropic-dod-dispute-v1/
```

The required sequence for every child TDD is:

```text
fixed deposited PDF bytes
    -> public deposited-source ingest
    -> pinned acceptable representation
    -> build projections owned by the active child TDD
    -> public retrieval query
    -> RetrievalQueryRecord
    -> ContextManifest
    -> direct local conformance result
```

The scenario must not fetch or regenerate the live Wikipedia page. The source URL supplies identity and attribution only.

### Fixture lock

The committed scenario carries a locked SHA-256 and page count because the repository does not track the PDF bytes.
A local conformance script must reject a missing fixture, a different digest, or a different page count.
A different fixture requires a new scenario version.
DR-1 through DR-3 scenario commands remain historical validation tools.
New retrieval work uses public `kotekomi` commands and a direct local conformance script.

### Validation tiers

Ordinary CI uses small project-owned fixtures and deterministic unit, contract, and integration tests. The untracked canonical PDF is required for local child-TDD closeout through a direct local conformance script. A missing or mismatched local fixture must produce a typed visible result; it must not be reported as a passing or skipped acceptance run.

### Query-pack progression

DR-1 through DR-3 query packs and suites are immutable historical validation inputs.
An active child TDD that uses the historical scenario runner adds one new immutable query pack.
Its cumulative suite references prior packs without copying or editing them.

```text
DR-1 suite = base-v1 + DR-1-v1
DR-2 suite = base-v1 + DR-1-v1 + DR-2-v1
...
```

A correction creates a new version. Closed packs are not silently modified.

The mandatory oracle is retrieval and context state, not exact LLM prose:

- expected authoritative hits and ranks;
- expected evidence anchors and structural locations;
- complete query records;
- ContextManifest contents and reasons;
- absence of forbidden synthetic evidence;
- projection rebuild equivalence.

A generated answer may be an additional smoke test. It is not the primary acceptance oracle.

## Contract ownership and change control

Each child TDD must state:

- contracts it owns;
- contracts it extends;
- contracts it consumes;
- contracts it supersedes;
- previous query packs it must rerun.

One active TDD owns a contract boundary. A later TDD may extend or explicitly supersede a contract. It must not rewrite historical query records or claim that an old projection used a new policy.

The program envelope changes only when a durable invariant, plane boundary, authority rule, ContextPlanner ownership rule, or target delivery map changes. Implementation details belong in the active leaf TDD.

## Completion and activation

Capability completion and default activation are separate states.

A semantic adapter may be complete and queryable while the default remains exact plus lexical. A later activation slice changes the default only after cumulative evaluation passes. Failed or inconclusive experiments leave the previous working policy intact and their derived state may be deleted.

The retrieval program uses ordinary repository checks and direct local conformance scripts. It does not require Harness task lifecycle or receipt functions.

## Program-level acceptance criteria

The program is complete when all planned child deliverables have been accepted and the following are true:

1. Document, Ledger, and Knowledge-Graph planes have explicit contracts and working baselines.
2. Plane and channel are recorded independently for every hit.
3. Exact unique identifiers and quotations retain deterministic precedence within the document plane.
4. Semantic document retrieval uses reproducible contextual representations without presenting synthetic context as evidence.
5. `embedding_text` can be regenerated from pinned inputs and policy identities and is not canonical state.
6. Hierarchical retrieval exposes structural context to ContextPlanner without bypassing its packing policy.
7. Ledger and graph results preserve their semantic roles and resolve to source evidence where evidence is required.
8. Cross-plane orchestration records every plane transition and does not use one global undifferentiated score.
9. Every selected result resolves to authoritative identities.
10. Deleting every retrieval index loses no knowledge and each projection can be rebuilt from pinned authoritative state.
11. ContextPlanner remains the only final context-construction authority.
12. The canonical scenario passes the active child TDD's direct local conformance check.
13. Historical query behavior remains inspectable through pinned policies, manifests, and records.

## Reference architecture and source files

Child TDDs should use these existing seams rather than creating parallel ones:

- `docs/2026-08-13-live-source-walking-skeleton.md`
- `packages/pipelines/src/kotekomi_pipelines/cli.py`
- `packages/application/src/kotekomi_application/context_planning.py`
- the persisted `DocumentRepresentationBundle` repository Port and Adapter
- the Archive and Ledger authority rules in root `AGENTS.md`
- TDD conventions in `docs/agent/writing-tdds.md`

## Halt conditions

Stop the active child TDD and revise its design if implementation would:

1. treat a retrieval index, vector, chunk, contextual string, score, or generated navigation artifact as canonical knowledge;
2. return synthetic contextualization as source evidence;
3. bypass authoritative node or accepted-record identities;
4. make ContextPlanner subordinate to a new prompt-building or RAG subsystem;
5. combine the three planes in one untyped global score space;
6. require detailed speculative contracts for unimplemented future slices;
7. fetch the live Wikipedia page during canonical-scenario validation;
8. silently accept changed canonical PDF bytes;
9. make the untracked canonical PDF a normal CI dependency;
10. treat a direct local conformance result as a Harness receipt or lifecycle record.
