# TDD: Evidence Graph Lineage Inputs

- Status: Accepted
- Parent: [DR-6.1 Evidence-Linked Graph Projections](2026-07-11-evidence-weighted-graph-projections.md)
- Depends on: [Evidence-Linked Graph Projection MVP](2026-08-23-evidence-linked-graph-projection-mvp.md)

## Context & Problem

KoteKomi explains a current Relationship through validated EvidenceTargets.
The explanation does not identify when two contributing Documents reproduce the same source bytes.
An analyst can therefore see two Documents without knowing whether they represent one publication lineage.

**SourceLineageRelation** is an accepted record that identifies one reviewed cross-source document relation.
**Verbatim republication** is two Documents from distinct Sources with identical archived bytes.
**Lineage cluster** is a derived group of Documents connected by accepted SourceLineageRelations.
**No cross-source relation recorded** means KoteKomi has a Source for a Document but no accepted relation to another Document.

### Primary flow

1. An operator ingests two source URLs that contain identical locked bytes.
2. The operator proposes a verbatim republication relation for the two Documents.
3. A reviewer approves the pending relation through the existing review flow.
4. The Application builds lineage clusters with the evidence graph projection.
5. A user explains a Relationship and receives each source Document, its lineage cluster, and original source context.

## Goals

- An analyst can distinguish raw source-document count from reviewed lineage-cluster count.
- A reviewer can inspect the exact Documents and review provenance for every cross-source relation.
- The explanation preserves original source context for every contributing Document.
- The projection marks an unlinked Document without calling it independent.

## Requirements

### Domain Core

- EGL-01: Domain Core defines SourceLineageRelation with two ordered distinct Document IDs, a shared byte digest, rationale, review provenance, and review time.
- EGL-02: SourceLineageRelation defines only `verbatim_republication` in this TDD.
- EGL-03: Domain Core defines a derived lineage cluster with member Document IDs, SourceLineageRelation IDs, policy ID, snapshot digest, and cross-source relation state.
- EGL-04: EvidenceGraphContribution identifies source Document IDs and lineage-cluster memberships.

### Application Layer

- EGL-05: The proposal use case accepts two existing Documents from distinct Sources with identical `content_sha256` values.
- EGL-06: The proposal use case writes one pending ProposedChange and one proposal ProvenanceActivity.
- EGL-07: The existing review use case accepts SourceLineageRelation and replaces its pending provenance value with review provenance.
- EGL-08: The review use case rejects a missing Document, equal Document IDs, equal Source IDs, or different byte digests.
- EGL-09: The evidence graph builder includes accepted SourceLineageRelations and contributing Documents in its source snapshot.
- EGL-10: The evidence graph builder creates one recorded-relation cluster for connected Documents.
- EGL-11: The evidence graph builder creates one no-cross-source-relation-recorded cluster for an unlinked contributing Document.
- EGL-12: The explanation reports raw document count, lineage-cluster count, clusters, Contributions, and ContextPlanner results.

### SQLite Adapter

- EGL-13: The SQLite Ledger persists SourceLineageRelation as accepted canonical state.
- EGL-14: The graph sidecar publishes lineage clusters atomically with evidence graph rows.
- EGL-15: The graph sidecar rejects a complete manifest when its lineage-cluster rows disagree with manifest counts.

### Pipeline

- EGL-16: `kotekomi lineage propose-verbatim-republication` accepts two `--document-id` values, `--proposer`, and `--rationale`.
- EGL-17: The command returns the pending ProposedChange ID.
- EGL-18: `kotekomi retrieval explain-graph-relationship` returns lineage clusters and counts.

## Proposed Architecture

```text
Two accepted Documents
          |
          v
Lineage proposal -> Review Application -> SourceLineageRelation
          |
          v
Evidence graph Application -> SQLite graph sidecar
          |
          v
Relationship explanation -> ContextPlanner -> ContextManifest
```

The Application owns relation validation and cluster policy.
The SQLite Ledger owns canonical SourceLineageRelation storage.
The graph sidecar owns derived lineage clusters.
ContextPlanner owns original-source context.

## Data Model

SourceLineageRelation is canonical accepted state.
It identifies two Documents and the byte digest that the reviewer accepted as the relation basis.
The review ProvenanceActivity identifies the reviewer and the review action.

LineageCluster is derived state.
It groups contributing Documents through accepted SourceLineageRelations.
It records `recorded_relation` or `no_cross_source_relation_recorded`.

## APIs / Interfaces

`kotekomi lineage propose-verbatim-republication --document-id <id> --document-id <id> --proposer <name> --rationale <text>` creates a pending relation proposal.

`kotekomi review approve --proposed-change-id <id> --reviewer <name>` accepts the proposed relation.

The existing evidence graph build command rebuilds lineage clusters.

## Behavior & Domain Rules

The relation uses the fixed basis `reviewed_exact_content_sha256_v1`.
The relation requires two different Sources.
The relation preserves both Documents and their source evidence.
The projection does not infer a relation from matching text, embeddings, or model output.
An unlinked Document remains visible in its own derived cluster.
An unlinked cluster does not assert independence.
The TDD does not implement scores, temporal views, automatic source matching, or wiki rendering.

## Acceptance Criteria

- AC-EGL-01: Domain tests prove relation and cluster validation rules.
- AC-EGL-02: Application tests prove proposal, review, rejection, cluster construction, and unlinked-document behavior.
- AC-EGL-03: Adapter tests prove canonical relation persistence and sidecar cluster rebuild.
- AC-EGL-04: Pipeline tests prove the public proposal command and review acceptance.
- AC-EGL-05: The canonical test ingests the locked PDF twice under declared distinct source URLs.
- AC-EGL-06: The canonical test proves two Sources, two Documents, one byte digest, and acceptable reloaded representations.
- AC-EGL-07: The canonical test proposes and approves a verbatim republication relation through public commands.
- AC-EGL-08: The canonical explanation returns two contributing Documents, one recorded-relation cluster, ready ContextManifests, and original `Directive 3000.09` source evidence.
- AC-EGL-09: The canonical test deletes and rebuilds the graph sidecar without changing the lineage explanation.

## Reference Implementations

- Review acceptance: `packages/application/src/kotekomi_application/proposed_change_review.py`.
- Source identity: `packages/application/src/kotekomi_application/source_capture.py`.
- Evidence graph projection: `packages/application/src/kotekomi_application/evidence_graph_projection.py`.

## Constraints and Halt Conditions

Stop if a relation needs a similarity or model-based decision.
Stop if a relation needs temporal or score policy.
Those decisions belong to later DR-6.1 child TDDs.
