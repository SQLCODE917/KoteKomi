# H14 dogfood plan

Candidate dogfood:

1. Run candidate lifecycle immediately after the candidate commit.
2. Run `verification-plan` from the H14 spec commit to the candidate commit.
3. Execute every planned check through `run-check`.
4. Validate all run records with `verify-checks`.
5. Push the candidate branch and require candidate CI success.

Main dogfood:

1. Merge the verified candidate into `main` with a merge commit.
2. Run `lifecycle-check --phase main` with `--main-base`, `--verified`, and
   `--head`.
3. Run the focused retained local checks.
4. Push `main`, require main CI success, delete H14 spec/candidate branches,
   and record final clean state.
