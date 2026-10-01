# TDD: Selection Label and Capture

- Status: Proposed
- Deliverable ID: `R6`
- Program: [Source-Grounded Attachment Deterministic-First Package](2026-09-24-source-grounded-attachment-deterministic-first-package.md)
- Parent: [Calibrated Residual Ownership](2026-09-29-calibrated-residual-ownership.md)
- Depends on: [Evaluation Remediation](2026-09-28-evaluation-remediation.md)

## 1. Context & Problem

R6 routes an Event whose selection is uncertain to residual review.
R6 measures that uncertainty with one Selection Score.
The current R6 scorer reads only the first emitted token.
So the scorer reports one first-position log probability per Candidate label.

The local model spells every Candidate label as one shared `C` token followed by one token per digit.
Every Candidate label therefore shares the same first token `C`.
The first-position score collides.
Every emitted label reports the same `C` probability.
The collision censors the per-label scores that R6 needs.

The model also emits two shapes that break first-position scoring.
First, the model may merge a comma with a label when it lists labels compactly.
The answer `C3,C6` emits the token `,C`, not a bare `C`.
A scorer that matches only a bare `C` or ` C` fails to reconstruct `C6`.
Second, the model may return prose instead of a finite answer.
A prose answer is a Rejected selection, but a scorer that scans prose may still find a label text and accept it.

### Terms

**Candidate label** means one ordered `C1..C<n>` token that names one syntax-attached candidate in one selection task.

**Token Probability Evidence** means the runtime record per emitted position.
It holds the chosen token text, its natural-log probability, and its top alternatives.

**Label run** means the contiguous emitted-token positions whose text spells one Candidate label exactly.

**Label log probability** means the sum of the natural-log probabilities of one Label run's tokens.

**Censored label** means a Candidate label the scorer cannot reconstruct.
A Censored label records no Label log probability.

**Selection Score** means the single per-Event natural-log probability the router compares to the threshold.
It equals the highest Label log probability of the emitted labels.

**Rejected selection** means a finite model answer that is neither `NONE` nor one comma-separated subset of the Candidate labels.

The terms Boundary gap, Event frame, Syntax-attached candidate, Residual review, and Calibration knob keep the
meanings that the Calibrated Residual Ownership TDD defines.

### Primary flow

1. The runner renders one selection task per Event over its syntax-attached candidates.
2. The model returns `NONE` or one comma-separated subset of the Candidate labels.
3. The runner captures Token Probability Evidence for every emitted position.
4. The scorer reconstructs each emitted Candidate label's Label run.
5. The scorer sums each Label run's token probabilities into one Label log probability.
6. The router sends a Rejected selection, a Censored label, and any Selection Score at or below the threshold to residual review.

## 2. Goals

- Operators observe one full token-sequence Selection Score per Event, free of the shared-`C` collision.
- Operators observe a Rejected selection routed to residual review, never accepted.
- Operators observe the scorer reconstruct every label the parser accepted, and no label the parser rejected.

## 3. Requirements

### Answer parsing

- PAR-01: The parser accepts the literal token `NONE` as a NONE selection.
- PAR-02: The parser accepts one comma-separated subset of the Candidate labels as a selected subset.
- PAR-03: The parser marks every other finite answer as a Rejected selection.

### Token Probability Evidence capture

- CAP-01: The runner records Token Probability Evidence for every emitted position, not only the first.
- CAP-02: The runner preserves each position's chosen token text, its natural-log probability, and its top alternatives unmodified.

### Scoring

- SCO-01: The scorer reconstructs each emitted Candidate label's Label run.
- SCO-02: A selected label's Label log probability equals the sum of the natural-log probabilities of its Label run's tokens.
- SCO-03: The scorer strips leading whitespace and one leading comma from a Label run's first token before it matches.
- SCO-04: The scorer matches longer Candidate labels first, so a shorter label never matches the prefix of a longer label in one run.
- SCO-05: A Candidate label with no reconstructable Label run is a Censored label.

### Routing

- RTE-01: A Rejected selection routes to residual review.
- RTE-02: The scorer never reconstructs a label from a Rejected answer.
- RTE-03: A Censored label lists its Event in the residual-review set by Event ID.
- RTE-04: A Selection Score at or below the threshold routes its Event to residual review.

### Fidelity

- FID-01: For every selected subset answer, the scorer's non-censored labels equal the parser's accepted subset exactly.

## 4. Proposed Architecture

```text
+---------+   prepare    +----------------------+
| Runner  | -----------> | tasks.json           |
+---------+              +----------------------+
     |         execute      +-------------------------------+
     +--------------------> | answers.jsonl + receipts.json  |
     |                      +-------------------------------+
     |          score       +--------------------------+
     +--------------------> | score.json                |
     |                      | (labels + routing)        |
     |         report      +---------------------------+
     +-------------------> | report.json + review.md    |
                            +---------------------------+
```

