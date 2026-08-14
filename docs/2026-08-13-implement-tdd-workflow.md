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

This TDD uses the term `run record` for the canonical record for one implementation run.

This TDD uses the term `run index` for the canonical record that assigns implementation run ordinals.

This TDD uses the term `task manifest` for the `.agent/tasks/<task-id>.toml` file that authorizes the Harness task.

Primary end-to-end Flow:

1. The user gives the implementation agent a TDD path.

2. The implementation agent runs the Harness implementation workflow command with the TDD path.

3. The Harness creates or reads the TDD binding.

4. The Harness resolves the internal task identifier from the TDD binding.

5. The Harness checks the task manifest path for the internal task identifier.

6. The Harness returns `create_task_manifest` when the task manifest is missing.

7. The implementation agent authors the task manifest when the Harness requests it.

8. The Harness reads receipts, run state, and branch state for the internal task identifier.

9. The Harness returns the implementation phase and next action.

10. The implementation agent follows the next action and reports the required operator step.

## Goals

- The user can start implementation with one instruction and one TDD path.

- The implementation agent can resume a TDD implementation after a failure.

- The Harness decides the next action from stored evidence.

- The implementation agent no longer reconstructs lifecycle state from chat context.

- The user does not need to know the internal task identifier.

- The Harness assigns implementation run identifiers deterministically.

## Requirements

TDD workflow boundary:

- TW-01: The workflow accepts a TDD path.

- TW-02: The workflow creates a TDD binding when none exists.

- TW-03: The workflow reads the existing TDD binding when one exists.

- TW-04: The workflow resolves the task identifier from the TDD binding.

- TW-05: The workflow returns blocked status when the TDD binding is blocked.

Manifest boundary:

- MF-01: The workflow derives the task manifest path as `.agent/tasks/<task-id>.toml`.

- MF-02: The workflow returns `create_task_manifest` when the task manifest is missing.

- MF-03: The workflow does not silently create the task manifest.

- MF-04: The implementation agent authors the task manifest when the workflow returns `create_task_manifest`.

- MF-05: The workflow validates the task manifest after it exists.

- MF-06: The workflow blocks when the task manifest task identifier differs from the TDD binding task identifier.

- MF-07: The workflow blocks when the task manifest TDD digest differs from the TDD binding TDD digest.

Run boundary:

- RN-01: The workflow stores the run index at `<state-root>/experiments/<task-id>/runs/index.json`.

- RN-02: The workflow stores each run record at `<state-root>/experiments/<task-id>/runs/<implementation-run-id>/run.json`.

- RN-03: The workflow creates run identifiers as `<task-id>-run-<three-digit-ordinal>`.

- RN-04: The workflow creates a run with status `active` when no active or blocked run exists.

- RN-05: The workflow reuses the latest active run.

- RN-06: The workflow reuses the latest blocked run.

- RN-07: The workflow changes a blocked run to active when the blocking condition is resolved.

- RN-08: The workflow changes an active run to blocked when a Harness gate blocks progress.

- RN-09: The workflow changes an active run to complete when main CI evidence and cleanup evidence exist.

- RN-10: The workflow never resumes a complete run.

- RN-11: The workflow never resumes an abandoned run.

- RN-12: Only an explicit operator command marks a run abandoned.

- RN-13: A new run after complete or abandoned requires an explicit new-run option.

- RN-14: Run record tests use an injected clock for `started_at` and `updated_at`.

- RN-15: Byte-stability tests exclude `started_at` and `updated_at` unless they inject the clock.

Status boundary:

- ST-01: The status resolver reports one implementation phase.

- ST-02: The status resolver reports one next action.

- ST-03: The status resolver reports the internal task identifier as evidence.

- ST-04: The status resolver reports the implementation run identifier as evidence.

- ST-05: The status resolver reports the requested TDD path.

- ST-06: The status resolver reports the primary TDD path.

- ST-07: The status resolver reports all TDD paths.

- ST-08: The status resolver reports missing receipt names.

- ST-09: The status resolver reports digest mismatch diagnostics.

- ST-10: The status resolver prints JSON output to stdout by default.

- ST-11: The status resolver writes an optional JSON copy when the operator passes `--output`.

- ST-12: The status resolver writes Markdown output when the operator requests it with `--markdown`.

Phase boundary:

