# TDD: CEA-1.9 Explicit Candidate Remainder Experiment

- Status: Accepted for implementation; production inactive
- Deliverable ID: `CEA-1.9`
- Program:
  [Competitive Event Attachment Program](2026-09-18-competitive-event-attachment-program.md)
- Predecessor:
  [CEA-1.8 Demonstration Cue Ablation](2026-09-20-competitive-attachment-demonstration-cue-ablation.md)

## 1. Context & Problem

CEA-1.8 proved that the positive demonstration shape affected Qwen's decisions.

The Cue-Balanced Prompt recovered four of eight Gold-positive cases.

Four Gold-positive cases remained false negatives.

The current task asks Qwen to infer the Candidate Remainder before it judges ownership.

KoteKomi already derives the Candidate Remainder from exact source ranges.

The current model input does not show those ranges as task-local text.

CEA-1.8 also omitted Baseline Arm Probability Evidence.

CEA-1.9 compares both task contracts inside one self-contained run package.

### Terms

**Candidate Remainder** means the ordered Candidate ranges outside the Target Event range.

**Baseline Arm** means the Cue-Balanced Prompt with the existing Candidate renderer.

**Remainder Arm** means the Remainder Prompt with explicit Candidate Remainder parts.

**Attachment Score** means the first-token log odds of `Y` against the combined `N` and `U` mass.

**Score Delta** means the Remainder Arm Attachment Score minus the Baseline Arm Attachment Score.

**Positive Recovery** means a Gold-positive case changes from Baseline `N` to Remainder `Y`.

**Negative Regression** means a Gold-negative case changes from Baseline `N` to another answer.

### Hypothesis

> Explicit Candidate Remainder text improves selective Residual Ownership judgment without regressing Gold-negative cases.

### Primary flow

1. KoteKomi validates the sealed CEA-1.8 tasks and corrected Residual Ownership Gold.
2. KoteKomi constructs each Candidate Remainder from authoritative source ranges.
3. Qwen judges each task once with the Baseline Arm.
4. Qwen judges each task once with the Remainder Arm.
5. KoteKomi records answers, probabilities, Score Deltas, and exact inputs.
6. KoteKomi classifies the hypothesis and writes a second-opinion handoff.

CEA-1.9 creates experimental evidence only.

## 2. Goals

- An operator can compare both task contracts for every exact occurrence.
- An operator can inspect one paired Score Delta for every case.
- An operator can distinguish selective gain from a uniform answer bias.
- A reviewer can inspect every exact model input and raw output.

## 3. Requirements

### Sealed evidence

- CEA19-EVD-01: The Pipeline must validate the complete CEA-1.8 package.
- CEA19-EVD-02: The Pipeline must require the exact ten CEA-1.8 tasks.
- CEA19-EVD-03: The Pipeline must preserve the corrected eight-positive and two-negative Gold inventory.
- CEA19-EVD-04: The Pipeline must preserve inherited and corrected Gold answers separately.
- CEA19-EVD-05: Gold must remain outside every model input.
- CEA19-EVD-06: The Pipeline must bind every direct input with a file digest.
- CEA19-EVD-07: The Pipeline must name DTO fingerprints separately from file digests.

### Deterministic rendering

- CEA19-RND-01: KoteKomi must derive Candidate Remainder parts from authoritative source characters.
- CEA19-RND-02: Candidate Remainder parts must remain ordered and non-overlapping.
- CEA19-RND-03: Candidate Remainder parts must exclude every Target Event character.
- CEA19-RND-04: Candidate Remainder parts and the Target Event must reconstruct the Candidate exactly.
- CEA19-RND-05: The Baseline Arm must use the existing Candidate renderer.
- CEA19-RND-06: The Remainder Arm must show every Candidate Remainder part explicitly.
- CEA19-RND-07: Both arms must preserve the same SourceSegment, Candidate, Target Event, and Other Events.
- CEA19-RND-08: Qwen must receive task-local labels instead of canonical identifiers or offsets.

### Prompt contract

- CEA19-PRM-01: The Baseline Arm must use the exact Cue-Balanced Prompt bytes.
- CEA19-PRM-02: The Remainder Prompt must preserve the Cue-Balanced demonstrations and answers.
- CEA19-PRM-03: The Remainder Prompt must define Candidate Remainder before using the term.
- CEA19-PRM-04: The Remainder Prompt must ask only whether all Candidate Remainder parts belong to the Target Event fact.
- CEA19-PRM-05: Both prompts must require exactly one `Y`, `N`, or `U` answer.

### Model execution

- CEA19-MOD-01: Qwen must execute each task once per arm.
- CEA19-MOD-02: Each execution must use temperature `0` and seed `17`.
- CEA19-MOD-03: Each execution must request ten token alternatives.
- CEA19-MOD-04: Each execution must limit the effective output to three tokens.
- CEA19-MOD-05: Both arms must use one runtime identity and one generation contract.
- CEA19-MOD-06: The run package must preserve twenty ModelRuns and twenty stage traces.
- CEA19-MOD-07: Validation tasks must remain unexecuted.

### Evaluation

