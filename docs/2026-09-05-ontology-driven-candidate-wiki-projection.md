# TDD: Ontology-Driven Candidate Wiki Projection

- Status: Implemented; focused and existing-state verification complete
- Program: [Candidate Ingestion Review](2026-08-24-candidate-ingestion-review-program.md)
- Deliverable ID: CIR-4.1
- Depends on: [CIR-4 Deterministic Candidate Wiki MVP](2026-09-04-deterministic-candidate-wiki-mvp.md)
- Uses: [HP-6 Qualified Event Semantics](2026-09-02-qualified-event-semantics-source-support.md)

## 1. Context & Problem

CIR-4 renders each Assertion as one subject, relation, and object line.

HP-7 represents a governed Event with several structural Assertions.

Each `has_argument` Assertion records one governed frame role in its qualifiers.

The CIR-4 planner discards those qualifiers when it creates a `WikiStatement`.

The resulting page exposes storage syntax instead of the represented event.

For example, a source passage says that Amodei described Donald Trump as a
"feudal warlord."

One incomplete standing Assertion instead records Amodei, the proposed relation
`described as feudal warlord`, and the literal `"feudal warlord"`.

The Candidate Wiki cannot recover Donald Trump from that incomplete Assertion.

The first CIR-4.1 implementation converted complete Event frames into fluent prose.

That made a poor role assignment look like a supported natural-language claim.

For example, one pending Event records `Trump` as the evaluated subject and
`Trump's approach to export restrictions on semiconductors` as the characterization.

The prose projection rendered this as "Amodei characterized Trump as Trump's approach."

The source says only that Amodei criticized Trump's approach.

The Candidate Wiki must therefore present the admitted ontology graph mechanically.

It must not synthesize prose that is more fluent or apparently certain than the graph.

### Terms

**WikiAssertionPresentation** means one deterministic presentation of one ordinary Assertion.

**WikiEventPresentation** means one deterministic presentation of one Event and its structural Assertions.

**WikiOntologyEdge** means one subject-predicate-object edge copied from one typed Assertion.

**WikiOntologyQualifier** means one key-value qualifier attached to a WikiOntologyEdge.

**Complete governed Event** means an Event whose structural Assertions satisfy one
`HYBRID_EVENT_SEMANTICS_V1` frame.

**Incomplete governed Event** means an Event whose structural Assertions name one governed
frame but omit or conflict with a required role.

**Audit catalog** means the immutable structured build file that maps stable Domain record IDs to
their ontology edges, review state, ProposedChanges, ProvenanceActivities, and evidence references.

**Wiki audit** means deterministic resolution of one stable Domain record ID through an immutable
Wiki build's manifest, audit catalog, and citation registry.

### Primary end-to-end flow

1. The user runs the existing Candidate Wiki build command.
2. The Application Layer resolves the selected CandidateKnowledgeView.
3. The Application Layer groups structural Assertions by Event.
4. The Application Layer creates WikiEventPresentations and WikiAssertionPresentations.
5. The exporter renders ontology edges and stable audit handles without inline evidence excerpts.
6. The exporter writes structured `audit.json` and `citations.json` files.
7. The Archive Adapter validates and publishes the immutable Candidate Wiki build.
8. A user or Wiki agent resolves provenance on demand with `kotekomi wiki audit`.

## 2. Goals

- A user can inspect exactly what an admitted ontology graph says.
- A user can distinguish ontology interpretation from exact source wording.
- A user can see poor or incomplete role assignments without prose hiding them.
- A user can trace each presentation to exact evidence using its stable Domain ID on demand.
- Routine human and model reading does not consume context on unused provenance details.
- The Candidate Wiki exposes incomplete ontology state without inventing missing meaning.
- Equal CandidateKnowledgeViews produce byte-identical Candidate Wiki builds.

## 3. Requirements

### Presentation planner

