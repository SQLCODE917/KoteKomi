# TDD: CEA-1.11 Single-Token Answer Termination

- Status: Accepted for implementation; production inactive
- Deliverable ID: `CEA-1.11`
- Program:
  [Competitive Event Attachment Program](2026-09-18-competitive-event-attachment-program.md)
- Predecessor:
  [CEA-1.10 Finite Answer Format Isolation](2026-09-20-competitive-attachment-finite-answer-format.md)

## 1. Context & Problem

CEA-1.10 isolated two demonstration answer formats on the same ten tasks.

Every Bare Arm execution emitted `Y` or `N` as its first token.

Seven Bare Arm executions then continued into explanatory prose.

Those complete raw outputs correctly failed the exact `Y`, `N`, or `U` parser.

The model had already expressed a finite decision before the invalid continuation.

KoteKomi must prevent the continuation at generation time rather than repair it afterward.

### Hypothesis

> A one-token generation limit preserves each archived Bare Arm first-token decision and produces exact, repeatable `Y`, `N`, or `U` outputs.

### Primary flow

1. KoteKomi validates the complete CEA-1.10 evidence package and Claude review.
2. KoteKomi reuses the exact ten Bare Arm tasks, prompt, renderer, model, and semantic settings.
3. Qwen executes two identical repetitions with an effective one-token output limit.
4. KoteKomi parses the complete raw output without repair.
5. KoteKomi compares each result with the archived Bare Arm Finite Label Argmax.
6. KoteKomi reports strict validity, semantic preservation, and repetition stability.

CEA-1.11 creates experimental evidence only.

## 2. Goals

- Prevent explanatory continuation before it enters model output.
- Preserve Qwen's first-token semantic decision.
- Measure repeatability under the exact same contract.
- Keep invalid model output invalid.

## 3. Requirements

### Sealed evidence

- CEA111-EVD-01: The Pipeline must validate the complete CEA-1.10 package.
- CEA111-EVD-02: The Pipeline must require its completed Claude review.
- CEA111-EVD-03: The Pipeline must reuse the exact ten CEA-1.10 Bare Arm tasks.
- CEA111-EVD-04: The Pipeline must preserve each archived Bare Arm Finite Label Argmax.
- CEA111-EVD-05: Gold must remain outside every model input and outcome gate.
- CEA111-EVD-06: Every direct input must carry a file digest.

### One-factor execution contract

- CEA111-MOD-01: Both repetitions must use the CEA-1.10 Bare Prompt unchanged.
- CEA111-MOD-02: Both repetitions must use the Candidate Remainder renderer unchanged.
- CEA111-MOD-03: Both repetitions must use the CEA-1.10 model identity.
- CEA111-MOD-04: Both repetitions must use temperature `0` and seed `17`.
- CEA111-MOD-05: Both repetitions must request ten first-token alternatives.
- CEA111-MOD-06: The effective output limit must be exactly one token.
- CEA111-MOD-07: Qwen must execute each task once in each repetition.
- CEA111-MOD-08: Validation tasks must remain unexecuted.

### Evaluation

- CEA111-EVL-01: Evaluation must align observations by exact task and Edge identifiers.
- CEA111-EVL-02: Strict validity must parse the complete raw output as exact `Y`, `N`, or `U`.
- CEA111-EVL-03: Invalid output must never be repaired from a prefix or probability distribution.
- CEA111-EVL-04: Every observation must preserve its first-token Finite Label Evidence.
- CEA111-EVL-05: The evaluator must count one-token outputs.
- CEA111-EVL-06: The evaluator must compare each Observed Answer with its Finite Label Argmax.
- CEA111-EVL-07: The evaluator must compare each Finite Label Argmax with the archived Bare Arm argmax.
- CEA111-EVL-08: The evaluator must compare both repetitions by exact task.
- CEA111-EVL-09: `supported` requires twenty complete Probability Evidence records.
- CEA111-EVL-10: `supported` requires twenty one-token outputs.
- CEA111-EVL-11: `supported` requires twenty strict valid outputs.
- CEA111-EVL-12: `supported` requires twenty Observed Answer-to-Argmax matches.
- CEA111-EVL-13: `supported` requires twenty archived-Argmax matches.
- CEA111-EVL-14: `supported` requires ten repeat-agreeing task decisions.
- CEA111-EVL-15: `mixed` requires improved strict validity with one or more other failed gates.
- CEA111-EVL-16: `falsified` requires complete evidence without improved strict validity.
- CEA111-EVL-17: `inconclusive` requires missing execution or Probability Evidence.

