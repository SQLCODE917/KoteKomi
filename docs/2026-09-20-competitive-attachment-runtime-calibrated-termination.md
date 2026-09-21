# TDD: CEA-1.12 Runtime-Calibrated Budget-Bounded Output

- Status: Complete; budget-bound mechanism supported; production inactive
- Deliverable ID: `CEA-1.12`
- Program:
  [Competitive Event Attachment Program](2026-09-18-competitive-event-attachment-program.md)
- Predecessor:
  [CEA-1.11 Single-Token Answer Termination](2026-09-20-competitive-attachment-single-token-termination.md)

## 1. Context & Problem

CEA-1.11 requested one output token for ten exact semantic tasks in two repetitions.

LM Studio returned twenty completed responses without an output item.

KoteKomi retained the twenty failed ModelRuns and rejected the missing output text.

Every ready ModelInputAdmission retained the CEA-1.10 model identity.

A direct runtime probe then varied only the requested output limit.

The probe emitted zero tokens at limit one.

The probe emitted one token at limit two.

The probe emitted two tokens at limit three.

The probe emitted three tokens at limit four.

The limit-two first-token distribution matched the archived limit-eight distribution exactly.

This evidence identifies limit two as the smallest observed functioning request.

It does not establish a documented LM Studio rule.

It does not establish a production-safe finite-answer mechanism.

### Terms

**Requested Output Limit** means the `max_output_tokens` value sent to LM Studio.

**Observed Output Count** means the runtime-reported output token count.

**Probability Position Count** means the number of preserved output probability positions.

**Exact Finite Answer** means raw output bytes equal to `Y`, `N`, or `U`.

**Position-Zero Distribution** means the emitted token and ordered alternatives at token position zero.

**Mechanism Proof** means evidence about budget-bounded runtime output behavior.

**Production Suitability** means evidence that a mechanism remains controlled across runtime changes and the full task pool.

### Hypothesis

> A two-token request yields one exact finite answer for every sealed task while preserving its archived position-zero distribution.

### Primary flow

1. KoteKomi validates the complete CEA-1.10 and CEA-1.11 evidence packages.
2. KoteKomi validates the direct output-limit probe and Claude review.
3. KoteKomi reuses the exact ten CEA-1.10 Bare tasks and model inputs.
4. Qwen executes two identical repetitions with a two-token request limit.
5. KoteKomi compares two response fields and exact raw bytes.
6. KoteKomi compares each Position-Zero Distribution with both repetitions and CEA-1.10.
7. KoteKomi reports Mechanism Proof separately from Production Suitability.

CEA-1.12 creates experimental evidence only.

## 2. Goals

- Establish whether the two-token request works across ten sealed tasks.
- Establish whether the result repeats across two executions.
- Detect any change in first-token model preference.
- Preserve every failed or malformed execution without repair.
- State the limits of the evidence explicitly.

## 3. Requirements

### Sealed evidence

- CEA112-EVD-01: The Pipeline must validate the complete CEA-1.10 package.
- CEA112-EVD-02: The Pipeline must validate the complete CEA-1.11 package.
- CEA112-EVD-03: The Pipeline must require the completed CEA-1.11 Claude review.
- CEA112-EVD-04: The Pipeline must validate the limit-one through limit-four probe files.
- CEA112-EVD-05: The Pipeline must reuse the exact ten CEA-1.10 Bare tasks.
- CEA112-EVD-06: The Pipeline must preserve each archived Position-Zero Distribution.
- CEA112-EVD-07: Gold must remain outside every model input and outcome gate.
- CEA112-EVD-08: Every direct input must carry a file digest.

### One-factor execution contract

- CEA112-MOD-01: Both repetitions must use the CEA-1.10 Bare Prompt unchanged.
- CEA112-MOD-02: Both repetitions must use the Candidate Remainder renderer unchanged.
- CEA112-MOD-03: Both repetitions must use the CEA-1.10 model identity.
- CEA112-MOD-04: Both repetitions must use temperature `0` and seed `17`.
- CEA112-MOD-05: Both repetitions must request ten first-token alternatives.
- CEA112-MOD-06: The Requested Output Limit must equal two tokens.
- CEA112-MOD-07: Qwen must execute each task once in each repetition.
- CEA112-MOD-08: Validation tasks must remain unexecuted.

### Mechanism evaluation

- CEA112-MEC-01: Evaluation must align observations by exact task and Edge identifiers.
- CEA112-MEC-02: Every successful execution must preserve one probability position at position zero.
- CEA112-MEC-03: Every successful execution must report one observed output token.
- CEA112-MEC-04: Runtime usage and probability positions must report one token.
- CEA112-MEC-05: The evaluator must inspect exact raw output before whitespace normalization.
- CEA112-MEC-06: An Exact Finite Answer must contain no surrounding bytes.
- CEA112-MEC-07: Probability evidence must not repair an invalid raw output.
- CEA112-MEC-08: Each live Position-Zero Distribution must match its archived distribution exactly.
- CEA112-MEC-09: Both live repetitions must have identical Position-Zero Distributions.
- CEA112-MEC-10: Each exact answer must equal its live finite-label argmax.
- CEA112-MEC-11: Every ready admission must use the archived model identity.
- CEA112-MEC-12: The existing LM Studio Adapter must reject a foreign response model.

### Outcome

- CEA112-OUT-01: `supported` requires all twenty executions to pass every Mechanism evaluation gate.
- CEA112-OUT-02: `mixed` requires complete evidence with one through nineteen exact finite answers.
- CEA112-OUT-03: `falsified` requires complete evidence with zero exact finite answers.
- CEA112-OUT-04: `inconclusive` requires a failed execution or missing Probability Evidence.
- CEA112-OUT-05: Every outcome must keep Production Suitability unmet.
- CEA112-OUT-06: The report must identify undeclared runtime sampling defaults as an open confound.
- CEA112-OUT-07: The report must identify runtime build identity as an open confound.
- CEA112-OUT-08: The report must identify truncation observability as an open confound.
- CEA112-OUT-09: The report must identify full-pool semantic quality as untested.

