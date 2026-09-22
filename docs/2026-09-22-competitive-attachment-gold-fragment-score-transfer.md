# TDD: CEA-1.25 Gold Fragment Score Transfer

- Status: Planned; production inactive
- Deliverable ID: `CEA-1.25`
- Program:
  [Competitive Event Attachment Program](2026-09-18-competitive-event-attachment-program.md)
- Predecessor:
  [CEA-1.24 Local Model Swap](2026-09-22-competitive-attachment-local-model-swap.md)
- Transfer Gold:
  [Source-Grounded Proposition Gold](hsq-source-grounded-proposition-gold-v1.json)

## 1. Context & Problem

CEA-1.24 compared Qwen2.5-14B and Qwen3-14B on twenty Nested Event ownership cases.

Qwen3 answered fifteen cases correctly by its emitted answer.

Its first-token probability evidence separated the `Y` and `N` Gold classes more clearly.

One threshold on the `N` token score classified nineteen calibration cases correctly.

This result came from the same twenty cases that exposed the threshold.

KoteKomi must test one frozen threshold on different source occurrences before it uses that signal.

**Calibration Set** means the twenty sealed Qwen3 cases from CEA-1.24.

**N Score** means the first output position's log probability for the finite answer `N`.

**Censored N Score** means that `N` falls below the returned alternative-token inventory.

**Calibration Interval** means the largest threshold interval that preserves `0.85` recall for
both calibration labels under conservative score bounds.

**Frozen Threshold** means the midpoint of the Calibration Interval.

**Gold Fragment Case** means one exact reviewed proposition Fragment paired with one Gold Event.

**Transfer Set** means forty positive and forty negative Gold Fragment Cases.

**Argmax Decision** means the exact `Y`, `N`, or `U` answer emitted by Qwen3.

**Threshold Decision** means the decision derived from the N Score and Frozen Threshold.

The Primary Flow is:

1. The runner validates the complete CEA-1.24 package and its twenty Qwen3 executions.
2. KoteKomi derives the Calibration Interval and Frozen Threshold without model execution.
3. KoteKomi derives eighty Gold Fragment Cases from approved Proposition Gold.
4. The runner writes the Frozen Threshold and Transfer Set before transfer execution.
5. Qwen3 answers the unchanged semantic question once for each Gold Fragment Case.
6. KoteKomi evaluates Argmax Decisions and Threshold Decisions separately.
7. The runner writes exact evidence and one second-opinion handoff.

CEA-1.25 creates no ProposedChange or accepted Ledger record.

CEA-1.25 does not activate production routing.

## 2. Goals

- An operator can verify that threshold selection precedes every transfer execution.
- An operator can inspect all eighty exact source inputs and outputs.
- An operator can compare Argmax and threshold quality on balanced human-approved Gold.
- An operator can distinguish an observed N Score from a Censored N Score.
- An operator can identify every transfer failure by SourceSegment and Event occurrence.
- An operator can send one self-contained evidence package for independent review.

## 3. Requirements

### Calibration evidence

- CEA125-CAL-01: The Pipeline validates the terminal CEA-1.24 report and all twenty executions.
- CEA125-CAL-02: The Pipeline requires one output token and one Qwen3 model identity.
- CEA125-CAL-03: The Pipeline preserves each first-position token alternative and log probability.
- CEA125-CAL-04: The Pipeline derives every N Score without changing an emitted answer.
- CEA125-CAL-05: A missing `N` alternative records a Censored N Score and its returned score floor.
- CEA125-CAL-06: The Calibration Set remains twelve `Y` cases and eight `N` cases.
- CEA125-CAL-07: Every calibration `N` case must contain an observed N Score.

### Threshold selection

- CEA125-THR-01: The threshold policy requires at least `0.85` recall for each label.
- CEA125-THR-02: The lower boundary preserves the required number of calibration `Y` cases.
- CEA125-THR-03: The upper boundary preserves the required number of calibration `N` cases.
- CEA125-THR-04: The lower boundary is exclusive and the upper boundary is inclusive.
- CEA125-THR-05: The Frozen Threshold is the arithmetic midpoint of those boundaries.
- CEA125-THR-06: The Calibration Interval must be at least five natural-log units wide.
- CEA125-THR-07: The runner writes the threshold policy before any transfer execution exists.
- CEA125-THR-08: The threshold policy records one canonical fingerprint.

