# Output Format

## Implementation Summary

Lead with the change and context.

Use short headers.

Use flat bullets.

Use inline code for paths, commands, and identifiers.

Reference files as markdown links when line numbers are known.

Avoid large file dumps.

Summarize command output.

Report tests run.

Report tests not run.

## Required Sections

Use these sections when reporting a code change:

```text
Changed
Tests
Notes
```

Use `Notes` only when there is useful residual context.

## Test Reporting

List each command that ran.

State whether it passed or failed.

State why a relevant test did not run.

## Product Progress and Completion

For capability work, Pipeline changes, and experiments, follow [Pipeline Improvement](pipeline-improvement.md).
Lead with the operator-visible result and its limits.
State implementation verification, demonstrated capability, and package target status separately.
Separate observations, suspected causes, and demonstrated causes.
Name the source cases, tested revisions, assessed population, and remaining failures behind a capability claim.
Report measured values separately from unknown values and identify who performed the assessment.
Disclose agent assistance and protocol changes before making an effort or transfer claim.
Do not present intermediate counts or agent execution time as usable intelligence or human review effort.
For `Target not met`, state retained benefits, remaining failures, and the required scope decision.
Recommend next work by comparing Pipeline stages rather than continuing automatically in the last edited component.
Use the current tracker or report; these requirements introduce no separate reporting system.

## File References

Use markdown links for files when line numbers are known.

Use inline code for file paths when line numbers are unknown.
