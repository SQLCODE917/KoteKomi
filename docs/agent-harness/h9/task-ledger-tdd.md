# H9 Task Ledger TDD

Searchable labels: H9-TASK-LEDGER, H9-TASK-STATUS, H9-TASK-TRANSITION, H9-TASK-COMPLETION-GATE, H9-AGENT-COMMAND-CONTRACT.

## Purpose

The task ledger keeps roadmap and task state out of the implementation agent context. The agent asks deterministic commands for state and invokes deterministic commands for transitions.

## Design

```text
kotekomi-agent task-ledger current
kotekomi-agent task-ledger next
kotekomi-agent task-ledger status TASK_ID
kotekomi-agent task-ledger update TASK_ID --status STATUS --evidence RECORD
```

```text
H9-TASK-COMPLETION-GATE
Can TASK_ID be marked complete?
  has main-ci evidence? no -> fail: h9.task.main_ci_missing
  has cleanup evidence? no -> fail: h9.task.cleanup_missing
  goal coverage ready? no -> fail: h9.task.goals_unmet
  retrospective exists? no -> fail: h9.task.retrospective_missing
  otherwise -> update status to complete
```

## Acceptance criteria

- current returns exactly one current task or a deterministic diagnostic.
- next returns the next planned task using deterministic ordering.
- status TASK_ID returns task id, status, evidence, diagnostics, and next required action.
- update TASK_ID --status complete fails if in-scope goals are unmet.
- update TASK_ID --status complete fails if evidence is missing.
- re-running the same valid update is idempotent.

## Definition of Done

Acceptance tests must guarantee:

- `test_task_ledger_current_returns_single_task`
- `test_task_ledger_next_uses_deterministic_ordering`
- `test_task_ledger_status_reports_next_required_action`
- `test_task_ledger_update_rejects_missing_evidence`
- `test_task_ledger_update_rejects_unmet_in_scope_goals`
- `test_task_ledger_update_complete_is_idempotent`

Unit tests must guarantee:

- `test_task_status_transition_requires_allowed_previous_state`
- `test_task_status_transition_requires_evidence_ref`
- `test_task_completion_gate_requires_goal_coverage`
- `test_task_ledger_json_is_sorted_and_stable`
