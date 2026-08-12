# H12 Acceptance Criteria

1. Add H12 docs and manifest under `docs/agent-harness` and `.agent/tasks`.
2. Add a deterministic command for local step preflight that records branch, HEAD, origin main, optional remote branch refs, and worktree status.
3. Add a deterministic recovery mode that can reset a known failed local candidate branch to an expected base, while refusing dirty `main` by default.
4. Add a deterministic failure-record command or mode that writes a machine-readable receipt for a failed local generated step.
5. Update `packages/devtools/AGENTS.md` so generated local scripts use deterministic preflight/recovery/failure recording instead of bespoke branch-reset logic.
6. Unit and acceptance tests cover clean preflight, dirty-main refusal, known-candidate reset behavior, and failure receipt output without network, GitHub, commits, pushes, or global repository state.
7. H12 is dogfooded with early candidate lifecycle, verification-plan, run-check, verify-checks, candidate CI, main lifecycle, main CI, branch cleanup, and final status receipts.
