# TDD Implementation Agent Guidance

## Context & Problem

A user wants to say `implement TDD <path>` and have the implementation agent use the Harness.

The user runs the implementation from the KoteKomi repository root.

The user identifies the Technical Design Document with a local file path.

The implementation agent needs written guidance that maps the user instruction to Harness commands.

The current agent guidance does not yet describe the TDD binding, task manifest bootstrap, implementation status, run state, metrics, and scorecard flow.

This TDD uses the term `TDD path` for the local file path that identifies the Technical Design Document.

This TDD uses the term `implementation agent` for the coding agent that changes repository files.

This TDD uses the term `operator` for the human who runs local commands when the agent cannot run them directly.

This TDD uses the term `Harness command` for a deterministic `kotekomi-agent` command that owns state or evidence.

This TDD uses the term `task manifest` for the `.agent/tasks/<task-id>.toml` file that authorizes a Harness task.

Primary end-to-end Flow:

1. The user asks the implementation agent to implement a TDD path.

2. The implementation agent reads the TDD path and relevant repository guidance.

3. The implementation agent runs or asks the operator to run the implementation workflow command.

4. The implementation agent authors the task manifest when the Harness returns `create_task_manifest`.

5. The implementation agent follows the next action from the Harness.

6. The implementation agent reports Harness evidence after completion.

7. The implementation agent reports TDD metrics and the TDD scorecard after completion.

## Goals

- The implementation agent starts every TDD implementation with Harness status.

- The implementation agent follows deterministic next actions.

- The implementation agent authors the task manifest only when the Harness requests it.

- The implementation agent reports evidence instead of chat-based completion claims.

- The operator receives one clear local command at each step.

- The user never needs to provide the internal task identifier.

## Requirements

Guidance boundary:

- GB-01: The guidance tells the implementation agent to run the implementation workflow command first.

- GB-02: The guidance tells the implementation agent to pass only the TDD path for the normal workflow.

- GB-03: The guidance tells the implementation agent to stop when Harness status is blocked.

- GB-04: The guidance tells the implementation agent to use the next action from Harness status.

- GB-05: The guidance tells the implementation agent to author the task manifest when the next action is `create_task_manifest`.

- GB-06: The guidance tells the implementation agent to use the reported manifest path.

- GB-07: The guidance tells the implementation agent to use the task manifest schema and existing task manifests as the authoring contract.

- GB-08: The guidance tells the implementation agent to use the task identifier from the TDD binding in the task manifest.

- GB-09: The guidance tells the implementation agent to use the TDD digest from the TDD binding in the task manifest.

- GB-10: The guidance tells the implementation agent to use verification-plan for check selection.

- GB-11: The guidance tells the implementation agent to use run-check for planned check execution.

- GB-12: The guidance tells the implementation agent to use verify-checks for planned check verification.

- GB-13: The guidance tells the implementation agent to use receipt-chain status before completion reports.

- GB-14: The guidance tells the implementation agent to generate TDD metrics after completion.

- GB-15: The guidance tells the implementation agent to generate a TDD scorecard after metrics.

- GB-16: The guidance tells the implementation agent that metrics and score commands return collections unless `--run` or `--latest` selects one run.

- GB-17: The guidance tells the implementation agent that documented command examples run without optional output flags.

Operator boundary:

- OP-01: The guidance tells the implementation agent to provide one local command block when the operator must run a command.

- OP-02: The guidance tells the implementation agent to ask for clipboard output after each local command.

- OP-03: The guidance tells the implementation agent to preserve failed command output as evidence.

- OP-04: The guidance tells the implementation agent to request `--new-run` only when the user asks for a new implementation run.

- OP-05: The guidance tells the implementation agent to request run abandonment only after explicit operator intent.

Reporting boundary:

- RP-01: The guidance tells the implementation agent to report the requested TDD path.

- RP-02: The guidance tells the implementation agent to report the primary TDD path.

- RP-03: The guidance tells the implementation agent to report TDD aliases when the Harness status includes them.

- RP-04: The guidance tells the implementation agent to report the TDD digest.

- RP-05: The guidance tells the implementation agent to report the internal task identifier as evidence.

- RP-06: The guidance tells the implementation agent to report the implementation run identifier as evidence.

- RP-07: The guidance tells the implementation agent to report lifecycle status.

