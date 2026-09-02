Read the authoritative paragraph and the task block.
Perform only the task named in the task block.
Detect every explicit real-world occurrence whose trigger literal is in the target SourceSegment.
An event is a bounded action, change, communication, decision, agreement, creation, appointment, movement, or other happening.
Do not treat a standing entity, general topic, capability, or timeless definition as an event.
Use the shortest eventive verb or eventive noun that clearly evokes each event.
Never use the name of a policy, product, project, or organization as a trigger when a verb expresses the event.
Do not use a whole clause as a trigger.
Do not return overlapping triggers when one proposed trigger contains another proposed trigger.
In `The agency established a policy`, use `established`, not `established a policy` or the policy name.
In `Its use prompted concerns, leading to protests`, consider `use`, `prompted`, and `protests` separately instead of copying the whole clause.
Copy each trigger character for character from the model-facing SourceSegment.
Use the target SourceSegment label supplied by KoteKomi.
Give each event a concise lowercase underscore-separated proposed type label.
The proposed type label can use one through four words.
Return events in source order with contiguous labels from e1.
If the target SourceSegment contains no explicit event, return one abstention line.
Do not infer events that the paragraph does not express.
Do not create source offsets, canonical identifiers, external identifiers, or Ledger records.
Write `event: ` at the start of every event line.
Use exactly `event: eN | sN | <trigger literal> | <event type>` for every event.
Do not insert blank lines, headings, commentary, or Markdown.
Return only complete lines in the pinned output contract.
