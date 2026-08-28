Perform named-entity type classification for only the literal candidate under `MENTION CANDIDATE`.
An Organization is a collective Agent with a common purpose beyond its current members that can act collectively.
Organizations include formal and informal bodies, governments, departments, courts, legislatures, administrations, military bodies, clubs, consortia, joint ventures, collaborations, institutional networks, and supranational bodies.
Reject a country name used only as a Place.
A region, another Place, law, document, Event, product, person, or role is not an Organization.
A project or initiative that does not denote a collective Agent is not an Organization.
A country name denotes an Organization when the source assigns its government collective action such as membership, signing, refusal, founding, or another deliberate act.
A named project or initiative denotes an Organization only when its referent is a collective Agent such as a cross-functional team or joint venture.
A proper name can denote an Organization even when the source does not state its type beside the name.
Use ordinary knowledge, source meaning, and grammar to decide what the candidate denotes in this occurrence.
Do not require the source to define the candidate before accepting it.
In `Northstar's technology reached many customers`, candidate `Northstar` denotes an Organization.
In `Northstar partnered with Harbor Institute`, both proper names denote Organizations.
In `Northstar said she accepted the role`, candidate `Northstar` denotes a person and is rejected.
In `the company released a system`, candidate `the company` is generic and is rejected.
In `Arcadia signed the agreement`, candidate `Arcadia` denotes its acting government and is accepted.
In `the conference took place in Arcadia`, candidate `Arcadia` denotes a Place and is rejected.
Do not use the presence or absence of a qualifier or initialism to decide the entity type.
If the candidate denotes an Organization, copy its complete displayed Organization expression from the source segment.
The complete expression must contain the candidate at this occurrence.
Include a directly attached geographic qualifier or parenthetical initialism only when it belongs to the same displayed name.
A geographic qualifier or parenthetical initialism is optional and its absence is not a reason to reject a candidate.
Accept a named publisher, news outlet, or club.
Reject a generic description, anaphor, or unnamed cohort.
For acceptance, return exactly one line that begins with `organization: ` and ends with the copied expression.
For rejection, return exactly `reject: not an organization`.
Before returning, verify that the result has exactly one line.
Return no template, alternative, reasoning, explanation, Markdown, code fence, identifier, offset, or source range.
