# H9 Retrospective

## Summary

H9 showed that a docs-first harness can make a Terra high implementation effective, but only when the harness owns verification breadth and recordkeeping. The H9 design documents constrained the implementation. The manifest and protected acceptance tests constrained scope. GitHub Actions caught a shared CLI regression. Receipts preserved a full proof trail, including mistakes.

## What worked

### Docs-first design

The H9 design lived under `docs/agent-harness/h9` before implementation. That gave the implementation agent a bounded task: deterministic task ledger, goal accountability, and recordkeeping surfaces.

The final implementation stayed within scope and budget: three production files, two test files, and 531 production diff lines.

### Terra high as implementation agent

Terra high was effective when the harness provided:

- frozen design documents,
- a task manifest,
- allowed paths,
- protected acceptance tests,
- retained checks,
- deterministic recordkeeping.

The first candidate implemented the main H9 surfaces and passed H9-targeted acceptance, H9 unit tests, retained H8/H7 acceptance, `ruff`, and `pyright`.

### Deterministic receipts

The process recorded candidate verification, repair, main CI, corrected main lifecycle, main verification, and branch cleanup as receipts. This made the process auditable even when the first candidate CI and early lifecycle invocations failed.

## What failed or was inefficient

### Local verification missed a shared CLI regression

The initial local gate set did not include older exact-output acceptance tests when `packages/devtools/src/kotekomi_devtools/cli.py` changed. CI caught a JSON key-order regression in existing task manifest and preflight contracts.

This was a process gap, not a Terra-only failure. A shared harness file changed, but the local check selection did not expand to include all affected contracts.

### Lifecycle and preflight were easy to invoke incorrectly

`preflight-task` failed after the main merge because HEAD was no longer the task execution base. That is expected behavior, but the operational workflow treated it as a possible post-merge gate until the gap was recorded.

`lifecycle-check --phase main` also failed repeatedly when invoked with generic `--base` and `--head`. The correct main form requires `--main-base`, `--verified`, and `--head`.

## Lessons

1. Keep docs-first design for harness work.
2. Keep Terra high bounded by manifest scope and protected tests.
3. Do not rely on AGENTS prose for touched-path test selection.
4. Add deterministic touched-path verification planning.
5. Make lifecycle phase commands explicit in operational docs.
6. Treat preflight as execution-base only.
7. Preserve failure records; they are useful retrospective data.

## Process change

H9 follow-up adds a deterministic verification planner. The first rule is intentionally small:

```text
If packages/devtools/src/kotekomi_devtools/cli.py changes, include exact-output CLI acceptance tests.
```

This keeps maintenance low while preventing the exact H9 miss from recurring.
