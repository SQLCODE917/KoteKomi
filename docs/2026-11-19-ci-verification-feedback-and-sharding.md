# CI Verification Feedback and Sharding

## Outcome

Get the first useful signal on a small PR without waiting for the full suite, and shorten the full gate without reducing coverage. This is a CI-only follow-up to [the harness pilot (PR #2)](https://github.com/SQLCODE917/KoteKomi/pull/2). Do not start implementation before that pilot is closed out and current `main` is checked for conflicts.

## Baseline

- The [green pilot PR job](https://github.com/SQLCODE917/KoteKomi/actions/runs/44534531754/job/135596335059?pr=2) on `155c00e` took 29m48s; `verify.sh` took 27m44s and PDF tool setup 1m48s.
- Earlier jobs with separate steps show [37m32s](https://github.com/SQLCODE917/KoteKomi/actions/runs/42880865063/job/130056455465) and [39m58s](https://github.com/SQLCODE917/KoteKomi/actions/runs/43014981509/job/130503677831) for pytest alone. The [paired push job](https://github.com/SQLCODE917/KoteKomi/actions/runs/44534519362/job/135596295526?pr=2) failed in PDF tool setup before tests; treat this separately from test runtime.

## MVP

1. Preserve `./scripts/verify.sh` as the one-command local full check. Factor it only enough for CI to run schema drift, Ruff format/lint, Pyright and a small deterministic smoke selection independently of APT or live inference. Give that job its own visible status; target five minutes or less to first useful feedback.
2. Use the existing pytest duration report, or collect timing/JUnit data if it is unavailable. Start with two or three explicit, timing-balanced pytest shards on separate runners. Install Poppler/qpdf only where tests need them; a shard must not pass by quietly skipping a test that previously ran. Keep real PDF and failure/retry coverage. Prefer plain GitHub Actions and pytest over a scheduler or custom runner.
3. Keep one stable aggregate CI result for the full gate. It must fail if a required component fails or its result is missing, cancelled or skipped. Retain the exact candidate/receipt SHA verification and main verification behavior. Do not change repository rules or weaken a gate to make the benchmark green.

## Acceptance evidence

- Add a lightweight regression proving that the configured pytest shards cover the baseline test collection exactly once, excluding only the intentional overlap with smoke. Compare collected node IDs and passed/failed/skipped counts under comparable conditions. Prove the aggregate cannot go green with a required shard missing or red.
- Run old and new verification on comparable revisions and runner class; report links, fast-signal time, longest required job, end-to-end required time and total runner minutes. Aim for at least 25% lower full-gate wall time; if it misses, show the bottleneck before expanding scope. Record APT/setup failures separately.
- Keep the implementation to CI wiring, the entry-point split, and coverage checks. No product behavior changes, test removals, or inference additions.

## Deferred

Eliminate duplicate feature-branch push/PR full runs only after verifying required-check settings and that candidate/receipt evidence and main verification still see the expected check on the exact SHA. Treat APT reliability as a separate follow-up only if it keeps blocking CI after this change. Neither is permission to change branch rules.
