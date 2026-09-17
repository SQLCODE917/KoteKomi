# Event-Entity Connection Second-Opinion Handoff

- Status: Evidence snapshot for external review
- Date: 2026-09-16
- Program: [Hybrid Semantic Quality Program](2026-09-06-hybrid-semantic-quality-program.md)
- Parent experiment:
  [Event-Entity Connection Experiment](2026-09-12-event-entity-connection-experiment.md)
- Latest diagnostic:
  [Stanza Predicate-Argument Diagnostic](2026-09-16-stanza-predicate-argument-diagnostic.md)
- Approved Gold: [Event-Entity Connection Gold v2](hsq-event-entity-connection-gold-v2.json)

## 1. Purpose

This document requests a second opinion on one unresolved Hybrid Pipeline boundary.

It records what KoteKomi has proved, what it has falsified, and where extraction remains unreliable.

It separates observed evidence from proposed explanations.

It does not authorize a new production contract.

## 2. Executive Summary

KoteKomi reliably reaches this state:

```text
authoritative SourceSegment
        +
exact source-grounded Event
        +
complete expected Actor and Organization candidate inventory
        |
        v
unresolved Event-to-entity semantic edge
```

The current boundary asks this question:

> Does this exact Actor or Organization occurrence belong to the complete source proposition
> centered on this exact Event expression?

The candidate boundary is not the present failure.

The current canonical preflight exposed all 47 expected development entities and all 43 expected
held-out entities.

The Event boundary is not the present failure.

KoteKomi preserved every reviewed Event as an exact source-grounded Event before this experiment.

Three downstream strategies failed to produce a reliable connection policy:

1. One Qwen2.5 judgment per Event-entity pair produced many misses and false positives.
2. One Qwen2.5 answer vector per Event reduced calls but reduced semantic quality.
3. Deterministic Stanza dependency paths preserved high structural recall but low precision.

The strongest current hypothesis is a contract problem before it is a parser problem.

The binary label combines several semantic relations under one word, `involved`.

Those relations include core participation, counterparties, attributed content, possessive
connections, controlled subjects, and source-grounded qualifications.

The same label must exclude temporal adjuncts, attribution sources, affiliations, background
descriptions, and neighboring Events.

Syntax exposes these relations but cannot decide their KoteKomi meaning.

The local model also fails to apply the broad binary definition consistently.

## 3. Architectural Constraints

The [KoteKomi design authority](2026-07-08-KoteKomi.md) defines these constraints.

- The Archive and accepted `DocumentRepresentationBundle` remain source authority.
- The Ledger remains accepted intelligence authority.
- Models and linguistic processors produce fallible derived evidence.
- KoteKomi validates exact source characters and constructs every record.
- A reviewer alone can accept model-derived intelligence.
- A model score cannot become evidence confidence.
- A missing optional semantic classification cannot erase a source-grounded Event.
- Every future solution must preserve exact source text and replayable lineage.

The [Hybrid Intelligence Extraction Pipeline](2026-09-01-hybrid-intelligence-extraction-pipeline.md)
assigns one bounded job to each component.

This review must preserve that authority boundary.

## 4. Position in the Pipeline

The current implemented flow is:

```text
Authoritative SourceSegment
    |
    v
MentionCandidates and ReferenceDecisions
    |
    v
SourceOccurrence and exact Event trigger
    |
    v
source-grounded Event and EventMention
    |
    v
exact Actor and Organization occurrence candidates
    |
    v
CURRENT BOUNDARY: Event-entity connection
    |
    v
later semantic assignments and CompleteProposition
    |
    v
support decision
    |
    v
ProposedChanges
    |
    v
human review
```

The current experiment does not assign semantic roles.

It does not classify the Event under an exhaustive Event ontology.

It does not create a `ProposedChange`.

It does not write accepted Ledger state.

## 5. Evaluation Basis

The approved Gold catalog contains 40 reviewed Events.

Development contains 20 Events.

Held-out validation contains 20 Events from the same source document.

The catalog contains 90 expected entity identities.

It contains 116 accepted exact source-occurrence alternatives.

