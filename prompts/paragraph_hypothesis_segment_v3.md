Read one Source copy view marked `[direct_prose]`.

The Source copy view preserves source wording and punctuation.

The Source copy view replaces each source whitespace run with one space.

The segment has one literal label after `SOURCE SEGMENT: sN`.

Use that label exactly in every claim.

Return each direct relationship that this segment states between two named organizations.

A company, government body, department, institute, university, consortium, network, or international body is an organization for this task.

Copy every subject and object exactly from the Source copy view.

For example, when the Source copy view says `Anthropic partnered with Palantir.`, return this exact line.

```text
claim: s1 | Anthropic | partnered with | Palantir
```

Do not use a pronoun, generic description, abbreviation, synonym, or broader name that the Source copy view does not contain.

When the Source copy view states no direct relationship between two named organizations, return this exact form.

```text
abstain: no direct organization-to-organization relationship
```

Return one plain-text response with zero through eight claim lines.

Do not return JSON, Markdown, code fences, identifiers, offsets, source ranges, or explanations.
