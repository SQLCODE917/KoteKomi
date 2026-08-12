# H11 Dogfood Plan

1. Create the H11 spec branch and record the spec commit and spec CI receipts.
2. Implement the candidate from the spec branch.
3. After candidate commit, run candidate lifecycle before verification-plan dogfood or CI.
4. Run `kotekomi-agent verification-plan` for the spec-to-candidate revision range.
5. Run every required check through `kotekomi-agent run-check`.
6. Run `kotekomi-agent verify-checks` against the plan and run records.
7. Run candidate CI only after candidate lifecycle and verify-checks are ready.
8. Merge to main with a no-fast-forward merge.
9. Run main lifecycle with `--main-base`, `--verified`, and `--head`.
10. Push main, require main CI success, record receipts, clean H11 branches, and record final status.
