# TDD: Source Lineage and Independence

- **Status:** Accepted
- **Parent:** [Authoritative Document Ingestion Program](2026-07-11-authoritative-document-ingestion-program.md)
- **Depends on:** source capture/versioning, structured news ingestion, and staged extraction

## 1. Context and problem

The same Reuters/AP dispatch may appear on many sites, a correction may resemble a duplicate, and later articles may quote or derive from earlier reporting. Counting documents or URLs as independent corroboration inflates support. At the same time, aggressive similarity clustering can wrongly merge genuinely independent reports.

## 2. Goals

- Record explicit source revision and derivation relationships.
- Detect exact and near-duplicate republications deterministically where possible.
- Separate provider revision lineage from cross-publisher syndication/derivation.
- Represent uncertainty and require review for ambiguous relationships.
- Derive independence clusters for corroboration without modifying source records.
- Preserve raw document count alongside lineage-aware independent count.
- Prevent false merges from silently suppressing independent evidence.

## 3. Non-goals and forbidden approaches

This TDD does not prove that two journalists worked independently or that similar claims are true.

Forbidden:

- treating distinct URLs or publishers as automatically independent;
- merging sources solely because embeddings or an LLM say they are similar;
- collapsing a whole article because it contains one quoted passage;
- deleting duplicate/republication documents;
- using a model-proposed relation as accepted lineage without review;
- hiding unknown lineage by assigning a confident cluster;
- applying lineage clusters directly as canonical source identity.

## 4. Requirements

1. Provider-declared revisions and syndication metadata create high-authority lineage facts with archived evidence.
2. Exact normalized document and paragraph hashes nominate deterministic duplicate relations.
3. Near-duplicate candidate generation uses a versioned deterministic algorithm such as shingles plus MinHash/SimHash or an equivalent disclosed method.
4. Candidate comparisons preserve matching spans, scores, thresholds, algorithm version, and exclusions.
5. A model may analyze borderline candidates only through a context manifest and produces a proposal, not accepted lineage.
6. Accepted lineage relations are typed, directional where appropriate, and evidence-backed.
7. Quote-level overlap is distinguishable from article-level republication.
8. Independence clusters are derived from accepted relation types under a versioned policy.
9. Corrections/revisions remain in one revision family but do not become multiple independent sources.
10. Corroboration APIs return raw document count, source count, lineage-cluster count, unknown count, and contributing identities.
11. Contradictory or cyclic derivation proposals fail validation or require explicit reviewed semantics.
12. Rebuilding clusters cannot alter source, document, assertion, or evidence records.

## 5. Relation model

```text
provider_revision
correction
withdrawal
verbatim_republication
edited_republication
quotation
summary_or_derived_report
common_upstream_source
unknown
```

Revision relations describe versions of one logical publication item. Derivation relations connect distinct sources/documents. `quotation` applies only to identified spans unless evidence supports broader derivation.

## 6. Invariants

- Every accepted lineage relation identifies its documents, type, basis, evidence, reviewer/provenance, and recorded time.
- No accepted document-level relation is inferred from claim similarity alone.
- Exact-duplicate algorithms are deterministic under pinned normalization and algorithm versions.
- A document remains individually queryable after clustering.
- Independence clusters are reproducible from accepted relations and policy.
- Unknown or unresolved candidates do not automatically collapse clusters.
- The same upstream dispatch contributes at most one independent lineage unit to a corroboration calculation under a policy.
- A correction does not add independent corroboration for the corrected story.
- Raw counts and cluster-adjusted counts are both retained and explainable.

## 7. Proposed architecture

```text
LineageCandidatePipeline
  ├── ProviderMetadataRules
  ├── ExactHashMatcher
  ├── ParagraphHashMatcher
  ├── NearDuplicateCandidateIndex
  ├── OptionalModelComparator
  └── ProposedChange review

AcceptedLineageRelations
  └── IndependenceClusterBuilder(policy-versioned, derived)
```

Deterministic matchers may create accepted relations only for explicitly safe rules defined by policy; all other matches enter review.

