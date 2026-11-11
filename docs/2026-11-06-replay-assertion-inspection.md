# Replay Assertion Inspection

- Status: Accepted for implementation by the operator on 2026-11-06
- Parent: [Ingestion to Reviewed Assertion](2026-11-04-ingestion-to-reviewed-assertion-agile-package.md)

## Outcome and Problem

The operator selects a composed Assertion and inspects its linked source spans, reviewed predicate, review status, and evidence handles.
The operator copies the same intelligence into a compact agent handoff.
The current interactive view and copied summary omit composition despite a persisted, proposed Assertion.
Plain output alone renders a composition footer.

## Flow and Ownership

```text
Ledger + composition files -> Pipeline -> Application inspection projection
                                      -> Textual / plain output / copied summary
```

The filesystem Adapter loads validated composition outcomes and their file digests.
The Pipeline supplies accepted identity names and ProposedChange records from the Ledger.
The Application Layer projects one shared inspection record per composed or held Event.
Presentation formats that record without reconstructing selection or composition.

## Requirements

- AI-01: Composition is an inspection layer separate from the seven canonical extraction phases.
- AI-02: Textual exposes composition through annotation navigation, clicks, and an `a` shortcut.
- AI-03: A composed annotation links the selected subject, the Event trigger, and the object by source coordinates.
- AI-04: The inspector names the reviewed predicate, accepted subject identity, proposed Assertion state, ProposedChange review state, and source/evidence IDs.
- AI-05: Held Events expose their hold reason and Event ID without an Assertion claim.
- AI-06: Plain output and Textual consume the same inspection projection.
- AI-07: Copy includes composition IDs, argument span indices, review handles, and a relative outcome path with its digest.
- AI-08: Copy retains the compact span table and excludes UI geometry and full duplicate Assertion/proposal payloads.
- AI-09: Invalid source bindings, missing Event anchors, and malformed composition outcomes fail explicitly.
- AI-10: Inspection writes no accepted Ledger state and invokes no models.

## Acceptance

- A regression fails on the existing interactive annotation projection because composition is absent.
- Headless Textual tests select composition with `a`, `n`/`p`, and the annotation click path.
- Selected source rendering highlights all three linked spans, including across wrapped rows.
- The inspector distinguishes proposed Assertion state from pending, approved, or rejected proposal review.
- Copy round-trips and resolves its selected Assertion ID with compact file and evidence handles.
- Hiding the composition layer removes its selectable records from view and copy.
- Held composition and extraction-only paragraphs remain inspectable.
- Model-free inspection of the completed operator run exposes `ast_431ca8ef1227f3d9da24431be66dbb2f` and its pending proposal.
- Existing replay, clipboard, composition-store, and cancellation regressions remain green.

## Preservation

The change preserves source text, extraction results, canonical phase order, composition policy, and review decisions.
No new ingestion, model call, acceptance action, or historical evidence rewrite is required.
The operator's visual confirmation remains separate from automated headless verification.

## Verification Record

The initial regression failed on the original projection: it returned no composition annotation.
The implementation passed 117 focused replay, inspection, clipboard, store, startup, cancellation, and R20 ingestion-transition tests.
Whole-tree formatting, lint, and typecheck passed.
The full repository test suite and pinned historical reproduction were not rerun for this presentation change.

Model-free headless inspection used run `igr_c4b8a09978114e49bb63e8c7df73a005`, paragraph 14.
The inspector displayed `United States → started → the 2026 Iran war`, proposed Assertion state, and pending proposal review.
The copied summary resolved the selected Assertion, the proposal and evidence IDs, the three source spans, and the outcome file digest.
The handoff root contains `assertion-inspection-summary.json` and `assertion-inspection.svg` as inspection evidence.
No ingestion, model call, approval, or accepted-state change was performed during this verification.
The operator can reopen the saved run with the supported replay command and press `a`, then `c`.
Replace `<state-root>` with the directory containing the saved run's `kotekomi.db` and `archive/`.

```bash
uv run kotekomi-live-replay --state-root <state-root> --paragraph 14
```
