# TDD: CEA-1.13 Part-Wise Residual Ownership

- Status: Accepted for implementation; production inactive
- Deliverable ID: `CEA-1.13`
- Program:
  [Competitive Event Attachment Program](2026-09-18-competitive-event-attachment-program.md)
- Predecessor:
  [CEA-1.12 Runtime-Calibrated Budget-Bounded Output](2026-09-20-competitive-attachment-runtime-calibrated-termination.md)

## 1. Context & Problem

CEA-1.12 established a stable budget-bound answer mechanism for ten Residual Ownership cases.

The whole-Candidate task answered seven of ten corrected Gold cases correctly.

Three failures remain.

Each failed Candidate contains two disjoint Candidate Remainder parts.

The whole-Candidate task asks Qwen to judge both parts and aggregate them in one answer.

That task conflates local semantic judgment with aggregation.

KoteKomi can ask one semantic question per exact part and aggregate the answers deterministically.

### Terms

**Remainder Part** means one exact Candidate range outside the Target Event range.

**Substantive Part** means a Remainder Part that contains one Unicode letter or number.

**Structural Part** means a Remainder Part that contains no Unicode letter or number.

**Whole Arm** means one judgment over all Candidate Remainder parts.

**Part Arm** means one independent judgment for each Substantive Part.

**Part Aggregate** means KoteKomi's Candidate-level answer from all Part Arm answers.

### Hypothesis

> Independent Remainder Part judgments improve corrected Residual Ownership accuracy without losing a correct Gold-positive or Gold-negative Whole Arm answer.

### Primary flow

1. KoteKomi validates the complete CEA-1.12 package and its Claude review.
2. KoteKomi derives every Remainder Part from authoritative source ranges.
3. KoteKomi classifies each Remainder Part as Substantive Part or Structural Part.
4. Qwen judges every Whole Arm case and every Substantive Part twice.
5. KoteKomi treats each Structural Part as source-preserving connective text.
6. KoteKomi builds each Part Aggregate from exact finite answers.
7. KoteKomi compares both arms with corrected Candidate-level Gold.

CEA-1.13 creates experimental evidence only.

## 2. Goals

- Expose whether one Remainder Part causes each incorrect whole-Candidate answer.
- Move Candidate-level aggregation from Qwen into deterministic KoteKomi code.
- Preserve exact model input and raw output for every judgment.
- Measure semantic quality separately from output-contract validity.

## 3. Requirements

### Source and Gold evidence

- CEA113-EVD-01: The Pipeline must validate the complete CEA-1.12 package.
- CEA113-EVD-02: The Pipeline must require the completed CEA-1.12 Claude review.
- CEA113-EVD-03: The Pipeline must reuse the exact ten CEA-1.12 Residual Ownership tasks.
- CEA113-EVD-04: The Pipeline must preserve the corrected eight-positive and two-negative Gold inventory.
- CEA113-EVD-05: Gold must remain outside every model input.
- CEA113-EVD-06: Every direct input must carry a file digest.
- CEA113-EVD-07: A predecessor repository file that changed after its run must validate against the source revision sealed in that predecessor handoff.

### Deterministic part construction

- CEA113-PRT-01: KoteKomi must derive every Remainder Part from authoritative source ranges.
- CEA113-PRT-02: Remainder Parts must remain ordered and non-overlapping.
- CEA113-PRT-03: Remainder Parts and the Target Event must reconstruct the Candidate exactly.
- CEA113-PRT-04: KoteKomi must classify a Remainder Part from its exact characters only.
- CEA113-PRT-05: KoteKomi must send each Substantive Part to Qwen independently.
- CEA113-PRT-06: KoteKomi must retain each Structural Part without a model call.
- CEA113-PRT-07: The sealed ten cases must produce eighteen exact Remainder Parts.
- CEA113-PRT-08: Seventeen Parts must be Substantive and one Part must be Structural.

### Model task

- CEA113-MOD-01: The Whole Arm must use the CEA-1.12 prompt and renderer.
- CEA113-MOD-02: The Part Arm prompt must define Passage, Candidate, Target Event, and Remainder Part.
- CEA113-MOD-03: The Part Arm must ask whether one Remainder Part belongs to the Target Event fact.
- CEA113-MOD-04: Qwen must return exactly one `Y`, `N`, or `U` character.
- CEA113-MOD-05: Both arms must use temperature `0`, seed `17`, and ten alternatives.
- CEA113-MOD-06: Both arms must request two output tokens.
- CEA113-MOD-07: Both arms must declare `frequency_penalty` as `0.0`.
- CEA113-MOD-08: Both arms must execute two repetitions.
- CEA113-MOD-09: Both arms must use one model identity and one runtime contract.
- CEA113-MOD-10: Validation tasks must remain unexecuted.
- CEA113-MOD-11: The experiment must preserve fifty-four model executions.

### Aggregation

- CEA113-AGG-01: All `Y` Part answers must produce Candidate answer `Y`.
- CEA113-AGG-02: One or more `N` Part answers must produce Candidate answer `N`.
- CEA113-AGG-03: One or more unresolved or `U` answers without an `N` must produce `U`.
- CEA113-AGG-04: Structural Parts must not change the Part Aggregate.
- CEA113-AGG-05: KoteKomi must preserve every Part answer before aggregation.

