# TDD: Event-Entity Connection Experiment

- Status: Accepted; implementation in progress
- Parent: [Source-Grounded Event Boundary](2026-09-12-source-grounded-event-boundary.md)
- Program: [Hybrid Semantic Quality Program](2026-09-06-hybrid-semantic-quality-program.md)
- Gold: `hsq-event-entity-connection-gold-v2.json`
- Second-opinion handoff:
  [Event-Entity Connection Second-Opinion Handoff](2026-09-16-event-entity-connection-second-opinion-handoff.md)

## 1. Context & Problem

KoteKomi now creates one source-grounded Event for each approved Event trigger.

The base Event contains no Actor or Organization connections.

The former role task requires a governed frame before it selects an entity.

That requirement drops source-grounded Events that lack a governed classification.

The former task also asks Qwen to interpret a frame, select a role, and select source text.

This TDD tests one smaller semantic question before KoteKomi adopts a production contract.

**Event-Entity Connection Candidate** means one KoteKomi-owned pair of one Event and one entity.

**Entity Involvement Judgment** means one `Y`, `N`, or `U` answer about that pair.

**Event-Entity Connection Draft** means one derived source-backed positive connection.

**Connection Gold** means the complete reviewed entity inventory for selected Events.

**Contextual Exclusion** means an exact source expression that must not become an Actor or
Organization candidate for the selected Event because it denotes another contextual kind.

**Reviewed Expected Gap** means one exact occurrence whose authoritative source meaning permits more
than one antecedent after review.

A disagreement between processors is diagnostic evidence, not source ambiguity.

An entity is involved when the Event expression makes that entity part of what happened.

This meaning includes an entity whose approach, statement, work, or decision is involved.

It does not assert a semantic role for the entity.

### Primary Flow

1. The Pipeline loads reviewed source-grounded Events and their upstream extraction evidence.
2. KoteKomi constructs Event-Entity Connection Candidates from effective entity mentions and
   source-aligned specialist grounding evidence.
3. KoteKomi proves that every reviewed Gold entity is available, every reviewed expected gap is
   present, and no unexpected typed candidate gap remains.
4. KoteKomi maps the pinned linguistic-analysis trace back to authoritative SourceSegment
   characters and routes candidates from a different linguistic sentence to `not_connected`.
5. KoteKomi supplies Qwen with one ordered inventory containing every remaining same-sentence
   Event-Entity Connection Candidate for the Event.
6. Qwen returns one fixed-length `Y` / `N` / `U` vector in that exact order.
7. KoteKomi maps each vector position back to the exact occurrence candidate and creates a typed
   disposition.
8. KoteKomi constructs Event-Entity Connection Drafts for `Y` answers.
9. The evaluator compares the complete result with Connection Gold.

This flow writes derived experiment evidence only.

## 2. Goals

- An operator can inspect every entity considered for one Event.
- An operator can inspect the exact input and output for every model judgment.
- The experiment preserves source-grounded entity involvement without governed frames.
- The development and validation sets reproduce their complete reviewed inventories.
- Deterministic task allocation reduces model work without reducing reviewed Gold availability.
- The experiment identifies a production contract without changing accepted Ledger state.

## 3. Requirements

### Candidate Construction

- EEC-C01: KoteKomi consumes approved source-grounded Events.
- EEC-C02: KoteKomi consumes existing MentionCandidates, ReferenceDecisions, and HP-3
  EntityLinkEvidence.
- EEC-C03: KoteKomi selects only effective Actor and Organization MentionCandidates.
- EEC-C04: An exact expression that identifies a person remains an Actor when that person acts in a
  governmental or institutional capacity.
- EEC-C04A: An administration, government, department, or other exact expression becomes an
  Organization candidate only when that expression denotes a collective Agent with continuing
  purpose beyond its current members.
- EEC-C04B: A role-qualified plural human expression such as `Trump officials`, `Biden officials`,
  or `Anthropic representatives` becomes a source-bound Actor candidate when an exact named Actor
  or Organization occurrence is immediately followed by the governed plural human-role head.
- EEC-C04C: KoteKomi does not merge a source-bound Actor group with a named person or associated
  Organization without separate identity evidence.
- EEC-C04D: A source-bound Actor-group identity includes its SourceSegment and exact occurrence so
  equal role phrases in separate contexts do not merge by normalized text alone.
- EEC-C04E: A named institutional program may denote an Organization when evidence identifies a
  persistent collective Agent that can act collectively; the word `Program` alone is insufficient.
- EEC-C05: KoteKomi resolves one candidate through one resolved ReferenceDecision.
- EEC-C06: KoteKomi preserves the source mention and resolved antecedent evidence.
- EEC-C07: KoteKomi creates one candidate for each distinct EventMention and exact entity mention
  occurrence.
- EEC-C08: Two source occurrences that may identify the same entity remain distinct candidates until
  their Event-involvement decisions are complete.
- EEC-C08A: Identity-level consolidation happens deterministically after occurrence-level decisions
  and preserves every positive, negative, and unresolved occurrence decision.
- EEC-C09: KoteKomi validates every range against authoritative SourceSegment characters.
- EEC-C10: An ambiguous entity type produces a typed candidate gap.
- EEC-C11: An ambiguous or unresolved reference produces a typed candidate gap.
- EEC-C12: An exact expression used as an Event does not become an Actor or Organization merely
  because the same name can identify an Organization elsewhere.
- EEC-C13: Effective source-valid mention observations from independent proposers accumulate
  monotonically into the candidate inventory.
- EEC-C14: A miss, abstention, or failure from one proposer cannot erase a source-valid observation
  from another proposer.
