# H15 dogfood plan

Candidate dogfood: run candidate lifecycle, run `verification-plan`, execute every planned check through `run-check`, validate with `verify-checks`, push the candidate branch, and require candidate CI success.

Main dogfood: merge the verified candidate into `main`, run `lifecycle-check --phase main`, run focused retained local checks, push `main`, require main CI success, delete H15 branches, and record final clean state.