- PH-01: The workflow reports `intake` when no ready TDD binding exists.

- PH-02: The workflow reports `spec` when the task manifest is missing.

- PH-03: The workflow reports `spec` when no spec receipt exists.

- PH-04: The workflow reports `candidate` when spec evidence exists and candidate evidence is missing.

- PH-05: The workflow reports `verification` when candidate evidence exists and verified check evidence is missing.

- PH-06: The workflow reports `candidate_ci` when verified check evidence exists and candidate CI evidence is missing.

- PH-07: The workflow reports `main` when candidate CI evidence exists and main merge evidence is missing.

- PH-08: The workflow reports `main_ci` when main merge evidence exists and main CI evidence is missing.

- PH-09: The workflow reports `complete` when main CI evidence and cleanup evidence exist.

Agent boundary:

- AG-01: The workflow output gives the implementation agent a command label for the next action.

- AG-02: The workflow output gives the implementation agent the required evidence for that next action.

- AG-03: The workflow output gives the implementation agent a blocked diagnostic when no next action is legal.

- AG-04: The workflow output gives the implementation agent the task manifest path when the next action is `create_task_manifest`.

- AG-05: The workflow output identifies the task manifest schema as the authoring contract for `create_task_manifest`.

## Proposed Architecture

The workflow command owns the user-facing entry point.

The TDD binding command owns TDD identity and internal task identity.

The manifest resolver owns task manifest discovery and validation.

The run state manager owns run index and run record updates.

The status resolver owns phase and next action selection.

The receipt-chain status command owns receipt completeness and digest checks.

The branch state reader owns local branch and remote branch facts.

```text
+------------------------+      +----------------------+
| Implementation agent   | ---> | Workflow command     |
+------------------------+      +----------------------+
                                           |
             +-----------------------------+-----------------------------+
             |                             |                             |
             v                             v                             v
   +------------------+          +-------------------+          +----------------+
   | TDD binding      |          | Manifest resolver |          | Run state      |
   +------------------+          +-------------------+          +----------------+
                                           |
                                           v
                                 +----------------------+
                                 | Status resolver      |
                                 +----------------------+
                                           |
                         +-----------------+-----------------+
                         |                                   |
                         v                                   v
               +----------------------+            +-------------------+
               | Receipt-chain status |            | Branch state      |
               +----------------------+            +-------------------+
```

## Key Interactions

Primary sequence:

```text
Agent     Workflow command   TDD binding   Manifest resolver   Run state   Status resolver
  |              |                |                 |              |              |
  | implement    |                |                 |              |              |
  |------------->|                |                 |              |              |
  |              | bind or read   |                 |              |              |
  |              |--------------->|                 |              |              |
  |              | binding        |                 |              |              |
  |              |<---------------|                 |              |              |
  |              | check manifest |                 |              |              |
  |              |--------------------------------->|              |              |
  |              | manifest facts |                 |              |              |
  |              |<---------------------------------|              |              |
  |              | get run        |                 |              |              |
  |              |------------------------------------------------>|              |
  |              | run facts      |                 |              |              |
  |              |<------------------------------------------------|              |
  |              | resolve status |                 |              |              |
  |              |--------------------------------------------------------------->|
  |              | status         |                 |              |              |
  |              |<---------------------------------------------------------------|
  | report       |                |                 |              |              |
  |<-------------|                |                 |              |              |
```

Manifest-missing sequence:

```text
Agent     Workflow command   TDD binding   Manifest resolver
  |              |                |                 |
  | implement    |                |                 |
  |------------->|                |                 |
  |              | bind or read   |                 |
  |              |--------------->|                 |
  |              | binding        |                 |
  |              |<---------------|                 |
  |              | check manifest |                 |
  |              |--------------------------------->|
  |              | missing        |                 |
  |              |<---------------------------------|
  | create task  |                |                 |
  | manifest     |                |                 |
  |<-------------|                |                 |
```

Blocked sequence:

```text
Agent        Workflow command      TDD binding
  |                 |                    |
  | implement TDD   |                    |
  |---------------->|                    |
  |                 | bind or read TDD   |
  |                 |------------------->|
  |                 | blocked binding    |
  |                 |<-------------------|
  | blocked status  |                    |
  |<----------------|                    |
```

## Data Model

The Harness will create an implementation status record.

