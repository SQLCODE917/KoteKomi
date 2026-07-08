# propose_assertions

You are proposing KoteKomi ProposedChange records from one Source-backed Document.

Return structured JSON only:

```json
{
  "proposals": [
    {
      "record_type": "Assertion",
      "stable_label": "short_stable_label",
      "record": {},
      "evidence": {
        "selector_type": "exact_text",
        "exact_text": "",
        "source_id": "",
        "document_id": ""
      }
    }
  ]
}
```

Rules:

- Use canonical Domain Core terms: Actor, Organization, Event, EvidenceSpan, Assertion, Relationship, Outcome, and ProposedChange.
- Preserve Source and Document references in every evidence object.
- Preserve exact EvidenceSpan text for Source-backed Assertions.
- Separate `source_report_confidence`, `extraction_confidence`, and `world_truth_confidence`.
- Use `assertion_type = "analytic_inference"` only for analytic inferences.
- Do not create accepted records. The output proposes records for review.
