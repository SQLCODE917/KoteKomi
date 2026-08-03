# H3 Task Budget Audit

## Purpose

Add a deterministic Task Budget Audit command to `kotekomi-agent`.

H2 proved that a behavior-correct candidate can still violate the task budget.
The budget audit must become a reusable harness command instead of a bespoke shell script.

## Scope

Add a top-level CLI command:

`kotekomi-agent budget-audit MANIFEST --base REV --head REV`

and:

`kotekomi-agent budget-audit MANIFEST --base REV --worktree`

The command reads one Task Manifest, reads the manifest `budget` and `allowed_paths`, inspects a Git diff, and emits compact JSON.

The command does not write repository files.
The command does not stage files.
The command does not create records.
The command does not call GitHub.
The command does not run acceptance commands.

## Allowed implementation paths

- `packages/devtools/src/kotekomi_devtools/cli.py`
- `packages/devtools/src/kotekomi_devtools/task_budget.py`
- `packages/devtools/tests/unit/`

## Command behavior

The command has two modes.

Revision mode:

`kotekomi-agent budget-audit MANIFEST --base REV --head REV`

Worktree mode:

`kotekomi-agent budget-audit MANIFEST --base REV --worktree`

The command resolves `REV` arguments to full commit identifiers.

The command validates the Task Manifest before budget analysis.
If the manifest is invalid, the command returns status `invalid` and exits `2`.

The command classifies changed paths:

- `production` when the path starts with `packages/devtools/src/`
- `test` when the path starts with `packages/devtools/tests/`
- `other` otherwise

The command checks whether each changed path is covered by one manifest `allowed_paths` entry.

An allowed path covers a changed path when:

- the allowed path equals the changed path, or
- the allowed path ends with `/` and the changed path starts with that allowed path

The command counts:

- production file count
- test file count
- production diff lines

Production diff lines are added lines plus deleted lines for `production` paths only.

In worktree mode, tracked changes and untracked non-ignored files are included.
Untracked files count as additions with zero deletions.
Worktree mode must not use `git add -N`.
Worktree mode must not modify the Git index.

## JSON result

The JSON result fields appear in this order:

1. `status`
2. `schema_version`
3. `task_id`
4. `mode`
5. `base_revision`
6. `head_revision`
7. `budget`
8. `totals`
9. `path_stats`
10. `diagnostics`

Status values:

- `within_budget`
- `over_budget`
- `invalid`

Exit codes:

- `0` for `within_budget`
- `1` for `over_budget`
- `2` for `invalid`
- `70` for unexpected internal failure

`head_revision` is the resolved commit in revision mode.
`head_revision` is `WORKTREE` in worktree mode.

`path_stats` entries contain:

1. `path`
2. `category`
3. `added`
4. `deleted`
5. `diff_lines`

`path_stats` are sorted by path.

Diagnostics contain:

1. `code`
2. `location`
3. `rule`

Diagnostics are sorted by location, code, and rule.

Budget diagnostics:

- `task_budget.budget_violation` at `/budget/maximum_production_files` with rule `production_files`
- `task_budget.budget_violation` at `/budget/maximum_test_files` with rule `test_files`
- `task_budget.budget_violation` at `/budget/maximum_production_diff_lines` with rule `production_diff_lines`

Scope diagnostics:

- `task_budget.scope_violation` at `/path_stats/{index}/path` with rule `allowed_path`

## Acceptance oracle

The protected H3 acceptance suite is initially skipped while `budget-audit` is absent.

The candidate must make the suite run.
The candidate must produce all H3 acceptance tests passed and zero skipped.

The acceptance suite verifies:

- CLI help exists
- revision diff within budget
- no-change diff within budget
- production diff line overrun
- production file count overrun
- test file count overrun
- changed path outside `allowed_paths`
- multiple diagnostics sorted deterministically
- worktree tracked modifications
- worktree untracked files
- worktree read-only behavior
- deleted production file line counting
- sorted path statistics

## Budget

The candidate must remain within:

- maximum production files: 2
- maximum test files: 2
- maximum production diff lines: 360

The target production diff is 300 lines.
The model should simplify before finishing if production diff exceeds 320 lines.

## Stop conditions

Stop before committing if:

- any protected artifact changes
- H3 acceptance is skipped after implementation
- H3 acceptance fails
- H1 or H2 acceptance fails
- the budget audit candidate exceeds its own budget
- implementation escapes allowed paths
