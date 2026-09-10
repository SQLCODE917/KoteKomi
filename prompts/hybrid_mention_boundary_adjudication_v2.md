Judge whether each supplied candidate is a complete expression in the supplied source context.
Perform only mention-boundary completeness judgment.
A complete candidate forms a coherent person, organization, government, place, event, project, initiative, product, policy, publication, or reference expression by itself.
A complete candidate can contain a possessive noun phrase when the full phrase expresses a distinct source meaning.
A proper name that identifies a referent remains complete when it is immediately followed by a possessive suffix and a possessed noun.
For example, in `Acme's services`, both `Acme` and `Acme's services` are complete because they express different source meanings.
An incomplete candidate contains an attached predicate, unrelated clause material, or only part of the expression needed for its source meaning.
Judge each candidate independently.
Overlapping and nested candidates can both be complete.
Do not prefer the longest candidate merely because it contains another complete candidate.
Use unclear when the source context does not determine completeness.
Complete every line listed under `required_output_prefixes` exactly once.
Append only `complete`, `incomplete`, or `unclear` after each supplied prefix.
Use only the supplied prefixes.
Return exactly the completed required-output lines and no other text.
