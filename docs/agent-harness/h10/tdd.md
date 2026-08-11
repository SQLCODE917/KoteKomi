# H10 TDD Plan

## Proposed files

Production:

```text
packages/devtools/src/kotekomi_devtools/verification_execution.py
packages/devtools/src/kotekomi_devtools/cli.py
```

Tests:

```text
packages/devtools/tests/acceptance/test_verification_execution_contract.py
packages/devtools/tests/unit/test_verification_execution.py
```

## Unit test cases

`verification_execution.py` should have pure parsing and validation functions with unit coverage for:

1. loading a plan and extracting planned checks,
2. loading run records,
3. matching run records to plan checks by id,
4. exact command matching,
5. missing check diagnostics,
6. failed check diagnostics,
7. duplicate check diagnostics,
8. malformed record diagnostics,
9. stable JSON payload construction,
10. stable Markdown rendering.

## Acceptance test cases

The acceptance suite should exercise the CLI as a user would:

1. `run-check` records a successful command and log digest.
2. `run-check` records a failing command and exits with that failure.
3. `verify-checks` returns ready when all planned checks have matching successful run records.
4. `verify-checks` exits nonzero and emits deterministic diagnostics when a planned check is missing.
5. `verify-checks` exits nonzero and emits deterministic diagnostics when a command differs.
6. `verify-checks` exits nonzero and emits deterministic diagnostics when a run record failed.
7. `verify-checks` emits stable Markdown.

## Fixture strategy

Tests should create tiny temporary plans and check records. They should not depend on network access, GitHub Actions, user shell configuration, or repository-global state.

The command run by `run-check` in acceptance tests should be small and portable, such as:

```bash
uv run python -c "print('ok')"
```

Failure tests should use a deterministic nonzero Python exit.

## Diagnostic code sketch

Suggested diagnostic codes:

```text
verification_execution.plan_invalid
verification_execution.record_invalid
verification_execution.check_missing
verification_execution.check_failed
verification_execution.check_duplicate
verification_execution.command_mismatch
verification_execution.extra_record
verification_execution.log_missing
verification_execution.log_digest_mismatch
```

## Output status sketch

`verify-checks` JSON should use:

```text
ready
not_ready
```

`run-check` JSON should use:

```text
passed
failed
record_error
```
