# TDD: CEA-1.17 Residual Ownership Transfer Calibration

- Status: Implemented; mixed; production inactive
- Deliverable ID: `CEA-1.17`
- Program:
  [Competitive Event Attachment Program](2026-09-18-competitive-event-attachment-program.md)
- Predecessor:
  [CEA-1.16 Remainder Cardinality Ablation](2026-09-21-competitive-attachment-remainder-cardinality-ablation.md)

## 1. Context & Problem

CEA-1.13 through CEA-1.16 isolated several model-input effects on the bounded Residual Ownership question.

The strongest observed policy keeps the Authoritative Candidate fixed, explicitly lists Candidate Remainder ranges, and omits only a leading complementizer `that` from that explicit list.

The source character and Authoritative Candidate remain unchanged.

On the ten development cases, sealed evidence for this policy yields eight literal answers correct out of ten.

Its finite-label Attachment Scores rank the corrected Gold labels much better than the literal boundary: AUROC is `0.9375`, and average precision is approximately `0.9861` in both repetitions.

A threshold between the highest negative score and the lowest non-outlier positive score yields nine correct cases out of ten.

No experiment has tested that frozen rendering and threshold on the seven eligible validation Residual Edges.

The CEA-1.5 Maximum Pool is not a valid substitute.

It contains task shapes where the Target Event is outside the Candidate or a Foreign Event is inside the Candidate, while Residual Ownership is defined only for proper Target containment without a contained Foreign Event.

### Terms

**Ownership Remainder policy** means exact Candidate Remainder enumeration with only a leading case-insensitive `that` token and its following whitespace omitted from the explicit list.

**Literal decision** means the emitted strict `Y` or `N` answer.

**Attachment Score** means normalized finite-label log odds `log P(Y) - log(P(N) + P(U))`.

**Development threshold** means the deterministic midpoint selected from sealed development scores without reading validation results.

### Hypothesis

> The source-exact Ownership Remainder policy plus a development-frozen Attachment Score threshold will retain at least six of seven validation decisions, reject the validation Gold-negative case, and not regress against literal validation answers.

## 2. Goals

- Stop drawing production conclusions from one-case binary ablations.
- Reuse sealed development executions when their model-visible input is byte-equivalent to the frozen policy.
- Freeze one score threshold from development evidence before validation runs.
- Execute every eligible validation Residual Edge twice.
- Preserve exact model data-in, raw data-out, Y/N/U probability evidence, deterministic threshold mapping, and evaluation.
- Keep all canonical state unchanged.

## 3. Requirements

### Inventory and Gold

- CEA117-INV-01: KoteKomi must bind the ten development and seven validation Residual Ownership tasks from the complete CEA-1.7 preflight.
- CEA117-INV-02: Every task must properly contain its Target Event and contain no complete Foreign Event.
- CEA117-INV-03: The experiment Gold must bind each answer to an exact Residual Ownership task ID and phase.
- CEA117-INV-04: Development Gold must contain eight `Y` and two `N` cases.
- CEA117-INV-05: Validation Gold must contain six `Y` and one `N` case.
- CEA117-INV-06: `aro_a78d053d2b82125d272b8977` must be `Y`; its conjunction and auxiliary do not create a sibling fact outside the `participated` Event.
- CEA117-INV-07: Gold must remain outside every model input.

### Frozen rendering

- CEA117-RND-01: The task block must preserve the Authoritative Candidate, Target Event, SourceSegment, and Other Events.
- CEA117-RND-02: The standard Source copy context can normalize whitespace and must preserve its authoritative range mapping.
- CEA117-RND-03: KoteKomi must derive all displayed Remainder ranges from authoritative offsets.
- CEA117-RND-04: KoteKomi can omit only a leading case-insensitive `that` token and its following whitespace from the explicit Remainder list.
- CEA117-RND-05: Every omitted range must remain visible inside the unchanged Authoritative Candidate.
- CEA117-RND-06: Tasks without that exact prefix must render byte-equivalently to the CEA-1.13 Whole task.
- CEA117-RND-07: The two development tasks with that exact prefix must render byte-equivalently to the CEA-1.15 filtered task.
- CEA117-RND-08: The prompt must remain `competitive_attachment_residual_ownership_format_bare_v1` without edits.

### Development calibration

- CEA117-CAL-01: KoteKomi must validate and reuse eight CEA-1.13 Whole executions and two CEA-1.15 filtered executions per repetition.
- CEA117-CAL-02: Every reused record must retain its exact execution lineage and Y/N/U probability evidence.
- CEA117-CAL-03: KoteKomi must report literal metrics, AUROC, average precision, and threshold metrics separately.
- CEA117-CAL-04: Threshold candidates must be derived only from adjacent distinct development scores.
- CEA117-CAL-05: Selection must maximize accuracy, then specificity, then F1, then distance from the nearest observed score, then threshold value.
- CEA117-CAL-06: The selected threshold and complete development report must be frozen before validation execution.

### Validation execution

