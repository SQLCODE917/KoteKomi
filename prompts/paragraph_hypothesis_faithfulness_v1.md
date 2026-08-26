Read one authoritative source segment and one proposed relationship.

Decide whether the source segment directly states the proposed relationship.

Accept only relation wording that faithfully represents the source sentence.

Reject inference, implication, changed modality, changed attribution, and an unstated relationship.

Return exactly two plain-text lines.

```text
verdict: accept
reason: the source directly states the relationship
```

Use `verdict: reject` when the source does not directly state the relationship.

Do not return JSON, Markdown, identifiers, offsets, or explanations beyond the required reason.
