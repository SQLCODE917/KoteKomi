# H10 Acceptance Criteria

Task id: `harness-10-verification-execution-accountability`

## AC1: H10 documentation exists

H10 documentation must exist under `docs/agent-harness/h10/` and include:

- goal and background,
- acceptance criteria,
- TDD plan,
- dogfood plan,
- explicit H9/H9-followup lessons carried forward.

## AC2: H10 task manifest exists

A task manifest must be created at:

```text
.agent/tasks/harness-10-verification-execution-accountability.toml
```

The manifest must include protected H10 docs, retained H6/H7/H8/H9/H9-followup acceptance checks, scope and budget constraints, and explicit candidate paths.

## AC3: `run-check` command exists

A deterministic command must exist:

```bash
uv run kotekomi-agent run-check CHECK_ID \
  --output CHECK_RECORD_JSON \
  --log CHECK_LOG \
  -- COMMAND [ARGS...]
```

It must:

- run the provided command argv without shell reinterpretation,
- write combined stdout/stderr to the requested log path,
- write stable JSON to the requested output path,
- include check id, command argv, exit code, status, log SHA-256, start timestamp, end timestamp, and duration,
- return the wrapped command's exit code for failed commands,
- return zero only when the wrapped command exits zero and the record is written successfully.

## AC4: `verify-checks` command exists

A deterministic command must exist:

```bash
uv run kotekomi-agent verify-checks PLAN_JSON \
  --run-record CHECK_RECORD_JSON \
  --output JSON \
  --markdown MARKDOWN
```

It must:

- load the H9-followup `verification-plan` JSON,
- require one successful run record for every planned check id,
- verify each run record's command exactly matches the planned command,
- fail closed on missing, failed, duplicate, malformed, or command-mismatched records,
- emit stable JSON and stable Markdown,
- include deterministic diagnostic codes.

## AC5: Failure behavior is covered

Acceptance tests must cover at least:

- all checks present and successful,
- missing check,
- failed check,
- duplicate check id,
- command mismatch,
- malformed run record,
- unknown extra record.

Unknown extra records may be allowed only if the output explicitly reports them; they must not satisfy a planned check.

## AC6: Stable output is covered

JSON output must use stable ordering. Markdown output must be deterministic and suitable for a receipt artifact.

## AC7: H10 dogfoods `verification-plan`

The H10 candidate must run:

```bash
uv run kotekomi-agent verification-plan MANIFEST --base BASE --head HEAD --output JSON --markdown MARKDOWN
```

before selecting checks. Every returned required check must be run.

## AC8: H10 dogfoods `run-check` and `verify-checks`

After H10 candidate code exists, required checks should be executed through `run-check` where practical, and `verify-checks` must prove that the required checks from `verification-plan` were completed.

If a bootstrapping exception is needed before `run-check` exists, it must be documented in the candidate record and not carried into the final candidate verification.

## AC9: Minimal AGENTS guidance

`packages/devtools/AGENTS.md` may be updated only with compact operational guidance:

```text
Run verification-plan.
Run every required check through run-check.
Run verify-checks to prove every required check succeeded.
Do not manually infer, omit, or replace checks.
```

## AC10: Main verification uses lifecycle main phase

Post-merge verification must use:

```bash
uv run kotekomi-agent lifecycle-check \
  .agent/tasks/harness-10-verification-execution-accountability.toml \
  --phase main \
  --main-base MAIN_BASE \
  --verified CANDIDATE_COMMIT \
  --head MAIN_MERGE_COMMIT
```

`preflight-task` remains an execution-base check and must not be treated as the main merge gate.

## AC11: Branch cleanup and final receipt

After main CI and main lifecycle verification succeed, H10 remote/local work branches must be deleted and a final status receipt must record the complete state.
