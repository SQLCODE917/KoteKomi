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

- Before review, ingestion records the grounding candidate and a composition
  hold. The hold is visible and names its reason. The candidate is not an
  accepted reference.
- After approval, recomposition runs with the accepted association available
  through the Adapter. Replay then shows the composed Assertion.
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
  any write.

Increments 2 through 4 remain open: the live Adapter, the ingestion composition
stage, and the persisted replay exposure. R20 is not complete until the
pre-review hold and the post-approval recomposition both appear in replay.
