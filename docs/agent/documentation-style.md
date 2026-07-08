# Documentation Style

## Purpose

Write documentation for engineers and coding agents.

Use precise terms.

State contract decisions clearly.

## Style Rules

Write in active voice.

Make the acting component the subject.

Use one instruction or fact per sentence.

Use one sentence per line in TDDs.

Keep sentences under 20 words when practical.

Use one term per concept.

Use glossary terms exactly.

State behavior positively.

Prefer "the Pipeline writes ProposedChange records" over "ProposedChange records are written."

Prefer "propose Assertions" over "Assertion proposal processing."

Keep noun clusters to three words or fewer.

Use plain ASCII diagrams.

Use fenced code blocks with language hints.

Use ATX headings.

Use pipe tables for structured comparisons.

Write technology choices as decisions.

Use bullets for enumerable lists.

Use prose for design rationale.

## Banned Patterns

Avoid elegant variation.

Avoid undefined terms.

Avoid stacked negation.

Avoid weak phrases.

Avoid agentless passive voice.

Avoid hidden actors.

Avoid repeated rules across sections.

Avoid non-parallel enumerations.

Avoid pseudocode in TDDs.

Avoid implementation snippets in TDDs.

Avoid function signatures in TDDs unless the signature is a public contract.

## Weak Phrases

Replace these phrases before finishing documentation.

| Weak phrase | Replace with |
|---|---|
| relevant | the exact selection rule |
| when available | the exact condition |
| should | must, can, or will |
| may | can, only when permission is intended |
| appropriate | the exact criterion |
| reasonable | the exact criterion |
| as needed | the exact trigger |
| support | the exact behavior |
| handle | the exact behavior |
| process | the exact action |
| data | the exact object name |
| artifact | the exact object name |

## Self-Contained Documents

Keep documentation self-contained.

Use normative markdown links for outside context.

Do not write documentation as a chat transcript.

Define terms before first use.

Use the canonical terms from `docs/agent/domain.md`.

Update documentation in the same change that changes contracts.
