## First, what your numbers actually say

The thing worth noticing: sibling leakage went 12 → 10. That was the hypothesis. It barely moved. What moved was recall — qualification 48.6 → 68.6, entity 94.3 → 100, character F1 82.9 → 89.0.

So the competitive framing didn't mainly fix attachment discrimination. It made the model more willing to emit multi-label sets, which lifted recall across the board. That's a real win, but it means your remaining precision problem (case 3, repeated identity) and your remaining recall problem (cases 2 and 4) are both still unaddressed by the design change itself. Good to know before you tune further.

## The under-attachment is structural, not a tuning issue

Your derived gold says:

> C attaches to Event when every meaningful character in C belongs to G.

That defines attachment as **containment in the event's proposition scope**. Your prompt defines it as **argumenthood**:

> the Candidate supplies part of that fact: a participant, affected thing, time, place, attribution, negation, uncertainty, purpose, comparison, or necessary clause content.

Those are not the same relation, and the gap is exactly where your failures live. Look at case 2. The candidate is `wrote` and the expected set includes E2 `describing`. `wrote` is not a participant, time, place, or clause content of the describing event. It's the **governing predicate** — the op-ed that does the describing is the thing that was written. Nothing in your criterion list licenses that answer. The model was right by the stated rule and wrong by the gold.

Your own Example 3 has the same shape (`Ravi` → `miss`) and it's the one example a model would find least generalizable, because Ravi participates in *viewing*, not in *missing*. It reads as an exception rather than a rule.

So you have a systematic class of gold positives — matrix predicates, attribution frames, host nouns, governing clauses — that the prompt tells the model to reject. That's likely a large share of your 65.

**The fix is to state the containment test directly.** Something close to:

> For each Event, imagine restating only the fact centered on the marked Event words, as a single standalone sentence a reader could understand without the rest of the passage. Select the Event when the Candidate's exact words would have to appear in that restatement — whether they name a participant or detail of the fact, or supply the framing that introduces, attributes, or hosts it.

Run that against your cases: restating *describing* standalone requires "Amodei wrote an op-ed describing…" → `wrote` is in. Restating *led* requires "…led to a conflict between Anthropic and the Trump administration" → `Trump administration` is in. Restating *urged* doesn't pull in `[6]` → NONE holds. Restating *miss* requires keeping Ravi's attribution → Example 3 stops being an exception and becomes an instance of the rule.

This is the decontextualization criterion from the APS/PropSegmEnt line, and it's what your gold derivation actually encodes. Align the two before you do anything else.

## Your examples teach a prefix shortcut

Seven examples, and the answers are `E1,E2` / `E1` / `E1,E2` / `NONE` / `E1,E2,E3,E4` / `E1,E2` / `E1,E2`. Every non-NONE answer is a **prefix of the option list**. You've never shown a selection that skips an option — no `E2`, no `E1,E3`, no `E2,E3`.

Combined with "in the order supplied," a 14B model can easily learn "answer a prefix" as the surface pattern. That produces precisely the bias you're seeing: it takes the first event or two and stops. Case 2's answer `E1` out of `E1,E2,E3` is a prefix. Case 4's `NONE` is the escape hatch when no prefix feels right.

Two cheap things:

1. Replace at least three examples with skip patterns: `E2` alone, `E1,E3`, `E2,E4`. Make one of them a case where E1 is clearly wrong so the model has to skip the first option.
2. Ablate for order sensitivity. Run the same validation with the event options shuffled. If exact-set accuracy moves more than a couple of points, you have positional bias, and you can average over two orderings per candidate as a stopgap.

## Fixing shared-fragment loss: run the matrix from both sides

Your gold unit is the per-event proposition scope, but you only ever query candidate → events. The model never sees the proposition it's assembling, so it has no way to notice it's missing a subject or a time phrase.

Add the transposed query: for each Event, show all deduplicated candidates at once and ask which ones the standalone restatement requires. That's ~40 calls on top of your 162, still well under the 359 baseline.

Then combine the two views of the same cell:

- both say attached → attach
- both say not → don't
- disagree → third adjudication call, or `UNCLEAR`

The two directions fail in opposite directions — candidate-major under-attaches (it's answering "does this belong somewhere else instead"), event-major over-attaches (it's answering "is my sentence complete"). Taking the union on disagreements will move recall hard; taking the intersection will move precision. You can tune which, per candidate type, against your dev gold.

## Get per-event confidence back

Your comma-list output format throws away calibration. Same call, same competitive framing, but a fixed slot format:

```
E1:Y E2:N E3:Y
```

Now you have a logprob per event and a tunable threshold. Under-attachment is a threshold problem at this point — drop the cutoff below 0.5 and watch exact-set accuracy versus sibling leakage trade off explicitly. This also gives `UNCLEAR` something to mean (score in a middle band), which I'd bet it still doesn't have, since your prompt-v3 run never emitted `U` either.

## Two targeted patches

**Repeated identity (case 3).** Inline markers on repeated surface forms failed in v3 and still fail. Stop prompting around it. Apply the same trick that worked for events: make the occurrences compete. One call, all occurrences of `Trump` in the passage marked ①②③, all events listed, and ask for the attachment set per occurrence. Forcing the model to differentiate them in a single output is much stronger than asking it to ignore the other two. As a cheap grounding check, have it echo the candidate with three words of context on each side before answering; a mismatched echo is a retry signal.

**Long-distance nesting (case 4).** You already run Stanza. Use it as a gate rather than only as a proposer. Compute the dependency path between the trigger and the candidate head, then:

- direct core dependent (`nsubj`/`obj`/`obl`/`ccomp`/`xcomp`/`advmod`) → auto-attach, don't ask
- no path and no coref link → auto-reject, don't ask
- everything else → ask the model, and inject the intervening phrase as evidence: *"Trump administration sits inside the phrase 'a conflict between Anthropic and the Trump administration', which depends on led."*

Case 4 is a candidate two levels down inside `ARG1`; surfacing the intervening constituent is usually enough. The UD predicate-argument study you cite says exactly this — syntax exposes most relations and the remainder need semantics. Right now you're spending model calls on the ones syntax already decides.

## One diagnostic worth running before any of this

Sample the 65 failures and label each by mechanism: governing-material positive, deep-nesting positive, occurrence confusion, genuine ambiguity, gold artifact. If governing-material dominates, the restatement reframing alone should recover most of it and everything else is premature.

While you're there, replace exact-set accuracy as your tuning signal with Jaccard or Hamming on the label sets, plus a split of "too few labels" versus "too many" versus "wrong labels." Exact-set is the right acceptance gate but it's a terrible gradient — a 4-label set that misses one scores the same as one that misses all four.
