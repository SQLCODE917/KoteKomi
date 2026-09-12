# TDD: Ontology-Driven Candidate Wiki Projection

- Status: Implemented; Event presentation superseded by the Source-Grounded Event Boundary
- Program: [Candidate Ingestion Review](2026-08-24-candidate-ingestion-review-program.md)
- Deliverable ID: CIR-4.1
- Depends on: [CIR-4 Deterministic Candidate Wiki MVP](2026-09-04-deterministic-candidate-wiki-mvp.md)
- Uses: [HP-6 Qualified Event Semantics](2026-09-02-qualified-event-semantics-source-support.md)
- Superseded event boundary: [Source-Grounded Event Boundary](2026-09-12-source-grounded-event-boundary.md)

## 1. Context & Problem

CIR-4 renders each Assertion as one subject, relation, and object line.

HP-7 originally represented a governed Event with several structural Assertions.

The Source-Grounded Event Boundary now admits an Event from its exact source expression and embedded
EventMention before any optional classification or argument assignment.

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

**WikiEventPresentation** means one deterministic presentation of one Event, its exact EventMention
evidence, and any admitted structural Assertions.

**WikiOntologyEdge** means one subject-predicate-object edge copied from one typed Assertion.

**WikiOntologyQualifier** means one key-value qualifier attached to a WikiOntologyEdge.

**Audit catalog** means the immutable structured build file that maps stable Domain record IDs to
their ontology edges, review state, ProposedChanges, ProvenanceActivities, and evidence references.

**Wiki audit** means deterministic resolution of one stable Domain record ID through an immutable
Wiki build's manifest, audit catalog, and citation registry.

### Primary end-to-end flow

1. The user runs the existing Candidate Wiki build command.
2. The Application Layer resolves the selected CandidateKnowledgeView.
3. The Application Layer resolves each Event and replays its EventMention evidence.
4. The Application Layer creates WikiEventPresentations and WikiAssertionPresentations.
5. The exporter renders compact intelligence summaries, exact Event evidence, and stable audit handles.
6. The exporter writes structured `audit.json` and `citations.json` files.
7. The Archive Adapter validates and publishes the immutable Candidate Wiki build.
8. A user or Wiki agent resolves provenance on demand with `kotekomi wiki audit`.

## 2. Goals

- A user can inspect exactly what an admitted ontology graph says.
- A user can distinguish ontology interpretation from exact source wording.
- A user can inspect optional argument assignments without those assignments controlling Event visibility.
- A user can trace each presentation to exact evidence using its stable Domain ID on demand.
- Routine human and model reading does not consume context on unused provenance details.
- The Candidate Wiki preserves an Event even when no governed classification or argument assignment exists.
- Equal CandidateKnowledgeViews produce byte-identical Candidate Wiki builds.

## 3. Requirements

### Presentation planner

- OWP-PLAN-01: The Application Layer creates presentations from typed CandidateKnowledgeView records.
- OWP-PLAN-02: The planner creates an Event presentation without requiring structural Assertions.
- OWP-PLAN-03: The planner replays each EventMention EvidenceTarget before presentation.
- OWP-PLAN-04: Optional structural Assertions remain audit material and cannot rename or hide an Event.
- OWP-PLAN-05: The planner creates one WikiEventPresentation per Event.
- OWP-PLAN-06: The planner creates one WikiAssertionPresentation per ungrouped Assertion.
- OWP-PLAN-07: The planner includes every Assertion in exactly one presentation.
- OWP-PLAN-08: The planner associates an Event presentation with each referenced named record page.
- OWP-PLAN-09: The planner associates an Assertion presentation with its subject and entity object pages.
- OWP-PLAN-10: The planner associates every presentation with the selected Document page.
- OWP-PLAN-11: The planner orders presentations by first citation number and stable identity.
- OWP-PLAN-12: The planner includes each presentation in the page input fingerprint.

### Source-grounded Event presentation

- OWP-EVT-01: A WikiEventPresentation identifies its Event and any component Assertions.
- OWP-EVT-02: A WikiEventPresentation uses the Event's exact source expression as its label.
- OWP-EVT-03: A WikiEventPresentation records the EventMention evidence identities.
- OWP-EVT-04: The exact Event source text immediately follows its label.
- OWP-EVT-05: Any component Assertion remains available through the audit catalog.
- OWP-EVT-06: A missing Event Type Assignment does not change the presentation.
- OWP-EVT-07: A classified, unclassified, or partial Event Type Assignment does not change the label.
- OWP-EVT-08: A missing or conflicting role assignment does not hide the Event.
- OWP-EVT-09: A new source expression requires no renderer rule or governed-frame addition.
- OWP-EVT-10: Optional polarity and modality remain derived enrichment until admitted separately.
- OWP-EVT-11: Optional Event arguments remain distinct from EventMention evidence.
- OWP-EVT-12: The projection does not paraphrase, invert, or complete source-grounded meaning.

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
- OWP-PAGE-02: The page lists each exact Event expression under `At a glance`.
- OWP-PAGE-03: The page lists ordinary pending Assertions under `Relationships requiring review`.
- OWP-PAGE-04: The page renders ordinary Assertions as compact relationship lines.
- OWP-PAGE-05: The page does not render internal ontology edges or qualifiers.
- OWP-PAGE-06: `At a glance` shows each Event's exact expression and exact source text; optional
  extracted roles may follow when present.
