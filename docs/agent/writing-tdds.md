# Writing Technical Design Documents (TDDs)

Write the smallest design that lets an implementing agent deliver the agreed outcome.
Place a dated TDD in `docs/` and link it from the feature's Agile package.
Use [Domain vocabulary](domain.md) and [documentation style](documentation-style.md).
For capability claims, use [Pipeline Improvement](pipeline-improvement.md) to select evidence appropriate to the claim.

Cover:

- The operator outcome and observed current behavior.
- The component that owns the change and the boundaries it affects.
- Acceptance examples that distinguish correct from incorrect behavior.
- The checks and human UAT needed to demonstrate that behavior.
- Any unresolved product decision that actually needs the operator.

Use existing interfaces and tests where they suffice.
Leave implementation choices to the implementing agent unless they change an acceptance decision.
A small correction does not require a glossary, diagrams, a manifest, or a new evaluation framework.
Add sections or diagrams only when they resolve a real ambiguity.

The active package evolves on its PR branch under [Implementing a TDD](implement-tdd-workflow.md).
A package correction within the agreed outcome needs no new document path, specification digest, task, or run.
Explain the change in the PR diff and review request.
The operator decides changes to the promised outcome and product tradeoffs.
Earlier TDDs remain history; the active package states which earlier behavior it changes.
Human UAT acceptance remains separate from engineering verification.
