# TDD: Corrective Re-Selection Execution

- Status: Accepted
- Deliverable ID: `R16`
- Next: [R17 Semantic Selection Contract](2026-10-07-semantic-selection-contract.md)
- Program: [Source-Grounded Attachment Agile Package](2026-10-01-source-grounded-attachment-agile-package.md)
- Parent: [Residual Selection-Failure Closure](2026-10-01-residual-selection-failure-closure.md)
- Depends on: [Residual Selection-Failure Closure](2026-10-01-residual-selection-failure-closure.md), [Calibrated Residual Ownership](2026-09-29-calibrated-residual-ownership.md), [Decontextualization Composition](2026-09-28-decontextualization-composition.md), [R6 runtime configuration](r6-calibrated-residual-ownership-run-config.toml)

## 1. Context & Problem

The operator needs to learn whether two corrected questions resolve the remaining selection failures.
The frozen run-005 experiment left `AHE-022` and `AHE-051` without selected Candidate labels.
R15 prepared one corrected question for each Event.
R15 executed neither question.
R16 will execute those questions once and record the actual selection and composition results.

### Terms

**Candidate label** identifies one parser constituent in an ordered Candidate list.
**Constituent Selection Task** binds an Event, Source text, Candidate labels, and a rendered question.
**CorrectiveSelectionTask** is the existing R15 DTO that binds a corrected question and its digests.
**Closure route** selects the R15 instruction and the permitted answer grammar.
**ConstituentSelectionAnswer** records `selected`, `none`, or `rejected`, with selected label indexes.
**Composer** is the existing deterministic Application Layer use case that produces a proposition or a hold.
**DecontextualizedProposition** records that proposition or hold, including its typed reason.
**Run root** is an immutable experiment directory, except for its typed lifecycle status.
**Execution item** binds one Event's attempt evidence, parsed answer, and composition result.

The [R15 TDD](2026-10-01-residual-selection-failure-closure.md) defines both closure routes.
The [Domain rules](agent/domain.md) define Ledger, Archive, Event, Source, and ProposedChange.

### Current evidence

R15 records the following routes.

| Event | Original slot | Closure route |
|---|---|---|
| `AHE-022` | `rejection_no_valid_label` | `label_only_reselection` |
| `AHE-051` | `abstained` | `best_choice_reselection` |

R12 through R14 already close the `AHE-004` arc.
The run-005 execution used LM Studio with model key `qwen2.5-14b-instruct`.
The best-choice question permits `NONE` when no Candidate fits.
A valid selection alone does not prove a complete proposition or semantic correctness.

### Primary flow

1. The operator prepares a new Run root from the sealed R15 report and frozen run-005 records.
2. The agent verifies the prepared questions and gives the operator the execution command.
3. The operator starts the experiment against the configured local runtime.
4. The Application Layer records each answer and applies the route's strict grammar.
5. The Composer re-measures each selected answer using the frozen constituent and dependency records.
6. The operator reports completion, and the agent inspects the sealed report to choose the next deliverable.

## 2. Goals

- The operator observes one terminal execution item for each of the two residual Events.
- The operator can distinguish selection rejection, abstention, runtime failure, and composition hold.
- The operator can inspect exact questions and answers after execution.
- The operator observes zero accepted Ledger changes and zero ProposedChanges.
- The operator can rebuild the report without another model call.

## 3. Requirements

### Frozen inputs: Pipeline

- R16-IN-01: The Pipeline validates R15 records through their declared DTOs and recomputes the report fingerprint.
- R16-IN-02: The Pipeline binds R15 to the run-005 report fingerprint recorded in R15 `run.json`.
- R16-IN-03: The Pipeline requires exactly `AHE-022` and `AHE-051`, ordered and distinct.
- R16-IN-04: The Pipeline verifies source file digests against run-005 `run.json` before preparing questions.
- R16-IN-05: The Pipeline validates original tasks, selectable constituents, Event frames, and dependency tokens through their DTOs.
- R16-IN-06: The Pipeline verifies each R15 prompt equals its instruction plus the unchanged original task body.
- R16-IN-07: The Pipeline verifies labels match the ordered selectable constituents and source-exact spans.
- R16-IN-08: The Pipeline reads no Gold, catalog, PDF, or model-derived replacement for the frozen inputs.

