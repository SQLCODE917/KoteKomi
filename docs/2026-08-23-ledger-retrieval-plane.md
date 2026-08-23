# Ledger Retrieval Plane

## Context & Problem

### Glossary

**Ledger Retrieval Unit**
A derived description of one searchable accepted Assertion, Relationship, or Outcome.

**Ledger Retrieval Representation**
A deterministic exact and lexical projection of one Ledger Retrieval Unit.

**Ledger Retrieval Hit**
A query-time result that identifies one accepted Ledger record and its terminal evidence path.

**Current policy**
A query policy that excludes superseded and retracted Assertions.

**Audit policy**
A query policy that includes historical Assertions and their Supersession lineage.

KoteKomi has Document retrieval over authoritative DocumentNodes.
KoteKomi does not yet retrieve accepted Ledger state with its evidence path.
Users need current and historical discovery without treating an index row as knowledge or evidence.

### Primary flow

1. A user builds the derived Ledger index from accepted Ledger records.
2. The Application creates Ledger Retrieval Units and Ledger Retrieval Representations.
3. The SQLite Adapter publishes exact, lexical, and structured search rows with a complete index manifest.
4. A user submits a Ledger query with text or canonical filters.
5. The Application returns Ledger Retrieval Hits under a named query policy.
6. The Application resolves each selected hit to terminal EvidenceTargets and authoritative DocumentNodes.
7. The existing ContextPlanner writes one ContextManifest for each source representation.

## Goals

- Users can find accepted Assertions, Relationships, and Outcomes.
- Users can ask for current state, latest current state, and historical state.
- Every returned Ledger result has an inspectable source-evidence path.
- Every returned context contains authoritative document material.
- Users can delete and rebuild the Ledger index without losing knowledge.

## Requirements

### Domain Core

- LRP-01: RetrievalPlane must include `ledger`.
- LRP-02: RetrievalChannel must include `structured_filter`.
- LRP-03: The Domain Core must define Ledger-specific RetrievalUnit, RetrievalRepresentation, RetrievalHit, RetrievalQueryRecord, and RetrievalIndexManifest records.
- LRP-04: A Ledger Retrieval Unit must identify its accepted Ledger record, record type, evidence Assertion IDs, source snapshot digest, and unit fingerprint.
- LRP-05: A Ledger Retrieval Hit must identify its accepted Ledger record, terminal EvidenceTarget IDs, channel observations, rank, selection decision, and selection reason.

### Ledger Retrieval Application

- LRP-06: The Application must index accepted Assertions, Relationships, and Outcomes.
- LRP-07: The Application must use Actor, Organization, Event, Place, and Entity records only as structured lookup values and derived projection text.
- LRP-08: The Application must include all indexed records and referenced lookup values in its source snapshot digest.
- LRP-09: The Application must fail with a typed stale-index result when the current source snapshot differs from the published manifest.
- LRP-10: The Application must use exact retrieval before lexical retrieval for a unique exact result after policy filters.
- LRP-11: The Application must reject a relevance or audit query with neither text nor a canonical filter.
- LRP-12: The Application must reject a filter that does not apply to the requested record type.
- LRP-13: The Application must use `ledger_current_relevance_v1` for current exact and lexical discovery.
- LRP-14: The Application must use `ledger_current_latest_v1` for current results ordered by `updated_at` descending.
- LRP-15: The Application must use `ledger_audit_history_v1` for historical discovery and lineage inspection.
- LRP-16: The Application must resolve every selected record through accepted Assertions to terminal EvidenceTargets.
- LRP-17: The Application must group terminal DocumentNode IDs by representation and call the existing ContextPlanner once per representation.
- LRP-18: The query record must preserve each context result, including `context_budget_blocked`.

### SQLite Adapter

- LRP-19: The Adapter must publish a complete exact, lexical, and structured manifest atomically.
- LRP-20: The Adapter must expose only complete manifests to queries.
- LRP-21: The Adapter must persist all query records in the derived sidecar store.
- LRP-22: The Adapter must produce equivalent query results after index deletion and rebuild from identical Ledger state.

### Pipeline