- EEC-C15: Nested and overlapping source-valid mention occurrences remain available until
  occurrence-level Event assignment decides their relevance.
- EEC-C16: Deterministic phrase-boundary expansion may propose an exact source occurrence, but it
  cannot create accepted Ledger state or infer an identity by itself.
- EEC-C17: Reference status is evaluated before mention interpretation so an ambiguous or unresolved
  reference receives its truthful gap reason.
- EEC-C18: One upstream mention or reference defect creates one segment-level gap and affects an
  Event only through an explicit Event-gap dependency.
- EEC-C19: ReFinED coarse `PER` evidence may reinforce Actor denotation and coarse `ORG` evidence may
  reinforce Organization denotation, while ranked external identities remain advisory.
- EEC-C20: Once one selected, typed exact name occurrence exists, deterministic token-boundary
  recurrence may add other exact occurrences of that same name in the SourceSegment.
- EEC-C21: Canonical entity names collapse PDF whitespace while their source spans preserve exact
  authoritative characters.
- EEC-C22: A source occurrence remains a typed gap when its authoritative wording permits multiple
  antecedents after bounded semantic review.
- EEC-C22A: Processor disagreement remains visible in reference evidence but cannot lower a clear
  Gold antecedent to an expected gap.
- EEC-C23: A source-valid exact GLiNER person or Organization observation remains eligible when a
  fallible boundary adjudication selects an overlapping alternative.
- EEC-C24: A ReFinED coarse type reinforces only source-aligned mention evidence and a compatible
  contextual kind; it cannot turn an explicitly Event-denoting occurrence into an Organization or
  override explicit Organization usage with a coarse person label.
- EEC-C25: A specific named publication may denote an Organization only when exact mention evidence
  is reinforced by source-aligned ReFinED coarse `ORG` evidence.
- EEC-C26: One resolved reference may inherit an Actor or Organization denotation only from one
  uniquely typed, source-backed antecedent name in the same upstream evidence bundle.
- EEC-C27: An Event depends on a typed mention gap only when its exact expression overlaps the gap,
  immediately follows its possessive marker, or immediately precedes its reference marker.
- EEC-C28: A deterministic source-bound Actor-group occurrence replaces a conflicting same-range
  candidate while preserving the named Actor evidence from which the group was derived.
- EEC-C29: A top-ranked exact-title external identity whose pinned class closure includes Wikidata
  `Q43229` may reinforce Organization denotation when the contextual interpretation is compatible
  and no strong person evidence conflicts.
- EEC-C30: The Application Layer owns the explicit external-class mapping. The ReFinED Adapter
  preserves raw classes and cannot decide KoteKomi ontology meaning.
- EEC-C31: Exact-title external Organization evidence may reinforce an identity whose contextual
  use is `project`, `initiative`, `policy`, or `publication`; it cannot override explicit person,
  place, Event, or product usage.
- EEC-C32: A source-exact named-symbol boundary such as `FedRAMP` remains effective when nested in a
  broader proposal such as `FedRAMP authorization`. This deterministic boundary decision supplies
  no ontology kind or identity; ordinary interpretation and grounding must still establish those
  meanings with inspectable evidence.

### Task Allocation

- EEC-A01: KoteKomi consumes the existing pinned `linguistic_analysis` trace used by Event-trigger
  extraction; it does not rerun the linguistic specialist for this boundary.
- EEC-A02: KoteKomi validates the trace producer, model version, resource identity, SourceSegment
  identity, SourceCopy digest, and every token range before routing a candidate.
- EEC-A03: KoteKomi maps SourceCopy token ranges back to exact authoritative SourceSegment
  characters before assigning linguistic sentence identities.
- EEC-A04: An entity occurrence in a different linguistic sentence from the exact Event expression
  is deterministically routed to `not_connected`.
- EEC-A05: Every same-sentence occurrence remains routed to one bounded semantic judgment,
  including nested and overlapping occurrences.
- EEC-A06: Span containment alone is not evidence that the contained entity is unrelated. A broad
  or malformed probabilistic candidate therefore cannot deterministically suppress valid source
  occurrences nested inside it.
- EEC-A07: A deterministic route creates a typed route and connection decision but no ModelRun,
  ExtractionTask, model trace, or connection draft.
- EEC-A08: A model route identifies the exact candidate and linguistic evidence that justified
  invoking Qwen.
- EEC-A09: Preflight fails before model execution when every occurrence matching a reviewed Gold
  entity would be deterministically rejected.
- EEC-A10: All model-routed candidates for one Event form one contrastive inventory and require at
  most one ModelRun.

### Model Judgment

- EEC-M01: Qwen receives one exact EventMention and the complete ordered inventory of model-routed
  exact entity mention occurrences for that Event per invocation.
- EEC-M02: Qwen receives the complete authoritative SourceSegment.
- EEC-M03: For each ordered candidate, KoteKomi supplies a source copy that marks the same exact
  Event expression occurrence inline with `<event>` tags.
- EEC-M04: Each candidate source copy marks only that candidate's exact entity occurrence inline
  with `<entity>` tags.
- EEC-M05: Qwen receives the resolved antecedent name for a resolved reference in that candidate's
  inventory entry.
- EEC-M06: The model-visible input contains no KoteKomi identifier or source offset.
- EEC-M07: Qwen returns exactly one `Y`, `N`, or `U` character per candidate, in supplied order,
  with no separators or additional text.
- EEC-M08: `Y` means the entity forms part of the Event meaning.
- EEC-M08A: Event involvement includes performing, experiencing, causing, receiving, owning,
  supplying, targeting, or participating in the marked Event.
