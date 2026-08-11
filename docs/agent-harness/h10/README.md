# H10: Verification Execution Accountability

## Goal

H10 turns the H9-followup verification planner from an advisory planning tool into an auditable execution loop.

H9-followup made the required checks deterministic. H10 makes the act of running those checks deterministic and inspectable. The harness should be able to answer:

1. What checks were required?
2. Which exact commands were run?
3. Did every required check run successfully?
4. What logs and digests prove the result?
5. Did the agent avoid substituting, omitting, or manually inferring checks?

## Background

H9 exposed a missing-check failure: a shared CLI change missed an older exact-output/lifecycle contract. H9-followup added `kotekomi-agent verification-plan` so required checks are derived from changed paths, retained checks, quality gates, and manifest checks.

The remaining gap is execution accountability. A plan can be produced correctly but still be ignored, partially executed, or manually summarized. H10 closes that gap by adding deterministic check-run records and a deterministic plan-completion verifier.

## Scope

H10 is scoped to devtools harness accountability.

Expected production paths:

- `packages/devtools/src/kotekomi_devtools/cli.py`
- `packages/devtools/src/kotekomi_devtools/verification_execution.py`
- Optional narrow support in existing harness modules if needed.

Expected tests:

- `packages/devtools/tests/acceptance/test_verification_execution_contract.py`
- `packages/devtools/tests/unit/test_verification_execution.py`

H10 should not redesign the task manifest, scope audit, budget audit, lifecycle checker, receipt writer, or verification planner. It should compose with them.

## Initial command shape

H10 should add two deterministic commands:

```bash
uv run kotekomi-agent run-check CHECK_ID \
  --output CHECK_RECORD_JSON \
  --log CHECK_LOG \
  -- COMMAND [ARGS...]

uv run kotekomi-agent verify-checks PLAN_JSON \
  --run-record CHECK_RECORD_JSON \
  --run-record CHECK_RECORD_JSON \
  --output JSON \
  --markdown MARKDOWN
```

`run-check` records the exact argv, exit code, log path, log SHA-256, start/end timestamps, duration, and status for one check.

`verify-checks` consumes the `verification-plan` JSON and one or more check-run records. It fails closed if any planned check is missing, failed, duplicated, command-mismatched, or malformed.

## Dogfood rule

H10 must dogfood H9-followup:

```text
Run the deterministic verification-plan command.
Run every required check it returns.
Do not manually infer, omit, or replace checks.
Record check execution through H10 verification-execution commands.
```

## Non-goals

H10 does not introduce a long-running CI service, remote execution system, task scheduler, or general-purpose workflow engine. It should remain a small local deterministic harness primitive.
