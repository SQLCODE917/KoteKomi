# TDD: Deterministic Context Planning

- **Status:** Accepted
- **Parent:** [Authoritative Document Ingestion Program](2026-07-11-authoritative-document-ingestion-program.md)
- **Depends on:** [Versioned Document Representations](2026-07-11-versioned-document-representations.md)

## 1. Context and problem

A long document cannot be sent wholesale to a bounded local model. Fixed-size chunks lose definitions, attribution, heading scope, table headers, footnotes, and cross-references. Retrieval alone is nondeterministic unless its candidates, scores, selection rules, and exact rendered prompt are preserved.

## 2. Goals

- Divide documents into meaningful analysis units without making those units source records.
- Compute required contextual closure from document structure and explicit dependencies.
- Fit model input within an exact token budget using deterministic priority and tie-breaking.
- Preserve an immutable manifest of everything included, excluded, rendered, and tokenized.
- Block or split tasks rather than silently truncate required context.
- Permit lexical/semantic retrieval as disclosed optional support, never hidden state.

## 3. Non-goals and forbidden approaches

This TDD does not decide claims or treat retrieval relevance as evidence.

Forbidden:

- arbitrary fixed-token chunks as the sole unit strategy;
- silent truncation by model runtime or tokenizer;
- undisclosed vector search or mutable “top K” results;
- including generated summaries as source evidence;
- using a tokenizer estimate different from the runtime tokenizer;
- dropping required definitions, table headers, or cited footnotes to fit optional neighbors;
- marking an over-budget task successful without split or blocked status.

## 4. Requirements

1. A planning policy creates deterministic `AnalysisUnit` records from a pinned representation.
2. Each unit identifies focus nodes, task type, and dependencies.
3. Context candidates have explicit role, reason code, required/optional status, priority, dependency path, and source node IDs.
4. Candidate generation considers document metadata, ancestor headings, definitions, acronym expansions, explicit references, footnotes, captions, table headers, required adjacent nodes, lexical retrieval, and optional semantic retrieval.
5. Token budget is computed from model context limit minus prompt, schema, reserved output, and safety margin using the exact runtime tokenizer.
6. Required candidates are packed before optional candidates.
7. Ordering and tie-breaking are stable and documented.
8. A `ContextManifest` records candidates, selected nodes, excluded nodes/reasons, rendered offsets, tokenizer identity, token count, and hashes.
9. The exact rendered model input is archived or reproducible byte-for-byte from the manifest and pinned renderer.
10. If required context does not fit, the planner applies a versioned split strategy or emits `context_budget_blocked` before model invocation.
11. Retrieval results record index version, query, method, raw score, rank, and selection decision.
12. Model runtime rejects input whose manifest token count exceeds the declared limit.

## 5. Invariants

- Every source segment in a model input maps to one or more nodes in the pinned representation.
- The manifest digest commits to task, representation, selected order, rendered input, prompt/schema, tokenizer, and planning policy.
- Required context is never displaced by optional context.
- The same pinned inputs and available deterministic indexes produce the same manifest digest.
- A model run references exactly one finalized manifest.
- Excluded candidates remain inspectable with a reason.
- Generated navigation summaries may nominate original nodes but are never rendered as authoritative evidence unless explicitly labeled non-source context and prohibited from citation.
- No model citation outside the manifest can pass validation.

## 6. Proposed architecture

```text
AnalysisPlanner
  ├── UnitPolicy
  ├── DependencyResolver
  ├── LexicalCandidateSource
  ├── OptionalSemanticCandidateSource
  ├── TokenBudgetCalculator
  ├── StableContextPacker
  └── ContextRenderer
```

Candidate generation and packing are separate. The planner can explain why a node was considered even when it was excluded.

## 7. Data model and interfaces

```yaml
AnalysisUnit:
  analysis_unit_id:
  representation_id:
  task_type:
  focus_node_ids:
  dependency_node_ids:
  planner_policy_id:
  unit_fingerprint:

ContextCandidate:
  node_id:
  role: focus | metadata | heading | definition | reference | footnote | table_context | neighbor | lexical | semantic
  reason_code:
  required:
  priority:
  dependency_path:
  retrieval_details:
  estimated_tokens:

ContextManifest:
  context_manifest_id:
  analysis_unit_id:
  representation_id:
  prompt_id:
  schema_id:
  renderer_version:
  planner_policy_id:
  tokenizer_id:
  model_context_limit:
  reserved_output_tokens:
  safety_margin_tokens:
  selected_candidates:
  excluded_candidates:
  rendered_segments:
  rendered_input_digest:
  input_token_count:
  manifest_digest:
  status: ready | split | context_budget_blocked
```

