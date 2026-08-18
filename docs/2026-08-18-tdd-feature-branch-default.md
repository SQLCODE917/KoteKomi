# TDD Feature Branch Default

## Context & Problem

The Harness records a candidate commit from the current Git branch.

The Harness does not create a task branch.

The Harness does not persist the `main` revision from which a task starts.

An implementation agent can therefore work on `main` without a branch contract.

This TDD makes the Git feature branch flow the only active Harness flow.

The **Harness** is the repository-local tool that records TDD implementation evidence.

The **Task Manifest** is the TOML record that declares one Harness task.

The **planning authority** is the operator that commits a Task Manifest to `main`.

The **specification revision** is the `main` commit that starts one implementation run.

The **feature branch** is the Git branch `feature/<task-id>`.

The **candidate commit** is the Git commit that the implementation agent proposes for promotion.

The **feature flow** creates the feature branch from the specification revision.

Task Manifest V1 and direct-main evidence are read-only historical records.

Task Manifest V2 records each active Harness task.

Primary end-to-end flow:

1. The planning authority commits a Task Manifest V2 to `main`.
2. The planning authority runs `implement-tdd` from clean, current `main`.
3. The Harness records the current `main` commit as the specification revision.
4. The Harness creates and pushes `feature/<task-id>` from that revision.
5. The implementation agent commits and pushes candidate commit `C` to the feature branch.
6. The Harness accepts `C` only when it equals the remote feature tip.
7. The verifier appends receipt commit `R` to the feature branch after it checks `C`.
8. Candidate CI validates `R`.
9. The promotion TDD merges `R` into `main` as merge commit `M`.
10. Main CI validates `M`, then the Harness pushes the task-result tag and deletes the feature branch.

## Goals

- Every active task has one feature branch.
- An implementation agent receives one stable branch name for one task.
- The Harness binds a feature branch to one persisted specification revision.
- The Harness rejects a candidate that is not the remote feature tip.
- Historical direct-main records remain available for reporting.

## Requirements

### Task Manifest boundary

- TM-01: The repository adds `.agent/schemas/task-manifest-v2.schema.json`.
- TM-02: Task Manifest V2 uses `schema_version = 2`.
- TM-03: Task Manifest V2 has the complete Task Manifest V1 field set.
- TM-04: Task Manifest V2 has no `delivery_mode` field.
- TM-05: The Task Manifest validator validates V1 with the V1 schema.
- TM-06: The Task Manifest validator validates V2 with the V2 schema.
- TM-07: The implementation workflow creates active runs only for Task Manifest V2.
- TM-08: The implementation workflow reports V1 as historical and read-only.
- TM-09: Metrics and scorecards retain access to V1 run evidence.

### Specification revision boundary

- SR-01: `implement-tdd` records specification evidence for each valid Task Manifest V2.
- SR-02: The command requires a clean worktree before it records specification evidence.
- SR-03: The command requires the local branch to be `main`.
- SR-04: The command requires `HEAD` to equal `origin/main`.
- SR-05: The command requires the current `HEAD` tree to contain the exact Task Manifest bytes.
- SR-06: The command records `HEAD` as the specification revision.
- SR-07: The canonical specification record path is `git/specification-revision.json`.
- SR-08: The specification evidence key uses phase `spec`.
- SR-09: The specification evidence key uses evidence type `specification_revision`.
- SR-10: The specification evidence key uses subject ID `specification`.
- SR-11: Specification evidence contains `schema_version`, `specification_revision`, and `manifest_sha256`.
- SR-12: Specification evidence contains `diagnostics`.
- SR-13: The evidence catalog trusts `specification_revision` and `manifest_sha256`.
- SR-14: A repeated `implement-tdd` command reuses valid specification evidence.
- SR-15: The command blocks on a specification-evidence conflict with the Task Manifest.
- SR-16: After it records or reuses valid specification evidence, `implement-tdd` invokes the feature branch producer.

### Feature branch boundary

