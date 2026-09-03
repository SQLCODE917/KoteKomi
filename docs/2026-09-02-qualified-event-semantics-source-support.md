# TDD: Qualified Event Semantics and Source Support

- Status: Implemented and verified
- Program: [Hybrid Intelligence Extraction Pipeline](2026-09-01-hybrid-intelligence-extraction-pipeline.md)
- Deliverable ID: HP-6
- Depends on: [HP-5 Atomic Claims and Ontology Validation](2026-09-02-hybrid-atomic-claims-ontology-validation.md)
- Gold catalog: [HP-6 Event Semantics Gold Catalog](hp6-event-semantics-gold-v1.json)

## Context & Problem

HP-4 preserves source-valid event triggers and open event and role labels.

HP-5 atomizes those proposals and reports exact ontology mismatches.

The HP-5 evaluation found 37 unmapped roles among 43 event arguments.

The open labels mix participant roles, entity types, actions, and event meanings.

The original HP-6 design asked Qwen2.5 to judge those undefined labels as prose.

That task could not distinguish source support from ontology meaning.

HP-6 will replace that design with qualified event semantics.

HP-6 will map source events to governed frames before it judges source support.

HP-6 will preserve every open parent label as derived evidence.

HP-6 will create no accepted intelligence and no `ProposedChange`.

### Terms

**UpperRole** means one stable role that supports comparison across event frames.

**EventFrameDefinition** means one governed event type with its allowed roles.

**FrameRoleDefinition** means one role whose meaning is scoped to one event frame.

**EventArgumentTargetDraft** means one source-backed target for an event role.

**EventArgumentAssignmentDraft** means one qualified connection from an event to one target.

**EventSemanticDraft** means one governed interpretation of one HP-5 event subject.

**SemanticCoverageGap** means one explicit missing or unresolved semantic component.

**SemanticStatement** means one deterministic readable statement derived from governed semantics.

**SemanticSupportJudgment** means one independent source-support result for one SemanticStatement.

**HybridEventSemanticsPreview** means one immutable derived HP-6 result.

### Primary end-to-end flow

1. An operator selects one immutable HP-5 Preview.
2. The Application Layer validates the complete parent and source lineage.
3. Qwen2.5 selects one supplied event frame, then separate bounded tasks select one target for each supplied frame role.
4. KoteKomi resolves each selected target to authoritative source characters or a sibling event and derives attribution from the governed frame policy.
5. KoteKomi constructs qualified semantic drafts and explicit coverage gaps.
6. Separate Qwen2.5 tasks judge deterministic SemanticStatements against exact evidence.
7. The Pipeline publishes one immutable HybridEventSemanticsPreview.

## Goals

- A reviewer can read a meaningful event frame instead of an undefined open label.
- A reviewer can distinguish entity type from event role.
- A reviewer can inspect event-to-event and event-to-source-span arguments.
- A reviewer can trace every semantic decision to exact authoritative text.
- A reviewer can inspect independent source support for each governed statement.
- The operation leaves accepted and proposed wiki state unchanged.

## Requirements

### Parent evidence

- HES-PAR-01: The command requires one HP-5 Preview ID.
- HES-PAR-02: The Application Layer validates canonical HP-5 bytes and digest.
- HES-PAR-03: The Application Layer validates HP-4 through HP-1 lineage.
- HES-PAR-04: The Application Layer replays every parent EvidenceTarget.
- HES-PAR-05: A deterministic parent failure stops before model execution.
- HES-PAR-06: The Application Layer processes every valid HP-5 event subject.

### Ontology profile