Required operations:

```python
plan_analysis_units(representation_id, policy_id) -> AnalysisPlan
build_context_manifest(unit_id, model_profile_id) -> ContextPlanningOutcome
render_context(manifest_id) -> bytes
```

## 8. Candidate priority contract

Default priority, overridable only by a versioned policy:

1. focus nodes;
2. source/document identity and required publication metadata;
3. ancestor headings and structural scope;
4. explicit definitions and acronym expansions used by focus text;
5. explicit cross-references and referenced footnotes;
6. table captions, units, row headers, and column headers;
7. required adjacent nodes needed for sentence/attribution completion;
8. lexical support nodes;
9. semantic support nodes;
10. optional generated navigation material, clearly isolated.

Within the same priority, order by dependency distance, document order, retrieval rank, then node ID.

## 9. Key interactions and domain rules

### Distant definition

An explicit definition edge marks the definition required. It enters before optional neighbors and appears in the manifest with a dependency path from focus to definition.

### Oversized table

The planner includes required headers and the focused rows/cells. If a semantically complete table unit cannot fit, it splits by a deterministic table-aware strategy or blocks; it never strips headers.

### Retrieval index change

A new index version may produce a new manifest. Historical model runs keep the old manifest and retrieval hit list. “Latest index” is never consulted during replay.

### Model profile change

A different tokenizer/context/output reserve creates a different planning fingerprint and manifest. Existing manifests are not rewritten.

## 10. Compatibility and delivery

- Initial units may be paragraph groups, subsections, and tables; the policy remains replaceable.
- Lexical retrieval is the mandatory first retrieval source. Semantic retrieval is optional and version-pinned.
- The legacy whole-document path is allowed only for fixtures that provably fit and is still represented by a manifest.
- Context manifests belong in the immutable analysis artifact store, not only logs.

## 11. Completion gates

### Correctness criteria

- Repeated planning with identical pinned inputs produces byte-identical rendered input and the same manifest digest.
- Exact runtime tokenization confirms every ready manifest is within budget.
- Gold units containing distant definitions, attribution, table headers, and footnotes include every labeled required node.
- Removing token budget causes deterministic optional exclusion, then split/block behavior without removing required nodes.
- Retrieval candidates and scores can be replayed from the recorded index version.
- A model reference to a node absent from the manifest is rejected.
- Runtime-side truncation is detected and treated as a failed run.

### Success criteria

- All analyzable gold-corpus units either receive dependency-complete ready manifests or explicit split/blocked outcomes.
- A reviewer can reconstruct why every included segment was selected and why every candidate was excluded.
- Long documents complete through bounded tasks without sending the whole source to the model.
- Changing policy, tokenizer, model profile, or index creates new manifests while preserving old replay.
- Required-context recall meets the evaluation TDD threshold.

### Failure criteria

This deliverable is incomplete if:

- task success depends on undocumented retrieval or mutable index state;
- a required definition/header/footnote can be truncated silently;
- reported token counts differ from runtime counts;
- the same pinned inputs yield unstable manifests without a declared nondeterministic dependency;
- generated summaries can be cited as source evidence;
- only selected context is stored while excluded candidates and reasons are lost;
- model calls can occur without finalized manifests.

## 12. R1-C fixture proof

Use the R1 press-release PDF fixture for the first context-planning proof.

The focus paragraph beginning `The CHIP highlights four key health priorities` must include the preceding `Community Health Improvement Plan (CHIP)` definition as required context.

The manifest must exclude preserved page furniture with an inspectable `furniture_excluded` reason.

The same fixture must produce deterministic ready, split, and `context_budget_blocked` outcomes under pinned tokenizer and budget inputs.

## 13. References

- KoteKomi pipeline and testing guidance
- Anthropic contextual retrieval: https://www.anthropic.com/engineering/contextual-retrieval
- Lost in the Middle: https://aclanthology.org/2024.tacl-1.9/

## 14. Halt conditions

Stop and revise when a required semantic dependency cannot be represented or tested, when the runtime cannot expose exact tokenization/truncation behavior, or when a mandatory source unit cannot be split without changing its meaning.