- FB-01: `kotekomi-agent create-feature-branch MANIFEST` creates the feature branch.
- FB-02: The command validates the Task Manifest before it reads Git state.
- FB-03: The command requires Task Manifest V2.
- FB-04: The command reads valid specification evidence before it creates a branch.
- FB-05: The command derives the branch name as `feature/<task-id>`.
- FB-06: The command creates the local branch at the specification revision.
- FB-07: The command pushes the local branch to `origin` without force.
- FB-08: The command writes feature-branch evidence after local and remote branch creation pass.
- FB-09: The canonical feature-branch record path is `git/feature-branch.json`.
- FB-10: The evidence key uses phase `candidate`.
- FB-11: The evidence key uses evidence type `feature_branch`.
- FB-12: The evidence key uses subject ID `feature-branch`.
- FB-13: Feature-branch evidence contains `schema_version`, `branch`, and `specification_revision`.
- FB-14: Feature-branch evidence contains `local_revision`, `remote_revision`, and `diagnostics`.
- FB-15: The evidence catalog trusts `branch` and `specification_revision`.
- FB-16: A repeat command succeeds when both feature refs equal the recorded specification revision.
- FB-17: The command blocks when either feature ref resolves to another revision.
- FB-18: The command removes a newly created local branch when the initial remote push fails.

### Candidate commit boundary

- CC-01: `record-candidate-commit` reads valid feature-branch evidence.
- CC-02: The command resolves the remote feature branch before it writes candidate commit evidence.
- CC-03: The command requires the requested candidate commit to equal the remote feature tip.
- CC-04: The command requires the specification revision to strictly precede the candidate commit.
- CC-05: The command writes no candidate commit evidence when feature topology validation fails.

### Workflow boundary

- WF-01: The implementation workflow requires specification evidence in the `spec` phase.
- WF-02: The workflow reports `create_feature_branch` before candidate lifecycle evidence.
- WF-03: The workflow requires feature-branch evidence before candidate lifecycle evidence.
- WF-04: The workflow requires feature-branch evidence before candidate commit evidence.
- WF-05: The workflow blocks on a Task Manifest conflict in specification evidence.
- WF-06: The workflow blocks on a Task Manifest conflict in feature-branch evidence.
- WF-07: The workflow does not resume a direct-main run.
- WF-08: The workflow blocks an active run with a direct main promotion record.
- WF-09: The workflow delegates receipt, promotion, result-tag, and cleanup requirements to later TDDs.

### Command result boundary

- CR-01: The command returns exit code `0` after it records valid feature-branch evidence.
- CR-02: The command returns exit code `1` on a feature-ref conflict with the specification revision.
- CR-03: The command returns exit code `2` for an invalid manifest or specification record.
- CR-04: The command returns exit code `2` for missing `origin` or an unresolved revision.
- CR-05: The command returns exit code `2` after a failed remote push.
- CR-06: The command emits compact JSON with `status`, `schema_version`, and `task_id`.
- CR-07: The command emits compact JSON with `branch` and `specification_revision`.
- CR-08: The command emits compact JSON with `local_revision`, `remote_revision`, and `diagnostics`.
- CR-09: `implement-tdd` returns the derived feature branch after it creates or reuses it.

## Proposed Architecture

The Task Manifest validator owns manifest-version validation.

The implementation workflow owns specification evidence creation and readiness decisions.

The feature branch producer owns local and remote feature branch creation.

The lifecycle evidence producer owns candidate-to-feature topology validation.

The evidence catalog owns canonical record paths and trusted fields.

```text
Planning authority -> Implementation workflow -> Evidence catalog
                              |
                              v
                     Feature branch producer -> origin feature branch
                                                    |
                                                    v
                                  Implementation agent and `record-candidate-commit`
```

## Key Interactions

```text
Planning authority -> Workflow: start the implementation run
Workflow -> Evidence catalog: record the specification revision
Workflow -> Feature branch producer: create the feature branch
Feature branch producer -> origin: push the feature branch at the specification revision
Implementation agent -> origin: push the candidate commit
record-candidate-commit -> origin: resolve the remote feature tip
record-candidate-commit -> Evidence catalog: record the candidate commit
```

## Data Model

The Harness writes this specification record:

```text
schema_version: 1
specification_revision: full commit ID
manifest_sha256: SHA-256 digest
diagnostics: []
```

The Harness writes this feature-branch record:

```text
schema_version: 1
branch: feature/<task-id>
specification_revision: full commit ID
local_revision: full commit ID
remote_revision: full commit ID
diagnostics: []
```

## APIs / Interfaces

```text
kotekomi-agent create-feature-branch MANIFEST
  --task-id <task-id> --run <implementation-run-id>
  --state-root <state-root>
```

The command uses `origin` as the remote name.

The command derives the feature branch name and does not accept a branch-name override.

## Behavior & Domain Rules

The planning authority invokes `implement-tdd` from clean, current `main` before feature work.

The implementation workflow records the specification revision once for the run.

The feature branch producer uses the persisted specification revision on every retry.

The implementation workflow invokes the feature branch producer after it records specification evidence.

The feature branch producer does not switch the caller worktree.

The implementation agent pushes the candidate before it invokes `record-candidate-commit`.

The verifier receipt TDD appends passed and failed Verification Receipts to the feature branch.

The promotion TDD creates merge commit `M` with the current `main` tip and receipt commit `R` as parents.

The promotion TDD pushes the result tag and deletes the feature branch only after successful main CI.

## Acceptance Criteria

- AC-TM-01: Manifest tests prove V1 and V2 validate with their own schemas.
- AC-TM-02: Manifest tests prove V2 rejects `delivery_mode`.
- AC-TM-03: Workflow tests prove V1 runs are historical and read-only.
- AC-TM-04: Metrics tests prove V1 run evidence remains readable.
- AC-SR-01: Disposable Git repository tests prove `implement-tdd` records `main` as specification evidence.
- AC-SR-02: Tests prove dirty worktrees and non-main branches block specification evidence.
- AC-SR-03: Tests prove stale `main` and uncommitted manifests block specification evidence.
- AC-SR-04: Tests prove a repeat reuses matching specification evidence and blocks conflicting evidence.
- AC-SR-05: Tests prove `implement-tdd` creates or reuses the task feature branch after it records specification evidence.
- AC-FB-01: Disposable Git repository tests prove the command pushes the derived feature branch.
- AC-FB-02: Tests prove the remote feature branch starts at the specification revision.
- AC-FB-03: Tests prove the command records the derived branch as canonical evidence.
- AC-FB-04: Tests prove an idempotent repeat accepts matching local and remote refs.
- AC-FB-05: Tests prove mismatched feature refs block before feature-branch evidence exists.
- AC-FB-06: Tests prove a failed initial remote push removes the newly created local branch.
- AC-CC-01: Tests prove the command rejects a candidate that differs from the remote feature tip.
- AC-CC-02: Tests prove the command rejects a candidate that equals the specification revision.
- AC-CC-03: Tests prove the command rejects a candidate that precedes the specification revision.
- AC-EC-01: Evidence catalog tests prove specification and feature-branch paths and keys.
- AC-EC-02: Evidence catalog tests prove trusted fields and invalid-record rejection.
- AC-WF-01: Workflow tests prove specification evidence precedes candidate evidence.
- AC-WF-02: Workflow tests prove feature branch creation precedes candidate evidence.
- AC-WF-03: Workflow tests prove valid branch evidence advances to candidate lifecycle evidence.
- AC-WF-04: Workflow tests prove a direct main promotion record blocks an active run.

## Reference Implementations

- Task Manifest validation: follow `packages/devtools/src/kotekomi_devtools/task_manifest.py`.

- Canonical Git evidence: follow `packages/devtools/src/kotekomi_devtools/lifecycle_evidence.py`.

- Evidence indexing: follow `packages/devtools/src/kotekomi_devtools/evidence_catalog.py`.

- Workflow status: follow `packages/devtools/src/kotekomi_devtools/tdd_workflow.py`.

## Constraints and Halt Conditions

The implementation keeps V1 Task Manifest validation for historical reporting.

The implementation does not create or resume a direct-main run.

The implementation does not mutate historical Verification Receipts on existing verification branches.

The implementation does not merge or delete feature branches.
