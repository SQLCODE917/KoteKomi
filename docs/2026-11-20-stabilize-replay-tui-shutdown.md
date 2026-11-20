# Stabilize Replay TUI Shutdown

## User story

As a Ledger operator, I want to quit Replay while the background operation is still finishing, so I can exit cleanly without a screen update crashing after teardown.

## Evidence and scope

[PR #7's push job](https://github.com/SQLCODE917/KoteKomi/actions/runs/44776683169/job/136469169500) failed in `test_copy_before_source_arrives_reports_no_paragraph` when `on_operation_finished` called `_refresh_status` and Textual could no longer find `#status`. The [same signature predates #7](https://github.com/SQLCODE917/KoteKomi/pull/5#issuecomment-7027838794). The test currently releases its threaded worker as it leaves `run_test()`. The test and application must not rely on which finishes first.

## Acceptance

1. **Mounted control.** With the worker blocked on an explicit gate, pressing copy before any paragraph exists still reports “No paragraph is available to copy yet.” It leaves the clipboard untouched and does not request exit. Release the worker while the view is still live and observe that the UI actually processes completion and displays normal completion before leaving the test context. A worker returning or a message being posted is not proof of handler completion.
2. **Shutdown overlap.** Add a deterministic regression at the real ReplayApp lifecycle boundary. Coordinate the worker, completion delivery and UI teardown so a completion queued or released for a closing view cannot query detached widgets or raise `NoMatches`. Exercise quitting while work is in flight and preserve the existing cancel behavior and exit code 130. The mounted control must still show normal completion; blanket message suppression is not a fix. Use bounded synchronization and ensure test failures release worker gates.
3. **Portable evidence.** Run both cases from a clean checkout with tracked inputs; no timing sleeps, retries as acceptance, skip, xfail, workstation database, or inference. Capture the pre-fix failure for the controlled failing interleaving, and the same test passing on the fix. Record test names and executed counts. Keep the existing replay TUI suite green.

Keep changes in ReplayApp and its TUI tests. Do not change composition inspection, product data, pipeline CI, or the Harness. Use the existing candidate closeout in the same run. For this follow-up, wait for both push and pull_request workflows on the final receipt SHA; link both in closeout and report any failed, missing, or pending required check as a blocker. Leave merge to the operator.
