# Explicit Review-Next Decision Execution

## 1. Context & Problem

Explicit Review-Next Decision Execution applies one reviewer decision to the next pending ProposedChange.
KoteKomi can select the next Review Packet with `review next`.
KoteKomi can approve, reject, or edit a ProposedChange by ID.
Agents still need a command that selects the next ProposedChange and applies one explicit decision without parsing human output.

## 2. Goals

- Select the same pending ProposedChange as `review next`.
- Apply exactly one explicit reviewer decision.
- Reuse existing approve, reject, and edit review transitions.
- Return structured agent JSON for the selected packet and decision result.
- Keep `pipeline run-next` as review inspection only.

## 3. Non-Goals & Forbidden Approaches

Non-goals:

- This TDD does not add automatic approval.
- This TDD does not change Review Queue ordering.
- This TDD does not change approve, reject, or edit semantics.
- This TDD does not add Ledger tables.
- This TDD does not add Domain Core records.
- This TDD does not add a scheduler.

Forbidden approaches:

- `review run-next` must not infer approve, reject, or edit.
- `review run-next` must not parse human CLI text.
- `review run-next` must not bypass Application Layer review use cases.
- `pipeline run-next` must not execute `review run-next`.
- The Pipeline must not decide review outcomes.
- The Adapter must not decide review outcomes.

## 4. Requirements

- `review run-next` must accept `--decision approve`, `--decision reject`, and `--decision edit`.
- `review run-next` must require `--reviewer`.
- `review run-next --decision reject` must require `--reason`.
- `review run-next --decision edit` must require `--accepted-record-json`.
- `review run-next` must accept record type, Source ID, and Document ID filters.
- `review run-next` must select the first matching pending ProposedChange in Review Queue order.
- `review run-next` must execute one review decision per invocation.
- `review run-next --dry-run` must select and validate the Review Packet without mutating Ledger state.
- `review run-next --format json` must emit structured JSON.
- Empty matching Review Queue state must return `has_next=false` and `executed=false`.
- Malformed selected ProposedChange state must fail fast.
- Failed approve or edit reference validation must roll back the Ledger transaction.
- `review next` action plans must point to `review run-next --decision`.
- `pipeline run-next` must continue to execute only `review next` during Review Required state.

## 5. Invariants

- ProposedChange remains the review gate before accepted Ledger state.
- Each executed review decision creates a ProvenanceActivity.
- Approve and edit decisions validate accepted record shape.
- Approve and edit decisions validate accepted record references before commit.
- Reject decisions do not create accepted records.
- Review decisions remain explicit.
- Deterministic invalid ProposedChange shape fails fast.

## 6. Proposed Architecture

The Pipeline exposes `review run-next`.
The Application Layer selects the next Review Packet and applies the explicit decision.
The Application Layer reuses existing review transition use cases.
The LedgerRepository Port loads and writes ProposedChange, accepted records, and ProvenanceActivity records.
The SQLite Adapter persists records without choosing review outcomes.

```text
+------------------+       +--------------------------+
| Pipeline         | ----> | Application Layer        |
| review run-next  |       | Review-Next decision     |
+------------------+       +------------+-------------+
                                        |
                                        v
                             +--------------------------+
                             | Application Layer        |
                             | approve/reject/edit      |
                             +------------+-------------+
                                        |
                                        v
                             +--------------------------+
                             | LedgerRepository         |
                             | Ledger records           |
                             +------------+-------------+
                                        |
                                        v
                             +--------------------------+
                             | SQLite Adapter           |
                             | persistence only         |
                             +--------------------------+
```

## 7. Key Interactions

### Approve Next ProposedChange

```text
Reviewer -> Pipeline: review run-next --decision approve --reviewer analyst
Pipeline -> Application Layer: run next review decision
Application Layer -> Application Layer: get Review-Next result
Application Layer -> Application Layer: approve selected ProposedChange
Application Layer -> LedgerRepository: write accepted record and ProvenanceActivity
Application Layer -> Pipeline: ReviewNextDecisionResult
Pipeline -> Reviewer: text or JSON result
```

### Dry Run Next Decision

```text
Agent -> Pipeline: review run-next --decision approve --reviewer analyst --dry-run
Pipeline -> Application Layer: run next review decision
Application Layer -> Application Layer: get Review-Next result
Application Layer -> Pipeline: selected packet and executed=false
Pipeline -> Agent: JSON result
```

