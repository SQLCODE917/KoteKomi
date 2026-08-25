# CIR-2.1: Typed Assertion Object MVP

- Status: Accepted
- Program: [Model and Ontology Boundary Program](2026-08-25-model-ontology-boundary-program.md)
- Deliverable ID: CIR-2.1
- Depends on: [CIR-2](2026-08-24-automatic-extraction-change-set.md)

## 1. Context & Problem

CIR-2 creates pending Assertion ProposedChanges from bounded model output.

The current staged claim schema has one `object_value` field.

That field represents a literal value.

The current schema cannot represent an object organization local reference.

The model can therefore emit an organization local identifier as a literal value.

The Application Layer then creates an Assertion with `object_value` instead of `object_entity_id`.

The existing Assertion contract requires exactly one entity object or literal object.

The model-facing contract must represent that distinction.

### Terms

**Object draft** means the typed object field in one staged claim output.

**Organization reference** means an Object draft with one local organization identifier.

**Literal value** means an Object draft that carries one text value.

### Primary end-to-end flow

1. The Pipeline creates a ContextManifest with source text and EvidenceCandidates.
2. The model returns a subject organization, predicate, Object draft, and evidence reference.
3. The Application Layer validates every task-local reference.
4. The Application Layer resolves an Organization reference to a canonical Organization ID.
5. The Application Layer creates a pending Assertion ProposedChange with the resolved Object draft.
6. The review flow receives the pending ProposedChange with its EvidenceTarget lineage.

## 2. Goals

- A model can propose an organization relationship without canonical identifiers.
- A model can propose a literal-valued Assertion without ambiguity.
- KoteKomi rejects an unknown organization reference before it creates a ProposedChange.
- A reviewer can distinguish an entity object from a literal object in a pending Assertion proposal.
- CIR-2 remains source-grounded and complete for the canonical deposited PDF.

## 3. Requirements

### Staged claim contract

- C21-SCHEMA-01: The staged claim schema defines one Object draft for each Assertion draft.
- C21-SCHEMA-02: An Object draft has exactly one kind: `organization_reference` or `literal`.
- C21-SCHEMA-03: An `organization_reference` Object draft contains only `organization_local_id`.
- C21-SCHEMA-04: A `literal` Object draft contains only a non-empty `value` string.
- C21-SCHEMA-05: An Assertion draft contains subject, predicate, Object draft, and evidence reference.
- C21-SCHEMA-06: The staged claim schema does not define `object_value` at the model boundary.
- C21-SCHEMA-07: The Application Layer assigns assertion local identifiers in output order.
- C21-SCHEMA-08: The original completed slice used `staged_claim_output_v4` and `cir_automatic_claim_extraction_v4`; CIR-2.2 supersedes that staged contract with v5.
- C21-SCHEMA-09: The original completed slice used `cir_automatic_claim_validator_v3`; CIR-2.2 supersedes it with `cir_automatic_claim_validator_v4` while retaining the existing context renderer.

### Grounded candidate boundary

- C21-GROUND-01: The Application Layer validates the subject organization reference against the organization catalogue.
- C21-GROUND-02: The Application Layer validates an Organization reference against the organization catalogue.
- C21-GROUND-03: The Application Layer resolves a valid Organization reference to the batch Organization ID.
- C21-GROUND-04: The Application Layer resolves a Literal value to an Assertion literal object.
- C21-GROUND-05: The Application Layer derives the Assertion ID from the resolved Object draft.
- C21-GROUND-06: The Application Layer writes `object_entity_id` for an Organization reference.
- C21-GROUND-07: The Application Layer writes `object_value` for a Literal value.
- C21-GROUND-08: The Application Layer archives malformed or unknown Object drafts without a ProposedChange.

### Ontology boundary

- C21-ONTO-01: The MVP retains the model-provided non-empty `predicate` string in each pending Assertion proposal.
- C21-ONTO-02: The MVP creates no canonical predicate record.
- C21-ONTO-03: The MVP creates no accepted Assertion from model output.

## 4. Proposed Architecture