### Runtime: Application Layer and Adapter

- R16-RT-01: The Pipeline selects LM Studio and `qwen2.5-14b-instruct` through the explicit R6 configuration.
- R16-RT-02: The Application Layer pins the loaded model identity and generation settings before execution.
- R16-RT-03: The Application Layer requests temperature `0`, seed `17`, and `max_output_tokens` from `ModelExecutionConfig.max_output_tokens`.
- R16-RT-04: The Application Layer admits each complete corrected prompt through the existing runtime tokenizer contract.
- R16-RT-05: The Adapter receives the exact corrected prompt bytes through `ModelTaskRuntime`.
- R16-RT-06: The Application Layer calls `run_model_task` at most once per Event in one Run root.
- R16-RT-07: The Application Layer validates each returned receipt against the admitted input, model identity, and generation settings.
- R16-RT-08: The Application Layer records blocked admission and runtime errors as terminal execution items.
- R16-RT-09: The Application Layer archives a completed response before parsing its answer grammar.
- R16-RT-10: The Adapter enforces `ModelExecutionConfig.timeout_seconds` as the total wall-clock deadline and discards partial answers on expiry.
- R16-RT-11: The Application Layer persists admission, execution specification, and attempt status before invocation.

### Answer grammar: Application Layer

- R16-ANS-01: The Application Layer decodes UTF-8 and permits outer ASCII whitespace without changing archived bytes.
- R16-ANS-02: The label-only route accepts one or more distinct labels separated by commas.
- R16-ANS-03: The label-only route permits ASCII spaces and tabs around commas.
- R16-ANS-04: The best-choice route accepts exactly one Candidate label or exact uppercase `NONE`.
- R16-ANS-05: The Application Layer rejects every foreign label, duplicate label, empty element, and non-grammar character.
- R16-ANS-06: The Application Layer orders accepted label indexes by the frozen Candidate list.
- R16-ANS-07: The Application Layer emits `ConstituentSelectionAnswer` with empty indexes for abstention and rejection.

### Composition: Application Layer

- R16-CMP-01: The Composer receives each `selected` answer with its frozen source, selectable constituents, trigger, and tokens.
- R16-CMP-02: The Composer receives the empty entity-reference tuple used by the R12 diagnostic.
- R16-CMP-03: The Application Layer records exactly one `DecontextualizedProposition` for each selected answer.
- R16-CMP-04: The Application Layer records no composition result for rejected, abstained, blocked, or failed answers.

### Evidence and operation: Pipeline

- R16-EV-01: The Pipeline writes typed Archive records for preparation, attempt status, execution items, and the sealed report.
- R16-EV-02: The Pipeline persists each terminal execution item before starting the next Event.
- R16-EV-03: The Pipeline records zero accepted Ledger changes and zero ProposedChanges.
- R16-EV-04: The Pipeline provides bounded read-only `show` and `artifacts` commands that validate record references and digests.
- R16-EV-05: The Pipeline exposes exact questions and completed answers only through an explicit `trace` command.
- R16-EV-06: The agent hands live execution to the operator under [Long-Running Operations](agent/long-running-operations.md).

## 4. Proposed Architecture

The Pipeline owns preparation, command routing, and the operator handoff.
The Application Layer owns admission, attempt transitions, strict parsing, composition requests, and report validation.
The existing LM Studio Adapter owns model inspection and transport.
The operator starts and monitors the command under R16-EV-06.
The runner executes model requests through that Adapter and records the responses automatically.
The existing Composer owns proposition construction and hold reasons.
The Archive stores validated experiment records without changing accepted knowledge.

