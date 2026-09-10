Read the supplied source context around one exact target reference and one supplied antecedent candidate.
Decide only whether the target reference means that supplied candidate in this context.
Return `supported` when the source wording supports the candidate as the target's antecedent.
Return `unsupported` when the source wording shows that the target means something else.
Return `unclear` when the source wording does not determine whether the candidate is the target's antecedent.
Write the selected verdict after `verdict:` on the first line.
Write one concise explanation after `reason:` on the second line.
Return exactly those two lines and no other text.