- HES-ONT-01: Domain Core defines `hybrid_event_semantics_v1`.
- HES-ONT-02: The profile defines `agent`, `theme`, `participant`, `content`, `cause`, and `result` as UpperRole values.
- HES-ONT-03: The profile defines `change_in_intensity` with required `affected_process`.
- HES-ONT-04: The profile defines `authorization` with required `authorizer`, `authorized_party`, and `permitted_action`.
- HES-ONT-05: The `authorization` frame defines optional `authorized_resource`.
- HES-ONT-06: The profile defines `characterization` with required `evaluator`, `evaluated_subject`, and `characterization`.
- HES-ONT-07: The profile defines `recommendation` with required `recommender` and `recommended_action`.
- HES-ONT-08: The `recommendation` frame defines optional `recommendation_subject`.
- HES-ONT-09: The profile defines `investment_abandonment` with required `disinvestor` and `abandoned_asset`.
- HES-ONT-10: The `investment_abandonment` frame defines optional `investee`.
- HES-ONT-11: The profile defines `causation` with required `cause` and `effect`.
- HES-ONT-12: The profile defines `classification` with required `classifier`, `classified_entity`, and `assigned_classification`.
- HES-ONT-13: The `classification` frame defines optional `stated_reason`.
- HES-ONT-14: Each frame role names one UpperRole and allowed target kinds.
- HES-ONT-15: Time, place, attribution, and entity type are not FrameRoleDefinition values.
- HES-ONT-16: The profile exposes canonical bytes and one SHA-256 digest.
- HES-ONT-17: A reporting frame can name one required agent role as its governed attribution role.

### Normalization task

- HES-NRM-01: The Application Layer creates one normalization task per event subject.
- HES-NRM-02: The task receives one exact source segment and exact trigger.
- HES-NRM-03: The task receives the open event label and open parent role labels as proposals.
- HES-NRM-04: The task receives task-local MentionCandidate and sibling event labels.
- HES-NRM-05: The task receives every definition in the bounded ontology profile.
- HES-NRM-06: The task selects one supplied frame ID or `unresolved`.
- HES-NRM-07: The task selects only roles that belong to its selected frame.
- HES-NRM-08: One role target proposal is a supplied label or source literal; it does not serialize KoteKomi's target kind.
- HES-NRM-09: The task receives parent time and place proposals under task-local labels and can select only those labels; KoteKomi resolves each label to its exact literal.
- HES-NRM-10: The task does not decide polarity, modality, or attribution.
- HES-NRM-11: The task receives no canonical record ID or storage path.
- HES-NRM-12: An unresolved frame produces no governed role assignment.
- HES-NRM-13: An invalid model field remains archived and is never silently used to construct an EventSemanticDraft; a separately valid bounded completion can replace it, and one redundant `label | exact catalog text` target can be normalized to that supplied label only by the named deterministic reconciliation rule and a complete trace.
- HES-NRM-14: Every role in the selected frame receives one bounded role-completion task; the broad normalization targets remain archived proposals and never directly construct role assignments.
- HES-NRM-15: A role-completion task returns only one source-valid target plus a reason, or explicit absence plus a reason; KoteKomi supplies the already selected frame and role, so the task cannot change either one or another role.
- HES-NRM-16: Every role-completion task and result remains independently traceable to the primary normalization task.
- HES-NRM-17: One source-invalid or schema-invalid role-completion result can trigger exactly one bounded retry that receives the rejected value and deterministic validation failure.
- HES-NRM-18: Deterministic role-target reconciliation accepts only a supplied candidate or sibling-event label followed by its exact whitespace-equivalent catalog text; it rejects mismatched, unknown, or target-kind-ineligible labels.

### Deterministic construction

- HES-CON-01: KoteKomi resolves every source literal to one unique authoritative range by exact match or whitespace-equivalent match.
- HES-CON-01A: A whitespace-equivalent match preserves source wording and punctuation and must remain unique.
- HES-CON-01B: A uniquely matching source literal reuses a task-local MentionCandidate when the selected role permits that target kind.
- HES-CON-01C: A supplied candidate or event label resolves to its exact source span when the governed role permits only a source-span target.
- HES-CON-02: KoteKomi derives every offset, digest, EvidenceTarget, and record ID.
- HES-CON-03: KoteKomi validates each role against its selected frame.
- HES-CON-04: KoteKomi validates each target kind against its role definition.
- HES-CON-05: KoteKomi rejects repeated target and role assignments.
- HES-CON-06: KoteKomi creates one gap for each missing required role.
- HES-CON-07: KoteKomi creates one gap for each omitted parent argument.
- HES-CON-07A: KoteKomi excludes an invented qualifier into an explicit gap and creates one gap for each omitted parent qualifier.
- HES-CON-07B: Excluding an invalid optional qualifier does not discard otherwise valid core event semantics.
- HES-CON-08: KoteKomi retains the open event and role labels as proposal lineage.
- HES-CON-09: A mapped frame creates one EventSemanticDraft.
- HES-CON-10: An unresolved frame creates one `unmapped_frame` gap.
- HES-CON-11: A target EvidenceTarget selects the exact target expression.
- HES-CON-12: A support EvidenceTarget selects the complete authoritative source segment.
- HES-CON-13: KoteKomi derives reporting attribution from the frame's governed attribution role and uses source-narrator attribution for frames without one.
- HES-CON-14: Missing governed attribution and disagreement with the open HP-4 attribution remain explicit gaps.

