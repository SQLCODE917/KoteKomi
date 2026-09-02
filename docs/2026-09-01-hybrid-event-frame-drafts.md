# TDD: Hybrid Event Frame Drafts

- Status: Accepted
- Program: [Hybrid Intelligence Extraction Pipeline](2026-09-01-hybrid-intelligence-extraction-pipeline.md)
- Increment: HP-4
- Depends on: [Hybrid Entity Identity Grounding](2026-09-01-hybrid-entity-identity-grounding.md)
- Scope: derived event evidence only
- Evaluation: [HP-4 Event Frame Evaluation](2026-09-02-hp4-event-frame-evaluation.md)

## Context & Problem

HP-1 preserves source-valid MentionCandidates and contextual interpretations.

HP-2 resolves only source-verifiable document aliases.

HP-3 preserves ranked external identity candidates without selecting an identity.

These stages do not represent a real-world event that connects several source mentions.

HP-4 will detect each explicit event trigger in one authoritative paragraph.

HP-4 will ask a separate bounded task to assign arguments and source qualifiers to each trigger.

KoteKomi will resolve every model label to source-valid records and characters.

HP-4 will preserve the model judgment as derived evidence.

HP-4 will not create an Event, AtomicClaim, ProposedChange, or accepted Ledger record.

### Terms

**EventTriggerDraft** means one source-literal event trigger and one open event label.

**EventArgumentDraft** means one task-local MentionCandidate reference and one open role label.

**EventQualifierDraft** means one source-literal time or place expression.

**EventFrameDraft** means one validated trigger with arguments, qualifiers, polarity, modality, and attribution.

**HybridEventFramePreview** means one immutable derived HP-4 result for one paragraph.

### Primary flow

1. An operator selects one immutable HybridEntityGroundingPreview.
2. The Pipeline verifies its HP-2 and HP-1 lineage and accepted DocumentRepresentationBundle.
3. Qwen2.5 detects event triggers separately in each SourceSegment.
4. KoteKomi maps each Source-copy trigger through its deterministic boundary map to one unique authoritative source range.
5. Qwen2.5 assigns arguments and qualifiers for each mapped trigger.
6. KoteKomi validates all task-local references and publishes one immutable Preview.

## Goals

- A reviewer can inspect every explicit event proposed for one paragraph.
- A reviewer can inspect each participant role without accepting it as Ledger truth.
- A reviewer can distinguish source assertion, negation, modality, and attribution.
- A reviewer can trace every model decision to exact input, raw output, and source characters.
- A reviewer can localize a failure to upstream mentions, references, trigger detection, or frame assignment.
- The operation changes no accepted intelligence.

## Requirements

### Parent evidence

- HEP-01: The command requires one HybridEntityGroundingPreview ID.
- HEP-02: The Pipeline strictly validates the HP-3 Preview and its canonical SHA-256.
- HEP-03: The Pipeline loads and validates the HP-2 and HP-1 parents named by the HP-3 lineage.
- HEP-04: The Pipeline verifies each parent digest before model execution.
- HEP-05: The Pipeline rejects a blocked HP-1 Preview.
- HEP-06: The Pipeline loads the accepted DocumentRepresentationBundle named by HP-1.
- HEP-07: The Pipeline loads the exact ContextManifest named by HP-1.
- HEP-08: The Pipeline verifies the paragraph, SourceSegments, and deterministic Source-copy boundary maps against authoritative characters.
- HEP-09: A partial or blocked HP-3 status remains diagnostic evidence and does not block HP-4.
- HEP-10: HP-4 does not send EntityLinkCandidates to Qwen2.5.

### Trigger tasks

- HET-01: HP-4 creates one trigger task for each SourceSegment in the paragraph.
- HET-02: Each task asks for every explicit event whose trigger occurs in its named SourceSegment.
- HET-03: The model returns zero or more task-local event labels, SourceSegment labels, Source-copy trigger literals, and open event labels.
- HET-04: An empty segment result uses an explicit abstention contract.
- HET-05: A trigger literal must occur exactly once in its named deterministic SourceCopyView.
- HET-06: KoteKomi maps the Source-copy range to authoritative characters and derives the trigger text, offsets, and digest there.
- HET-07: KoteKomi rejects unknown, duplicate, non-literal, or ambiguous trigger output.
- HET-08: One invalid trigger task contributes no EventTriggerDrafts.
- HET-09: HP-4 does not impose an event-count limit beyond the pinned model output budget.

