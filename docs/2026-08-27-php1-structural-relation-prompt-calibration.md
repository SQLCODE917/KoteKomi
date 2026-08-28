# TDD: PHP-1 Structural Direct-Relation Prompt Calibration

- Status: Evaluated
- Program: [PHP-1 Reliability Improvement Program](2026-08-27-php1-reliability-improvement-program.md)
- Deliverable ID: H1
- Depends on: [Segment-Bound PHP-1 Evaluation](2026-08-27-php1-segment-bound-evaluation.md)
- Outcome: Not accepted for production

## Implementation Outcome

The V6 replay matched seven scored Targets.

The V6 replay missed `php1-target-ad-09-anthropic-palantir`.

That Target is a mandatory H0 interoperability baseline.

The H1 scorecard returned `failed`.

The V6 replay matched these scored Targets.

- `php1-target-ad-06-anthropic-palantir`
- `php1-target-ad-06-anthropic-aws`
- `php1-target-ad-07-anthropic-aisi`
- `php1-target-ad-13-anthropic-dod`
- `php1-target-ai-03-uk-aisi-frontier-taskforce`
- `php1-target-ai-04-us-aisi-nist`
- `php1-target-cs-05-anthropic-aisic`

The V6 replay missed these scored Targets.

- `php1-target-ad-04-anthropic-congress`
- `php1-target-ad-09-anthropic-palantir`
- `php1-target-ai-15-aisi-dsit`
- `php1-target-ai-18-us-aisi-nist`

The Pipeline continues to use `paragraph_hypothesis_segment_v3`.

The repository retains V6, the H1 scorecard, and `verify_php1_h1.py` as reproducible calibration
evidence.

H2 will separate Organization mention detection from direct-relationship judgment.

## 1. Context & Problem

H0 established a source-segment-bound, verifier-gated PHP-1 baseline.

The baseline matched partnerships and interoperability but missed containment, lineage, membership,
agreement, and directed institutional relationships.

The existing prompt describes only a `partnered with` direct relation.

The existing prompt does not say that a direct binary relation can be expressed without `with`.

The existing prompt does not distinguish an ordered relation from coordinated participants in one Event.

**Structural direct relation** means an ordered direct relation such as containment, lineage, membership,
agreement, directed action, or refusal between two literal named Organizations.

**H1 scorecard** means the versioned held-out Target set and pass threshold for this prompt change.

**Observation target** means a catalog target reported for review but excluded from the H1 pass threshold.

### Primary end-to-end flow

1. An ingestion Pipeline derives one authoritative Source copy segment.
2. The Pipeline pins the v6 direct-relation prompt in the ContextManifest and ModelRun.
3. The model returns zero through eight ordinary-language hypothesis lines.
4. Existing deterministic validation and faithfulness verification decide publication eligibility.
5. The packet replay matches verifier-accepted hypotheses to H0 Expectations.
6. The H1 scorecard reports held-out coverage, observations, and unexpected accepted hypotheses.

## 2. Goals

- A reviewer receives more source-grounded structural direct Organization hypotheses.
- The H1 replay uses the versioned V6 extraction prompt.
- H1 measures prompt improvement against held-out Targets instead of anecdotal results.
- H1 preserves unexpected accepted hypotheses for review without claiming an unmeasured precision score.

## 3. Requirements

### Prompt contract

- H1-PROMPT-01: The repository retains v3 as immutable historical prompt provenance.
- H1-PROMPT-02: The H1 replay prompt is `paragraph_hypothesis_segment_v6`.
- H1-PROMPT-03: V6 uses invented generic Organization examples only.
- H1-PROMPT-04: V6 teaches partnership, interoperability, containment, lineage, membership, agreement, directed action, and refusal constructions.
- H1-PROMPT-05: V6 uses generic example wording that mirrors each held-out supported construction.
- H1-PROMPT-06: V6 requires literal ordered subject and object copy from the Source copy view.
- H1-PROMPT-07: V6 directs abstention for coordinated participants in one shared activity.
- H1-PROMPT-08: V6 requires adjacent claim lines and retains the eight-claim maximum.

### Replay provenance

- H1-PROV-01: The H1 replay reads V6 for every PHP-1 Source segment.
- H1-PROV-02: The H1 ContextManifest and ModelExecutionSpec record the V6 prompt ID and digest.
- H1-PROV-03: The rendering policy remains `paragraph_hypothesis_segment_context_v3`.

### Held-out scorecard

