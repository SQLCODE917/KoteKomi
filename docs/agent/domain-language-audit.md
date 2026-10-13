# Domain Language Audit

## Purpose

Prevent duplicate, invented, or renamed terms in KoteKomi communications.

Use one canonical term per concept across answers, TDDs, documentation, and Agile packages.

## Governed communications

Run this audit before sending or saving any of these:

- a human-facing answer, summary, review, or finding;
- a TDD;
- a documentation change;
- an Agile package.

## Phase one: read before drafting

Read these two vocabularies before deciding the content:

1. the [Domain Vocabulary](./domain.md) in `docs/agent/domain.md`;
2. the [Architecture Vocabulary](./hexagonal-architecture-vocabulary.md) in `docs/agent/hexagonal-architecture-vocabulary.md`.

Use only the terms those vocabularies already define.

Treat a pre-existing code label that conflicts with a vocabulary term as implementation evidence, not authority to rename the concept.

## Phase two: review after drafting

After the content is decided, review it against both vocabularies.

Repair any of these before sending or saving:

- a term the vocabularies define but spelled or named differently;
- a new synonym for an existing canonical term;
- an architectural term used for a business concept, or the reverse;
- a new business term stated as established without the vocabulary's promotion rules.

Mark a genuinely new business concept as proposed and define it locally.

## Sources

Mirror the vocabulary check onto the "Check Before Sending or Saving" list in `docs/agent/self-contained-communication.md`.