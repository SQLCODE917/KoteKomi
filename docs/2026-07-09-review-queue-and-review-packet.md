# Review Queue and Review Packet

## 1. Context & Problem

A Review Queue is a deterministic list of ProposedChange records that need review.
A Review Packet is a human-readable view of one ProposedChange with evidence and reference context.
KoteKomi can already approve, reject, and edit ProposedChange records by ID.
KoteKomi does not yet give reviewers enough context to review without raw JSON inspection.

## 2. Goals

- Show pending ProposedChange records in deterministic review order.
- Show one ProposedChange with its proposed record, evidence, and references.
- Let reviewers export editable proposed record JSON for the existing edit command.
- Preserve Domain Core and Application Layer validation at every boundary.
- Keep review presentation derived from Ledger records.
- Make blind approval unnecessary for fixture and real model output.

## 3. Non-Goals & Forbidden Approaches

Non-goals:

- This TDD does not add a terminal user interface.
- This TDD does not add a web review interface.
- This TDD does not change Domain Core record schemas.
- This TDD does not add Ledger tables.
- This TDD does not change approve, reject, or edit semantics.
- This TDD does not make review decisions automatically.

Forbidden approaches:

- The Pipeline must not assemble review meaning from raw JSON.
- The Pipeline must not decide reference validity.
- The Adapter must not decide review ordering.
- The Review Packet must not silently repair malformed ProposedChange records.
- The Review Packet must not hide missing references.
- The export command must not write wrapper metadata into editable record JSON.
- The review presentation must not become canonical Ledger state.

## 4. Requirements

- `review list` must show ProposedChange records awaiting review.
- `review list` must default to `pending` records.
- `review list` must accept a review status filter.
- `review list` must accept a record type filter.
- `review list` must accept Source ID and Document ID filters.
- `review list` must sort records by deterministic review order.
- `review list` must include ProposedChange ID, review status, record type, stable label, Source ID, Document ID, model name, and creation time.
- `review show` must render one Review Packet.
- `review show` must fail when the ProposedChange ID does not exist.
- `review show` must include ProposedChange metadata.
- `review show` must include proposed record fields.
- `review show` must include evidence exact text.
- `review show` must include evidence prefix text and suffix text.
- `review show` must include Source title and Document ID.
- `review show` must include selector type and selector location.
- `review show` must include Assertion epistemic fields for Assertion records.
- `review show` must classify referenced IDs as accepted, pending, or missing.
- `review export` must write proposed record JSON to the requested path.
- `review export` output must be accepted by `review edit --accepted-record-json`.

## 5. Invariants

- ProposedChange remains the review gate before accepted Ledger state.
- A reviewer can approve, reject, or edit a ProposedChange.
- Each approve, reject, or edit action creates a ProvenanceActivity.
- Domain Core records validate accepted record shape.
- The Application Layer validates accepted record references before commit.
- Review Queue and Review Packet outputs are derived read models.
- The Ledger remains the canonical store for ProposedChange records.
- Review presentation does not change review status.

## 6. Proposed Architecture

The Pipeline exposes review commands.
The Application Layer builds Review Queue and Review Packet DTOs.
The Application Layer parses ProposedChange payloads through declared contracts.
The LedgerRepository Port loads ProposedChange records and referenced records.
The SQLite Adapter persists and loads records without review decisions.

```text
+------------------+       +---------------------+
| Pipeline         | ----> | Application Layer   |
| review commands  |       | review read models  |
+------------------+       +----------+----------+
                                      |
                                      v
                           +---------------------+
                           | LedgerRepository    |
                           | existing records    |
                           +----------+----------+
                                      |
                                      v
                           +---------------------+
                           | SQLite Adapter      |
                           | persistence only    |
                           +---------------------+
```

## 7. Key Interactions

### List Review Queue

```text
User -> Pipeline: review list
Pipeline -> Application Layer: list Review Queue
Application Layer -> LedgerRepository: list ProposedChange records
Application Layer -> Application Layer: filter and sort queue items
Application Layer -> Pipeline: ReviewQueueResult
Pipeline -> User: readable table
```

### Show Review Packet

```text
User -> Pipeline: review show ProposedChange ID
Pipeline -> Application Layer: get Review Packet
Application Layer -> LedgerRepository: get ProposedChange
Application Layer -> Domain Core: parse proposed record payload
Application Layer -> LedgerRepository: load Source, Document, EvidenceSpan, and references
Application Layer -> Pipeline: ReviewPacket
Pipeline -> User: readable packet
```

### Export Editable Record

```text
User -> Pipeline: review export ProposedChange ID
Pipeline -> Application Layer: export editable record
Application Layer -> LedgerRepository: get ProposedChange
Application Layer -> Domain Core: parse proposed record payload
Application Layer -> Pipeline: proposed record JSON
Pipeline -> local file: write JSON
```

## 8. Data Model

`ReviewQueueItem` represents one row in the Review Queue.

```text
ReviewQueueItem
- proposed_change_id
- review_status
- record_type
- stable_label
- source_id
- document_id
- model_name
- prompt_id
- created_at
```

`ReviewPacket` represents one ProposedChange for human review.

```text
ReviewPacket
- proposed_change_id
- review_status
- record_type
- stable_label
- proposed_record_json
- metadata
- evidence_contexts
- reference_contexts
- assertion_context
```

