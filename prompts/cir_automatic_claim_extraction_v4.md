Return exactly one JSON object and no other text, Markdown, code fence, explanation, or example.

Set `schema_id` to exactly `staged_claim_output_v4`.

Every non-abstention response must have the top-level fields `kind`, `schema_id`,
`organizations`, `evidence`, and `assertions`. Set its top-level `kind` to exactly
`"candidates"`. Never return an assertion list without this candidate envelope.

Use only the identifier after `evidence_candidate:` as each `evidence_candidate_id`.

For example, `[evidence_candidate:evidence_01]` permits only `"evidence_candidate_id":"evidence_01"`.

Each selected identifier names one complete authoritative source node.

Do not return DocumentNode identifiers, canonical KoteKomi identifiers, quotations, offsets, TextView IDs, region IDs, or source text.

Each assertion has an `object`. Use `{"kind":"organization_reference","organization_local_id":"..."}` when its object is one organization listed in this task's `organizations` output. Use `{"kind":"literal","value":"..."}` for an ordinary literal value. Never use an organization local identifier as a literal value.

An `organization_reference.organization_local_id` must exactly equal one `organizations[].local_id` in this same response. A literal `value` must be non-empty. If either condition cannot be met, return `abstain`; do not emit a partial assertion.

Use this exact assertion shape, with no additional fields:

```json
{
  "subject_organization_local_id": "org_01",
  "evidence_local_id": "ev_01",
  "predicate": "ordinary_source_grounded_relation",
  "object": {"kind": "organization_reference", "organization_local_id": "org_02"}
}
```

For a literal object, replace only `object` with:

```json
{"kind": "literal", "value": "non-empty source-grounded value"}
```

Do not include `local_id` in an assertion. KoteKomi assigns assertion identities in output order. Do not include `object_value`.

Return `abstain` when the context does not support an atomic source claim.
