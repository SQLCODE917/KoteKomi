# Hold Incomplete Authorization

## Context & Problem

As a Ledger reviewer, I want KoteKomi to hold an authorization whose permitted action it cannot preserve, so I do not have to catch a misleading Assertion myself.

The [recorded assessment](2026-11-11-ingestion-improvements-task.md#remaining-failures-and-next-scope-decision) found that the DHS Event `sge_988e0f4478a351967c708e3e` proposed an Assertion with `its  workers` as the object. The proposal lost the permitted use, commercial artificial intelligence systems including Claude, and the limit through May 2025. A reviewer rejected it. The [checked-in capture](../packages/pipelines/tests/fixtures/ipi_promotion/README.md) preserves the Event and parse without needing inference. This is a development regression, not independent accuracy evidence.

The parser attaches `workers` to `authorized` as `obj`. It attaches `use` separately to that same trigger as `xcomp`, marked by `to`. The systems and time limit attach within the action subtree. The existing object completion looks for clauses or appositives under the object noun, so it does not address this loss.

The operator sees the hold and the relevant Source passage in the review packet, can still record ordinary identity and construction decisions, then sees an explicit held outcome on recomposition and saved replay. The Ledger creates no new Assertion proposal for this Event.

## Goals

- Stop the known misleading proposal without changing which complete Assertions the current path can propose.
- Show the same supported hold in the packet and in the persisted result once review prerequisites are satisfied.
- Preserve exact, inspectable Source evidence for the omitted action and its time limit in a new construction review. Preserve prior reviews and their evidence unchanged.

## Requirements and independently verifiable subtasks

| Subtask | Depends on | Current code and independent check |
| --- | --- | --- |
| A. Pin the Source counterexample | None | Reuse the typed capture loader and review flow in `test_ipi_production_promotion.py`; select the exact Event ID. Run the new acceptance test before changing production and retain the red result. Confirm the failure is the truncated proposal, not setup, identity selection, or missing capture. |
| B. Refuse to compose an unrepresented governed action | A | `build_decontextualized_proposition` owns representability. Test the captured dependency shape, a supported object completion, and a complement belonging to another trigger. Keep existing identity diagnostics and behavior when the new rule does not apply. |
| C. Preserve and replay the held outcome | A, B | The packet builder previews independently, recomposition delegates to the same composer, and the outcome store supplies saved replay. Reuse the rule, bind new review evidence, and exercise the actual packet, decision, recomposition, retry, and replay operations on the captured Event. |

## Proposed Architecture

```text
Captured Source and parse -> shared representability check -> review packet
                          -> shared composer             -> persisted hold -> saved replay
                                     |
                                     +-> Assertion proposal only if composed
```

Put the structural rule in the Application composition boundary. Use it from the packet builder and the proposition builder. Do not rely on the packet warning to enforce the rule or add the rule to the proposal store.

The rule applies when the Event has an existing selected direct object (the recipient in the DHS case) and the Event trigger directly governs a verbal `xcomp` with a `to` marker whose action is outside the represented roles. Check token ownership, not words such as `authorized` or the captured IDs. Do not extend this rule to all clausal complements, noun-attached clauses, or clauses beneath a different trigger. Reuse the existing held outcome contract; use the reason `unsupported_predicate_complement` in both callers without changing the persisted outcome schema.

Keep existing source, selection, and subject prerequisite checks. A packet may flag the structural issue before review, but it must still show the required decisions. In composition, keep earlier selection, subject, and reference diagnostics ahead of the new hold. Test that a missing identity retains its existing actionable diagnostic and that the new hold appears once identity and the other prerequisites are valid.

## Key Interactions and Evidence

1. Packet: show the held reason and keep the Source available. The selected object remains the recipient; do not present the omitted action as a represented object or trigger time.
2. Decision: for a new review of this Event, the statement EvidenceTarget must include the exact action and time phrase, through `May 2025`, from the stored Source, excluding unrelated neighboring sentences. This range explains the hold; it is not evidence of a complete Assertion. Resolve offsets from the validated tokens and Source; test the captured half-open end at paragraph-relative offset 564. Do not rewrite an existing EvidenceTarget or review on identical retry.
3. Recompose: with valid review, return a held outcome with no Assertion. Persist it through the existing outcome store. Do not create a new Assertion or an Assertion ProposedChange. A retry must not change review identity or create proposals.
4. Saved replay: reload the same Event from saved state, display the same hold, and do not show fabricated Assertion content. Verify that the new review's bound source text still resolves exactly.

## Acceptance Criteria

- The pinned captured Event changes from one misleading new Assertion proposal to zero on clean reviewed state. It produces zero complete Assertions both before and after; this is a fidelity correction, not a coverage gain.
- The operator-path test uses the production packet, decision, recomposition, and saved replay interfaces with no parser mock or live model. It proves the exact evidence range, held reason, no new Assertion or proposal, and stable retry. The test fails for the expected truncation on the pinned pre-change code.
- Focused rules tests reject the governed-action case and retain the supported completion and other-trigger control. A different verb with the same structural shape must also hold. The complete announcement, the existing captured promotion journeys, and the unsupported-complement hold remain working.
- The PR records the independent checks, one whole-journey result, candidate receipt, and terminal candidate CI against the receipt commit in the existing Harness run. Separate the reported semantic result from checks and from handoff process measures.

## Constraints and Stop Conditions

No changes to fresh-ingestion admission, the parser, prompts, inference, stored schemas, or general complement completion. No migration or proposal cleanup. Recomposition does not revoke a historical pending proposal; report one as historical if encountered and leave its normal review lifecycle untouched. Do not claim this correction makes such a proposal unreviewable. A policy for reconciling a held outcome with old proposal state is a separate scope decision; this pilot uses disposable state without a prior Assertion proposal.

Use one focused rule and one correction attempt as defined in [Pipeline Improvement](agent/pipeline-improvement.md). Ordinary debugging within that rule is allowed. If the capture cannot demonstrate the same loss, a comparison case disproves the rule, or a new representation or migration becomes necessary, post the counterexample and stop for a scope decision. Do not broaden the rule to make the target pass.
