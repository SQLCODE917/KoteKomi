# TDD: HP-8 Mention Interpretation Batching

- Status: Rejected after canonical evaluation
- Program: [Hybrid Intelligence Extraction Pipeline](2026-09-01-hybrid-intelligence-extraction-pipeline.md)
- Deliverable ID: HP-8.1
- Depends on: [HP-8 Hybrid Document Orchestration](2026-09-03-hybrid-document-orchestration.md)
- Baseline: `3a914f6575009d5119981626287c8cec42477eac`

## Context & Problem

HP-8 asks Qwen2.5 to interpret each MentionCandidate in a separate model task.

The canonical HP-8 run created 171 MentionInterpretation tasks across 19 paragraph contexts.

Those tasks consumed 2,141.6 seconds of measured model execution time.

Each task supplied about 1,003 input tokens and produced about 30 output tokens on average.

The repeated paragraph context dominates this stage.

**Candidate Batch** means one through four ordered MentionCandidates from one paragraph context.

**Dimension Batch** means one model task that classifies one dimension for one Candidate Batch.

**Dimension Classification** means one task-local candidate label and one enum value.

**Semantic Comparison** means a comparison that excludes execution-derived record identifiers.

**Semantic Adjudication** means a reviewed `equivalent`, `improvement`, or `regression` decision.

### Primary end-to-end flow

1. The Application Layer orders selected MentionCandidates within one paragraph context.
2. The Application Layer partitions the MentionCandidates into Candidate Batches.
3. Qwen2.5 classifies one ontology dimension for each Candidate Batch per model task.
4. The Application Layer validates all three Dimension Batches.
5. The Application Layer joins three Dimension Classifications into each MentionInterpretation.
6. The evaluator compares performance, meaning, and provenance with the HP-8 baseline.

## Goals

- A user receives the same or better reviewable intelligence with fewer model requests.
- A reviewer can inspect each Dimension Batch input and output.
- A reviewer can trace each MentionInterpretation through its three model executions.
- A malformed Dimension Batch remains visible and creates no interpretation for its Candidate Batch.
- A repeated ingestion reuses every completed paragraph without a model request.

## Requirements

### Batch planning

- HMB-PLN-01: The Application Layer orders candidates by SourceSegment order and source offset.
- HMB-PLN-02: The Application Layer uses the candidate ID as the final order key.
- HMB-PLN-03: The Application Layer assigns labels `c1` through `cN` in batch order.
- HMB-PLN-04: One Candidate Batch contains at most four candidates.
- HMB-PLN-05: One Candidate Batch uses one paragraph context.
- HMB-PLN-06: The Application Layer partitions candidates before the model call.
- HMB-PLN-07: The Application Layer reduces a batch when its rendered input exceeds the model context.
- HMB-PLN-08: One candidate that exceeds the model context produces the existing typed context failure.
- HMB-PLN-09: The HP-8 policy pins the batch policy version and item limit.
- HMB-PLN-10: Mention proposal retains its HP-8 prompt and schema unchanged.
- HMB-PLN-11: Interpretation uses a separate pinned ContextManifest, prompt, and schema so batching cannot change proposal behavior.

### Model boundary

- HMB-MOD-01: The model input contains every label, MentionCandidate literal, and source label.
- HMB-MOD-02: Each model input contains guidance for exactly one interpretation dimension.
- HMB-MOD-03: The Application Layer creates three Dimension Batches per Candidate Batch.
- HMB-MOD-04: The three dimensions are referentiality, contextual kind, and discourse role.
- HMB-MOD-05: Each model output contains one Dimension Classification per supplied label.
- HMB-MOD-05A: The parser requires Dimension Classifications in supplied label order.
- HMB-MOD-06: The parser rejects a missing, duplicate, reordered, or unknown label.
- HMB-MOD-07: The parser rejects an unknown field value or support label.
- HMB-MOD-08: Each ExtractionTask identifies every candidate in its Candidate Batch.
- HMB-MOD-09: Each ModelRun stores one complete Dimension Batch response.
- HMB-MOD-10: Each ModelRun records its dimension and parsed item count.

