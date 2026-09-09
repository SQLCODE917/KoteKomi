# TDD: Source-Bound Governed Event Extraction

- Status: Accepted for implementation
- Deliverable ID: HSQ-6
- Program: [Hybrid Semantic Quality Program](2026-09-06-hybrid-semantic-quality-program.md)
- Depends on: [Standing Fact Semantic Admission](2026-09-06-standing-fact-semantic-admission.md)
- Gold: [Amodei Intelligence Gold](hsq-amodei-intelligence-gold-v1.json)

## Context & Problem

The current event path asks Qwen to create an open EventFrameDraft.

HP-5 then converts that frame into AtomicClaimDraft records.

HP-6 asks Qwen to map the same event into the governed event profile.

The open frame and AtomicClaimDraft stages add model calls and validation boundaries.

They do not add source authority or accepted knowledge.

The canonical Anthropic ingestion lost five source-backed Amodei events in these stages.

Some model outputs selected unrelated paragraph candidates.

Some model outputs used a malformed optional qualifier.

Some model outputs found the correct meaning but assigned an unsupported role.

One malformed optional value currently erases the complete event proposal.

**EventTriggerDraft** means one exact source trigger with one diagnostic open label.

**Governed event task** means one model task that selects a governed frame and roles for one trigger.

**Composite source target** means an exact source span that contains one or more validated Entities.

**Embedded entity reference** means one validated Entity reference inside a Composite source target.

**Line rejection** means one typed record of an invalid optional model-output line.

### Primary end-to-end flow

1. Qwen finds explicit Event triggers in one SourceSegment.
2. KoteKomi maps each trigger to exact authoritative source characters.
3. Qwen selects one governed frame and source-bound roles for each trigger.
4. KoteKomi validates each returned line and constructs deterministic event records.
5. Qwen and the NLI Adapter judge one CompleteProposition against exact source text.
6. KoteKomi creates reviewable ProposedChanges and projects them into the Candidate Wiki.

## Goals

- A reviewer sees the five Gold events on the Amodei Candidate Wiki page.
- A reviewer sees exact source text directly beneath each event.
- A reviewer can audit every event from the Candidate Wiki to model and source evidence.
- One malformed optional value does not erase a valid event.
- Ingestion spends no model call on an open frame that HP-6 must reinterpret.
- Existing adjudicated correct events remain available.

## Requirements

### Domain Core

- SGE-DOM-01: The Domain Core defines event semantic profile `hybrid_event_semantics_v4`.
- SGE-DOM-02: Version 4 adds `medium` to UpperRole.
- SGE-DOM-03: The criticism frame adds optional role `criticism.assessment`.
- SGE-DOM-04: The publication frame adds optional role `publication.outlet`.
- SGE-DOM-05: The Domain Core defines `before`, `during`, `after`, and `at` as TemporalRelation values.
- SGE-DOM-06: Each time qualifier names one TemporalRelation.
- SGE-DOM-07: The structural ontology defines `has_argument_entity_reference`.
- SGE-DOM-08: The profile adds no catch-all event frame.

### Trigger discovery

- SGE-TRG-01: HP-4 creates one trigger task for each SourceSegment.
- SGE-TRG-02: The task asks for finite, infinitive, participial, and eventive-nominal triggers.
- SGE-TRG-03: KoteKomi maps each trigger literal to one exact range in its SourceSegment.
- SGE-TRG-04: KoteKomi reconciles overlapping trigger proposals deterministically.
- SGE-TRG-05: HP-4 stores one immutable HybridEventTriggerPreview.
- SGE-TRG-06: An open event label remains diagnostic evidence.
- SGE-TRG-07: HP-4 does not create an open EventFrameDraft.

### Governed event task

- SGE-EVT-01: HP-6 creates one governed event task for each EventTriggerDraft.
- SGE-EVT-02: The task contains only the target SourceSegment and its selected MentionCandidates.
- SGE-EVT-03: A resolved local reference can include its validated antecedent metadata.
- SGE-EVT-04: The task supplies the complete governed event profile.
- SGE-EVT-05: Qwen selects a governed frame, roles, polarity, modality, and attribution.
- SGE-EVT-06: Qwen can select exact time and place qualifier text.
- SGE-EVT-07: Qwen selects one TemporalRelation for each time qualifier.
- SGE-EVT-08: Qwen creates no canonical identifier, digest, offset, or Ledger record.

