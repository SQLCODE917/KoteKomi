# IPI-04: Carry a Trigger Time Expression as an Assertion Qualifier

- Status: Implemented for cycle 2
- Deliverable: IPI-04 in the [Intelligence Pipeline Improvement](2026-11-06-intelligence-pipeline-improvement-agile-package.md) package
- Evidence: [IPI-02 ranking](2026-11-06-ipi-02-baseline-diagnostic-and-ranking.md), [IPI-03 evidence](2026-11-06-ipi-03-evidence.md)
- Baseline revision: `7dc9a44`

## 1. User outcome

An operator reviews a sentence whose Event carries a time expression, for example `The Department of Defense established a policy on the use of artificial intelligence in 2012`.
Before this change the packet shows the participants but recomposition holds the Event as `unsupported_time_place`, and the Source's time meaning is lost.
After this change the packet shows the time expression, the reviewed decision's statement evidence covers it, and recomposition proposes an Assertion whose `qualifiers.time` is that exact text.

## 2. Current behaviour and evidence

The composer holds every Event whose trigger head has a plain `obl` dependent.
On the stored population that rule stops 20 of the 38 Events that already offer a review candidate.
Most of those obliques are not time expressions: `over the use of its products`, `with the firms ...`, `for a stay ...`, `According to Semafor`, `as "chaotic"`.
The correction therefore represents the one shape the Assertion can carry and keeps every other shape a typed hold.

## 3. Ownership

`packages/application/trigger_time_qualifier` owns the derivation.
`decontextualization_composition` replaces the blanket hold with the derivation and carries the qualifier on the proposition.
`assertion_construction` writes `qualifiers.time` and includes it in the deterministic Assertion ID.
`packages/pipelines/event_review_workflow` presents the qualifier in the packet and includes it in the statement evidence span.
The Domain Core keeps its current rules; `Assertion.qualifiers` already carries free-form qualifier content.

## 4. Contract

`derive_trigger_time_qualifier(event_id, source_text, tokens, trigger_head_start, trigger_head_end)` returns `TriggerTimeQualifier | None` and raises `TriggerTimeUnsupported`.

1. Zero plain `obl` dependents in the trigger head's sentence returns `None`.
2. More than one plain `obl` dependent raises.
3. The oblique subtree must use only these relations: `case`, `det`, `amod`, `nummod`, `compound`, `flat`, `fixed`, `punct`, `nmod:tmod`, `advmod`.
4. The subtree must contain no `nmod` dependent, which excludes a second prepositional complement such as `in a June 2026 Bloomberg interview about ...`.
5. The subtree must be contiguous in the source text: no token between its first and last character lies outside the subtree.
6. Exactly one `case` dependent must carry a temporal preposition: `in`, `on`, `at`, `since`, `during`, `until`, `after`, `before`, `by`, `from`, `prior`, `as`, `through`, `within`.
7. A preposition other than `prior` requires temporal evidence in the subtree: a four-digit year, a month name, or a temporal noun from the fixed list `year`, `month`, `week`, `day`, `decade`, `century`, `morning`, `afternoon`, `evening`, `night`, `today`, `yesterday`, `tomorrow`, `tonight`, and the four seasons.
8. Trailing punctuation is excluded from the qualifier span.
9. The qualifier range is the exact source slice, and the packet and Assertion use the same range.

`DecontextualizedProposition.adjunct_qualifier` carries the qualifier; a held proposition carries none.
`Assertion.qualifiers.time` carries the exact qualifier text.
The deterministic Assertion ID includes the qualifier text, so two statements that differ only by time cannot share an ID.

## 5. Preserved behaviour

- An Event with no plain oblique is unchanged.
- `obl:unmarked` and other oblique subtypes are unchanged, so the IRA case `the US started the 2026 Iran war` still composes without a qualifier.
- A non-time oblique still holds as `unsupported_time_place`.
- Object completion, attribution, coordination, and reference diagnostics are unchanged.
- Review inputs, decision digests, and acceptance requirements are unchanged.

## 6. Verification

| Check | Command |
| --- | --- |
| Captured year, place, instrumental, and no-plain-oblique cases | `uv run pytest packages/application/tests/test_trigger_time_qualifier.py` |
| Time qualifier reaches the proposition; non-time content still holds | `uv run pytest packages/application/tests/test_decontextualization_composition.py` |
| Application suite | `uv run pytest packages/application/tests` |
| Review workflow, operator journey, and recomposition suites | `uv run pytest packages/pipelines/tests/test_operator_journey.py packages/pipelines/tests/test_operator_journey_stored_case.py packages/pipelines/tests/test_unsupported_complement_hold.py packages/pipelines/tests/test_recompose_command.py` |

The production-path check is one copied stored root: `review event-packet --event sge_c0ff4b58ad8962717514c9f3` shows the time qualifier and a statement span that covers it, `review decide` accepts `Department  of  Defense` as an Organization, `review recompose` reports a proposed Assertion, and saved replay of paragraph 3 prints `time: "in  2012"`.

## 7. Out of scope

- Place expressions and non-time oblique complements.
- Temporal relation semantics beyond the exact expression text.
- Changing what the reviewer must decide.
