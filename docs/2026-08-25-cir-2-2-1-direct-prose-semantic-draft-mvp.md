# CIR-2.2.1: Direct Prose Semantic Draft MVP

- Status: Accepted
- Program: [Model and Ontology Boundary Program](2026-08-25-model-ontology-boundary-program.md)
- Deliverable ID: CIR-2.2.1
- Depends on: [CIR-2.2](2026-08-25-cir-2-2-predicate-proposal-review-contract.md)

## 1. Context & Problem

A user ingests a Document and reviews source-grounded Assertion proposals.

CIR-2.2 creates a ProposedAssertion before any reviewer accepts ontology meaning.

The current model task receives a ContextManifest with several EvidenceCandidates.

The current model selects one EvidenceCandidate in its JSON candidate envelope.

The canonical PDF produced a relation proposal that selected a reference-list item.

The reference-list item identified a citation rather than direct prose for the relation.

KoteKomi must select eligible prose before it calls the model.

KoteKomi must construct every Domain Core record from pinned context and one SemanticDraft.

The model must decide only whether one eligible prose node supports one relation.

### Terms

**Eligible prose** means one focus DocumentNode with `node_type = paragraph`.

**SemanticDraft** means a small plain-text model response for one eligible prose node.

**Bound evidence candidate** means the eligible EvidenceCandidate for one SemanticDraft task.

### Primary end-to-end flow

1. The ContextPlanner creates one ContextManifest for one paragraph focus node.
2. The ContextPlanner creates one bound evidence candidate for that paragraph.
3. The Pipeline sends the manifest and the bound evidence candidate to the model.
4. The model returns one SemanticDraft or abstains.
5. The Application Layer validates the SemanticDraft against the bound evidence candidate.
6. The Application Layer creates EvidenceTarget, ProposedAssertion, ProposedChange, and provenance.

## 2. Goals

- A proposed Assertion cites direct paragraph prose from its pinned DocumentRepresentation.
- A reference-list item cannot become direct Assertion evidence.
- A model returns semantic judgment without Ledger JSON or KoteKomi identifiers.
- KoteKomi creates every pending record from deterministic source state and one SemanticDraft.
- A reviewer can inspect the exact source prose for every proposed relation.

## 3. Requirements

### ContextPlanner

- C221-CTX-01: The ContextPlanner defines `direct_prose_evidence_v1` as an evidence policy.
- C221-CTX-02: The policy creates an EvidenceCandidate for every focus paragraph DocumentNode.
- C221-CTX-03: The policy excludes every ContextCandidate except a focus paragraph.
- C221-CTX-04: The policy orders EvidenceCandidates by focus node `order_index`.
- C221-CTX-05: ContextManifest verification rebuilds the candidate catalogue with the policy.
- C221-CTX-06: ContextManifest verification rejects a changed candidate catalogue.

### Pipeline

- C221-PIPE-01: The automatic claim Pipeline plans claim tasks from paragraph focus nodes only.
- C221-PIPE-02: The Pipeline creates one AnalysisUnit with one paragraph focus node.
- C221-PIPE-03: The Pipeline creates one ready ContextManifest with one bound evidence candidate.
- C221-PIPE-04: The Pipeline sends no task for an AnalysisUnit without a bound evidence candidate.
- C221-PIPE-05: The Pipeline pins `cir_direct_prose_semantic_draft_v1` for every claim task.
- C221-PIPE-06: The Pipeline pins `semantic_draft_text_v1` for every claim task.

### Model boundary

- C221-MODEL-01: The prompt labels the bound evidence paragraph as direct prose.
- C221-MODEL-02: The prompt gives original source text and no KoteKomi identifier, range, or region.
- C221-MODEL-03: The model returns exactly one plain-text SemanticDraft or plain-text abstention.
- C221-MODEL-04: A claim SemanticDraft has exactly five specified lines in the specified order.
- C221-MODEL-05: An abstention SemanticDraft has ordered `outcome` and `reason` lines.
- C221-MODEL-06: `outcome` equals `claim` or `abstain`.
- C221-MODEL-07: `object_kind` equals `organization` or `literal`.
- C221-MODEL-08: A claim SemanticDraft contains only the five specified lines.
- C221-MODEL-09: The Application Layer archives raw model output before it parses a SemanticDraft.
- C221-MODEL-10: The Application Layer records malformed SemanticDraft output as `invalid_output`.
- C221-MODEL-11: The Application Layer creates no ProposedChange from malformed output.

### Grounding boundary

- C221-GROUND-01: The Application Layer derives the EvidenceTarget only from the bound candidate.
- C221-GROUND-02: The Application Layer requires the draft subject in the bound candidate text.
- C221-GROUND-03: The Application Layer requires an organization object in the bound candidate text.
- C221-GROUND-04: The Application Layer requires a literal object in the bound candidate exact text.
- C221-GROUND-05: The Application Layer stores the relation line as `relation_label`.
- C221-GROUND-06: The Application Layer derives Organization candidates and task-local identifiers.
- C221-GROUND-07: The Application Layer derives Assertion, EvidenceTarget, and provenance identity.
- C221-GROUND-08: The Application Layer creates no record from an invalid SemanticDraft.

