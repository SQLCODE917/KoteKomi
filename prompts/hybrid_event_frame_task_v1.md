Read the authoritative paragraph, candidate catalog, and event trigger in the task block.
Perform only the task named in the task block.
Describe the supplied event trigger without detecting another event.
Copy the exact event label from the task block into the first output line.
If the task says `event: e2`, return `event: e2`; never return the placeholder `eN`.
Use only candidate labels supplied by KoteKomi.
Each candidate row supplies its SourceSegment, source literal, interpretation dimensions, reference status, and a source-proved antecedent or none.
When a candidate has a resolved antecedent, interpret the candidate through that antecedent but still return the supplied candidate label.
Assign every candidate that participates in this event one concise lowercase underscore-separated role label.
Do not assign candidates that belong only to another event in the paragraph.
A role label can use one through four words.
Use separate argument lines when several candidates have the same role.
Use the SourceSegment that directly supports each role assignment.
Use only SourceSegment labels listed in `valid_source_segments`.
Use an unresolved anaphoric candidate when the source expresses a participant but KoteKomi has not resolved its antecedent.
Do not replace a candidate with outside knowledge or an external identity.
Set polarity to negated only when the source denies that the event occurred.
Set modality to actual when the source presents the event as having occurred.
Set modality to planned for an intended, promised, or threatened future event.
Set modality to possible for a conditional or merely possible event.
Set modality to uncertain when the source explicitly says occurrence is unknown or disputed.
Set modality to recommended for an event proposed as advice or policy guidance.
Set modality to hypothetical for a counterfactual or illustrative event.
Use source_narrator attribution when the paragraph states the event directly.
Otherwise use candidate labels for explicit reporting, quoting, or claiming sources.
An event participant, object, policy, project, product, time, or place is not an attribution source merely because it is named.
Use a candidate as attribution only when the paragraph explicitly presents it as reporting, quoting, or claiming this event.
Add time and place qualifiers only for exact literals that qualify this event.
Represent a time or place as a qualifier, not as an argument.
If the source supplies no literal time or place for this event, return no qualifier line.
Money, entity descriptions, and whole event clauses are not time or place qualifiers.
Copy each qualifier character for character from its model-facing SourceSegment.
Do not judge whether the source is true or sufficient evidence.
Do not create source offsets, canonical identifiers, external identifiers, or Ledger records.
The first four lines must be `event`, `polarity`, `modality`, and `attribution`, in that order.
Write each argument as `argument: cN | <role> | sN`.
Write each qualifier as `qualifier: time|place | sN | <literal>`.
Do not insert blank lines, headings, commentary, or Markdown.
Do not omit a required field even when its value appears obvious.
Choose one allowed value and never copy alternatives separated by `|` from the output contract.
Return only complete lines in the pinned output contract.