```text
+----------+     +----------+     +-------------------+
| Operator | --> | Pipeline | --> | Application Layer |
+----------+     +----------+     +-------------------+
                      |             |             |
                      v             v             v
                 +---------+  +-----------+  +----------+
                 | Archive |  | LM Studio |  | Composer |
                 +---------+  | Adapter   |  +----------+
                              +-----------+
```

The Adapter implements the Application Layer's existing `ModelTaskRuntime` Port.
R16 requires no Domain Core or production extraction changes.

## 5. Key Interactions

```text
Operator       Pipeline        Application Layer       Runtime       Archive
   | prepare      |                    |                   |            |
   |------------->| validate and bind  |                   |            |
   |              |------------------->| write prepared records-------->|
   | execute      |                    |                   |            |
   |------------->| execute frozen set |                   |            |
   |              |------------------->| admit and call---->|            |
   |              |                    |<---response/error-|            |
   |              |                    | archive response-------------->|
   |              |                    | parse; compose selected answer |
   |              |                    | write terminal item----------->|
   |              |                    | [repeat for second Event]      |
   |              |                    | seal report------------------->|
   | show         |                    |                   |            |
   |------------->| read and validate evidence------------------------->|
   |<-------------| bounded status     |                   |            |
```

## 6. Data Model

Existing records include `CorrectiveSelectionTask`, `ConstituentSelectionTask`, and `ConstituentSelectionAnswer`.
Existing runtime records include `ModelInputAdmission`, `ModelExecutionSpec`, and `ModelExecutionReceipt`.
Existing composition records include `DecontextualizedProposition`.
R16 adds strict Application Layer DTOs for the following Archive records.

| Record | Required contents | Access |
|---|---|---|
| Preparation | Run identity, TDD digest, input references and digests, model configuration, two tasks | By Run root |
| Attempt | Run identity, Event ID, execution identity, admission, execution specification, status, error | By Run root and Event |
| Execution item | Attempt reference, response reference and digest, receipt, parsed answer, composition result | By Run root and Event |
| Report | Source fingerprints, ordered items, outcome counts, write counts, result fingerprint | By Run root |
| Status | Run identity, lifecycle state, terminal item count, model execution count, report reference | By Run root |

Attempt states are `prepared`, `running`, `answered`, `input_blocked`, and `runtime_failed`.
Run states are `prepared`, `running`, `complete`, and `failed`.
An answered item requires a raw response reference, its digest, a validated receipt, and a parsed answer.
An input-blocked item requires blocked admission and carries no receipt, answer, or composition result.
A runtime-failed item requires a typed error and carries no usable answer or composition result.
Each item uses its preparation record to resolve the corrected prompt and original Candidate list.
Every structured record rejects unknown fields and impossible combinations.

The Run root contains `preparation.json`, `tasks.json`, `status.json`, and `attempts/<event-id>.json`.
Completed responses use `responses/<event-id>.bin`.
Terminal items use `items/<event-id>.json`.
A terminal run contains `report.json` and a derived `review.md`.
The report fingerprint hashes canonical JSON results and evidence digests, excluding the fingerprint field.

## 7. APIs / Interfaces

The runner is `scripts/run_corrective_reselection_execution.py`.
The runner exposes `prepare`, `execute`, `report`, `show`, `artifacts`, and `trace`.

`prepare` requires `--config`, `--run-005-root`, `--r15-root`, and an empty `--run-root`.
`prepare` rejects any config that is not `lm_studio` + `qwen2.5-14b-instruct`.
`execute` requires `--config` and `--run-root` and uses the preparation's pinned configuration.
`execute` rejects any drift in adapter, endpoint, model, profile, output limit, context limit, or deadline.
`report` rebuilds the sealed report from terminal items without invoking the runtime.
`show` returns validated lifecycle state, outcome counts, and the report fingerprint as JSON.
`artifacts` returns validated evidence identities, paths, and digests as JSON.
`trace` requires `--run-root` and `--event-id` and returns the exact corrected question and completed answer.

