# H9 Task Ledger Accountability

Searchable labels: H9-HUB, H9-TASK-LEDGER, H9-GOAL-LEDGER, H9-DETERMINISTIC-RECORDING, H9-GOAL-COVERAGE-GATE, H9-PORTABLE-HARNESS, H9-DDD-BOUNDARY, H9-AGENT-COMMAND-CONTRACT, H9-RETROSPECTIVE-ACCOUNTABILITY.

## Purpose

H9 matures the Terra High implementation-agent harness after H1-H8. H1-H8 established manifest validation, preflight, scope and budget gates, protected oracle handling, lifecycle checks, receipts, and retrospective metrics. H9 adds durable goal accountability and deterministic task state.

The H9 rule is:

```text
Declared goals become durable obligations.
Implementation agents use deterministic harness commands for roadmap and record state.
The harness owns task state, goal state, evidence links, output formats, and completion gates.
```

H9 is not a product feature for KoteKomi. It is harness infrastructure that should eventually be portable to other projects.

## Hub links

- [Architecture](architecture.md)
- [Task ledger TDD](task-ledger-tdd.md)
- [Goal ledger TDD](goal-ledger-tdd.md)
- [Deterministic recordkeeping TDD](deterministic-recordkeeping-tdd.md)
- [Portable harness TDD](portable-harness-tdd.md)
- [Retrospective accountability TDD](retrospective-accountability-tdd.md)
- [Copyable AGENTS guidance](copyable-agents-guidance.md)

## H9 feature map

| Goal | Feature | In H9? | Detail document | Verification theme |
| --- | --- | --- | --- | --- |
| H9-G1 | Turn prose goals into tracked obligations | yes | goal-ledger-tdd.md | goal coverage tests |
| H9-G2 | Keep roadmap and status outside agent context | yes | task-ledger-tdd.md | task ledger state tests |
| H9-G3 | Prohibit manual record/status authoring by implementation agents | yes | deterministic-recordkeeping-tdd.md | deterministic command tests |
| H9-G4 | Document DDD architecture for the harness | yes | architecture.md | doc static tests |
| H9-G5 | Make harness guidance copyable to other projects | yes | portable-harness-tdd.md, copyable-agents-guidance.md | copyability doc tests |
| H9-G6 | Dogfood the harness while building H9 | yes | retrospective-accountability-tdd.md | H9 final goal report |
| H9-G7 | Implement scaffold-task | no, deferred | future H10 | future task reference |
| H9-G8 | Implement oracle self-check and oracle repair | no, deferred | future H11 | future task reference |
| H9-G9 | Redesign lifecycle CLI names | no, deferred | future H12 | future task reference |
| H9-G10 | Add Bash 3/POSIX compatibility gate | no, deferred | future H13 | future task reference |
| H9-G11 | Extract self-contained harness module | no, deferred | future H14 | future task reference |

## H9 top-level flow

```text
[Implementation Agent] H9-AGENT
        |
        | calls commands, does not hand-write state
        v
[Harness CLI] H9-AGENT-COMMAND-CONTRACT
        |
        +--> [Task Ledger API] H9-TASK-LEDGER
        +--> [Goal Ledger API] H9-GOAL-LEDGER
        +--> [Receipt Writer] H9-DETERMINISTIC-RECORDING
        +--> [Lifecycle Gates] H9-GOAL-COVERAGE-GATE
        +--> [Retrospective Metrics] H9-RETROSPECTIVE-ACCOUNTABILITY
        v
[Evidence Store] H9-EVIDENCE-LEDGER
```

## H9 accountability decision tree

```text
H9-GOAL-COVERAGE-GATE
Is every declared goal in the ledger?
  no  -> fail: h9.goal.missing
  yes -> continue
For each in-scope goal: evidence missing? -> fail: h9.goal.missing_evidence
For each deferred goal: reason or future_task missing? -> fail
For each out-of-scope goal: rationale missing? -> fail
```

## Agent rule

Implementation agents must not manually maintain records, roadmap state, goal status, or final summaries. They must invoke deterministic harness commands that create or update those artifacts.

## H9 must dogfood itself

H9 development must use the existing harness flow:

```text
spec docs -> manifest/acceptance -> preflight -> candidate -> audits -> CI -> merge -> cleanup -> retrospective -> goal report
```

H9 is complete only when the goal report proves every in-scope H9 goal is met and every deferred goal has a reason and a future task.

## Definition of Done

Acceptance tests must guarantee:

- `test_h9_goal_report_fails_for_missing_in_scope_evidence`
- `test_h9_goal_report_fails_for_deferred_goal_without_future_task`
- `test_h9_task_ledger_rejects_completion_with_open_goals`
- `test_h9_recordkeeping_commands_write_deterministic_outputs`
- `test_h9_docs_have_searchable_labels`
- `test_h9_hub_links_every_leaf_tdd`

Unit tests must guarantee:

- `test_goal_status_counts_are_deterministic`
- `test_goal_coverage_gate_reports_all_unmet_goals`
- `test_task_status_transition_requires_evidence`
- `test_markdown_report_is_stable`
- `test_json_report_is_sorted_and_stable`
