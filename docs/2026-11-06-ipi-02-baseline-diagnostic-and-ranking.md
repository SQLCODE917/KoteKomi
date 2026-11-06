# IPI-02 Baseline Diagnostic and Cross-Stage Ranking

- Status: Diagnostic record; the operator baseline is still open
- Package: [Intelligence Pipeline Improvement](2026-11-06-intelligence-pipeline-improvement-agile-package.md)
- Revision measured: `7dc9a44`
- Population: IngestionRun `igr_c4b8a09978114e49bb63e8c7df73a005`, 36 paragraphs, 167 Events
- Manifest: [IPI-01 passage manifest](2026-11-06-ipi-01-passage-manifest-and-measurement-protocol.md)

## 1. What this record is

This record compares every Pipeline stage on one stored, human-run ingestion before any code change.
It is the bounded diagnostic the package allows before a production cycle.
It is not the operator's timed baseline.
The operator's baseline adds active review time, waiting time, and corrections for the fixed development and reserved reference statements.

## 2. Method

The diagnostic reads the stored IRA acceptance run and calls the retained deterministic functions:

- `load_paragraph_inputs` for the authoritative paragraph text and stage outputs.
- `build_profile` for mentions, references, grounding, triggers, semantics, and Events.
- `ingested_grounding_candidates` for the review candidates the operator can accept.
- `build_constituent_candidate_inventory`, `select_source_grounded_constituents`, and `role_boundary_ranges` for selection.
- `derive_object_content_completion` and `build_decontextualized_proposition` for composition.
- `construct_inspectable_assertion` for Assertion construction.

No model runs, no writes, and no seeded records.
The permissive review is modelled as the strongest review the operator can perform: accept one eligible candidate inside the selected subject boundary and choose the predicate and classifications.
Objects stay values unless an accepted occurrence exists, which matches what the review workflow can accept today.

## 3. Stage table

Each Event is counted once, at its first blocking stage.

| Stage | Events | Evidence |
| --- | --- | --- |
| Selection boundary gap | 44 | 31 `unterminated_tie`, 11 `unsupported_relation`, 2 `multi_head_ambiguity` |
| No subject role realized | 65 | 41 `selection_empty`, 12 `subject_unavailable`, 10 additionally time-held, 2 additionally object-complement-held |
| No eligible review candidate inside the subject | 20 | 10 also time-held, 4 attribution-ambiguous, 3 otherwise composable, 3 missing-object |
| Composition hold with a candidate present | 25 | 20 `unsupported_time_place`, 3 `object_complement`, 2 `attribution_ambiguous` |
| Assertion construction block | 8 | `missing_object` after a substance-free proposition |
| Composable and reviewable | 5 | `targeted`, `told`, `told`, `sought`, `started` |

Two facts dominate the table.

First, most reference statements cannot reach review at all; their Events stop at selection or at a missing review candidate.
Second, of the 38 Events that do offer a review candidate, 20 are held by one rule: the composer refuses every Event whose trigger head carries a plain `obl` dependent.
Those 20 include 13 Events that already realize both a subject and an object.


## 4. Candidate corrections

Each candidate was measured by a counterfactual run over the same stored population.
A counterfactual changes one rule in the process and reruns the same deterministic path.
Counterfactual counts are mechanism evidence; they select and explain a correction and they never count as usable results or measured effort.

| Candidate | Production change | Events unblocked | Composable and reviewable after the change | Risk |
| --- | --- | --- | --- | --- |
| C1 Trigger-adverb representation | Represent a source-exact trigger-time adjunct as an Assertion `time` qualifier instead of holding the Event | 25 stop holding on `unsupported_time_place` | 12, up from 5 | A new Assertion qualifier needs a focused TDD and counterexamples |
| C2 Noun-phrase boundary completion | Select the single covering candidate when its extra content is the role head's own prepositional complement | 19 leave the selection gap; candidate-bearing Events rise from 38 to 49 | 7, up from 5 | A boundary policy change can widen a name into a clause if the permitted shapes are loose |
| C3 Review-candidate recovery | Accept an anaphoric or appositive subject as a reviewable mention | up to 65 subject-role gaps | unmeasured; the identity would be inferred, not reviewed | Unsafe: it would let the Pipeline choose an identity |
| C1 and C2 together | Both changes | 44 leave their first blocker | 15, up from 5 | Two cycles |

## 5. Ranking and selected correction

C1 outranks C2 for the first cycle for three reasons.

- C1 acts on the largest blocked group that is otherwise ready: 20 of 38 candidate-bearing Events, and 13 of them already realize both roles.
- C1 keeps every decision with the reviewer: it adds meaning the Source states, does not guess an identity, and leaves every unclassifiable adjunct an explicit hold.
- C1 cannot widen a participant boundary, so it cannot silently change who an Assertion is about.

C2 has a larger long-term ceiling but a smaller first-cycle product gain and a boundary-policy risk that needs its own counterexample set.
The counterfactual shows that C2 without C1 yields 7 composable Events, and that C2 becomes much more valuable after C1 exists.
C2 is therefore the first candidate for the second cycle if IPI-03 does not meet the target.

C3 is rejected.
It would let the Pipeline pick an identity the reviewer did not choose, which the package forbids.

## 6. Setup cost

The diagnostic setup used existing typed observability and retained Application Layer functions.
It added no persisted machine-readable product boundary.
Agent effort for this diagnostic and the measurement format stayed inside one working day.
Model calls: zero. New ingestions: zero.

## 7. Limitations

- The population is one Document in one stored run.
- The permissive review models the best decision available to the operator; a reviewer may choose a different candidate.
- Semantic completeness is not assessed here; it is the reviewer's job under the rubric.
- The 41 `selection_empty` Events have no subject or object dependent at all, so no review can complete them; they are outside every bounded correction considered.
