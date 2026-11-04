# Ingestion to Reviewed Assertion Agile Package

- Status: In progress
- Program ID: `ingestion-to-reviewed-assertion`
- Parent: [Hybrid Intelligence Extraction Pipeline](2026-09-01-hybrid-intelligence-extraction-pipeline.md)
- Predecessor: [Ingestion Stabilization Agile Package](2026-11-03-ingestion-stabilization-agile-package.md)
- First deliverable: IRA-01, Pin one supported Event and its expected Assertion
- Next deliverable: IRA-05 human-run operator check

## User Outcome

An operator ingests a PDF and sees why one Event cannot yet produce an Assertion.
The operator opens a generated review packet and makes the missing decisions through a supported command.
The operator explicitly recomposes the Event and sees a correct proposed Assertion with evidence in replay.
The resulting pending ProposedChange is discoverable through the existing review workflow.
The operator writes no IDs, evidence selectors, dependency tokens, or recomposition request JSON.

An Assertion is an atomic statement with a subject, predicate, object, classifications, and evidence.
A ProposedChange awaits human review before it changes accepted Ledger state.
Completing this package produces a reviewable proposed Assertion, not an automatically accepted Assertion.
Accepting that Assertion remains a separate action through the existing review workflow.

## Context and Current Behavior

R19 demonstrated deterministic composition for two reviewed residual Events.
[R20](2026-10-30-ingestion-live-references.md) connected accepted identity occurrences, composition, and replay to normal ingestion.
The Ingestion Stabilization Agile Package unified ingestion interfaces and composition persistence.

The stabilization package records an operator run with 36 paragraphs and 167 Event composition outcomes.
All 167 outcomes report `assertion_inputs_unavailable`.
Those counts describe that run, not general extraction accuracy.

The [operator instructions](operator-ingestion.md) currently require calling Application Layer identity use cases and supplying recomposition JSON.
The recomposition request contains inventories, tokens, source coordinates, identity mappings, predicates, and classifications.
The system already holds much of that information in the Ledger and Archive.
The missing capability is a supported operator workflow that obtains those inputs and records the remaining human decisions.

This package targets that workflow rather than another prompt experiment.
It preserves the distinction between correct selection, complete composition, reviewed identity, and accepted Assertion state.

## Planned Operator Flow

1. Normal ingestion persists an Event and a visible composition hold.
2. The operator selects the Event from the run and opens its generated review packet.
3. The operator reviews identity, predicate, and classification decisions using source evidence.
4. Application Layer use cases validate the decisions and commit approved prerequisites through the existing acceptance path.
5. The operator invokes explicit recomposition by selecting the Event; the Pipeline obtains its inputs from stored records.
6. Replay shows the proposed Assertion and supporting spans; the review workflow exposes its pending ProposedChange.

For this package, a review packet means a proposed operator-facing view of one Event, its evidence, and unresolved decisions.
It is an interface description, not a new Domain Core record type.
Focused TDDs define its stored contracts before implementation.

## Scope and Preservation Rules

The development case comes from the existing Anthropic–United States Department of Defense dispute PDF.
IRA-01 selects one Event with a supported subject–predicate–object structure and same-view evidence.
The case must require review of at least one identity occurrence produced by ingestion.
IRA-01 records the Event, IngestionRun, paragraph, source bindings, and expected Assertion content before implementation.
The case becomes development evidence and cannot serve as independent held-out validation.

The package generates replayable EvidenceTargets from archived coordinates and validates them through the existing evidence path.
The operator reviews meaning-bearing choices, including identity, predicate, AssertionType, SourceAuthority, and AttributionBasis.
An existing accepted decision can be reused only when its declared scope covers the selected Event and Source.
Absent decisions remain visible; the implementation supplies no implicit classification or identity acceptance.
The Application Layer generates canonical IDs and validates references.

Accepted identity occurrences continue through `propose_identity_occurrence` and `accept_identity_occurrence`.
The live reference Adapter continues to read accepted occurrences only.
The shared selector, composer, Assertion constructor, composition store, and replay reader remain the retained implementations.
New code does not substitute reviewed expected selections or Assertions for production output.
Historical R16–R19 evidence, reviewed fixtures, prompts, and frozen contracts remain unchanged.

The package excludes:

- Automatic acceptance of Assertions or model candidates.
- New model experiments, substitutions, prompt tuning, or ranking experiments.
- New selection policies or general extraction accuracy work.
- Cross-view reference resolution, multiple-subject composition, and unsupported time/place composition.
- Briefing generation and automatic recomposition after approval.
- Resolving all 167 Events or claiming that one successful case establishes reliability.

