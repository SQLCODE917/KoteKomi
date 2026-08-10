# H9 Goal Ledger TDD

Searchable labels: H9-GOAL-LEDGER, H9-GOAL-STATUS, H9-GOAL-EVIDENCE, H9-GOAL-COVERAGE-GATE, H9-GOAL-DEFERRAL.

## Purpose

The goal ledger turns declared prose goals into tracked obligations. The implementation agent should not remember goal status. It should ask the harness.

## Design

```text
kotekomi-agent goal-ledger status TASK_ID
kotekomi-agent goal-ledger complete TASK_ID GOAL_ID --evidence RECORD_OR_ARTIFACT
kotekomi-agent goal-ledger defer TASK_ID GOAL_ID --reason TEXT --future-task TASK_ID
kotekomi-agent goal-check GOALS_FILE --records-dir RECORDS_DIR --output JSON --markdown MARKDOWN
```

```text
H9-GOAL-COVERAGE-GATE
For every declared goal: status missing? yes -> fail: h9.goal.status_missing
For every in_scope goal: evidence missing? yes -> fail: h9.goal.evidence_missing
For every deferred goal: reason or future_task missing? yes -> fail
```

## Acceptance criteria

- goal-check fails if an in-scope goal has no evidence.
- goal-check fails if a deferred goal lacks a reason.
- goal-check fails if a deferred goal lacks a future task.
- goal-check fails if an out-of-scope goal lacks a reason.
- goal-check emits deterministic JSON and Markdown.
- H9 cannot be completed unless all in-scope goals are met and all deferred goals have reason and future task.

## Definition of Done

Acceptance tests must guarantee:

- `test_goal_check_fails_when_in_scope_goal_has_no_evidence`
- `test_goal_check_fails_when_deferred_goal_has_no_reason`
- `test_goal_check_fails_when_deferred_goal_has_no_future_task`
- `test_goal_check_fails_when_out_of_scope_goal_has_no_reason`
- `test_goal_check_passes_when_all_goals_are_accounted_for`
- `test_goal_check_outputs_deterministic_json_and_markdown`

Unit tests must guarantee:

- `test_goal_coverage_counts_states`
- `test_goal_coverage_gate_lists_every_unmet_goal`
- `test_goal_evidence_ref_validates_record_sha`
- `test_goal_defer_requires_future_task_ref`
- `test_goal_report_markdown_is_stable`
