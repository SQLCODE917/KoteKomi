# TDD: Selectable-Pool Floor

- Status: Accepted
- Deliverable ID: `R9`
- Program: [Source-Grounded Attachment Deterministic-First Package](2026-09-24-source-grounded-attachment-deterministic-first-package.md)
- Parent: [Parser-Constituent Candidate Filter](2026-09-30-parser-constituent-candidate-filter.md)
- Depends on: [Selection Label and Capture](2026-09-30-selection-label-and-capture.md)

## 1. Context & Problem

run-004 applied every R8 Candidate filter before rendering.

Event AHE-051 began with 7 syntax-attached candidates.

The filters narrowed the pool to 2 Selectable candidates.

The model answered `NONE` against the pool of 2.

The answer routed AHE-051 to residual review with reason `composition_hold`.

R8 never bounds the minimum pool size before rendering.

A pool of 2 makes one finite subset selection task near-degenerate.

The model abstains from a near-empty pool instead of selecting.

R9 adds one minimum Selectable pool size that the derivation preserves.

### Terms

**Selectable-pool floor** means the minimum Selectable candidate count the derivation preserves before rendering.

The Selectable-pool floor default is `3`.

**Hard filter** means the trigger filter or the core filter.

The hard filters preserve the R8 correctness invariants.

**Precision filter** means the function-word filter, the artifact filter, the dedup filter, or the nested filter.

The precision filters raise precision but can over-narrow.

**Relaxation level** means the set of precision filters the derivation skips.

Relaxation level `0` skips no precision filter.

Relaxation level `1` skips the nested filter.

Relaxation level `2` skips the nested and dedup filters.

Relaxation level `3` skips the nested, dedup, and artifact filters.

Relaxation level `4` skips every precision filter.

**Pool-floor relaxation record** means one report record that names one Event, its Relaxation level, and its Selectable count before and after relaxing.

The terms Selectable candidate, Candidate filter, and Boundary gap keep the meanings the Parser-Constituent Candidate Filter TDD defines.

The term Selection Score keeps the meaning the Selection Label and Capture TDD defines.

The term residual review keeps the meaning the Calibrated Residual Ownership TDD defines.

### Primary flow

1. The runner derives the syntax-attached candidates, unchanged.
2. The Application Layer applies the hard filters and each precision filter in fixed order.
3. The Application Layer measures the survivor count.
4. The Application Layer relaxes precision filters in reverse order until the survivor count meets the floor.
5. The runner renders one selection task over the relaxed Selectable list under the Event frame.
6. The scorer captures the answer and computes the Selection Score, unchanged.
7. The router sends an uncertain, rejected, or `NONE` selection to residual review, unchanged.
8. The report records one Pool-floor relaxation record per relaxed Event.

## 2. Goals

- Operators observe no selection task rendered below the floor when the attached pool holds at least the floor many candidates.
- Operators observe one Pool-floor relaxation record per Event whose derivation relaxed.
- Operators observe zero Boundary gaps after relaxation.
- Operators observe the parser and the scorer still agree on every relaxed selection task.

## 3. Requirements

- R9-FLR-01: The Application Layer applies the R8 filters in the fixed order before measuring.
- R9-FLR-02: The hard filters stay applied at every Relaxation level.
- R9-FLR-03: The Selectable-pool floor default equals `3`.
- R9-FLR-04: The Application Layer selects the lowest Relaxation level whose survivor count meets the floor.
- R9-FLR-05: The Application Layer skips precision filters in reverse order: nested, then dedup, then artifact, then function-word.
- R9-FLR-06: The derivation reads no Gold and invokes no model.
- R9-FLR-07: The relaxed derivation never changes the inventory the Boundary-gap detector reads.
- R9-FLR-08: Parser and scorer label-set parity holds on a relaxed render.
- R9-FLR-09: The report records one Pool-floor relaxation record per relaxed Event.
- R9-FLR-10: An Event whose attached count sits below the floor reaches residual review with reason `no_selectable` and renders no task.

## 4. Proposed Architecture

```text
syntax-attached candidates
             |
             v
 hard filters (trigger, core)  ----- never skipped
             |
             v
 precision filters, newest first (nested, dedup, artifact, function-word)
             |
             v
 survivor count meets the floor?
   yes -> render and score
   no  -> skip the newest precision filter and recount
```

## 5. Key Interactions

The Selectable derivation runs the R8 filters, then checks the survivor count against the floor.

The Selectable derivation walks the Relaxation levels from `0` upward.

It stops at the first level whose survivor count meets the floor.

The renderer renders the relaxed Selectable list under the Event frame, unchanged.

The report builder collects one Pool-floor relaxation record per relaxed Event.

The scorer and the router stay unchanged.

## 6. Data Model

The Selectable derivation returns one Selectable list plus one Relaxation level and the Selectable counts before and after relaxing.

The report gains one ordered Pool-floor relaxation record tuple.

One Pool-floor relaxation record carries four fields.

The `event_id` field names the Event.

The `relaxation_level` field carries an integer from `0` through `4`.

