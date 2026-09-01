# TDD: Hybrid Document Reference Resolution

- Status: Accepted
- Program: [Hybrid Intelligence Extraction Pipeline](2026-09-01-hybrid-intelligence-extraction-pipeline.md)
- Increment: HP-2
- Depends on: [Hybrid Mention Interpretation MVP](2026-09-01-hybrid-mention-interpretation-mvp.md)
- Scope: derived preview evidence only

## Context & Problem

HP-1 preserves source-valid MentionCandidates and separate contextual interpretations.

HP-1 does not resolve a later abbreviation to an earlier document declaration.

HP-1 also preserves anaphoric MentionCandidates such as `it` or `the institute`.

A model can suggest an antecedent for those expressions.

That suggestion cannot prove document identity.

HP-2 will resolve only explicit document aliases that KoteKomi can verify from source characters.

HP-2 will preserve every other reference as unresolved derived evidence.

HP-2 will consume one immutable HybridExtractionPreview.

HP-2 will publish one immutable HybridReferencePreview.

HP-2 will not call a model or create accepted intelligence.

### Terms

**ReferenceSpan** means one exact character range in an authoritative TextView.

**AliasDeclaration** means one source-valid `Expanded Name (ALIAS)` declaration.

**ReferenceDecision** means one terminal result for one eligible MentionCandidate.

**HybridReferencePreview** means the complete derived HP-2 result and its lineage.

**Unique alias** means one alias whose valid declarations have one expanded literal.

**Conflicting alias** means one alias whose valid declarations have multiple expanded literals.

### Primary flow

1. An operator selects one immutable HybridExtractionPreview.
2. The Pipeline loads its accepted DocumentRepresentationBundle.
3. The Application Layer finds explicit AliasDeclarations in every paragraph node.
4. The Application Layer resolves exact unique aliases among the HP-1 MentionCandidates.
5. The Application Layer records conflicting and anaphoric references as unresolved decisions.
6. The Pipeline publishes one HybridReferencePreview and prints its identity.

The operator can inspect each declaration, decision, source range, and parent Preview.

The operation creates no ModelRun and changes no accepted intelligence.

## Goals

- A reviewer can inspect exact document-local alias declarations.
- A reviewer can distinguish resolved aliases from conflicting aliases.
- A reviewer can inspect anaphoric references without an invented antecedent.
- A reviewer can trace each decision to exact source characters.
- An operator can replay HP-2 without a model runtime.
- The operation creates no ProposedChange or accepted intelligence record.

## Requirements

### Parent Preview

- HRP-01: The Pipeline requires one HybridExtractionPreview ID.
- HRP-02: The Archive loads the HybridExtractionPreview through its strict DTO.
- HRP-03: The Pipeline verifies the parent Preview canonical bytes and SHA-256 digest.
- HRP-04: The Pipeline accepts a complete or partial parent Preview.
- HRP-05: The Pipeline rejects a blocked parent Preview.
- HRP-06: The Pipeline loads the accepted representation named by the parent Preview.
- HRP-07: The Pipeline verifies the parent paragraph belongs to that representation.

### Alias declarations

- HRA-01: The Application Layer examines every paragraph node in the representation.
- HRA-02: The Application Layer reads paragraph characters from each node's TextView.
- HRA-03: An AliasDeclaration requires one parenthesized alias after one expanded literal.
- HRA-04: The alias contains two through sixteen ASCII letters, digits, or periods.
- HRA-05: The alias normalizes to at least two alphanumeric characters.
- HRA-06: The alias equals an initialism of the expanded literal.
- HRA-07: The initialism rule ignores the existing function-word vocabulary.
- HRA-08: The initialism rule retains the existing geographic-prefix behavior.
- HRA-09: The declaration finder selects the complete adjacent name expression.
- HRA-10: A ReferenceSpan stores absolute half-open TextView positions.
- HRA-11: Each ReferenceSpan stores the exact literal and its SHA-256 digest.
- HRA-12: The Application Layer validates every ReferenceSpan against TextView characters.
- HRA-13: Invalid parenthetical text creates no AliasDeclaration.
- HRA-14: A stage trace records each accepted AliasDeclaration.

### Reference eligibility

- HRE-01: HP-2 considers each selected HP-1 MentionCandidate once.
- HRE-02: An exact alias match makes a MentionCandidate eligible.
- HRE-03: An anaphoric MentionInterpretation makes a MentionCandidate eligible.
- HRE-04: Other MentionCandidates produce no ReferenceDecision.
- HRE-05: HP-2 reconstructs each candidate range from the parent paragraph.
- HRE-06: HP-2 verifies the reconstructed SourceSegment identity.
- HRE-07: HP-2 verifies the candidate text and source digest before a decision.

