# Implement TDD Workflow

## Context & Problem

A user wants to say `implement TDD <path>` and have an implementation agent use the Harness correctly.

The user runs Harness commands from the KoteKomi repository root.

The user identifies the Technical Design Document with a local file path.

The Harness currently exposes separate commands for lifecycle gates, verification plans, check runs, check verification, receipts, and receipt-chain status.

The implementation agent still needs to decide which Harness command comes next.

This creates operator load and makes the agent depend on chat context.

This TDD uses the term `TDD path` for the local file path that identifies the Technical Design Document.

This TDD uses the term `implementation status` for the Harness report that names the current phase and next action.

This TDD uses the term `next action` for the one Harness-guided action that can legally move the task forward.

This TDD uses the term `implementation phase` for the current Harness phase of a TDD implementation.

This TDD uses the term `implementation run` for one attempt to implement one TDD from intake through completion or block.

This TDD uses the term `run index` for the canonical record that assigns and lists implementation runs for one task identifier.

Primary end-to-end Flow:

1. The user gives the implementation agent a TDD path.

2. The implementation agent runs the Harness implementation workflow command with the TDD path.

3. The Harness creates or reads the TDD binding.

4. The Harness resolves the internal task identifier from the TDD binding.

5. The Harness creates or reloads an implementation run.

6. The Harness indexes external TDD binding and task manifest evidence for the run.

7. The Harness validates the task manifest when it exists.

8. The Harness reads the evidence index for the implementation run.

9. The Harness returns the implementation phase and next action.

10. The implementation agent follows the next action and reports the required operator step.

## Goals

- The user can start implementation with one instruction and one TDD path.

- The implementation agent can resume a TDD implementation after a failure.

- The Harness decides the next action from stored evidence.

- The implementation agent no longer reconstructs lifecycle state from chat context.

- The user does not need to know the internal task identifier.

## Requirements

TDD workflow boundary:

- TW-01: The workflow accepts a TDD path.

- TW-02: The workflow creates a TDD binding when none exists.

- TW-03: The workflow reads the existing TDD binding when one exists.

- TW-04: The workflow resolves the task identifier from the TDD binding.

- TW-05: The workflow returns blocked status when the TDD binding is blocked.

- TW-06: The workflow indexes the TDD binding as external evidence when it creates or reloads a run.

Manifest boundary:

- MF-01: The workflow uses `.agent/tasks/<task-id>.toml` as the task manifest path.

- MF-02: The workflow returns `create_task_manifest` when the task manifest is missing.

- MF-03: The workflow does not create the task manifest automatically.

- MF-04: The implementation agent authors the task manifest at the reported path.

- MF-05: The workflow validates the task manifest against the task manifest schema when the manifest exists.

- MF-06: The workflow blocks when `manifest.task_id` differs from the binding task identifier.

- MF-07: The workflow blocks when `manifest.tdd_sha256` differs from the binding TDD digest.

- MF-08: The workflow blocks when `manifest.tdd_path` is not one of the binding TDD paths.

- MF-09: The workflow indexes the task manifest as external evidence when the manifest exists.

- MF-10: The workflow indexes task manifest validation evidence after each validation run.

Run boundary:

- RN-01: The workflow stores the run index at `<state-root>/experiments/<task-id>/runs/index.json`.

- RN-02: The workflow stores each run record at `<state-root>/experiments/<task-id>/runs/<implementation-run-id>/run.json`.

- RN-03: The workflow derives run identifiers as `<task-id>-run-<ordinal>`.

- RN-04: The ordinal is a three-digit decimal number.

- RN-05: The run index assigns the next ordinal.

- RN-06: The workflow creates a run with status `active`.

- RN-07: The workflow reuses the latest `active` run unless the user requests a new run.

- RN-08: The workflow reuses the latest `blocked` run when its blocking condition is resolved.

- RN-09: The workflow does not resume a `complete` run.

- RN-10: The workflow does not resume an `abandoned` run.

- RN-11: A new run after `complete` or `abandoned` requires `--new-run`.

- RN-12: The workflow accepts `--abandon-run <implementation-run-id>`.

- RN-13: `--abandon-run` is mutually exclusive with `--new-run`.

- RN-14: Only `--abandon-run` can change a run to `abandoned`.

- RN-15: The workflow uses an injected clock for `started_at` and `updated_at` in tests.

- RN-16: Each run index entry includes the implementation run identifier.

