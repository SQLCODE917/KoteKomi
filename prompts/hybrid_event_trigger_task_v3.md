Read the authoritative SourceSegment and the task block.
Perform only event-occurrence selection.
KoteKomi supplies an ordered catalog where each `oN` is one exact source occurrence.
Select every catalog occurrence that explicitly evokes a real-world action, change, communication, decision, agreement, creation, appointment, movement, or other happening.
Include finite, infinitive, participial, and eventive-nominal occurrences.
Do not select a standing entity, general topic, capability, timeless definition, or unchanged status.
Select the shortest supplied occurrence that clearly evokes each event.
Do not select a policy, product, project, or organization name when a supplied verb evokes the event.
Do not copy or alter source text.
Do not invent an occurrence ID.
Give each selected occurrence a concise lowercase underscore-separated diagnostic event label of one through four words.
The diagnostic label is not governed ontology.
Return selected occurrences in source order.
If the target SourceSegment contains no explicit event, return one abstention line.
Do not infer events that the SourceSegment does not express.
Do not create source offsets, canonical identifiers, external identifiers, or Ledger records.
Write each selection exactly as `event: <supplied_oN> | <event_type>`.
Do not insert blank lines, headings, commentary, or Markdown.
Return only complete lines in the pinned literal output contract.
