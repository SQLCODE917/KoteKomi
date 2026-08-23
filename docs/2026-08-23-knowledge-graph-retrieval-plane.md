# Knowledge-Graph Retrieval Plane

- Status: Accepted

## Context & Problem

### Glossary

**Knowledge-Graph retrieval projection** is a disposable SQLite view of current accepted Ledger records.

**Graph seed** is one current Actor, Entity, Event, Organization, or Place that a user names.

**Graph path** is an ordered sequence of derived graph edges from a Graph seed to an accepted record.

**Graph hit** is an accepted Assertion, Relationship, or Outcome selected through a Graph path.

KoteKomi has a PoC graph command that creates an in-memory NetworkX projection.

The PoC command does not pin a Ledger snapshot or persist graph query provenance.

The PoC graph-mining command creates ProposedChanges through rules that this TDD does not define.

KoteKomi needs graph navigation that returns original source evidence through the existing ContextPlanner.

### Primary flow

1. A user supplies a name phrase such as `Anthropic` or `Department of Defense`.
2. The Pipeline resolves the phrase to one current Graph seed through exact or lexical labels.
3. The Application traverses one or two derived graph edges in either direction.
4. The Application selects accepted Assertion, Relationship, and Outcome records in deterministic order.
5. The Application resolves each selected record through accepted Assertions and terminal EvidenceTargets.
6. The ContextPlanner creates a ContextManifest from the resolved authoritative DocumentNodes.

## Goals

- Users can navigate current accepted knowledge from names without supplying canonical IDs.
- Each Graph hit exposes its derived path and terminal evidence path.
- Each Graph context contains only original authoritative document material.
- Users can delete and rebuild graph retrieval state without losing Ledger knowledge.
- Operators can detect a stale graph projection before it serves a query.

## Requirements

### Domain Core

- KGR-01: RetrievalPlane includes `knowledge_graph`.
- KGR-02: RetrievalChannel includes `graph_traversal`.
- KGR-03: The Domain Core defines graph nodes, evidence-linked graph edges, retrieval units, paths, hits, query records, seed candidates, and index manifests.
- KGR-04: Every graph edge identifies one or more accepted Assertion IDs.
- KGR-05: A Graph hit identifies its selected accepted record, traversal path, terminal EvidenceTarget IDs, and graph traversal observation.

### Application Layer

- KGR-06: The Application builds graph nodes for current Actors, Entities, Events, Organizations, Places, Assertions, Relationships, and Outcomes.
- KGR-07: The Application excludes proposed, superseded, and retracted Assertions from the current graph projection.
- KGR-08: The Application excludes a Relationship or Outcome when any supporting Assertion is outside the current graph projection.
- KGR-09: The Application creates graph edges only from current accepted records and their accepted Assertion support.
- KGR-10: The Application resolves a Graph seed through exact labels before lexical labels.
- KGR-11: The Application returns `knowledge_graph_seed_missing` when no current seed matches.
- KGR-12: The Application returns `knowledge_graph_seed_ambiguous` when more than one seed matches.
- KGR-13: The Application traverses stored edges in both directions and records `forward` or `reverse` for each path edge.
- KGR-14: The Application accepts only one or two hops.
- KGR-15: The Application ranks paths by hop count and canonical edge and node IDs.
- KGR-16: The Application selects only Assertion, Relationship, and Outcome nodes as Graph hits.
- KGR-17: The Application resolves every Graph hit to terminal EvidenceTargets through accepted Assertion support.
- KGR-18: The Application groups authoritative DocumentNode IDs by representation and calls ContextPlanner once per representation.
- KGR-19: The Application records graph seed candidates, paths, hits, contexts, policy, manifest, and typed failures in a query record.

### SQLite Adapter

- KGR-20: The SQLite Adapter publishes graph nodes, edges, units, labels, and one complete manifest atomically.
- KGR-21: The SQLite Adapter exposes only complete manifests.
- KGR-22: The SQLite Adapter stores exact and lexical seed-label rows as derived state.
- KGR-23: The SQLite Adapter stores graph query records in the derived sidecar.
- KGR-24: The Application returns `knowledge_graph_index_stale` when the Ledger snapshot differs from the manifest snapshot.
- KGR-25: Delete and rebuild from identical Ledger state produces equivalent graph query selections.

### Pipeline