- RN-17: Each run index entry includes the ordinal.

- RN-18: Each run index entry includes the run record path.

- RN-19: Each run index entry includes the run status.

- RN-20: `--latest` selects `latest_run_id` from the run index.

- RN-21: The workflow blocks when `latest_run_id` points to a missing run record.

Status boundary:

- ST-01: The status resolver reports one implementation phase.

- ST-02: The status resolver reports one next action.

- ST-03: The status resolver reports the internal task identifier as evidence.

- ST-04: The status resolver reports the implementation run identifier as evidence.

- ST-05: The status resolver reports the requested TDD path.

- ST-06: The status resolver reports the primary TDD path.

- ST-07: The status resolver reports TDD paths.

- ST-08: The status resolver reports missing evidence names.

- ST-09: The status resolver reports digest mismatch diagnostics.

- ST-10: The status resolver reports ready-to-run producer arguments.

- ST-11: The status resolver prints JSON to stdout by default.

- ST-12: The status resolver accepts optional `--output` and `--markdown` copy paths.

Phase boundary:

- PH-01: The workflow reports `intake` when no ready TDD binding exists.

- PH-02: The workflow reports `spec` when task manifest evidence or task manifest validation evidence is missing.

- PH-03: The workflow reports `candidate` when spec evidence exists and candidate evidence is missing.

- PH-04: The workflow reports `verification` when candidate evidence exists and verified check evidence is missing.

- PH-05: The workflow reports `candidate_ci` when verified check evidence exists and candidate CI evidence is missing.

- PH-06: The workflow reports `main` when candidate CI evidence exists and main evidence is missing.

- PH-07: The workflow reports `main_ci` when main evidence exists and main CI evidence is missing.

- PH-08: The workflow reports `complete` when complete phase evidence exists.

Agent boundary:

- AG-01: The workflow output gives the implementation agent a command label for the next action.

- AG-02: The workflow output gives the implementation agent the required evidence for that next action.

- AG-03: The workflow output gives the implementation agent a blocked diagnostic when no next action is legal.

- AG-04: The workflow output gives the implementation agent suggested command arguments for the next Harness producer command.

## Proposed Architecture

The workflow command owns the user-facing entry point.

The TDD binding command owns TDD identity and internal task identity.

The run manager owns implementation run identity and status transitions.

The evidence catalog owns evidence discovery.

The status resolver owns phase and next action selection.

The task manifest validator owns manifest schema and binding checks.

```text
+------------------------+      +----------------------+
| Implementation agent   | ---> | Workflow command     |
+------------------------+      +----------------------+
                                           |
                                           v
                 +-------------------------+------------------------+
                 |                         |                        |
                 v                         v                        v
        +------------------+      +------------------+      +-------------------+
        | TDD binding      |      | Run manager      |      | Manifest validator|
        +------------------+      +------------------+      +-------------------+
                                           |
                                           v
                                  +------------------+
                                  | Evidence catalog |
                                  +------------------+
                                           |
                                           v
                                  +------------------+
                                  | Status resolver  |
                                  +------------------+
```

## Key Interactions

Primary sequence:

```text
Agent        Workflow command      TDD binding      Run manager      Evidence catalog      Status resolver
  |                 |                    |                |                 |                   |
  | implement TDD   |                    |                |                 |                   |
  |---------------->|                    |                |                 |                   |
  |                 | bind or read TDD   |                |                 |                   |
  |                 |------------------->|                |                 |                   |
  |                 | binding result     |                |                 |                   |
  |                 |<-------------------|                |                 |                   |
  |                 | create or reload run                 |                 |                   |
  |                 |------------------------------------->|                 |                   |
  |                 | run record         |                |                 |                   |
  |                 |<-------------------------------------|                 |                   |
  |                 | index external evidence              |                 |                   |
  |                 |------------------------------------------------------>|                   |
  |                 | read evidence                         |                 |                   |
  |                 |------------------------------------------------------>|                   |
  |                 | evidence facts                        |                 |                   |
  |                 |<------------------------------------------------------|                   |
  |                 | resolve status                        |                 |                   |
  |                 |----------------------------------------------------------------------->|
  |                 | implementation status                 |                 |                   |
  |                 |<-----------------------------------------------------------------------|
  | status report   |                    |                |                 |                   |
  |<----------------|                    |                |                 |                   |
```

Manifest creation sequence:

