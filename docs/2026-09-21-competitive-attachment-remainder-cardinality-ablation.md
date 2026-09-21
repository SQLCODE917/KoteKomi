# TDD: CEA-1.16 Remainder Cardinality Ablation

- Status: Accepted for implementation; production inactive
- Deliverable ID: `CEA-1.16`
- Program:
  [Competitive Event Attachment Program](2026-09-18-competitive-event-attachment-program.md)
- Predecessor:
  [CEA-1.15 Remainder Enumeration Isolation](2026-09-21-competitive-attachment-remainder-enumeration-isolation.md)

## 1. Context & Problem

CEA-1.15 reproduced one CEA-1.14 recovery without moving the Authoritative Candidate marker.

Its successful task omitted the exact function-word Remainder `that ` and changed from two displayed Remainder parts to one.

The result proves that Candidate-marker movement was unnecessary.

It does not establish whether the recovery came from omitting `that ` or from displaying one part rather than two.

The unchanged prompt contains one positive one-part example and one negative two-part example.

A cardinality shortcut is therefore a concrete competing explanation.

### Terms

**Recovered task** means `aro_e05ad7d4c4c93ca6ceac7a6d`.

**One-part control** means the exact CEA-1.15 task whose sole displayed Remainder is ` services with FedRAMP authorization`.

**Split view** means the same task with that exact text represented as two adjacent source ranges: ` services` and ` with FedRAMP authorization`.

### Hypothesis

> If one-part cardinality caused the CEA-1.15 recovery, splitting the same Remainder characters into two adjacent parts will change the answer from `Y` to `N`.

### Primary flow

1. KoteKomi validates the complete CEA-1.15 package and independent review.
2. KoteKomi selects the recovered task by exact inherited task ID.
3. KoteKomi derives two adjacent, source-exact Remainder ranges whose concatenation equals the one-part control.
4. Qwen judges the Split view once with the unchanged prompt and runtime settings.
5. KoteKomi preserves the exact answer and complete position-zero Y/N/U probability evidence.
6. KoteKomi compares the fresh result with the sealed CEA-1.15 `Y/Y` control.

CEA-1.16 creates experimental evidence only.

## 2. Goals

- Change only the boundary between two displayed Remainder parts.
- Preserve every model-visible source character, Candidate marker, Event marker, passage, prompt, and runtime setting.
- Retain exact finite-label probabilities rather than reducing them to token positions.
- Falsify or support the cardinality explanation with one fresh execution.
- Produce one self-contained second-opinion handoff.

## 3. Requirements

### Evidence

- CEA116-EVD-01: The Pipeline must validate the complete CEA-1.15 package and independent review.
- CEA116-EVD-02: The Pipeline must select the recovered task by exact inherited task ID.
- CEA116-EVD-03: The Pipeline must preserve the sealed one-part `Y/Y` answers separately from the fresh answer.
- CEA116-EVD-04: Every direct input must carry a file digest.
- CEA116-EVD-05: Gold must remain outside the model input.

### Split view

- CEA116-SPL-01: The Candidate, Target Event, passage, and Other Events must remain unchanged.
- CEA116-SPL-02: The Split view must contain exactly two ordered, adjacent source ranges.
- CEA116-SPL-03: Concatenating the Split ranges must reproduce the exact one-part control text.
- CEA116-SPL-04: The first range must be ` services`.
- CEA116-SPL-05: The second range must be ` with FedRAMP authorization`.
- CEA116-SPL-06: No source character may be added, removed, normalized, or reordered.

### Model execution

- CEA116-MOD-01: The exact CEA-1.15 prompt must remain unchanged.
- CEA116-MOD-02: Qwen must return exactly one `Y`, `N`, or `U` character.
- CEA116-MOD-03: The execution must use temperature `0`, seed `17`, ten alternatives, frequency penalty `0.0`, and a two-token output request.
- CEA116-MOD-04: The execution must use the CEA-1.15 model identity and runtime contract.
- CEA116-MOD-05: The experiment must execute exactly one fresh model task.
- CEA116-MOD-06: The report must preserve position-zero Y/N/U log probabilities and the finite-label argmax.

### Evaluation

- CEA116-EVL-01: `supported` requires a strict fresh `N` whose finite-label argmax is `N`.
- CEA116-EVL-02: `falsified` requires a strict fresh `Y` whose finite-label argmax is `Y`.
- CEA116-EVL-03: `inconclusive` covers `U`, invalid output, missing probability evidence, or disagreement between the observed answer and finite-label argmax.
- CEA116-EVL-04: `supported` means the task is cardinality-sensitive; it does not prove a general production rule.
- CEA116-EVL-05: `falsified` means one-part cardinality was not necessary for this recovery.
- CEA116-EVL-06: The experiment must not claim false-positive safety, validation quality, or production readiness.

### Evidence package

- CEA116-PKG-01: The package must preserve preflight, execution, report, review, handoff, run, and status files.
- CEA116-PKG-02: The review must show exact data in, the sealed control, raw output, parsed answer, and all Y/N/U probabilities.
- CEA116-PKG-03: The handoff must cite direct file digests and the report fingerprint.
- CEA116-PKG-04: The package must report zero ProposedChanges and accepted Ledger writes.

## 4. Proposed Architecture

```text
sealed CEA-1.15 recovered task
              |
              v
same Remainder characters
              |
              v
one part -> two adjacent parts
              |
              v
one bounded Qwen judgment
              |
              v
answer plus finite-label probabilities
```

The Application Layer owns exact Split-view construction and rendering.

The existing ModelRuntime Port owns bounded Qwen execution.

The Pipeline owns evidence validation, evaluation, and review rendering.

The disposable runner composes the experiment.

The human starts and monitors the live model call.

## 5. Acceptance Criteria

- CEA116-ACC-01: Tests prove only the Remainder boundary changes.
- CEA116-ACC-02: Tests prove split ranges are adjacent, ordered, source-exact, and content-preserving.
- CEA116-ACC-03: Tests prove all three outcomes and probability-agreement gates.
- CEA116-ACC-04: Tests reject foreign or drifted predecessor evidence.
- CEA116-ACC-05: Focused formatting, lint, typecheck, and tests pass.
- CEA116-ACC-06: Model-free preparation validates the sealed predecessor package.
- CEA116-ACC-07: The human-run experiment preserves one complete model execution and zero canonical writes.

## 6. Constraints and Halt Conditions

- Stop if any model-visible source character changes.
- Stop if the Candidate, Event, passage, prompt, Gold answer, model identity, or runtime contract changes.
- Stop if the Split ranges overlap, leave a gap, or fail to reconstruct the one-part control.
- Stop if Gold enters the model input.
- Stop if the execution lacks a typed ModelRun, stage trace, or position-zero Y/N/U evidence.
- Stop before validation or production integration regardless of outcome.
