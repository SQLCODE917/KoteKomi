# DR-6.1: Evidence-Linked Graph Projections

- Status: Accepted
- Parent: [Derived Document Retrieval Program](2026-07-11-derived-document-retrieval.md)
- Depends on: [Knowledge-Graph Retrieval Plane](2026-08-23-knowledge-graph-retrieval-plane.md)
- Active child: [Evidence-Linked Graph Projection MVP](2026-08-23-evidence-linked-graph-projection-mvp.md)

## Context & Problem

KoteKomi can navigate current accepted Relationships through the Knowledge-Graph retrieval plane.
The graph traversal result identifies the accepted Assertions that justify a Relationship.
The graph does not yet provide a dedicated projection that explains each Relationship through validated source evidence.

**Relationship** is an accepted canonical record that connects two canonical graph nodes.
**Evidence graph** is a disposable projection that maps one current accepted Relationship to its accepted Assertion basis.
**Contribution** is a derived record that traces one Relationship support Assertion to terminal direct Assertions and their validated EvidenceTargets.
**Projection policy** is the named rule that selects current accepted Relationships and builds Contributions.
**Score** is a numeric or ordered assessment that combines Contributions.

### Primary flow

1. An operator builds an evidence graph from the current accepted Ledger.
2. The Application traces every selected Relationship support Assertion to terminal direct Assertions.
3. The Application accepts terminal evidence only through accepted AssertionEvidenceLinks with successful EvidenceValidationAttempts.
4. The projection stores an EvidenceGraphEdge and one or more Contributions in disposable derived storage.
5. A user requests an explanation for a canonical Relationship ID.
6. The Application resolves the Contribution EvidenceTargets through ContextPlanner and returns original source context.

## Goals

- An analyst can inspect the validated source basis for each projected Relationship.
- An operator can delete and rebuild evidence graph state without changing Ledger or Archive records.
- Each derived result identifies the accepted Ledger snapshot and Projection policy that produced it.
- Later graph features can add lineage, time, dimensions, and Scores without changing DR-6.1A records.

## Program Decisions

The Ledger, Archive, accepted Assertions, EvidenceTargets, AssertionEvidenceLinks, and EvidenceValidationAttempts remain authoritative.
EvidenceGraphEdges, Contributions, manifests, explanation records, dimensions, and Scores remain derived state.
Every EvidenceGraphEdge must trace to current accepted Assertions and successful evidence validation.
The Application must preserve unknown values as explicit values when a later child needs them.
The Application must not publish a Score until a child TDD defines its policy and interpretation.
The Application must not call an uncalibrated Score a probability.
Each projection manifest must identify its source snapshot, Projection policy, builder version, adapter identity, configuration digest, and content fingerprint.
Deleting a projection must not change authoritative records.
Rebuilding from identical authoritative inputs and policy must preserve selected edges and Contributions.

## Delivery Map

| Child | Purpose | Validation |
| --- | --- | --- |
| DR-6.1A | Project current Relationships into Contributions that trace to validated evidence. | A canonical source produces an inspectable Relationship explanation and identical rebuild result. |
| DR-6.1B | Add source lineage groups and independence inputs. | A syndicated-source fixture preserves all sources but identifies one lineage group. |
| DR-6.1C | Add temporal and historical projection views. | A correction or withdrawal fixture returns distinct current and as-of explanations. |
| DR-6.1D | Add explicit dimensions and a named Score policy. | A contradiction and unknown-dimension fixture exposes each input without false probability semantics. |

DR-6.1A is the only child specified for implementation now.
The project must design each later child after it evaluates the completed preceding child.

## Proposed Architecture

```text
Accepted Ledger + Archive
          |
          v
Evidence graph Application
          |
          v
Derived graph sidecar
          |
          v
Relationship explanation -> ContextPlanner -> ContextManifest
```

The Application owns current-state selection and evidence tracing.
The graph sidecar stores only derived rows and explanation records.
ContextPlanner owns the original-source context that an explanation exposes.

## Constraints and Halt Conditions

Stop a child when a Contribution cannot trace to an accepted Assertion and a successfully validated EvidenceTarget.
Stop a child when it needs a Score before a named policy defines the Score inputs and interpretation.
Stop a child when it needs a source-lineage or temporal decision that no accepted child TDD defines.
