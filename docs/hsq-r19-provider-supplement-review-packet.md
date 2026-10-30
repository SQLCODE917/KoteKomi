# R19 Provider Supplement Review Packet

Status: Approved and run.

## Purpose

This packet records the proposed R19 provider supplement, its bound input
digests, the original and re-anchored occurrences, and the unresolved references.

The supplement draft is `docs/hsq-r19-provider-supplement-v1.json`.

The draft cannot authorize composition until a human approves it.

## Bound input digests

| Input | Path | SHA-256 |
| --- | --- | --- |
| Connection Gold | docs/hsq-event-entity-connection-gold-v2.json | afb3b25a421913b8d6b1c29eda90ee681d3bbf71719f7e0377a626bfc6067294 |
| Proposition Gold | docs/hsq-source-grounded-proposition-gold-v1.json | f496ab64e6590de05b1bc07ef069335fae6a7094b009b2fae3ca02cc627e54b0 |
| AHE-022 input | data/r17-semantic-selection-contract/inputs/AHE-022.json | c5b4a6b0af51d8403d9431c445b8b4b563cd46c58417b50993d265e1198da1b3 |
| AHE-022 source | source_text | f5203eec5a0a146a39dc7e74438ec542884f230f9ca096c006c941979b29651f |
| AHE-051 input | data/r17-semantic-selection-contract/inputs/AHE-051.json | 8f423411c3105c555121beaed5e1e68c4730e3741e4c4d3f952b8cab4fbcb703 |
| AHE-051 source | source_text | 5f07f7fa1cef6f5d818cfa3fc4f2afe8c22f93be9825a0ff28cecdc80558356c |

## Event bindings

| Residual Event | Residual trigger | Provider Event | Provider trigger | Rationale |
| --- | --- | --- | --- | --- |
| AHE-022 | viewed 6-12 | TGE-018 | viewed 6-12 | The Sacks viewing Event; same source modulo whitespace. |
| AHE-051 | final 28-33 | none | none | No Connection Gold Event; subject is a reviewed non-entity value. |

## AHE-022 original and re-anchored occurrences

Each Connection Gold occurrence re-anchors into the AHE-022 single-spaced
coordinate system. Every re-anchored slice is source-exact.

| Entity | Original span | Re-anchored span |
| --- | --- | --- |
| Sacks | 0:5 Sacks | 0:5 Sacks |
| Amodei | 13:19 Amodei | 13:19 Amodei |
| Trump | 71:76 Trump | 71:76 Trump |
| Trump's | 71:78 Trump's | 71:78 Trump's |
| Trump | 268:273 Trump | 256:261 Trump |
| Trump's | 268:275 Trump's | 256:263 Trump's |
| Anthropic | 141:150 Anthropic | 135:144 Anthropic |
| Anthropic's | 141:152 Anthropic's | 135:146 Anthropic's |
| Anthropic | 240:249 Anthropic | 228:237 Anthropic |
| Open Philanthropy | 205:222 Open Philanthropy | 193:210 Open Philanthropy |

## AHE-051 subject-value exclusion

The reviewed exclusion names `The April order` at 5-20 as `non_entity_value`.

The residual subject resolves to that value only after human approval.

## Proposed predicate mappings

| Relation label | Predicate | Rationale |
| --- | --- | --- |
| is | is | The copula surface text is the reviewed predicate; the TDD pins predicate is. |
| view | viewed | The composer folds the trigger-head lemma of viewed to view; the canonical predicate names the reviewed viewing relation. |

## Event evidence

The supplement records one evidence pair per Residual Event.

| Event | SourceAuthority | AttributionBasis | Source | EvidenceTarget |
| --- | --- | --- | --- | --- |
| AHE-022 | secondary | direct_document | src_d97195ee5c8ced32c0cd41b0 | unresolved |
| AHE-051 | secondary | direct_document | src_d97195ee5c8ced32c0cd41b0 | unresolved |

## Unresolved references

The supplement names these required references that have no accepted canonical
record yet.

- EGE-019 (Sacks, actor): No accepted Actor record for David Sacks exists in the Ledger.
- AHE-022 evidence_target_id: No EvidenceTarget record exists for the AHE-022 source span.
- AHE-051 evidence_target_id: No EvidenceTarget record exists for the AHE-051 source span.

Amodei (EGE-020) is embedded in the AHE-022 object value `Amodei's decision`.
The supplement therefore requires no accepted Amodei Actor record.

The Ledger holds zero Actor, zero Organization, and zero EvidenceTarget records.

It holds one Source, `src_d97195ee5c8ced32c0cd41b0`, the Wikipedia article on the
Anthropic-United States Department of Defense dispute.

## Proposed prerequisite records

These proposed records derive from the archived Document. A reviewer creates them
through the existing review workflow as accepted records with a ProvenanceActivity.
The IDs are provisional until that workflow assigns or accepts them.

### Proposed Actor record

| Field | Value |
| --- | --- |
| id | act_david_sacks (provisional) |
| kind | Actor |
| canonical name | David Sacks |
| accepted names | David Sacks, Sacks |
| supporting span | Sacks at 0-5 in the AHE-022 source |

### Proposed EvidenceTarget records

Both targets resolve mechanically against the archived Document's logical text
view `tvw_82b32b975fbbd7dd75627fb3_logical` of representation
`rep_82b32b975fbbd7dd75627fb3`, source
`src_d97195ee5c8ced32c0cd41b0`, document
`doc_eaaad11a475988142cad48d7`.

| Field | AHE-022 | AHE-051 |
| --- | --- | --- |
| id | etg_ahe_022 (provisional) | etg_ahe_051 (provisional) |
| representation_id | rep_82b32b975fbbd7dd75627fb3 | rep_82b32b975fbbd7dd75627fb3 |
| text_view_id | tvw_82b32b975fbbd7dd75627fb3_logical | tvw_82b32b975fbbd7dd75627fb3_logical |
| text_view_digest | 7fcd6f4d104813254de2a930d009d74ce7920925af03195414aad58be872e9c2 | 7fcd6f4d104813254de2a930d009d74ce7920925af03195414aad58be872e9c2 |
| start_char | 4682 | 9992 |
| end_char | 4966 | 10029 |
| node_ids | nod_82b32b975fbbd7dd75627fb3_0013 | nod_82b32b975fbbd7dd75627fb3_0028 |
| exact_text digest | 3ae4294fe559d09dd035e7dfaf027607fdc9ac1ec53848b3f789926357d8f9e7 | b0d7969edcd331a70a44d19a2b9a7c3a2f7d8feaabdd88d3f70441d0b33d27c7 |
| normalization_policy | utf8_identity_v1 | utf8_identity_v1 |

The exact text is the archived double-spaced occurrence. The residual
single-spaced coordinate is its whitespace-normalized form.

## Missing prerequisites

Composition cannot reach a complete, inspectable Assertion until the proposed
Actor and per-Event EvidenceTarget records above are accepted.

The pipeline must not fabricate those IDs.

The loader now cross-checks each binding's source digests and trigger spans
against the bound files, and the closure check verifies each resolved ID's
existence, record type, and Source relationship through the typed repository
boundary.

## After approval

1. Create the proposed Actor and per-Event EvidenceTarget records through a reviewed path.
2. Mark the supplement `review_status` `approved` and update the bound digests.
3. Run the Pipeline and the scoring report.