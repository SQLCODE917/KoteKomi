# TDD: Semantic Instruction Discrimination Experiment

- Status: Proposed
- Deliverable ID: `R18`
- Program: [Source-Grounded Attachment Agile Package](2026-10-01-source-grounded-attachment-agile-package.md)
- Parent: [Semantic Selection Contract](2026-10-07-semantic-selection-contract.md)
- Depends on: [Semantic Selection Contract](2026-10-07-semantic-selection-contract.md), [Corrective Re-Selection Execution](2026-10-06-corrective-reselection-execution.md), [Decontextualization Composition](2026-09-28-decontextualization-composition.md), [Parser-Constituent Sub-Span Candidate Generation](2026-09-25-parser-constituent-sub-span-candidate-generation.md), [Calibrated Residual Ownership](2026-09-29-calibrated-residual-ownership.md), [Residual Selection-Failure Closure](2026-10-01-residual-selection-failure-closure.md), [R6 runtime configuration](r6-calibrated-residual-ownership-run-config.toml)

## 1. Context & Problem

R17 freezes one versioned semantic selection contract and its five-signal evaluator.

R17 is model-free: it evaluates frozen observed answers against frozen reference policy records.

R17 runs no model under a semantic instruction.

R16 executes the two residual Events under the frozen R15 corrective instructions.

The original selection instruction and both R15 corrective instructions name answer format only.

R16 produces grammatically valid answers that fail semantic selection: `AHE-022` selects every Candidate and `AHE-051` abstains with `NONE`.

No experiment has measured whether naming the eligibility rule and the complete-selected-set rules changes the observed selection.

R18 asks one question: does naming the eligibility and complete-selected-set rules improve the instruction-sensitive signals over the format-only instruction?

R18 keeps the source text, the Candidate pools, the routes, the model, and the runtime configuration fixed.

R18 varies only the instruction prefix.

R18's semantic instruction names only the eligibility rule and the complete-selected-set rules, so its conclusion is scoped to that instruction prefix.

R18 runs one execution per (variant, record) pair, which supports a bounded development result, not a general reliability claim.

R18 reuses the R16 execution infrastructure and the R17 evaluation.

### Terms

The terms Reference policy record, Observed answer, Eligibility rule, Complete-selected-set rules, NONE, Answer grammar, Semantic selection, Boundary coverage, Abstention correctness, Composition readiness, Expected selected set, Expected source range, Route, Event, Candidate, Candidate label, Candidate pool, Event frame, Constituent Selection Task, Run root, Execution item, Model execution receipt, and ModelInputAdmission keep their existing meanings.

**Instruction variant** means one pinned instruction prefix the model reads: `format_only` or `semantic`.

**Format-only instruction** means the frozen R15 corrective instruction for the Event's route; it names answer format only.

**Semantic instruction** means the format-only instruction followed, verbatim, by the frozen R17 eligibility rule and the five complete-selected-set rules. It deliberately omits the R17 NONE rule and the canonical-boundary rules, so every conclusion is evidence about that instruction prefix, never the whole R17 policy.

**Discrimination experiment** means one controlled comparison of the two instruction variants over one fixed case set under one fixed execution budget.

**Execution budget** means the predetermined maximum model executions for the experiment.

**Terminal outcome** means one of `answered`, `blocked`, or `failed` for one (instruction variant, reference policy record) pair.

**Experimental observation** means one unreviewed model response admitted through R18's experimental path and bound to its prepared task, execution receipt, and archived response; it never carries a human review claim.

**Discrimination verdict** means the predeclared, per-signal comparison of the three instruction-sensitive signals across the two variants, with an explicit denominator that keeps malformed and terminal pairs in the count.

### Primary flow

1. The runner loads the frozen R17 contract and the 11 reference policy records.
2. The runner renders two prompts per reference policy record: one format-only and one semantic.
3. The operator starts the experiment against the configured LM Studio runtime.
4. The Application Layer admits each prompt through the existing tokenizer contract; an admission-blocked pair becomes terminal `blocked` with no model execution.
5. The Application Layer invokes the model once per admitted pair and archives each raw response and execution receipt.
6. The Application Layer parses each archived response once through the route's strict R16 grammar; a runtime failure becomes terminal `failed`.
7. The Application Layer evaluates each answered pair through the five-signal experimental evaluator.
8. The Application Layer applies the predeclared verdict to the three instruction-sensitive signals with an explicit denominator.
9. The Application Layer seals one report with zero canonical writes and zero ProposedChanges.

## 2. Goals

