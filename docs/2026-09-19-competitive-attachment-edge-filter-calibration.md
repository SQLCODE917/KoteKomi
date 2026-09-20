# TDD: CEA-1.5 Calibrated Competitive Edge Filter

- Status: Verified not separable; production inactive
- Deliverable ID: `CEA-1.5`
- Program: [Competitive Event Attachment Program](2026-09-18-competitive-event-attachment-program.md)
- Predecessor: [CEA-1.4 High-Recall Competitive Edge Filter](2026-09-19-competitive-attachment-edge-filter.md)
- Development Gold: [Source-Grounded Proposition Gold](hsq-source-grounded-proposition-gold-v1.json)

## 1. Context & Problem

CEA-1.4 tested two Prompt Arms on sixteen difficult development Pool Edges.
Each Prompt Arm matched thirteen of sixteen Gold decisions in two repetitions.
The Prompt Arms exchanged false-positive and false-negative decisions.
The mandatory perfection gate stopped the full development replay.
CEA-1.4 therefore did not test its aggregate Edge Filter hypothesis.

The finite `Y`, `N`, or `U` answer retained only Qwen2.5's winning token.
It discarded the relative probability of the three allowed answers.
KoteKomi therefore cannot distinguish one firm answer from one marginal answer.
KoteKomi also cannot test whether one score threshold separates useful and harmful Pool Edges.

### Terms

**Prompt Arm** means the exact CEA-1.4 V8 or V9 prompt bytes.

**Token Probability Evidence** means the runtime-reported token, natural-log probability, bytes, and alternatives.

**Attachment Score** means `log P(Y) - log(P(N) + P(U))` for the first meaningful answer token.

The three grouped values are normalized as a conditional distribution over recognized `Y`, `N`, and `U` token variants. The receipt retains the unmodified runtime alternatives. This prevents finite-precision runtime rounding from producing an impossible positive grouped log probability without changing the Attachment Score.

**Calibration Threshold** means the frozen minimum Attachment Score that retains a Pool Edge.

**Protected Positive** means a Gold-positive diagnostic edge that tests entity or attribution retention.

**Hard Negative** means a Gold-negative diagnostic edge from the declared Gold-`NONE` challenge.

**Expected-Exact Profile** means the Maximum Pool edge cardinalities for every Candidate.

**Expected-Exact Accuracy** means an explicit independent-edge feasibility estimate.

**Calibrated Edge Decision** means threshold retention plus the unchanged literal model answer.

### Hypothesis

> One sealed Prompt Arm ranks correct Pool Edges above incorrect Pool Edges well enough for one frozen threshold to improve complete Attachment Sets without losing protected intelligence.

### Primary flow

1. KoteKomi validates the sealed CEA-1.4 pools, tasks, catalog, Prompt Arms, and runtime.
2. LM Studio returns typed Token Probability Evidence for the sixteen diagnostic tasks twice per Prompt Arm.
3. KoteKomi computes Attachment Scores and applies the safety and break-even gates.
4. KoteKomi replays the selected Prompt Arm over all development Pool Edges.
5. Development Gold freezes one Calibration Threshold and one Pool Arm.
6. KoteKomi applies the frozen contract to validation once and writes the evidence package.

CEA-1.5 produces experimental evidence only.

## 2. Goals

- An operator can inspect the exact probability evidence behind each calibrated decision.
- An operator can determine whether CEA-1.4 failed because of ranking or threshold selection.
- An operator can stop before the expensive replay when the score cannot clear break-even safely.
- An operator can compare calibrated Pool Arms with the CEA-1.3 primary policy.
- A future reviewer receives exact task input, raw output, probability evidence, metrics, and lineage.

## 3. Requirements

### Sealed evidence

- CEA15-EVD-01: The Pipeline must validate the V8 and V9 CEA-1.4 run roots.
- CEA15-EVD-02: The Pipeline must require identical pools, tasks, catalog, Gold, and runtime contracts across Prompt Arms.
- CEA15-EVD-03: The Pipeline must recover each exact Prompt Arm from sealed model input and verify its digest.
- CEA15-EVD-04: The Pipeline must require 490 development and 257 validation Maximum Pool Edges.
- CEA15-EVD-05: Gold must not enter a model task.
- CEA15-EVD-06: The Pipeline must reject changed prompts, tasks, pools, Gold, runtime, or generation settings.

### Runtime evidence

