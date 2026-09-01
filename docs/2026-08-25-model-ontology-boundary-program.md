# Model and Ontology Boundary Program

- Status: Superseded
- Successor: [Hybrid Intelligence Extraction Pipeline](2026-09-01-hybrid-intelligence-extraction-pipeline.md)
- Program ID: `model-ontology-boundary`
- Parent program: [Candidate Ingestion Review](2026-08-24-candidate-ingestion-review-program.md)
- Completed children:
  - [CIR-2.1 Typed Assertion Object MVP](2026-08-25-cir-2-1-typed-assertion-object-mvp.md)
  - [CIR-2.2 Predicate Proposal and Review Contract](2026-08-25-cir-2-2-predicate-proposal-review-contract.md)
  - [CIR-2.2.1 Direct Prose Semantic Draft MVP](2026-08-25-cir-2-2-1-direct-prose-semantic-draft-mvp.md)
- Superseded next child:
  CIR-2.3 Predicate vocabulary and review UX.
- Related program:
  [Paragraph Hypothesis Development Program](2026-08-26-paragraph-hypothesis-development-program.md).

The completed CIR-2.1, CIR-2.2, and CIR-2.2.1 results remain historical implementation evidence.

The Hybrid Pipeline supersedes the planned CIR-2.3 and later model-boundary work.

## Context and problem

KoteKomi uses a local model to interpret authoritative source text.

KoteKomi stores accepted intelligence in the Ledger.

The model cannot author accepted Ledger state.

KoteKomi must preserve useful model language without accepting unverified ontology meaning.

CIR-2.1 lets the model propose a typed organization or literal object.

CIR-2.2 stores a model relation label in a ProposedAssertion.

CIR-2.2 requires a reviewer to select the canonical predicate for an accepted Assertion.

The current claim task still lets the model select an EvidenceCandidate from a multi-node context.

The model selected a reference-list item for one proposed relation in the canonical PDF.

The reference-list item identifies a source citation.

The reference-list item does not provide direct prose for that relation.

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

**Semantic draft** means small model output that describes one source claim without Ledger records.

**Eligible prose** means one focus DocumentNode with `node_type = paragraph`.

**Relation label** means the ordinary-language relationship phrase in a semantic draft.

**Canonical predicate** means a KoteKomi-owned term for one accepted relationship meaning.

**Entity object** means an Assertion object that resolves to one canonical record.

**Literal object** means an Assertion object that stores one text, number, date, or other literal value.

## Certain design decisions

KoteKomi owns source identity, source text, node identity, source ranges, source regions, and Ledger writes.

The ContextPlanner owns the source text that one model task receives.

The ContextManifest owns the EvidenceCandidate catalogue for one model task.

The model receives original source text and task-local labels.

The model does not receive canonical IDs, Archive paths, database paths, source ranges, or source regions.

The model can propose one organization name, relation label, and typed object.

The Application Layer binds each model task to one eligible EvidenceCandidate before it creates a ModelTaskRequest.

The Application Layer derives all record IDs, EvidenceTargets, provenance records, and task-local identifiers.

The Application Layer archives every raw model output before it validates the semantic draft.

The Application Layer creates no ProposedChange from invalid model output.

The review flow remains the only path from a model proposal to accepted Ledger state.

The accepted Assertion contract already requires exactly one entity object or literal object.

The model-facing contract exposes that same distinction.

The model can use ordinary-language relation labels in a pending proposal.

KoteKomi must govern canonical predicates before it accepts a relation as ontology state.

## Implemented boundary

CIR-2.1 resolves an organization object to `Assertion.object_entity_id`.

CIR-2.1 resolves a literal object to `Assertion.object_value`.

CIR-2.2 retains a relation label in each ProposedAssertion.

CIR-2.2 requires a reviewer to supply a canonical predicate before Assertion acceptance.

CIR-2.2.1 binds each model task to one eligible prose node.

CIR-2.2.1 replaces the model JSON candidate envelope with a small plain-text SemanticDraft.

## Superseded delivery map

This table records the former delivery sequence.

| Deliverable | Role | Precondition | Postcondition |
|---|---|---|---|
| Direct prose semantic draft | Binds one model task to direct prose. | Typed proposals and predicate review exist. | Each proposed Assertion has deterministic direct evidence. |
| Predicate vocabulary | Maps labels in review. | Direct prose SemanticDrafts exist. | Accepted Assertions use governed canonical predicates. |
| Extended references | Adds task-local Actor, Event, Place, and Entity references. | Organization references resolve. | KoteKomi resolves each permitted object kind. |
| Constrained output | Uses runtime constraints for draft transport. | The draft schema is stable. | The runtime reduces malformed drafts. |
| Model retry | Records a second bounded attempt after an invalid draft. | Invalid drafts are archived. | Each retry has provenance and a reason. |

## Validation strategy

The MVP uses ContextPlanner and Application tests to prove paragraph-only selection and typed object resolution.

The MVP uses Adapter tests to prove persisted proposed Assertion shape after restart and Pipeline tests to prove one bound paragraph task.

The MVP uses the canonical deposited PDF to prove that CIR-2 remains complete and direct-prose-grounded.

The Hybrid Pipeline replaces all undelivered entries in this table.
