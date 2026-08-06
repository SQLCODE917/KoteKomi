# H7: Receipt Writer

## Intent

H7 adds a flat `kotekomi-agent write-receipt` command that standardizes agent proof-chain receipts.

The command is a disciplined proof-chain primitive. It writes deterministic, schema-checked JSON records for task lifecycle events, but it does not orchestrate lifecycle actions. It must not create commits, switch branches, push, call GitHub, run tests, or clean the worktree.

## Command

```bash
kotekomi-agent write-receipt
```

The command remains flat to match the existing CLI shape:

```bash
kotekomi-agent validate-task
kotekomi-agent preflight-task
kotekomi-agent scope-audit
kotekomi-agent budget-audit
kotekomi-agent lifecycle-check
kotekomi-agent write-receipt
```

## Required options

```text
--task-id TEXT
--record-kind TEXT
--result TEXT
--output PATH
```

## Repeatable options

```text
--input-record NAME=PATH
--artifact NAME=PATH
--field KEY=VALUE
```

## Optional behavior flags

```text
--force
```

## Receipt payload

A receipt is canonical JSON with sorted keys, two-space indentation, and a final newline. The writer prints a small JSON result to stdout containing the written path and receipt SHA-256.

A minimal receipt contains:

```json
{
  "schema_version": 1,
  "task_id": "harness-07-task-receipt-writer",
  "record_kind": "candidate-commit",
  "result": "candidate_committed",
  "created_at": "2026-08-06T00:00:00+00:00",
  "git": {
    "branch": "main",
    "head": "REVISION",
    "parents": ["REVISION"],
    "worktree_clean": true
  },
  "input_records": {},
  "artifacts": {},
  "fields": {}
}
```

`created_at` is the only intentionally time-varying field. All other field ordering and formatting must be deterministic.

## Input records

Each `--input-record NAME=PATH` entry must point to an existing file. The writer records the path as supplied and the SHA-256 of that file:

```json
"input_records": {
  "candidate-ci": {
    "path": "/path/to/candidate-ci.json",
    "sha256": "..."
  }
}
```

Input record names must be non-empty and unique.

## Artifacts

Each `--artifact NAME=PATH` entry must point to an existing file. The writer records the path as supplied and the SHA-256 of that file:

```json
"artifacts": {
  "manifest": {
    "path": ".agent/tasks/harness-07-task-receipt-writer.toml",
    "sha256": "..."
  }
}
```

Artifact names must be non-empty and unique.

## Fields

Each `--field KEY=VALUE` entry records a string scalar in `fields`. Field keys must be non-empty and unique. Field values are strings. H7 intentionally avoids nested ad hoc field encoding; richer receipt shapes can be added later as typed receipt writers.

## Git state

When the command runs inside a Git worktree, the receipt includes:

```text
branch
head
parents
worktree_clean
```

`parents` is the parent list for `HEAD`. Merge commits therefore have two parents. Initial commits have an empty parent list.

When the command runs outside a Git worktree, the command should still be able to write a receipt, with the git object indicating that no worktree was detected. H7 acceptance focuses on in-repository behavior.

## Overwrite policy

The command refuses to overwrite an existing output file unless `--force` is provided. On refusal it exits nonzero and must not change the existing file.

## Side-effect boundary

Allowed side effects:

```text
- create or overwrite the requested output receipt when allowed
- create parent directories for the requested output path
- write stdout/stderr
```

Forbidden side effects:

```text
- git commits
- branch changes
- pushes
- GitHub API calls
- test execution
- modifying files other than the requested receipt
- cleaning or staging the worktree
```

## Acceptance tests

The protected acceptance test covers:

1. `write-receipt --help` exposes the command and core options.
2. A minimal receipt is canonical JSON and stdout reports its SHA-256.
3. Existing receipt files are not overwritten without `--force`.
4. `--force` permits overwrite.
5. Input record and artifact paths are validated and hashed.
6. Missing input record or artifact paths are rejected.
7. Dirty worktree state is reported without being changed.

## Implementation scope

Allowed production files:

```text
packages/devtools/src/kotekomi_devtools/cli.py
packages/devtools/src/kotekomi_devtools/receipt_writer.py
```

Allowed test file:

```text
packages/devtools/tests/unit/test_receipt_writer.py
```

The protected acceptance file and this TDD must not be changed by the candidate.
