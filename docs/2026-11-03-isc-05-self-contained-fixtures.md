# TDD: Self-Contained Test Fixtures and Subprocess Imports

- Status: Accepted
- Deliverable: ISC-05
- Parent: [Ingestion Stabilization](2026-11-03-ingestion-stabilization-agile-package.md)

## 1. User outcome

A developer runs the documented tests without adding shell-specific import paths.
A spawned worker imports the checkout under test.

## 2. Current behavior

`test_replay_cancellation.py` imported `example_profile` from another test module.
A spawned worker therefore needed the repository root on `sys.path`, and the documented
command had to prepend `PYTHONPATH=.`.
Without that variable five cancellation tests failed with
`ModuleNotFoundError: No module named 'packages'`.

## 3. Ownership

| Concern | Owner |
|---|---|
| Replay annotation fixture | `packages/pipelines/tests/support/replay_fixtures.py` |
| Child interpreter import paths | repository `conftest.py` |
| In-process test import paths | `[tool.pytest.ini_options] pythonpath` |

`conftest.py` derives the repository root from its own location, so it names this
checkout. It prepends the root and every package `src` directory to `PYTHONPATH` for child
interpreters only.

## 4. Preserved behavior

- Cancellation still reaps the worker and records the interruption.
- Cold start still starts the worker process.
- The R20 transition still drives the real worker against a real SQLite Ledger.
- Fixture text, coordinates, and validation stay unchanged.

## 5. Acceptance tests

| Check | Test |
|---|---|
| ISC-05-A | `PYTHONPATH= uv run pytest packages/pipelines/tests/test_replay_cancellation.py packages/pipelines/tests/test_replay_process_startup.py packages/pipelines/tests/test_r20_ingestion_transition.py -q` |
| ISC-05-B | each affected file runs alone and in the combined run |
| ISC-05-C | `conftest.py` derives child paths from its own checkout |
| ISC-05-D | the moved fixture keeps the same profile content and the replay assertions still pass |

## 6. Verification

- `uv run pytest packages/pipelines/tests/test_replay_reader.py
  packages/pipelines/tests/test_replay_snapshot.py -q`
- `uv run ruff format --check`, `uv run ruff check`, `uv run pyright` on changed files.
