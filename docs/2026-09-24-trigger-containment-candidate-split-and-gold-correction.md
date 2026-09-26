# TDD: Trigger-Containment Candidate Split and Gold Correction

- Status: Accepted
- Deliverable ID: `R2`
- Program: [Source-Grounded Attachment Deterministic-First Package](2026-09-24-source-grounded-attachment-deterministic-first-package.md)
- Parent: [Competitive Event Attachment Program](2026-09-18-competitive-event-attachment-program.md)
- Depends on: [R1 Deterministic Dependency-Path Attachment Router](2026-09-24-deterministic-dependency-path-attachment-router.md)
- Prior art: [CEA-1.2 Review-Claim Verification Diagnostic](2026-09-18-competitive-event-attachment-review-verification.md)

## 1. Context & Problem

The frozen Attachment Gold derives every Gold Attachment Set through exact fragment membership.

A candidate attaches to an Event when the candidate exact range equals one fragment of that Event.

That rule makes one candidate label a property of segmentation, not of language.

A candidate that grows across a foreign Event trigger gains a label it would not have at its correct size.

The Competitive Event Attachment Program already named this defect.

CEA-1.2 recorded 184 Segmentation Flips among 438 strict Nested Candidate Pairs.

CEA-1.2 preserved source-exact split proposals but never changed the Gold.

R1 kept trigger containment as a diagnostic field and never gated the NONE route on it.

R1 still scores against a Gold whose false-NONE labels partly encode that artifact.

R3, R4, and R5 also consume that Gold.

R2 corrects the Gold before any later deliverable consumes it.

### Terms

**Attachment Candidate** means one exact source occurrence considered against an Event proposition.

**Candidate universe** means the 187 distinct exact fragment ranges in the frozen Proposition Gold.

**Gold Attachment Set** means the set of Events whose fragment list contains the candidate exact range.

**Event trigger** means one accepted expression range of one Event in the frozen trigger Gold.

**Foreign Event trigger** means an Event trigger strictly contained in the candidate range and owned by an Event the candidate does not already attach to.

**Trigger-containment candidate** means a candidate that strictly contains at least one foreign Event trigger.

**Resized candidate** means one source-exact candidate fragment that remains after a trigger-containment candidate loses every foreign Event trigger range.

**Corrected Attachment Gold** means the Attachment Gold whose trigger-containment candidates are replaced by resized candidates and re-labeled by exact fragment membership.

**Segmentation artifact** means a Gold label that changes only because a candidate range crosses a foreign Event trigger.

**Baseline re-score** means mapping each R1 Route Decision onto the Corrected Attachment Gold and recounting the error classes.

### Primary flow

1. The runner binds the frozen Proposition Gold, trigger Gold, connection Gold, Stanza runtime, and per-segment source text by SHA-256.
2. The Application Layer builds the candidate universe from the frozen fragment occurrence ranges.
3. The splitter detects each candidate that strictly contains a foreign Event trigger.
4. The splitter emits one resized candidate per trigger-containment candidate.
5. The splitter re-derives the Gold Attachment Set of each resized candidate by exact fragment membership.
6. The report re-scores the R1 Route Decisions against the Corrected Attachment Gold.
7. The runner writes one corrected Attachment Gold file and one JSON report plus one Markdown review.

R2 creates derived state and one new reference Gold file.

R2 executes no model task and changes no canonical state.

## 2. Goals

- An operator can read the corrected label for every candidate.
- An operator can see, per trigger-containment candidate, the resize and the label before and after.
- An operator can compare the R1 baseline error classes before and after the correction.
- An operator can rebuild the corrected Gold file byte-for-byte from the frozen inputs.
- The report keeps the held-out partition reserved and unread.

## 3. Requirements

### Partition roles and candidate universe

- R2-PRT-01: The runner must reuse the frozen forty-Event phase split.
- R2-PRT-02: The splitter must derive the candidate universe from the 187 distinct fragment ranges only.
- R2-PRT-03: The splitter must reject a candidate whose partition role is unknown.
- R2-PRT-04: The splitter must never tune a decision on the held-out partition.
- R2-PRT-05: The report must record each candidate partition role.

### Frozen input evidence

