Read one authoritative source segment marked `[direct_prose]`.

The segment has one literal label after `SOURCE SEGMENT: sN`.

Use that label exactly in every claim.

Return each direct relationship that this segment states between two named organizations.

A company, government body, department, institute, university, consortium, network, or international body is an organization for this task.

Copy every subject and object character-for-character from the source segment.

For example, when the source segment says `Anthropic partnered with Palantir.`, return this exact line.

```text
claim: s1 | Anthropic | partnered with | Palantir
```

Do not use a pronoun, an abbreviation, a synonym, or a broader name that the source segment does not contain.

When the source segment states no direct relationship between two named organizations, return this exact form.

```text
abstain: no direct organization-to-organization relationship
```

Return one plain-text response with zero through eight claim lines.

Do not return JSON, Markdown, code fences, identifiers, offsets, source ranges, or explanations.
