# Derived Projection Readiness

- Status: Accepted

## Context & Problem

### Glossary

**Projection readiness** means that a public retrieval query has a complete derived projection for its authoritative snapshot.

**Required projection** is the derived projection that one retrieval query needs before it reads candidates.

**Projection manifest** identifies one complete derived projection and its authoritative snapshot.

KoteKomi requires users to build document, Ledger, Knowledge-Graph, and evidence-graph projections before querying them.

Those projections are disposable state.

Users should not manage disposable state before they search the local intelligence ledger.

### Primary flow

1. A user changes canonical state through source ingest or review.
2. The canonical state changes the authoritative snapshot for affected projections.
3. A user runs an existing public retrieval query.
4. The Application builds or reuses each Required Projection for the query snapshot.
5. The Application executes the query against the resulting complete Projection Manifest.
6. The Pipeline returns the query result and the manifest identities.

## Goals

- Users run public retrieval queries without prior projection-build commands.
- Each query uses complete derived state for its authoritative snapshot.
- Canonical writes remain independent of derived projection availability.
- Users can delete derived sidecars and receive equivalent query behavior after the next query.

## Requirements

### Application Layer

- DPR-01: Each document exact-lexical query builds or reuses its document exact-lexical projection before candidate selection.
- DPR-02: Each document semantic query builds or reuses its document semantic projection before candidate selection.
- DPR-03: Each document hybrid query builds or reuses its document exact-lexical and semantic projections before candidate selection.
- DPR-04: Each Ledger query builds or reuses its Ledger projection before candidate selection.
- DPR-05: Each Knowledge-Graph query builds or reuses its Knowledge-Graph projection before seed resolution.
- DPR-06: Each evidence-graph explanation builds or reuses its current or review-time projection before edge resolution.
- DPR-07: The Application validates the manifest snapshot after readiness and before candidate selection.
- DPR-08: The Application returns the existing typed build or query failure when readiness cannot create a complete projection.

### Pipeline

- DPR-09: Existing public retrieval query commands require no new build flag.
- DPR-10: Existing public build commands remain available for deterministic diagnostics and rebuild checks.
- DPR-11: Query output includes the complete Projection Manifest identity or identities that the query used.

## Proposed Architecture

```text
Canonical Ledger or Archive
            |
            v
     Public retrieval query
            |
            v
 Application readiness step
            |
            v
 Complete derived projection
            |
            v
 Candidate selection and ContextPlanner
```

The Ledger and Archive own canonical state.

The Application owns projection readiness and snapshot validation.

SQLite Adapters own atomic derived projection publication.

The Pipeline composes existing public query use cases.

## Key Interactions

```text
User -> Pipeline: retrieval query
Pipeline -> Application: query command
Application -> SQLite sidecar: publish or reuse complete projection
Application -> Ledger: validate current snapshot
Application -> SQLite sidecar: read candidates
Application -> ContextPlanner: authoritative focus nodes
Pipeline -> User: result and manifest identities
```

## Data Model

This TDD adds no canonical record.

Existing Projection Manifests remain the readiness record for their derived stores.

Existing query records retain the manifest identities that each query used.

## APIs / Interfaces

`kotekomi retrieval query` prepares its required document projection before querying.

`kotekomi retrieval query-ledger` prepares its required Ledger projection before querying.

`kotekomi retrieval query-graph` prepares its required Knowledge-Graph projection before querying.

`kotekomi retrieval explain-graph-relationship` prepares its required evidence-graph projection before explaining.

## Behavior & Domain Rules

A canonical write does not build or wait for a derived projection.

A changed authoritative snapshot makes an older Projection Manifest unsuitable for a later query.

The next query builds a new complete projection from the current authoritative snapshot.

The Application does not serve candidate rows from a missing, incomplete, corrupt, or stale projection.

The Application preserves semantic embedding profile validation and embedding Adapter failures.

The Application stores no projection readiness state in the Ledger.

## Acceptance Criteria

- AC-DPR-01: Application tests prove each query reuses a current complete projection.
- AC-DPR-02: Application tests prove each query replaces a missing or stale projection before candidate selection.
- AC-DPR-03: Application tests prove semantic and hybrid readiness retain typed embedding failures.
- AC-DPR-04: Adapter tests prove readiness uses complete manifests and preserves rebuild equivalence.
- AC-DPR-05: Pipeline tests prove public query commands succeed without prior build commands.
- AC-DPR-06: The canonical verifier ingests the locked PDF, seeds accepted Ledger state, and runs document, Ledger, Knowledge-Graph, and evidence-graph queries without manual projection builds.
- AC-DPR-07: The canonical verifier deletes each derived sidecar and proves the next public query recreates equivalent selections and authoritative context.

## Reference Implementations

- Document projection build: `packages/application/src/kotekomi_application/document_retrieval.py`.
- Ledger projection build: `packages/application/src/kotekomi_application/ledger_retrieval.py`.
- Knowledge-Graph projection build: `packages/application/src/kotekomi_application/knowledge_graph_retrieval.py`.
- Evidence-graph projection build: `packages/application/src/kotekomi_application/evidence_graph_projection.py`.

## Constraints and Halt Conditions

Stop if readiness requires a canonical write to store derived state.

Stop if source ingest or review waits for a derived index, an embedding Adapter, or a ContextPlanner operation.

Stop if readiness serves candidate rows without a complete Projection Manifest for the current snapshot.
