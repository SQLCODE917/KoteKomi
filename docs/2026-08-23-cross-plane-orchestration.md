# Cross-Plane Orchestration

- Status: Accepted

## Context & Problem

### Glossary

**Cross-plane query** is one user query that uses the Ledger and Knowledge-Graph retrieval planes in sequence.

**Cross-plane policy** is a versioned rule that fixes the plane order and every retrieval limit.

**Cross-plane transition** records one plane result in a Cross-plane query record.

KoteKomi has working document, Ledger, and Knowledge-Graph retrieval planes.

Each plane records its local query provenance.

KoteKomi does not yet expose one public query that coordinates those planes.

### Primary flow

1. A user enters one free-text query.
2. The Pipeline applies the named Cross-plane policy.
3. The Application runs Ledger discovery with the user query.
4. The Application runs Knowledge-Graph traversal with the user query as the Graph seed.
5. The Application resolves only terminal EvidenceTargets from selected Graph hits to authoritative DocumentNodes.
6. The existing ContextPlanner creates ContextManifests from those DocumentNodes.
7. The Pipeline returns the Cross-plane query record and the ContextManifest identities.

## Goals

- Users can start evidence-led investigation with one free-text query.
- Users receive original source context instead of index or graph text.
- Users can inspect each plane transition and its local provenance.
- The system returns typed results for an unresolved Graph seed.
- The system rebuilds missing or stale derived projections before a query uses them.

## Requirements

### Domain Core

- CPO-01: The Domain Core defines CrossPlaneQueryRecord and CrossPlaneTransition.
- CPO-02: A CrossPlaneQueryRecord stores its query, policy, transitions, selected record IDs, terminal EvidenceTarget IDs, ContextManifest results, and failure code.
- CPO-03: A CrossPlaneTransition stores its phase, retrieval plane, local query record ID, index manifest ID, selected record IDs, terminal EvidenceTarget IDs, and failure code.

### Application Layer

- CPO-04: The Application defines `cross_plane_ledger_graph_evidence_v1` as the initial Cross-plane policy.
- CPO-05: The policy sets the Ledger policy, Graph hop limit, Graph hit limit, and ContextPlanner profile.
- CPO-06: The Application runs Ledger discovery before Graph traversal.
- CPO-07: The Application returns `cross_plane_ledger_empty` when Ledger discovery selects no accepted record.
- CPO-08: The Application uses the user query as the Graph seed.
- CPO-09: The Application maps `knowledge_graph_seed_ambiguous` to `cross_plane_seed_ambiguous`.
- CPO-10: The Application maps a missing Graph seed to `cross_plane_seed_missing`.
- CPO-11: The Application selects terminal EvidenceTargets only from selected Graph hits.
- CPO-12: The Application returns `cross_plane_evidence_missing` when selected Graph hits have no terminal EvidenceTargets.
- CPO-13: The Application returns Graph ContextPlanner results as the final context results.
- CPO-14: The Application records every completed or blocked transition in one CrossPlaneQueryRecord.

### SQLite Adapter

- CPO-15: The SQLite Knowledge-Graph sidecar stores CrossPlaneQueryRecord values as derived query provenance.
- CPO-16: The sidecar can load one CrossPlaneQueryRecord by its deterministic ID.

### Pipeline

- CPO-17: `kotekomi retrieval query-cross-plane --query <text>` is the public Cross-plane query command.
- CPO-18: The Pipeline accepts no per-plane limit flags for the initial policy.
- CPO-19: The Pipeline serializes transitions, selected records, terminal EvidenceTargets, and ContextManifest results.

## Proposed Architecture

```text
User
  |
  v
Pipeline
  |
  v
Cross-plane Application
  |              |
  v              v
Ledger query   Graph query
                   |
                   v
      terminal EvidenceTargets
                   |
                   v
           ContextPlanner
                   |
                   v
           ContextManifest
```

The Ledger owns accepted records and EvidenceTargets.

The plane-local Applications own local candidate and traversal policies.

The Cross-plane Application owns policy order, typed outcomes, and transition provenance.

The SQLite Knowledge-Graph sidecar owns disposable CrossPlaneQueryRecord storage.

The ContextPlanner owns final source context construction.

## Key Interactions

```text
User -> Pipeline: query-cross-plane --query <text>
Pipeline -> Cross-plane Application: QueryCrossPlaneCommand
Cross-plane Application -> Ledger query: discover accepted records
Cross-plane Application -> Graph query: resolve seed and traverse
Graph query -> Ledger: resolve terminal EvidenceTargets
Graph query -> ContextPlanner: resolve authoritative DocumentNodes
Cross-plane Application -> SQLite sidecar: save CrossPlaneQueryRecord
Pipeline -> User: transitions and ContextManifest identities
```

## Data Model

CrossPlaneQueryRecord is derived state.

The record does not become Ledger knowledge.

CrossPlaneTransition identifies Ledger discovery, Graph traversal, evidence resolution, or context planning.

The record stores local query record IDs and index manifest IDs instead of copying index rows.

## APIs / Interfaces

`kotekomi retrieval query-cross-plane --query <text>` runs `cross_plane_ledger_graph_evidence_v1`.

The command returns a typed result when the Graph seed is missing or ambiguous.

The command returns canonical IDs only as audit provenance.

## Behavior & Domain Rules

The Cross-plane policy uses `ledger_current_relevance_v1`.

The Cross-plane policy permits two Graph hops and five Graph hits.

The Cross-plane policy uses `retrieval-validation-v1` for ContextPlanner validation.

The Application does not compare Ledger and Graph ranks.

The Application does not create a global score.

The Application does not introduce DocumentNodes that lack selected Graph-hit terminal EvidenceTargets.

The Application does not place graph labels, graph paths, or index text in a ContextManifest.

## Acceptance Criteria

- AC-CPO-01: Domain tests validate CrossPlaneQueryRecord and CrossPlaneTransition shapes.
- AC-CPO-02: Application tests prove the fixed policy order and terminal EvidenceTarget selection.
- AC-CPO-03: Application tests prove `cross_plane_ledger_empty`, `cross_plane_seed_missing`, and `cross_plane_seed_ambiguous`.
- AC-CPO-04: Adapter tests prove CrossPlaneQueryRecord persistence and reload.
- AC-CPO-05: Pipeline tests prove the public command accepts one required query and returns transition provenance.
- AC-CPO-06: The canonical scenario ingests the locked PDF, seeds accepted Ledger records, queries `Anthropic`, and returns source context containing `Directive 3000.09`.
- AC-CPO-07: The canonical scenario deletes derived sidecars and returns equivalent selected record IDs and EvidenceTarget IDs.

## Reference Implementations

- Ledger discovery: `packages/application/src/kotekomi_application/ledger_retrieval.py`.
- Graph traversal: `packages/application/src/kotekomi_application/knowledge_graph_retrieval.py`.
- Sidecar query records: `packages/adapters/src/kotekomi_adapters/sqlite_knowledge_graph_retrieval.py`.
- Public retrieval commands: `packages/pipelines/src/kotekomi_pipelines/cli.py`.

## Constraints and Halt Conditions

Stop when a Cross-plane query needs a global rank across planes.

Stop when a Cross-plane query needs source text from an index row.

Stop when a Cross-plane query needs generated answer text.
