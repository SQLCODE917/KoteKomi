# Model and Ontology Boundary Program

- Status: Proposed
- Program ID: `model-ontology-boundary`
- Parent program: [Candidate Ingestion Review](2026-08-24-candidate-ingestion-review-program.md)
- First child: [CIR-2.1 Typed Assertion Object MVP](2026-08-25-cir-2-1-typed-assertion-object-mvp.md)

## Context and problem

KoteKomi uses a local model to interpret authoritative source text.

KoteKomi stores accepted intelligence in the Ledger.

The model cannot author accepted Ledger state.

KoteKomi must preserve useful model language without accepting unverified ontology meaning.

The current CIR-2 claim schema represents every assertion object as `object_value`.

The schema cannot express a relationship between two task-local organizations.

The model can therefore place an organization local identifier in a literal-value field.

The Application Layer then creates a literal-valued Assertion instead of an entity relationship.

This program defines the stable boundary between model interpretation and KoteKomi authority.

### Program statement

KoteKomi must let a model propose grounded semantic drafts in ordinary language.

KoteKomi must compile valid drafts into pending ProposedChanges with authoritative lineage.

KoteKomi must require review before a semantic draft changes accepted ontology state.

```text
DocumentRepresentationBundle
    -> ContextManifest with EvidenceCandidates
    -> model semantic draft
    -> validated typed candidate
    -> authoritative EvidenceTarget and pending ProposedChange
    -> reviewer decision
    -> accepted Assertion with governed ontology meaning
```

## Terms

**Semantic draft** means small model output that names task-local references and one source claim.

**Relation label** means the ordinary-language relationship phrase in a semantic draft.

**Canonical predicate** means a KoteKomi-owned term for one accepted relationship meaning.

**Entity object** means an Assertion object that resolves to one canonical record.

**Literal object** means an Assertion object that stores one text, number, date, or other literal value.

## Certain design decisions

KoteKomi owns source identity, source text, node identity, source ranges, source regions, and Ledger writes.

The ContextPlanner owns the source text that one model task receives.

The ContextManifest owns the EvidenceCandidate catalogue that one model task can select.

The model receives original source text and task-local labels.

The model does not receive canonical IDs, Archive paths, database paths, source ranges, or source regions.

The model can propose one organization name, relation label, typed object, and EvidenceCandidate selection.

The Application Layer validates every task-local reference before it creates a ProposedChange.

The Application Layer derives canonical IDs, EvidenceTargets, provenance records, and deterministic record IDs.

The Application Layer archives every raw model output before it validates the semantic draft.

The Application Layer creates no ProposedChange from invalid model output.

The review flow remains the only path from a model proposal to accepted Ledger state.

The accepted Assertion contract already requires exactly one entity object or literal object.

The model-facing contract must expose that same distinction.

The model can use ordinary-language relation labels in a pending proposal.

KoteKomi must govern canonical predicates before it accepts a relation as ontology state.

## MVP

The first deliverable proves the typed object boundary for task-local organizations.

The MVP accepts either a literal object or a task-local organization reference.

The MVP resolves a valid organization reference to `Assertion.object_entity_id`.

The MVP resolves a valid literal object to `Assertion.object_value`.

The MVP retains the current free-text `predicate` field in pending Assertion proposals.

The MVP does not define canonical predicates.

The MVP does not add entity references for Actors, Events, Places, or generic Entities.

The MVP does not add automatic predicate normalization.

The MVP does not change the review decision model.

## Later deliverables

Each later deliverable stays undefined until the MVP ships and produces implementation evidence.

| Deliverable | Role | Precondition | Postcondition |
|---|---|---|---|
| Predicate governance | Maps labels in review. | Typed proposals exist. | Accepted Assertions use canonical predicates. |
| Extended references | Adds task-local Actor, Event, Place, and Entity references. | Organization references resolve. | KoteKomi resolves each permitted object kind. |
| Constrained output | Uses runtime constraints for draft transport. | The draft schema is stable. | The runtime reduces malformed drafts. |
| Model retry | Records a second bounded attempt after an invalid draft. | Invalid drafts are archived. | Each retry has provenance and a reason. |

## Validation strategy

The MVP uses Domain and Application tests to prove typed object resolution.

The MVP uses Adapter tests to prove persisted proposed Assertion shape after restart.

The MVP uses the canonical deposited PDF to prove that CIR-2 remains complete and source-grounded.

Later deliverables must add their own TDD before implementation.
