# Pipeline Executable Agent Next Step Plans

## 1. Context & Problem

Pipeline Readiness reports the current stage and next command template.
Agent Next Step returns JSON for agents.
The JSON still contains placeholders such as `<path>` and `<title>`.
Agents need executable argv or explicit missing inputs.

## 2. Goals

- Return executable argv when the next Pipeline command has all inputs.
- Return typed missing inputs when the next command needs user or agent context.
- Keep JSON as the agent contract.
- Keep text output human-facing.
- Keep the command read-only.

## 3. Non-Goals & Forbidden Approaches

Non-goals:

- This TDD does not add a scheduler.
- This TDD does not run the next command.
- This TDD does not enforce gates for existing commands.
- This TDD does not persist command plans.
- This TDD does not add Ledger tables.

Forbidden approaches:

- Agents must not parse human CLI text to assemble commands.
- Command plans must not contain angle-bracket placeholders in argv.
- The Pipeline must not infer Domain meaning.
- The command plan must not mutate Ledger or Archive state.
- The command plan must not hide review blockers.

## 4. Requirements

- `pipeline next --format json` must include `command_plan`.
- `pipeline status --format json` must include `next_command_plan`.
- Command plans must include argv when ready to execute.
- Command plans must include typed missing inputs when not ready to execute.
- Command plan argv must include resolved `--ledger-path`.
- Command plan argv must include resolved `--archive-path` for commands that use the Archive.
- Command plan argv must not contain placeholder strings.
- Command plans must preserve existing stage, counts, blocker, and readiness fields.
- CLI flags must let agents provide missing planning inputs.

## 5. Invariants

- Pipeline Readiness is derived from Ledger state and input context.
- Pipeline Readiness does not become canonical Ledger state.
- Pipeline Readiness does not change accepted Ledger records.
- Pipeline Readiness does not change ProposedChange review status.
- ProposedChange remains the gate before accepted Ledger state.
- The Application Layer owns command-plan decisions.
- The Pipeline renders Application Layer DTOs.

## 6. Proposed Architecture

The Pipeline reads config and planning flags.
The Pipeline passes resolved paths and supplied context into the Application Layer.
The Application Layer derives Pipeline Readiness and a command plan.
The Pipeline serializes the command plan to JSON or text.

```text
+------------------+       +---------------------+
| Pipeline         | ----> | Application Layer   |
| planning flags   |       | command-plan DTOs   |
+------------------+       +----------+----------+
                                      |
                                      v
                           +---------------------+
                           | Review Readiness    |
                           | pending review gate |
                           +----------+----------+
                                      |
                                      v
                           +---------------------+
                           | LedgerRepository    |
                           | Ledger records      |
                           +---------------------+
```

## 7. Key Interactions

### Agent Reads Missing Inputs

```text
Agent -> Pipeline: pipeline next --format json
Pipeline -> Application Layer: get Pipeline Next Step
Application Layer -> Pipeline: command plan with missing inputs
Pipeline -> Agent: JSON object
```

### Agent Supplies Planning Inputs

```text
Agent -> Pipeline: pipeline next --format json --source-file-path article.md
Pipeline -> Application Layer: get Pipeline Next Step with context
Application Layer -> Pipeline: executable command plan
Pipeline -> Agent: JSON object
```

### Agent Encounters Review Gate

```text
Agent -> Pipeline: pipeline next --format json
Pipeline -> Application Layer: get Pipeline Next Step
Application Layer -> Review Readiness: get pending review blockers
Application Layer -> Pipeline: executable review list plan
Pipeline -> Agent: JSON object
```

## 8. Data Model

`PipelineCommandPlan` describes one next command.

```text
PipelineCommandPlan
- stage
- command
- argv
- ready_to_execute
- missing_inputs
- blockers
```

`PipelinePlanInputRequirement` describes one missing value.

```text
PipelinePlanInputRequirement
- name
- kind
- required
- description
- allowed_values
```

`PipelineStatusInput` carries planning context.

```text
PipelineStatusInput
- ledger_path
- archive_path
- source_file_path
- model_output_fixture_path
- document_id
- briefing_title
```

## 9. APIs / Interfaces

The Application Layer extends these JSON serializers:

```text
pipeline_status_to_json
pipeline_next_to_json
```

The Pipeline extends these commands with planning flags:

```text
kotekomi pipeline status
kotekomi pipeline next
```

Both commands accept:

```text
--archive-path
--source-file-path
--model-output-fixture
--document-id
--briefing-title
```

## 10. Behavior & Domain Rules

An empty Ledger requires `source_file_path`.
When supplied, the plan returns argv for `source add-file`.

A Document without accepted Assertions requires `model_output_fixture_path`.
If exactly one candidate Document exists, the plan uses that Document.
If multiple candidate Documents exist, the plan requires `document_id`.

Pending review returns executable argv for `review list`.
The plan includes Review Readiness blockers.

Graph projection and graph mining return executable argv with `--ledger-path`.

Briefing generation requires `briefing_title`.
When supplied, the plan returns argv for `briefing generate`.

`briefing_current` returns no argv.
`briefing_current` has no missing inputs.

Example:

```json
{
  "ready_to_execute": false,
  "missing_inputs": [
    {
      "name": "source_file_path",
      "kind": "path",
      "required": true,
      "description": "Path to a local Source file.",
      "allowed_values": []
    }
  ]
}
```

Example:

```json
{
  "ready_to_execute": true,
  "argv": [
    "source",
    "add-file",
    "/abs/article.md",
    "--ledger-path",
    "/abs/kotekomi.db",
    "--archive-path",
    "/abs/archive"
  ]
}
```

## 11. Acceptance Criteria

- Application tests prove missing source path blocks source ingest execution.
- Application tests prove supplied source path creates complete source ingest argv.
- Application tests prove a single candidate Document is selected automatically.
- Application tests prove multiple candidate Documents require `document_id`.
- Application tests prove pending review returns executable `review list` argv.
- Application tests prove graph mining returns executable argv.
- Application tests prove missing Briefing title blocks Briefing execution.
- Application tests prove supplied Briefing title creates complete Briefing argv.
- Application tests prove `briefing_current` returns no argv.
- Pipeline tests prove JSON includes command plans across the fixture pipeline.
- `docs/CHECK_PLAN.md` includes command-plan checks.

## 12. Cross-Cutting Concerns

JSON output is the agent contract.
Text output is for humans.
Path values in argv are resolved before serialization.
Command planning does not check file existence.

## 13. Reference Implementations

- `packages/application/src/kotekomi_application/pipeline_readiness.py`
- `packages/pipelines/src/kotekomi_pipelines/cli.py`
- `packages/pipelines/tests/test_pipeline_readiness.py`

## 14. Alternatives Considered

- Add `pipeline plan`.
  The chosen design extends existing JSON to avoid another command.
- Replace `pipeline next` JSON.
  The chosen design keeps old fields as stable context.
- Keep placeholders in argv.
  The chosen design uses missing inputs for machine readability.

## 15. Halt Conditions

- Halt if command planning needs to execute a command.
- Halt if a command plan requires a new Ledger table.
- Halt if command planning requires parsing CLI text.
