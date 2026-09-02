# TDD: Hybrid Entity Identity Grounding

- Status: Accepted
- Program: [Hybrid Intelligence Extraction Pipeline](2026-09-01-hybrid-intelligence-extraction-pipeline.md)
- Increment: HP-3
- Depends on: [Hybrid Document Reference Resolution](2026-09-01-hybrid-document-reference-resolution.md)
- Scope: derived candidate evidence only

## Context & Problem

HP-1 preserves source-valid MentionCandidates and separates referentiality from contextual kind.

HP-2 resolves only source-verifiable document aliases and preserves ambiguous references.

Neither stage says which external entity a specific source expression might denote.

ReFinED can propose ranked Wikidata candidates from caller-owned spans.

Its highest-scored candidate is fallible model evidence, not an identity decision.

HP-3 sends only eligible exact mentions to a pinned offline ReFinED worker.

HP-3 publishes every returned rank, including NIL, in one immutable HybridEntityGroundingPreview.

HP-3 never resolves an Entity, invokes a language model, creates a ProposedChange, or writes accepted intelligence.

### Terms

**EntityGroundingEligibility** means the terminal HP-3 inclusion or exclusion decision for one HP-1 MentionCandidate.

**EntityLinkCandidate** means one ranked Wikidata or NIL candidate proposed by the entity-linking model.

**EntityLinkEvidence** means one MentionCandidate's exact source span, complete ranked candidates, and model lineage.

**HybridEntityGroundingPreview** means the immutable derived result of one HP-3 run.

### Primary flow

1. An operator selects one immutable HybridReferencePreview.
2. The Pipeline verifies the HP-2 Preview, its HP-1 parent, ContextManifest, and accepted DocumentRepresentationBundle.
3. The Application Layer records one eligibility result for every HP-1 MentionCandidate.
4. The Application Layer groups eligible exact spans by their authoritative SourceSegment.
5. A pinned offline ReFinED worker proposes ranked Wikidata or NIL candidates.
6. KoteKomi validates source alignment, candidate ordering, identities, scores, and titles.
7. The Pipeline archives model output, task/run lineage, traces, and one immutable Preview.

## Goals

- A reviewer can inspect external identity candidates only for source expressions already judged specific.
- A reviewer can trace every candidate to exact authoritative characters and one pinned model run.
- A reviewer can see NIL, runtime failures, and excluded mentions without hidden fallback behavior.
- Replaying the same parent and model evidence produces equivalent candidate evidence.
- The operation changes no accepted intelligence.

## Requirements

### Parent evidence

- HGP-01: The command requires one HybridReferencePreview ID.
- HGP-02: The Pipeline strictly validates the HP-2 Preview's canonical bytes and SHA-256.
- HGP-03: The Pipeline loads and validates the HP-1 parent named by HP-2.
- HGP-04: The HP-1 digest must equal the digest recorded by HP-2.
- HGP-05: The Pipeline rejects a blocked HP-1 parent.
- HGP-06: The Pipeline loads the accepted DocumentRepresentationBundle named by HP-1.
- HGP-07: The Pipeline loads the exact ContextManifest named by HP-1 and validates its representation lineage.
- HGP-08: MentionCandidate text, offsets, SourceSegment identity, and source digest must match authoritative characters.

### Eligibility

- HGE-01: HP-3 records one EntityGroundingEligibility for every HP-1 MentionCandidate.
- HGE-02: A candidate is eligible only when HP-1 selected its boundary.
- HGE-03: A candidate is eligible only when its MentionInterpretation referentiality is `specific_entity`.
- HGE-04: A candidate with an ambiguous HP-1 boundary is ineligible.
- HGE-05: A candidate with a missing MentionInterpretation is ineligible.
- HGE-06: A candidate with generic, unclear, or anaphoric referentiality is ineligible.
- HGE-07: A candidate with an ambiguous or anaphoric HP-2 ReferenceDecision is ineligible.
- HGE-08: A uniquely resolved explicit alias is eligible and retains its HP-2 decision ID.
- HGE-09: An unmatched explicit alias such as `NIST` remains eligible when HP-1 judged it specific.
- HGE-10: Each exclusion uses one named reason and remains visible in the Preview.

### Entity-linking boundary

