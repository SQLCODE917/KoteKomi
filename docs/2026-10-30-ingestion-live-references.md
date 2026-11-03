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

The first increment defines and implements one Application Layer use case.

- Input: one grounding candidate (mention span, candidate kind, candidate
  identity, and source anchoring) plus a reviewed decision.
- Output: a pending `ProposedChange` that proposes the `Actor` or `Organization`
  record together with its accepted occurrence. The step writes no accepted
  state.
- Guard: a grounding candidate without a reviewed approval never becomes an
  accepted reference.
- Hold: `nil`, ineligible, or ambiguous candidates produce a typed hold. They
  produce no proposal and no value.
- New typed record: an accepted identity-occurrence association binds one
  accepted `Actor` or `Organization` to one accepted `EvidenceTarget`. The
  Adapter reads this association, never a grounding candidate.

## 6. Increment sequence

1. Acceptance/resolution step and the identity-occurrence association.
2. Live Adapter over accepted identities and accepted occurrences, with no
   Connection Gold.
3. Composition stage over ingested Events using the live Adapter.
4. Persisted inspection output and replay-TUI exposure.

The increment is done when a normal ingestion shows its source-grounded Assertion,
or its explicit hold, in replay, with no Connection Gold dependency.

## 7. Constraints

- Ingestion reads no reviewed Connection Gold and no fixture-specific binding.
- A candidate identity never silently becomes an accepted reference.
- The Domain Core owns the identity-occurrence record shape and its invariants.
- The Application Layer owns the acceptance decision and the hold reasons.
