# Assertion Epistemic Scope and Source Authority TDD

## Context & Problem

KoteKomi records Assertions instead of Facts.
An Assertion can describe what a Source reports, what an Actor stated, what KoteKomi accepts as world state, or what KoteKomi infers.
The current Assertion shape separates source report confidence from world truth confidence.
It does not identify the Assertion's epistemic scope or the authority basis for the Source evidence.

## Goals

- Represent the Assertion's epistemic scope as a required Domain Core field.
- Represent Source authority as a required Domain Core field.
- Represent attribution basis as a required Domain Core field.
- Preserve primary-source references as structured Source and EvidenceSpan IDs.
- Let Briefings explain scope and authority in plain prose.
- Let agents inspect scope and authority without parsing Briefing Markdown.

## Non-Goals & Forbidden Approaches

- Do not fetch linked primary Sources in this TDD.
- Do not build source credibility scoring in this TDD.
- Do not export RDF, JSON-LD, ClaimReview, or Nanopublication records in this TDD.
- Do not infer primary authority from a news article that merely mentions an official source.
- Do not store epistemic scope or Source authority only in `qualifiers`.
- Do not treat `source_report_confidence` as `world_truth_confidence`.
- Do not make Briefing Markdown the machine-readable authority layer.

## Requirements

- Every Assertion declares `epistemic_scope`.
- Every Assertion declares `source_authority`.
- Every Assertion declares `attribution_basis`.
- An attributed statement identifies the Actor or Organization that made the statement.
- A primary-source-backed Assertion identifies the Source and EvidenceSpan that establish primary authority.
- Model output fails validation before `ProposedChange` when an Assertion omits required epistemic fields.
- Ledger reads fail validation when stored Assertion payloads violate epistemic rules.
- Briefings distinguish Source reports, attributed statements, world-state Assertions, causal explanations, and inferences.

## Invariants

- Assertion remains the center of the Ontology Profile.
- EvidenceSpan remains the pointer to text inside a Document.
- ProvenanceActivity remains the record of Domain record creation or change.
- A Source-backed accepted Assertion references at least one EvidenceSpan.
- An accepted Assertion references at least one ProvenanceActivity.
- Source authority never upgrades an Assertion's world truth confidence by itself.
- Agents resolve authority through structured Domain fields.

## Proposed Architecture

```text
Model output
  -> Application validation
  -> ProposedChange
  -> Review use case
  -> Assertion Domain validation
  -> Ledger payload JSON
  -> Briefing generation
```

Domain Core owns epistemic validation.
The Application Layer parses model proposals through Domain Core records.
Adapters persist and load Assertion payload JSON through Domain Core parsers.
Pipelines compose these use cases without deciding authority semantics.
Briefing generation renders scope and authority from accepted Domain records.

## Key Interactions

```text
ModelRuntime -> Application: ModelProposal(record_type=Assertion)
Application -> Domain Core: parse Assertion
Domain Core -> Application: valid Assertion JSON or validation error
Application -> Ledger: save ProposedChange
```

```text
Reviewer -> Application: approve ProposedChange
Application -> Domain Core: parse accepted Assertion
Application -> Ledger: save accepted Assertion and ProvenanceActivity
```

```text
Briefing Pipeline -> Ledger: list accepted canonical records
Briefing Pipeline -> Application: generate Briefing
Application -> Domain records: read epistemic fields
Application -> Archive: write Markdown and structured citation registry
```

## Data Model

`Assertion.epistemic_scope` uses these values:

| Value | Meaning |
|---|---|
| `source_report` | The Assertion states what a Source reports. |
| `attributed_statement` | The Assertion states what an Actor or Organization said. |
| `world_state` | The Assertion states a world condition or event. |
| `causal_explanation` | The Assertion states a causal explanation. |
| `analytic_inference` | The Assertion states a KoteKomi inference. |

`Assertion.source_authority` uses these values:

| Value | Meaning |
|---|---|
| `primary` | The Assertion references direct primary evidence. |
| `secondary` | The Assertion references reporting or analysis about the matter. |
| `tertiary` | The Assertion references aggregated or summary material. |
| `unknown` | The Source authority cannot be determined from the Source. |
| `not_applicable` | The Assertion is not Source-backed. |

