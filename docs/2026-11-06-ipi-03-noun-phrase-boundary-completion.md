# IPI-03: Complete a Noun-Phrase Boundary from One Covering Candidate

- Status: Proposed for review
- Deliverable: IPI-03 in the [Intelligence Pipeline Improvement](2026-11-06-intelligence-pipeline-improvement-agile-package.md) package
- Evidence: [IPI-02 baseline diagnostic](2026-11-06-ipi-02-baseline-diagnostic-and-ranking.md)
- Baseline revision: `7dc9a44`

## 1. User outcome

An operator opens the review packet for a sentence whose subject is a full organization name.
The name carries a prepositional complement, for example `the United States Department of Defense`.
Today the packet shows no subject and the Event holds as `selection_gap`, so the operator cannot record any decision.
After this change the packet shows the complete name, the operator records the decision, and explicit recomposition proposes a pending Assertion whose subject is that organization.

## 2. Current behaviour and evidence

The deterministic selector reduces each content role to a canonical boundary.
It then looks for one candidate constituent that equals that boundary.
When no candidate is equal, but exactly one candidate covers the boundary, the selector raises `unterminated_tie`, and the whole selection becomes `selection_gap`.

On the stored IRA acceptance run this single rule stops 31 of 167 Events, and 19 of them become reviewable when the rule is corrected.
The cause is visible in the parse.
The subject head `Department` carries `Defense` as an `nmod` dependent with the preposition `of`.
The canonical-boundary policy treats `nmod` as optional content, so the boundary stops at `Department` and excludes `of Defense`.
The only covering candidate is `the United States Department of Defense`, which is the correct complete name.

## 3. Ownership

`packages/application/source_grounded_selection` owns the boundary policy and the candidate choice.
`packages/application/source_grounded_reference_composition` and `packages/application/decontextualization_composition` consume the selected boundary unchanged.
`packages/pipelines/event_review_workflow` presents the boundary in the packet and passes it into composition.
The Domain Core keeps its current Assertion and EvidenceTarget rules.

## 4. Contract change

Inside one role reduction, when no candidate equals the canonical boundary:

1. The selector collects every candidate that contains the role head and excludes the trigger head, exactly as today.
2. The selector keeps the candidates that cover the canonical boundary.
3. The selector selects that candidate only when exactly one candidate covers the boundary and every token of that candidate outside the boundary is part of one contiguous prepositional-complement subtree of the role head.
4. A token belongs to that subtree when its nearest ancestor inside the candidate is a direct dependent of the role head with relation `nmod`, or when it is that dependent, or when it is the `case` token of that dependent, or when it is a descendant of one of those tokens through the relations `case`, `det`, `amod`, `compound`, `flat`, `nummod`, `punct`, `fixed`, `nmod`, `dep`.
5. The selected boundary becomes the candidate's exact range, and the selector returns it as the canonical boundary of that conjunct.
6. In every other case the selector raises the existing typed gap without selecting a candidate.

The permitted shape is a name with its own prepositional complement.
Any relative clause, appositive, coordination, adverbial modifier, or clause complement leaves the shape outside the permitted set, and the Event keeps its typed hold.

## 5. Preserved behaviour

- A candidate equal to the boundary is still selected first and is unchanged.
- Two covering candidates still produce `unterminated_tie`.
- A role with no covering candidate still produces `no_covering_candidate`.
- An unsupported direct dependent on the role head still produces `unsupported_relation`.
- Composition, Assertion construction, review, proposal persistence, evidence, and replay use the selected boundary with no special case.

## 6. Verification

| Check | Command |
| --- | --- |
| Captured positive parse selects the complete name | `uv run pytest packages/application/tests/test_source_grounded_selection_completion.py` |
| Relative clause, appositive, coordination, two-covering-candidate, and non-complement extras stay typed gaps | same file |
| Composition accepts the completed boundary and builds the Assertion | `uv run pytest packages/application/tests/test_source_grounded_composition.py packages/application/tests/test_decontextualization_composition.py` |
| Review packet and recomposition carry the completed boundary | `uv run pytest packages/pipelines/tests/test_event_review_workflow.py` |
| Existing selection and composition contracts still pass | `uv run pytest packages/application/tests packages/pipelines/tests` |

The production-path check is one copied stored state root, one `review event-packet`, one `review decide`, one `review recompose`, and one saved replay.
It uses no seeded accepted record and no expected Assertion written by hand.

## 7. Out of scope

- Appositive and coordinated subjects.
- Anaphoric subjects.
- Trigger time and place adjuncts.
- Any change to review decision inputs.
- Any change to candidate generation or grounding.

## 8. Stop condition

The change ships when the captured positive case composes, the counterexamples stay typed holds, the whole suite passes, and the copied stored run produces one pending Assertion for the selected development statement.
If the copied run does not produce that Assertion, the change is reverted and the next candidate from the IPI-02 table is considered.
