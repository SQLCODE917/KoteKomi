# Implementing a TDD

## Human at the terminal

Run one local command block per operator action.

Ask for the command output after each operator action.

Keep failed output as Harness evidence.

Run the Harness status command first.

```text
kotekomi-agent implement-tdd <tdd-path>
```

Treat the status record as the lifecycle authority.

Stop when the status reports a blocker.

Use the reported `next_action` and `producer_arguments`.

Resume the active run by repeating the same command. Use `--new-run` only after
the previous run is terminal. Use `--abandon-run <implementation-run-id>` only
when an operator has decided that a non-terminal run will not continue.

When the next action is `create_task_manifest`, create the manifest at `manifest_path`.

Use the task manifest schema and an existing manifest as the authoring contract.

Use the binding task identifier, TDD path, and TDD digest in that manifest.

Run `verification-plan`, `run-check`, and `verify-checks` for local verification.

Pass `--task-id` and `--run` from `producer_arguments` to every run-scoped
producer. Those commands write canonical evidence and update the run evidence
index; `--output` and `--markdown` are report copies, not evidence discovery.

Run `receipt-chain-status` before reporting completion.

After completion, run `tdd-metrics <tdd-path>` and then `tdd-score <tdd-path>`.

Use `tdd-metrics <tdd-path> --latest` or `--run <implementation-run-id>` only
when selecting one run. With no path or selector, metrics and scorecards cover
all known runs. Use `tdd-compare <tdd-path> <tdd-path>` for TDD inputs, or
repeat `--scorecard <scorecard-json>` for explicit scorecard records.

Report the requested and primary TDD paths, aliases, digest, task identifier, run identifier, lifecycle evidence, metrics path, and scorecard path.

## Agent with a checkout

An implementing agent that has the PR branch checked out runs the same commands directly.

It does not relay instructions through a human at the terminal.

It reports check results, the candidate receipt, or a concrete blocker on the PR.

## Candidate closeout on the same PR

A checked-out implementing agent owns pre-merge closeout in the existing Harness run.
Capture the product's red baseline before editing. Retain the exact test or probe and its output.
Pushing the candidate verification receipt starts closeout; it does not complete it.

1. Identify the CI workflow triggered by `pull_request` for the current PR, repository, and exact receipt commit SHA.
   Confirm that the PR head still equals that SHA before recording anything.
   A green `push` run is not a substitute.
