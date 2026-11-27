# Writing Technical Design Documents (TDDs)

Write the smallest design that lets an implementing agent deliver the agreed outcome.
Place a dated TDD in `docs/` and link it from the feature's Agile package.
Use [Domain vocabulary](domain.md) and [documentation style](documentation-style.md).
For capability claims, use [Pipeline Improvement](pipeline-improvement.md) to select evidence appropriate to the claim.

Cover:

- The operator outcome and observed current behavior.
- The complete operator path, its decision owners, and state read or finalized outside the returned value.
- Binding contracts and their rationale, distinguished from implementation proposals and unverified assumptions.
- Acceptance examples that distinguish correct from incorrect behavior.
- Existing evidence and the missing proof at the changed boundary, plus human UAT for the promised outcome.
- Any unresolved product decision that actually needs the operator.

Use existing interfaces and tests where they suffice.
Use the affected-path questions in [Implementing a TDD](implement-tdd-workflow.md#understand-and-adapt) before prescribing internals.
Specify observable meaning; require an exact shape or sequence only when another choice would violate a binding contract.
For example, a Source quotation must preserve its text and line breaks; a private helper layout is not an acceptance requirement.
Leave private decomposition, work order, and fixture arrangement to the implementing agent.
Stop drafting when the outcome, owners, contracts, sufficient evidence, and first useful step are clear.
Carry consequential unknowns into implementation with the question they must resolve, rather than guessing a restrictive design.
A small correction does not require a glossary, diagrams, a manifest, or a new evaluation framework.
Add sections or diagrams only when they resolve a real ambiguity.

The active package evolves on its PR branch under [Implementing a TDD](implement-tdd-workflow.md).
A package correction within the agreed outcome needs no new document path, specification digest, task, or run.
Explain the change in the PR diff and review request.
Use the discovery and escalation rules in [Implementing a TDD](implement-tdd-workflow.md#understand-and-adapt).
Earlier TDDs remain history; the active package states which earlier behavior it changes.
Human UAT acceptance remains separate from engineering verification.
