# TDD: Centralized Identity Resolution

- Status: Accepted
- Deliverable ID: `R14`
- Program: [Source-Grounded Attachment Agile Package](2026-10-01-source-grounded-attachment-agile-package.md)
- Parent: [Eventive Statement Recognition](2026-10-01-eventive-statement-recognition.md)
- Depends on: [Eventive Statement Recognition](2026-10-01-eventive-statement-recognition.md), [Label-Mismatch Recovery](2026-10-01-label-mismatch-recovery.md)

## 1. Context & Problem

R13 reifies the recovered `AHE-004` statement into one Assertion draft.

The draft subject is an eventive activity: `event`, exact text `Efforts`, no reference.

R13 keeps the vague Assertion and defers the link to a later concrete mention.

The R13 keep-and-link contract pins supersession and joining through a Relationship or an analytic inference.

No deliverable decides whether one vague activity mention and one concrete mention name the same activity.

No deliverable runs that decision through one step for every statement shape.

### Terms

**Vague mention** means one reified statement whose subject is an eventive activity with no reference.

**Concrete mention** means one reified statement whose subject resolves to a published entity reference.

**Identity resolution** means the one deterministic step that decides whether one vague mention and one concrete mention name the same activity.

**Identity key** means one closed deterministic condition that proves two mentions name the same activity.

**Explicit supersede** means one concrete Assertion names one vague Assertion through `supersedes_assertion_id`.

**Shared subject reference** means two mentions carry the same non-null subject reference.

The terms Keep and link, Supersede, never delete, Eventive activity, and Reify keep the meanings the Eventive Statement Recognition TDD defines.

The terms Assertion, Relationship, analytic inference, and ProvenanceActivity keep the meanings in `docs/agent/domain.md`.

### Primary flow

1. The runner binds one frozen `AHE-004` vague mention.

2. The runner binds one deterministic concrete-mention fixture that names the vague Assertion through `supersedes_assertion_id`.

3. The resolver reads the two mentions and selects one closed identity key.

4. The resolver selects `explicit_supersede` and resolves the pair.

5. The resolver returns one keep-and-link record: the concrete Assertion supersedes the vague Assertion, and the vague Assertion keeps its original record.

6. The resolver books one typed hold for a pair that matches no identity key.

7. The Application Layer seals one report with zero canonical writes, zero ProposedChanges, and zero model executions.

## 2. Goals

- Operators observe one closed identity key per resolved pair.

- Operators observe one keep-and-link record per resolved pair.

- Operators observe one step serves every statement shape.

- Operators observe a pair with no key books one typed hold, never a fabricated reference.

- Operators observe zero canonical writes, zero ProposedChanges, and zero model executions.

## 3. Requirements

### Identity keys

- R14-KEY-01: The Application Layer defines the closed identity keys `explicit_supersede`, `shared_subject_reference`, and `no_shared_identity_key`.

- R14-KEY-02: The resolver selects `explicit_supersede` when the concrete mention's `supersedes_assertion_id` equals the vague assertion id.

- R14-KEY-03: The resolver selects `shared_subject_reference` when both mentions carry the same non-null subject reference.

- R14-KEY-04: The resolver selects `no_shared_identity_key` for every pair that matches no other key.

### One-step centralization

- R14-CEN-01: One resolver handles every statement shape.

- R14-CEN-02: The resolver reads only the Assertion id, the subject reference, and the supersedes field, never the statement shape.

### Keep and link

- R14-KEEP-01: A resolved pair returns one keep-and-link record whose concrete Assertion supersedes the vague Assertion.

- R14-KEEP-02: The vague Assertion keeps its original record.

- R14-KEEP-03: The Application Layer never deletes an Assertion to supersede it.

### Hold

- R14-HLD-01: An unresolved pair books one typed hold with reason `no_shared_identity_key`.

- R14-HLD-02: The resolver never invents a subject reference to resolve a pair.

### Report

- R14-REP-01: The report records one resolution per pair, ordered and distinct.

- R14-REP-02: The report records zero canonical writes, zero ProposedChanges, and zero model executions.

- R14-REP-03: The report seals one fingerprint over the resolution set.

## 4. Proposed Architecture

```text
Vague mention ------------+
                          |
Concrete mention ---------+--> Identity resolver --> one identity key
                                 (exhaustive, shape-blind)        |
                                                                  v
                                          resolved -> keep-and-link record (supersede)
                                          unresolved -> typed hold (no_shared_identity_key)
```

The Application Layer owns the resolver and the sealed report.

One resolver handles every shape; no per-shape resolver exists.

The Domain Core owns the Assertion record shape and the `supersedes_assertion_id` rule.

No Adapter, model runtime, or Pipeline change happens in this deliverable.

## 5. Key Interactions

```text
Runner -> Resolver            : bind one vague and one concrete mention
Resolver -> Identity keys     : select one closed identity key
Resolver -> Keep-and-link     : build one supersede record on resolution
Resolver -> Hold record       : book one no_shared_identity_key hold
Application Layer -> Report   : seal one zero-write report
```

## 6. Data Model

One mention carries one Assertion id, one Event id, and one subject.