- EEC-M08B: Event involvement includes an explicitly named entity whose action, decision,
  statement, policy, order, work, property, or relationship is the marked Event's subject or object.
- EEC-M08C: An entity explicitly named in the content of a reporting, statement, or judgment Event
  forms part of what that Event says happened.
- EEC-M08D: A person's name nested only inside a participating group or Organization expression does
  not make the person individually involved.
- EEC-M08E: The explicitly named source of an attributed statement forms part of an Event that
  represents the attributed content.
- EEC-M08F: An explicitly named Organization in a source-grounded qualification of the Event's
  object forms part of the Event meaning without becoming the Event's performer.
- EEC-M09: `N` means the SourceSegment excludes the entity from that Event meaning.
- EEC-M10: `U` means the SourceSegment does not decide the question.
- EEC-M11: KoteKomi rejects malformed, additional, or wrong-length model output.
- EEC-M12: One failed contrastive execution leaves its complete model-routed inventory unresolved;
  deterministic route decisions remain valid.
- EEC-M13: Two equal entity strings at different source ranges produce distinct ordered candidate
  copies within the same model input.
- EEC-M14: KoteKomi supports an entity occurrence nested wholly inside an Event expression while
  rejecting crossing target ranges and an Event expression whose occurrence is not unique.
- EEC-M15: Qwen never returns source offsets, internal identifiers, records, or JSON; KoteKomi owns
  the ordered-position mapping and every resulting record.

### Deterministic Reconciliation

- EEC-R01: KoteKomi maps `Y` to `connected`.
- EEC-R02: KoteKomi maps `N` to `not_connected`.
- EEC-R03: KoteKomi maps `U` to `unresolved`.
- EEC-R04: KoteKomi creates an Event-Entity Connection Draft only for `connected`.
- EEC-R05: Each draft identifies its Event, entity identity hypothesis, and exact positive mention
  occurrence.
- EEC-R06: Each draft identifies the supporting mention and optional reference records for that
  occurrence without coalescing sibling occurrences.
- EEC-R07: Each draft identifies the exact Event EvidenceTargets and exact entity source spans.
- EEC-R08: Each draft identifies its ModelRun and ExtractionStageTrace.
- EEC-R09: A draft contains no frame, frame role, or UpperRole.
- EEC-R10: Reconciliation derives every identifier and EvidenceTarget deterministically.
- EEC-R11: An identity-level Event connection is a deterministic projection over preserved
  occurrence-level decisions.

### Experiment Evidence

- EEC-E01: Connection Gold references the approved Event Trigger Gold digest.
- EEC-E02: Connection Gold contains twenty development Events.
- EEC-E03: Connection Gold contains twenty validation Events.
- EEC-E04: Each Gold Event records its complete expected Actor and Organization inventory.
- EEC-E04A: Every accepted source expression exists byte-for-byte in the selected Event's exact
  authoritative SourceSegment; normalized names and aliases belong only in the accepted entity-name
  inventory.
- EEC-E04B: Every accepted source occurrence is identified by exact start, end, and source text so
  repeated equal literals cannot satisfy one another.
- EEC-E04C: A Connection Gold Event meaning must equal its bound Trigger Gold meaning so a
  downstream catalog cannot drop reporting or attribution context.
- EEC-E05: Gold can record an exact source expression as a contextual exclusion with its observed
  non-Actor/Organization kind and rationale.
- EEC-E05A: Preflight and final evaluation fail when an Actor or Organization candidate uses a
  contextually excluded expression.
- EEC-E05B: Every other eligible same-segment Actor or Organization is an implicit negative for the
  selected Event.
- EEC-E05C: Gold may record one exact expected candidate gap with source range, reason, and human
  rationale only when the authoritative source itself remains genuinely ambiguous.
- EEC-E05D: A reviewed expected gap is matched one-to-one by exact range, exact source text, and gap
  reason; a missing expected gap or any unexpected gap fails the preflight.
- EEC-E06: A human approves Connection Gold before any scored model replay.
- EEC-E06A: Preparation compares every expected Gold entity with the candidates supplied by
  immutable upstream evidence.
- EEC-E06B: A missing expected candidate, missing reviewed gap, or unexpected typed candidate gap
  produces `upstream_blocked` before Qwen runs.
- EEC-E06C: The preflight report preserves the exact SourceSegment, expected entities, actual
  candidate inventory, and typed gaps.
- EEC-E07: The evaluator matches expected and actual entities one-to-one.
- EEC-E08: The report counts missing, extra, wrong, and unresolved connections.
- EEC-E09: Each execution record preserves the ordered candidates, exact input, raw answer vector,
  parsed vector, and deterministic candidate-to-disposition mapping.
- EEC-E10: Three development repetitions produce identical results.
- EEC-E11: The validation run uses one frozen prompt, policy, and runtime configuration.
- EEC-E12: Validation results cannot change the approved Gold or frozen policy.
- EEC-E13: The evaluator writes no ProposedChange or accepted Ledger record.

## 4. Proposed Architecture

```text
source-grounded Event + EventMention
                 |
MentionCandidates + ReferenceDecisions + EntityLinkEvidence
                 |
                 v
   deterministic candidate builder
                 |
                 v
 ordered same-Event candidate inventory
                 |
                 v
 pinned linguistic trace +
 deterministic route decision
          /             \
 different sentence   same sentence
       |                    |
 deterministic N      one contrastive Qwen vector
          \             /
                 v
 deterministic position mapper + reconciler
                 |
                 v
 Event-Entity Connection Draft + trace
```