- CEA19-EVL-01: The evaluator must align both arms by exact task and Edge identifiers.
- CEA19-EVL-02: The evaluator must require Probability Evidence for both arms.
- CEA19-EVL-03: The evaluator must report both answers and both Attachment Scores per case.
- CEA19-EVL-04: The evaluator must report one Score Delta per case.
- CEA19-EVL-05: The evaluator must report positive accuracy and negative accuracy per arm.
- CEA19-EVL-06: The evaluator must report every Positive Recovery.
- CEA19-EVL-07: The evaluator must report every Negative Regression.
- CEA19-EVL-08: The evaluator must report the positive median Score Delta.
- CEA19-EVL-09: The evaluator must report the maximum negative Score Delta.
- CEA19-EVL-10: A `supported` result requires complete paired evidence.
- CEA19-EVL-11: A `supported` result requires a higher total correct count in the Remainder Arm.
- CEA19-EVL-12: A `supported` result requires at least one Positive Recovery.
- CEA19-EVL-13: A `supported` result requires zero Negative Regressions.
- CEA19-EVL-14: A `supported` result requires the positive median Score Delta to exceed the maximum negative Score Delta.
- CEA19-EVL-15: A `mixed` result has a Positive Recovery with a failed selectivity or safety gate.
- CEA19-EVL-16: A `falsified` result has complete evidence and no Positive Recovery.
- CEA19-EVL-17: An `inconclusive` result lacks one answer or Probability Evidence item.

### Evidence package

- CEA19-PKG-01: The package must preserve typed preflight, report, review, status, and run files.
- CEA19-PKG-02: The review must show exact source, Candidate, Target Event, and Candidate Remainder.
- CEA19-PKG-03: The review must label every score by arm.
- CEA19-PKG-04: The handoff must cite the comparison report fingerprint and every file digest.
- CEA19-PKG-05: The handoff must explain the corrected Gold inventory.
- CEA19-PKG-06: The handoff must distinguish hypothesis support from production readiness.
- CEA19-PKG-07: The handoff must link every exact model input and raw output.
- CEA19-PKG-08: The package must report zero ProposedChanges and accepted Ledger writes.

## 4. Proposed Architecture

```text
sealed CEA-1.8 tasks + corrected Gold
                  |
                  v
    deterministic Remainder builder
                  |
            +-----+-----+
            |           |
            v           v
      Baseline Arm  Remainder Arm
            |           |
            +-----+-----+
                  v
       paired probability evaluator
```

The Application Layer owns exact Candidate Remainder construction and typed evidence.

The existing ModelRuntime Port owns bounded Qwen execution.

The Pipeline owns paired evaluation and review rendering.

The disposable runner owns experiment orchestration.

The human owns the Claude invocation.

## 5. Key Interactions

```text
Human          Runner          KoteKomi          Qwen
  | prepare      |                |                |
  |------------->| validate      |                |
  | run          |                |                |
  |------------->| baseline task |--------------->|
  |              | answer + probability<----------|
  |              | remainder task|--------------->|
  |              | answer + probability<----------|
  |              | paired report |                |
```

## 6. Data Model

CEA-1.9 adds Application DTOs for paired observations, case evaluation, and report status.

The DTOs remain experimental derived evidence.

CEA-1.9 adds no Domain Core record or Ledger schema.

## 7. APIs / Interfaces

The runner `prepare` action accepts the CEA-1.8 root, configuration, and output root.

The runner `run` action accepts the prepared output root and configuration.

The runner prints report, review, handoff, and Claude review paths.

The human invokes Claude through standard input and standard output.

## 8. Behavior & Domain Rules

- Exact source characters remain authoritative.
- KoteKomi performs every range operation.
- Qwen returns only `Y`, `N`, or `U`.
- KoteKomi maps every answer to the exact supplied task.
- Both arms use the same corrected Residual Ownership Gold only during evaluation.
- CEA-1.9 does not change production selection or Attachment policy.
- CEA-1.9 creates no ProposedChange or accepted Ledger record.

## 9. Acceptance Criteria

- CEA19-ACC-01: Tests prove Candidate Remainder reconstruction for prefix, suffix, and split ranges.
- CEA19-ACC-02: Tests prove the Remainder renderer exposes exact source text without identifiers or offsets.
- CEA19-ACC-03: Tests prove both arms preserve all semantic inputs except the declared task contract.
- CEA19-ACC-04: Tests reject missing Probability Evidence in either arm.
- CEA19-ACC-05: Tests prove paired scores and Score Deltas.
- CEA19-ACC-06: Tests prove all four outcome classifications.
- CEA19-ACC-07: Tests prove run metadata separates DTO fingerprints from file digests.
- CEA19-ACC-08: Focused formatting, lint, typecheck, and tests pass.
- CEA19-ACC-09: The human-run diagnostic produces twenty complete model executions.
- CEA19-ACC-10: The package reports zero canonical writes.

## 10. Reference Implementations

- Exact Candidate Remainder:
  `packages/application/src/kotekomi_application/competitive_attachment_residual_ownership.py`
- Bounded execution:
  `packages/application/src/kotekomi_application/competitive_attachment_edge_filter_preview.py`
- Probability mapping:
  `packages/pipelines/src/kotekomi_pipelines/competitive_attachment_edge_filter_calibration.py`
- Paired review pattern:
  `packages/pipelines/src/kotekomi_pipelines/competitive_attachment_residual_cue_ablation.py`

## 11. Constraints and Halt Conditions

- Stop when one arm uses a different task inventory.
- Stop when one arm uses a different runtime identity.
- Stop when one Candidate Remainder fails exact reconstruction.
- Stop when one execution lacks Probability Evidence.
- Stop when an action would execute validation tasks.
- Stop when an action would write canonical intelligence.
