# TDD: Eventive Statement Recognition and Single-Record Reification

- Status: Accepted
- Deliverable ID: `R13`
- Program: [Source-Grounded Attachment Agile Package](2026-10-01-source-grounded-attachment-agile-package.md)
- Parent: [Label-Mismatch Recovery](2026-10-01-label-mismatch-recovery.md)
- Depends on: [Decontextualization Composition](2026-09-28-decontextualization-composition.md), [Selection-Failure Slot Routing](2026-10-01-selection-failure-slot-routing.md)

## 1. Context & Problem

R12 recovers the frozen `AHE-004` selection to `{C1}`.

`{C1}` names the candidate `Efforts`.

R12 re-measures the recovered selection to `held` with reason `subject_unavailable`.

The deterministic composer holds because its `subject` slot accepts only an Actor or Organization entity reference.

The recovered `C1` names no published connection Gold entity in the held-out partition.

The `AHE-004` sentence is `Efforts to utilize artificial intelligence intensified under the term of Secretary Ash Carter`.

That sentence states one eventive activity, not one connection between two known entities.

The composer asymmetry is exact: `subject` requires an entity reference, while `object` can fall back to `object_value`.

No deliverable reifies an eventive subject into one Assertion record.

No deliverable keeps a vague statement so a later concrete article about the same activity can link to it.

No deliverable adds a closed shape vocabulary that routes every statement to one of a fixed set.

R13 recognizes one statement shape and then reifies it into one Assertion record.

R13 uses one Ledger consumer, so the pipeline count does not grow with the shape count.

R13 keeps the vague statement and lets a later concrete Assertion about the same activity link to it.

R13 deletes nothing; a successor supersedes, never deletes.

### Terms

**Shape vocabulary** means the closed set of statement shapes this TDD defines.

**Connection** means one statement whose subject and object both resolve to published entity references.

**Eventive state change** means one statement whose subject names an eventive activity and whose predicate states a change.

**Eventive activity** means a nominal activity or process the Source describes, for example `Efforts to utilize artificial intelligence`.

**Unknown shape** means one statement the recognizer cannot assign to any closed shape.

**Reify** means to turn one recognized statement into exactly one Assertion record.

**Keep and link** means to retain one accepted Assertion and to join a later Assertion about the same activity to it.

**Supersede, never delete** means a successor names a predecessor through `supersedes_assertion_id` and the predecessor keeps its original record.

The terms Composition hold, Held safety, `subject_unavailable`, Selection-failure slot, Re-measure, Recovered selection, Candidate label, Held-out partition, and `DecontextualizationHoldReason` keep the meanings the earlier TDDs define.

The terms Assertion, Relationship, ArgumentEdge, analytic inference, EventMention, EvidenceTarget, and ProvenanceActivity keep the meanings in `docs/agent/domain.md`.

### Primary flow

1. The runner binds the frozen `AHE-004` recovered selection and its re-measured result, unchanged.

2. The recognizer reads the statement and assigns one closed shape.

3. The recognizer assigns `eventive_state_change` for `AHE-004`.

4. The reifier turns the statement into exactly one Assertion record with a widened subject.

5. The reifier books an unknown shape into one typed hold, never a silent drop.

6. The keep-and-link contract retains the Assertion and joins a later Assertion about the same activity through a Relationship or an analytic inference.

7. The Application Layer seals one report with zero canonical writes, zero ProposedChanges, and zero model executions.

## 2. Goals

- Operators observe one closed shape per recognized statement.

- Operators observe one Assertion record per recognized statement, independent of shape.

- Operators observe the recognizer remains blind to the held-out partition Gold.

- Operators observe a superseded Assertion keeps its original record.

- Operators observe a later concrete Assertion about the same activity can link to the kept vague statement.

- Operators observe the report records zero canonical writes, zero ProposedChanges, and zero model executions.

## 3. Requirements

### Shape vocabulary

- R13-SHP-01: The Application Layer defines the closed shapes `connection`, `eventive_state_change`, and `unknown_shape`.

- R13-SHP-02: The recognizer assigns exactly one shape per statement.

- R13-SHP-03: The recognizer assigns `connection` when the statement subject and object both resolve to published entity references.

- R13-SHP-04: The recognizer assigns `eventive_state_change` when the statement subject names an eventive activity and the predicate states a change.

- R13-SHP-05: The recognizer assigns `unknown_shape` for every statement it cannot assign to `connection` or `eventive_state_change`.

### Reification

- R13-REF-01: The reifier turns each `connection` statement into one Assertion whose subject and object reference entities, with an object entity-or-value.

