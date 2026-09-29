# TDD: Decontextualization Composition

- Status: Proposed
- Deliverable ID: `R4`
- Program: [Source-Grounded Attachment Deterministic-First Package](2026-09-24-source-grounded-attachment-deterministic-first-package.md)
- Parent: [Competitive Event Attachment Program](2026-09-18-competitive-event-attachment-program.md)
- Depends on: [R3-A Parser-Constituent Sub-Span Candidate Generation](2026-09-25-parser-constituent-sub-span-candidate-generation.md)
- Prior art: [Deterministic Trigger-Scope Split](2026-09-22-deterministic-trigger-scope-split.md), [Attributed-Statement Construction](2026-09-22-attributed-statement-construction.md), [Event Attribution Wiring Composition](2026-09-22-event-attribution-wiring-composition.md), [Source-Grounded Proposition Scope Experiment](2026-09-17-source-grounded-proposition-scope-experiment.md), [Second-opinion review 2](../2nd-opinion-2.md)

## 1. Context & Problem

Stages two and three of proposition composition fail.
Stage two attaches the exact source occurrences that complete one Event proposition.
Stage three assembles the ordered fragment set into one decontextualized proposition.
R1 replaced part of stage two with a model-free dependency-path router.
R2 corrected the Attachment Gold that later deliverables consume.
R3 and R3-A replaced boundary drawing with parser-constituent selection.
R3-A recorded one Selected Constituent Set per Event.
No deliverable assembles that set into a proposition.
The decontextualization criterion from the APS/PropSegmEnt line is missing.
The criterion restates only the fact centered on the marked Event words as one standalone sentence.
R4 implements that assembly deterministically.
R4 composes one content triple and one attribution from the Selected Constituent Set.
The composed result names the exact fields the already-shipped D1 and D4 wiring consume.

### Terms

**Selected Constituent Set** keeps the R3 meaning: the Parser Constituents one Constituent Selection names.
**Content triple** means one subject reference, one relation label, and one object reference or object value.
**Relation label** means the deterministic normalized Event predicate derived from the Event trigger token, reused as `proposed_event_label`.
**Subject role** means the core event constituent the dependency tree marks `nsubj` to the trigger head.
**Object role** means the core event constituent the dependency tree marks `obj`, `iobj`, or `obl` to the trigger head.
**Attribution** means the reporting carrier the Source credits with the Event content.
**Reporting carrier** keeps the D3 meaning: the governing source clause that names who delivered the reported content.
**Governed complement** keeps the D3 meaning: the subordinate content clause the reporting carrier reports.
**Decontextualization** keeps the package meaning: the restatement of one Event proposition as one standalone content triple plus attribution.
**Polarity** means `affirmed` or `negated`.
**Modality** means one of the domain modality values.
**Held-out partition** keeps the R1 meaning.

### Primary flow

1. The runner binds the frozen Proposition Gold, trigger Gold, connection Gold, Stanza runtime, and frozen R3-A inventories and selection answers by SHA-256.
2. The Application Layer rebuilds one Selected Constituent Set per Event from the frozen inventory and answer.
3. The Application Layer locates the trigger head token in the pinned dependency tree.
4. The Application Layer derives the relation label from the trigger token only.
5. The Application Layer assigns the subject role and the object role from the selected core event constituents.
6. The Application Layer classifies attribution with the D3 split.
7. The Application Layer detects polarity and modality from the selected fragments.
8. A rejected, empty, or incomplete selection produces a typed held result.
9. The runner writes one JSON result set, one report, and one Markdown review with zero model executions and zero canonical writes.

## 2. Goals

- An operator can read one composed content triple and attribution per Event.
- An operator can read one typed hold reason for each Event the composer cannot assemble.
- The composer is deterministic and model-free.
- The composed roles stay source-exact.
- The composer never fabricates a subject, object, or attribution target.
- The held-out partition stays reserved and unread.

## 3. Requirements

### Frozen input evidence

The runner binds the frozen inputs to these exact SHA-256 digests.