The Application Layer owns candidate construction and reconciliation.

The ModelRuntime Port supplies one bounded semantic vector per Event.

The Pipeline owns stage-local composition and Gold evaluation.

## 5. Key Interactions

```text
Pipeline       Application       Qwen       Evaluator
   |                |              |             |
   |-- evidence --->|              |             |
   |                |-- inventory >|             |
   |                |<-- YNU... ---|             |
   |                |-- map + reconcile          |
   |<-- drafts -----|              |             |
   |-------------------------------------------> Gold
   |<----------------------------------------- report
```

## 6. Data Model

`EventEntityConnectionCandidate` stores one Event and entity pair with source lineage.

`EventEntityDenotationDecision` stores the exact evidence and rule that classified one source
occurrence as an Actor or Organization.

`EventEntityGapDependency` stores why one unresolved source occurrence affects one exact Event and
prevents a segment-wide gap from being copied to unrelated Events.

`ConnectionGoldExpectedGap` stores the human-reviewed exact range, expected reason, and rationale
for one deliberately unresolved upstream occurrence.

`EventEntityLinguisticEvidence` maps one pinned linguistic-analysis trace to exact authoritative
SourceSegment ranges.

`EventEntityCandidateRoute` records why KoteKomi or Qwen owns one candidate decision.

`EntityInvolvementJudgment` stores one candidate-position answer and the shared contrastive model
execution lineage.

`EventEntityConnectionDecision` stores one deterministic terminal disposition.

`EventEntityConnectionDraft` stores one positive source-backed connection.

`EventEntityIdentityConnection` is a deterministic projection over all occurrence-level decisions
for one Event and entity identity; it never erases negative or unresolved occurrences.

`EventEntityConnectionPreview` stores complete derived stage evidence.

These records remain derived experiment evidence in the Archive.

## 7. APIs / Interfaces

The stage-local runner provides `prepare`, `run`, `finalize`, and `compare` commands.

`prepare` validates manifest-authorized upstream Event, mention, and reference evidence.

It writes a candidate preflight and returns `gold_review_required`, `upstream_blocked`, or
`prepared` without invoking Qwen.

`run` writes one result for each selected source-grounded Event.

`finalize` validates complete execution evidence and writes the Gold report.

`compare` joins development and validation reports without changing either run.

## 8. Behavior & Domain Rules

- EEC-B01: The experiment does not populate Event participant fields.
- EEC-B02: The experiment does not create a Relationship or Assertion.
- EEC-B03: The exact Event expression preserves source phenomenology.
- EEC-B04: An Event-Entity Connection Draft expresses involvement, not a semantic role.
- EEC-B05: The former governed role route remains an optional comparison baseline.
- EEC-B06: A validation failure leaves the production contract unproven.
- EEC-B07: Validation evidence cannot become new development evidence in this TDD.
- EEC-B08: Institutional-capacity enrichment is outside this experiment and cannot change entity
  identity or Event involvement.
- EEC-B09: A Qwen involvement judgment cannot replace the entity kind established by validated
  source evidence.
- EEC-B10: No proposer observation or Event-Entity Connection Draft becomes accepted Ledger state in
  this experiment.

## 9. Acceptance Criteria

- AC-EEC-C01: Tests prove candidate ranges replay exact authoritative characters.
- AC-EEC-C02: Tests prove occurrence-level candidates remain distinct and identity-level
  consolidation preserves every occurrence decision.
- AC-EEC-C03: Tests prove genuine source ambiguity produces a typed gap.
- AC-EEC-C04: Tests prove named people remain Actors, named administrations remain Organizations,
  and source-bound official groups remain Actors.
- AC-EEC-C04A: Tests prove an Event-denoting expression is explicitly absent from Actor and
  Organization candidates.
- AC-EEC-C05: Tests prove independent source-valid proposer observations accumulate without a
  proposer veto.
- AC-EEC-C06: Tests prove repeated, nested, and overlapping mentions remain occurrence-addressable
  through Event assignment.
- AC-EEC-C07: Tests prove one ambiguous reference is recorded once and does not block unrelated
  Events in the same SourceSegment.
- AC-EEC-C08: Tests prove ReFinED coarse Organization evidence can rescue a named Organization that
  Qwen contextually described as an initiative without accepting ReFinED's ranked identity.
- AC-EEC-C09: Tests prove exact-name recurrence can supply a missed later source occurrence and that
  normalized entity names do not alter exact source spans.
- AC-EEC-C10: Tests prove processor disagreement cannot satisfy an expected source-ambiguity gap.
- AC-EEC-C10A: Tests prove a reviewed source ambiguity remains visible without blocking unrelated
  evidence, while an unreviewed ambiguity blocks model execution.
- AC-EEC-C11: Tests prove a source-valid exact specialist person occurrence survives an overlapping
  boundary-model choice.
- AC-EEC-C12: Tests prove explicit Event usage blocks a coarse Organization rescue while a specific
  publication reinforced by coarse `ORG` evidence remains available as an Organization.
- AC-EEC-C13: Tests prove one resolved reference inherits a unique source-backed antecedent kind
  without requiring a second mention-interpretation result.
- AC-EEC-C14: Tests prove a reference gap affects only an overlapping or immediately adjacent Event
  expression and does not spread through a semicolon-delimited clause.
- AC-EEC-C15: Tests prove a source-bound official group replaces a conflicting same-range
  Organization occurrence and remains distinct from its named Actor evidence.
- AC-EEC-A01: Tests prove linguistic trace mapping validates pinned specialist identity and maps
  SourceCopy token ranges to exact authoritative SourceSegment characters.
