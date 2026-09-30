# TDD: Calibrated Residual Ownership

- Status: Accepted
- Deliverable ID: `R6`
- Program: [Source-Grounded Attachment Deterministic-First Package](2026-09-24-source-grounded-attachment-deterministic-first-package.md)
- Parent: [Competitive Event Attachment Program](2026-09-18-competitive-event-attachment-program.md)
- Depends on: [R5 Evaluation Remediation](2026-09-28-evaluation-remediation.md)

## 1. Context & Problem

R5 measured transfer on the held-out Anthropic/DoD partition once.

The error-type census records the 53 held-out Events: 0 ok, 37 boundary_miss, 53 selection_error, 23 composition_hold, 1 content_error, 8 attribution_error, and 6 polarity_modality_error.

Two mechanisms dominate the failure.

First, `boundary_miss` is deterministic. The R3-A parser-constituent pool omits 37 Gold fragments at their exact boundaries. The model never sees those fragments, so no selection can recover them. This is a candidate-coverage gap, not a model error.

Second, `selection_error` is semantic. The current selection task renders a bare "return a subset" instruction over every token group without an Event frame. The local model therefore over-selects, and the first-position Selection Scores sit near log `0` — the over-selection is certain, not uncertain.

The Verdict named the fix: the model selects among syntax-attached candidates and never draws boundaries; calibration (the logprob threshold) is the primary knob before any prompt rewrite; and the model stays reserved for the residue — nominal predicates, sense selection, and genuine ambiguity.

R6 implements that split: it closes the deterministic boundary gap, constrains the model to the syntax-attached constituents of one Event, and gates every selection on its Selection Score, routing uncertain Events to a residual review rather than accepting a certain wrong answer.

### Terms

**Boundary gap** means one Gold fragment whose exact source span no candidate carries.

**Event frame** means the Event trigger and its R1 syntax-attached core constituents rendered once per selection task.

**Syntax-attached candidate** means a parser constituent whose token span the R1 dependency-path router attaches to the Event trigger head.

**Selection Score threshold** means one calibrated first-position natural-log-probability cutoff; a selection at or below the threshold routes to residual review.

**Residual review** means the deterministic or modeled step that owns an Event whose selection is uncertain or whose composition held.

**Calibration knob** means the Selection Score threshold adjusted before any prompt rewrite.

### Primary flow

1. R6 re-derives the R3-A constituent pool and adds the sub-span candidates needed so every development Gold fragment boundary is carried by one candidate; the runner fails fast on any remaining gap.
2. The R1 dependency-path router marks each candidate attached, not-attached, or model-review against the Event trigger head.
3. The selection task renders one Event frame — the trigger plus the syntax-attached core constituents — and asks the local model to select only among those candidates.
4. The runner captures Token Probability Evidence per Event and computes the Selection Score.
5. A Selection Score at or below the calibrated threshold routes the Event to residual review; a score above the threshold may only produce accepted selection when syntax also attaches.
6. The composer assembles the selected fragments; any Event left in `composition_hold` or `attribution_ambiguous` goes to residual review, never to fabricated state.

## 2. Goals

- Every development Gold fragment boundary is carried by one candidate.
- The local model selects only among syntax-attached candidates under one Event frame.
- Every selection carries a Selection Score and a threshold decision.
- The model stays reserved for residual Events the deterministic route cannot close.
- No catalog read tunes a decision.

## 3. Requirements

### Boundary coverage

- R6-BND-01: The runner re-derives the R3-A constituent pool and adds sub-span candidates so every development Gold fragment boundary is carried by one candidate.
- R6-BND-02: The runner fails fast, with one typed Boundary Gap per fragment ID, when a Gold fragment boundary remains uncovered.

### Event frame and attachment

- R6-FRM-01: The selection task renders one Event frame per Event with the trigger and its syntax-attached core constituents only.
- R6-ATT-01: The selection task contains zero candidate that the R1 router does not attach to the Event trigger head.
- R6-ATT-02: A candidate the R1 router marks not-attached never enters a selection task.

### Calibration

- R6-CAL-01: Every Event selection records Token Probability Evidence and one Selection Score.
- R6-CAL-02: A Selection Score at or below the calibrated threshold routes the Event to residual review.
- R6-CAL-03: A censored Selection Score lists its Event in the residual-review set by Event ID.

