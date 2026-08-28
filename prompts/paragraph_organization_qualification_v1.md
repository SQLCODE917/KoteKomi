Perform named-entity type classification for only the literal candidate under `MENTION CANDIDATE`.
For this task, an Organization is a company, agency, lab, publisher, university, nonprofit, think tank, or institution.
A legislature, government body, department, institute, consortium, network, or international body is also an Organization.
A country, region, group of states, law, agreement, product, method, event, person, role, or military in general is not an Organization.
A proper name can denote an Organization even when the source does not state its type beside the name.
Use ordinary knowledge, source meaning, and grammar to decide what the candidate denotes in this occurrence.
Do not require the source to define the candidate before accepting it.
In `Northstar's technology reached many customers`, candidate `Northstar` denotes an Organization.
In `Northstar partnered with Harbor Institute`, both proper names denote Organizations.
In `Northstar said she accepted the role`, candidate `Northstar` denotes a person and is rejected.
In `the company released a system`, candidate `the company` is generic and is rejected.
In `Arcadia adopted a law`, candidate `Arcadia` denotes a country and is rejected.
Do not use the presence or absence of a qualifier or initialism to decide the entity type.
If the candidate denotes an Organization, copy its complete displayed Organization expression from the source segment.
The complete expression must contain the candidate at this occurrence.
Include a directly attached geographic qualifier or parenthetical initialism only when it belongs to the same displayed name.
A geographic qualifier or parenthetical initialism is optional and its absence is not a reason to reject a candidate.
For acceptance, return exactly one line that begins with `organization: ` and ends with the copied expression.
For rejection, return exactly `reject: not an organization`.
Before returning, verify that the result has exactly one line.
Return no template, alternative, reasoning, explanation, Markdown, code fence, identifier, offset, or source range.
