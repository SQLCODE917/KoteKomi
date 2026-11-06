# IPI-04 Evidence: Trigger Time Qualifier

- Status: Implemented; the operator comparison and reserved evaluation remain open
- TDD: [Trigger time qualifier](2026-11-06-ipi-04-trigger-time-qualifier.md)
- Branch: `feature/ipi-intelligence-pipeline-improvement`
- Baseline revision: `7dc9a44`

## 1. Why a second cycle

After cycle 1 the development reference statement R-DEV-04 produced one pending proposed Assertion.
The declared capability route needs at least two additional usable statements, so the cycle limit allowed one more bounded correction.
[The ranking](2026-11-06-ipi-02-baseline-diagnostic-and-ranking.md) still placed the trigger-adverb correction ahead of every alternative: it acts on 20 candidate-bearing Events, 13 of which already realize both roles.
Cycle 1 also raised the value of this correction, because completed noun phrases now reach composition and its time adjunct for the first time.

## 2. The change

The composer no longer holds every Event whose trigger head carries a plain `obl`.
It derives one exact time expression through `trigger_time_qualifier` and carries it as `Assertion.qualifiers.time`.
Every other oblique shape keeps the `unsupported_time_place` hold.

## 3. Development result on the copied stored run

| Step | Command | Observed |
| --- | --- | --- |
| Packet | `review event-packet --event sge_c0ff4b58ad8962717514c9f3` | subject `The  Department  of  Defense`, object `a  policy  on  the  use  of  artificial intelligence`, time qualifier `in  2012`, statement span 127..232 |
| Decision | `review decide ... --candidate-text "Department  of  Defense" --identity-kind organization --identity "new:United States Department of Defense" --predicate established --assertion-type reported_observation --source-authority secondary --attribution-basis direct_document` | review `ecr_3ef7e55debc2ded37e4b8d11`, occurrence `org_d486a90c90d9554d741c244f`, evidence `etg_0eec0b6923cc10dcbd93e8c1` |
| Recomposition | `review recompose ...` | `status: composed`, `assertion_status: proposed`, `ast_12a7c5b54c46490c65606961d2de5c6e`, `qualifiers.time` `in  2012` |
| Replay | `kotekomi-live-replay --paragraph 3 --plain` | `United States Department of Defense → established → a  policy  on  the  use  of  artificial intelligence`, `Review: pending`, `Qualifiers: {"polarity": "affirmed", "modality": "actual", "time": "in  2012"}` |

The development statement R-DEV-01 therefore changes from an unreachable selection gap to one pending proposed Assertion whose content preserves the Source's year.

## 4. Development measures after two cycles

| Reference statement | Baseline | After cycle 1 | After cycle 2 |
| --- | --- | --- | --- |
| R-DEV-01 `established ... in 2012` | selection gap | selection gap resolved, composition hold | pending proposed Assertion with `time` qualifier |
| R-DEV-02 `began developing ... as early as ...` | selection gap | selection gap | selection gap |
| R-DEV-03 `integrated Anthropic's services` | composition hold | composition hold | composes when the reviewer approves; the `Prior to the dispute` frame qualifies |
| R-DEV-04 `criticized Trump's approach ...` | selection gap | pending proposed Assertion | unchanged |
| R-DEV-05 `announced GenAI.mil ...` | no object role | no object role | no object role |
| R-DEV-06, R-DEV-07 AISI statements | not ingested | not ingested | not ingested |

The agent-run development count is two statements with a pending proposed Assertion, not a measured operator result.
The operator's timed baseline and final runs decide the package routes.

## 5. Counterfactual population after both cycles

| Measure | Baseline | Both cycles |
| --- | --- | --- |
| Selection gaps | 44 | 25 |
| Events with a review candidate inside the subject | 38 | 49 |
| Composable propositions | 19 | 50 |
| Composable, reviewable, both roles realized | 5 | 15 |

## 6. Checks

| Check | Result |
| --- | --- |
| `uv run pytest packages/application/tests` | passed |
| `uv run pytest packages/application/tests/test_trigger_time_qualifier.py` | 4 passed |
| Review workflow, operator journey, unsupported complement, recomposition tests | passed |
| `uv run ruff check` and `uv run pyright` on changed files | passed |
| `uv run pytest packages/pipelines/tests` | passed for cycle 1; rerun recorded below when complete |

Not run: whole-tree suite, domain and adapter suites for this increment, any live ingestion or model call, and the operator's timed comparisons.

## 7. Limitations

- Two Documents' statements remain outside the agent's verification; the AISI passages are not ingested.
- The qualifier carries the exact Source text, not a normalized date; a reviewer compares text.
- A time expression that also names an event (`Following the government's actions`) stays a hold.
- One Document supplies the counterfactual population.
