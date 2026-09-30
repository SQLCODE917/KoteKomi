# TDD: Source-Grounded Attachment Status-Field Reconciliation

- Status: Accepted
- Deliverable ID: `R-STAT`
- Program: [Source-Grounded Attachment Deterministic-First Package](2026-09-24-source-grounded-attachment-deterministic-first-package.md)
- Parent: [Competitive Event Attachment Program](2026-09-18-competitive-event-attachment-program.md)

## 1. Context & Problem

The Source-Grounded Attachment Deterministic-First Package catalogs deliverables R1 through R5.

Each deliverable header records one `Status` field.

The package does not define the difference between `Accepted` and `Proposed`.

R1 ships with an accept commit `8130d7f` that writes `Status: Accepted`.

R2 ships with an accept commit `3008c5b` that writes `Status: Accepted`.

R3 ships with an accept commit `6d55df9`.

Commit `6d55df9` is titled "Accept R3 parser-constituent candidate generation TDD and add task manifest".

Commit `6d55df9` creates the R3 document with `Status: Proposed`.

The R3 accept-commit title and the R3 status field disagree.

R3-A ships with an implementation commit `e69c9ff` and a `Status: Proposed` header.

R3-A has no accept commit and no task manifest.

The package Deliverables table lists only R1 through R5.

The package Deliverables table does not record that R3-A exists.

The package Deliverables table does not record that no `R3-B` deliverable exists.

A codebase search finds zero occurrences of the string `R3-B`.

The only `R3-C...` string in the package is the `R3-CST` acceptance-criteria prefix.

`R3-CST` names acceptance criteria, not a deliverable.

No deliverable named `R3-B` or `R3-C` exists.

The R3-A header records `Supersedes: candidate granularity of R3 requirements R3-CST-02 and R3-CST-03`.

This TDD reconciles the R3 and R3-A status fields and records the R3-A catalog entry.

### Terms

**Status field** means the `Status:` key-value pair in one deliverable or package header.

**Status vocabulary** means the set of allowed `Status:` values one package uses.

**Accept commit** means one commit that states "Accept" in its message and that adds a deliverable task manifest.

**Implementation commit** means one commit that adds deliverable code.

**Drift** means a Status field that disagrees with the commit history.

**Catalog entry** means one row or note in the package Deliverables section that records one deliverable.

**Accepted** means the design is accepted for implementation.

**Proposed** means the design is not yet accepted for implementation.

### Primary flow

1. The reconciler sets the R3 header Status field to `Accepted`.
2. The reconciler sets the R3-A header Status field to `Accepted`.
3. The reconciler adds an R3-A catalog entry and a no-R3-B note to the package Deliverables section.
4. The reconciler leaves the R1, R2, R4, and R5 headers unchanged.

## 2. Goals

- Each deliverable header states a Status that matches its commit history.
- The R3 header states `Accepted`.
- The R3-A header states `Accepted`.
- The package Deliverables section records that R3-A exists.
- The package Deliverables section records that R3-A supersedes `R3-CST-02` and `R3-CST-03`.
- The package Deliverables section records that no `R3-B` deliverable exists.
- The R1, R2, R4, and R5 headers keep their current Status values.

## 3. Requirements

### R3 document

The R3 document owns these requirements.

- R3-STAT-01: The R3 document records `Status: Accepted`.
- R3-STAT-02: The R3 document keeps `Deliverable ID: R3`.

### R3-A document

The R3-A document owns these requirements.

- R3A-STAT-01: The R3-A document records `Status: Accepted`.
- R3A-STAT-02: The R3-A document keeps the `Supersedes` field naming `R3-CST-02` and `R3-CST-03`.

### Package document

The package document owns these requirements.

- PKG-STAT-01: The package Deliverables section records one R3-A catalog entry.
- PKG-STAT-02: The package Deliverables section records that R3-A supersedes `R3-CST-02` and `R3-CST-03`.
- PKG-STAT-03: The package Deliverables section records that no `R3-B` deliverable exists.
- PKG-STAT-04: The package header keeps `Status: Proposed`.

### Unchanged documents

Each named document owns one requirement.

