# TDD: Evidence Graph Temporal Views

- Status: Accepted
- Parent: [DR-6.1 Evidence-Linked Graph Projections](2026-07-11-evidence-weighted-graph-projections.md)
- Depends on: [Evidence Graph Lineage Inputs](2026-08-23-evidence-graph-lineage-inputs.md)

## Context & Problem

KoteKomi explains a current Relationship through validated source evidence.
KoteKomi does not yet explain which evidence supported a Relationship before a later review corrected it.
An analyst therefore cannot distinguish current Ledger knowledge from an earlier accepted Ledger state.

**Current view** selects the accepted Ledger state at query time.
**As-of view** selects the accepted Ledger state at or before one UTC review timestamp.
**Acceptance activity** is the approving or edited review ProvenanceActivity for one accepted record.
**Temporal provenance** is the acceptance activity and reviewed ProposedChange that reconstruct one record at an as-of cutoff.
**Correction** is a later accepted Assertion that names an earlier Assertion through `supersedes_assertion_id`.

### Primary flow

1. An operator builds a current or as-of evidence graph view.
2. The Application selects accepted records through their review ProvenanceActivities.
3. The Application reconstructs the Assertion state at the requested cutoff.
4. The Application builds Contributions from validated EvidenceTargets in the selected state.
5. A user explains a Relationship through the matching temporal view.
6. ContextPlanner returns original source context for the selected EvidenceTargets.

## Goals

- An analyst can distinguish current accepted evidence from earlier accepted evidence.
- An analyst can inspect the review activity that fixed each temporal boundary.
- Each temporal explanation contains original source context and exact authoritative references.
- An operator can rebuild one temporal view without changing another temporal view.

## Requirements

### Domain Core

- EGT-01: Domain Core defines `current` and `as_of` EvidenceGraph view kinds.
- EGT-02: An as-of view requires one RFC 3339 UTC timestamp.
- EGT-03: A current view has no cutoff timestamp.
- EGT-04: EvidenceGraphProjectionManifest records the view kind and cutoff.
- EGT-05: EvidenceGraphExplanationRecord records the view kind and cutoff.

### Application Layer

- EGT-06: The Application selects an as-of record only when its Acceptance activity occurred at or before the cutoff.
- EGT-07: The Application derives an Assertion's historical payload from its accepted ProposedChange JSON.
- EGT-08: A successor Assertion supersedes its predecessor only after the successor Acceptance activity.
- EGT-09: The Application selects an AssertionEvidenceLink only when its provenance activity occurred at or before the cutoff.
- EGT-10: The Application selects an EvidenceValidationAttempt only when it succeeded at or before the cutoff.
- EGT-11: The Application returns `evidence_graph_temporal_provenance_invalid` when a selected historical record lacks one unambiguous Acceptance activity.
- EGT-12: The Application includes the view kind and cutoff in the source snapshot and content fingerprint.
- EGT-13: The Application does not use source publication time for an as-of view.

### SQLite Adapter

- EGT-14: The graph sidecar stores current and as-of projection rows by projection manifest ID.
- EGT-15: The graph sidecar reads edges, Contributions, and lineage clusters only from the requested manifest.
- EGT-16: The graph sidecar replaces only the requested view when an operator requests rebuild.
- EGT-17: The graph sidecar discards only obsolete evidence-graph tables when it finds the prior single-manifest schema.

### Pipeline

- EGT-18: `kotekomi retrieval build-graph-evidence --as-of <timestamp>` builds one as-of view.
- EGT-19: `kotekomi retrieval explain-graph-relationship --as-of <timestamp>` reads the matching as-of view.
- EGT-20: The Pipeline rejects a timestamp without a UTC offset.
- EGT-21: The explain command returns a typed projection-not-found failure when the matching view is absent.

## Proposed Architecture

```text
Accepted Ledger + review provenance
              |
              v
Temporal evidence graph Application
              |
              v
Manifest-scoped SQLite graph sidecar
              |
              v
Relationship explanation -> ContextPlanner -> ContextManifest
```

