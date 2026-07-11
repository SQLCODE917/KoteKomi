# TDD: Source Capture and Document Versioning

- **Status:** Accepted
- **Parent:** [Authoritative Document Ingestion Program](2026-07-11-authoritative-document-ingestion-program.md)

## 1. Context and problem

A stable publication item, one retrieval event, downloaded bytes, and one content revision are different facts. Content-derived IDs currently collapse those facts and cannot faithfully represent repeated retrievals, corrections, withdrawals, unchanged recaptures, or conflicting provider identity.

## 2. Goals

- Give a logical publication item a stable `Source` identity independent of downloaded bytes.
- Preserve every material retrieval event and immutable raw payload.
- Represent each distinct content revision as an immutable `Document`.
- Record revision relationships without overwriting history.
- Make capture idempotent under retries while detecting identity conflicts.
- Preserve provider, HTTP/file, rights, embargo, and timestamp metadata.

## 3. Non-goals and forbidden approaches

This TDD does not parse document structure or decide whether a source claim is true.

Forbidden:

- using a payload hash as the sole logical `Source` identity;
- overwriting raw bytes or a prior `Document` after a correction;
- silently treating different bytes under the same provider version as identical;
- discarding response metadata, rights, embargo, or retrieval time;
- inferring that repeated captures are independent sources.

## 4. Requirements

1. A capture command accepts a source identity hint, retrieval envelope, payload, media type, and idempotency key.
2. The raw payload is content-addressed with a named cryptographic hash and immutable once committed.
3. `Source` resolution uses provider item identity or another adapter-defined stable identity policy.
4. A `SourceCapture` records when, how, and from where the payload was obtained.
5. A distinct normalized content revision creates a distinct immutable `Document`.
6. A repeated capture may reference an existing raw blob and `Document` while preserving the new capture event when policy requires it.
7. Provider updates, corrections, withdrawals, and supersessions create typed relations.
8. The application detects conflicting reuse of an idempotency key before any partial write is visible.
9. Capture and document records expose publication, provider-update, capture, and transaction times separately.
10. Rights and distribution metadata remain available to downstream export and logging policy.

## 5. Invariants

- A `RawBlob` hash always verifies against its stored bytes.
- A `SourceCapture` references exactly one `Source` and one `RawBlob`.
- A `Document` references exactly one `Source`, at least one capture, and one immutable content identity.
- No revision relation points from a document to itself.
- Revision graphs are acyclic for `supersedes` and `corrects` relations.
- The same idempotency key plus the same canonical request produces the same committed outcome.
- The same idempotency key plus materially different input produces a typed conflict and no mutation.
- Deleting a downstream representation cannot delete its source capture or blob.

## 6. Proposed architecture

```text
CaptureUseCase
  ├── SourceIdentityPolicy (provider-specific or generic)
  ├── BlobStore
  ├── CaptureRepository
  ├── DocumentRepository
  └── RevisionRelationRepository
```

Adapters supply provider IDs and retrieval metadata. Application code owns canonical hashing, idempotency, transaction boundaries, and relation validation.

## 7. Data model and interfaces

```yaml
RawBlob:
  blob_id: deterministic hash identity
  hash_algorithm:
  digest:
  byte_length:
  media_type:
  storage_locator:

SourceCapture:
  capture_id:
  source_id:
  blob_id:
  idempotency_key:
  retrieval_method:
  requested_uri:
  canonical_uri:
  request_metadata:
  response_metadata:
  provider_item_id:
  provider_version:
  rights_profile_id:
  embargo_until:
  captured_at:
  transaction_time:

Document:
  document_id:
  source_id:
  content_digest:
  provider_version:
  publication_time:
  provider_update_time:
  version_kind: original | update | correction | withdrawal | unknown
  created_from_capture_id:

DocumentRevisionRelation:
  relation_id:
  earlier_document_id:
  later_document_id:
  relation_type: updates | corrects | supersedes | withdraws
  basis: provider_metadata | operator | deterministic_rule
  recorded_at:
```

Required application operation:

```python
capture_source(request: CaptureRequest) -> CaptureOutcome
```

`CaptureOutcome` reports created/reused records and typed conflicts; it never hides deduplication decisions.

## 8. Key interactions and domain rules

### Retry of the same request

The use case verifies the idempotency record and blob digest, then returns the previously committed outcome. It does not create duplicate documents or relations.

### Same bytes retrieved again

The blob is reused. A new capture event is recorded when the retrieval itself matters. The existing `Document` may be reused if provider/version and canonical content identity agree.

### Same provider item, corrected body

A new blob, capture, and `Document` are written. Provider metadata creates a `corrects` relation. The old document and its evidence remain valid historical records.

### Identity conflict

If the same provider item/version or idempotency key arrives with incompatible bytes, the transaction fails with a conflict record. Resolution requires an explicit adapter policy or operator action.

## 9. Compatibility and delivery

- Existing fixture ingestion creates a generic `Source`, synthetic local-file capture, raw blob, and `Document`.
- Existing content-derived source IDs may be retained as aliases during migration.
- Archive storage can remain filesystem-backed, but commit semantics must prevent ledger records from pointing to missing bytes.
- Migrations are additive and reversible without deleting source history.

## 10. Completion gates

### Correctness criteria

- Hash verification succeeds for every persisted fixture payload and detects a one-byte mutation.
- Repeating an identical capture request yields the same logical outcome without duplicate `Document` records.
- A second retrieval of unchanged bytes records policy-correct capture history without manufacturing a new revision.
- Changed bytes under a valid provider update create a new `Document` and the correct typed relation.
- Conflicting idempotency or provider-version input performs no partial write.
- Rights, embargo, provider identity, and all four relevant times round-trip exactly.
- Revision-cycle insertion is rejected.

### Success criteria

- Current `.md` and `.txt` fixtures ingest through this path unchanged at the user-visible proposal level.
- A test sequence covering original → update → correction → withdrawal preserves all versions and relations.
- A capture can be replayed from the archive without network access and yields the same blob/document identities.
- Downstream code can select a specific document revision without consulting mutable external state.

### Failure criteria

This deliverable is incomplete if:

- source identity still changes whenever bytes change;
- a correction replaces or mutates an earlier document;
- duplicate retries create duplicate revisions;
- conflict handling relies only on a log message;
- capture metadata or rights cannot be queried after ingestion;
- an archive failure leaves committed ledger pointers to absent bytes;
- revision history can contain an unreported cycle.

## 11. References

- KoteKomi domain and archive ports
- W3C PROV-O entity/activity concepts: https://www.w3.org/TR/prov-o/

## 12. Halt conditions

Stop and revise when a provider's identity/version semantics cannot map without loss, or when storage cannot provide atomic publication of blob and metadata references.