- KGR-26: `kotekomi retrieval build-graph` builds the disposable Knowledge-Graph retrieval projection.
- KGR-27: `kotekomi retrieval query-graph` accepts `--seed`, `--maximum-hops`, `--maximum-hits`, and `--context-profile`.
- KGR-28: The query command serializes seed candidates, paths, selected record IDs, terminal evidence IDs, and ContextManifest IDs.
- KGR-29: The Pipeline removes `kotekomi graph project` and `kotekomi graph mine`.

## Proposed Architecture

```text
Current accepted Ledger
        |
        v
Knowledge-Graph retrieval Application
        |
        v
SQLite graph retrieval sidecar
        |
        v
Graph hit -> EvidenceTarget -> DocumentNode
        |
        v
ContextPlanner -> ContextManifest
```

The Ledger owns accepted records and evidence links.

The Application owns current-state policy, path selection, evidence resolution, and ContextPlanner handoff.

The SQLite Adapter owns disposable graph rows and query receipts.

## Key Interactions

```text
User -> Pipeline: retrieval query-graph --seed <name>
Pipeline -> Application: QueryKnowledgeGraphCommand
Application -> SQLite sidecar: resolve seed and load complete graph
Application -> Ledger: resolve accepted Assertion evidence
Application -> ContextPlanner: authoritative focus nodes
ContextPlanner -> Ledger: ContextManifest
Application -> SQLite sidecar: KnowledgeGraphRetrievalQueryRecord
Pipeline -> User: graph paths and context provenance
```

## Data Model

KnowledgeGraphNode and KnowledgeGraphEdge are derived graph topology.

KnowledgeGraphEdge carries accepted Assertion IDs that explain why the edge exists.

KnowledgeGraphRetrievalUnit identifies one selectable accepted record.

KnowledgeGraphTraversalPath records nodes, edge IDs, and each stored-edge direction.

KnowledgeGraphRetrievalHit records a selected record and terminal EvidenceTarget IDs.

KnowledgeGraphRetrievalIndexManifest pins the current Ledger snapshot, policies, adapter identity, counts, and content fingerprint.

KnowledgeGraphRetrievalQueryRecord preserves the seed resolution and traversal result.

## APIs / Interfaces

`kotekomi retrieval build-graph --ledger-path <path>` creates the derived projection.

`kotekomi retrieval query-graph --seed <name phrase> --maximum-hops <1|2>` queries the projection.

The public query accepts a human name phrase and never requires a canonical ID.

The query returns canonical IDs only as audit provenance.

## Behavior & Domain Rules

The first DR-6 policy is `knowledge_graph_current_traversal_v1`.

The policy contains current accepted state only.

The graph stores no source evidence text as navigation authority.

The graph stores no embeddings, aggregate weights, generated communities, or generated reports.

The ContextManifest contains no graph labels, path text, or index rows as source evidence.

The implementation removes the PoC NetworkX graph projection and graph-mining workflow.

The next graph slice implements evidence-weighted graph projections from `2026-07-11-evidence-weighted-graph-projections.md`.

That slice adds historical policy, lineage handling, quality dimensions, and score semantics before DR-7 cross-plane orchestration.

## Acceptance Criteria

- AC-KGR-01: Domain tests prove graph record validation and edge Assertion support.
- AC-KGR-02: Application tests prove current-state filtering, exact and lexical seed resolution, ambiguity, bidirectional paths, deterministic rank, and evidence resolution.
- AC-KGR-03: Adapter tests prove atomic publication, complete-manifest reads, stale rejection, query-record persistence, and delete-and-rebuild equivalence.
- AC-KGR-04: Pipeline tests prove public graph commands and removal of PoC graph commands.
- AC-KGR-05: The canonical scenario ingests the locked Anthropic PDF, seeds accepted DR-5 records, resolves `Anthropic` and `Department of Defense`, and creates ready ContextManifests with `Directive 3000.09` source evidence.
- AC-KGR-06: The canonical scenario proves identical Graph selections after sidecar deletion and rebuild.

## Reference Implementations

- Ledger retrieval contracts: `packages/application/src/kotekomi_application/ledger_retrieval.py`.
- SQLite derived index publication: `packages/adapters/src/kotekomi_adapters/sqlite_ledger_retrieval.py`.
- ContextPlanner handoff: `packages/application/src/kotekomi_application/context_planning.py`.

## Constraints and Halt Conditions

Stop if a Graph hit cannot resolve through accepted Assertions to terminal EvidenceTargets.

Stop if graph traversal must place derived graph text into a ContextManifest.

Stop if a score, weight, temporal history, or lineage rule is required before deterministic current traversal works.
