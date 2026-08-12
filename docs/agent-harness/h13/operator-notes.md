# H13 operator notes

H13 is intentionally smaller than H12. Do not refactor CLI dispatch while
adding the planner rule.

The main risk is proving the wrong behavior: the acceptance test must verify
that command argv after `--` is preserved, not just that `run-check` succeeds.

The planner must remain deterministic. It may inspect Git diff paths and emit a
plan, but it must not execute checks, switch branches, stage files, commit,
push, or call GitHub.
