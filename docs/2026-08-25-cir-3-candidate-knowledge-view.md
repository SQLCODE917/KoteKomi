# CIR-3: Candidate Knowledge View

- Status: Proposed
- Program: [Candidate Ingestion Review](2026-08-24-candidate-ingestion-review-program.md)
- Deliverable ID: CIR-3
- Depends on: [CIR-2](2026-08-24-automatic-extraction-change-set.md)

## 1. Context & Problem

CIR-2 creates one closed IngestionChangeSet for a completed automatic extraction run.

The Ledger stores the ProposedChanges in that set separately from accepted knowledge.

Existing retrieval and graph builders read accepted Ledger records only.

KoteKomi does not yet provide one read model for accepted knowledge plus a pending change set.

Later review projections need that read model without granting accepted status to ProposedChanges.

### Terms

**PublishedKnowledgeRevision** means the immutable digest of the current accepted canonical records.

**CandidateKnowledgeView** binds one PublishedKnowledgeRevision to one IngestionChangeSet.

**Effective record set** contains accepted records and one view's pending records.

**KnowledgeView** means an Application Layer read model over one effective record set.

**Active CandidateKnowledgeView** means the one CandidateKnowledgeView whose `active` field is true.

### Primary end-to-end flow

1. The Application Layer loads one closed IngestionChangeSet from the Ledger.
2. The Application Layer computes the current PublishedKnowledgeRevision from accepted records.
3. The Application Layer validates every pending ProposedChange in the IngestionChangeSet.
4. The Application Layer writes one CandidateKnowledgeView for a non-empty change set.
5. The Application Layer resolves the CandidateKnowledgeView into a KnowledgeView.
6. Retrieval and graph state builders read the KnowledgeView without accepted Ledger writes.

## 2. Goals

- KoteKomi can represent one pending ingestion as one durable candidate knowledge view.
- KoteKomi can prove which accepted knowledge snapshot each candidate view extends.
- KoteKomi can build deterministic retrieval and graph state from a current candidate view.
- KoteKomi keeps every candidate record pending until a later review decision accepts it.
- KoteKomi identifies a candidate view whose base accepted knowledge changed.

## 3. Requirements

### CandidateKnowledgeView record

- C3-VIEW-01: The Domain Core defines CandidateKnowledgeView as a durable Ledger record.
- C3-VIEW-02: CandidateKnowledgeView stores every field in Section 6.
- C3-VIEW-03: The CandidateKnowledgeView policy ID is `candidate_knowledge_view_v1`.
- C3-VIEW-04: The Application Layer digests all accepted records by record type and record ID.
- C3-VIEW-05: The candidate digest covers the base digest, change-set digest, and policy ID.
- C3-VIEW-06: The CandidateKnowledgeView ID derives from its candidate snapshot digest.
- C3-VIEW-07: The Adapter permits zero or one Active CandidateKnowledgeView.

### Candidate view creation

- C3-CREATE-01: The change set must be closed and belong to its IngestionRun.
- C3-CREATE-02: The use case returns `no_changes` for an empty change set.
- C3-CREATE-03: Each named ProposedChange must exist and remain pending.
- C3-CREATE-04: This deliverable accepts Organization and Assertion ProposedChanges.
- C3-CREATE-05: The Application Layer rejects every other ProposedChange record type.
- C3-CREATE-06: The Application Layer validates each proposed record with its Domain Core model.
- C3-CREATE-07: Each proposed reference must resolve in accepted records or the same change set.
- C3-CREATE-08: A proposed record ID must not duplicate an accepted record ID.
- C3-CREATE-09: An identical active candidate snapshot returns its existing view.
- C3-CREATE-10: A different Active CandidateKnowledgeView blocks creation.
- C3-CREATE-11: Candidate view creation writes no accepted canonical record.

### KnowledgeView resolution

- C3-RESOLVE-01: The Application Layer resolves a current view into its effective record set.
- C3-RESOLVE-02: KnowledgeView exposes its digest and each effective record by record ID.
- C3-RESOLVE-03: The KnowledgeView retains `proposed` status on each candidate Assertion.
- C3-RESOLVE-04: The use case returns `stale` when the base revision digest changed.
- C3-RESOLVE-05: A stale CandidateKnowledgeView produces no KnowledgeView.

### Derived state builders

- C3-DERIVED-01: The ledger retrieval unit builder accepts a KnowledgeView.
- C3-DERIVED-02: The knowledge graph state builder accepts a KnowledgeView.
- C3-DERIVED-03: A published KnowledgeView preserves current published retrieval and graph behavior.
- C3-DERIVED-04: Candidate ledger retrieval units include pending candidate Assertions.
- C3-DERIVED-05: Candidate graph state includes pending Organizations and Assertions.
- C3-DERIVED-06: Each candidate retrieval unit and graph unit records the candidate snapshot digest.
- C3-DERIVED-07: CIR-3 builds state only and writes no retrieval or graph sidecar index.

## 4. Proposed Architecture

```text
SQLite Ledger
    |
    v
Candidate view use case
    |
    v
CandidateKnowledgeView
    |
    v
KnowledgeView
    |             |
    v             v
Ledger state   Graph state
builder        builder
```