- UNCH-STAT-01: The R1 document keeps `Status: Accepted`.
- UNCH-STAT-02: The R2 document keeps `Status: Accepted`.
- UNCH-STAT-03: The R4 document keeps `Status: Proposed`.
- UNCH-STAT-04: The R5 document keeps `Status: Proposed`.

## 4. Proposed Architecture

```text
Source-Grounded Attachment Deterministic-First Package
      |
      +-- R1  (Status: Accepted)   -> keep
      +-- R2  (Status: Accepted)   -> keep
      +-- R3  (Status: Proposed)   -> flip to Accepted
      |        +-- R3-A (Status: Proposed) -> flip to Accepted
      +-- R4  (Status: Proposed)   -> keep
      +-- R5  (Status: Proposed)   -> keep
      |
      Deliverables table -> add R3-A entry + no-R3-B note
```

## 5. Key Interactions

```text
Reconciler -> R3 document      : set Status to Accepted
Reconciler -> R3-A document    : set Status to Accepted
Reconciler -> package document : add R3-A entry + no-R3-B note
Reconciler -> R1, R2, R4, R5   : no change
```

## 6. Data Model

The `Status:` field is one key-value pair in a deliverable or package header.

The Status vocabulary this TDD uses holds two values: `Accepted` and `Proposed`.

The catalog note is prose that follows the package Deliverables table.

## 7. APIs / Interfaces

This TDD changes documentation headers only.

This TDD changes no software interface and no record schema.

## 8. Behavior & Domain Rules

The reconciler flips a Status value only when the commit history proves the new value.

An accept commit plus a task manifest marks an Accepted deliverable.

R3 has an accept commit `6d55df9` and a task manifest, so R3 reconciles to `Accepted`.

R3-A lacks an accept commit and a task manifest.

R3-A implements and tests the R3 constituent-generation boundary.

R3-A supersedes the Accepted requirements `R3-CST-02` and `R3-CST-03`.

So R3-A reconciles to `Accepted` as an amendment of the Accepted R3.

R4 lacks an accept commit, so it keeps `Proposed`.

R5 lacks an accept commit and a passing held-out transfer gate, so it keeps `Proposed`.

The catalog note names the R3-A deliverable and names no other deliverable.

## 9. Acceptance Criteria

- AC-R3-STAT-01: The R3 header states `Status: Accepted`.
- AC-R3-STAT-02: The R3 header states `Deliverable ID: R3`.
- AC-R3A-STAT-01: The R3-A header states `Status: Accepted`.
- AC-R3A-STAT-02: The R3-A header `Supersedes` field names `R3-CST-02` and `R3-CST-03`.
- AC-PKG-STAT-01: The package Deliverables section states that R3-A exists.
- AC-PKG-STAT-02: The package Deliverables section states that R3-A supersedes `R3-CST-02` and `R3-CST-03`.
- AC-PKG-STAT-03: The package Deliverables section states that no `R3-B` deliverable exists.
- AC-PKG-STAT-04: The package header states `Status: Proposed`.
- AC-UNCH-STAT-01: The R1 and R2 headers state `Status: Accepted`.
- AC-UNCH-STAT-02: The R4 and R5 headers state `Status: Proposed`.
- AC-STAT-ALL: Focused spelling and link checks pass.

## 10. Reference Implementations

- Status alignment precedent: `git show cb7e383` flips D1/D2/D3 from `Planned` to `Accepted`.
- R3 accept commit and manifest: `git show 6d55df9` and `.agent/tasks/tdd-parser-constituent-candidate-generation-a1ce85452a56.toml`.
- R3-A implementation commit: `git show e69c9ff`.
- Package catalog to update: `docs/2026-09-24-source-grounded-attachment-deterministic-first-package.md`.
- Style guide: `docs/agent/documentation-style.md`.

## 11. Constraints and Halt Conditions

Do not rename any deliverable ID while reconciling a Status value.

Do not create an `R3-B` deliverable.

Do not change the R1, R2, R4, or R5 Status values in this change.

Do not change the package Status value in this change.

Stop when a supersession note would also rename an acceptance-criteria prefix.

Flag for a separate change any disagreement between the package Deliverables `Depends on` column and a deliverable header `Depends on` field.

Do not read the held-out DoD partition in this reconciliation.

This change reads no Gold and re-runs no evaluation.

All changes in this TDD are documentation-only.