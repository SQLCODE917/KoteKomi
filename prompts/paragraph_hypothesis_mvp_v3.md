Read one authoritative paragraph marked `[direct_prose]`.

Each source segment starts with `SOURCE SEGMENT: sN`.

The literal token after `SOURCE SEGMENT:` is the only valid source-segment label.

Use that token exactly in every claim.

For example, use `s1`.

Do not use brackets, angle brackets, quotes, or other punctuation around a source-segment label.

Return only relationships that one source segment states directly between two named organizations.

For this task, a named company, government body, department, institute, university, consortium, network, or international body may be an organization.

Do not abstain merely because the relationship is not in a fixed vocabulary.

Use one source segment for each relationship.

Copy the organization subject and organization object character-for-character from the cited source segment.

Do not expand a name, resolve a pronoun, paraphrase a name, or combine text from different source segments.

Return one plain-text response.

Return one line for each selected relationship.

```text
claim: s1 | Anthropic | partnered with | Palantir
```

Return at most eight claim lines.

If more than eight relationships qualify, select eight in source-segment order.

Within one source segment, select relationships in the order of their subject mention.

Return no abstention line when you return one or more claim lines.

Return exactly one abstention line when no relationship qualifies.

```text
abstain: no direct organization-to-organization relationship
```

Do not return JSON, Markdown, code fences, identifiers, offsets, source ranges, or explanations.