### Reference decisions

- HRD-01: One unique alias produces one resolved ReferenceDecision.
- HRD-02: A resolved decision references every declaration for its expanded literal.
- HRD-03: A conflicting alias produces one ambiguous ReferenceDecision.
- HRD-04: An ambiguous decision references every conflicting declaration.
- HRD-05: An anaphoric candidate without an exact alias produces one unresolved decision.
- HRD-06: An unmatched alias-shaped candidate produces one unresolved decision.
- HRD-07: A ReferenceDecision preserves its MentionCandidate ID.
- HRD-08: A ReferenceDecision preserves its exact ReferenceSpan.
- HRD-09: Scores cannot select an AliasDeclaration or antecedent.
- HRD-10: MentionInterpretation kind and role cannot override exact alias evidence.
- HRD-11: HP-2 does not resolve fuzzy, pluralized, or case-normalized aliases.
- HRD-12: HP-2 does not resolve pronouns or generic nominal references.
- HRD-13: Each ReferenceDecision records one named terminal reason.
- HRD-14: A stage trace records each ReferenceDecision and its declaration inputs.

### Preview evidence

- HRV-01: The Application Layer constructs one HybridReferencePreview.
- HRV-02: The Preview identifies its parent Preview and parent digest.
- HRV-03: The Preview identifies the representation and HP-2 policy.
- HRV-04: The Preview contains all AliasDeclarations and ReferenceDecisions.
- HRV-05: The Preview contains every HP-2 ExtractionStageTrace.
- HRV-06: The Preview uses canonical JSON encoding.
- HRV-07: The Pipeline writes the Preview atomically to the Archive.
- HRV-08: Deterministic replay reuses an identical Preview.
- HRV-09: Changed authoritative input produces a different Preview identity.
- HRV-10: The Pipeline prints the Preview ID, digest, parent ID, and Archive location.
- HRV-11: HP-2 creates no ModelRun or ExtractionTask.
- HRV-12: HP-2 creates no accepted Ledger record.

## Proposed Architecture

```text
Operator CLI
    |
    v
Reference Pipeline
    |
    v
Application use case ----> Ledger Port
    |                         |
    |                         +----> accepted representation
    |
    +--------------------> PreviewStore Port
                              |
                              +----> parent and HP-2 Previews
```

The Pipeline owns command composition and result rendering.

The Application Layer owns declaration and decision rules.

The Ledger Adapter loads the accepted representation.

The Archive Adapter validates and stores immutable Preview bytes.

## Key Interactions

```text
Operator       Pipeline       Application       Ledger        Archive
   |              |                |               |              |
   | resolve      |                |               |              |
   |------------->| load parent    |               |              |
   |              |--------------------------------------------->|
   |              | validate       |               |              |
   |              |--------------->| load bundle   |              |
   |              |                |-------------->|              |
   |              |                | find aliases  |              |
   |              |                |------|         |              |
   |              |                | decide refs    |              |
   |              |                |------|         |              |
   |              |                | publish Preview               |
   |              |--------------------------------------------->|
   | result       |                |               |              |
   |<-------------|                |               |              |
```

## Data Model

### Existing records

HP-2 reuses DocumentRepresentationBundle and ExtractionStageTrace.

HP-2 consumes HybridExtractionPreview, MentionCandidate, and MentionInterpretation.

### New Application Layer DTOs

```text
ReferenceSpan
  id
  representation_id
  node_id
  text_view_id
  start_char
  end_char
  text
  text_sha256

AliasDeclaration
  id
  expanded_span
  alias_span
  rule_id
  trace_id

ReferenceDecision
  id
  candidate_id
  reference_span
  reference_kind
  status
  declaration_ids
  antecedent_span_ids
  reason
  trace_id

HybridReferencePreview
  schema_version
  id
  parent_preview_id
  parent_preview_sha256
  representation_id
  policy_id
  alias_declarations
  reference_decisions
  traces
  terminal_status
  diagnostics
```

### Vocabularies

```text
ReferenceKind
  explicit_alias
  anaphoric

ReferenceStatus
  resolved
  ambiguous
  unresolved

ReferenceReason
  unique_explicit_alias
  conflicting_explicit_alias
  explicit_alias_missing
  semantic_resolution_deferred
```

The Archive stores each HybridReferencePreview as derived evidence.

The Ledger stores no new record for HP-2.

