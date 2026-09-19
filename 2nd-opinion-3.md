## The headline finding is right, and it's bigger than you've stated

You've got it: universal (`∀ chars of C ∈ G`) versus existential (`removing C loses meaning`). But the consequence is stronger than a prompt/oracle mismatch.

Under the containment oracle, **the gold label for a candidate is a property of your segmentation, not of the language.** Take `Palantir` and grow the span leftward to `with Palantir and Amazon Web Services, companies that offered services with FedRAMP authorization`. Nothing about the sentence changed. The gold flips from `{partnered, offered}` to `NONE`. The model's answer (`partnered`) is linguistically correct in both cases and is scored correct in one and wrong in the other.

That is why no prompt rewrite touched the `NONE` category. You are asking the model a question about language and grading it against a question about span arithmetic. Eight prompt conditions can't close that gap, and §8.5 is you documenting exactly this.

The follow-on: 13 of your 65 CEA-1 failures are Gold-`NONE` false attachments, and some share of the 25 partial under-attachments have the same cause. Your true model error rate is meaningfully lower than 65/179. You've been optimizing against a partly artifactual target.

## The arm comparison is statistically empty

24 candidates. At p≈0.45 the binomial SE is ±10 points; one candidate is 4.2 points. Control 10/24 versus scope-reversed 13/24 is three items. Edge metrics are better but not much: 29 gold-positive cells, and your best-versus-worst TP spread is 14 to 21.

Then you gated on eight conjunctive criteria, most of them "improved in both orders." If each is roughly a coin flip on noise, P(all pass) is under 1%. The `mixed` verdict was close to predetermined by the design, independent of whether the corrections work.

The report's line that this "falsifies prompt wording and example balance as sufficient corrections" overclaims. What you have is: no large effect, on a small, previously-seen, deliberately-hard sample, with 14 of 24 candidates drawn from a single sentence. Four SourceSegments and one dominant sentence means your effective n for anything sentence-structural is closer to 4 than 24.

One thing the design *does* measure well is order sensitivity, because that's a paired within-item comparison. 7–9 of 24 flipping is a real result.

## A confound in the examples arm

CEA11-PRM-03 says the arm changes only the examples. It changed two things.

Original answer cardinalities: 2, 1, 2, 0, **4**, 2, 2. Revised: 2, 1, 2, 0, **2**, 2, 2. Replacing Example 5 (`E1,E2,E3,E4`) with `E2,E4` removed skip-shape *and* dropped the maximum demonstrated set size from four to two.

Combined/source then produced your most conservative condition: TP 14, FP 6, edge recall 0.4828 against control's 0.6897, and 0/11 qualification edges. The recall collapse tracks the cardinality prior, not the skip-shape manipulation. You measured "fewer labels demonstrated → fewer labels emitted," which is a well-known in-context effect and not the hypothesis you registered.

If you rerun this factor, hold cardinality fixed: include a skip example with four labels out of six options.

Related: §8.7 and the 6/6 non-prefix scores show the prefix-shortcut hypothesis from the last round was mostly wrong. Fair enough — that's what the arm was for. Good null.

## Governing context is 0/4 in all eight conditions, and it's solvable without the model

This is the cleanest signal in the experiment, and I don't think it's a model-capability problem.

`Palantir` → `offered` requires: `Palantir` is conjoined/appositive with `companies`; `companies` heads an `acl:relcl` whose predicate is `offered`; `that` is `nsubj` of `offered`. Stanza gives you every link.

Same shape elsewhere in your data:
- `wrote` → `describing`: `describing` is `acl` on `op-ed`, `op-ed` is `obj` of `wrote`.
- `his` → `viewed` (§8.4): `his` is `nmod:poss` of `hiring`; `hiring` is a `conj` item under the object of `viewed`. Qwen got the local edge right and lifted to `support` instead of `viewed`. The parse says `viewed`.

Your gold's governing edges look like a transitive closure over a specific relation set (`acl`, `acl:relcl`, `ccomp`, `xcomp`, `obj`+`appos`/`conj`). If that's true, they're computable.

**The experiment I'd run before anything else costs zero model calls.** Define `G' = trigger subtree ∪ lifted governors` from Stanza, apply your containment rule, and score the derived matrix against all 179 validation candidates and 40 gold events. You already have everything needed. If `G'` reproduces 85%+ of gold edges, your architecture inverts: syntax decides the matrix, Qwen adjudicates only the residue. If it reproduces 60%, you know which relation types leak and you've localized the semantic work precisely.

