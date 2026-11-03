# TDD: Ingestion Live References and Replay Exposure

- Status: Proposed
- Deliverable: R20
- Parent: [Production Closure of AHE-022 and AHE-051](2026-10-22-deterministic-residual-composition-completion.md)

## 1. Context and Problem

R19 proves composition closure for AHE-022 and AHE-051 through the R4 workflow.
That workflow uses reviewed Connection Gold. Normal ingestion must reach the same
source-grounded Assertion, or a typed hold, with no Connection Gold dependency,
and expose the result through existing replay records.

## 2. Established facts

- Ingestion produces grounding candidates and identity-resolution links, not
  accepted identities. `hybrid_entity_grounding.py` emits `EntityLinkCandidate`
  (`knowledge_base_entity` or `nil`), `EntityGroundingEligibility`, and exact
  `EntityLinkMention` spans.
- `grounded_candidates.py` turns grounded candidates into `ProposedChange`
  batches. Accepted `Actor` and `Organization` records arise only through
  `approve_proposed_change`, which saves them from a reviewed ProposedChange.
- No accepted record links an `Actor` or `Organization` to its accepted source
  occurrences. `Actor` and `Organization` carry identity fields only.

## 3. Consequence

An Adapter cannot yet translate accepted identities into references, because the
accepted identity-to-occurrence association does not exist.

Building the Adapter over grounding candidates directly would let a candidate
silently become an accepted reference. The contract forbids that.

## 4. Architectural rule

- The Adapter translates accepted identity records into `EventEntityReferences`.
  It does not decide which mentions are Actors or Organizations.
- The Application Layer owns the mention-to-identity decision and its review
  acceptance.
- A missing or ambiguous reference yields a visible hold. Absence of a reference
  never authorizes `subject_value`.

## 5. Narrow acceptance/resolution step

The first increment defines one Domain Core record and two Application Layer use
cases.

### 5.1 Proposal

- Input: one grounding candidate (mention span, candidate kind, candidate
  identity or `nil`, and source anchoring) plus one reviewed proposal decision.
- The decision is one of two kinds: link the occurrence to an existing `Actor` or
  `Organization`, or propose a new `Actor` or `Organization`.
- Output: a pending `ProposedChange`. It proposes the identity decision and its
  occurrence association. It writes no accepted state.
- Guard: a grounding candidate without a review approval never becomes an
  accepted reference.
- Hold: `nil`, ineligible, or ambiguous candidates produce a typed hold. They
  produce no proposal and no value.
- Repeated mentions of one identity reuse that identity. A further mention adds
  one occurrence association; it never creates a duplicate identity.

### 5.2 Acceptance

- The review use case accepts one proposal atomically. It validates the identity,
  a replayable `EvidenceTarget`, the occurrence association, and a
  `ProvenanceActivity` together. It commits all of them or none.
- The occurrence association names one exact mention span through its
  `EvidenceTarget`. A paragraph-wide `EvidenceTarget` alone is insufficient.
- An accepted association binds one accepted `Actor` or `Organization` to one
  accepted `EvidenceTarget`. It supports both a newly accepted identity and a
  newly accepted occurrence on an existing identity.
- The Adapter reads accepted associations. It never reads a grounding candidate.

### 5.3 Workflow consequence

- An identity-resolution hold is not a composition hold. Ingestion records one
  Event-specific composition outcome that names the required reference the Event
  cannot resolve.
- A valid candidate that awaits review also produces that visible composition
  hold. It is neither `nil` nor necessarily ambiguous; it is simply not yet an
  accepted reference.
- Before review, ingestion records the grounding candidate and the composition
  hold. The hold is visible and names its reason. The candidate is not an
  accepted reference.
- After approval, recomposition runs with the accepted association available
  through the Adapter. Replay then replaces the hold with the composed Assertion.
- Without this second transition, the association stays disconnected
  infrastructure.

## 6. Completion bar

The increment is done only when all four parts ship and the completion bar holds.

1. Proposal and acceptance use cases plus the identity-occurrence record.
2. Live Adapter over accepted identities and accepted occurrences, with no
   Connection Gold.
