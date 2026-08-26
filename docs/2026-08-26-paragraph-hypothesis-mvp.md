# TDD: Bounded Paragraph Hypothesis MVP

- Status: Accepted
- Program: [Paragraph Hypothesis Development Program](2026-08-26-paragraph-hypothesis-development-program.md)
- Deliverable ID: PHP-1
- Depends on: [CIR-2.2.1 Direct Prose Semantic Draft MVP](2026-08-25-cir-2-2-1-direct-prose-semantic-draft-mvp.md)
- Evaluation corpus: [CIR Evaluation Annotation Packet](2026-08-26-cir-evaluation-annotation-packet.md)

## 1. Context & Problem

A reviewer needs to inspect every supported organization-to-organization relation in one Paragraph.

The current CIR-2.2.1 model task produces only one SemanticDraft for one Paragraph.

A relationship-rich Paragraph contains several distinct direct relations.

The current task can therefore omit valid direct relations even when the model understands them.

PHP-1 will create a bounded Hypothesis batch for one Paragraph.

PHP-1 will retain the existing review path for every verified Atomic hypothesis.

### Terms

**Paragraph** means one authoritative `DocumentNode` with `node_type = paragraph`.

**Source segment** means one ordered, contiguous span inside one Paragraph.

**Atomic hypothesis** means one organization subject, relation label, organization object, and one Source segment.

**Hypothesis batch** means a model response containing zero through eight Atomic hypotheses for one Paragraph.

**Verified hypothesis** means an Atomic hypothesis whose Source-segment label and source mentions pass deterministic checks.

### Primary end-to-end flow

1. The Pipeline selects one eligible Paragraph through the existing direct-prose policy.
2. The Application Layer derives ordered Source segments for the Paragraph.
3. The ModelTaskRuntime receives the Paragraph and its task-local Source-segment labels.
4. The model returns one Hypothesis batch or one abstention.
5. The Application Layer archives and verifies the complete Hypothesis batch.
6. The Application Layer creates one pending ProposedChange for each Verified hypothesis.

## 2. Goals

- A reviewer can inspect zero through eight direct organization hypotheses from one Paragraph.
- Each pending hypothesis resolves to an exact authoritative source span.
- A malformed or ungrounded batch changes no pending candidate state.
- A model response contains no Ledger identifiers or source coordinates.
- A local diagnostic run exposes behavior on selected annotation-packet rows.

## 3. Requirements

### Source segmentation

- PHP1-SEG-01: The Application Layer defines `paragraph_segment_v1`.
- PHP1-SEG-02: The policy creates ordered non-overlapping Source segments for every eligible Paragraph.
- PHP1-SEG-03: The Source segments concatenate to the Paragraph text without omission or addition.
- PHP1-SEG-04: The policy assigns labels `s1` through `sN` in source order.
- PHP1-SEG-05: The policy creates one Source segment equal to the Paragraph when it finds no boundary.
- PHP1-SEG-06: The Pipeline records `paragraph_segment_v1` in the ModelRun execution data.

### Model boundary

- PHP1-MODEL-01: The Pipeline sends one eligible Paragraph and its Source segments to one model task.
- PHP1-MODEL-02: The Pipeline pins `paragraph_hypothesis_mvp_v3` for the task prompt.
- PHP1-MODEL-03: The task prompt identifies Source segments by task-local labels.
- PHP1-MODEL-04: The task prompt permits at most eight claim lines.
- PHP1-MODEL-05: The task prompt requires one abstention line when it proposes no claim line.
- PHP1-MODEL-06: The task prompt requests only organization-to-organization relations.
- PHP1-MODEL-07: The task prompt contains no canonical identifiers, source offsets, page regions, or storage paths.
- PHP1-MODEL-08: The Application Layer archives raw model output before it parses the Hypothesis batch.

### Verification and normalization

- PHP1-VERIFY-01: The Application Layer accepts only claim lines that use one declared Source-segment label.
- PHP1-VERIFY-02: The Application Layer requires the subject and object in the declared Source segment.
- PHP1-VERIFY-03: The Application Layer rejects a batch with more than eight claim lines.
- PHP1-VERIFY-04: The Application Layer rejects a batch that mixes an abstention line with a claim line.
- PHP1-VERIFY-05: The Application Layer rejects a batch with malformed, unknown-label, or ungrounded lines.
- PHP1-VERIFY-06: The Application Layer records a rejected batch as `invalid_output`.
- PHP1-VERIFY-07: The Application Layer creates no ProposedChange from a rejected batch.
- PHP1-VERIFY-08: The Application Layer records every duplicate valid claim line in the ModelRun outcome.
- PHP1-VERIFY-09: The Application Layer creates one direct EvidenceTarget from the declared Source segment.
- PHP1-VERIFY-10: The Application Layer normalizes both source mentions through the CIR-2.1 Organization proposal contract.
- PHP1-VERIFY-11: The Application Layer creates one pending ProposedChange for each unique Verified hypothesis.
- PHP1-VERIFY-12: The Application Layer retains the relation text as the existing `relation_label`.
- PHP1-VERIFY-13: The existing CIR-2.2 review path supplies a canonical predicate before acceptance.

### Local diagnostic run

