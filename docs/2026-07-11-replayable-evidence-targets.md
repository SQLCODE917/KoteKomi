# TDD: Replayable Evidence Targets

- **Status:** Accepted
- **Parent:** [Authoritative Document Ingestion Program](2026-07-11-authoritative-document-ingestion-program.md)
- **Depends on:** [Source Capture](2026-07-11-source-capture-and-document-versioning.md), [Document Representations](2026-07-11-versioned-document-representations.md)

## 1. Context and problem

Checking whether an exact quote occurs somewhere in a document does not identify which occurrence was intended, whether selectors agree, or which table headers, definitions, attribution, and scope are necessary to support a normalized assertion. Evidence must be replayable at one exact source occurrence and its role must be separate from the evidence object itself.

## 2. Goals

- Pin evidence to an immutable document representation and text view.
- Resolve each evidence target uniquely using multiple agreeing selectors.
- Support text, PDF region, DOM, node, and table selectors.
- Relate evidence to assertions through explicit semantic roles.
- Preserve context dependencies without presenting generated text as evidence.
- Make evidence validation deterministic and fail closed.

## 3. Non-goals and forbidden approaches

This TDD does not decide whether evidence is persuasive or whether a source is truthful.

Forbidden:

- accepting `exact_text in document_text` as sufficient grounding;
- storing only a quote without occurrence-disambiguating context or position;
- attaching `assertion_id` directly to a reusable evidence target;
- citing summaries, model paraphrases, or normalized claims as source text;
- silently reanchoring evidence after representation changes;
- accepting selector disagreement or multiple matching occurrences.

## 4. Requirements

1. Every evidence target identifies source, document, representation, and text view.
2. Text evidence includes quote and position selectors; prefix/suffix disambiguate repeated text.
3. Node selectors identify the structural units containing the evidence.
4. PDF evidence may include one or more page regions in a declared coordinate system.
5. HTML/news evidence may include DOM/path selectors when supplied by the representation.
6. Table evidence identifies the value cell and required header, caption, or footnote cells/nodes.
7. A deterministic validator resolves all supplied selectors and verifies agreement.
8. Assertions reference evidence through `AssertionEvidenceLink` records with roles and polarity.
9. Validation state, validator version, and target digest are recorded.
10. Reanchoring creates a new target and provenance relation; it never mutates the old target.

## 5. Invariants

- A valid evidence target resolves to exactly one occurrence in one pinned representation.
- `exact_text` equals the text selected by stored start/end positions.
- Prefix and suffix, when present, match adjacent text under the declared normalization policy.
- All node, region, DOM, and table selectors supplied for a target refer to the same source occurrence.
- An accepted source-backed assertion has at least one validated `direct_support` link.
- Contextual evidence cannot substitute for missing direct support.
- One evidence target may support several assertions without duplication or mutation.
- Generated artifacts are structurally incapable of being selected as authoritative evidence.

## 6. Proposed architecture

```text
EvidenceTargetValidator
  ├── TextSelectorResolver
  ├── NodeSelectorResolver
  ├── PdfRegionResolver
  ├── DomSelectorResolver
  └── TableSelectorResolver

Assertion ── AssertionEvidenceLink ──► EvidenceSpan/Target
```

`EvidenceSpan` may retain its current name, but its semantics become a representation-pinned target. Assertion linkage moves to a join record.

## 7. Data model and interfaces

```yaml
EvidenceSpan:
  evidence_span_id:
  source_id:
  document_id:
  representation_id:
  text_view_id:
  text_view_digest:
  exact_text:
  prefix:
  suffix:
  start_char:
  end_char:
  node_ids:
  pdf_regions:
  dom_selector:
  table_selector:
  selector_normalization_policy:
  validation_status:
  validator_version:
  validated_at:

AssertionEvidenceLink:
  assertion_evidence_link_id:
  assertion_id:
  evidence_span_id:
  role: direct_support | attribution | definition | scope | temporal_anchor | identity_resolution | contradiction | background
  polarity: supports | contradicts | contextualizes
  necessity: required | supplementary
  provenance_id:
```

Required operations:

```python
validate_evidence_target(target_id) -> EvidenceValidationResult
link_assertion_evidence(command) -> AssertionEvidenceLink
reanchor_evidence(command) -> ReanchoringOutcome
```

## 8. Key interactions and domain rules

### Repeated quote

Position, prefix/suffix, and node selectors identify one occurrence. If the selector set identifies zero or multiple occurrences, validation fails and no accepted link can use it.

### Cross-section definition

The assertion links the local statement as `direct_support` and the earlier definition as `definition`. Review displays both and preserves each exact source location.

### Attribution

A quote may directly support that a speaker said something while a byline/dateline or surrounding sentence establishes attribution. These are separate links; KoteKomi does not silently convert reported speech into world truth.

### Table claim

The direct evidence set includes the value cell and every header/caption/footnote needed to determine its subject, unit, time, and qualifiers. A flattened value alone is insufficient.

### Parser upgrade

Old targets remain valid against the old representation. A migration may propose new targets and records a mapping with confidence/review, but accepted history still points to the original target.

## 9. Compatibility and delivery

- Legacy evidence is imported into a pinned legacy text representation.
- Automatic validation is allowed only when the quote resolves uniquely and its stored context agrees.
- Ambiguous legacy evidence remains visible but is marked unvalidated and cannot satisfy the new acceptance invariant.
- The current assertion/evidence API can be shimmed while callers migrate to the join record.

## 10. Completion gates

### Correctness criteria

- Unique text, repeated text, Unicode normalization, line-break, and punctuation fixtures resolve according to an explicit policy.
- Zero-match, multi-match, offset mismatch, prefix/suffix mismatch, stale view digest, invalid node, and region disagreement all fail deterministically.
- A valid target replays after process restart from archived artifacts only.
- One evidence target can link to multiple assertions while preserving independent roles.
- An accepted assertion without validated direct support is rejected at the acceptance boundary.
- Table claims fail validation when any required header context is removed.
- Reanchoring leaves the original target byte-for-byte unchanged.

### Success criteria

- Review can navigate from assertion to exact quote, structural context, and page/region without a live provider or parser.
- A cross-section claim displays direct, definition, attribution, and temporal evidence as distinct roles.
- Evidence validation is runnable as a batch integrity check over the ledger.
- All new grounded model proposals use only manifest-visible source nodes and produce validator-passing targets.

### Failure criteria

This deliverable is incomplete if:

- substring presence is still the acceptance test;
- repeated quotes can attach to the wrong occurrence;
- an evidence target changes when an assertion changes;
- a generated summary can pass as evidence;
- selector disagreement is logged but accepted;
- table evidence loses its interpretation context;
- a historical target requires the current parser or current website to replay.

## 11. References

- W3C Web Annotation selectors: https://www.w3.org/TR/annotation-model/
- W3C PROV-O: https://www.w3.org/TR/prov-o/

## 12. Halt conditions

Stop and revise if exact source occurrences cannot be represented for a mandatory source class, or if the acceptance boundary cannot atomically enforce validated direct support.
