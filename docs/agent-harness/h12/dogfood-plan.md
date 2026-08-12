# H12 Dogfood Plan

1. Create the H12 spec branch from H11 main.
2. Validate the H12 manifest and run retained local checks.
3. Push the H12 spec branch and require spec CI success.
4. Implement H12 on a candidate branch.
5. After candidate commit, run candidate lifecycle before dogfood verification execution or CI.
6. Run `verification-plan`, then every required check through `run-check`, then `verify-checks`.
7. Push the candidate only after candidate lifecycle and verify-checks are ready.
8. Require candidate CI success.
9. Merge to main with a no-fast-forward merge.
10. Run main lifecycle with `--main-base`, `--verified`, and `--head`.
11. Push main, require main CI success, clean branches, and record final status.
