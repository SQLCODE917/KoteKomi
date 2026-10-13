# Self-Contained Communication

## Purpose and Scope

Make each communication understandable without requiring the reader to reconstruct earlier conversations, inspect code, or consult a glossary to resolve its meaning.
Apply this guidance to commentary, answers, reviews, findings, implementation summaries, documentation, tables, and diagrams.
Canonical naming and local explanation are separate requirements; satisfy both.
This guide governs communication, not business meaning or authorization to change code.

## Domain Vocabulary in Every Communication

[Domain Vocabulary](domain-vocabulary.md), at `docs/domain-vocabulary.md`, is the authority for Ralph business names and meanings.
Read the current vocabulary at the start of each task and reread it when it changes.
Check every written communication against it before sending or saving, even when the task is read-only.

- When a domain concept already exists, use its exact canonical name, capitalization, and meaning.
- Use the vocabulary's canonical code symbol when discussing the corresponding implementation.
- Do not invent an alternate name for an existing concept, even when the alternate sounds clearer or more familiar.
- Explain locally what the canonical concept means in the current passage, how it participates in the behavior being discussed, and why it matters.
- Distinguish canonical business names from framework objects, infrastructure resources, and existing code labels, and explain their mapping explicitly.
- Treat an existing code label that conflicts with the vocabulary as implementation evidence, not authority to rename the domain concept.
- Use the [Architecture Vocabulary](../architecture/hexagonal-monorepo/architecture-vocabulary.md) for architectural roles rather than forcing those roles into the business vocabulary.
- For genuinely new business concepts, mark their meaning as proposed and define them locally.
  Follow the vocabulary's existing candidate classification and definition/promotion rules before dependent documentation or implementation; do not present proposed terminology as established Ralph vocabulary.

Do not create a competing glossary in this guide or redefine business terms in a response.
Use the existing Domain Language Audit when the vocabulary or task guidance requires its full report.
For other communications, perform the check internally without adding audit boilerplate to every response.

## Explain Objects Where They Matter

- Explain each domain object or unfamiliar term where it first matters: what it means, what behavior it represents, and why it affects the finding or recommendation.
- Define terms narrowly beside their use; a glossary elsewhere or a definition in an earlier response does not replace a local explanation.
- Name the members of a referenced group in the same passage.
  Do not write "all four answer families," "both settings," or "the existing paths" without identifying the members.
- When describing a setting, give its code identifier, relevant values, and the behavior each value selects.
- When describing a component, distinguish its business responsibility, implementing code/framework, and deployment location where relevant.
- Use concrete examples when an abstract statement would require the reader to infer how it applies to Ralph.
- Keep canonical names and meanings consistent across prose, tables, diagrams, and code references.
  Explain diagram abbreviations beside the diagram.
- Avoid unrelated background and unnecessary repetition within a short, continuous passage.

For example:

> A Canned Answer is authored response text selected by an explicit question match and feature setting.
> Its matching behavior can move into `ralph-domain` because it requires neither model inference nor retrieval.
> The existing function `check_hardcoded_response` implements question normalization and delegates answer selection to `canned_answer`.

## Conclusions, Evidence, and Actions

Present findings as what is true or missing, supporting evidence, why it matters, and the required action.
Use conclusions first, followed by method, evidence, quantifications where useful, and qualifications.
Do not make readers reconstruct a conversation or discovery chronology.
Distinguish current implementation, proposed changes, assumptions, and verified results explicitly.
Support claims of cost, speed, reliability, or exclusive framework capabilities with evidence or label them as assumptions.
Do not present a hypothetical calculation as a measured outcome.
Write prose with one sentence per source line.
Do not wrap prose to a fixed column width.

## Check Before Sending or Saving

1. Every existing business concept uses its canonical Domain Vocabulary name and meaning.
2. No invented synonym replaces an existing concept.
3. Each unfamiliar concept is explained where needed, including how it applies to the current behavior.
4. Every referenced group's members and relevant setting values are named.
5. Names and meanings agree across prose, tables, diagrams, and code references.
6. Each finding explains its consequence and recommended action.
7. Current facts, proposals, assumptions, and verified results are distinguishable.
8. The reader needs neither an earlier conversation nor an external glossary to understand the communication.

Repair failed checks before completing the communication.

