# TDD: Paragraph Standing Facts MVP

- Status: Accepted for implementation
- Program: [Hybrid Intelligence Extraction Pipeline](2026-09-01-hybrid-intelligence-extraction-pipeline.md)
- Deliverable ID: HP-10
- Depends on: [HP-8 Hybrid Document Orchestration](2026-09-03-hybrid-document-orchestration.md)
- Depends on: [HP-9 Document Entity Reconciliation](2026-09-04-evidence-backed-document-entity-reconciliation.md)

## Context & Problem

The Hybrid Pipeline selects every paragraph from one accepted DocumentRepresentationBundle.

The Pipeline currently sends each selected paragraph through an event-only semantic route.

That route excludes standing relationships and literal attributes by design.

The governed event profile also cannot represent a standing relationship as an Event.

A perfect event model therefore cannot propose many ordinary wiki Assertions.

Examples include organization membership, ownership, location, classification, and attributes.

The Domain Core already represents those statements as Assertions.

The review flow already assigns one canonical predicate to each ProposedAssertion.

HP-10 will add one paragraph-local standing-fact route to the production ingestion flow.

### Terms

**Standing Fact** means one source-reported relationship or attribute that is not a bounded Event.

**Standing Fact Draft** means one source-bound model proposal for a Standing Fact.

**Standing Fact Decision** means one deterministic admission result for a Standing Fact Draft.

**Standing Fact Plan** means one immutable paragraph plan with event and Standing Fact proposals.

**Eligible Mention** means one source-valid mention that satisfies the HP-10 candidate policy.

### Primary end-to-end flow

1. HP-8 completes HP-1 through HP-7 for one paragraph.
2. The Application Layer selects Eligible Mentions from HP-1 and HP-2 evidence.
3. Qwen2.5 proposes Standing Fact Drafts from one exact SourceSegment and a local candidate catalog.
4. The Application Layer validates each draft against authoritative characters and candidate identities.
5. The Application Layer creates pending entity and ProposedAssertion bodies for admitted drafts.
6. HP-9 reconciles the combined paragraph plans before HP-8 closes the IngestionChangeSet.

## Goals

- A user receives pending Assertions for standing relationships in selected paragraphs.
- A user receives pending Assertions for literal attributes in selected paragraphs.
- A reviewer can inspect the exact source text for each proposed Assertion.
- A reviewer can inspect the model input, raw output identity, and deterministic mapping result.
- Existing event proposals remain unchanged and enter the same document reconciliation flow.
- A failed standing-fact task cannot erase valid event proposals or accepted Ledger state.

## Requirements

### Parent evidence

- HSF-PAR-01: HP-10 requires one immutable HP-7 HybridProposalPlan.
- HSF-PAR-02: HP-10 validates the complete HP-7 through HP-1 lineage.
- HSF-PAR-03: HP-10 reloads the authoritative paragraph from the pinned representation.
- HSF-PAR-04: HP-10 validates the paragraph text digest before each model task.
- HSF-PAR-05: A parent validation failure stops before HP-10 writes derived evidence.

### Candidate policy

- HSF-CAN-01: HP-10 uses only HP-1 candidates selected by a MentionBoundaryDecision.
- HSF-CAN-02: An Eligible Mention has referentiality `specific_entity`.
- HSF-CAN-03: An Eligible Mention has contextual kind `person`, `organization`, or `government`.
- HSF-CAN-04: An agentive `geopolitical_entity` is also an Eligible Mention.
- HSF-CAN-05: An agentive geopolitical mention has discourse role `actor` or `participant`.
- HSF-CAN-06: HP-2 applies one resolved explicit alias before candidate display.
- HSF-CAN-07: HP-10 excludes unresolved, generic, anaphoric, and ambiguous candidates.
- HSF-CAN-08: HP-10 skips a SourceSegment with no Eligible Mention without a model call.

### Model task

- HSF-MOD-01: HP-10 runs at most one Standing Fact task per eligible SourceSegment.
- HSF-MOD-02: The task input contains the exact SourceSegment and a local candidate catalog.
- HSF-MOD-03: The task input contains no Ledger ID, source offset, or storage path.
- HSF-MOD-04: The model returns zero or more Standing Fact Drafts in one literal line contract.
- HSF-MOD-05: Each draft names one candidate subject and one free-text relation label.
- HSF-MOD-06: An entity-object draft names one different Eligible Mention.
- HSF-MOD-07: A literal-object draft copies one exact SourceSegment substring.
- HSF-MOD-08: The model returns an explicit abstention when it finds no Standing Fact.
- HSF-MOD-09: The prompt excludes bounded actions and occurrences from Standing Facts.
- HSF-MOD-10: The model does not select a canonical predicate.
- HSF-MOD-11: The runtime archives raw output and records one ModelRun.