The implementation status record has these fields:

- `schema_version`

- `task_id`

- `implementation_run_id`

- `requested_tdd_path`

- `primary_tdd_path`

- `tdd_paths`

- `tdd_sha256`

- `manifest_path`

- `implementation_phase`

- `status`

- `next_action`

- `required_evidence`

- `missing_receipts`

- `diagnostics`

The run index record has these fields:

- `schema_version`

- `task_id`

- `next_ordinal`

- `runs`

- `diagnostics`

Each run index entry has these fields:

- `implementation_run_id`

- `run_record_path`

- `status`

- `ordinal`

The run record has these fields:

- `schema_version`

- `task_id`

- `implementation_run_id`

- `ordinal`

- `status`

- `started_at`

- `updated_at`

- `terminal_at`

- `diagnostics`

The legal run status transitions are:

```text
active -> blocked
active -> complete
active -> abandoned
blocked -> active
blocked -> abandoned
complete -> terminal
abandoned -> terminal
```

The Harness will read TDD binding records by `requested_tdd_path` through the TDD index.

The Harness will read receipt-chain status records by `task_id`.

The Harness will read branch state by `task_id`.

## APIs / Interfaces

The CLI contract is:

```text
kotekomi-agent implement-tdd <tdd-path> [--output <status-json>] [--markdown <status-md>]
```

The new-run CLI contract is:

```text
kotekomi-agent implement-tdd <tdd-path> --new-run [--output <status-json>] [--markdown <status-md>]
```

The abandon-run CLI contract is:

```text
kotekomi-agent implement-tdd <tdd-path> --abandon-run <implementation-run-id> [--output <status-json>] [--markdown <status-md>]
```

The CLI prints the JSON result to stdout when `--output` is absent.

The `--output` file is an optional JSON copy.

The `--markdown` file is an optional Markdown copy.

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
missing_receipts
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

The next action for a missing task manifest is:

```text
create_task_manifest
```

The required contract for `create_task_manifest` is the task manifest schema and existing task manifest examples.

## Behavior & Domain Rules

The workflow resolves TDD binding before it resolves implementation status.

The workflow treats blocked TDD binding as a blocked implementation status.

The workflow validates the task manifest before it selects candidate or later phases.

The workflow treats missing task manifest as `spec` phase with next action `create_task_manifest`.

The implementation agent authors the task manifest at the reported manifest path.

The workflow treats task manifest schema validation errors as blocked status.

The workflow treats task manifest task identifier mismatch as blocked status.

The workflow treats task manifest TDD digest mismatch as blocked status.

The workflow selects the earliest incomplete implementation phase.

The workflow selects one next action for each non-complete phase.

The workflow returns complete only when main CI evidence and cleanup evidence exist.

The workflow records missing evidence as diagnostics.

The workflow does not treat chat context as implementation evidence.

The workflow exposes the internal task identifier as evidence.

The workflow exposes the implementation run identifier as evidence.

The workflow does not require the user to provide the internal task identifier.

The workflow reuses active or blocked runs according to the run transition rules.

The workflow uses an injected clock in tests that assert timestamp values.

The workflow excludes timestamp fields from byte-stability assertions when tests do not inject the clock.

## Acceptance Criteria

- AC-TW-01: CLI tests prove the workflow accepts a TDD path.

- AC-TW-02: Acceptance tests prove the workflow creates a TDD binding when none exists.

- AC-TW-03: Acceptance tests prove the workflow reads an existing TDD binding.

- AC-TW-04: Acceptance tests prove the workflow resolves the task identifier from the TDD binding.

- AC-TW-05: Acceptance tests prove blocked TDD binding returns blocked workflow status.

- AC-MF-01: Acceptance tests prove the manifest path is `.agent/tasks/<task-id>.toml`.

- AC-MF-02: Acceptance tests prove missing task manifest returns `create_task_manifest`.

- AC-MF-03: Acceptance tests prove the workflow does not create the task manifest.

- AC-MF-04: Documentation tests prove the implementation agent authors the task manifest.

- AC-MF-05: Acceptance tests prove existing task manifest is validated.

- AC-MF-06: Acceptance tests prove task identifier mismatch returns blocked status.

- AC-MF-07: Acceptance tests prove TDD digest mismatch returns blocked status.