### Frame tasks

- HEF-01: HP-4 creates one bounded frame task for each validated EventTriggerDraft.
- HEF-02: The task receives the trigger and every selected HP-1 candidate with an interpretation.
- HEF-03: The task receives HP-2 reference status and a resolved antecedent only when HP-2 proved it.
- HEF-04: The task receives no ReFinED rank, score, label, title, or external identity.
- HEF-05: An EventArgumentDraft references one task-local MentionCandidate label.
- HEF-06: An EventArgumentDraft contains one concise open role label and one support SourceSegment label.
- HEF-07: Specific, generic, and unresolved anaphoric MentionCandidates can be EventArgumentDrafts.
- HEF-08: An unresolved argument remains visibly unresolved in the Preview.
- HEF-09: An EventQualifierDraft names `time` or `place`, one SourceSegment, and one Source-copy literal.
- HEF-10: A qualifier literal must occur exactly once in its named deterministic SourceCopyView and map to one authoritative range.
- HEF-11: Polarity is `affirmed` or `negated`.
- HEF-12: Modality is `actual`, `planned`, `possible`, `uncertain`, `recommended`, or `hypothetical`.
- HEF-13: Attribution is `source_narrator` or one or more task-local MentionCandidate labels.
- HEF-14: Open event and role labels use one through four lowercase underscore-separated words.
- HEF-15: KoteKomi rejects unknown labels, references, duplicated values, and malformed output.
- HEF-16: KoteKomi preserves a failed frame task without publishing a partial frame from that task.

### Execution evidence

- HEE-01: Trigger detection and frame assignment use separate prompt and schema identities.
- HEE-02: Every model call creates one immutable ExtractionTask and ModelRun.
- HEE-03: Every task binds the ContextManifest, exact task input, prompt, schema, model, and generation settings.
- HEE-04: The Archive stores the complete raw model response before semantic mapping.
- HEE-05: Every task has one ExtractionStageTrace with exact data in, data out, and lineage.
- HEE-06: Trace input includes the source text and every task-local record supplied to the model.
- HEE-07: Trace output includes the raw-output digest and the parsed or rejected result.
- HEE-08: Runtime, protocol, parsing, mapping, and Archive failures remain typed diagnostics.

### Preview evidence

- HEV-01: The Preview identifies its HP-3 parent and the verified HP-2 and HP-1 lineage.
- HEV-02: The Preview contains every validated EventTriggerDraft and EventFrameDraft.
- HEV-03: The Preview contains every ExtractionTask ID, ModelRun ID, trace, and diagnostic.
- HEV-04: A successful explicit abstention for every SourceSegment produces an empty complete Preview.
- HEV-05: A complete HP-1 parent and successful HP-4 tasks produce a complete Preview.
- HEV-06: A partial HP-1 parent or any failed HP-4 task produces a partial Preview when some HP-4 task succeeds.
- HEV-07: Failed trigger detection for every SourceSegment produces a blocked Preview.
- HEV-08: HP-3 terminal status does not change HP-4 terminal status.
- HEV-09: The Preview uses canonical JSON and a content-derived identity.
- HEV-10: The Archive publishes the Preview atomically and reuses identical bytes.
- HEV-11: Reload validates canonical bytes, identity, digests, and parent lineage.
- HEV-12: Changed source, parent, prompt, schema, model evidence, or execution lineage changes the Preview identity.
- HEV-13: HP-4 creates no Event, Assertion, AtomicClaim, ProposedChange, or accepted Ledger state.

### Public operation

- HEC-01: `kotekomi extraction draft-event-frames --preview-id <hp3-preview-id>` runs HP-4.
- HEC-02: The command uses the configured ModelExecution runtime.
- HEC-03: Standard output identifies status, Preview ID, parent ID, digest, and Archive path.
- HEC-04: A complete Preview exits zero.
- HEC-05: A partial or blocked Preview exits one.

## Proposed Architecture

```text
HP-3 Preview -> verified HP-2 and HP-1 evidence -> accepted bundle
                                                        |
                                                        v
                                              Qwen trigger tasks
                                                        |
                                                        v
                                           source trigger validation
                                                        |
                                                        v
                                               Qwen frame tasks
                                                        |
                                                        v
                                      immutable HybridEventFramePreview
```