- Frozen Proposition Gold catalog `docs/hsq-source-grounded-proposition-gold-v1.json`: SHA-256 `f496ab64e6590de05b1bc07ef069335fae6a7094b009b2fae3ca02cc627e54b0`.
- Child Event-entity connection Gold `docs/hsq-event-entity-connection-gold-v2.json`: SHA-256 `afb3b25a421913b8d6b1c29eda90ee681d3bbf71719f7e0377a626bfc6067294`.
- Child Event-trigger Gold `docs/hsq-event-trigger-gold-v1.json`: SHA-256 `844eb564fb953e8d202f211469465f29f6de95dd811c033506f616cf425fe83f`.
- Pinned Stanza dependency runtime `packages/adapters/src/kotekomi_adapters/stanza-model-lock.json`: SHA-256 `4e66da09e0da1b3daef940ac8bec68d814b99d9fb10538e371548c9914d87bb3`.
- Frozen R3-A Constituent Candidate Inventory `data/r3-parser-constituent-runs/run-002/inventories.json`: SHA-256 `5579dedfaf02b9271e5046c446989e8f7907ba93a3315b88a15cc72aaa889c3f`.
- Frozen R3-A Constituent Selection Answers `data/r3-parser-constituent-runs/run-002/answers.jsonl` (one `{"event_id","raw_answer"}` record per line, the canonical raw model artifact): SHA-256 `b9d1834785ec3116b1f2057282296914460f638c07a37b20327c55ef895a15dc`.
- The held-out partition `docs/anthropic-dod-attachment-proposition-held-out-gold-v1.json` is reserved for R5 and is not read by R4.

- R4-EVD-01: The runner must bind every direct input by SHA-256.
- R4-EVD-02: The runner must rebuild each Selected Constituent Set from the frozen inventory and answer without a model execution.
- R4-EVD-03: The composer must stop when one selected constituent cannot materialize to exact source characters.

### Selection consumption

- R4-SEL-01: A rejected Constituent Selection produces a typed held result with no roles and no attribution.
- R4-SEL-02: A NONE Constituent Selection produces a typed held result with no roles and no attribution.
- R4-SEL-03: The Selected Constituent Set stays in source order.
- R4-SEL-04: Only spans named by the answer may enter the composition.

### Relation label

- R4-REL-01: The relation label derives from the Event trigger token only.
- R4-REL-02: The composer never reads a model answer to choose the relation label.
- R4-REL-03: A trigger head that resolves to no single dependency token produces a typed held result.

### Role assignment

- R4-ROL-01: The subject role is one selected core event constituent whose token span contains the trigger head `nsubj` dependent.
- R4-ROL-02: The object role is one selected core event constituent whose token span contains the trigger head `obj`, `iobj`, or `obl` dependent.
- R4-ROL-03: The object role may carry an object value instead of an entity reference when the object denotes a time, place, or quoted literal with no connection Gold entity.
- R4-ROL-04: The subject resolves to one connection Gold entity reference through an accepted source occurrence.
- R4-ROL-05: A subject role with no connection Gold entity reference produces a typed held result.
- R4-ROL-06: The composer never invents an entity reference or an object value.

### Attribution

- R4-ATR-01: The composer reuses `split_trigger_scope` to find one reporting carrier.
- R4-ATR-02: A complete split produces a targeted attribution naming the carrier reporter.
- R4-ATR-03: A split held with `reporting_predicate_missing` produces `source_narrator` attribution.
- R4-ATR-04: A split held with `trigger_head_unresolved` produces a `trigger_head_unresolved` held result.
- R4-ATR-05: A split held with `reporting_predicate_ambiguous` or `governed_complement_missing` produces an `attribution_ambiguous` held result.
- R4-ATR-06: The composer never fabricates an attribution target.

### Polarity and modality

- R4-POL-01: The composer records `negated` polarity when the selected fragments contain a `neg` dependent of the trigger head, and `affirmed` otherwise.
- R4-MOD-01: The composer records the modality present in the selected fragments, and `actual` when none is present.

### Evidence and safety

- R4-SAF-01: The runner must execute zero models.
- R4-SAF-02: The runner must create zero canonical Ledger writes.
- R4-SAF-03: The runner must create zero ProposedChanges.
- R4-SAF-04: The runner must record zero accepted state changes.
- R4-SAF-05: The held-out partition stays reserved and unread.

## 4. Proposed Architecture

```text
frozen Proposition Gold + trigger Gold + connection Gold
                      |
                      +--> frozen R3-A inventory x answer
                      |        -> Selected Constituent Set per Event
                      v
         pinned Stanza dependency tree
                      |
                      +--> trigger head token
                      |        -> relation label (deterministic)
                      v
         selected core event constituents
                      |
                      +--> subject role + object role + polarity + modality
                      |
                      +--> D3 split -> attribution target or source_narrator
                      v
         one DecontextualizedProposition per Event, or a typed hold
                      |
                      v
         JSON result set + report + Markdown review
```

## 5. Key Interactions

```text
Runner       -> frozen bindings          : verify SHA-256 digests
Application  -> frozen R3-A inventory    : rebuild Selected Constituent Set
Application  -> pinned dependency tree   : locate trigger head and role dependents
Application  -> connection Gold          : resolve subject and object entity references
Application  -> D3 split_trigger_scope   : classify attribution
Application  -> report                   : census of composed and held Events
```

## 6. Data Model

`DecontextualizationStatus` stores `proposition` or `held`.