A subject carries a closed kind, an exact text, and an optional reference.

The closed identity keys are `explicit_supersede`, `shared_subject_reference`, and `no_shared_identity_key`.

One resolved pair carries one keep-and-link record with a successor and a predecessor Assertion id.

One unresolved pair carries one typed hold with reason `no_shared_identity_key`.

The sealed report carries the ordered resolution set, three zero counters, and one fingerprint.

No new Domain Core record appears in this deliverable; the resolver reuses the Assertion record shape and the `supersedes_assertion_id` rule.

This deliverable writes no canonical state.

## 7. APIs / Interfaces

No public Application Layer port changes in this deliverable.

The new module exposes one resolver, one mention converter, and one report builder.

## 8. Behavior & Domain Rules

The resolver reads the two mentions only; it re-invokes no model.

The resolver does not read the held-out partition Gold.

The identity-key dispatch is exhaustive; every pair selects exactly one key or one typed hold.

One resolver serves every statement shape.

The resolver never invents a subject reference.

A resolved pair supersedes; it never deletes.

A superseded Assertion keeps its original record.

## 9. Acceptance Criteria

- AC-R14-KEY-01: Tests prove `explicit_supersede` resolves a vague-to-concrete pair.

- AC-R14-KEY-02: Tests prove `shared_subject_reference` resolves a concrete-to-concrete pair.

- AC-R14-KEY-03: Tests prove a pair with no key books `no_shared_identity_key`.

- AC-R14-CEN-01: Tests prove one resolver serves every shape: an eventive-to-connection pair, a connection-to-connection pair, and an eventive-to-eventive pair all flow through `resolve_identity`.

- AC-R14-KEEP-01: Tests prove a resolved pair marks the concrete Assertion as successor and the vague Assertion as predecessor.

- AC-R14-KEEP-02: Tests prove a superseded Assertion keeps its original record.

- AC-R14-FAB-01: Tests prove the resolver never invents a subject reference to resolve a pair.

- AC-R14-REP-01: Tests prove the report records zero canonical writes, zero ProposedChanges, and zero model executions.

- AC-R14-ALL: Focused formatting, lint, typecheck, and tests pass.

## 10. Reference Implementations

- Eventive statement recognition: `packages/application/src/kotekomi_application/eventive_statement_recognition.py` (`ReificationDraft`, `ReificationSubject`, `ReificationSubjectKind`).

- Label-mismatch recovery: `packages/application/src/kotekomi_application/label_mismatch_recovery.py`.

- Assertion record shape and supersession rule: `packages/domain/src/kotekomi_domain/models.py` (`Assertion`, `supersedes_assertion_id`).

- Domain rules: `docs/agent/domain.md` ("A superseded Assertion keeps its original record.").

- New module: `packages/application/src/kotekomi_application/centralized_identity_resolution.py`.

- Tests: `packages/application/tests/test_centralized_identity_resolution.py`.

- Runner: `scripts/run_centralized_identity_resolution.py`.

## 11. Constraints and Halt Conditions

- Do not change the R3 parser, the R4 composer, the R11 classifier, the R12 recovery, or the R13 recognizer.

- Do not re-invoke the model; R14 resolves two mentions only.

- Do not read the held-out partition Gold.

- Do not introduce one resolver per shape.

- Stop when the resolver invents a subject reference to resolve a pair.

- Stop when a superseded Assertion is deleted rather than retained.

- Stop when the report records any canonical write, ProposedChange, or model execution.

## 12. Execution & Experimentation Directive

- Implement and test this TDD.

- Run the resolver over the frozen `AHE-004` vague mention and one deterministic concrete-mention fixture.

- Record the selected identity key, the resolution outcome, and the report fingerprint in the Run Record.

- Validate the keep-and-link rules with unit tests against the `Assertion` record shape.

- Decide the next logical step from the observed result.

- Commit between the TDD, the implementation, and the run.

## 13. Run Record

R14 resolves the frozen `AHE-004` vague mention against one deterministic concrete-mention fixture once.

Run root: `data/r14-centralized-identity-resolution-runs/run-001`.

The concrete-mention fixture is a labeled deterministic fixture, not model output and not a held-out read.

The vague mention carries Assertion id `ast_ahe004_vague_001`, Event id `AHE-004`, and an eventive subject (`event`, exact text `Efforts`, no reference).

The concrete mention carries Assertion id `ast_ahe004_concrete_001`, Event id `TGE-017`, an entity subject (`ent_ahe004_efforts_001`), and `supersedes_assertion_id = ast_ahe004_vague_001`.

The resolver selects `explicit_supersede` and resolves the pair.

The keep-and-link record names the concrete Assertion as successor and the vague Assertion as predecessor.

R14 writes no canonical state, records no ProposedChanges, and executes no model.

R14 report fingerprint: `ebed3e5dba45532536649f4768e6039be4388486121f0e12ed82557fc04e86c9`.

| Pair | Identity key | Outcome |
|---|---|---|
| `AHE-004` vague `ast_ahe004_vague_001` -> `TGE-017` concrete `ast_ahe004_concrete_001` | `explicit_supersede` | `resolved_same_activity` |