Some identities accept nested or abbreviated source expressions.

The evaluator therefore reports identity and candidate-occurrence results separately.

The source fixture is:

```text
raw/Anthropic–United_States_Department_of_Defense_dispute.pdf
```

The fixture is intentionally untracked.

The approved Gold is human-reviewed but comes from one document and one subject area.

The validation split tests unseen Events, not a held-out document or domain.

## 6. What Is Experimentally Proven

### 6.1 Exact Events survive incomplete classification

The [Source-Grounded Event Boundary](2026-09-12-source-grounded-event-boundary.md) separates exact
Event evidence from optional governed classification.

The canonical Event evaluation preserved all 87 reviewed trigger groundings.

An incomplete Event vocabulary no longer suppresses source evidence.

### 6.2 Expected candidate identities reach this boundary

The latest canonical preflight exposed 47 of 47 expected development identities.

It exposed 43 of 43 expected held-out identities.

It reported zero typed candidate gaps and zero deterministic Gold rejections.

This evidence localizes the current failure after mention, reference, and entity-denotation work.

### 6.3 Exact source and execution evidence remain inspectable

KoteKomi supplies exact source ranges, entity occurrences, Event expressions, and source digests.

KoteKomi owns all candidate positions, identifiers, records, and result mapping.

The model returns only finite semantic answers.

Every experiment retains exact input, raw output, parsed output, and Gold comparison.

### 6.4 The implementation is mechanically verified

The repository suite passed with 1,574 tests and one skip on September 16.

Formatting, lint, and type checking passed.

The latest model-free diagnostic produced byte-identical equal-input replays.

These checks reduce the likelihood of a mechanical implementation defect.

They do not establish semantic correctness.

## 7. Current Job Allocation

| Component | Current bounded job | Authority |
| --- | --- | --- |
| KoteKomi | Build exact candidates and validate all source ranges. | Deterministic project authority. |
| Stanza | Supply tokens, lemmas, dependency heads, and dependency relations. | Fallible derived evidence. |
| Qwen2.5 | Judge candidate membership in one Event-centered proposition. | Fallible derived evidence. |
| Gold evaluator | Compare completed observations with reviewed expectations. | Evaluation authority only. |
| Reviewer | Accept or reject later `ProposedChange` records. | Accepted-state authority. |

Relevant implementation files:

- [Event-entity candidate construction](../packages/application/src/kotekomi_application/event_entity_connections.py)
- [Qwen execution boundary](../packages/application/src/kotekomi_application/event_entity_connection_preview.py)
- [Finite output parser](../packages/application/src/kotekomi_application/event_entity_connection_model_output.py)
- [Current Qwen prompt](../prompts/event_entity_involvement_v5.md)
- [Predicate-argument analyzer](../packages/application/src/kotekomi_application/event_entity_predicate_arguments.py)
- [Predicate-argument evaluator](../packages/pipelines/src/kotekomi_pipelines/event_entity_predicate_argument_stage_local.py)
- [Experiment runner](../scripts/run_event_entity_connection_experiment.py)

## 8. Experiment Findings

### 8.1 Candidate readiness

This stage asked whether every expected Actor or Organization reached the judgment boundary.

| Phase | Expected identities | Available identities | Missing identities |
| --- | ---: | ---: | ---: |
| Development | 47 | 47 | 0 |
| Held-out validation | 43 | 43 | 0 |

Result: candidate availability passed.

Interpretation: downstream misses cannot be attributed to absent expected identities in this run.

### 8.2 Pairwise Qwen judgments

The first semantic contract made one Qwen call per Event-entity pair.

| Phase | Matched | Missing | Extra | Model calls |
| --- | ---: | ---: | ---: | ---: |
| Development | 35/47 | 12 | 31 | 166 |
| Held-out validation | 38/43 | 5 | 32 | 106 |

Result: the pairwise contract failed.

Interpretation: narrow calls improved recall over the later batch but still produced many false
positive connections.

The call count also made this path operationally expensive.

