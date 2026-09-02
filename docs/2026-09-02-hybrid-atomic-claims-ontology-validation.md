# TDD: Hybrid Atomic Claims and Ontology Validation

- Status: Accepted
- Program: [Hybrid Intelligence Extraction Pipeline](2026-09-01-hybrid-intelligence-extraction-pipeline.md)
- Increment: HP-5
- Depends on: [Hybrid Event Frame Drafts](2026-09-01-hybrid-event-frame-drafts.md)
- Scope: derived AtomicClaimDrafts and canonical EvidenceTargets only
- Evaluation: [HP-5 Atomic Claim and Ontology Evaluation](2026-09-02-hp5-atomic-claim-evaluation.md)

## Context & Problem

HP-4 preserves source-valid EventFrameDrafts with open event and role labels.

HP-4 does not turn those frames into atomic claims.

HP-4 also does not evaluate whether its open labels conform to the Ontology Profile.

The HP-4 evaluation found source-valid frames with inconsistent event and role labels.

Some HP-4 frames also contain semantically questionable model judgments.

HP-5 will atomize every structurally valid frame without repairing its semantics.

HP-5 will validate each atom against one versioned structural ontology slice.

HP-5 will retain every unknown label as an explicit ontology finding.

HP-5 will create exact EvidenceTargets from authoritative SourceSegments.

HP-5 will create no accepted intelligence and no ProposedChange.

### Terms

**EventSubjectDraft** means one derived event subject for one HP-4 EventFrameDraft.

**AtomicClaimDraft** means one derived subject-predicate-object statement about an EventSubjectDraft.

**Structural predicate** means one source-agnostic relation in the HP-5 ontology slice.

**Ontology finding** means one deterministic conformance failure for an AtomicClaimDraft or frame.

**OntologyValidationReport** means the complete ontology result for one HP-4 frame.

**HybridAtomicClaimPreview** means one immutable derived HP-5 result for one HP-4 Preview.

### Primary flow

1. An operator selects one immutable HybridEventFramePreview.
2. The Application Layer verifies its complete HP-4 through HP-1 lineage.
3. The Application Layer creates one EventSubjectDraft for each valid EventFrameDraft.
4. The Application Layer constructs event-first AtomicClaimDrafts from each frame field.
5. The Application Layer creates and validates SourceSegment-backed EvidenceTargets.
6. The Application Layer validates each draft against the pinned ontology slice.
7. The Pipeline stores one immutable HybridAtomicClaimPreview and prints its identity.

## Goals

- A reviewer can inspect one atomic statement for each event-frame component.
- A reviewer can inspect every ontology finding without losing the proposed claim.
- A reviewer can replay every claim against exact authoritative source text.
- A reviewer can distinguish an upstream semantic error from an HP-5 mapping error.
- An operator can rerun HP-5 without a model runtime.
- The operation creates no accepted intelligence or ProposedChange.

## Requirements

### Parent evidence

- HAC-PAR-01: The command requires one HybridEventFramePreview ID.
- HAC-PAR-02: The Application Layer verifies canonical HP-4 Preview bytes and digest.
- HAC-PAR-03: The Application Layer verifies the HP-3, HP-2, and HP-1 parent chain.
- HAC-PAR-04: The Application Layer verifies one accepted DocumentRepresentationBundle.
- HAC-PAR-05: The Application Layer rejects changed source or parent evidence before Ledger writes.
- HAC-PAR-06: The Application Layer processes every valid frame from a partial HP-4 Preview.
- HAC-PAR-07: The Application Layer does not reinterpret a questionable HP-4 frame.

### Ontology slice

