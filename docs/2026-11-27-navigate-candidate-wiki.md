# Navigate between the Candidate Wiki index, Document, and record pages

## Outcome and ownership

The operator follows generated links to move around one Candidate Wiki without relying on browser history.
Currently, the index links to record pages but not its generated Document page.
Non-index pages have no generated link home.
The existing public planner/renderer fixture demonstrates both gaps.

The Application Layer planner owns page relationships and generated paths.
The Markdown exporter renders those paths relative to each page.
Reuse the existing page/detail link representation where it suffices.
This feature changes no Ledger records or ingestion behavior.

## Acceptance examples

- The index links to the generated Document page using its display filename.
- The Document page links back to the index.
- Every generated record page links to both the index and the Document page.
- Links resolve to emitted files from each page's actual directory, including a filename requiring sanitization.
- Existing record links, quotations, citation JSON, and canonical IDs retain their behavior.
- Rendering the same input twice remains deterministic.

Keep navigation discoverable through the existing presentation; no new navigation framework or persistent schema is required.

## Verification and UAT

Add a failing regression through the public planner and verify the emitted Markdown links with the existing parser.
Run focused planner/exporter tests during editing and fast checks for the candidate.
Full PR CI supplies the full-suite merge gate.
Generate a complete small Wiki in `/private/tmp/kotekomi-navigation-uat` for UAT.
Keep the actual emitted Markdown files and an HTML preview whose local links map to corresponding preview pages.
The operator opens the index, follows Document and record links, and returns home.
This verifies navigation in a synthetic fixture, not ingestion quality.

## Agent handoff for this PR

The implementing agent owns product edits and is the only writer in the checkout.
After committing, submit fast checks followed by push as one bounded job, addressed to `spymaster`.
End the implementing turn with a notice or no_reply; do not poll or issue a second review request.
A generated completion delivered to Spymaster is the review request for its named candidate.
Spymaster reads this package, the candidate diff from main, and the job result, then approves to operator or requests revisions from implementer-1.
A failed job requires an actionable correction request; an uncertain push is inspected before retrying.
Review uses existing results and targeted probes; it does not rerun the full suite or create an independent receipt.
The coordinator observes CI deterministically and hands successful work to the operator for UAT.
