# Superseded Task Closure

- Status: Proposed
- Program: `tdd-harness`
- Deliverable ID: `TDD-SUPERSEDED-CLOSURE`

## Context & Problem

The Harness closes a normal feature task after the task branch reaches `main`.
The Harness can abandon an implementation run that does not reach `main`.
The Harness cannot close a task when a successor task carries its delivered patch after a scope discovery.
The original task then remains active even though its delivered work reached `main` through the successor.

**Glossary**

- A **superseded task** is a task whose successor delivered its handoff patch after a scope discovery.
- A **successor task** is a completed Harness task that carries a superseded task handoff patch.
- A **handoff commit** is the local commit on the superseded feature branch that the successor candidate carries.
- A **handoff tag** is the annotated tag that retains the handoff commit after branch deletion.

### Primary end-to-end flow

1. An operator names a superseded task run, a completed successor run, and a handoff commit.
2. The closure producer validates the successor result, successor cleanup, and the two Git histories.
3. The closure producer publishes a result tag at the successor target and a handoff tag at the handoff commit.
4. The closure producer deletes the superseded local and remote feature branches without force.
5. The evidence catalog records the superseded result and cleanup state.
6. The workflow marks the original run terminal and reports the scope discovery.

## Goals

- Operators can close a superseded task without creating false candidate or promotion evidence.
- The Harness retains a recoverable reference to a deleted handoff commit.
- Metrics identify scope-discovery supersession without reporting a misleading quality score.
- The Harness leaves a completed successor as the source of implementation and CI evidence.

## Requirements

### Closure producer requirements

- SC-01: `close-superseded-task` accepts task, run, successor task, successor run, and handoff commit identifiers.
- SC-02: The producer requires valid original task binding and manifest evidence.
- SC-03: The producer requires successor completed task-result evidence and complete cleanup evidence.
- SC-04: The producer requires the published successor result tag to match the successor task-result evidence.
- SC-05: The producer requires the successor target commit to be reachable from `origin/main`.
- SC-06: The producer requires `origin/feature/<task-id>` to be reachable from the successor target commit.
- SC-07: The producer requires the handoff commit to be reachable from local `feature/<task-id>`.
- SC-08: The producer requires the handoff commit stable patch ID to equal the successor candidate commit stable patch ID.
- SC-09: The producer creates no candidate, verification, candidate-CI, promotion, lifecycle, or main-CI evidence for the superseded task.

### Result and cleanup requirements

- RC-01: The producer publishes `kotekomi/tasks/<task-id>/result` as an annotated result tag at the successor target.
- RC-02: The result tag message records `outcome = superseded` and `supersession_reason = scope_discovery`.
- RC-03: The result tag message records successor task identity, successor run identity, successor result tag, successor target commit, handoff commit, and handoff patch ID.
- RC-04: The producer publishes `kotekomi/tasks/<task-id>/superseded-handoff` as an annotated handoff tag at the handoff commit.
- RC-05: The handoff tag message records the same supersession identity as the result tag message.
- RC-06: The producer pushes both tags without force before it deletes a feature branch.
- RC-07: A matching published tag makes a retry succeed.
- RC-08: A conflicting tag blocks branch deletion.
- RC-09: The producer deletes local and remote `feature/<task-id>` without force after tag publication.
- RC-10: The producer writes complete cleanup evidence only when neither feature reference remains.

### Evidence and workflow requirements

- EW-01: `task_result.outcome` accepts `superseded`.
- EW-02: Superseded task-result evidence records every field in RC-03 and the result tag digest.
- EW-03: The evidence catalog trusts every superseded task-result field.
- EW-04: The workflow reports terminal `superseded` when superseded task-result evidence and complete cleanup evidence exist.
- EW-05: The workflow stores run status `superseded` and terminal reason `superseded_by_successor`.
- EW-06: The workflow never resumes or creates a new run for a superseded task.
- EW-07: Metrics record status `superseded`, successor identity, and `scope_discovery_supersession_count = 1`.
- EW-08: Scorecards record status `superseded` and no implementation-quality score.

