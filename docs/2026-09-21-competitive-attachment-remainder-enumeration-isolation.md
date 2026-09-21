# TDD: CEA-1.15 Remainder Enumeration Isolation

- Status: Implemented; marker movement unnecessary; cardinality unresolved; production inactive
- Deliverable ID: `CEA-1.15`
- Program:
  [Competitive Event Attachment Program](2026-09-18-competitive-event-attachment-program.md)
- Predecessor:
  [CEA-1.14 Candidate Marker Boundary Ablation](2026-09-21-competitive-attachment-candidate-marker-boundary-ablation.md)

## 1. Context & Problem

CEA-1.14 moved one leading introducer outside the model-visible Candidate marker.

That manipulation recovered one stable false negative without a measured regression.

The recovered task also changed from two explicitly enumerated Candidate Remainder parts to one part.

The experiment therefore changed both marker placement and Remainder enumeration.

The harder leading-`that` false negative retained two Remainder parts and did not recover.

Every single-part arm in CEA-1.14 answered `Y`.

The current evidence cannot distinguish a Candidate-marker effect from an explicit-enumeration effect.

### Terms

**Authoritative Candidate** means the unchanged exact Candidate range inherited from CEA-1.14.

**Authoritative Remainder** means every exact Authoritative Candidate range outside its Target Event.

**Filtered Remainder** means an exact source subrange produced by moving one leading `that` token and its following whitespace outside the explicit Remainder marker.

**Enumeration-only task** means a model task with the Authoritative Candidate marker, unchanged passage, unchanged Target Event, unchanged prompt, and Filtered Remainders.

**Recovered case** means `aro_e05ad7d4c4c93ca6ceac7a6d`.

**Hard control** means `aro_7d658622da90db3299ebee76`.

### Hypothesis

> Explicitly omitting the leading `that` token from Candidate Remainder enumeration while preserving the Authoritative Candidate marker reproduces the CEA-1.14 recovery.

### Primary flow

1. KoteKomi validates the complete CEA-1.14 evidence package and independent review.
2. KoteKomi selects the recovered case and hard control by exact inherited task ID.
3. KoteKomi derives Filtered Remainders from authoritative source characters.
4. Qwen judges each Enumeration-only task twice with the unchanged Whole Arm prompt.
5. KoteKomi compares fresh answers with the sealed Structural and Introducer answers.

CEA-1.15 creates experimental evidence only.

## 2. Goals

- Keep each Candidate marker byte-for-byte identical to its Authoritative Candidate marker.
- Change only the explicitly enumerated leading `that` Remainder text.
- Preserve exact model input and raw output for all four judgments.
- Distinguish part-inventory sufficiency from marker-placement necessity.
- Produce one self-contained second-opinion handoff.

## 3. Requirements

### Predecessor evidence

- CEA115-EVD-01: The Pipeline must validate the complete CEA-1.14 package.
- CEA115-EVD-02: The Pipeline must require the completed CEA-1.14 independent review.
- CEA115-EVD-03: The Pipeline must reuse the exact recovered case and hard control.
- CEA115-EVD-04: The Pipeline must preserve each inherited Authoritative Candidate, Target Event, and Gold answer.
- CEA115-EVD-05: The Pipeline must record CEA-1.14's typed outcome as `supported` and reviewed mechanism outcome as `inconclusive`.
- CEA115-EVD-06: Gold must remain outside every model input.
- CEA115-EVD-07: Every direct input must carry a file digest.

### Filtered enumeration

- CEA115-RND-01: KoteKomi must derive each Filtered Remainder from authoritative source characters.
- CEA115-RND-02: The Candidate range and Candidate marker must remain unchanged.
- CEA115-RND-03: The Target Event range and Event marker must remain unchanged.
- CEA115-RND-04: The full passage must remain unchanged.
- CEA115-RND-05: KoteKomi may filter only one leading case-insensitive `that` token and its following whitespace from the prefix Remainder.
- CEA115-RND-06: KoteKomi must omit the prefix Remainder when no source character remains after filtering.
- CEA115-RND-07: KoteKomi must preserve the source-exact residual prefix when content remains after filtering.
- CEA115-RND-08: KoteKomi must preserve every other Remainder range unchanged.
- CEA115-RND-09: KoteKomi must preserve the filtered token as an exact omitted source range.
- CEA115-RND-10: No Filtered Remainder can overlap the Target Event or leave the Authoritative Candidate.

### Model task

- CEA115-MOD-01: Both cases must use the exact CEA-1.14 prompt unchanged.
- CEA115-MOD-02: Qwen must return exactly one `Y`, `N`, or `U` character.
- CEA115-MOD-03: Both cases must use temperature `0`, seed `17`, ten alternatives, and frequency penalty `0.0`.
- CEA115-MOD-04: Both cases must request two output tokens.
- CEA115-MOD-05: Both cases must execute two repetitions.
- CEA115-MOD-06: All four executions must use one model identity and one runtime contract.
- CEA115-MOD-07: Validation tasks must remain unexecuted.

### Evaluation

- CEA115-EVL-01: The evaluator must preserve sealed Structural and Introducer answers separately from fresh answers.
- CEA115-EVL-02: The evaluator must report exact answers for both cases and both repetitions.
- CEA115-EVL-03: The evaluator must report strict finite-output validity and repetition stability.
- CEA115-EVL-04: `supported` requires stable fresh `Y/Y` for the recovered case.
- CEA115-EVL-05: `falsified` requires stable fresh `N/N` for the recovered case.
- CEA115-EVL-06: `inconclusive` requires an unresolved, unstable, or different recovered-case result.
- CEA115-EVL-07: The evaluator must classify the secondary mechanism as `part_inventory_sufficient` when the recovered case is `Y/Y` and the hard control remains `N/N`.
- CEA115-EVL-08: The evaluator must classify the secondary mechanism as `introducer_enumeration_sufficient` when both cases become `Y/Y`.
- CEA115-EVL-09: The evaluator must classify the secondary mechanism as `marker_effect_remains` when the recovered case remains `N/N`.
- CEA115-EVL-10: The evaluator must not claim false-positive safety because no Gold-`N` case is eligible.

