# HP-4 Event Frame Evaluation

- Feature: [HP-4 Hybrid Event Frame Drafts](2026-09-01-hybrid-event-frame-drafts.md)
- Fixture: `raw/Anthropic–United_States_Department_of_Defense_dispute.pdf`
- Fixture SHA-256: `c63c85796559453acf708dab46a35da36ffed00a408a25275576ba07138e9624`
- Catalog: [HP-4 Event Frame Development Cases](hp4-event-frame-development-v1.json)
- Runtime: local LM Studio with Qwen2.5-14B-Instruct
- Scope: 12 reviewed event-rich paragraphs

## Evaluation operation

`scripts/verify_hp4_event_frames.py` resolves every catalog anchor against one
accepted representation and invokes the public HP-1, HP-2, HP-3, and HP-4
commands. The JSON report checkpoints after each paragraph. It contains the
complete authoritative paragraph, command results, every HP-4 Preview and
stage trace, and every raw Qwen response. The final report also proves that the
accepted canonical Ledger snapshot did not change.

The evaluation catalog describes expected semantic work rather than exact Gold
frames. Counts below therefore describe stage behavior. They are not precision
or recall scores.

## Observed stage results

All 12 catalog paragraphs were attempted.

Two paragraphs stopped before HP-4 because HP-1 produced blocked mention
previews that HP-2 correctly refused to consume. Ten paragraphs reached HP-4.
Their HP-3 parents were blocked because the isolated evaluation did not have a
ReFinED profile. HP-4 correctly retained that diagnostic and performed no work
with ReFinED output.

The ten HP-4 runs produced:

- 38 SourceSegment-local trigger tasks;
- 21 syntactically valid non-abstention model trigger batches;
- 12 explicit trigger abstentions;
- 5 invalid trigger outputs;
- 6 source-mapping rejections after syntactically valid trigger output;
- 27 source-valid EventTriggerDrafts;
- 27 frame tasks;
- 21 source-valid EventFrameDrafts; and
- 6 frame rejections caused by non-unique qualifier literals.

The resulting Preview statuses were two complete, seven partial, and one
blocked. Every invalid or rejected result retained the exact task input, raw
Qwen output, mapping diagnostic, ExtractionTask, ModelRun, and
ExtractionStageTrace. No failed task contributed a partial frame.

Summed public-command elapsed time was 1,313,691 milliseconds for HP-1,
4,038 milliseconds for HP-2, 3,169 milliseconds for HP-3, and 366,079
milliseconds for HP-4. Rebuilding mention interpretation therefore dominated
the end-to-end evaluation time; HP-4 itself took about six minutes across the
ten paragraphs it received.

A second complete replay reproduced the case statuses, diagnostic categories,
27 source-valid triggers, and 21 source-valid frames. Content-derived Preview
and execution IDs changed because each run retained new model-execution
lineage. The semantic stage totals did not change.

## Semantic findings

HP-4 demonstrated useful model work when the task was bounded. It separated the
causal dispute and disinvestment events in HP4-AD-08. It represented explicit
speech, conditional behavior, descriptions, and recommendations separately in
HP4-AD-07. It preserved actual, hypothetical, and recommended modality and
source-literal time qualifiers in successful frames.

The deterministic boundary did important integrity work. It rejected mixed
event-and-abstention responses, translated event labels, non-literal trigger
phrases, repeated trigger literals, and time expressions that did not map to
one unique source range. Those outputs remained inspectable derived evidence
and did not become accepted intelligence.

The evaluation also exposed incomplete semantic coverage. Some accepted
trigger batches contained broad or overlapping triggers. Some frames confused
participants with attribution sources or assigned imprecise open roles. Long
paragraphs supplied as many as 31 candidates to each frame task, even when the
event occurred in one SourceSegment. The local model also omitted explicit
events from dense paragraphs. HP-4 makes these defects visible; it does not
claim that a source-valid frame is semantically correct.

## Responsibility assessment

The basic division of authority held:

- Qwen performed event and role interpretation.
- KoteKomi supplied authoritative text and task-local records.
- KoteKomi constructed all offsets, digests, identities, and Preview records.
- ReFinED evidence was retained as parent lineage but did not influence event
  semantics.
- No proposer output entered accepted Ledger state.

Two jobs remain poorly assigned. Qwen is being asked to reproduce exact trigger
and qualifier characters even though KoteKomi is better at deterministic span
construction. Qwen is also being asked to select roles from an entire-paragraph
candidate catalog when most event arguments are local to the trigger segment.

## Ranked testable hypotheses

1. **Bound the frame candidate catalog.** Give a frame task candidates from the
   trigger SourceSegment plus source-proved HP-2 antecedents. Compare role and
   attribution accuracy against the current all-paragraph catalog, while
   requiring no loss of cross-segment participants.
2. **Propose trigger and qualifier spans deterministically.** Give Qwen stable
   task-local span labels from a broad syntactic or temporal proposer and ask it
   to select and interpret labels instead of copying characters. Compare source
   mapping rejection rates and semantic recall.
3. **Separate qualifier judgment from role assignment.** Run a bounded
   qualifier-selection task only over deterministic time and place candidates.
   Compare the current six qualifier rejections and event-specific qualifier
   accuracy.
4. **Add deterministic overlap evidence for trigger batches.** Preserve both
   broad and narrow model proposals, classify containment explicitly, and test
   a monotonic arbitration policy before suppressing either proposal.
5. **Repair upstream HP-1 protocol reliability independently.** Replay the two
   blocked paragraphs through HP-1 and classify whether prompt protocol,
   output parsing, or mention semantics prevented HP-4 coverage.

These are follow-up experiments. HP-4 stops at reviewable derived event frames
and does not implement their policies.
