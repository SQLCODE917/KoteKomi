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

PHP-1.8 improves input copy fidelity, generation reproducibility, generic-description rejection, and diagnostic visibility.

PHP-1.8 does not solve missing direct relationships by itself.

The next work evaluates PHP-1 before it changes model prompts or extraction stages.

## Incremental TDDs

| ID | User outcome | Precondition | Postcondition | TDD |
| --- | --- | --- | --- | --- |
| H0 | An operator sees exact target coverage for each eligible Source segment. | The packet has paragraph-level anchors and provisional eligibility labels. | The diagnostic reports matched, missing, unresolved, and unexpected hypothesis results without cross-segment credit. | [Segment-Bound PHP-1 Evaluation](2026-08-27-php1-segment-bound-evaluation.md) |
| H1 | A reviewer receives more direct containment, membership, lineage, and directed-action hypotheses. | H0 reports a deduplicated PHP-1 baseline. | A calibrated prompt improves held-out target coverage without reducing verifier-surviving precision. | Planned after H0. |
| H2 | A reviewer can see whether PHP-1 missed Organization mentions or direct relationships. | H1 records target coverage by relationship shape. | A bounded mention task and relationship task report separate candidate and relationship outcomes. | Planned after H1. |
| H3 | A reviewer does not receive country or other unsupported-type references as Organization hypotheses. | H2 records literal mention candidates. | PHP-1 marks unsupported types explicitly before it proposes a direct Organization relationship. | Planned after H2. |
| H4 | A reviewer receives results from one consistent PHP-1 text contract. | H3 identifies remaining format or source-copy failures. | The extraction task and verifier task use consistent Source copy and source-label contracts. | Planned after H3. |

## Validation strategy

H0 adds deterministic fixture tests for Expectation resolution and target matching.

H0 retains the existing 50-row replay as a local diagnostic.

Each later TDD uses the H0 report and a held-out source-segment set.

The held-out set must contain Source segments from all three packet documents.

No TDD treats a model result as its own expected result.

## Constraints

This program does not create Event records.

This program does not change the accepted ontology.

The proposed Event frame slice starts after this program produces a trustworthy PHP-1 baseline.