- AC-EEC-A02: Tests prove a different-sentence candidate produces `not_connected` without creating
  a model execution or draft.
- AC-EEC-A03: Tests prove nested and overlapping same-sentence candidates remain model-routable.
- AC-EEC-A04: Development and held-out preflight each preserve every reviewed Gold entity after
  deterministic routing.
- AC-EEC-M01: Fake-Port tests prove each Event produces at most one invocation containing its
  complete ordered model-routed candidate inventory.
- AC-EEC-M02: Parser tests accept only a non-empty `Y` / `N` / `U` vector whose length equals the
  supplied candidate count.
- AC-EEC-M03: Tests prove repeated entity strings receive occurrence-distinct ordered candidate
  copies without exposing offsets or internal identifiers.
- AC-EEC-M04: Tests prove nested Event/entity markers preserve exact source characters and repeated
  Event text fails before model execution when no exact occurrence is addressable.
- AC-EEC-M05: Tests prove malformed or wrong-length vectors leave every model-routed candidate
  unresolved while preserving deterministic decisions.
- AC-EEC-R01: Tests prove only `Y` creates an Event-Entity Connection Draft.
- AC-EEC-R02: Tests prove every draft has complete source and execution lineage.
- AC-EEC-E01: Catalog tests prove Connection Gold contains twenty Events per phase.
- AC-EEC-E01A: Tests prove preflight attributes a missing expected entity to upstream evidence.
- AC-EEC-E01B: The runner cannot invoke Qwen before Gold approval and a passing preflight.
- AC-EEC-E01C: Catalog loading fails when any accepted source expression is absent from its exact
  SourceSegment.
- AC-EEC-E02: Development and validation reports contain no missing or extra connections.
- AC-EEC-E03: Development and validation reports contain no wrong connections.
- AC-EEC-E04: Development and validation reports contain no unresolved connections.
- AC-EEC-E05: Three development repetitions have identical content fingerprints.
- AC-EEC-E06: Tests prove the evaluator writes no canonical state.

### Implementation State

The Application contracts, bounded model task, deterministic reconciliation, stage-local evaluator,
and experiment runner are implemented.

A refreshed read-only preparation replay against canonical coverage report
`hdc_531970a43dc9a886c345846b` found all twenty development Events.

That preparation retained 99 upstream mention instances, constructed 84 distinct Event-entity
candidates, and preserved five typed candidate gaps without rerunning mention, reference, or Event
extraction.

A deterministic pre-model comparison against the proposed Gold initially found thirteen expected
development entities that upstream evidence could not supply.

Human review established that the World Economic Forum denotes its gathering in the reviewed
attendance context rather than the Organization.

Review also added Joe Biden to the two Events involving his Executive Order while preserving him as
an implicit negative for the separate discussions Event.

Human review later rejected TGE-020 as a standalone source-grounded Event because the source embeds
attendance under TGE-019's decision without establishing that attendance occurred or will occur.
The experiment removed TGE-020 and replaced it with approved source-grounded Event TGE-054 to retain
the twenty-Event development partition.
Human review approved TGE-054's three-Organization inventory.
TGE-019 now includes Trump because his inauguration is the stated alternative in Amodei's decision.
Human review approved the changed TGE-019 inventory.

Human review also rejected TGE-010 as a standalone source-grounded Event.
The phrase `ahead of the 2024 presidential election` supplies anticipated temporal context without
establishing that the election occurred.
The experiment removed TGE-010 and selected approved source-grounded Event TGE-060 to retain the
twenty-Event validation partition.
Human review approved TGE-060's Anthropic inventory.

The last preflight before the exact TGE-019 expression correction evaluated 42 expected entities,
found 32 available, and preserved both contextual exclusions without a violation. It left ten
provisional missing entities plus five typed candidate gaps. All three TGE-054 entities were
available.

The exact TGE-019 correction changed its source-grounded Event identity. A newer completed canonical
ingestion contains the corrected source-grounded Event and allowed a fresh deterministic preflight
without invoking Qwen.

Human review established that named people remain Actors when acting in governmental capacity,
named administrations remain Organizations, and role-qualified plural groups such as `Trump
officials` and `Biden officials` remain source-bound Actor candidates. Institutional-capacity
enrichment is deferred until it can add independently supported context without replacing identity.

The first post-review preflight retained 119 occurrence-level candidates.

It improved the prior ten missing entities and five copied gaps to four missing entities and one
scoped processor disagreement.

The remaining deterministic causes were a missed later `Trump` occurrence, canonical-name
whitespace, unused ReFinED coarse Organization evidence for `Open Philanthropy`, and the unresolved
`his` reference in TGE-022.

The candidate builder now uses exact-name recurrence, canonical-name whitespace normalization, and
retained HP-3 coarse mention types. This intentionally changed disposable HP-3 evidence, so old
derived Previews were not upgraded or silently repaired.

An exact-source audit found twenty-six accepted source expressions across nineteen Events that were
normalized aliases, expanded names, possessive variants, or normalized PDF whitespace rather than
literal substrings of their authoritative SourceSegments. The Gold catalog and its human review copy
now preserve literal source occurrences separately from normalized identity aliases. Catalog loading
enforces exact start, end, and source characters; normalized names remain separately in
`accepted_entity_names`.

Focused contract tests pass.

Human review approved the then-current semantic inventories for all forty Connection Gold Events on
September 13, 2026.

