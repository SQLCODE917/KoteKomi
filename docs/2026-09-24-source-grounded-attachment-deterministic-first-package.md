# Source-Grounded Attachment Deterministic-First Package

- Status: Proposed
- Program ID: `source-grounded-attachment-deterministic-first`
- Parent: [Competitive Event Attachment Program](2026-09-18-competitive-event-attachment-program.md)
- Predecessor evidence:
  [Source-Grounded Proposition Scope Experiment](2026-09-17-source-grounded-proposition-scope-experiment.md),
  [Event Attribution Production Wiring Package](2026-09-22-event-attribution-wiring-package.md),
  [Second-opinion review 1](../2nd-opinion.md),
  [Second-opinion review 3](../2nd-opinion-3.md),
  [Second-opinion review 4](../2nd-opinion-4.md),
  [Second-opinion review 5](../2nd-opinion-5.md)

## Context & Problem

KoteKomi composes one source-grounded proposition through four stages.

Stage one identifies the exact Event expression from one SourceSegment.

Stage two attaches the exact source occurrences that complete the Event proposition.

Stage three assembles the ordered fragment set into one decontextualized proposition.

Stage four assigns arguments and emits one `attributed_statement` Assertion.

Stage four ships deterministically through the Event Attribution Production Wiring Package.

Stage two and stage three fail.

The Competitive Event Attachment Program asked Qwen2.5-14B one semantic membership question per candidate.

The program graded that answer against Attachment Gold that encodes proposition containment.

The model question and the Gold question differ.

The model answered a language question.

The Gold measured span arithmetic.

No prompt rewrite closed that gap across eight conditions.

The `NONE` category failed every cycle because the Gold label is a property of segmentation, not language.

Deterministic dependency syntax resolves most of stage two and stage three without a model call.

Syntax path distance one reaches validation edge precision `0.930` to `0.967`.

Syntax path distance one reaches validation `NONE` accuracy `0.947`.

Qwen reaches validation `NONE` accuracy `0.421`.

The earlier `syntax_can_replace_qwen: falsified` result measured unbounded dependency-path closure, not syntax.

The route is inverted.

The model performs the work that syntax decides cheaply.

The deterministic route that solves the `NONE` class stays unused.

### Terms

**Proposition composition** means the four stages that turn one SourceSegment into one attributed Assertion.

**Attachment Candidate** means one exact source occurrence considered against one Event proposition.

**Attachment Gold** means the approved reference set of Attachment Candidates per Event.

**Dependency-path router** means the deterministic rule that routes one candidate through the parse tree.

**Decontextualization** means the restatement of one Event proposition as one standalone sentence.

**Model-review outcome** means the residual case where syntax routes one candidate to the local model.

### Conclusion

Keep the four stages.

Redesign the route through stages two and three.

Run the deterministic route first.

Reserve the local model for the residual cases.

Change the evaluation target and gates.

Gate each route on its error class instead of exact-set equality.

## Deliverables

| Deliverable | Title | Produces | Depends on |
|---|---|---|---|
| R1 | Deterministic dependency-path attachment router | one route decision per candidate: attached, not-attached, or model-review, model-free | none |
| R2 | Trigger-containment candidate split and Gold correction | one resized candidate per judgment, one corrected Attachment Gold | R1 |
| R3 | Parser-constituent candidate generation | constituents as candidates; the local model selects, and never draws boundaries | R2 |
| R3-A | Parser-constituent sub-span candidate generation | sub-span candidates so word-level and phrase-level Gold fragments enter the pool | R3 |
| R4 | Decontextualization composition | one `EventSemanticDraft` content triple and attribution from selected fragments | R3 |
| R5 | Evaluation remediation | one fresh held-out partition, logprob capture, one error-type census, error-class gates | R4 |
| R6 | Calibrated residual ownership | one syntax-attached selection per Event under one Event frame, gated on a Selection Score threshold, reserving the model for residual composition | R5 |
| R7 | Selection label and capture | one full token-sequence Selection Score per Event, free of the shared-`C` collision | R6 |
| R8 | Parser-constituent candidate filter | one Selectable candidate list per Event, filtered for content, dedup, and trigger exclusion before rendering | R7 |
| R9 | Selectable-pool floor | one Selectable pool preserved at or above the floor before rendering, with one relaxation record per relaxed Event | R8 |

R3-A supersedes the candidate granularity of R3 requirements `R3-CST-02` and `R3-CST-03`.

No `R3-B` deliverable exists.

R6 is accepted. R7, R8, and R9 extend R6 with full-token-sequence scoring, deterministic Candidate filters, and the Selectable-pool floor.

## Transfer result

R4 accepted with commit `ddbc7fe`.

R5 measured the held-out Anthropic/DoD partition once.

The sealed report fingerprint is `254f1b89cd21c29b6d0a7e3b51a3408038d71cca1f695460d2eddc83324a783e`.

The run root is `data/r5-evaluation-remediation-runs/run-001`.

The error-type census records the 53 held-out Events:

- ok: `0`
- boundary_miss: `37`
- selection_error: `53`
- composition_hold: `23`
- content_error: `1`
- attribution_error: `8`
- polarity_modality_error: `6`

The exact-set score is `0.0` and does not gate acceptance.

Two mechanisms dominate.

`boundary_miss` means the parser-constituent pool omits 37 Gold fragments at their exact boundaries before the model answers.

`selection_error` means the local model over-selects across every Event; the first-position Selection Scores sit near log `0`, so the over-selection is certain rather than uncertain.

R6 closes the boundary gap, restricts the model to syntax-attached candidates under one Event frame, and gates selection on a Selection Score threshold.

## Fresh partition prerequisite

The Attachment Gold draws from authoritative Documents that have already served a CEA decision.

A fresh partition needs one authoritative Source Document that has never informed a CEA decision.

That Document needs human-reviewed Attachment proposition Gold.

The Gold record carries `annotation_status` equal to `human_reviewed_held_out_gold`.

The Gold record carries `development_overlap_count` equal to `0`.

The human supplies the Document and reviews the Gold during R5.

The Competitive Event Attachment Program already names an Independent held-out evaluation as a late deliverable.

This package pulls that partition forward as a prerequisite.

## Order

Hold out one fresh partition first.

R1 ships only after that partition is reserved.

R1 is model-free and deterministically testable.

R1 ships against the current Attachment Gold.

R1 gates each route on its error class, never on the 179 validation candidates.

R2 corrects the segmentation artifact that current Attachment Gold encodes.

R3 replaces boundary-drawing prompts with constituent selection.

R4 feeds the selected fragments into the existing deterministic wiring.

R5 measures transfer on the partition that never informed a decision.

Each deliverable ships and reverts independently.

## Completion

The package completes when every deliverable passes its acceptance criteria.

The package completes when the deterministic route covers every candidate that syntax decides.

The package completes when the local model answers only the residual cases.

The package completes when each route passes its error-class gate.

The package completes when one fresh partition measures transfer without selection.