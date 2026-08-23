# TDD: Evidence-Linked Graph Projection MVP

- Status: Accepted
- Parent: [DR-6.1 Evidence-Linked Graph Projections](2026-07-11-evidence-weighted-graph-projections.md)
- Depends on: [Knowledge-Graph Retrieval Plane](2026-08-23-knowledge-graph-retrieval-plane.md)

## Context & Problem

KoteKomi can traverse current accepted Relationships through the Knowledge-Graph retrieval plane.
The traversal result contains Relationship IDs and accepted Assertion IDs.
An analyst cannot yet ask why one Relationship exists and receive its validated original source evidence as a dedicated graph result.

**EvidenceGraphEdge** is a derived semantic edge for one current accepted Relationship.
**EvidenceGraphContribution** is a derived trace from one support Assertion to terminal direct Assertions and validated EvidenceTargets.
**EvidenceGraphProjectionManifest** identifies one complete evidence graph snapshot.
**EvidenceGraphExplanationRecord** records the result of one Relationship explanation request.
**Terminal direct Assertion** is an accepted Assertion that is not an Analytic Inference.

### Primary flow

1. An operator builds an EvidenceGraphProjection from the current accepted Ledger.
2. The Application selects a current Relationship only when every support Assertion is current.
3. The Application traces each support Assertion through Analytic Inference support until it reaches terminal direct Assertions.
4. The Application builds a Contribution only when each terminal direct Assertion has accepted validated evidence.
5. A user supplies a Relationship ID from `kotekomi retrieval query-graph`.
6. The Application loads the matching EvidenceGraphEdge and asks ContextPlanner for context from its EvidenceTarget DocumentNodes.
7. The Pipeline returns the edge, Contributions, ContextManifest IDs, and typed failure values.

## Goals

- A user can inspect the source basis for a current accepted Relationship.
- The explanation contains original source context rather than graph labels or synthetic source text.
- A failed or missing evidence validation blocks a Contribution.
- A stale evidence graph blocks explanation.
- Deleting and rebuilding the sidecar preserves explanation identity and Contribution content for identical inputs.

## Requirements

### Domain Core

- EGM-01: Domain Core defines EvidenceGraphEdge, EvidenceGraphContribution, EvidenceGraphProjectionManifest, and EvidenceGraphExplanationRecord.
- EGM-02: EvidenceGraphEdge identifies one Relationship and one or more unique Contribution IDs.
- EGM-03: EvidenceGraphContribution identifies its Relationship, support Assertion, terminal direct Assertions, validated evidence links, validation attempts, and EvidenceTargets.
- EGM-04: EvidenceGraphProjectionManifest identifies the source snapshot, Projection policy, builder, adapter, configuration digest, counts, content fingerprint, and publication state.
- EGM-05: A successful EvidenceGraphExplanationRecord identifies its edge and Contribution IDs.

### Application Layer

- EGM-06: The Application selects only current accepted Relationships.
- EGM-07: The Application excludes Relationships with proposed, superseded, retracted, or replaced support Assertions.
- EGM-08: The Application resolves Analytic Inference support to terminal direct Assertions.
- EGM-09: The Application accepts a terminal direct Assertion only through an AssertionEvidenceLink whose EvidenceValidationAttempt succeeded for the linked EvidenceTarget.
- EGM-10: The Application returns `evidence_graph_evidence_invalid` when a selected Relationship cannot produce complete validated Contributions.
- EGM-11: The Application stores no Score, independence value, temporal conclusion, or world-truth assessment.
- EGM-12: The Application returns `evidence_graph_projection_stale` when the current Ledger snapshot differs from the manifest snapshot.
- EGM-13: The Application groups EvidenceTarget DocumentNode IDs by representation and calls ContextPlanner once per representation.
- EGM-14: The Application records a typed failed explanation when a valid manifest has no edge for the requested Relationship ID.

### SQLite Adapter

- EGM-15: The SQLite Adapter publishes EvidenceGraphEdges, Contributions, and one complete manifest atomically.
- EGM-16: The SQLite Adapter exposes only complete evidence graph manifests.
- EGM-17: The SQLite Adapter stores ExplanationRecords in the derived graph sidecar.
- EGM-18: The SQLite Adapter deletes only evidence graph rows when an operator requests rebuild.

### Pipeline

