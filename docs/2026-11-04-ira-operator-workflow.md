# TDD: Operator Workflow from Ingestion to a Proposed Assertion

- Status: Accepted for the workflow contract; the development case is withdrawn
  pending a source-faithful case from the required Anthropic-DoD PDF
- Deliverables: IRA-01 through IRA-05
- Parent: [Ingestion to Reviewed Assertion](2026-11-04-ingestion-to-reviewed-assertion-agile-package.md)
- Baseline revision: `a0e2bc1`

## 1. Development case (IRA-01) - withdrawn, plumbing evidence only

Review finding: the automated fixture uses `packages/adapters/tests/fixtures/pdf/2025-community-health-improvement-plan-press-release.pdf`.
That is a community-health press release, not the Anthropic-United States Department of
Defense dispute PDF the package requires.
The fixture also forces `share` to be the clause root and drops the surrounding
construction `is excited to`. The resulting Assertion therefore proves plumbing, not
correct extraction, and the case is withdrawn as a correctness claim.

The required PDF exists only as a local operator input at
`raw/Anthropic-United_States_Department_of_Defense_dispute.pdf`; it is not tracked, so a
clean checkout cannot use it.
A source-faithful development case therefore requires the operator run below, and
IRA-01-A stays open until a human selects and reviews that case.

The deterministic fixture case remains useful for the workflow tests. Its pinned values
are plumbing evidence only: paragraph `_0012`, trigger `share` at 75..80, subject
`HealthyJoCo` at 49..60, object `Plan` at 114..118, hold `assertion_inputs_unavailable`.

| Element | Pinned value |
|---|---|
| Paragraph node | ends with `_0012` |
| Paragraph text | 450 characters, source digest recorded by the packet |
| Trigger | `share`, paragraph offsets 75..80 |
| Subject | `HealthyJoCo`, paragraph offsets 49..60 |
| Object | `Plan`, paragraph offsets 114..118 |
| Relation label | `share` |
| Review-eligible candidate | `HealthyJoCo` from HP-3 eligibility and link evidence |
| Ingestion state | one Event with hold `assertion_inputs_unavailable` |

