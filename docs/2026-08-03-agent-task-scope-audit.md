# H4 Task Scope and Protected Artifact Audit

## Purpose

This task adds a deterministic scope audit command.

The command checks whether an agent candidate stayed inside the Task Manifest boundary.

The command checks whether protected artifacts were left unchanged.

The command is read-only.

The command does not create records.

The command does not run acceptance tests.

The command does not contact GitHub.

The command is a local gate used before a candidate commit is accepted.

## Command

The command name is `scope-audit`.

The revision form is:

```bash
kotekomi-agent scope-audit MANIFEST --base REV --head REV
```

The worktree form is:

```bash
kotekomi-agent scope-audit MANIFEST --base REV --worktree
```

The command validates the Task Manifest first.

If the manifest is invalid, the command emits compact JSON with status `invalid`.

If the manifest is invalid, the command exits 2.

If the audit is clean, the command exits 0.

If the audit finds a violation, the command exits 1.

Unexpected internal failures use the existing CLI guard and exit 70.

## Output

The command emits compact JSON to stdout.

The output object uses this field order:

```text
status
schema_version
task_id
mode
base_revision
head_revision
changed_paths
protected_artifacts
diagnostics
```

The `status` value is one of:

```text
clean
scope_violation
protected_artifact_violation
invalid
```

If there are no diagnostics, status is `clean`.

If there are only scope diagnostics, status is `scope_violation`.

If there is at least one protected artifact diagnostic, status is `protected_artifact_violation`.

If the manifest is invalid, status is `invalid`.

## Revision mode

Revision mode resolves `--base` and `--head` to full Git commit IDs.

Revision mode obtains changed paths from the Git diff between base and head.

Revision mode includes added, modified, deleted, and renamed paths as changed paths.

Revision mode checks protected artifact content at the head revision.

Revision mode does not require the working tree to match the head revision.

## Worktree mode

Worktree mode resolves `--base` to a full Git commit ID.

Worktree mode uses `WORKTREE` as `head_revision`.

Worktree mode includes tracked worktree changes.

Worktree mode includes staged changes.

Worktree mode includes untracked non-ignored files.

Worktree mode does not modify the Git index.

Worktree mode does not use `git add -N`.

Worktree mode checks protected artifact content from the working tree.

## Changed paths

A changed path is allowed when it equals an item in `allowed_paths`.

A changed path is allowed when an item in `allowed_paths` ends with `/` and the changed path starts with that item.

All other changed paths are scope violations.

A changed path entry contains:

```text
path
allowed
protected
```

Changed path entries are sorted by path.

The `protected` field is true when the path equals a protected artifact path.

## Protected artifacts

For each manifest protected artifact, the command checks existence.

For each manifest protected artifact, the command checks SHA-256 digest.

For each manifest protected artifact, the command checks whether the path changed between base and head.

For worktree mode, the command checks whether the path changed between base and the worktree.

A protected artifact entry contains:

```text
path
kind
exists
changed
expected_sha256
actual_sha256
```

Protected artifact entries are sorted by path.

If a protected artifact does not exist, `exists` is false and `actual_sha256` is null.

If a protected artifact exists, `exists` is true and `actual_sha256` is its SHA-256 digest.

## Diagnostics

A scope violation diagnostic has:

```text
code = "task_scope.scope_violation"
location = "/changed_paths/{index}/path"
rule = "allowed_path"
```

A protected artifact missing diagnostic has:

```text
code = "task_scope.protected_artifact_missing"
location = "/protected_artifacts/{index}/path"
rule = "protected_artifact_exists"
```

A protected artifact changed diagnostic has:

```text
code = "task_scope.protected_artifact_changed"
location = "/protected_artifacts/{index}/path"
rule = "protected_artifact_unchanged"
```

A protected artifact digest diagnostic has:

```text
code = "task_scope.protected_artifact_digest_mismatch"
location = "/protected_artifacts/{index}/actual_sha256"
rule = "protected_artifact_digest"
```

Diagnostics are sorted by location, then code, then rule.

## Implementation boundary

The implementation may change:

```text
packages/devtools/src/kotekomi_devtools/cli.py
packages/devtools/src/kotekomi_devtools/task_scope.py
packages/devtools/tests/unit/
```

The implementation must not change the H4 Task Manifest.

The implementation must not change this TDD.

The implementation must not change acceptance tests.

The implementation must not change existing receipts.

The implementation must not change protected artifacts.

## Acceptance

The H4 acceptance oracle must pass with 13 tests.

The H4 acceptance oracle must report zero skipped tests after the command exists.

The H3 acceptance oracle must still pass.

The H2 acceptance oracle must still pass.

The H1 acceptance oracle must still pass.

Devtools unit tests must pass.

Ruff must pass.

Pyright must pass.

Repository tests must pass.

## Budget

The implementation budget is:

```text
maximum_production_files = 2
maximum_test_files = 2
maximum_production_diff_lines = 430
```

The target production diff line count is 360.

Simplify before handoff if production diff line count exceeds 380.
