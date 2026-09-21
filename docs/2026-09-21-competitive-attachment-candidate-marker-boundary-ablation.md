# TDD: CEA-1.14 Candidate Marker Boundary Ablation

- Status: Implemented; procedural result supported; mechanism inconclusive; production inactive
- Deliverable ID: `CEA-1.14`
- Program:
  [Competitive Event Attachment Program](2026-09-18-competitive-event-attachment-program.md)
- Predecessor:
  [CEA-1.13 Part-Wise Residual Ownership](2026-09-20-competitive-attachment-partwise-residual-ownership.md)

## 1. Context & Problem

CEA-1.13 compared one Whole Arm with one Part Arm on ten Residual Ownership cases.

The Whole Arm answered seven cases correctly.

The Part Arm answered three cases correctly.

The Part Arm changed both the prompt criterion and the model-visible part context.

The result therefore rejected that Part Arm without isolating Candidate marker placement.

One controlled pair supplied the same Passage, Target Event, and Remainder Part twice.

The pair changed only the location of the opening `<candidate>` marker.

Qwen answered `N` twice in one marker position and `Y` twice in the other position.

Both remaining Whole Arm false negatives begin with `that`.

One false negative also contains a participant and a light verb before its Target Event.

The existing evidence therefore makes marker placement testable but does not prove its effect.

### Terms

**Authoritative Candidate** means the original exact Candidate range from CEA-1.13.

**Rendered Candidate** means the source-exact inner range marked as the Candidate for one model task.

**Structural Trim Arm** means a Rendered Candidate without leading or trailing non-alphanumeric characters.

**Introducer Trim Arm** means the Structural Trim Arm after one leading `that`, `which`, `who`, or `to` token and its following whitespace move outside the Candidate marker.

**Removed Boundary** means the exact source characters between an Authoritative Candidate boundary and its Rendered Candidate boundary.

### Hypothesis

> A source-preserving Candidate marker boundary can recover a stable Whole Arm false negative without regressing a correct Whole Arm answer.

### Primary flow

1. KoteKomi validates the complete CEA-1.13 package and independent review.
2. KoteKomi derives both Rendered Candidates from every Authoritative Candidate.
3. Qwen judges each Rendered Candidate twice with the unchanged Whole Arm prompt.
4. KoteKomi maps each answer back to its Authoritative Candidate occurrence.
5. KoteKomi compares both arms with the archived Whole Arm and corrected Gold.

CEA-1.14 creates experimental evidence only.

## 2. Goals

- Preserve every authoritative source character and Candidate occurrence.
- Isolate marker placement without changing the Whole Arm prompt.
- Measure each recovery and regression at exact occurrence level.
- Preserve exact model input and raw output for every judgment.
- Produce one self-contained second-opinion handoff.

## 3. Requirements

### Predecessor evidence

- CEA114-EVD-01: The Pipeline must validate the complete CEA-1.13 package.
- CEA114-EVD-02: The Pipeline must require the completed CEA-1.13 independent review.
- CEA114-EVD-03: The Pipeline must reuse the exact ten CEA-1.13 Authoritative Candidates.
- CEA114-EVD-04: The Pipeline must preserve the corrected eight-positive and two-negative Gold inventory.
- CEA114-EVD-05: The Pipeline must record the reviewed CEA-1.13 outcome as `falsified`.
- CEA114-EVD-06: Gold must remain outside every model input.
- CEA114-EVD-07: Every direct input must carry a file digest.

### Rendered Candidate construction

- CEA114-RND-01: KoteKomi must derive each Rendered Candidate from authoritative source characters.
- CEA114-RND-02: Each Rendered Candidate must remain inside its Authoritative Candidate.
- CEA114-RND-03: Each Rendered Candidate must contain the complete Target Event occurrence.
- CEA114-RND-04: The Structural Trim Arm must move past only Unicode characters outside letter and number categories.
- CEA114-RND-05: The Introducer Trim Arm must apply Structural Trim first.
- CEA114-RND-06: The Introducer Trim Arm can remove one bounded leading introducer token.
- CEA114-RND-07: An introducer token can move only when its complete range precedes the Target Event.
- CEA114-RND-08: KoteKomi must preserve every Removed Boundary as an exact source range.
- CEA114-RND-09: KoteKomi must recompute model-visible Remainder Parts from the Rendered Candidate.
- CEA114-RND-10: KoteKomi must keep the full Passage unchanged in every model input.

### Model task

- CEA114-MOD-01: Both arms must use the CEA-1.13 Whole Arm prompt unchanged.
- CEA114-MOD-02: Both arms must use the CEA-1.13 Whole Arm question and answer contract.
- CEA114-MOD-03: Qwen must return exactly one `Y`, `N`, or `U` character.
- CEA114-MOD-04: Both arms must use temperature `0`, seed `17`, and ten alternatives.
- CEA114-MOD-05: Both arms must request two output tokens.
- CEA114-MOD-06: Both arms must declare `frequency_penalty` as `0.0`.
- CEA114-MOD-07: Both arms must execute two repetitions.
- CEA114-MOD-08: Both arms must use one model identity and one runtime contract.
- CEA114-MOD-09: The experiment must preserve forty model executions.
- CEA114-MOD-10: Validation tasks must remain unexecuted.

### Evaluation

