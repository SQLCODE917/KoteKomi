## Current Handoff

- Status: ready
- Spec commit: `<full 40-character lowercase SHA>`
- TDD: `<repository-relative leaf TDD path>`
- Prerequisite: none

Status is `ready` or `blocked`; draft is not a readiness state.
The PR branch supplies the delivery branch, so the handoff does not repeat it.
Comments can propose a replacement. Only this section in the PR description is the active handoff.

## Scope

- Goal:
- In scope:
- Out of scope:

## Evidence

- Extract the PR body outside the checkout: `gh pr view <pr-url> --json body --jq .body > "${TMPDIR:-/tmp}/kotekomi-handoff.md"`.
- Preflight from the checkout root: `uv run kotekomi-agent handoff-preflight "${TMPDIR:-/tmp}/kotekomi-handoff.md"`.
- Start only with the `start_command` that preflight returns for a ready handoff.
- Post focused check results, the candidate receipt, or a concrete blocker on this PR.
- Merge remains a human decision.
