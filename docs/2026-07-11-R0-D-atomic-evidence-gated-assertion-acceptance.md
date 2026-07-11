# R0-D — Atomic evidence-gated assertion acceptance

Do not merely add a lookup for an existing `AssertionEvidenceLink`. That would create a lifecycle deadlock in the current design:

* `link_assertion_evidence()` currently requires the assertion to already exist;
* the new acceptance invariant requires the direct-support link to exist when the assertion becomes accepted. ([GitHub][3])

Instead, assertion acceptance must atomically commit the assertion **and its evidence links**.

## Add evidence-link specifications to an assertion proposal

For new proposals:

```yaml
record_type: Assertion
record:
  ...
evidence_links:
  - evidence_span_id: evs_...
    role: direct_support
    polarity: supports
    necessity: required
  - evidence_span_id: evs_...
    role: definition
    polarity: contextualizes
    necessity: required
```

For the legacy proposal adapter, translate existing `Assertion.evidence_span_ids` to:

```text
role: direct_support
polarity: supports
necessity: required
```

Make this an explicit compatibility policy, not an invisible permanent assumption.

## Add a pure replay operation

The existing validator returns early for a previously validated target after checking its target digest. Acceptance should perform a full replay against the pinned representation. ([GitHub][3])

Add:

```python
def verify_evidence_target(
    evidence_span: EvidenceSpan,
    repository: EvidenceTargetLedger,
) -> EvidenceReplayResult:
    """Read-only complete selector replay."""
```

It should verify:

* validation status is `VALIDATED`;
* stored target digest still matches the immutable selectors;
* representation and text view exist;
* text-view digest agrees;
* position and exact text agree;
* prefix and suffix agree;
* selected nodes and regions agree;
* source and document agree;
* all supplied selector types identify the same occurrence.

It must not update the evidence record.

## Atomic acceptance algorithm

For a source-backed assertion:

```python
accepted_assertion = construct_accepted_assertion(...)
link_specs = parse_and_validate_link_specs(...)

prepared_links = []

for spec in link_specs:
    evidence = require_evidence(spec.evidence_span_id)
    verify_evidence_target(evidence)

    require evidence.source_id in accepted_assertion.source_ids
    require evidence.id in accepted_assertion.evidence_span_ids

    prepared_links.append(
        deterministic_assertion_evidence_link(...)
    )

require at least one link where:
    role == DIRECT_SUPPORT
    polarity == SUPPORTS
    evidence.validation_status == VALIDATED

save accepted assertion
save all prepared links
save review provenance
update ProposedChange
commit transaction
```

Any failure must roll back all four categories of writes.

The acceptance result should include the created evidence-link IDs so the review packet can show exactly what crossed the authority boundary.

## R0-D acceptance tests

The following must fail atomically:

```text
Source-backed assertion with no evidence links
Only definition/background links
Direct-support link to an unvalidated target
Direct-support link to a stale text-view digest
Direct-support link with selector disagreement
Evidence source absent from assertion.source_ids
Evidence ID absent from assertion.evidence_span_ids
Missing representation
Corrupted representation output digest
Failure while saving the second of several links
```

The following must succeed:

```text
Validated direct-support target
Assertion and all links committed in one transaction
Review provenance preserved
Exact evidence replay works after closing and reopening SQLite
```

This closes the third agreed release gate.

[1]: https://github.com/SQLCODE917/KoteKomi/commits/main "Commits · SQLCODE917/KoteKomi · GitHub"
[2]: https://raw.githubusercontent.com/SQLCODE917/KoteKomi/main/packages/adapters/src/kotekomi_adapters/sqlite_ledger.py "raw.githubusercontent.com"
[3]: https://raw.githubusercontent.com/SQLCODE917/KoteKomi/main/packages/application/src/kotekomi_application/evidence_targets.py "raw.githubusercontent.com"
[4]: https://raw.githubusercontent.com/SQLCODE917/KoteKomi/main/packages/application/src/kotekomi_application/source_file_ingest.py "raw.githubusercontent.com"
[5]: https://raw.githubusercontent.com/SQLCODE917/KoteKomi/main/docs/2026-07-11-source-capture-and-document-versioning.md "raw.githubusercontent.com"
[6]: https://raw.githubusercontent.com/SQLCODE917/KoteKomi/main/packages/adapters/src/kotekomi_adapters/docling_pdf_parser.py "raw.githubusercontent.com"
[7]: https://raw.githubusercontent.com/SQLCODE917/KoteKomi/main/packages/domain/src/kotekomi_domain/models.py "raw.githubusercontent.com"
[8]: https://raw.githubusercontent.com/SQLCODE917/KoteKomi/main/docs/2026-07-11-authoritative-document-ingestion-program.md "raw.githubusercontent.com"

