# TDD: Evidence-Backed Document Entity Reconciliation

- Status: Implemented; canonical verification pending
- Program: [Hybrid Intelligence Extraction Pipeline](2026-09-01-hybrid-intelligence-extraction-pipeline.md)
- Increment: HP-9
- Depends on: [Hybrid Document Orchestration](2026-09-03-hybrid-document-orchestration.md)
- Scope: document-local Actor and Organization candidate identities

## Context & Problem

HP-7 creates one candidate Actor or Organization identity from one source mention.

HP-8 retains each paragraph HP-7 Plan before it sees the complete document candidate set.

Two mentions of `Anthropic` can therefore create two pending Organization records and two Wiki pages.

The source mentions are distinct evidence.

The source mentions can still denote one real-world entity.

HP-9 will separate source mention identity from candidate entity identity.

HP-9 will reconcile candidates after HP-8 accounts for every paragraph.

HP-9 will run before HP-8 submits pending ProposedChanges.

### Terms

**Entity Identity Cluster** means one document-local candidate identity for one Actor or Organization.

**Entity Identity Decision** means one terminal assignment for one mention-derived candidate record.

**Identity Match Justification** means the recorded reason for one candidate assignment.

**Document Reconciliation Preview** means the immutable derived HP-9 reconciliation result.

**Document Proposal Plan** means the immutable proposal batch rewritten to use reconciled identities.

### Primary flow

1. HP-8 verifies every Paragraph Receipt and reloads every HP-7 Plan.
2. The Application Layer groups exact names and source-declared aliases by entity kind.
3. The Application Layer writes one Entity Identity Decision for every candidate record.
4. The Application Layer publishes one Document Reconciliation Preview.
5. The Application Layer rewrites one Document Proposal Plan with the reconciled identities.
6. HP-8 atomically submits that Plan and closes the IngestionChangeSet.

## Goals

- A user sees one candidate Wiki page for repeated mentions of one named entity.
- A reviewer sees every exact source mention that supports the candidate identity.
- A reviewer sees the deterministic reason for each identity assignment.
- A reviewer approves one pending record for one document-local candidate identity.
- A replay produces the same identity assignments without a model call.

## Requirements

### Input evidence

- HPR-IN-01: HP-9 requires one complete Hybrid coverage report.
- HPR-IN-02: HP-9 reloads every HP-7 Plan through its strict replay contract.
- HPR-IN-03: Every HP-7 Plan must name the coverage representation.
- HPR-IN-04: HP-9 considers every Actor and Organization ProposedChange in those Plans.
- HPR-IN-05: HP-9 preserves every source selector and Hybrid lineage value.
- HPR-IN-06: HP-9 rejects conflicting bodies for one HP-7 ProposedChange ID.

### Identity rules

- HPR-ID-01: HP-9 reconciles Actor candidates only with Actor candidates.
- HPR-ID-02: HP-9 reconciles Organization candidates only with Organization candidates.
- HPR-ID-03: The name key applies Unicode NFC, case folding, and whitespace collapse.
- HPR-ID-04: The name key preserves punctuation and words.
- HPR-ID-05: Equal name keys create one Entity Identity Cluster.
- HPR-ID-06: A unique HP-2 alias uses its expanded source name before HPR-ID-03.
- HPR-ID-07: A conflicting HP-2 alias does not join an expanded-name cluster.
- HPR-ID-08: A candidate without another match creates one singleton cluster.
- HPR-ID-09: Model scores and external identifiers cannot decide an HP-9 cluster.
- HPR-ID-10: Paragraph order cannot change an Entity Identity Cluster.
- HPR-ID-11: An Entity Identity Cluster ID includes the representation, kind, policy, and name key.
- HPR-ID-12: HP-9 retains conflicting Organization type observations for review.

### Decisions and justifications