- R13-REF-02: The reifier turns each `eventive_state_change` statement into one Assertion whose subject references the eventive activity as an Event, EventMention, or entity.

- R13-REF-03: The reifier widens the subject slot to admit the eventive activity, never a fabricated Actor or Organization.

- R13-REF-04: The reifier preserves the source-exact subject, predicate, and object text.

- R13-REF-05: The reifier never invents an entity to satisfy a slot.

### Keep and link

- R13-KEEP-01: The reified Assertion remains an accepted Assertion; it is never dropped.

- R13-KEEP-02: A successor Assertion names one predecessor through `supersedes_assertion_id`.

- R13-KEEP-03: A superseded Assertion keeps its original record.

- R13-KEEP-04: The Application Layer joins a later Assertion about the same activity to the kept Assertion through a Relationship derived from the accepted Assertions, or through one analytic inference Assertion referencing both.

- R13-KEEP-05: The Application Layer never deletes an Assertion to supersede it.

### Hold

- R13-HLD-01: The reifier books an `unknown_shape` statement into one typed hold.

- R13-HLD-02: A held statement carries exactly one typed hold reason and zero composed content.

- R13-HLD-03: The reifier never coerces an unknown shape into a known shape.

### Centralization

- R13-CEN-01: The Application Layer centralizes identity resolution between a vague activity mention and a concrete mention in one step, not one step per shape.

### Report

- R13-REP-01: The report records one recognition plus one reification draft per statement, ordered and distinct.

- R13-REP-02: The report records zero canonical writes, zero ProposedChanges, and zero model executions.

- R13-REP-03: The report seals one fingerprint over the recognition-and-reification set.

## 4. Proposed Architecture

```text
Recovered statement ----+
                        |
Connection Gold        +--> Shape recognizer --> one closed shape
(development)          |        (exhaustive dispatch)
                        +--------------------> unknown shape -> typed hold
                                                       |
                                                       v
                        +------------------------------+
                        v
             Reifier (one Assertion per statement)
                        |
                        +--> connection Assertion (entity subject and object)
                        +--> eventive_state_change Assertion (eventive subject)
                        |
                        v
        Keep-and-link contract (Relationship / analytic inference / supersede)
                        |
                        v
             Sealed report (zero canonical writes)
```

The Application Layer owns the recognizer, the reifier, and the sealed report.

The shape vocabulary is closed; one dispatch handles every statement, so no per-shape pipeline exists.

The Domain Core owns the Assertion, Relationship, and analytic inference record shapes.

No Adapter, model runtime, or Pipeline change happens in this deliverable.

## 5. Key Interactions

```text
Runner -> Recognizer             : classify one recovered statement
Recognizer -> Shape vocabulary   : assign one closed shape
Recognizer -> Reifier            : hand one shape and one statement
Reifier -> Assertion record      : build one reification draft
Reifier -> Hold record           : book one unknown shape
Application Layer -> Keep-and-link contract : pin supersession and linking
Application Layer -> Report      : seal one zero-write report
```

## 6. Data Model

One recognition record carries an Event id, one statement, and one closed shape.

The closed shape is one of `connection`, `eventive_state_change`, and `unknown_shape`.

One reification draft carries one Assertion in a proposed shape.

A `connection` Assertion carries a subject entity reference and an object entity reference or value.

An `eventive_state_change` Assertion carries an eventive subject and an object entity-or-value.

The widened subject admits an Event, EventMention, or entity reference.

The keep-and-link contract reuses `supersedes_assertion_id`, `Relationship`, and the analytic inference Assertion record shape.

The sealed report carries the ordered recognition-and-reification set, three zero counters, and one fingerprint.

No new Domain Core record appears in this deliverable; the recognizer and reifier reuse existing record shapes.

This deliverable validates the keep-and-link rules with unit tests over record shapes; it writes no canonical state.

## 7. APIs / Interfaces

No public Application Layer port changes in this deliverable.

The new module exposes one shape recognizer, one reifier, and one report builder.

## 8. Behavior & Domain Rules

The recognizer reads the recovered statement only; it re-invokes no model.

The recognizer does not read the held-out partition Gold.

The shape dispatch is exhaustive; every statement lands in exactly one closed shape or one typed hold.

The reifier reifies each recognized statement into exactly one Assertion record, not one pipeline per shape.

The subject slot widens for the eventive activity only; the reifier never fabricates an Actor or Organization.

The keep-and-link contract supersedes; it never deletes.

A superseded Assertion keeps its original record.

No hold promotes to accepted content without a completed recognition and a completed reification.

## 9. Acceptance Criteria

- AC-R13-SHP-01: Tests prove the recognizer assigns `eventive_state_change` for the recovered `AHE-004` statement.