### Evidence package

- CEA112-PKG-01: The package must preserve preflight, report, review, handoff, status, and run files.
- CEA112-PKG-02: The review must show exact SourceSegment, Candidate, Target Event, and Candidate Remainder.
- CEA112-PKG-03: The review must show raw output and both output-count witnesses.
- CEA112-PKG-04: The review must show archived, repetition-one, and repetition-two distribution digests.
- CEA112-PKG-05: The handoff must cite every direct file digest and the report fingerprint.
- CEA112-PKG-06: The package must report zero ProposedChanges and accepted Ledger writes.

## 4. Proposed Architecture

```text
sealed CEA-1.10 distributions
             +
sealed CEA-1.11 runtime evidence
             |
             v
  two-token repetition 1
             |
  two-token repetition 2
             |
             v
 exact bytes + count witnesses
             |
             v
 distribution preservation report
```

The existing ModelRuntime Port owns bounded Qwen execution.

The Application Layer owns typed experiment evidence and outcome rules.

The Pipeline owns evidence validation, alignment, and review rendering.

The disposable runner composes the existing execution functions.

The human starts and monitors the live run.

## 5. Key Interactions

```text
Human       Runner       Pipeline       ModelRuntime       Qwen
  |            |             |               |              |
  |-- start -->|             |               |              |
  |            |-- prepare ->|               |              |
  |            |             |-- task ------>|-- request -->|
  |            |             |<-- evidence --|<-- output ---|
  |            |             |-- evaluate -->|              |
  |            |<-- package -|               |              |
  |<-- paths --|             |               |              |
```

## 6. Data Model

CEA-1.12 adds experimental Application DTOs for preflight, observations, cases, report, and status.

Each observation preserves exact raw output and one Position-Zero Distribution digest.

Each report preserves Mechanism Proof counts and unmet Production Suitability conditions.

CEA-1.12 adds no Domain Core record or Ledger schema.

## 7. APIs / Interfaces

The runner accepts one CEA-1.11 package root and one absent experiment root.

Preparation writes a digest-bound preflight before model execution.

Execution writes one typed record for each task and repetition.

Finalization writes one terminal report and human-readable review.

## 8. Behavior & Domain Rules

- Exact source characters remain authoritative.
- Qwen supplies one bounded semantic answer.
- KoteKomi supplies every identifier, comparison, digest, and record.
- The evaluator validates raw output before the existing stripping parser.
- Runtime usage and probability positions remain separate response fields.
- Runtime input usage remains distinct from ModelInputAdmission measurement.
- The Adapter continues to reject a response from a foreign model.
- Gold does not enter model input or determine the outcome.
- Production selection remains unchanged.
- No ProposedChange or accepted Ledger record is written.

## 9. Acceptance Criteria

- CEA112-ACC-01: Tests prove the effective generation contract requests two output tokens.
- CEA112-ACC-02: Tests prove exact raw bytes differ from stripped parser validity.
- CEA112-ACC-03: Tests prove both output-count response fields must report one token.
- CEA112-ACC-04: Tests prove exact distribution comparison across three observations.
- CEA112-ACC-05: Tests prove all four terminal outcomes.
- CEA112-ACC-06: Tests reject missing or foreign task observations.
- CEA112-ACC-07: Focused formatting, lint, typecheck, and tests pass.
- CEA112-ACC-08: Model-free preparation validates both predecessor packages and probe evidence.
- CEA112-ACC-09: The human-run experiment preserves twenty complete model executions.
- CEA112-ACC-10: The package reports zero canonical writes.

## 10. Reference Implementations

- Execution record pattern: `scripts/run_competitive_attachment_single_token_termination.py`.
- Model execution: `scripts/run_competitive_attachment_edge_filter_experiment.py`.
- Probability evidence: `packages/pipelines/src/kotekomi_pipelines/competitive_attachment_finite_answer_format.py`.
- Runtime validation: `packages/adapters/src/kotekomi_adapters/lm_studio_model_runtime.py`.

## 11. Constraints and Halt Conditions

- Stop when any direct input digest changes.
- Stop when any model identity or exact task input differs from CEA-1.10.
- Stop when Gold enters model input.
- Stop when an execution lacks a typed ModelRun or stage trace.
- Stop when the two output-count witnesses disagree.
- Stop when an action would run validation tasks.
- Stop when an action would write canonical intelligence.
- A supported outcome establishes Mechanism Proof only.
- A supported outcome does not activate production.

## 12. Experimental Outcome

CEA-1.12 completed on September 20, 2026.

All twenty executions returned one exact `Y` or `N` byte sequence.

All twenty executions reported one output token and one probability position.

All twenty Position-Zero Distributions matched the CEA-1.10 archive.

Both repetitions agreed for all ten tasks.

The experiment therefore supports the budget-bound mechanism hypothesis.

The experiment does not establish model-chosen termination.

The limit-three probe emitted `Y` followed by a newline token.

The limit-four probe then emitted the beginning of an explanation.

Under the pinned runtime, the two-token request therefore constrained observed output to the answer token.

The runtime usage count and probability positions derive from one LM Studio response.

They corroborate response shape but do not provide independent transport measurements.

LM Studio also echoed an undeclared `frequency_penalty` value of `1.1`.

That setting remains a semantic-quality confound until KoteKomi controls it explicitly.

The independent review proposed another termination probe.

The program does not adopt that proposal because the existing probe already settles termination.

CEA-1.13 returns to semantic Attachment quality.