- CEA117-VAL-01: Qwen must answer one bounded Residual Ownership task per validation case and repetition.
- CEA117-VAL-02: Qwen must return exactly one `Y`, `N`, or `U` character.
- CEA117-VAL-03: KoteKomi must preserve position-zero Y/N/U probability evidence and compute the Attachment Score.
- CEA117-VAL-04: KoteKomi must apply the frozen threshold without changing the observed answer or model evidence.
- CEA117-VAL-05: The seven cases must execute twice under the pinned model identity, prompt, renderer, and generation settings.
- CEA117-VAL-06: Validation evidence must not alter the rendering, prompt, Gold, or threshold inside this TDD.

### Evaluation

- CEA117-EVL-01: `supported` requires strict valid output, stable semantic answers and threshold decisions, at least six of seven threshold-correct cases in both repetitions, rejection of the validation `N` case, and no threshold regression from literal accuracy.
- CEA117-EVL-02: `mixed` requires complete stable evidence but misses one or more quality gates without threshold regression.
- CEA117-EVL-03: `falsified` requires complete stable evidence with threshold accuracy below literal accuracy or retention of the validation `N` case.
- CEA117-EVL-04: `inconclusive` covers incomplete, invalid, foreign, or unstable evidence.
- CEA117-EVL-05: The report must distinguish observed answer, finite-label argmax, and threshold decision.
- CEA117-EVL-06: The literal token `Answer` probability must not be described as the answer probability.

### Evidence package

- CEA117-PKG-01: Preflight must bind every direct input by SHA-256.
- CEA117-PKG-02: Review output must show exact source, Candidate, Event, displayed and omitted Remainders, expected answer, exact model input, raw output, finite-label probabilities, score, and threshold result for every case.
- CEA117-PKG-03: The handoff must explain the task-family boundary and why the CEA-1.5 Maximum Pool was not used.
- CEA117-PKG-04: The package must preserve zero ProposedChanges and zero accepted Ledger writes.
- CEA117-PKG-05: The human must start and monitor validation and invoke Claude through standard input and standard output.

## 4. Proposed Architecture

```text
CEA-1.7 eligible Residual Edges
              |
              v
exact Ownership Remainder rendering
              |
       +------+------+
       |             |
       v             v
sealed development   fresh validation twice
probability evidence probability evidence
       |             |
       v             |
development threshold|
       +------+------+ 
              v
occurrence-level transfer report
```

The Application Layer owns exact rendering and typed experiment evidence.

The Pipeline owns Gold binding, score calibration, evaluation, and review rendering.

The existing ModelRuntime Port owns bounded Qwen execution.

The disposable runner validates sealed evidence and composes the experiment.

## 5. Acceptance Criteria

- CEA117-ACC-01: Tests prove the 10/7 inventory and 8/2 plus 6/1 Gold distributions.
- CEA117-ACC-02: Tests prove exact rendering equivalence and the bounded leading-`that` omission.
- CEA117-ACC-03: Tests prove deterministic threshold selection and all terminal outcomes.
- CEA117-ACC-04: Tests reject task, Gold, prompt, probability, model identity, and execution-lineage drift.
- CEA117-ACC-05: Model-free preparation reproduces development AUROC `0.9375` and approximately `0.9861111111` average precision in both repetitions.
- CEA117-ACC-06: Model-free preparation freezes a threshold that yields nine of ten development cases correct in both repetitions.
- CEA117-ACC-07: Focused formatting, lint, typecheck, and tests pass.
- CEA117-ACC-08: Human-run validation preserves fourteen complete model executions and a self-contained independent-review handoff.

## 6. Constraints and Halt Conditions

- Stop if a selected task is outside the Residual Ownership task family.
- Stop if any authoritative Candidate, Event, or SourceSegment character changes.
- Stop if any omitted range is not exactly the bounded leading complementizer.
- Stop if the reused development input is not equivalent to the frozen renderer.
- Stop if Gold enters a model input.
- Stop if the development threshold is recomputed after validation begins.
- Stop if a validation execution lacks complete Y/N/U probability evidence.
- Stop before production integration regardless of outcome.

## 7. Experimental Outcome

CEA-1.17 completed on September 21, 2026.

The report classified the result as `mixed`.

All fourteen validation executions returned strict finite answers.

Both repetitions produced identical semantic answers and probability evidence.

The frozen threshold improved development accuracy from eight of ten to nine of ten.

The frozen threshold changed zero validation decisions.

Literal and threshold validation accuracy both remained five of seven.

The validation Gold-negative case remained rejected.

The two validation false negatives centered on `hiring` and `agreement`.

The threshold therefore did not transfer a correction to validation.

The leading-`that` omission received no validation coverage.

Four Candidates began at their Target Event.

All four were Gold-positive and threshold-correct.

Thirteen Candidates had a leading Remainder.

Ten of those thirteen were threshold-correct.

Leading-Remainder AUROC fell from about `0.9167` in development to `0.5` in validation.

The pair `agreements with the Trump administration` scored about `8.90`.

The pair `an agreement with the AI Safety Institute` scored about `-9.84`.

This contrast shows that the score tracks Candidate boundary shape more than the shared ownership relation.

The `hiring` Gold answer remains defensible under the frozen prompt.

Its appositive descriptions make it the least clear Gold-positive case.

The standard Source copy context normalized internal whitespace in six development cases and four validation cases.

The task block retained every authoritative SourceSegment character.

The run created zero ProposedChanges and zero accepted Ledger writes.

Production integration remains `not_activated`.