The agent runs model-free preparation after implementation.
```bash
uv run python scripts/run_corrective_reselection_execution.py prepare \
  --r15-root data/r15-residual-selection-failure-closure-runs/run-001 \
  --run-005-root data/r6-calibrated-residual-ownership-runs/run-005 \
  --config docs/r6-calibrated-residual-ownership-run-config.toml \
  --run-root data/r16-corrective-reselection-execution-runs/run-001
```

The operator starts the live experiment.
```bash
uv run python scripts/run_corrective_reselection_execution.py execute \
  --run-root data/r16-corrective-reselection-execution-runs/run-001
```

The operator uses this deterministic completion probe.
```bash
uv run python scripts/run_corrective_reselection_execution.py show \
  --run-root data/r16-corrective-reselection-execution-runs/run-001
```

The agent uses this bounded evidence inspection command after the operator reports completion.
```bash
uv run python scripts/run_corrective_reselection_execution.py artifacts \
  --run-root data/r16-corrective-reselection-execution-runs/run-001
```

The agent uses this command to read one exact corrected question and its completed answer.
```bash
uv run python scripts/run_corrective_reselection_execution.py trace \
  --run-root data/r16-corrective-reselection-execution-runs/run-001 \
  --event-id AHE-022
```

All expected outputs reside beneath the specified Run root at the paths in Section 6.
The experiment succeeds operationally when both Events have validated terminal items and a sealed report.
The experiment resolves a residual only when its answer is selected and its composition status is `proposition`.

## 8. Behavior & Domain Rules

The Pipeline validates deterministic inputs before it calls the runtime under R16-IN-01 through R16-IN-08.
The Pipeline rejects execution of any Run root whose state is not `prepared`.
The Pipeline writes `running` before the first attempt starts.
The Application Layer continues to the second Event after a terminal blocked or failed first attempt.
The Pipeline marks a fully recorded run `failed` if either item is blocked or runtime-failed.
Otherwise, the Pipeline marks the run `complete`, including grammatical rejection, abstention, and composition hold.
The report counts calls to `run_model_task`, including calls that raise a runtime error.
Admission blocking contributes zero model executions.
A run with both admitted Events records exactly two model executions.
Temperature `0` and seed `17` do not guarantee identical responses across runtime versions, quantizations, or hardware.
The Pipeline rebuilds reports from archived responses rather than invoking the model again.

Under R16-ANS-02, `NONE` is a rejected label-only answer.
Under R16-ANS-04, `NONE` is a best-choice abstention that leaves the residual open.
Internal newlines, explanations, Markdown fences, lowercase labels, and mixed labels with `NONE` are rejected.
The existing permissive R3 answer parser cannot replace the R16 grammar check.
R16 preserves malformed answers under R16-RT-09 and performs no label repair or second question.

Under R16-CMP-01 through R16-CMP-04, selection and composition remain separate observations.
A hold preserves its typed reason and carries no composed content.
The empty entity-reference tuple can produce `subject_unavailable` even after a valid selection.
R16 records that limitation without inventing an Actor or Organization reference.
R16 computes no Gold score and makes no production routing or confidence-threshold change.

A process interruption leaves the run `running` with every previously persisted item intact.
Inspection reports that nonterminal state without inferring completion from elapsed time.
Another experiment requires a new Run root.
Deterministic evidence corruption halts inspection and report reconstruction.

## 9. Acceptance Criteria

- AC-IN: Negative fixtures prove each R16-IN requirement halts on its exact input failure before invocation.
- AC-RT: Fake-Port tests prove R16-RT-02 through R16-RT-09 and R16-RT-11.
  The tests include first-Event failure and second-Event execution.
