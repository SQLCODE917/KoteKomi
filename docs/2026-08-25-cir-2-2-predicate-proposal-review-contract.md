# CIR-2.2: Predicate Proposal and Review Contract

- Status: Accepted
- Program: [Model and Ontology Boundary Program](2026-08-25-model-ontology-boundary-program.md)
- Deliverable ID: CIR-2.2
- Depends on: [CIR-2.1](2026-08-25-cir-2-1-typed-assertion-object-mvp.md)

## 1. Context & Problem

CIR-2.1 lets a model propose a typed Assertion object.

The staged claim schema calls the model field `predicate`.

The review use case copies that model value into an accepted Assertion.

The model value is an ordinary-language interpretation of source text.

An accepted Assertion requires a KoteKomi-owned canonical predicate.

KoteKomi needs one explicit reviewer decision between the model relation label and the accepted predicate.

### Terms

**Relation label** means the non-empty free-text relationship phrase from model output.

**ProposedAssertion** means the pending Assertion shape that contains a relation label.

**Canonical predicate** means a reviewer-selected lower-snake-case identifier.

**Predicate decision** means the review action that selects a canonical predicate for one ProposedAssertion.

### Primary end-to-end flow

1. The model returns a relation label with a typed object and evidence reference.
2. The Application Layer validates the staged output and writes a ProposedAssertion.
3. The review packet shows the relation label and requires a canonical predicate.
4. The reviewer supplies one canonical predicate with an approval or edit decision.
5. The Application Layer creates an accepted Assertion with that canonical predicate.
6. The Ledger retains the relation label, accepted predicate, and review ProvenanceActivity.

## 2. Goals

- The model can propose a relation without creating accepted ontology meaning.
- A reviewer selects every accepted Assertion predicate explicitly.
- KoteKomi retains the model relation label beside the accepted predicate.
- KoteKomi rejects an Assertion approval without a canonical predicate.
- KoteKomi prevents bulk approval from assigning one predicate to multiple Assertions.

## 3. Requirements

### Domain Core

- C22-DOM-01: Assertion `predicate` accepts only a canonical predicate.
- C22-DOM-02: A canonical predicate matches `^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$`.
- C22-DOM-03: ProposedAssertion stores `relation_label` instead of `predicate`.
- C22-DOM-04: ProposedAssertion validates the same subject, object, source, and evidence fields as a direct Assertion.
- C22-DOM-05: ProposedAssertion has no accepted Assertion status or review ProvenanceActivity field.

### Model and candidate boundary

- C22-MODEL-01: The staged claim schema replaces `predicate` with `relation_label`.
- C22-MODEL-02: The Pipeline pins `staged_claim_output_v5` and `cir_automatic_claim_extraction_v5`.
- C22-MODEL-03: The Application Layer retains the relation label exactly after staged-output validation.
- C22-MODEL-04: The grounded candidate batch writes a ProposedAssertion inside each Assertion ProposedChange.
- C22-MODEL-05: The Application Layer derives pending Assertion identity from the relation label.

### Review boundary

- C22-REVIEW-01: Assertion approval requires one canonical predicate.
- C22-REVIEW-02: Assertion edit requires one canonical predicate and accepted record JSON.
- C22-REVIEW-03: Assertion edit requires the input predicate and accepted record predicate to match exactly.
- C22-REVIEW-04: The Application Layer compiles a ProposedAssertion into an accepted Assertion.
- C22-REVIEW-05: The Application Layer stores the canonical predicate in the accepted Assertion.
- C22-REVIEW-06: The ProposedChange retains the original ProposedAssertion.
- C22-REVIEW-07: The accepted ProposedChange JSON retains the accepted Assertion.
- C22-REVIEW-08: The review ProvenanceActivity identifies the reviewer and accepted Assertion.
- C22-REVIEW-09: Review rejection requires no canonical predicate.
- C22-REVIEW-10: Non-Assertion review behavior remains unchanged.

### Review commands

- C22-CLI-01: `kotekomi review approve` accepts `--canonical-predicate`.
- C22-CLI-02: `kotekomi review run-next --decision approve` accepts `--canonical-predicate`.
- C22-CLI-03: `kotekomi review edit` requires `--canonical-predicate` for an Assertion.
- C22-CLI-04: `kotekomi review run-next --decision edit` accepts `--canonical-predicate`.
- C22-CLI-05: The CLI passes the canonical predicate through Application Layer inputs.
- C22-CLI-06: The review packet exposes the relation label.
- C22-CLI-07: An Assertion action plan lists canonical predicate as a required input.
- C22-CLI-08: Review drain approval rejects a selection that contains an Assertion.
- C22-CLI-09: Review drain rejection retains existing behavior.

