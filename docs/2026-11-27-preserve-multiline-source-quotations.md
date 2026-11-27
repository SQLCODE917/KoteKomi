# Preserve paragraphs and line breaks in Candidate Wiki Source quotations

## Outcome and current behavior

A Candidate Wiki lets the operator inspect proposed intelligence and its Source quotations.
Currently, `MarkdownCandidateWikiRenderer.render` replaces quotation newlines with spaces.
For example, two paragraphs and a final line beginning with `-` become one paragraph.
Citation JSON retains the original text.

The operator will see paragraph boundaries and single line breaks in those quotations.
This changes Source quotation normalization preserved by M-06 in the earlier literal-text TDD.
Single-line labels and other page presentation retain their existing behavior.

## Ownership and acceptance examples

The Markdown exporter owns presentation of the existing typed plan.
Its public input and output interfaces remain unchanged.

- In both Event Source quotations and Assertion Exact source quotations, `First paragraph.\n\nSecond paragraph:\n- literal source item` displays two paragraphs with the final item on a new line.
- LF and CRLF inputs display the same line and paragraph boundaries.
- Markdown controls remain literal text, including a line beginning with a heading marker, list marker, blockquote marker, or code fence.
- Every Source line stays inside its generated quotation; input text creates no page heading, list, link, or code block.
- The existing punctuation protection, generated headings, navigation, review labels, and following page sections remain intact.
- Citation JSON preserves the original text exactly; rendering the same plan twice produces identical output.

Keep the change in the exporter and its tests unless inspection establishes another necessary presentation dependency.
No Ledger writes, new persisted records, or fresh ingestion are needed.

## Verification and UAT

Add a failing regression through the public renderer using the existing typed fixture.
Parse the complete emitted page with the existing Markdown parser to verify paragraphs, visible line breaks, literal text, and surrounding structure.
Keep existing Exporter tests passing.
Run focused tests during editing, `./scripts/verify.sh fast` for the candidate, and full PR CI before UAT.
Use the existing background runner for long checks and continue from its completion notification.

Generate one representative rendered HTML page and its Markdown outside the checkout for operator inspection.
Retain a before-example and the final example without creating a new reporting framework.
The operator checks both kinds of quotation and the surrounding page, then accepts UAT and merges.
Engineering checks and agent approval do not supply human acceptance.
