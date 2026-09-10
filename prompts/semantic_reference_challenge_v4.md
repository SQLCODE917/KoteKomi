Read the supplied source context around one target reference and its supplied antecedent candidates.
Perform only semantic antecedent selection for the target reference.
Resolve only the exact target between `source_context_before_target` and `source_context_after_target`.
Each candidate entry contains one exact source expression and nearby wording that identifies its occurrence.
Select one supplied `aN` label only when that exact source expression is what the target reference means in context.
Return `ambiguous` when two or more supplied candidates remain plausible.
Return `unresolved` when no supplied candidate is supported by the source context.
Write the selected value after `antecedent:` on the first line.
Write one concise explanation after `reason:` on the second line.
Return exactly those two lines and no other text.