3. Composition stage over ingested Events using the live Adapter.
4. Persisted inspection output and replay-TUI exposure.

The completion bar is a normal ingestion whose source-grounded Assertion, or
explicit hold, appears in replay with no Connection Gold dependency.

The pre-review hold and the post-approval recomposition are both required. An
accepted association with no replay transition does not meet the bar.

## 7. Constraints

- Ingestion reads no reviewed Connection Gold and no fixture-specific binding.
- A candidate identity never silently becomes an accepted reference.
- The Domain Core owns the identity-occurrence record shape and its invariants.
- The Application Layer owns the proposal decision, the acceptance validation,
  and the hold reasons.
- Acceptance is atomic and source-exact.

## 8. Implementation status

Increment 1 is implemented and tested.

- Domain Core: `IdentityOccurrence` and `IdentityOccurrenceKind`, with the
  `identity_occurrences` Ledger table and schema.
- Application Layer: `propose_identity_occurrence` emits a pending
  `ProposedChange`; `accept_identity_occurrence` validates the replayable
  `EvidenceTarget`, resolves a new or existing identity, and commits the
  occurrence, identity, evidence, and `ProvenanceActivity` atomically.
- Holds: a `nil`, ineligible, or ambiguous candidate raises a typed
  `IdentityOccurrenceHold`; an unreplayable span raises the evidence hold before
  any write. An Event-specific composition hold for a valid candidate awaiting
  review is still open.
- Atomicity: a real-SQLite test fails after an earlier write and proves the
  identity, `EvidenceTarget`, occurrence, provenance, and proposal status all
  roll back together. A companion test proves the successful commit.

Increment 2 is also implemented and tested.

- Pipelines: `LiveIdentityReferenceProvider` translates accepted
  `IdentityOccurrence` records into `EventEntityReferences`. It reads no
  grounding candidate. When the Event source view matches the accepted
  `EvidenceTarget`, it uses the accepted coordinates. Otherwise it locates the
  mention by a unique exact or whitespace-equivalent match.
- The Adapter fails fast when an accepted occurrence references a missing
  identity, a missing `EvidenceTarget`, or coordinates that do not replay its
  exact text. It never turns those cases into an empty reference set.
- An ambiguous or unfound mention leaves a typed `LiveReferenceDiagnostic`. The
  composition stage turns that diagnostic into an Event-specific hold.
- The composer `DecontextualizationEntityRef` now admits the accepted canonical
  `act_` and `org_` identity IDs alongside the reviewed `EGE` IDs, so the live
  Adapter can carry an accepted identity into composition.

Increments 3 and 4 are implemented and tested as one vertical slice.

- Application Layer: `compose_event_from_resolution` consumes a
  `ReferenceResolution` (accepted references plus typed diagnostics) and returns
  an `EventCompositionRecord`. A diagnostic that explains an unavailable
  reference becomes the Event-specific hold reason and names the missing
  reference. `write_event_composition_record` and
  `load_event_composition_record` persist and reload the outcome as the replay
  read model.
- Pipelines: `compose_ingested_event` wires the live Adapter to the use case,
  routes mention diagnostics, and adds an `awaiting_acceptance` diagnostic for a
  valid candidate that awaits review.
- Approval path: acceptance is atomic and explicit. Recompose is an explicit
  second Pipeline call after approval; approval does not trigger recomposition
  automatically.
- End-to-end test `test_ingestion_composition_transition.py` drives the held ->
  composed -> replay transition on a real SQLite Ledger: a valid candidate
  awaiting review persists a held record that names the missing identity,
  approval commits the occurrence atomically, explicit recomposition composes
  the Assertion with supporting spans, and the reloaded record shows the
  composed outcome.

The bounded ingestion deliverable is met: the pre-review hold and the
post-approval recomposition both appear in the persisted replay record for a
normal ingestion, with no Connection Gold dependency.

The remaining presentation step is wiring `load_event_composition_record` into
the interactive replay reader (`ParagraphSnapshot`), so the changed outcome
shows in the Textual replay view rather than only in the persisted read model.

