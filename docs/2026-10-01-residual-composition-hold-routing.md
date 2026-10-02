# TDD: Residual Composition-Hold Routing

- Status: Accepted
- Deliverable ID: `R10`
- Program: [Source-Grounded Attachment Agile Package](2026-10-01-source-grounded-attachment-agile-package.md)
- Parent: [Selectable-Pool Floor](2026-09-30-selectable-pool-floor.md)
- Depends on: [Calibrated Residual Ownership](2026-09-29-calibrated-residual-ownership.md), [Decontextualization Composition](2026-09-28-decontextualization-composition.md)

## 1. Context & Problem

run-005 leaves three Events in residual review.

`AHE-004` carries the routing reason `rejected`.

`AHE-022` carries the routing reason `rejected`.

`AHE-051` carries the routing reason `composition_hold`.

The routing reason `composition_hold` names only the `NONE` answer.

The same Event name does not say whether the selection failed or the composer held.

The two `rejected` Events fail at the selection layer.

`AHE-051` abstains at the selection layer with `NONE`.

No residual Event has yet reached the composer.

No deliverable names the exact missing slot for a residual Event.

No deliverable enforces the rule that a hold never becomes accepted state.

R10 adds one deterministic disposition per residual Event.

R10 separates selection failure from composition hold.

R10 enforces held safety before any modeled residual experiment spends model budget.

### Terms

**Residual disposition** means one typed record that names one Event and one residual-disposition reason.

**Residual-disposition reason** means one value from the closed taxonomy this TDD defines.

**Selection failure** means the residual Event failed before the composer ran.

**Composition hold** means an accepted selection the deterministic composer cannot assemble.

**Held safety** means the invariant that a hold never becomes an accepted proposition.

**Exact missing slot** means one `DecontextualizationHoldReason` value that names what the composer could not resolve.

The terms Boundary gap, Event frame, Selection Score, Residual review, and Selection Score threshold keep the meanings the Calibrated Residual Ownership TDD defines.

The terms Content triple, Attribution, hold, and `DecontextualizationHoldReason` keep the meanings the Decontextualization Composition TDD defines.

### Primary flow

1. The runner binds the frozen selection routing, selection answers, and composition results by digest, unchanged.

2. The Application Layer maps each residual Event to one residual disposition.

3. The mapping renames the routing reason `composition_hold` to `selection_abstained`.

4. The mapping reserves `composition_hold` for an accepted selection the composer holds.

5. The composer result decides `composable` or `composition_hold` only when the selection is accepted.

6. The Application Layer validates held safety across the disposition set.

7. The Application Layer seals one report with zero canonical writes, zero ProposedChanges, and zero model executions.

## 2. Goals

- Operators observe one residual disposition per residual Event.

- Operators observe `selection_abstained` for `AHE-051`, never `composition_hold`.

- Operators observe one exact missing slot for a composition hold.

- Operators observe no hold promotes to accepted state.

## 3. Requirements

### Disposition taxonomy

- R10-DIS-01: The Application Layer defines the closed residual-disposition reasons `selection_rejected`, `selection_censored`, `selection_below_threshold`, `selection_abstained`, `composition_hold`, and `composable`.

- R10-DIS-02: A routing reason `rejected` maps to `selection_rejected`.

- R10-DIS-03: A routing reason `censored` maps to `selection_censored`.

- R10-DIS-04: A routing reason `below_threshold` maps to `selection_below_threshold`.

- R10-DIS-05: A routing reason `composition_hold` maps to `selection_abstained`.

- R10-DIS-06: An accepted selection with a `held` composition maps to `composition_hold` and carries one `DecontextualizationHoldReason`.

- R10-DIS-07: An accepted selection with a `proposition` status maps to `composable`.

### Held safety

- R10-SAF-01: A `selection_*` disposition carries no hold reason and no proposition.

- R10-SAF-02: A `composition_hold` disposition carries exactly one hold reason and no proposition.

- R10-SAF-03: A `composable` disposition requires a proposition whose status is `proposition`.

- R10-SAF-04: A `held` composition never yields a `composable` disposition.

- R10-SAF-05: The disposition set equals the residual-review set with no drift, ordered and distinct.

### Report

- R10-REP-01: The report records zero canonical writes, zero ProposedChanges, and zero model executions.

- R10-REP-02: The report seals one result fingerprint over the disposition set.

## 4. Proposed Architecture

```text
Selection routing --+
                     |
Selection answers --> Residual disposition mapping -> Residual dispositions
                     |                                    |
Composition results -+                                    v
                                                       Held-safety check
                                                            |
                                                            v
                                                     Sealed report
```

The Application Layer owns the disposition mapping, the held-safety check, and the sealed report.

The composer keeps its existing role: it produces the proposition or the held result.

No Adapter, Pipeline, model runtime, or Domain Core change in this deliverable.

## 5. Key Interactions

```text
Runner -> Application Layer : dispose one residual Event
Application Layer -> Routing record  : read decision and reason
Application Layer -> Composition     : read proposition or held result
Application Layer -> Held-safety     : reject promotion or drift
Application Layer -> Report          : seal zero-write disposition set
```

