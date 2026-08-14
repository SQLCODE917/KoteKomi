# TDD Lifecycle Evidence Producers

## Context & Problem

A user wants `implement-tdd` to name executable Harness commands for every remaining lifecycle phase.

The evidence catalog defines canonical paths for candidate commit, candidate CI, main merge, main CI, and cleanup evidence.

The Harness does not yet expose commands that create those canonical records.

The workflow can therefore identify missing evidence without giving the operator an executable producer command.

This TDD uses the term `candidate commit` for the Git commit created before candidate verification.

This TDD uses the term `CI result record` for a local JSON record that reports one CI conclusion for one commit.

This TDD uses the term `main merge` for a two-parent Git merge commit on the main branch.

This TDD uses the term `cleanup branch` for one candidate branch that the operator expects Git to remove.

This TDD uses the term `lifecycle evidence producer` for one Harness command that validates and writes one lifecycle evidence record.

Primary end-to-end Flow:

1. The workflow reports a lifecycle evidence next action with a task identifier and implementation run identifier.

2. The implementation agent runs the named lifecycle evidence producer.

3. The producer reads Git state or a pinned CI result record.

4. The producer validates the facts for its evidence type.

5. The producer writes its canonical record and updates the evidence index.

6. The workflow reads the new evidence and advances to the next phase.

## Goals

- The workflow names an executable producer command for every lifecycle evidence next action.

- The Harness writes one canonical record for each lifecycle evidence type.

- The Harness rejects lifecycle facts that do not match Git state or a pinned CI result record.

- The metrics collector reads lifecycle evidence without caller-provided report paths.

## Requirements

Common producer boundary:

- CP-01: Each lifecycle evidence producer accepts `--task-id <task-id>`.

- CP-02: Each lifecycle evidence producer accepts `--run <implementation-run-id>`.

- CP-03: Each lifecycle evidence producer accepts `--state-root <state-root>`.

- CP-04: Each lifecycle evidence producer prints its canonical record as JSON to stdout.

- CP-05: Each lifecycle evidence producer writes a JSON copy when the user supplies `--output <json>`.

- CP-06: Each lifecycle evidence producer writes a Markdown copy when the user supplies `--markdown <markdown>`.

- CP-07: Each lifecycle evidence producer writes its canonical record before it updates the evidence index.

- CP-08: Each lifecycle evidence producer uses its command name as `producer_command`.

- CP-09: Each lifecycle evidence producer appends one evidence event after it indexes its record.

Candidate commit boundary:

- CC-01: `record-candidate-commit` accepts `--commit <revision>`.

- CC-02: The command resolves the revision to one local Git commit.

- CC-03: The command blocks when the resolved commit has no first parent.

- CC-04: The command writes `commit_sha` as the resolved commit SHA-1.

- CC-05: The command writes `parent_sha` as the resolved first-parent SHA-1.

- CC-06: The command writes candidate commit evidence with phase `candidate` and subject identifier `candidate`.

CI result boundary:

- CI-01: `record-candidate-ci` accepts `--ci-result <path>`.

- CI-02: `record-main-ci` accepts `--ci-result <path>`.

- CI-03: A CI result record is UTF-8 JSON with `schema_version`, `conclusion`, and `head_sha`.

- CI-04: `conclusion` is one of `success`, `failure`, `cancelled`, or `skipped`.

- CI-05: `head_sha` is a lowercase 40-character Git SHA-1.

- CI-06: Each CI command resolves `head_sha` to one local Git commit.

- CI-07: Each CI command copies `conclusion` and `head_sha` into its canonical record.

- CI-08: Each CI command writes `ci_result_sha256` from the complete CI result record bytes.

- CI-09: `record-candidate-ci` writes candidate CI evidence with phase `candidate_ci` and subject identifier `candidate`.

- CI-10: `record-main-ci` writes main CI evidence with phase `main_ci` and subject identifier `main`.

