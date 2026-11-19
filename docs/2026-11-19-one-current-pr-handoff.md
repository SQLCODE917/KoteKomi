# One Current PR Handoff

## User Story

As a KoteKomi developer starting from a PR URL, I want one current handoff that names the exact specification revision, so I can start work on the existing branch without reconstructing instructions from chat or comments.

## Context

The [Agile package](2026-11-19-same-branch-delivery-handoff-agile-package.md) owns the delivery sequence. PR #2 left an obsolete spec-only instruction in its description; PR #3 superseded its original pin in a comment. The existing `implement-tdd --specification-commit` command already validates an explicit branch pin when starting a run. Do not change its semantics or add another lifecycle.

## Contract

- The PR description contains one `## Current Handoff` section. It identifies `Status` (`ready` or `blocked`), `Spec commit` (full SHA), `TDD` (repo-relative path), and `Prerequisite` (`none` or an explicit dependency/blocker). Draft is not a readiness state. The PR supplies the existing branch; do not duplicate it as a handoff field.
- Add the PR template and update the existing workflow guide. The guide must distinguish a human at the terminal from an agent with a checkout. The latter runs the existing commands and posts evidence or blockers on the PR. The PR must be self-contained, and comments cannot silently override the active pin.
- Add a small, read-only preflight in devtools. Accept the PR description and a fetched checkout of the PR branch as inputs; no GitHub SDK or credentials needed by the checker. For a ready handoff, validate that the full pin is reachable from that branch and that the TDD and Task Manifest V2 agree at the pin and still match the checkout. Reuse existing validation primitives where practical. Return the explicit start command only when the checks pass. Check the declared readiness; do not invent dependency resolution or remote status state.
- Missing or duplicate handoffs, blocked status, invalid or unreachable pins, a missing or mismatched TDD/manifest, and checkout drift must stop pickup with a useful diagnostic. Never infer the pin from the branch tip or follow an older handoff in a comment.

## Acceptance

1. A disposable branch with the template filled in passes preflight. A later implementation push does not change the command or pin. A repair to code under the same acceptance contract keeps that pin.
2. Replacing the handoff with a new spec revision selects only the new pin and does not mutate the old spec or its evidence. A duplicated old/new handoff blocks. No new run is started by the preflight.
3. Regression cases cover blocked or malformed input, unreachable pin, and TDD/manifest mismatch or drift. Use local Git fixtures, not live GitHub or network services.
4. The template and guide show a standalone URL-only pickup; a reviewer can find the start command, scope, and evidence expectations from the PR. Document any inability to update the current PR description rather than treating comments as the canonical fallback.
5. Publish focused check results and a normal same-branch receipt. Leave the real ingestion trial and event-driven pickup for later slices.

## Scope and Stop Conditions

Change only the guide, the PR template, the preflight and its tests. No new manifest schema, application code, branch-rule or workflow changes, new agent deployment, or merge. Stop if this needs a second source of truth or forces changes to the harness lifecycle itself.
