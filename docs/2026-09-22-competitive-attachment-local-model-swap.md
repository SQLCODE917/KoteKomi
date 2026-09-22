# TDD: CEA-1.24 Local Model Swap

- Status: Implemented; output transport recalibrated; execution pending; production inactive
- Deliverable ID: `CEA-1.24`
- Program:
  [Competitive Event Attachment Program](2026-09-18-competitive-event-attachment-program.md)
- Predecessor:
  [CEA-1.23 Nested Event Ownership Transfer](2026-09-21-competitive-attachment-nested-event-transfer.md)

## 1. Context & Problem

CEA-1.23 tested one bounded semantic ownership question on twenty blind cross-document cases.

Qwen2.5-14B answered sixteen cases correctly.

The result established transfer but did not meet the production-readiness gates.

The previous experiments changed task structure, rendering, or deterministic policy while they kept the language model fixed.

**Historical Baseline** means the exact Qwen2.5-14B executions preserved by CEA-1.23.

**Comparator Baseline** means one new Qwen2.5-14B replay of all twenty cases under Exact Source Context.

**Exact Source Context** means the ContextManifest renders the already-selected SourceSegment as one exact focus node without sentence segmentation.

**Challenger Model** means one locally loaded Qwen3-14B GGUF model.

**Semantic Prompt** means the unchanged CEA-1.23 prompt bytes.

**Non-Thinking Control** means the exact `/no_think` text that the renderer appends after the complete task for Qwen3.

**Primary Variant** means Qwen3-14B `Q6_K`.

**Fallback Variant** means Qwen3-14B `Q5_K_M`.

**Output Transport Allowance** means the maximum output-token count sent to LM Studio.

The first Challenger execution used the two-token Output Transport Allowance from CEA-1.23.

All twenty ModelRuns ended with the same runtime response error.

LM Studio marked each request complete but supplied no `output_text` item.

A bounded probe varied only the Output Transport Allowance and log-probability request.

The two-token control supplied no `output_text` item.

The sixteen-token controls supplied one exact `N` output token.

The result remained the same with and without log probabilities.

The sixteen-token control reported zero reasoning tokens.

CEA-1.24 therefore uses a sixteen-token Output Transport Allowance for Qwen3.

KoteKomi still accepts only one exact `Y`, `N`, or `U` output token.

The Primary Flow is:

1. The runner validates the complete CEA-1.23 package and blind labels.
2. The Comparator Baseline answers all twenty questions under Exact Source Context.
3. The runner records Historical-to-Comparator answer changes.
4. The operator estimates and loads the Primary Variant in LM Studio.
5. The runner verifies the loaded artifact and Non-Thinking Control.
6. The Challenger Model answers the same twenty semantic questions under Exact Source Context.
7. The evaluator compares each Challenger answer with blind Gold and the Comparator Baseline answer.
8. The runner writes exact evidence and a second-opinion handoff.

The operator may select the Fallback Variant only after the Primary Variant fails its memory or load gate.

The experiment creates no ProposedChange or accepted Ledger record.

The experiment does not activate production routing.

## 2. Goals

- An operator can compare Qwen3-14B with Qwen2.5-14B on identical semantic cases.
- An operator can distinguish a model change from the corrected context-rendering policy.
- An operator can verify which quantized model artifact produced every answer.
- An operator can see every corrected case and every regression.
- An operator can distinguish model quality from prompt or Gold changes.
- An operator can send one self-contained evidence package for independent review.

## 3. Requirements

### Baseline binding

- CEA124-BAS-01: The Pipeline validates the complete CEA-1.23 report and every referenced evidence digest.
- CEA124-BAS-02: The Pipeline reuses all twenty CEA-1.23 cases in their original order.
- CEA124-BAS-03: The Pipeline reuses the exact CEA-1.23 blind review response.
- CEA124-BAS-04: The Pipeline reuses the exact CEA-1.23 Semantic Prompt bytes.
- CEA124-BAS-05: The Pipeline does not regenerate or revise an expected label.
- CEA124-BAS-06: The Comparator Baseline replays all twenty cases with the CEA-1.23 Qwen2.5 runtime contract and generation settings.
- CEA124-BAS-07: The Comparator Baseline uses Exact Source Context for every case.
- CEA124-BAS-08: The Pipeline preserves Historical-to-Comparator corrections and regressions by source occurrence.

### Exact source context

- CEA124-CTX-01: The runner treats each catalog SourceSegment as the complete authoritative focus node.
- CEA124-CTX-02: The ContextPlanner does not apply sentence segmentation to that focus node.
- CEA124-CTX-03: The ContextManifest contains the complete exact SourceSegment once.
- CEA124-CTX-04: The task-local `Passage` contains the same complete exact SourceSegment once.
- CEA124-CTX-05: The Pipeline fails before model execution when either exact occurrence is missing or duplicated.
- CEA124-CTX-06: The Challenger input before the terminal Non-Thinking Control equals the Comparator Baseline input byte for byte.