- OWP-PLAN-01: The Application Layer creates presentations from typed CandidateKnowledgeView records.
- OWP-PLAN-02: The planner groups structural Assertions by their Event subject.
- OWP-PLAN-03: The planner reads `frame_role_id` and `upper_role` from `has_argument` qualifiers.
- OWP-PLAN-04: The planner validates a named frame against `HYBRID_EVENT_SEMANTICS_V1`.
- OWP-PLAN-05: The planner creates one WikiEventPresentation per governed Event.
- OWP-PLAN-06: The planner creates one WikiAssertionPresentation per ungrouped Assertion.
- OWP-PLAN-07: The planner includes every Assertion in exactly one presentation.
- OWP-PLAN-08: The planner associates an Event presentation with each referenced named record page.
- OWP-PLAN-09: The planner associates an Assertion presentation with its subject and entity object pages.
- OWP-PLAN-10: The planner associates every presentation with the selected Document page.
- OWP-PLAN-11: The planner orders presentations by first citation number and stable identity.
- OWP-PLAN-12: The planner includes each presentation in the page input fingerprint.

### Governed Event presentation

- OWP-EVT-01: A WikiEventPresentation identifies its Event and component Assertions.
- OWP-EVT-02: A WikiEventPresentation records the governed frame ID.
- OWP-EVT-03: A WikiEventPresentation records every structural Assertion as one WikiOntologyEdge.
- OWP-EVT-04: Each edge preserves its exact structural predicate, object, and qualifiers.
- OWP-EVT-05: A WikiEventPresentation combines the citations of its component Assertions.
- OWP-EVT-06: A complete governed Event receives the mechanical label `{frame label} Event`.
- OWP-EVT-07: An incomplete governed Event receives the mechanical label
  `Incomplete {frame label} Event`.
- OWP-EVT-08: An incomplete governed Event lists each missing or conflicting required role.
- OWP-EVT-09: A new governed frame uses the same generic edge renderer without a new prose rule.
- OWP-EVT-10: Polarity and modality remain explicit structural edges.
- OWP-EVT-11: Optional frame roles remain explicit structural edges.
- OWP-EVT-12: The projection does not paraphrase, invert, or complete an ontology edge.

### Ordinary Assertion presentation

- OWP-AST-01: A WikiAssertionPresentation identifies its Assertion or ProposedAssertion.
- OWP-AST-02: The presentation records its subject, relation, object, and qualifiers as one
  WikiOntologyEdge.
- OWP-AST-03: A pending relation uses the label `Proposed relationship`.
- OWP-AST-04: An accepted relation uses the label `Relationship`.
- OWP-AST-05: The presentation displays a string literal without JSON escape syntax.
- OWP-AST-06: The presentation preserves a non-string literal through canonical JSON.
- OWP-AST-07: The presentation does not infer a missing entity from source text.
- OWP-AST-08: The presentation does not convert an open relation label into a governed frame.

### Page content

- OWP-PAGE-01: A named-record page starts with identity details and review state.
- OWP-PAGE-02: The page lists each Event frame and its role edges under `At a glance`.
- OWP-PAGE-03: The page lists ordinary pending Assertions under `Relationships requiring review`.
- OWP-PAGE-04: The page renders one detailed section for each presentation.
- OWP-PAGE-05: A detailed section displays its ontology object graph.
- OWP-PAGE-06: A page does not inline source excerpts or detailed provenance.
- OWP-PAGE-07: Every page carries its Wiki build ID once in YAML frontmatter.
- OWP-PAGE-08: Every Domain-record page carries its stable record ID in YAML frontmatter.
- OWP-PAGE-09: A page renders a self-reference as text instead of a self-link.
- OWP-PAGE-10: The page labels pending and accepted presentations distinctly.
- OWP-PAGE-11: Every Event and Assertion presentation visibly carries its stable Domain record ID.
- OWP-PAGE-12: Pages contain no presentation-only citation numbers or audit command instructions.