The Application owns temporal record selection and Assertion state reconstruction.
The SQLite Adapter stores only derived manifest-scoped projection rows.
ContextPlanner owns structural source expansion and context packing.

## Key Interactions

```text
Operator -> Pipeline: build-graph-evidence --as-of <timestamp>
Pipeline -> Application: build temporal evidence graph
Application -> Ledger: load accepted records, reviews, links, and validations
Application -> SQLite sidecar: publish one complete manifest-scoped view

User -> Pipeline: explain-graph-relationship --as-of <timestamp>
Pipeline -> Application: load matching temporal view
Application -> ContextPlanner: build context from selected EvidenceTargets
Pipeline -> User: Contributions, review boundary, and ContextManifest IDs
```

## Data Model

EvidenceGraphProjectionManifest gains one view kind and an optional as-of timestamp.
EvidenceGraphExplanationRecord gains the same view fields.
The current view uses no timestamp.
The as-of view uses the inclusive UTC review-time cutoff.
The Ledger, Archive, ProposedChange, and ProvenanceActivity records remain authoritative.

## APIs / Interfaces

`kotekomi retrieval build-graph-evidence --as-of <RFC3339-UTC>` builds one historical view.
`kotekomi retrieval explain-graph-relationship --relationship-id <id> --as-of <RFC3339-UTC>` explains one historical Relationship.
The existing commands without `--as-of` use the current view.

## Behavior & Domain Rules

The temporal policy ID is `evidence_graph_temporal_relationship_contributions_v1`.
The Application compares review timestamps with inclusive UTC ordering.
The Application selects a historical Relationship only when its support Assertions were current at the cutoff.
The Application preserves the existing current-view behavior when the caller omits `--as-of`.
The Application uses the accepted ProposedChange payload to restore a predecessor Assertion before supersession.
The Application does not infer a historical state from mutable `updated_at` values.
The graph sidecar can retain multiple complete views at once.
The graph sidecar must not return a row from another view.
This TDD implements supersession corrections only.
This TDD does not implement withdrawal transitions, source-time views, temporal graph traversal, Scores, or wiki rendering.

## Acceptance Criteria

- AC-EGT-01: Domain tests prove current and as-of view validation rules.
- AC-EGT-02: Application tests prove pre-correction and post-correction Assertion selection.
- AC-EGT-03: Application tests prove missing and ambiguous temporal provenance return the typed failure.
- AC-EGT-04: Adapter tests prove current and as-of manifests coexist without cross-view reads.
- AC-EGT-05: Pipeline tests prove `--as-of` routes through both public commands.
- AC-EGT-06: The canonical verifier ingests the locked Anthropic PDF through `kotekomi source add-file`.
- AC-EGT-07: The canonical verifier seeds two reviewed PDF-backed Assertions at fixed distinct UTC times.
- AC-EGT-08: The canonical verifier proves an as-of explanation selects the earlier Assertion and original PDF context.
- AC-EGT-09: The canonical verifier proves a current explanation selects the successor Assertion and original PDF context.
- AC-EGT-10: The canonical verifier proves each ContextManifest resolves selected authoritative DocumentNode IDs.
- AC-EGT-11: The canonical verifier rebuilds the as-of view without changing the current explanation.

## Reference Implementations

- Review provenance: `packages/application/src/kotekomi_application/proposed_change_review.py`.
- Current graph selection: `packages/application/src/kotekomi_application/evidence_graph_projection.py`.
- Derived graph persistence: `packages/adapters/src/kotekomi_adapters/sqlite_knowledge_graph_retrieval.py`.
- Canonical graph verification: `scripts/verify_dr6_1_canonical.py`.

## Constraints and Halt Conditions

Stop if historical selection requires source publication time.
Stop if a historical Contribution cannot trace through accepted review provenance and validated source evidence.
Stop if the feature requires a withdrawal state transition.
