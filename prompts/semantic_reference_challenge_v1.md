Read the authoritative source context, the one target reference, and the supplied antecedent candidate catalog.
Perform only semantic antecedent selection for the target reference.
F-Coref has proposed the supplied candidates, but its proposal is fallible and is not a decision.
Select one supplied candidate ID only when that exact source expression is what the target reference means in context.
Return `ambiguous` when two or more supplied candidates remain plausible.
Return `unresolved` when no supplied candidate is supported by the source context.
Do not copy an antecedent name or invent a candidate, source range, Entity ID, or Ledger record.
Write the decision as `antecedent: <supplied_candidate_id>`, `antecedent: ambiguous`, or `antecedent: unresolved`.
Put one concise explanation on the second line as `reason: <one non-empty sentence>`.
Do not insert blank lines, JSON, Markdown, headings, or commentary.
Return exactly two complete lines in the pinned output contract.