The parent experiment preserves the full [pairwise result](2026-09-12-event-entity-connection-experiment.md#9-acceptance-criteria).

### 8.3 One contrastive Qwen vector per Event

The second semantic contract supplied one ordered candidate inventory for each Event.

Qwen returned one `Y`, `N`, or `U` character per candidate.

| Phase | Matched | Missing | Extra | Unresolved | Model calls |
| --- | ---: | ---: | ---: | ---: | ---: |
| Development | 21/47 | 26 | 44 | 23 | 20 |
| Held-out validation | 28/43 | 15 | 20 | 5 | 20 |

Result: the batched contract failed.

All three development repetitions produced the same failed result.

The batching change reduced development calls from 166 to 20.

It reduced development formatted input from 90,491 to 27,397 tokens.

It increased the largest request from 577 to 1,823 tokens.

One thirteen-candidate task returned fourteen answers and invalidated its inventory.

Development model execution still required about 157 seconds.

Held-out model execution required about 100 seconds.

Interpretation: batching improved cost but worsened semantic accuracy.

The stable failures indicate a contract or capability problem rather than random sampling noise.

### 8.4 Model-free Stanza predicate-argument diagnostic

The third strategy removed Qwen.

KoteKomi mapped each exact Event head and entity occurrence onto the pinned Stanza dependency tree.

KoteKomi classified each path as direct, coordinated, relative-clause, inherited, qualified,
different-sentence, Semantic Remainder, or Diagnostic Gap.

| Metric | Development | Held-out validation |
| --- | ---: | ---: |
| Events | 20 | 20 |
| Candidate occurrences | 177 | 115 |
| Expected entity identities | 47 | 43 |
| Structurally covered identities | 46 | 36 |
| Semantic Remainder identities | 1 | 7 |
| Structural occurrence matches | 61 | 41 |
| Structural occurrence extras | 95 | 40 |
| Structural precision | 0.3910 | 0.5062 |
| Diagnostic gaps | 0 | 3 |
| Model calls | 0 | 0 |

Every expected identity received either structural coverage or a Semantic Remainder classification.

The result therefore confirms high structural recall.

The result also rejects broad dependency-path acceptance.

The strongest class was `direct_argument`.

Development produced 12 direct matches and zero direct extras.

Held-out validation produced 16 direct matches and two direct extras.

The two held-out extras were a temporal expression and an attribution source.

The diagnostic completed successfully, but `routing_hypothesis_supported` was `false`.

`passed: true` means that all 40 diagnostic cases produced valid evidence.

It does not mean that the proposed routing policy passed.

## 9. Telling Failure Examples

### 9.1 Relative-clause and inherited-subject failure

Exact SourceSegment:

> As the Trump administration targeted law firms, Amodei cut ties with the firms Skadden, Arps,
> Slate, Meagher & Flom and Latham & Watkins, which reached agreements with the Trump administration
> to avoid punishment.

Reviewed Events:

- The law firms reached agreements with the Trump administration.
- The law firms intended to avoid punishment.

Expected connections:

- Both named law firms connect to `reached agreements`.
- The Trump administration connects as the counterparty.
- Both named law firms inherit the subject of `avoid punishment`.

Observed Qwen behavior:

- Pairwise judgments rejected expected firms in the relative clause.
- Controlled-subject judgments rejected firms and selected unrelated neighboring entities.
- The batched task did not repair the pattern.

### 9.2 Qualification versus participation failure

Exact SourceSegment:

> By November 2024, Anthropic had already partnered with Palantir and Amazon Web Services, companies
> that offered services with FedRAMP authorization.

Reviewed Event:

> Palantir and Amazon Web Services offered services with FedRAMP authorization.

Expected connections:

- Palantir.
- Amazon Web Services.
- FedRAMP as the institutional qualification attached to the offered services.

Observed behavior:

- Candidate preflight exposed all three identities.
- Qwen rejected expected source-grounded connections.
- A standard core-participant extractor could also omit FedRAMP because it is a qualification.

This case demonstrates that KoteKomi's current binary target is broader than ordinary core argument
extraction.

### 9.3 Temporal adjunct false positive

Exact SourceSegment:

> That month, Amodei criticized Trump's approach to export restrictions on semiconductors.

Reviewed Event:

> That month, Amodei criticized Trump's approach to export restrictions on semiconductors.

Candidate:

> That month

Expected result: not an Actor or Organization participant.

Observed Stanza result: `direct_argument` through `criticized -> month`.

### 9.4 Attribution-source false positive

Exact SourceSegment:

> According to Semafor, Trump officials chastised Anthropic's hiring of several officials ...

Reviewed Event:

> Trump officials chastised Anthropic's hiring.

Candidate:

> Semafor

Expected result: attribution source, not Event participant.

Observed Stanza result: `direct_argument` through `chastised -> Semafor`.

These two cases prove that short syntactic paths do not establish the semantic edge KoteKomi needs.

## 10. Exact Point of Impasse

KoteKomi has one exact Event and a complete set of exact entity occurrences.

KoteKomi still needs a reliable rule for creating the edge between them.

The edge currently means all of these things:

- the entity performs or experiences the Event;
- the entity is a counterparty, target, object, owner, or supplier;
- the entity occurs in attributed Event content;
- the entity controls an implicit subject;
- the entity qualifies an Event object or service;
- the entity belongs to the complete source proposition in another approved way.

The edge must reject all of these things:

- time;
- place used only as context;
- reporting or attribution source;
- title or affiliation;
- background description;
- an entity participating only in a neighboring Event;
- a person nested only inside a participating collective expression.

The word `involved` hides this heterogeneity.

Qwen2.5 has not learned one stable decision surface from the prompt and source alone.

Stanza exposes grammatical paths but not the required semantic distinctions.

The current boundary is therefore stuck between syntax and meaning.

## 11. Root-Cause Hypotheses

These hypotheses remain unproven.

Each hypothesis includes a falsification test.

### H1: The binary target conflates incompatible semantic functions

Evidence:

- The prompt maps core participation, attributed content, and qualifications to the same `Y` label.
- Temporal and attribution expressions can share equally short syntactic paths.
- FedRAMP is expected because it qualifies services, not because it performs the Event.

Test:

1. Add diagnostic-only function labels to the existing candidate occurrences.
2. Use coarse labels such as core participant, counterparty, content entity, qualification,
   attribution source, temporal context, background, and neighboring Event.
3. Measure agreement before mapping those functions back to a binary Ledger policy.

H1 gains support when errors concentrate at transitions between those function classes.

H1 loses support when both Qwen and a stronger reference model classify the functions correctly but
still fail the binary mapping.

### H2: The marked Event expression is too narrow to identify the complete proposition

Evidence:

- The prompt admits that `<event>` can contain only a head or short phrase.
- The model must recover relative-clause antecedents and controlled subjects from the full sentence.
- Complex sentences contain several valid Events and several neighboring entities.

Test:

1. Derive one source-exact proposition envelope around each Event.
2. Preserve the original SourceSegment and Event head separately.
3. Compare the existing head-only task with the proposition-envelope task on the sealed 40 cases.

H2 gains support when proposition envelopes improve both precision and recall without changing Gold.

### H3: Candidate batching causes cross-candidate interference

Evidence:

- Pairwise judgments achieved better recall than the batched vector.
- The batched request repeated one marked passage for every candidate.
- One task returned the wrong answer count.
- Stable development failures show that the effect is repeatable.

Test:

1. Run identical candidate occurrences through one-candidate, small-group, and full-Event tasks.
2. Keep model, prompt meaning, temperature, and source context fixed.
3. Score candidate occurrences before identity consolidation.

H3 loses support if one-candidate judgments retain the existing false-positive rate.

### H4: Qwen2.5 has reached a semantic capability ceiling for this task

Evidence:

- Qwen fails explicit prompt examples involving relative clauses and controlled subjects.
- Stable retries reproduce the same errors.
- The task requires distinctions between participant, attribution, qualification, and context.

Test:

1. Seal the exact KoteKomi inputs and evaluator.
2. Replay them once with a stronger reference model.
3. Keep KoteKomi's source validation and record construction unchanged.

H4 gains support when the stronger model materially improves held-out precision and recall.

H4 loses support when the stronger model reproduces the same semantic confusion.

### H5: A semantic-role or Event-argument specialist can supply a better proposal layer

Evidence:

- Stanza supplies syntax, not semantic roles.
- The failures include classic predicate-argument structures.
- Mature SRL schemes distinguish core arguments from temporal and locative adjuncts.

Test:

1. Run one pinned SRL or Event-argument extractor over the same exact SourceSegments.
2. Map every proposed span back to authoritative characters.
3. Score it as a fallible proposer without admitting its output to Ledger state.
4. Measure core participant recall, adjunct rejection, latency, and replay stability.

H5 loses support if the specialist misses controlled, relative-clause, and qualification cases needed
by KoteKomi.

### H6: Proposition-first extraction fits the task better than entity-pair classification

Evidence:

- KoteKomi already has exact Event heads and exact source structure.
- Pair classification creates hundreds of decisions from only 40 Events.
- Many false positives come from entities outside the Event's proposition.

Test:

1. Propose one source-exact proposition span or clause graph per Event.
2. Intersect validated entity occurrences with that proposition.
3. Ask semantic questions only about ambiguous boundaries or inherited links.

H6 gains support when proposition coverage remains complete while semantic calls and extras fall.

### H7: Identity-level scoring hides occurrence-level boundary defects

Evidence:

- One entity can have nested, abbreviated, or repeated accepted occurrences.
- Earlier model reports consolidated occurrence decisions into entity identities.
- The Stanza diagnostic exposed different occurrence-level precision from identity-level coverage.

Test:

1. Preserve occurrence-level precision and recall in every future experiment.
2. Consolidate identities only after occurrence adjudication.
3. Report both metrics and every merge decision.

H7 explains measurement confusion, but it cannot explain all observed semantic errors by itself.

### H8: The current corpus is too narrow to select a general production policy

Evidence:

- Development and validation come from one PDF.
- Both splits concern related political and institutional events.
- The current experiment already performs poorly under this favorable same-document condition.

Test:

1. Preserve the current 40 cases as development evidence.
2. Create a second human-reviewed packet from another source and subject area.
3. Run the frozen winning contract once on that packet.

H8 governs generalization evidence.

It does not explain the current same-document failures.

## 12. Alternative Architecture Families for Review

### 12.1 Coarse semantic-function routing

KoteKomi can replace one broad binary question with a small finite function inventory.

KoteKomi can then map reviewed functions into Ledger edges.

This approach needs enough functions to separate participant, content, qualification, attribution,
and context.

It must not become an exhaustive FrameNet-scale ontology.

### 12.2 Proposition envelope followed by bounded adjudication

KoteKomi can first identify the exact source proposition centered on the Event.

It can then evaluate only entities inside or grammatically inherited by that proposition.

This architecture gives deterministic code a larger role without treating syntax as semantics.

### 12.3 Specialist SRL or Event-argument proposer

A semantic-role or Event-argument model can propose argument spans and coarse functions.

KoteKomi can validate every span and preserve the proposal as derived evidence.

Qwen can adjudicate only conflicts and KoteKomi-specific qualification cases.

This architecture matches the existing hybrid authority model.

It does not solve the FedRAMP-style qualification case by itself.

### 12.4 Trained local edge classifier

KoteKomi can train a small span-pair or proposition-edge classifier after collecting enough reviewed
examples.

The current 40 cases are insufficient evidence for a production-trained classifier.

The current exact traces could seed a larger annotation effort.

### 12.5 Stronger model as a diagnostic control

A stronger model can reveal whether local Qwen capability is the limiting factor.

This test does not require granting that model authority or adopting it for local production.

### 12.6 Review-first fallback

KoteKomi can preserve source-grounded Events without automatic entity connections.

It can expose uncertain connection candidates for explicit review.

This option protects Ledger integrity while extraction research continues.

It offers less automatic intelligence value.

## 13. External Research That Frames the Alternatives

The following sources define neighboring approaches.

They do not establish that one approach fits KoteKomi.

- [Stanza dependency parsing](https://stanfordnlp.github.io/stanza/depparse.html) produces syntactic
  dependency trees and relations.
- [PropBank semantic-role research](https://aclanthology.org/J08-2006/) distinguishes core arguments
  from modifiers such as time and location.
- [PropBank documentation](https://github.com/propbank/propbank-documentation) records mature
  predicate-argument annotation rules.
- [Document-Level Event Argument Extraction by Conditional Generation](https://aclanthology.org/2021.naacl-main.69/)
  uses Event templates and document context.
- [Transfer Learning from Semantic Role Labeling to Event Argument Extraction](https://aclanthology.org/2022.emnlp-main.169/)
  investigates SRL transfer and natural-language slot queries.
- [Thinking about How to Extract](https://aclanthology.org/2024.findings-acl.328/) identifies key
  feature forgetting and cross-Event argument confusion in document-level extraction.

Most Event-argument systems assume typed Events or role templates.

KoteKomi deliberately preserves source-grounded Events without requiring exhaustive classification.

Any borrowed model must therefore act as a proposer, not as ontology or source authority.

## 14. Questions for the Second Opinion

1. Is `belongs to the complete source proposition` a coherent atomic target?
2. Must core participants and source-grounded qualifications use separate edge kinds?
3. Can a small function inventory avoid an exhaustive Event-role ontology?
4. Does proposition-first extraction fit KoteKomi better than entity-pair classification?
5. Which local specialist can propose semantic arguments on Apple Silicon within 24 GB?
6. Which experiment best separates task-contract failure from Qwen capability limits?
7. How can KoteKomi preserve phenomenological source precision while making edges queryable?
8. What evidence threshold justifies production integration without weakening Ledger integrity?

## 15. Exact Experiment Records

The tracked TDDs preserve all conclusions needed to understand this handoff.

The following local records retain exact inputs and outputs on the originating machine.

### Batched Qwen v6

```text
/private/tmp/kotekomi-event-entity-contrastive-v6-development-r1-20260916/report.json
/private/tmp/kotekomi-event-entity-contrastive-v6-development-r1-20260916/review.md
/private/tmp/kotekomi-event-entity-contrastive-v6-validation-r1-20260916/report.json
/private/tmp/kotekomi-event-entity-contrastive-v6-validation-r1-20260916/review.md
/private/tmp/kotekomi-event-entity-contrastive-v6-comparison-20260916.json
```

### Model-free Stanza diagnostic

```text
/private/tmp/kotekomi-stanza-predicate-argument-diagnostic-v2-20260916/diagnostic.json
/private/tmp/kotekomi-stanza-predicate-argument-diagnostic-v2-20260916/review.md
/private/tmp/kotekomi-stanza-predicate-argument-diagnostic-v2-20260916/summary.json
/private/tmp/kotekomi-stanza-predicate-argument-diagnostic-v2-20260916/manifest.json
```

The diagnostic result fingerprint is:

```text
6a3c5002665dcf026272c0fee9774ce157f9db5d39ada62be10eb2f144d2f890
```

The byte-identical replay is:

```text
/private/tmp/kotekomi-stanza-predicate-argument-diagnostic-v2-replay-20260916/
```

### Repository verification

```text
/private/tmp/kotekomi-stanza-predicate-argument-full-tests-20260916.log
/private/tmp/kotekomi-stanza-predicate-argument-full-tests-20260916.xml
/private/tmp/kotekomi-stanza-predicate-argument-full-tests-20260916.status.json
```

## 16. Current Recommendation

Do not tune the existing `Y` / `N` / `U` vector prompt again without changing the task contract.

Do not promote broad Stanza path classes into deterministic Event connections.

Preserve both failed experiments as evidence.

Ask the second reviewer to evaluate H1, H2, H5, and H6 first.

The next bounded experiment must separate semantic functions before it selects another model or
prompt.

The experiment must retain the same Gold, exact source evidence, occurrence-level scoring, and zero
accepted-state writes.
