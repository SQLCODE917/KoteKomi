# Navigate the Candidate Wiki

The operator can move between the Wiki index, its Document page, and every record page.
The current six-page fixture generates a Document page with no incoming link and no links back to the index.
The [TDD](2026-11-27-navigate-candidate-wiki.md) defines this bounded presentation change.

Use one PR from merged main and the ordinary development workflow.
The operator authorized implementation and verification; UAT acceptance and merge remain with the operator.
Ordinary package corrections stay on this branch.
Use existing planner/renderer fixtures, focused checks, fast checks, and full PR CI.
A small complete generated Wiki supplies navigation UAT without fresh ingestion or new instrumentation.

For this coordination trial, the implementing agent commits locally and submits one bounded job that runs fast checks and then pushes only if they pass.
The job completion goes directly to Spymaster for review; the implementing agent ends its turn without forwarding the result.
On failure, Spymaster returns one actionable request after inspecting the result.
GitHub and existing job/delivery records supply the efficiency comparison.
