# TDD: Selection-Failure Slot Routing

- Status: Proposed
- Deliverable ID: `R11`
- Program: [Source-Grounded Attachment Agile Package](2026-10-01-source-grounded-attachment-agile-package.md)
- Parent: [Residual Composition-Hold Routing](2026-10-01-residual-composition-hold-routing.md)
- Depends on: [Calibrated Residual Ownership](2026-09-29-calibrated-residual-ownership.md), [Parser-Constituent Candidate Generation](2026-09-25-parser-constituent-candidate-generation.md)

## 1. Context & Problem

R10 names one selection-layer disposition per residual Event.

The frozen run-005 residual set holds three Events.

`AHE-004` carries the disposition `selection_rejected`.

`AHE-022` carries the disposition `selection_rejected`.

`AHE-051` carries the disposition `selection_abstained`.

No residual Event carries the disposition `composition_hold`.

Every residual Event fails at the selection layer.

The selection layer has one deterministic finite-answer parse.

The parse books every raw selection answer as `selected`, `none`, or `rejected`.

The parse names no rejection reason.

One raw answer can produce `rejected` for three disjoint reasons.

An empty raw answer produces `rejected`.

A raw answer with tokens but zero valid candidate labels produces `rejected`.

A raw answer with at least one valid candidate label and at least one foreign token produces `rejected`.

The three reasons name recoverability differently.

A label-mismatch answer keeps its valid candidate labels; the selection can recover them without a new model call.

An empty answer keeps no candidate label.

A no-label answer keeps no candidate label.

No deliverable names the exact rejection reason per residual Event.

R11 adds one selection-failure slot per residual Event, derived from the frozen raw selection answer.

R11 separates a recoverable label mismatch from an unrecoverable rejection.

### Terms

**Selection-failure slot** means one closed value that names the exact point where one selection answer failed to yield an accepted selection.

**Raw selection answer** means the untouched model-returned text over one Constituent Selection Task.

**Candidate label** means one `C1`-style label from the Constituent Selection Task.

**Rejection reason** means why the finite-answer parse rejected one raw selection answer.

**Label mismatch** means a raw selection answer that names at least one valid candidate label and at least one token that is not a valid candidate label.

**No-label rejection** means a raw selection answer that names zero valid candidate labels.

**Recoverable** means a label-mismatch rejection whose valid candidate labels the selection can recover without a new model call.

The terms Selection Score, Residual review, Selection Score threshold, Selectable candidate, and Event frame keep the meanings the Calibrated Residual Ownership TDD defines.

The terms Constituent Selection Task, Constituent Selection Answer, and candidate label keep the meanings the Parser-Constituent Candidate Generation TDD defines.

### Primary flow

1. The runner binds the frozen run-005 raw selection answers and Constituent Selection Tasks by Event, unchanged.

2. The Application Layer re-tokenizes each raw selection answer.

3. The Application Layer classifies each raw selection answer into one closed selection-failure slot.

4. The Application Layer marks a label-mismatch rejection recoverable.

5. The Application Layer marks an empty rejection and a no-label rejection not recoverable.

6. The Application Layer seals one report with zero canonical writes, zero ProposedChanges, and zero model executions.

## 2. Goals

- Operators observe one selection-failure slot per residual Event.

- Operators observe the slot derived only from the frozen raw answer and the Constituent Selection Task.

- Operators observe the slot agreeing with the frozen Constituent Selection Answer status.

- Operators observe `recoverable` true only for a label-mismatch rejection.

- Operators observe the report records zero canonical writes, zero ProposedChanges, and zero model executions.

## 3. Requirements

### Slot taxonomy

- R11-SLT-01: The Application Layer defines the closed selection-failure slots `selected`, `abstained`, `rejection_empty`, `rejection_no_valid_label`, and `rejection_label_mismatch`.

- R11-SLT-02: A raw answer whose tokens name only valid candidate labels maps to `selected`.

- R11-SLT-03: A raw answer whose single token is `NONE` maps to `abstained`.

- R11-SLT-04: A raw answer with zero tokens maps to `rejection_empty`.

- R11-SLT-05: A raw answer with tokens and zero valid candidate labels maps to `rejection_no_valid_label`.

- R11-SLT-06: A raw answer with at least one valid candidate label and at least one invalid token maps to `rejection_label_mismatch`.

### Recoverability

- R11-REC-01: The diagnosis marks `recoverable` true only for a `rejection_label_mismatch` slot.

- R11-REC-02: The diagnosis marks `recoverable` false for `selected`, `abstained`, `rejection_empty`, and `rejection_no_valid_label`.

### Alignment

- R11-ALN-01: The diagnosis slot agrees with the frozen Constituent Selection Answer status `selected`, `none`, or `rejected` without disagreement.

### Report

- R11-REP-01: The report records one diagnosis per residual Event, ordered and distinct.

- R11-REP-02: The report records zero canonical writes, zero ProposedChanges, and zero model executions.

- R11-REP-03: The report seals one fingerprint over the diagnosis set.

## 4. Proposed Architecture