If the selected case exposes a defect in an existing supported contract, reproduce it with a failing test.
Record the violated requirement and bounded correction in the deliverable TDD.
A new unsupported semantic capability requires an explicit scope revision.

## Ownership

| Component | Responsibility |
| --- | --- |
| Application Layer | Assemble review content, validate decisions, own review transitions, and request transactions through Ports |
| Adapters | Load ingestion records, persist decisions and outcomes, and replay EvidenceTargets |
| Pipelines | Resolve the selected run and Event, compose use cases, and expose supported commands |
| Replay presentation | Display the persisted hold or proposed Assertion with source spans and review status |
| Domain Core | Validate accepted identity, evidence, provenance, ProposedChange, and Assertion invariants |

CLI commands and Textual presentation reuse Application Layer decisions.
Adapters do not choose identity kinds, predicates, classifications, or review outcomes.
The review interface can extend existing CLI commands; this package does not require a new Textual editor.

## Deliverable Tracker

| ID | Deliverable | Depends on | Status | Evidence |
| --- | --- | --- | --- | --- |
| IRA-01 | Pin one supported Event and its expected Assertion | None | In review | The fixture case is withdrawn as a correctness claim: it uses the community-health press release and drops the `is excited to` construction. Demonstrated on the stored parse of the Anthropic-DoD run: `sge_8f37b32d221d8974c7725e42` selects `Sacks` / `Amodei's decision` and composes with no structural hold; the proposed Assertion awaits human review |
| IRA-02 | Generate an evidence-backed review packet | IRA-01 | In progress | `kotekomi review event-packet`; `test_cli_commands_drive_the_journey_without_json_authoring`, `test_review_packet_rejects_an_event_from_another_run`, `test_packet_rejects_a_changed_source_text` |
| IRA-03 | Record operator decisions and accept prerequisites | IRA-02 | In progress | `kotekomi review decide`; `test_decision_accepts_prerequisites_and_is_idempotent`, `test_decision_rejects_a_candidate_outside_the_packet`, `test_conflicting_decision_is_rejected` |
| IRA-04 | Recompose into a reviewable Assertion and replay it | IRA-03 | In progress | `kotekomi review recompose`; `test_recomposition_proposes_assertion_and_replay_shows_it`, `test_recomposition_retry_keeps_one_proposal` |
| IRA-05 | Verify the operator journey and record product measures | IRA-04 | In progress | Automated journey test in `packages/pipelines/tests/test_operator_journey.py`; real-PDF operator run outstanding |

### IRA-01: Pin one supported Event and its expected Assertion

Inspect the existing run through typed observability commands.
Select one supported Event without modifying production policy to fit the case.
Record its expected subject, predicate, object, qualifiers, classifications, and source spans for human review.
Preserve portable source and deterministic ingestion fixtures sufficient to test the same structure from a clean checkout.
Existing saved ingestion can guide development; automated acceptance still starts through normal ingestion.

Acceptance:

- [ ] IRA-01-A: A human-reviewed development record pins one Event and its expected content independently of the implementation.
- [x] IRA-01-B: Deterministic fixtures drive normal ingestion to a paragraph, Event, and review-eligible identity candidate.
- [x] IRA-01-C: Tests assert those prerequisites and the persisted hold before testing any review or composition behavior.
- [x] IRA-01-D: The focused TDD records the supported structure and explicit reasons that other structures remain outside scope.

### IRA-02: Generate an evidence-backed review packet

The operator selects a run and Event through a supported command.
The system assembles source text, trigger, candidate identities, required decisions, and replayable evidence from stored ingestion records.
The packet distinguishes generated suggestions, unresolved decisions, and already accepted records.
Its bindings prevent a decision from applying to a different Event, paragraph, or source revision.

Acceptance:

- [x] IRA-02-A: A command generates the packet from the ingested Event without hand-written source coordinates or IDs.
- [x] IRA-02-B: Every displayed evidence span replays against the archived Document representation.
- [x] IRA-02-C: Tests reject incorrect coordinates, changed source bindings, and an Event selected from another run.
- [x] IRA-02-D: Generation leaves accepted identity and Assertion state unchanged and exposes missing inputs explicitly.

### IRA-03: Record operator decisions and accept prerequisites

The operator reviews the packet through supported commands that name choices and show their evidence.
The workflow supports linking an existing Actor or Organization and proposing a new identity.
The system records approved construction decisions so recomposition can load them by Event.
The existing acceptance use case validates and commits identity, evidence, occurrence, and provenance atomically.
The focused TDD specifies review storage, decision bindings, rejection, retry, and partial-completion behavior.

Acceptance:

