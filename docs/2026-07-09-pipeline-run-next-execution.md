# Pipeline Run Next Execution

## 1. Context & Problem

Pipeline Executable Agent Next Step Plans return executable argv.
Agents still need to copy argv into a separate command invocation.
KoteKomi needs a controlled one-step executor that uses the existing command plan.
The executor must not become a scheduler or bypass review.

## 2. Goals

- Add `pipeline run-next` for one planned command.
- Reuse Pipeline Readiness command plans.
- Execute only ready command plans.
- Return structured JSON for agents.
- Preserve existing command transaction boundaries.

## 3. Non-Goals & Forbidden Approaches

Non-goals:

- This TDD does not add a scheduler.
- This TDD does not add multi-step execution.
- This TDD does not persist run history.
- This TDD does not approve, reject, or edit ProposedChange records.
- This TDD does not add Ledger tables.

Forbidden approaches:

- `run-next` must not parse CLI text to decide what to run.
- `run-next` must not mutate state when the command plan is not ready.
- `run-next` must not bypass `review_required`.
- `run-next` must not spawn a subprocess.
- `run-next` must not execute commands outside `command_plan.argv`.

## 4. Requirements

- `pipeline run-next` must compute Pipeline Next Step.
- `pipeline run-next` must execute exactly `command_plan.argv` when ready.
- `pipeline run-next --dry-run` must not execute the planned command.
- `pipeline run-next --format json` must emit structured JSON.
- Missing inputs must return exit code `2`.
- `briefing_current` must return exit code `0` without execution.
- `review_required` must execute only the safe planned `review next`.
- The result must include captured stdout and stderr lines.

## 5. Invariants

- Application Layer owns Pipeline Readiness and command-plan decisions.
- Pipeline owns execution of Pipeline commands.
- Existing commands own their Ledger transactions.
- ProposedChange review remains a gate before accepted Ledger state.
- `run-next` executes one command per invocation.

## 6. Proposed Architecture

The Pipeline computes Pipeline Next Step.
The Pipeline validates the command plan.
The Pipeline dispatches the planned argv through the existing CLI dispatcher.
The Pipeline captures output and renders a result.

```text
+------------------+       +---------------------+
| Pipeline         | ----> | Application Layer   |
| run-next         |       | command plan        |
+--------+---------+       +---------------------+
         |
         v
+------------------+
| Existing CLI     |
| command handler  |
+------------------+
```

## 7. Key Interactions

### Missing Inputs

```text
Agent -> Pipeline: pipeline run-next --format json
Pipeline -> Application Layer: get Pipeline Next Step
Application Layer -> Pipeline: command plan with missing inputs
Pipeline -> Agent: JSON result, executed=false, exit_code=2
```

### Execute One Step

```text
Agent -> Pipeline: pipeline run-next --format json --source-file-path article.md
Pipeline -> Application Layer: get Pipeline Next Step
Application Layer -> Pipeline: executable command plan
Pipeline -> CLI dispatcher: planned argv
CLI dispatcher -> Pipeline: exit code and output
Pipeline -> Agent: JSON result
```

### Dry Run

```text
Agent -> Pipeline: pipeline run-next --dry-run --format json
Pipeline -> Application Layer: get Pipeline Next Step
Pipeline -> Agent: JSON result, executed=false
```

## 8. Data Model

`PipelineRunNextResult` describes one `run-next` attempt.

```text
PipelineRunNextResult
- stage
- command
- command_plan
- ready_to_execute
- executed
- dry_run
- exit_code
- stdout_lines
- stderr_lines
- reason
```

## 9. APIs / Interfaces

The Application Layer adds:

```text
run_next_result_to_json
```

The Pipeline adds:

```text
kotekomi pipeline run-next
kotekomi pipeline run-next --format json
kotekomi pipeline run-next --dry-run
```

`run-next` accepts the same planning flags as `pipeline next`.

## 10. Behavior & Domain Rules

If `ready_to_execute=false`, `run-next` does not execute.
The result exit code is `2`.

If `command_plan.command is None`, `run-next` does not execute.
The result exit code is `0`.

If `--dry-run` is set, `run-next` does not execute.
The result exit code is `0` when the plan is ready.

If the plan is ready, `run-next` calls the existing CLI dispatcher with `command_plan.argv`.
The result exit code is the dispatched command exit code.

In `review_required`, the planned command is `review next`.
`run-next` must not approve, reject, or edit ProposedChange records.

## 11. Acceptance Criteria

- Application tests prove run result JSON includes command plan and output lines.
- Application tests prove missing inputs serialize through run result JSON.
- Pipeline tests prove missing inputs return exit code `2`.
- Pipeline tests prove dry run does not mutate the Ledger.
- Pipeline tests prove source ingest runs through `run-next`.
- Pipeline tests prove assertion proposal runs through `run-next`.
- Pipeline tests prove review-required runs `review next` only.
- Pipeline tests prove graph mining runs through `run-next`.
- Pipeline tests prove missing Briefing title returns exit code `2`.
- Pipeline tests prove Briefing generation runs through `run-next`.
- Pipeline tests prove `briefing_current` executes nothing.

## 12. Cross-Cutting Concerns

JSON output is the agent contract.
Text output is for humans.
Captured command output is structured as lines.
`run-next` does not store run history.

## 13. Reference Implementations

- `packages/application/src/kotekomi_application/pipeline_readiness.py`
- `packages/pipelines/src/kotekomi_pipelines/cli.py`
- `packages/pipelines/tests/test_pipeline_readiness.py`

## 14. Alternatives Considered

- Spawn a subprocess.
  The chosen design uses internal dispatch for testability.
- Block review-required execution.
  The chosen design allows safe `review next` only.
- Return pass-through output only.
  The chosen design returns structured JSON for agents.

## 15. Halt Conditions

- Halt if execution requires multi-step orchestration.
- Halt if execution requires persistent run history.
- Halt if execution would approve or edit ProposedChange records.
