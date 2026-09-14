# TDD: Standing-Fact Semantic Admission

- Status: Complete and canonically verified
- Deliverable ID: HSQ-5
- Program: [Hybrid Semantic Quality Program](2026-09-06-hybrid-semantic-quality-program.md)
- Depends on: [HSQ-4 Bounded Semantic Reference Resolution](2026-09-06-bounded-semantic-reference-resolution.md)

## Context & Problem

HP-10 validates source spans and candidate references before it creates standing-Assertion proposals.

It does not validate whether the complete binary proposition preserves source meaning.

It can therefore flatten events or substitute an incomplete subject.

**StandingFactQualification** means one semantic classification of a complete standing-Assertion proposition.

### Primary end-to-end flow

1. Qwen proposes one standing-Assertion draft.
2. KoteKomi validates source spans and references.
3. KoteKomi renders one CompleteProposition.
4. Qwen classifies the complete proposition.
5. The NLI Adapter challenges source entailment.
6. KoteKomi creates a ProposedChange only for a qualified standing Assertion.

## Goals

- A reviewer sees standing Assertions that preserve source participants and meaning.
- Event-like material remains in the Event route.
- Every held draft exposes one specific reason.

## Requirements

### Domain Core

- SFA-DOM-01: StandingFactQualification outcomes are `supported_standing_fact`, `event_not_standing`, `incomplete_or_wrong_arguments`, `unsupported`, and `ambiguous`.
- SFA-DOM-02: A StandingFactDecision records the qualification and proposition decision.

### Application Layer

- SFA-APP-01: KoteKomi renders the complete subject, predicate, and object proposition.
- SFA-APP-02: Qwen judges the complete proposition against exact source text.
- SFA-APP-03: The NLI Port evaluates the same source and proposition.
- SFA-APP-04: Admission requires `supported_standing_fact` and NLI entailment.
- SFA-APP-05: `event_not_standing` produces `event_route_required` without a standing ProposedChange.
- SFA-APP-06: An unresolved reference holds the draft.
- SFA-APP-07: An absent semantic subject holds the draft.
- SFA-APP-08: A standing draft is held as `event_route_required` before model qualification only when its exact relation range overlaps an Event trigger in the same SourceSegment.
- SFA-APP-09: An independent standing fact remains eligible when another clause in the same SourceSegment contains one or more Events.
- SFA-APP-10: Every model-visible candidate label includes its exact SourceOccurrence locator so repeated names are unambiguous.
- SFA-APP-11: A literal object is selected through a supplied SourceOccurrence range; Qwen does not transcribe its text or offsets.
- SFA-APP-12: KoteKomi rejects a relation range that overlaps a MentionCandidate instead of repairing or qualifying the malformed proposal.
- SFA-APP-13: KoteKomi constructs a CompleteProposition from the source-bound subject, relation, and object ranges so source grammar is retained without duplicate text.
- SFA-APP-14: When Qwen supplies only a terminal source anchor for a post-relation literal object, KoteKomi deterministically completes the literal from the relation boundary through that anchor, unless a clause boundary intervenes.

## Proposed Architecture

```text
StandingFactDraft
       |
       v
CompleteProposition
     /   \
    v     v
  Qwen   NLI
    \     /
     v   v
StandingFactDecision
       |
       v
eligible ProposedChange or typed hold
```

## Key Interactions

```text
Application -> Qwen: exact source plus standing proposition
Application -> NLI Adapter: exact source plus standing proposition
Application -> Domain Core: qualification and proposition evidence
Application -> review flow: eligible ProposedChange only
```

## Data Model

The StandingFactPlan stores each CompleteProposition and qualification record.

The plan retains held drafts and exact stage evidence.

## Behavior & Domain Rules

- SFA-RUL-01: A bounded event uses an Event record.
- SFA-RUL-02: A standing Assertion uses one complete subject-predicate-object meaning.
- SFA-RUL-03: Model agreement does not accept the Assertion into the Ledger.
- SFA-RUL-04: Event and standing-fact routes may both produce review candidates from one mixed SourceSegment when their source meanings do not overlap.
- SFA-RUL-05: Invalid model-selected component boundaries remain typed held evidence and cannot become ProposedChanges.
- SFA-RUL-06: Literal completion uses only authoritative characters between two already selected source boundaries and remains visible beside the parsed model proposal in stage evidence.

## Acceptance Criteria

- AC-SFA-APP-01: The accurate `cut ties with` standing relation remains eligible.
- AC-SFA-APP-02: `urged associates to vote` does not become a binary Amodei-to-Harris standing Assertion.
- AC-SFA-APP-03: `Amodei's statement included views` does not substitute Amodei as subject.
- AC-SFA-APP-04: `effort executor` event material receives `event_route_required`.
- AC-SFA-APP-05: Every decision retains exact Qwen, NLI, source, and deterministic validation evidence.
- AC-SFA-APP-06: Qwen and NLI agreement cannot admit a binary Assertion whose relation range overlaps an Event discovered in the same source segment.
- AC-SFA-APP-07: `AMO-07` preserves `Anthropic's strategy has mirrored Amodei's views toward Trump` as one standing proposition while the same SourceSegment independently retains `urged`, `vote`, and `describing` Events.
- AC-SFA-APP-08: The previously observed `mirrored Amodei's views toward Trump` plus entity `Trump` proposal is held because its relation overlaps MentionCandidates; it cannot produce `... Trump Trump.`
- AC-SFA-APP-09: The model output `fact: c1 | o2-o4 | literal | o8` deterministically maps to the complete literal `Amodei's views toward Trump`, not the truncated value `Trump`.

## Verification Result

The September 13, 2026 canonical run verified the corrective mixed-proposition contract.

- The repository check run passed 1,541 tests with one skip.
- Coverage report `hdc_b11adbd6fa1963b54d4fff4e` accounted for all 36 required paragraphs.
- The exact model proposal was `fact: c1 | o2-o4 | literal | o8`.
- KoteKomi recorded `object_mapping = completed_post_relation`.
- KoteKomi reconstructed `Amodei's views toward Trump` from authoritative characters.
- CompleteProposition `cpr_2fc1b56ee1ab935360ff010b` preserved the complete standing meaning.
- Qwen and the NLI challenger supported the proposition.
- ProposedChange `pcg_1e907fc2d989e32d56e37fe1` reached review.
- The ingestion created no accepted intelligence record.
- The immutable replay created zero ModelRun records.

## Reference Implementations

- Standing plans: follow `packages/application/src/kotekomi_application/hybrid_standing_facts.py`.
- Complete proposition evidence: follow HSQ-3 records and Ports.
- Mixed-proposition Gold: follow `AMO-07` in `docs/hsq-task-allocation-amodei-gold-v1.json`.