### Evaluation

- CEA113-EVL-01: The evaluator must score Candidate answers at exact occurrence level.
- CEA113-EVL-02: The evaluator must report strict raw-output validity separately.
- CEA113-EVL-03: The evaluator must report Whole Arm and Part Arm accuracy.
- CEA113-EVL-04: The evaluator must report positive and negative accuracy by arm.
- CEA113-EVL-05: The evaluator must report each recovery and regression.
- CEA113-EVL-06: The evaluator must report repetition stability by case and part.
- CEA113-EVL-07: `supported` requires complete evidence and stable repetitions.
- CEA113-EVL-08: `supported` requires higher Part Arm Candidate accuracy.
- CEA113-EVL-09: `supported` requires at least one recovered Whole Arm error.
- CEA113-EVL-10: `supported` requires zero regressions from correct Whole Arm answers.
- CEA113-EVL-11: `supported` requires both Gold-negative cases to produce `N`.
- CEA113-EVL-12: `mixed` requires one recovery with a failed safety gate.
- CEA113-EVL-13: `falsified` requires complete evidence without higher Candidate accuracy.
- CEA113-EVL-14: `inconclusive` requires missing or unresolved evidence.

### Evidence package

- CEA113-PKG-01: The package must preserve preflight, report, review, handoff, run, and status files.
- CEA113-PKG-02: The review must show exact source, Candidate, Target Event, and Remainder Parts.
- CEA113-PKG-03: The review must show every exact model input and raw output.
- CEA113-PKG-04: The review must show Whole Arm and Part Aggregate comparisons.
- CEA113-PKG-05: The handoff must cite every direct file digest and report fingerprint.
- CEA113-PKG-06: The package must report zero ProposedChanges and accepted Ledger writes.

## 4. Proposed Architecture

```text
sealed CEA-1.12 tasks
          |
          v
exact Remainder Part builder
       /             \
      v               v
Whole Arm          Part Arm
one answer      one answer per part
      \               /
       v             v
 deterministic Part Aggregate
          |
          v
 occurrence-level comparison
```

The Application Layer owns exact part construction and aggregation.

The ModelRuntime Port owns bounded Qwen execution.

The Pipeline owns evidence validation, evaluation, and review rendering.

The disposable runner composes the experiment.

The human starts and monitors the live run.

## 5. Key Interactions

```text
Human       Runner       KoteKomi       Qwen
  |            |             |            |
  |-- start -->|             |            |
  |            |-- derive -->|            |
  |            |-- whole ---------------->|
  |            |<------------- Y/N/U -----|
  |            |-- each part ------------>|
  |            |<------------- Y/N/U -----|
  |            |-- aggregate ->|           |
  |<-- paths --|             |            |
```

## 6. Data Model

CEA-1.13 adds experimental Application DTOs for Part tasks, observations, cases, and reports.

Each Part task binds one exact Remainder Part to its parent Residual Ownership task.

CEA-1.13 adds no Domain Core record or Ledger schema.

## 7. APIs / Interfaces

The runner accepts one complete CEA-1.12 root and one absent experiment root.

Preparation writes a digest-bound preflight before model execution.

Execution writes one typed record for each model task and repetition.

Finalization writes one report, review, handoff, and status record.

## 8. Behavior & Domain Rules

- Exact source characters remain authoritative.
- KoteKomi performs every range operation and aggregation.
- Qwen answers one semantic question about one supplied range.
- KoteKomi maps each answer to the supplied exact occurrence.
- Probability evidence cannot repair invalid raw output.
- Production Attachment selection remains unchanged.
- The Pipeline writes no ProposedChange or accepted Ledger record.

## 9. Acceptance Criteria

- CEA113-ACC-01: Tests prove exact part derivation and Candidate reconstruction.
- CEA113-ACC-02: Tests prove deterministic Structural Part classification.
- CEA113-ACC-03: Tests prove the Part renderer exposes one exact part without canonical IDs.
- CEA113-ACC-04: Tests prove all `Y`, any `N`, and unresolved aggregation rules.
- CEA113-ACC-05: Tests prove Candidate-level recoveries and regressions.
- CEA113-ACC-06: Tests prove all four outcome classifications.
- CEA113-ACC-07: Tests reject missing, foreign, or duplicate Part observations.
- CEA113-ACC-08: Focused formatting, lint, typecheck, and tests pass.
- CEA113-ACC-09: Model-free preparation validates the sealed predecessor package.
- CEA113-ACC-10: The human-run experiment preserves every model execution.
- CEA113-ACC-11: The package reports zero canonical writes.

## 10. Reference Implementations

- Exact ranges: `competitive_attachment_residual_ownership.py`.
- Bounded execution: `competitive_attachment_edge_filter_preview.py`.
- Runtime calibration: `run_competitive_attachment_runtime_calibrated_termination.py`.
- Paired evaluation: `competitive_attachment_candidate_remainder.py`.

## 11. Constraints and Halt Conditions

- Stop when any exact range differs from authoritative source characters.
- Stop when the ten Candidate-level Gold answers change.
- Stop when Gold enters one model input.
- Stop when one execution lacks a typed ModelRun or stage trace.
- Stop when one arm uses a foreign model identity.
- Stop when an action would execute validation tasks.
- Stop when an action would write canonical intelligence.