Human review on September 15 found that TGE-021 incorrectly promoted an embedded inauguration
mention into the unsupported claim that the inauguration occurred. Source-Grounded Event Gold now
rejects TGE-021. Connection Gold removes it and adds already approved development Event TGE-055,
`Palantir and Amazon Web Services offered services with FedRAMP authorization`, to preserve the
20/20 partition. TGE-055 expects Palantir and Amazon Web Services as offerers and FedRAMP as the
institutional authorization program qualifying the services. FedRAMP is not an offerer, and
Anthropic remains an implicit negative because it participates in the neighboring partnership Event
rather than the relative-clause services Event. The replacement inventory and exact occurrence
bindings were subsequently approved in the focused September 16 review.

A bounded review of the remaining `his` occurrence found that F-Coref selects Trump.

Qwen explicitly rejects Trump and then selects Amodei from the complete source-valid catalog.

Human review determined that `his hiring of Biden officials` clearly refers to Amodei.

Connection Gold therefore requires both the explicit `Amodei` occurrence and the resolved `his`
occurrence for TGE-022.

The former `EGG-001` exception was invalid because it encoded processor disagreement as source
ambiguity.

The v11 semantic-reference policy removes a rejected specialist candidate's veto after one unique
contrastive selection while retaining every execution record.

A fresh canonical ingestion produced coverage report `hdc_2bc1f339a55f4bd259bfc1f1`.
Its first preflight exposed four remaining deterministic boundary defects: a same-range Organization
candidate displaced `Trump officials`; coarse specialist types overrode explicit contextual usage;
resolved references still required redundant mention interpretations; and semicolon-clause gap
propagation copied one reference defect onto unrelated Events. Exact GLiNER spans for `JD Vance` and
`The New York Times` also showed that valid specialist evidence was being discarded by fallible
boundary or contextual decisions.

The earlier deterministic replay invoked no model and passed both then-current partitions.

It made all 44 development entities and all 41 validation entities available while treating
`EGG-001` as expected.

The corrected Gold removes every expected candidate gap.

Against immutable v10 upstream evidence, development preflight blocked truthfully on the one
unexpected TGE-022 reference gap while validation preflight passed.

A focused live v11 reference replay on September 15 resolved exact source occurrence `100:103`,
`his`, to exact antecedent `13:19`, `Amodei`. F-Coref's proposed `Trump` antecedent remained in the
trace, Qwen explicitly rejected it, and Qwen's contrastive task selected Amodei. The terminal
ReferenceDecision is `resolved` with reason `unique_semantic_antecedent`; the replay passed its one
case with no failed stage and no accepted Ledger change. This evidence removes the former EGG-001
source-ambiguity claim. A fresh complete Connection Gold preflight still must consume the corrected
reference evidence before the scored connection replay can begin.

The first complete development model replay preserved 176 exact input/output records and took
114,610 model milliseconds. It matched 30 of 44 expected entities but produced fourteen false
negatives, fourteen extra connections, and twenty-five unresolved occurrences. Inspection showed
that repeated entity strings received byte-identical model tasks and that a bare Event expression was
not marked within its clause. The persisted run remains the v1 experimental baseline.

The v2 task gave Qwen one deterministically marked source passage. Equal names at different
occurrences received different input, nested names remained source-exact, and the prompt exposed no
KoteKomi IDs or offsets. Its first fresh development replay matched 38 of 44 expected identities and
eliminated all 25 prior unresolved judgments, but produced 37 extra occurrence-level connections in
186,972 model milliseconds. Inspection showed a strong `Y` bias: the broad involvement rules caused
affiliations and entities from neighboring, embedded, or containing Events to be treated as
participants. The replay is retained as the v2 experimental result rather than accepted as an
improvement.

The v3 task kept one marked pair and one finite answer. It omitted the resolved identity name for a
direct source mention so that another occurrence of the same identity could not distract from the
marked occurrence. Its first development replay matched 33 of 44 expected entities, missed eleven,
and produced 27 extra identity-level connections in 175,423 model milliseconds. Although precision
improved, it lost five entities previously found by v2. It therefore failed the monotonic improvement
rule and is retained only as experiment evidence.

The v2 replay also exposed an evaluation-contract limitation: text values cannot distinguish equal
literals at different SourceSegment ranges. Connection Gold v2 therefore binds every accepted and
excluded occurrence to exact start, end, and source characters. The new occurrence bindings require
human review before another scored model replay.

A first deterministic routing hypothesis treated both different-sentence candidates and entities
nested inside distinct candidate spans as structural negatives. Development preflight preserved all
44 expected entities, but held-out preflight rejected nine expected entities. Inspection showed that
malformed whole-clause Organization proposals enclosed legitimate named people and Organizations.
The generic nesting rule amplified an upstream probabilistic error and was removed.

The bounded v4 routing policy reuses the pinned Stanza linguistic trace and deterministically rejects
only exact entity occurrences in a different linguistic sentence from the Event expression. Fresh
model-free preflights against the TGE-055 replacement preserve all 45 development and 41 validation
expected entities plus the one reviewed development gap. The development split routes 16 of 167
candidates deterministically and leaves 151 for Qwen. The held-out split routes 7 of 113
deterministically and leaves 106 for Qwen. Same-sentence nesting and overlap remain semantic
questions. The v4 prompt restores the stronger v2 involvement language; a scored replay remains
blocked on human approval of the exact Gold occurrence bindings.

Human review then found that TGE-025 had dropped the source attribution while describing the content
of Sacks's statement as world state. Trigger Gold now preserves the source verb `stated` and the
complete attributed content. Connection Gold binds that same meaning, expects both Sacks as the
attribution source and Anthropic as the statement subject, and explicitly records that the source
does not independently establish the quoted activity. Human review also restored TGE-055's omitted
`with FedRAMP authorization` qualification and the source-exact FedRAMP Organization occurrence.
The review also restored The New York Times to TGE-007's Event meaning; EGE-045 already preserved
the publication Organization and exact occurrence.

