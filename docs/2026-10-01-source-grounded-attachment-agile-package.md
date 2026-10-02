# Source-Grounded Attachment Agile Package

- Status: Proposed
- Package ID: `source-grounded-attachment-agile`
- Parent: [Competitive Event Attachment Program](2026-09-18-competitive-event-attachment-program.md)
- Predecessor: [Source-Grounded Attachment Deterministic-First Package](2026-09-24-source-grounded-attachment-deterministic-first-package.md)
- First deliverable: [R10 Residual Composition-Hold Routing](2026-10-01-residual-composition-hold-routing.md)
- Next deliverable: R12 Label-mismatch recovery (`rejection_label_mismatch` for `AHE-004`)

## Context & Problem

This package is the experiment-driven execution spine for the remaining source-grounded attachment work.

The Deterministic-First Package delivered R1 through R9.

R10 names one typed disposition per residual Event.

R10 separates selection failure from composition hold.

The three Events do not share one failure class.

Every residual Event fails at the selection layer; none reaches the deterministic composer.

This package turns each observed selection diagnosis into one iterative TDD.

### The spine (report)

KoteKomi turns one PDF into one source-grounded attributed statement through four stages.

Stage one identifies the exact Event expression from one SourceSegment.

Stage two attaches the exact source occurrences that complete the Event proposition.

Stage three assembles the ordered fragment set into one decontextualized proposition.

Stage four assigns arguments and emits one `attributed_statement` Assertion.

Stage four ships deterministically through the Event Attribution Production Wiring Package.

Stages two and three failed under the model-first Competitive Event Attachment Program.

The Deterministic-First Package replaced the model-first route with syntax-first routing.

R1 delivered the dependency-path router.

R2 corrected the Attachment Gold segmentation artifact.

R3 and R3-A replaced boundary drawing with parser-constituent selection.

R4 assembled selected fragments into one content triple plus one attribution, or a typed hold.

R5 measured transfer on the held-out partition once.

R6 closed the boundary gap, rendered one Event frame, and gated selection on a Selection Score threshold.

R7 captured one full token-sequence Selection Score free of the shared-label collision.

R8 shrunk each pool with five deterministic Candidate filters.

R9 preserved each pool at or above the Selectable-pool floor.

run-005 measures the held-out Anthropic/DoD partition.

The Selection Score threshold is `-1.0`.

The run records zero Boundary gaps, zero canonical writes, and zero ProposedChanges.

The run records 53 model executions.

50 Events reach accepted selection.

3 Events stay in residual review: `AHE-004`, `AHE-022`, and `AHE-051`.

`AHE-004` routes to residual review with reason `rejected`.

`AHE-022` routes to residual review with reason `rejected`.

`AHE-051` routes to residual review with reason `composition_hold`.

R9 relaxes `AHE-051` from 2 to 4 Selectable candidates.

The model answers `NONE` against the relaxed 4-candidate pool.

The near-empty-pool hypothesis is falsified for `AHE-051`.

R10 maps each frozen run-005 residual Event to one selection-layer disposition.

`AHE-004` carries the disposition `selection_rejected`.

`AHE-022` carries the disposition `selection_rejected`.

`AHE-051` carries the disposition `selection_abstained`.

No residual Event carries the disposition `composition_hold`.

R11 targets the selection layer and names the exact failure slot per residual Event.

### Blocker taxonomy

The report classifies the remaining blockers into four classes.

**Boundary gap** means one Gold fragment whose exact source span no candidate carries.

R6 closed every development Boundary gap.

**Selection over-selection** means the model selects too many candidates with near-certain probability.

R6, R7, R8, and R9 reduced over-selection.

R10 names the two remaining Events `selection_rejected`.

R11 names the exact rejection reason behind `selection_rejected`.

**Selection abstention** means the model returns `NONE` against a well-formed pool.

`AHE-051` is the only selection abstention.

**Composition hold** means a completed selection that the deterministic composer cannot assemble.

R10 reserves the name `composition_hold` for the composer.

R10 renames the `NONE` answer to `selection_abstained`.

R10 confirms no residual Event is a composition hold.

R11 targets the selection layer that R10 exposed.

### R11 result

R11 classifies the three frozen residual selection answers into one closed slot each.

`AHE-004` lands in `rejection_label_mismatch` and is recoverable.

Its raw answer names `C1` plus an `E2` the model explains as a mislabeled `C2`.

`AHE-022` lands in `rejection_no_valid_label` and is not recoverable.

Its raw answer is free prose with zero candidate labels.

`AHE-051` lands in `abstained` and is not recoverable.

Its raw answer is exactly `NONE`.

Only `rejection_label_mismatch` enables automatic label recovery.

The R11 selection-failure diagnosis is adopted as the durable zero-write diagnosis layer.

The next logical step iterates on the one recoverable slot.

### Conclusion

Keep the deterministic-first route.

Reserve the model for the residual cases.

The residual Events fail at selection before the composer runs.

Name the exact selection-failure slot for each residual Event before spending model budget.

Never let a hold become accepted state without a completed selection and a completed composition.

### Terms

**Spine** means this package's report section that any agent can read to understand the whole task.

**Experiment** means one repeatable prediction that one implementation run confirms or rejects.

**Derisk** means to spend the least budget that tests the riskiest assumption.

**Observe** means to record the actual run result as durable evidence.

**Next logical step** means the one deliverable the observed result now justifies.

The terms Boundary gap, Event frame, Syntax-attached candidate, Selection Score, Selectable candidate, and Residual review keep the meanings the Deterministic-First Package defines.

The terms Content triple, Attribution, and hold keep the meanings the Decontextualization Composition TDD defines.

### The Agile loop

This package runs one four-step cycle per deliverable.

1. Make the plan. Write the spine and the roadmap in this package.

2. Make the first MVP TDD. Write one TDD that derisks the riskiest assumption.

3. Implement, verify, observe. Implement the TDD, run focused tests, then run the experiment and record the result.

4. Decide the next logical step. Read the observed result and write the next TDD, or pivot.

Repeat the cycle until the residual is closed or the plan is falsified.

Each TDD links back to this package and forward to the next TDD.

An agent that finds any artifact can recover the roadmap and continue the cycle.

## Roadmap

| Deliverable | Title | Purpose | Status |
|---|---|---|---|
| R10 | Residual Composition-Hold Routing | one typed disposition per residual Event plus one held-safety invariant | Accepted |
| R11 | Selection-Failure Slot Routing | one selection-failure slot per residual Event plus one recoverability marker | Accepted |
| R12 | Label-mismatch recovery | fold the one recoverable rejection_label_mismatch slot back into a completed selection and re-measure | Planned |

The observed R11 result specifies R12: recover the one recoverable `rejection_label_mismatch` slot (`AHE-004`).

The not-recoverable slots (`rejection_no_valid_label`, `abstained`) stay out of automatic recovery.

## Order

Read the spine before writing any deliverable.

Write one TDD per cycle.

Commit between the TDD, the implementation, and each experiment.

Record each observable result in the TDD Run Record section.

Never read the held-out partition to tune a decision.

## Completion

The package completes when no residual Event fails to reach a completed selection and a completed composition.

The package completes when one held-out run measures zero Boundary gaps and zero fabricated roles.

The package completes when each held Event carries one typed reason and no composed content.