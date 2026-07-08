# Writing Technical Design Documents

## Purpose

A TDD pins down decisions that cross a contract boundary.

A TDD stays silent on implementation choices that do not affect a contract.

A TDD will be reviewed by a human and handed to a coding agent.

## File Location

Place TDDs in `docs/`.

Name each TDD with a date and title:

```text
YYYY-MM-DD-meaningful-title.md
```

## Sizing Gate

One TDD covers one independently shippable and revertable unit of work.

Split the TDD before writing when any condition applies:

- the architecture diagram needs more than six components
- the TDD needs more than four sequence diagrams
- an ASCII diagram cannot express the design clearly
- the work changes unrelated package boundaries
- the work combines a domain change with an unrelated Adapter change

## Required Sections

Use these sections in this order.

1. Context & Problem
2. Goals
3. Non-Goals & Forbidden Approaches
4. Requirements
5. Invariants
6. Proposed Architecture
7. Key Interactions
8. Data Model
9. APIs / Interfaces
10. Behavior & Domain Rules
11. Acceptance Criteria
12. Cross-Cutting Concerns
13. Reference Implementations
14. Alternatives Considered
15. Halt Conditions

## Context & Problem

Define new terms before use.

Use 2-4 sentences for the problem.

State what exists today.

State what is missing or broken.

## Goals

Write measurable goals.

Use bullets only for parallel items.

## Non-Goals & Forbidden Approaches

Use Non-Goals to exclude scope.

Use Forbidden Approaches to block valid-looking wrong designs.

Keep each item specific to this TDD.

Do not use this section for broad style rules.

## Requirements

Each Requirement has one possible reading.

Each Requirement has a finite verification check.

## Invariants

Each Invariant remains true before and after the work ships.

Use Invariants for data integrity, compatibility, idempotency, and boundary guarantees.

## Proposed Architecture

Describe the architecture in prose.

Include one C4 Container-level ASCII diagram.

Write one sentence per component.

State each component responsibility once.

## Key Interactions

Include 2-4 ASCII sequence diagrams.

Choose flows that exercise the most architectural surface.

## Data Model

List entities, relationships, and access patterns.

Use schema sketches.

Do not include full DDL unless the DDL is the contract.

## APIs / Interfaces

Name endpoints, interfaces, commands, methods, and purposes.

Pin request and response shapes only when the shape is a contract decision.

## Behavior & Domain Rules

State each rule once.

Add 1-3 worked examples for each rule group.

Include the ugliest edge case.

Examples are normative.

Fix the prose when prose and example conflict.

## Acceptance Criteria

Write observable checks.

Write checks so tests can implement them directly.

Group large work into ordered verification gates.

## Cross-Cutting Concerns

Mention auth, observability, error handling, performance, or security only when the TDD changes repo conventions.

Do not restate `AGENTS.md`.

## Reference Implementations

Point to existing files or modules that the implementer should imitate.

Use one line per reference.

## Alternatives Considered

Use one bullet per alternative.

State the chosen option and the reason in one line.

Link an ADR when the reason needs more detail.

## Halt Conditions

Use Halt Conditions for unresolved decisions that block implementation.

Phrase each Halt Condition as an explicit instruction.

## Final Edit

Before finishing a TDD, delete sentences that describe implementation choices outside contract boundaries.

Keep a sentence only when a PR would be rejected if the implementer chose differently.
