# Review-Next Execution

## 1. Context & Problem

Review-Next Execution is the safe execution of the next review inspection step.
KoteKomi can list a Review Queue, show a Review Packet, and apply explicit review decisions by ProposedChange ID.
Agents still need a single command that selects the next pending ProposedChange and returns the packet without parsing queue text.
The review gate must stay explicit because approve, reject, and edit decisions require reviewer judgment.

## 2. Goals

- Select the next pending ProposedChange in deterministic Review Queue order.
- Return the selected Review Packet as human text and agent JSON.
- Return structured action plans for approve, reject, and edit commands.
- Let Pipeline run-next execute the safe review inspection step.
- Keep review decisions in explicit review commands.

## 3. Non-Goals & Forbidden Approaches

Non-goals:

- This TDD does not add automatic approval.
- This TDD does not add a terminal user interface.
- This TDD does not add a web review interface.
- This TDD does not add Ledger tables.
- This TDD does not change Domain Core record schemas.
- This TDD does not change approve, reject, or edit semantics.

Forbidden approaches:

- The Pipeline must not infer approve, reject, or edit.
- `pipeline run-next` must not execute approve, reject, or edit.
- Agents must not parse human Review Queue text to pick a ProposedChange.
- Review-Next must not mutate review status.
- Review-Next must not write accepted Ledger records.
- Review-Next must not repair malformed ProposedChange records.

## 4. Requirements

- `review next` must inspect pending ProposedChange records by default.
- `review next` must select the first pending item in Review Queue order.
- `review next` must accept record type, Source ID, and Document ID filters.
- `review next` must report `has_next`.
- `review next` must return the selected Review Queue item.
- `review next` must return the selected Review Packet.
- `review next` must return approve, reject, and edit action plans.
- Each action plan must include command text, argv, readiness, missing inputs, and blockers.
- Approve action plans must require a reviewer.
- Reject action plans must require a reviewer and reason.
- Edit action plans must require a reviewer and accepted record JSON path.
- `review next --format json` must emit structured JSON.
- `review next` must return `has_next=false` when no matching pending ProposedChange exists.
- `review status` must recommend `kotekomi review next` when review is required.
- Pipeline Review Required state must plan `kotekomi review next`.
- `pipeline run-next` must execute `review next` in Review Required state.

## 5. Invariants

- ProposedChange remains the review gate before accepted Ledger state.
- Review-Next is a derived read model.
- Review-Next does not become canonical Ledger state.
- Review-Next does not create ProvenanceActivity records.
- Review-Next does not change accepted Ledger records.
- Review-Next parses selected ProposedChange payloads through Domain Core records.
- Deterministic invalid ProposedChange shape fails fast.
- Explicit review commands remain the only review status transition commands.

## 6. Proposed Architecture

The Pipeline exposes `review next`.
The Application Layer selects the first Review Queue item and builds its Review Packet.
The Application Layer builds action plans for existing review commands.
The LedgerRepository Port loads ProposedChange records and referenced records.
The SQLite Adapter persists and loads records without review decisions.

```text
+------------------+       +---------------------+
| Pipeline         | ----> | Application Layer   |
| review next      |       | Review-Next DTO     |
+------------------+       +----------+----------+
                                      |
                                      v
                           +---------------------+
                           | LedgerRepository    |
                           | Ledger records      |
                           +----------+----------+
                                      |
                                      v
                           +---------------------+
                           | SQLite Adapter      |
                           | persistence only    |
                           +---------------------+
```

## 7. Key Interactions

### Agent Reads Next Review Packet

```text
Agent -> Pipeline: review next --format json
Pipeline -> Application Layer: get next review packet
Application Layer -> LedgerRepository: list ProposedChange records
Application Layer -> Application Layer: select first queue item
Application Layer -> LedgerRepository: get selected ProposedChange and references
Application Layer -> Pipeline: ReviewNextResult
Pipeline -> Agent: JSON object
```

### Pipeline Executes Review Inspection

```text
Agent -> Pipeline: pipeline run-next --format json
Pipeline -> Application Layer: get Pipeline Next Step
Application Layer -> Pipeline: command plan for review next
Pipeline -> Pipeline: dispatch planned argv
Pipeline -> Application Layer: get next review packet
Pipeline -> Agent: captured Review-Next output
```