### Record retention

- C221-RET-01: The Pipeline creates no new `staged_claim_output_v5` claim task after this change.
- C221-RET-02: Existing CIR-2.2 ModelRun and ProposedChange records remain read-only Ledger history.
- C221-RET-03: The Pipeline removes the v5 claim prompt from new claim task execution.
- C221-RET-04: The Pipeline removes the v5 schema registry from new claim task execution.

## 4. Proposed Architecture

```text
ContextPlanner
    -> ContextManifest with one bound evidence candidate
    -> ModelTaskRuntime
    -> SemanticDraft
    -> Application Layer
    -> ProposedChange and EvidenceTarget
    -> Ledger
```

The ContextPlanner selects paragraph evidence.

The Pipeline binds the model task to the ContextManifest.

The ModelTaskRuntime returns raw SemanticDraft text.

The Application Layer validates source grounding and creates pending records.

The SQLite Adapter persists the Application Layer commit.

## 5. Key Interactions

```text
Pipeline          ContextPlanner       ModelTaskRuntime       Application Layer       Ledger
   |                     |                     |                     |                 |
   | plan paragraph unit |                     |                     |                 |
   |-------------------->|                     |                     |                 |
   | ContextManifest    |                     |                     |                 |
   |<--------------------|                     |                     |                 |
   | bound task                                |                     |                 |
   |------------------------------------------>|                     |                 |
   | SemanticDraft or abstention               |                     |                 |
   |<------------------------------------------|                     |                 |
   |--------------------------------------------------------------->|                 |
   |                                                                | validate draft  |
   |                                                                |---------------->|
```

## 6. Data Model

The existing ContextManifest stores the bound evidence candidate.

The existing EvidenceCandidate stores authoritative node identity and character bounds.

SemanticDraft is an Application Layer input value.

SemanticDraft has no Domain Core record identity.

The Application Layer creates the existing pending record types.

The Application Layer attaches the derived EvidenceTarget to the ProposedAssertion.

## 7. APIs / Interfaces

The model response uses this public text contract.

```text
outcome: claim
subject: <source-grounded organization name>
relation: <ordinary-language relation label>
object_kind: organization
object: <source-grounded organization name>
```

The literal variant replaces `organization` with `literal`.

The abstention response uses this public text contract.

```text
outcome: abstain
reason: <non-empty reason>
```

The Application Layer parses lines in the specified order.

The Application Layer requires each field key exactly once.

## 8. Behavior & Domain Rules

The Pipeline sends a claim task only for a ready ContextManifest with one bound evidence candidate.

The Application Layer attaches only the bound evidence candidate to a proposed Assertion.

The Application Layer rejects a claim when its subject or object lacks an exact source-text match.

The Application Layer records a valid abstention as an abstained ModelRun.

The Application Layer records malformed or ungrounded model output as an invalid ModelRun.

The Application Layer creates no pending record for an abstained or invalid ModelRun.

The reviewer continues to supply the canonical predicate under CIR-2.2.

## 9. Acceptance Criteria

- AC-C221-01: ContextPlanner tests prove only focus paragraphs enter `direct_prose_evidence_v1`.
- AC-C221-02: ContextPlanner tests prove a `References` list item creates no candidate.
- AC-C221-03: Pipeline tests prove one paragraph creates one task and one bound candidate.
- AC-C221-04: Application tests prove a SemanticDraft creates a ProposedAssertion.
- AC-C221-05: Application tests prove that a model cannot choose a different EvidenceCandidate.
- AC-C221-06: Application tests prove an ungrounded subject or object produces no ProposedChange.
- AC-C221-07: Application tests prove malformed plain-text output creates no ProposedChange.
- AC-C221-08: Application tests prove an abstention creates no ProposedChange.
- AC-C221-09: Adapter tests prove restart-safe EvidenceTarget and ProposedAssertion persistence.
- AC-C221-10: The canonical PDF creates no proposed Assertion with a list-item EvidenceTarget.
- AC-C221-11: The canonical PDF creates ProposedAssertions with paragraph EvidenceTargets.
- AC-C221-12: Formatting, lint, type, Domain, Application, Adapter, and Pipeline checks pass.

## 10. Reference Implementations

- ContextManifest: `packages/application/src/kotekomi_application/context_planning.py`.
- Model archive: `packages/application/src/kotekomi_application/staged_model_extraction.py`.
- ProposedAssertion: `packages/application/src/kotekomi_application/grounded_candidates.py`.
- Atomic SQLite commit: `packages/adapters/src/kotekomi_adapters/sqlite_ledger.py`.

## 11. Constraints and Halt Conditions

CIR-2.2.1 accepts no Assertion.

CIR-2.2.1 creates no predicate vocabulary.

CIR-2.2.1 creates no Actor, Event, Place, or generic Entity draft.

CIR-2.2.1 does not retry a model task.

CIR-2.2.1 does not add runtime JSON-mode or tool-call behavior.

The implementation stops when the canonical PDF proves direct paragraph grounding.

CIR-2.3 defines predicate vocabulary and review decisions after CIR-2.2.1 ships.