```text
Agent        Workflow command      TDD binding      Manifest validator
  |                 |                    |                    |
  | implement TDD   |                    |                    |
  |---------------->|                    |                    |
  |                 | bind or read TDD   |                    |
  |                 |------------------->|                    |
  |                 | binding result     |                    |
  |                 |<-------------------|                    |
  |                 | find manifest      |                    |
  |                 |---------------------------------------->|
  |                 | missing manifest   |                    |
  |                 |<----------------------------------------|
  | create manifest |                    |                    |
  |<----------------|                    |                    |
```

## Data Model

The run index has these fields:

- `schema_version`

- `task_id`

- `runs`

- `latest_run_id`

- `next_ordinal`

- `diagnostics`

Each run index entry has these fields:

- `implementation_run_id`

- `ordinal`

- `run_record_path`

- `status`

- `started_at`

- `updated_at`

Each run record has these fields:

- `schema_version`

- `task_id`

- `implementation_run_id`

- `status`

- `started_at`

- `updated_at`

- `terminal_reason`

- `diagnostics`

The run status values are:

- `active`

- `blocked`

- `complete`

- `abandoned`

`latest_run_id` is the run with the highest ordinal among `active`, `blocked`, and `complete` runs.

The run index excludes `abandoned` runs from `latest_run_id` when at least one non-abandoned run exists.

The run index uses the highest abandoned ordinal as `latest_run_id` when all runs are abandoned.

The legal run transitions are:

- `active` to `blocked`

- `active` to `complete`

- `active` to `abandoned`

- `blocked` to `active`

- `blocked` to `abandoned`

The `complete` status is terminal.

The `abandoned` status is terminal.

The implementation status record has these fields:

- `schema_version`

- `status`

- `task_id`

- `implementation_run_id`

- `requested_tdd_path`

- `primary_tdd_path`

- `tdd_paths`

- `tdd_sha256`

- `manifest_path`

- `implementation_phase`

- `next_action`

- `required_evidence`

- `missing_evidence`

- `producer_arguments`

- `suggested_commands`

- `diagnostics`

## APIs / Interfaces

The CLI contract is:

```text
kotekomi-agent implement-tdd <tdd-path> [--new-run] [--abandon-run <implementation-run-id>] [--output <status-json>] [--markdown <status-md>]
```

The `--new-run` option starts a new implementation run when the current latest run is terminal.

The `--abandon-run` option marks one non-terminal run abandoned.

The JSON result contract is:

```text
schema_version
status
task_id
implementation_run_id
requested_tdd_path
primary_tdd_path
tdd_paths
tdd_sha256
manifest_path
implementation_phase
next_action
required_evidence
missing_evidence
producer_arguments
suggested_commands
diagnostics
```

The implementation phase values are:

```text
intake
spec
candidate
verification
candidate_ci
main
main_ci
complete
blocked
```

The producer arguments object includes:

```text
task_id
implementation_run_id
run_root
evidence_index_path
```

## Behavior & Domain Rules

The workflow resolves TDD binding before it resolves implementation status.

The workflow treats blocked TDD binding as a blocked implementation status.

The workflow creates or reloads an implementation run before it reads run-scoped evidence.

The workflow indexes external TDD binding evidence when it creates or reloads a run.

The workflow indexes external task manifest evidence when the manifest exists.

The workflow writes task manifest validation evidence after each manifest validation.

The workflow validates task manifest schema before it treats the spec phase as ready.

The workflow blocks when task manifest identity differs from binding identity.

The workflow reads required evidence from the evidence catalog.

The workflow selects the earliest incomplete implementation phase.

The workflow selects one next action for each non-complete phase.

The workflow returns complete only when complete phase evidence exists.

The workflow records missing evidence as diagnostics.

The workflow does not treat chat context as implementation evidence.

The workflow exposes the internal task identifier as evidence.

The workflow does not require the user to provide the internal task identifier.

The `create_task_manifest` next action means the implementation agent authors the manifest.

The `create_task_manifest` next action includes the manifest path and binding identity fields.

## Acceptance Criteria

- AC-TW-01: CLI tests prove the workflow accepts a TDD path.

- AC-TW-02: Acceptance tests prove the workflow creates a TDD binding when none exists.

- AC-TW-03: Acceptance tests prove the workflow reads an existing TDD binding.

- AC-TW-04: Acceptance tests prove the workflow resolves the task identifier from the TDD binding.