### Audit catalog and command

- OWP-AUD-01: Every build contains canonical `audit.json` and `citations.json` files.
- OWP-AUD-02: The audit catalog identifies every projected Source, Document, and intelligence record.
- OWP-AUD-03: An audit record preserves its exact admitted payload and payload digest.
- OWP-AUD-04: An audit record lists its ontology edges, ProposedChanges, ProvenanceActivities, and
  evidence reference keys.
- OWP-AUD-05: Audit catalog evidence keys resolve only through the same build's citation registry.
- OWP-AUD-06: `wiki audit` resolves one build ID and record ID without parsing Markdown.
- OWP-AUD-07: Audit output includes exact source text, source selectors, and available validation IDs.
- OWP-AUD-08: Missing records, mismatched snapshots, unsafe build IDs, changed files, and dangling
  audit references fail explicitly.
- OWP-AUD-09: `--format json` emits a stable structured result suitable for a Wiki agent.
- OWP-AUD-10: Default text output remains directly inspectable by a human.
- OWP-AUD-11: The manifest defines the trusted build closure.
- OWP-AUD-12: Publication and audit exclude unmanifested editor files from validation and output.

### Deterministic rendering and publication

- OWP-REN-01: The exporter renders only validated presentation DTOs.
- OWP-REN-02: The exporter makes no model-runtime call.
- OWP-REN-03: The exporter escapes Markdown and HTML control text from source records.
- OWP-REN-04: Equal page inputs produce byte-identical Markdown.
- OWP-REN-05: The renderer policy ID changes from the CIR-4 policy ID.
- OWP-REN-06: The view policy ID changes from the CIR-4 policy ID.
- OWP-REN-07: The build manifest covers every changed page input and output byte.
- OWP-REN-08: The Archive Adapter preserves prior immutable builds.
- OWP-REN-09: The mechanical graph revision uses new view and renderer policy IDs.
- OWP-REN-10: The build ID derives from pinned snapshot and policy identity without hashing its own
  rendered appearance in page frontmatter.
- OWP-REN-11: The manifest independently hashes every output file and rejects changed bytes.

## 4. Proposed Architecture

```text
Ledger + Archive
      |
      v
CandidateKnowledgeView
      |
      v
Ontology graph presentation planner
      |
      +--> WikiEventPresentation
      +--> WikiAssertionPresentation
      +--> WikiOntologyEdge
      +--> WikiAuditCatalog
      +--> WikiCitationRegistry
      |
      v
Markdown Wiki exporter
      |
      v
Candidate Wiki Archive Port
      |
      v
review/wiki-builds/<build-id>/
      |
      +--> Markdown graph pages
      +--> audit.json
      +--> citations.json
      +--> manifest.json
```

The Application Layer owns ontology grouping and completeness decisions.

The exporter owns Markdown layout and escaping.

The Archive Adapter owns immutable build publication.

## 5. Key Interactions

```text
User              Pipeline          Application        Exporter          Archive
 |                   |                   |                 |                |
 | wiki build        |                   |                 |                |
 |------------------>|                   |                 |                |
 |                   | load view         |                 |                |
 |                   |------------------>|                 |                |
 |                   |                   | plan pages      |                |
 |                   |                   |---------------->|                |
 |                   |                   |                 | render files   |
 |                   |                   |                 |--------------->|
 |                   |                   |                 |                | publish
 |<------------------| review/wiki/      |                 |                |
```

## 6. Data Model

CIR-4.1 adds no canonical Domain record.

CIR-4.1 adds no Ledger table or migration.

The Candidate Wiki remains disposable derived state.

`WikiEventPresentation`, `WikiAssertionPresentation`, `WikiOntologyEdge`, and
`WikiOntologyQualifier` are
immutable Application Layer DTOs.

`audit.json`, `citations.json`, and `manifest.json` are derived structured build files.