- HAC-ONT-01: Domain Core defines the `hybrid_event_core_v1` ontology slice.
- HAC-ONT-02: The slice defines `has_event_type` for one literal event label.
- HAC-ONT-03: The slice defines `has_argument` for one MentionCandidate reference.
- HAC-ONT-04: The slice defines `has_time` and `has_place` for one literal qualifier.
- HAC-ONT-05: The slice defines `has_polarity` and `has_modality` for one literal value.
- HAC-ONT-06: The slice defines `according_to` for one Source or MentionCandidate reference.
- HAC-ONT-07: The slice recognizes exact core role labels only.
- HAC-ONT-08: The core role labels are `actor`, `participant`, `object`, `place`, and `time`.
- HAC-ONT-09: The slice recognizes `event` as its only core event label.
- HAC-ONT-10: The slice applies no alias, fuzzy, case-fold, or semantic mapping.
- HAC-ONT-11: The slice exposes canonical bytes and a SHA-256 digest.

### Atomic claim construction

- HAC-ATM-01: One EventFrameDraft creates one EventSubjectDraft.
- HAC-ATM-02: The EventSubjectDraft identity binds its frame, trigger, and HP-4 parent.
- HAC-ATM-03: One frame creates one `has_event_type` AtomicClaimDraft.
- HAC-ATM-04: Each EventArgumentDraft creates one `has_argument` AtomicClaimDraft.
- HAC-ATM-05: Each time qualifier creates one `has_time` AtomicClaimDraft.
- HAC-ATM-06: Each place qualifier creates one `has_place` AtomicClaimDraft.
- HAC-ATM-07: Each frame creates one `has_polarity` AtomicClaimDraft.
- HAC-ATM-08: Each frame creates one `has_modality` AtomicClaimDraft.
- HAC-ATM-09: Source narrator attribution creates one `according_to` AtomicClaimDraft.
- HAC-ATM-10: Candidate attribution requires an exact attribution support SourceSegment.
- HAC-ATM-11: HP-4 supplies no candidate attribution support SourceSegment in this increment.
- HAC-ATM-12: HP-5 preserves unsupported candidate attribution as a finding without an atom.
- HAC-ATM-13: Every AtomicClaimDraft has exactly one object reference or literal object.
- HAC-ATM-14: The Application Layer orders claims by frame, predicate, and object identity.
- HAC-ATM-15: The Application Layer derives every draft identity from canonical content.
- HAC-ATM-16: HP-5 preserves separate claims across frames and performs no semantic deduplication.

### EvidenceTargets

- HAC-EVD-01: Every AtomicClaimDraft references one canonical EvidenceTarget.
- HAC-EVD-02: Event type, polarity, modality, and source attribution use the trigger SourceSegment.
- HAC-EVD-03: An argument atom uses its declared support SourceSegment.
- HAC-EVD-04: A qualifier atom uses its qualifier SourceSegment.
- HAC-EVD-05: Each EvidenceTarget selects the full authoritative SourceSegment.
- HAC-EVD-06: Each EvidenceTarget binds the Source, Document, representation, and TextView.
- HAC-EVD-07: Each EvidenceTarget retains the paragraph node and its source regions.
- HAC-EVD-08: The Application Layer validates each unsaved EvidenceTarget before persistence.
- HAC-EVD-09: The Ledger reuses an identical EvidenceTarget and validation attempt.
- HAC-EVD-10: The Ledger rejects conflicting EvidenceTarget or validation-attempt bytes.
- HAC-EVD-11: EvidenceTarget creation changes no accepted intelligence record.

### Ontology validation

- HAC-VAL-01: Each frame creates one OntologyValidationReport.
- HAC-VAL-02: The report identifies its ontology slice and digest.
- HAC-VAL-03: An unknown event label creates `unmapped_event_type`.
- HAC-VAL-04: An unknown argument role creates `unmapped_argument_role`.
- HAC-VAL-05: Unsupported candidate attribution creates `attribution_support_missing`.
- HAC-VAL-06: A finding never removes or rewrites an AtomicClaimDraft.
- HAC-VAL-07: A conformant report has no findings.
- HAC-VAL-08: A nonconformant report contains one or more ordered findings.
- HAC-VAL-09: Ontology conformance does not assert textual support.
- HAC-VAL-10: An ontology finding does not block later source-support judgment.