- CEA15-RUN-01: An LM Studio model task can request between one and ten output token alternatives; the Adapter must reject a larger request before generation transport.
- CEA15-RUN-02: The LM Studio Adapter must request `message.output_text.logprobs` only for an explicit request.
- CEA15-RUN-03: The Adapter must map the runtime response into Application Layer Token Probability Evidence.
- CEA15-RUN-04: Token Probability Evidence must preserve token text, bytes, log probability, position, and ordered alternatives.
- CEA15-RUN-05: The Adapter must reject missing, malformed, duplicate, or inconsistent requested probability evidence.
- CEA15-RUN-06: A task without an explicit probability request must retain an empty probability inventory.
- CEA15-RUN-07: `ModelRun.execution_receipt` must preserve the typed probability inventory.
- CEA15-RUN-08: The generation settings digest must bind the probability request.

### Score mapping

- CEA15-SCR-01: KoteKomi must inspect the first meaningful output token.
- CEA15-SCR-02: The emitted token must parse through the existing finite `Y`, `N`, or `U` contract.
- CEA15-SCR-03: KoteKomi must group token variants by their parsed finite answer.
- CEA15-SCR-04: KoteKomi must combine same-answer variants with log-sum-exp.
- CEA15-SCR-05: Every scored decision must contain `Y`, `N`, and `U` alternatives.
- CEA15-SCR-06: KoteKomi must compute the Attachment Score from the three grouped probabilities.
- CEA15-SCR-07: A Calibrated Edge Decision must preserve the literal answer separately from threshold retention.

### Diagnostic gate

- CEA15-DIA-01: Each Prompt Arm must execute the sixteen diagnostic tasks twice.
- CEA15-DIA-02: Each observation must bind exact model input, raw output, receipt, task, Prompt Arm, and repetition.
- CEA15-DIA-03: KoteKomi must report AUROC and average precision for each repetition.
- CEA15-DIA-04: KoteKomi must derive threshold candidates from the observed score ordering.
- CEA15-DIA-05: The Expected-Exact Profile must preserve true, false, and missing Gold edge counts per Candidate.
- CEA15-DIA-06: The feasibility estimate must state its homogeneous independent-edge assumption.
- CEA15-DIA-07: An eligible threshold must retain every Protected Positive in both repetitions.
- CEA15-DIA-08: An eligible threshold must reject every Hard Negative in both repetitions.
- CEA15-DIA-09: An eligible threshold must exceed CEA-1.3 exact-set accuracy for both phase profiles and repetitions.
- CEA15-DIA-10: Cross-class score ordering must remain stable across repetitions.
- CEA15-DIA-11: The Pipeline must stop before development when neither Prompt Arm passes every diagnostic gate.
- CEA15-DIA-12: A diagnostic stop must preserve exact evidence and keep production inactive.

### Development freeze

- CEA15-DEV-01: The selected Prompt Arm must execute every development Maximum Pool task once.
- CEA15-DEV-02: The Pipeline can reuse an exact diagnostic execution with matching task, prompt, runtime, and generation digests.
- CEA15-DEV-03: Development Gold must select one Calibration Threshold and one Pool Arm.
- CEA15-DEV-04: Selection must maximize exact Attachment Set accuracy, then edge F1, then lower Sibling-Event Leakage.
- CEA15-DEV-05: Selection must preserve CEA-1.3 entity, qualification, shared-fragment, character, and Gold-`NONE` recall.
- CEA15-DEV-06: The freeze must bind the Prompt Arm, prompt digest, runtime digest, generation digest, threshold, Pool Arm, and report digest.

### Validation and outcome

- CEA15-VAL-01: Validation must execute the frozen contract once.
- CEA15-VAL-02: Validation must not change the Prompt Arm, threshold, Pool Arm, parser, score, or candidate policy.
- CEA15-VAL-03: The report must label validation as diagnostic rather than independent transfer evidence.
- CEA15-OUT-01: The terminal aggregate result must be `supported`, `mixed`, or `falsified`.
- CEA15-OUT-02: `supported` requires strict exact-set and edge-precision gains over CEA-1.3 in both phases.
- CEA15-OUT-03: `supported` requires lower Sibling-Event Leakage in both phases.
- CEA15-OUT-04: `supported` requires no CEA-1.3 recall regression in either phase.
- CEA15-OUT-05: `supported` requires complete valid model evidence and zero silent drops.
- CEA15-OUT-06: `mixed` applies when the calibrated path meets only part of the aggregate contract.
- CEA15-OUT-07: `falsified` applies when the calibrated path provides no safe aggregate gain.
- CEA15-OUT-08: Every outcome must keep production integration inactive.

### Evidence package