- HGL-01: The Application Layer defines an ontology-neutral EntityLinkingPort.
- HGL-02: One request contains one exact SourceSegment and ordered eligible MentionCandidates from that segment.
- HGL-03: The Adapter uses ReFinED caller-supplied-span mode.
- HGL-04: ReFinED runs with `apply_class_check=false`, `prune_ner_types=true`, and `return_special_spans=false`.
- HGL-05: ReFinED downloads are disabled during grounding.
- HGL-06: Runtime Python, worker script, resource directory, timeout, package revision, model identity, and resource digest are pinned.
- HGL-07: The worker uses standard output only for line-delimited canonical JSON and sends diagnostics to standard error.
- HGL-08: The worker emits every ReFinED top-k rank, including NIL.
- HGL-09: A knowledge-base candidate has a valid Wikidata `Q` identifier.
- HGL-10: A NIL candidate has no Wikidata identifier or Wikipedia title.
- HGL-11: Ranks are contiguous, start at one, and contain no duplicate external identity.
- HGL-12: Every score is finite.
- HGL-13: Every Wikipedia title is looked up using that ranked candidate's own Wikidata identifier.
- HGL-14: The Adapter rejects changed, reordered, missing, or extra source spans.
- HGL-15: The Adapter rejects malformed output rather than dropping or repairing it.
- HGL-16: ReFinED scores remain model scores and never become evidence confidence.

### Execution evidence

- HGR-01: One SourceSegment request creates one immutable ExtractionTask and one ModelRun.
- HGR-02: The ExtractionTask binds the HP-1 ContextManifest and its digest.
- HGR-03: The task fingerprint binds exact input, policy, worker, model, package, schema, and resource identities.
- HGR-04: The complete canonical worker response is archived as raw ModelRun output.
- HGR-05: A successful run records its output digest, execution receipt, timing, and candidate counts.
- HGR-06: Runtime, protocol, resource, source-alignment, and Archive failures produce failed ModelRuns.
- HGR-07: Missing runtime configuration or resources is a typed blocked outcome, not a configuration crash.
- HGR-08: Every eligibility decision and link evidence item has one ExtractionStageTrace.
- HGR-09: Traces expose exact data in, data out, parent traces, and task/run IDs.

### Preview evidence

- HGV-01: The Preview contains its HP-2 parent ID and digest, HP-1 parent ID and digest, representation ID, and policy ID.
- HGV-02: The Preview contains every eligibility decision in source order.
- HGV-03: The Preview contains all successful EntityLinkEvidence in source and rank order.
- HGV-04: The Preview contains all ExtractionTask IDs, ModelRun IDs, traces, and diagnostics.
- HGV-05: `complete` requires a complete HP-1 parent and successful execution of every eligible batch.
- HGV-06: `partial` results when HP-1 is partial or only some eligible batches fail.
- HGV-07: `blocked` results when every required eligible batch is unavailable or fails.
- HGV-08: A complete parent with no eligible candidates produces an empty complete Preview.
- HGV-09: The Preview uses canonical JSON, content-derived identity, immutable atomic Archive publication, and strict reload validation.
- HGV-10: Replay preserves independent ModelRun lineage and reports equivalent ranked candidates when pinned inputs and model evidence are equivalent.
- HGV-11: Changed authoritative input, parent evidence, policy, model evidence, or execution lineage changes the Preview identity.
- HGV-12: HP-3 creates no Entity, Assertion, ProposedChange, review decision, or accepted Ledger state.

### Configuration and CLI

- HGC-01: Optional strict `[entity_linking]` configuration selects the `refined` Adapter.
- HGC-02: Configuration requires `python_executable`, `data_dir`, and positive `timeout_seconds`.
- HGC-03: Relative runtime paths resolve relative to the selected configuration file.
- HGC-04: Unknown entity-linking keys or Adapter names fail configuration loading.
- HGC-05: The repository-owned worker script is selected by KoteKomi and is not caller-overridable.
- HGC-06: `kotekomi extraction ground-entities --preview-id <hp2-preview-id>` runs HP-3.
- HGC-07: Standard output identifies status, Preview ID, parent Preview ID, digest, and Archive path.
- HGC-08: A complete Preview exits zero; partial or blocked exits one.

## Proposed Architecture

```text
HP-2 Preview + HP-1 Preview + ContextManifest + accepted bundle
    |
    v
Application eligibility policy
    |
    +----> excluded eligibility evidence
    |
    v
EntityLinkingPort
    |
    v
Pinned offline ReFinED Adapter/worker
    |
    v
ranked Wikidata/NIL evidence + ModelRun + traces
    |
    v
immutable HybridEntityGroundingPreview
```

The Application Layer owns eligibility, terminal status, validation intent, and task/run recording.