The Parser owns the PAR requirements.
The Capture component inside the Runner owns the CAP requirements.
The Scorer owns the SCO and FID requirements.
The Router owns the RTE requirements.

## 5. Key Interactions

```text
Runner    Model      Parser     Scorer     Router
  |          |          |          |          |
  |--execute(task)----->|          |          |
  |<--answer+evidence---|          |          |
  |--parse(answer)----->|          |          |
  |<--NONE|subset|Rejected--------|          |
  |--reconstruct(evidence, labels)--------->|
  |<--label log probability | Censored-----|
  |--route(scores, threshold)---------------------->|
  |<--residual review | accepted selection----------|
```

## 6. Data Model

`SelectionProbabilityReceipt` exists and carries the first position's alternatives only.
It will carry the full per-position Token Probability Evidence.

`SelectionScore` exists and carries `label`, `log_probability`, and `censored`.
It will keep those fields.
`log_probability` becomes the Label log probability.
`censored` keeps its meaning: no reconstructable Label run, so no probability.

`ConstituentSelectionAnswer` exists and carries `event_id`, `status`, and `selected_label_indexes`.
It will keep those fields.
The Rejected status feeds residual review.

## 7. APIs / Interfaces

`SelectionScore.label` keeps the `C<ordinal>` or `NONE` shape.

One reconstruction entry point maps one `SelectionProbabilityReceipt` and one ordered Candidate label set
to one log probability or one censoring per Candidate label.

The router keeps one threshold comparison per Event.
It compares the Selection Score, which stays the highest emitted Label log probability.

## 8. Behavior & Domain Rules

A Rejected selection routes to residual review.
No label reconstruction runs on a Rejected answer.

A Censored label yields no probability.
A censored Event routes to residual review by Event ID.

A Selection Score at or below the threshold routes to residual review.
A Selection Score above the threshold may only produce an accepted selection when syntax also attaches.

The parser and the scorer agree for every selected subset answer.
Their accepted and reconstructed label sets match exactly.

## 9. Acceptance Criteria

- AC-PAR-01: Tests prove the parser returns NONE for the literal `NONE` answer.
- AC-PAR-02: Tests prove the parser returns the correct ordered subset for a comma-separated subset answer.
- AC-PAR-03: Tests prove the parser returns Rejected for prose, an empty answer, an unknown label, and trailing chatter.
- AC-CAP-01: Tests prove the receipt carries Token Probability Evidence for every emitted position.
- AC-CAP-02: Tests prove the receipt preserves each position's chosen token, its log probability, and its top alternatives unmodified.
- AC-SCO-01: Tests prove the scorer reconstructs a label whose Label run is a bare `C` plus digit tokens.
- AC-SCO-02: Tests prove a label's Label log probability equals the sum of its Label run's token probabilities.
- AC-SCO-03: Tests prove the scorer reconstructs a label whose first token carries leading whitespace or one leading comma.
- AC-SCO-04: Tests prove a shorter label never matches the prefix of a longer label in one run.
- AC-SCO-05: Tests prove the scorer censors a label with no reconstructable Label run and records no probability.
- AC-RTE-01: Tests prove a Rejected selection routes to residual review.
- AC-RTE-02: Tests prove no label is reconstructed from a prose answer.
- AC-RTE-03: Tests prove a censored label lists its Event in the residual-review set by Event ID.
- AC-RTE-04: Tests prove a Selection Score at or below the threshold routes to residual review.
- AC-FID-01: Tests prove the scorer's non-censored labels equal the parser's accepted subset for every selected subset answer.
- AC-ALL: Focused formatting, lint, typecheck, and tests pass.

## 10. Reference Implementations

- Answer parser: `packages/application/src/kotekomi_application/parser_constituent_candidate_generation.py`.
- Score records and scoring: `packages/application/src/kotekomi_application/evaluation_remediation.py`.
- Token Probability Evidence pattern: `packages/application/src/kotekomi_application/competitive_attachment_edge_filter_calibration.py`.
- Runner pattern: `scripts/run_calibrated_residual_ownership.py`.

## 11. Constraints and Halt Conditions

Keep the `C1..C<n>` Candidate labels.
Do not relabel candidates with single-token labels.
The grammar-safe single-token alphabet of digits plus uppercase and lowercase letters holds 62 symbols.
One Event holds 69 syntax-attached candidates, which that alphabet cannot label.

Keep the representative Selection Score aggregation unchanged.
This TDD changes how each label's log probability is computed, not how the per-Event Selection Score aggregates the labels.

Do not reconstruct any label from a Rejected answer.
A Rejected selection is prose, not a finite selection, and routes to residual review.