### Empty Queue

```text
Agent -> Pipeline: review run-next --decision approve --reviewer analyst
Pipeline -> Application Layer: run next review decision
Application Layer -> Application Layer: get Review-Next result
Application Layer -> Pipeline: has_next=false and executed=false
Pipeline -> Agent: JSON result
```

## 8. Data Model

`ReviewNextDecisionInput` represents one explicit decision attempt.

```text
ReviewNextDecisionInput
- decision
- reviewer
- reviewed_at
- record_type
- source_id
- document_id
- reason
- accepted_record_json
- dry_run
```

`ReviewNextDecisionResult` represents the selected packet and decision outcome.

```text
ReviewNextDecisionResult
- has_next
- item
- packet
- decision
- executed
- dry_run
- review_result
```

`decision` uses these values:

| Value | Meaning |
|---|---|
| `approve` | Approve the selected ProposedChange as proposed. |
| `reject` | Reject the selected ProposedChange with a reason. |
| `edit` | Approve the selected ProposedChange with corrected accepted record JSON. |

## 9. APIs / Interfaces

The Application Layer adds `run_review_next_decision`.
The Application Layer adds `review_next_decision_result_to_json`.

The Pipeline adds:

```text
kotekomi review run-next --decision approve --reviewer <name>
kotekomi review run-next --decision reject --reviewer <name> --reason <reason>
kotekomi review run-next --decision edit --reviewer <name> --accepted-record-json <path>
kotekomi review run-next --decision approve --reviewer <name> --dry-run
kotekomi review run-next --decision approve --reviewer <name> --format json
```

The command accepts:

- `--record-type`
- `--source-id`
- `--document-id`
- `--ledger-path`

## 10. Behavior & Domain Rules

`review run-next` selects before applying a decision.
Selection uses Review Queue order.
The command never accepts a ProposedChange ID.

Example:

```text
The first pending Review Queue item is anthropic_ai_lab.
review run-next --decision approve approves anthropic_ai_lab.
```

Example:

```text
The first matching Assertion has a missing EvidenceSpan reference.
review run-next --decision approve fails before commit.
The ProposedChange remains pending.
```

Example:

```text
No matching pending ProposedChange exists.
review run-next returns has_next=false and executed=false.
```

## 11. Acceptance Criteria

- Application tests prove approve selects and approves the first pending Review Queue item.
- Application tests prove reject selects and rejects the first pending Review Queue item.
- Application tests prove edit selects and edits the first pending Review Queue item.
- Application tests prove filters constrain selection.
- Application tests prove empty matching queue returns `has_next=false`.
- Application tests prove dry run does not mutate ProposedChange, accepted records, or ProvenanceActivity.
- Application tests prove missing reject reason fails before mutation.
- Application tests prove missing edit JSON fails before mutation.
- Application tests prove malformed selected ProposedChange fails fast.
- Pipeline tests prove fixture approve through `review run-next`.
- Pipeline tests prove fixture reject through `review run-next`.
- Pipeline tests prove fixture edit through `review run-next`.
- Pipeline tests prove dry run leaves pending count unchanged.
- Pipeline tests prove `pipeline run-next` still executes `review next`.
- `docs/CHECK_PLAN.md` includes Review-Next decision execution checks.

## 12. Cross-Cutting Concerns

JSON output is the agent contract.
Text output is for humans.
Both outputs derive from Application Layer DTOs.

The command opens one Ledger transaction.
The transaction rolls back when validation fails.

## 13. Reference Implementations

- `docs/2026-07-10-review-next-execution.md`
- `packages/application/src/kotekomi_application/review_queue_packet.py`
- `packages/application/src/kotekomi_application/proposed_change_review.py`
- `packages/pipelines/src/kotekomi_pipelines/cli.py`

## 14. Alternatives Considered

- Add ProposedChange ID to `review run-next`: rejected because the command must select the next queue item.
- Let `pipeline run-next` apply decisions: rejected because Pipeline run-next must remain inspection only.
- Implement review transitions in the Pipeline: rejected because the Application Layer owns status transitions.

## 15. Halt Conditions

- Halt if the command needs inferred review decisions.
- Halt if `pipeline run-next` must execute approve, reject, or edit.
- Halt if the Pipeline must parse human output to find a ProposedChange.
- Halt if a failed review decision can partially commit Ledger state.
