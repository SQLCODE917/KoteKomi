# Review Drain Queue

## 1. Context & Problem

Review Drain repeats one explicit review decision across the pending Review Queue.
KoteKomi can inspect the next Review Packet and apply one explicit Review-Next decision.
KoteKomi still requires repeated commands to review a known-good deterministic batch.
Agents need a bounded batch command that preserves explicit review decisions.

## 2. Goals

- Apply one explicit decision repeatedly to matching pending ProposedChange records.
- Reuse Review-Next decision execution for every item.
- Stop when the queue is empty, the limit is reached, or validation fails.
- Return structured JSON with per-item decision results.
- Keep `pipeline run-next` as review inspection only.

## 3. Non-Goals & Forbidden Approaches

Non-goals:

- This TDD does not add automatic decision inference.
- This TDD does not add scheduling.
- This TDD does not add Ledger tables.
- This TDD does not change Review Queue ordering.
- This TDD does not change approve, reject, or edit semantics.

Forbidden approaches:

- `review drain` must not infer approve, reject, or edit.
- `review drain` must not parse human CLI text.
- `review drain` must not bypass `run_review_next_decision`.
- `pipeline run-next` must not execute `review drain`.
- The Pipeline must not decide review outcomes.
- The Adapter must not decide review outcomes.

## 4. Requirements

- `review drain` must accept `--decision approve`, `--decision reject`, and `--decision edit`.
- `review drain` must require `--reviewer`.
- `review drain --decision reject` must require `--reason`.
- `review drain --decision edit` must require `--accepted-record-json`.
- `review drain` must accept record type, Source ID, and Document ID filters.
- Omitted `--limit` must drain all matching pending ProposedChange records.
- `review drain --limit N` must stop after N matching attempts.
- `review drain --dry-run` must select matching packets without mutating Ledger state.
- `review drain --format json` must emit structured JSON.
- Non-dry-run drain must commit each successful item independently.
- Non-dry-run drain must stop on the first validation failure.
- Prior successful decisions must remain committed when a later item fails.
- `pipeline run-next` must continue to execute only `review next` during Review Required state.

## 5. Invariants

- ProposedChange remains the review gate before accepted Ledger state.
- Every executed review decision creates a ProvenanceActivity.
- Approve and edit decisions validate accepted record shape.
- Approve and edit decisions validate accepted record references before commit.
- Reject decisions do not create accepted records.
- Review decisions remain explicit.
- Deterministic invalid ProposedChange shape fails fast.

## 6. Proposed Architecture

The Pipeline exposes `review drain`.
The Application Layer defines drain DTOs and drain result serialization.
The Application Layer reuses Review-Next decision execution for item decisions.
The Pipeline opens one SQLite transaction per non-dry-run item.
The SQLite Adapter persists records without choosing review outcomes.