- CEA15-PKG-01: The runner must expose `prepare`, `diagnose`, `run-development`, `run-validation`, and `finalize` actions.
- CEA15-PKG-02: Every long action must be resumable from validated execution records; an explicit `model_failed` record must move to a digest-bound failed-attempt inventory before an operator-requested retry, while invalid deterministic evidence must still fail fast.
- CEA15-PKG-03: The runner must write exact diagnostic and phase reviews.
- CEA15-PKG-04: The runner must write the development freeze before validation.
- CEA15-PKG-05: The runner must write a report, summary, review, handoff, manifest, and terminal status.
- CEA15-PKG-06: The manifest must bind every input, execution directory, Archive output, and result fingerprint.
- CEA15-PKG-07: CEA-1.5 must create zero ProposedChanges and zero accepted Ledger writes.

## 4. Proposed Architecture

```text
sealed Prompt Arms + Maximum Pool
                |
                v
   LM Studio probability evidence
                |
                v
 deterministic Attachment Score
                |
                v
 safety + break-even diagnostic
                |
                v
 development threshold and Pool Arm
                |
                v
 frozen validation + evidence package
```

The Application Layer owns typed probability and calibration DTOs.
The LM Studio Adapter owns the external response mapping.
The Pipeline owns score mapping, threshold selection, Pool Arm evaluation, and outcome rules.
The disposable runner owns experiment orchestration and evidence packaging.
The Domain Core validates the persisted `ModelRun` receipt shape.

## 5. Key Interactions

```text
Operator       Runner        ModelRuntime       Pipeline
   |              |               |                |
   | prepare      | validate sealed evidence       |
   |------------->|-------------------------------->|
   | diagnose     | execute 2 prompts x 2 repeats  |
   |------------->|-------------->|                |
   |              | typed probabilities            |
   |              |<---------------|                |
   |              | score and gate |-------------->|
   | run dev      | only after safe break-even      |
   |------------->|-------------->|--------------->|
   | validate     | frozen prompt and threshold     |
   |------------->|-------------->|--------------->|
```

## 6. Data Model

CEA-1.5 adds Application Layer DTOs for token alternatives, score evidence, threshold evaluations, phase results, the freeze, and the evidence package.

`ModelRun.execution_receipt` adds an ordered `output_token_probabilities` field.

The field is empty when the model task did not request probability evidence.

CEA-1.5 adds no accepted Domain Core record.

## 7. APIs / Interfaces

The existing model task keeps its exact source and finite answer contract.

The generation settings add this optional field:

```text
top_logprobs: integer from 1 through 10
```

The LM Studio request maps it to `top_logprobs` and `include`.

The runtime receipt exposes tool-independent Token Probability Evidence.

The runner commands write bounded JSON status and durable evidence paths.

## 8. Behavior & Domain Rules

- Source characters remain authoritative.
- Gold supplies evaluation labels after model execution.
- Runtime probability evidence remains model evidence rather than source evidence.
- KoteKomi computes every score and threshold decision deterministically.
- Threshold retention never rewrites the literal model answer.
- Development can tune the threshold and Pool Arm.
- Validation cannot tune the frozen contract.
- Expected-Exact Accuracy is a feasibility estimate rather than a measured endpoint.
- Aggregate phase metrics remain the acceptance authority.
- CEA-1.5 cannot create a ProposedChange or accepted Ledger state.

## 9. Acceptance Criteria

- CEA15-ACC-01: Runtime tests verify request mapping, typed response mapping, and strict probability failures.
- CEA15-ACC-02: Domain and Application tests verify receipt serialization and validation.
- CEA15-ACC-03: Pipeline tests verify score grouping, ranking metrics, break-even estimates, and safety gates.
- CEA15-ACC-04: Pipeline tests verify threshold and Pool Arm freeze behavior.
- CEA15-ACC-05: The model-free runner preflight verifies sealed Prompt Arm recovery and generation binding.
- CEA15-ACC-06: The live diagnostic preserves two repetitions for both Prompt Arms.
- CEA15-ACC-07: The full replay runs only after one Prompt Arm passes the diagnostic gate.
- CEA15-ACC-08: The final package reports exact aggregate metrics against CEA-1.3.
- CEA15-ACC-09: Formatting, lint, typecheck, focused tests, and the full repository suite pass.

## 10. Reference Implementations