- AC-R13-SHP-02: Tests prove a two-entity statement assigns `connection`.

- AC-R13-SHP-03: Tests prove every statement lands in exactly one closed shape.

- AC-R13-SHP-04: Tests prove an unassignable statement books `unknown_shape` and a typed hold, never a silent drop.

- AC-R13-REF-01: Tests prove an `eventive_state_change` statement reifies to one Assertion whose subject is the eventive activity, not a fabricated Actor or Organization.

- AC-R13-REF-02: Tests prove a `connection` statement reifies to one Assertion with an entity subject and an object entity-or-value.

- AC-R13-REF-03: Tests prove one statement yields exactly one Assertion record, independent of shape.

- AC-R13-BLIND: Tests prove the recognizer never reads the held-out partition Gold.

- AC-R13-KEEP-01: Tests prove a superseded Assertion keeps its original record.

- AC-R13-KEEP-02: Tests prove a successor names a predecessor through `supersedes_assertion_id`.

- AC-R13-KEEP-03: Tests prove the keep-and-link contract joins a later Assertion about the same activity through a Relationship or an analytic inference Assertion, and never deletes the predecessor.

- AC-R13-CEN-01: Tests prove one identity-resolution step serves every shape.

- AC-R13-REP-01: Tests prove the report records zero canonical writes, zero ProposedChanges, and zero model executions.

- AC-R13-ALL: Focused formatting, lint, typecheck, and tests pass.

## 10. Reference Implementations

- Deterministic composer: `packages/application/src/kotekomi_application/decontextualization_composition.py` (`DecontextualizedProposition`, `DecontextualizationHoldReason`, subject role, object role).

- Recovered selection and re-measure: `packages/application/src/kotekomi_application/label_mismatch_recovery.py`.

- Selection-failure slots: `packages/application/src/kotekomi_application/selection_failure_slot_routing.py`.

- Assertion record shape and supersession rule: `packages/domain/src/kotekomi_domain/models.py` (`Assertion`, `AssertionType`, `EpistemicScope`, `supersedes_assertion_id`).

- Relationship and analytic inference: `packages/domain/src/kotekomi_domain/models.py` (`Relationship`, `AssertionType.ANALYTIC_INFERENCE`).

- Domain rules: `docs/agent/domain.md` ("A superseded Assertion keeps its original record.").

- New module: `packages/application/src/kotekomi_application/eventive_statement_recognition.py`.

- Tests: `packages/application/tests/test_eventive_statement_recognition.py`.

- Runner: `scripts/run_eventive_statement_recognition.py`.

## 11. Constraints and Halt Conditions

- Do not change the R3 parser, the R4 composer, the R11 classifier, or the R12 recovery.

- Do not re-invoke the model; R13 reads the recovered `AHE-004` statement only.

- Do not read the held-out partition Gold.

- Do not introduce one pipeline per shape.

- Stop when one statement yields more or fewer than one Assertion record.

- Stop when the reifier fabricates an Actor or Organization for the eventive subject.

- Stop when the recognizer silently drops or coerces an unknown shape.

- Stop when a superseded Assertion is deleted rather than retained.

- Stop when the report records any canonical write, ProposedChange, or model execution.

## 12. Execution & Experimentation Directive

- Implement and test this TDD.

- Run the recognizer over the frozen `AHE-004` recovered statement and record the assigned shape plus the reification draft.

- Record the actual `AHE-004` shape and reification draft in the Run Record.

- Validate the keep-and-link rules with unit tests against the `Assertion`, `Relationship`, and analytic inference record shapes.

- Decide the next logical step, including the centralized identity-resolution algorithm, from the observed result.

- Commit between the TDD, the implementation, and the run.

## 13. Run Record

R13 recognizes the recovered `AHE-004` statement and reifies it into one Assertion draft once.

Run root: `data/r13-eventive-statement-recognition-runs/run-001`.

Source R12 report fingerprint: `541e05e40dc2ceaed090b8b63470f8c1f93d3d52dd1845ac43ff729f679db9b2`.

The assigned shape is `eventive_state_change`. The reification draft carries an eventive subject (`event`, exact text `Efforts`, no reference), a predicate (`intensified`, lemma `intensify`), and an object value (`under the term of Secretary Ash Carter`). No Actor or Organization is fabricated.

R13 report fingerprint: `01ccab983dee3c68d2114efee9dd3eb1e70f1db50f3985e6ec58db7ffe0eba68`.

| Event | Assigned shape | Reification outcome |
|---|---|---|
| `AHE-004` | `eventive_state_change` | `assertion_draft` (`event` subject + object value) |