- AC-RN-01: Acceptance tests prove the workflow writes the run index.

- AC-RN-02: Acceptance tests prove the workflow writes the run record.

- AC-RN-03: Unit tests prove run identifiers use three-digit ordinals.

- AC-RN-04: Unit tests prove a new run starts as active.

- AC-RN-05: Unit tests prove the workflow reuses the latest active run.

- AC-RN-06: Unit tests prove the workflow reuses the latest blocked run.

- AC-RN-07: Unit tests prove blocked changes to active when the block resolves.

- AC-RN-08: Unit tests prove active changes to blocked when a Harness gate blocks progress.

- AC-RN-09: Unit tests prove active changes to complete when main CI and cleanup evidence exist.

- AC-RN-10: Unit tests prove complete is terminal.

- AC-RN-11: Unit tests prove abandoned is terminal.

- AC-RN-12: CLI tests prove only the explicit abandon-run command marks a run abandoned.

- AC-RN-13: CLI tests prove a new run after complete or abandoned requires `--new-run`.

- AC-RN-14: Unit tests prove timestamp assertions use an injected clock.

- AC-RN-15: Byte-stability tests exclude timestamp fields when no clock is injected.

- AC-ST-01: Unit tests prove the status resolver reports one implementation phase.

- AC-ST-02: Unit tests prove the status resolver reports one next action.

- AC-ST-03: Acceptance tests prove the internal task identifier appears as evidence.

- AC-ST-04: Acceptance tests prove the implementation run identifier appears as evidence.

- AC-ST-05: Acceptance tests prove requested TDD path appears in output.

- AC-ST-06: Acceptance tests prove primary TDD path appears in output.

- AC-ST-07: Acceptance tests prove all TDD paths appear in output.

- AC-ST-08: Acceptance tests prove missing receipts appear in output.

- AC-ST-09: Acceptance tests prove digest mismatch diagnostics appear in output.

- AC-ST-10: CLI tests prove JSON output appears on stdout when `--output` is absent.

- AC-ST-11: CLI tests prove `--output` writes an optional JSON copy.

- AC-ST-12: CLI tests prove Markdown output exists when requested.

- AC-ST-13: CLI tests prove `kotekomi-agent implement-tdd <tdd-path>` runs as documented.

- AC-PH-01: Fixture tests prove the `intake` phase.

- AC-PH-02: Fixture tests prove the `spec` phase for a missing task manifest.

- AC-PH-03: Fixture tests prove the `spec` phase for missing spec receipt.

- AC-PH-04: Fixture tests prove the `candidate` phase.

- AC-PH-05: Fixture tests prove the `verification` phase.

- AC-PH-06: Fixture tests prove the `candidate_ci` phase.

- AC-PH-07: Fixture tests prove the `main` phase.

- AC-PH-08: Fixture tests prove the `main_ci` phase.

- AC-PH-09: Fixture tests prove the `complete` phase.

- AC-AG-01: Acceptance tests prove the output contains a command label.

- AC-AG-02: Acceptance tests prove the output contains required evidence.

- AC-AG-03: Acceptance tests prove blocked status has no legal next action.

- AC-AG-04: Acceptance tests prove `create_task_manifest` output includes the task manifest path.

- AC-AG-05: Acceptance tests prove `create_task_manifest` output identifies the task manifest schema.

## Reference Implementations

- TDD binding: follow `packages/devtools/src/kotekomi_devtools/tdd_binding.py`.

- Receipt-chain status: follow `packages/devtools/src/kotekomi_devtools/receipt_chain_status.py`.

- Lifecycle checks: follow `packages/devtools/src/kotekomi_devtools/lifecycle_check.py`.

- Verification planning: follow `packages/devtools/src/kotekomi_devtools/verification_plan.py`.

- Check execution: follow `packages/devtools/src/kotekomi_devtools/verification_execution.py`.

- Task manifest validation: follow `packages/devtools/src/kotekomi_devtools/task_manifest.py`.

- CLI command wiring: follow `packages/devtools/src/kotekomi_devtools/cli.py`.

## Constraints and Halt Conditions

The implementer must halt if receipt-chain status cannot expose the evidence that the status resolver needs.

The implementer must halt if branch state cannot be read deterministically in local tests.

The implementer must halt if the existing task manifest schema cannot store the TDD path and TDD digest.
