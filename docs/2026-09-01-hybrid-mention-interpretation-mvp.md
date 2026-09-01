# TDD: Hybrid Mention Interpretation MVP

- Status: Accepted
- Program: [Hybrid Intelligence Extraction Pipeline](2026-09-01-hybrid-intelligence-extraction-pipeline.md)
- Increment: HP-1
- Depends on: [Staged Model Extraction](2026-07-11-staged-model-extraction.md)
- Evidence baseline: [ORG-R1 Result](organization-boundary-reconciliation-result-v1.json)
- Scope: derived preview evidence only

## Context & Problem

KoteKomi uses GLiNER and Qwen2.5 to propose Organization source spans.

The current proposer contract asks each model to assume that the target is an Organization.

ORG-R1 validates literal boundaries and preserves unresolved candidate conflicts.

ORG-R2 asks Qwen2.5 and ReFinED whether one literal candidate denotes an Organization.

The ORG-R2 benchmark shows that entity type and contextual source use are different decisions.

The current contract cannot represent that difference.

For example, `European Union` can identify an Organization while the sentence uses it as an origin.

The expression `AISIs` can describe a generic Organization class without naming one Organization.

HP-1 will create ontology-neutral MentionCandidates from one authoritative paragraph.

HP-1 will ask Qwen2.5 to judge three separate contextual dimensions for each candidate.

HP-1 will preserve the results in one durable HybridExtractionPreview.

HP-1 will not call ReFinED or create ProposedChanges.

### Terms

**SourceSegment** means one exact contiguous source range that KoteKomi derives from a paragraph.

**MentionObservation** means one GLiNER or Qwen2.5 source-span proposal.

**MentionCandidate** means one source-valid span that retains every matching MentionObservation.

**Referentiality** identifies whether a MentionCandidate refers to one specific entity.

**ContextualKind** identifies what the MentionCandidate denotes in its source context.

**DiscourseRole** identifies how the sentence uses the MentionCandidate.

**MentionInterpretation** records all three contextual dimensions for one MentionCandidate.

**OntologyGuidelineCard** defines the contextual dimensions for one model task.

**HybridExtractionPreview** records the complete HP-1 result and stage lineage.

### Primary flow

1. An operator selects one paragraph from an accepted DocumentRepresentationBundle.
2. The Pipeline builds one ContextManifest and runs GLiNER and Qwen2.5 as independent proposers.
3. The Application Layer validates and reconciles all MentionObservations against source characters.
4. The Pipeline asks Qwen2.5 to interpret each MentionCandidate with one OntologyGuidelineCard.
5. The Pipeline stores one HybridExtractionPreview and prints its identity and Archive location.

The operator can inspect every source span, proposal, boundary decision, and interpretation.

The operation creates execution records but does not change accepted intelligence.

## Goals

- A reviewer can inspect broad source-span proposals from GLiNER and Qwen2.5.
- A reviewer can inspect referentiality, contextual kind, and discourse role separately.
- A reviewer can trace every interpretation to exact source characters and one ModelRun.
- A reviewer can distinguish unclear semantics from invalid model output.
- An operator can replay the deterministic stages from retained evidence.
- The operation creates no ProposedChange or accepted intelligence record.

## Requirements

### Paragraph selection

- HM-SRC-01: The Pipeline accepts one representation ID and one paragraph node ID.
- HM-SRC-02: The Pipeline loads the accepted DocumentRepresentationBundle from the Ledger.
- HM-SRC-03: The Pipeline rejects a node that does not belong to the representation.
- HM-SRC-04: The Pipeline rejects a node whose type is not `paragraph`.
- HM-SRC-05: The ContextPlanner uses the named `hybrid_mention_preview_v1` policy.
- HM-SRC-06: The ContextManifest includes the paragraph and its required structural ancestry.
- HM-SRC-07: The Pipeline validates the ContextManifest before it calls either proposer.

### Mention proposers

- HM-PRO-01: GLiNER and Qwen2.5 receive the same SourceSegments.
- HM-PRO-02: Each proposer creates a separate execution record.
- HM-PRO-03: GLiNER returns source ranges through the generic MentionProposer Port.
- HM-PRO-04: Qwen2.5 returns literal expressions and type hints through the ModelRuntime Port.
- HM-PRO-05: The Application Layer maps each Qwen2.5 expression to every exact source occurrence.
- HM-PRO-06: Each resulting MentionObservation identifies one SourceSegment and one half-open range.
- HM-PRO-07: Each MentionObservation includes one or more ContextualKind type hints.
- HM-PRO-08: A proposer score remains diagnostic evidence.
- HM-PRO-09: The Pipeline requires both proposer executions to reach a terminal status.
- HM-PRO-10: A missing proposer runtime produces a typed blocked result.
- HM-PRO-11: The Pipeline preserves complete raw proposer output before validation.

