# H6: Task Lifecycle State Machine

## Status

Specification for implementation.

## Problem

H1 through H5 use this lifecycle:

```text
spec -> candidate -> verified -> main -> cleanup
```

The valid checks depend on the lifecycle phase.

`preflight-task` is valid at the execution base.
It is not valid after the candidate, verified, or main merge commits move `HEAD` past the execution base.

H4 and H5 both exposed this process hazard.
The harness needs a read-only command that tells the operator which lifecycle checks are valid for the current phase.

## Goal

Add this deterministic lifecycle checker:

```text
kotekomi-agent lifecycle-check MANIFEST --phase PHASE
```

The command reads the manifest and Git state.
The command does not mutate the repository.
The command does not call GitHub.
The command does not run acceptance tests.

## Non-goals

The command does not create branches.
The command does not delete branches.
The command does not push commits.
The command does not watch CI.
The command does not replace `scope-audit` or `budget-audit`.

## CLI

### Command

```text
kotekomi-agent lifecycle-check MANIFEST --phase PHASE
```

### Phase values

```text
spec
candidate
verified
main
```

### Optional arguments

```text
--base REV
--head REV
--worktree
--records-dir PATH
--main-base REV
--verified REV
```

## Output contract

The command writes compact JSON to stdout.

The JSON object has these fields:

```text
status
schema_version
task_id
phase
diagnostics
required_checks
observed_records
```

`schema_version` is `1`.

`status` is one of:

```text
ready
not_ready
invalid
```

`diagnostics` is a list.
Each diagnostic has these fields:

```text
code
location
rule
```

The command exits with status code `0` when `status` is `ready`.
The command exits with a non-zero status code when `status` is `not_ready` or `invalid`.

## Phase rules

### spec phase

The spec phase is ready when the manifest is valid and current `HEAD` equals the manifest execution base.

If current `HEAD` does not equal the execution base, return:

```text
status: not_ready
diagnostic code: task_lifecycle.head_not_execution_base
diagnostic rule: preflight_requires_execution_base
```

### candidate phase

The candidate phase is ready when:

```text
the manifest is valid
--base is present
exactly one of --head or --worktree is present
scope classification is clean
budget classification is within_budget
protected artifacts are unchanged
```

If `--base` is missing, return:

```text
status: invalid
diagnostic code: task_lifecycle.missing_revision_range
diagnostic rule: candidate_requires_base_and_head_or_worktree
```

If both `--head` and `--worktree` are present, return:

```text
status: invalid
diagnostic code: task_lifecycle.ambiguous_revision_range
diagnostic rule: candidate_requires_exactly_one_target
```

### verified phase

The verified phase is ready when the records directory contains these valid JSON files:

```text
candidate-commit.json
candidate-ci.json
```

If either record is missing, return:

```text
status: not_ready
diagnostic code: task_lifecycle.record_missing
diagnostic rule: verified_requires_candidate_records
```

The command only checks local files.
It does not verify GitHub state.

### main phase

The main phase is ready when:

```text
--head is a merge commit
first parent of --head equals --main-base
second parent of --head equals --verified
```

If the merge parents do not match, return:

```text
status: not_ready
diagnostic code: task_lifecycle.merge_parent_mismatch
diagnostic rule: main_requires_expected_merge_parents
```

## Required checks field

`required_checks` identifies the checks that are valid for the phase.

Examples:

```json
["validate-task", "preflight-task"]
["validate-task", "scope-audit", "budget-audit", "protected-artifacts"]
["candidate-commit-record", "candidate-ci-record"]
["merge-parents", "main-ci-record"]
```

## Observed records field

`observed_records` is a list.

For `verified`, it includes the candidate records it found.

For other phases, it can be an empty list.

## Implementation guidance

Add a new production module:

```text
packages/devtools/src/kotekomi_devtools/task_lifecycle.py
```

Update the CLI:

```text
packages/devtools/src/kotekomi_devtools/cli.py
```

Use existing manifest parsing and Git helpers where possible.

Do not duplicate the H3 and H4 public contracts.
Call existing read-only classification logic if it is available.
If the existing logic is too CLI-coupled, extract a small internal function without changing the external command behavior.

## Allowed production changes

```text
packages/devtools/src/kotekomi_devtools/cli.py
packages/devtools/src/kotekomi_devtools/task_lifecycle.py
```

## Allowed test changes

```text
packages/devtools/tests/unit/test_task_lifecycle.py
```

The H6 protected acceptance contract is part of the spec.
The implementation candidate must not modify it.

## Acceptance

The protected acceptance test is:

```text
packages/devtools/tests/acceptance/test_task_lifecycle_contract.py
```

The test is skipped before the lifecycle command exists.
The test must pass after implementation.

## Success criteria

H6 is successful when:

```text
lifecycle-check exists
spec phase reports the execution-base rule
candidate phase requires a revision range
candidate phase succeeds for a clean candidate diff
verified phase checks local record presence
main phase verifies merge parents
output is compact JSON
the command is read-only
H1-H5 retained tests still pass
```
