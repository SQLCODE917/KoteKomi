# CEA-1.1 Discrimination Experiment Review Handoff

- Status: Complete evidence handoff
- Experiment: [Competitive Event Attachment Discrimination Experiment](2026-09-18-competitive-event-attachment-discrimination-experiment.md)
- Program: [Competitive Event Attachment Program](2026-09-18-competitive-event-attachment-program.md)
- Model: `qwen2.5-14b-instruct`
- Runtime: LM Studio at `http://127.0.0.1:1234/v1`
- Experimental outcome: `mixed`
- Production integration: `not_activated`

## 1. Review question

KoteKomi has one exact Candidate occurrence and several Event occurrences from one authoritative SourceSegment.

Qwen receives that Candidate and every competing Event at once.

Qwen returns the Event labels to which the Candidate belongs.

CEA-1.1 tested two proposed corrections:

1. Replace argument-like wording with complete-proposition wording.
2. Replace prefix-shaped examples with examples that skip Event labels.

The review question is:

> Did either correction improve exact Candidate-to-Event attachment independently of Event presentation order and without losing protected intelligence?

The experiment answered `no` under its acceptance contract.

The result was not a runtime failure.

The result was a complete, reproducible `mixed` experimental outcome.

## 2. Critical oracle and prompt distinction

The Gold oracle applies a universal character-containment rule.

For Candidate `C` and Event Gold proposition `G`, the Gold edge exists when:

```text
non_whitespace_characters(C) is a nonempty subset of non_whitespace_characters(G)
```

The implementation appears in
[`competitive_event_attachment_stage_local.py`](../packages/pipelines/src/kotekomi_pipelines/competitive_event_attachment_stage_local.py).

The tested scope instruction instead applies a removal test:

> Select the Event when removing the Candidate's exact words would lose source-stated meaning from that retelling.

These are not equivalent tests.

A broad Candidate can contain some words that belong to an Event and other words that do not.

Removing that broad Candidate loses Event meaning, so the scope prompt licenses selection.

The Gold oracle rejects that same Candidate because not every Candidate character belongs to the Event proposition.

This distinction is especially important for the four `NONE` challenge cases.

Those cases do not necessarily contain semantically unrelated text.

They contain exact spans that overreach every individual Gold proposition.

The reviewer must therefore distinguish three possible causes:

- Qwen made the wrong semantic judgment.
- The prompt asked a different question from the oracle.
- The Candidate should have been split before semantic judgment.

## 3. Experimental population

CEA-1.1 first audited the 65 nonexact CEA-1 validation candidates.

That frozen audit reproduced:

- seventeen complete omissions;
- 25 partial under-attachments;
- thirteen Gold-`NONE` false attachments;
- five over-attachments;
- five wrong-set substitutions.

The model replay did not rerun those validation candidates.

KoteKomi selected a development-only challenge set with the same diagnosed failure classes.

The challenge set contains 24 exact Candidate occurrences from four SourceSegments.

It contains seventy Candidate-to-Event cells and 29 Gold-positive edges.

The category inventory is:

| Category | Candidate count |
|---|---:|
| Non-Prefix Gold Set | 6 |
| Governing context | 4 |
| Shared-fragment under-attachment | 4 |
| Gold-`NONE` false attachment | 4 |
| Repeated text | 3 |
| Exact control | 3 |

The four SourceSegments expose these Event inventories:

| Selected Candidates | Event occurrences |
|---:|---|
| 14 | `partnered`, `offered` |
| 7 | `viewed`, `decision to attend …`, `hiring`, `support` |
| 2 | `criticized`, `opposed`, `rescission`, `noted`, `discussions` |
| 1 | `targeted`, `cut`, `agreements`, `avoid` |

This is a deliberately difficult diagnostic sample.

Its aggregate accuracy is not an estimate of production-document accuracy.

The source documents and Gold have also participated in prior development.

CEA-1.1 therefore provides mechanism evidence rather than an independent generalization result.

The 65-case failure audit contains no human-entered Mechanism Labels or review rationales.

The operator approved the deterministic audit, challenge catalog, and Prompt Arm digests.