- CEA114-EVL-01: The evaluator must score each answer against its Authoritative Candidate.
- CEA114-EVL-02: The evaluator must preserve archived Whole Arm answers as the Baseline.
- CEA114-EVL-03: The evaluator must report Candidate accuracy for all three arms.
- CEA114-EVL-04: The evaluator must report positive and negative accuracy for all three arms.
- CEA114-EVL-05: The evaluator must report each recovery and regression by arm.
- CEA114-EVL-06: The evaluator must report repetition stability by case and arm.
- CEA114-EVL-07: The evaluator must report strict raw-output validity separately.
- CEA114-EVL-08: `supported` requires complete evidence and stable repetitions.
- CEA114-EVL-09: `supported` requires higher Introducer Trim accuracy than Baseline.
- CEA114-EVL-10: `supported` requires at least one Introducer Trim recovery.
- CEA114-EVL-11: `supported` requires zero Introducer Trim regressions.
- CEA114-EVL-12: `falsified` requires no Introducer Trim recovery or no accuracy gain.
- CEA114-EVL-13: `mixed` requires an accuracy gain with a failed safety gate.
- CEA114-EVL-14: `inconclusive` requires incomplete, unresolved, or unstable evidence.

### Evidence package

- CEA114-PKG-01: The package must preserve preflight, report, review, handoff, run, and status files.
- CEA114-PKG-02: The review must show each Source, Authoritative Candidate, and Target Event.
- CEA114-PKG-03: The review must show each Rendered Candidate and Removed Boundary.
- CEA114-PKG-04: The review must show every exact model input and raw output.
- CEA114-PKG-05: The handoff must cite every direct file digest and report fingerprint.
- CEA114-PKG-06: The package must report zero ProposedChanges and accepted Ledger writes.

## 4. Proposed Architecture

```text
sealed CEA-1.13 cases
          |
          v
deterministic marker views
       /             \
      v               v
Structural Trim   Introducer Trim
      |               |
      +------ Qwen ---+
              |
              v
 occurrence-level comparison
```

The Application Layer owns exact Rendered Candidate construction.

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
  |            |-- each view ------------>|
  |            |<--------------- Y/N/U ---|
  |            |-- compare --->|           |
  |<-- paths --|             |            |
```

## 6. Data Model

CEA-1.14 adds experimental Application DTOs for marker views, observations, cases, and reports.

Each marker view binds one Rendered Candidate to one Authoritative Candidate.

CEA-1.14 adds no Domain Core record or Ledger schema.

## 7. APIs / Interfaces

The runner accepts one complete CEA-1.13 root and one absent experiment root.

Preparation writes a digest-bound preflight before model execution.

Execution writes one typed record for each arm and repetition.

Finalization writes one report, review, handoff, and status record.

## 8. Behavior & Domain Rules

- Exact source characters remain authoritative.
- The model-visible marker can move inside the Authoritative Candidate.
- The Authoritative Candidate remains the scored occurrence.
- KoteKomi performs every range operation and answer mapping.
- Qwen answers one semantic question about one supplied Rendered Candidate.
- Probability evidence cannot repair invalid raw output.
- Production Attachment selection remains unchanged.
- The Pipeline writes no ProposedChange or accepted Ledger record.

## 9. Acceptance Criteria

- CEA114-ACC-01: Tests prove both marker algorithms on leading and trailing boundaries.
- CEA114-ACC-02: Tests prove each Rendered Candidate remains source-exact and contains its Target Event.
- CEA114-ACC-03: Tests prove the renderer preserves the Passage and recomputes Remainder Parts.
- CEA114-ACC-04: Tests prove marker views never change the Authoritative Candidate.
- CEA114-ACC-05: Tests prove the four outcome classes are mutually exclusive.
- CEA114-ACC-06: Tests reject missing, foreign, or duplicate observations.
- CEA114-ACC-07: Focused formatting, lint, typecheck, and tests pass.
- CEA114-ACC-08: Model-free preparation validates the sealed predecessor package.
- CEA114-ACC-09: The human-run experiment preserves every model execution.
- CEA114-ACC-10: The package reports zero canonical writes.

## 10. Reference Implementations

- Exact ranges: `competitive_attachment_residual_ownership.py`.
- Bounded execution: `competitive_attachment_edge_filter_preview.py`.
- Runtime contract: `run_competitive_attachment_partwise_residual_ownership.py`.
- Paired evaluation: `competitive_attachment_partwise_residual_ownership.py`.

## 11. Constraints and Halt Conditions

- Stop when one Rendered Candidate leaves its Authoritative Candidate.
- Stop when one Rendered Candidate excludes any Target Event character.
- Stop when the ten Candidate-level Gold answers change.
- Stop when Gold enters one model input.
- Stop when one execution lacks a typed ModelRun or stage trace.
- Stop when one arm uses a foreign model identity.
- Stop when an action would execute validation tasks.
- Stop when an action would write canonical intelligence.
- Stop before production integration regardless of the experimental outcome.

## 12. Experimental Outcome

CEA-1.14 completed on September 21, 2026.

The archived Baseline answered seven of ten cases correctly.

The fresh Structural Trim Arm answered seven of ten cases correctly.

The fresh Introducer Trim Arm answered eight of ten cases correctly.

All forty model executions returned one strict finite answer.

Both fresh arms were stable on all ten cases.

The Introducer Trim Arm recovered one false negative and regressed no correct case.

The typed evaluator therefore returned `supported` under the accepted TDD.

Independent review reconciled every headline metric, file digest, source range, model identity, and generation setting.

The review also established that only three cases received a distinct Introducer input.

Only one perturbed case was a previously correct case, and no perturbed case had Gold answer `N`.

The sole recovery changed both Candidate marker placement and Candidate Remainder enumeration.

Its Remainder inventory contracted from two parts to one part at the same time that its answer changed from stable `N` to stable `Y`.

The other leading-`that` false negative retained two Remainder parts and remained stable `N`.

CEA-1.14 therefore supports its literal existential acceptance gate but does not identify marker placement as the cause.

The reviewed mechanism outcome is `inconclusive`.

The stored report remains unchanged as historical execution evidence.

CEA-1.15 isolates explicit Remainder enumeration while preserving the Authoritative Candidate marker.
