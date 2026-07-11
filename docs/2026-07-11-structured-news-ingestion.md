# TDD: Structured News Ingestion

- **Status:** Accepted
- **Parent:** [Authoritative Document Ingestion Program](2026-07-11-authoritative-document-ingestion-program.md)
- **Depends on:** [Source Capture](2026-07-11-source-capture-and-document-versioning.md), [Representations](2026-07-11-versioned-document-representations.md), [Evidence Targets](2026-07-11-replayable-evidence-targets.md)

## 1. Context and problem

Reuters, AP, and other news providers expose stable item identities, revisions, metadata, rights, and structured bodies through licensed delivery mechanisms. Public web pages are mutable renderings and may omit update semantics or prohibit automated copying. KoteKomi must preserve provider-native identity and revision history while still supporting ordinary permitted web articles.

## 2. Goals

- Ingest authorized provider feeds, APIs, exports, and standards-based news packages.
- Preserve provider item/version identity, update type, timestamps, metadata, rights, and raw payload.
- Convert provider structure into the canonical document representation without erasing it.
- Model corrections, clarifications, withdrawals/kills, and updates as immutable revision history.
- Provide a generic HTML/article fallback for sources where collection is permitted.
- Keep copyrighted provider bodies out of public fixtures and logs.

## 3. Non-goals and forbidden approaches

This TDD does not grant content rights or define provider contracts.

Forbidden:

- scraping Reuters/AP public pages as a substitute for licensed delivery;
- bypassing authentication, paywalls, robots controls, or provider restrictions;
- treating URL as sufficient provider identity when an item ID exists;
- overwriting an article after correction, clarification, disregard, kill, or withdrawal;
- dropping rights, embargo, distribution, or usage metadata;
- committing licensed article bodies to public repository fixtures;
- treating a republisher as an independent original source by default.

## 4. Requirements

1. A provider adapter consumes an authorized payload or local export and emits a provider-neutral capture request plus structured document DTO.
2. The raw provider payload and delivery envelope are archived subject to rights policy.
3. Stable provider item ID and provider revision/version are preserved verbatim and normalized separately.
4. Headline, alternate headline, byline, dateline, body elements, publication/update time, language, subjects, locations, media references, and provider metadata survive when present.
5. Rights, embargo, distribution scope, and retention restrictions are queryable by downstream policy.
6. Update semantics map to immutable document-revision relations without losing provider-specific status.
7. Provider-native structure has priority over HTML extraction.
8. Standards-based NewsML-G2/NITF or equivalent payloads retain their identifiers and element hierarchy.
9. Generic web ingestion archives the permitted response envelope and records extraction strategy and canonical URL.
10. Provider adapters validate required identity/version fields and reject ambiguous payloads before committing a logical revision.
11. Adapter conformance tests run against recorded, rights-safe payloads; optional live smoke tests are read-only and entitlement-gated.
12. Provider errors, throttling, expired credentials, and embargo restrictions produce typed outcomes without fabricating empty documents.

## 5. Invariants

- Every structured-news `Document` is traceable to one archived payload and provider adapter/version.
- Provider item identity is stable across its revisions; revision identity distinguishes changed versions.
- Provider timestamps remain distinct from KoteKomi capture and transaction times.
- A correction/withdrawal never deletes or mutates the earlier document.
- Rights policy travels with every capture and document revision.
- Structured body order and element type are deterministic under a pinned adapter.
- A generic extracted page never claims provider-native completeness.
- Content unavailable under current rights remains restricted even when derived indexes are rebuilt.

## 6. Proposed architecture

```text
NewsIngestUseCase
  ├── NewsProviderAdapter
  │     ├── APAdapter
  │     ├── ReutersAdapter
  │     ├── NewsMLG2Adapter
  │     └── GenericArticleAdapter
  ├── ProviderIdentityPolicy
  ├── RightsPolicy
  ├── SourceCaptureUseCase
  ├── CanonicalNewsRepresentationAdapter
  └── RevisionRelationPolicy
```

Adapters own wire-format knowledge. Application/domain code owns capture, identity conflicts, immutable revisions, validation, and acceptance boundaries.

## 7. Data model and interfaces

```yaml
ProviderNewsItem:
  provider_name:
  provider_item_id:
  provider_version:
  provider_status:
  version_created_at:
  first_published_at:
  updated_at:
  canonical_uri:
  language:
  headlines:
  bylines:
  dateline:
  subjects:
  locations:
  body_elements:
  media_references:
  rights:
  embargo:
  raw_metadata:

NewsRevisionClassification:
  document_id:
  previous_document_id:
  generic_kind: original | update | correction | clarification | withdrawal | unknown
  provider_kind:
  classification_basis:
```