2. For this handoff only, the agent may start one bounded
   [GitHub CLI wait](https://cli.github.com/manual/gh_run_watch) for the matching run:
   `gh run watch <run-id> --repo <owner/name> --exit-status`.
   Set a 30-minute deadline in the command runner. Do not loop in the model.
   If no matching run is visible, it is still pending at the deadline, or the local session cannot wait,
   post `waiting for CI` with the exact receipt SHA and run link if known. Resume the same run, not implementation, when woken.
   For failure, post the failed check and next action; do not record it as success.
3. Re-read GitHub's terminal workflow record. Verify repository, PR, workflow, event, head, and required jobs.
   Normalize the successful result to `{"schema_version":1,"head_sha":"<receipt-sha>","conclusion":"success"}` in a temporary file outside the checkout.
   Run `uv run kotekomi-agent record-candidate-ci --task-id <task-id> --run <run-id> --ci-result <file>`.
   Keep the existing state root; pass `--state-root <path>` if it differs from the default.
4. Re-run the same `implement-tdd` status command with the existing pin and no `--new-run`.
   Check that candidate CI is no longer missing and the next action is main promotion.
   Use `uv run kotekomi-agent evidence-index --task-id <task-id> --run <run-id>` to confirm the candidate CI producer.
   Leave the full receipt-chain and promotion closeout to the post-merge workflow.
   Post one PR closeout with baseline and final product results, controls, receipt SHA, successful PR CI run link,
   Harness run ID and recorded candidate CI, and any remaining action. Count review wakes, a wake to resume waiting for CI,
   and prompts that had to request closeout separately. Collect evidence without assuming a missing count was zero.
   Stop before main promotion. Only the operator decides to merge.

This exception applies only to the named candidate PR CI run.
The human-at-terminal workflow and long-running local and model work retain their existing rules.

## Review wake on the same PR

A review wake watches one enrolled PR for a versioned marker comment.
The listener is a foreground command.
The Mac must be awake and the listener must be running.
The listener reads GitHub with the existing `gh` authentication and writes no GitHub state.

Enroll one checkout, its current branch, the PR, the pinned specification commit, and one existing terminal Cline session ID.
Keep the state file outside the checkout.

```bash
uv run kotekomi-agent review-wake enroll \
  --state "$HOME/.local/state/kotekomi/review-wake/pull-11.json" \
  --checkout "$PWD" \
  --repo SQLCODE917/KoteKomi \
  --pr 11 \
  --branch spec/targeted-review-wake-refresh \
  --pin <full-lowercase-spec-sha> \
  --session-id <existing-terminal-cline-session-id> \
  --hub "$HOME/.local/share/monai/projects/<project-id>/cline/locks/hub/production.json" \
  --author <trusted-comment-author> \
  --operator <operator-login> \
  --harness-run <existing-harness-run-id>
```

Use `--replace` to rebind the same state file.
The rebind preserves delivered comment IDs.
Use `--authorize-shared-account` only when the operator explicitly authorizes a shared-account marker signal.
Without that flag, a marker whose author equals the operator produces a notification-only alert.

The review comment carries exactly one marker in addition to its human-readable text.

```html
<!-- kotekomi-review-request:v1 repo=SQLCODE917/KoteKomi pr=11 head=<reviewed-head-sha> pin=<pinned-spec-sha> -->
```

Run the listener in the foreground and poll every 30 seconds.

```bash
while true; do
  uv run kotekomi-agent review-wake check --state "$HOME/.local/state/kotekomi/review-wake/pull-11.json"
  sleep 30
done
```

Each poll prints one JSON object.
`status: processed` reports actionable `alerts`.
`status: suppressed` reports a closed PR or a checkout on the wrong branch.
`status: blocked` reports a GitHub or state read failure.
The alert `message` is fixed: `New review comment on your current PR: <comment URL>. Please check it.`
The listener never includes the comment body or command text in the alert.

The listener uses the declared `websockets==16.1` synchronous client with the local Cline Hub's v1 loopback protocol and the token from the enrolled discovery file.
It validates the negotiated `cline-hub-auth.<token>` subprotocol and fails closed when the selected subprotocol is missing or wrong.
It verifies the exact session ID, checkout, current branch, and idle status before sending.
Immediately before transmission it re-fetches the selected comment and PR, rechecks repository/PR membership, open state, current head, canonical pin, and shared-account authorization, and rechecks idle status after history preparation.
Before transmission it records the ordered message-ID prefix count and digest, then persists send intent.
It sends only the fixed alert plus the trusted comment link to that enrolled session.
Both transcript reads must name the enrolled session; a missing or foreign session identity blocks before send or remains unknown after send.
It sends the input once, then observes events and transcript samples under one 30-second monotonic receipt deadline.
The `run.started` correlation reads `payload.requestId` and requires the envelope session ID to match.
It requires the prefix to be unchanged and exactly one new user message with a single exact text block containing the fixed alert, confirmed by a subsequent stable sample.
Missing evidence is sampled again until the deadline; contradictory identity/history and duplicate receipts fail closed.
A historical match, assistant echo, tool result or mixed content, malformed wrapper, changed whitespace, changed prefix, or duplicate new alert cannot establish delivery.
The only accepted transport wrapper is `<user_input mode="act|plan|yolo">...</user_input>` around the entire exact alert.
A dedicated non-propagating transport logger suppresses library handshake records so tokens cannot reach DEBUG output.
A busy or unavailable target is queued and revalidated on a later poll.
An unproven session binding or unverifiable history is blocked, and an unconfirmed or ambiguous send becomes `unknown` without a blind retry.
Delivered, notified, blocked, unknown, and failed records are never replayed after restart.
The token stays in the discovery file; it is never passed as an argument or printed.
The listener does not spawn a task, press approvals, or change sandbox settings.
The enrollment records the existing Harness run ID.
The listener creates no second implementation lifecycle.

The state file holds the enrollment and one record per marker comment ID.
Restart the same command to resume.
A delivered or notified comment is not replayed.
A `sending` record becomes `unknown` and is not retried.
Stop the listener with Ctrl-C.

Use this command to inspect the retained alerts.

```bash
python3 -c 'import json,sys;print(json.dumps(json.load(open(sys.argv[1]))["alerts"],indent=2,sort_keys=True))' \
  "$HOME/.local/state/kotekomi/review-wake/pull-11.json"
```

## Start from one PR URL

Use this path when the handoff is a PR description and the branch is already fetched.

1. Read the single `## Current Handoff` section in the PR description.
   The section declares `Status`, `Spec commit`, `TDD`, and `Prerequisite`.
2. Extract the PR description to a file outside the checkout.
   Run this command from the checkout root.

   ```text
   gh pr view <pr-url> --json body --jq .body > "${TMPDIR:-/tmp}/kotekomi-handoff.md"
   ```

   An untracked file inside the checkout would dirty the worktree and block the Harness start.
3. Run the read-only preflight with `uv run`.

   ```text
   uv run kotekomi-agent handoff-preflight "${TMPDIR:-/tmp}/kotekomi-handoff.md"
   ```

   The preflight does not contact GitHub, write repository files, or start a run.
   It stops pickup when the handoff is missing, duplicated, blocked, malformed, or has a pending prerequisite.
   It stops pickup when the pin is not a full lowercase SHA, does not resolve, or is not an ancestor of `HEAD`.
   It stops pickup when the TDD or Task Manifest V2 is missing, does not bind the pin, or differs from the checkout.
   It stops pickup when the manifest task identifier is not the identifier the Harness derives from the pinned TDD.
4. Run the returned `start_command` only when the preflight reports `ready`.
   The command is `uv run kotekomi-agent implement-tdd <tdd-path> --specification-commit <full-sha>`.
5. Continue with the Harness status command and the human-at-the-terminal commands above.

## Current Handoff Authority

The PR description holds exactly one active handoff.

Comments can propose or explain a change; they cannot replace the handoff.

A replacement pin is an edit to the `Spec commit` field in the PR description.

A replacement TDD revision uses a new path, so the Harness derives a new task identifier and the old evidence remains valid.

Do not infer a pin from the branch tip and do not follow an older handoff in a comment.

When the author cannot update the PR description, stop pickup and report the blocker on the PR.

A comment is not the canonical fallback.

## Specification Source

A pushed specification branch that contains the TDD and Task Manifest V2 is a valid specification source.

The specification branch does not need to merge to `main` before implementation starts.

Select the immutable specification commit explicitly.

```text
kotekomi-agent implement-tdd <tdd-path> --specification-commit <full-sha>
```

The Harness requires the selected commit to be an ancestor of `HEAD`, a clean worktree, a matching TDD binding, byte-identical Task Manifest bytes, and a Task Manifest V2.

It records the selected commit, manifest digest, and existing non-`main` branch as the feature branch.

It does not create or push a new feature branch in this mode.

Later implementation commits and pushes do not change the persisted specification record.

The default command without `--specification-commit` retains the clean current-main path.

## Same-task implementation amendments

[Reduce Harness Coordination](../2026-11-27-reduce-harness-coordination.md) makes size budgets advisory.
`budget-audit` preserves cumulative counts and `over_budget` diagnostics, but returns zero for size-only excess.
Scope violations, invalid manifests, and protected-file changes still block the task.
A high count is review information, not a reason to abandon and recreate a run.

The planning authority can amend `allowed_paths` and `budget` for the same accepted behavior.
Commit and push the amended manifest on the existing feature branch while its agents and checks are idle.
Apply the amendment with one command:

```text
kotekomi-agent implement-tdd <tdd-path> --specification-commit <full-new-sha> --amend-reason "<reason>"
```

The command retains the existing task and run IDs.
It archives previous run evidence under `experiments/<task>/amendments/<run>/<new-sha>/` in the state root.
It invalidates current candidate, verification, CI, and promotion records and returns to the candidate phase.
Run fresh verification before asking for review or acceptance.
Repeating the same applied amendment preserves evidence produced afterward.
If an amendment is pending after interruption, repeat that exact command before other workflow actions.
The command resumes filesystem work without replaying checks.
TDD, protected content, acceptance commands, baseline, and other manifest fields remain fixed.
A changed behavior or oracle requires a separate specification decision.

For authorized long checks, use the [job runner workflow](long-running-operations.md#authorized-job-runner).
Report the generated candidate evidence once the job completes.
The full receipt and promotion workflow remains the authority for project completion.
