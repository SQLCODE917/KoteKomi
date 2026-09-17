# TDD: Source-Grounded Event Boundary

- Status: Complete and canonically verified
- Parent: [Event Trigger Boundary](2026-09-10-source-occurrence-event-trigger-boundary.md)
- Program: [Hybrid Semantic Quality Program](2026-09-06-hybrid-semantic-quality-program.md)
- Gold: [Source-Grounded Event Gold](hsq-source-grounded-event-gold-v1.json)

## 1. Context & Problem

KoteKomi now finds exact Event triggers in authoritative SourceSegments.

The current semantic route requires one of seven governed frames before it proposes an Event.

English expresses more Event meanings than that governed vocabulary represents.

The requirement therefore drops source-grounded Events that lack a broad classification.

It can also replace precise source meaning with a broad frame label.

This TDD makes exact source evidence the durable Event boundary.

The design follows the Simple Event Model separation between Events and optional types.

The design follows the Grounded Annotation Framework separation between Events and textual mentions.

**Source-Grounded Event** means an Event whose identity and label come from one exact source mention.

**EventMention** means the embedded link from an Event to its exact head, expression, and support.

**Event Type Assignment** means optional derived classification under one pinned vocabulary.

**Source-Grounded Event Gold** means reviewed outcomes over the approved Event Trigger Gold corpus.

### Primary Flow

1. The Application Layer loads one EventTriggerDraft and its authoritative SourceSegment.
2. KoteKomi constructs exact head, expression, and support EvidenceTargets.
3. KoteKomi constructs one EventMention from those EvidenceTargets.
4. KoteKomi proposes one Event whose name equals the exact expression text.
5. A human approves, edits, or rejects the proposed Event as one atomic review item.
6. The Candidate Wiki renders the exact Event expression followed by exact source text.

An optional semantic route can classify the Event after step three.

That classification does not change steps four through six.

## 2. Goals

- A reviewer sees every source-grounded Event without requiring an exhaustive Event vocabulary.
- A reviewer can trace every Event to exact authoritative characters.
- A reviewer can reject a false trigger without losing sibling Events.
- A Candidate Wiki preserves source wording at a glance.
- Optional Event classification cannot remove or rename an Event.

## 3. Requirements

### Domain Core

- SGE-D01: The Domain Core defines EventMention as an embedded Event value object.
- SGE-D02: EventMention identifies one head EvidenceTarget.
- SGE-D03: EventMention identifies one expression EvidenceTarget.
- SGE-D04: EventMention identifies one support EvidenceTarget.
- SGE-D05: One source-derived Event contains exactly one EventMention.
- SGE-D06: An EventMention identity depends only on its three EvidenceTarget identities.
- SGE-D07: Event stores source-derived meaning in its exact expression name.
- SGE-D08: Event participant fields remain independent from EventMention.

### Source Grounding

- SGE-G01: KoteKomi maps the trigger head to exact authoritative characters.
- SGE-G02: KoteKomi maps the trigger expression to exact authoritative characters.
- SGE-G03: KoteKomi maps the SourceSegment to exact authoritative characters.
- SGE-G04: The head range lies inside the expression range.
- SGE-G05: The expression range lies inside the support range.
- SGE-G06: All three EvidenceTargets share one Source identity.
- SGE-G07: All three EvidenceTargets share one Document identity.
- SGE-G08: All three EvidenceTargets share one DocumentRepresentation identity.
- SGE-G09: All three EvidenceTargets share one TextView identity and digest.
- SGE-G10: KoteKomi validates and replays all three EvidenceTargets before proposal.
- SGE-G11: KoteKomi derives Event and EventMention identities deterministically.

### Proposal and Review

- SGE-P01: One valid EventTriggerDraft creates one pending Event ProposedChange.
- SGE-P02: The Event ProposedChange contains the embedded EventMention.
- SGE-P03: The Event name equals the expression EvidenceTarget exact text.
- SGE-P04: The base Event proposal has empty participant fields.
- SGE-P05: A frame mapping is not an admission requirement.
- SGE-P06: A required-role mapping is not an admission requirement.
- SGE-P07: A complete-proposition support decision is not an admission requirement.
- SGE-P08: A human reviews the Event and EventMention as one ProposedChange.
- SGE-P09: Event approval validates all EventMention references again.
- SGE-P10: One rejected Event ProposedChange preserves every sibling proposal.
- SGE-P11: Invalid deterministic grounding blocks only the affected Event proposal.

