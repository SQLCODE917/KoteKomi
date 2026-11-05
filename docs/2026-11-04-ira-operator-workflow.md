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

### 1a. Case screening result

The current selection and composition path has not demonstrated a semantically complete case
for the stored Anthropic-DoD population; the bounded complement increment is specified in
[IRA-01 Case Screening](2026-11-04-ira-case-screening.md).
The previously demonstrated case `sge_8f37b32d221d8974c7725e42` is retained as a semantic-loss
counterexample, and the population screening with its evidence and the two required decisions is
recorded in [IRA-01 Case Screening](2026-11-04-ira-case-screening.md).
IRA-01-A stays open until a scope decision is made and a screened case is approved.

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

## 3a. Evidence qualification

The pipeline hold regression (`packages/pipelines/tests/test_unsupported_complement_hold.py`)
is a **failure-injection integration test**: it replaces both derivation call sites with an
unsupported outcome. It proves that the hold survives review, persistence, replay, and retry
without creating an Assertion proposal. It does not prove recognition from actual tokens.
Recognition at the derivation boundary is covered separately by
`test_blog_post_complement_is_unsupported_because_it_governs_a_clause`, which runs on the
stored parse with the unmodified derivation.

## 3b. Retained-run disclosure and the live acceptance root

The retained run `data/operator-r20-20261103-150517` **contains approvals created by earlier
test runs** of the stored-case tests, before those tests copied the run. It is evidence, not a
fresh fixture: the copied-run tests are supplementary checks, and their state starts
post-approval.
Clean-checkout acceptance evidence is the deterministic fresh-state journey in
`packages/pipelines/tests/test_operator_journey.py`, which drives normal ingestion from the
committed PDF and captured analyzer/model responses into a fresh temporary Ledger and asserts:
the Event and candidate exist with hold `assertion_inputs_unavailable`, no accepted identity
occurrence or construction review exists, the review creates the prerequisites, recomposition
creates exactly one pending Assertion proposal, and replay shows the Assertion with both
supporting spans.
The live acceptance run and the product-measure report must use a **fresh state root**, not the
retained run.

## 3c. Verification provenance

Two results are recorded separately, at different revisions:

| Scope | Revision | Result |
|---|---|---|
| Full current suite | `9f945d5` | `EXIT=0` (`/tmp/full2.log`, log inspected; it does **not** cover the later test correction) |
| Reconciled residual-composition file (8 tests) | `1b5fe11` | 8 passed; `ruff format --check` 691 files; `ruff check` clean; `pyright` 0 errors on the file |

A full-suite run at `1b5fe11` has not been performed; the only change after `9f945d5` is one
test file, so the full-suite result is reported for `9f945d5` and the focused result for
`1b5fe11`, not merged into a single claim.

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

The exact fresh-root commands, Event discovery, probes, and measures inputs are in
[IRA Operator Handoff](2026-11-04-ira-operator-handoff.md).

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