Required adapter contract:

```python
class NewsProviderAdapter:
    def identify(self, payload, envelope) -> ProviderIdentity: ...
    def parse(self, payload, envelope) -> ProviderNewsItem: ...
    def classify_revision(self, item, prior_items) -> RevisionDecision: ...
```

The adapter returns data only; it does not write the ledger or allocate canonical KoteKomi IDs.

## 8. Key interactions and domain rules

### AP/Reuters revision

The stable provider item resolves the existing `Source`. A new provider version with changed canonical content creates a new `Document`. Provider status and timestamps determine a typed relation, subject to validation.

### Kill or withdrawal

The withdrawn content remains archived and historically queryable. A relation and current-state status prevent downstream projections from presenting it as the current provider version without erasing what was previously reported.

### Generic HTML article

The adapter preserves the raw permitted response, canonical URL, discovered metadata, and DOM-aware structure. Its identity policy documents weaker guarantees than a provider item ID. Subsequent materially changed content creates a new document rather than overwriting text.

### Rights-restricted content

Archive, logs, test snapshots, exports, and derived stores apply the rights profile. Diagnostic output uses IDs/hashes and bounded metadata, not article bodies, unless an authorized operator explicitly requests content.

## 9. Format precedence

When more than one representation is available, adapters SHALL prefer:

1. provider-native API/feed payload;
2. NewsML-G2, NITF, or equivalent structured package;
3. embedded structured metadata such as `NewsArticle` JSON-LD;
4. semantic article HTML/DOM;
5. versioned general main-text extraction fallback.

Fallback use is recorded and lowers only the representation-completeness assessment, not source credibility.

## 10. Compatibility and delivery

- Initial delivery may implement one recorded AP adapter and one recorded Reuters adapter behind optional dependencies while the generic DTO and conformance suite are mandatory.
- Production readiness for a provider requires an authorized recorded payload suite and a read-only live smoke test under project-held credentials.
- Public CI uses synthetic or provider-authorized fixtures with invented bodies but realistic metadata/version chains.
- Secrets and entitlements are environment-provided and never stored in artifacts or logs.

## 11. Completion gates

### Correctness criteria

- Recorded provider fixtures preserve stable item ID, exact provider version, status, timestamps, language, body order, metadata, and rights.
- Original → update → correction/clarification → withdrawal fixtures create immutable documents and correct relations.
- Replaying the same payload is idempotent; conflicting bytes for the same provider identity/version fail closed.
- Generic HTML extraction identifies body and metadata without silently claiming provider-native fields.
- Rights and embargo rules prevent forbidden export/log/index behavior in policy tests.
- Malformed payloads, expired credentials, rate limits, and provider errors cannot create empty successful documents.
- Adapter output validates without network access and has deterministic canonical serialization.

### Success criteria

- An authorized Reuters item and AP item can each proceed from captured payload to structured representation and replayable evidence.
- A provider correction is visible in revision history and current-state selection while the earlier evidence remains navigable.
- A NewsML-G2 fixture preserves item/version identity and structured body elements.
- A permitted ordinary web article reaches the same downstream representation interface with its weaker provenance explicitly marked.
- Public CI passes without licensed bodies or credentials; entitlement-gated smoke tests pass in the deployment environment.

### Failure criteria

This deliverable is incomplete if:

- production provider ingestion depends on scraping public article pages;
- correction or kill status is reduced to a changed timestamp;
- provider identity/version or rights metadata is lost;
- tests require committing copyrighted article bodies publicly;
- an unauthorized or embargoed payload leaks through logs, exports, or derived indexes;
- provider errors are represented as successful no-text documents;
- only generic HTML is implemented while claiming Reuters/AP support.

## 12. References

- AP Media API content metadata: https://developer.ap.org/ap-media-api/agent/Content_Metadata_Fields.htm
- Reuters API integrations: https://reutersagency.com/content-delivery-platforms/api-integrations/
- IPTC NewsML-G2: https://iptc.org/std/NewsML-G2/specification/

## 13. Halt conditions

Stop and revise for any provider whose contract or payload semantics conflict with archival, versioning, testing, or downstream-use requirements. Do not substitute unauthorized scraping to preserve schedule.