- [ ] IRA-03-A: The command records identity, predicate, and classification decisions without requiring Python calls or JSON authoring.
- [x] IRA-03-B: A repeated mention can reuse an accepted identity without creating a duplicate identity.
- [x] IRA-03-C: Missing, rejected, or stale decisions preserve an explicit hold and create no accepted Assertion.
- [ ] IRA-03-D: Real SQLite tests prove rollback on a write failure and prevent stale or duplicate decision application.

### IRA-04: Recompose into a reviewable Assertion and replay it

The operator explicitly requests recomposition using the selected run and Event.
The Pipeline loads validated tokens, inventory, accepted occurrences, evidence, and reviewed construction decisions.
The Application Layer reuses production selection, composition, and Assertion construction.
The workflow persists the composed outcome and exposes a pending ProposedChange for the proposed Assertion.
Replay labels the Assertion as proposed and renders its supporting source spans after reload.
The focused TDD defines retry behavior when canonical proposal storage succeeds before derived outcome persistence.

Acceptance:

- [x] IRA-04-A: Recomposition requires no operator-authored `RecompositionRequest` JSON and invokes the retained production path.
- [x] IRA-04-B: The proposed Assertion matches the reviewed subject, predicate, object, qualifiers, classifications, and evidence.
- [x] IRA-04-C: Replay changes from held to composed and displays both supporting argument spans for the selected case.
- [x] IRA-04-D: The existing review workflow discovers one pending Assertion ProposedChange; recomposition does not accept it.
- [ ] IRA-04-E: Retry after an interrupted write neither loses the proposal nor creates duplicate proposals for an unchanged decision.

### IRA-05: Verify the operator journey and record product measures

One automated boundary test invokes normal ingestion, packet generation, review, explicit recomposition, and replay loading.
It uses deterministic analyzer and model fixtures with real SQLite transactions and archived evidence replay.
It seeds neither composition outcomes nor accepted identity occurrences and imports no Connection Gold provider.
The operator then runs the supported workflow on the real PDF and records the outcome.

Acceptance:

- [x] IRA-05-A: The automated test proves the complete planned operator flow using the supported command paths.
- [x] IRA-05-B: A clean checkout runs the test without local operator files or manual `PYTHONPATH` changes.
- [ ] IRA-05-C: A human-run check demonstrates the same journey on the real PDF with durable evidence and no manual JSON plumbing.
- [ ] IRA-05-D: A report lists Event IDs, proposed Assertion IDs, remaining holds, and the measures below.
- [ ] IRA-05-E: Operator instructions include exact commands, durable paths, completion probes, and interpretation of proposed versus accepted state.
- [x] IRA-05-F: Applicable tests, formatting, lint, typecheck, and preserved R19/R20 and stabilization regressions pass.

## Product Measures

The report declares the IngestionRun and Event population before counting results.
It distinguishes whole-run counts from the single selected development case.

| Measure | Definition |
| --- | --- |
| Events discovered | Distinct persisted Events in the declared population |
| Review packets generated | Events with validated source bindings and an actionable decision list |
| Correct, complete Assertion proposals | Events whose proposed content matches reviewed expectations and whose evidence replays |
| Remaining holds | Events still held, listed individually and counted by reason |
| Operator effort | Decision actions, command invocations, and any manual repair needed for the selected case |

Report proposed Assertions without reviewed correctness as unassessed, not correct.
Keep grammar, selection, and composition diagnostics as supporting measures.
Record operator effort without claiming improvement until a comparable baseline exists.

## Execution and Verification

Execute IRA-01 through IRA-05 in order.
Write a focused TDD before changing a boundary contract.
Keep design, implementation, and operator-run evidence in separate commits.
Each tracker row records its TDD, implementation revision, exact verification commands, and results.
Each deliverable adds its repeatable checks to [CHECK_PLAN.md](CHECK_PLAN.md).

Use deterministic local tests during implementation and reuse saved ingestion for diagnosis.
Live model calls and accepted-state writes to the operator Ledger require the documented human-run handoff.
Follow the [long-running operations rules](agent/long-running-operations.md) for command, output paths, completion probe, and success criteria.
Do not start a new full-model ingestion for each intermediate change.
Preserve failed and unrun checks in the evidence record.

## Completion and Next Direction

The package completes when all five deliverables have evidence for every acceptance checkbox.
Completion requires one correct, complete, proposed Assertion through the supported operator workflow on the real PDF.
A generated packet, an accepted identity, a passing component test, or a persisted hold alone does not satisfy that bar.
The operator must not repair IDs, selectors, tokens, or recomposition JSON to finish the journey.

Completion does not establish general extraction reliability or complete the Source-Grounded Attachment Agile Package.
Independent held-out validation remains separate and outstanding.
After this journey works, expand to a small fixed development set and measure coverage before freezing for held-out validation.
Each investigation must name the implementation decision its result changes.
