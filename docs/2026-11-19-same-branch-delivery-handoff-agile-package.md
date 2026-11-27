# Same-Branch Delivery Handoff Agile Package

- Status: Handoff-01 and Handoff-02 merged; closeout pilot ready
- Program ID: `same-branch-delivery-handoff`
- First deliverable: [Handoff-01, make the current handoff unambiguous](2026-11-19-one-current-pr-handoff.md)
- Predecessors: [same-branch harness pilot (PR #2)](https://github.com/SQLCODE917/KoteKomi/pull/2), [CI verification follow-up (PR #3)](https://github.com/SQLCODE917/KoteKomi/pull/3)

## User Outcome

As a developer coordinating a KoteKomi change, I want to give the implementing agent only a PR link, so it can find the current spec, contribute on that branch, and respond to review without me copying instructions between tools. I still decide what should ship and retain merge control.

## Context and Problem

PR #2 demonstrated explicit spec pinning and a same-branch receipt fixture, but its description still instructed the implementer to merge the spec and open a second PR. PR #3 used the real same-branch receipt path, but the active pin had to supersede the original pin in a comment. The workflow accommodates discovery; finding the authoritative instruction is the fragile part. Fix that before adding dispatch automation.

## Domain Boundaries

| Existing concept | Responsibility |
| --- | --- |
| Agile package | Owns the outcome, slice names, and useful follow-ups. It is not the run log. |
| Leaf TDD and Task Manifest V2 | Define the slice's acceptance, permitted scope, and checks. Acceptance lives here, not in a duplicate PR checklist. |
| PR and its feature branch | Hold one current handoff, subsequent code contributions, and review discussion. GitHub owns merge state. |
| Harness run and receipt | Bind the spec and candidate to the checks actually performed. The harness owns verification and promotion evidence. |

Use those concepts as they exist. Do not add an orchestration database, a second lifecycle, or a manifest schema just to track a handoff.

## How Work Changes

| Discovery | Keep or change the handoff? |
| --- | --- |
| The implementation breaks the current promise | Fix it on the same branch under the same pin; add a regression. PR #3's no-argument verification bug is the example. |
| The same slice needs a changed acceptance contract | Block pickup while deciding. Publish the replacement pin explicitly; do not advance an in-flight run silently. If an already bound TDD changes bytes, use a new revision path and let the harness derive the new task ID. Keep the package slice name and old evidence. A baseline-only refresh repins the manifest without creating a new slice. |
| The discovery has its own outcome and proof | Record it in the package. Open a linked follow-up PR when it is ready to specify. Make it a dependency only if the current slice cannot deliver without it. |

## Planned Slices

### Handoff-01: One current handoff (MVP)

Update the existing [implement-tdd guide](https://github.com/SQLCODE917/KoteKomi/blob/main/docs/agent/implement-tdd-workflow.md), add a small PR template, and add a read-only preflight that consumes the handoff and uses existing Git and harness validation where possible. Keep any code in devtools. Reuse the existing [self-contained communication guide](https://github.com/SQLCODE917/KoteKomi/blob/main/docs/agent/self-contained-communication.md). Preserve the guide’s one-command-at-a-time instructions for humans who are running commands themselves. An implementing agent with a checkout runs the existing commands directly and reports evidence or blockers on the PR, not through a human relay.

The PR description has one current handoff: `ready` or `blocked`, the full spec SHA, the leaf TDD path, and any real prerequisite or blocker. The PR already identifies its branch; don't introduce a second branch field. Draft status is not the readiness signal. Comments propose and explain changes; they do not replace the canonical handoff. Confirm that the authoring path can update the PR description before claiming the workflow eliminates human relay.

Acceptance:
- Starting with just a PR URL and normal repository access, an implementer can find the one ready handoff, resolve its pin on the feature branch, validate the bound TDD and V2 manifest, and use the existing same-branch start command.
- Missing, duplicate, blocked, stale, unreachable, or mismatched input produces a clear stop. The check doesn't infer a pin from the branch tip or search comments for instructions.
- Cheap fixtures prove that an implementation push does not change the pin, a bug fix stays under that pin, and replacing a spec selects only the new handoff while preserving evidence for the old one.
- No changes to the ingestion pipeline, branch protection, or CI architecture. No external agent starts in this slice.

### Handoff-02: Prove it on a real ingestion slice

Select one bounded operator-facing outcome from the active ingestion package with an observable before/after result. Give the implementing agent only the PR URL. Capture pickup, implementation, review, candidate receipt, and the actual checks in the same PR. Verify the merge/promotion evidence separately if the user merges it.

Pass if no one has to relay or reinterpret the handoff outside the PR. If the agent needs clarification, resolve it in the PR and record what the handoff was missing. Don't manufacture a spec change or bug for the live trial; the fixtures cover those branches.

#### Handoff-02 pilot: Hold Incomplete Authorization

[Leaf TDD](2026-11-19-hold-incomplete-authorization.md). This is one reviewed-ingestion correction, not a new extraction experiment or dispatcher.

- **Investigate.** The [prior assessment](2026-11-11-ingestion-improvements-task.md#remaining-failures-and-next-scope-decision) records a truncated DHS authorization proposal that the reviewer rejected. The checked-in capture includes the Event and the original parse. The permitted action, systems, and time attach below the trigger's infinitival complement, not below the selected recipient noun. Treat the assessment as historical until the implementer runs the red regression.
- **Split and check.** (1) Reproduce the exact Event on clean disposable state with the retained capture. (2) Make shared composition hold this unrepresented governed action, with positive and near-miss controls. (3) Carry the same result through packet, review evidence, recomposition, and saved replay. The leaf TDD binds each checkpoint to its code, dependency, and verification.
- **Synthesize.** A packet warning cannot stop proposal creation; the shared composer must own that decision. Showing the full Source paragraph is not the same as binding a complete review evidence range. Preserve identity prerequisites and historical review and proposal records, and verify the hold on fresh reviewed state. Narrow the rule or stop if the controls fail; do not extend the parser or broaden the product claim.
- **Review the pilot.** Record what the planning pass caught, what still required clarification or rework, and planning effort if known. Count manual wakes and copied instructions separately. Record candidate CI in the existing Harness run and link the evidence in the PR. Judge the product by the exact before/after fixture and known-good controls, not by the number of planning steps. Revisit guidance only after observing this handoff.

### Closeout pilot: Report Composition Failure After Capture

[Leaf TDD](2026-11-20-report-composition-failure-after-capture.md). [PR #5](https://github.com/SQLCODE917/KoteKomi/pull/5#issuecomment-7027838794) proved URL-only pickup and exact candidate CI in an existing Harness run, but required a separate closeout prompt. The next ordinary product slice pilots [agent-owned candidate closeout](agent/implement-tdd-workflow.md#candidate-closeout-on-the-same-pr) without a new Harness or dispatcher.

- **Investigate:** The workflow distinguishes a Composition exception from successful capture; the worker and view collapse both to exit code zero.
- **Split and check:** Reproduce with a deterministic post-capture fault, carry the existing fact across the typed worker boundary, then verify truthful terminal status and preserved inspection. The controls are successful Composition (including normal holds), pre-admission failure, and unchanged replay/cancellation.
- **Synthesize:** The terminal signal describes what this live operation achieved; it does not change what the Ledger records as captured. Use an explicit state root to prove retention. Do not expand this into recovery, retry, or new Ledger state.
- **Measure:** Target zero prompts asking the implementer to close out. Record an ordinary review wake or a wake to resume CI as separate events, and state explicitly if the session could not wait. Verify source behavior and delivery separately. The operator still decides to merge.

### Review wake: targeted local pilot

[Leaf TDD](2026-11-20-deliver-targeted-review-wake.md). PR #6 eliminated the separate closeout prompt, but required a review wake. Address only that wake first. Treat GitHub as the durable inbox and target one registered Cline session; do not treat VS Code's current task as an identity. A scoped alert or dry run is not proof that the agent can resume.

### Handoff-03: Make pickup event-driven (conditional)

Start only after Handoff-02 is repeatable without human translation. Use one explicit, authorized ready event; re-read the PR and run preflight before dispatch. One implementation attempt per repository, PR, and spec SHA; duplicate delivery is harmless. Ordinary pushes and bot replies don't trigger another start. A replacement pin must not race an active run. The implementer reports to the same PR and has no merge authority. Defer routing, cross-repo support, and any custom scheduler.

## Evidence and Stop Conditions

Handoff-01 should produce the guide, template, preflight, and focused regressions. Handoff-02 records the live PR and any off-PR intervention. Do not proceed to automation if the canonical handoff cannot be updated, an old run can act on a replacement pin, or the URL-only trial still requires someone to translate instructions. Fix that specific gap before extending the process.