### Execution evidence

- HAC-TRC-01: Each frame creates one atomic-construction ExtractionStageTrace.
- HAC-TRC-02: Each frame creates one ontology-validation ExtractionStageTrace.
- HAC-TRC-03: The construction trace contains the exact frame, source records, and created drafts.
- HAC-TRC-04: The validation trace contains the exact slice, claims, and report.
- HAC-TRC-05: The validation trace names the construction trace as its parent.
- HAC-TRC-06: HP-5 creates no ExtractionTask or ModelRun.

### Preview evidence

- HAC-PRV-01: The Preview identifies its HP-4 parent and verified upstream lineage.
- HAC-PRV-02: The Preview contains every EventSubjectDraft and AtomicClaimDraft.
- HAC-PRV-03: The Preview contains every OntologyValidationReport and stage trace.
- HAC-PRV-04: The Preview references every EvidenceTarget and validation attempt.
- HAC-PRV-05: The Preview uses canonical JSON and a content-derived identity.
- HAC-PRV-06: The Archive publishes the Preview atomically and reuses identical bytes.
- HAC-PRV-07: Reload verifies canonical bytes, lineage, EvidenceTargets, and attempts.
- HAC-PRV-08: A complete HP-4 parent produces a complete HP-5 Preview.
- HAC-PRV-09: A partial HP-4 parent with valid frames produces a partial HP-5 Preview.
- HAC-PRV-10: A blocked parent with no valid frames produces a blocked HP-5 Preview.
- HAC-PRV-11: A complete empty parent produces a complete empty HP-5 Preview.
- HAC-PRV-12: Ontology findings do not change the execution status.
- HAC-PRV-13: HP-5 creates no Event, Assertion, Relationship, or ProposedChange.

### Public operation

- HAC-CLI-01: `kotekomi extraction build-atomic-claims` runs HP-5.
- HAC-CLI-02: The command requires `--preview-id <hp4-preview-id>`.
- HAC-CLI-03: The command requires no model runtime.
- HAC-CLI-04: Standard output includes status, Preview identities, digest, path, and record counts.
- HAC-CLI-05: A complete Preview exits zero.
- HAC-CLI-06: A partial or blocked Preview exits one.

## Proposed Architecture

```text
HP-4 Preview -> verified parent and source lineage
                         |
                         v
                 deterministic atomizer
                         |
             +-----------+-----------+
             |                       |
             v                       v
     EvidenceTargets          ontology validation
             |                       |
             +-----------+-----------+
                         |
                         v
              HybridAtomicClaimPreview
```

Domain Core owns the structural ontology slice and intrinsic ontology rules.

The Application Layer owns atomization, source mapping, validation, and terminal status.

The Pipeline owns Ledger transactions, Archive composition, and public output.

The existing SQLite and local Archive Adapters persist the records.

## Key Interactions

```text
Operator       Pipeline       Application       Ledger       Archive
   |              |                |               |             |
   | build claims |                |               |             |
   |------------->| load parent    |               |             |
   |              |--------------------------------------------->|
   |              | validate source--------------->|             |
   |              | atomize        |               |             |
   |              |--------------->|               |             |
   |              | persist evidence-------------->|             |
   |              | publish Preview----------------------------->|
   |<-------------| result         |               |             |
```

## Data Model

HP-5 adds a pure Domain Core `HybridEventOntologySlice` record.

HP-5 adds derived Application Layer DTOs.