The causal explanations in this handoff remain hypotheses for review.

## 4. Experimental conditions

CEA-1.1 ran four Prompt Arms.

Each Prompt Arm ran once in source Event order and once in reversed Event order.

The combined arm ran a second time in each order.

| Prompt Arm | Scope wording | Non-prefix examples |
|---|---|---|
| `control` | Original | Original |
| `scope` | Revised | Original |
| `examples` | Original | Revised |
| `combined` | Revised | Revised |

The experiment therefore executed ten conditions.

Each condition judged the same 24 Candidate occurrences.

The experiment executed 240 bounded model tasks.

KoteKomi mapped each task-local label back to the same canonical Event occurrence before evaluation.

Reversing Event order did not change Candidate text, Candidate ranges, Event text, or Event ranges.

## 5. Runtime and execution facts

| Runtime fact | Value |
|---|---|
| Adapter | LM Studio |
| Model | `qwen2.5-14b-instruct` |
| Context limit | 16,384 tokens |
| Temperature | `0` |
| Seed | `17` |
| Runtime timeout | 300 seconds |
| Task output cap | 7, 11, or 13 tokens, based on finite label inventory |
| Model executions | 240 |
| Model failures | 0 |
| Context-budget blocks | 0 |
| Invalid finite outputs | 3 |
| KoteKomi preflight formatted-input tokens | 250,454 |
| LM Studio response-usage input tokens | 65,142 |
| LM Studio response-usage output tokens | 557 |
| Summed model elapsed time | 791,793 ms |
| Median model elapsed time | 2,124 ms |
| Maximum model elapsed time | 19,226 ms |
| Median first response event | 24 ms |

KoteKomi records preflight token measurement and LM Studio response usage separately.

The two token totals are observations from different boundaries and are not treated as equal.

No execution hung or reached the timeout.

Every condition retained source validity `1.0` and Gold coverage `1.0`.

The experiment created zero ProposedChanges and zero accepted Ledger writes.

## 6. Exact prompts

### 6.1 Control Prompt Arm

Prompt file:
[`competitive_event_attachment_v1.md`](../prompts/competitive_event_attachment_v1.md)

Prompt SHA-256:
`25976366bcd7bd04749097a580cc6474108f5341846777e6d58cc63cfe84e491`

```text
Read one passage containing one Candidate occurrence and several Event options.

The Candidate is the exact text between `<candidate>` and `</candidate>`.
Each labeled Event option marks both that same Candidate occurrence and one Event between `<event>` and `</event>`.
When those ranges cross, the option shows separate Candidate and Event views of the same passage.

For each Event, consider the complete fact centered on the marked Event words.
Select the Event when the Candidate supplies part of that fact: a participant, affected thing, time, place, attribution, negation, uncertainty, purpose, comparison, or necessary clause content.
Follow grammatical references such as pronouns, descriptions, and relative clauses.
An introductory time phrase or connector applies only to the clauses it actually links.
Do not select an Event merely because the Candidate is nearby or appears in the same sentence.
Select every applicable Event; the Candidate may belong to no Event, one Event, or several Events.

Example 1:

Source: `During the hearing, Alex criticized Plan A and opposed Plan B.`
Candidate: `Alex`
E1 Event: `criticized`
E2 Event: `opposed`
Answer: `E1,E2`

Example 2:

Source: `During the hearing, Alex criticized Plan A and opposed Plan B.`
Candidate: `Plan A`
E1 Event: `criticized`
E2 Event: `opposed`
Answer: `E1`

Example 3:

Source: `Ravi viewed the delay as evidence that Orion would miss its deadline.`
Candidate: `Ravi`
E1 Event: `viewed`
E2 Event: `miss`
Answer: `E1,E2`

Example 4:

Source: `[7] Acme launched Nova.`
Candidate: `[7]`
E1 Event: `launched`
Answer: `NONE`

Example 5:

Source: `While the agency investigated suppliers, Lee left the suppliers Northstar and Bayview, which settled with the agency to avoid penalties.`
Candidate: `Northstar and Bayview`
E1 Event: `investigated`
E2 Event: `left`
E3 Event: `settled`
E4 Event: `avoid`
Answer: `E1,E2,E3,E4`

Example 6:

Source: `As Mira testified, Rowan took notes, which Rowan filed the next day.`
Candidate: `As`
E1 Event: `testified`
E2 Event: `took`
E3 Event: `filed`
Answer: `E1,E2`

Example 7:

Source: `Mira rejected Northstar's claims, intensifying their dispute.`
Candidate: `Northstar`
E1 Event: `rejected`
E2 Event: `intensifying`
Answer: `E1,E2`