- CI-11: Each CI producer exits zero after it records a valid CI conclusion.

Main merge boundary:

- MM-01: `record-main-merge` accepts `--merge <revision>`.

- MM-02: The command resolves the revision to one local Git commit.

- MM-03: The command blocks unless the resolved commit has exactly two parents.

- MM-04: The command writes `merge_commit` as the resolved merge SHA-1.

- MM-05: The command writes `parent_commit` as the first-parent SHA-1.

- MM-06: The command writes `verified_parent_commit` as the second-parent SHA-1.

- MM-07: The command writes main merge evidence with phase `main` and subject identifier `main`.

Cleanup boundary:

- CL-01: `record-branch-cleanup` accepts one or more `--branch <branch-name>` options.

- CL-02: The command reads local branches and `origin` remote-tracking branches.

- CL-03: The command rejects duplicate branch names.

- CL-04: The command sorts `remaining_branches` lexicographically.

- CL-05: The command writes `remaining_branches` as requested branches that Git still exposes locally or under `origin`.

- CL-06: The command writes `branch_cleanup_complete` as true only when `remaining_branches` is empty.

- CL-07: The command writes cleanup evidence with phase `main_ci` and subject identifier `cleanup`.

Workflow boundary:

- WF-01: The workflow suggests `record-candidate-commit` when candidate commit evidence is missing.

- WF-02: The workflow suggests `record-candidate-ci` when candidate CI evidence is missing.

- WF-03: The workflow suggests `record-main-merge` when main merge evidence is missing.

- WF-04: The workflow suggests `record-main-ci` when main CI evidence is missing.

- WF-05: The workflow suggests `record-branch-cleanup` when cleanup evidence is missing.

- WF-06: The workflow blocks when candidate CI evidence has a conclusion other than `success`.

- WF-07: The workflow blocks when main CI evidence has a conclusion other than `success`.

- WF-08: The workflow blocks when cleanup evidence has `branch_cleanup_complete` false.

- WF-09: The workflow blocks unless candidate CI `head_sha` equals candidate commit `commit_sha`.

- WF-10: The workflow blocks unless main merge `verified_parent_commit` equals candidate commit `commit_sha`.

- WF-11: The workflow blocks unless main CI `head_sha` equals main merge `merge_commit`.

## Proposed Architecture

Each lifecycle evidence producer owns one evidence type.

The Git reader owns Git revision and branch inspection.

The CI result reader owns CI result record validation.

The evidence catalog owns canonical record indexing.

The workflow owns the next command selection.

```text
+-------------------+      +------------------+      +----------------+
| Operator           | ---> | Producer command | ---> | Evidence catalog|
+-------------------+      +------------------+      +----------------+
                                  |                         |
                                  v                         v
                           +-------------+           +-------------+
                           | Git or CI    |           | Workflow    |
                           +-------------+           +-------------+
```

## Key Interactions

CI producer sequence:

```text
Operator       CI producer        CI result record       Evidence catalog
   |                  |                    |                    |
   | command          |                    |                    |
   |----------------->|                    |                    |
   |                  | read and hash      |                    |
   |                  |------------------->|                    |
   |                  | validate fields    |                    |
   |                  |---------------------------------------->|
   |                  | write canonical record and index        |
   |                  |---------------------------------------->|
   | canonical JSON   |                    |                    |
   |<-----------------|                    |                    |
```

## Data Model

| Record | Fields |
| --- | --- |
| Candidate commit | `schema_version`, `commit_sha`, `parent_sha`, `diagnostics` |
| Candidate CI | `schema_version`, `conclusion`, `head_sha`, `ci_result_sha256`, `diagnostics` |
| Main merge | `schema_version`, `merge_commit`, `parent_commit`, `verified_parent_commit`, `diagnostics` |
| Main CI | `schema_version`, `conclusion`, `head_sha`, `ci_result_sha256`, `diagnostics` |
| Cleanup | `schema_version`, `branch_cleanup_complete`, `remaining_branches`, `diagnostics` |