### Optional Classification

- SGE-C01: Event Type Assignment is derived state.
- SGE-C02: Event Type Assignment identifies its Event and pinned vocabulary.
- SGE-C03: Event Type Assignment records `classified`, `unclassified`, or `partial`.
- SGE-C04: Missing Event Type Assignment means classification was not requested.
- SGE-C05: Event Type Assignment cannot change Event identity.
- SGE-C06: Event Type Assignment cannot change EventMention identity.
- SGE-C07: Event Type Assignment cannot decide proposal or review status.
- SGE-C08: Event Type Assignment cannot become accepted Ledger state in this slice.
- SGE-C09: The existing governed frame vocabulary remains an optional vocabulary.

### Candidate Wiki

- SGE-W01: The Candidate Wiki groups every source-grounded Event without a type Assertion.
- SGE-W02: The at-a-glance label uses the exact Event expression.
- SGE-W03: Exact source text follows the Event label.
- SGE-W04: The page keeps the stable Event ID as an audit handle.
- SGE-W05: The default page omits Event Type Assignment details.
- SGE-W06: The audit catalog retains EventMention and EvidenceTarget identities.

### Gold Evaluation

- SGE-E01: Source-Grounded Event Gold pins the approved Event Trigger Gold path and SHA-256.
- SGE-E02: Every Gold item identifies one parent Trigger Gold Event.
- SGE-E03: Every Gold item records `approved` or `rejected` review outcome.
- SGE-E04: Every Gold item records one review rationale.
- SGE-E05: TGE-033 records `rejected` because its phrase is a compound modifier.
- SGE-E05A: TGE-020 records `rejected` because its attendance is embedded under a decision and the
  source does not establish that attendance occurred or will occur.
- SGE-E05B: TGE-010 records `rejected` because `ahead of` supplies anticipated temporal context and
  does not establish that the election occurred.
- SGE-E05C: TGE-021 records `rejected` because the inauguration is embedded as an alternative under
  Amodei's decision and the source does not establish that it occurred.
- SGE-E06: Gold evaluation compares exact Event names and EventMention evidence.
- SGE-E07: Gold evaluation reports missing, extra, and incorrectly grounded Events.
- SGE-E08: Gold evaluation preserves development and validation partitions.
- SGE-E09: Gold evaluation writes no ProposedChange or accepted Ledger record.
- SGE-E10: The evaluation report binds the immutable document coverage report ID and SHA-256.

## 4. Proposed Architecture

```text
EventTriggerDraft
        |
        v
exact EvidenceTargets
        |
        v
embedded EventMention
        |
        +----------------------+
        |                      |
        v                      v
pending Event          optional Event type
ProposedChange         derived enrichment
        |
        v
human review
        |
        v
accepted Event
```

The Domain Core owns Event and EventMention shape.

The Application Layer owns EvidenceTarget construction and cross-record validation.

The Pipeline composes Event proposal submission and optional enrichment.

The Candidate Wiki exporter renders the derived human-readable view.

## 5. Key Interactions

```text
Pipeline       Application       Ledger       Reviewer       Wiki
   |                |               |             |            |
   |-- trigger ---->|               |             |            |
   |                |-- evidence -->|             |            |
   |                |-- proposal -->|             |            |
   |<-- pending ----|               |             |            |
   |--------------------------------------------->|            |
   |<-------------------------------- decision ---|            |
   |--------------------------------------------------------->|
   |<------------------------------------- exact expression ---|
```

Optional classification does not appear in this required interaction.

## 6. Data Model

### Existing Records

`EventTriggerDraft` identifies one exact source expression and exact source head.

`EvidenceTarget` identifies authoritative characters inside one TextView.

`Event` stores one bounded real-world happening.

`ProposedChange` stores one reviewable Event proposal.

### New EventMention Value Object

| Field | Meaning |
|---|---|
| `id` | Deterministic EventMention identity. |
| `head_evidence_target_id` | Exact trigger head. |
| `expression_evidence_target_id` | Exact source expression. |
| `support_evidence_target_id` | Complete supporting SourceSegment. |

`Event.mentions` embeds EventMention values.

