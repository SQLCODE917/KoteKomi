Read one source segment.
Evaluate only the two literal Organization candidates under `CANDIDATE PAIR`.

Return one direct ordered relationship only when the segment explicitly states one between those two Organizations.

A direct relationship includes source-stated partnership, agreement, membership, containment, lineage, directed action, refusal, or interoperability.
These examples do not limit other direct relationships explicitly stated by the source.
An elided second clause can omit a repeated verb while still stating a direct relationship.
For example, `Harbor Institute was established from Northstar University, and Civic Science Department as part of Regional Council` states that `Civic Science Department` is part of `Regional Council`.
For example, `Harbor Institute reached an agreement with Civic Science Department`, `Harbor Institute joined Civic Science Department`, `Harbor Institute is part of Civic Science Department`, and `Harbor Institute was established as an evolution of Civic Science Department` each state a direct ordered relationship.
For example, `Harbor Institute lobbied Civic Science Department` and `Harbor Institute refused to allow Civic Science Department to use its system` each state a direct ordered relationship.

Use the relationship direction expressed by the source.
Copy the complete subject and object names exactly from `CANDIDATE PAIR`.
The subject field must equal one candidate exactly and the object field must equal the other candidate exactly.
Put action details, objects of the action, and quoted conditions in the relation field rather than the subject or object field.
Use the shortest source phrase that expresses the relationship.
Do not invent a relation label.

Do not turn coordinated participants in one shared action into a direct ordered relationship.
For example, `Harbor Institute and Civic Science Department began consulting` does not state one for this task.

Use the source-segment label displayed after `SOURCE SEGMENT:` in this form.

```text
claim: s1 | Harbor Institute | partnered with | Civic Science Department
```

For example, when `Harbor Institute refused to allow Civic Science Department to use its system`, return `claim: s1 | Harbor Institute | refused to allow | Civic Science Department`.

When the segment states no direct relationship between the two candidates, return only this exact line.

```text
abstain: no direct organization-to-organization relationship
```

Return only plain text.
Do not return JSON, Markdown, code fences, identifiers, offsets, source ranges, reasoning, or explanations.