The completed Event review then removed four unsuitable Connection Gold cases without deleting
their source evidence.

- TGE-012 is a rejected embedded action because the source does not establish that the requested
  vote occurred.
- TGE-024 remains a valid reporting Event, but TGE-025 preserves its speaker, attribution, and full
  substantive content, so TGE-024 adds no connection judgment.
- TGE-029 and TGE-031 remain valid source-grounded Events, but TGE-030 preserves both Amodei and JD
  Vance plus the substantive relation between their views, so the two narrower cases add no
  connection judgment.
- TGE-078 replaces TGE-024 in development.
- TGE-064, TGE-069, and TGE-085 replace TGE-012, TGE-029, and TGE-031 in validation.

The replacement cases preserve the 20/20 partition while increasing the reviewed inventory to 47
development and 43 validation entities. Their exact occurrences include a threat with resolved
Organization references, a policy conflict with unrelated same-segment federal agencies, an
attributed opposition by a source-bound Actor group, and a court denial.

The human review approved the focused replacement addendum on September 16. Connection Gold v2 now
has status `approved`, and its exact 20/20 inventories authorize a fresh preflight and scored replay.

The first post-approval model-free replay against immutable September 14 evidence exposed four
separate upstream conditions rather than sending an invalid inventory to Qwen. Two were current
deterministic defects. The Actor-group rule recognized only `officials`, so it omitted exact source
occurrence `Anthropic representatives`; coarse person labels from GLiNER and ReFinED also overrode
Qwen's explicit Organization interpretation for `Anthropic` in the court-denial sentence. The
generic repair admits a governed plural human-role head after either a named Actor or Organization,
and permits coarse person evidence to reinforce only `person`, `government`, or `unclear` contextual
usage. It does not override explicit Organization usage.

Replaying the corrected deterministic selector over the same immutable evidence moved held-out
validation from 41/43 to 43/43 available expected entities, with no typed gaps or deterministic
rejections. Development remains truthfully blocked on two upstream conditions: the old canonical
bundle predates the approved semantic resolution of `his` to Amodei, and `FedRAMP` lacks an
Organization-denoting exact candidate even though the broader `FedRAMP authorization` policy span
exists. The first requires fresh current reference evidence. The second requires upstream mention
and denotation evidence; this connection boundary must not manufacture an Organization solely to
make Gold pass.

A focused offline ReFinED probe then separated the FedRAMP boundary and identity questions. With
the same authoritative SourceSegment, caller-owned exact span `FedRAMP` linked to Wikidata
`Q21070748` / Wikipedia title `FedRAMP` at `0.9575`, while caller-owned span
`FedRAMP authorization` returned only NIL. ReFinED supplied no coarse mention type for either span.
This proves that exact-span recovery can preserve useful external-identity evidence, but that ranked
identity evidence alone cannot establish KoteKomi's Organization denotation. A bounded semantic
Organization-qualification probe over exact `FedRAMP` is required before selecting the production
repair.

The bounded qualification probe admitted the complete 286-token request under the pinned
`qwen2.5-14b-instruct` profile and returned the valid one-token judgment `ambiguous` in 153 ms. The
exact input supplied `FedRAMP`, the complete authoritative paragraph, and KoteKomi's Organization
definition. This falsifies source-only semantic qualification as the repair: the paragraph says
that services had FedRAMP authorization, but does not itself state that FedRAMP is a continuing
collective Agent. The next bounded probe must inspect the pinned local ReFinED entity-class
evidence for `Q21070748`; neither the prompt nor the connection selector may manufacture that
missing world knowledge.

That offline class-evidence probe linked exact `FedRAMP` to `Q21070748` at `0.9358`. ReFinED's
contextual classifier did not predict Organization; its highest contextual labels included
`planned process`, so the contextual result cannot close the gap. The pinned linked-entity class
closure, however, includes `Q43229` (`organization`) alongside broad superclass and relation-derived
labels. ReFinED constructs this table from Wikidata `instance of`, occupation, sport, and country
relations plus superclass closure. Therefore the class table is useful external-identity evidence,
but it is neither source evidence nor an ontology decision. A production repair must expose the raw
linked-entity classes through the Adapter contract and apply an explicit Application-owned mapping;
it must not treat every returned class as authoritative or hide the mapping in the Adapter.

The first production-equivalent bounded replay then exposed one additional upstream boundary
defect. Deterministic named-symbol discovery produced exact candidate
`mnc_b844563585bf530abe355832` for source characters `126:133`, but semantic boundary adjudication
marked it `incomplete` in favor of `FedRAMP authorization`. Only the broader span reached ReFinED,
which correctly returned NIL. The repair now treats exact named-symbol discovery as authoritative
only for candidate-boundary completeness; Qwen still owns referentiality and contextual-use
judgments, ReFinED still owns external-link evidence, and the Application Layer still owns ontology
mapping.

The corrected bounded replay completed on September 16. It preserved exact `FedRAMP` as a complete
candidate, recorded Qwen's separate `specific_entity` / `policy` interpretation, admitted the
candidate to grounding, and linked it to `Q21070748` / `FedRAMP` at `0.9575`. The transported class
closure contained `Q43229` (`organization`). Every result retained exact SourceSegment identity,
source digest, ModelRun, ExtractionTask, and stage-trace lineage. This validates the complete bounded
upstream evidence chain without creating a ProposedChange or accepted Ledger record.

