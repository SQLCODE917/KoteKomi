# TDD: HP-8 Semantic Support Batching

- Status: Rejected after canonical evaluation
- Program: [Hybrid Intelligence Extraction Pipeline](2026-09-01-hybrid-intelligence-extraction-pipeline.md)
- Deliverable ID: HP-8.2
- Depends on: [HP-8 Hybrid Document Orchestration](2026-09-03-hybrid-document-orchestration.md)
- Baseline: `3a914f6575009d5119981626287c8cec42477eac`

## Context & Problem

HP-8 asks Qwen2.5 to judge each SemanticStatement in a separate model task.

The canonical HP-8 run created 130 source-support tasks.

Those tasks consumed 597.7 seconds of measured model execution time.

Each task repeats one authoritative EvidenceTarget while changing only the governed SemanticStatement.

**Support Batch** means one bounded model task for one through four SemanticStatements that share one EvidenceTarget.

**Support Item** means one statement label, support outcome, and reason.

### Primary end-to-end flow

1. HP-6 constructs typed SemanticStatements from governed event semantics.
2. The Application Layer groups statements by exact EvidenceTarget identity.
3. The Application Layer orders and partitions each group into Support Batches.
4. Qwen2.5 judges every labeled statement against the shared authoritative evidence.
5. The Application Layer validates the complete response.
6. The Application Layer creates one SemanticSupportJudgment and trace per valid Support Item.
7. The evaluator compares performance, meaning, and provenance with the HP-8 baseline.

## Goals

- A user receives the same or better reviewable intelligence with fewer model requests.
- One authoritative EvidenceTarget is supplied once for multiple bounded support judgments.
- A reviewer can inspect the exact input and output for every Support Batch.
- Every SemanticSupportJudgment retains candidate-level source and model lineage.
- A malformed batch is visible and creates no support judgment.
- Repeated ingestion reuses completed paragraph evidence without a model request.

## Requirements

### Batch planning

- HSB-PLN-01: The Application Layer groups only SemanticStatements with the same EvidenceTarget ID.
- HSB-PLN-02: The Application Layer orders statements by deterministic semantic identity.
- HSB-PLN-03: The Application Layer assigns labels `q1` through `qN` in batch order.
- HSB-PLN-04: One Support Batch contains at most four statements.
- HSB-PLN-05: One Support Batch supplies its exact EvidenceTarget once.
- HSB-PLN-06: The Application Layer partitions statements before the model call.
- HSB-PLN-07: The Application Layer reduces a batch when its rendered input exceeds the model context.
- HSB-PLN-08: One statement that exceeds the model context creates a typed support gap without a model call.
- HSB-PLN-09: The HP-8 policy pins the batch policy version and item limit.
- HSB-PLN-10: Normalization and role-completion retain their HP-8 prompts and schemas unchanged.
- HSB-PLN-11: Support batching uses a separate pinned prompt, schema, and ContextManifest.

### Model boundary

- HSB-MOD-01: Model input contains one exact EvidenceTarget, every statement label, statement text, and governed definition.
- HSB-MOD-02: Model input contains no source text outside the shared EvidenceTarget.
- HSB-MOD-03: Model output contains one Support Item per supplied label.
- HSB-MOD-04: Each Support Item contains one existing SupportOutcome and one non-empty reason.
- HSB-MOD-05: The parser requires Support Items in supplied label order.
- HSB-MOD-06: The parser rejects a missing, duplicate, reordered, or unknown label.
- HSB-MOD-07: The parser rejects unknown fields or SupportOutcome values.
- HSB-MOD-08: One ExtractionTask identifies every SemanticStatement in the Support Batch.
- HSB-MOD-09: One ModelRun stores the complete raw model response.
- HSB-MOD-10: One ModelRun records the parsed item count.

### Result construction

- HSB-RES-01: The Application Layer creates one SemanticSupportJudgment per valid Support Item.
- HSB-RES-02: Each judgment references the shared ExtractionTask and ModelRun.
- HSB-RES-03: The Application Layer creates one ExtractionStageTrace per SemanticStatement.
- HSB-RES-04: Each trace references the shared ExtractionTask and ModelRun.
- HSB-RES-05: Each trace records the statement label, exact EvidenceTarget, statement, and parsed judgment.
- HSB-RES-06: A malformed response invalidates the complete Support Batch.
- HSB-RES-07: A malformed Support Batch creates no SemanticSupportJudgment.
- HSB-RES-08: The Application Layer does not retry or split a malformed Support Batch.
- HSB-RES-09: The ModelRun and traces retain the malformed response and affected statement IDs.
- HSB-RES-10: HP-8 records every affected statement as an accounted support gap.

### Evaluation

- HSB-EVL-01: The evaluator records complete rendered inputs and raw outputs for baseline and candidate runs.
- HSB-EVL-02: The evaluator records call count, elapsed time, latency, and token counts by task type.
- HSB-EVL-03: The evaluator compares statements by authoritative source and semantic content, excluding execution-derived IDs.
- HSB-EVL-04: The evaluator compares every support outcome and reason.
- HSB-EVL-05: The evaluator reports every downstream event, claim, judgment, and proposal difference.
- HSB-EVL-06: Every semantic difference receives a reviewed comparison class and rationale.
- HSB-EVL-07: Acceptance requires zero regressions and zero inconclusive differences.
- HSB-EVL-08: Acceptance requires all HP-1 contextual Gold expectations.
- HSB-EVL-09: Acceptance requires all seven approved HP-7 Gold events.
- HSB-EVL-10: Acceptance requires the known false event to produce no proposal.
- HSB-EVL-11: Acceptance requires zero accepted intelligence records before review.
- HSB-EVL-12: Acceptance requires complete source and model lineage for every proposal.
- HSB-EVL-13: Acceptance requires fewer source-support model calls.
- HSB-EVL-14: Acceptance requires lower aggregate source-support elapsed time.
- HSB-EVL-15: The evaluator reports per-EvidenceTarget and whole-ingestion timing as descriptive evidence.

