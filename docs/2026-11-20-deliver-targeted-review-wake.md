# Deliver a Targeted Review Wake

## User Story

As a KoteKomi maintainer, I want a review request I post on the PR to reach the registered local implementing session, so I do not have to relay it. I still control approvals and merge.

## Scope and Signal

Pilot on one explicitly enrolled PR and one local Cline session first. Use the top-level GitHub review comment as a durable inbox. Dot adds an explicit versioned review-request marker to the comment it publishes; its immutable GitHub comment ID is the deduplication key. The public comment remains normal human-readable feedback. Working protocol fields are repository, PR number, comment ID and URL, exact reviewed head, and pinned spec SHA. Keep the agent/session binding and delivered IDs locally, outside the checkout. Do not use the GitHub `ready_for_review` event or pick up arbitrary PRs. The pickup and candidate CI workflows stay unchanged.

A local foreground listener uses the existing GitHub authentication with read-only access and is explicitly armed for one PR. Treat source identity as a precondition before sending an agent turn: an account shared by Dot and the operator is not independent proof of Dot authorship. If only allowlisted account plus marker can be verified, allow notification/dry-run but do not inject a turn until operator explicitly authorizes that signal or independent provenance is available. No inbound port, repository workflow, new credentials, launch agent, background install, or web service for this pilot. Document that the Mac must be awake and the listener running.

## Checkpoints

1. **Validate and route without launching an agent.** Fetch the exact comment using authenticated GitHub reads. Match the registered repo/PR, author or trusted producer and marker; re-read the open PR's head and canonical pin. Drop ordinary comments, other PRs/authors, stale heads/pins, duplicates, and closed PRs. A restart must not replay an already delivered comment; unclear send outcomes must not be retried blindly. Use only a fixed notification plus trusted PR/comment link, not comment text or commands.
2. **Prove one Cline target.** Use the installed Cline CLI or Hub only after proving the registered session ID and history match the intended implementation session and repository. Use a disposable task and a second unrelated task to prove the latter receives nothing. Only send a fixed, read-only request to check the linked PR review. Suppress sends to busy, unidentifiable, or unavailable targets; retain a queued alert or show an actionable local notification with a link. Do not use VS Code's send-to-active-task API as a fallback, spawn a new task, press approval buttons, or change sandbox settings. If the installed Cline cannot safely target the existing task, report that blocker rather than claiming a wake. No Codex adapter in this pilot.
3. **Verify one real delivery after opt-in.** With the operator's named Cline session enrolled, send one review request. Count exactly one delivery to that session, zero duplicate and wrong-session turns, and zero manual relays only if the intended session actually received it. A local notification alone is an explicit degraded mode, not a pilot pass. Keep the same Harness run and leave all tool approvals, code changes, and merge authority unchanged.

## References and Stops

[Cline VS Code exports](https://github.com/cline/cline/blob/main/apps/vscode/src/exports/cline.d.ts), [Cline CLI](https://github.com/cline/cline/blob/main/apps/cli/README.md), [Cline Hub](https://github.com/cline/cline/blob/main/docs/sdk/architecture/hub-spoke.mdx). Verify the installed surface before committing to an adapter. Do not broaden to arbitrary comments, lifecycle orchestration, CI wakes, or persistent execution. If safe identity or routing is unavailable, retain a notification-only demonstration and report manual resume still required. Use a separate product-neutral pilot; do not add it to the Composition product diff.