### Evidence package

- CEA115-PKG-01: The package must preserve preflight, report, review, handoff, run, and status files.
- CEA115-PKG-02: The review must show each exact Source, Candidate, Target Event, Authoritative Remainder, Filtered Remainder, and omitted range.
- CEA115-PKG-03: The review must show every exact model input and raw output.
- CEA115-PKG-04: The handoff must cite every direct file digest and report fingerprint.
- CEA115-PKG-05: The package must report zero ProposedChanges and accepted Ledger writes.

## 4. Proposed Architecture

```text
sealed CEA-1.14 cases
          |
          v
fixed Authoritative Candidate marker
          |
          v
source-exact Remainder enumeration filter
          |
          v
four bounded Qwen judgments
          |
          v
mechanism comparison
```

The Application Layer owns exact Filtered Remainder construction and rendering.

The ModelRuntime Port owns bounded Qwen execution.

The Pipeline owns predecessor validation, evaluation, and review rendering.

The disposable runner composes the experiment.

The human starts and monitors the live run.

## 5. Key Interactions

```text
Human       Runner       KoteKomi       Qwen
  |            |             |            |
  |-- start -->|             |            |
  |            |-- filter -->|            |
  |            |-- each task ------------>|
  |            |<--------------- Y/N/U ---|
  |            |-- compare --->|           |
  |<-- paths --|             |            |
```

## 6. Data Model

CEA-1.15 adds experimental Application DTOs for enumeration views, observations, case evaluations, and reports.

Each view binds Filtered Remainders and omitted source ranges to one unchanged Authoritative Candidate task.

CEA-1.15 adds no Domain Core record or Ledger schema.

## 7. APIs / Interfaces

The runner accepts one complete CEA-1.14 root and one absent experiment root.

Preparation writes a digest-bound preflight before model execution.

Execution writes one typed record for each case and repetition.

Finalization writes one report, review, handoff, and status record.

## 8. Behavior & Domain Rules

- Exact source characters remain authoritative.
- The Candidate marker remains fixed.
- Only explicit Remainder enumeration changes.
- KoteKomi performs every range operation and answer mapping.
- Qwen answers the unchanged bounded semantic question.
- The mechanism result cannot establish false-positive safety or production readiness.
- Production Attachment selection remains unchanged.
- The Pipeline writes no ProposedChange or accepted Ledger record.

## 9. Acceptance Criteria

- CEA115-ACC-01: Tests prove exact leading-`that` filtering for both an exhausted and retained prefix Remainder.
- CEA115-ACC-02: Tests prove Candidate, Event, passage, prompt, and task identity remain unchanged.
- CEA115-ACC-03: Tests prove every Filtered Remainder is source-exact and ordered.
- CEA115-ACC-04: Tests prove all outcome and secondary-mechanism classes.
- CEA115-ACC-05: Tests reject missing, duplicate, or foreign observations.
- CEA115-ACC-06: Focused formatting, lint, typecheck, and tests pass.
- CEA115-ACC-07: Model-free preparation validates the sealed predecessor package.
- CEA115-ACC-08: The human-run experiment preserves four complete model executions.
- CEA115-ACC-09: The package reports zero canonical writes.

## 10. Reference Implementations

- Exact ranges: `competitive_attachment_residual_ownership.py`.
- Bounded execution: `competitive_attachment_edge_filter_preview.py`.
- Runtime contract: `run_competitive_attachment_candidate_marker_boundary.py`.
- Paired evaluation: `competitive_attachment_candidate_marker_boundary.py`.

## 11. Constraints and Halt Conditions

- Stop when a Candidate, Event, passage, prompt, or Gold answer changes.
- Stop when a Filtered Remainder is not an exact subrange of its Authoritative Remainder.
- Stop when Gold enters one model input.
- Stop when one execution lacks a typed ModelRun or stage trace.
- Stop when one execution uses a foreign model identity.
- Stop when an action would execute validation tasks.
- Stop when an action would write canonical intelligence.
- Stop before production integration regardless of the experimental outcome.

## 12. Experimental Outcome

CEA-1.15 completed on September 21, 2026.

The report preserved four strict finite outputs under one model identity and runtime contract.

Both repetitions were byte-identical within each case.

The recovered case changed from sealed Structural `N/N` to fresh `Y/Y` while retaining the full Authoritative Candidate marker.

The hard control remained `N/N`.

One of two Gold-`Y` cases therefore passed.

No ProposedChange or accepted Ledger write occurred.

The typed report returned `supported` and `part_inventory_sufficient` under the accepted evaluator.

Independent review and local verification reconciled all direct and predecessor digests, exact inputs, raw outputs, runtime settings, and finite-label probabilities.

The evidence establishes that Candidate-marker movement was not necessary for the recovered case.

The `part_inventory_sufficient` label is broader than the evidence because the successful manipulation both omitted the explicit `that` Remainder and reduced the displayed inventory from two parts to one.

The reviewed mechanism conclusion is therefore `cardinality_unresolved`.

CEA-1.16 splits the same remaining characters into two adjacent parts without changing any source character or marker.