### Model artifact

- CEA124-MOD-01: The Challenger Model architecture is `qwen3`.
- CEA124-MOD-02: The Challenger Model parameter description identifies the 14B model.
- CEA124-MOD-03: The Primary Variant quantization is `Q6_K`.
- CEA124-MOD-04: The Fallback Variant quantization is `Q5_K_M`.
- CEA124-MOD-05: A Fallback Variant run records a non-empty Primary Variant failure reason.
- CEA124-MOD-06: The Pipeline preserves the LM Studio model key, loaded instance identifier, format, quantization, size, context length, and raw metadata digest.
- CEA124-MOD-07: The loaded instance identifier equals the configured model identifier.
- CEA124-MOD-08: The loaded context length equals the Comparator Baseline's `16384` tokens.
- CEA124-MOD-09: The Primary Variant memory gate requires an LM Studio `Estimated Total Memory` of at most `18 GiB` and no resource-guardrail rejection.
- CEA124-MOD-10: The Fallback Variant preserves the rejected Q6_K readiness record and identifies an estimate above `18 GiB`, an LM Studio resource-guardrail rejection, or a failed Primary Variant load.

### Model task

- CEA124-TASK-01: The Semantic Prompt digest equals the CEA-1.23 prompt digest.
- CEA124-TASK-02: The Challenger input before the Non-Thinking Control equals the Comparator Baseline model input.
- CEA124-TASK-03: The renderer appends `/no_think` after the complete model-visible task.
- CEA124-TASK-04: The model input contains no expected label or reviewer rationale.
- CEA124-TASK-05: The Challenger Model returns exactly `Y`, `N`, or `U`.
- CEA124-TASK-06: The Pipeline preserves exact input, raw output, token evidence, and elapsed time.
- CEA124-TASK-07: The Pipeline rejects an execution that contains a reasoning preamble or another extra output token.
- CEA124-TASK-08: The Comparator uses a two-token Output Transport Allowance.
- CEA124-TASK-09: The Challenger uses a sixteen-token Output Transport Allowance.
- CEA124-TASK-10: The Pipeline requires one observed Challenger output token.
- CEA124-TASK-11: The Pipeline reports the preserved runtime error before it checks for a receipt.

### Evaluation

- CEA124-EVL-01: The evaluator scores every source occurrence independently.
- CEA124-EVL-02: The evaluator reports Challenger accuracy and `Y` and `N` recall.
- CEA124-EVL-03: The evaluator reports corrected, regressed, unchanged-correct, and unchanged-incorrect case IDs.
- CEA124-EVL-03A: The evaluator reports Historical-to-Comparator transitions separately from Comparator-to-Challenger transitions.
- CEA124-EVL-04: The evaluator reports Comparator Baseline and Challenger elapsed time separately.
- CEA124-EVL-05: `supported` requires at least eighteen correct Challenger answers.
- CEA124-EVL-06: `supported` requires at least `0.85` Challenger recall for both `Y` and `N`.
- CEA124-EVL-07: `supported` requires a positive accuracy delta and more corrections than regressions.
- CEA124-EVL-08: `supported` requires zero invalid, failed, blocked, or unclear Challenger answers.
- CEA124-EVL-09: `mixed` records a partial improvement or an equal score with both corrections and regressions.
- CEA124-EVL-10: A complete result that does not meet `supported` or `mixed` is `falsified`.
- CEA124-EVL-11: One unresolved Challenger result makes the outcome `inconclusive`.

### Evidence package

- CEA124-PKG-01: The runner writes a typed model-artifact preflight before model execution.
- CEA124-PKG-02: The report preserves each exact input, expected answer, Historical Baseline answer, Comparator Baseline answer, and Challenger answer.
- CEA124-PKG-03: The handoff identifies the four CEA-1.23 failures and their Challenger outcomes.
- CEA124-PKG-04: The handoff states that one model family and twenty cases limit the inference.
- CEA124-PKG-05: The report records zero canonical writes.
- CEA124-PKG-06: The report binds the byte-exact Qwen3 output calibration evidence.

## 4. Proposed Architecture

```text
sealed CEA-1.23 package
          |
          +----> blind Gold labels
          |
          +----> frozen Semantic Prompt
          |
          v
Qwen2.5 ----> Exact Source Context ----> Comparator Baseline
                                            |
                                            v
LM Studio model metadata ----> verified Qwen3-14B variant
                                      |
                                      v
                         Non-Thinking task renderer
                                      |
                                      v
                      calibrated transport allowance
                                      |
                                      v
                           occurrence evaluator
```

The Application Layer owns the model-artifact and comparison evidence contracts.

The Application Layer owns the Non-Thinking task renderer.

The Pipeline owns artifact verification and occurrence evaluation.

The disposable runner owns local runtime inspection and evidence-package composition.

## 5. Key Interactions