- H1-SCORE-01: The repository stores one versioned H1 scorecard separate from the H0 Expectation catalog.
- H1-SCORE-02: The scorecard identifies eleven scored binary direct-Organization Expectations.
- H1-SCORE-03: The scorecard records the UNESCO and MeitY consultation target as an Event-frame observation only.
- H1-SCORE-04: H1 requires all three H0 baseline matches.
- H1-SCORE-05: H1 requires lineage and membership matches.
- H1-SCORE-06: H1 requires one containment match and one directed-action or refusal match.
- H1-SCORE-07: H1 requires at least seven scored Target matches.
- H1-SCORE-08: H1 reports every unexpected verifier-accepted hypothesis without a pass/fail cap.

## 4. Proposed Architecture

```text
Authoritative Source segment
            |
            v
  V6 generic direct-relation prompt
            |
            v
    existing PHP-1 validation
            |
            v
 H0 target report + unexpected list
            |
            v
      H1 held-out scorecard
```

The prompt owns model instruction calibration.

The existing Application Layer owns validation and faithfulness decisions.

The packet diagnostic owns reproducible replay and Target matching.

The H1 scorecard owns the explicit prompt-calibration threshold.

## 5. Key Interactions

```text
Ingestion Pipeline      Model          Verifier       H1 replay
       |                  |                |              |
       | v6 + segment     |                |              |
       |----------------->|                |              |
       | claim lines      |                |              |
       |<-----------------|                |              |
       |------------------------------->|              |
       | accepted hypotheses             |              |
       |<-------------------------------|              |
       |---------------------------------------------->|
       |                    held-out scorecard result  |
       |<----------------------------------------------|
```

## 6. Data Model

V6 is `prompts/paragraph_hypothesis_segment_v6.md`.

The H1 scorecard is `docs/php1-h1-evaluation-v1.json`.

The scorecard root is:

```text
schema_version
scored_expectation_ids
observation_expectation_ids
required_matched_expectation_ids
required_any_matched_expectation_id_sets
minimum_matched_count
```

The H1 result contains matched and missing scored Target IDs, missing required IDs and groups,
the Event-frame observation result, and unexpected verifier-accepted hypotheses.

The scorecard does not create Ledger state.

## 7. APIs / Interfaces

`uv run python scripts/verify_php1_h1.py` runs the historical packet replay with the V6 prompt.

`--output <path>` writes the complete replay and H1 scorecard result to a local JSON file.

The existing `scripts/verify_php1_packet.py` remains available for a non-gating diagnostic report.

## 8. Behavior & Domain Rules

V6 teaches only literal direct Organization relations that PHP-1 already supports.

V6 does not change Organization type classification, coreference, Source segmentation, or verification.

The consultation observation is not a direct ordered relationship under PHP-1.

It remains visible because a later Event-frame slice must account for such coordinated action.

An unexpected verifier-accepted hypothesis is review evidence, not a precision metric.

H1 does not weaken validation to make the score pass.

## 9. Acceptance Criteria

- AC-H1-01: Tests prove V6 teaches generic direct-relation constructions and contains no H0 corpus Organization names.
- AC-H1-02: Tests prove the H1 replay prompt is V6, the production prompt is V3, and the renderer is V3.
- AC-H1-03: Tests reject malformed, unknown, overlapping, or contradictory H1 scorecard Target sets.
- AC-H1-04: Tests prove the scorecard passes only when all required baseline and structural conditions hold.
- AC-H1-05: Tests prove the consultation observation does not affect the H1 threshold.
- AC-H1-06: Tests prove unexpected hypotheses remain visible in the H1 result.
- AC-H1-07: The local three-fixture packet replay completes with V6 and writes the H1 scorecard result.
- AC-H1-08: The local replay matches at least seven scored Targets, including the required baseline, lineage, membership, containment, and directed-action or refusal targets.

## 10. Reference Implementations

- Production automatic extraction: `packages/pipelines/src/kotekomi_pipelines/cli.py`.
- Isolated replay: `scripts/php1_diagnostic_support.py`.
- Packet diagnostic and scorecard: `scripts/verify_php1_packet.py`.
- H0 target catalog: `docs/php1-evaluation-expectations-v1.json`.

## 11. Constraints and Halt Conditions

H1 does not alter the current verifier, ontology, Source-segment policy, or eight-claim limit.

H1 does not add Events, country handling, people, coreference, or multi-segment evidence.

H1 stops after the held-out replay records a reproducible scorecard result for review.