```text
ContextManifest
    |
    v
ModelTaskRuntime
    |
    v
staged claim output
    |
    v
Staged extraction use case
    |
    v
Grounded candidate batch
    |
    v
pending Assertion ProposedChange
```

The ContextPlanner owns the model-visible source text and EvidenceCandidate labels.

The ModelTaskRuntime returns raw staged claim output.

The staged extraction use case archives and validates the output.

The grounded candidate batch resolves task-local organization identifiers and derives EvidenceTargets.

The review flow retains ownership of accepted state changes.

## 5. Key Interactions

```text
Pipeline -> ContextPlanner: build ContextManifest
ContextPlanner -> ModelTaskRuntime: prompt, schema, source text, and local labels
ModelTaskRuntime -> Staged extraction use case: staged claim output
Staged extraction use case -> Grounded candidate batch: typed candidate input
Grounded candidate batch -> Ledger: EvidenceTarget and pending ProposedChanges
Review flow -> Ledger: later reviewer decision
```

## 6. Data Model

The existing Assertion record remains unchanged.

The existing Assertion record already stores one `object_entity_id` or one `object_value`.

The staged claim output replaces the current assertion object field with this contract.

```text
Object draft
    kind = organization_reference
    organization_local_id

Object draft
    kind = literal
    value
```

The output organization catalogue remains task-local model output.

The Application Layer derives canonical Organization IDs from that catalogue.

The MVP adds no stored ontology vocabulary record.

## 7. APIs / Interfaces

The existing user command remains unchanged.

```text
kotekomi ingest <path> --url <SOURCE_URL>
```

The ModelTaskRuntime Port remains the only model boundary.

The MVP pins a new prompt and staged claim schema version inside each ModelExecutionSpec.

The MVP exposes no new User CLI option.

## 8. Behavior & Domain Rules

The Application Layer treats an Organization reference as an entity object.

The Application Layer treats a Literal value as a literal object.

The Application Layer rejects an Object draft that does not match its declared kind.

The Application Layer rejects an Organization reference that names no task-local organization.

The Application Layer archives rejected raw output before it records `INVALID_OUTPUT`.

The Application Layer creates no partial ProposedChange batch after rejection.

The existing EvidenceCandidate rules remain unchanged.

The existing review flow remains unchanged.

## 9. Acceptance Criteria

- AC-C21-01: Domain tests prove that Assertion accepts one entity object or one literal object.
- AC-C21-02: Application tests prove that an Organization reference resolves to `object_entity_id`.
- AC-C21-03: Application tests prove that a Literal value resolves to `object_value`.
- AC-C21-04: Application tests prove that an unknown Organization reference creates `INVALID_OUTPUT` and no ProposedChange.
- AC-C21-05: Application tests prove that an Object draft with both kinds becomes invalid output.
- AC-C21-06: Application tests prove that a model task has EvidenceCandidate labels and no canonical ID.
- AC-C21-07: SQLite tests prove restart-safe persistence of both Assertion object forms.
- AC-C21-08: Pipeline tests prove that the user command retains its existing output shape.
- AC-C21-09: The canonical PDF ingestion completes CIR-2 coverage and creates pending ProposedChanges.

## 10. Reference Implementations

- ContextManifest: `packages/application/src/kotekomi_application/context_planning.py`.
- Staged model boundary: `packages/application/src/kotekomi_application/staged_model_extraction.py`.
- Grounded candidates: `packages/application/src/kotekomi_application/grounded_candidates.py`.
- Assertion validation: `packages/domain/src/kotekomi_domain/models.py`.
- Proposed change review: `packages/application/src/kotekomi_application/proposed_change_review.py`.

## 11. Constraints and Halt Conditions

This TDD permits only task-local Organization references and literal values.

Stop if the implementation requires Actor, Event, Place, or generic Entity references.

Stop if the implementation requires a canonical predicate registry.

Stop if the implementation requires automatic predicate normalization.

Stop if the implementation requires a new model runtime protocol.

The follow-on program TDD must define each stopped scope before implementation.
