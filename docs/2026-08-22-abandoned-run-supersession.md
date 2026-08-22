# TDD Abandoned Run Supersession

## Context & Problem

An abandoned candidate run can later reach `main` through a completed successor task.

The Harness closure producer writes supersession evidence for that run.

The workflow currently refuses to change an abandoned run to `superseded`.

The run then reports an outcome that conflicts with its completed successor.

**Glossary**

- An **abandoned candidate run** has run status `abandoned` and no task-result evidence.
- **Supersession evidence** contains `task_result.outcome = superseded` and complete cleanup evidence.
- A **prior terminal state** is the status and terminal reason that the workflow replaces.

Primary end-to-end flow:

1. A completed successor delivers the abandoned candidate patch to `main`.
2. The closure producer writes supersession evidence and removes the old feature branch.
3. The workflow reads the canonical supersession evidence.
4. The workflow records `superseded` as the run status.
5. The run record retains its prior terminal state.

## Goals

- Operators see `superseded` when a completed successor delivers an abandoned candidate patch.
- The run record retains the earlier abandoned status and terminal reason.
- Ordinary abandoned runs remain terminal.

## Requirements

### Workflow requirements

- AWS-01: `mark_run_superseded` accepts an active, blocked, or abandoned run.
- AWS-02: The workflow changes an abandoned run only when canonical supersession evidence exists.
- AWS-03: The workflow requires `task_result.outcome = superseded` for an abandoned run.
- AWS-04: The workflow requires `cleanup.branch_cleanup_complete = true` for an abandoned run.
- AWS-05: The workflow leaves an abandoned run unchanged when AWS-03 or AWS-04 fails.
- AWS-06: The workflow writes `status = superseded` and `terminal_reason = superseded_by_successor`.
- AWS-07: The workflow writes `prior_status = abandoned` and the prior terminal reason before AWS-06.
- AWS-08: The workflow preserves existing active and blocked run behavior.

## Proposed Architecture

The closure producer owns supersession evidence.

The workflow owns the run status transition.

```text
Closure producer -> Evidence catalog -> Workflow -> Run record
```

## Key Interactions

```text
Operator -> Closure producer: close superseded task
Closure producer -> Evidence catalog: task result and cleanup
Workflow -> Evidence catalog: validate supersession evidence
Workflow -> Run record: superseded status and prior terminal state
```

## Data Model

The run record adds optional `prior_status` and `prior_terminal_reason` fields.

The workflow writes both fields only when it reclassifies an abandoned run.

The evidence catalog remains the authority for task-result and cleanup evidence.

## APIs / Interfaces

The public `kotekomi-agent implement-tdd` command retains its existing interface.

The command reports terminal `superseded` after the workflow validates supersession evidence.

## Behavior & Domain Rules

The workflow does not infer supersession from a commit message or a branch name.

The workflow reads only canonical task-result and cleanup records.

The workflow does not resume an abandoned run.

The workflow does not create a new run during this status transition.

## Acceptance Criteria

- AC-AWS-01: Tests prove a completed successor can reclassify an abandoned candidate run.
- AC-AWS-02: Tests prove the run record retains the prior abandoned status and terminal reason.
- AC-AWS-03: Tests prove missing, non-superseded, or incomplete evidence leaves an abandoned run unchanged.
- AC-AWS-04: Existing workflow tests prove active and blocked supersession behavior remains unchanged.
- AC-AWS-05: Formatting, lint, type checks, Harness verification, and both CI gates pass.

## Reference Implementations

- Terminal run status: `packages/devtools/src/kotekomi_devtools/tdd_workflow.py`.
- Supersession evidence: `packages/devtools/src/kotekomi_devtools/superseded_task_closure.py`.
- Workflow tests: `packages/devtools/tests/acceptance/test_tdd_workflow_contract.py`.

## Constraints and Halt Conditions

The implementation must not alter the closure producer or task-result schema.

The implementation must not reclassify a run without canonical supersession evidence.
