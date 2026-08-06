# H8 Task Retrospective Metrics

## Task

Implement `kotekomi-agent task-retrospective`.

The command converts a task execution records directory into deterministic retrospective outputs:

```bash
kotekomi-agent task-retrospective RECORDS_DIR --output retrospective.json --markdown retrospective.md
```

H8 is an improvement of the H1-H7 harness functionality. It does not add a new product feature. It turns the evidence created by the harness into measurable planning, implementation, and retrospective metrics.

## Motivation

H1-H7 established the following capabilities:

- manifest validation
- task preflight
- budget audit
- scope audit and protected artifacts
- oracle fixture toolkit
- lifecycle phase checking
- deterministic receipt writing

Those capabilities enforce an agent SDLC. H8 measures how well that SDLC worked on a concrete task.

The H7 run showed why this is needed. H7 produced spec, CI, candidate, oracle-failure, oracle-repair, candidate-verification, main-merge, main-CI, cleanup, and final-summary records. The records are useful, but currently they need manual reading to answer:

- How many repair loops occurred?
- Did the plan constrain the candidate?
- Did Terra High stay in scope and budget?
- Were failures due to implementation, oracle, CI, or operator/tooling?
- Did protected artifacts remain intact?
- How much time elapsed between phases?
- Did cleanup finish?

H8 turns those questions into machine-readable metrics and a concise Markdown retrospective.

## Command

```bash
kotekomi-agent task-retrospective RECORDS_DIR --output JSON --markdown MARKDOWN [--task-id TASK_ID] [--allow-incomplete]
```

Arguments:

- `RECORDS_DIR`: directory searched recursively for `.json` records.
- `--output JSON`: path for deterministic machine-readable metrics.
- `--markdown MARKDOWN`: path for a human-readable retrospective.
- `--task-id TASK_ID`: optional filter. When present, records for other tasks are ignored.
- `--allow-incomplete`: permits partial historical records and broken local references, while surfacing diagnostics.

## Required behavior

The command must:

1. Read JSON records recursively from `RECORDS_DIR`.
2. Parse records with at least:
   - `schema_version`
   - `record_kind`
   - `task_id`
   - `result`
   - `created_at`
3. Verify referenced `input_records` and `artifacts` SHA-256 values when referenced paths exist locally.
4. Fail closed on malformed JSON, missing directories, and broken SHA chains unless `--allow-incomplete` is supplied.
5. Emit diagnostics for incomplete or invalid records.
6. Compute deterministic metrics:
   - records total
   - records by kind
   - records by result
   - first and last `created_at`
   - timeline duration seconds
   - candidate count
   - oracle failure count
   - oracle repair count
   - CI total and success count
   - cleanup completion status
   - changed paths
   - local check pass counts
   - budget totals and statuses where available
   - scope statuses where available
7. Emit JSON with `indent=2`, `sort_keys=True`, and a final newline.
8. Emit Markdown with a concise retrospective summary.
9. Perform no git mutation and no network access.

## Expected JSON shape

The exact schema may evolve, but the H8 acceptance contract requires these top-level keys:

```json
{
  "task_id": "harness-07-task-receipt-writer",
  "diagnostics": [],
  "records": {
    "total": 10,
    "by_kind": {},
    "by_result": {}
  },
  "timeline": {
    "first_created_at": "...",
    "last_created_at": "...",
    "duration_seconds": 3900
  },
  "events": {
    "candidate_attempts": 1,
    "oracle_failures": 1,
    "oracle_repairs": 1,
    "cleanup_complete": true
  },
  "ci": {
    "total": 2,
    "success": 2
  },
  "audits": {
    "scope_statuses": {},
    "budget_statuses": {},
    "production_diff_lines": 188
  },
  "checks": {
    "passed": 6
  },
  "changed_paths": []
}
```

## Acceptance requirements

Acceptance tests must prove:

- `task-retrospective --help` exposes `RECORDS_DIR`, `--output`, `--markdown`, `--task-id`, and `--allow-incomplete`.
- A fixture records tree produces deterministic JSON and Markdown outputs.
- A broken SHA chain fails closed by default.
- `--allow-incomplete` permits broken local references and emits diagnostics.
- `--task-id` filters mixed records correctly.
- The command does not mutate git state.

## Deferred improvement backlog

H8 should document, but not implement, the larger H1-H7 improvement backlog:

- H9: manifest/task scaffold generator.
- H10: oracle self-check and acceptance sanity checker.
- H11: lifecycle command semantics cleanup.
- H12: first-class oracle-repair and candidate-reapply commands.
- Generated harness script compatibility checks for macOS Bash 3 and POSIX shell constraints.

## Non-goals

H8 must not:

- add a database
- call GitHub
- call the network
- generate dashboards
- mutate git
- implement H9-H12
