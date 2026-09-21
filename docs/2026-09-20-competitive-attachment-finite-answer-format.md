# TDD: CEA-1.10 Finite Answer Format Isolation

- Status: Accepted for implementation; production inactive
- Deliverable ID: `CEA-1.10`
- Program:
  [Competitive Event Attachment Program](2026-09-18-competitive-event-attachment-program.md)
- Predecessor:
  [CEA-1.9 Explicit Candidate Remainder Experiment](2026-09-20-competitive-attachment-candidate-remainder.md)

## 1. Context & Problem

CEA-1.9 compared two task contracts at the same time.

The Remainder Arm changed task wording, demonstrations, and task rendering.

Two Remainder Arm executions returned `Answer:` instead of `Y`, `N`, or `U`.

Both demonstrations ended with labeled and backticked answers.

The shared schema then requested one bare answer character.

The complete model input therefore demonstrated one output form and required another output form.

Both invalid executions retained first-position alternatives for `Y`, `N`, and `U`.

Those alternatives permit a finite-label diagnostic without repairing the invalid raw output.

CEA-1.10 isolates the demonstration answer format before KoteKomi tests another semantic task.

### Terms

**Labeled Arm** means the Remainder Prompt whose demonstrations end with `Answer: \`Y\`` or `Answer: \`N\``.

**Bare Arm** means the same prompt whose demonstrations end with bare `Y` or `N` characters.

**Observed Answer** means the complete raw output parsed through the strict `Y`, `N`, or `U` contract.

**Finite Label Evidence** means normalized first-position probabilities for `Y`, `N`, and `U`.

**Finite Label Argmax** means the highest-probability label in Finite Label Evidence.

**Answer Label Pressure** means the first-position probability evidence for the token `Answer`.

**Conservative Answer Log Probability** means the exact `Answer` log probability when present.

When `Answer` is absent, this value equals the lowest returned alternative log probability.

The absent-token value is an upper bound because the runtime returns alternatives in probability order.

**Answer Pressure Delta Upper Bound** means the Bare Arm's Conservative Answer Log Probability minus the Labeled Arm's exact `Answer` log probability.

KoteKomi records this bound only when the Labeled Arm returned an exact `Answer` alternative.

### Hypothesis

> Bare demonstration answers remove answer-label imitation without changing Qwen's finite-label semantic preference.

### Primary flow

1. KoteKomi validates the complete CEA-1.9 evidence package.
2. KoteKomi derives Finite Label Evidence from all twenty archived receipts.
3. KoteKomi proves the eighteen existing scores remain byte-for-byte equivalent as numbers.
4. Qwen judges the same ten tasks once with each format arm.
5. KoteKomi preserves Observed Answers and Finite Label Evidence separately.
6. KoteKomi classifies the format hypothesis and writes a second-opinion handoff.

CEA-1.10 creates experimental evidence only.

## 2. Goals

- An operator can distinguish invalid output from finite-label preference.
- An operator can see whether labeled demonstrations cause `Answer` output.
- An operator can compare semantic label preference across format arms.
- A reviewer can inspect every exact model input and raw output.

## 3. Requirements

### Sealed evidence

- CEA110-EVD-01: The Pipeline must validate the complete CEA-1.9 package.
- CEA110-EVD-02: The Pipeline must require the exact ten CEA-1.9 tasks.
- CEA110-EVD-03: The Pipeline must validate all twenty archived execution records.
- CEA110-EVD-04: The Pipeline must preserve actual output validity separately from Finite Label Evidence.
- CEA110-EVD-05: Gold must remain outside every model input.
- CEA110-EVD-06: The Pipeline must bind every direct input with a file digest.

### Archived probability recovery

- CEA110-REC-01: KoteKomi must inspect first-position alternatives independently of the emitted token.
- CEA110-REC-02: Finite Label Evidence requires alternatives for `Y`, `N`, and `U`.
- CEA110-REC-03: Finite Label Evidence must retain the actual emitted first token.
- CEA110-REC-04: The recovered eighteen Attachment Scores must equal the sealed scores within `1e-12`.
- CEA110-REC-05: The two invalid outputs must remain invalid Observed Answers.
- CEA110-REC-06: The recovery report must contain twenty Finite Label Evidence records.

### One-factor prompt contract

- CEA110-PRM-01: Both arms must use the Candidate Remainder task semantics.
- CEA110-PRM-02: Both arms must use the same Candidate Remainder renderer.
- CEA110-PRM-03: Both prompt files must omit the final output instruction.
- CEA110-PRM-04: The shared schema must append the final output instruction once.
- CEA110-PRM-05: The two prompt files must differ only in two demonstration answer lines.
- CEA110-PRM-06: The Labeled Arm must use labeled and backticked demonstration answers.
- CEA110-PRM-07: The Bare Arm must use bare demonstration answer characters.

### Model execution

- CEA110-MOD-01: Qwen must execute each task once per arm.
- CEA110-MOD-02: Each execution must use temperature `0` and seed `17`.
- CEA110-MOD-03: Each execution must request ten token alternatives.
- CEA110-MOD-04: Each execution must limit output to eight tokens.
- CEA110-MOD-05: Both arms must use one runtime identity and one generation contract.
- CEA110-MOD-06: The package must preserve twenty ModelRuns and twenty stage traces.
- CEA110-MOD-07: Validation tasks must remain unexecuted.

### Evaluation

