# Copyable AGENTS Guidance for Terra High Harness

Searchable labels: H9-COPYABLE-GUIDANCE, H9-AGENT-COMMAND-CONTRACT, H9-NO-MANUAL-STATE, H9-GOAL-COVERAGE-GATE, H9-PORTABLE-HARNESS.

This section is designed to be copied into another project's AGENTS guidance. Replace bracketed placeholders with project-specific values.

## Implementation agent role

The implementation agent may edit code only inside the task's allowed paths. It must preserve protected artifacts and pass the harness gates.

## Deterministic recordkeeping rule

Implementation agents must not manually maintain records, roadmap files, goal status files, or final summaries.

Instead, use harness commands:

```text
[HARNESS_COMMAND] task-ledger current
[HARNESS_COMMAND] task-ledger next
[HARNESS_COMMAND] task-ledger status TASK_ID
[HARNESS_COMMAND] task-ledger update TASK_ID --status STATUS --evidence RECORD
[HARNESS_COMMAND] goal-ledger status TASK_ID
[HARNESS_COMMAND] goal-ledger complete TASK_ID GOAL_ID --evidence RECORD_OR_ARTIFACT
[HARNESS_COMMAND] goal-ledger defer TASK_ID GOAL_ID --reason TEXT --future-task TASK_ID
[HARNESS_COMMAND] write-receipt ...
[HARNESS_COMMAND] task-retrospective ...
```

## Required workflow

```text
H9-AGENT-COMMAND-CONTRACT
1. Ask the harness for the current task.
2. Read the task manifest and TDDs.
3. Run preflight before implementation.
4. Make only allowed edits.
5. Run scope and budget audits.
6. Run local tests.
7. Record phase evidence through commands.
8. Never hand-write ledger or receipt state.
9. Do not mark a task complete until the goal coverage gate passes.
```

## Do not

```text
do not hand-write receipt JSON
do not hand-write roadmap status
do not hand-write goal status
do not infer next task from memory
do not claim completion without evidence
do not modify protected artifacts
```

## Project-specific placeholders

```text
[HARNESS_COMMAND]
[PROJECT_TEST_COMMANDS]
[PROJECT_CI_PROVIDER]
[PROJECT_PACKAGE_MANAGER]
[PROJECT_ALLOWED_PATHS]
[PROJECT_PROTECTED_ARTIFACTS]
```

## Acceptance criteria

- The copied guidance keeps the H9-NO-MANUAL-STATE rule intact.
- The copied guidance includes task ledger and goal ledger commands.
- The copied guidance includes project-specific placeholders.
- The copied guidance mentions the H9-GOAL-COVERAGE-GATE.

## Definition of Done

Acceptance tests must guarantee:

- `test_copyable_guidance_includes_no_manual_state_rule`
- `test_copyable_guidance_includes_task_ledger_commands`
- `test_copyable_guidance_includes_goal_ledger_commands`
- `test_copyable_guidance_includes_project_placeholders`

Documentation checks must guarantee:

- this document has no KoteKomi-only product requirement
- this document contains H9-COPYABLE-GUIDANCE
- this document can be copied without losing the deterministic recordkeeping rule
