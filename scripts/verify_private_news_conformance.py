"""Run an authorized, repository-external provider recording suite."""

from __future__ import annotations

import argparse
import importlib
import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from kotekomi_adapters import LocalArchiveStore, SQLiteLedgerInitializer, sqlite_ledger_transaction
from kotekomi_application import (
    BuildIdentity,
    JsonValue,
    NewsDeliveryEnvelope,
    NewsIngestInput,
    NewsIngestStatus,
    NewsProviderAdapter,
    UtcProcessingClock,
    Uuid4ProcessingAttemptIdFactory,
    ingest_structured_news,
)


def _adapter(spec: str) -> NewsProviderAdapter:
    module_name, separator, attribute_name = spec.partition(":")
    if not separator or not module_name or not attribute_name:
        raise ValueError("Adapter factory must use module:attribute syntax.")
    module = importlib.import_module(module_name)
    factory = getattr(module, attribute_name)
    return cast(NewsProviderAdapter, factory())


def _object(value: object, context: str) -> dict[str, JsonValue]:
    if not isinstance(value, dict):
        raise ValueError(f"{context} must be a JSON object.")
    mapping = cast(dict[object, object], value)
    return {str(key): cast(JsonValue, item) for key, item in mapping.items()}


def _string(value: object, context: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{context} must be a nonempty string.")
    return value


def _optional_string(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def run_suite(provider: str, fixture_dir: Path, adapter_spec: str) -> None:
    manifest_value = cast(object, json.loads((fixture_dir / "manifest.json").read_text()))
    manifest = _object(manifest_value, "manifest")
    if manifest.get("provider") != provider:
        raise ValueError("Private manifest provider does not match the requested provider.")
    raw_cases = manifest.get("cases")
    if not isinstance(raw_cases, list) or not raw_cases:
        raise ValueError("Private manifest requires a nonempty cases list.")
    adapter = _adapter(adapter_spec)
    now = datetime(2026, 7, 14, tzinfo=UTC)
    build = BuildIdentity(
        package_version="private-news-conformance",
        source_revision="private-news-conformance",
        artifact_digest="d" * 64,
        representation_policy_version="structured-news-v1",
    )
    with tempfile.TemporaryDirectory(prefix=f"kotekomi-{provider}-") as temporary:
        root = Path(temporary)
        ledger_path = root / "ledger.db"
        archive = LocalArchiveStore(root / "archive")
        archive.initialize()
        SQLiteLedgerInitializer(ledger_path).initialize()
        representation_ids: list[str] = []
        case_values = cast(list[object], raw_cases)
        for index, raw_case in enumerate(case_values):
            case = _object(raw_case, f"cases[{index}]")
            case_id = _string(case.get("id"), f"cases[{index}].id")
            payload = (
                fixture_dir / _string(case.get("payload"), f"{case_id}.payload")
            ).read_bytes()
            envelope_path = fixture_dir / _string(case.get("envelope"), f"{case_id}.envelope")
            envelope_bytes = envelope_path.read_bytes()
            safe_metadata = _object(cast(object, json.loads(envelope_bytes)), f"{case_id}.envelope")
            delivery = NewsDeliveryEnvelope(
                payload=payload,
                media_type=_string(case.get("media_type"), f"{case_id}.media_type"),
                envelope_bytes=envelope_bytes,
                envelope_media_type="application/json",
                retrieval_method="authorized_recording",
                requested_uri=_optional_string(case.get("requested_uri")),
                canonical_uri=_optional_string(case.get("canonical_uri")),
                response_status=200,
                safe_metadata=safe_metadata,
            )
            first_identification = adapter.identify(delivery)
            if first_identification != adapter.identify(delivery):
                raise AssertionError(f"{case_id}: adapter identification is nondeterministic")
            first_item = adapter.parse(delivery)
            if first_item != adapter.parse(delivery):
                raise AssertionError(f"{case_id}: adapter parse output is nondeterministic")
            expected = _object(case.get("expected"), f"{case_id}.expected")
            expected_item_path = fixture_dir / _string(
                case.get("expected_item"), f"{case_id}.expected_item"
            )
            expected_item = _object(
                cast(object, json.loads(expected_item_path.read_bytes())),
                f"{case_id}.expected_item",
            )
            if first_item.model_dump(mode="json") != expected_item:
                raise AssertionError(f"{case_id}: provider-neutral item does not match fixture")
            identity = first_identification.identity
            exact_values = {
                "provider_namespace": identity.provider_namespace,
                "provider_item_id": identity.provider_item_id,
                "provider_version": identity.provider_version,
                "provider_status": identity.provider_status,
                "format_precedence": first_identification.format_precedence.value,
            }
            for key, actual in exact_values.items():
                if expected.get(key) != actual:
                    raise AssertionError(f"{case_id}: expected {key} does not match adapter output")
            with sqlite_ledger_transaction(ledger_path) as repository:
                outcome = ingest_structured_news(
                    NewsIngestInput(delivery, now, now, case_id, build),
                    repository,
                    archive,
                    adapter,
                    Uuid4ProcessingAttemptIdFactory(),
                    UtcProcessingClock(),
                )
                expected_status = NewsIngestStatus(
                    _string(expected.get("ingest_status"), f"{case_id}.ingest_status")
                )
                if outcome.status is not expected_status:
                    raise AssertionError(f"{case_id}: unexpected ingest status {outcome.status}")
                if outcome.revision_classification_id is None:
                    raise AssertionError(f"{case_id}: missing revision classification")
                classification = repository.get_news_revision_classification(
                    outcome.revision_classification_id
                )
                if classification is None or expected.get("generic_kind") != (
                    classification.generic_kind.value
                ):
                    raise AssertionError(f"{case_id}: unexpected generic revision kind")
                if outcome.representation_id is not None:
                    bundle = repository.get_document_representation_bundle(
                        outcome.representation_id
                    )
                    if bundle is None:
                        raise AssertionError(f"{case_id}: missing committed representation")
                    representation_ids.append(outcome.representation_id)
            with sqlite_ledger_transaction(ledger_path) as repository:
                replay = ingest_structured_news(
                    NewsIngestInput(delivery, now, now, f"{case_id}-replay", build),
                    repository,
                    archive,
                    adapter,
                    Uuid4ProcessingAttemptIdFactory(),
                    UtcProcessingClock(),
                )
                replay_status_value = expected.get("replay_status", "reused")
                expected_replay_status = NewsIngestStatus(
                    _string(replay_status_value, f"{case_id}.replay_status")
                )
                if replay.status is not expected_replay_status:
                    raise AssertionError(f"{case_id}: unexpected replay status {replay.status}")
        with sqlite_ledger_transaction(ledger_path) as repository:
            for representation_id in representation_ids:
                if repository.get_document_representation_bundle(representation_id) is None:
                    raise AssertionError(
                        "Private conformance representation failed restart replay."
                    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", required=True)
    parser.add_argument("--fixture-dir", type=Path, required=True)
    parser.add_argument("--adapter-factory", required=True)
    args = parser.parse_args()
    run_suite(args.provider, args.fixture_dir, args.adapter_factory)


if __name__ == "__main__":
    main()
