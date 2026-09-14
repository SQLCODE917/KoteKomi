Identify standing facts stated by one source segment.
A standing fact is a relationship, classification, affiliation, ownership, location, status, or literal attribute that holds as a state.
An action, occurrence, announcement, decision, change, request, recommendation, or attributed opinion is not a standing fact.
Use only the supplied source segment, candidate catalog, and word catalog.
Each candidate has a `cN` label, the `oN[-oN]` location where it appears, its exact source wording, and the entity it refers to.
The occurrence location distinguishes candidates whose names repeat.
Use one candidate as the subject.
Use a different candidate as an entity object only when that entity itself is the complete object.
When the object is a view, policy, strategy, title, description, status, or other source phrase, select the complete phrase as a literal object even if it contains entity names.
Select the smallest contiguous relation range that preserves the standing meaning without including the subject or object.
Select literal objects from the word catalog instead of copying their text.
Return every distinct standing fact directly stated by the source segment.
For example, if the source says `Northstar's policy mirrors Rivera's views on exports`, and the catalogs assign `c1` to `Northstar`, `o2-o3` to `policy mirrors`, and `o4-o7` to `Rivera's views on exports`, return `fact: c1 | o2-o3 | literal | o4-o7`.
Return one line per fact in exactly one of these forms:
fact: cN | <supplied oN[-oN] relation selector> | entity | cN
fact: cN | <supplied oN[-oN] relation selector> | literal | <supplied oN[-oN] object selector>
If the source segment states no standing fact between the listed candidates or their literal attributes, return exactly:
abstain: no_supported_standing_fact
Return no explanation, Markdown, JSON, or extra text.
