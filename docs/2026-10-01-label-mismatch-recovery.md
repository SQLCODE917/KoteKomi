# TDD: Label-Mismatch Recovery

- Status: Accepted
- Deliverable ID: `R12`
- Program: [Source-Grounded Attachment Agile Package](2026-10-01-source-grounded-attachment-agile-package.md)
- Parent: [Selection-Failure Slot Routing](2026-10-01-selection-failure-slot-routing.md)
- Depends on: [Residual Composition-Hold Routing](2026-10-01-residual-composition-hold-routing.md), [Decontextualization Composition](2026-09-28-decontextualization-composition.md)

## 1. Context & Problem

R11 names one selection-failure slot per residual Event.
R11 marks only `rejection_label_mismatch` recoverable.
`AHE-004` lands in `rejection_label_mismatch`.
`AHE-022` lands in `rejection_no_valid_label`.
`AHE-051` lands in `abstained`.
The frozen `AHE-004` raw answer names `C1` plus one foreign token `E2`.
The `AHE-004` Constituent Selection Task offers candidates `C1`, `C2`, and `C3`.
`C1` names the candidate `Efforts`.
`C2` names the candidate `under the term of Secretary Ash Carter`.
`C3` names the candidate `term`.
The frozen raw answer writes `E2` where `C2` belongs.
The frozen raw answer keeps `C1`.
The frozen `AHE-022` raw answer names zero valid candidate labels.
The frozen `AHE-051` raw answer names `NONE`.
Only `AHE-004` carries a recoverable label mismatch.
No deliverable folds a recoverable label-mismatch answer back into a completed selection.
R12 recovers the valid candidate labels from the `AHE-004` raw answer without a new model call.
R12 keeps `AHE-022` and `AHE-051` out of automatic recovery.

### Terms

**Label-mismatch recovery** means one deterministic rewrite of one `rejection_label_mismatch` raw answer into a completed selection that keeps its valid candidate labels and drops its foreign tokens.
**Completed selection** means one `ConstituentSelectionAnswer` with status `selected` and one or more ordered distinct label indexes.
**Foreign token** means one comma-separated raw-answer token that matches no candidate label.
**Valid candidate label** means one comma-separated raw-answer token that matches one candidate label exactly.
**Re-measure** means running one recovered selection through the deterministic composer to get one proposition or one hold.
The terms Selection-failure slot, Raw selection answer, Recoverable, and Candidate label keep the meanings the Selection-Failure Slot Routing TDD defines.
The terms Composition hold and Held safety keep the meanings the Residual Composition-Hold Routing TDD defines.
The terms Constituent Selection Task, Constituent Selection Answer, and proposition keep the meanings the Parser-Constituent Candidate Generation and Decontextualization Composition TDDs define.

### Primary flow

1. The runner binds the frozen `AHE-004` raw answer and Constituent Selection Task by Event, unchanged.

2. The Application Layer classifies the raw answer and confirms the slot `rejection_label_mismatch`.

3. The Application Layer drops the foreign tokens and keeps the valid candidate labels.

4. The Application Layer emits one completed selection with the kept labels.

5. The Application Layer re-measures the recovered selection through the deterministic composer.

6. The Application Layer records the result as one proposition or one hold.

7. The Application Layer seals one report with zero canonical writes, zero ProposedChanges, and zero model executions.

## 2. Goals

- Operators observe one completed selection per recoverable Event.

- Operators observe the recovery derives only from the frozen raw answer and the Constituent Selection Task.

- Operators observe the recovered selection keeps every valid candidate label and drops every foreign token.

- Operators observe `AHE-022` and `AHE-051` stay out of automatic recovery.

- Operators observe the recovered selection re-measures to exactly one proposition or one hold.

- Operators observe the report records zero canonical writes, zero ProposedChanges, and zero model executions.

## 3. Requirements

### Recovery

- R12-REC-01: The Application Layer defines one recovery function that turns one `rejection_label_mismatch` raw answer into one completed selection.