Return `NONE` when the Candidate belongs to no listed Event.
Return `UNCLEAR` when the passage does not decide which listed Events the Candidate belongs to.
Otherwise return only the applicable Event labels, separated by commas and in the order supplied, such as `E1,E3`.
Do not add an explanation.
```

### 6.2 Scope Prompt Arm

Prompt file:
[`competitive_event_attachment_scope_v2.md`](../prompts/competitive_event_attachment_scope_v2.md)

Prompt SHA-256:
`775469bb9e30d285729c9a125e37c6ebc89bab62c252d4648a8d24accf157795`

The scope arm changes only the two original scope sentences.

It replaces them with these three sentences:

```text
For each Event, consider a complete retelling of the source-stated fact centered on the marked Event words.
Select the Event when removing the Candidate's exact words would lose source-stated meaning from that retelling.
The Candidate can supply a participant, affected thing, time, place, attribution, modality, negation, purpose, comparison, necessary clause content, or framing that introduces or contains the Event.
```

Every other line remains identical to the control prompt.

### 6.3 Examples Prompt Arm

Prompt file:
[`competitive_event_attachment_examples_v2.md`](../prompts/competitive_event_attachment_examples_v2.md)

Prompt SHA-256:
`a9bf5db66cd0d281d1a62c1789bd3742222b1551d8f33d1bba0e3a52724dbd2a`

The examples arm retains the control instructions.

It replaces Examples 2, 3, and 5 with these non-prefix answers:

```text
Example 2:

Source: `During the hearing, Alex criticized Plan A and Riley opposed Plan B.`
Candidate: `Plan B`
E1 Event: `criticized`
E2 Event: `opposed`
Answer: `E2`

Example 3:

Source: `Alex criticized Plan A, Riley opposed Plan B, and Alex endorsed Plan C.`
Candidate: `Alex`
E1 Event: `criticized`
E2 Event: `opposed`
E3 Event: `endorsed`
Answer: `E1,E3`

Example 5:

Source: `Lena arrived, Omar criticized Plan A, Mira departed, and Omar praised Plan B.`
Candidate: `Omar`
E1 Event: `arrived`
E2 Event: `criticized`
E3 Event: `departed`
E4 Event: `praised`
Answer: `E2,E4`
```

Every other line remains identical to the control prompt.

### 6.4 Combined Prompt Arm

Prompt file:
[`competitive_event_attachment_combined_v2.md`](../prompts/competitive_event_attachment_combined_v2.md)

Prompt SHA-256:
`c9f3ceb26cf70fade570744231cb6872015ab22a3b9eeb87ef371fb3628e5ab5`

The combined arm applies both exact changes above.

### 6.5 Per-task rendering

KoteKomi appends one finite output instruction derived from the supplied Event labels.

For a four-Event task, it is:

```text
Return exactly NONE, UNCLEAR, or a comma-separated subset of these Event labels in supplied order: E1,E2,E3,E4. Surrounding ASCII whitespace is framing only.
```

KoteKomi then supplies the authoritative SourceSegment, the marked Candidate occurrence, and one marked copy per Event option.

Qwen never receives canonical Event IDs or source offsets.

## 7. Aggregate results

Exact Set is the primary metric.

It requires the predicted canonical Event set to equal the Gold set exactly.

Jaccard gives partial credit for overlap.

Hamming scores every Candidate-to-Event cell.

Lower Hamming is better.

| Arm | Order | Exact Set | Mean Jaccard | Hamming | Edge precision | Edge recall | Gold-`NONE` correct | Invalid |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Control | Source | 10/24 | 0.5972 | 0.3143 | 0.6061 | 0.6897 | 0/4 | 0 |
| Control | Reversed | 10/24 | 0.5694 | 0.2714 | 0.7083 | 0.5862 | 1/4 | 2 |
| Scope | Source | 10/24 | 0.5347 | 0.3286 | 0.6071 | 0.5862 | 0/4 | 0 |
| Scope | Reversed | 13/24 | 0.6736 | 0.2286 | 0.7241 | 0.7241 | 2/4 | 0 |
| Examples | Source | 10/24 | 0.5833 | 0.2857 | 0.6552 | 0.6552 | 0/4 | 0 |
| Examples | Reversed | 10/24 | 0.5417 | 0.3143 | 0.6400 | 0.5517 | 1/4 | 1 |
| Combined | Source | 10/24 | 0.5208 | 0.3000 | 0.7000 | 0.4828 | 1/4 | 0 |
| Combined | Reversed | 11/24 | 0.5903 | 0.2571 | 0.7200 | 0.6207 | 1/4 | 0 |

The combined-arm second repetitions exactly reproduced both semantic result fingerprints.

That repeatability does not remove the source-versus-reversed disagreement.

### 7.1 Outcome gates

| Gate | Result |
|---|---|
| Combined repeat stable | Passed |
| Exact accuracy improved in both orders | Failed |
| Jaccard improved in both orders | Failed |
| Hamming reduced in both orders | Passed |
| Order sensitivity reduced | Failed |
| Sibling leakage not increased | Passed |
| Protected recall preserved | Failed |
| Gold-`NONE` accuracy preserved | Passed |
| Scope factor improved its declared mechanism | Failed |
| Examples factor improved its declared mechanism | Failed |
| All production safety gates | Failed |

The final classifier therefore returned `mixed`.

### 7.2 Edge confusion counts

Every condition scores the same 29 Gold-positive and 41 Gold-negative cells.

| Arm | Order | TP | FP | FN | TN |
|---|---|---:|---:|---:|---:|
| Control | Source | 20 | 13 | 9 | 28 |
| Control | Reversed | 17 | 7 | 12 | 34 |
| Scope | Source | 17 | 11 | 12 | 30 |
| Scope | Reversed | 21 | 8 | 8 | 33 |
| Examples | Source | 19 | 10 | 10 | 31 |
| Examples | Reversed | 16 | 9 | 13 | 32 |
| Combined | Source | 14 | 6 | 15 | 35 |
| Combined | Reversed | 18 | 7 | 11 | 34 |

The combined source-order arm reduced cell errors from 22 to 21.

It did so by removing seven false positives while adding six false negatives.

It retained six fewer Gold edges than the control source-order arm.

The Hamming improvement therefore hides a material recall tradeoff.

### 7.3 Order sensitivity

Order-Sensitive Candidate counts compare canonical Event sets after label mapping.

| Prompt Arm | Order-Sensitive Candidates |
|---|---:|
| Control | 7/24 |
| Scope | 9/24 |
| Examples | 6/24 |
| Combined | 8/24 |

The scope-only arm produced the best single condition in reversed order.

The same arm produced worse Hamming and Jaccard than control in source order.

The scope correction therefore increased rather than reduced order sensitivity.

### 7.4 Protected intelligence

| Arm | Order | Entity edges | Qualification edges | Governing edges | Shared edges |
|---|---|---:|---:|---:|---:|
| Control | Source | 8/12 | 5/11 | 12/19 | 9/18 |
| Control | Reversed | 6/12 | 4/11 | 10/19 | 7/18 |
| Scope | Source | 4/12 | 2/11 | 11/19 | 7/18 |
| Scope | Reversed | 8/12 | 7/11 | 14/19 | 11/18 |
| Examples | Source | 7/12 | 4/11 | 12/19 | 9/18 |
| Examples | Reversed | 5/12 | 3/11 | 10/19 | 7/18 |
| Combined | Source | 4/12 | 0/11 | 8/19 | 5/18 |
| Combined | Reversed | 6/12 | 4/11 | 12/19 | 9/18 |

The combined source-order arm lost every protected qualification edge in the selected catalog.

This regression is why reduced over-selection could not justify promotion.

### 7.5 Category exactness

Each value is exact Candidate count over category size.

| Arm / order | Non-prefix | Governing | Shared | Gold-`NONE` | Repeated | Controls |
|---|---:|---:|---:|---:|---:|---:|
| Control / source | 6/6 | 0/4 | 0/4 | 0/4 | 1/3 | 3/3 |
| Control / reversed | 5/6 | 0/4 | 0/4 | 1/4 | 1/3 | 3/3 |
| Scope / source | 6/6 | 0/4 | 0/4 | 0/4 | 1/3 | 3/3 |
| Scope / reversed | 5/6 | 0/4 | 2/4 | 2/4 | 1/3 | 3/3 |
| Examples / source | 6/6 | 0/4 | 0/4 | 0/4 | 1/3 | 3/3 |
| Examples / reversed | 5/6 | 0/4 | 0/4 | 1/4 | 1/3 | 3/3 |
| Combined / source | 6/6 | 0/4 | 0/4 | 1/4 | 1/3 | 2/3 |
| Combined / reversed | 5/6 | 0/4 | 1/4 | 1/4 | 1/3 | 3/3 |

Five of six Non-Prefix candidates were exact in all eight first-repetition conditions.

The examples factor therefore targeted a mostly solved behavior.

All four governing-context candidates failed in every condition.

Ten of 24 Candidates were never exact under any Prompt Arm or Event Order.

Those ten comprise every governing-context Candidate, two Gold-`NONE` Candidates, two repeated-text Candidates, and two shared-fragment Candidates.

Eight of 24 Candidates were exact in all eight conditions.

## 8. Representative exact cases

### 8.1 Qualification attachment changes under Event reordering

Candidate ID: `cac_f7f62d6442199cb59cac803b`

Category: `non_prefix_gold`

Source:

> By November 2024, Anthropic had already partnered with Palantir and Amazon Web Services, companies that offered services with FedRAMP authorization.

Candidate:

> with FedRAMP authorization

Gold canonical Event set:

```text
offered
```

Control source-order task:

```text
E1 Event: partnered
E2 Event: offered
Qwen raw output: E2
Canonical result: offered
Evaluation: exact
```

Control reversed-order task:

```text
E1 Event: offered
E2 Event: partnered
Qwen raw output: NONE
Canonical result: NONE
Evaluation: missing offered
```

Every Prompt Arm showed this same source-order success and reversed-order omission.

The source characters, Candidate, and Event occurrences did not change.

Only Event presentation order and task labels changed.

### 8.2 Governing context fails under every condition

Candidate ID: `cac_3821932407c6229384a9a4b4`

Category: `governing_context`

Source:

> By November 2024, Anthropic had already partnered with Palantir and Amazon Web Services, companies that offered services with FedRAMP authorization.

Candidate:

> Palantir

Gold canonical Event set:

```text
partnered
offered
```

Source-order task:

```text
E1 Event: partnered
E2 Event: offered
Qwen raw output: E1
Canonical result: partnered
```

Reversed-order task:

```text
E1 Event: offered
E2 Event: partnered
Qwen raw output: E2
Canonical result: partnered
```

All four Prompt Arms retained only `partnered` in both orders.

The missing edge depends on resolving `companies` to Palantir and Amazon Web Services through the appositive-relative-clause structure.

Prompt wording and non-prefix examples did not recover it.

### 8.3 Repeated surface text attaches to the wrong occurrence

Candidate ID: `cac_6825eb0cc2fb0a7d7bae7e7f`

Category: `repeated_text`

Source:

> Sacks viewed Amodei's decision to attend the World Economic Forum over Trump's second inauguration; his hiring of Biden officials; and Anthropic's association with the philanthropic initiative Open Philanthropy as evidence that Anthropic would not support Trump's agenda.

Candidate:

> the first `Anthropic`, in `Anthropic's association`

