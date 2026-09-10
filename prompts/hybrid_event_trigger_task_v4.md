Read the authoritative SourceSegment and the task block.
Perform only event-occurrence selection.
KoteKomi supplies an ordered catalog where each `oN` is one exact source occurrence.
Select every explicit real-world action, change, communication, decision, agreement, creation, appointment, movement, or other happening.
For each event, select one contiguous expression range and one event-bearing head occurrence inside that range.
Include auxiliaries, modifiers, particles, and fixed predicate complements in the expression only when they are needed to identify what happened.
Exclude participants and ordinary role arguments that the later role tasks will select.
Choose the lexical verb or eventive nominal as the head, never an auxiliary, modal, determiner, pronoun, conjunction, or preposition.
Include finite, infinitive, participial, and eventive-nominal expressions.
Do not select a standing entity, general topic, capability, timeless definition, or unchanged status.
Select the shortest meaning-complete contiguous expression that clearly evokes each event.
Do not select a policy, product, project, or organization name when a supplied verb evokes the event.
Do not copy or alter source text.
Do not invent an occurrence ID.
Give each selected occurrence a concise lowercase underscore-separated diagnostic event label of one through four words.
The diagnostic label is not governed ontology.
Return selected occurrences in source order.
If the target SourceSegment contains no explicit event, return one abstention line.
Do not infer events that the SourceSegment does not express.
Do not create source offsets, canonical identifiers, external identifiers, or Ledger records.
Write each selection exactly as `event: <supplied_oN[-oN]> | <supplied_head_oN> | <event_type>`.
Do not insert blank lines, headings, commentary, or Markdown.
Return only complete lines in the pinned literal output contract.
