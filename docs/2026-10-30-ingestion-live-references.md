# TDD: Ingestion Live References and Replay Exposure

- Status: Completed
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
  any write. A valid candidate awaiting review produces an Event-specific
  composition hold in §8, never an identity.
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

The presentation step is also done: `InspectionSession` loads
`<ledger parent>/composition-outcomes` into `ParagraphAnnotationProfile`, and the
shared renderer shows the hold or the composed Assertion with its supporting span
in the live block and the Textual replay view.

## 9. Acceptance Checks (all resolved)

1. Cross-view lineage: done as an explicit hold. The Adapter resolves a mention
   only when the Event source view matches the accepted `EvidenceTarget` view. A
   different view returns a `cross_view_unsupported` diagnostic and no reference;
   it never guesses by unique text. Verified cross-view lineage stays deferred and
   is not part of R20.
2. Interactive replay display: done. `CompositionAnnotation` is a
   `ParagraphAnnotationProfile` field, `composition_annotations_for` loads the
   persisted records, and `render_annotated_paragraph` renders a `composition`
   section.
3. Normal ingestion entry point: done. `run_ingestion_worker` invokes
   `ingestion_composition_pass.compose_ingested_run` after `ingest_user_file`
   finalizes. For every paragraph that realizes an Event it analyzes the
   authoritative paragraph once, writes the validated `IngestionTokenArtifact` to
   `<ledger parent>/token-artifacts`, and persists one composition outcome per
   Event to `<ledger parent>/composition-outcomes`.
   `test_normal_worker_persists_the_hold_then_recomposition_composes` drives that
   worker entry point: ingestion discovers the paragraph and its Event, the worker
   alone writes the token artifact and the Event-specific hold
   (`assertion_inputs_unavailable`), the review step consumes a candidate that
   ingestion itself persisted (`ingested_grounding_candidates` derives
   review-selectable candidates from HP-3 eligibility and link evidence), and the
   explicit `run_recomposition` produces a composed Assertion that
   `composition_annotations_for` reloads with its supporting span. The test
   contains no separate composition call, no constructed candidate, and no seeded
   outcome.
4. Run binding and failure taxonomy: the pass composes the IngestionRun the worker
   was assigned, so a concurrent ingestion cannot make it compose another run's
   source. A recoverable analyzer failure keeps an explicit `inventory_unavailable`
   hold; an invalid deterministic token-artifact binding raises instead of
   degrading to a hold; a persistence failure writes `artifact_persistence_failed`
   holds before it reaches the error stream.
5. Token source: `IngestionTokenArtifact` binds ordered dependency tokens to the
   representation, TextView, paragraph node and range, source-text digest, and
   analyzer identity. `load_ingestion_token_artifact` validates the digest and
   every token coordinate against the authoritative paragraph. Reviewed assertion
   inputs (predicate mapping, per-Event `EvidenceTarget`) stay review decisions;
   the pass holds with `assertion_inputs_unavailable` until they are supplied.

### 9.1 Coordinate contract (resolved)

The live analysis unit and the composition unit differ.

- `run_hybrid_event_trigger_preview` analyzes one `SourceSegment` at a time on
  `derive_source_copy_view(segment.exact_text)`, which collapses whitespace, so
  analyzed tokens are in segment-source-copy coordinates.
- The composition use case and `EventCompositionRecord` spans assume one
  paragraph `source_text` with paragraph-local tokens, and the replay reader needs
  paragraph-local spans.

Resolution: the pass analyzes the authoritative paragraph text unchanged once per
Event-bearing paragraph and pins those tokens in `IngestionTokenArtifact` with
paragraph-local offsets. HP4 keeps its existing segmented analysis; every segment
source-copy trigger is mapped through `SourceCopyView.authoritative_range` and the
segment's paragraph offset, and each mapped span is validated against the
paragraph text, never located by text search.

### 9.2 Cancellation-test blocker (resolved)

`test_replay_cancellation.py` imports
`from packages.pipelines.tests.test_replay_reader import example_profile`, so its
spawned worker needs the repository root on `sys.path`. Without it the worker
fails with `ModuleNotFoundError: No module named 'packages'`. Running the suite
with `PYTHONPATH=.` makes all eight cancellation tests pass; the check plan
records that invocation.

Explicit recomposition stays the chosen behavior; automatic recomposition after
approval is out of scope. The command is discoverable and tested:
`scripts/recompose_ingested_event.py --request <json> --ledger <db> --out <json>`
wraps `run_recomposition` in `ingestion_composition_command.py`.

## 10. Completion Record

R20 is complete. Same-view reference resolution is explicitly supported; a
different source view is explicitly held with `cross_view_unsupported` and no
reference. Verified cross-view resolution is deliberately out of scope and is not
implied by this completion.

Guarantees this record rests on:

- An accepted identity occurs only through `accept_identity_occurrence`, which
  validates the identity, the replayable `EvidenceTarget`, the occurrence, and the
  `ProvenanceActivity` together. A grounding candidate never becomes an accepted
  reference.
- The live Adapter reads accepted occurrences only, prefers the accepted
  `EvidenceTarget` coordinates, fails fast on missing evidence or identity, and
  reports ambiguous or unfound mentions as typed diagnostics that become
  Event-specific holds.
- Normal ingestion persists one composition outcome per Event, keyed to the
  worker's IngestionRun, and the replay reader shows the hold or the composed
  Assertion with supporting spans.

Verification evidence:

- `packages/application`, `packages/adapters`, and `packages/pipelines`:
  2,200 tests pass with `PYTHONPATH=.` (one skipped).
- Historical R17 and R18 contracts are unchanged. `git diff 5de64dc..HEAD -- data/
  docs/hsq-*` touches exactly one file, the current-test contract
  `data/r18-current-test-contract/semantic_selection_contract.json`; the rebind is
  separate, scripted, and recorded in `docs/CHECK_PLAN.md`.
- The R18 failure attributed to a pre-existing R17 defect was R20-caused: relaxing
  `_EntityId` in `decontextualization_composition.py` drifted the bound scoring
  digest. Reproducing that failure at pre-R20 `5de64dc` and at `5727595`, and its
  appearance at `745cedf`, established the attribution.

R20 completion is scoped to this ingestion and composition path. It does not
establish whole-package completion, held-out validation, or general extraction
reliability.

## 11. Operator Handoff and Next Priorities

1. Operator-run ingestion through the normal CLI, then interactive replay. This is
   a human-run step: start it, watch it, and inspect the durable records
   afterwards.
   - Ingest:
     `uv run kotekomi --config <kotekomi.toml> ingest <source-file> --url <url>`
   - Replay the persisted run interactively:
     `uv run kotekomi-live-replay --state-root <state-root>`
   - Explicit recomposition after a reviewed occurrence is accepted:
     `uv run python scripts/recompose_ingested_event.py --request <request.json> --ledger <ledger.db> --out <out.json>`
   - Expected durable outputs: `<state-root>/kotekomi.db`,
     `<state-root>/archive/`, `<state-root>/token-artifacts/<paragraph-node>.json`,
     `<state-root>/composition-outcomes/<event-id>.json`.
   - Success criteria: the replay view shows a `composition` section for each Event
     that realized a trigger, each outcome names either a hold reason or a composed
     Assertion with a supporting span, and recomposition after approval changes that
     Event from held to composed on reload.
2. Independent held-out validation for the package. R20 used development inputs
   only; the held-out partition stays a separate, outstanding package requirement.
3. Cross-view reference resolution stays unimplemented until real usage shows it
   matters.