- CEA110-EVL-01: The evaluator must align both arms by exact task and Edge identifiers.
- CEA110-EVL-02: The evaluator must report strict Observed Answer validity for each arm.
- CEA110-EVL-03: The evaluator must report first emitted tokens for each arm.
- CEA110-EVL-04: The evaluator must report Finite Label Argmax for each arm.
- CEA110-EVL-05: The evaluator must report Answer Label Pressure for each arm.
- CEA110-EVL-06: The evaluator must report Finite Label Argmax agreement across arms.
- CEA110-EVL-07: The evaluator must report the median conservative pressure change.
- CEA110-EVL-07A: A pressure comparison requires an exact Labeled Arm `Answer` probability.
- CEA110-EVL-08: `supported` requires ten valid Bare Arm Observed Answers.
- CEA110-EVL-09: `supported` requires zero Bare Arm outputs whose first token is `Answer`.
- CEA110-EVL-10: `supported` requires at least one Labeled Arm output whose first token is `Answer`.
- CEA110-EVL-11: `supported` requires a median pressure reduction of at least five natural-log units.
- CEA110-EVL-11A: `supported` requires ten valid Answer Pressure Delta Upper Bounds.
- CEA110-EVL-12: `supported` requires Finite Label Argmax agreement on at least nine tasks.
- CEA110-EVL-13: `mixed` requires improved strict validity with one failed causal gate.
- CEA110-EVL-14: `falsified` requires complete evidence without improved strict validity.
- CEA110-EVL-15: `inconclusive` requires missing execution or Finite Label Evidence.

### Evidence package

- CEA110-PKG-01: The package must preserve preflight, recovery, report, review, status, and run files.
- CEA110-PKG-02: The review must show exact source, Candidate, Target Event, and Candidate Remainder.
- CEA110-PKG-03: The review must show raw output, Observed Answer, and Finite Label Argmax per arm.
- CEA110-PKG-04: The handoff must cite every file digest and the report fingerprint.
- CEA110-PKG-05: The handoff must identify disputed Gold labels without changing them.
- CEA110-PKG-06: The package must report zero ProposedChanges and accepted Ledger writes.

## 4. Proposed Architecture

```text
sealed CEA-1.9 receipts
          |
          v
finite-label recovery
          |
   +------+------+
   |             |
   v             v
Labeled Arm   Bare Arm
   |             |
   +------+------+
          v
 format-effect evaluator
```

The Application Layer owns typed Finite Label Evidence.

The existing ModelRuntime Port owns bounded Qwen execution.

The Pipeline owns recovery, paired evaluation, and review rendering.

The disposable runner owns experiment orchestration.

The human owns the Claude invocation.

## 5. Key Interactions

```text
Human          Runner          KoteKomi          Qwen
  | prepare      |                |                |
  |------------->| recover       |                |
  | run          |                |                |
  |------------->| labeled task  |--------------->|
  |              | bare task     |--------------->|
  |              | format report |                |
```

## 6. Data Model

CEA-1.10 adds Application DTOs for Finite Label Evidence, paired observations, and one report.

The DTOs remain experimental derived evidence.

CEA-1.10 adds no Domain Core record or Ledger schema.

## 7. APIs / Interfaces

The runner `prepare` action accepts the CEA-1.9 root, configuration, and output root.

The runner `run` action accepts the prepared output root and configuration.

The runner prints report, review, handoff, and Claude review paths.

The human invokes Claude through standard input and standard output.

## 8. Behavior & Domain Rules

- Exact source characters remain authoritative.
- KoteKomi performs every range and probability operation.
- Qwen returns model text under the shared finite-answer schema.
- KoteKomi parses the complete raw output without repair.
- KoteKomi uses first-position alternatives only as diagnostic evidence.
- CEA-1.10 does not change production selection or Attachment policy.
- CEA-1.10 creates no ProposedChange or accepted Ledger record.

## 9. Acceptance Criteria

- CEA110-ACC-01: Tests recover all twenty archived Finite Label Evidence records.
- CEA110-ACC-02: Tests reproduce all eighteen sealed CEA-1.9 scores within `1e-12`.
- CEA110-ACC-03: Tests preserve `Answer:` as invalid while deriving its finite-label argmax.
- CEA110-ACC-04: Tests prove prompt files differ only in two answer lines.
- CEA110-ACC-05: Tests prove both arms use the same task renderer and generation contract.
- CEA110-ACC-06: Tests prove conservative Answer Label Pressure when `Answer` is absent.
- CEA110-ACC-07: Tests prove all four outcome classifications.
- CEA110-ACC-08: Focused formatting, lint, typecheck, and tests pass.
- CEA110-ACC-09: The human-run diagnostic produces twenty complete model executions.
- CEA110-ACC-10: The package reports zero canonical writes.

## 10. Reference Implementations

- Bounded execution:
  `packages/application/src/kotekomi_application/competitive_attachment_edge_filter_preview.py`
- Probability mapping:
  `packages/pipelines/src/kotekomi_pipelines/competitive_attachment_edge_filter_calibration.py`
- Paired package:
  `packages/pipelines/src/kotekomi_pipelines/competitive_attachment_candidate_remainder.py`
- Experiment runner:
  `scripts/run_competitive_attachment_candidate_remainder.py`

## 11. Constraints and Halt Conditions

- Stop when the prompt files differ outside two answer lines.
- Stop when one arm uses a different task renderer.
- Stop when one arm uses a different runtime identity.
- Stop when one archived score changes beyond `1e-12`.
- Stop when one execution lacks first-position token alternatives.
- Stop when an action would execute validation tasks.
- Stop when an action would write canonical intelligence.