- Operators observe, per reference policy record, the five signals under the format-only instruction and under the semantic instruction, reported separately.
- Operators observe the three instruction-sensitive signals compared across the two variants.
- Operators observe the two instruction-invariant signals restated, never merged, and never used to judge instruction discrimination.
- Operators observe one reproducible report rebuilt from archived responses with zero canonical writes and zero ProposedChanges.
- Operators observe each semantic instruction pinned to the frozen R17 rule text.
- Operators observe one predeclared, per-signal verdict whose denominator counts every malformed and terminal pair.
- Operators observe `AHE-022` and `AHE-051` reported individually and distinguished from the nine constructed cases.

## 3. Requirements

### Instruction variants

- R18-INS-01: The format-only instruction equals the frozen R15 corrective instruction for the Event's route, byte for byte.
- R18-INS-02: The semantic instruction equals the format-only instruction followed by the frozen R17 eligibility rule and the five complete-selected-set rules, byte for byte.
- R18-INS-03: No other instruction text enters either variant.
- R18-INS-04: The prompt body — Event frame, Passage, and Candidates — is byte-identical across variants and equals the frozen R15 corrective task body.
- R18-INS-05: The route grammar stays unchanged: `label_only_reselection` forbids `NONE`, and `best_choice_reselection` permits exactly one label or the exact token `NONE`.
- R18-INS-06: The semantic instruction names only the eligibility rule and the complete-selected-set rules; it names no NONE rule and no canonical-boundary rule, so its conclusions are scoped to that prefix.

### Case set, execution budget, and terminal outcomes

- R18-CASE-01: The experiment runs the 11 frozen R17 reference policy records.
- R18-CASE-02: Each record's source text, Candidate pool, route, and Event frame come from the frozen R17 input bindings.
- R18-BUDGET-01: The execution budget is at most 22 model executions: at most one per (instruction variant, reference policy record) pair.
- R18-BUDGET-02: The experiment produces exactly 22 terminal pair records, one per (instruction variant, reference policy record) pair.
- R18-BUDGET-03: A blocked or runtime-failed pair becomes a terminal `blocked` or `failed` record; the runner never retries it.
- R18-BUDGET-04: The comparison is complete only when all 22 pairs are `answered`; otherwise the report marks the experiment incomplete.
- R18-RT-01: The runner selects LM Studio and `qwen2.5-14b-instruct` through the frozen R6 configuration, with temperature `0` and seed `17`.
- R18-RT-02: The Application Layer admits each prompt through the existing tokenizer contract; admission blocking yields `blocked`, never an execution.
- R18-RT-03: The Application Layer archives each raw response and execution receipt before parsing; a runtime failure yields `failed`.

### Experimental admission (observed answers)

- R18-OBS-01: R18 introduces one experimental observation path; it never constructs the reviewed-fixture `ObservedAnswer` and never fabricates `reviewer_identity`, `review_mode`, `review_date`, `review_commit`, or human `review_evidence`.
- R18-OBS-02: One experimental observation binds a pair to its prepared task route, its model execution receipt, and its digest-verified archived raw response.
- R18-OBS-03: The experimental evaluator produces the five signals through the exact R17 signal rules (the same computation as `evaluate_selection`); `evaluate_selection` itself stays byte-identical and remains the reviewed-fixture evaluator.
- R18-OBS-04: The reviewed-fixture loader keeps failing fast on any `ObservedAnswer` missing review metadata; R18 never weakens or bypasses those checks.
- R18-OBS-05: An experimental observation is marked `unreviewed_experimental` and can never become a reviewed answer fixture or a canonical write.

### Evaluation reuse

- R18-EVL-01: The evaluator parses each archived answer once through the R16 strict parser and applies the exact R17 five-signal rules through the experimental observation path; the reviewed-fixture `evaluate_selection` stays byte-identical.
- R18-EVL-02: The five signals never merge into one score.
- R18-EVL-03: `semantic_selection`, `answer_grammar`, and `abstention_correctness` are instruction-sensitive and are the comparison signals.
- R18-EVL-04: `boundary_coverage` and `composition_readiness` evaluate the frozen reference record, not the observed answer, and restate identically across variants.

### Report

- R18-REP-01: The report records, per (instruction variant, reference policy record) pair, a terminal outcome, and for `answered` pairs the raw response digest, the parsed answer, and the five signal results.
- R18-REP-02: The report rebuilds from archived responses without another model call.
- R18-REP-03: The report records zero canonical writes and zero ProposedChanges.
- R18-REP-04: The report carries one result fingerprint that changes when any terminal outcome, signal result, or raw response digest changes.
- R18-REP-05: A sealed report is immutable; another experiment requires a new Run root.
- R18-REP-06: The report separates `AHE-022` and `AHE-051` into one diagnostic group and the remaining nine records into one constructed group, and reports each of the two diagnostic records individually.

### Verdict (predeclared)