The Adapter translates the pinned ReFinED protocol into Application DTOs.

The worker executes ReFinED and corrects only the upstream top-k title lookup defect by looking up each title from its own Wikidata identifier.

The Pipeline composes configuration, Ledger, Archive, Application use case, and rendering.

## Acceptance Criteria

- AC-HG-01: A unit test records exactly one eligibility result for every HP-1 candidate.
- AC-HG-02: Unit tests cover selected specific, boundary conflict, missing interpretation, generic, unclear, anaphoric, HP-2 ambiguous, HP-2 unresolved-anaphoric, resolved alias, and unmatched alias cases.
- AC-HG-03: Application tests prove eligible candidates are batched by exact SourceSegment and ineligible candidates are never sent to the Port.
- AC-HG-04: Application tests prove complete, partial, blocked, and empty-complete terminal states.
- AC-HG-05: Adapter tests prove strict protocol validation, offline flags, caller-span options, finite scores, contiguous ranks, distinct Wikidata IDs, NIL, and exact source alignment.
- AC-HG-06: A worker test proves each top-k Wikipedia title corresponds to that candidate's own Wikidata ID.
- AC-HG-07: Archive tests prove immutable create, identical reuse, conflict rejection, and strict reload.
- AC-HG-08: Configuration tests prove valid, relative, missing, and invalid `[entity_linking]` behavior.
- AC-HG-09: CLI tests prove complete and blocked rendering and exit codes.
- AC-HG-10: Tests prove one task/run/raw-output/receipt/trace chain per attempted SourceSegment.
- AC-HG-11: Tests prove HP-3 creates no ProposedChange or accepted intelligence.
- AC-HG-12: Fresh ingestion of the Anthropic PDF can produce HP-1, HP-2, and HP-3 evidence through public commands.
- AC-HG-13: The reviewed Anthropic source span returns Department of Defense (`Q11209`) at rank one.
- AC-HG-14: The reviewed AISI source span returns NIST (`Q176691`) at rank one.
- AC-HG-15: The evaluation records the pinned snapshot's known Anthropic-company and AISI identity misses without promoting incorrect identities or blocking closeout.
- AC-HG-16: Repeating the reviewed evaluation reports equivalent ranks and complete lineage after restart.
- AC-HG-17: Formatting, lint, typecheck, focused tests, and the full repository test suite pass.

## Reviewed Evaluation Contract

The machine-readable contract is [HP-3 Entity Grounding Gold v1](hp3-entity-grounding-gold-v1.json).

The Gold contract pins fixture byte digests and exact source segments from the current accepted
representation policy.

It deliberately does not pin representation, node, or SourceSegment IDs. Those IDs identify one
accepted interpretation and can legitimately change when the authoritative parser improves. The
fixture bytes, exact source characters, and source-text digest are the stable acceptance oracle;
each run must record its current representation and SourceSegment lineage in the HP-3 Preview.

`NIST` and `Department of Defense` are required rank-one wins.

`AISI` and `Anthropic` are known pinned-snapshot gaps.

Known gaps remain visible as evaluation misses and cannot become accepted identity.

## Not in Scope

- selecting or accepting one identity;
- Qwen reranking or adjudication;
- entity creation or alias persistence;
- cross-document identity clustering;
- network access or Wikidata lookup during grounding;
- threshold-based acceptance;
- ProposedChange or accepted Ledger writes;
- changing HP-1 or HP-2 semantics.

## Verification

```bash
uv run pytest packages/application/tests/test_hybrid_entity_grounding.py
uv run pytest packages/adapters/tests/test_refined_entity_linking.py
uv run pytest packages/adapters/tests/test_local_archive_store.py
uv run pytest packages/pipelines/tests/test_cli.py
uv run ruff format --check .
uv run ruff check .
uv run pyright
uv run pytest
```

The reviewed local-fixture acceptance additionally requires the two reviewed untracked PDFs and the
pinned isolated ReFinED runtime.

## Research Basis

[TAC Entity Discovery and Linking](https://catalog.ldc.upenn.edu/docs/LDC2019T02/guidelines/TAC_KBP_2015_EDL_Guidelines_V1.2.pdf) separates mention discovery from identity linking and retains NIL.

[ReFinED](https://aclanthology.org/2022.naacl-industry.24/) models NIL as an explicit entity-link candidate and evaluates ranked linking independently from mention discovery.

[ReFinED's official implementation](https://github.com/amazon-science/ReFinED) supports caller-supplied spans and offline pinned resources.