## 6. Data Model

One residual disposition carries an Event id, one residual-disposition reason, an optional `DecontextualizationHoldReason`, and an optional proposition.

The optional hold reason appears only on a `composition_hold` disposition.

The optional proposition appears only on a `composable` disposition.

The sealed report carries the ordered disposition set, the residual-review Event ids, three zero counters, and one fingerprint.

## 7. APIs / Interfaces

No public Application Layer port changes in this deliverable.

The new module exposes one disposition mapping function, one held-safety check, and one report builder.

## 8. Behavior & Domain Rules

A routing reason `composition_hold` means the model answered `NONE`.

R10 names that answer `selection_abstained`, not a composition hold.

The name `composition_hold` names only an accepted selection the composer cannot assemble.

The disposition mapping dispatches every supported routing reason explicitly.

The mapping fails fast on an unsupported residual-review reason.

A held result stays held; no residual disposition fabricates a role.

The Application Layer writes zero canonical state and zero ProposedChanges.

## 9. Acceptance Criteria

- AC-R10-SEL-REJ: Tests prove a `rejected` routing maps to `selection_rejected` with no hold reason and no proposition.

- AC-R10-SEL-CEN: Tests prove a `censored` routing maps to `selection_censored`.

- AC-R10-SEL-BTW: Tests prove a `below_threshold` routing maps to `selection_below_threshold`.

- AC-R10-SEL-ABS: Tests prove a `composition_hold` routing maps to `selection_abstained`.

- AC-R10-CMP-HOLD: Tests prove an accepted selection with a `held` composition maps to `composition_hold` with the exact `DecontextualizationHoldReason`.

- AC-R10-CMP-OK: Tests prove an accepted selection with a `proposition` composition maps to `composable` and carries the proposition.

- AC-R10-FAIL: Tests prove an unsupported residual-review reason raises a typed halt.

- AC-R10-SAF-01: Tests prove a `selection_*` disposition carries zero hold reason and zero proposition.

- AC-R10-SAF-02: Tests prove a `composition_hold` disposition carries exactly one hold reason and zero proposition.

- AC-R10-SAF-03: Tests prove a `held` composition never yields `composable`.

- AC-R10-SAF-04: Tests prove the disposition set equals the residual-review set with no drift, ordered and distinct.

- AC-R10-REP-01: Tests prove the report records zero canonical writes, zero ProposedChanges, and zero model executions.

- AC-R10-REP-02: Tests prove the report fingerprint changes when one disposition changes.

- AC-R10-ALL: Focused formatting, lint, typecheck, and tests pass.

## 10. Reference Implementations

- Selection routing: `packages/application/src/kotekomi_application/calibrated_residual_ownership.py` (`route_selection_scores`, `SelectionRouting`, `ResidualReviewReason`, `SelectionRoutingDecision`).

- Composition records: `packages/application/src/kotekomi_application/decontextualization_composition.py` (`DecontextualizedProposition`, `DecontextualizationStatus`, `DecontextualizationHoldReason`).

- Selection answer: `packages/application/src/kotekomi_application/parser_constituent_candidate_generation.py` (`ConstituentSelectionAnswer`, `ConstituentSelectionStatus`).

- New module: `packages/application/src/kotekomi_application/residual_composition_hold_routing.py`.

- Tests: `packages/application/tests/test_residual_composition_hold_routing.py`.

## 11. Constraints and Halt Conditions

- Do not change the R4 composer, the R6 router, or the R7 scorer.

- Do not relabel the residual-review set or its Event ids.

- Stop when the disposition set drifts from the residual-review set.

- Stop when a held composition yields a `composable` disposition.

- Stop when the disposition mapping silently drops an unsupported routing reason.

- Stop when the report records any canonical write, ProposedChange, or model execution.

## 12. Execution & Experimentation Directive

- Implement and test this TDD.

- Run the disposition mapping over the frozen run-005 bindings and record the three dispositions.

- Record the actual `AHE-004`, `AHE-022`, and `AHE-051` dispositions in the Run Record.

- Decide the next logical step from the observed dispositions.

- Commit between the TDD, the implementation, and the run.

## 13. Run Record

R10 measured the frozen run-005 residual set once.

The run root is `data/r10-residual-composition-hold-routing-runs/run-001`.

The source report fingerprint is `61efb0e36d18549852a36752872e909b40bfd5ad73a505231ba0f5e6845ef671`.

The sealed result fingerprint is `72c56437075ffe6336cd0e6c90524a940034806236cc49a77169b8501a478a7b`.

The three observed dispositions are:

- `AHE-004`: `selection_rejected`.

- `AHE-022`: `selection_rejected`.

- `AHE-051`: `selection_abstained`.

No residual Event is a composition hold.

The disambiguation holds: `AHE-051` abstains at the selection layer, not at the composer.

The run records zero canonical writes, zero ProposedChanges, and zero model executions.