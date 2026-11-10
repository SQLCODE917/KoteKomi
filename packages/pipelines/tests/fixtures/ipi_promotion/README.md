# Captured development inputs for IPI promotion

These fixtures come from the IRA development ingestion `igr_c4b8a09978114e49bb63e8c7df73a005`.
The original state is `data/ira-acceptance-20261105-141506-176099/state` on the retained IPI branch.
The capture uses the typed paragraph inspector and validates receipt, stage, source, and evidence bindings.
It calls no models and changes no original records.

The fixture retains paragraph nodes `nod_f1e64380625a2f2c533fc277_0008` and `nod_f1e64380625a2f2c533fc277_0011`.
These hold the Department of Defense policy, Amodei criticism, and integration of Anthropic's services.
Their original paragraph ordinals are 2 and 4; fixture coverage ordinals are 0 and 1.
The coverage report indexes these two paragraphs only.
Its identifier, digest, counts, proposal union, and IngestionChangeSet digest identify that fixture scope.
The original policy manifest and captured stage bytes remain unchanged.
The source representation remains complete so its existing selectors and digests remain valid.
Bundle nodes load in parent-before-child order.
The raw Source bytes and parser fingerprint satisfy the existing Archive and Ledger references.

`ledger.json` contains explicit Domain Core records and a DocumentRepresentationBundle.
The loader parses each record through its declared type and uses typed SQLite writes.
The pending Actor, Organization, and Event ProposedChanges come from the captured ingestion plans.
The fixture contains no Assertion proposal, accepted identity occurrence, construction review, or composition outcome.
The supported decision and recomposition operations create those review prerequisites and outcomes during each test.

The exact expectations in `test_ipi_production_promotion.py` follow the reviewed development meanings.
They are not generated from composition output.
`in  2012` retains the Source's doubled space.
`Prior to the dispute` remains an exact relative-time expression.
These are captured-input integration regressions, not fresh ingestion or independent accuracy evidence.

Run the potentially long regressions under the human-started full-suite procedure in
[the promotion design](../../../../../docs/2026-11-10-ipi-production-promotion.md).