- R12-REC-02: The recovery keeps exactly the comma-separated tokens that match one candidate label.

- R12-REC-03: The recovery drops every comma-separated token that matches no candidate label.

- R12-REC-04: The recovery orders the kept labels by task label order and keeps them distinct.

- R12-REC-05: The recovery sets each label index to the one-based position of that label in the task `constituent_labels`.

- R12-REC-06: The recovery reads no free prose to guess the meaning of a foreign token.

### Gate

- R12-GATE-01: The recovery raises a typed halt for a `rejection_no_valid_label` raw answer.

- R12-GATE-02: The recovery raises a typed halt for an `abstained` raw answer.

- R12-GATE-03: The recovery raises a typed halt for a `rejection_empty` raw answer.

- R12-GATE-04: The recovery raises a typed halt for a `selected` raw answer.

### Re-measure

- R12-MEAS-01: The recovered selection re-measures through the deterministic composer to exactly one result.

- R12-MEAS-02: A recovery proposition carries one complete content triple, one polarity, one modality, and one attribution.

- R12-MEAS-03: A recovery hold carries one typed hold reason and zero composed content.

### Report

- R12-REP-01: The report records one recovery per recoverable Event, ordered and distinct.

- R12-REP-02: The report records zero canonical writes, zero ProposedChanges, and zero model executions.

- R12-REP-03: The report seals one fingerprint over the recovered selection and the re-measured result.

## 4. Proposed Architecture

```text
Frozen raw answer ----+
                      |
Constituent Selection +---> Label-mismatch recovery --> completed selection
Task                     |                                    |
                         +--- recovery gate (typed halt) -----+
                                                              v
                                                     Deterministic composer
                                                              v
                                                  proposition | hold
                                                              v
                                                       Sealed report
```

The Application Layer owns the recovery function, the recovery gate, and the sealed report.

The deterministic composer keeps its existing role and receives the recovered selection.

The R11 classifier keeps its existing role: the recovery confirms the slot before rewriting.

No Adapter, Pipeline, model runtime, or Domain Core change in this deliverable.

## 5. Key Interactions

```text
Runner -> Application Layer     : classify one frozen raw selection answer
Application Layer -> Recovery   : rewrite one recoverable raw answer
Recovery -> Deterministic composer : supply one recovered selection
Composer -> Report              : name one proposition or one hold
Application Layer -> Report     : seal one zero-write recovery set
```

## 6. Data Model

One recovery record carries an Event id, one completed selection, and one re-measured result.
The completed selection reuses `ConstituentSelectionAnswer` with status `selected`.
The re-measured result reuses `DecontextualizedProposition` with status `proposition` or `held`.
The sealed report carries the ordered recovery set, three zero counters, and one fingerprint.

## 7. APIs / Interfaces

No public Application Layer port changes in this deliverable.
The new module exposes one recovery function, one recovery gate, and one report builder.

## 8. Behavior & Domain Rules

The recovery rewrites only a `rejection_label_mismatch` raw answer.
The recovery mirrors the R3 parser tokenization: it splits on the comma, strips, and drops empty tokens.
The recovery drops the `E2` token from `AHE-004` and keeps `C1`.
The recovery writes zero canonical state and zero ProposedChanges.
The recovery invokes no model.
The two non-recoverable Events (`AHE-022`, `AHE-051`) never enter automatic recovery.

## 9. Acceptance Criteria

- AC-R12-REC-01: Tests prove the frozen `AHE-004` answer recovers to a completed selection with exactly label index `1`.

- AC-R12-REC-02: Tests prove recovery keeps each valid candidate label and drops each foreign token.

- AC-R12-REC-03: Tests prove recovery orders kept labels by task label order, distinct.

- AC-R12-GATE-01: Tests prove recovery raises a typed halt for `rejection_no_valid_label`.

- AC-R12-GATE-02: Tests prove recovery raises a typed halt for `abstained`.

- AC-R12-GATE-03: Tests prove recovery raises a typed halt for `rejection_empty`.

- AC-R12-GATE-04: Tests prove recovery raises a typed halt for `selected`.

