# TDD: PHP-1 Organization Semantics and Annotation Alignment

- Status: Accepted
- Program: [PHP-1 Reliability Improvement Program](2026-08-27-php1-reliability-improvement-program.md)
- Deliverable ID: H2.2.1
- Depends on: [Organization Mention Qualification](2026-08-27-php1-organization-mention-qualification.md)

## 1. Context & Problem

PHP-1 measures named Organization mentions against a repository-owned catalog.

The Domain glossary defines Organization more narrowly than the current prompts.

The catalog identifies itself as provisional agent-authored material.

These conflicts can score a correct proposer as wrong.

**Organization** means a collective Agent with a common purpose beyond its current members.

**Named Organization mention** means one literal expression that identifies an Organization in one Source segment.

**Mention policy** means the versioned inclusion and boundary rules for Named Organization mentions.

**Development benchmark** means a reviewed benchmark used for local design feedback.

### Primary end-to-end flow

1. A reviewer applies one Organization definition to the design, Domain glossary, and prompts.
2. The reviewer applies one Mention policy to every Source segment in the packet.
3. The catalog records the Mention policy identity and a policy-aligned status.
4. The evaluator rejects a catalog that uses another policy or status.
5. An operator can interpret proposer metrics against one explicit contract.

## 2. Goals

- An operator sees one Organization meaning throughout PHP-1.
- An operator can inspect the exact Mention policy behind every score.
- An operator can distinguish the development benchmark from a held-out release benchmark.
- A later experiment can compare proposers without label-policy drift.

## 3. Requirements

### Domain semantics

- H221-ORG-01: The design and Domain glossary use the same Organization definition.
- H221-ORG-02: Organization includes formal and informal collective Agents.
- H221-ORG-03: Organization includes governments, departments, courts, legislatures, administrations, and military bodies.
- H221-ORG-04: Organization includes clubs, consortia, collaborations, and institutional networks.
- H221-ORG-05: A bare country, region, or other Place remains a Place.

### Mention policy

- H221-POL-01: The repository stores one versioned Mention policy.
- H221-POL-02: The Mention policy requires the maximal literal expression for one displayed name.
- H221-POL-03: The Mention policy includes each repeated occurrence.
- H221-POL-04: The Mention policy includes an attached geographic qualifier that forms part of the displayed name.
- H221-POL-05: The Mention policy includes a parenthetical initialism in the same mention.
- H221-POL-06: The Mention policy excludes generic descriptions, anaphora, unnamed cohorts, and names used only as Places.
- H221-POL-07: The Mention policy excludes laws, documents, Events, products, and projects that do not denote collective Agents.
- H221-POL-08: The Mention policy includes a named publisher or news outlet.
- H221-POL-09: The Mention policy includes the European Union as a supranational Organization.
- H221-POL-10: The Mention policy includes a named club and excludes a generic club description.
- H221-POL-11: The Mention policy includes a country name when the Source assigns its government institutional agency.

### Catalog alignment

- H221-CAT-01: A reviewer applies the Mention policy to every unique packet Source segment.
- H221-CAT-02: The catalog records the Mention policy identity.
- H221-CAT-03: The catalog status is `human_reviewed_development_gold`.
- H221-CAT-04: The catalog records every mention in Source order.
- H221-CAT-05: The catalog remains a development benchmark.
- H221-CAT-06: The catalog does not claim held-out or release-gate status.

### Prompt alignment

- H221-PRM-01: The mention prompt uses the canonical Organization definition.
- H221-PRM-02: The qualification prompt uses the canonical Organization definition.
- H221-PRM-03: Both prompts apply the Mention policy boundary rules.

## 4. Proposed Architecture

```text
Design + Domain glossary
          |
          v
     Mention policy
       /        \
      v          v
 Mention prompts  Reviewed catalog
       \          /
        v        v
       H2 evaluator
```

The Domain glossary owns Organization meaning.

The Mention policy owns annotation inclusion and boundary rules.

The prompts own model instructions for the same contract.

The reviewed catalog owns expected literal spans.

## 5. Key Interactions

```text
Reviewer       Mention policy       Catalog       Evaluator
   |                 |                 |              |
   | review segments |                 |              |
   |---------------->| apply rules     |              |
   |---------------------------------->| record spans |
   |                                                    |
   | operator runs evaluator                            |
   |--------------------------------------------------->|
   |                 |<---------------------------------|
   |                 | validate identity                |
   |                 |                 |<---------------|
   |                 |                 | validate spans |
```

## 6. Data Model

The repository adds `docs/php1-named-organization-mention-policy-v1.json`.

The policy records its identity, definition, inclusions, exclusions, and boundary rules.

The Mention catalog adds `annotation_policy_id` at its root.

The Mention catalog replaces its provisional status with the H221-CAT-03 status.

## 7. APIs / Interfaces

The H2 evaluator validates the policy identity and catalog status before model execution.

The evaluator records the policy identity in each comparison report.

## 8. Behavior & Domain Rules

The Mention policy classifies denotation in the Source occurrence.

Capitalization alone does not make an expression an Organization.

An explicit government name denotes an Organization.

A country name used only as a Place denotes a Place.

A country name assigned institutional agency denotes its acting government for Mention extraction.

An explicit military body name denotes an Organization.

The policy treats an alias declaration as one complete displayed mention.

The policy treats a later standalone alias as a separate mention occurrence.

## 9. Acceptance Criteria

- AC-H221-ORG-01: Documentation checks prove one Organization definition across both authority files.
- AC-H221-POL-01: Policy tests prove every required inclusion and exclusion rule exists.
- AC-H221-CAT-01: Catalog tests prove all Source segments use the policy-aligned status and identity.
- AC-H221-CAT-02: Catalog tests prove every stored span matches the Source copy.
- AC-H221-CAT-03: A manual review confirms all 164 Source segments against the Mention policy.
- AC-H221-PRM-01: Prompt tests prove both model tasks use the canonical definition and boundary rules.
- AC-H221-ISO-01: Pipeline tests prove public ingestion retains PHP-1 V3.

## 10. Reference Implementations

- Domain terms: `docs/agent/domain.md`.
- Mention catalog validation: `scripts/php1_span_proposer_evaluation.py`.
- Mention prompt: `prompts/paragraph_organization_mention_v1.md`.
- Qualification prompt: `prompts/paragraph_organization_qualification_v1.md`.

## 11. Constraints and Halt Conditions

H2.2.1 changes evaluation semantics and annotations.

H2.2.1 does not select a production proposer.

H2.2.1 does not change the eight-hypothesis PHP-1 limit.

## 12. Observed Result

The Domain glossary, design, Mention policy, mention prompt, and qualification prompt now use one
Organization definition based on the W3C Organization concept.

The human review covers all 164 unique Source segments and records 209 exact Mention occurrences.

The catalog status is `human_reviewed_development_gold`.

The catalog does not claim held-out or release-gate authority.
