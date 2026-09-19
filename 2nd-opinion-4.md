## This cycle worked, and the path-length result is unambiguous

Development syntax, precision against path length:

| Policy | Edge P | Edge R | Leakage |
|---|---:|---:|---:|
| path_1 | 0.930 | 0.295 | 2 |
| path_2 | 0.775 | 0.494 | 29 |
| path_3 | 0.663 | 0.624 | 74 |
| path_4 | 0.568 | 0.690 | 129 |
| unbounded | 0.504 | 0.771 | 193 |

Leakage 193 → 2, precision 0.504 → 0.930. Validation shows the same shape with precision 0.967 at path_1. CEA-1.2's `syntax_can_replace_qwen: falsified` was measuring an unbounded-closure artifact, not a property of syntax. That's now settled, and it cost zero model calls.

And you have your first real gain since CEA-1: validation exact-set 0.642 → 0.682. The `supported` classification is earned.

## The largest finding in this report isn't in the summary

Validation NONE accuracy:

- Qwen: 0.421 (8/19)
- Syntax path_1: **0.947 (18/19)**
- Qwen ∪ syntax path_1: 0.421 (8/19)

Union is set-additive, so a syntax NONE can never override a Qwen non-empty set. You have a component that nearly solves the metric that has failed in every cycle since v3, and the combiner structurally discards it.

The arithmetic confirms this is where the headroom is. Validation, in candidates out of 179:

```
Qwen alone                     115
Qwen ∪ syntax path_1           125
Qwen ∪ syntax path_1_plus      122
candidate_source ceiling       134
per_edge ceiling               144
```

The gap from your primary (122) to the candidate-source ceiling (134) is 12 candidates. Syntax path_1 rescues 10 NONE candidates that union throws away. **Essentially the entire union-to-ceiling gap is NONE discrimination.**

**The next computation, again model-free:** the 2×2 of "syntax path_1 returns empty" against "normalized Gold is NONE," on both partitions. You know syntax path_1 catches 18/19 true NONEs. What you don't know is how often it returns empty for a candidate with a non-empty gold set, and path_1's edge recall of 0.413 means that's likely common. If the false-NONE rate is low, add a veto rule: syntax-empty implies NONE. If it's high, gate the veto on head-aware trigger flagging and re-measure. Either way this is the single highest-value number you don't have.

## The policy selection deserves a second look

You selected `path_1_plus_complement`. Compare on validation:

| | exact-set | edge P | leakage | rescue |
|---|---:|---:|---:|---:|
| path_1 union | **0.698** | **0.853** | **12** | **11/12** |
| path_1_plus union | 0.682 | 0.835 | 17 | 14/20 |

path_1 dominates on every one of those. On development it loses by one candidate (85 vs 87) and by 0.033 edge F1, which is where the selection came from.

Worth noting explicitly: path_1 adds only **3 edges** on development and **12** on validation. That's not a small difference in degree, it's the policy being nearly inert on one partition and materially useful on the other. Syntax path_1 exact-set is 0.198 on dev and 0.430 on validation. Same parser, same policy, same gold rule. The partitions differ structurally, and that gap is larger than any effect you've measured this cycle. It bears on transfer more than the selection does.

The complement extension buys recall (dev edge R 0.295 → 0.506) at a real precision cost (0.930 → 0.884). Both are defensible. But the selection currently rests on a two-candidate development margin, and it should be stated that way rather than as a policy the evidence picked.

## The ceiling is pool-specific, so compute more than one

Your per-edge ceiling recall (dev 0.845, val 0.831) exactly equals the path_1_plus union recall. Correctly constructed, but it means the ceiling is bounded by whatever pool you fed it. Larger pools have higher ceilings:

| Pool | Val union edge recall |
|---|---:|
| path_1_plus | 0.831 |
| path_3_plus | 0.878 |
| unbounded_plus | 0.920 |

The architectural question for CEA-2 is whether a good filter over a noisy pool beats a weak filter over a clean one. Run the per-edge ceiling at path_3_plus and unbounded_plus. If unbounded_plus tops out near 0.85 exact-set against path_1_plus's 0.804, the recall is worth chasing and you should build a filter. If it tops out at 0.81, stop at path_1 and spend the effort elsewhere.

## Two residuals, both narrow

**Repeated occurrences: 1/3, identity preserved 3/3.** `with` now resolves correctly. The other two are both the Sacks sentence and both fail by adding exactly one spurious event, `support`. Path: `support/acl → evidence/nmod → association/conj`. Under a distance-1-plus-complements policy that edge should not survive unless the complement family follows `acl` through an `nmod` host. Excluding nmod-mediated `acl` would likely fix both, and it's a one-line policy change to test.

**Head-aware trigger containment: P 0.643, R 0.300.** Up from 0.42 precision on the naive rule, so the refinement helped, but it's a weak detector and syntax path_1 NONE at 0.947 supersedes it. The five false positives are interpretable: `that Anthropic had held discussions…` contains `discussions` as a foreign head, yet `discussions`' own proposition swallows the entire candidate. Containing a foreign trigger doesn't imply overreach when the containing proposition covers the candidate anyway. Keep the rule as a diagnostic, don't make it the NONE gate.

## Two things to be honest about

**The normalization was smaller than I implied.** Three gold changes, worth one validation candidate. Correct to do and free, but not the artifact class I made it out to be.

**Validation is now a selection set.** You have used these 179 candidates to choose a prompt architecture, a path policy, and a union operator across three cycles. The 0.682 is a selection-on-validation figure, not transfer. Before any production gate, you need a partition that has never informed a decision. This is now your largest risk and it grows with every cycle that doesn't address it.

## Suggested order

1. Syntax-empty versus Gold-NONE confusion matrix. Decides the NONE router, which is worth roughly 10 validation candidates.
2. Per-edge ceiling at path_3_plus and unbounded_plus. Decides filter-versus-pool for CEA-2.
3. Drop nmod-mediated `acl` from the complement family; re-score the three repeated cases.
4. Re-open the path_1 versus path_1_plus choice once 1 and 3 land, since a NONE router changes the trade.
5. Hold out a genuinely fresh partition before anything is promoted.
6. Model swap on the unchanged CEA-1 harness. Still the largest untested variable, and the ceiling analysis now gives you a clean way to read the result.

On process: this cycle was the right size. Three open questions answered, zero model executions, the first substantive gain in three iterations, and the diagnostic apparatus doing exactly what it was built for. The sweep design in particular, plus the complement variants and both ceiling types, is better instrumentation than the question strictly required and it will keep paying off.