## Proposed Architecture

The closure producer owns Git validation, tag publication, and branch deletion.
The evidence catalog owns superseded task-result records.
The workflow owns terminal task state.
The metrics and scorecard collectors own reporting semantics.

```text
Operator -> Closure producer -> origin result and handoff tags
                  |                         |
                  v                         v
            Git validation             Branch deletion
                  |                         |
                  +------> Evidence catalog <------+
                                      |
                                      v
                         Workflow, metrics, and scorecard
```

## Key Interactions

```text
Operator -> Closure producer: original run, successor run, handoff commit
Closure producer -> Evidence catalog: validate original and successor evidence
Closure producer -> Git: validate main ancestry and patch equivalence
Closure producer -> origin: publish result and handoff tags
Closure producer -> Git: delete superseded feature branch
Closure producer -> Evidence catalog: write task result and cleanup
Workflow -> Run record: write superseded terminal status
```

## Data Model

The superseded result tag message uses this shape.

```text
schema_version: 1
task_id: string
implementation_run_id: string
outcome: superseded
supersession_reason: scope_discovery
successor_task_id: string
successor_run_id: string
successor_result_tag: string
successor_target_commit: full commit ID
handoff_commit: full commit ID
handoff_patch_id: SHA-1 patch ID
```

The superseded task-result record adds the fields after `tag_message_sha256` from the result tag message.

The handoff tag uses the result tag message shape and targets `handoff_commit`.

## APIs / Interfaces

```text
kotekomi-agent close-superseded-task
  --task-id <task-id>
  --run <implementation-run-id>
  --successor-task-id <task-id>
  --successor-run <implementation-run-id>
  --handoff-commit <commit>
  --state-root <state-root>
```

The command returns exit code `0` after complete cleanup evidence.
The command returns exit code `2` for invalid evidence, history, patch, tag, or cleanup state.

## Behavior & Domain Rules

The producer treats the successor task result as the only proof that implementation reached `main`.
The producer does not infer successor identity from TDD prose or commit messages.
The operator supplies successor identity through the command interface.
The producer records the fixed reason `scope_discovery`.
The producer performs all Git changes without force.
The producer retains task-result evidence when branch cleanup fails and records incomplete cleanup.

## Acceptance Criteria

- AC-SC-01: Disposable Git tests prove a valid completed successor closes a superseded task.
- AC-SC-02: Tests prove invalid successor evidence, changed main ancestry, missing feature branch, and patch mismatch block before publication.
- AC-RC-01: Tests prove result and handoff tags contain required canonical messages and targets.
- AC-RC-02: Tests prove matching retries succeed and tag conflicts retain feature branches.
- AC-RC-03: Tests prove successful closure deletes local and remote feature branches without force.
- AC-RC-04: Tests prove branch deletion failure records incomplete cleanup after tags and task-result evidence.
- AC-EW-01: Evidence catalog tests prove superseded result records validate and rebuild.
- AC-EW-02: Workflow tests prove superseded runs are terminal and cannot create replacement runs.
- AC-EW-03: Metrics and scorecard tests prove supersession remains visible without a quality score.

## Reference Implementations

- Completion and cleanup: `packages/devtools/src/kotekomi_devtools/feature_branch_promotion.py`.
- Historic closure: `packages/devtools/src/kotekomi_devtools/feature_branch_reconciliation.py`.
- Evidence records: `packages/devtools/src/kotekomi_devtools/evidence_catalog.py`.
- Workflow state: `packages/devtools/src/kotekomi_devtools/tdd_workflow.py`.

## Constraints and Halt Conditions

The implementation does not modify `origin/main`.
The implementation does not create missing historic lifecycle evidence.
The implementation does not delete a branch before both tags publish.
The implementation does not treat a matching commit message as patch equivalence.
