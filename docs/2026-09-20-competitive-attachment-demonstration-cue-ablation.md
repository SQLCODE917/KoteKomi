# TDD: CEA-1.8 Demonstration Cue Ablation

- Status: Accepted; implementation in progress; production inactive
- Deliverable ID: `CEA-1.8`
- Program:
  [Competitive Event Attachment Program](2026-09-18-competitive-event-attachment-program.md)
- Predecessor:
  [CEA-1.7 Residual Ownership](2026-09-20-competitive-attachment-residual-ownership.md)

## 1. Context & Problem

CEA-1.7 produced one constant answer across twenty model executions.

Qwen returned `N` for every Residual Edge in both repetitions.

The positive example in the prompt listed no Other Event.

The negative example listed one Other Event.

Every scored task listed at least one Other Event.

The demonstration block supplied one shortcut that predicted every observed answer.

CEA-1.8 changes only that shortcut before KoteKomi redesigns the task criterion.

### Terms

**Baseline Prompt** means the exact CEA-1.7 prompt bytes.

**Cue-Balanced Prompt** means the Baseline Prompt with one changed positive example.

The changed example contains one Other Event outside its Candidate.

The changed example lists that Other Event and retains answer `Y`.

**Cue Effect** means at least one Gold-positive case changes from stable `N` to stable `Y`.

**Probability Evidence** means the runtime token alternatives for the first `Y`, `N`, or `U` token.

### Hypothesis

> The Other Event demonstration cue contributed to the CEA-1.7 constant-`N` collapse.

### Primary flow

1. KoteKomi validates the sealed CEA-1.7 report and ten development tasks.
2. KoteKomi verifies that only the positive example differs between the two prompts.
3. Qwen judges the same ten tasks twice with the Cue-Balanced Prompt.
4. KoteKomi records each answer, Probability Evidence, transition, and exact input.
5. KoteKomi classifies the Cue Effect and writes a second-opinion handoff.

CEA-1.8 creates experimental evidence only.

## 2. Goals

- An operator can determine whether the demonstration cue affected Qwen's answers.
- An operator can inspect answer confidence for every Cue-Balanced Prompt execution.
- An operator can compare each answer with the exact CEA-1.7 answer.
- A reviewer can distinguish a cue effect from a production-ready Attachment task.

## 3. Requirements

### Sealed evidence

- CEA18-EVD-01: The Pipeline must validate the complete CEA-1.7 report.
- CEA18-EVD-02: The Pipeline must require ten tasks and twenty stable `N` answers.
- CEA18-EVD-03: The Pipeline must reuse the exact ten CEA-1.7 development tasks.
- CEA18-EVD-04: The Pipeline must preserve the CEA-1.5 and CEA-1.6 input digests.
- CEA18-EVD-05: Gold must remain outside task selection and every model input.

### Prompt ablation

- CEA18-PRM-01: The Baseline Prompt must match the sealed CEA-1.7 prompt digest.
- CEA18-PRM-02: The Cue-Balanced Prompt must change only the positive example block.
- CEA18-PRM-03: The changed positive example must contain one Other Event outside the Candidate.
- CEA18-PRM-04: The changed positive example must list that Other Event.
- CEA18-PRM-05: The changed positive example must retain answer `Y`.
- CEA18-PRM-06: The task criterion, negative example, and final instruction must remain unchanged.

### Model execution

- CEA18-MOD-01: Qwen must execute each development task twice.
- CEA18-MOD-02: Each execution must use temperature `0` and seed `17`.
- CEA18-MOD-03: Each execution must request ten token alternatives.
- CEA18-MOD-04: Each execution must limit the effective output to three tokens.
- CEA18-MOD-05: Each ModelRun must preserve the effective generation settings.
- CEA18-MOD-06: Each run package must preserve configured and effective settings separately.
- CEA18-MOD-07: Validation tasks must remain unexecuted.

### Evaluation

- CEA18-EVL-01: The evaluator must compare answers by exact task and Edge identifiers.
- CEA18-EVL-02: The evaluator must report the answer distribution for both prompts.
- CEA18-EVL-03: The evaluator must report every positive recovery.
- CEA18-EVL-04: The evaluator must report every negative regression.
- CEA18-EVL-05: The evaluator must report repetition stability.
- CEA18-EVL-06: The evaluator must preserve Probability Evidence for every new execution.
- CEA18-EVL-07: A `supported` result requires at least one stable positive recovery.
- CEA18-EVL-08: A `supported` result requires zero negative regressions.
- CEA18-EVL-09: A `supported` result requires ten stable Cue-Balanced Prompt cases.
- CEA18-EVL-10: A `mixed` result has a Cue Effect with a regression or unstable case.
- CEA18-EVL-11: A `falsified` result has complete evidence and no Cue Effect.
- CEA18-EVL-12: An `inconclusive` result lacks complete answer or Probability Evidence.

