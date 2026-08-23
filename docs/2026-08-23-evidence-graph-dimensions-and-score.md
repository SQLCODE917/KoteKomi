# TDD: Evidence Graph Dimensions and Score

- Status: Accepted
- Parent: [DR-6.1 Evidence-Linked Graph Projections](2026-07-11-evidence-weighted-graph-projections.md)
- Depends on: [Evidence Graph Temporal Views](2026-08-23-evidence-graph-temporal-views.md)

## Context & Problem

KoteKomi explains a Relationship through accepted Assertions, validated EvidenceTargets, source lineage,
and current or historical review state.
An analyst cannot yet see a policy-defined assessment that exposes contradiction and source-lineage uncertainty.

**Evidence graph dimension** is one derived categorical input for a Relationship in one complete
EvidenceGraphProjectionManifest.
**Evidence graph score** is one derived ordinal assessment for a Relationship under one named policy.
**Contradiction input** is an accepted ArgumentEdge whose relation is `contradicts` and whose target
Assertion supports the selected Relationship.
**Source-lineage input** is the cross-source relation state from the selected Contributions.
**Unknown source lineage** means selected source Documents have no reviewed SourceLineageRelation.

### Primary flow

1. An operator builds a current or as-of evidence graph view.
2. The Application derives a contradiction dimension from accepted ArgumentEdges.
3. The Application derives a source-lineage dimension from the selected Contributions.
4. The Application derives one ordinal Score from the validated-evidence and contradiction dimensions.
5. A user explains a Relationship and receives the Score, Dimensions, Contributions, and source context.

## Goals

- An analyst can see each input to an evidence assessment.
- An analyst can distinguish contested evidence from supported evidence.
- An analyst can see unknown source lineage without an independence claim.
- An explanation retains original source context and exact canonical references.
- An operator can delete and rebuild dimensions and Scores from pinned authoritative state.

## Requirements

### Domain Core

- EGS-01: Domain Core defines `EvidenceGraphDimensionName` with `validated_evidence`, `contradiction`, and `source_lineage`.
- EGS-02: Domain Core defines `EvidenceGraphDimensionValue` with `present`, `absent`, `unknown`, and `recorded_relation`.
- EGS-03: Domain Core defines `EvidenceGraphScoreValue` with `supported` and `contested`.
- EGS-04: EvidenceGraphDimension identifies one projection manifest, Relationship, name, value, policy, and ordered unique input IDs.
- EGS-05: EvidenceGraphScore identifies one projection manifest, Relationship, policy, value, and ordered unique Dimension IDs.
- EGS-06: A Dimension accepts only values defined for its name.
- EGS-07: A Score accepts only Dimensions from its projection manifest and Relationship.

### Application Layer

- EGS-08: The Application derives `validated_evidence = present` only from complete selected Contributions.
- EGS-09: The Application derives `contradiction = present` when an accepted ArgumentEdge with relation `contradicts` targets a selected support Assertion.
- EGS-10: The Application derives `contradiction = absent` when no selected contradiction input exists.
- EGS-11: The Application derives `source_lineage = recorded_relation` only when every selected source-lineage input has a reviewed relation.
- EGS-12: The Application derives `source_lineage = unknown` when any selected source-lineage input has no reviewed relation.
- EGS-13: The Application derives `contested` when the contradiction Dimension is `present`.
- EGS-14: The Application derives `supported` when the validated-evidence Dimension is `present` and the contradiction Dimension is `absent`.
- EGS-15: The Application does not use source-lineage values to derive the Score.
- EGS-16: The Application selects ArgumentEdges from the same current or as-of accepted state as the projection.
- EGS-17: The Application includes Dimension and Score content in the manifest fingerprint.

### SQLite Adapter

- EGS-18: The SQLite graph sidecar publishes Dimensions and Scores atomically with their projection manifest.
- EGS-19: The SQLite graph sidecar reads Dimensions and Scores only from the requested projection manifest.
- EGS-20: The SQLite graph sidecar rejects a complete manifest when stored Dimension or Score counts disagree with the manifest.
- EGS-21: The SQLite graph sidecar removes Dimensions and Scores when it removes their projection manifest.

### Pipeline

- EGS-22: `kotekomi retrieval build-graph-evidence` builds Dimensions and Scores for its selected view.
- EGS-23: `kotekomi retrieval explain-graph-relationship` returns the selected Dimensions and Score.
- EGS-24: The explain command returns Dimension input IDs, Contributions, and ContextPlanner results together.

