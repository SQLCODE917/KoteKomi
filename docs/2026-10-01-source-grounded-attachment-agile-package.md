# Source-Grounded Attachment Agile Package

- Status: Proposed
- Package ID: `source-grounded-attachment-agile`
- Parent: [Competitive Event Attachment Program](2026-09-18-competitive-event-attachment-program.md)
- Predecessor: [Source-Grounded Attachment Deterministic-First Package](2026-09-24-source-grounded-attachment-deterministic-first-package.md)
- First deliverable: [R10 Residual Composition-Hold Routing](2026-10-01-residual-composition-hold-routing.md)

## Context & Problem

This package is the experiment-driven execution spine for the remaining source-grounded attachment work.

The Deterministic-First Package delivered R1 through R9.

R9 leaves three held-out Events in residual review.

The three Events do not share one failure class.

No deliverable traces a residual Event through the deterministic composer to name the exact missing slot.

This package turns that diagnosis into an iterative, experiment-driven plan.

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

### Blocker taxonomy

The report classifies the remaining blockers into four classes.

**Boundary gap** means one Gold fragment whose exact source span no candidate carries.

R6 closed every development Boundary gap.

**Selection over-selection** means the model selects too many candidates with near-certain probability.

R6, R7, R8, and R9 reduced over-selection.

The two `rejected` Events remain.

**Selection abstention** means the model returns `NONE` against a well-formed pool.

`AHE-051` is the only selection abstention.

**Composition hold** means a completed selection that the deterministic composer cannot assemble.

The routing reason `composition_hold` currently names only the `NONE` answer.

A composer hold names the exact missing slot instead.

No deliverable distinguishes selection abstention from composition hold.

### Conclusion

Keep the deterministic-first route.

Reserve the model for the residual cases.

Trace each residual Event through the deterministic composer before spending model budget.

Name the exact missing slot for each residual Event.

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
| R11 | Residual slot completion experiment | one modeled experiment that targets the slot R10 names | Planned |
| R12 | Divergent residual recycle | fold the observed result into selection or composition and re-measure | Planned |

R11 and R12 are slots, not specifications.

The observed R10 result decides what R11 specifies.

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