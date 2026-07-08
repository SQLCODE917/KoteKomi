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

## File References

Use markdown links for files when line numbers are known.

Use inline code for file paths when line numbers are unknown.