Gold canonical Event set:

```text
viewed
```

The second `Anthropic` is the subject of `support`.

Control source-order raw output:

```text
E1,E4
```

Control canonical result:

```text
viewed
support
```

Combined source-order raw output:

```text
E4
```

Combined canonical result:

```text
support
```

Combined reversed-order raw output:

```text
E1
```

Combined reversed canonical result:

```text
support
```

The Candidate markers identify the first occurrence exactly.

The combined prompt nevertheless selected only the Event governed by the second equal string.

### 8.4 Shared framing flips from wrong substitution to exact

Candidate ID: `cac_4151631c11848327dd1150c8`

Category: `shared_under_attachment`

Source:

> Sacks viewed Amodei's decision to attend the World Economic Forum over Trump's second inauguration; his hiring of Biden officials; and Anthropic's association with the philanthropic initiative Open Philanthropy as evidence that Anthropic would not support Trump's agenda.

Candidate:

> his

Gold canonical Event set:

```text
hiring
viewed
```

Scope source-order task and output:

```text
E1 Event: viewed
E2 Event: decision to attend …
E3 Event: hiring
E4 Event: support
Qwen raw output: E3,E4
Canonical result: hiring, support
Evaluation: wrong-set substitution
```

Scope reversed-order task and output:

```text
E1 Event: support
E2 Event: hiring
E3 Event: decision to attend …
E4 Event: viewed
Qwen raw output: E2,E4
Canonical result: hiring, viewed
Evaluation: exact
```