## Proposed Architecture

```text
Accepted Ledger + Archive
          |
          v
Evidence graph Application
          |
          v
Dimensions and Score
          |
          v
SQLite graph sidecar
          |
          v
Relationship explanation -> ContextPlanner -> ContextManifest
```

The Application owns Dimension and Score policy decisions.
The SQLite Adapter persists only derived manifest-scoped records.
ContextPlanner owns original-source context selection and packing.

## Key Interactions

```text
Operator -> Pipeline: build-graph-evidence [--as-of]
Pipeline -> Application: build selected graph view
Application -> Ledger: load accepted Assertions, ArgumentEdges, and lineage relations
Application -> SQLite sidecar: publish manifest, Contributions, Dimensions, and Scores

User -> Pipeline: explain-graph-relationship [--as-of]
Pipeline -> Application: load selected graph view
Application -> ContextPlanner: build context for Contribution EvidenceTargets
Pipeline -> User: Score, Dimensions, input IDs, Contributions, and ContextManifest IDs
```

## Data Model

EvidenceGraphDimension and EvidenceGraphScore are derived records.
They belong to one EvidenceGraphProjectionManifest and one Relationship.
The manifest records Dimension and Score counts.
EvidenceGraphExplanationRecord identifies selected Dimension and Score IDs.
The Ledger and Archive remain authoritative.

## APIs / Interfaces

The existing `kotekomi retrieval build-graph-evidence` command builds the selected view and its assessment records.
The existing `kotekomi retrieval explain-graph-relationship --relationship-id <id>` command returns its assessment records.
The existing `--as-of <RFC3339-UTC>` option selects the accepted state for Dimensions and Score inputs.

## Behavior & Domain Rules

The policy ID is `evidence_graph_evidence_status_v1`.
The Application evaluates every selected Contribution before it publishes the Score.
The Score does not express world-truth confidence, evidence confidence, or probability.
An accepted contradiction makes the Score `contested` even when validated supporting evidence exists.
Unknown source lineage remains visible in its Dimension when the Score is `supported` or `contested`.
The Application does not infer source independence from unmatched text, source count, or absent relations.
The Application preserves prior current and as-of view selection rules.
The Application rebuilds equivalent Dimensions and Score from identical accepted Ledger state and policy.

## Acceptance Criteria

- AC-EGS-01: Domain tests prove Dimension names, values, input IDs, and Score references validate.
- AC-EGS-02: Application tests prove contradiction and unknown source-lineage Dimension selection.
- AC-EGS-03: Application tests prove the policy derives `supported` and `contested` without a numeric value.
- AC-EGS-04: Application tests prove current and as-of views select only accepted ArgumentEdges at their review-time boundary.
- AC-EGS-05: Adapter tests prove atomic publication, manifest-scoped reads, deletion, count validation, and rebuild equivalence.
- AC-EGS-06: Pipeline tests prove build and explain commands return Dimensions and Score.
- AC-EGS-07: The canonical verifier ingests the locked Anthropic PDF through `kotekomi source add-file`.
- AC-EGS-08: The canonical verifier creates reviewed PDF-backed Assertions and one reviewed contradiction ArgumentEdge.
- AC-EGS-09: The canonical verifier returns `contested`, all three Dimensions, source-lineage `unknown`, and original PDF context.
- AC-EGS-10: The canonical verifier verifies ContextManifest focus nodes and anchor text for each selected EvidenceTarget.
- AC-EGS-11: The canonical verifier rebuilds the graph sidecar and preserves the Dimension and Score records.

## Reference Implementations

- Projection policy: `packages/application/src/kotekomi_application/evidence_graph_projection.py`.
- Canonical review flow: `packages/application/src/kotekomi_application/proposed_change_review.py`.
- Sidecar publication: `packages/adapters/src/kotekomi_adapters/sqlite_knowledge_graph_retrieval.py`.
- Public graph commands: `packages/pipelines/src/kotekomi_pipelines/cli.py`.
- Temporal canonical verification: `scripts/verify_dr6_1c_canonical.py`.

## Constraints and Halt Conditions

Stop if a Score requires a numeric confidence, source independence inference, or model judgment.
Stop if a Dimension cannot name the accepted canonical input IDs that determine its value.
Stop if the feature requires changes to ContextPlanner source selection.
