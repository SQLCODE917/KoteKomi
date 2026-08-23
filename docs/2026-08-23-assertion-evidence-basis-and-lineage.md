# Assertion Evidence Basis and Lineage

## Context & Problem

### Glossary

**Direct Assertion**
An Assertion that cites original source evidence through one or more EvidenceTargets.

**Analytic Inference**
An Assertion that derives from one or more accepted Assertions.

**Terminal Assertion**
A Direct Assertion reached by following the supporting Assertion chain of an Analytic Inference.

**Supersession**
One accepted Assertion replaces one earlier Assertion with the same claim identity.

KoteKomi currently accepts source-backed Assertions and some evidence-free analytic Assertions.
The Ledger cannot prove the basis of every accepted Assertion.
The Ledger also retains superseded Assertions without a canonical successor relation.

### Primary flow

1. A reviewer accepts a Direct Assertion with Source and EvidenceTarget references.
2. A reviewer accepts an Analytic Inference with accepted supporting Assertion references.
3. The review use case validates every reference before it changes the Ledger.
4. The review use case resolves each inference chain to Terminal Assertions.
5. A reviewer accepts a successor Assertion and names one predecessor.
6. The review use case saves the successor and marks the predecessor superseded in one transaction.

## Goals

- Every accepted Assertion has an inspectable basis.
- Every Analytic Inference resolves to original document evidence.
- A user can distinguish current Assertions from their historical predecessors.
- The Ledger retains prior Assertions for audit.

## Requirements

### Domain Core

- AEBL-01: The Assertion record must contain `supporting_assertion_ids` and `supersedes_assertion_id`.
- AEBL-02: A Direct Assertion must contain nonempty `source_ids` and `evidence_target_ids`.
- AEBL-03: A Direct Assertion must contain no `supporting_assertion_ids`.
- AEBL-04: An Analytic Inference must contain nonempty `supporting_assertion_ids`.
- AEBL-05: An Analytic Inference must contain no Source or EvidenceTarget references.
- AEBL-06: An Analytic Inference must use `source_authority=not_applicable` and `attribution_basis=not_applicable`.
- AEBL-07: An Assertion must use exactly one of the Direct Assertion and Analytic Inference forms.
- AEBL-08: A Relationship and an Outcome must contain one or more unique Assertion references.

### Review Application

- AEBL-09: The review use case must require every supporting Assertion to exist and have an accepted status.
- AEBL-10: The review use case must reject a self reference, a duplicate support reference, and a support cycle.
- AEBL-11: The review use case must reject an inference chain that does not terminate in one or more Direct Assertions.
- AEBL-12: The review use case must require the superseded predecessor to exist and have an accepted current status.
- AEBL-13: The review use case must require a successor and predecessor to have the same subject, predicate, and EpistemicScope.
- AEBL-14: The review use case must reject a predecessor that already has a successor.
- AEBL-15: The review use case must save the successor, the revised predecessor, review ProvenanceActivity, evidence links, and ProposedChange transition atomically.
- AEBL-16: The review ProvenanceActivity must list both Assertions when it performs Supersession.
- AEBL-17: The revised predecessor must have `status=superseded`, its review ProvenanceActivity ID, and the review timestamp as `updated_at`.

## Proposed Architecture

```text
ProposedChange
    |
    v
Review Application -----> SQLite Ledger
    |                         |
    |                         +--> Direct Assertion -> EvidenceTarget -> DocumentNode
    |
    +--> Analytic Inference -> supporting Assertion IDs -> Terminal Assertions
```

The Domain Core validates intrinsic Assertion form rules.
The Review Application validates Ledger references, inference closure, and Supersession state transitions.
The SQLite Ledger commits the accepted-state transition atomically.

## Key Interactions

```text
Reviewer -> Review Application: approve successor ProposedChange
Review Application -> Ledger: load predecessor and support graph
Review Application -> Review Application: validate claim identity and terminal evidence
Review Application -> Ledger: atomically save successor and supersede predecessor
Review Application -> Reviewer: accepted record IDs and review ProvenanceActivity ID
```

## Data Model

`Assertion.supporting_assertion_ids` stores the direct premises of an Analytic Inference.
`Assertion.supersedes_assertion_id` stores the single predecessor of a successor Assertion.
The predecessor does not store a mutable successor field.
The Review Application derives predecessor successor uniqueness from accepted Assertions.

`Relationship.assertion_ids` and `Outcome.assertion_ids` store the accepted Assertions that establish their meaning.

## APIs / Interfaces

The existing ProposedChange review Application use cases remain the accepted-state boundary.
The SQLite review commit Port gains an atomic Supersession operation.
The result DTO reports the superseded predecessor ID when a review action performs Supersession.

## Behavior & Domain Rules

The Review Application permits multi-level Analytic Inference chains.
Every chain must be acyclic and end in a Direct Assertion.
The Review Application uses the Direct Assertion EvidenceTargets as the source evidence for an Analytic Inference.

The Review Application defines claim identity for Supersession as subject, predicate, and EpistemicScope.
Object values, object entities, qualifiers, confidence, and assessment text can change in a successor.
The Review Application excludes `superseded` and `retracted` Assertions from current-state views.
The Review Application retains these Assertions in audit views.

## Acceptance Criteria

- AC-AEBL-01: Domain tests reject each invalid Assertion basis form.
- AC-AEBL-02: Application tests reject missing, proposed, duplicate, self-referential, cyclic, and terminal-source-less support graphs.
- AC-AEBL-03: Application tests accept an acyclic inference chain that ends in Direct Assertions.
- AC-AEBL-04: Application tests reject Supersession with a missing, historical, identity-mismatched, or already-replaced predecessor.
- AC-AEBL-05: Adapter tests prove a Supersession commit is atomic across every write boundary.
- AC-AEBL-06: Review tests prove the predecessor remains queryable with `status=superseded`.

## Reference Implementations

- Review acceptance: `packages/application/src/kotekomi_application/proposed_change_review.py`.
- Atomic Assertion acceptance: `packages/adapters/src/kotekomi_adapters/sqlite_ledger.py`.
- Evidence validation: `packages/application/src/kotekomi_application/evidence_targets.py`.
