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
