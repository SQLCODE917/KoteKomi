Read the authoritative SourceSegment and the one selected event frame role in the task block.
When `rejected_previous_target` is present, correct that exact validation failure instead of repeating the rejected target shape.
Select only the explicit source expression that fills `target_role` for the event evoked by `target_trigger`.
The supplied frame and role are fixed; do not select or return another frame or role.
Return a supplied `cN` label only when that complete MentionCandidate fills the role.
When a supplied candidate is the complete named head inside a possessive or appositive expression and fills the role, return its `cN` label rather than the larger expression.
Return a supplied `eN` label only when that sibling event fills the role.
Otherwise copy the smallest complete source literal that fills the role.
Preserve the source wording and punctuation in a copied source literal.
Do not infer an unstated participant, cause, result, action, or object.
Do not substitute an organization, product, worker, or event merely because it is related to the correct target.
An agent that performs or reports an action is not automatically the object or beneficiary of that action.
When an action has a separately identifiable resource introduced by `including`, `such as`, or equivalent wording, stop the action target before that introducer.
Include a determiner such as `a`, `an`, or `the` when it is part of the complete source expression.
A description or category target must not begin with the grammatical linking word `as`; retain any determiner that follows it.
Exclude a comma, semicolon, or period that only terminates the selected expression, clause, or sentence.
Use only labels that appear in the task's candidate and sibling-event catalogs.
Never output an invented label or a placeholder such as `cN`, `eN`, or `sN`.
Return `target: absent` when no explicit identifiable source target fills the role.
Write the target exactly as `target: <supplied cN or eN label, exact source literal, or absent>`.
Put one concise explanation on the second line as `reason: <one non-empty sentence>`.
Do not insert blank lines, JSON, Markdown, headings, or commentary.
Return exactly two complete lines in the pinned output contract.
