# H5 — Oracle Fixture Toolkit

## Status

This TDD defines the H5 leaf task.

H5 starts from main commit `63fa7cae7c4a5f03619ceeec953aee7fbf7eea53`.

H4 is complete and is available on main.

## Problem

The H2 and H4 harness work exposed oracle defects in Git-backed acceptance tests.

The H2 class is an unsafe fixture write.

A test writes a fixture file without guaranteeing that the parent directory exists.

The H4 class is an unsafe Git baseline.

A test captures an index hash before running a helper that can refresh Git index metadata.

These defects are test-oracle defects.

They are not production behavior defects.

The acceptance test suite repeats the same fixture and Git helper patterns across H2, H3, and H4 tests.

That repetition makes new oracle defects likely.

## Inspection evidence

The H5 inspection record is stored outside the repository at:

`~/.local/state/kotekomi/experiments/harness-05-oracle-fixture-toolkit/acceptance-fixture-inspection.json`

The inspection found:

```text
acceptance_file_count: 4
raw_write_text_occurrence_count: 6
git_subprocess_occurrence_count: 40
status_index_occurrence_count: 32
json_command_occurrence_count: 40
write_sites_without_nearby_parent_mkdir_count: 2
repeated_helper_name_count: 15
repeated_helper_body_count: 2
```

The repeated helper names include:

```text
_assert_result
_cli
_create_ready_repo
_diagnostic
_git
_git_output
_index_sha
_payload
_render_manifest
_run
_sha256_file
_status
_toml_value
_write
```

## Goal

Create a shared, test-only oracle fixture toolkit for Git-backed acceptance tests.

Use the toolkit to remove repeated unsafe helper patterns from the H2, H3, and H4 acceptance tests.

Add a static guard that prevents the same unsafe write pattern from re-entering Git-backed protected acceptance fixtures.

## Non-goals

Do not change production CLI behavior.

Do not change the task manifest schema.

Do not modify H1 acceptance tests unless the change is only needed to keep imports or formatting valid.

Do not rewrite all acceptance tests for style.

Do not change existing receipts except the new H5 receipt.

Do not change H1, H2, H3, or H4 protected fixture receipts.

## Design

Add this test-only helper module:

```text
packages/devtools/tests/acceptance/_oracle_fixtures.py
```

The helper module owns the repeated acceptance-test primitives.

The implementation tests call these helpers instead of local ad hoc helpers.

The module must not be imported by production code.

### Required helper API

The helper module must expose these functions:

```text
write_fixture_text(path, text)
sha256_file(path)
run_command(cwd, args, expected_exit_code=None)
run_json_command(cwd, args, expected_exit_code=0)
git(repo, *args)
git_output(repo, *args)
init_git_repo(repo)
status_short(repo)
index_sha(repo)
status_then_index_baseline(repo)
assert_status_and_index_unchanged(repo, baseline)
protected_artifact(path, kind)
render_manifest(data)
```

### `write_fixture_text`

`write_fixture_text` writes UTF-8 text.

It creates the parent directory before writing.

It replaces direct `Path.write_text` in Git-backed acceptance fixtures.

### `status_then_index_baseline`

`status_then_index_baseline` must run status normalization before it reads the index hash.

This prevents the H4 oracle defect class.

The returned baseline must be suitable for `assert_status_and_index_unchanged`.

### `run_json_command`

`run_json_command` must run a command from a chosen working directory.

It must parse stdout as JSON.

It must return the process exit code and JSON payload.

It must include enough stderr/stdout detail in assertion failures to debug failed commands.

### `protected_artifact`

`protected_artifact` must produce a dictionary with:

```text
kind
path
sha256
```

The `sha256` value is the SHA-256 digest of the artifact file.

### `render_manifest`

`render_manifest` must render a deterministic TOML manifest text for test fixtures.

The output must be stable between runs.

The helper only needs to support the value types used by the H2, H3, H4, and H5 acceptance fixture manifests.

## Migration requirement

The H2, H3, and H4 acceptance tests must use `_oracle_fixtures.py` where applicable.

The migrated tests must not contain direct `.write_text(` calls.

The migrated tests must not define local duplicate helpers where the shared helper exists.

This rule applies to:

```text
packages/devtools/tests/acceptance/test_task_preflight_contract.py
packages/devtools/tests/acceptance/test_task_budget_audit_contract.py
packages/devtools/tests/acceptance/test_task_scope_audit_contract.py
```

## Static guard

The H5 acceptance test must fail when direct `.write_text(` exists in the Git-backed acceptance fixture tests.

The H5 acceptance test must fail when those tests do not import the shared toolkit.

The static guard is intentionally narrow.

It only covers the Git-backed acceptance fixture tests listed above.

## Allowed implementation paths

The candidate may change only these paths:

```text
packages/devtools/tests/acceptance/_oracle_fixtures.py
packages/devtools/tests/acceptance/test_task_preflight_contract.py
packages/devtools/tests/acceptance/test_task_budget_audit_contract.py
packages/devtools/tests/acceptance/test_task_scope_audit_contract.py
```

The H5 acceptance test is a protected specification artifact.

The candidate must not modify it.

## Acceptance

The H5 candidate must satisfy:

```text
PYTHONDONTWRITEBYTECODE=1 uv run pytest -p no:cacheprovider packages/devtools/tests/acceptance/test_oracle_fixture_toolkit_contract.py
PYTHONDONTWRITEBYTECODE=1 uv run pytest -p no:cacheprovider packages/devtools/tests/acceptance/test_task_scope_audit_contract.py
PYTHONDONTWRITEBYTECODE=1 uv run pytest -p no:cacheprovider packages/devtools/tests/acceptance/test_task_budget_audit_contract.py
PYTHONDONTWRITEBYTECODE=1 uv run pytest -p no:cacheprovider packages/devtools/tests/acceptance/test_task_preflight_contract.py
uv run pytest packages/devtools/tests/acceptance/test_task_manifest_contract.py
uv run pytest packages/devtools/tests/unit
uv run ruff check
uv run pyright
```

Before the implementation exists, the H5 acceptance test must skip all H5 behavior checks.

After the implementation exists, the H5 acceptance test must pass.

## Budget

This is a test-only refactor.

Actual production files changed must be 0.

Actual production diff lines must be 0.

The manifest budget uses the lowest schema-valid production limits because the manifest schema requires positive budget values.

Allowed paths and stop conditions enforce the zero-production-change rule.

Maximum test files changed: 4.

Maximum test diff lines: 800.

The candidate should simplify before handoff if the test diff exceeds 700 lines.

## Stop conditions

Stop if production files are changed.

Stop if the task manifest schema changes.

Stop if H1, H2, H3, or H4 receipts change.

Stop if the H5 protected acceptance test changes.

Stop if H2, H3, or H4 acceptance behavior changes instead of only moving fixture mechanics into the shared helper.

Stop if static guard scope expands beyond Git-backed acceptance fixture tests.

## Expected output

The candidate output must include:

```text
changed paths
helper API implemented
migration summary by test file
static guard result
acceptance results
budget result
```
