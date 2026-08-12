# H13 TDD

## Red

Add an acceptance test that constructs a repository where `cli.py` changes and
asserts that `verification-plan` requires a CLI delimiter regression check.

Add or retain a delimiter acceptance test for `run-check` that passes
option-like command arguments after `--` and asserts the recorded argv preserves
them exactly.

## Green

Add a focused touched-path rule in `verification_plan.py` for CLI dispatch
changes that emits the delimiter regression check.

## Refactor

Keep the touched-path rule table compact. Do not encode every possible CLI
subcommand as a bespoke checklist item.