The Wiki build ID is derived from the candidate snapshot, policy identities, ingestion identities,
and counts. The manifest separately binds every rendered output byte. This avoids a circular identity
when the build ID appears in page frontmatter and makes an unannounced renderer-policy change conflict
with the existing immutable build.

## 7. APIs / Interfaces

The public command remains:

```text
kotekomi wiki build <filename> --candidate
```

The provenance command is:

```text
kotekomi wiki audit --build-id <build-id> --record-id <record-id> [--format text|json]
```

The build command returns the existing active Candidate Wiki path.

Neither command adds a model-runtime option.

## 8. Behavior & Domain Rules

CIR-4.1 supersedes CIR-4 requirements CW-PLAN-06, CW-PLAN-07, and CW-REN-06
through CW-REN-09 for Candidate Wiki presentation only.

CIR-4.1 preserves CIR-4 view selection, evidence replay, publication, and authority rules.

The planner treats the ontology records as the only source of projected meaning.

The renderer shows graph edges and does not generate event prose.

The source text remains evidence and does not supply missing presentation fields. It is emitted only
by deterministic audit resolution, not by the routine Markdown projection.

Held extraction previews do not enter the Candidate Wiki.

Stable Domain IDs are audit handles. The audit catalog does not make the Wiki canonical state.

## 9. Acceptance Criteria

- AC-OWP-01: Application tests prove complete and incomplete Event grouping under OWP-PLAN.
- AC-OWP-02: Application tests prove generic edge rendering across every governed frame.
- AC-OWP-03: Application tests prove neutral ordinary Assertion rendering under OWP-AST.
- AC-OWP-04: Page tests prove human layout and page association under OWP-PAGE.
- AC-OWP-05: Exporter tests prove build frontmatter, stable record handles, lean pages, and structured
  audit retention under OWP-AUD.
- AC-OWP-06: Exporter tests prove escaping and byte identity under OWP-REN.
- AC-OWP-07: Pipeline tests prove the public command and zero model calls.
- AC-OWP-08: Archive tests prove immutable build replacement remains unchanged.
- AC-OWP-09: The existing HP-10 state rebuild resolves exact Amodei source evidence through
  `wiki audit`.
- AC-OWP-10: The Amodei standing Assertion does not become a Trump characterization Event.
- AC-OWP-11: A complete characterization fixture names evaluator, subject, and characterization.
- AC-OWP-12: Ruff, Pyright, focused tests, and the full test suite pass.
- AC-OWP-13: The export-restriction fixture exposes its poor role assignment mechanically and
  contains no synthesized sentence claiming that Amodei characterized Trump as an approach.
- AC-OWP-14: Structured audit evidence contains no empty alias evidence target.
- AC-OWP-15: Application tests prove exact record and evidence resolution without Markdown parsing.
- AC-OWP-16: Adapter tests prove complete immutable-build validation before audit reads.
- AC-OWP-17: Pipeline tests prove public `wiki audit` routing and JSON output selection.

## 10. Reference Implementations

- Candidate view planning: follow `packages/application/src/kotekomi_application/candidate_wiki.py`.
- Governed frame definitions: follow `packages/domain/src/kotekomi_domain/hybrid_event_ontology.py`.
- Markdown rendering: follow `packages/exporters/src/kotekomi_exporters/markdown_wiki.py`.
- Statement references: follow [Wikidata statements](https://www.wikidata.org/wiki/Help:Statements).
- Entity fact layout: follow [Semantic MediaWiki factboxes](https://www.semantic-mediawiki.org/wiki/Help:Factbox).
- Readable source references: follow [GraphRAG outputs](https://microsoft.github.io/graphrag/index/outputs/).

## 11. Constraints and Halt Conditions

Stop if the exporter needs a model judgment.

Stop if the planner must read a held extraction preview.

Stop if the page hides an admitted Assertion.

Stop if a presentation requires meaning absent from the admitted ontology records.