The Application Layer owns task construction, source mapping, validation, and terminal status.

The existing ModelTaskRuntime Port executes Qwen2.5 calls.

The Pipeline composes configuration, Ledger, Archive, and public output.

The Archive Adapter validates and stores immutable Preview bytes.

## Key Interactions

```text
Operator       Pipeline       Application       Qwen2.5       Archive
   |              |                |                |              |
   | draft frames |                |                |              |
   |------------->| load lineage   |                |              |
   |              |---------------------------------------------->|
   |              | validate       |                |              |
   |              |--------------->| detect trigger |              |
   |              |                |--------------->|              |
   |              |                | archive raw output------------>|
   |              |                | assign roles   |              |
   |              |                |--------------->|              |
   |              |                | archive raw output------------>|
   |              |                | publish Preview--------------->|
   |<-------------| result         |                |              |
```

## Data Model

HP-4 adds derived Application DTOs for EventTriggerDraft, EventArgumentDraft,
EventQualifierDraft, EventFrameDraft, and HybridEventFramePreview.

HP-4 reuses ExtractionTask, ModelRun, ExtractionStageTrace, ContextManifest,
MentionCandidate, MentionInterpretation, and ReferenceDecision.

HP-4 adds no accepted Domain Core record and no Ledger migration.

## APIs / Interfaces

The HybridEventFramePreview Archive Port writes and reads canonical Preview bytes by Preview ID.

The HP-4 use case accepts one HP-3 Preview ID and returns one Preview, digest, and Archive path.

The trigger output contract uses one `event` line per proposal or one `abstain` line.

The frame output contract uses fixed scalar fields followed by repeated argument and qualifier lines.

## Behavior & Domain Rules

Model labels are scoped to one task and never become canonical record IDs.

KoteKomi maps Source-copy literals through the existing deterministic SourceCopyView boundary map.

The mapping is not fuzzy matching, character repair, or a second source of text authority.

Published trigger and qualifier text always comes from the authoritative TextView range.

Open labels remain proposals until HP-5 validates ontology structure.

Modality describes how the source presents an event and does not express evidence confidence.

HP-6 remains responsible for source-support judgment.

## Acceptance Criteria

- AC-HE-01: Tests prove zero, one, and multiple triggers in one SourceSegment.
- AC-HE-02: Tests prove triggers across several SourceSegments produce one paragraph Preview.
- AC-HE-03: Tests prove unique source mapping and reject unknown, duplicate, changed, and ambiguous literals.
- AC-HE-04: Tests prove specific, generic, resolved alias, and unresolved anaphoric arguments.
- AC-HE-05: Tests prove polarity, every modality, attribution, time, and place contracts.
- AC-HE-06: Tests prove invalid task output remains archived and creates no partial frame.
- AC-HE-07: Tests prove complete, empty complete, partial, and blocked Preview states.
- AC-HE-08: Tests prove partial and blocked HP-3 status does not gate valid HP-4 work.
- AC-HE-09: Tests prove ReFinED candidates never enter rendered Qwen input.
- AC-HE-10: Tests prove complete task, run, raw output, receipt, and stage-trace lineage.
- AC-HE-11: Archive tests prove immutable create, reuse, conflict rejection, and restart reload.
- AC-HE-12: CLI tests prove routing, portable output, and exit codes.
- AC-HE-13: Tests prove HP-4 creates no accepted-state record.
- AC-HE-14: A production-equivalent evaluation covers 12 reviewed event-rich paragraphs.
- AC-HE-15: The evaluation emits exact data in, raw Qwen output, mapped output, and diagnostics per task.
- AC-HE-16: The evaluation classifies each discrepancy by its owning stage and records ranked testable hypotheses.
- AC-HE-17: Formatting, lint, pyright, focused tests, and the full repository test suite pass.

## Reference Implementations

- Task recording: follow `hybrid_mention_preview.py`.
- Parent and Preview validation: follow `hybrid_entity_grounding_preview.py`.
- Immutable Archive storage: follow `local_archive.py`.

## Constraints and Halt Conditions

Stop when HP-4 requires a canonical event type, canonical role, AtomicClaim, or accepted Event.

Stop when a model score must become evidence confidence or select an external identity.
