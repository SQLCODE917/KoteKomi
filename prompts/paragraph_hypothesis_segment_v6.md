Read one Source copy view marked `[direct_prose]`.

The Source copy view preserves source wording and punctuation.

The Source copy view replaces each source whitespace run with one space.

The segment has one literal label after `SOURCE SEGMENT: sN`.

Use that label exactly in every claim line.

Return every direct ordered relationship that this segment explicitly states between two named
organizations.

A company, government body, department, institute, university, consortium, network, or
international body is an organization for this task.

These are direct ordered relationships for this task.

```text
Harbor Institute had already partnered with Civic Science Department and Beacon Corporation.
claim: s1 | Harbor Institute | partnered with | Civic Science Department
claim: s1 | Harbor Institute | partnered with | Beacon Corporation

Through its interoperability with Civic Science Department, Harbor Institute could provide a service.
claim: s1 | Harbor Institute | interoperability with | Civic Science Department

Harbor Institute reached an agreement with Civic Science Department.
claim: s1 | Harbor Institute | reached an agreement with | Civic Science Department

Harbor Institute refused to agree to allow Civic Science Department access.
claim: s1 | Harbor Institute | refused to agree to allow | Civic Science Department

Harbor Institute privately lobbied for Parliament to vote against a bill.
claim: s1 | Harbor Institute | lobbied for | Parliament

Current Institute was officially established as an evolution of Frontier Taskforce.
claim: s1 | Current Institute | was established as an evolution of | Frontier Taskforce

Harbor Institute and Beacon Corporation joined Safety Consortium.
claim: s1 | Harbor Institute | joined | Safety Consortium
claim: s1 | Beacon Corporation | joined | Safety Consortium

Current Institute was founded as part of Civic Science Department.
claim: s1 | Current Institute | was founded as part of | Civic Science Department
```

Copy every subject and object exactly from the Source copy view.

Use the source wording for the relation label where possible.

Do not use a pronoun, generic description, abbreviation, synonym, or broader name that the Source
copy view does not contain.

Do not turn coordinated participants in one shared action into a direct ordered relationship.

For example, `Harbor Institute and Civic Science Department began consulting` is not an ordered
organization-to-organization relationship for this task.

Do not treat a person, country, product, or event as an organization.

When the Source copy view states no direct relationship between two named organizations, return this
exact form.

```text
abstain: no direct organization-to-organization relationship
```

Return only one plain-text response.

Return one `claim:` line for each relationship with no blank lines between claim lines.

Return zero through eight claim lines.

Do not return JSON, Markdown, code fences, identifiers, offsets, source ranges, or explanations.