### Boundary reconciliation

- HM-BND-01: The Application Layer validates every proposed range against source characters.
- HM-BND-02: The Application Layer rejects one malformed MentionObservation without repairing it.
- HM-BND-03: Equal ranges produce one MentionCandidate with all proposer evidence.
- HM-BND-04: The Application Layer applies the ORG-R1 parenthetical declaration rule.
- HM-BND-05: The Application Layer applies the ORG-R1 terminal possessive rule.
- HM-BND-06: Every other nested or crossing conflict remains ambiguous.
- HM-BND-07: An ambiguous conflict retains every source-valid MentionObservation.
- HM-BND-08: Scores, proposer identity, input order, and observation count cannot select a boundary.
- HM-BND-09: The new generic records do not modify the sealed ORG-R1 evidence bundles.

### Ontology guideline

- HM-ONT-01: One versioned OntologyGuidelineCard defines all HP-1 labels.
- HM-ONT-02: The card defines each label with positive and negative source-use examples.
- HM-ONT-03: The card distinguishes a specific entity from a generic class.
- HM-ONT-04: The card distinguishes contextual kind from discourse role.
- HM-ONT-05: The Pipeline records the card bytes and SHA-256 digest in each interpretation task.
- HM-ONT-06: The Pipeline sends only the HP-1 card instead of the complete KoteKomi ontology.

### Mention interpretation

- HM-INT-01: The Pipeline creates one bounded task for each selected or uncontested MentionCandidate.
- HM-INT-02: The task receives one task-local candidate label and exact source text.
- HM-INT-03: The task receives the SourceSegment that contains the candidate.
- HM-INT-04: The task receives structural context from the verified ContextManifest.
- HM-INT-05: The task receives no Ledger ID, Archive path, source offset, or external entity ID.
- HM-INT-06: The model selects one Referentiality value.
- HM-INT-07: The model selects one ContextualKind value.
- HM-INT-08: The model selects one DiscourseRole value.
- HM-INT-09: The model selects one visible SourceSegment as its contextual support.
- HM-INT-10: The Application Layer maps the task-local label to the MentionCandidate ID.
- HM-INT-11: The Application Layer maps the support label to an exact SourceSegment.
- HM-INT-12: The Application Layer rejects unknown labels and extra fields.
- HM-INT-13: Invalid model output creates no MentionInterpretation.
- HM-INT-14: Invalid model output preserves the MentionCandidate and failed ModelRun.
- HM-INT-15: An unclear label is a valid semantic judgment.

### Diagnostic Gold

- HM-GOLD-01: One reviewed catalog identifies a fixed set of exact MentionCandidates.
- HM-GOLD-02: The catalog binds each candidate to authoritative source identity and characters.
- HM-GOLD-03: The catalog assigns expected values for all three contextual dimensions.
- HM-GOLD-04: The catalog includes specific, generic, anaphoric, and unclear cases.
- HM-GOLD-05: The catalog includes actor, origin, location, object, and modifier uses.
- HM-GOLD-06: The catalog includes competing Organization, place, project, initiative, and product hints.
- HM-GOLD-07: The catalog records reviewer notes for each expected interpretation.
- HM-GOLD-08: The catalog is diagnostic evidence and does not define a production threshold.

### Preview evidence

- HM-PRV-01: The Application Layer constructs one HybridExtractionPreview after all tasks terminate.
- HM-PRV-02: The preview identifies the representation, paragraph, ContextManifest, and policy.
- HM-PRV-03: The preview includes all observations, candidates, boundary decisions, and interpretations.
- HM-PRV-04: The preview references every ExtractionTask, ModelRun, and ExtractionStageTrace.
- HM-PRV-05: The preview records blocked, invalid, abstained, and unclear outcomes explicitly.
- HM-PRV-06: The preview uses canonical JSON encoding.
- HM-PRV-07: The Pipeline writes the preview atomically to the configured Archive.
- HM-PRV-08: A new nondeterministic run creates a new preview and preserves the prior preview.
- HM-PRV-09: The Pipeline prints the preview ID, digest, and Archive location as JSON.
- HM-PRV-10: The Pipeline creates no ProposedChange, Organization, Event, Assertion, or Relationship.

## Proposed Architecture

```text
Operator CLI
    |
    v
Preview Pipeline
    |
    v
Application use case ----> ContextPlanner
    |          |
    |          +---------> ModelRuntime Port ----> Qwen2.5 Adapter
    |
    +--------------------> MentionProposer Port -> GLiNER Adapter
    |
    +--------------------> PreviewStore Port ----> Archive Adapter
```

