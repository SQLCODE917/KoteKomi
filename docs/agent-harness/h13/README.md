# H13 CLI delimiter planner rule

H13 closes the deferred CLI delimiter regression follow-up from the H12-H15
roadmap.

The target outcome is narrow: whenever a candidate touches CLI dispatch, the
deterministic `verification-plan` output must require the CLI delimiter
regression contract. That contract exists because `run-check` has special
`--` parsing semantics: command arguments after the delimiter must be preserved
exactly, including values that look like options.

This task must not expand the planner into a broad path-specific checklist.
The planner should add one low-maintenance touched-path rule and a focused
acceptance proof.