Expected Assertion for the *fixture* case (plumbing evidence; not a correctness claim,
and not the package's development case):

| Field | Proposed value |
|---|---|
| Type | `reported_observation` |
| Epistemic scope | `source_report` |
| Subject | newly accepted `Organization` for `HealthyJoCo` |
| Predicate | `shared` |
| Object | value `Plan` |
| Qualifiers | `polarity: affirmed`, `modality: actual` |
| Source authority | `secondary` |
| Attribution basis | `direct_document` |
| Evidence | a statement EvidenceTarget covering subject, predicate, and object |
| Status | `proposed` |

Declared out of scope: multi-subject composition, cross-view references, unsupported
time or place composition, automatic acceptance, and prompt or policy changes.

### 1a. Demonstrated development case (agent-verified on the stored parse; awaiting human review)

The withdrawn proposal failed on structure: for `Anthropic publicly disagreed with the administration's policies`, the stored parse attaches both nouns to `disagreed` as `obl`, so selection realizes only `subject` and composition holds on `unsupported_time_place`.
A reviewed predicate cannot supply a missing object role.

The demonstration below uses the saved operator run `igr_3a167add040a4fcc8aec6aba36363502` and its stored tokens.
No model call is involved.

**Selected case: `sge_8f37b32d221d8974c7725e42`**

| Element | Verified value |
|---|---|
| Paragraph node | `nod_da86f9a7f68fd497cb47a88e_0013` |
| Paragraph source digest | `c608ac71f813d95607a005494b5cc90fb949590778631fcec2e34bf09e57327a` |
| TextView / representation | `tvw_da86f9a7f68fd497cb47a88e_logical` / `rep_da86f9a7f68fd497cb47a88e` |
| Node start | 4682 |
| Trigger | `viewed`, 6..12 (label `view`) |
| Subject boundary | `Sacks`, 0..5 (absolute 4682..4687) |
| Object boundary | `Amodei's decision`, 13..30 (absolute 4695..4712) |
| Statement span | 0..30, `Sacks viewed Amodei's decision` (absolute 4682..4712) |
| Selection | `selected`, realized roles `subject`, `object` |
| Composition | `composed`, no structural hold (label `view`, subject `Sacks`, object `Amodei's decision`) |
| Identity candidate | `Sacks` at 0..5 from HP-3 eligibility and link evidence; review required |

Proposed expected Assertion (agent-drafted; awaiting human review):

| Field | Proposed value |
|---|---|
| Type | `reported_observation` |
| Epistemic scope | `source_report` |
| Subject | newly accepted `Actor` for `Sacks` |
| Predicate | `viewed` |
| Object | value `Amodei's decision` |
| Qualifiers | `polarity: affirmed`, `modality: actual` |
| Source authority | `secondary` |
| Attribution basis | `direct_document` |
| Evidence | statement EvidenceTarget over 4682..4712 |
| Status | `proposed` |

Context: the sentence continues `to attend the World Economic Forum over Trump's second inauguration`.
The statement span preserves the asserted relation and excludes that infinitive adjunct, and composition does not hold on it.
The reviewed predicate `viewed` matches the R19 precedent for this relation.

Negative evidence from the same scan: `sge_6054fa9e10adfd8c6ec99d0a` and `sge_fc5ecf8c1d8dfb15a312e0e4` both realize subject and object yet hold on `unsupported_time_place`, which is why the demonstration step precedes approval.

Reproduction: load the run's paragraph inputs and token artifacts, build the constituent inventory for the Event, run `select_source_grounded_constituents`, then `compose_event_from_resolution` with one synthetic accepted organization reference.
The probe prints the values above.


## 2. Contracts

`kotekomi_application.event_construction_review` owns the packet DTO, the decision input,
the decision digest, the reviewed-decision use case, and the assertion-input conversion.
`kotekomi_pipelines.event_review_workflow` assembles the packet from stored records and
composes the use cases. `EventConstructionReview` is a Domain Core record with the
`event_construction_reviews` table (migration `013`).

The packet binds the IngestionRun, Event, paragraph, TextView digest, source text digest,
and the exact displayed spans. The reviewed-decision use case rejects a decision whose
candidate is absent from the packet, and it rejects a second different decision for the
same Event.

Recomposition requires an approved review bound to the same source digest. It loads the
pinned token artifact, the constituent inventory, and the accepted occurrence, then calls
the retained `compose_ingested_event` and the retained Assertion constructor.

## 3. Supported commands

```bash
uv run kotekomi --config <config> review event-packet --run <igr_...> --event <sge_...>
uv run kotekomi --config <config> review decide --run <igr_...> --event <sge_...> \
  --candidate-text HealthyJoCo --identity-kind organization --identity new:HealthyJoCo \
  --predicate shared --assertion-type reported_observation \
  --source-authority secondary --attribution-basis direct_document --reviewer <name>
uv run kotekomi --config <config> review recompose --run <igr_...> --event <sge_...>
```

The operator supplies decisions only. IDs, evidence selectors, dependency tokens, and
recomposition JSON come from stored records.

## 4. Acceptance evidence

| Check | Evidence |
|---|---|
| IRA-01-B/C | `test_normal_ingestion_persists_event_candidate_and_hold` |
| IRA-02-A/B | `test_cli_commands_drive_the_journey_without_json_authoring` |
| IRA-02-C | `test_review_packet_rejects_an_event_from_another_run`, `test_packet_rejects_a_changed_source_text` |
| IRA-02-D | `test_recomposition_without_a_review_keeps_the_hold` |
| IRA-03-A/B | `test_decision_accepts_prerequisites_and_is_idempotent` |
| IRA-03-C | `test_decision_rejects_a_candidate_outside_the_packet`, `test_conflicting_decision_is_rejected` |
| IRA-04-A/B/C | `test_recomposition_proposes_assertion_and_replay_shows_it` |
| IRA-04-D | the pending `Assertion` ProposedChange assertions in the same test |
| IRA-04-E | `test_recomposition_retry_keeps_one_proposal` |
| IRA-05-A/B | the whole file runs normal ingestion with no seeded outcomes and no Connection Gold |
| IRA-05-C | operator handoff below; human-run result outstanding |

## 5. Operator handoff for the real-PDF check (IRA-05-C)

Commands, run against a disposable state root and the real model configuration:

```bash
uv run kotekomi --config <config> ingest <press-release.pdf> --url <source-url>
uv run kotekomi ingestions list
uv run kotekomi --config <config> review event-packet --run <igr_...> --event <sge_...>
uv run kotekomi --config <config> review decide --run <igr_...> --event <sge_...> \
  --candidate-text <candidate> --identity-kind <actor|organization> \
  --identity <new:Name|existing:act_...> --predicate <predicate> \
  --assertion-type <reported_observation|reported_claim> \
  --source-authority <primary|secondary|tertiary|unknown> \
  --attribution-basis <direct_document|second_hand_report|anonymous_report|unknown> \
  --reviewer <name>
uv run kotekomi --config <config> review recompose --run <igr_...> --event <sge_...>
uv run kotekomi review list --record-type Assertion
uv run kotekomi-live-replay --state-root <state-root>
```

Durable outputs: `<state-root>/kotekomi.db`, `<state-root>/archive/`,
`<state-root>/token-artifacts/`, `<state-root>/composition-outcomes/<event>.json`.
Completion probe: `review recompose` prints `"status": "composed"` and an
`assertion_status` of `proposed`; `review list --record-type Assertion` lists one pending
record for that Event; replay shows the composition section with both supporting spans.
Success criteria: one correct, complete, proposed Assertion whose content matches the
reviewed decision and whose evidence replays.

## 6. Limitations

- The development case and its expected Assertion are agent-authored and await human review.
- The real-PDF operator run is outstanding; IRA-05-C is open until it is recorded.
- The journey covers one Event and one paragraph. It says nothing about extraction accuracy.
- Cross-view references remain out of scope.