- HPR-DEC-01: Every input candidate record has one Entity Identity Decision.
- HPR-DEC-02: A repeated-name decision has status `clustered`.
- HPR-DEC-03: A one-member decision has status `singleton`.
- HPR-DEC-04: A conflicting source alias remains in a separate singleton cluster while its HP-2 ambiguity evidence remains unchanged.
- HPR-DEC-05: Every resolved decision names one Entity Identity Cluster.
- HPR-DEC-06: Every decision names one Identity Match Justification.
- HPR-DEC-07: A justification names its input ProposedChanges and source evidence.
- HPR-DEC-08: A justification records its deterministic method and policy.
- HPR-DEC-09: HP-9 emits one ExtractionStageTrace for each decision.

### Preview evidence

- HPR-PRV-01: The Document Reconciliation Preview names every parent Plan and SHA-256.
- HPR-PRV-02: The Preview contains every cluster, decision, justification, and trace.
- HPR-PRV-03: The Preview uses canonical JSON and a content-derived identity.
- HPR-PRV-04: The Archive publishes the Preview immutably and atomically.
- HPR-PRV-05: Strict reload rebuilds the Preview from its parent Plans.
- HPR-PRV-06: Changed parent bytes, evidence, policy, or decisions change the Preview identity.
- HPR-PRV-07: The Preview changes no Ledger state.

### Document Proposal Plan

- HPR-PLN-01: The Document Proposal Plan names its Preview and parent Plans.
- HPR-PLN-02: The Plan emits one Actor or Organization ProposedChange per cluster.
- HPR-PLN-03: A named-entity proposal contains every cluster source selector.
- HPR-PLN-04: A named-entity proposal contains every member candidate and decision ID.
- HPR-PLN-05: The Plan rewrites Event participant IDs to Entity Identity Cluster record IDs.
- HPR-PLN-06: The Plan rewrites Assertion entity IDs to Entity Identity Cluster record IDs.
- HPR-PLN-07: The Plan recalculates each changed content-derived ID.
- HPR-PLN-08: The Plan validates every rewritten cross-record reference.
- HPR-PLN-09: The Plan preserves original HP-7 ProposedChange IDs as lineage.
- HPR-PLN-10: The Plan uses canonical JSON and a content-derived identity.
- HPR-PLN-11: The Archive publishes the Plan immutably and atomically.

### Submission and review

- HPR-SUB-01: HP-8 submits only the Document Proposal Plan.
- HPR-SUB-02: One Ledger transaction stores the Plan's provenance and ProposedChanges.
- HPR-SUB-03: The IngestionChangeSet contains only reconciled ProposedChange IDs.
- HPR-SUB-04: Retry reuses an identical Preview, Plan, provenance activity, and batch.
- HPR-SUB-05: Retry preserves every existing review status.
- HPR-SUB-06: Human review remains the only path to accepted Actor or Organization state.
- HPR-SUB-07: Rejection preserves the cluster, decisions, evidence, and proposal.

### Candidate Wiki

- HPR-WIKI-01: The Candidate Wiki creates one page per Entity Identity Cluster record.
- HPR-WIKI-02: The page cites every exact source selector in the cluster.
- HPR-WIKI-03: The page shows every inbound and outbound rewritten statement.
- HPR-WIKI-04: The page labels the record as pending until human review accepts it.
- HPR-WIKI-05: The default Markdown does not expose canonical Domain IDs.

## Proposed Architecture

```text
Paragraph HP-7 Plans
        |
        v
Application reconciliation ----> Archive
        |                           |
        |                           +--> Preview and Document Plan
        v
HP-8 closure -------------------> Ledger
        |                           |
        |                           +--> pending ProposedChanges
        v
Candidate Wiki
```

The Application Layer owns identity rules and proposal rewriting.

The Archive Adapter validates and stores canonical Preview and Plan bytes.

HP-8 composes reconciliation, publication, and atomic Ledger submission.

The Candidate Wiki renders reconciled proposal evidence.

## Key Interactions

```text
HP-8       Application       Archive       Ledger
 |             |                |             |
 | parent Plans|                |             |
 |------------>| validate       |             |
 |             | reconcile      |             |
 |             | publish Preview|             |
 |             |--------------->|             |
 |             | rewrite Plan   |             |
 |             | publish Plan   |             |
 |             |--------------->|             |
 | submit Plan |                |             |
 |------------------------------------------->|
 | close run   |                |             |
 |------------------------------------------->|
```