## 8. Data model and interfaces

```yaml
SourceLineageRelation:
  lineage_relation_id:
  from_document_id:
  to_document_id:
  relation_type:
  scope: document | section | paragraph | quote
  scope_selectors:
  basis: provider_metadata | exact_hash | similarity | model_proposal | reviewer
  confidence_class: deterministic | reviewed | unresolved
  evidence_span_ids:
  provenance_id:
  recorded_at:

LineageCandidate:
  candidate_id:
  document_pair:
  algorithm_id:
  algorithm_version:
  normalized_input_digests:
  exact_matches:
  matching_spans:
  similarity_features:
  score:
  proposed_relation_type:
  status:

IndependenceCluster:
  cluster_id:
  policy_id:
  member_document_ids:
  supporting_relation_ids:
  cluster_digest:
```

Required operations:

```python
find_lineage_candidates(document_id, policy_id) -> CandidateSet
accept_lineage_relation(proposed_change_id) -> SourceLineageRelation
build_independence_clusters(snapshot_id, policy_id) -> ClusterSet
explain_corroboration(assertion_set, policy_id) -> CorroborationBreakdown
```

## 9. Key interactions and domain rules

### Provider syndication

Matching provider item IDs or explicit syndication metadata establish common origin. Rehosting domains remain separate sources/documents but share one independence cluster for that dispatch.

### Correction

The correction relation comes from provider versioning. Current-state projection may choose the corrected version. Both versions remain in one revision family and one independence contribution.

### Article quoting one paragraph

The matching passage becomes quote-scope lineage. The rest of the article can still contain independent reporting. Document-level collapse requires stronger evidence.

### Similar independent reports

Shared named entities and facts can produce a candidate, but absent derivation evidence the relation remains unknown/separate. The system favors avoiding false merges over maximizing deduplication.

### Model comparison

The model receives bounded original spans and metadata, returns a reasoned relation proposal and cited spans, and is reviewed. It cannot directly assign clusters.

## 10. Compatibility and delivery

- Existing sources default to unknown/separate until relations are established; this is explicit in corroboration output.
- Exact normalized duplicates can be delivered before near-duplicate and model-assisted comparison.
- Cluster storage is disposable and rebuildable.
- Similarity indexes are derived and versioned; accepted relations and review records are authoritative.

## 11. Completion gates

### Correctness criteria

- Exact duplicate, provider revision, correction, verbatim syndication, edited republication, partial quotation, and independent-control fixtures receive the expected relation behavior.
- The required corpus has zero false document-level merges among independent-control pairs.
- Corrections and repeated captures do not increase independent corroboration count.
- One quoted paragraph does not collapse unrelated article sections or the whole document.
- Every accepted non-provider relation has replayable matching-source evidence and review/provenance.
- Cluster rebuilds are deterministic and explain every membership through accepted relation IDs.
- Cyclic or semantically incompatible directional relations are rejected.

### Success criteria

- A Reuters/AP-style dispatch republished by multiple outlets reports all documents but one independence contribution.
- Two genuinely independent reports of the same event remain separate contributions.
- Operators can inspect exact matching spans, algorithms, scores, and review decisions.
- Corroboration output exposes raw documents, logical sources, independence clusters, and unknowns.
- Rebuilding or changing cluster policy affects only derived results and preserves authoritative records.

### Failure criteria

This deliverable is incomplete if:

- URL count is still used as independent-source count;
- an embedding/LLM similarity score directly merges sources;
- duplicates are deleted rather than related;
- correction versions count as corroboration;
- partial quotation collapses whole documents automatically;
- unknown lineage is hidden as certain independence or dependence;
- cluster membership cannot be traced to accepted relation evidence.

## 12. References

- FollowTheMoney statement/provenance concepts: https://followthemoney.tech/docs/
- Provider identity and revision metadata from the structured-news TDD

## 13. Halt conditions

Stop and revise when validation data shows false merges above zero for protected independent controls, or when provider/licensing rules prevent retaining the evidence needed to justify a lineage relation.