### Model-output boundary

- SGE-OUT-01: The parser validates the required event envelope as one unit.
- SGE-OUT-02: The parser validates each argument line independently.
- SGE-OUT-03: The parser validates each qualifier line independently.
- SGE-OUT-04: The parser retains valid lines when an optional line is invalid.
- SGE-OUT-05: The parser emits one Line rejection for each invalid optional line.
- SGE-OUT-06: An invalid required envelope produces a typed event gap.
- SGE-OUT-07: KoteKomi records the exact raw model output and parsed result.

### Deterministic construction

- SGE-CON-01: KoteKomi resolves every selected literal to authoritative characters.
- SGE-CON-02: KoteKomi constructs every event, role, qualifier, EvidenceTarget, and identifier.
- SGE-CON-03: KoteKomi completes only a missing required role.
- SGE-CON-04: KoteKomi does not run role completion for an optional role.
- SGE-CON-05: An absent optional role remains an explicit coverage gap.
- SGE-CON-06: Gold verification treats a required Gold omission as a failure.
- SGE-CON-07: KoteKomi retains existing CompleteProposition and NLI admission checks.

### Composite source targets

- SGE-CMP-01: A Composite source target preserves its complete exact source span.
- SGE-CMP-02: KoteKomi finds validated MentionCandidates wholly contained in that span.
- SGE-CMP-03: KoteKomi stores those candidate IDs as Embedded entity references.
- SGE-CMP-04: A partial or non-contained candidate cannot become an Embedded entity reference.
- SGE-CMP-05: HP-7 materializes one `has_argument_entity_reference` Assertion per reference.
- SGE-CMP-06: The Assertion preserves the governed frame role as a qualifier.
- SGE-CMP-07: The Candidate Wiki uses the reference for Entity page placement.
- SGE-CMP-08: The Candidate Wiki displays the Composite source target as the semantic role value.

### Proposal and Wiki boundaries

- SGE-WIK-01: HP-7 remains the proposal admission boundary.
- SGE-WIK-02: A human review remains the only path into accepted Ledger state.
- SGE-WIK-03: The Candidate Wiki displays governed roles and exact source text.
- SGE-WIK-04: The Candidate Wiki omits structural Embedded entity reference edges from display.
- SGE-WIK-05: `wiki audit` exposes every structural edge and its source lineage.
- SGE-WIK-06: Canonical evaluation identifies the first failed stage for each Gold event.

### Superseded stages

- SGE-SUP-01: HP-4 EventFrameDraft behavior is superseded by HP-4 trigger discovery.
- SGE-SUP-02: HP-5 AtomicClaimDraft behavior is superseded by direct governed event construction.
- SGE-SUP-03: The Pipeline removes the HP-5 stage from its stage order.
- SGE-SUP-04: HP-6 consumes one HybridEventTriggerPreview directly.
- SGE-SUP-05: Prior HP-4 and HP-5 outputs remain disposable derived artifacts.
- SGE-SUP-06: KoteKomi adds no compatibility reader or migration for those artifacts.

## Proposed Architecture

```text
DocumentRepresentationBundle
             |
             v
     HP-4 trigger discovery
             |
             v
  HybridEventTriggerPreview
             |
             v
  HP-6 governed event task
             |
             v
 source validation + support
             |
             v
    HP-7 ProposedChanges
             |
             v
       Candidate Wiki
```

The Domain Core owns the governed event profile.

The Application Layer owns source validation, event construction, and admission decisions.

The model runtime supplies fallible semantic selections.

The Pipeline composes the stages and stores derived evidence in the Archive.

The Candidate Wiki projects review state and accepted Ledger state.

## Key Interactions