- PHP1-DIAG-01: The local diagnostic run processes `AD-06`, `AD-13`, `AI-06`, `AI-14`, `CS-05`, and `CS-10`.
- PHP1-DIAG-02: The run records each raw model response, ModelRun outcome, and created ProposedChange ID.
- PHP1-DIAG-03: The run records `fixture_missing` for an unavailable deposited PDF.
- PHP1-DIAG-04: The run reports every selected row as complete, abstained, invalid, or fixture missing.
- PHP1-DIAG-05: The run creates no release-quality threshold.

## 4. Proposed Architecture

```text
ContextPlanner
    -> Paragraph and Source segments
    -> ModelTaskRuntime
    -> Hypothesis batch
    -> Application Layer verification
    -> ProposedChanges and EvidenceTargets
    -> Ledger
```

The ContextPlanner selects the Paragraph.

The Application Layer derives Source segments and verifies model text.

The ModelTaskRuntime returns one raw text response.

The Application Layer creates pending review records.

The SQLite Adapter persists the atomic commit.

## 5. Key Interactions

```text
Pipeline       Application Layer       ModelTaskRuntime       Ledger
   |                   |                      |                |
   | select Paragraph  |                      |                |
   |------------------>| derive segments      |                |
   |                   | task                 |                |
   |                   |--------------------->|                |
   |                   | raw batch            |                |
   |                   |<---------------------|                |
   |                   | archive and verify   |                |
   |                   |-------------------------------------->|
```

## 6. Data Model

The existing DocumentRepresentationBundle and DocumentNode remain authoritative source records.

The existing ContextManifest remains the source context record.

`SourceSegment` is a new Application Layer value with a task-local label and exact character bounds.

KoteKomi rederives each SourceSegment from the pinned policy and authoritative Paragraph.

`HypothesisBatch` is a new Application Layer input value that contains claim lines or one abstention line.

The existing ModelRun archives the raw response and terminal outcome.

The existing ModelRun records the pinned Source-segment policy.

The existing EvidenceTarget points to the exact Source segment.

The existing ProposedAssertion and ProposedChange retain each Verified hypothesis for review.

PHP-1 creates no accepted Assertion, Relationship, Actor, Event, Place, or generic Entity.

## 7. APIs / Interfaces

The model response uses one of these text contracts.

```text
claim: <sN> | <organization subject> | <relation label> | <organization object>
```

The model returns one claim line for each Atomic hypothesis.

The model returns no more than eight claim lines.

The abstention response uses this text contract.

```text
abstain: <non-empty reason>
```

The Application Layer treats a response as one atomic Hypothesis batch.

The Application Layer parses no repair, fallback, or partial-acceptance format.

## 8. Behavior & Domain Rules

The Pipeline sends a task only for a ready ContextManifest with one eligible Paragraph.

The Application Layer derives an EvidenceTarget from the declared Source segment only.

The Application Layer preserves every raw response and terminal ModelRun outcome.

The Application Layer creates no pending record from an abstention.

The Application Layer creates no pending record from an invalid batch.

The Application Layer retains one pending record for each unique Verified hypothesis.

The reviewer accepts, rejects, or edits each ProposedChange through the existing review flow.

## 9. Acceptance Criteria

- AC-PHP1-01: Application tests prove deterministic Source-segment labels and exact reconstruction of Paragraph text.
- AC-PHP1-02: Application tests prove one Paragraph produces three Verified hypotheses and three ProposedChanges.
- AC-PHP1-03: Application tests prove each ProposedChange has a direct EvidenceTarget for its declared Source segment.
- AC-PHP1-04: Application tests prove an unknown segment label creates no ProposedChange.
- AC-PHP1-05: Application tests prove an ungrounded subject or object creates no ProposedChange.
- AC-PHP1-06: Application tests prove a malformed, mixed, or oversized batch creates no ProposedChange.
- AC-PHP1-07: Application tests prove duplicate claim lines create one ProposedChange and a visible duplicate record.
- AC-PHP1-08: Adapter tests prove raw response, EvidenceTarget, and ProposedChange persistence survive restart.
- AC-PHP1-09: Pipeline tests prove the model receives only source text and task-local labels.
- AC-PHP1-10: The local diagnostic run accounts for all six named packet rows without silent skip.
- AC-PHP1-11: Formatting, lint, type, Application, Adapter, and Pipeline checks pass.

## 10. Reference Implementations

- Paragraph context: `packages/application/src/kotekomi_application/context_planning.py`.
- Direct prose task: `packages/application/src/kotekomi_application/staged_model_extraction.py`.
- Grounded candidate commit: `packages/application/src/kotekomi_application/grounded_candidates.py`.
- Model response archive: `packages/application/src/kotekomi_application/staged_model_extraction.py`.
- Atomic persistence: `packages/adapters/src/kotekomi_adapters/sqlite_ledger.py`.

## 11. Constraints and Halt Conditions

PHP-1 creates only organization-to-organization candidates.

PHP-1 accepts one supporting Source segment per Atomic hypothesis.

PHP-1 does not define corpus quality thresholds.

PHP-1 does not add semantic embeddings, a vector database, a graph traversal path, or a prompt-construction service.

PHP-1 does not add retries, predicate vocabulary, Actor, Event, Place, literal, or generic Entity candidates.

The implementation stops after the local diagnostic run produces replayable outcomes for the six named rows.
