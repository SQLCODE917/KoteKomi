# PHP-1 Reliability Improvement Program

- Status: Accepted
- Program ID: `php1-reliability-improvement`
- Parent: [Paragraph Hypothesis Development Program](2026-08-26-paragraph-hypothesis-development-program.md)
- Evaluation corpus: [CIR Evaluation Annotation Packet](2026-08-26-cir-evaluation-annotation-packet.md)

## User outcome

An operator can measure PHP-1 extraction quality from source-segment expectations.

The operator can distinguish a missing hypothesis from an abstention that PHP-1 cannot address.

The operator can improve direct Organization relationship extraction without weakening Ledger authority.

## Context and problem

PHP-1 proposes direct relationships between two named Organizations from one authoritative Source segment.

PHP-1 validates literal source mentions and sends each claim to a faithfulness verifier.

The current packet report records one outcome for each paragraph case.

The report marks a case complete when any Source segment in its paragraph produces a verified claim.

The report does not bind an expected relationship to one Source segment and one Organization pair.

The report can therefore count a claim from another Source segment as a successful case outcome.

The report also repeats one authoritative paragraph across several cases.

The report cannot measure PHP-1 target coverage or direct-relationship recall.

The current replay retrieves mutual partnerships more often than containment, membership, lineage, and
directed institutional relationships.

### Terms

**Expectation** means one reviewable PHP-1 target for one Source segment and one ordered Organization pair.

**Target coverage** means the presence of one verifier-accepted hypothesis that matches one Expectation.

**Unexpected hypothesis** means a verifier-accepted hypothesis that does not match an Expectation.

**Unsupported PHP-1 target** means source meaning that needs a type or evidence span outside PHP-1.

## Invariable decisions

The Archive and accepted DocumentRepresentationBundle remain the authority for source text.

KoteKomi continues to derive Source segments before it calls a model.

The model continues to return ordinary-language hypothesis lines.

The model does not create Ledger records, source offsets, or canonical predicates.

KoteKomi creates pending ProposedChanges after deterministic validation and faithfulness verification succeed.

A reviewer remains the only actor that accepts an Assertion into the Ledger.

PHP-1 continues to use only literal named Organization mentions and direct Organization relationships.

PHP-1 does not add coreference, multi-segment evidence, Events, Places, Actors, countries, products, or policy objects.

The eight-claim limit remains unchanged until reviewed corpus evidence evaluates that limit.

## Current scope

H0 established source-segment Target coverage without cross-segment credit.

The H0 replay retained three partnership or interoperability targets and missed nine targets.

The missed targets concentrate in containment, membership, lineage, agreement, and directed-action
relationship constructions.

H1 evaluated V6 with generic direct-relation examples that mirror supported syntax.

The V6 replay matched seven scored Targets.

The V6 replay missed the mandatory `php1-target-ad-09-anthropic-palantir` interoperability
Target.

The H1 scorecard therefore failed.

The Pipeline continues to use V3.

The repository retains V6, its scorecard, its replay command, and its result contract as historical
calibration evidence.

H2 separates Organization mention detection from direct-relationship judgment.

H2.1 shows that Qwen2.5 has higher exact-span precision and GLiNER has higher Gold mention overlap.

H2.2 combines both fallible proposers behind source validation and semantic qualification.

The H2.2 three-run evaluation completed reproducibly but did not select the qualified path.

Exact-span recall increased from `0.695402` to `0.844828`, and F1 increased from `0.778135` to
`0.809917`.

Exact-span precision decreased from `0.883212` to `0.777778`.

The qualified path also lost 27 exact Qwen2.5 true positives, although it resolved the reviewed NIST
alias and preserved the mandatory Anthropic-Palantir Candidate pair in every run.

The Pipeline therefore continues to use PHP-1 V3.

## Incremental TDDs

| ID | User outcome | Precondition | Postcondition | TDD |
| --- | --- | --- | --- | --- |
| H0 | An operator sees exact target coverage for each eligible Source segment. | The packet has paragraph-level anchors and provisional eligibility labels. | The diagnostic reports matched, missing, unresolved, and unexpected hypothesis results without cross-segment credit. | [Segment-Bound PHP-1 Evaluation](2026-08-27-php1-segment-bound-evaluation.md) |
| H1 | A reviewer receives more direct containment, membership, lineage, and directed-action hypotheses. | H0 reports a deduplicated PHP-1 baseline. | V6 matched seven scored Targets but missed the mandatory interoperability baseline. | [Structural Direct-Relation Prompt Calibration](2026-08-27-php1-structural-relation-prompt-calibration.md) |
| H2 | A reviewer can see whether PHP-1 missed Organization mentions or direct relationships. | H0 resolves one Source segment for each Expectation. | A bounded mention task and relationship task report separate candidate and relationship outcomes. | [PHP-1 Mention and Relationship Diagnosis](2026-08-27-php1-mention-relationship-diagnosis.md) |
| H2.1 | An operator can compare Qwen2.5 with a specialized Organization span proposer. | H2 records literal Mention candidates separately from Pair judgments. | A 50-case exact-span report compares quality, latency, and stability without changing production PHP-1. | [Specialized Organization Span Proposer Evaluation](2026-08-27-php1-specialized-organization-span-proposer-evaluation.md) |
| H2.2 | An operator can evaluate source-validated and semantically qualified Organization mentions from both proposers. | H2.1 measures complementary proposer behavior. | Only validated, alias-aware Organization identity candidates enter diagnostic pair generation. | [Organization Mention Qualification](2026-08-27-php1-organization-mention-qualification.md) |
| H3 | A reviewer does not receive country or other unsupported-type references as Organization hypotheses. | A refined qualified-mention candidate passes the H2.2 no-regression gates. | A production selection TDD adopts qualified mentions without losing demonstrated Qwen2.5 behavior. | Blocked by the H2.2 evaluation result. |
| H4 | A reviewer receives results from one consistent PHP-1 text contract. | H3 identifies remaining format or source-copy failures. | The extraction task and verifier task use consistent Source copy and source-label contracts. | Planned after H3. |

## Validation strategy

H0 adds deterministic fixture tests for Expectation resolution and target matching.

H0 retains the existing 50-row replay as a local diagnostic.

Each later TDD uses the H0 report and a held-out source-segment set.

H1 scored eleven binary direct-Organization Expectations and recorded the coordinated consultation
target only as an Event-frame observation.

H1 retained seven scored matches but did not retain all mandatory baseline matches.

H2 starts from the stable V3 production baseline.

H2.2 retains the complete three-run candidate, qualification, alias, pair, ModelRun, and selection
evidence outside accepted Ledger state.

H2.2 records `not_selected` because higher recall did not compensate for lower precision or lost
demonstrated true positives.

The held-out set must contain Source segments from all three packet documents.

No TDD treats a model result as its own expected result.

## Constraints

This program does not create Event records.

This program does not change the accepted ontology.

The proposed Event frame slice starts after this program produces a trustworthy PHP-1 baseline.