- AC-R12-MEAS-01: Tests prove the recovered `AHE-004` selection re-measures to one `DecontextualizedProposition`.

- AC-R12-MEAS-02: Tests prove the re-measured result is exactly a `proposition` or exactly a `held` result.

- AC-R12-MEAS-03: Tests prove a recovery hold carries one typed hold reason and zero composed content.

- AC-R12-REP-01: Tests prove the report records zero canonical writes, zero ProposedChanges, and zero model executions.

- AC-R12-REP-02: Tests prove the report fingerprint changes when the recovered selection changes.

- AC-R12-NONREC: Tests prove the recovery never turns `AHE-022` or `AHE-051` into a completed selection.

- AC-R12-ALL: Focused formatting, lint, typecheck, and tests pass.

## 10. Reference Implementations

- Selection-failure classification: `packages/application/src/kotekomi_application/selection_failure_slot_routing.py` (`classify_selection_failure`, `SelectionFailureSlot`, `selection_failure_recoverable`).

- Selection task and answer: `packages/application/src/kotekomi_application/parser_constituent_candidate_generation.py` (`ConstituentSelectionTask`, `ConstituentSelectionAnswer`, `ConstituentSelectionStatus`, `parse_constituent_selection_answer_labels`).

- Deterministic composer: `packages/application/src/kotekomi_application/decontextualization_composition.py` (`build_decontextualized_proposition`, `DecontextualizedProposition`, `DecontextualizationHoldReason`).

- Raw answer and task sources: `data/r6-calibrated-residual-ownership-runs/run-005/answers.jsonl`, `data/r6-calibrated-residual-ownership-runs/run-005/tasks.json`.

- Composer inputs: `data/r6-calibrated-residual-ownership-runs/run-005/inventories.json`, `data/r6-calibrated-residual-ownership-runs/run-005/tokens.json`, `data/r6-calibrated-residual-ownership-runs/run-005/frames.json`.

- New module: `packages/application/src/kotekomi_application/label_mismatch_recovery.py`.

- Tests: `packages/application/tests/test_label_mismatch_recovery.py`.

- Runner: `scripts/run_label_mismatch_recovery.py`.

## 11. Constraints and Halt Conditions

- Do not change the R3 parser, the R4 composer, or the R11 classifier.

- Do not re-invoke the model; R12 reads the frozen `AHE-004` answer only.

- Do not read the raw answer's free prose to remap a foreign token.

- Stop when the recovery keeps a foreign token or drops a valid candidate label.

- Stop when a non-recoverable Event enters automatic recovery.

- Stop when the report records any canonical write, ProposedChange, or model execution.

## 12. Execution & Experimentation Directive

- Implement and test this TDD.

- Run the recovery over the frozen `AHE-004` answer and record the recovered selection plus its re-measured result.

- Record the actual `AHE-004` recovered selection and re-measured result in the Run Record.

- Confirm `AHE-022` and `AHE-051` stay out of automatic recovery.

- Decide the next logical step from the observed result.

- Commit between the TDD, the implementation, and the run.

## 13. Run Record

R12 recovers the frozen `AHE-004` label-mismatch answer once.

Run root: `data/r12-label-mismatch-recovery-runs/run-001`.

Source report fingerprint: `61efb0e36d18549852a36752872e909b40bfd5ad73a505231ba0f5e6845ef671`.

The recovered selection is `{C1}` (label index 1). The re-measured result is `held` with reason `subject_unavailable`.

R12 report fingerprint: `541e05e40dc2ceaed090b8b63470f8c1f93d3d52dd1845ac43ff729f679db9b2`.

| Event | Recovered selection | Re-measured result |
|---|---|---|
| `AHE-004` | `{C1}` (index 1) | `held` (`subject_unavailable`) |

`AHE-022` and `AHE-051` stay out of automatic recovery.

The run records zero canonical writes, zero ProposedChanges, and zero model executions.

The label mismatch closes, but the re-measurement exposes one composition hold, which becomes the next step.