Read the authoritative SourceSegment and the one target trigger in the task block.
Perform only governed event-frame selection.
KoteKomi supplies the complete list of allowed frame IDs and their definitions.
Choose the one supplied frame whose definition best represents the occurrence evoked by the target trigger.
Judge the target occurrence itself, not a nearby cause, effect, report, quotation, or nested event.
Treat the diagnostic open event label as a fallible hint rather than governed vocabulary.
Return `unresolved` when no supplied frame accurately represents the occurrence.
Do not select participants, role targets, qualifiers, polarity, modality, or attribution.
Do not invent a frame, source text, source offset, identifier, digest, or Ledger record.
Write the decision as `frame: <supplied_frame_id>` or `frame: unresolved`.
Put one concise explanation on the second line as `reason: <one non-empty sentence>`.
Do not insert blank lines, JSON, Markdown, headings, or commentary.
Return exactly two complete lines in the pinned output contract.