`Assertion.attribution_basis` uses these values:

| Value | Meaning |
|---|---|
| `direct_document` | The EvidenceSpan is from the issuing Source itself. |
| `quoted_statement` | The EvidenceSpan quotes the attributed Actor or Organization. |
| `reported_by_source` | The EvidenceSpan reports attribution without direct source text. |
| `anonymous_source` | The EvidenceSpan attributes the claim to unnamed people or materials. |
| `unclear` | The EvidenceSpan does not establish attribution clearly. |
| `not_applicable` | The Assertion has no attribution basis. |

Assertion also stores:

- `attributed_to_id`
- `authority_source_ids`
- `authority_evidence_span_ids`

## APIs / Interfaces

The public Assertion schema adds these required fields:

- `epistemic_scope`
- `source_authority`
- `attribution_basis`

The public Assertion schema adds these optional or repeated fields:

- `attributed_to_id`
- `authority_source_ids`
- `authority_evidence_span_ids`

The ModelRuntime proposal contract requires Assertion records to include the required epistemic fields.
The LedgerRepository contract continues to persist payload JSON.
No new Port is required.

## Behavior & Domain Rules

Every Assertion must declare its epistemic scope.
Every Assertion must declare its Source authority.
Every Assertion must declare its attribution basis.

An Assertion with `epistemic_scope = attributed_statement` must include `attributed_to_id`.
An Assertion with `source_authority = primary` must include `authority_source_ids`.
An Assertion with `source_authority = primary` must include `authority_evidence_span_ids`.
Authority Source IDs must be a subset of Source IDs.
Authority EvidenceSpan IDs must be a subset of EvidenceSpan IDs.

An Assertion with `assertion_type = analytic_inference` must use `epistemic_scope = analytic_inference`.
An Assertion with `epistemic_scope = analytic_inference` must use `assertion_type = analytic_inference`.
An analytic inference without Source IDs must use `source_authority = not_applicable`.
An analytic inference without Source IDs must use `attribution_basis = not_applicable`.

Example:

```text
The article says Fable 5 was delayed because of cyber concerns.
epistemic_scope = source_report
source_authority = secondary
attribution_basis = reported_by_source
```

Example:

```text
An official statement says Fable 5 was delayed because of cyber concerns.
epistemic_scope = attributed_statement
source_authority = primary
attribution_basis = direct_document
attributed_to_id = org_white_house
authority_source_ids = [the official statement Source]
authority_evidence_span_ids = [the official statement EvidenceSpan]
```

Example:

```text
KoteKomi infers that Anthropic and Commerce shared a governance outcome.
epistemic_scope = analytic_inference
source_authority = not_applicable
attribution_basis = not_applicable
```

## Acceptance Criteria

- Domain Core rejects Assertion records missing epistemic fields.
- Domain Core rejects primary authority without authority Source and EvidenceSpan references.
- Domain Core rejects attributed statements without attribution.
- Model output cannot become a ProposedChange when an Assertion omits epistemic fields.
- ProposedChange review writes accepted Assertions with epistemic fields preserved.
- SQLite Ledger round-trips Assertions with epistemic fields.
- Briefing Markdown labels source reports and inferences using plain prose.
- Briefing structured data retains citation and authority IDs for agent use.
- The synthetic article Pipeline fixture remains coherent.

## Cross-Cutting Concerns

This TDD changes Domain validation.
Deterministic boundaries fail fast through Domain Core parsers.
The fixture article remains secondary reporting unless the fixture includes a primary Source.

## Reference Implementations

- `packages/domain/src/kotekomi_domain/models.py`
- `packages/application/src/kotekomi_application/model_proposal_validation.py`
- `packages/application/src/kotekomi_application/proposed_change_review.py`
- `packages/application/src/kotekomi_application/briefing_generation.py`

## Alternatives Considered

- Store authority in `qualifiers`: rejected because boundary validation would not enforce it.
- Derive authority from `SourceType`: rejected because Source type does not prove authority.
- Use only confidence dimensions: rejected because confidence does not identify claim ownership.

## Halt Conditions

- Halt if a required epistemic field cannot be represented in Domain Core without Adapter imports.
- Halt if a happy-path fixture requires silent repair to pass validation.