The `selectable_count_before` field carries the survivor count after the full filter order.

The `selectable_count_after` field carries the survivor count after relaxation.

The record rejects a negative count.

The record rejects a Relaxation level outside `0` through `4`.

## 7. APIs / Interfaces

The public Selectable derivation entry point is `derive_selectable_constituents`.

The public renderer entry point is `render_event_frame_selection_task`.

The public routing entry point is `route_selection_scores`.

The public report builder entry point is the report stage in `scripts/run_calibrated_residual_ownership.py`.

## 8. Behavior & Domain Rules

Relaxation level `0` keeps every precision filter.

Relaxation level `4` keeps only the hard filters and drops every precision filter.

The derivation keeps the trigger and the core filters applied at every level.

The nested filter keeps the containing candidate and removes the contained candidate; relaxation skips the filter, it never inverts the direction.

The derivation never repairs, coerces, or re-orders candidates.

The derivation only skips filter sets.

The Boundary-gap detector still reads the full inventory, so relaxation never changes Boundary Fidelity.

An Event whose attached count sits below the floor uses level `4` and routes to residual review with `no_selectable`.

## 9. Acceptance Criteria

- AC-R9-FLR-01: Tests prove the hard filters stay applied at Relaxation level `4`.
- AC-R9-FLR-02: Tests prove the Selectable-pool floor default equals `3`.
- AC-R9-FLR-03: Tests prove the derivation selects the lowest Relaxation level whose survivor count meets the floor.
- AC-R9-FLR-04: Tests prove the precision filters skip in reverse order.
- AC-R9-FLR-05: Tests prove a seven-to-two narrowing relaxes to at least the floor.
- AC-R9-FLR-06: Tests prove the derivation reads no Gold and invokes no model.
- AC-R9-FLR-07: Tests prove the relaxed derivation does not change the inventory the Boundary-gap detector reads.
- AC-R9-FLR-08: Tests prove parser and scorer label-set parity holds on a relaxed render.
- AC-R9-FLR-09: Tests prove the report records one Pool-floor relaxation record per relaxed Event.
- AC-R9-FLR-10: Tests prove an attached count below the floor routes to residual review with `no_selectable` and renders no task.
- AC-R9-ALL: Focused formatting, lint, typecheck, and tests pass.

## 10. Reference Implementations

- Selectable derivation: `packages/application/src/kotekomi_application/calibrated_residual_ownership.py` (`derive_selectable_constituents`).
- Renderer: `packages/application/src/kotekomi_application/calibrated_residual_ownership.py` (`render_event_frame_selection_task`).
- Routing: `packages/application/src/kotekomi_application/calibrated_residual_ownership.py` (`route_selection_scores`).
- Runner and report: `scripts/run_calibrated_residual_ownership.py`.
- Application tests: `packages/application/tests/test_parser_constituent_candidate_filter.py`, `packages/application/tests/test_calibrated_residual_ownership.py`.

## 11. Constraints and Halt Conditions

- Do not change the candidate inventory the Boundary-gap detector reads.
- Do not relax the trigger or the core filter.
- Do not change the `C1..C<n>` Candidate labels or the finite answer parser.
- Stop when relaxation introduces any nonzero Boundary gap.
- Stop when parser-scorer parity fails on any relaxed Event.
- Stop when a relaxed Event renders below the floor while its attached count meets the floor.

## 12. Execution & Experimentation Directive

- Implement and test this TDD.
- Run `scripts/run_calibrated_residual_ownership.py` over the held-out partition and derive insights from the run.
- Iteratively improve the Selectable derivation while the improvement is reasonable.
- Commit between each deliverable and each experiment.
- Commit before each experiment so an unsuccessful change can be reverted while preserving the learnings.

## 13. Run Record

R9 measured the held-out Anthropic/DoD partition once under `scripts/run_calibrated_residual_ownership.py`.

The run root is `data/r6-calibrated-residual-ownership-runs/run-005`.

The sealed result fingerprint is `61efb0e36d18549852a36752872e909b40bfd5ad73a505231ba0f5e6845ef671`.

The Selection Score threshold is `-1.0`.

The derivation relaxed exactly one of the 53 Events: `AHE-051` at Relaxation level `3`, from 2 Selectable candidates to 4.

The relaxation recovered the artifact-text candidate `[45]` and the nested `45` candidate before rendering.

The Boundary-gap detector still read the full inventory; the run records zero Boundary gaps.

No Event rendered below the floor.

No Event carried a Selectable count below the floor; the `no_selectable` path produced zero Events.

The residual-review set is unchanged from run-004: `AHE-004` (`rejected`), `AHE-022` (`rejected`), `AHE-051` (`composition_hold`).

The model answered `NONE` against `AHE-051` under both the 2-candidate pool (run-004) and the relaxed 4-candidate pool (run-005).

The near-empty-pool hypothesis is falsified for the motivating case; relaxing the pool did not change the model abstention.

The Selectable-pool floor is necessary but not sufficient for `AHE-051`; the residual composition hold needs a follow-up deliverable beyond R9.