- AC-ADAPTER: Existing LM Studio tests verify admission, receipt binding, and the R16-RT-10 deadline contract.
- AC-ANS: Route tests accept valid single and multiple labels, allowed whitespace, and best-choice `NONE`.
- AC-REJECT: Route tests reject every failure in R16-ANS-05 and the examples in Section 8.
- AC-CMP: Boundary fixtures prove R16-CMP-01 through R16-CMP-04 for proposition, hold, and absent composition.
- AC-EV: Pipeline tests prove evidence persistence, digest checks, bounded inspection, and R16-EV-03 write counts.
- AC-LIFECYCLE: Pipeline tests prove one execution per root, interrupted-run visibility, and deterministic report replay.
- AC-LIVE: The operator-run experiment records both observed answers and composition outcomes without requiring positive selections.
- AC-CHECKS: Implementation passes focused formatting, lint, typecheck, and Application Layer and Pipeline tests.

The implementer adds repeatable R16 checks to [CHECK_PLAN](CHECK_PLAN.md) when the runner and tests exist.
The agent runs focused deterministic checks directly.
The operator runs AC-LIVE under R16-EV-06.

## 10. Reference Implementations

- R15 tasks and report hashing: `packages/application/src/kotekomi_application/residual_selection_failure_closure.py`.
- Selection DTOs: `packages/application/src/kotekomi_application/parser_constituent_candidate_generation.py`.
- Composer: `packages/application/src/kotekomi_application/decontextualization_composition.py`.
- Frozen composition inputs: `scripts/run_label_mismatch_recovery.py`.
- Runtime Port and receipts: `packages/application/src/kotekomi_application/staged_model_extraction.py`.
- Runtime admission and execution: `scripts/run_calibrated_residual_ownership.py`.
- Local transport and deadline: `packages/adapters/src/kotekomi_adapters/lm_studio_model_runtime.py`.
- Runtime configuration: `docs/r6-calibrated-residual-ownership-run-config.toml`.
- Resolved output ceiling and deadline: `packages/pipelines/src/kotekomi_pipelines/config.py` (`ModelExecutionConfig`).

## 11. Constraints and Halt Conditions

The Pipeline halts preparation when the frozen experiment or R15 evidence fails validation.
The Application Layer records runtime identity drift through R16-RT-08.
Changing to llama-server or another model requires a separately named experiment.
R16 keeps the R3 parser, R4 Composer, R11 classifier, and R12 recovery unchanged.
R16 leaves production submission and the closed `AHE-004` arc outside this deliverable.

### Run record

R16 is implemented and accepted.

The deterministic fixture validation recorded these terminal outcomes.

| Event | Route | Answer | Parsed status | Composition | Outcome |
|---|---|---|---|---|---|
| `AHE-022` | `label_only_reselection` | all 35 Candidate labels | `selected` | `held` (`subject_unavailable`) | `selected_hold` |
| `AHE-051` | `best_choice_reselection` | `NONE` | `none` | — | `abstained` |

Report fingerprint: `c462bb5baa79e03164d07abe50b9d52e913affade5e032c24620b25d38c6ed53`.
Model executions: `2`. Canonical writes: `0`. Proposed changes: `0`.

`AHE-022` recovered the required answer format, but selecting every candidate does not establish
useful semantic selection. `AHE-022`'s composition hold reflects missing entity-resolution inputs
and does not measure selection quality. `AHE-051` abstained. Neither residual is closed by R16.
The live `AC-LIVE` experiment against LM Studio executed under R16-EV-06 and matched the deterministic
prediction exactly: `2` model executions (`AHE-022` → `selected_hold`, `AHE-051` → `abstained`),
zero canonical writes, zero ProposedChanges, and result fingerprint
`c462bb5baa79e03164d07abe50b9d52e913affade5e032c24620b25d38c6ed53`.
The agent selects the next deliverable [R17 Semantic Selection Contract](2026-10-07-semantic-selection-contract.md):
freeze one versioned semantic selection contract and its independent acceptance criteria.
Model discrimination and ranking experiments follow after the contract freezes.
