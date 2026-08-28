Read one source segment.

Find every distinct literal Organization name in that segment.
An Organization is a collective Agent with a common purpose beyond its current members that can act collectively.
Organizations include formal and informal bodies, governments, departments, courts, legislatures, administrations, military bodies, clubs, consortia, joint ventures, collaborations, institutional networks, and supranational bodies.
A single proper name can identify an Organization when the segment does not state its type beside it.
A country name used only as a Place, a region, another Place, a law, document, Event, product, project or initiative that does not denote a collective Agent, person, or role is not an Organization.
Return a country name when it denotes its government acting collectively, but not when it denotes only a place.
Membership, signing, refusal, founding, or another deliberate act indicates that a country or supranational name denotes its acting government or body.
Classify what the name denotes rather than classifying from a word in the name; a named project is an Organization when its known referent is a collective Agent such as a cross-functional team or joint venture.
Scan the segment from left to right and do not omit a named Organization because it appears in a list, possessive phrase, or longer sentence.

Copy each complete Organization name exactly as displayed.
Treat each separately named Organization in a coordinated list as a separate Organization.
For example, when a sentence names `Harbor Institute, Civic Science Department, and Northstar University`, return all three names.
Include a possessive geographic qualifier that directly introduces an Organization name, as in `Republic of Arcadia's Ministry of Science`.
The qualifier remains part of the returned Organization name and does not become a separate nested mention.
Include parenthetical text that is part of the displayed name, as in `National Research Institute (NRI)`.
Exclude a grammatical determiner such as lowercase `the` unless it conventionally belongs to the displayed Organization name, as in `The New York Times`.
Do not return only a shorter substring of a complete displayed Organization name.
When an Organization name modifies or possesses a product name, return only the Organization component; for example, return `Google` from `Google Gemini` and `OpenAI` from `OpenAI's ChatGPT`.
Return a named publisher or news outlet.
Return a supranational name such as `European Union` when it denotes the acting body, but not when it denotes only a place or jurisdiction of origin.
Return a named club and do not return a generic club description.
Do not return a generic description, anaphor, or unnamed cohort.

Use the source-segment label displayed after `SOURCE SEGMENT:` in every result.
When the segment contains one or more Organizations, return one `mention:` line for every Organization with no blank lines and no `abstain:` line.

```text
mention: s1 | Harbor Institute
```

When the segment contains no Organization, return only this exact line.

```text
abstain: no literal organization mention
```

Before returning, verify that every named Organization has one line and every line copies one complete displayed name.
Return only plain text.
Do not comment on the result.
Do not return JSON, Markdown, code fences, identifiers, offsets, source ranges, reasoning, or explanations.
