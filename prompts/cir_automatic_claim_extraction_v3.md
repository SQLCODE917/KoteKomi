Return exactly one JSON object and no other text, Markdown, code fence, explanation, or example.

Set `schema_id` to exactly `staged_claim_output_v3`.

Use only the identifier after `evidence_candidate:` as each `evidence_candidate_id`.

For example, `[evidence_candidate:evidence_01]` permits only `"evidence_candidate_id":"evidence_01"`.

Each selected identifier names one complete authoritative source node.

Do not return DocumentNode identifiers, quotations, offsets, TextView IDs, region IDs, or source text.

Do not include `local_id` in an assertion. KoteKomi assigns assertion identities in output order.

Return `abstain` when the context does not support an atomic source claim.