### Reviewer Applies Explicit Decision

```text
Reviewer -> Pipeline: review next
Pipeline -> Reviewer: selected Review Packet and action plans
Reviewer -> Pipeline: review approve ProposedChange ID and reviewer
Pipeline -> Application Layer: approve ProposedChange
Application Layer -> LedgerRepository: write accepted record and ProvenanceActivity
```

## 8. Data Model

`ReviewNextResult` represents the next pending review unit.

```text
ReviewNextResult
- has_next
- item
- packet
- action_plans
```

`item` is a `ReviewQueueItem`.
`packet` is a `ReviewPacket`.
Both fields are null when `has_next=false`.

`action_plans` uses `ReviewActionPlan`.

```text
ReviewActionPlan
- action
- command
- argv
- ready_to_execute
- missing_inputs
- blockers
```

Review action plans mirror Pipeline command-plan fields without importing Pipeline types.

`ReviewActionPlanBlocker` describes why a review action plan is not ready.

```text
ReviewActionPlanBlocker
- blocker_type
- blocker_id
- reason
```

## 9. APIs / Interfaces

The Application Layer adds `get_review_next`.
The Application Layer adds `review_next_result_to_json`.

`ReviewNextInput` contains:

- `record_type`
- `source_id`
- `document_id`

The Pipeline adds:

```text
kotekomi review next
kotekomi review next --format json
kotekomi review next --record-type <record_type>
kotekomi review next --source-id <source_id>
kotekomi review next --document-id <document_id>
```

## 10. Behavior & Domain Rules

Review-Next selection uses the existing Review Queue order.
The command selects one pending ProposedChange.
The command returns no packet when the filtered pending queue is empty.

Example:

```text
The pending Review Queue starts with Organization anthropic_ai_lab.
review next returns the anthropic_ai_lab Review Packet.
```

Example:

```text
The reviewer approves anthropic_ai_lab.
The next review next call returns the next pending Review Queue item.
```

Example:

```text
The selected ProposedChange lacks a record object.
review next fails before rendering output.
```

## 11. Acceptance Criteria

- Application tests prove Review-Next selects the first pending Review Queue item.
- Application tests prove Review-Next filters by record type, Source ID, and Document ID.
- Application tests prove Review-Next returns `has_next=false` for an empty filtered queue.
- Application tests prove Review-Next returns a Review Packet for the selected item.
- Application tests prove Review-Next JSON includes structured item, packet, and action plans.
- Application tests prove Review-Next fails fast on malformed selected ProposedChange records.
- Pipeline tests prove fixture `review next` renders the first pending Review Packet.
- Pipeline tests prove fixture `review next --format json` parses as JSON.
- Pipeline tests prove `review next` advances after explicit approval.
- Pipeline tests prove `review status` recommends `kotekomi review next`.
- Pipeline tests prove `pipeline next` plans `review next` during Review Required state.
- Pipeline tests prove `pipeline run-next` executes `review next` during Review Required state.
- Pipeline tests prove `pipeline run-next` does not approve, reject, or edit ProposedChange records.
- `docs/CHECK_PLAN.md` includes Review-Next checks.

## 12. Cross-Cutting Concerns

JSON output is the agent contract.
Text output is for humans.
Both outputs derive from the same Application Layer DTOs.

The command reads local Ledger state only.
The command does not fetch network content.

## 13. Reference Implementations

- `docs/2026-07-09-review-queue-and-review-packet.md`
- `docs/2026-07-09-review-readiness-agent-state.md`
- `docs/2026-07-09-pipeline-run-next-execution.md`
- `packages/application/src/kotekomi_application/review_queue_packet.py`
- `packages/pipelines/src/kotekomi_pipelines/cli.py`

## 14. Alternatives Considered

- Keep `review list` as the Review Required next step: rejected because agents would need a second command to obtain the selected packet.
- Add `review run-next --decision`: rejected for this slice because review decisions require explicit reviewer judgment.
- Auto-approve valid packets: rejected because ProposedChange review is the accepted state gate.

## 15. Halt Conditions

- Halt if Review-Next must infer review decisions.
- Halt if Review-Next mutates review status.
- Halt if Review-Next writes accepted Ledger records.
- Halt if agent JSON requires parsing human CLI text.
