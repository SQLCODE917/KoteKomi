# TDD: Evidence-Weighted Graph Projections

- **Status:** Accepted
- **Parent:** [Authoritative Document Ingestion Program](2026-07-11-authoritative-document-ingestion-program.md)
- **Depends on:** replayable evidence, coverage, source lineage, and derived retrieval

## 1. Context and problem

KoteKomi grows a knowledge graph by adding relationships among concepts. A naked model-generated weighted edge hides which assertions, evidence, source versions, lineage groups, review decisions, and temporal conditions produced the number. Graph edges and weights must therefore be derived projections over reified authoritative assertions.

## 2. Goals

- Keep accepted `Assertion` records and evidence links as canonical epistemic units.
- Build graph edges from inspectable `EdgeContribution` records.
- Keep quality dimensions separate and explicit before any aggregate score.
- Account for source lineage so republications do not multiply support.
- Preserve supporting, contradicting, withdrawn, and superseded contributions.
- Version every projection and scoring policy.
- Rebuild and explain every edge and score from authoritative snapshots.
- Distinguish publication, capture, claim-valid, and ledger transaction times.

## 3. Non-goals and forbidden approaches

This TDD does not require one universal probability of truth.

Forbidden:

- letting the model write canonical weighted edges directly;
- treating extraction confidence as world-truth probability;
- hiding unknown values inside arbitrary numeric defaults;
- counting each syndicated document as an independent contribution;
- deleting contradictory, corrected, expired, or historical assertions from provenance;
- changing historical scores without a new policy/snapshot;
- storing graph projections as the only copy of accepted relationships;
- calling an uncalibrated aggregate a probability.

## 4. Requirements

1. Projection input is a pinned accepted-ledger snapshot plus evidence, coverage, lineage, authority, and temporal policy data.
2. Each projected semantic edge lists the assertions and evidence links that contribute.
3. Each contribution records polarity, status, lineage cluster, temporal scope, and quality dimensions.
4. Dimensions include at least grounding quality, extraction quality, source-reported certainty, source authority within scope, lineage independence, temporal applicability, and review state.
5. World-state assessment remains separate from the certainty with which a source reported a statement.
6. Missing dimensions remain unknown and are surfaced to policy.
7. A scoring policy declares inclusion rules, aggregation, contradiction handling, time reference, normalization, calibration status, and output interpretation.
8. Same-lineage contributions are combined according to policy before cross-lineage aggregation.
9. Corrections, withdrawals, and temporal expiry influence current projections without deleting historical contributions.
10. Projection build is deterministic for a pinned snapshot/policy and publishes atomically.
11. An explanation API reconstructs every score and edge from contribution records.
12. Projection deletion/rebuild cannot change authoritative assertions or evidence.

## 5. Invariants

- Every `EdgeContribution` references an accepted assertion and its validated evidence links.
- Every projected edge has one named policy and one source snapshot.
- No contribution is counted as independent more than once per lineage cluster under a policy.
- Unknown is not coerced to zero, neutral, or maximum.
- Supporting and contradicting contributions remain separately inspectable.
- A current-state projection and a historical-as-of projection can differ without mutating inputs.
- Rebuild with the same snapshot and policy yields the same canonical output digest.
- A scalar score, when emitted, is reproducible from visible dimensions and is labeled with its interpretation/calibration status.

## 6. Proposed architecture

```text
Accepted Ledger Snapshot
  + Evidence validation
  + Coverage state
  + Source lineage clusters
  + Authority/temporal policies
              │
              ▼
ContributionBuilder
              │
              ▼
GraphProjectionBuilder(policy-versioned)
  ├── semantic edges
  ├── dimensional annotations
  ├── optional aggregate scores
  └── explanation records
```

The graph store is a read model. Reified assertions remain the canonical source for relationships.

## 7. Data model and interfaces

