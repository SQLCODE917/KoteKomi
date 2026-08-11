# Verification Plan TDD

## Command

```bash
kotekomi-agent verification-plan MANIFEST --base BASE --head HEAD --output JSON --markdown MARKDOWN
```

## Intent

The verification planner computes the local checks required for a task revision. It removes path-sensitive check selection from agent memory.

## Inputs

- `MANIFEST`: task manifest path.
- `--base BASE`: base revision.
- `--head HEAD`: head revision.
- `--output JSON`: JSON output path.
- `--markdown MARKDOWN`: Markdown output path.

## JSON output

The command writes a deterministic JSON object:

```json
{
  "status": "ready",
  "schema_version": 1,
  "task_id": "harness-09-followup-retrospective-verification-plan",
  "base_revision": "BASE",
  "head_revision": "HEAD",
  "changed_paths": [
    "packages/devtools/src/kotekomi_devtools/cli.py"
  ],
  "checks": [
    {
      "id": "task-manifest-contract",
      "command": "uv run pytest -p no:cacheprovider packages/devtools/tests/acceptance/test_task_manifest_contract.py",
      "reason": "cli.py touched; exact-output CLI contract must be retained",
      "source": "touched-path"
    }
  ],
  "diagnostics": []
}
```

`checks` must be sorted deterministically by check id.

## Markdown output

The Markdown report includes:

- task id,
- base revision,
- head revision,
- changed paths,
- required checks,
- reason for each check,
- diagnostics.

## Required sources of checks

The planner combines:

1. Manifest-declared acceptance checks.
2. Manifest-declared retained checks.
3. Shared touched-path rules.
4. Required quality checks: `ruff` and `pyright`.

## Initial touched-path rule table

| Path glob | Required checks |
| --- | --- |
| `packages/devtools/src/kotekomi_devtools/cli.py` | `test_task_manifest_contract.py`, `test_task_preflight_contract.py`, manifest command-specific acceptance tests, retained acceptance tests, `ruff`, `pyright` |

The rule table is intentionally small. It should grow only when a shared harness path has a clear, recurring cross-cutting contract.

## Fail-closed behavior

The planner must not silently return an incomplete plan. It emits a deterministic diagnostic when a changed path is neither:

- included in manifest `allowed_paths`, nor
- covered by a shared touched-path rule, nor
- a protected artifact frozen by the manifest.

Example diagnostic:

```json
{
  "code": "verification_plan.uncovered_changed_path",
  "location": "/changed_paths/0",
  "rule": "changed_paths_require_manifest_or_shared_rule"
}
```

## Determinism requirements

- Stable JSON key order.
- Stable check ordering.
- Stable Markdown ordering.
- No timestamps.
- No environment-specific absolute paths in outputs.
