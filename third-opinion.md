The central finding is this:

> PHP-1 has the right authority boundary, but it currently asks a general-purpose model to discover too much structure before that boundary can help it.

Keep KoteKomi’s deterministic control. Narrow Qwen’s job. Make the ontology explicit during extraction, and distinguish binary relationships from events before asking for predicates.

## Begin with one sentence

Take:

> Anthropic reached an agreement with the AI Safety Institute.

You already know the first operation:

```text
Find the organization mentions.
```

That produces:

```text
m1 = Anthropic
m2 = AI Safety Institute
```

Now ask a different question:

```text
What semantic shape does this sentence contain?
```

The answer is:

```text
binary relationship
```

Only then ask:

```text
What relationship is asserted between m1 and m2?
```

The answer might be:

```text
m1 reached an agreement with m2
```

Finally, KoteKomi—not the model—does the record-making work:

```text
validate m1 and m2 against exact source spans
validate that both are Organizations
construct the ProposedChange
attach source offsets and provenance
send it to review
```

This is very close to PHP-1, and the important part is already right: the model interprets language; KoteKomi owns identities, evidence, records, and acceptance.

Now take another sentence:

> UNESCO and MeitY began consulting with experts.

We again find two organizations:

```text
m1 = UNESCO
m2 = MeitY
```

But now the semantic shape is different. The sentence does not necessarily say:

```text
UNESCO consulted with MeitY
```

It says both organizations participated in a consulting event.

The faithful representation is closer to:

```text
ConsultationEvent
    participant: UNESCO
    participant: MeitY
    participant: experts
```

This explains one of the current model’s “abstentions.” It may not be failing to understand the sentence. PHP-1 may be offering it only the wrong representational shape.

## What PHP-1 gets right

PHP-1 has four unusually strong properties.

First, authoritative text remains authoritative. Model output cannot rewrite the source.

Second, model output is only a proposal. Invalid or unsupported output cannot silently become Ledger state.

Third, every accepted claim can be traced to a source segment and exact offsets.

Fourth, extraction is inspectable in stages. We can see whether a failure came from mention detection, pair construction, semantic judgment, or deterministic validation.

This aligns well with ontology-driven extraction research. Text2KGBench, for example, evaluates three separate questions:

```text
Did the system extract the facts?
Did it conform to the ontology?
Did it invent unsupported facts?
```