```text
+------------------+       +--------------------------+
| Pipeline         | ----> | Application Layer        |
| review drain     |       | Review Drain contract    |
+------------------+       +------------+-------------+
                                        |
                                        v
                             +--------------------------+
                             | Application Layer        |
                             | Review-Next decision     |
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

### Drain Approvals

```text
Reviewer -> Pipeline: review drain --decision approve --reviewer analyst
Pipeline -> Application Layer: validate drain input
Pipeline -> LedgerRepository: open transaction for next item
Pipeline -> Application Layer: run Review-Next decision
Application Layer -> LedgerRepository: write accepted record and ProvenanceActivity
Pipeline -> LedgerRepository: commit item
Pipeline -> Pipeline: repeat until queue empty or failure
Pipeline -> Reviewer: drain summary
```

### Drain Dry Run

```text
Agent -> Pipeline: review drain --decision approve --reviewer analyst --dry-run
Pipeline -> Application Layer: run drain dry run
Application Layer -> LedgerRepository: inspect matching Review Queue
Application Layer -> Pipeline: packet sequence and executed=false
Pipeline -> Agent: JSON result
```

### Stop On Validation Failure

```text
Reviewer -> Pipeline: review drain --decision approve --reviewer analyst
Pipeline -> Application Layer: run Review-Next decision
Application Layer -> LedgerRepository: validation fails before commit
Pipeline -> Pipeline: stop drain
Pipeline -> Reviewer: validation_failed summary
```

## 8. Data Model

`ReviewDrainInput` represents one drain request.

```text
ReviewDrainInput
- decision
- reviewer
- reviewed_at
- record_type
- source_id
- document_id
- reason
- accepted_record_json
- limit
- dry_run
```

`ReviewDrainResult` represents the batch outcome.

```text
ReviewDrainResult
- decision
- attempted_count
- executed_count
- dry_run
- stopped_reason
- item_results
- error_message
```

`stopped_reason` uses these values:

| Value | Meaning |
|---|---|
| `queue_empty` | No matching pending ProposedChange remains. |
| `limit_reached` | The drain reached the requested limit. |
| `validation_failed` | A selected item failed validation. |
| `dry_run_complete` | Dry run selected all requested items. |

## 9. APIs / Interfaces

The Application Layer adds `run_review_drain`.
The Application Layer adds `review_drain_result_to_json`.

The Pipeline adds:

```text
kotekomi review drain --decision approve --reviewer <name>
kotekomi review drain --decision reject --reviewer <name> --reason <reason>
kotekomi review drain --decision edit --reviewer <name> --accepted-record-json <path>
kotekomi review drain --decision approve --reviewer <name> --limit 10
kotekomi review drain --decision approve --reviewer <name> --dry-run
kotekomi review drain --decision approve --reviewer <name> --format json
```

The command accepts:

- `--record-type`
- `--source-id`
- `--document-id`
- `--ledger-path`

## 10. Behavior & Domain Rules

Review Drain selects before each decision.
Selection uses Review Queue order.
The command never accepts a ProposedChange ID.

Example:

```text
The queue has three matching pending Organizations.
review drain --decision approve approves all three Organizations.
stopped_reason = queue_empty
```

Example:

```text
The queue has five matching pending records.
review drain --decision approve --limit 2 approves two records.
stopped_reason = limit_reached
```

Example:

```text
The third selected record fails reference validation.
The first two decisions remain committed.
stopped_reason = validation_failed
```

## 11. Acceptance Criteria

- Application tests prove approve drains all matching pending ProposedChange records.
- Application tests prove approve with `limit=2` executes exactly two decisions.
- Application tests prove reject drains matching pending records with one reason.
- Application tests prove edit drains matching pending records with accepted record JSON.
- Application tests prove filters constrain the drained queue.
- Application tests prove dry run reports selected items and leaves all records pending.
- Application tests prove empty queue returns zero counts and `queue_empty`.
- Pipeline tests prove fixture approve drain can drain the fixture Review Queue.
- Pipeline tests prove fixture `--limit 2` approves exactly two records.
- Pipeline tests prove fixture `--dry-run` leaves pending count unchanged.
- Pipeline tests prove reject and edit forms execute through CLI.
- Pipeline tests prove `pipeline run-next` still executes `review next`.
- `docs/CHECK_PLAN.md` includes Review Drain checks.

## 12. Cross-Cutting Concerns

JSON output is the agent contract.
Text output is for humans.
Both outputs derive from Application Layer DTOs.

The non-dry-run Pipeline command uses one SQLite transaction per item.
The command stops on the first raised validation error.

## 13. Reference Implementations

- `docs/2026-07-10-explicit-review-next-decision-execution.md`
- `packages/application/src/kotekomi_application/proposed_change_review.py`
- `packages/pipelines/src/kotekomi_pipelines/cli.py`
- `packages/pipelines/tests/test_review_proposed_change.py`

## 14. Alternatives Considered

- Make `--limit 10` the default: rejected because fixture and deterministic batch review needs all-pending ergonomics.
- Use one transaction for the whole drain: rejected because prior successful decisions must survive later validation failures.
- Let `pipeline run-next` drain automatically: rejected because Pipeline run-next remains inspection only.

## 15. Halt Conditions

- Halt if Review Drain needs inferred review decisions.
- Halt if `pipeline run-next` must execute Review Drain.
- Halt if the Pipeline must parse human output to find selected ProposedChange records.
- Halt if a failed item can roll back prior successful item commits.