The Ledger stores embedded EventMention values in the Event JSON record.

This TDD adds no EventMention table.

### Source-Grounded Event Draft

The derived Source-Grounded Event Draft binds one EventTriggerDraft to one EventMention.

The draft records exact parent identities and source digests.

The draft does not become accepted Ledger state.

### Event Type Assignment

The immutable HybridEventSemanticsPreview stores Event Type Assignments as derived evidence when
classification is requested.

The assignment records Event identity, vocabulary identity, outcome, and execution evidence.

## 7. APIs / Interfaces

The source-grounding use case accepts one pinned Event-trigger Preview.

The use case returns source-grounded Event drafts and exact EvidenceTarget identities.

The proposal planner consumes source-grounded Event drafts.

The review use case accepts the Event and embedded EventMention in one decision.

The Candidate Wiki planner consumes Event records without requiring type Assertions.

## 8. Behavior & Domain Rules

The source expression supplies phenomenological precision.

The Event name preserves source punctuation and spacing.

An EventMention can reuse one EvidenceTarget when the head equals the complete expression.

Classification failure leaves the source-grounded Event unchanged.

Classification disagreement leaves the source-grounded Event unchanged.

The Pipeline records model output only as derived execution evidence or ProposedChange evidence.

The reviewer decides whether a source expression denotes a bounded real-world happening.

Cross-source Event reconciliation remains outside this TDD.

Semantic Argument Assignment remains the next hybrid pipeline boundary.

## 9. Acceptance Criteria

- AC-SGE-D01: Domain tests validate EventMention shape and deterministic identity.
- AC-SGE-D02: Domain tests reject duplicate EventMention identities inside one Event.
- AC-SGE-G01: Application tests prove head, expression, and support containment.
- AC-SGE-G02: Application tests reject mixed Source, Document, representation, or TextView lineage.
- AC-SGE-G03: Application tests replay all three EvidenceTargets.
- AC-SGE-P01: Pipeline tests prove an unclassified trigger reaches pending review.
- AC-SGE-P02: Pipeline tests prove classification failure cannot remove that proposal.
- AC-SGE-P03: Review tests reject a changed Event name or broken EventMention reference.
- AC-SGE-P04: SQLite tests round-trip embedded EventMention values.
- AC-SGE-C01: Tests prove optional classification changes no Event proposal bytes.
- AC-SGE-W01: Wiki tests render an Event without one `has_event_type` Assertion.
- AC-SGE-W02: Wiki tests render exact expression and exact source text together.
- AC-SGE-W03: Wiki audit tests expose EventMention and EvidenceTarget identities.
- AC-SGE-E01: Gold tests cover every approved Trigger Gold Event exactly once.
- AC-SGE-E02: Gold tests preserve TGE-010, TGE-020, TGE-021, and TGE-033 as reviewed rejections.
- AC-SGE-E03: Gold replay preserves the parent development and validation split.
- AC-SGE-ALL: Formatting, lint, typecheck, focused tests, and repository tests pass.

### Verification Result

The canonical ingestion completed successfully on September 12, 2026.

- The repository check run passed 1,509 tests with one skip.
- IngestionRun `igr_971c7a38d0894449a45ceea65a606250` produced coverage report
  `hdc_531970a43dc9a886c345846b`.
- The development partition grounded all 50 expected Events across 12 SourceSegments.
- The validation partition grounded all 37 expected Events across 14 SourceSegments.
- The combined result contained 87 expected, observed, and exactly grounded Events.
- The result contained no missing, extra, or incorrectly grounded Events.

- Evaluation created zero ProposedChanges and zero accepted Ledger changes.

Human review on September 13 corrected the Gold contract after that replay.

- The corrected Gold contains 84 approved Events and three rejected Events.
- TGE-010 remains a valid linguistic trigger observation and derived grounding record but cannot
  become an admitted Event proposal.
- Its election mention supplies anticipated temporal context for the Facebook post without
  establishing occurrence.
- TGE-020 remains a valid linguistic trigger observation and derived grounding record but cannot
  become an admitted Event proposal.
- Its infinitival attendance is embedded under TGE-019's decision and has no established occurrence
  or future modality.
- TGE-019 now requires the complete exact decision expression.
- A deterministic replay against the September 12 coverage correctly reported one missing corrected
  TGE-019 Event and one stale extra Event derived from the former `decision`-only expression.