- OWP-PAGE-07: Every page carries its Wiki build ID once in YAML frontmatter.
- OWP-PAGE-08: Every Domain-record page carries its stable record ID in YAML frontmatter.
- OWP-PAGE-09: A page renders a self-reference as text instead of a self-link.
- OWP-PAGE-10: The page labels pending and accepted presentations distinctly.
- OWP-PAGE-11: Every Event and Assertion presentation visibly carries its stable Domain record ID.
- OWP-PAGE-12: Pages contain no presentation-only citation numbers or audit command instructions.
- OWP-PAGE-13: The renderer deduplicates source references with the same authoritative text range.
- OWP-PAGE-14: Detailed provenance remains available only through `wiki audit`.
- OWP-PAGE-15: Every ordinary Assertion presentation places its exact supporting source text directly
  below the relationship.
- OWP-PAGE-16: An ordinary Assertion source excerpt contains no provenance trace beyond the stable
  Assertion ID and page-level Wiki build ID needed by `wiki audit`.

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
- OWP-REN-12: The superseding source-grounded renderer uses policy ID
  `source_grounded_markdown_wiki_v8`.

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

The Application Layer owns Event evidence replay and presentation planning.

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

`EventMention` is embedded authoritative Ledger state inside an Event.

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

The planner treats the admitted Event and its exact EventMention evidence as the source of Event
presentation meaning.

The renderer shows exact Event expressions and ordinary relationships without generating event prose.

The audit catalog retains the complete ontology graph.

The source text remains evidence and does not supply missing presentation fields.

The routine Markdown projection shows exact Event and ordinary Assertion evidence for review.

Deterministic audit resolution supplies the complete provenance record.

Held extraction previews do not enter the Candidate Wiki.

Stable Domain IDs are audit handles. The audit catalog does not make the Wiki canonical state.

## 9. Acceptance Criteria

- AC-OWP-01: Application tests prove Event presentation with and without structural Assertions.
- AC-OWP-02: Application tests prove Event presentation without a governed frame or type Assertion.
- AC-OWP-03: Application tests prove neutral ordinary Assertion rendering under OWP-AST.
- AC-OWP-04: Page tests prove human layout and page association under OWP-PAGE.
- AC-OWP-05: Exporter tests prove build frontmatter, stable record handles, compact Event evidence,
  and structured audit retention under OWP-AUD.
- AC-OWP-06: Exporter tests prove escaping and byte identity under OWP-REN.
- AC-OWP-07: Pipeline tests prove the public command and zero model calls.
- AC-OWP-08: Archive tests prove immutable build replacement remains unchanged.
- AC-OWP-09: The existing HP-10 state rebuild resolves exact Amodei source evidence through
  `wiki audit`.
- AC-OWP-10: The Amodei standing Assertion does not become a Trump characterization Event.
- AC-OWP-11: A source-grounded characterization fixture preserves its exact expression and source.
- AC-OWP-12: Ruff, Pyright, focused tests, and the full test suite pass.
- AC-OWP-13: The export-restriction fixture exposes its poor role assignment mechanically and
  contains no synthesized sentence claiming that Amodei characterized Trump as an approach.
- AC-OWP-14: Structured audit evidence contains no empty alias evidence target.
- AC-OWP-15: Application tests prove exact record and evidence resolution without Markdown parsing.
- AC-OWP-16: Adapter tests prove complete immutable-build validation before audit reads.
- AC-OWP-17: Pipeline tests prove public `wiki audit` routing and JSON output selection.
- AC-OWP-18: Exporter tests prove duplicate evidence origins produce one source excerpt.
- AC-OWP-19: Exporter tests prove Markdown omits ontology graph details retained by `wiki audit`.
- AC-OWP-20: Exporter tests prove each ordinary relationship shows deduplicated exact source text while
  leaving the full provenance trace in `wiki audit`.

## 10. Reference Implementations

- Candidate view planning: follow `packages/application/src/kotekomi_application/candidate_wiki.py`.
- Source-grounded Event construction: follow
  `packages/application/src/kotekomi_application/source_grounded_events.py`.
- Markdown rendering: follow `packages/exporters/src/kotekomi_exporters/markdown_wiki.py`.
- Statement references: follow [Wikidata statements](https://www.wikidata.org/wiki/Help:Statements).
- Entity fact layout: follow [Semantic MediaWiki factboxes](https://www.semantic-mediawiki.org/wiki/Help:Factbox).
- Readable source references: follow [GraphRAG outputs](https://microsoft.github.io/graphrag/index/outputs/).

## 11. Constraints and Halt Conditions

Stop if the exporter needs a model judgment.

Stop if the planner must read a held extraction preview.

Stop if the page hides an admitted Assertion.

Stop if a presentation requires meaning absent from the admitted ontology records.