A fresh canonical ingestion then passed both model-free Event-entity preflights: development made
all 47/47 expected entities available and held-out validation made all 43/43 available, with zero
candidate gaps, missing entities, contextual-exclusion violations, or deterministic Gold
rejections. TGE-055 included exact Organization candidate `FedRAMP` at source characters `126:133`
alongside Palantir and Amazon Web Services. The enclosing document verifier remained nonterminal on
independent Front-Half (37/40) and Standing Fact (1/3) Gold findings; source-grounded Events remained
87/87 exact. Those broader findings do not invalidate this boundary's passing candidate preflight.

The parent-binding validator rejects any future Event-meaning drift. The scored three-development /
one-held-out replay remains required before this experimental boundary can close.

The first scored replay after the 47/47 development and 43/43 validation preflights falsified the
pairwise v5 judgment contract rather than the candidate pipeline. All three development repetitions
were identical: 35 of 47 expected identities matched, twelve were missing, thirty-one extra
identity connections were created, only two of twenty Events passed, and 166 separate Qwen calls
were required. Held-out validation matched 38 of 43 identities, missed five, added thirty-two extra
connections, left one occurrence unresolved, passed six of twenty Events, and required 106 Qwen
calls.

The preserved traces expose systematic rather than stochastic errors. For the relative clause
`firms ... which reached agreements`, Qwen rejected the firms when judging `agreements`; for the
controlled infinitive `agreements ... to avoid punishment`, it rejected the firms and selected an
unrelated neighboring person; and for `companies that offered services with FedRAMP authorization`,
it rejected Palantir, Amazon Web Services, and FedRAMP. Independent binary calls denied Qwen the
contrast needed to partition all available same-Event candidates consistently and amplified its
per-call `Y` / `N` bias.

The v6 hypothesis therefore changes only task allocation. KoteKomi supplies one ordered inventory
of all model-routed exact occurrences for one Event; Qwen returns one fixed-length `Y` / `N` / `U`
vector; KoteKomi owns the position mapping, records, ranges, identifiers, and reconciliation. This
reduces the observed model-call upper bounds from 166 and 106 to at most twenty per phase without
removing any candidate evidence. Fake-Port and parser tests must pass before a fresh scored replay;
the replay, not this architectural argument, decides whether v6 is an improvement.

The fresh v6 replay falsified that hypothesis on September 16. All three development repetitions
were stable but failed identically: 21 of 47 expected identities matched, 26 were missed, 44 extra
connections were created, 23 candidate occurrences remained unresolved, and no Event passed. The
held-out run matched 28 of 43 identities, missed 15, created 20 extras, left five unresolved, and
passed two Events. Candidate preflight remained complete at 47/47 and 43/43, so this is a judgment
failure rather than an upstream recall failure.

The batching optimization reduced model executions from 166 to 20 in development and from 106 to
20 in validation, but did not improve elapsed model time: development remained about 157--160
seconds and validation about 100 seconds. It reduced development formatted input from 90,491 to
27,397 tokens, but increased the largest individual request from 577 to 1,823 tokens. One
thirteen-candidate task returned fourteen answers and invalidated its whole inventory. Valid vectors
also exposed systematic semantic errors: the model rejected both law firms connected through a
relative clause, selected only the nearest member of a coordinated company phrase, rejected
FedRAMP's source-grounded qualification, and selected entities from neighboring clauses.

The v6 contract is therefore retained as negative experiment evidence and is not eligible for
production integration. The next experiment must not tune this vector prompt in place. It must first
measure source-exact predicate-argument proposals from the already pinned linguistic evidence,
including direct dependencies, coordination, relative-clause antecedents, and controlled or
inherited subjects. Those fallible specialist proposals remain derived evidence. Only after their
Gold recall and precision are measured may a smaller Qwen task adjudicate the genuinely semantic
remainder.

The accepted [Stanza Predicate-Argument Diagnostic](2026-09-16-stanza-predicate-argument-diagnostic.md)
owns that measurement.

It uses the same approved 40-case Gold catalog and changes no production routing contract.

That diagnostic completed on September 16 with zero model executions and zero accepted Ledger
writes. Development structurally covered 46 of 47 expected entity identities, and held-out
validation covered 36 of 43. Occurrence-level precision was only `0.3910` and `0.5062`, respectively,
because broad dependency paths also admitted entities from neighboring clauses and modifiers.

Even direct paths were not semantically sufficient on held-out data. They admitted the temporal
adjunct `That month` and the attribution source `Semafor` as if they were Event participants. The
structural auto-routing hypothesis is therefore falsified. Pinned Stanza evidence remains useful for
describing candidate paths and defining smaller semantic contrasts, but it cannot independently
decide Event involvement.

## 10. Reference Implementations

- Event grounding: follow `packages/application/src/kotekomi_application/source_grounded_events.py`.
- Bounded judgments: follow `packages/application/src/kotekomi_application/hybrid_event_trigger_preview.py`.
- Stage evaluation: follow `packages/pipelines/src/kotekomi_pipelines/event_trigger_stage_local.py`.
- Stage runner: follow `scripts/run_hsq7_stage_local.py`.

## 11. Constraints and Halt Conditions

The TDD halts before model execution when Connection Gold lacks human approval.

The TDD returns `upstream_blocked` before model execution when an expected entity is unavailable, a
reviewed expected gap is absent or changed, or an unexpected upstream candidate gap remains.

The experiment records that upstream failure instead of repairing it in this boundary.

The TDD halts when validation differs from Connection Gold.

The next TDD can integrate only an experimentally verified connection contract.