This single case illustrates why the best reversed-order aggregate cannot establish a stable semantic policy.

### 8.5 A broad Candidate exposes the oracle-task mismatch

Candidate ID: `cac_558eeee91aaeab31fbc9b57f`

Category: `none_false_positive`

Source:

> By November 2024, Anthropic had already partnered with Palantir and Amazon Web Services, companies that offered services with FedRAMP authorization.

Candidate:

> with Palantir and Amazon Web Services, companies that offered services with FedRAMP authorization

Gold canonical Event set:

```text
NONE
```

All eight first-repetition conditions selected only `partnered`.

The model's answer is understandable under both tested prompts.

The Candidate contains the complete complement of `partnered`.

The Candidate also crosses into the separate `offered` proposition.

The Gold oracle therefore rejects the whole Candidate for every individual Event.

This result can indicate Candidate overbreadth or prompt-oracle mismatch rather than a simple semantic hallucination.

### 8.6 The scope correction can reject one broad Candidate

Candidate ID: `cac_64717b1eca3810289d389cd2`

Category: `none_false_positive`

Source:

> As the Trump administration targeted law firms, Amodei cut ties with the firms Skadden, Arps, Slate, Meagher & Flom and Latham & Watkins, which reached agreements with the Trump administration to avoid punishment.

Candidate:

> with the firms Skadden, Arps, Slate, Meagher & Flom and Latham & Watkins, which reached agreements with the Trump administration to avoid punishment

Gold canonical Event set:

```text
NONE
```

Control source-order raw output:

```text
E2,E3,E4
```

Control canonical result:

```text
cut
agreements
avoid
```

Combined source-order raw output:

```text
NONE
```

Combined reversed-order raw output:

```text
NONE
```

This is a real improvement for one broad Candidate.

The same correction did not generalize to the preceding broad Candidate or preserve protected recall.

### 8.7 Non-prefix selection already works

Candidate ID: `cac_c951a89058bae19cd89503b1`

Category: `non_prefix_gold`

Source:

> By November 2024, Anthropic had already partnered with Palantir and Amazon Web Services, companies that offered services with FedRAMP authorization.

Candidate:

> offered

Gold canonical Event set:

```text
offered
```

Every Prompt Arm returned `E2` in source order and `E1` in reversed order.

Every result mapped to the same canonical `offered` Event.

This case and five consistently exact Non-Prefix cases weaken the original prefix-shortcut hypothesis.

### 8.8 Three invalid outputs were ordering violations

The reversed finite contract required labels in supplied order.

Qwen returned `E2,E1` three times.

KoteKomi preserved each raw output and classified it as `invalid_output`.

No prose, unknown label, or malformed JSON caused these failures.

For Candidate `his`, `E2,E1` would map to `hiring,support` if treated as an unordered set.

That semantic set is still wrong against Gold `hiring,viewed`.