```text
Operator        Runner          LM Studio       Pipeline
   |               |                |               |
   | baseline      |                |               |
   |-------------->| Qwen2.5 exact-context replay  |
   |               |------------------------------->| compare history
   |<--------------| comparator report             |
   | load model    |                |               |
   |-------------->| inspect        |               |
   |               |--------------->| metadata      |
   |               |<---------------|               |
   | run           |                |               |
   |-------------->| validate comparator            |
   |               |--------------->| twenty tasks  |
   |               |<---------------| answers       |
   |               |------------------------------->| compare
   |<--------------| report and handoff             |
```

## 6. Data Model

`AttachmentLocalModelArtifact` records the exact loaded Challenger Model artifact.

`AttachmentLocalModelOutputCalibration` records the byte-exact Qwen3 calibration result.

`AttachmentLocalModelSwapCase` compares one Historical Baseline answer, one Comparator Baseline answer, and one Challenger answer.

`AttachmentLocalModelSwapReport` records metrics, outcome, and complete lineage.

All three records remain derived experiment evidence.

## 7. APIs / Interfaces

The `prepare` command accepts the complete CEA-1.23 root and one output root.

The `prepare` command writes the expected model and immutable baseline bindings.

The `run-baseline` command executes the twenty-case Comparator Baseline.

The `run` command accepts the output root and one KoteKomi configuration.

The `run` command accepts a loaded model identifier and one model variant.

The `run` command accepts the byte-exact output calibration root.

The `run` command accepts an optional fallback reason.

The `run` command reads LM Studio model metadata before model execution.

The `run` command writes execution records, a report, a review, and a second-opinion handoff.

## 8. Behavior & Domain Rules

- The Non-Thinking Control configures Qwen3 behavior rather than defining semantic task meaning.
- The renderer places the Non-Thinking Control after the complete task.
- The Comparator uses the CEA-1.23 two-token Output Transport Allowance.
- The Challenger uses the calibrated sixteen-token Output Transport Allowance.
- The evaluator requires one exact output token from both models.
- The report labels the exact quantization as experiment evidence.
- The Fallback Variant does not silently replace the Primary Variant.
- The Pipeline preserves Historical Baseline, Comparator Baseline, and Challenger errors independently.
- The experiment does not write canonical state.

## 9. Acceptance Criteria

- CEA124-ACC-01: Tests reject a changed CEA-1.23 prompt, case, label, or artifact digest.
- CEA124-ACC-01A: Tests prove a multi-sentence SourceSegment remains complete in Exact Source Context.
- CEA124-ACC-01B: Tests reject truncated, duplicated, or re-segmented Exact Source Context before runtime invocation.
- CEA124-ACC-02: Tests reject a non-Qwen3, non-14B, unknown-quantization, or wrong-instance model.
- CEA124-ACC-03: Tests require a fallback reason only for `Q5_K_M`.
- CEA124-ACC-03A: Tests reject a missing, mismatched, over-limit, or guardrail-rejected LM Studio readiness record.
- CEA124-ACC-04: Tests prove that `/no_think` is the final model-visible content.
- CEA124-ACC-04A: Tests lock the Comparator allowance at two tokens.
- CEA124-ACC-04B: Tests lock the Challenger allowance at sixteen tokens.
- CEA124-ACC-04C: Tests reject every successful output except one exact answer token.
- CEA124-ACC-04D: Tests expose the exact ModelRun error before receipt validation.
- CEA124-ACC-05: Tests prove corrected and regressed case classification.
- CEA124-ACC-06: Tests prove all four terminal outcomes.
- CEA124-ACC-07: Focused formatting, lint, typecheck, and tests pass.
- CEA124-ACC-08: The report records zero canonical writes.
- CEA124-ACC-09: Tests reject calibration evidence for a different input or runtime control.

## 10. Reference Implementations

- Blind Gold and execution evidence: `competitive_attachment_nested_event_transfer.py`.
- Model runtime identity: `lm_studio_model_runtime.py`.
- Output transport calibration: `2026-09-20-competitive-attachment-runtime-calibrated-termination.md`.
- Model metadata: [LM Studio List Models](https://lmstudio.ai/docs/developer/rest/list).
- Non-Thinking Control: [LM Studio Qwen3-14B](https://lmstudio.ai/models/qwen/qwen3-14b).
- Quantized artifacts: [Qwen3-14B GGUF](https://huggingface.co/Qwen/Qwen3-14B-GGUF).

## 11. Constraints and Halt Conditions

- Stop when the CEA-1.23 package fails validation.
- Stop when the Comparator Baseline differs from the Historical Baseline in model identity, generation settings, prompt, cases, or labels.
- Stop when one Comparator or Challenger input violates Exact Source Context.
- Stop when LM Studio metadata cannot identify the exact loaded artifact.
- Stop when the Primary Variant fails and no reason authorizes the Fallback Variant.
- Stop when `/no_think` is not the final model-visible content.
- Stop when a Challenger response lacks one exact output token.
- Stop when one expected answer enters a model input.
- Stop before production integration.
