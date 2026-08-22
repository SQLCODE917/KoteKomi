# Superseded Result Tag

## Context & Problem

An abandoned task can have a published `kotekomi/tasks/<task-id>/result` tag.

A completed successor can later deliver the abandoned task patch to `main`.

The closure producer currently requires the `result` tag to contain the later superseded outcome.

The producer then blocks because the published abandoned tag is immutable.

**Glossary**

- A **historical result tag** is an existing `result` tag with `outcome = abandoned`.
- A **superseded result tag** is `kotekomi/tasks/<task-id>/superseded-result`.
- A **superseded task result** is canonical task-result evidence with `outcome = superseded`.

Primary end-to-end flow:

1. A completed successor proves that an abandoned task patch reached `main`.
2. The closure producer reads the historical result tag.
3. The closure producer retains the historical result tag.
4. The closure producer publishes a superseded result tag at the successor target.
5. The closure producer writes superseded task-result evidence that identifies both tags.
6. The workflow records the task as superseded.

## Goals

- Operators retain the original abandoned result.
- Operators can identify the later superseded outcome.
- The closure producer deletes the retained feature branch after both result records are published.

## Requirements

### Closure producer requirements

- SRT-01: The producer reads the existing `result` tag before it publishes a result tag.
- SRT-02: The producer retains a matching historical result tag with `outcome = abandoned`.
- SRT-03: The producer publishes `superseded-result` at the completed successor target after SRT-02.
- SRT-04: The superseded result tag uses the existing canonical supersession message.
- SRT-05: The producer keeps the existing `result` tag behavior when no historical result tag exists.
- SRT-06: A non-abandoned historical result tag blocks the closure before branch deletion.
- SRT-07: A conflicting superseded result tag blocks the closure before branch deletion.

### Evidence requirements

- SRE-01: Superseded task-result evidence identifies the published superseded result tag.
- SRE-02: Superseded task-result evidence identifies `historical_result_tag` only after SRT-02.
- SRE-03: The evidence catalog preserves existing task-result validation rules.

## Proposed Architecture

The closure producer owns result-tag selection and publication.

The evidence catalog owns the superseded task result.

```text
Closure producer -> origin result tags -> Evidence catalog -> Workflow
```

## Key Interactions

```text
Closure producer -> origin: read historical result tag
Closure producer -> origin: publish superseded result tag
Closure producer -> Evidence catalog: write superseded task result
Closure producer -> Git: remove feature branch
Workflow -> Run record: superseded status
```

## Data Model

Superseded task-result evidence adds optional `historical_result_tag`.

The field contains the retained `result` tag name.

The field is absent when the closure producer publishes `result` as the superseded result tag.

## APIs / Interfaces

The public `kotekomi-agent close-superseded-task` command retains its existing interface.

The command result identifies the published superseded result tag.

## Behavior & Domain Rules

The producer does not replace, delete, or retarget a historical result tag.

The producer publishes tags before it deletes a feature branch.

The producer uses non-force Git commands for every publication and deletion.

The producer records a failed closure without feature branch deletion when tag validation fails.

## Acceptance Criteria

- AC-SRT-01: Disposable Git tests prove a historical abandoned result tag remains unchanged.
- AC-SRT-02: Tests prove the producer publishes the required superseded result tag and handoff tag.
- AC-SRT-03: Tests prove task-result evidence identifies both tags after a historical abandonment.
- AC-SRT-04: Tests prove conflicting historical and superseded tags retain the feature branch.
- AC-SRE-01: Existing superseded task-result validation remains valid without a historical result tag.
- AC-SRE-02: Formatting, lint, type checks, Harness verification, and both CI gates pass.

## Reference Implementations

- Superseded closure: `packages/devtools/src/kotekomi_devtools/superseded_task_closure.py`.
- Result tags: `packages/devtools/src/kotekomi_devtools/feature_branch_promotion.py`.
- Closure contracts: `packages/devtools/tests/acceptance/test_superseded_task_closure_contract.py`.

## Constraints and Halt Conditions

The implementation must not modify a published tag.

The implementation must not create a second result tag for a completed task.
