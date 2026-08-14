# TDD Implementation Agent Guidance

## Context & Problem

A user wants to say `implement TDD <path>` and have the implementation agent use the Harness.

The user runs the implementation from the KoteKomi repository root.

The user identifies the Technical Design Document with a local file path.

The implementation agent needs written guidance that maps the user instruction to Harness commands.

The current agent guidance does not yet describe the TDD binding, implementation status, run evidence catalog, metrics, and scorecard flow.

This TDD uses the term `TDD path` for the local file path that identifies the Technical Design Document.

This TDD uses the term `implementation agent` for the coding agent that changes repository files.

This TDD uses the term `operator` for the human who runs local commands when the agent cannot run them directly.

This TDD uses the term `Harness command` for a deterministic `kotekomi-agent` command that owns state or evidence.

Primary end-to-end Flow:

1. The user asks the implementation agent to implement a TDD path.

2. The implementation agent reads the TDD path and relevant repository guidance.

3. The implementation agent runs or asks the operator to run the implementation workflow command.

4. The implementation agent follows the next action from the Harness.

5. The implementation agent runs Harness producer commands with task and run arguments from workflow status.

6. The implementation agent reports Harness evidence after completion.

7. The implementation agent reports TDD metrics and the TDD scorecard after completion.

## Goals

- The implementation agent starts every TDD implementation with Harness status.

- The implementation agent follows deterministic next actions.

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

- GB-06: The guidance tells the implementation agent to use workflow-provided producer arguments for Harness producer commands.

- GB-07: The guidance tells the implementation agent to use verification-plan for check selection.

- GB-08: The guidance tells the implementation agent to use run-check for planned check execution.

- GB-09: The guidance tells the implementation agent to use verify-checks for planned check verification.

- GB-10: The guidance tells the implementation agent to use receipt-chain status before completion reports.

- GB-11: The guidance tells the implementation agent to generate TDD metrics after completion.

- GB-12: The guidance tells the implementation agent to generate a TDD scorecard after metrics.

Operator boundary:

- OP-01: The guidance tells the implementation agent to provide one local command block when the operator must run a command.

- OP-02: The guidance tells the implementation agent to ask for clipboard output after each local command.

- OP-03: The guidance tells the implementation agent to preserve failed command output as evidence.

- OP-04: The guidance examples use executable commands without required omitted flags.

Reporting boundary:

- RP-01: The guidance tells the implementation agent to report the TDD path.

- RP-02: The guidance tells the implementation agent to report the TDD digest.

- RP-03: The guidance tells the implementation agent to report the internal task identifier as evidence.

- RP-04: The guidance tells the implementation agent to report the implementation run identifier as evidence.

- RP-05: The guidance tells the implementation agent to report lifecycle status.

- RP-06: The guidance tells the implementation agent to report verification status.

- RP-07: The guidance tells the implementation agent to report CI status.

- RP-08: The guidance tells the implementation agent to report metrics path.

- RP-09: The guidance tells the implementation agent to report scorecard path.

## Proposed Architecture

The documentation owns agent behavior.

The implementation workflow command owns next action status.

The run evidence catalog owns evidence discovery.

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
| Implement workflow   |      | Run evidence       |      | TDD metrics        |
+----------------------+      | catalog            |      +--------------------+
                              +--------------------+                |
                                                                    v
                                                           +--------------------+
                                                           | TDD scorecard      |
                                                           +--------------------+
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

- run index record

- implementation status record

- evidence index record

- evidence event log

- run-check record

- verify-checks record

- receipt-chain status record

- TDD metrics record

- TDD scorecard record

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

The normal metrics command for all known TDDs is:

```text
kotekomi-agent tdd-metrics
```

The normal score command for all known TDDs is:

```text
kotekomi-agent tdd-score
```

The normal comparison command is:

```text
kotekomi-agent tdd-compare <tdd-path> <tdd-path>
```

## Behavior & Domain Rules

The implementation agent treats Harness status as the source of lifecycle state.

The implementation agent treats the TDD path as the user-facing TDD identifier.

The implementation agent treats the TDD digest as the source of TDD identity.

The implementation agent treats workflow producer arguments as the source of task and run command arguments.

The implementation agent treats verification-plan output as the source of required checks.

The implementation agent treats verify-checks output as the source of local verification readiness.

The implementation agent treats main CI evidence as the source of merged implementation readiness.

The implementation agent reports blocked status when the Harness reports blocked status.

The implementation agent reports uncertainty when Harness evidence is missing.

The implementation agent reports the internal task identifier only as evidence.

The implementation agent treats aggregate metrics, scorecard, and comparison outputs as reports rather than run evidence.

The implementation agent reports the implementation run identifier only as evidence.

The implementation agent does not ask the user for a task identifier.

The implementation agent does not ask the user for an implementation run identifier in the normal workflow.

The implementation agent authors the task manifest when the workflow reports `create_task_manifest`.

The implementation agent validates the task manifest through the workflow before it starts candidate implementation.

## Acceptance Criteria

- AC-GB-01: Documentation review proves the guidance starts with the implementation workflow command.

- AC-GB-02: Documentation review proves the guidance passes only the TDD path for the normal workflow.

- AC-GB-03: Documentation review proves the guidance stops on blocked Harness status.

- AC-GB-04: Documentation review proves the guidance follows the next action from Harness status.

- AC-GB-05: Documentation review proves the guidance says the agent authors the task manifest for `create_task_manifest`.

- AC-GB-06: Documentation review proves the guidance uses workflow-provided producer arguments.

- AC-GB-07: Documentation review proves the guidance names verification-plan as the check selector.

- AC-GB-08: Documentation review proves the guidance names run-check as the check executor.

- AC-GB-09: Documentation review proves the guidance names verify-checks as the check verifier.

- AC-GB-10: Documentation review proves the guidance names receipt-chain status before completion reports.

- AC-GB-11: Documentation review proves the guidance names TDD metrics after completion.

- AC-GB-12: Documentation review proves the guidance names TDD scorecard after metrics.

- AC-OP-01: Documentation review proves local command blocks contain one operator action.

- AC-OP-02: Documentation review proves the guidance asks for clipboard output.

- AC-OP-03: Documentation review proves failed command output remains evidence.

- AC-OP-04: Documentation review proves documented command examples run without omitted required flags.

- AC-RP-01: Documentation review proves final reports include the TDD path.

- AC-RP-02: Documentation review proves final reports include the TDD digest.

- AC-RP-03: Documentation review proves final reports include the internal task identifier as evidence.

- AC-RP-04: Documentation review proves final reports include the implementation run identifier as evidence.

- AC-RP-05: Documentation review proves final reports include lifecycle status.

- AC-RP-06: Documentation review proves final reports include verification status.

- AC-RP-07: Documentation review proves final reports include CI status.

- AC-RP-08: Documentation review proves final reports include metrics path.

- AC-RP-09: Documentation review proves final reports include scorecard path.

## Reference Implementations

- Operator command style: follow the existing local Harness runbook pattern in this conversation.

- Agent guidance style: follow `docs/agent/writing-tdds.md`.

- Harness status command references: follow `packages/devtools/src/kotekomi_devtools/cli.py`.

## Constraints and Halt Conditions

The implementer must halt if the documented command name does not exist after the earlier TDDs land.

The implementer must halt if the guidance cannot route `implement TDD <path>` to one deterministic Harness command.