- RP-08: The guidance tells the implementation agent to report verification status.

- RP-09: The guidance tells the implementation agent to report CI status.

- RP-10: The guidance tells the implementation agent to report metrics collection path.

- RP-11: The guidance tells the implementation agent to report scorecard collection path.

## Proposed Architecture

The documentation owns agent behavior.

The implementation workflow command owns next action status.

The task manifest schema owns task manifest validity.

The metrics command owns implementation metrics.

The scorecard command owns TDD scores.

```text
+----------------------+      +--------------------+
| User                 | ---> | Implementation     |
| implement TDD path   |      | agent              |
+----------------------+      +--------------------+
                                         |
                                         v
                              +--------------------+
                              | Agent guidance     |
                              +--------------------+
                                         |
            +----------------------------+----------------------------+
            |                            |                            |
            v                            v                            v
+----------------------+      +--------------------+      +--------------------+
| Implement workflow   |      | TDD metrics        |      | TDD scorecard      |
+----------------------+      +--------------------+      +--------------------+
            |
            v
+----------------------+
| Task manifest        |
+----------------------+
```

## Key Interactions

Primary sequence:

```text
User        Implementation agent      Agent guidance      Harness commands      Operator
 |                  |                       |                    |                 |
 | implement TDD    |                       |                    |                 |
 |----------------->|                       |                    |                 |
 |                  | read guidance         |                    |                 |
 |                  |---------------------->|                    |                 |
 |                  | guidance              |                    |                 |
 |                  |<----------------------|                    |                 |
 |                  | run status or ask run |                    |                 |
 |                  |------------------------------------------->|                 |
 |                  | next action           |                    |                 |
 |                  |<-------------------------------------------|                 |
 |                  | local command         |                    |                 |
 |                  |----------------------------------------------------------->|
 |                  | clipboard output      |                    |                 |
 |                  |<-----------------------------------------------------------|
 | evidence report  |                       |                    |                 |
 |<-----------------|                       |                    |                 |
```

Manifest authoring sequence:

```text
Agent        Harness commands      Task manifest
  |                  |                  |
  | implement-tdd    |                  |
  |----------------->|                  |
  | create manifest  |                  |
  |<-----------------|                  |
  | author manifest  |                  |
  |------------------------------------>|
  | implement-tdd    |                  |
  |----------------->|                  |
  | validated status |                  |
  |<-----------------|                  |
```

Blocked sequence:

```text
User        Implementation agent      Harness commands
 |                  |                        |
 | implement TDD    |                        |
 |----------------->|                        |
 |                  | run status             |
 |                  |----------------------->|
 |                  | blocked status         |
 |                  |<-----------------------|
 | blocked report   |                        |
 |<-----------------|                        |
```

## Data Model

This TDD creates documentation.

This TDD does not create stored records.

The guidance references these stored records:

- TDD binding record

- TDD binding revision record

- TDD index record

- task manifest

- implementation status record

- run index record

- run record

- run-check record

- verify-checks record

- receipt-chain status record

- TDD metrics collection

- TDD scorecard collection

## APIs / Interfaces

The guidance documents these Harness commands:

```text
kotekomi-agent implement-tdd
kotekomi-agent verification-plan
kotekomi-agent run-check
kotekomi-agent verify-checks
kotekomi-agent receipt-chain-status
kotekomi-agent tdd-metrics
kotekomi-agent tdd-score
kotekomi-agent tdd-compare
```

The user-facing instruction is:

```text
implement TDD <path>
```

The normal first Harness command is:

```text
kotekomi-agent implement-tdd <tdd-path>
```

The command prints JSON to stdout unless the agent adds an optional `--output` path.

The agent adds optional `--markdown` only when a Markdown copy is useful.

The manifest authoring path comes from the workflow status field `manifest_path`.

The metrics command for all runs of one TDD is:

```text
kotekomi-agent tdd-metrics <tdd-path>
```

The metrics command for all known TDDs is:

```text
kotekomi-agent tdd-metrics
```

The metrics commands print JSON to stdout unless the agent adds an optional `--output` path.

The scorecard command for all runs of one TDD is:

```text
kotekomi-agent tdd-score <tdd-path>
```

The scorecard command for all known TDDs is:

```text
kotekomi-agent tdd-score
```

