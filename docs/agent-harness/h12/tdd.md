# H12 TDD

## Public command shape

H12 should expose deterministic functionality through `kotekomi-agent`, using names that make local generated script intent explicit. Acceptable command shapes include one command with submodes or multiple focused commands, for example:

```bash
uv run kotekomi-agent step-preflight --task-id TASK --base BASE --branch BRANCH
uv run kotekomi-agent step-preflight --task-id TASK --base BASE --branch BRANCH --recover-candidate
uv run kotekomi-agent record-step-failure --task-id TASK --step STEP --reason REASON --output JSON
```

The final command names may differ, but the behavior must be deterministic and test-covered.

## Preflight contract

Preflight output must be JSON with at least:

- `status`
- `task_id`
- `branch`
- `head`
- `origin_main` or an injected origin-main equivalent in tests
- `worktree_status`
- `diagnostics`

Dirty worktrees must fail closed unless the requested mode explicitly and safely handles them.

## Recovery contract

Recovery mode must only reset a known candidate branch when all of these are true:

- current branch equals the expected candidate branch, or test-injected state is equivalent
- expected base is known
- dirty files are local failed-attempt artifacts
- `main` is not dirty

Dirty `main` must be refused by default.

## Failure receipt contract

A failed generated local step should produce a receipt or JSON record that includes:

- task id
- step id/name
- branch
- head
- failure reason
- optional log path or digest
- status indicating failure
- schema version

## Test strategy

Tests must not require GitHub, network, global repository state, commits, pushes, or branch switching. Use injected state or temporary repositories as needed.

## Dogfood requirement

The H12 implementation script should use the new deterministic preflight/recovery/failure recording commands once they exist. Before they exist, the spec step may use the existing scripted preflight pattern.
