# TDD: Parser-Constituent Candidate Generation

- Status: Proposed
- Deliverable ID: `R3`
- Program: [Source-Grounded Attachment Deterministic-First Package](2026-09-24-source-grounded-attachment-deterministic-first-package.md)
- Parent: [Competitive Event Attachment Program](2026-09-18-competitive-event-attachment-program.md)
- Depends on: [R2 Trigger-Containment Candidate Split and Gold Correction](2026-09-24-trigger-containment-candidate-split-and-gold-correction.md)
- Prior art: [Source-Grounded Proposition Scope Experiment](2026-09-17-source-grounded-proposition-scope-experiment.md)

## 1. Context & Problem

Stages two and three of proposition composition fail.
Stage two attaches the exact source occurrences that complete one Event proposition.
Stage three assembles the ordered fragment set into one decontextualized proposition.
The Competitive Event Attachment Program asked Qwen2.5-14B one semantic membership question per candidate.
The model also drew every candidate boundary.
The model boundary and the Gold boundary differ.
R1 replaced part of stage two with a model-free dependency-path router.
R2 corrected the Attachment Gold that later deliverables consume.
The boundary-drawing failure remains.
The second-opinion review recommends the fix.
The review says KoteKomi must stop letting the model choose span boundaries.
The review says KoteKomi must propose candidates from parser constituents and let the model only select among them.
R3 implements that separation.
R3 derives every candidate boundary from the parser, never from the model.
R3 asks the local model one finite selection over that candidate inventory.
R3 measures selection correctness separately from boundary fidelity.

### Terms

**Parser Constituent** means one clause-local, source-exact contiguous token group that the pinned Stanza dependency parse derives.
**Constituent Candidate Inventory** means the ordered set of Parser Constituents proposed for one Event in one SourceSegment.
**Constituent Selection** means one finite multi-label decision the local model returns over one Constituent Candidate Inventory.
**Selected Constituent Set** means the Parser Constituents one Constituent Selection names.
**Boundary Fidelity** means whether the Constituent Candidate Inventory covers every corrected Gold fragment by exact span.
**Constituent Pool Ceiling** means the exact-set Attachment Gold score the corrected Gold would reach if every Constituent Selection were perfect.
**Corrected Attachment Gold** means the Attachment Gold R2 produced and R3 and later deliverables consume.
**Attachment Candidate** means one exact source occurrence considered against one Event proposition.
**Gold Attachment Set** means the set of Events whose fragment list contains a candidate exact range.
**Event trigger** means one accepted expression range of one Event in the frozen trigger Gold.
**Held-out partition** means an authoritative Source Document that has never informed a Competitive Event Attachment decision.

### Primary flow

1. The runner binds the frozen Proposition Gold, trigger Gold, connection Gold, and Stanza runtime by SHA-256.
2. The runner re-derives the Corrected Attachment Gold with the R2 splitter.
3. The Application Layer derives one Constituent Candidate Inventory per Event from the pinned dependency tree.
4. The Application Layer measures Boundary Fidelity by comparing each corrected Gold fragment against the inventory.
5. The runner renders one finite selection task per Event; the task names every constituent by one stable label.
6. The local model returns one Constituent Selection per task; it never draws a span boundary.
7. The report scores each selection against the corrected Gold Attachment Set and records the census.

Boundary generation is model-free.
Only the selection step executes a model.
R3 creates derived evidence and changes no canonical state.

## 2. Goals

- An operator can read every Parser Constituent the parser proposed for one Event.
- An operator can read every corrected Gold fragment the inventory misses.
- An operator can read the Constituent Pool Ceiling on both partitions.
- An operator can read one Constituent Selection per Event and its exact selected spans.
- An operator can compare selection correctness with boundary fidelity.
- The held-out partition stays reserved and unread.

## 3. Requirements

### Partition roles and candidate inventory

- R3-PRT-01: The runner must reuse the frozen forty-Event development/validation split.
- R3-PRT-02: The inventory builder must derive one Constituent Candidate Inventory per Event.
- R3-PRT-03: The inventory builder must reject a source range that leaves its SourceSegment.
- R3-PRT-04: The runner must never tune a decision on the held-out partition.
- R3-PRT-05: The report must record each Event partition role.

### Frozen input evidence

The runner binds the frozen inputs to these exact SHA-256 digests.

