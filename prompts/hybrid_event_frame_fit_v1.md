Read the authoritative SourceSegment, one source-bound event expression, and one selected governed frame.
Perform only binary frame-fit verification.
Return `yes` only when the selected frame definition accurately represents the event evoked by the target expression in this source.
Judge the target event itself, not a nearby cause, effect, report, quotation, participant, or nested event.
A frame that is merely the closest available option does not fit.
Return `no` when the expression describes a different event family or no governed frame can represent it accurately.
Do not select a replacement frame, participant, role, qualifier, polarity, modality, attribution, identifier, or source range.
Write the decision as `fit: yes` or `fit: no`.
Put one concise explanation on the second line as `reason: <one non-empty sentence>`.
Do not insert blank lines, JSON, Markdown, headings, or commentary.
Return exactly two complete lines in the pinned literal output contract.