- R18-VER-01: The verdict is per signal, never one merged experiment score.
- R18-VER-02: `answer_grammar` compares `valid` against `invalid`; `invalid` is a malformed tally, never ordered below `valid`.
- R18-VER-03: `semantic_selection` orders `unmet` below `met`; a malformed record carries `not_applicable` and is tallied as malformed, never mapped onto the `unmet`/`met` scale.
- R18-VER-04: `abstention_correctness` orders `unjustified` below `justified` over records that observed NONE; `not_applicable` means no NONE observed (or malformed) and is tallied separately.
- R18-VER-05: The denominator for every signal is the full pair count for its group; no malformed, blocked, or failed pair is dropped from the comparison.
- R18-VER-06: `improvement` requires at least one strictly better comparable pair and zero strictly worse comparable pairs.
- R18-VER-07: `regression` requires at least one strictly worse comparable pair and zero strictly better comparable pairs.
- R18-VER-08: `mixed` requires at least one strictly better and at least one strictly worse comparable pair.
- R18-VER-09: `inconclusive` covers no difference across comparable pairs, or any incomplete comparison (a non-`answered` pair, or a malformed pair that makes the signal undecidable).
- R18-VER-10: One execution per condition bounds the claim to a development result, never a general reliability claim.

## 4. Proposed Architecture

```text
frozen R17 contract + 11 reference policy records
      |
      +--> instruction renderer -----------------> two prompts per record
      |        format-only = frozen R15 corrective instruction
      |        semantic     = format-only + eligibility + complete-selected-set rules
      |                                (no NONE rule, no canonical-boundary rules)
      |
      v
experimental admission (tokenizer contract) --blocked--> terminal BLOCKED (no execution)
      |
      v
LM Studio Adapter (temperature 0, seed 17, at most one call per pair)
      |
      +--> execution receipt + archived raw response --failed--> terminal FAILED
      |
      v
experimental observation (unreviewed) -> R16 strict parser + R17 five signal rules
      |-- answer grammar           instruction-sensitive
      |-- semantic selection       instruction-sensitive
      |-- boundary coverage        instruction-invariant
      |-- abstention correctness   instruction-sensitive
      |-- composition readiness    instruction-invariant
      |
      v
predeclared per-signal verdict (22 terminal records, explicit denominators)
      |
      v
sealed, reproducible report (zero canonical writes, zero ProposedChanges)
```

## 5. Key Interactions

The runner loads the frozen R17 contract and the 11 reference policy records and renders two prompts per record.
The two prompts share one byte-identical body and differ only in the instruction prefix; the semantic prefix names only the eligibility and complete-selected-set rules.
The Application Layer admits each prompt through the tokenizer contract; an admission-blocked prompt becomes a terminal `blocked` pair with no model call.
The Application Layer invokes the model at most once per pair and archives each raw response with its execution receipt; a runtime failure becomes a terminal `failed` pair.
The evaluator parses each answered response once through the R16 strict parser and applies the five R17 signal rules through the experimental observation path, without fabricating a human review.
Boundary coverage and composition readiness evaluate the frozen reference record and restate identically across the two variants.
The report compares the three instruction-sensitive signals across variants with the predeclared verdict and never merges any signal into one score.
The report keeps the malformed, blocked, and failed pairs in the denominator and reports the diagnostic records individually.
The report rebuilds from archived responses without invoking the model again.

## 6. Data Model

`InstructionVariant` names one of `format_only` or `semantic`.
`TerminalOutcome` names one of `answered`, `blocked`, or `failed`.
`ExperimentalObservation` stores, for one pair, the Event ID, the route, the instruction variant, the unreviewed experimental marker, the execution receipt reference, the archived raw response reference and digest, and the reused parsed answer.
`DiscriminationObservationItem` stores, per pair, the terminal outcome and, when `answered`, the five signal results.
`DiscriminationReport` stores the contract version, the diagnostic group (`AHE-022`, `AHE-051`) and the constructed group (nine records), the ordered observation items, the per-signal per-variant counts and malformed tallies, and the result fingerprint.
Every structured record rejects unknown fields and impossible combinations.

## 7. APIs / Interfaces

The runner is `scripts/run_semantic_instruction_discrimination.py`.
The runner exposes `prepare`, `execute`, `report`, and `show`.
`prepare` renders the two prompts per record, verifies the frozen R17 contract binding, and writes a `prepared` Run root.
`execute` runs the model at most once per pair under the frozen R6 configuration and archives every execution receipt and raw response, recording terminal outcomes.
`report` rebuilds the sealed report from archived responses without invoking the model.
`show` returns the validated report fingerprint, the per-signal counts, and the predeclared verdict.

## 8. Behavior & Domain Rules