The producers write the canonical paths from `2026-08-13-tdd-run-evidence-catalog.md`.

## APIs / Interfaces

```text
kotekomi-agent <producer> --task-id <task-id> --run <run-id>
[--state-root <state-root>] [--output <json>] [--markdown <markdown>]
```

```text
record-candidate-commit --commit <revision>
record-candidate-ci --ci-result <path>
record-main-merge --merge <revision>
record-main-ci --ci-result <path>
record-branch-cleanup --branch <branch-name> [--branch <branch-name>...]
```

## Behavior & Domain Rules

Each producer blocks before it writes evidence when its input fails validation.

Each producer can replace only its current evidence index entry.

Each producer preserves prior evidence event log entries.

The CI producers preserve a failing CI conclusion as canonical evidence.

The workflow treats a CI result as evidence only for the lifecycle commit whose
SHA-1 equals its `head_sha`.

The workflow treats a main merge as the continuation of the candidate only
when its second parent equals the recorded candidate commit.

The cleanup producer records incomplete cleanup when Git still exposes a requested branch.

The cleanup producer does not delete branches.

The Git reader uses `git rev-parse --verify <revision>^{commit}` to resolve revisions.

The Git reader uses Git parent order for candidate and merge parent fields.

The CI result reader computes `ci_result_sha256` from the exact input bytes.

The workflow selects the command from WF-01 through WF-05 only after it validates the evidence index.

The workflow reports a blocked diagnostic from WF-06 through WF-08 without a next action.

## Acceptance Criteria

- AC-CP-01: CLI tests prove each producer requires task and run identifiers.

- AC-CP-02: CLI tests prove each producer prints canonical JSON to stdout.

- AC-CP-03: Acceptance tests prove each producer updates the evidence index and event log.

- AC-CC-01: Repository tests prove candidate commit records use the resolved commit and first parent.

- AC-CC-02: Repository tests prove a root commit blocks candidate commit recording.

- AC-CI-01: Unit tests prove CI result records require the fields from CI-03.

- AC-CI-02: Unit tests prove CI result records reject unsupported conclusions and invalid SHA-1 values.

- AC-CI-03: Repository tests prove CI producers reject unknown local head commits.

- AC-CI-04: Acceptance tests prove each CI producer copies CI facts and writes the source digest.

- AC-CI-05: CLI tests prove failing CI conclusions create evidence and return success.

- AC-MM-01: Repository tests prove main merge records use ordered merge parents.

- AC-MM-02: Repository tests prove a non-merge commit blocks main merge recording.

- AC-CL-01: Repository tests prove cleanup records list requested local and origin branches.

- AC-CL-02: Repository tests prove cleanup records set completion only after Git exposes no requested branch.

- AC-CL-03: Unit tests prove duplicate cleanup branches block recording.

- AC-WF-01: Workflow tests prove each missing lifecycle evidence type returns its producer command.

- AC-WF-02: Workflow tests prove failed CI and incomplete cleanup block phase advancement.

## Reference Implementations

- Evidence indexing: follow `packages/devtools/src/kotekomi_devtools/evidence_catalog.py`.

- Git revision checks: follow `packages/devtools/src/kotekomi_devtools/task_lifecycle.py`.

- CI record loading: follow `packages/devtools/src/kotekomi_devtools/verification_execution.py`.

- Receipt output: follow `packages/devtools/src/kotekomi_devtools/receipt_chain_status.py`.

- CLI wiring: follow `packages/devtools/src/kotekomi_devtools/cli.py`.

## Constraints and Halt Conditions

The implementer must halt if the repository lacks a Git executable.

The implementer must halt if the catalog trusted fields conflict with this TDD.

The implementer must halt if an existing protected producer command uses incompatible public arguments.