### Deterministic mapping

- HSF-MAP-01: The Application Layer resolves task labels to Eligible Mention identities.
- HSF-MAP-02: The Application Layer rejects an unknown or ineligible candidate label.
- HSF-MAP-03: The Application Layer rejects an entity self-relationship.
- HSF-MAP-04: The Application Layer rejects a literal absent from the SourceSegment.
- HSF-MAP-05: The Application Layer rejects a repeated or empty relation label.
- HSF-MAP-06: One valid draft creates one Standing Fact Decision with disposition `proposed`.
- HSF-MAP-07: One rejected draft creates one Standing Fact Decision with disposition `held`.
- HSF-MAP-08: A held decision records every applicable reason code.
- HSF-MAP-09: An invalid draft cannot remove another valid draft from the same model output.
- HSF-MAP-10: KoteKomi derives every record ID from immutable source and policy identities.

### Evidence and proposal construction

- HSF-EVD-01: Every Standing Fact Draft references its exact SourceSegment.
- HSF-EVD-02: Every subject and entity object retains its exact mention selector.
- HSF-EVD-03: Each Assertion EvidenceTarget selects the complete supporting SourceSegment.
- HSF-EVD-04: KoteKomi constructs every entity record and ProposedAssertion body.
- HSF-EVD-05: A person mention creates a pending Actor body.
- HSF-EVD-06: An organization or government mention creates a pending Organization body.
- HSF-EVD-07: An agentive geopolitical mention creates a pending Organization body.
- HSF-EVD-08: An entity object uses `object_entity_id`.
- HSF-EVD-09: A literal object uses `object_value`.
- HSF-EVD-10: A ProposedAssertion stores the model relation as `relation_label`.
- HSF-EVD-11: A ProposedAssertion has epistemic scope `source_report`.
- HSF-EVD-12: A ProposedAssertion references its Source and exact EvidenceTarget.
- HSF-EVD-13: HP-10 creates no accepted Domain record.
- HSF-EVD-14: Review requires one canonical predicate before Assertion acceptance.

### Standing Fact Plan

- HSF-PLN-01: The Standing Fact Plan pins its HP-7 parent bytes and digest.
- HSF-PLN-02: The Plan pins the HP-1 and HP-2 inputs used by the candidate policy.
- HSF-PLN-03: The Plan contains every Standing Fact Draft and Standing Fact Decision.
- HSF-PLN-04: The Plan retains every ModelRun and ExtractionTask identity.
- HSF-PLN-05: The Plan retains one ExtractionStageTrace per SourceSegment task.
- HSF-PLN-06: Each trace contains exact task input and exact parsed output.
- HSF-PLN-07: The Plan includes all unchanged HP-7 ProposedChanges.
- HSF-PLN-08: The Plan includes each admitted HP-10 ProposedChange.
- HSF-PLN-09: The Plan uses canonical JSON and a content-derived identity.
- HSF-PLN-10: The Archive stores and reloads the Plan immutably.
- HSF-PLN-11: Rebuild from identical parent evidence produces byte-identical output.

### Document integration

- HSF-DOC-01: HP-8 records HP-10 after HP-7 in each Paragraph Receipt.
- HSF-DOC-02: An HP-10 failure creates an accounted paragraph gap.
- HSF-DOC-03: An HP-10 failure retains the paragraph's HP-7 event proposals.
- HSF-DOC-04: HP-9 consumes Standing Fact Plans instead of raw HP-7 Plans.
- HSF-DOC-05: HP-9 reconciles entity proposals from both semantic routes together.
- HSF-DOC-06: HP-9 rewrites Standing Fact Assertion references to reconciled identities.
- HSF-DOC-07: HP-8 submits one combined reconciled proposal batch.
- HSF-DOC-08: Retry reuses a valid HP-10 Paragraph Receipt without a model call.
- HSF-DOC-09: Ingestion inspection reports proposed, held, and failed Standing Fact counts.

## Proposed Architecture

```text
HP-1 and HP-2 evidence ----+
                           v
HP-7 event Plan ---> Standing Fact route ---> Standing Fact Plan
                                                   |
                                                   v
                                          HP-9 reconciliation
                                                   |
                                                   v
                                             review queue
```

The Domain Core owns Assertion shape and accepted-state validation.

The Application Layer owns candidate policy, source mapping, and proposal construction.

The ModelRuntime Adapter returns fallible Standing Fact Drafts.

