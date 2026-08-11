# H10 Dogfood Plan

## Rule

H10 must use the H9-followup verification planner before selecting checks.

```bash
uv run kotekomi-agent verification-plan \
  .agent/tasks/harness-10-verification-execution-accountability.toml \
  --base BASE \
  --head HEAD \
  --output verification-plan.json \
  --markdown verification-plan.md
```

The required checks returned by that command are authoritative.

## Bootstrap sequence

H10 has one bootstrap exception: before `run-check` exists, the docs/spec work may use the existing shell-record pattern. Once candidate code creates `run-check`, H10 must use `run-check` for candidate verification checks where practical.

The final candidate verification must include `verify-checks` evidence.

## Required retained checks

H10 should retain these historical harness checks unless the manifest explicitly explains why not:

- H6 task lifecycle contract,
- H7 receipt writer contract,
- H8 task retrospective contract,
- H9 goal accountability contract,
- H9 task ledger contract,
- H9-followup verification-plan contract,
- task manifest contract,
- task preflight contract,
- repository static checks,
- repository type checks.

## Local/CI split

Local portable checks should stay focused and deterministic. Full repository pytest remains CI-authoritative unless the PDF/qpdf environment issue is normalized.

## Main merge

For main merge verification, use lifecycle main phase. Do not use post-merge preflight as the merge gate because preflight validates the manifest execution base.
