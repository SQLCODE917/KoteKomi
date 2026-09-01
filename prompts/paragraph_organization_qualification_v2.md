Judge only whether the exact expression under `MENTION CANDIDATE` denotes an Organization in the supplied source segment.
An Organization is a collective Agent with a shared purpose beyond its current members that can act collectively.
Organizations include formal or informal bodies, governments, departments, courts, legislatures, administrations, military bodies, clubs, consortia, joint ventures, collaborations, institutional networks, news outlets, publishers, and supranational bodies.
A country name denotes an Organization when the source uses it as its acting government.
A named project or initiative denotes an Organization only when it refers to a collective Agent such as a team or joint venture.
A place, law, document, event, product, person, job title, role, generic class, anaphor, or unnamed cohort is not an Organization.
Use `ambiguous` when the supplied source segment and ordinary knowledge do not support either classification.
Do not change, extend, trim, normalize, or rewrite the candidate expression.
Return exactly `organization`, `not_organization`, or `ambiguous`.
Return no explanation, punctuation, whitespace, Markdown, or additional line.