```text
Pipeline -> Qwen: SourceSegment and trigger task
Qwen -> Application: trigger proposals
Application -> Archive: HybridEventTriggerPreview
Pipeline -> Qwen: trigger, local candidates, and governed profile
Qwen -> Application: governed event selection
Application -> Qwen and NLI: CompleteProposition and exact source
Application -> Ledger: pending ProposedChanges
Pipeline -> Candidate Wiki: reviewable governed Events
```

## Data Model

`HybridEventTriggerPreview` replaces `HybridEventFramePreview`.

`EventArgumentTargetDraft` adds ordered `embedded_candidate_ids`.

`SemanticQualifierDraft` adds `temporal_relation` for time qualifiers.

`EventSemanticParseResult` contains one optional proposal and ordered Line rejections.

Version 4 replaces version 3 for newly built derived event semantics.

The accepted Event, Assertion, EvidenceTarget, and ProposedChange records retain their existing schemas.

## APIs / Interfaces

`kotekomi extraction discover-event-triggers --preview-id <hp3-preview-id>` runs HP-4.

The Pipeline removes `draft-event-frames` and `build-atomic-claims`.

The HP-6 command accepts one HybridEventTriggerPreview ID.

The Archive Port reads and writes HybridEventTriggerPreview bytes by Preview ID.

## Behavior & Domain Rules

- SGE-RUL-01: One trigger maps to at most one governed frame.
- SGE-RUL-02: One governed role maps to one complete source-backed target.
- SGE-RUL-03: A model line cannot create a source span that KoteKomi cannot resolve uniquely.
- SGE-RUL-04: Invalid optional lines cannot erase valid required fields.
- SGE-RUL-05: Structural Entity references support navigation and audit.
- SGE-RUL-06: Structural Entity references do not replace semantic role targets.
- SGE-RUL-07: A new profile or policy identity makes prior derived previews stale.
- SGE-RUL-08: Replay uses stored stage evidence and performs zero model calls.

## Acceptance Criteria

- AC-SGE-DOM-01: Domain tests prove the exact version-4 frame and role inventory.
- AC-SGE-DOM-02: Domain tests prove TemporalRelation validation.
- AC-SGE-TRG-01: Trigger tests detect `describing` as a distinct event trigger.
- AC-SGE-TRG-02: Trigger tests prove each task receives only SourceSegment-local candidates.
- AC-SGE-OUT-01: Parser tests retain valid roles after one malformed optional line.
- AC-SGE-OUT-02: Parser tests produce a typed gap for an invalid required envelope.
- AC-SGE-CON-01: Tests prove role completion runs only for missing required roles.
- AC-SGE-CMP-01: Tests prove exact Composite source targets and contained Entity references.
- AC-SGE-CMP-02: Tests reject non-contained Embedded entity references.
- AC-SGE-WIK-01: All five Amodei Gold events reach pending ProposedChanges.
- AC-SGE-WIK-02: All five events appear on the Amodei Candidate Wiki page.
- AC-SGE-WIK-03: Each Gold event displays exact source text and passes `wiki audit`.
- AC-SGE-REG-01: The seven previously approved Gold events retain their dispositions.
- AC-SGE-REG-02: The known false `said` event remains held or absent.
- AC-SGE-REG-03: Canonical replay performs zero model calls.
- AC-SGE-REG-04: Tests prove the operation writes no accepted Ledger state.

## Reference Implementations

- Stage evidence: follow `packages/application/src/kotekomi_application/extraction_stage_trace.py`.
- Model tasks: follow `packages/application/src/kotekomi_application/staged_model_extraction.py`.
- Optional line recovery: follow `packages/application/src/kotekomi_application/hybrid_standing_fact_model_output.py`.
- Source validation: follow `packages/application/src/kotekomi_application/evidence_targets.py`.
- Candidate Wiki audit: follow `packages/application/src/kotekomi_application/candidate_wiki.py`.

## Constraints and Halt Conditions

Stop if the implementation loses one previously approved Gold event.

Stop if a model result writes accepted Ledger state without human review.

Stop if a Composite source target replaces its exact source span with one contained Entity.