The fresh September 13 canonical ingestion verified the corrected contract.

- The repository check run passed 1,541 tests with one skip.
- IngestionRun `igr_242c7d642e4148b3ac2a927a70d543f6` executed the fresh ingestion.
- Coverage report `hdc_b11adbd6fa1963b54d4fff4e` retained its document-wide evidence.
- The development partition grounded all 50 reviewed Events exactly.
- The validation partition grounded all 37 reviewed Events exactly.
- The combined result contained 87 expected, observed, and exactly grounded Events.
- The result contained no missing, extra, or incorrectly grounded Events.
- The catalog retained 84 approved and three rejected human review outcomes.
- Evaluation created zero accepted Ledger changes.
- Re-evaluation reused immutable ingestion evidence and created zero ModelRun records.

Human review on September 15 found one additional factuality error in the Gold contract.

- TGE-021's inauguration is named only as an alternative under TGE-019's decision.
- The SourceSegment does not establish that the inauguration occurred.
- TGE-021 remains a valid linguistic Event mention and derived grounding record but is rejected from
  Event admission.
- At that point, the catalog contained 83 approved Events and four rejected Events.
- A read-only replay against immutable coverage report `hdc_2bc1f339a55f4bd259bfc1f1` verified all
  87 exact grounding records against the revised Gold, including 83 approved and four rejected review
outcomes, without rerunning a model or changing accepted Ledger state.

The completed Event-entity Gold review on September 16 found one further occurrence error.

- TGE-012's infinitival `vote` is embedded under TGE-011's urging.
- The SourceSegment establishes that Amodei urged his associates to vote, but it does not establish
  that they voted.
- TGE-012 remains an exact linguistic Event observation and derived grounding record, but it is
  rejected from Event admission.
- The current source-grounded Event catalog therefore contains 82 approved Events and five rejected
  Events.
- The correction changes no source characters, trigger range, or accepted Ledger state.

The same review established that source-grounded Event meanings preserve explicit calendar
expressions, relative temporal anchors, source aspect, active voice, attribution, and material
qualifications without normalizing them into inferred calendar facts.

The same review corrected TGE-025 to retain Sacks's source-exact act of stating the quoted claim.
TGE-025 remains an approved source-grounded Event, but its meaning now preserves attribution and does
not treat the quoted regulatory-capture characterization as independently established world state.

TGE-055 now likewise preserves that Palantir and Amazon Web Services offered services `with FedRAMP
authorization`; the qualification is part of the source-grounded Event meaning rather than optional
presentation detail.

TGE-007 now preserves that Amodei wrote the op-ed in The New York Times. This records the source's
publication venue without implying that the publication commissioned or endorsed the op-ed.

The enclosing ingestion reported accounted gaps in other extraction stages for 20 of 36 paragraphs.

Those gaps do not alter this boundary result and remain outside this TDD.

## 10. Reference Implementations

- Event records: `packages/domain/src/kotekomi_domain/models.py`
- Trigger evidence: `packages/application/src/kotekomi_application/hybrid_event_triggers.py`
- Evidence validation: `packages/application/src/kotekomi_application/evidence_targets.py`
- Proposal planning: `packages/application/src/kotekomi_application/hybrid_proposed_changes.py`
- Review validation: `packages/application/src/kotekomi_application/proposed_change_review.py`
- Wiki planning: `packages/application/src/kotekomi_application/candidate_wiki.py`
- Wiki rendering: `packages/exporters/src/kotekomi_exporters/markdown_wiki.py`
- Gold evaluation: `packages/pipelines/src/kotekomi_pipelines/source_grounded_event_evaluation.py`
- Canonical verifier: `scripts/verify_source_grounded_events.py`
- Event core pattern: follow [The Simple Event Model](https://semanticweb.cs.vu.nl/2009/11/sem/).
- Mention grounding pattern: follow
  [GAF: A Grounded Annotation Framework for Events](https://aclanthology.org/W13-1202/).

## Constraints and Halt Conditions

This TDD does not define Semantic Argument Assignment.

This TDD does not define cross-source Event reconciliation.

This TDD does not require an exhaustive Event type vocabulary.

The implementation must halt if exact source characters cannot ground an EventMention.
