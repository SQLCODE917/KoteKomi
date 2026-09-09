Read the authoritative SourceSegment and the one selected event-frame role in the task block.
Perform only target selection for that one supplied role.
The supplied frame and role are fixed.
Do not select or return another frame or role.
Select the explicit source expression that fills the target role for the occurrence evoked by the target trigger.
Return a supplied `cN` label only when that complete MentionCandidate fills the role.
When a candidate's reference metadata is `resolved`, interpret that candidate as its supplied antecedent but still return the `cN` label.
When a supplied candidate is the complete named head inside a possessive or appositive expression and fills the role, return its `cN` label rather than the larger expression.
Otherwise return the smallest contiguous range from the supplied source-occurrence catalog that fills the role.
Write a one-occurrence range as `oN` and a multi-occurrence range as `oN-oN`.
KoteKomi, not you, reconstructs exact source wording and punctuation from that selector.
Do not infer an unstated participant, cause, result, action, or object.
Do not substitute an organization, product, worker, event, owner, or reporter merely because it is related to the correct target.
When an action has a separately identifiable resource introduced by `including`, `such as`, or equivalent wording, stop the action target before that introducer.
Include a determiner such as `a`, `an`, or `the` when it belongs to the complete source expression.
Exclude punctuation that only terminates the selected expression, clause, or sentence.
Use only labels present in the supplied candidate catalog.
Use only occurrence IDs present in the supplied source-occurrence catalog and put them in source order.
Never output an invented label, occurrence, literal, or placeholder.
Return `target: absent` when no explicit, identifiable source target fills this role.
Write the target exactly as `target: <supplied cN, supplied oN[-oN], or absent>`.
Put one concise explanation on the second line as `reason: <one non-empty sentence>`.
Do not insert blank lines, JSON, Markdown, headings, or commentary.
Return exactly two complete lines in the pinned output contract.
