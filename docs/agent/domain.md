# Domain Rules

## Canonical Terms

Use these exact terms.

| Term | Meaning |
|---|---|
| KoteKomi | The project. |
| Domain Core | The package that defines domain types, domain rules, and ontology semantics. |
| Application Layer | The package that implements use cases through Ports. |
| Adapter | A package that implements a Port for a tool. |
| Port | An interface that the Application Layer calls. |
| Pipeline | A command-line workflow that composes Application Layer use cases. |
| Ledger | The canonical local SQLite database. |
| Archive | The local file tree for Sources, Documents, Briefings, and exports. |
| Actor | A person or role-bearing entity. |
| Organization | A company, agency, lab, publisher, university, nonprofit, think tank, or institution. |
| Event | A bounded real-world happening with time, participants, and optional place. |
| Place | A physical or virtual location. |
| Source | An external artifact that contains information. |
| Document | A local archived copy of a Source or extracted content from a Source. |
| EvidenceTarget | A precise pointer to evidence inside a Document. |
| Assertion | An atomic statement about the world, a Source, another Assertion, or an inference. |
| Relationship | A typed edge between two domain objects. |
| ArgumentEdge | A typed edge between two Assertions. |
| Outcome | A real-world result linked to Actors, Organizations, Events, or Assertions. |
| ProvenanceActivity | A recorded action that created or changed domain records. |
| ProposedChange | A model-generated or script-generated change that awaits human review. |
| Briefing | A generated report that explains changed state since a previous Briefing. |
| Ontology Profile | The internal ontology used by the Domain Core. |
| EpistemicScope | The kind of claim an Assertion makes. |
| SourceAuthority | The authority level of Source evidence for an Assertion. |
| AttributionBasis | The way an Assertion attributes a claim to an Actor, Organization, or Source. |

Do not introduce synonyms for these terms.

## Ontology Profile

The Ontology Profile centers on Assertion.

The system uses Assertion rather than Fact.

An Assertion tracks uncertainty, contradiction, and inference.

The Ontology Profile maps to these external patterns:

| Standard pattern | KoteKomi use |
|---|---|
| Wikidata statement model | Assertion subject-predicate-object pattern with qualifiers and references |
| W3C PROV-O | ProvenanceActivity model |
| Nanopublication pattern | Assertion plus provenance plus publication metadata |
| W3C Web Annotation | EvidenceTarget targeting |
| Simple Event Model | Event, Actor, Place, Time pattern |
| CIDOC CRM | future reference for deeper Event modeling |
| AIF | ArgumentEdge semantics |
| Schema.org / ClaimReview | export format |

## Assertion Rules

An Assertion has one subject.

An Assertion has one predicate.

An Assertion has either one object entity or one object value.

An Assertion has an EpistemicScope.

An Assertion has a SourceAuthority.

An Assertion has an AttributionBasis.

An accepted Assertion has at least one ProvenanceActivity.

A Source-backed Assertion has at least one Source.

A Source-backed accepted Assertion has at least one EvidenceTarget.

An analytic inference has `assertion_type = analytic_inference`.

An analytic inference has `epistemic_scope = analytic_inference`.

A non-source analytic inference has `source_authority = not_applicable`.

A non-source analytic inference has `attribution_basis = not_applicable`.

An attributed statement has `attributed_to_id`.

A primary-source-backed Assertion has authority Source IDs and authority EvidenceTarget IDs.

A causal analytic inference has `causal_confidence`.

A contradiction creates an ArgumentEdge with `relation = contradicts`.

A superseded Assertion keeps its original record.

## ProposedChange Rules

A ProposedChange starts with `review_status = pending`.

A reviewer can approve, reject, or edit a ProposedChange.

An approved ProposedChange creates or updates accepted records.

A rejected ProposedChange remains in the Ledger.

An edited ProposedChange stores the original proposed JSON and the accepted JSON.

Each review action creates a ProvenanceActivity.

## Confidence Dimensions

Use separate confidence dimensions.

| Dimension | Meaning |
|---|---|
| `source_report_confidence` | Confidence that the Source said the thing. |
| `extraction_confidence` | Confidence that the system parsed the Source correctly. |
| `world_truth_confidence` | Confidence that the Assertion is true. |
| `causal_confidence` | Confidence that one thing caused or influenced another thing. |

"The Source said X" is not the same as "X is true."

## Briefing Rules

A Briefing compares current Ledger state with the previous Briefing.

A Briefing Markdown uses numbered citations for Source-backed Assertions.

A Briefing citation registry stores Source IDs and EvidenceTarget IDs for accepted Source-backed Assertions.

A Briefing stores numbered citations as structured derived data alongside the Markdown file.

Agents resolve Briefing citations through the structured citation registry, not by parsing Markdown.

Default human-facing Briefing Markdown does not expose raw canonical Domain IDs.

A Briefing labels analytic inferences.

A Briefing records the ProvenanceActivity that generated it.

A Briefing narrative is derived from accepted Ledger records.

A Briefing narrative does not introduce unsupported claims.

A Briefing narrative preserves Source, EvidenceTarget, Assertion, Relationship, ArgumentEdge, and Outcome boundaries.