§10 notes you deliberately withhold syntax and coreference from Qwen. That was the right call for a clean prompt experiment. It is the wrong call for the pipeline, and it's why the same four cases fail eight times.

## Candidate splitting is deterministic; don't spend a model call on it

Your §12 successor (`WHOLE`/`PARTIAL`/`NONE`/`UNCLEAR`) correctly identifies overbreadth as the missing distinction. But it asks the model to detect something your trigger inventory already tells you:

> A candidate span containing an approved Event trigger other than its own head is overbroad. Split at the trigger before judgment.

Apply that to §8.5 and §8.6: both candidates contain `offered` / `agreements`+`avoid`. Both are flagged, split, and the resulting fragments get answerable gold labels. I'd expect most of the `NONE` category to dissolve.

Keep `PARTIAL` as a residual signal for cases syntax misses, but don't make it the primary detector.

## Answers to your §11 questions

**Q1.** The containment rule is correct for *assembling* a proposition scope — you're unioning fragments, so they must fit. It's wrong as a *judgment target*, for the reason above. Keep it for assembly; ask the model something whose answer is invariant to candidate resizing.

**Q2.** Yes, and it's the central defect.

**Q3.** Yes, and deterministically, per the trigger-containment rule.

**Q4/Q5.** Target-conditioned with siblings as contrast is a reasonable next shape, and the four-way contract does expose overbreadth. But it multiplies calls back to ~n×m, undoing your 55% reduction. Prefer: split first, then judge.

**Q6.** Worth testing, but as a cross-check on the same cells rather than a replacement. Candidate-major under-attaches; event-major over-attaches (it's asking "is my sentence complete"). Disagreement is a useful `UNCLEAR` signal.

**Q7.** Yes. This is the highest-value change in the list.

**Q8.** Yes, unconditionally. Parse as an unordered set, retain emission order as a diagnostic field. The three `E2,E1` rejections carried no semantic information and only added noise to your metrics. You already concluded permissive sorting wouldn't fix the underlying attachment error — correct, and it costs nothing to stop counting it as a failure.

**Q9.** No. Four segments, one supplying 14 of 24 candidates, all previously seen. Fine for mechanism probing, useless for any accept/reject decision.

**Q10.** The syntax-derivation experiment above, because it separates "the model can't do this" from "we never told the model what we know."

## Two mechanical fixes for order sensitivity

Free-generating a comma-separated label list is maximally position-sensitive: the model is choosing which labels to emit *and* in what order, in 7–13 tokens.

Switch to fixed per-event slots:

```
E1:Y E2:N E3:Y
```

You get a logprob per event, a tunable threshold instead of a hard argmax, an `UNCLEAR` band that finally means something, and no ordering contract to violate.

Then run both orders and combine. Your error profile is recall-dominated (17 omissions + 25 under-attachments versus 5 over-attachments, and a chunk of the 13 `NONE` FPs are oracle artifacts), so union on disagreement. With slot-level scores you can average the two orders instead and skip the union/intersection choice entirely.

## Repeated text: three experiments, three failures

v3 markers failed, CEA-1 markers failed, CEA-1.1 markers failed at 1/3 in every condition. §8.3 shows the combined arm selecting the event governed by the *other* occurrence of the same string.

Stop iterating on markers. Either mark all occurrences ①②③ in one call and force per-occurrence answers, or — since "which event's subtree contains token index *i*" is a parse question — route it deterministically like the governing cases.

## If you want a sequence

1. Syntax-derivation experiment on the full 179. Zero model calls. Decides the architecture.
2. Trigger-containment candidate splitting. Re-derive gold; re-score CEA-1 against the corrected target. Your baseline will move on its own.
3. Slot-format output with logprobs; unordered parsing; two-order averaging.
4. Only then, another prompt arm — with cardinality held constant, on ≥15 segments and ≥150 candidates, with one pre-registered primary endpoint instead of eight conjunctive gates.

The infrastructure around this is genuinely good. Frozen evidence, factor isolation, digests, zero ledger writes, reproducible fingerprints, the source/reversed pairing that caught the order effect. The experiment did its job. It just answered a smaller question than the report claims, and it pointed at the target definition rather than at Qwen.