### Evidence package

- CEA18-PKG-01: The runner must preserve typed preflight, report, and status files.
- CEA18-PKG-02: The review must show exact Candidate, Target Event, and answer transition.
- CEA18-PKG-03: The review must show the new answer probabilities.
- CEA18-PKG-04: The handoff must state the hypothesis, intervention, results, and limitations.
- CEA18-PKG-05: The handoff must link every exact model input and raw output.
- CEA18-PKG-06: The human must invoke Claude through standard input and standard output.
- CEA18-PKG-07: The package must report zero ProposedChanges and accepted Ledger writes.

## 4. Proposed Architecture

```text
sealed CEA-1.7 evidence
          |
          v
deterministic prompt-diff gate
          |
          v
same ten tasks + Cue-Balanced Prompt
          |
          v
Qwen answers + token probabilities
          |
          v
occurrence-level transition report
```

The Application Layer owns the typed comparison evidence.

The Pipeline owns prompt validation, transition evaluation, and review rendering.

The existing ModelRuntime Port owns Qwen execution and Probability Evidence.

The disposable runner owns experiment orchestration.

The human owns the Claude invocation.

## 5. Key Interactions

```text
Human          Runner          KoteKomi          Qwen
  | prepare      |                |                |
  |------------->| validate cue   |                |
  |              |--------------->|                |
  | run          |                |                |
  |------------->| same tasks     |                |
  |              |------------------------------->|
  |              | answers + probabilities        |
  |              |<-------------------------------|
  |              | compare + handoff               |
```

## 6. Data Model

CEA-1.8 adds Application DTOs for one case transition and one comparison report.

The comparison report references the sealed baseline and new typed run reports.

CEA-1.8 adds no Domain Core record or Ledger schema.

## 7. APIs / Interfaces

The runner `prepare` action accepts the CEA-1.7 root, configuration, and output root.

The runner `run` action accepts the prepared output root and configuration.

The runner prints the handoff and expected Claude review paths.

The human invokes Claude with this command shape:

```text
claude -p --model opus --effort high --add-dir RUN_ROOT < HANDOFF > REVIEW
```

## 8. Behavior & Domain Rules

- Exact source characters remain authoritative.
- Attachment Gold remains authoritative for this experiment's expected answers.
- The known `As ... targeted ...` convention mismatch remains visible in the report.
- CEA-1.8 tests cue causality rather than Attachment task quality.
- The CEA-1.7 task renderer and criterion remain unchanged.
- KoteKomi creates every identifier, trace, mapping, metric, and file.
- Production integration remains inactive.

## 9. Acceptance Criteria

- CEA18-ACC-01: Tests reject any prompt change outside the positive example.
- CEA18-ACC-02: Tests prove the changed example has a listed Other Event and answer `Y`.
- CEA18-ACC-03: Tests prove all four experiment outcomes.
- CEA18-ACC-04: Tests prove exact case alignment and transition counts.
- CEA18-ACC-05: Tests reject missing or malformed Probability Evidence.
- CEA18-ACC-06: Tests prove run metadata distinguishes configured and effective settings.
- CEA18-ACC-07: Focused formatting, lint, typecheck, and tests pass.
- CEA18-ACC-08: The human-run diagnostic produces twenty complete executions.
- CEA18-ACC-09: The package reports zero canonical writes.

## 10. Reference Implementations

- Residual task evidence:
  `packages/application/src/kotekomi_application/competitive_attachment_residual_ownership.py`
- Probability mapping:
  `packages/pipelines/src/kotekomi_pipelines/competitive_attachment_edge_filter_calibration.py`
- Model execution:
  `packages/application/src/kotekomi_application/competitive_attachment_edge_filter_preview.py`
- CEA-1.7 runner: `scripts/run_competitive_attachment_residual_ownership.py`

## 11. Constraints and Halt Conditions

- Stop when the sealed CEA-1.7 answer distribution is not constant `N`.
- Stop when the ten task fingerprints differ from CEA-1.7.
- Stop when the prompt diff changes text outside the positive example.
- Stop when one execution lacks Probability Evidence.
- Stop when an action would execute validation tasks.
- Stop when an action would write canonical intelligence.