## 9. Remaining Acceptance Checks

1. Cross-view lineage: done as an explicit hold. The Adapter resolves a mention
   only when the Event source view matches the accepted `EvidenceTarget` view. A
   different view returns a `cross_view_unsupported` diagnostic and no reference;
   it never guesses by unique text. Verified cross-view lineage stays deferred.
2. Interactive replay display: done at the data and render level.
   `CompositionAnnotation` is a `ParagraphAnnotationProfile` field.
   `InspectionSession` loads persisted records from
   `<ledger parent>/composition-outcomes` through `composition_annotations_for`,
   and `render_annotated_paragraph` (used by `render_live_block` and the Textual
   view) renders a `composition` section with the hold or Assertion summary.
3. Normal ingestion entry point: partially open. The composition pass
   `compose_paragraph_events` derives each Event's inventory from live
   dependency tokens, runs the shared use case with the live Adapter, and
   persists a composed or explicit held record for every Event
   (`inventory_unavailable`, `assertion_inputs_unavailable`, or a broader hold).
   It is tested. The token source is now specified as a derived artifact:
   `IngestionTokenArtifact` binds ordered dependency tokens to the
   representation, TextView, paragraph node and range, source-text digest, and
   analyzer identity. `load_ingestion_token_artifact` validates the digest and
   every token coordinate against the authoritative paragraph. The remaining
   wiring is to write this artifact where the ingestion orchestration runs
   Stanza, and to call `compose_paragraph_events` from the ingestion worker after
   the run finalizes. Reviewed assertion inputs (predicate mapping, per-Event
   `EvidenceTarget`) stay review decisions; the pass holds explicitly with
   `assertion_inputs_unavailable` until they are supplied in the
   review/recomposition request.

### 9.1 Coordinate contract finding (blocks the producer)

The live analysis unit and the composition unit differ.

- `run_hybrid_event_trigger_preview` analyzes one `SourceSegment` at a time
  (`paragraph_source_segments(paragraph_text, PARAGRAPH_SEGMENT_V3)`), on
  `derive_source_copy_view(segment.exact_text)`, which collapses whitespace.
- A paragraph therefore has several segments, and the analyzed tokens are in
  segment-source-copy coordinates, not paragraph coordinates.
- The composition use case and `EventCompositionRecord` spans assume one
  `source_text` with tokens covering it, and the replay reader needs
  paragraph-local spans.

Writing the artifact at the analysis point without resolving this would put
tokens and spans in a different coordinate system than composition and replay
expect. Two resolvable options:

1. Build a paragraph-level artifact: analyze the paragraph text once (or
   reconstruct paragraph tokens from the segment tokens through
   `SourceCopyView.authoritative_range` and the segment offsets).
2. Compose per segment and remap every resulting span back to paragraph
   coordinates. The artifact must then also bind the segment identity and its
   source-copy boundary map.

This mapping is the concrete implementation decision the producer and worker
need; it is not a file-count concern.

### 9.2 Cancellation-test blocker (resolved)

`test_replay_cancellation.py` imports
`from packages.pipelines.tests.test_replay_reader import example_profile`, so its
spawned worker needs the repository root on `sys.path`. Without it the worker
fails with `ModuleNotFoundError: No module named 'packages'`. Running the suite
with `PYTHONPATH=.` makes all eight cancellation tests pass. The failure is a
test-invocation concern, reproducible and explained, not code flakiness.

Explicit recomposition stays the chosen behavior. Automatic recomposition after
approval is out of scope for this increment.

The user-boundary acceptance test is open until check 3 lands: invoke normal
ingestion, inspect the hold through the replay reader, approve the occurrence,
invoke `scripts/recompose_ingested_event.py`, reload replay, and verify the
Assertion.

The explicit recomposition command is discoverable and tested:
`scripts/recompose_ingested_event.py --request <json> --ledger <db> --out <json>`
wraps `run_recomposition` in `ingestion_composition_command.py`. The
`test_recomposition_command_composes_after_approval` test exercises that command
path against a real Ledger.
