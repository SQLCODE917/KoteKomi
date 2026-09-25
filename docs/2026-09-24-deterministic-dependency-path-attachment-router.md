# TDD: Deterministic Dependency-Path Attachment Router

- Status: Accepted
- Deliverable ID: `R1`
- Program: [Source-Grounded Attachment Deterministic-First Package](2026-09-24-source-grounded-attachment-deterministic-first-package.md)
- Parent: [Competitive Event Attachment Program](2026-09-18-competitive-event-attachment-program.md)
- Prior art: [CEA-1.18 Dependency-Head Residual Routing](2026-09-21-competitive-attachment-dependency-head-routing.md)

## 1. Context & Problem

Stages two and three of proposition composition fail.

Stage two attaches the exact source occurrences that complete one Event proposition.

Stage three assembles the ordered fragment set into one decontextualized proposition.

The Competitive Event Attachment Program asked Qwen2.5-14B one semantic membership question per candidate.

The Attachment Gold encodes proposition containment through exact fragment ranges.

The model answered a language question against a span-arithmetic Gold.

Eight prompt conditions did not close that gap.

KoteKomi stores one pinned Stanza dependency tree for each SourceSegment.

Syntax dependency distance one reaches edge precision 0.930 on development.

Syntax dependency distance one reaches edge precision 0.967 on validation.

Syntax dependency distance one reaches validation NONE accuracy 0.947.

Qwen reaches validation NONE accuracy 0.421.

The selected policy rests on a two-candidate development margin.

The NONE class fails because its Gold label is a segmentation property, not language.

The deterministic route that solves the NONE class stays unused.

The model performs the work that syntax decides cheaply.

### Terms

**Route Decision** means one of `attached`, `not-attached`, or `model-review`.

**Attachment Candidate** means one exact source occurrence considered against one Event proposition.

**Attachment Set** means every Event that receives an Attachment Edge from one Attachment Candidate.

**Gold Attachment Set** means the Attachment Set derived from approved Proposition Gold.

**Competing Event Set** means every source-grounded Event under review in one SourceSegment.

**Syntax-Empty candidate** means one candidate whose dependency analysis returns no path to any Event in its Competing Event Set.

**Gold-NONE candidate** means one candidate whose Gold Attachment Set is empty.

**False-NONE** means a Syntax-Empty candidate whose Gold Attachment Set is not empty.

**NONE confusion matrix** means the two-by-two count of Syntax-Empty against Gold-NONE.

**Event Anchor** means the Stanza token at the exact Target Event head range.

**Complement family** means the direct governed clausal complement subtree of a reporting Event, marked by `ccomp` or `xcomp`.

**nmod-mediated acl** means an `acl` relation that reaches a candidate through an `nmod` host.

**Trigger containment** means a candidate that contains a foreign Event trigger.

**Error class** means one of `none`, `mixed`, or `temporal` in this deliverable.

**Held-out partition** means an authoritative Source Document that has never informed a Competitive Event Attachment decision.

### Primary flow

1. The runner validates the frozen forty-Event phase split and one pinned phase result.
2. The Application Layer maps each candidate and Event to pinned Stanza tokens.
3. The router computes one Route Decision per candidate.
4. The router applies the NONE rule to assign `not-attached`.
5. The router applies the path-depth and complement policy to assign `attached`.
6. The router labels every other candidate `model-review`.
7. The Pipeline compares each Route Decision with Gold at the exact occurrence.
8. The Pipeline computes the NONE confusion matrix and the per-pool ceilings.
9. The Pipeline computes the error-class census.
10. The runner writes one JSON report and one Markdown review.

R1 creates experimental evidence only.

R1 executes no model task and changes no canonical state.

## 2. Goals

- An operator can read one Route Decision per candidate.
- An operator can read the NONE confusion matrix on both partitions.
- An operator can compare the deterministic route with the selected policy.
- An operator can read the per-pool ceiling at dependency distance three and at unbounded distance.
- An operator can read one error-class census, not one exact-set score.
- The report keeps the held-out partition reserved and unread.

## 3. Requirements

### Partition roles

- R1-PRT-01: The runner must validate the frozen forty-Event phase split.
- R1-PRT-02: The router must reject a candidate whose partition role is unknown.
- R1-PRT-03: The router must never tune a decision on the held-out partition.
- R1-PRT-04: The report must record each candidate's partition role.
- R1-PRT-05: The report must record which partition informed each router decision.

### Input evidence

- R1-EVD-01: The runner must bind every direct input by SHA-256.
- R1-EVD-02: Gold must remain outside dependency analysis.
- R1-EVD-03: The Application Layer must reuse each pinned Stanza trace.
- R1-EVD-04: The router must stop when one candidate lacks exact Stanza evidence.

### Frozen input evidence

The runner binds the frozen inputs to these exact SHA-256 digests.

- Frozen Proposition Gold catalog: `docs/hsq-source-grounded-proposition-gold-v1.json` (SHA-256 `f496ab64e6590de05b1bc07ef069335fae6a7094b009b2fae3ca02cc627e54b0`).
- The catalog seals its child Gold by digest: `docs/hsq-event-entity-connection-gold-v2.json` (SHA-256 `afb3b25a421913b8d6b1c29eda90ee681d3bbf71719f7e0377a626bfc6067294`) and `docs/hsq-event-trigger-gold-v1.json` (SHA-256 `844eb564fb953e8d202f211469465f29f6de95dd811c033506f616cf425fe83f`).
- Per-Segment source text binds by each `source_text_sha256` field inside the frozen catalog.
- Pinned Stanza dependency runtime: `packages/adapters/src/kotekomi_adapters/stanza-model-lock.json` (SHA-256 `4e66da09e0da1b3daef940ac8bec68d814b99d9fb10538e371548c9914d87bb3`), resource `stanza_english_v1`, package `1.14.0`, resources JSON (SHA-256 `4e41c1df152146fa26ed0c006a08feea7a60bb3414bb6d57dbda24ad2e3cb99c`).
- The held-out partition `docs/anthropic-dod-attachment-proposition-held-out-gold-v1.json` is reserved for R5 and is not read by R1.

