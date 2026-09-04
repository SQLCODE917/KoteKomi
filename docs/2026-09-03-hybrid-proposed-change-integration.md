# TDD: Hybrid ProposedChange Integration

- Status: Accepted
- Program: [Hybrid Intelligence Extraction Pipeline](2026-09-01-hybrid-intelligence-extraction-pipeline.md)
- Deliverable ID: HP-7
- Depends on: [HP-6 Qualified Event Semantics and Source Support](2026-09-02-qualified-event-semantics-source-support.md)
- Gold catalog: [HP-7 Proposal Admission Gold Catalog](hp7-proposal-admission-gold-v1.json)

## Context & Problem

HP-6 creates governed event semantics and source-support judgments as derived evidence.

HP-6 creates no `ProposedChange` and changes no accepted wiki state.

A reviewer cannot yet inspect an HP-6 event through the existing review flow.

HP-6 also proved that direct support does not prove that an event interpretation is correct.

One Qwen2.5 task misclassified a statement of uncertainty as a recommendation.

Every statement for that event received a separate `directly_supported` judgment.

HP-7 will admit only complete and fully supported event semantics to human review.

Human review will remain the only authority that creates accepted Ledger intelligence.

### Terms

**ProposalDisposition** means `proposed` or `held` for one HP-6 event.

**ProposalAdmissionDecision** means one deterministic disposition with complete reasons and lineage.

**HybridProposalPlan** means one immutable derived plan for all events in one HP-6 Preview.

HP-7 Plans remain paragraph-local derived evidence in the HP-8 document flow.

HP-9 reconciles their named candidates before HP-8 submits ProposedChanges.

**Typed candidate record** means one pending `Actor`, `Organization`, or `Event` record.

**Advisory gap** means an HP-6 gap that records disagreement with an open parent proposal after HP-6 constructed complete governed semantics.

### Primary end-to-end flow

1. An operator selects one immutable HP-6 Preview.
2. The Application Layer validates its complete HP-6 through HP-1 lineage and source evidence.
3. The Application Layer gives every semantic event one deterministic admission decision.
4. KoteKomi constructs typed candidate records and `ProposedAssertion` records for each proposed event.
5. The Archive stores one immutable `HybridProposalPlan` with complete data in and data out.
6. The Ledger atomically stores one provenance activity and every new `ProposedChange`.
7. The existing review flow accepts, edits, or rejects each pending proposal.

## Goals

- A reviewer can inspect governed event semantics through the existing review flow.
- A reviewer can trace every candidate record to exact source evidence and HP-1 through HP-6 decisions.
- A reviewer can distinguish proposed events from held events.
- A reviewer can reject a supported but incorrect event without changing accepted intelligence.
- A repeated submission reuses identical proposals and preserves prior review decisions.

## Requirements

### Parent evidence

- HPC-PAR-01: The operation requires one HP-6 Preview ID.
- HPC-PAR-02: The Application Layer validates the canonical HP-6 bytes and digest.
- HPC-PAR-03: The Application Layer validates the HP-5 through HP-1 lineage.
- HPC-PAR-04: The Application Layer replays every referenced `EvidenceTarget`.
- HPC-PAR-05: A parent validation failure stops before the Archive or Ledger changes.
- HPC-PAR-06: The Application Layer evaluates every HP-6 semantic event.

### Admission policy

- HPC-ADM-01: The Application Layer creates one `ProposalAdmissionDecision` per semantic event.
- HPC-ADM-02: One proposed event has a governed frame and every required frame role.
- HPC-ADM-03: One proposed event has exactly one `SemanticSupportJudgment` for every `SemanticStatement`.
- HPC-ADM-04: Every judgment for one proposed event has outcome `directly_supported`.
- HPC-ADM-05: `missing_required_role` and `missing_governed_attribution` hold a materialized semantic event.
- HPC-ADM-06: A missing or repeated support judgment holds an event.
- HPC-ADM-07: A non-direct support judgment holds an event.
- HPC-ADM-08: Omitted parent proposals and excluded optional qualifiers remain advisory gaps.
- HPC-ADM-09: A parent-attribution disagreement remains an advisory gap when the governed attribution statement has direct support.
- HPC-ADM-10: Every held decision names all applicable reason codes.
- HPC-ADM-11: Admission does not use a model score as confidence or authority.
- HPC-ADM-12: Admission does not run a model task.
- HPC-ADM-13: An `unmapped_frame` belongs to an HP-5 event subject for which HP-6 deliberately created no semantic event; the Plan retains that unresolved subject and gap as a diagnostic and creates no proposal or synthetic admission decision for it.

