# R0-B — Stable source identity and document revisioning

Once R0-A is merged, replace `add_source_from_file()`’s content-derived source identity with a real capture use case.

The current implementation derives `Source`, `Document`, `SourceCapture`, representation, and provenance IDs from the same content digest. Consequently, changed bytes create a new logical source rather than a new revision of the same source. ([GitHub][4])

## Add the application operation specified by the TDD

```python
capture_source(request: CaptureRequest) -> CaptureOutcome
```

Suggested request:

```python
@dataclass(frozen=True)
class CaptureRequest:
    identity_hint: SourceIdentityHint
    payload: bytes
    media_type: str
    idempotency_key: str
    retrieval_method: str

    requested_uri: str | None
    canonical_uri: str | None

    provider_item_id: str | None
    provider_version: str | None
    version_kind: DocumentVersionKind

    publication_time: datetime | None
    provider_update_time: datetime | None
    captured_at: datetime
    transaction_time: datetime

    rights_profile_id: str | None
    embargo_until: datetime | None

    request_metadata: dict[str, JsonValue]
    response_metadata: dict[str, JsonValue]

    revision_of_document_id: str | None = None
    revision_type: DocumentRevisionType | None = None
```

## Add a source identity policy port

```python
class SourceIdentityPolicy(Protocol):
    @property
    def policy_id(self) -> str: ...

    def canonical_key(
        self,
        hint: SourceIdentityHint,
    ) -> str: ...
```

Identity examples:

```text
AP/Reuters:
    provider namespace + provider item ID

Generic web publication:
    publisher namespace + canonical publication key

Local file:
    explicit source key, falling back to normalized canonical path
```

Then:

```python
source_id = deterministic_id(
    "src",
    identity_policy.policy_id,
    canonical_source_key,
)
```

The payload digest must not participate in `source_id`.

## Identity rules

```text
RawBlob ID:
    byte digest

SourceCapture ID:
    source ID + idempotency key/canonical request fingerprint

Document ID:
    source ID + provider version + canonical content digest
    or source ID + canonical content digest when no version exists

Revision relation ID:
    earlier document + later document + relation type
```

The exact formula is less important than these observable properties:

* changed content under the same source identity creates a new `Document`;
* the earlier `Document` remains unchanged;
* a correction or update creates a typed relation;
* an identical retry reuses the previous committed outcome;
* the same idempotency key with different material input fails atomically;
* the same provider item/version with incompatible bytes is a conflict.

## Revision-cycle check

Before saving `corrects` or `supersedes`, traverse the existing relations and reject any edge that would make the later document an ancestor of itself.

Do this in application code before the insert and repeat it inside the same transaction that commits the relation.

## Local-file ingestion

Extend `SourceFileIngestInput` with a stable source key:

```python
source_identity_key: str | None = None
idempotency_key: str | None = None
```

For the local-file adapter:

```text
source_identity_key defaults to normalized local file identity
idempotency_key defaults to a request fingerprint
```

Therefore, editing one fixture file creates:

```text
same Source
new RawBlob
new SourceCapture
new Document
typed update relation
```

—not a completely unrelated source.

## R0-B acceptance sequence

One integration test should run:

```text
original
→ unchanged recapture
→ update
→ correction
→ withdrawal
```

It must prove:

* one stable `Source`;
* four immutable `Document` versions where policy requires them;
* every capture retained;
* correct relation types;
* old raw bytes still readable;
* same request retry returns the same outcome;
* conflict injection creates no partial write;
* cycle insertion fails;
* rights, embargo, provider IDs, and all timestamps round-trip.

That directly satisfies the source-versioning completion gate. ([GitHub][5])

[1]: https://github.com/SQLCODE917/KoteKomi/commits/main "Commits · SQLCODE917/KoteKomi · GitHub"
[2]: https://raw.githubusercontent.com/SQLCODE917/KoteKomi/main/packages/adapters/src/kotekomi_adapters/sqlite_ledger.py "raw.githubusercontent.com"
[3]: https://raw.githubusercontent.com/SQLCODE917/KoteKomi/main/packages/application/src/kotekomi_application/evidence_targets.py "raw.githubusercontent.com"
[4]: https://raw.githubusercontent.com/SQLCODE917/KoteKomi/main/packages/application/src/kotekomi_application/source_file_ingest.py "raw.githubusercontent.com"
[5]: https://raw.githubusercontent.com/SQLCODE917/KoteKomi/main/docs/2026-07-11-source-capture-and-document-versioning.md "raw.githubusercontent.com"
[6]: https://raw.githubusercontent.com/SQLCODE917/KoteKomi/main/packages/adapters/src/kotekomi_adapters/docling_pdf_parser.py "raw.githubusercontent.com"
[7]: https://raw.githubusercontent.com/SQLCODE917/KoteKomi/main/packages/domain/src/kotekomi_domain/models.py "raw.githubusercontent.com"
[8]: https://raw.githubusercontent.com/SQLCODE917/KoteKomi/main/docs/2026-07-11-authoritative-document-ingestion-program.md "raw.githubusercontent.com"