The scorecard commands print JSON to stdout unless the agent adds an optional `--output` path.

## Behavior & Domain Rules

The implementation agent treats Harness status as the source of lifecycle state.

The implementation agent treats the TDD path as the user-facing TDD identifier.

The implementation agent treats the TDD digest as the source of TDD identity.

The implementation agent treats the task identifier as Harness evidence, not user input.

The implementation agent treats the implementation run identifier as Harness evidence, not user input.

The implementation agent authors the task manifest only when the Harness returns `create_task_manifest`.

The implementation agent validates the task manifest by rerunning the workflow command.

The implementation agent treats verification-plan output as the source of required checks.

The implementation agent treats verify-checks output as the source of local verification readiness.

The implementation agent treats main CI evidence as the source of merged implementation readiness.

The implementation agent reports blocked status when the Harness reports blocked status.

The implementation agent reports uncertainty when Harness evidence is missing.

The implementation agent reports collection outputs unless the user requested one run.

## Acceptance Criteria

- AC-GB-01: Documentation review proves the guidance starts with the implementation workflow command.

- AC-GB-02: Documentation review proves the guidance passes only the TDD path for the normal workflow.

- AC-GB-03: Documentation review proves the guidance stops on blocked Harness status.

- AC-GB-04: Documentation review proves the guidance follows the next action from Harness status.

- AC-GB-05: Documentation review proves the guidance authors the task manifest for `create_task_manifest`.

- AC-GB-06: Documentation review proves the guidance uses the reported manifest path.

- AC-GB-07: Documentation review proves the guidance references the task manifest schema and existing manifests.

- AC-GB-08: Documentation review proves the guidance uses the task identifier from the TDD binding.

- AC-GB-09: Documentation review proves the guidance uses the TDD digest from the TDD binding.

- AC-GB-10: Documentation review proves the guidance names verification-plan as the check selector.

- AC-GB-11: Documentation review proves the guidance names run-check as the check executor.

- AC-GB-12: Documentation review proves the guidance names verify-checks as the check verifier.

- AC-GB-13: Documentation review proves the guidance names receipt-chain status before completion reports.

- AC-GB-14: Documentation review proves the guidance names TDD metrics after completion.

- AC-GB-15: Documentation review proves the guidance names TDD scorecard after metrics.

- AC-GB-16: Documentation review proves the guidance explains collection output for metrics and score commands.

- AC-GB-17: Documentation review proves documented command examples run without optional output flags.

- AC-OP-01: Documentation review proves local command blocks contain one operator action.

- AC-OP-02: Documentation review proves the guidance asks for clipboard output.

- AC-OP-03: Documentation review proves failed command output remains evidence.

- AC-OP-04: Documentation review proves `--new-run` requires user intent.

- AC-OP-05: Documentation review proves run abandonment requires explicit operator intent.

- AC-RP-01: Documentation review proves final reports include the requested TDD path.

- AC-RP-02: Documentation review proves final reports include the primary TDD path.

- AC-RP-03: Documentation review proves final reports include TDD aliases when the Harness status includes them.

- AC-RP-04: Documentation review proves final reports include the TDD digest.

- AC-RP-05: Documentation review proves final reports include the internal task identifier as evidence.

- AC-RP-06: Documentation review proves final reports include the implementation run identifier as evidence.

- AC-RP-07: Documentation review proves final reports include lifecycle status.

- AC-RP-08: Documentation review proves final reports include verification status.

- AC-RP-09: Documentation review proves final reports include CI status.

- AC-RP-10: Documentation review proves final reports include metrics collection path.

- AC-RP-11: Documentation review proves final reports include scorecard collection path.

## Reference Implementations

- Operator command style: follow the existing local Harness runbook pattern in this conversation.

- Agent guidance style: follow `docs/agent/writing-tdds.md`.

- Harness status command references: follow `packages/devtools/src/kotekomi_devtools/cli.py`.

- Task manifest examples: follow existing `.agent/tasks/*.toml` files.

## Constraints and Halt Conditions

The implementer must halt if the documented command name does not exist after the earlier TDDs land.

The implementer must halt if the guidance cannot route `implement TDD <path>` to one deterministic Harness command.

The implementer must halt if task manifest schema examples cannot support the TDD binding fields.
