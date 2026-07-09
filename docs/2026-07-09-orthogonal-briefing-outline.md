# Orthogonal Briefing Outline

## 1. Context & Problem

KoteKomi generates a Briefing from accepted Ledger records.

The current Briefing repeats the same judgment across multiple sections.

That repetition weakens readability and blurs each section purpose.

KoteKomi needs a Briefing outline where each section answers one intelligence question.

## 2. Goals

- The Briefing Markdown uses eight human-facing sections with distinct purposes.
- The Briefing keeps citation numbers readable for humans.
- The Briefing keeps citation resolution in structured derived records for agents.
- The Briefing separates source reports, analytic inferences, evidence quality, implications, and gaps.
- The Briefing exposes Domain meaning without exposing raw canonical Domain IDs.

## 3. Non-Goals & Forbidden Approaches

Non-goals:

- This TDD does not add model-generated prose.
- This TDD does not change Ledger persistence rules.
- This TDD does not change Domain Core record schemas.
- This TDD does not add a hosted Briefing service.

Forbidden approaches:

- The renderer must not parse Markdown to recover citations.
- The renderer must not invent claims absent from accepted Ledger records.
- The human-facing Briefing must not expose raw canonical Domain IDs by default.
- The Briefing generator must not fetch specific Domain types through enumerated repository calls.
- The Briefing must not use repeated sections to restate the same judgment.

## 4. Requirements

- The Briefing Markdown must contain `Executive Judgment`.
- The Briefing Markdown must contain `What Changed`.
- The Briefing Markdown must contain `Judgment Basis`.
- The Briefing Markdown must contain `Evidence and Source Quality`.
- The Briefing Markdown must contain `Open Questions and Collection Gaps`.
- The Briefing Markdown must contain `Indicators to Watch`.
- The Briefing Markdown must contain `Implications`.
- The Briefing Markdown must contain `Reference Appendix`.
- The top-level sections must render in the listed order.
- The Briefing Markdown must keep numbered citation markers beside cited prose.
- The citation registry must map each citation number to canonical Domain IDs.
- Agents must resolve citations through the citation registry.
- `Executive Judgment` must contain the highest-value analytic conclusion.
- `What Changed` must list accepted source-backed developments since the previous Briefing.
- `Judgment Basis` must explain the reasoning chain for the executive judgment.
- `Evidence and Source Quality` must classify cited support by `SourceAuthority`.
- `Evidence and Source Quality` must classify cited support by `AttributionBasis`.
- `Open Questions and Collection Gaps` must list intelligence gaps.
- `Open Questions and Collection Gaps` must not list schema completeness gaps.
- `Indicators to Watch` must list future observable signals.
- `Implications` must state consequences derived from accepted records.
- `Reference Appendix` must contain supporting trace and entity context.

## 5. Invariants

- A Briefing narrative is derived only from accepted Ledger records.
- A Briefing citation registry stores structured citation records beside the Markdown.
- An agent resolves citation numbers without parsing Markdown.
- Source-backed Assertions preserve Source and EvidenceSpan boundaries.
- Analytic inferences remain labeled as analytic inferences.
- Default human-facing Markdown does not expose raw canonical Domain IDs.
- The Application Layer owns Briefing section decisions.
- The Markdown renderer only renders structured Briefing input.

## 6. Proposed Architecture

The Pipeline invokes the Briefing generation use case.

The Application Layer selects accepted canonical records from the Ledger.

The Application Layer builds structured narrative sections and the citation registry.

The Briefing Renderer converts structured narrative sections into Markdown.

The Archive stores the Markdown and citation registry as derived Briefing outputs.

```text
+------------------+       +---------------------+
| Pipeline         | ----> | Application Layer   |
| briefing command |       | generate Briefing   |
+------------------+       +----------+----------+
                                      |
                                      v
                           +---------------------+
                           | Briefing Narrative  |
                           | structured sections |
                           +----------+----------+
                                      |
                                      v
                           +---------------------+
                           | Briefing Renderer   |
                           | Markdown output     |
                           +----------+----------+
                                      |
                                      v
                           +---------------------+
                           | Archive             |
                           | Markdown + registry |
                           +---------------------+
```

## 7. Key Interactions

### Generate First Briefing

```text
Pipeline -> Application Layer: generate Briefing
Application Layer -> Ledger: list accepted canonical records
Ledger -> Application Layer: accepted records
Application Layer -> Application Layer: build eight structured sections
Application Layer -> Renderer: render Briefing input
Renderer -> Application Layer: Markdown
Application Layer -> Archive: store Markdown and citation registry
Application Layer -> Ledger: save Briefing and ProvenanceActivity
```

### Resolve Citation

```text
Agent -> Archive: read citation registry
Archive -> Agent: structured citation registry
Agent -> Application Layer: resolve citation number
Application Layer -> Agent: Source IDs, EvidenceSpan IDs, Assertion IDs
```

### Render Human Markdown

```text
Renderer -> Briefing input: read structured sections
Renderer -> Renderer: append citation markers
Renderer -> Renderer: render Reference Appendix
Renderer -> Application Layer: Markdown
```

## 8. Data Model

`BriefingNarrative` represents the eight-section outline.

Schema sketch:

```text
BriefingNarrative
- executive_judgment: BriefingNarrativeSentence | None
- what_changed: tuple[BriefingNarrativeSentence, ...]
- judgment_basis: tuple[BriefingJudgmentBasis, ...]
- evidence_quality: tuple[BriefingEvidenceQuality, ...]
- collection_gaps: tuple[BriefingOpenQuestion | BriefingUncertainty, ...]
- indicators_to_watch: tuple[BriefingNarrativeSentence, ...]
- implications: tuple[BriefingNarrativeSentence, ...]
- reference_appendix: BriefingReferenceAppendix
```

`BriefingEvidenceQuality` exposes human-readable evidence quality.

Schema sketch:

```text
BriefingEvidenceQuality
- claim: BriefingNarrativeSentence
- source_authority: SourceAuthority
- attribution_basis: AttributionBasis
- source_count: int
- evidence_span_count: int
- citation_numbers: tuple[int, ...]
```

`BriefingReferenceAppendix` contains structured trace material.

Schema sketch:

```text
BriefingReferenceAppendix
- analytic_trace: tuple[BriefingNarrativeSentence, ...]
- selected_actor_ids: tuple[str, ...]
- selected_organization_ids: tuple[str, ...]
- selected_event_ids: tuple[str, ...]
- selected_outcome_ids: tuple[str, ...]
- selected_source_ids: tuple[str, ...]
```

## 9. APIs / Interfaces

The Application Layer updates `BriefingNarrative`.

The renderer input remains `BriefingRenderInput`.

The renderer reads the new `BriefingNarrative` sections.

The citation registry JSON shape remains structured and numbered.

The public citation resolver keeps accepting `BriefingCitationRegistry` and a citation number.

The Ledger repository keeps using `list_accepted_canonical_records`.

## 10. Behavior & Domain Rules

`Executive Judgment` states one primary conclusion.

`What Changed` states observed developments from source-backed accepted Assertions and Outcomes.

`Judgment Basis` explains why KoteKomi reached the executive judgment.

`Evidence and Source Quality` describes evidence strength without restating the full narrative.

`Open Questions and Collection Gaps` states missing intelligence needed to sharpen confidence.

`Indicators to Watch` lists observable future developments.

`Implications` states consequences derived from current Ledger state.

`Reference Appendix` carries supporting trace and entity context.

Human prose uses citation numbers only.

Structured citation records store canonical Domain IDs.

Citation numbers remain stable within one generated Briefing.

Every cited source-backed Assertion citation includes Source IDs and EvidenceSpan IDs.

Every cited analytic inference citation includes Assertion IDs.

Every cited analytic inference citation includes supporting ArgumentEdge IDs when they exist.

Source reports use concrete source phrasing.

Analytic inferences use concrete inference phrasing.

The Briefing says whether a statement came from a Source or from KoteKomi analysis.

The Briefing must not soften concrete records with vague phrases like `appears to`.

### Worked Example

A source-backed Assertion says Commerce requested a pause.

`What Changed` can state the Commerce pause request.

`Evidence and Source Quality` can state secondary reporting and reported-by-source attribution.

`Judgment Basis` can connect the pause request to rollout delay and pilot suspension.

`Executive Judgment` can state the inferred release-governance constraint.

## 11. Acceptance Criteria

- Generated fixture Briefing contains exactly the eight required top-level sections.
- Generated fixture Briefing omits top-level `Bottom Line`.
- Generated fixture Briefing omits top-level `Judgment`.
- Generated fixture Briefing omits top-level `Key Judgments`.
- Generated fixture Briefing omits top-level `Evidence Basis`.
- Generated fixture Briefing omits top-level `Analytic Trace`.
- Generated fixture Briefing states the Anthropic-Commerce conclusion plainly in `Executive Judgment`.
- Generated fixture Briefing distinguishes source reports from KoteKomi analytic inferences.
- Generated fixture Briefing does not expose raw canonical Domain IDs outside structured citation records.
- Generated fixture Briefing includes evidence quality rows for source-backed Assertions.
- The citation registry resolves every visible citation number.
- The citation registry includes Assertion IDs, Source IDs, and EvidenceSpan IDs where applicable.
- The citation registry includes ArgumentEdge IDs for cited analytic inferences where applicable.
- Tests verify that agents can resolve citations without Markdown parsing.
- Tests verify that repeated prose does not appear across primary narrative sections.

## 12. Cross-Cutting Concerns

Error handling follows existing boundary validation rules.

Invalid structured Briefing input fails before Markdown rendering.

The renderer remains deterministic.

The Briefing generator preserves current local-first behavior.

## 13. Reference Implementations

- `packages/application/src/kotekomi_application/briefing_generation.py` shows current narrative assembly.
- `packages/application/src/kotekomi_application/ports.py` defines Briefing DTOs.
- `packages/briefing/src/kotekomi_briefing/markdown.py` renders current Markdown.
- `packages/pipelines/tests/test_briefing_generate.py` verifies fixture end-to-end output.
- `packages/application/tests/test_generate_briefing.py` verifies Application Layer Briefing behavior.

## 14. Alternatives Considered

- Keep existing sections and reduce duplication.
  Rejected because section identities remain unclear.
- Move all trace content out of Markdown.
  Rejected because humans need a readable appendix.
- Add model-generated narrative synthesis now.
  Rejected because deterministic authority boundaries need to land first.
- Make citations a Markdown-only feature.
  Rejected because agents must resolve citations through structured records.

## 15. Halt Conditions

- Halt if the eight-section outline cannot render without exposing raw canonical Domain IDs.
- Halt if citation resolution requires parsing Markdown.
- Halt if the Application Layer cannot derive a section from accepted Ledger records.
- Halt if tests require fixture claims absent from accepted Domain records.