The runner binds the frozen inputs to these exact SHA-256 digests.

- Frozen Proposition Gold catalog `docs/hsq-source-grounded-proposition-gold-v1.json`: SHA-256 `f496ab64e6590de05b1bc07ef069335fae6a7094b009b2fae3ca02cc627e54b0`.
- Child Event-Entity connection Gold `docs/hsq-event-entity-connection-gold-v2.json`: SHA-256 `afb3b25a421913b8d6b1c29eda90ee681d3bbf71719f7e0377a626bfc6067294`.
- Child Event-trigger Gold `docs/hsq-event-trigger-gold-v1.json`: SHA-256 `844eb564fb953e8d202f211469465f29f6de95dd811c033506f616cf425fe83f`.
- Per-segment source text binds by each `source_text_sha256` field inside the frozen catalog.
- Pinned Stanza dependency runtime `packages/adapters/src/kotekomi_adapters/stanza-model-lock.json`: SHA-256 `4e66da09e0da1b3daef940ac8bec68d814b99d9fb10538e371548c9914d87bb3`.
- Stanza resource `stanza_english_v1`, package `1.14.0`, resources JSON: SHA-256 `4e41c1df152146fa26ed0c006a08feea7a60bb3414bb6d57dbda24ad2e3cb99c`.
- The held-out partition `docs/anthropic-dod-attachment-proposition-held-out-gold-v1.json` is reserved for R5 and is not read by R2.

- R2-EVD-01: The runner must bind every direct input by SHA-256.
- R2-EVD-02: The splitter must stop when one Event trigger cannot be materialized to exact source characters.

### Trigger containment detection

- R2-TRG-01: The splitter must detect one Event trigger strictly contained in a candidate.
- R2-TRG-02: The splitter must classify a contained trigger as foreign only when its Event is not in the candidate Gold Attachment Set.
- R2-TRG-03: The splitter must never treat a trigger own Event as foreign.
- R2-TRG-04: The report must list every trigger-containment candidate with its foreign trigger ranges.

### Resize

- R2-SPL-01: The splitter must emit one resized candidate per trigger-containment candidate.
- R2-SPL-02: The resized candidate must exclude every foreign Event trigger range.
- R2-SPL-03: The resized candidate must be source-exact.
- R2-SPL-04: The splitter must choose the longest non-whitespace fragment that remains.
- R2-SPL-05: The splitter must choose the leftmost fragment when two remaining fragments tie in length.
- R2-SPL-06: The splitter must never repair a source range.
- R2-SPL-07: The splitter must never change the original Proposition Gold.

### Corrected Attachment Gold

- R2-GLD-01: The splitter must re-derive each resized candidate label by exact fragment membership.
- R2-GLD-02: A non-trigger-containment candidate must keep its original label.
- R2-GLD-03: The corrected Gold must preserve every Event, fragment, and source text unchanged.
- R2-GLD-04: The corrected Gold must serialize one new file `docs/hsq-source-grounded-proposition-gold-v1-corrected.json`.
- R2-GLD-05: Equal inputs must produce a byte-identical corrected Gold file.
- R2-GLD-06: The report must bind the corrected Gold file by its computed SHA-256.

### Baseline re-score

- R2-SCR-01: The report must carry the R1 Route Decision for each candidate unchanged.
- R2-SCR-02: The report must recount the `none` error class against the corrected Gold on both partitions.
- R2-SCR-03: The report must recount the `mixed` error class against the corrected Gold on both partitions.
- R2-SCR-04: The report must recount the `temporal` error class against the corrected Gold on both partitions.
- R2-SCR-05: The report must list every candidate whose Route Decision comparison changes after correction.

### Evidence and safety

- R2-SAF-01: R2 must execute zero model tasks.
- R2-SAF-02: R2 must create zero ProposedChanges.
- R2-SAF-03: R2 must create zero accepted Ledger writes.
- R2-SAF-04: The manifest must bind every input, output, policy, and TDD digest.

## 4. Proposed Architecture

```text
frozen Proposition Gold + trigger Gold
                |
                +--> candidate universe (187 fragment ranges)
                |
                v
      trigger-containment splitter
                |
                +--> resize decision per trigger-containment candidate
                |
                +--> Corrected Attachment Gold file
                |
                +--> baseline re-score against corrected Gold
                |
                v
       JSON report + Markdown review
```