```yaml
EdgeContribution:
  contribution_id:
  assertion_id:
  assertion_evidence_link_ids:
  projected_subject_id:
  projected_predicate:
  projected_object_id_or_value:
  polarity:
  assertion_status:
  lineage_cluster_id:
  valid_time:
  publication_time:
  capture_time:
  transaction_time:
  grounding_quality:
  extraction_quality:
  source_reported_certainty:
  source_authority_scope:
  independence_class:
  world_state_assessment:

GraphScorePolicy:
  policy_id:
  version:
  input_snapshot_rules:
  inclusion_rules:
  lineage_aggregation:
  contradiction_handling:
  temporal_reference:
  missing_value_rules:
  dimension_normalization:
  aggregate_formula:
  calibration_status:
  output_interpretation:

WeightedGraphEdge:
  projected_edge_id:
  subject_id:
  predicate:
  object_id_or_value:
  policy_id:
  source_snapshot_id:
  contribution_ids:
  dimension_summary:
  aggregate_score:
  output_digest:
```

Required operations:

```python
build_edge_contributions(snapshot_id, policy_id) -> ContributionSet
build_graph_projection(snapshot_id, policy_id, as_of=None) -> GraphProjection
explain_projected_edge(edge_id) -> EdgeExplanation
verify_projection(projection_id) -> ProjectionVerificationResult
```

## 8. Key interactions and domain rules

### Multiple syndicated reports

All accepted assertions remain visible, but contributions sharing one upstream lineage cluster are combined before independent-source aggregation. Raw document count remains available in the explanation.

### Correction or withdrawal

Historical projections show what was accepted at the selected transaction time. Current projections apply correction/withdrawal policy and mark displaced contributions rather than erasing them.

### Contradiction

Support and contradiction dimensions are reported separately. A policy may calculate a net score, but explanation exposes each side and does not present disagreement as missing data.

### Unknown authority or truth assessment

The dimension remains unknown. A policy may exclude aggregate output or emit a bounded “insufficient inputs” state. It cannot silently assign a convenient number.

### Calibration

An aggregate may be called a probability only after a documented calibration/evaluation process demonstrates that interpretation for a named domain and data distribution.

## 9. Temporal behavior

The projection SHALL distinguish:

- `valid_time`: when the asserted condition holds in the world;
- `publication_time`: when the source published it;
- `capture_time`: when KoteKomi received it;
- `transaction_time`: when KoteKomi recorded/accepted it.

“As of” queries declare which clock they constrain. Defaults are explicit in the policy and API.

## 10. Compatibility and delivery

- Initial delivery may expose only dimensions and contribution counts; an aggregate scalar is optional.
- Existing graph edges can be rebuilt as projections and linked to their source assertions.
- Projection schemas can live in SQLite, graph DB, or files, but canonical serialization and explanation behavior are backend-neutral.
- Policy updates create new projections; they never rewrite old score records.

## 11. Completion gates

### Correctness criteria

- Every projected edge and dimension traces to accepted assertions and validated evidence links.
- Rebuild from the same snapshot/policy produces the same edge IDs, contribution sets, dimensions, scores, and output digest.
- Syndicated fixtures contribute one independence unit while preserving every underlying assertion/document.
- Contradictory fixtures expose both sides and follow the declared policy exactly.
- Correction, withdrawal, and temporal fixtures produce correct current and historical projections without deleting history.
- Unknown dimension fixtures remain unknown through storage, API, explanation, and aggregation.
- Deleting graph stores and rebuilding changes no authoritative record.
- A scalar without calibrated semantics is never labeled probability.

### Success criteria

- An analyst can expand any weighted edge into its policy, dimensions, assertions, exact evidence, source versions, lineage clusters, and review history.
- Two policy versions can be compared over the same snapshot without ambiguity.
- Current-state and historical-as-of queries return policy-correct, reproducible results.
- Projection build and verification run automatically after accepted-ledger changes.
- Evaluation fixtures demonstrate no support inflation from repeated captures, revisions, or republications.

### Failure criteria

This deliverable is incomplete if:

- the graph contains authoritative relationships that cannot be reconstructed from assertions;
- a model-generated strength is stored as the accepted edge weight;
- extraction confidence is presented as truth probability;
- source copies inflate independent support;
- corrected/contradictory evidence disappears from explanation;
- missing values are silently replaced with arbitrary numbers;
- a score changes without a different snapshot or policy identity;
- projection loss destroys source, evidence, or review information.

## 12. References

- KoteKomi epistemic scope and source-authority documentation
- Microsoft GraphRAG outputs as a derived-graph precedent: https://microsoft.github.io/graphrag/index/outputs/

## 13. Halt conditions

Stop and revise when an asserted graph relationship cannot remain reified and evidence-linked, when score semantics cannot be stated precisely, or when calibration data contradicts a probability interpretation.