The instruction variant is one of `format_only` or `semantic`; the route grammar never changes.
The semantic variant names only the eligibility rule and the complete-selected-set rules; it names no NONE rule and no canonical-boundary rule, so every conclusion scopes to that instruction prefix.
The five signals stay independent; the experiment never converts them into one selection score.
Boundary coverage and composition readiness evaluate the reference policy record, never the observed answer, so the instruction cannot change them.
A justified abstention and a typed hold are records, never counted as completed selection or completed composition.
An experimental observation is unreviewed and never carries a human review claim; the reviewed-fixture `ObservedAnswer` path and its fail-fast checks stay unchanged.
A terminal pair is `blocked` when admission blocks the call, `failed` when a runtime step fails, and `answered` otherwise; only `answered` pairs carry response-dependent results.
A malformed record fails the strict R16 grammar and still counts in the denominator for every signal, never mapped onto an ordered scale.
Selecting the correct `C3` for `AHE-051` under the semantic instruction raises `semantic_selection` to `met` while `boundary_coverage` stays `gap` and `composition_readiness` stays `not_ready`.
`AHE-022`'s composition readiness remains `not_ready` because its subject role lacks a resolved entity reference, so semantic selection and composition follow-up stay separate decisions.
`AHE-022` and `AHE-051` form the diagnostic group reported individually; the remaining nine records form the constructed group reported in the aggregate.
The experiment writes no canonical Ledger state and no ProposedChanges.
The experiment does not tune against the held-out partition.

## 9. Acceptance Criteria

- AC-R18-INS: Tests prove the renderer emits exactly two prompts per record whose shared body is byte-identical and whose instruction prefixes equal the frozen R15 and R17 rule text; the semantic prefix names only the eligibility and complete-selected-set rules.
- AC-R18-OBS: Tests prove an experimental observation binds to its prepared task, execution receipt, and archived response, carries no fabricated human review metadata, and that the reviewed-fixture loader still fails fast on missing review metadata.
- AC-R18-BUDGET: Tests prove 22 terminal pair records with at most 22 model executions, and that a blocked or failed pair becomes terminal without retry.
- AC-R18-EVL: Tests prove the experimental evaluator applies the exact R17 five-signal rules and reports the three instruction-sensitive signals and the two instruction-invariant signals separately.
- AC-R18-VER: Tests prove the verdict is per signal, keeps malformed and terminal pairs in the denominator, and computes improvement, regression, mixed, and inconclusive as specified.
- AC-R18-REP: Tests prove the report rebuilds from archived responses, records zero canonical writes and zero ProposedChanges, separates the diagnostic from the constructed group, and changes fingerprint when any terminal outcome, signal result, or raw response digest changes.
- AC-R18-LIVE: The operator-run experiment records 22 terminal pair records with at most 22 model executions, zero canonical writes, and zero ProposedChanges; the comparison is complete only when all 22 pairs are `answered`.
- AC-R18-ALL: Focused formatting, lint, typecheck, and tests pass.

## 10. Reference Implementations

- Corrective instruction text: `packages/application/src/kotekomi_application/residual_selection_failure_closure.py` (`corrective_instruction_for`).
- Eligibility and complete-selected-set rule text: `packages/application/src/kotekomi_application/semantic_selection_contract.py`.
- Strict grammar parsers: `packages/application/src/kotekomi_application/corrective_reselection_execution.py`.
- Five-signal evaluator: `packages/application/src/kotekomi_application/semantic_selection_contract.py` (`evaluate_selection`).
- Model execution runner and config: `scripts/run_corrective_reselection_execution.py`, `docs/r6-calibrated-residual-ownership-run-config.toml`.
- Reference policy records and input bindings: `data/r17-semantic-selection-contract/reference_policy_records.json`, `data/r17-semantic-selection-contract/task_manifest.json`, `data/r17-semantic-selection-contract/inputs/`.
- New module: `packages/application/src/kotekomi_application/semantic_instruction_discrimination.py`.
- Tests: `packages/application/tests/test_semantic_instruction_discrimination.py`.

## 11. Constraints and Halt Conditions

Keep the R3 parser, the R4 composer, the R11 classifier, the R12 recovery, and the R15 closure routes unchanged.
Do not change the route grammar, the model, the seed, the temperature, the source text, the Candidate pools, or the runtime configuration.
Do not read the held-out partition Gold.
Do not merge the five signals into one score.
Do not count a justified abstention or a typed hold as a completed selection or a completed composition.
Halt when the frozen R17 contract binding fails to verify.
Halt when the execution budget exceeds 22 model executions.
Halt when the report records any canonical write or ProposedChange.

## 12. Execution & Experimentation Directive

- Implement the instruction renderer, the experimental observation path, the terminal-outcome model, the runner, and the report model.
- Verify the renderer, the admission path, the verdict, and the report with focused tests.
- Hand the live `execute` phase to the operator under the frozen R6 configuration.
- Inspect the sealed report after the operator reports completion.
- Record the per-signal comparison and the predeclared verdict in the Run Record.
- Decide the next logical step from the observed signals.

## 13. Run Record

Pending execution.