# Historical Evidence Validation

## Context & Problem

The Harness stores a SHA-256 digest for each run evidence record.
The evidence index stores task manifests with `path_scope: repo`.
The current validator reads each repository path from the current checkout.
An operator can correct a later task manifest without changing the historic specification commit.
That correction makes valid historic evidence appear invalid.
The superseded-task closure then blocks before it can prove the historic delivery.

**Specification revision** is the immutable Git commit recorded for one Harness run before implementation begins.
**Repository-scoped evidence** is an evidence record whose path scope is `repo`.

### Primary end-to-end flow

1. The Harness records a specification revision and a repository-scoped task manifest digest for a run.
2. A later mainline commit changes the same task manifest path.
3. An operator validates the historic run.
4. The evidence catalog reads the task manifest from the recorded specification revision.
5. The evidence catalog accepts the historic digest and the closure producer can evaluate delivery proof.

## Goals

- Operators can validate historic runs after later mainline changes modify their task-manifest paths.
- The Harness rejects a missing pinned revision, missing pinned path, or mismatching pinned bytes.
- Current runs retain deterministic evidence validation.

## Requirements

### Evidence catalog

- HE-01: The evidence catalog identifies the run specification revision from the indexed `specification_revision` record before it validates repository-scoped evidence.
- HE-02: The evidence catalog validates the specification-revision record from the state root before it trusts its revision value.
- HE-03: The evidence catalog reads every repository-scoped evidence path from the recorded specification revision.
- HE-04: The evidence catalog compares the bytes from the recorded specification revision with the indexed SHA-256 digest.
- HE-05: The evidence catalog fails with a deterministic evidence error when the specification revision is absent, unreadable, invalid, or unavailable in Git.
- HE-06: The evidence catalog fails with a deterministic evidence error when a repository-scoped path is absent from the specification revision or its digest differs.
- HE-07: The evidence catalog does not read repository-scoped evidence from the current checkout when it validates a run.

### Superseded closure

- SC-01: The superseded-task closure uses the evidence catalog validation result before it evaluates exact or contained delivery proof.
- SC-02: The closure preserves feature references when historical evidence validation fails.

## Proposed Architecture

The evidence catalog owns repository-scoped evidence validation.
The catalog reads state-scoped records from the state root.
The catalog reads repository-scoped records through Git at the pinned specification revision.
The closure producer continues to consume only validated evidence entries.

```text
Run evidence index
        |
        v
Evidence catalog ----> state record
        |
        v
Git specification revision ----> repository-scoped bytes
        |
        v
Validated entries ----> superseded closure
```

## Key Interactions

```text
Operator -> Closure producer: historic task and run
Closure producer -> Evidence catalog: validate entries
Evidence catalog -> State root: read specification revision
Evidence catalog -> Git: read pinned repository path
Evidence catalog -> Closure producer: validated entries or evidence error
Closure producer -> Git: prove delivery only after validation
```

## Data Model

The existing `specification_revision` evidence record remains the source of the pinned revision.
The existing evidence-index entry remains the source of path scope and SHA-256 digest.
This task adds no persistent record type.

## APIs / Interfaces

`validated_entries` retains its current public input and output contract.
The function changes its repository-scoped byte source from the current checkout to the pinned specification revision.

## Behavior & Domain Rules

The evidence catalog validates the specification-revision record before it reads its revision value.
The catalog validates all state-scoped evidence against the state root.
The catalog validates all repository-scoped evidence against the same specification revision.
The catalog reports one evidence error when Git cannot provide the pinned bytes.
The closure producer does not write a tag, result, cleanup record, or run-state change after an evidence error.

## Acceptance Criteria

- AC-HE-01: A catalog test proves a historic task manifest validates after the current checkout changes that manifest path.
- AC-HE-02: A catalog test proves a missing specification-revision record blocks repository-scoped evidence validation.
- AC-HE-03: A catalog test proves a missing path or mismatching bytes at the pinned revision blocks validation.
- AC-HE-04: A disposable-Git closure test proves a historic contained delivery can close after the current checkout changes its manifest path.
- AC-HE-05: The Harness regression checks pass through the generated verification plan.

## Reference Implementations

- Evidence index validation: `packages/devtools/src/kotekomi_devtools/evidence_catalog.py`.
- Superseded closure: `packages/devtools/src/kotekomi_devtools/superseded_task_closure.py`.
- Historical closure contracts: `packages/devtools/tests/acceptance/test_superseded_task_closure_contract.py`.

## Constraints and Halt Conditions

The implementation must not rewrite historic evidence indexes or manifest digests.
The implementation must not validate repository-scoped evidence from unpinned current-checkout bytes.
The implementation must not weaken SHA-256 validation.