`ReviewEvidenceContext` exposes evidence without requiring raw JSON inspection.

```text
ReviewEvidenceContext
- source_id
- source_title
- document_id
- selector_type
- exact_text
- prefix_text
- suffix_text
- location
```

`ReviewReferenceContext` classifies one referenced Domain ID.

```text
ReviewReferenceContext
- referenced_id
- referenced_type
- resolution_status
```

`resolution_status` uses these values:

| Value | Meaning |
|---|---|
| `accepted` | The referenced record exists in accepted Ledger state. |
| `pending` | A pending ProposedChange proposes the referenced record. |
| `missing` | No accepted record or pending ProposedChange contains the reference. |

## 9. APIs / Interfaces

The Application Layer adds `list_review_queue`.
The Application Layer adds `get_review_packet`.
The Application Layer adds `export_review_editable_record`.

`ReviewQueueInput` contains:

- `review_status`
- `record_type`
- `source_id`
- `document_id`

`ReviewPacketInput` contains:

- `proposed_change_id`

`ReviewEditableRecordExportInput` contains:

- `proposed_change_id`

The Pipeline adds these commands:

```text
kotekomi review list
kotekomi review show --proposed-change-id <id>
kotekomi review export --proposed-change-id <id> --output <path>
```

Existing commands remain:

```text
kotekomi review approve
kotekomi review reject
kotekomi review edit
```

## 10. Behavior & Domain Rules

Review Queue sorting uses this record type order:

```text
Organization
Actor
Event
EvidenceSpan
Assertion
Relationship
Outcome
ArgumentEdge
```

Records with the same record type sort by stable label.
Records with the same stable label sort by ProposedChange ID.
Unsupported record types fail before rendering.

A Review Packet parses the proposed record through the matching Domain Core record.
An Assertion packet displays epistemic scope, Source authority, attribution basis, and confidence dimensions.
An EvidenceSpan packet displays exact text and selector fields.
Relationship, Outcome, and ArgumentEdge packets display their referenced IDs with resolution status.

Example:

```text
An Assertion references evs_delay_after_us_cyber_concerns.
The EvidenceSpan has an accepted Ledger record.
The Review Packet marks the reference accepted.
```

Example:

```text
An Assertion references evs_delay_after_us_cyber_concerns.
A pending EvidenceSpan ProposedChange contains that ID.
The Review Packet marks the reference pending.
```

Example:

```text
An Assertion references evs_missing.
No accepted record or pending ProposedChange contains that ID.
The Review Packet marks the reference missing.
```

## 11. Acceptance Criteria

- Application tests prove `list_review_queue` returns pending records by default.
- Application tests prove queue ordering matches deterministic review order.
- Application tests prove queue filters by status, record type, Source ID, and Document ID.
- Application tests prove `get_review_packet` includes evidence context for an Assertion.
- Application tests prove `get_review_packet` includes Assertion epistemic fields.
- Application tests prove accepted references resolve as `accepted`.
- Application tests prove pending references resolve as `pending`.
- Application tests prove absent references resolve as `missing`.
- Application tests prove malformed ProposedChange payloads fail fast.
- Application tests prove unsupported record types fail fast.
- Application tests prove export returns only proposed record JSON.
- Pipeline tests prove fixture output for `review list`.
- Pipeline tests prove fixture output for `review show`.
- Pipeline tests prove `review export` output can feed `review edit`.
- `docs/CHECK_PLAN.md` includes a review queue and packet fixture check.

## 12. Cross-Cutting Concerns

Review Packet rendering can expose Source text.
The CLI prints local Ledger content only.
The command must not fetch network content.

Large proposed records can make CLI output long.
The first implementation prints full packets for correctness.
Pagination belongs to a later terminal user interface.

The Application Layer reports invalid deterministic state with explicit errors.
It does not recover from malformed ProposedChange records.

## 13. Reference Implementations

- `packages/application/src/kotekomi_application/proposed_change_review.py` implements existing review transitions.
- `packages/pipelines/src/kotekomi_pipelines/cli.py` implements current review commands.
- `packages/pipelines/tests/review_helpers.py` defines current deterministic review order.
- GitHub pull request reviews separate review context from approve and change-request actions: <https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/reviewing-changes-in-pull-requests/about-pull-request-reviews>.
- Label Studio quality workflows separate queue ordering, review, correction, and acceptance: <https://labelstud.io/guide/quality.html>.
- Intelligence tradecraft separates evidence, judgments, source quality, and confidence: <https://www.dni.gov/index.php/what-we-do/ic-related-menus/ic-related-links/intelligence-community-directives>.

## 14. Alternatives Considered

- Reuse raw ProposedChange JSON as the review interface: rejected because it encourages blind approval.
- Store Review Packet records in the Ledger: rejected because packets derive from ProposedChange records.
- Put review packet assembly in the Pipeline: rejected because the Application Layer owns domain decisions.
- Add a terminal user interface now: rejected because CLI commands give a smaller shippable contract.

## 15. Halt Conditions

- Halt if Review Packet assembly requires Adapter imports in the Application Layer.
- Halt if packet rendering requires accepting invalid deterministic state.
- Halt if exported JSON cannot round-trip into the existing edit command.
- Halt if a happy-path fixture contains missing references after all expected proposals exist.