## Data Model

HP-9 adds no accepted Domain Core record.

The Archive stores the Document Reconciliation Preview and Document Proposal Plan as derived evidence.

The Ledger stores the existing ProvenanceActivity, ProposedChange, and IngestionChangeSet records.

An Actor or Organization ProposedChange keeps one primary source selector.

Its `identity_reconciliation` value stores all selectors, member IDs, decisions, and Preview identity.

## APIs / Interfaces

The Application Layer exposes explicit build, publish, load, and submit results.

The Archive Port reads and writes the Preview and Document Proposal Plan by content identity.

HP-8 deterministically builds and publishes the Document Proposal Plan from the strictly replayed Paragraph Plans.

Ingestion inspection reports the Preview ID, Plan ID, cluster counts, and decision counts.

## Behavior & Domain Rules

HP-9 automatically accepts a deterministic candidate cluster.

HP-9 does not accept the resulting Actor or Organization into the Ledger.

An ambiguous candidate remains visible and does not join an expanded-name cluster.

ReFinED output remains fallible model evidence.

The first HP-9 policy performs no fuzzy matching or model adjudication.

Historical closed IngestionRuns and immutable Wiki builds remain unchanged.

The design follows the established separation between mention discovery, mention clustering, and knowledge-base linking.

It also follows reconciliation systems that retain candidate features and explicit match justifications rather than treating a candidate score as identity truth.

## Acceptance Criteria

- AC-HPR-01: Two exact Anthropic mentions create one Organization cluster and one proposal.
- AC-HPR-02: Two exact person mentions create one Actor cluster and one proposal.
- AC-HPR-03: Equal Actor and Organization labels create separate clusters.
- AC-HPR-04: One explicit NIST declaration and later NIST mention create one cluster.
- AC-HPR-05: Conflicting NIST declarations remain ambiguous.
- AC-HPR-06: `OpenAI` and `Open AI` remain separate.
- AC-HPR-07: Reordered parent Plans produce byte-identical output.
- AC-HPR-08: Tampered parents, evidence, decisions, or references fail before publication.
- AC-HPR-09: SQLite tests prove atomic new publication and exact retry reuse.
- AC-HPR-10: Review tests prove one approval creates one accepted record.
- AC-HPR-11: Candidate Wiki tests prove one Anthropic page with every source citation.
- AC-HPR-12: HP-8 tests prove the IngestionChangeSet contains only reconciled IDs.
- AC-HPR-13: Canonical PDF validation proves one pending Anthropic Organization.
- AC-HPR-14: Canonical PDF validation proves one Anthropic Wiki page contains both known contexts.
- AC-HPR-15: Canonical PDF validation proves zero accepted intelligence before review.

## Reference Implementations

- Stage traces: `packages/application/src/kotekomi_application/extraction_stage_trace.py`
- Source aliases: `packages/application/src/kotekomi_application/hybrid_document_references.py`
- Immutable evidence: `packages/adapters/src/kotekomi_adapters/local_archive.py`
- Atomic proposal publication: `packages/application/src/kotekomi_application/hybrid_proposed_changes.py`
- TAC KBP Entity Discovery and Linking guidelines: <https://catalog.ldc.upenn.edu/docs/LDC2019T02/guidelines/TAC_KBP_2015_EDL_Guidelines_V1.2.pdf>
- W3C Reconciliation API draft: <https://reconciliation-api.github.io/specs/1.0-draft/>
- SSSOM mapping justifications: <https://mapping-commons.github.io/sssom/1.0/>
- ReFinED entity linking evidence: <https://aclanthology.org/2022.naacl-industry.24/>

## Constraints and Halt Conditions

Stop if HP-9 must merge candidates across representations.

Stop if HP-9 must treat an external identifier as accepted KoteKomi identity.

Stop if HP-9 requires a model call for an exact-name or explicit-alias decision.

Stop if HP-9 must mutate a historical closed IngestionRun.