- AC-TW-05: Acceptance tests prove blocked TDD binding returns blocked workflow status.

- AC-TW-06: Acceptance tests prove the workflow indexes external TDD binding evidence.

- AC-MF-01: Acceptance tests prove missing manifest returns `create_task_manifest`.

- AC-MF-02: Acceptance tests prove the workflow does not create the manifest automatically.

- AC-MF-03: Acceptance tests prove manifest schema validation runs when the manifest exists.

- AC-MF-04: Acceptance tests prove mismatched manifest task identifier blocks.

- AC-MF-05: Acceptance tests prove mismatched manifest TDD digest blocks.

- AC-MF-06: Acceptance tests prove manifest TDD path outside binding aliases blocks.

- AC-RN-01: Unit tests prove run identifiers use task identifier and three-digit ordinal.

- AC-RN-02: Unit tests prove the run index assigns the next ordinal.

- AC-RN-03: Schema tests prove each run index entry includes implementation run identifier, ordinal, run record path, and status.

- AC-RN-04: Unit tests prove `latest_run_id` selects the highest non-abandoned ordinal.

- AC-RN-05: Unit tests prove `latest_run_id` selects the highest abandoned ordinal when all runs are abandoned.

- AC-RN-06: Unit tests prove the workflow blocks when `latest_run_id` points to a missing run record.

- AC-RN-03: Unit tests prove the workflow reuses the latest active run.

- AC-RN-04: Unit tests prove a resolved blocked run can return to active.

- AC-RN-05: Unit tests prove complete and abandoned are terminal.

- AC-RN-06: CLI tests prove `--new-run` creates a new run after a terminal run.

- AC-RN-07: CLI tests prove `--abandon-run` marks a non-terminal run abandoned.

- AC-RN-08: CLI tests prove `--abandon-run` and `--new-run` are mutually exclusive.

- AC-RN-09: Unit tests prove injected clocks control run timestamps.

- AC-ST-01: Unit tests prove the status resolver reports one implementation phase.

- AC-ST-02: Unit tests prove the status resolver reports one next action.

- AC-ST-03: Acceptance tests prove the internal task identifier appears as evidence.

- AC-ST-04: Acceptance tests prove the implementation run identifier appears as evidence.

- AC-ST-05: Acceptance tests prove requested, primary, and alias TDD paths appear in output.

- AC-ST-06: Acceptance tests prove missing evidence appears in output.

- AC-ST-07: Acceptance tests prove digest mismatch diagnostics appear in output.

- AC-ST-08: CLI tests prove JSON output exists by default.

- AC-ST-09: CLI tests prove optional `--output` and `--markdown` write copies.

- AC-ST-10: Acceptance tests prove producer arguments appear in output.

- AC-PH-01: Fixture tests prove the `intake` phase.

- AC-PH-02: Fixture tests prove the `spec` phase.

- AC-PH-03: Fixture tests prove the `candidate` phase.

- AC-PH-04: Fixture tests prove the `verification` phase.

- AC-PH-05: Fixture tests prove the `candidate_ci` phase.

- AC-PH-06: Fixture tests prove the `main` phase.

- AC-PH-07: Fixture tests prove the `main_ci` phase.

- AC-PH-08: Fixture tests prove the `complete` phase.

- AC-AG-01: Acceptance tests prove the output contains a command label.

- AC-AG-02: Acceptance tests prove the output contains required evidence.

- AC-AG-03: Acceptance tests prove blocked status has no legal next action.

- AC-AG-04: Acceptance tests prove suggested commands contain task and run arguments.

## Reference Implementations

- TDD binding: follow `packages/devtools/src/kotekomi_devtools/tdd_binding.py`.

- Task manifest validation: follow `packages/devtools/src/kotekomi_devtools/task_manifest.py`.

- Task lifecycle records: follow `packages/devtools/src/kotekomi_devtools/task_lifecycle.py`.

- Verification planning: follow `packages/devtools/src/kotekomi_devtools/verification_plan.py`.

- Check execution: follow `packages/devtools/src/kotekomi_devtools/verification_execution.py`.

- CLI command wiring: follow `packages/devtools/src/kotekomi_devtools/cli.py`.

## Constraints and Halt Conditions

The implementer must halt if the task manifest schema cannot validate `task_id`, `tdd_path`, and `tdd_sha256`.

The implementer must halt if evidence catalog phase requirements cannot distinguish all implementation phases.
