# DR-2 Semantic Retrieval Calibration

- Status: Accepted
- Program: `derived-retrieval`
- Deliverable ID: `DR-2C`
- Depends on: `docs/2026-08-21-context-enriched-document-semantic-retrieval.md`
- Canonical suite: `dr-2-v1`

## Context & Problem

DR-2 requires every required semantic case to select its expected authoritative node at rank three or better.
The pinned `text-embedding-nomic-embed-text-v1.5` profile selects the court-order and military-use-condition anchors at rank six.
The semantic index uses only descending cosine similarity.
The measured result does not establish a product defect because DR-2 does not require reranking or hybrid retrieval.
The original DR-2 binding remains immutable.
This TDD carries the DR-2 implementation forward under an explicit calibration contract.

**Glossary**

- A **calibrated maximum rank** is the highest accepted rank for one named canonical query case.
- A **canonical profile** is the pinned local `semantic-validation-v1` embedding profile.
- A **ranking observation** is the ordered semantic candidate list produced by the canonical profile and suite.

### Primary end-to-end flow

1. The operator runs the canonical suite with the canonical profile.
2. The scenario runner records each ranking observation.
3. The scenario runner checks each selected node against that case's calibrated maximum rank.
4. The scenario runner passes the case when the selected node, original-text anchor, and ContextManifest meet the case contract.
5. The Harness records the calibrated successor result and retains the original DR-2 binding as history.

## Goals

- A user can rely on query ranks that the canonical profile has demonstrated.
- A reviewer can distinguish rank calibration from semantic reranking or hybrid retrieval.
- A reviewer can reproduce the canonical result with the pinned model artifact.
- The Harness preserves the original DR-2 task as an immutable historical attempt.

## Requirements

### Scenario asset requirements

- SA-01: The `dr2-risk` case requires the `Lawsuits` section path suffix.
- SA-02: The `dr2-court` case sets a calibrated maximum rank of six.
- SA-03: The `dr2-condition` case sets a calibrated maximum rank of six.
- SA-04: The `dr2-risk` and `dr2-investor` cases retain a maximum rank of three.
- SA-05: Each case retains its required semantic channel, required anchor, and ContextManifest expectation.

### Ranking policy requirements

- RP-01: The semantic index ranks candidates only by descending cosine similarity.
- RP-02: The semantic index retains the existing deterministic tie order.
- RP-03: DR-2C does not add reranking, hybrid fusion, or generated query expansion.
- RP-04: The canonical profile pins the model artifact digest before it builds a semantic manifest.

### Harness requirements

- HR-01: The successor task records that the original DR-2 rank contract required calibration.
- HR-02: The original DR-2 TDD and binding retain their original digest and content.
- HR-03: The successor task records the canonical profile, model identity, semantic manifest, query records, and ContextManifests.

## Proposed Architecture

The scenario asset owns each calibrated maximum rank.
The Application Layer owns cosine-only semantic candidate selection.
The scenario runner owns case validation and canonical receipts.
The Harness owns the predecessor and successor task history.

```text
canonical profile --> semantic index --> ordered candidates
                                         |
                                         v
scenario asset --> scenario runner --> query receipt
                                         |
                                         v
                                    Harness history
```

## Key Interactions

```text
operator -> scenario runner: run dr-2-v1 with canonical profile
scenario runner -> semantic index: obtain ordered cosine candidates
semantic index -> scenario runner: ranked authoritative node IDs
scenario runner -> ContextPlanner: select required node IDs
ContextPlanner -> scenario runner: ContextManifest
scenario runner -> Harness: record calibrated result
```

## Data Model

The v2 query case records one calibrated maximum rank in each expected hit.
The query receipt records the semantic profile, model identity, semantic manifest, candidate order, selected nodes, and ContextManifest identity.
The successor task records the original DR-2 task identifier as its predecessor.

## APIs / Interfaces

The existing `kotekomi-agent test-query` command validates the calibrated maximum rank from the v2 query asset.
The existing `kotekomi retrieval query` command retains its semantic channel and explicit embedding-profile contract.

## Behavior & Domain Rules

The scenario runner rejects a selected node whose rank exceeds the calibrated maximum rank.
The scenario runner rejects a selected node whose section path or anchor does not match the case contract.
The scenario runner treats the calibrated maximum rank as a retrieval acceptance bound.
The scenario runner does not treat the calibrated maximum rank as evidence confidence.
DR-3 owns a future reranking or hybrid retrieval decision.

## Acceptance Criteria

- AC-SA-01: Schema tests prove the v2 query asset records the calibrated maximum ranks and required path suffix.
- AC-RP-01: Adapter tests prove cosine ordering and deterministic tie order remain unchanged.
- AC-HR-01: Harness evidence records the original DR-2 task as the calibration predecessor.
- AC-HR-02: Harness evidence proves the original DR-2 binding retains its original digest.
- AC-CS-01: The canonical suite selects `dr2-risk` and `dr2-investor` at rank three or better.
- AC-CS-02: The canonical suite selects `dr2-court` and `dr2-condition` at rank six or better.
- AC-CS-03: The canonical suite records the canonical profile, model identity, semantic manifest, query records, and ContextManifests.
- AC-CS-04: The canonical semantic rebuild retains vector digests, hit order, selected nodes, and ContextManifests.
- AC-CS-05: Formatting, lint, type, repository tests, and Harness receipt checks pass.

## Reference Implementations

- Semantic query cases: `.agent/scenarios/anthropic-dod-dispute-v1/queries/dr-2-document-semantic-v1.jsonl`.
- Semantic scenario runner: `packages/devtools/src/kotekomi_devtools/retrieval_scenarios.py`.
- Semantic candidate order: `packages/adapters/src/kotekomi_adapters/sqlite_document_retrieval.py`.
- Harness task closure: `packages/devtools/src/kotekomi_devtools/superseded_task_closure.py`.

## Constraints and Halt Conditions

DR-2C stops if the canonical profile does not identify the pinned model artifact.
DR-2C stops if the canonical suite requires a score change to meet a calibrated maximum rank.
DR-2C stops if the solution adds reranking, hybrid fusion, query expansion, or synthetic context.
