I'll check the current tooling landscape before answering the "what should I use instead" parts.Your setup makes sense, but it's actually three different tasks wearing one prompt, and that's most of your problem.

## What you're doing has names

The core question ("is this span an argument or modifier of this predicate?") is **semantic role labeling** (SRL), specifically the argument-identification half of it. In PropBank terms your `Y` cases map to numbered args and `ARGM-*` adjuncts: `In January 2025` is `ARGM-TMP`, `that Anthropic had held discussions...` is `ARG1` of *noted*, `Skadden...` is a coordinated `ARG0`.

The framing with a marked trigger and a candidate span is **event argument extraction** (EAE), the ACE/RAMS/WikiEvents/MAVEN-Arg line of work.

The thing you're actually building toward, reconstructing a complete, self-contained proposition with exact source boundaries, is **proposition segmentation / claim decomposition**, sometimes called atomic fact extraction. The canonical formulation asks for units that are atomic and minimal, fully decontextualized, explicitly present in the source, and jointly exhaustive. PropSegmEnt, FActScore, and the APS work are the reference points. Older but directly relevant: ClausIE and MinIE from the OpenIE line, since MinIE explicitly annotates polarity, modality and attribution, which is exactly your 58% qualification recall gap.

All three are well studied. None of them is solved by a single binary prompt.

## Your two error clusters are distinct and have different fixes

Sort your ten cases:

**False negatives (2, 4, 5, 9, 10, and half of 1)** are all non-subject, non-object arguments: a sentence-initial temporal adjunct, a `that`-complement, a conjunct inside a coordinated NP, a nominal modifier inside an argument, and a coreference antecedent. Your single in-prompt example shows only bare NP participants in a coordinated VP. The model has literally never been shown that an adjunct or a complement clause counts. This is a demonstration-coverage failure.

**False positives (3, 6, 7, 8, and the other half of 1)** are all spans that attach to a *competing predicate in the same sentence*: `as "chaotic"` → *criticized*; `with the firms...` → *cut ties*; `Sacks` → *viewed*; `the World Economic Forum` → *attend*. Every one of these is an attachment decision, and your prompt never makes the model consider the rival predicate at all. It only asks "does this relate to the marked event?", and by a generous reading, all of them do.

That split explains your headline number. With 187/359 gold positives, majority-class guessing gets 52%. You're at 64.6%. You have roughly 13 points of signal.

## The prompt's stated criterion contradicts its examples

> Answer `Y` when removing the exact Candidate words would lose part of what the passage says about the Event.

This is an **informativeness** test, not an **attachment** test. Delete `as "chaotic"` and you do lose something the passage says about Amodei's stance toward Stargate, and *opposed* is part of that stance. A model following your written rule answers `Y`. Your example, meanwhile, teaches a structural rule. When rule and example disagree, the model follows the rule on anything the example doesn't cover, which is exactly the hard cases.

Other concrete issues:

- **`U` can never fire.** You gave it a vague criterion ("does not make clear") and zero demonstrations. Instruction-tuned models collapse to the demonstrated label set. If you want abstention, read the Y/N token logprobs and threshold, or make U a typed outcome with its own example.
- **Inline markers on repeated strings are unreliable.** Case 1 isn't semantics, it's the model losing track of which `Anthropic` is tagged. Pass character offsets, or replace the marked occurrence with a unique sentinel and state explicitly that other occurrences of the same string are irrelevant.
- **Binary is the wrong output space.** Ask for a role label (`agent / patient / recipient / time / manner / purpose / attribution / none-of-these`). Forcing a commitment to a specific relation is far more discriminative than a relevance judgment, and you get your qualification types for free.
- **Better still: make it competitive.** Give all predicates in the sentence and ask which one the candidate attaches to, or none. That single change targets your entire false-positive cluster, because the model can no longer answer "related to the topic" — it has to pick a head.

## Your gold encodes rules the prompt doesn't contain

This is the part I'd fix first. Reading your ten cases, your annotation guideline includes at least these:

1. Include restrictive modifiers of arguments (`FedRAMP` modifies *services*, which is `ARG1` of *offered*).
2. Include the antecedent for a definite anaphor (`Department of Defense` for *the department*).
3. Include clausal complements in full.
4. Include adjuncts, including sentence-initial temporals, with their punctuation.
5. Exclude anything attached to a sibling predicate, even in the same sentence.
6. For a predicate embedded under an attitude verb (*Sacks viewed... as evidence that... support*), only material inside the embedded clause counts.

None of these appear in your prompt. Rules 2 and 6 in particular are not SRL at all — rule 2 is coreference resolution plus decontextualization, rule 6 is discourse/attribution structure. You're asking a 14B model to infer an annotation manual from four examples in one sentence. There's a 2026 study on exactly this: LLM event extractors improve substantially when given dataset-specific, detailed annotation guidelines that represent the actual human annotation procedure, and the underperformance is attributed to underspecified task instructions.

Two more data-side problems:

**Your Event spans are inconsistent in granularity.** In TGE-019 the event is the whole nominalization `decision to attend the World Economic Forum over Trump's second inauguration`. In TGE-023 the event is the bare trigger `support`, and the candidate `the World Economic Forum` sits *inside* that same nominalization. Sometimes a trigger, sometimes a trigger plus its arguments. Pick one convention. Nominal predicates (*agreements*, *decision*) are NomBank territory and have different argument-realization patterns from verbs; consider handling them in a separate pass.

**Character-exact F1 partly measures boundary conventions, not semantics.** 80% recall with only 62% exact-fragment match says a lot of your misses are near-misses on span edges. This is a known LLM failure mode: on MAVEN-Arg, LLM bag-of-words F1 is markedly higher than exact match, because predictions are free-format and don't respect human annotation boundaries. Don't ask the LLM for boundaries. Generate candidates as parser constituents/subtrees and have the LLM only select among them. Report role-correctness and boundary-correctness separately.

## Is Qwen2.5-14B suitable?

For the *proposing* role, yes. For the *deciding* role, marginally, and not in this formulation. It's a reasonable semantic candidate generator, which your 85% entity recall already shows. But fine-grained attachment under competing predicates is close to a parsing task, and a 14B instruct model has no reliable implicit parser. The honest framing from the literature is that LLMs used as zero-shot or example-driven annotators are substantially outperformed by supervised techniques on structured extraction tasks like event detection and argument extraction.

You'd get more from the same compute with:

- **A supervised SRL model as the prior.** `transformer-srl` (BERT-based, PropBank/VerbAtlas) reports 86.0 F1 on arguments and 95.5 on predicates for CoNLL-2012. AllenNLP is unmaintained but the model still runs. That handles cases 2, 3, 4, 5, 9 essentially for free, and gives you argument spans with correct boundaries.
- **A dependency parser** (spaCy `en_core_web_trf` or Stanza) for the attachment questions. "Is this span in the subtree of predicate X or predicate Y" resolves cases 3, 6, 7 deterministically.
- **A coreference model** as a separate decontextualization pass for case 10. Don't fold it into the argument judgment.
- **Qwen only for what's left**: nominal predicates, VerbAtlas/PropBank sense selection, and adjudicating where parser and SRL disagree.

If you want a single learned judge, you already have labeled data. Fine-tune a DeBERTa-v3-large cross-encoder on `(sentence, predicate-marked, candidate-marked) → role` span-pair classification. 359 candidates is a dev set, not a training set; you'd want 1–2k, which is a day of annotation given you already have the guideline in your head. That will very likely beat prompted Qwen-14B by a wide margin at a fraction of the inference cost.

## If you only change three things

1. Replace the deletion test with a typed, competitive attachment question: list every predicate in the sentence, ask which one the candidate is a dependent of, and which role.
2. Write your six implicit annotation rules into the prompt with one worked example each, drawn from the exact phenomena in your ten failures.
3. Stop letting the LLM choose span boundaries; propose candidates from parser constituents and score selection separately from boundary fidelity.

Worth a look before you iterate further: RAMS and MAVEN-Arg for EAE evaluation conventions, PropSegmEnt for proposition-level gold, and MinIE for how the OpenIE community factored out attribution, polarity and modality rather than trying to judge them inline.