### Candidate graph construction

- HPC-GPH-01: KoteKomi creates one pending `Event` for each proposed event.
- HPC-GPH-02: KoteKomi creates source-specific pending `Actor` and `Organization` records for eligible typed mention targets.
- HPC-GPH-03: A specific `person` mention maps to an `Actor`.
- HPC-GPH-04: A specific `organization` or `government` mention maps to an `Organization`.
- HPC-GPH-05: An agentive or participant `geopolitical_entity` mention maps to an `Organization`.
- HPC-GPH-06: HP-2 reference decisions select the source expression used for one candidate identity.
- HPC-GPH-07: KoteKomi does not use a ReFinED candidate as an accepted local identity.
- HPC-GPH-08: Unsupported mention kinds remain exact literal assertion objects.
- HPC-GPH-09: Event-subject targets reference another pending Event from the same plan.
- HPC-GPH-10: KoteKomi creates `ProposedAssertion` records for frame type, roles, time, place, polarity, modality, and targeted attribution.
- HPC-GPH-11: A role Assertion records the governed frame role and UpperRole in qualifiers.
- HPC-GPH-12: Every Assertion uses one existing hybrid structural predicate as its relation label.
- HPC-GPH-13: Every Assertion has epistemic scope `source_report` and source authority `unknown`.
- HPC-GPH-14: Every Assertion references its Source and replayable support `EvidenceTarget`.
- HPC-GPH-15: One typed target uses `object_entity_id` and one literal target uses `object_value`.
- HPC-GPH-16: The Event participant lists contain typed agents and participants only.
- HPC-GPH-17: HP-7 creates no `Relationship`.
- HPC-GPH-18: KoteKomi derives every record ID from immutable parent identities.

### Plan and lineage

- HPC-PLN-01: The `HybridProposalPlan` identifies its HP-6 parent and digest.
- HPC-PLN-02: The Plan contains every admission decision in source order.
- HPC-PLN-03: A proposed decision names every ProposedChange ID for its event bundle.
- HPC-PLN-04: A held decision names no ProposedChange ID.
- HPC-PLN-05: Every decision retains its event, gap, statement, judgment, model-run, and trace identities.
- HPC-PLN-06: Every proposed record retains the same HP-1 through HP-6 lineage.
- HPC-PLN-07: The Plan contains complete deterministic data in and data out in `ExtractionStageTrace` records.
- HPC-PLN-08: The Plan uses canonical JSON and a content-derived identity.
- HPC-PLN-09: The Archive reuses byte-identical Plan content.
- HPC-PLN-10: Plan reload validates canonical bytes, parent lineage, and source evidence.

### Ledger publication

- HPC-LED-01: One `ProvenanceActivity` groups every ProposedChange created by the Plan.
- HPC-LED-02: Every ProposedChange references the grouping `ProvenanceActivity`.
- HPC-LED-03: The Application Layer validates every proposal reference against accepted records or the same batch.
- HPC-LED-04: The SQLite Adapter stores the provenance activity and new proposals atomically.
- HPC-LED-05: A repeated submission reuses byte-identical records.
- HPC-LED-06: A repeated submission does not reset an approved, edited, or rejected proposal.
- HPC-LED-07: An identity conflict stops the entire new publication.
- HPC-LED-08: HP-7 creates no accepted `Actor`, `Organization`, `Event`, `Assertion`, or `Relationship`.

### Public operation

- HPC-CLI-01: `kotekomi extraction submit-event-changes` runs HP-7.
- HPC-CLI-02: The command requires `--preview-id`.
- HPC-CLI-03: JSON output reports the Plan ID, disposition counts, proposal counts by record type, and diagnostics.
- HPC-CLI-04: Text output reports the same review summary without requiring a canonical ID as user input to the review flow.
- HPC-CLI-05: A valid Plan exits zero even when every event is held.
- HPC-CLI-06: Invalid parent evidence or failed publication exits one.

## Proposed Architecture

```text
HP-6 Preview -> lineage and evidence replay
                         |
                         v
              deterministic admission
                         |
                         v
                candidate graph plan
                    |            |
                    v            v
                 Archive       Ledger
                                  |
                                  v
                           existing review flow
```

