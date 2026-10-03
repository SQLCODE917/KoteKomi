# TDD: Residual Selection-Failure Closure

- Status: Accepted
- Deliverable ID: `R15`
- Program: [Source-Grounded Attachment Agile Package](2026-10-01-source-grounded-attachment-agile-package.md)
- Parent: [Centralized Identity Resolution](2026-10-01-centralized-identity-resolution.md)
- Depends on: [Selection-Failure Slot Routing](2026-10-01-selection-failure-slot-routing.md), [Label-Mismatch Recovery](2026-10-01-label-mismatch-recovery.md), [Residual Composition-Hold Routing](2026-10-01-residual-composition-hold-routing.md)

## 1. Context & Problem

R11 names one selection-failure slot per residual Event.

R12 folds the one recoverable `rejection_label_mismatch` slot back into a completed selection.

R13 and R14 close the recovered `AHE-004` arc through reification and identity resolution.

Two residuals still carry a selection-failure slot with no automatic recovery.

`AHE-022` carries the slot `rejection_no_valid_label`.

`AHE-051` carries the slot `abstained`.

Both slots stay out of automatic recovery.

No deliverable names one closure route per unrecovered selection-failure slot.

R15 decides one closure route per residual Event.

The route is corrective re-selection, because the model is reserved for the residual cases the deterministic path cannot close.

The corrective instruction names how the model must answer the re-selection.

### Terms

**Residual selection-failure closure** means one deterministic step that decides one closure route per unrecovered selection failure.

**Closure route** means one value from the closed route set this TDD defines.

**Corrective re-selection** means one model-reserved re-selection task with a corrected instruction.

**Corrective instruction** means one closed instruction string that replaces the original selection instruction.

**Label-only re-selection** means one corrective re-selection that forbids candidate text and demands only candidate labels.

**Best-choice re-selection** means one corrective re-selection that demands exactly one candidate label or one exact `NONE`.

The terms Selection-failure slot, Raw selection answer, Recoverable, and Candidate label keep the meanings the Selection-Failure Slot Routing TDD defines.

The terms Constituent Selection Task, Constituent Selection Answer, label, and proposition keep the meanings the Parser-Constituent Candidate Generation and Decontextualization Composition TDDs define.

The terms Residual review and Residual disposition keep the meanings the Calibrated Residual Ownership and Residual Composition-Hold Routing TDDs define.

### Primary flow

1. The runner binds the frozen run-005 raw answers and Constituent Selection Tasks by Event, unchanged.

2. The Application Layer classifies each residual raw answer into one selection-failure slot.

3. The Application Layer maps each unrecovered slot to one closure route.

4. The Application Layer builds one corrective re-selection task per residual Event.

5. The Application Layer seals one report with zero canonical writes, zero ProposedChanges, and zero model executions.

The corrective re-selection itself runs in the next deliverable.

## 2. Goals

- Operators observe one closure route per unrecovered residual Event.

- Operators observe one corrective instruction per closure route.

- Operators observe `label_only` for `AHE-022`.

- Operators observe `best_choice` for `AHE-051`.

- Operators observe zero canonical writes, zero ProposedChanges, and zero model executions.

## 3. Requirements

### Closure route set

- R15-RTE-01: The Application Layer defines the closed closure routes `label_only_reselection` and `best_choice_reselection`.

- R15-RTE-02: The Application Layer maps `rejection_no_valid_label` to `label_only_reselection`.

- R15-RTE-03: The Application Layer maps `abstained` to `best_choice_reselection`.

- R15-RTE-04: The Application Layer halts on a recoverable or selected slot.

### Corrective instruction

- R15-INS-01: The Application Layer defines the closed corrective instructions `label_only` and `best_choice`.

- R15-INS-02: The `label_only` instruction demands only candidate labels and forbids candidate text.

- R15-INS-03: The `best_choice` instruction demands exactly one candidate label or one exact `NONE`.

- R15-INS-04: The corrective instruction replaces the original selection instruction and keeps the Event, Passage, and Candidates body unchanged.

- R15-INS-05: The corrective task carries a digest over the corrected prompt and a digest over the original rendered input.

### Report

- R15-REP-01: The Application Layer seals one report with the ordered residual set and zero canonical writes, zero ProposedChanges, and zero model executions.

## 4. Acceptance Criteria

- AC-R15-RTE-01: Tests prove `rejection_no_valid_label` maps to `label_only_reselection`.

- AC-R15-RTE-02: Tests prove `abstained` maps to `best_choice_reselection`.

- AC-R15-RTE-03: Tests prove a recoverable or selected slot raises a typed halt.

- AC-R15-INS-01: Tests prove the corrective instruction replaces only the first rendered input line.

- AC-R15-INS-02: Tests prove the corrected prompt digest matches the corrected prompt text.

- AC-R15-INS-03: Tests prove the corrective task keeps the original rendered input digest.

- AC-R15-ALN: Tests prove the closure set equals the residual set with no drift, ordered and distinct.

- AC-R15-REP-01: Tests prove the report records zero canonical writes, zero ProposedChanges, and zero model executions.

- AC-R15-REP-02: Tests prove the report fingerprint changes when one route changes.

- AC-R15-ALL: Focused formatting, lint, typecheck, and tests pass.

## 10. Reference Implementations

- Selection-failure classification: `packages/application/src/kotekomi_application/selection_failure_slot_routing.py` (`SelectionFailureSlot`, `classify_selection_failure`).

- Selection task: `packages/application/src/kotekomi_application/parser_constituent_candidate_generation.py` (`ConstituentSelectionTask`).

- Raw answer and task sources: `data/r6-calibrated-residual-ownership-runs/run-005/answers.jsonl`, `data/r6-calibrated-residual-ownership-runs/run-005/tasks.json`.

- New module: `packages/application/src/kotekomi_application/residual_selection_failure_closure.py`.

- Tests: `packages/application/tests/test_residual_selection_failure_closure.py`.

- Runner: `scripts/run_residual_selection_failure_closure.py`.

## 11. Constraints and Halt Conditions

- Do not change the R3 parser, the R4 composer, the R11 classifier, or the R12 recovery.

- Do not re-invoke the model; R15 prepares corrective re-selection tasks only.

- Do not read the held-out partition Gold.

- Do not turn a recoverable or selected slot into a closure route.

- Stop when a recoverable slot enters the closure routing.

- Stop when the closure set drifts from the residual set.

- Stop when the report records any canonical write, ProposedChange, or model execution.

## 12. Execution & Experimentation Directive

- Implement and test this TDD.

- Run the closure routing over the frozen run-005 residual answers and record the two routes.

- Record the actual `AHE-022` and `AHE-051` routes and corrective instructions in the Run Record.

- Decide the next logical step from the observed routes.

- Commit between the TDD, the implementation, and the run.

## 13. Run Record

R15 routes the frozen run-005 residual selection answers once.

Run root: `data/r15-residual-selection-failure-closure-runs/run-001`.

Source report fingerprint: `61efb0e36d18549852a36752872e909b40bfd5ad73a505231ba0f5e6845ef671`.

R15 report fingerprint: `7297d2d7b42c7d451c0f18705530f3973645700652d93e7bc571a4a96bded4d9`.

`AHE-004` stays out of the closure routing because R12 already recovered it.

| Event | Closure route | Corrective instruction |
|---|---|---|
| `AHE-022` | `label_only_reselection` | `label_only` |
| `AHE-051` | `best_choice_reselection` | `best_choice` |

The run records zero canonical writes, zero ProposedChanges, and zero model executions.