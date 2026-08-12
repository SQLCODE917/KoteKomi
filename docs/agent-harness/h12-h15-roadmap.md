# Agent Harness Roadmap: H12-H15

## Purpose

H1-H11 established task manifests, lifecycle gates, verification planning, run-check execution records, verify-checks accountability, log integrity, and early lifecycle ergonomics. The next four tasks harden the remaining operator and harness failure modes observed while dogfooding those changes.

## H12: step-script safety

### Problem

The highest-friction failures in H10 and H11 came from generated local orchestration scripts, not from the target harness features. The failures included brittle patch anchors, dirty local candidate branches after failed attempts, invalid generated Python indentation, tests patched at the wrong helper layer, and repeated manual reset scripts.

### Goal

Add deterministic support for local step preflight, recovery, and failure recording so generated local scripts are safer and easier to resume.

### Outcome

Generated step scripts should invoke deterministic harness commands for preflight/recovery and should record machine-readable failure receipts when they stop.

## H13: CLI delimiter regression planner rule

### Problem

CLI dispatch and delimiter handling are fragile when command definitions change. Verification planning should automatically require CLI delimiter/dispatch tests when CLI entry points change.

### Goal

Extend the verification planner touched-path rules so changes to CLI dispatch surfaces require delimiter/dispatch contract checks.

### Outcome

A candidate touching CLI dispatch cannot claim verification readiness without the relevant CLI regression checks.

## H14: verification-plan coverage expansion

### Problem

Verification planning has useful touched-path rules but remains narrow. Documentation, AGENTS guidance, task lifecycle tests, and test-helper edits need more precise required checks.

### Goal

Expand verification-plan coverage for docs, AGENTS guidance, lifecycle code, receipt code, and devtools test-helper changes.

### Outcome

The plan is more complete and less dependent on operator judgment when changed paths cross harness subsystems.

## H15: receipt chain status command

### Problem

Operators still manually infer task progress from receipt files, branch state, remotes, and CI records. This is inconsistent with the harness principle that roadmap/accountability state should be deterministic.

### Goal

Add a deterministic command that summarizes a task's receipt chain, missing records, branch state, remote branches, worktree status, and next legal action.

### Outcome

At any point in a dogfood run, the operator can ask the harness for the task status instead of reconstructing progress by hand.

## Sequencing

1. H12 first because it reduces the failure cost of every later task.
2. H13 second because CLI dispatch regressions are high leverage and narrowly scoped.
3. H14 third because broader planner coverage benefits from safer scripts and stronger CLI planner tests.
4. H15 fourth because receipt-chain status can then cover the expanded harness flow.
