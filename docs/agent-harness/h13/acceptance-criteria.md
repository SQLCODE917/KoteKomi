# H13 acceptance criteria

1. The H13 manifest and docs define the CLI delimiter planner-rule scope.
2. `verification-plan` includes a CLI delimiter regression check when `cli.py`
   changes.
3. The planner result remains deterministic and does not run tests or mutate
   Git state.
4. The CLI delimiter regression check proves `run-check` preserves command
   arguments after `--`, including option-like arguments.
5. Acceptance tests cover the planner rule and delimiter contract.
6. Retained H12, H11, H10, H9, task-manifest, and task-preflight contracts pass.
7. Candidate dogfood runs `verification-plan`, executes every planned check with
   `run-check`, and proves the run records with `verify-checks`.
8. Main merge uses `lifecycle-check --phase main`, main CI, branch cleanup, and
   final status receipts.
