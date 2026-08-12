# H13 dogfood plan

1. Create the candidate from this spec commit.
2. Run the candidate lifecycle gate immediately after the candidate commit.
3. Run `verification-plan` for spec to candidate.
4. Execute every planned check through `run-check`.
5. Run `verify-checks` against the plan and all run records.
6. Push the candidate only after local dogfood is ready.
7. Merge through main only after candidate CI succeeds.
8. Record receipts for candidate commit, candidate lifecycle, verification
   plan, verify-checks, candidate CI, main lifecycle, main CI, branch cleanup,
   and final status.