## 5. Key Interactions

```text
Runner       -> trigger Gold     : read accepted expression ranges
Runner       -> Proposition Gold : read fragments and partition roles
Application  -> splitter         : detect foreign trigger containment
Application  -> splitter         : emit one resized candidate
Application  -> corrected Gold   : re-derive label by exact membership
Application  -> report           : re-score R1 decisions vs corrected Gold
```

## 6. Data Model

`TriggerContainmentResize` stores one candidate ID, its foreign trigger ranges, one resized candidate range, and the label before and after.

`CorrectedAttachmentGold` stores the corrected label mapping and the corrected Gold file digest.

`TriggerContainmentCorrectionReport` stores the resize census, the corrected Gold digest, and the before-and-after error-class counts.

These records are derived experimental evidence plus one new reference Gold file.

They do not change accepted Ledger state.

## 7. APIs / Interfaces

The splitter accepts the frozen Gold catalog, the frozen trigger Gold, and the pinned Stanza runtime.

The splitter returns one corrected Attachment Gold and one report.

The corrected Gold file replaces no predecessor and is consumed by R3, R4, and R5.

## 8. Behavior & Domain Rules

The candidate primary source span defines the scored occurrence.

The Event trigger binds by the accepted expression range in the trigger Gold.

A trigger is foreign only when its Event is not in the candidate Gold Attachment Set.

The splitter computes resized candidates without reading the R1 Route Decision.

The report computes the re-score after the corrected Gold exists.

The corrected Gold never alters the original Proposition Gold.

The resized candidate never invents source characters.

The Markdown review renders typed records and does not define the split.

## 9. Acceptance Criteria

- AC-R2-PRT: Tests reject an unknown partition role and reuse the frozen forty-Event split.
- AC-R2-TRG-01: Tests prove the splitter detects a candidate that strictly contains a foreign Event trigger.
- AC-R2-TRG-02: Tests prove the trigger's own Event stays non-foreign.
- AC-R2-SPL-01: Tests prove one resized candidate replaces one trigger-containment candidate.
- AC-R2-SPL-02: Tests prove the resized candidate excludes every foreign trigger range and stays source-exact.
- AC-R2-SPL-03: Tests prove the leftmost-longest fragment tie rule.
- AC-R2-GLD-01: Tests prove a non-trigger-containment candidate keeps its original label.
- AC-R2-GLD-02: Tests prove a resized candidate re-labels by exact fragment membership.
- AC-R2-GLD-03: Equal inputs produce a byte-identical corrected Gold file.
- AC-R2-SCR-01: The report recounts all three error classes against the corrected Gold on both partitions.
- AC-R2-SCR-02: The report lists every candidate whose comparison changes after correction.
- AC-R2-EVID: Tests reject changed Gold, source, or Stanza digests.
- AC-R2-WRITE: The report records zero model executions and zero canonical writes.
- AC-R2-ALL: Focused formatting, lint, typecheck, and tests pass.

## 10. Reference Implementations

- Router record types and frozen binding: `packages/application/src/kotekomi_application/deterministic_dependency_path_attachment_router.py`.
- Split-proposal construction: `_split_candidate` in `packages/pipelines/src/kotekomi_pipelines/competitive_attachment_review_verification.py`.
- Trigger-containment record types: `packages/application/src/kotekomi_application/competitive_attachment_review_verification.py`.
- Foreign-trigger diagnostics: `packages/application/src/kotekomi_application/competitive_attachment_selection.py`.
- Trigger scope split: `packages/application/src/kotekomi_application/trigger_scope_split.py`.
- Stanza token binding: [Stanza dependency parsing](https://stanfordnlp.github.io/stanza/depparse.html).

## 11. Constraints and Halt Conditions

- Stop when one Event trigger cannot be materialized to exact source characters.
- Stop when the splitter must change authoritative source characters.
- Stop when the corrected Gold must alter the original Proposition Gold.
- Stop when a Route Decision would invoke a model runtime.
- Stop when the held-out partition is read to tune a decision.