Domain Core owns accepted record validation and the governed event ontology.

The Application Layer owns admission, mapping, reference validation, and transaction intent.

The Archive Adapter stores immutable Plan bytes.

The SQLite Adapter stores the pending proposal batch atomically.

The Pipeline owns configuration, publication order, and public output.

## Key Interactions

```text
Operator   Pipeline   Application   Archive   Ledger   Reviewer
   |          |            |           |        |         |
   | submit   |            |           |        |         |
   |--------->| load Plan  |           |        |         |
   |          |----------->| replay evidence--->|         |
   |          |            | build Plan|        |         |
   |          |            |---------->|        |         |
   |          |            | commit proposals-->|         |
   |<---------| summary    |           |        |         |
   |          |            |           |        | review  |
   |          |            |           |        |<--------|
```

## Data Model

`ProposalAdmissionDecision` is a frozen Application Layer DTO.

It records the event ID, disposition, reason codes, advisory gap IDs, lineage IDs, and ProposedChange IDs.

`HybridProposalPlan` is a frozen Application Layer DTO stored in the Archive.

It records the parent identity, representation identity, decisions, proposal bodies, deterministic grouping provenance identity, traces, and diagnostics.

The timestamped `ProvenanceActivity` is operational Ledger state created atomically with the pending proposals, so it is not part of the content-addressed Plan.

HP-7 adds no accepted Domain record and requires no Ledger migration.

## APIs / Interfaces

The public command is:

```text
kotekomi extraction submit-event-changes --preview-id <HP-6_PREVIEW_ID>
```

The Application Layer exposes explicit plan, prepare, and publication results.

The Archive Port stores and reads one `HybridProposalPlan` by content-derived identity.

The Ledger Port loads referenced records and commits one prepared proposal batch.

## Behavior & Domain Rules

HP-7 stores the immutable Plan before it commits pending Ledger records.

An uncommitted Plan is disposable derived evidence and can be reused by a retry.

The ProposedChange bodies preserve enough lineage to reconstruct the Plan if the Plan copy is unavailable.

Existing review order presents Organizations, Actors, Events, and Assertions in dependency order.

The reviewer supplies the canonical predicate when the reviewer approves one `ProposedAssertion`.

A supported but incorrect event remains a possible pending proposal.

The reviewer rejects that proposal before it can affect accepted intelligence.

Document-wide HP-1 through HP-7 orchestration remains a later deliverable.

## Acceptance Criteria

- AC-HPC-01: Domain and Application tests prove the complete admission matrix.
- AC-HPC-02: Application tests prove typed and literal target mapping for every supported target kind.
- AC-HPC-03: Application tests prove exact source evidence and HP-1 through HP-6 lineage for every proposal.
- AC-HPC-04: Application tests prove no model task runs during HP-7.
- AC-HPC-05: Application and Adapter tests prove atomic publication, rollback, reuse, and review-status preservation.
- AC-HPC-06: Archive tests prove canonical Plan persistence, restart reload, and corruption rejection.
- AC-HPC-07: Pipeline tests prove text output, JSON output, valid empty admission, and typed failures.
- AC-HPC-08: Review tests approve one reviewed Gold event and retain exact evidence and review provenance.
- AC-HPC-09: Review tests reject one supported but incorrect event and create no accepted intelligence from it.
- AC-HPC-10: The canonical evaluation processes the seven HP-6 Gold events and the known Amodei false event.
- AC-HPC-11: The canonical evaluation records exact data in, admission output, proposed JSON, review packet, and review outcome per event.
- AC-HPC-12: The canonical evaluation classifies findings by model, policy, ontology, data, or implementation ownership.
- AC-HPC-13: Two submissions produce the same Plan, IDs, and proposal bodies without duplicates.
- AC-HPC-14: Formatting, Ruff, Pyright, focused tests, and the full test suite pass.

## Reference Implementations

- Parent replay: follow `hybrid_event_semantics_preview.py`.
- Candidate construction: follow `grounded_candidates.py`.
- Review packets and reference order: follow `review_queue_packet.py`.
- Atomic SQLite publication: follow `commit_grounded_candidate_batch`.

## Constraints and Halt Conditions

Stop if HP-7 needs a new model judgment.

Stop if a ReFinED identity must become accepted to construct a proposal.

Stop if a proposed record cannot retain exact source evidence.

Stop if one pending proposal can become accepted without review.
