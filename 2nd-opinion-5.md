## The gate falsified a proxy, not the hypothesis

Your registered hypothesis was aggregate: a bounded filter over a high-recall pool improves exact-set accuracy and edge precision across 490 development and 257 validation edges. What you actually tested was perfection on sixteen adversarially selected edges, and the `falsified` verdict rests entirely on that proxy. The full development run never executed. The hypothesis is untested.

At n=16, 13/16 has a 95% interval of roughly [54%, 96%]. You cannot distinguish 81% from 93% with that sample, and CEA14-SEL-04A demanded 100%. Meanwhile the catalog was built by CEA14-SEL-02 to be maximally hard: Qwen false positives, syntax-only false edges, Gold-NONE, repeated occurrences, attribution, time, long paths. Accept-everything scores 8/16 on it. The filter beat that by five on the hardest cases you could assemble.

The filter does not need to be perfect. It needs to beat not filtering. The Maximum Pool has development edge precision around 0.52, so roughly half its edges are false. A filter at 85% sensitivity and 85% specificity would lift that precision into the mid-0.80s. Whether that translates into exact-set gain depends on edges-per-candidate, which is exactly the thing your evidence can answer and your gate prevented you from asking.

Your own reasoning for stopping is right: further example tuning would overfit sixteen cases. But the conclusion that follows is "measure on 490," not "build four new tasks, each to be tuned against its own sixteen cases."

## The V8/V9 error pattern says threshold, not category

Sort the five cases by direction:

- **V8 errors**: mixed→offered (FP), earlier Anthropic→intensifying (FP), January→rescission (FP). All three false positives.
- **V9 errors**: Department→threatened (FN), viewed→support (FN), January→rescission (FP). Two false negatives.

V9 did not teach a distinction. It moved a decision boundary. Two edges crossed one way, two crossed the other, and the one furthest from the boundary (January→rescission) never moved at all.

That is a calibration signature, and it means the decisive experiment is small. **Re-run the same sixteen cases under V8 and V9 capturing the Y-token logprob.** Thirty-two calls, minutes of runtime.

- If the eight gold-positives separate from the eight gold-negatives at some threshold under either prompt, you get 16/16 from a threshold with no prompt work, and the four-way router is unnecessary.
- If January→rescission scores above Department→threatened, no threshold rescues it and decomposition is justified on evidence rather than inference.

This is the third cycle in which a finite-token output contract has discarded the information that would settle the architectural question. CEA14-MOD-07 mandates exactly `Y`, `N`, or `U`; nothing in that requirement prevents you from also archiving the logprobs, and CEA14-MOD-10 arguably already asks for them under "execution diagnostics."

## Three model-free computations before any router

**Break-even surface.** Over the frozen Maximum Pool with gold, compute filtered exact-set accuracy as a function of hypothetical filter sensitivity and specificity. Find the contour where filtered exact-set equals 0.682, your current validation primary. If break-even sits at 95% per-edge, 81% is hopeless and the router is warranted. If it sits near 80%, you are already at the boundary and the gate rejected a working component.

**Type census.** Classify all 490 development pool edges as reference-supported, attribution-scope, temporal-scope, mixed-candidate, or generic. If the four named types cover 15% of edges, a four-way router addresses 15% of the problem and 85% still needs the generic filter you just declared falsified.

**Nominal-event temporal rule.** Your implementation notes already record that temporal candidates legitimately propagate across coordinated and inherited verbal events. The January→rescission failure is a temporal adjunct reaching an *embedded nominal* event. Test the deterministic rule directly on the pool: temporal adjuncts do not attach to nominal events lacking their own temporal modifier. `rescission`, `agreements`, `hiring`, `discussions`, `decision` are all nominals in your inventory, so this is measurable across both partitions right now. If it holds, that error class leaves the model entirely.

## Problems with the four-way router as specified

**The router needs a classifier.** Something decides which task an edge gets. If that is syntactic and deterministic, fine. If it is the model, you have added a decision point with its own error rate multiplying through four downstream tasks.

**The categories overlap.** `viewed → support` is attribution *and* an eight-edge path. `the Department → threatened` is reference *and* participation. `January 2025 → rescission` is temporal *and* embedded-event scope. An edge needing two tasks has no defined behavior in the current sketch.

**The cost is four CEA-1.4 cycles.** Four prompts, four diagnostics, four approval gates, each with fewer cases and therefore less power than the one that just failed. If the gate shape stays as it is, you have committed to four more falsified verdicts.

If the logprob test shows genuine ranking failure, I would still build one filter with a typed output (`participant / time / attribution / framing / none`) rather than four routed tasks. Forcing a typed commitment is most of the discriminative benefit of decomposition without the routing layer, the overlap problem, or the fourfold diagnostic cost.

## On gate design

Three cycles running, the acceptance criterion has been stricter than the question:

- CEA-1.1: eight conjunctive both-orders gates → `mixed`, near-predetermined.
- CEA-1.2: CEA12-SYN-15 "meets every declared metric" → `falsified` on a proposal nobody made.
- CEA-1.4: 16/16 adversarial → `falsified`, blocked a 490-call run that takes about seventeen minutes at your median latency.

CEA-1.3 is the counterexample, and it is the one cycle that produced a usable answer. It asked what the sweep looked like instead of whether a threshold was cleared.

A better shape for CEA14-SEL-04A: gate on error *class* rather than error count. "No gold-positive entity edge rejected" and "no mixed candidate accepted whole" are checkable on sixteen cases and directly protect the things you care about. Then let the aggregate endpoint on 490 edges decide whether the filter works.

## Order

1. Logprob capture, V8 and V9, sixteen cases. Decides calibration versus decomposition.
2. Break-even surface on the frozen pool. Zero calls.
3. Type census. Zero calls.
4. Nominal-event temporal rule test. Zero calls.
5. If 1 and 2 are favorable, run the full development pool under V8 and replace the diagnostic gate with the aggregate endpoint already written into CEA14-OUT-02.
6. Router only if the ranking is genuinely bad, and with a deterministic pre-classifier.

Separately, the model swap remains untested across four experiments and is still the largest unexamined variable. The break-even surface from step 2 would also tell you what a stronger model would need to deliver to matter, which makes that test cheaper to interpret when you get to it.