- Frozen Proposition Gold catalog `docs/hsq-source-grounded-proposition-gold-v1.json`: SHA-256 `f496ab64e6590de05b1bc07ef069335fae6a7094b009b2fae3ca02cc627e54b0`.
- Child Event-Entity connection Gold `docs/hsq-event-entity-connection-gold-v2.json`: SHA-256 `afb3b25a421913b8d6b1c29eda90ee681d3bbf71719f7e0377a626bfc6067294`.
- Child Event-trigger Gold `docs/hsq-event-trigger-gold-v1.json`: SHA-256 `844eb564fb953e8d202f211469465f29f6de95dd811c033506f616cf425fe83f`.
- Pinned Stanza dependency runtime `packages/adapters/src/kotekomi_adapters/stanza-model-lock.json`: SHA-256 `4e66da09e0da1b3daef940ac8bec68d814b99d9fb10538e371548c9914d87bb3`.
- The held-out partition `docs/anthropic-dod-attachment-proposition-held-out-gold-v1.json` is reserved for R5 and is not read by R3.

- R3-EVD-01: The runner must bind every direct input by SHA-256.
- R3-EVD-02: The runner must re-derive the Corrected Attachment Gold byte-identically with the R2 splitter.
- R3-EVD-03: The inventory builder must stop when one constituent cannot be materialized to exact source characters.

### Parser constituent generation

- R3-CST-01: The inventory builder must derive every Parser Constituent from the pinned Stanza dependency tree.
- R3-CST-02: Every Parser Constituent must be source-exact.
- R3-CST-03: Every Parser Constituent must be a clause-local contiguous token group.
- R3-CST-04: The inventory must always include the exact Event expression.
- R3-CST-05: The inventory builder must not read the corrected Gold while deriving constituents.
- R3-CST-06: The inventory must never invent source characters.
- R3-CST-07: Equal inputs must produce a byte-identical Constituent Candidate Inventory.

### Boundary fidelity

- R3-FID-01: The report must classify each corrected Gold fragment as exactly covered or not.
- R3-FID-02: A Gold fragment is exactly covered when one constituent has the same exact span.
- R3-FID-03: The report must list every missed Gold fragment.
- R3-FID-04: The report must compute the Constituent Pool Ceiling per partition.

### Constituent selection task

- R3-SEL-01: The renderer must name every constituent by one stable label.
- R3-SEL-02: One selection task must contain one whole SourceSegment and its full inventory.
- R3-SEL-03: The renderer must reject a task whose Event literal repeats in the SourceSegment.
- R3-SEL-04: The model must return a finite answer only.
- R3-SEL-05: The model answer must be a subset of the named labels or the exact NONE token.
- R3-SEL-06: The parser must reject an answer that names a label outside the inventory.
- R3-SEL-07: The renderer must never send a candidate boundary to the model.

### Selection scoring

- R3-SCR-01: The report must map each Selected Constituent Set onto the corrected Gold Attachment Set.
- R3-SCR-02: The report must record selection correctness separately from boundary fidelity.
- R3-SCR-03: The report must record the selection census per partition.

### Evidence and safety

- R3-SAF-01: Model output must never enter accepted state.
- R3-SAF-02: The runner must create zero ProposedChanges.
- R3-SAF-03: The runner must create zero accepted Ledger writes.
- R3-SAF-04: The manifest must bind every input, output, policy, and TDD digest.

## 4. Proposed Architecture

```text
frozen Proposition Gold + trigger Gold + connection Gold
                      |
                      +--> re-derived Corrected Attachment Gold (R2 splitter)
                      |
                      v
         pinned Stanza dependency tree
                      |
                      +--> Parser Constituent per clause-local token group
                      |
                      v
         Constituent Candidate Inventory per Event
                      |
                      +--> Boundary Fidelity census (vs corrected Gold)
                      |
                      v
         finite selection tasks (one per Event, stable labels)
                      |
                      +--> local model Constituent Selection
                      |
                      v
         selection census + JSON report + Markdown review
```

## 5. Key Interactions

```text
Runner       -> R2 splitter           : re-derive Corrected Attachment Gold
Application  -> Stanza dependency tree : derive Parser Constituents
Application  -> Boundary Fidelity     : classify Gold fragments as covered or missed
Application  -> selection renderer    : name every constituent by one stable label
Runner       -> local model           : run one Constituent Selection per Event
Application  -> selection parser      : parse one finite subset or NONE
Application  -> report                : score selections vs corrected Gold
```

## 6. Data Model

`ParserConstituent` stores one constituent ID, one Event ID, one source digest, one exact range, and the dependencies that produced it.

`ConstituentCandidateInventory` stores one Event ID and the ordered Parser Constituent list.

`BoundaryFidelityCensus` stores one partition role, the covered and missed Gold fragment lists, and the Constituent Pool Ceiling.

`ConstituentSelectionTask` stores one Event ID, the rendered finite task, and the rendered input digest.