### Result construction

- HMB-RES-01: The Application Layer creates one MentionInterpretation per valid candidate label.
- HMB-RES-02: Each MentionInterpretation references all three Dimension Batch ModelRuns.
- HMB-RES-03: The Application Layer creates one ExtractionStageTrace per candidate.
- HMB-RES-04: Each trace references all three ExtractionTasks and ModelRuns.
- HMB-RES-05: Each trace records the candidate label and parsed interpretation fields.
- HMB-RES-06: A malformed Dimension Batch invalidates the complete Candidate Batch.
- HMB-RES-07: An invalid Candidate Batch creates no MentionInterpretation.
- HMB-RES-08: The Application Layer does not retry or split an invalid Candidate Batch.
- HMB-RES-09: The ModelRuns and traces retain each response and affected candidate ID.
- HMB-RES-10: HP-8 records each affected candidate as an accounted interpretation gap.
- HMB-RES-11: The Application Layer assigns each candidate SourceSegment as interpretation support.

### Evaluation

- HMB-EVL-01: The evaluator records complete rendered inputs and raw outputs for both runs.
- HMB-EVL-02: The evaluator records call counts, elapsed time, latency, and token counts by task type.
- HMB-EVL-03: The evaluator compares each result through its authoritative source identity.
- HMB-EVL-04: The evaluator compares every interpretation field and support SourceSegment.
- HMB-EVL-05: The evaluator reports every downstream event, claim, judgment, and proposal difference.
- HMB-EVL-06: The evaluator classifies each semantic difference with the reviewed comparison classes.
- HMB-EVL-06A: The evaluator treats each unreviewed semantic difference as `inconclusive`.
- HMB-EVL-06B: Each Semantic Adjudication identifies the paragraph text digest and ordinal.
- HMB-EVL-06C: Each Semantic Adjudication records a non-empty rationale.
- HMB-EVL-07: The evaluator requires zero candidate regressions and zero inconclusive differences.
- HMB-EVL-08: The evaluator requires all HP-1 contextual Gold expectations.
- HMB-EVL-09: The evaluator requires all seven approved HP-7 Gold events.
- HMB-EVL-10: The evaluator requires the known false event to produce no proposal.
- HMB-EVL-11: The evaluator requires zero accepted intelligence records before review.
- HMB-EVL-12: The evaluator requires complete source and model lineage for every proposal.
- HMB-EVL-13: The evaluator requires lower aggregate MentionInterpretation elapsed time.
- HMB-EVL-14: The evaluator reports the fraction of matched contexts that execute faster.
- HMB-EVL-15: The evaluator requires fewer MentionInterpretation model calls.
- HMB-EVL-16: The evaluator reports complete ingestion wall time as descriptive evidence.

## Proposed Architecture

```text
Paragraph Context -> Candidate Planner -> 3 Dimension Batches
                            |                     |
                            v                     v
                    ExtractionTasks          Qwen2.5
                            \                     /
                             v                   v
                     Application Validator + Join
                                  |
                                  v
                   MentionInterpretations + Stage Traces
```

The Application Layer owns ordering, partitioning, validation, and result construction.

The ModelRuntime Adapter executes one complete Dimension Batch.

The Ledger stores each ExtractionTask and ModelRun.

The Archive stores each raw model response and terminal HybridExtractionPreview.

The evaluator owns performance measurement and Semantic Comparison.

## Key Interactions

```text
Application   Ledger   Qwen2.5   Archive   Evaluator
     | plan candidate batch|        |          |
     |----------->|        |        |          |
     | execute three tasks -->|       |          |
     |<-----------------------|       |          |
     | store tasks and runs ->|       |          |
     | archive raw outputs ---------->|          |
     | validate, join, create records |          |
     |----------------------------------------->|
     |<------------ strict comparison ----------|
```

## Data Model

`MentionDimensionDraftBatch` is a new Application Layer DTO.