### Independent source support

- HES-SUP-01: KoteKomi renders one SemanticStatement for the frame assignment.
- HES-SUP-02: KoteKomi renders one SemanticStatement for each role assignment.
- HES-SUP-03: KoteKomi renders statements for polarity, modality, qualifiers, and attribution.
- HES-SUP-04: One independent task judges each SemanticStatement.
- HES-SUP-05: The task receives the exact support EvidenceTarget and governed definitions.
- HES-SUP-06: The task receives no normalization reason or raw parent model output.
- HES-SUP-07: The task returns `directly_supported`, `partially_supported`, `unsupported`, `contradicted`, or `ambiguous`.
- HES-SUP-08: A support outcome describes source support and not world truth.
- HES-SUP-09: A failed support task creates no SemanticSupportJudgment.
- HES-SUP-10: One support-task failure does not cancel later independent tasks.

### Preview and evidence

- HES-PRV-01: The Preview identifies its HP-5 parent and ontology digest.
- HES-PRV-01A: The Preview identifies the pinned normalization, role-completion, and source-support prompt and schema digests.
- HES-PRV-02: The Preview contains every EventSemanticDraft and EventArgumentTargetDraft.
- HES-PRV-03: The Preview contains every EventArgumentAssignmentDraft and SemanticCoverageGap.
- HES-PRV-04: The Preview contains every valid SemanticSupportJudgment.
- HES-PRV-05: The Preview references every task, ModelRun, EvidenceTarget, and stage trace.
- HES-PRV-06: Every stage trace contains complete data in and data out.
- HES-PRV-07: The Preview uses canonical JSON and a content-derived identity.
- HES-PRV-08: The Archive reuses byte-identical Preview content.
- HES-PRV-09: Reload validates bytes, parent lineage, ontology identity, and evidence.
- HES-PRV-10: Semantic outcomes do not determine execution status.
- HES-PRV-11: HP-6 creates no Event, Assertion, Relationship, or ProposedChange.

### Public operation

- HES-CLI-01: `kotekomi extraction build-event-semantics` runs HP-6.
- HES-CLI-02: The command requires `--preview-id`.
- HES-CLI-03: The command accepts existing model runtime arguments.
- HES-CLI-04: JSON output includes identities, record counts, gap counts, and support counts.
- HES-CLI-05: Text output identifies the Preview, status, and diagnostic summary.
- HES-CLI-06: A complete Preview exits zero.
- HES-CLI-07: A partial or blocked Preview exits one.

## Proposed Architecture

```text
HP-5 Preview -> parent and source validation
                         |
                         v
               Qwen semantic selection
                         |
                         v
              deterministic construction
                         |
                         v
             independent support tasks
                         |
                         v
             HybridEventSemanticsPreview
```

Domain Core owns the governed ontology profile.

The Application Layer owns task construction, source mapping, validation, and status.

The ModelRuntime Adapter executes independent Qwen2.5 tasks.

The Archive Adapter stores raw output and immutable Preview bytes.

The Pipeline owns configuration, transactions, publication, and public output.

## Key Interactions

```text
Operator   Pipeline   Application   Qwen2.5   Ledger   Archive
   |          |            |            |        |        |
   | build    |            |            |        |        |
   |--------->| load parent|            |        |        |
   |          |----------->| replay evidence---->|        |
   |          |            | normalize  |        |        |
   |          |            |----------->|        |        |
   |          |            | archive raw output---------->|
   |          |            | construct evidence-->|       |
   |          |            | judge atoms|        |        |
   |          |            |----------->|        |        |
   |          |            | publish Preview------------->|
   |<---------| result     |            |        |        |
```

## Data Model

HP-6 adds one pure Domain Core ontology profile.

HP-6 adds derived Application Layer DTOs for semantic drafts, gaps, and judgments.

HP-6 stores new EvidenceTarget and EvidenceValidationAttempt records in existing tables.