`ConstituentSelectionAnswer` stores one task ID, the selected constituent labels, and the parsed finite status.

`ConstituentSelectionReport` stores both partition censuses, the selection census, and one semantic fingerprint.

These records are derived experimental evidence.

They do not change accepted Ledger state.

## 7. APIs / Interfaces

The inventory builder accepts the frozen Proposition Gold catalog and the pinned Stanza dependency evidence.

The inventory builder returns one `ConstituentCandidateInventory` per Event and one `BoundaryFidelityCensus` per partition.

The selection renderer accepts one inventory and returns one `ConstituentSelectionTask` per Event.

The selection parser accepts one finite model answer and returns one `ConstituentSelectionAnswer`.

No record replaces a predecessor.

## 8. Behavior & Domain Rules

The parser, not the model, draws every candidate boundary.

The corrected Gold never enters constituent derivation.

A Gold fragment is covered only by an exact equal span.

The Constituent Pool Ceiling is a diagnostic bound, not a selection.

The model answers a finite subset over a fixed label set.

An invalid model answer produces rejection or quarantine, never accepted state.

The report maps selections onto the corrected Gold after the inventory exists.

The held-out partition stays reserved and unread.

## 9. Acceptance Criteria

- AC-R3-PRT-01: Tests reject an unknown partition role and reuse the frozen forty-Event split.
- AC-R3-CST-01: Tests prove every constituent derives from the pinned dependency tree.
- AC-R3-CST-02: Tests prove a constituent stays source-exact.
- AC-R3-CST-03: Tests prove a constituent is a clause-local contiguous token group.
- AC-R3-CST-04: Tests prove the Event expression is always proposed.
- AC-R3-CST-05: Tests prove the inventory builder reads no Gold.
- AC-R3-CST-06: Tests prove the inventory invents no source characters.
- AC-R3-CST-07: Tests prove equal inputs produce a byte-identical inventory.
- AC-R3-FID-01: Tests prove each corrected Gold fragment classifies covered or missed.
- AC-R3-FID-02: Tests prove a Gold fragment is covered only by an exact equal span.
- AC-R3-FID-03: Tests prove the report lists every missed Gold fragment.
- AC-R3-FID-04: Tests prove the Constituent Pool Ceiling recomputes.
- AC-R3-SEL-01: Tests prove constituent labels are stable across renderings.
- AC-R3-SEL-03: Tests prove a repeated Event literal is rejected.
- AC-R3-SEL-04: Tests prove the parser accepts only a finite answer.
- AC-R3-SEL-05: Tests prove the answer is a subset of the labels or the exact NONE token.
- AC-R3-SEL-06: Tests prove an out-of-inventory label is rejected.
- AC-R3-SEL-07: Tests prove no boundary byte reaches a selection task.
- AC-R3-EVD-01: Tests reject changed Gold, source, or Stanza digests.
- AC-R3-EVD-02: Tests prove the corrected Gold re-derives byte-identically with the R2 splitter.
- AC-R3-SCR-01: Tests prove a Selected Constituent Set maps onto the corrected Gold Attachment Set.
- AC-R3-WRITE: The report records zero canonical writes and zero ProposedChanges.
- AC-R3-ALL: Focused formatting, lint, typecheck, and tests pass.

## 10. Reference Implementations

- Constituent derivation: `packages/application/src/kotekomi_application/source_grounded_proposition_scope.py` (`_clause_local_constituents`).
- Stanza binding: `packages/adapters/src/kotekomi_adapters/stanza_linguistic_analysis.py`.
- Corrected Gold and span-derived candidate ID: `packages/application/src/kotekomi_application/trigger_containment_candidate_split.py`.
- Finite answer format: `packages/application/src/kotekomi_application/competitive_attachment_finite_answer_format.py`.
- Local model swap: `packages/application/src/kotekomi_application/competitive_attachment_local_model_swap.py`.
- LM Studio runtime: `packages/adapters/src/kotekomi_adapters/lm_studio_model_runtime.py`.
- Stage-local catalogs: `packages/pipelines/src/kotekomi_pipelines/source_grounded_proposition_stage_local.py`, `packages/pipelines/src/kotekomi_pipelines/event_trigger_stage_local.py`.
- R2 runner pattern: `scripts/run_trigger_containment_candidate_split.py`.

## 11. Constraints and Halt Conditions

- Stop when one constituent cannot be materialized to exact source characters.
- Stop when the builder must invent source characters.
- Stop when the corrected Gold re-derivation diverges from the R2 splitter.
- Stop when the selection renderer must send a candidate boundary to the model.
- Stop when model output would become accepted state.
- Stop when the held-out partition is read to tune a decision.