`DecontextualizationHoldReason` stores one of `selection_rejected`, `selection_empty`, `trigger_head_unresolved`, `subject_unavailable`, `attribution_ambiguous`, or `source_offset_drift`.

`DecontextualizedRole` stores one role (`subject` or `object`), one exact selected fragment range, and one resolved entity reference or one object value.

`DecontextualizationAttributionKind` stores `targeted` or `source_narrator`.

`DecontextualizedAttribution` stores one attribution kind, one exact reporting carrier range, and one resolved reporter reference.

`DecontextualizedProposition` stores one Event ID, one source digest, one relation label, one subject role, one object role, one polarity, one modality, one attribution, and one status.

`DecontextualizationCensus` stores one partition role, the composed Event count, the held Event count, and the hold reason counts.

`DecontextualizationReport` stores both partition censuses, one semantic fingerprint, one model execution count, and one canonical write count.

These records are derived experimental evidence.

They do not change accepted Ledger state.

R4 emits no Domain Core record and no full `EventSemanticDraft`.

R4 names the content triple and attribution that the D1 and D4 wiring consume.

## 7. APIs / Interfaces

The composer accepts the frozen Gold catalogs, the frozen Selected Constituent Sets, the pinned dependency evidence, and the connection Gold entity references.

The composer returns one `DecontextualizedProposition` per Event and one `DecontextualizationReport`.

No record replaces a predecessor.

## 8. Behavior & Domain Rules

The relation label derives from the trigger token only, never from model output.

The subject and object roles come from selected core event constituents only.

The composer never invents a subject, object, or attribution target.

A rejected, empty, or incomplete selection holds and never fabricates a role.

The composed roles stay source-exact against the authoritative SourceSegment.

The composer emits derived evidence only and writes no canonical state.

The report records each Event `event_meaning` alongside the composed proposition for human review.
The report does not gate on exact string equality.

The held-out partition stays reserved and unread.

## 9. Acceptance Criteria

- AC-R4-EVD: Tests reject changed Proposition Gold, connection Gold, trigger Gold, Stanza, inventory, or answer digests.
- AC-R4-SEL-01: A rejected Constituent Selection produces a `held` result with `selection_rejected` and no roles.
- AC-R4-SEL-02: A NONE Constituent Selection produces a `held` result with `selection_empty` and no roles.
- AC-R4-REL-01: Tests prove the relation label equals the Event trigger predicate and never a model answer.
- AC-R4-ROL-01: For TGE-002 the subject role is `Anthropic CEO Dario Amodei` and resolves to the `EGE-001` actor reference.
- AC-R4-ROL-02: For TGE-002 the object role is `the artificial intelligence investment project Stargate` and carries an object value because Stargate is outside the Actor-and-Organization slice.
- AC-R4-ATR-01: For TGE-002 the attribution is `source_narrator` with no reporting carrier.
- AC-R4-ATR-02: For TGE-025 the attribution is `targeted` and names the `EGE-092` reporter `Sacks` for the Event `running`.
- AC-R4-POL-01: Tests prove a selected `neg` dependent records `negated` polarity, and `affirmed` otherwise.
- AC-R4-HOLD-01: Tests prove a missing subject role produces a `held` result with `subject_unavailable` and no fabricated subject.
- AC-R4-SAF-01: The report records zero model executions, zero canonical writes, and zero ProposedChanges.
- AC-R4-ALL: Focused formatting, lint, typecheck, and tests pass.

## 10. Reference Implementations

- Selected Constituent Set records: `packages/application/src/kotekomi_application/parser_constituent_candidate_generation.py`.
- Deterministic trigger-scope split: `packages/application/src/kotekomi_application/trigger_scope_split.py`.
- Content triple and attribution dispatch naming: `packages/application/src/kotekomi_application/attributed_statement_construction.py`.
- Content triple wiring input naming: `packages/application/src/kotekomi_application/event_attribution_wiring.py`.
- Predicate-argument core relations: `packages/application/src/kotekomi_application/event_entity_predicate_arguments.py`.
- Dependency token model: `packages/application/src/kotekomi_application/event_entity_connections.py`.
- Event trigger and relation label source: `packages/application/src/kotekomi_application/hybrid_event_triggers.py`.
- EventSemanticDraft `proposed_event_label` and `EventAttributionKind`: `packages/application/src/kotekomi_application/hybrid_event_semantics.py`.
- Runner pattern: `scripts/run_parser_constituent_candidate_generation.py`.

## 11. Constraints and Halt Conditions

- Stop when an input digest drifts from the frozen binding.
- Stop when a selected constituent cannot materialize to exact source characters.
- Stop when the relation label must come from model output.
- Stop when the composer must invent a subject, object, or attribution target.
- Stop when a selected role fragment must change authoritative source characters.
- Stop when a model call becomes necessary.
- Stop when the held-out partition is read to tune a decision.