- EGM-19: `kotekomi retrieval build-graph-evidence` builds the disposable evidence graph.
- EGM-20: `kotekomi retrieval explain-graph-relationship --relationship-id <id>` returns a Relationship explanation.
- EGM-21: The explain command returns edge, Contributions, ContextPlanner results, Projection manifest ID, policy ID, and typed failure.

## Proposed Architecture

```text
Current accepted Ledger
          |
          v
Evidence graph Application
          |
          v
SQLite graph sidecar
          |
          v
EvidenceTarget DocumentNodes
          |
          v
ContextPlanner -> ContextManifest
```

The Application owns Relationship selection, Assertion tracing, and evidence-validation decisions.
The SQLite Adapter persists derived graph rows and explanation records.
ContextPlanner owns structural source expansion and context packing.

## Key Interactions

```text
Operator -> Pipeline: build-graph-evidence
Pipeline -> Application: build current evidence graph
Application -> Ledger: load accepted Relationships and evidence records
Application -> SQLite sidecar: publish complete projection

User -> Pipeline: explain-graph-relationship <relationship-id>
Pipeline -> Application: load and validate projection
Application -> ContextPlanner: build source context from EvidenceTargets
Application -> SQLite sidecar: save explanation record
Pipeline -> User: edge, Contributions, and ContextManifest IDs
```

## Data Model

EvidenceGraphEdge maps one accepted Relationship to its Contributions.
EvidenceGraphContribution preserves the path from a support Assertion to terminal direct Assertions and validated EvidenceTargets.
EvidenceGraphProjectionManifest pins the complete derived projection to its accepted Ledger snapshot.
EvidenceGraphExplanationRecord preserves the explain result or typed failure.
KnowledgeGraphEdge remains the DR-6 navigation record and does not gain Contribution fields.

## APIs / Interfaces

`kotekomi retrieval build-graph-evidence --ledger-path <path>` builds the evidence graph sidecar rows.
`kotekomi retrieval build-graph-evidence --rebuild --ledger-path <path>` deletes evidence graph rows and rebuilds them.
`kotekomi retrieval explain-graph-relationship --relationship-id <id> --context-profile <id>` returns one explanation.
The caller obtains `<id>` from the existing `kotekomi retrieval query-graph` result.

## Behavior & Domain Rules

The MVP uses the policy ID `evidence_graph_relationship_contributions_v1`.
The MVP uses current accepted Relationship state only.
The MVP treats a replacement Assertion as non-current when a later accepted Assertion names it as superseded.
The MVP preserves support, polarity, necessity, source authority, and exact record IDs without aggregating them.
The MVP fails before publication when selected evidence is missing or validation failed.
The MVP must rebuild an equivalent projection from identical accepted Ledger state.
The MVP must never write projection rows into the Ledger or Archive.

## Acceptance Criteria

- AC-EGM-01: Domain tests prove required evidence graph record fields and validation rules.
- AC-EGM-02: Application tests prove Analytic Inference tracing reaches terminal direct Assertions.
- AC-EGM-03: Application tests prove a failed validation returns `evidence_graph_evidence_invalid`.
- AC-EGM-04: Adapter tests prove atomic publish, complete-manifest reads, evidence-only deletion, and rebuild.
- AC-EGM-05: Pipeline tests prove both public commands route to the Application Layer.
- AC-EGM-06: The canonical scenario ingests the locked Anthropic PDF and seeds accepted Ledger records.
- AC-EGM-07: The canonical scenario obtains `rel_anthropic_policy` through the public DR-6 graph query.
- AC-EGM-08: The canonical scenario explains `rel_anthropic_policy` through `etg_directive` and ready original-source ContextManifest results.
- AC-EGM-09: The canonical scenario deletes and rebuilds the evidence graph sidecar and preserves the selected edge and Contribution IDs.

## Reference Implementations

- Current graph selection: `packages/application/src/kotekomi_application/knowledge_graph_retrieval.py`.
- Context handoff: `packages/application/src/kotekomi_application/context_planning.py`.
- Derived SQLite publication: `packages/adapters/src/kotekomi_adapters/sqlite_knowledge_graph_retrieval.py`.
- Public graph commands: `packages/pipelines/src/kotekomi_pipelines/cli.py`.
- Canonical DR-6 verifier: `scripts/verify_dr6_canonical.py`.

## Constraints and Halt Conditions

Stop if an ExplanationRecord must contain derived graph text as source evidence.
Stop if an implementation requires lineage independence, historical time, or a Score.
Those features belong to later DR-6.1 child TDDs.
