# H9 Retrospective Accountability TDD

Searchable labels: H9-RETROSPECTIVE-ACCOUNTABILITY, H9-FAILURE-CLASSIFICATION, H9-CI-METRICS, H9-GOAL-REPORT, H9-DOGFOOD.

## Purpose

H8 added task-retrospective, but its own H8 retrospective undercounted CI success for H8 receipts. H9 must refine retrospective accountability and use goal reporting to prevent missed goals.

## Design

```text
H9-DOGFOOD
[H9 Declared Goals] -> [Goal Ledger] -> [Implementation Through Harness] -> [Receipts + CI + Checks] -> [Task Retrospective] -> [Goal Report] -> [Completion Gate]
```
Metrics to refine include H9-CI-METRICS, H9-FAILURE-CLASSIFICATION, and H9-GOAL-REPORT.

## Acceptance criteria

- Retrospective CI extraction recognizes H8-style main-ci, candidate-ci, and specification-ci receipts.
- Retrospective output reports failure classifications when receipts contain known failure record kinds.
- Goal report compares declared goals against delivered evidence.
- H9 final retrospective must include goal coverage.
- H9 cannot complete with in-scope goals missing evidence.
- Deferred goals must name future tasks H10-H14 when applicable.

## Definition of Done

Acceptance tests must guarantee:

- `test_retrospective_counts_h8_style_ci_records`
- `test_retrospective_classifies_budget_failure`
- `test_retrospective_classifies_lifecycle_invocation_bug`
- `test_goal_report_lists_unmet_goals`
- `test_h9_dogfood_goal_report_allows_completion_only_when_accounted`

Unit tests must guarantee:

- `test_ci_metric_extractor_accepts_result_field`
- `test_ci_metric_extractor_accepts_github_actions_artifact`
- `test_failure_classifier_maps_budget_record`
- `test_failure_classifier_maps_lifecycle_record`
- `test_goal_report_links_evidence_records`