- LRP-23: `kotekomi retrieval build-ledger` must build the derived Ledger projection.
- LRP-24: `kotekomi retrieval query-ledger` must accept text, `record-id`, record type, Assertion status, subject ID, predicate, policy, maximum hits, and context profile inputs.
- LRP-25: The Pipeline must serialize Ledger query provenance, selected record IDs, terminal EvidenceTarget IDs, and per-representation ContextManifest IDs.

## Proposed Architecture

```text
Accepted Ledger -> Ledger Retrieval Application -> SQLite Ledger Index
      |                     |                         |
      |                     v                         v
      +-> EvidenceTarget -> DocumentNode         Ledger Retrieval Hit
                                |
                                v
                         ContextPlanner -> ContextManifest
```

The Ledger owns accepted Assertions, Relationships, Outcomes, and evidence links.
The Ledger Retrieval Application owns query policy, index freshness, result selection, and evidence resolution.
The SQLite Adapter owns derived index storage.
The ContextPlanner owns source structure expansion and context packing.

## Key Interactions

```text
User -> Pipeline: retrieval query-ledger
Pipeline -> Ledger Retrieval Application: query command
Application -> SQLite Ledger Index: load complete manifest and candidates
Application -> Ledger: load accepted records and evidence references
Application -> ContextPlanner: authoritative nodes grouped by representation
ContextPlanner -> Ledger: ContextManifest
Application -> SQLite Ledger Index: Ledger RetrievalQueryRecord
Pipeline -> User: query results and context provenance
```

## Data Model

The Ledger index contains derived rows only.
Each index manifest pins the complete Ledger source snapshot, unit policy, projection policy, builder version, adapter identity, adapter configuration digest, channels, and content fingerprint.

An Assertion projection contains its subject label, predicate, object label or value, qualifiers, and current assessment.
A Relationship projection contains its subject label, predicate, and object label.
An Outcome projection contains its description and linked Actor, Organization, and Event labels.
These strings remain derived representations.

## APIs / Interfaces

`kotekomi retrieval build-ledger --ledger-path <path>` builds the Ledger index.
`kotekomi retrieval query-ledger --ledger-path <path>` executes a Ledger query.
The query command accepts `--query`, `--record-id`, `--record-type`, `--assertion-status`, `--subject-id`, `--predicate`, `--policy`, `--maximum-hits`, and `--context-profile`.
The relevance and audit policies require `--query` or one canonical filter.
The latest policy accepts no text or filter.
The command accepts Assertion status only with `--record-type assertion`.
The command accepts subject and predicate only with Assertion or Relationship record types.

## Behavior & Domain Rules

The current policies include accepted Assertions except `superseded` and `retracted`.
The audit policy includes every accepted Assertion status.
The audit policy reports the predecessor ID for a successor and the successor ID derived from accepted Assertions for a predecessor.

The Application returns no source text from index rows as evidence.
The Application returns original source material only through ContextManifest records.
The query result remains successful when one ContextPlanner result is blocked.
The query record identifies the blocked representation and reason.
The canonical suite requires ready contexts for every expected representation.

## Acceptance Criteria

- AC-LRP-01: Domain tests prove Ledger retrieval identities and manifest validation.
- AC-LRP-02: Application tests prove current, latest, audit, exact, lexical, structured, and invalid-filter behavior.
- AC-LRP-03: Application tests prove direct, inference, Relationship, and Outcome hits resolve to terminal EvidenceTargets.
- AC-LRP-04: Application tests prove multi-document results create one ContextManifest per representation.
- AC-LRP-05: Adapter tests prove atomic publication, stale-index failure, query-record persistence, and delete-and-rebuild equivalence.
- AC-LRP-06: Pipeline tests prove public command parsing and provenance output.
- AC-LRP-07: The canonical scenario proves exact, lexical, structured, latest, audit, inference, Relationship, and Outcome retrieval against the locked PDF.
- AC-LRP-08: The canonical scenario reports `fixture_missing` when the locked local PDF is absent.

## Reference Implementations

- Document retrieval Application: `packages/application/src/kotekomi_application/document_retrieval.py`.
- Document retrieval SQLite Adapter: `packages/adapters/src/kotekomi_adapters/sqlite_document_retrieval.py`.
- ContextPlanner handoff: `packages/application/src/kotekomi_application/context_planning.py`.
- Canonical DR-4 verifier: `scripts/verify_dr4_canonical.py`.