The Domain Core validates CandidateKnowledgeView shape.

The Application Layer creates and resolves CandidateKnowledgeView records.

The SQLite Adapter persists CandidateKnowledgeView records and enforces the active-view rule.

The retrieval and graph builders consume KnowledgeView records.

The Pipeline retains the current CIR-2 ingest behavior.

## 5. Key Interactions

```text
Application -> Ledger: load IngestionRun and IngestionChangeSet
Application -> Ledger: load accepted records and ProposedChanges
Application -> Domain Core: validate proposed Organization and Assertion records
Application -> Ledger: save CandidateKnowledgeView
Application -> KnowledgeView: resolve effective record set
Ledger state builder -> KnowledgeView: build retrieval units
Graph state builder -> KnowledgeView: build graph units and nodes
```

## 6. Data Model

CandidateKnowledgeView is a new Domain Core record.

```text
CandidateKnowledgeView
    id
    ingestion_run_id
    ingestion_change_set_id
    base_revision_digest
    candidate_snapshot_digest
    policy_id
    active
    created_at
```

PublishedKnowledgeRevision is an Application Layer value derived from accepted canonical records.

The Ledger does not persist a second copy of published records for CIR-3.

KnowledgeView is an Application Layer read model.

KnowledgeView contains the effective record set and its candidate snapshot digest.

The effective record set contains accepted records, pending Organizations, and pending Assertions.

The SQLite Ledger adds one CandidateKnowledgeView table and one active-view uniqueness constraint.

## 7. APIs / Interfaces

The Application Layer adds a candidate view creation use case.

The use case accepts an IngestionRun ID.

The use case returns `created`, `existing`, `no_changes`, or an explicit error.

The Application Layer adds a candidate view resolution use case.

The use case returns `current` with a KnowledgeView or `stale` without a KnowledgeView.

The Ledger Port saves and loads CandidateKnowledgeView records.

The Ledger Port loads the Active CandidateKnowledgeView.

KnowledgeView exposes the effective record set, record lookup, digest, and view kind.

The User CLI adds no command in CIR-3.

The existing `kotekomi ingest` command remains at `[CAPTURED]` after CIR-2 completes.

## 8. Behavior & Domain Rules

The Application Layer creates a CandidateKnowledgeView after CIR-2 closes an IngestionChangeSet.

The Application Layer does not create a CandidateKnowledgeView for an empty change set.

The Application Layer reconstructs the effective record set on every resolution.

The Application Layer treats a proposed Organization as a candidate entity record.

The Application Layer treats a proposed Assertion as a candidate knowledge record.

The Assertion subject and entity object must resolve in the effective record set.

The Assertion Source and EvidenceTarget references must resolve in accepted records.

The Application Layer retains a stale CandidateKnowledgeView for audit.

The Application Layer produces no derived candidate state from a stale view.

Later CIR deliverables define view retirement, decisions, indexes, and User CLI commands.

## 9. Acceptance Criteria

- AC-C3-01: Domain tests prove CandidateKnowledgeView validates its required fields.
- AC-C3-02: Application tests prove deterministic base and candidate snapshot digests.
- AC-C3-03: Application tests prove one non-empty closed change set creates a current KnowledgeView.
- AC-C3-04: Application tests prove an empty change set returns `no_changes` without persistence.
- AC-C3-05: Application tests prove invalid proposal inputs fail without persistence.
- AC-C3-06: Application tests prove candidate Assertion references resolve in the view.
- AC-C3-07: Application tests prove a different active candidate view blocks creation.
- AC-C3-08: Application tests prove a changed accepted snapshot returns `stale`.
- AC-C3-09: Retrieval tests prove candidate units contain pending Assertions and the view digest.
- AC-C3-10: Graph tests prove candidate state contains pending Organizations and Assertions.
- AC-C3-11: SQLite tests prove restart-safe view persistence and active-view enforcement.
- AC-C3-12: Pipeline tests prove the existing user ingest result remains `[CAPTURED]`.
- AC-C3-13: Full formatting, lint, type, Domain, Application, Adapter, and Pipeline checks pass.

## 10. Reference Implementations

- Change-set closure: `packages/application/src/kotekomi_application/ingestion_change_sets.py`.
- Ingestion lifecycle: `packages/application/src/kotekomi_application/ingestion_runs.py`.
- Proposed record review: `packages/application/src/kotekomi_application/proposed_change_review.py`.
- Ledger retrieval state: `packages/application/src/kotekomi_application/ledger_retrieval.py`.
- Graph state: `packages/application/src/kotekomi_application/knowledge_graph_retrieval.py`.
- SQLite ingestion records: `packages/adapters/src/kotekomi_adapters/sqlite_ledger.py`.

## 11. Constraints and Halt Conditions

This deliverable permits Organization and Assertion ProposedChanges only.

Stop if candidate construction requires a new ProposedChange record type.

Stop if candidate construction requires a User CLI review command.

Stop if candidate state requires a retrieval or graph sidecar write.

Stop if candidate construction requires an accepted Ledger write.

The next CIR TDD must define each stopped scope before implementation.