```text
Raw selection answers --+
                        |
Constituent Selection --> Selection-failure classifier -> Diagnosis set
Tasks                   |                                    |
                        +-- Recoverability marker -----------+
                                                             v
                                                      Sealed report
```

The Application Layer owns the classifier, the recoverability marker, and the sealed report.

The finite-answer parser keeps its existing role: the diagnosis reads the frozen raw answer directly.

No Adapter, Pipeline, model runtime, or Domain Core change in this deliverable.

## 5. Key Interactions

```text
Runner -> Application Layer : classify one frozen raw selection answer
Application Layer -> Constituent Selection Task : read candidate labels
Application Layer -> Recoverability marker      : set one boolean
Application Layer -> Report                     : seal zero-write diagnosis set
```

## 6. Data Model

One selection-failure diagnosis carries an Event id, a raw-answer digest, one closed slot, and one recoverable boolean.

The closed slot is one of `selected`, `abstained`, `rejection_empty`, `rejection_no_valid_label`, and `rejection_label_mismatch`.

The recoverable boolean is true only for `rejection_label_mismatch`.

The sealed report carries the ordered diagnosis set, three zero counters, and one fingerprint.

## 7. APIs / Interfaces

No public Application Layer port changes in this deliverable.

The new module exposes one slot classifier, one recoverability marker, and one report builder.

## 8. Behavior & Domain Rules

The diagnosis reads the frozen raw answer and the Constituent Selection Task; it re-invokes no model.

The diagnosis partitions the raw-answer tokens into valid candidate labels and invalid tokens.

The diagnosis dispatches every token partition explicitly.

The slot taxonomy covers every `selected`, `none`, and `rejected` status the parser books.

The Application Layer writes zero canonical state and zero ProposedChanges.

## 9. Acceptance Criteria

- AC-R11-SEL: Tests prove an all-valid-token raw answer maps to `selected`.

- AC-R11-ABS: Tests prove a `NONE` raw answer maps to `abstained`.

- AC-R11-EMP: Tests prove an empty raw answer maps to `rejection_empty`.

- AC-R11-NOLBL: Tests prove a zero-valid-label raw answer maps to `rejection_no_valid_label`.

- AC-R11-MISMATCH: Tests prove a mixed valid-and-invalid raw answer maps to `rejection_label_mismatch`.

- AC-R11-REC-01: Tests prove `recoverable` is true only for `rejection_label_mismatch`.

- AC-R11-REC-02: Tests prove `recoverable` is false for `selected`, `abstained`, `rejection_empty`, and `rejection_no_valid_label`.

- AC-R11-ALN: Tests prove the diagnosis slot agrees with the frozen Constituent Selection Answer status.

- AC-R11-SET: Tests prove the diagnosis set equals the residual-review set with no drift, ordered and distinct.

- AC-R11-REP-01: Tests prove the report records zero canonical writes, zero ProposedChanges, and zero model executions.

- AC-R11-REP-02: Tests prove the report fingerprint changes when one diagnosis changes.

- AC-R11-ALL: Focused formatting, lint, typecheck, and tests pass.

## 10. Reference Implementations

- Selection routing records: `packages/application/src/kotekomi_application/calibrated_residual_ownership.py` (`SelectionRouting`, `ResidualReviewReason`, `ResidualReviewSet`).

- Selection task and answer: `packages/application/src/kotekomi_application/parser_constituent_candidate_generation.py` (`ConstituentSelectionTask`, `ConstituentSelectionAnswer`, `ConstituentSelectionStatus`).

- Finite-answer parse: `packages/application/src/kotekomi_application/parser_constituent_candidate_generation.py` (`parse_constituent_selection_answer_labels`).

- Raw answer and task sources: `data/r6-calibrated-residual-ownership-runs/run-005/answers.jsonl`, `data/r6-calibrated-residual-ownership-runs/run-005/tasks.json`.

- New module: `packages/application/src/kotekomi_application/selection_failure_slot_routing.py`.

- Tests: `packages/application/tests/test_selection_failure_slot_routing.py`.

- Runner: `scripts/run_selection_failure_slot_routing.py`.

## 11. Constraints and Halt Conditions

- Do not change the R3 parser, the R6 router, or the R7 scorer.

- Do not re-invoke the model; R11 reads frozen run-005 answers only.

- Do not relabel the residual-review set or its Event ids.

- Stop when a diagnosis disagrees with the frozen Constituent Selection Answer status.

- Stop when `recoverable` is true for a non-label-mismatch slot.

- Stop when the report records any canonical write, ProposedChange, or model execution.

## 12. Execution & Experimentation Directive

- Implement and test this TDD.

- Run the slot classifier over the frozen run-005 residual answers and record the three slots.

- Record the actual `AHE-004`, `AHE-022`, and `AHE-051` slots in the Run Record.

- Decide the next logical step from the observed slots.

- Commit between the TDD, the implementation, and the run.

## 13. Run Record

R11 records the frozen run-005 residual selection answers once.

The run root and the sealed fingerprints are recorded after the run.

The observed selection-failure slots are recorded after the run.