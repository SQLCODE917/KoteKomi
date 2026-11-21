# Replay TUI Shutdown Agile Package

[Leaf TDD](2026-11-20-stabilize-replay-tui-shutdown.md) · [Blocked downstream PR #7](https://github.com/SQLCODE917/KoteKomi/pull/7)

## What PR #7 taught us

- **Keep:** The product slice stayed bounded. Review found the actual gap, and the implementer posted revised closeout without a separate prompt.
- **Improve acceptance:** The first mixed fixture depended on an ignored local database; passing commands hid the skips. Pin the concrete clean-checkout witness and require executed tests, not just a successful exit code.
- **Improve CI evidence:** The exact-SHA pull_request workflow was green while the push workflow on that same SHA was red. Check both before recommending merge. The aggregate verify failure was downstream of the pipeline shard, not a separate cause.

## Plan and checks against code

- **Derisk:** In the existing copy-before-source test, the worker gate is released in the same turn as context exit. Use explicit synchronization to control the failure ordering and make a red test, not a stress loop.
- **Lifecycle fix:** Trace `ReplayApp._run_operation`, `on_operation_finished`, and `action_quit`. Posting and handling completion are separate moments. Prove that normal completion is visible while mounted and a closing view cannot be updated by a late completion. Prefer the smallest lifecycle change supported by the witness.
- **Synthesize:** The same worker can complete normally or concurrently with quit. Both behaviors fit in one TDD and one test file. The two tests exercise opposite sides of the same boundary.

Land this independently on main. Then refresh the PR #7 spec against the repaired baseline before replaying the composition changes; do not merge main under its old pin. Reverify with fresh evidence, then move to PR #8.