The Archive Adapter stores the immutable Standing Fact Plan.

The Pipeline composes HP-10 between HP-7 and HP-9.

The reviewer owns the canonical predicate and accepted Assertion decision.

## Key Interactions

```text
HP-8       Application       Model       Archive       HP-9
 |              |              |            |            |
 | HP-7 Plan    |              |            |            |
 |------------->| select       |            |            |
 |              | task-------> |            |            |
 |              |<------drafts |            |            |
 |              | map and trace|            |            |
 |              | publish Plan------------->|            |
 | Standing Fact Plan                                      |
 |-------------------------------------------------------->|
```

## Data Model

`StandingFactDraft` is a frozen Application Layer DTO.

It records the subject mention, relation label, object, SourceSegment, and model lineage.

`StandingFactDecision` is a frozen Application Layer DTO.

It records `proposed` or `held`, reason codes, and ProposedChange identities.

`StandingFactPlan` is a frozen Application Layer DTO stored in the Archive.

It records its parent evidence, task evidence, drafts, decisions, traces, and proposal bodies.

HP-10 adds no accepted Domain Core record and requires no Ledger migration.

## APIs / Interfaces

The public ingestion command remains:

```text
kotekomi ingest <PATH> --url <HTTPS_URL>
```

The Application Layer exposes explicit build, publish, and strict-load operations.

The Archive Port reads and writes one Standing Fact Plan by content identity.

The existing review commands continue to require `--canonical-predicate` for Assertions.

## Behavior & Domain Rules

A Standing Fact describes a state, relationship, classification, or literal attribute.

A bounded happening remains the responsibility of the existing Event route.

The model proposes ordinary-language relation labels without growing the Ontology Profile.

KoteKomi admits only candidates whose source identities and characters replay exactly.

Admission proves structural and source alignment.

Admission does not prove world truth or assign a canonical predicate.

The reviewer approves, edits, or rejects each ProposedAssertion.

An abstention is a complete SourceSegment outcome.

A runtime or output failure is an accounted gap.

## Acceptance Criteria

- AC-HSF-01: Model-output tests prove multiple facts, abstention, and strict parsing.
- AC-HSF-02: Application tests prove the complete Eligible Mention matrix.
- AC-HSF-03: Application tests prove entity-object and literal-object mapping.
- AC-HSF-04: Negative tests reject unknown labels, self-relations, and absent literals.
- AC-HSF-05: Application tests prove exact EvidenceTarget and stage-trace replay.
- AC-HSF-06: Application tests prove invalid drafts cannot erase valid drafts.
- AC-HSF-07: Archive tests prove immutable write, strict reload, and corruption rejection.
- AC-HSF-08: HP-9 tests prove event and Standing Fact entities reconcile together.
- AC-HSF-09: HP-8 tests prove combined proposal closure and receipt reuse.
- AC-HSF-10: Review tests accept one Standing Fact with a reviewer predicate.
- AC-HSF-11: Review tests reject one inaccurate Standing Fact without accepted state.
- AC-HSF-12: A fixture ingestion proposes one entity relationship and one literal attribute.
- AC-HSF-13: The fixture run exposes exact data in and data out through stage traces.
- AC-HSF-14: Formatting, Ruff, Pyright, focused tests, and the full test suite pass.
- AC-HSF-15: Canonical PDF validation grades accuracy, recall, traceability, and review safety.

## Reference Implementations

- Model task execution: `hybrid_event_frame_preview.py`.
- Literal output parsing: `hybrid_event_model_output.py`.
- ProposedAssertion construction: `hybrid_proposed_changes.py`.
- Entity reconciliation: `document_entity_reconciliation.py`.
- Immutable Archive evidence: `local_archive.py`.
- Relation extraction baseline: [Stanford OpenIE](https://nlp.stanford.edu/software/openie.html).
- Schema-guided extraction: [UIE](https://aclanthology.org/2022.acl-long.395/).
- Candidate relation selection: [ReLiK](https://aclanthology.org/2024.findings-acl.839/).
- Statement model: [Wikidata statements](https://www.wikidata.org/wiki/Help:Statements).
- Evidence selectors: [W3C Web Annotation](https://www.w3.org/TR/annotation-model/).

## Constraints and Halt Conditions

Stop if HP-10 must create an accepted Assertion without review.

Stop if HP-10 must convert a Standing Fact into a synthetic Event.

Stop if HP-10 requires a canonical predicate vocabulary.

Stop if a proposed subject or object cannot replay to authoritative source characters.

Stop if HP-10 requires list-item or table extraction.