### Residual reservation

- R6-RES-01: The local model is invoked only for Events the deterministic route cannot close.
- R6-RES-02: Nominal predicates, sense selection, and genuine ambiguity are the only modeled selection inputs; the model never draws a candidate boundary.

### Safety

- R6-SAF-01: The runner writes derived evidence only and creates zero canonical writes and zero ProposedChanges.

## 4. Negative Cases

- An Event whose Gold fragment boundary stays uncovered holds with a typed Boundary Gap and never reaches the model.
- An Event whose Selection Score is censored never produces an accepted selection.
- An unattached candidate never appears in a selection task.
- A held partition is never read to tune the threshold or the candidate pool.

## 5. Key Interactions

```text
Runner -> R3-A re-derivation      : add sub-span candidates, fail fast on gap
Runner -> R1 dependency-path router : mark attached / not-attached / model-review
Runner -> local model             : select only among attached candidates under one Event frame
Runner -> Selection Score         : threshold -> accepted selection or residual review
Runner -> composer                : assemble selected fragments
Runner -> residual review         : own held or ambiguous Events
```

## 6. Data Model

The Selection Score threshold is one natural-log-probability scalar that applies across Events.

The Boundary Gap record names one fragment ID, one start, and one end for each uncovered Gold fragment.

The residual-review set is one list of Event IDs routed off the primary selection path.

## 7. APIs / Interfaces

The runner exposes one `prepare` phase (deterministic), one `execute` phase (model selection with Token Probability Evidence), one `score` phase (Selection Scores and threshold routing), and one `report` phase (sealed report and review).

No public Application Layer port changes in this deliverable.

## 8. Behavior & Domain Rules

The R3-A constituent pool is the only candidate source; R6 enlarges coverage but never lets the model draw a boundary.

The R1 dependency-path router is the only attachment authority.

The Selection Score threshold is the primary knob; prompt changes are not a substitute for a missing or wrong threshold.

The held-out partition is evaluated once and never read to tune a decision.

The report records the error-type census and the exact-set score without gating on perfect counts.

## 9. Acceptance Criteria

- AC-R6-BND-01: Tests prove the corrected pool covers every development Gold fragment boundary.
- AC-R6-BND-02: Tests prove an uncovered boundary raises a typed Boundary Gap referencing its fragment ID.
- AC-R6-ATT-01: Tests prove the selection task contains zero unattached candidate.
- AC-R6-FRM-01: Tests prove one Event frame renders per task with the trigger and core constituents only.
- AC-R6-CAL-01: Tests prove a Selection Score at or below the threshold routes to residual review.
- AC-R6-CAL-02: Tests prove a censored Selection Score lists its Event in the residual-review set.
- AC-R6-RES-01: Tests prove the model is invoked only when deterministic composition cannot close an Event.
- AC-R6-SAF-01: The report records zero canonical writes and zero ProposedChanges.
- AC-R6-ALL: Focused formatting, lint, typecheck, and tests pass.

## 10. Reference Implementations

- Constituent inventory builder: `packages/application/src/kotekomi_application/parser_constituent_candidate_generation.py`.
- Dependency-path attachment router: `packages/application/src/kotekomi_application/deterministic_dependency_path_attachment_router.py`.
- Selection rendering and probability evidence: `packages/application/src/kotekomi_application/evaluation_remediation.py`.
- Token Probability Evidence pattern: `packages/application/src/kotekomi_application/competitive_attachment_edge_filter_calibration.py`.
- Decontextualization composition: `packages/application/src/kotekomi_application/decontextualization_composition.py`.
- Runner pattern: `scripts/run_evaluation_remediation.py`.
- LM Studio runtime: `packages/adapters/src/kotekomi_adapters/lm_studio_model_runtime.py`.

## 11. Constraints and Halt Conditions

- Stop when a Gold fragment boundary remains uncovered.
- Stop when a selection task carries an unattached candidate.
- Stop when a model call would draw a candidate boundary.
- Stop when the threshold routes a certain Event to accepted state.
- Stop when the held-out partition is read to tune a decision.
- Stop when any phase would write canonical intelligence.