## Proposed Architecture

```text
SemanticStatements grouped by EvidenceTarget
                    |
                    v
              Batch Planner
                    |
                    v
                 Qwen2.5
                    |
                    v
       Complete-response Validator
                    |
                    v
SemanticSupportJudgments + candidate-level Stage Traces
```

The Application Layer owns grouping, ordering, partitioning, validation, and result construction.

The ModelRuntime Adapter executes one complete Support Batch.

The Ledger stores immutable ExtractionTasks and ModelRuns.

The Archive stores raw responses and terminal HP-6 evidence.

The evaluator owns timing and semantic comparison; it does not alter extraction evidence.

## Data Model

`SemanticSupportModelJudgmentBatch` is a new Application Layer DTO.

It contains one through four ordered labeled support judgments.

The existing `SemanticStatement`, `EvidenceTarget`, `SemanticSupportJudgment`, `ExtractionTask`, `ModelRun`, and `ExtractionStageTrace` contracts remain authoritative for their current roles.

HP-8.2 adds no accepted Domain Core record.

## APIs / Interfaces

The task type remains `hybrid_semantic_source_support`.

The batch schema ID and output contract version are `hybrid_semantic_support_batch_text_v1`.

Each Support Item uses this fixed field order:

```text
statement: qN
outcome: directly_supported|partially_supported|unsupported|contradicted|ambiguous
reason: <one non-empty sentence>
```

The output concatenates Support Items without headings or commentary.

It may use either no blank line or one blank line between complete Support Items.

The public `kotekomi ingest` command does not change.

## Behavior & Domain Rules

Support is judged independently for every SemanticStatement.

A shared model execution does not merge SemanticStatements or SemanticSupportJudgments.

The exact EvidenceTarget and deterministic statement construction remain KoteKomi-owned.

Model output remains untrusted derived evidence.

The reviewer remains the only actor that accepts intelligence into the Ledger.

A changed prompt, schema, policy, item limit, EvidenceTarget, or statement set creates a new task fingerprint.

Historical HP-8 and rejected HP-8.1 experiment evidence remains immutable.

## Acceptance Criteria

- AC-HSB-01: Application tests prove HSB-PLN-01 through HSB-PLN-11.
- AC-HSB-02: Parser tests prove HSB-MOD-03 through HSB-MOD-07.
- AC-HSB-03: Application tests prove HSB-MOD-08 through HSB-RES-05.
- AC-HSB-04: Negative tests prove HSB-RES-06 through HSB-RES-10.
- AC-HSB-05: Archive tests prove exact raw-output and HP-6 Preview replay.
- AC-HSB-06: Pipeline tests prove public ingestion and zero-call paragraph reuse.
- AC-HSB-07: The canonical evaluator proves HSB-EVL-01 through HSB-EVL-15.
- AC-HSB-08: The canonical run reduces 130 source-support calls to at most 37.
- AC-HSB-09: Formatting, Ruff, Pyright, focused tests, and full pytest pass.

## Reference Implementations

- HP-6 orchestration: `packages/application/src/kotekomi_application/hybrid_event_semantics_preview.py`
- Model output: `packages/application/src/kotekomi_application/hybrid_event_semantics_model_output.py`
- Model execution: `packages/application/src/kotekomi_application/staged_model_extraction.py`
- Immutable evidence: `packages/adapters/src/kotekomi_adapters/local_archive.py`
- Evaluation: `scripts/compare_hp8_compaction.py`

## Constraints and Halt Conditions

Stop rollout when one established Gold result regresses.

Stop rollout when one semantic difference remains inconclusive.

Stop rollout when one baseline-supported statement loses its support judgment.

Stop rollout when measured source-support elapsed time does not improve.

## Design Experiments

An eight-item targeted batch reduced 26 calls to four, but one response omitted its eighth result and one previously supported statement changed to `unsupported`.

Eight-item batching is rejected.

A four-item targeted batch reduced the same 26 calls to seven and reduced input tokens from 11,923 to 3,897.

It retained all 26 judgments as `directly_supported`, produced no support diagnostics, and reduced measured support time from 115,074 milliseconds to 113,433 milliseconds.

That targeted timing difference is too small to establish a repeatable improvement by itself.

The complete canonical replay is therefore the acceptance authority for both semantic equivalence and performance.

## Evaluation Outcome

The full canonical run reduced source-support calls from 130 to 41.

Measured source-support time changed from 597,698 milliseconds to 597,616 milliseconds, a reduction of 82 milliseconds, or approximately 0.014 percent.

That difference is not a meaningful repeatable performance improvement.

More importantly, the run changed 11 paragraph-level semantic outputs.

Among statements present in both runs, six support outcomes changed, including established `directly_supported` statements that became `unsupported`.

The candidate also contained 19 baseline statements with no matching candidate judgment and 32 candidate statements absent from the baseline because unchanged upstream model stages varied across the two complete ingestions.

Pending ProposedChanges fell from 115 to 107.

The unchanged upstream variation means whole-ingestion comparisons cannot isolate every statement-set difference to support batching, but the changed support outcomes for identical EvidenceTargets and SemanticStatements are sufficient to falsify monotonic quality.

The candidate therefore fails HSB-EVL-07, HSB-EVL-14, AC-HSB-07, and the halt conditions.

The production support path was restored to the accepted HP-8 behavior.

The evaluator, complete data-in/data-out artifacts, targeted experiments, and this rejection record remain available to guide a future optimization that preserves statement independence.
