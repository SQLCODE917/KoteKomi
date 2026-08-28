Read one source segment.

Find every distinct literal Organization name in that segment.
For this task, an Organization is a company, legislature, government body, department, institute, university, consortium, network, or international body.
A single proper name can identify a company even when the segment does not include a word such as `company` or `corporation` beside it.
A country, region, group of states, law, agreement, product, method, or military in general is not an Organization for this task.
Scan the segment from left to right and do not omit a named Organization because it appears in a list, possessive phrase, or longer sentence.

Copy each complete Organization name exactly as displayed.
Treat each separately named Organization in a coordinated list as a separate Organization.
For example, when a sentence names `Harbor Institute, Civic Science Department, and Northstar University`, return all three names.
Include a possessive geographic qualifier that directly introduces an Organization name, as in `Republic of Arcadia's Ministry of Science`.
The qualifier remains part of the returned Organization name even though the country itself is not an Organization.
Include parenthetical text that is part of the displayed name, as in `National Research Institute (NRI)`.
Do not return only a shorter substring of a complete displayed Organization name.

Use the source-segment label displayed after `SOURCE SEGMENT:` in every result.
When the segment contains one or more Organizations, return one `mention:` line for every Organization with no blank lines and no `abstain:` line.

```text
mention: s1 | Harbor Institute
```

Return no more than twelve `mention:` lines.
When the segment contains no Organization, return only this exact line.

```text
abstain: no literal organization mention
```

Before returning, verify that every named Organization has one line and every line copies one complete displayed name.
Return only plain text.
Do not comment on the result.
Do not return JSON, Markdown, code fences, identifiers, offsets, source ranges, reasoning, or explanations.
