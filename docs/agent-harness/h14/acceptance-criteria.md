# H14 acceptance criteria

1. Add the H14 task manifest and H14 documentation set.
2. Extend `verification-plan` touched-path coverage for known harness-owned
   implementation areas beyond the H13 CLI delimiter case.
3. Coverage must include deterministic checks for step script safety, lifecycle
   checks, task manifest/preflight contracts, verification execution, and
   verification-plan contracts when those known areas are touched in fixture
   repositories.
4. Unknown changed paths must still fail closed with diagnostics.
5. The H13 CLI delimiter regression rule must remain required for CLI dispatch
   or delimiter-sensitive planner changes.
6. Unit and acceptance tests must cover the new coverage map and at least one
   fail-closed path.
7. H14 must dogfood the normal sequence: early candidate lifecycle,
   verification-plan, run-check, verify-checks, candidate CI, main lifecycle,
   main CI, branch cleanup, and final status receipts.
