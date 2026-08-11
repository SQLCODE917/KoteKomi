# H9 Follow-up: Retrospective and Verification Plan

Status: draft TDD for `harness-09-followup-retrospective-verification-plan`.

## Purpose

H9 delivered deterministic task and goal accountability. The follow-up captures what the H9 harness run taught us before starting H10, and converts the most important process lesson into a deterministic command.

The key decision is to add a low-maintenance verification planner instead of expanding agent instructions. Agents should not memorize path-sensitive test rules. The harness should compute them.

## Scope

This follow-up includes:

1. A written H9 retrospective.
2. A deterministic `verification-plan` command.
3. Minimal AGENTS guidance that tells agents to run the planner and follow its output.
4. Documentation for post-merge preflight semantics.
5. Documentation for the correct main lifecycle invocation.
6. An H10 readiness checklist.

## Non-goals

This follow-up does not implement H10 scaffolding, redesign lifecycle commands broadly, extract the harness as a portable module, or reopen H9 implementation.

The lifecycle CLI ergonomics exposed by H9 should be treated as input to a later lifecycle-redesign task. This follow-up documents the correct invocation and preserves deterministic records.

## Design decision

Use deterministic planning over expanded prose guidance.

The H9 CI miss was not a lack of agent effort. The local gate set did not automatically expand when `packages/devtools/src/kotekomi_devtools/cli.py` changed. That is a harness rule, not an agent-memory rule.

AGENTS guidance should stay short:

```text
Run the deterministic verification-plan command.
Run every required check it returns.
Do not manually infer, omit, or replace checks.
```

## Acceptance criteria

### AC1: H9 retrospective exists

`docs/agent-harness/h9-followup/retrospective.md` records what worked, what failed, and what changed in the harness process.

### AC2: Verification planner exists

A command exists:

```bash
kotekomi-agent verification-plan MANIFEST --base BASE --head HEAD --output JSON --markdown MARKDOWN
```

It inspects changed paths between `BASE` and `HEAD`, emits deterministic JSON and Markdown, and explains why every check is required.

### AC3: CLI touched-path expansion exists

When `packages/devtools/src/kotekomi_devtools/cli.py` changes, the plan includes the exact-output CLI regression checks:

```text
packages/devtools/tests/acceptance/test_task_manifest_contract.py
packages/devtools/tests/acceptance/test_task_preflight_contract.py
```

It also includes manifest-declared command-specific acceptance tests, retained acceptance tests, `ruff`, and `pyright`.

### AC4: Planner is fail-closed

A changed path that is neither covered by manifest scope nor by a shared touched-path rule produces a deterministic diagnostic instead of a silently incomplete plan.

### AC5: Main lifecycle invocation is documented

The correct main lifecycle form is documented:

```bash
kotekomi-agent lifecycle-check MANIFEST \
  --phase main \
  --main-base MAIN_BASE \
  --verified VERIFIED_CANDIDATE \
  --head MAIN_MERGE
```

### AC6: Post-merge preflight semantics are documented

`preflight-task` is an execution-base check. It is not a post-merge gate unless HEAD is intentionally at the task execution base.

### AC7: H10 readiness checklist exists

`docs/agent-harness/h9-followup/h10-readiness.md` defines the checklist to run before starting H10.