- Model execution: `packages/application/src/kotekomi_application/staged_model_extraction.py`
- LM Studio mapping: `packages/adapters/src/kotekomi_adapters/lm_studio_model_runtime.py`
- Pool evaluation: `packages/pipelines/src/kotekomi_pipelines/competitive_attachment_edge_filter.py`
- Experiment orchestration: `scripts/run_competitive_attachment_edge_filter_experiment.py`
- Review that motivated the calibration experiment: [`2nd-opinion-5.md`](../2nd-opinion-5.md)
- Runtime protocol: [LM Studio Open Responses](https://lmstudio.ai/blog/openresponses)

## 11. Constraints and Halt Conditions

- Stop before development when neither Prompt Arm clears every diagnostic gate.
- Stop when LM Studio omits any requested `Y`, `N`, or `U` alternative.
- Stop when one persisted receipt cannot reproduce its Attachment Score.
- Stop when one threshold changes the literal model answer.
- Stop when validation changes the development freeze.
- Stop when any experiment path writes canonical intelligence.

## 12. Implementation State

The Application Layer now owns typed token-probability, calibration, threshold, phase, freeze, report, manifest, and status contracts.

The LM Studio Adapter requests output-token alternatives only when `top_logprobs` is explicitly present.

The Adapter rejects missing or malformed requested evidence and maps valid evidence into the tool-independent receipt contract.

The Domain Core validates the persisted nested receipt shape, canonical ordering, contiguous positions, emitted-token membership, and probability agreement.

The Pipeline computes Y/N/U grouped probabilities, Attachment Scores, ranking metrics, threshold surfaces, expected exact-set feasibility, development selection, frozen validation, and the terminal outcome.

The resumable runner exposes `prepare`, `diagnose`, `run-development`, `run-validation`, and `finalize`.

An operator-requested retry preserves each validated `model_failed` execution under `failed-attempts/` before re-executing its task. `unclear` remains valid finite-answer evidence; invalid deterministic records are not retried or repaired.

The terminal package includes exact diagnostic data in and data out, aggregate phase comparisons, a second-opinion handoff, a digest-closed manifest, and typed terminal status.

The model-free preflight passed against the sealed CEA-1.4 V8 and V9 roots.

It recovered both exact Prompt Arms and validated sixteen diagnostic tasks, 162 development Candidates, 490 development Maximum-Pool Edges, 179 validation Candidates, and 257 validation Maximum-Pool Edges.

Focused formatting, lint, typecheck, and tests pass.

The live two-repetition diagnostic completed under the Cost-Saving Measures.

The first live diagnostic exposed a runtime-contract defect before producing semantic evidence. CEA-1.5 requested twenty alternatives, but the installed LM Studio MLX backend accepts at most ten. LM Studio rejected the first request and crashed while handling the second, unloading the model. The corrected Adapter rejects values above ten before generation transport, the experiment requests ten, terminal SSE errors retain the runtime message, and the failed run remains preserved rather than being interpreted as calibration evidence.

The corrected live diagnostic then completed its first sixteen-task repetition and exposed a deterministic replay-parser defect. The runner had passed a JSON-native dictionary to strict Python-mode `ModelRun` validation, which correctly rejected serialized enum and datetime strings. The runner now parses that persisted payload through canonical JSON mode, and all sixteen preserved execution records validate and remain reusable.

The resumed validator exposed the same boundary error for persisted `ExtractionStageTrace` tuples and enums. Trace replay now uses the same strict canonical JSON boundary rather than Python-mode coercion.

The first probability replay then exposed a finite-precision aggregation defect. LM Studio can report the winning token at log probability `0.0` while also reporting tiny same-answer token variants. Their direct log-sum-exp is slightly positive even though a log probability cannot exceed zero. KoteKomi now normalizes the grouped `Y`, `N`, and `U` masses as a conditional finite-answer distribution while retaining every raw runtime alternative in the receipt; the normalization leaves the Attachment Score invariant.

The same preserved repetition then exposed a generation-contract comparison defect. The runtime profile's `2,048`-token configured ceiling was compared directly with the finite Y/N/U task's effective three-token limit. The Application Layer now exposes the bounded Attachment Edge Filter generation contract, and the runner validates both `ModelRun.generation_parameters` and the execution-receipt digest against the effective settings actually sent to LM Studio. All sixteen preserved records carry the expected `{max_output_tokens: 3, seed: 17, temperature: 0, top_logprobs: 10}` settings and one matching receipt digest, so they remain reusable.

V8 produced AUROC `0.828125` and average precision `0.8295003607503607` in both repetitions.

V9 produced AUROC `0.84375` and average precision `0.8604548229548228` in both repetitions.

Both Prompt Arms preserved their cross-class score ordering across repetitions.

Neither Prompt Arm supplied one threshold that retained every Protected Positive and rejected every Hard Negative.

Both Prompt Arms therefore have the `not_separable` diagnostic outcome.

The diagnostic authorized no development replay.

The full repository suite passed before the diagnostic review.

The independent review correctly identified score drift, Prompt Arm contamination, and the former outcome-name defect.

The independent review also proposed a target-containment rejection rule.

A direct check against normalized occurrence-level Attachment Gold found that the rule would reject twelve Gold-positive Pool Edges.

CEA-1.6 records that check through a digest-bound model-free experiment.

Production integration remains `not_activated`.