`MentionDimensionDraftBatch` contains one through four ordered Dimension Classifications.

The existing MentionInterpretation remains the typed result for one candidate.

Each ExtractionTask stores every Candidate Batch ID and one dimension input.

Each ModelRun stores one response digest, raw-output reference, and execution receipt.

The existing ExtractionStageTrace retains one candidate-level decision.

HP-8.1 adds no accepted Domain Core record.

## APIs / Interfaces

The model task uses task type `hybrid_mention_interpretation`.

Mention proposal retains schema ID `hybrid_mention_task_text_v1`.

Mention interpretation uses these schema IDs:

- `hybrid_mention_referentiality_batch_text_v1`
- `hybrid_mention_contextual_kind_batch_text_v1`
- `hybrid_mention_discourse_role_batch_text_v1`

Each Dimension Classification uses this fixed shape:

```text
classification: cN | <allowed dimension value>
```

The model output concatenates Dimension Classifications without headings or commentary.

It can use no blank line or one blank line between Dimension Classifications.

The public `kotekomi ingest` command does not change.

## Behavior & Domain Rules

The Dimension Batch policy preserves candidate-level semantic independence.

The Application Layer joins dimensions by the ordered candidate label.

The Application Layer derives support from each candidate SourceSegment.

Shared model execution does not merge MentionInterpretation records.

The parser validates the complete response before the Application Layer creates any result.

The Application Layer treats model output as untrusted derived evidence.

The reviewer remains the only actor that accepts intelligence into the Ledger.

A changed prompt, schema, policy, item limit, or candidate set creates a new task fingerprint.

Historical HP-8 evidence remains immutable.

## Acceptance Criteria

- AC-HMB-01: Application tests prove HMB-PLN-01 through HMB-PLN-11.
- AC-HMB-02: Parser tests prove HMB-MOD-03 through HMB-MOD-07.
- AC-HMB-03: Application tests prove HMB-MOD-08 through HMB-RES-05.
- AC-HMB-04: Negative tests prove HMB-RES-06 through HMB-RES-10.
- AC-HMB-05: Archive tests prove exact raw-output and Preview replay.
- AC-HMB-06: Pipeline tests prove public ingestion and zero-call paragraph reuse.
- AC-HMB-07: The canonical evaluator proves HMB-EVL-01 through HMB-EVL-16.
- AC-HMB-08: The canonical run reduces 171 interpretation calls to at most 150.
- AC-HMB-09: Formatting, Ruff, Pyright, focused tests, and full pytest pass.

## Reference Implementations

- Model execution: follow `packages/application/src/kotekomi_application/staged_model_extraction.py`.
- Mention interpretation: follow `packages/application/src/kotekomi_application/hybrid_mention_preview.py`.
- Immutable evidence: follow `packages/adapters/src/kotekomi_adapters/local_archive.py`.
- Evaluation: follow `scripts/verify_hp8_document_orchestration.py`.

## Constraints and Halt Conditions

Stop rollout when one established Gold result regresses.

Stop rollout when one semantic difference remains inconclusive.

Stop rollout when one baseline-successful candidate becomes an interpretation gap.

Stop rollout when the measured stage does not produce a repeatable elapsed-time improvement.

## Evaluation Outcome

The implementation experiment is preserved as evidence but must not become production behavior.

The four-candidate, three-dimension design reduced the canonical MentionInterpretation elapsed time from 2,141,620 milliseconds to 1,056,515 milliseconds and reduced model calls from 171 to 162.

It also reduced complete paragraphs from 19 to 17 and changed established candidate interpretations.

A follow-up single-candidate compact-output experiment reduced one difficult paragraph from 476,772 milliseconds to 383,788 milliseconds, but changed `Trump administration` from `actor` to `participant` and `Biden administration` from `origin` to `participant`.

Those are semantic regressions under HMB-EVL-07.

The production mention path was therefore restored to the accepted HP-8 behavior.

The evaluator, complete data-in/data-out evidence, and this rejection record remain useful for future optimization work.