The deterministic contract catalog is `docs/hp2-document-reference-gold-v1.json`.

## APIs / Interfaces

The Operator CLI adds `kotekomi extraction resolve-references`.

The command requires `--preview-id`.

The command accepts the existing Ledger and Archive configuration options.

The command does not require model runtime configuration.

The command emits one JSON object to stdout.

The command sends diagnostics to stderr.

The command returns exit code `0` for a complete Preview.

The command returns exit code `1` when a precondition fails.

The command prints these fields:

```text
status
preview_id
parent_preview_id
sha256
archive_path
```

The Archive path is `extraction/reference-previews/<preview-id>.json`.

The PreviewStore Port loads HybridExtractionPreview bytes.

The PreviewStore Port publishes and loads HybridReferencePreview bytes.

The PreviewStore rejects different bytes for an existing Preview identity.

The PreviewStore reuses identical bytes for an existing Preview identity.

## Behavior & Domain Rules

HP-2 resolves an alias only from source-valid explicit declarations.

Repeated declarations of one alias and one expanded literal remain one unique alias.

The resolved decision retains every repeated declaration.

One alias with multiple expanded literals remains ambiguous.

Document order cannot resolve a conflicting alias.

An anaphoric candidate remains unresolved even when one likely antecedent is visible.

An unresolved decision contains no antecedent span ID.

An ambiguous decision contains all candidate antecedent span IDs.

A resolved decision contains all spans for its one expanded literal.

HP-2 uses exact alias characters for lookup.

HP-2 treats `AISI`, `A.I.S.I.`, and `AISIs` as different expressions.

HP-2 preserves parent HP-1 evidence instead of copying it into the new Preview.

HP-2 uses parent Preview identity and digest as the immutable lineage link.

HP-2 stage traces contain complete deterministic data-in and data-out payloads.

HP-2 never turns derived reference evidence into accepted identity.

## Acceptance Criteria

- AC-HRP-01: Tests reject missing, malformed, blocked, and representation-drifted parents.
- AC-HRA-01: Tests prove same-paragraph and cross-paragraph declarations use exact ranges.
- AC-HRA-02: Tests prove function words and geographic prefixes retain current behavior.
- AC-HRA-03: Tests prove malformed initialisms create no AliasDeclaration.
- AC-HRE-01: Tests prove each selected candidate receives at most one decision.
- AC-HRE-02: Tests prove ordinary full names receive no ReferenceDecision.
- AC-HRD-01: Tests prove one unique exact alias resolves across paragraphs.
- AC-HRD-02: Tests prove repeated equal declarations remain resolved.
- AC-HRD-03: Tests prove conflicting declarations remain ambiguous.
- AC-HRD-04: Tests prove anaphoric references remain unresolved.
- AC-HRD-05: Tests prove scores, kind, role, and order cannot select an antecedent.
- AC-HRD-06: Tests prove fuzzy, pluralized, and case-changed aliases do not resolve.
- AC-HRV-01: Tests prove canonical serialization and stable identity.
- AC-HRV-02: Restart tests prove immutable Archive publication and reuse.
- AC-HRV-03: Negative tests prove tampered parent and HP-2 Preview bytes fail.
- AC-HRV-04: Tests prove every decision has complete stage lineage.
- AC-HRV-05: Tests prove HP-2 creates no model execution or accepted state.
- AC-HRV-06: CLI tests prove exact JSON output and exit behavior.
- AC-HRV-07: A local PDF run proves one later alias resolves to its declaration.
- AC-HRV-08: The local run proves semantic references remain visible and unresolved.

## Reference Implementations

- Parent Preview contract: follow `packages/application/src/kotekomi_application/hybrid_mention_interpretation.py`.
- Parent Preview orchestration: follow `packages/application/src/kotekomi_application/hybrid_mention_preview.py`.
- Initialism behavior: follow `packages/application/src/kotekomi_application/organization_mention_qualification.py`.
- Stage traces: follow `packages/application/src/kotekomi_application/extraction_stage_trace.py`.
- Archive publication: follow `packages/adapters/src/kotekomi_adapters/local_archive.py`.
- CLI composition: follow `packages/pipelines/src/kotekomi_pipelines/cli.py`.

## Constraints and Halt Conditions

Stop when a unique alias requires a semantic guess about its expanded literal.

Stop when HP-2 requires Qwen2.5, ReFinED, or another model to publish a resolved decision.

Stop when a ReferenceDecision must become accepted Entity or Organization identity.

Stop when a source range cannot be reconstructed from the accepted representation.