## 4. Proposed Architecture

```text
ContextManifest
    |
    v
ModelTaskRuntime
    |
    v
ProposedAssertion
    |
    v
Review packet and decision
    |
    v
Accepted Assertion
    |
    v
Ledger and ProvenanceActivity
```

The ContextPlanner owns model-visible source text and EvidenceCandidates.

The ModelTaskRuntime returns a relation label and typed references.

The Application Layer validates and stores a ProposedAssertion.

The Pipeline passes one reviewer predicate to the review use case.

The Application Layer compiles the accepted Assertion and writes review provenance.

## 5. Key Interactions

```text
Pipeline -> Application: review decision and canonical predicate
Application -> Ledger: load pending ProposedChange
Application -> Domain Core: validate ProposedAssertion and canonical predicate
Application -> Domain Core: compile accepted Assertion
Application -> Ledger: commit Assertion, evidence links, ProposedChange, and provenance
Pipeline -> Reviewer: structured review result
```

## 6. Data Model

ProposedAssertion is a new Domain Core model inside an Assertion ProposedChange.

```text
ProposedAssertion
    id
    assertion_type
    epistemic_scope
    subject_entity_id
    relation_label
    object_entity_id or object_value
    source authority and attribution
    source and EvidenceTarget references
    assertion qualifiers
```

Assertion retains its existing record shape.

Assertion `predicate` stores only the canonical predicate after review.

The existing ProposedChange fields retain both the proposed JSON and accepted JSON.

The existing review ProvenanceActivity records the predicate decision actor and time.

## 7. APIs / Interfaces

The staged claim output exposes `relation_label` for each Assertion draft.

The review Application inputs expose an optional `canonical_predicate` field.

The Application Layer requires that field only when the selected ProposedChange is an Assertion.

The field contains one canonical predicate.

The review packet JSON adds `relation_label` and `canonical_predicate_required` to assertion context.

The CLI adds `--canonical-predicate` to review approve, run-next, and edit commands.

The User Ingestion CLI remains unchanged.

## 8. Behavior & Domain Rules

The Application Layer accepts no Assertion from a relation label alone.

The Application Layer validates the canonical predicate before it starts accepted Ledger writes.

The Application Layer compares the edit flag and accepted record predicate before it starts accepted Ledger writes.

The Application Layer leaves an invalid review input pending.

The Application Layer assigns no predicate vocabulary entry in CIR-2.2.

The Application Layer maps no relation label automatically in CIR-2.2.

The Application Layer rejects bulk approval before it approves any selected Assertion.

The Application Layer permits bulk rejection because rejection creates no accepted Assertion.

## 9. Acceptance Criteria

- AC-C22-01: Domain tests prove canonical predicate validation and ProposedAssertion validation.
- AC-C22-02: Application tests prove staged relation labels create ProposedAssertions.
- AC-C22-03: Application tests prove Assertion approval without a canonical predicate fails without writes.
- AC-C22-04: Application tests prove a valid predicate creates an accepted Assertion.
- AC-C22-05: Application tests prove edit requires matching canonical predicate inputs.
- AC-C22-06: Application tests prove proposed and accepted predicate values remain auditable.
- AC-C22-07: Application tests prove bulk Assertion approval fails before queue mutation.
- AC-C22-08: Adapter tests prove restart-safe proposed and accepted Assertion persistence.
- AC-C22-09: Pipeline tests prove review packets, action plans, and CLI validation expose the contract.
- AC-C22-10: Pipeline tests prove non-Assertion approval and bulk rejection retain current behavior.
- AC-C22-11: The local Anthropic--DoD PDF ingestion creates pending ProposedAssertions with relation labels.
- AC-C22-12: Full formatting, lint, type, Domain, Application, Adapter, and Pipeline checks pass.

## 10. Reference Implementations

- Staged extraction: `packages/application/src/kotekomi_application/staged_model_extraction.py`.
- Grounded candidates: `packages/application/src/kotekomi_application/grounded_candidates.py`.
- Review use cases: `packages/application/src/kotekomi_application/proposed_change_review.py`.
- Review packet: `packages/application/src/kotekomi_application/review_queue_packet.py`.
- SQLite review commit: `packages/adapters/src/kotekomi_adapters/sqlite_ledger.py`.

## 11. Constraints and Halt Conditions

CIR-2.2 creates no predicate vocabulary record.

CIR-2.2 maps no relation label to a predicate automatically.

CIR-2.2 adds no Actor, Event, Place, or generic Entity model references.

CIR-2.2 adds no ModelTaskRuntime protocol or structured-output transport change.

CIR-2.3 must define predicate vocabulary and mapping decisions before implementation.
