# R19 Provider Supplement Review Packet

Status: Proposed, awaiting human approval.

## Purpose

This packet records the proposed R19 provider supplement, its bound input
digests, the original and re-anchored occurrences, and the unresolved references.

The supplement draft is `docs/hsq-r19-provider-supplement-v1.json`.

The draft cannot authorize composition until a human approves it.

## Bound input digests

| Input | Path | SHA-256 |
| --- | --- | --- |
| Connection Gold | docs/hsq-event-entity-connection-gold-v2.json | afb3b25a421913b8d6b1c29eda90ee681d3bbf71719f7e0377a626bfc6067294 |
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
| is | be | The copula expresses predicative equation; its lemma is be. |
| viewed | viewed | The trigger-head lemma names the viewing relation. |

## Unresolved references

The supplement names these required references that have no accepted canonical
record yet.

- EGE-019 (Sacks, actor): No accepted Actor record for David Sacks exists in the Ledger.
- EGE-020 (Amodei, actor): No accepted Actor record for Dario Amodei exists in the Ledger.
- Assertion evidence_target_id: No EvidenceTarget record exists for the residual source span.

The Ledger holds zero Actor, zero Organization, and zero EvidenceTarget records.

It holds one Source, `src_d97195ee5c8ced32c0cd41b0`, the Wikipedia article on the
Anthropic-United States Department of Defense dispute.

## Missing prerequisites

Composition cannot reach a complete, inspectable Assertion until the unresolved
references above are created as accepted records with their own
ProvenanceActivity.

The pipeline must not fabricate those IDs.

## After approval

1. Create the missing Actor and EvidenceTarget records through a reviewed path.
2. Mark the supplement `review_status` `approved` and update the bound digests.
3. Finish the Assertion constructor, the Pipeline, and the scoring report.