The Pipeline owns command orchestration and result rendering.

The Application Layer owns source validation, reconciliation, and interpretation mapping.

The Adapters translate tool outputs into Application Layer DTOs.

The PreviewStore Port owns immutable HybridExtractionPreview publication.

## Key Interactions

```text
Operator     Pipeline     Application     GLiNER       Qwen       PreviewStore
   |            |              |             |            |             |
   | preview    |              |             |            |             |
   |----------->| load context |             |            |             |
   |            |------------->|             |            |             |
   |            |              | propose     |            |             |
   |            |              |------------>|            |             |
   |            |              | propose     |            |             |
   |            |              |------------------------->|             |
   |            |              | reconcile   |            |             |
   |            |              |------|       |            |             |
   |            |              | interpret candidates     |             |
   |            |              |------------------------->|             |
   |            |              | publish preview          |             |
   |            |              |--------------------------------------->|
   | result     |              |             |            |             |
   |<-----------|              |             |            |             |
```

## Data Model

### Existing records

HP-1 reuses DocumentRepresentationBundle, ContextManifest, ExtractionTask, and ModelRun.

HP-1 reuses ExtractionStageTrace as derived diagnostic evidence.

### New Application Layer DTOs

```text
MentionObservation
  id
  source_segment_id
  start
  end
  text
  type_hints
  producer_id
  execution_record_id
  score
  diagnostics

MentionCandidate
  id
  source_segment_id
  source_text_sha256
  start
  end
  text
  observation_ids
  type_hints

MentionBoundaryDecision
  id
  source_segment_id
  candidate_ids
  status
  rule_id
  selected_candidate_ids
  preserved_candidate_ids
  alias_evidence_candidate_ids
  diagnostics

MentionInterpretation
  id
  candidate_id
  referentiality
  contextual_kind
  discourse_role
  support_segment_id
  model_run_id
  trace_id

HybridExtractionPreview
  schema_version
  id
  representation_id
  paragraph_node_id
  context_manifest_id
  policy_id
  ontology_card_sha256
  observations
  candidates
  boundary_decisions
  interpretations
  extraction_task_ids
  model_run_ids
  traces
  terminal_status
  diagnostics
```

### Label vocabularies

```text
Referentiality
  specific_entity
  generic_class
  anaphoric
  unclear

ContextualKind
  person
  organization
  government
  geopolitical_entity
  place
  event
  project
  initiative
  product
  policy
  publication
  other
  unclear

DiscourseRole
  actor
  participant
  origin
  location
  object
  modifier
  other
  unclear
```

The Archive stores each HybridExtractionPreview as derived evidence.

The Ledger stores only the existing execution records created by HP-1.

The reviewed diagnostic catalog is `docs/hp1-contextual-mention-gold-v1.json`.

The catalog binds its exact source text to
`packages/application/tests/fixtures/hybrid-mention-context-v1.json`.

## APIs / Interfaces

The Operator CLI adds `kotekomi extraction preview-mentions`.

The command requires `--representation-id` and `--node-id`.

The command accepts the existing global configuration option.

The command emits one JSON object to stdout.

The command sends runtime diagnostics to stderr.

The command returns exit code `0` only for a `complete` preview.

The command returns exit code `1` for a `partial` or `blocked` preview.

The command prints these fields for every published preview:

```text
status
preview_id
sha256
archive_path
```

The Archive path is `extraction/previews/<preview-id>.json`.

The Application Layer defines one generic MentionProposer Port.

The GLiNER Adapter implements the generic MentionProposer Port.

The Qwen2.5 path uses the existing ModelRuntime Port.

The Application Layer defines one PreviewStore Port.

The Archive Adapter implements the PreviewStore Port.

The PreviewStore rejects different bytes for an existing Preview identity.

The PreviewStore can reuse identical bytes for an existing Preview identity.

The Application Layer derives the Preview identity from the canonical Preview body.

The Preview body excludes the Preview identity during identity derivation.

The Preview body includes the nondeterministic ModelRun and trace identities.

Therefore, a new model execution creates a new Preview identity.

## Behavior & Domain Rules

The Pipeline requires both proposer results before it reconciles candidates.

One blocked proposer produces a blocked HybridExtractionPreview and skips reconciliation.

One proposer output that fails its complete output contract produces a blocked
HybridExtractionPreview and skips reconciliation.

One valid proposer abstention supplies an empty proposal set.

The Pipeline continues after one valid proposer abstention when the other proposer succeeds.

One invalid MentionObservation does not invalidate another source-valid observation.

The preview reports each invalid observation with its producer evidence.

An ambiguous boundary receives no selected MentionCandidate for that conflict.

The preview still retains every observation in that ambiguous conflict.

