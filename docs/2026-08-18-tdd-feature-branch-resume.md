# TDD Feature Branch Resume

## Context & Problem

An operator resumes an active Task Manifest V2 run by running `implement-tdd` again.

The implementation agent has already pushed one or more candidate commits to the feature branch.

The current workflow calls the feature branch producer on every resume.

The producer accepts a repeat only while feature refs equal the specification revision.

The workflow therefore blocks after a valid candidate commit advances the feature branch.

The **initial branch evidence** is the `feature_branch` record from feature branch creation.

The **resume** is a later `implement-tdd` command for the same active run.

Primary end-to-end flow:

1. The Harness creates and records the initial branch evidence.
2. The implementation agent pushes a candidate commit to the feature branch.
3. The operator runs `implement-tdd` for the active run.
4. The workflow validates the existing initial branch evidence.
5. The workflow reads the current run evidence and returns the next lifecycle action.

## Goals

- An operator can resume an active feature-branch run after a candidate commit.
- The Harness retains the initial branch evidence as the branch-origin proof.
- The workflow continues to block conflicting branch evidence.

## Requirements

### Workflow boundary

- WF-01: The workflow invokes the feature branch producer when `feature_branch` evidence is absent.
- WF-02: The workflow reuses one valid `feature_branch` evidence record during a resume.
- WF-03: The workflow does not invoke the feature branch producer while it reuses branch evidence.
- WF-04: The workflow returns the next lifecycle action after it reuses branch evidence.
- WF-05: The workflow blocks when `specification_revision` differs from specification evidence.
- WF-06: The workflow blocks when branch evidence has a name that differs from `feature/<task-id>`.

### Evidence boundary

- EB-01: Initial branch evidence remains the record of the local and remote refs at branch creation.
- EB-02: A candidate commit does not replace initial branch evidence.
- EB-03: Candidate commit validation remains the owner of remote feature-tip validation.

## Proposed Architecture

The implementation workflow owns the decision to create or reuse a feature branch.

The feature branch producer owns only initial branch creation.

The candidate commit producer owns validation of an advanced remote feature tip.

```text
Operator -> Implementation workflow -> Initial branch evidence
                    |                         |
                    | create when absent       | reuse when present
                    v                         v
             Feature branch producer    Current run evidence
```

## Key Interactions

```text
Operator -> Workflow: implement-tdd
Workflow -> Evidence catalog: read initial branch evidence
Workflow -> Workflow: validate branch and specification identity
Workflow -> Operator: return current lifecycle action
```

## Data Model

This TDD does not add a record type.

The workflow continues to read the existing `feature_branch` record at `git/feature-branch.json`.

The record continues to contain the branch name and the specification revision from branch creation.

## APIs / Interfaces

`kotekomi-agent implement-tdd <tdd-path>` retains its current command interface.

The result retains its current `feature_branch` field.

## Behavior & Domain Rules

The workflow creates the feature branch once for each active Task Manifest V2 run.

The workflow reuses initial branch evidence for every later resume of that run.

The workflow does not require the feature tip to equal the specification revision during a resume.

The candidate commit producer later requires the candidate commit to equal the remote feature tip.

## Acceptance Criteria

- AC-WF-01: Disposable Git tests prove the first workflow command creates branch evidence.
- AC-WF-02: Tests prove a resume succeeds after a candidate commit advances the remote branch.
- AC-WF-03: Tests prove the resumed workflow command returns the next candidate lifecycle action.
- AC-WF-04: Tests prove the resumed workflow command does not call the initial branch producer.
- AC-WF-05: Tests prove conflicting branch or specification evidence blocks a resume.

## Reference Implementations

- Workflow evidence reuse: follow `packages/devtools/src/kotekomi_devtools/tdd_workflow.py`.

- Branch topology: follow `packages/devtools/src/kotekomi_devtools/lifecycle_evidence.py`.

## Constraints and Halt Conditions

The implementation does not weaken initial branch creation validation.

The implementation does not validate candidate remote tips in the workflow.

The implementation halts if a resume requires a new branch record after a candidate commit.