### Route decision

- R1-RTE-01: The router must emit exactly one Route Decision per candidate.
- R1-RTE-02: The router must assign `attached` only through distance-one or complement evidence.
- R1-RTE-03: The router must assign `not-attached` only through the NONE rule.
- R1-RTE-04: The router must assign `model-review` to every remaining candidate.
- R1-RTE-05: A Route Decision must never change canonical state.

### NONE router

- R1-NONE-01: The router must compute the NONE confusion matrix on both partitions.
- R1-NONE-02: The router must emit a false-NONE count and rate.
- R1-NONE-03: The router must route a Syntax-Empty candidate `not-attached` without reading Gold.
- R1-NONE-04: The report must classify each `not-attached` decision as true-NONE or false-NONE.
- R1-NONE-05: The trigger-containment rule must remain a diagnostic field.
- R1-NONE-06: The trigger-containment rule must never gate the NONE route.

### Path depth and complement family

- R1-PATH-01: Distance-one evidence may route a candidate `attached`.
- R1-PATH-02: Direct governed complement evidence may route a candidate `attached`.
- R1-PATH-03: The complement family must exclude nmod-mediated `acl`.
- R1-PATH-04: The router must compute the no-complement `path_1` comparison column.
- R1-PATH-05: The router must record the selected policy for each `attached` decision.

### Ceilings

- R1-CEI-01: The router must compute the candidate-source ceiling at dependency distance three.
- R1-CEI-02: The router must compute the candidate-source ceiling at unbounded dependency distance.
- R1-CEI-03: The router must compute the per-edge ceiling at each dependency distance.
- R1-CEI-04: A ceiling value must be a typed report field.
- R1-CEI-05: A ceiling value must not change a Route Decision.

### Error-class census

- R1-ERR-01: The router must count the `none` class on both partitions.
- R1-ERR-02: The router must count the `mixed` class on both partitions.
- R1-ERR-03: The router must count the `temporal` class on both partitions.
- R1-ERR-04: The report must list every `mixed` candidate the router routed `attached`.
- R1-ERR-05: The report must list every false-NONE case whose Gold contains a `temporal` fragment.

## 4. Data Model

`AttachmentRouteDecision` stores one candidate ID, one Route Decision, and the Event IDs that route allows.

`NoneConfusionMatrix` stores the two-by-two counts for one partition.

`AttachmentRouteReport` stores the route decisions, the confusion matrices, the ceilings, and the error-class census.

`PartitionRole` stores `development`, `validation`, or `held_out`.

These records are derived experimental evidence.

They do not change accepted Ledger state.

## 5. APIs / Interfaces

The router accepts one frozen Source-Grounded Proposition Gold catalog and one pinned phase result.

The router returns one `AttachmentRouteReport`.

The report schema replaces no predecessor.

## 6. Behavior & Domain Rules

The candidate primary source span defines the scored occurrence.

The Event Anchor binds by exact source range.

One Route Decision holds even when the candidate repeats across Events.

The router computes Route Decisions without reading Gold.

The report computes the error-class census against Gold after routing.

The report flags every false-NONE decision instead of hiding it.

The complement family never follows `acl` through an `nmod` host.

A ceiling is a diagnostic bound, not a Route Decision.

The Markdown review renders typed records and does not define the route.

## 7. Acceptance Criteria

- AC-R1-PRT: Tests reject a candidate with an unknown partition role.
- AC-R1-NONE-01: Tests prove a Syntax-Empty candidate routes `not-attached` without Gold in scope.
- AC-R1-NONE-02: Tests prove the report labels each `not-attached` decision true-NONE or false-NONE.
- AC-R1-MIX: Tests prove the report lists one `mixed` candidate the router routed `attached`.
- AC-R1-TEMPORAL: Tests prove the report lists a false-NONE case whose Gold contains a `temporal` fragment.
- AC-R1-COMP: Tests prove the complement family rejects nmod-mediated `acl`.
- AC-R1-CEI: Tests prove every ceiling field equals its recomputed value.
- AC-R1-EXACT: The report records the exact-set score, and the score does not gate acceptance.
- AC-R1-EVID: Tests reject changed Gold, source, or Stanza digests.
- AC-R1-WRITE: The report records zero model executions and zero canonical writes.
- AC-R1-ALL: Focused formatting, lint, typecheck, and tests pass.

## 8. Reference Implementations

- Dependency mapping: `competitive_attachment_review_verification.py`.
- Path policies and complement scope: `competitive_attachment_selection.py`.
- Trigger scope split: `trigger_scope_split.py`.
- Head alignment: `competitive_attachment_dependency_head_routing.py`.
- Dependency relations: [Universal Dependencies](https://universaldependencies.org/u/dep/).
- Stanza token heads: [Stanza dependency parsing](https://stanfordnlp.github.io/stanza/depparse.html).

## 9. Constraints and Halt Conditions

- Stop when one candidate lacks exact Stanza evidence.
- Stop when one Event or candidate range changes.
- Stop when Gold enters dependency analysis.
- Stop when a Route Decision would invoke a model runtime.
- Stop when a Route Decision would write canonical intelligence.
- Stop when the held-out partition is read to tune a decision.