Those are separate qualities and should remain separate in KoteKomi too. [Text2KGBench](https://arxiv.org/abs/2308.02357)

The danger would be replacing this with an opaque model call that directly emits accepted graph records. That might appear more capable while making failures much harder to locate or audit.

## Where PHP-1 is straining

PHP-1 currently expects a general-purpose model to perform several jobs at once:

```text
find every organization
preserve the complete mention boundary
classify each mention correctly
consider every organization pair
decide whether the pair has a direct relationship
distinguish a relationship from shared event participation
describe that relationship
obey an exact output format
```

These are different tasks. When they are combined, a failure near the beginning eliminates everything downstream.

For example:

```text
Anthropic is omitted
    ↓
Anthropic–DoD is never proposed as a pair
    ↓
no relationship judgment is possible
```

This is why better relation instructions cannot repair a missing mention.

It also explains the prompt sensitivity we observed. One prompt revision recovered agreement and refusal relations but weakened containment or membership cases. We were not simply teaching one rule. We were changing the model’s implicit definition of the entire task.

There is also a scaling problem. If a paragraph contains twelve organizations, blindly considering every unordered pair gives:

```text
12 × 11 ÷ 2 = 66 candidate pairs
```

Most will be negative. That consumes model work and encourages the model to reason about pairs the prose never presented as a relationship.

## What Qwen2.5 is good at

The current Qwen2.5-14B-Instruct model is credible for bounded semantic decisions.

Our results show it can often answer questions such as:

```text
Given these two grounded organizations and this source segment,
does the segment directly assert a relationship between them?
```

It retained known cases and recovered relationships such as:

```text
Anthropic → agreement with → AI Safety Institute
Anthropic → refusal directed toward → Department of Defense
```

Its official model card emphasizes improved instruction following and structured output, particularly JSON. [Qwen2.5-14B-Instruct](https://huggingface.co/Qwen/Qwen2.5-14B-Instruct)

But “good at structured output” does not mean “complete information-extraction engine.”

Our tests still found it:

- omitting obvious organizations;
- shortening a required complete name;
- producing both a mention and `abstain`;
- changing capabilities noticeably when prompt wording changed.

That does not prove Qwen is a poor model. It proves that a generic 14-billion-parameter instruction model is being asked to perform a specialized information-extraction task without task-specific training.

The model is strongest when KoteKomi gives it:

```text
a small amount of authoritative text
already grounded candidates
one semantic decision
a small decision contract
```

It is weakest when asked:

```text
Find everything, classify everything, determine every relationship,
and serialize the whole result perfectly.
```

## What established approaches suggest

### 1. Use a specialized span proposer

GLiNER is designed specifically for named-entity extraction. It performs parallel entity extraction with a relatively compact bidirectional model and reported stronger zero-shot NER results than much larger general chat models on its evaluations. [GLiNER](https://aclanthology.org/2024.naacl-long.300/)

This does not mean GLiNER should become authoritative. It could become one more fallible proposer:

```text
authoritative SourceSegment
    ↓
GLiNER proposes Organization spans
    ↓
KoteKomi validates every character span
    ↓
validated MentionCandidates
```

The practical experiment is simple: run GLiNER and Qwen against the same 50-paragraph packet and compare:

```text
mention recall
mention precision
complete-name boundaries
latency
run-to-run stability
```

No architectural commitment is needed before seeing those results.

### 2. Make the ontology an explicit instruction

GoLLIE found that detailed annotation guidelines materially improve information-extraction behavior, especially when models are trained to follow those guidelines. It also shows why generic prompting alone has limits: reliable guideline compliance is itself a learned capability. [GoLLIE](https://arxiv.org/abs/2310.03668)

KoteKomi should therefore provide a small, versioned ontology card for the current task:

```text
Allowed entity type:
- Organization

Allowed semantic shapes:
- direct binary relation
- shared event participation
- attributed statement
- no supported claim

Direct relation:
The source asserts a relationship from one organization to another.

Shared event:
Both organizations participate in the same event, but the source does
not assert that one acts directly upon the other.
```

This is better than gradually accumulating examples and warnings in a prose prompt.

Later, KoteKomi can select only the relevant ontology fragment for each extraction task instead of placing the complete ontology into every prompt. Schema-adaptive KG research follows this general pattern: supply the relevant schema and condition extraction on it. [AdaKGC](https://aclanthology.org/2023.findings-emnlp.425/)

### 3. Constrain syntax, but do not confuse syntax with semantics

GenIE uses constrained decoding so that generated triples conform to an allowed entity and relation schema. [GenIE](https://aclanthology.org/2022.naacl-main.342/)

KoteKomi can use LM Studio’s supported structured-output mechanism for a tiny decision DTO:

```json
{
  "decision": "direct_relation",
  "direction": "first_to_second",
  "relation_phrase": "reached an agreement with"
}
```

This can prevent malformed combinations such as:

```text
mention Congress
abstain
```

But constrained output cannot make the model notice Anthropic when it omitted Anthropic. Nor can it decide whether consultation is a direct edge or an event. It solves grammar, not understanding.

KoteKomi should deserialize this small decision and construct the real `ProposedChange` itself. The model still never supplies Ledger IDs, source offsets, provenance records, or accepted graph objects.

### 4. Introduce semantic-shape routing

Unified information-extraction work explicitly models entities, relations, and events as related but distinct structures. UIE uses a schema-driven framework across those tasks; DyGIE++ also treats entities, relations, events, and coreference as separate interacting structures. [UIE](https://aclanthology.org/2022.acl-long.395/), [DyGIE++](https://aclanthology.org/D19-1585/)

The next bounded decision should therefore be:

```text
What kind of knowledge is present here?
```

Possible answers:

```text
binary_relation
event_frame
attributed_statement
no_supported_claim
```

Only a `binary_relation` proceeds into PHP-1’s pair-relation path.

An `event_frame` proceeds into the planned event proposal slice:

```text
EventFrame
    trigger
    participants
    object
    time
    location
    evidence_span
```

This prevents PHP-1 from manufacturing misleading pairwise edges merely because two organizations occur in the same sentence.

## The recommended KoteKomi pipeline

The clean long-term shape is:

```text
Authoritative SourceSegment
    ↓
Mention proposer
    ↓
KoteKomi-validated MentionCandidates
    ↓
Semantic-shape router
    ├── direct relation
    ├── event frame
    ├── attributed statement
    └── no supported claim
    ↓
Small semantic draft from Qwen
    ↓
KoteKomi source and ontology validation
    ↓
Predicate or event-type governance
    ↓
Pending ProposedChange
    ↓
Human review
    ↓
Accepted Ledger records
```

The principle is:

> Closed structure, open meaning.

“Closed structure” means the model must choose an understood kind of proposal.

“Open meaning” means it can preserve an ordinary-language relationship such as:

```text
declined to grant unrestricted access to
entered into an evaluation agreement with
was established within
```

KoteKomi can subsequently map that phrase to a governed predicate—or reject the mapping—without losing what the source actually said.

## What I would test next

I would not continue enlarging the current prompts indefinitely. The latest experiments show that prompt edits can exchange one demonstrated capability for another.

The most informative next experiments are:

1. Compare GLiNER and Qwen mention proposal on the existing 50 paragraphs.

2. Add a bounded semantic-shape classifier:

```text
binary relation | event | attributed statement | none
```

3. Use task-local mention labels such as `m1` and `m2`, never model-generated record identifiers.

4. Constrain only the small decision DTO through LM Studio structured output.

5. Score each stage independently:

```text
mention recall
mention boundary accuracy
candidate coverage
shape-routing accuracy
relation direction
semantic accuracy
source grounding
ontology conformance
unsupported-claim rate
format validity
run stability
```

6. Preserve strict per-case non-regression:

> If an improvement loses an already demonstrated ability, it is not yet an improvement we can trust.

The 50-paragraph packet should remain an evaluation set, not become prompt examples or fine-tuning data. If task-specific training is pursued later, it needs a separate training corpus so the packet remains capable of detecting real generalization.

In short: PHP-1’s deterministic authority model is the part to preserve. The next improvement is not “a smarter all-purpose prompt.” It is to turn extraction into smaller typed semantic decisions, introduce event frames where binary edges are unfaithful, and use specialized models where they demonstrably outperform Qwen—while allowing none of those models to own KoteKomi’s truth.