The Pipeline interprets only selected and uncontested MentionCandidates.

The Pipeline records `interpretation_pending_boundary` for ambiguous conflicts.

The Pipeline persists completed interpretations even when another interpretation task fails.

The terminal preview reports `complete`, `partial`, or `blocked`.

A partial preview contains at least one valid MentionCandidate and one failed interpretation task.

A complete preview can contain no MentionCandidate when both proposer executions terminate with
valid empty results.

ReFinED does not run during HP-1.

HP-1 does not resolve global entity identity or document-level coreference.

### Model output contracts

The Qwen2.5 proposer returns one line for each proposal:

```text
mention: <sN> | <contextual-kind>[,<contextual-kind>...] | <literal expression>
```

The Qwen2.5 proposer can return one abstention line:

```text
abstain: <non-empty reason>
```

The Application Layer maps each literal expression only inside its named SourceSegment.

The Qwen2.5 interpretation task returns exactly five lines:

```text
candidate: c1
referentiality: <allowed Referentiality value>
contextual_kind: <allowed ContextualKind value>
discourse_role: <allowed DiscourseRole value>
support: <sN>
```

The Application Layer rejects a different line order, an unknown value, or another line.

### Proposer execution records

The Pipeline records one ExtractionTask and one ModelRun for the GLiNER proposer.

The Pipeline records one ExtractionTask and one ModelRun for the Qwen2.5 proposer.

The Pipeline stores the canonical GLiNER Adapter output as the GLiNER ModelRun raw output.

The Pipeline stores the exact Qwen2.5 runtime output as the Qwen2.5 ModelRun raw output.

## Acceptance Criteria

- AC-HM-SRC-01: Pipeline tests prove representation and paragraph ownership validation.
- AC-HM-SRC-02: Pipeline tests prove non-paragraph and missing nodes fail before model work.
- AC-HM-PRO-01: Adapter tests prove both proposers receive identical SourceSegments.
- AC-HM-PRO-02: Tests prove a missing proposer produces a typed blocked result.
- AC-HM-BND-01: Application tests prove equal, parenthetical, possessive, and ambiguous outcomes.
- AC-HM-BND-02: Perturbation tests prove scores, order, and proposer identity do not select boundaries.
- AC-HM-ONT-01: Tests prove the task fingerprint changes when the guideline card changes.
- AC-HM-INT-01: Application tests prove every valid label combination maps without source drift.
- AC-HM-INT-02: Negative tests prove unknown labels and support segments create no interpretation.
- AC-HM-INT-03: Tests prove an unclear value remains distinct from invalid model output.
- AC-HM-GOLD-01: Catalog tests prove source identity, exact characters, and complete expected labels.
- AC-HM-GOLD-02: The canonical run reports each contextual dimension against the reviewed catalog.
- AC-HM-PRV-01: Restart tests prove the PreviewStore preserves immutable canonical JSON.
- AC-HM-PRV-02: Tests prove repeated nondeterministic runs preserve both previews.
- AC-HM-PRV-03: Tests prove no ProposedChange or accepted intelligence record is created.
- AC-HM-E2E-01: A fixture classifies `European Union` as specific, organizational, and origin use.
- AC-HM-E2E-02: A fixture classifies `AISIs` as a generic organizational class.
- AC-HM-E2E-03: A fixture classifies a country signatory as a specific government actor.
- AC-HM-E2E-04: A fixture preserves competing product and Organization hints until interpretation.
- AC-HM-E2E-05: A canonical local run writes complete data-in and data-out evidence for review.
- AC-HM-E2E-06: The canonical run reports stage-local accuracy without selecting production behavior.

## Reference Implementations

- Model execution: follow `packages/application/src/kotekomi_application/staged_model_extraction.py`.
- Boundary rules: follow `packages/application/src/kotekomi_application/organization_mention_boundary_reconciliation.py`.
- Stage traces: follow `packages/application/src/kotekomi_application/extraction_stage_trace.py`.
- GLiNER mapping: follow `packages/adapters/src/kotekomi_adapters/gliner_organization_mention_proposer.py`.
- ReFinED evidence remains outside HP-1 in `packages/adapters/src/kotekomi_adapters/refined_organization_type.py`.
- CLI composition: follow `packages/pipelines/src/kotekomi_pipelines/cli.py`.

## Constraints and Halt Conditions

Stop when HP-1 requires a global identity decision to produce MentionInterpretation.

Stop when the model must return source offsets or canonical IDs.

Stop when a broad type hint becomes an accepted contextual type without Qwen2.5 interpretation.

Stop when a preview cannot retain complete proposer and interpretation evidence.

Stop when an implementation changes sealed ORG-R1 or ORG-R2 evidence.
