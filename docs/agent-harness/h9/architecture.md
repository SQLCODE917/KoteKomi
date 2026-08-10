# H9 Harness Architecture

Searchable labels: H9-DDD-BOUNDARY, H9-TASK-LEDGER, H9-GOAL-LEDGER, H9-EVIDENCE-LEDGER, H9-QUALITY-GATE, H9-PORTABLE-HARNESS, H9-KOTEKOMI-ADAPTER.

## Purpose

This document defines the H9 domain model and architecture. The harness must become a coherent pipeline, not a set of glue scripts held together by operator memory.

## Bounded contexts

```text
[Task Specification] H9-TASK-SPECIFICATION
[Task Ledger] H9-TASK-LEDGER
[Goal Ledger] H9-GOAL-LEDGER
[Lifecycle Management] H9-LIFECYCLE
[Evidence Ledger] H9-EVIDENCE-LEDGER
[Agent Execution] H9-AGENT-EXECUTION
[Quality Gates] H9-QUALITY-GATE
[Retrospective Analytics] H9-RETROSPECTIVE-ACCOUNTABILITY
[Portability] H9-PORTABLE-HARNESS
```

## Aggregate roots and services

```text
TaskRun H9-TASK-RUN
TaskLedger H9-TASK-LEDGER
GoalLedger H9-GOAL-LEDGER
ReceiptSet H9-EVIDENCE-LEDGER
GoalCoverageGate H9-GOAL-COVERAGE-GATE
TaskCompletionGate H9-TASK-COMPLETION-GATE
ReceiptIntegrityService H9-EVIDENCE-INTEGRITY
RetrospectiveClassifier H9-RETROSPECTIVE-ACCOUNTABILITY
```

## Ports and adapters

```text
[Harness Core] H9-PORTABLE-HARNESS
        |
        +-- GitPort -> GitCliAdapter
        +-- CiPort -> GitHubActionsAdapter
        +-- FilePort -> LocalFilesystemAdapter
        +-- ClockPort -> SystemClockAdapter
        +-- HashPort -> Sha256Adapter
        +-- AgentPort -> TerraCodexAdapter
        +-- ReceiptPort -> JsonReceiptAdapter
        +-- CliPort -> ArgparseAdapter
```

The core domain must not depend on KoteKomi package paths. KoteKomi-specific path layout belongs in adapters or configuration.

## Pipeline architecture

```text
H9-PIPELINE
[Specification Freeze] -> [Goal Ledger Initialized] -> [Preflight + Goal Coverage Gate] -> [Terra Candidate Execution] -> [Scope/Budget/Oracle Checks] -> [Candidate CI + Evidence Ledger] -> [Main Merge + Main CI] -> [Retrospective + Goal Report]
```

## Acceptance criteria

- The implementation exposes domain functions that can be unit tested without invoking GitHub Actions or Terra.
- CLI commands delegate to domain/application services rather than embedding all rules in argparse handlers.
- KoteKomi-specific configuration is isolated from portable harness concepts.
- Goal coverage and task completion are separate domain gates.
- Record writing is performed through deterministic commands, not manual agent-authored files.

## Definition of Done

Acceptance tests must guarantee:

- `test_h9_architecture_docs_define_bounded_contexts`
- `test_h9_architecture_docs_define_ports_and_adapters`
- `test_h9_cli_uses_domain_services_for_goal_check`
- `test_h9_portable_core_does_not_require_kotekomi_paths`

Unit tests must guarantee:

- `test_goal_coverage_gate_is_pure_domain_logic`
- `test_task_completion_gate_blocks_unmet_goals`
- `test_receipt_integrity_service_reports_sha_mismatch`
- `test_retrospective_classifier_counts_failure_modes`