### Evidence package

- CEA111-PKG-01: The package must preserve preflight, report, review, handoff, status, and run files.
- CEA111-PKG-02: The review must show exact source, Candidate, Target Event, Candidate Remainder, archived argmax, raw output, Observed Answer, and live argmax.
- CEA111-PKG-03: The package must preserve thirty comparisons: twenty archived-to-live and ten across repetitions.
- CEA111-PKG-04: The handoff must cite every direct file digest and the report fingerprint.
- CEA111-PKG-05: The package must report zero ProposedChanges and accepted Ledger writes.

## 4. Proposed Architecture

```text
sealed CEA-1.10 Bare observations
                |
                v
       one-token repetition 1
                |
       one-token repetition 2
                |
                v
 strict parser + Finite Label Evidence
                |
                v
 deterministic preservation evaluator
```

The existing ModelRuntime Port owns bounded Qwen execution.

The Application Layer owns typed experiment evidence.

The Pipeline owns alignment, evaluation, and review rendering.

The disposable runner composes the existing execution functions.

The human starts and monitors the live run.

## 5. Data Model

CEA-1.11 adds experimental Application DTOs for preflight, observations, paired cases, report, and status.

It adds no Domain Core record or Ledger schema.

## 6. Behavior & Domain Rules

- Exact source characters remain authoritative.
- Qwen supplies one bounded semantic token.
- KoteKomi supplies every identifier, mapping, comparison, and record.
- The parser validates the complete generated output.
- Probability evidence never repairs invalid output.
- Gold does not enter model input or determine this experiment's outcome.
- Production selection remains unchanged.
- No ProposedChange or accepted Ledger record is written.

## 7. Acceptance Criteria

- CEA111-ACC-01: Tests prove the effective generation contract contains one output token.
- CEA111-ACC-02: Tests prove all four terminal outcomes.
- CEA111-ACC-03: Tests reject missing or foreign task observations.
- CEA111-ACC-04: Tests distinguish raw validity, live argmax, archived argmax, and repetition agreement.
- CEA111-ACC-05: Focused formatting, lint, typecheck, and tests pass.
- CEA111-ACC-06: Model-free preparation validates the sealed CEA-1.10 package.
- CEA111-ACC-07: The human-run experiment preserves twenty complete model executions.
- CEA111-ACC-08: The package reports zero canonical writes.

## 8. Testing

Run focused tests for the new Application DTOs, Pipeline evaluator, runner, and the existing Attachment Edge Filter generation contract.

Run the full repository check command through the human-run cost-saving path after the bounded experiment is interpretable.

## 9. Observability

Each execution preserves exact model input, raw model output, ModelRun, execution receipt, stage trace, elapsed time, prompt digest, renderer identity, and generation contract.

The report preserves occurrence-level comparisons and aggregate counts.

## 10. Security & Privacy

All model execution remains local.

The second-opinion package may be sent to Anthropic only through the already authorized human-run Claude process.

## 11. Risks & Open Questions

- A one-token limit can reveal a runtime or tokenizer assumption that did not appear at eight tokens.
- One-token validity does not prove semantic correctness against Gold.
- Stable preservation of the Bare decision does not solve multi-part semantic aggregation.
- Per-Remainder-part attachment remains the next semantic experiment if CEA-1.11 is supported.

## 12. Stop Conditions

- Stop when any direct input digest changes.
- Stop when any model identity or task input differs across repetitions.
- Stop when Gold enters model input.
- Stop when an execution lacks its typed ModelRun or stage trace.
- Stop when an action would run validation tasks.
- Stop when an action would write canonical intelligence.