HP-6 stores each Preview at `extraction/event-semantic-previews/<preview-id>.json`.

HP-6 requires no Ledger migration.

## APIs / Interfaces

The normalization response uses one `frame` line followed by argument and qualifier lines.

Each argument line contains one supplied role ID and one supplied label or source literal.

Each qualifier line contains one supplied task-local qualifier label.

The model does not serialize target kinds, offsets, or record-shaped JSON.

KoteKomi resolves labels and exact literals to typed targets and authoritative offsets.

KoteKomi carries validated parent polarity and modality into the semantic draft without asking the model to reproduce them.

KoteKomi derives attribution from the governed frame policy and retains disagreement with the open parent attribution as a gap.

Broad normalization argument lines remain diagnostic proposals.

KoteKomi constructs role assignments only from the separate bounded role-completion contract.

The response ends with one concise `reason` line.

The response uses `frame: unresolved` with no semantic lines when no supplied frame fits.

A role-completion response uses only one `target` line followed by one concise `reason` line.

KoteKomi assigns that target to the already selected frame role and rejects unknown labels or non-unique source literals.

The support response uses one `outcome` line and one `reason` line.

## Behavior & Domain Rules

An open model label remains a proposal.

A governed frame and role come only from the pinned ontology profile.

An entity type does not become an event role.

An argument role has meaning only inside its event frame.

An UpperRole supports comparison across event frames.

A source span remains a derived target until later review creates canonical state.

An unresolved frame remains visible and creates no guessed semantics.

HP-7 can consume only governed drafts with complete source-support evidence.

## Acceptance Criteria

- AC-HES-01: Domain tests prove exact profile content, ordering, bytes, and digest.
- AC-HES-02: Tests prove every frame role maps to one allowed UpperRole.
- AC-HES-03: Tests reject entity types, time, place, and attribution as event roles.
- AC-HES-04: Parser tests prove supplied role IDs, local target references, strict fields, unresolved output, and the separate target-only role-completion contract.
- AC-HES-05: Tests prove exact MentionCandidate, sibling event, and source-span targets.
- AC-HES-06: Tests reject unknown, changed, repeated, and ambiguous source literals.
- AC-HES-07: Tests prove required-role and omitted-parent gaps.
- AC-HES-08: Tests prove proposal labels survive without becoming governed IDs.
- AC-HES-09: Tests prove independent support input excludes normalization rationale.
- AC-HES-10: Tests prove every support outcome and isolated task failure.
- AC-HES-11: Tests prove complete, partial, blocked, and unresolved Preview behavior.
- AC-HES-12: Tests prove immutable Archive publication and restart reload.
- AC-HES-13: CLI tests prove routing, JSON, text, counts, and exits.
- AC-HES-14: Tests prove no accepted or proposed intelligence changes.
- AC-HES-15: The evaluation processes all fourteen retained EvidenceTargets twice.
- AC-HES-16: The evaluation locks detailed Gold semantics for five reviewed scenarios.
- AC-HES-17: The evaluation does not score unreviewed parent events as either mapped or unresolved.
- AC-HES-17A: Unit tests prove explicit unresolved behavior for out-of-profile events.
- AC-HES-18: The evaluation records complete data in and data out for every task.
- AC-HES-19: The evaluation reports exact targets, frame roles, UpperRoles, gaps, support outcomes, and stability.
- AC-HES-19A: Gold comparison preserves every exact target in the report and treats only one trailing comma, semicolon, or sentence period appended to the exact expected target as a boundary-equivalent clause delimiter.
- AC-HES-20: Formatting, Ruff, Pyright, focused tests, and the full test suite pass.

## Reference Implementations

- Parent validation: follow `hybrid_atomic_claim_preview.py`.
- Source mapping: follow `hybrid_event_frame_preview.py`.
- EvidenceTargets: follow `grounded_candidates.py`.
- Model execution: follow `hybrid_event_frame_preview.py`.
- Immutable storage: follow `local_archive.py`.

## Constraints and Halt Conditions

Stop when the model must invent a canonical ontology identifier.

Stop when one normalization task must validate its own source support.

Stop when a source literal cannot map uniquely to authoritative characters.

Stop when a semantic draft must become accepted state without review.

Stop when an out-of-profile event must be forced into a governed frame.