```text
EventSubjectDraft
  id
  parent_preview_id
  frame_id
  trigger_id

AtomicClaimDraft
  id
  frame_id
  event_subject_id
  predicate
  object_kind
  object_reference_id or object_value
  role_label
  evidence_target_id
  evidence_validation_attempt_id
  source_trace_ids

OntologyValidationFinding
  code
  frame_id
  claim_id
  field_path
  proposed_value

OntologyValidationReport
  id
  frame_id
  ontology_slice_id
  ontology_slice_sha256
  claim_ids
  status
  findings

HybridAtomicClaimPreview
  schema_version
  id
  parent_preview_id
  parent_preview_sha256
  upstream lineage identities and digests
  representation_id
  paragraph_node_id
  policy_id
  ontology_slice_id
  ontology_slice_sha256
  event_subjects
  atomic_claims
  ontology_reports
  evidence_target_ids
  evidence_validation_attempt_ids
  traces
  terminal_status
  diagnostics
```

The Ledger stores EvidenceTarget and EvidenceValidationAttempt records.

The Archive stores each HybridAtomicClaimPreview as derived evidence.

HP-5 requires no Ledger migration.

## APIs / Interfaces

The HP-5 use case accepts one HP-4 Preview ID.

The use case returns one Preview, digest, and Archive path.

The Archive Port reads and writes HybridAtomicClaimPreview canonical bytes.

The Archive path is `extraction/atomic-claim-previews/<preview-id>.json`.

The CLI emits these fields:

```text
status
preview_id
parent_preview_id
sha256
archive_path
claim_count
ontology_finding_count
evidence_target_count
```

## Behavior & Domain Rules

AtomicClaimDraft records remain derived evidence.

An ontology finding describes conformance and does not describe source truth.

HP-5 transforms HP-4 semantics without correcting them.

HP-6 can judge source support for conformant and nonconformant AtomicClaimDrafts.

Only later review can create accepted Event or Assertion records.

A deterministic integrity failure aborts the Ledger transaction and publishes no Preview.

An Archive failure can leave reusable EvidenceTargets but no accepted intelligence.

## Acceptance Criteria

- AC-HAC-01: Domain tests prove exact structural predicates, labels, bytes, and digest.
- AC-HAC-02: Application tests prove every frame component creates the required atom.
- AC-HAC-03: Tests prove unknown labels create findings without deleting claims.
- AC-HAC-04: Tests prove HP-5 applies no alias, case-fold, fuzzy, or semantic mapping.
- AC-HAC-05: Tests prove SourceSegment-backed EvidenceTargets replay exactly.
- AC-HAC-06: Tests prove identical reruns reuse EvidenceTargets and Preview bytes.
- AC-HAC-07: Negative tests prove stale, conflicting, and tampered evidence fails before publication.
- AC-HAC-08: Tests prove source narrator and unsupported candidate attribution behavior.
- AC-HAC-09: Tests prove complete, partial, blocked, and empty complete Preview states.
- AC-HAC-10: Tests prove no Event, Assertion, Relationship, or ProposedChange is created.
- AC-HAC-11: Archive tests prove immutable create, reuse, conflict, and restart reload.
- AC-HAC-12: CLI tests prove routing, output fields, counts, and exit codes.
- AC-HAC-13: A production-equivalent evaluation covers the 12 reviewed HP-4 paragraphs.
- AC-HAC-14: The evaluation records exact frame input, claim output, evidence, and findings.
- AC-HAC-15: The evaluation assigns every discrepancy to its owning Pipeline stage.
- AC-HAC-16: A second HP-5 replay produces identical Preview bytes and counts.
- AC-HAC-17: Formatting, lint, pyright, focused tests, and the full test suite pass.

## Reference Implementations

- Parent validation: follow `hybrid_event_frame_preview.py`.
- EvidenceTarget construction: follow `grounded_candidates.py`.
- Immutable Archive storage: follow `local_archive.py`.
- Stage traces: follow `extraction_stage_trace.py`.

## Constraints and Halt Conditions

Stop when HP-5 requires a model to select one ontology label.

Stop when HP-5 must repair one semantically questionable HP-4 frame.

Stop when ontology conformance must become source-support confidence.

Stop when an AtomicClaimDraft must become accepted intelligence without review.
