# IPI-03 Evidence: Noun-Phrase Boundary Completion

- Status: Implemented; development journey recorded; operator comparison open
- TDD: [Noun-phrase boundary completion](2026-11-06-ipi-03-noun-phrase-boundary-completion.md)
- Branch: `feature/ipi-intelligence-pipeline-improvement`
- Baseline revision: `7dc9a44`

## 1. The change

`source_grounded_selection` now selects the single candidate that covers a role's canonical boundary when that candidate only completes the role's own noun phrase.
The permitted completion is noun-phrase content inside the candidate: determiners, modifiers, compounds, punctuation, and at most one prepositional complement rooted in the boundary.
Relative clauses, appositives, coordination, adverbial material, and a second prepositional complement keep the existing typed gap.

## 2. Why this change

[The IPI-02 ranking](2026-11-06-ipi-02-baseline-diagnostic-and-ranking.md) shows 31 Events stopped by `unterminated_tie` and 19 released by this correction.
The stored run's cause is the `of Defense` complement of `Department`: the boundary policy drops `nmod` content, so the canonical boundary is a prefix of the real name and no candidate equals it.

## 3. Development result on a copied stored run

The verification used a copy of the IRA acceptance state root, so no historical operator evidence changed.
No outcome was seeded; the only writes are the ones the supported review commands perform.

| Step | Command | Observed |
| --- | --- | --- |
| Packet | `uv run kotekomi --config <copy>/kotekomi.toml review event-packet --run igr_c4b8a09978114e49bb63e8c7df73a005 --event sge_e8d444a0222b3344ab28d1d8` | subject `Amodei`, object `Trump's approach to export restrictions on semiconductors`, statement span 1199..1274, hold `assertion_inputs_unavailable` |
| Decision | `review decide ... --candidate-text Amodei --identity-kind actor --identity "new:Dario Amodei" --predicate criticized --assertion-type reported_observation --source-authority secondary --attribution-basis direct_document --reviewer ipi-verification` | review `ecr_b5af559f80bba91064e847c2`, occurrence `act_3c76bef831858faa6edf8624`, evidence `etg_37a5e90e4213ce64b63d729a` |
| Recomposition | `review recompose ...` | `status: composed`, `assertion_status: proposed`, `ast_4c1b2796171b5f39ac8ba82fa5ab2d24` |
| Review queue | `review list --record-type Assertion` | `pcg_5698773a147de157ab3b96c0 | pending | Assertion | ast_4c1b2796171b5f39ac8ba82fa5ab2d24` |
| Replay | `uv run kotekomi-live-replay --state-root <copy> --ingestion-run igr_c4b8a09978114e49bb63e8c7df73a005 --paragraph 5 --plain` | `Dario Amodei → criticized → Trump's approach to export restrictions on semiconductors`, `Assertion state: proposed`, `Review: pending`, evidence `etg_ad0365628c4b4a972ac2ecee`, spans 1199:1205, 1206:1216, 1217:1274 |

Before the change the same Event returned `selection_gap` with no subject, and the operator had no decision to record.
The development reference statement R-DEV-04 therefore changes from not attempted to one pending proposed Assertion.

## 4. Population counterfactual

The same stored population was rerun with the corrected selector.

| Measure | Before | After |
| --- | --- | --- |
| Selection gaps | 44 | 25 |
| Events with a review candidate inside the subject | 38 | 49 |
| Composable propositions | 19 | 22 |
| Composable, reviewable, both roles realized | 5 | 7 |

No previously composable Event lost its outcome.

## 5. Checks

| Check | Result |
| --- | --- |
| `uv run pytest packages/application/tests` | passed |
| `uv run pytest packages/pipelines/tests` | passed |
| `uv run pytest packages/application/tests/test_source_grounded_selection_completion.py` | 9 passed |
| `uv run ruff check` on changed files | passed |
| `uv run pyright` on changed files | 0 errors |

Not run: the domain, adapter, briefing, exporter, and devtools suites for this increment; the whole-tree suite; any live ingestion or model call; the operator's timed development and reserved comparisons.

## 6. Limitations

- The production journey is agent-run on a copied root; the package's operator comparison remains open.
- One Document supplies the captured parses and the counterfactual population.
- The change does not address appositive, coordinated, or anaphoric subjects.
- The `criticized` statement keeps its local name in the Assertion subject; the reviewer supplied the canonical name through the supported command.