Permissive sorting would remove the format failure but would not solve that attachment error.

## 9. What the result establishes

The result establishes these facts for this challenge set and pinned runtime:

- Qwen can return exact non-prefix label sets.
- Adding non-prefix examples does not solve the remaining error classes.
- Complete-proposition wording can improve one Event order and regress the other.
- Event presentation order changes canonical semantic results after correct label mapping.
- Governing-context attachment is not recovered by either tested prompt factor.
- Candidate markers do not reliably prevent equal-string occurrence confusion.
- The combined correction becomes more conservative in source order.
- That conservatism reduces false positives while losing more Gold edges.
- Repeating the combined conditions reproduces the same order-dependent results.
- No tested arm is safe to activate in production.

## 10. What the result does not establish

The result does not establish general Qwen2.5 extraction accuracy.

The result does not use an independently held-out corpus.

The result does not compare another language model.

The result does not compare an Event-major task.

The result does not compare one-target binary judgments with multi-label generation.

The result does not supply syntax or coreference evidence to Qwen.

The result does not prove that every Gold-`NONE` judgment expresses the clearest semantic task.

The result does not prove that Event order is the only cause of attachment error.

The result does not authorize a production Prompt Arm.

## 11. Questions for a second reviewer

1. Does the universal whole-Candidate Gold rule define the desired intelligence boundary?
2. Does the removal-based scope prompt ask an existential question that conflicts with that Gold rule?
3. Should overreaching Candidates be split before semantic attachment rather than scored as Gold `NONE`?
4. Should one task judge one targeted Event while still showing sibling Events as contrast?
5. Would a `WHOLE`, `PARTIAL`, `NONE`, `UNCLEAR` contract expose Candidate overbreadth directly?
6. Should an Event-major transpose ask which Candidates a standalone Event proposition requires?
7. Should syntax or resolved-reference paths deterministically route governing-context cases before Qwen?
8. Should distinct valid Event labels be parsed as an unordered set while preserving an output-order diagnostic?
9. Does the four-SourceSegment challenge set contain enough linguistic variety for the next decision?
10. Which next experiment best separates model limitations from task-contract and Candidate-construction defects?

## 12. Current recommended bounded successor

The current recommendation is a target-conditioned competitive judgment.

KoteKomi would supply:

- one exact Candidate occurrence;
- one explicit Target Event;
- every sibling Event as contrast;
- the exact authoritative SourceSegment.

Qwen would return one task-local answer:

```text
WHOLE
PARTIAL
NONE
UNCLEAR
```

`WHOLE` would mean every meaningful Candidate word belongs to the Target Event proposition.

`PARTIAL` would mean only part of the Candidate belongs and Candidate splitting may be required.

`NONE` would mean no Candidate meaning belongs to the Target Event proposition.

`UNCLEAR` would preserve unresolved semantic evidence.

KoteKomi would construct all IDs, mappings, edges, diagnostics, and evaluation records.

The same 24-candidate catalog and both Event Orders can test this decomposition without creating new Gold.

This recommendation remains a hypothesis.

CEA-1.1 did not test it.

## 13. Integrity references

| Record | SHA-256 |
|---|---|
| Failure audit | `4e441053e284eab68787b5b96dee91122a9b6da80ac2640b789d3bc5e170b997` |
| Development catalog | `47e13a7cee16b35e8a6222854305a3da6033010a909733716dc655746ba98640` |
| Prompt manifest | `8655178c41e41bdba5028bacfdd5a8ad767f5cfc1892ad33d06a9f23cccf73a3` |
| Operator approval | `784ec392275a63a13d3233a5bf0877ebf0afe7bcb357eb0c8cb825ec1ed231af` |
| Final comparison | `6f09dd6bb92ec7e8eb775495300914df61e9210243a144db82ead2caa88a71fa` |

The local validated records are under:

```text
/private/tmp/kotekomi-cea11-discrimination-20260918
```

The exact final comparison is:

```text
/private/tmp/kotekomi-cea11-discrimination-20260918/comparison.json
```

The human-readable final comparison is:

```text
/private/tmp/kotekomi-cea11-discrimination-20260918/comparison-review.md
```