### Transfer catalog

- CEA125-CAT-01: The Pipeline requires approved Source-Grounded Proposition Gold.
- CEA125-CAT-02: The Pipeline requires the approved parent Event Trigger Gold.
- CEA125-CAT-03: Every Gold Fragment Case preserves exact SourceSegment characters and ranges.
- CEA125-CAT-04: The Transfer Set contains one positive case for every one of forty Gold Events.
- CEA125-CAT-05: A positive case uses one Fragment assigned to its target Gold Event.
- CEA125-CAT-06: Positive selection prefers a Fragment outside the target Event head.
- CEA125-CAT-07: Positive selection then prefers the longest Fragment and earliest occurrence.
- CEA125-CAT-08: A negative case uses a Fragment not assigned to its target Gold Event.
- CEA125-CAT-09: Negative selection gives every multi-Event target one case before filling the set.
- CEA125-CAT-10: Remaining negatives use deterministic SourceSegment round-robin order.
- CEA125-CAT-11: The Transfer Set contains exactly forty `Y` and forty `N` cases.
- CEA125-CAT-12: The Transfer Set covers all forty Events and all nineteen SourceSegments.
- CEA125-CAT-13: The model-visible task contains no Gold answer or review rationale.

### Model task

- CEA125-MOD-01: The Pipeline reuses the exact CEA-1.24 prompt bytes.
- CEA125-MOD-02: The Pipeline reuses the exact Qwen3 artifact and `/no_think` control.
- CEA125-MOD-03: Each task shows one Passage, Candidate, Target Event, and Contained Event list.
- CEA125-MOD-04: The Contained Event list can contain `NONE`.
- CEA125-MOD-05: Qwen3 returns exactly one `Y`, `N`, or `U` token.
- CEA125-MOD-06: The runtime uses temperature `0`, seed `17`, and sixteen output tokens.
- CEA125-MOD-07: The runtime requests twenty first-position alternative tokens.
- CEA125-MOD-08: The Pipeline preserves exact input, raw output, receipt, and elapsed time.

### Score interpretation

- CEA125-SCR-01: An observed N Score at least equal to the Frozen Threshold yields `N`.
- CEA125-SCR-02: An observed N Score below the Frozen Threshold yields `Y`.
- CEA125-SCR-03: A Censored N Score yields `Y` when its score floor is below the threshold.
- CEA125-SCR-04: Every other Censored N Score remains unresolved.
- CEA125-SCR-05: Score interpretation preserves the model's Argmax Decision separately.

### Evaluation

- CEA125-EVL-01: The evaluator scores source occurrences rather than string identities.
- CEA125-EVL-02: The evaluator reports `Y` recall, `N` recall, and accuracy for both policies.
- CEA125-EVL-03: The evaluator reports balanced accuracy and Matthews correlation coefficient.
- CEA125-EVL-04: The evaluator reports corrections and regressions from Argmax to threshold.
- CEA125-EVL-05: The evaluator reports observed, censored-safe, and unresolved score counts.
- CEA125-EVL-06: `supported` requires at least `0.85` transfer recall for each label.
- CEA125-EVL-07: `supported` requires higher threshold balanced accuracy than Argmax.
- CEA125-EVL-08: `supported` requires threshold MCC at least equal to Argmax MCC.
- CEA125-EVL-09: `supported` requires zero failed, invalid, unclear, or unresolved transfer cases.
- CEA125-EVL-10: `mixed` records a complete improvement that misses one supported gate.
- CEA125-EVL-11: A complete result without improvement is `falsified`.
- CEA125-EVL-12: An incomplete result is `inconclusive`.

### Evidence package

- CEA125-PKG-01: The preflight binds every input path and digest.
- CEA125-PKG-02: The report includes exact data in, expected answer, and both actual answers.
- CEA125-PKG-03: The handoff states the calibration, corpus, and model limitations.
- CEA125-PKG-04: The report records zero ProposedChanges and zero accepted Ledger writes.
- CEA125-PKG-05: The report states that production integration remains inactive.

