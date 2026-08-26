Read one authoritative source segment marked `[direct_prose]`.

The segment has one literal label after `SOURCE SEGMENT:`.

Use that label exactly in every claim.

Return each direct relationship that this segment states between two named organizations.

A company, government body, department, institute, university, consortium, network, or international body is an organization for this task.

Copy each subject and object character-for-character from this source segment.

Return one plain-text response with zero through eight claim lines.

```text
claim: s1 | Anthropic | partnered with | Palantir
```

Return exactly one abstention line when the segment states no eligible relationship.

```text
abstain: no direct organization-to-organization relationship
```

Do not return JSON, Markdown, code fences, identifiers, offsets, source ranges, or explanations.
