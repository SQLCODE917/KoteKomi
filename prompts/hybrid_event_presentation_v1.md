Read the authoritative SourceSegment, one fixed event frame, and its already selected role targets in the task block.
Perform only event-presentation classification.
Do not change the frame or any role target.
Choose `affirmed` when the source affirms the event and `negated` when it explicitly negates it.
Choose one modality from `actual`, `planned`, `possible`, `uncertain`, `recommended`, or `hypothetical` according to how the source presents the event's realization.
Choose `source_narrator` when the document states the target event directly.
Choose a supplied candidate label or source-occurrence range only when that party supplies the target event as reported content.
Choose `unresolved` when attribution cannot be determined from the supplied source.
Do not confuse a speaker inside one role target with the source presentation of the outer event.
Add a time qualifier only when a supplied source-occurrence range qualifies the target event.
Use `before`, `during`, `after`, or `at` for each time qualifier.
Add a place qualifier only when a supplied source-occurrence range names the target event place.
Do not add a qualifier that belongs only to a nearby or nested event.
Do not create source offsets, identifiers, digests, JSON, or Ledger records.
Put polarity, modality, and attribution first in that order.
Write each time qualifier as `qualifier: time | <relation> | <supplied oN[-oN]>`.
Write each place qualifier as `qualifier: place | <supplied oN[-oN]>`.
Put one concise reason line last.
Do not insert blank lines, Markdown, headings, placeholders, or commentary.
Return only complete lines from the pinned output contract.