## 4. Proposed Architecture

```text
sealed CEA-1.24 executions ----> score bounds ----> Frozen Threshold
                                                        |
approved Proposition Gold ----> eighty exact cases -----+
                                                        |
                                                        v
                                                Qwen3 execution
                                                        |
                                                        v
                                      Argmax and threshold evaluator
```

The Application Layer owns score, threshold, case, observation, and report contracts.

The Pipeline owns deterministic case selection, threshold selection, and evaluation.

The ModelRuntime Port owns Qwen3 execution evidence.

The disposable runner owns package composition.

## 5. Key Interactions

```text
Operator       Runner          Pipeline          Qwen3
   |              |               |                |
   | prepare      |               |                |
   |------------->| validate      |                |
   |              |-------------->| freeze policy  |
   |<-------------| preflight     |                |
   | run          |               |                |
   |------------->|------------------------------->|
   |              |<-------------------------------|
   |              |-------------->| evaluate       |
   |<-------------| report        |                |
```

## 6. Data Model

`AttachmentScoreEvidence` records one observed or censored N Score.

`AttachmentScoreThresholdPolicy` records the Calibration Interval and Frozen Threshold.

`AttachmentScoreTransferCase` records one source-exact Gold Fragment Case.

`AttachmentScoreTransferCatalog` records the frozen eighty-case Transfer Set.

`AttachmentScoreTransferObservation` records one Qwen3 execution and both decisions.

`AttachmentScoreMetrics` records one policy's occurrence-level confusion matrix.

`AttachmentScoreTransferReport` records the terminal comparison and outcome.

All records remain derived experiment evidence.

## 7. APIs / Interfaces

The `prepare` command accepts the CEA-1.24 root and one output root.

The `prepare` command writes the threshold policy, Transfer Set, and preflight.

The `run` command accepts the prepared root and one runtime configuration.

The `run` command writes execution records, a report, a review, and a handoff.

## 8. Behavior & Domain Rules

- A Gold Fragment Case asks semantic membership rather than Event role classification.
- A `Y` label means the approved Gold assigns the exact Fragment to the target Event.
- An `N` label means the approved Gold assigns the exact Fragment only elsewhere.
- The Threshold Decision changes no preserved Argmax Decision.
- Top-alternative count changes evidence capture rather than the decoding rule.
- A supported result authorizes only a repeatability or same-task comparator experiment.

## 9. Acceptance Criteria

- CEA125-ACC-01: Tests reproduce the sealed CEA-1.24 N Scores and threshold boundaries.
- CEA125-ACC-02: Tests prove conservative Censored N Score interpretation.
- CEA125-ACC-03: Tests prove exact source mapping for all eighty cases.
- CEA125-ACC-04: Tests prove the forty-positive and forty-negative selection contract.
- CEA125-ACC-05: Tests prove the model input excludes Gold labels and rationales.
- CEA125-ACC-06: Tests prove balanced accuracy and MCC from exact confusion counts.
- CEA125-ACC-07: Tests prove all four terminal outcomes.
- CEA125-ACC-08: Focused formatting, lint, typecheck, and tests pass.
- CEA125-ACC-09: The report records zero canonical writes.

## 10. Reference Implementations

- Score evidence: `competitive_attachment_edge_filter_calibration.py`.
- Exact task execution: `run_competitive_attachment_nested_event_transfer.py`.
- Qwen3 runtime binding: `run_competitive_attachment_local_model_swap.py`.
- Event head mapping: `event_trigger_stage_local.py`.
- Calibration background: [Guo et al. 2017](https://proceedings.mlr.press/v70/guo17a.html).
- Runtime log probabilities: [LM Studio Open Responses](https://lmstudio.ai/blog/openresponses).

## 11. Constraints and Halt Conditions

- Stop when one calibration `N` case lacks an observed N Score.
- Stop when the Calibration Interval is narrower than five natural-log units.
- Stop when the prepared threshold or Transfer Set changes after model execution starts.
- Stop when one Gold Fragment or Event head is not source-exact.
- Stop when the model identity or prompt digest differs from CEA-1.24.
- Stop before production integration.
