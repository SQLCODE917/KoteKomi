# H11 Acceptance Criteria

1. Add an H11 manifest/spec documenting lifecycle ergonomics and early candidate gate accountability.
2. `kotekomi-agent lifecycle-check --phase main` fails closed with explicit diagnostics when `--main-base`, `--verified`, or `--head` is missing.
3. Main-phase lifecycle help or docs state the required argument set for main merges.
4. `packages/devtools/AGENTS.md` says to run candidate lifecycle immediately after candidate commit and before dogfood verification execution or CI.
5. Acceptance and unit tests cover missing main lifecycle arguments and early-candidate-gate guidance.
6. Unit and acceptance tests require no network, GitHub, global repository state, branch switching, commits, or pushes.
7. H11 is dogfooded with `verification-plan`, `run-check`, and `verify-checks`.
8. Main lifecycle verification, main CI, branch cleanup, and final status receipts are recorded.
