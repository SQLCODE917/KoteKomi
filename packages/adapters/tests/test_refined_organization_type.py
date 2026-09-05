from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest
from kotekomi_adapters.refined_organization_type import (
    REFINED_ENTITY_SET,
    REFINED_MODEL_ID,
    REFINED_MODEL_REVISION,
    REFINED_PACKAGE_REVISION,
    REFINED_RESOURCE_MANIFEST_SHA256,
    RefinedContextualOrganizationTypeAdapter,
    RefinedWorkerConfig,
    RefinedWorkerError,
)
from kotekomi_adapters.refined_worker_transport import RefinedWorkerExchange
from kotekomi_application.organization_mention_boundary_reconciliation import (
    MentionBoundaryDecisionStatus,
)
from kotekomi_application.organization_semantic_qualification import (
    ContextualOrganizationTypeInput,
    QualificationCandidate,
)


class FakeTransport:
    def __init__(self, response: dict[str, object]) -> None:
        self.response = response
        self.requests: list[dict[str, object]] = []
        self.discarded = False

    def request(self, payload: dict[str, object]) -> RefinedWorkerExchange:
        self.requests.append(payload)
        request_id = "rwr_11111111111111111111111111111111"
        raw_output = json.dumps(
            {
                "schema_version": "refined_worker_exchange_v1",
                "request_id": request_id,
                "payload": self.response,
            },
            allow_nan=False,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        return RefinedWorkerExchange(request_id, self.response, raw_output)

    def discard(self) -> None:
        self.discarded = True

    def close(self) -> None:
        pass


def _candidate(source: str, text: str, start: int, *, suffix: str = "1") -> QualificationCandidate:
    return QualificationCandidate(
        id=f"qfc_{suffix}",
        source_segment_id="src_1",
        source_text_sha256=hashlib.sha256(source.encode()).hexdigest(),
        text=text,
        start=start,
        end=start + len(text),
        boundary_decision_id=f"mbd_{suffix}",
        boundary_status=MentionBoundaryDecisionStatus.UNCONTESTED,
        boundary_rule_id="uncontested_source_span_v1",
        source_candidate_ids=(f"mnc_{suffix}",),
        proposer_ids=("gliner",),
    )


def _request(
    source: str, candidates: tuple[QualificationCandidate, ...]
) -> ContextualOrganizationTypeInput:
    return ContextualOrganizationTypeInput(
        source_segment_id="src_1",
        source_text_sha256=hashlib.sha256(source.encode()).hexdigest(),
        source_text=source,
        candidates=candidates,
    )


def _evidence(candidate: QualificationCandidate, **changes: object) -> dict[str, object]:
    value: dict[str, object] = {
        "candidate_id": candidate.id,
        "returned_text": candidate.text,
        "start": candidate.start,
        "end": candidate.end,
        "coarse_type": "MENTION",
        "coarse_mention_type": "ORG",
        "predicted_entity": {
            "wikidata_entity_id": "Q111",
            "wikipedia_entity_title": "Northstar (organization)",
            "human_readable_name": None,
            "parsed_string": None,
            "score": None,
        },
        "entity_linking_score": 0.82,
        "top_k_entities": [
            {
                "wikidata_entity_id": "Q111",
                "wikipedia_entity_title": "Northstar (organization)",
                "human_readable_name": None,
                "parsed_string": None,
                "score": 0.82,
            }
        ],
        "predicted_entity_types": [
            {"type_id": "Q43229", "type_label": "organization", "confidence": 0.77}
        ],
        "failed_class_check": False,
    }
    value.update(changes)
    return value


def _response(evidences: list[dict[str, object]]) -> dict[str, object]:
    return {
        "schema_version": "refined_contextual_type_response_v1",
        "status": "completed",
        "producer_id": "refined:1.0",
        "model_id": REFINED_MODEL_ID,
        "model_revision": REFINED_MODEL_REVISION,
        "entity_set": REFINED_ENTITY_SET,
        "package_revision": REFINED_PACKAGE_REVISION,
        "resource_manifest_sha256": REFINED_RESOURCE_MANIFEST_SHA256,
        "load_elapsed_ms": 1500,
        "inference_elapsed_ms": 25,
        "evidences": evidences,
    }


def _config() -> RefinedWorkerConfig:
    return RefinedWorkerConfig(
        python_executable=Path("/worker/bin/python"),
        worker_script=Path("/worker/refined_worker.py"),
        data_dir=Path("/worker/resources"),
    )


def test_refined_adapter_sends_exact_predetermined_spans_and_maps_complete_evidence() -> None:
    source = "Northstar worked with Southstar."
    first = _candidate(source, "Northstar", 0)
    second = _candidate(source, "Southstar", 22, suffix="2")
    transport = FakeTransport(_response([_evidence(first), _evidence(second)]))
    adapter = RefinedContextualOrganizationTypeAdapter(_config(), transport=transport)

    batch = adapter.qualify(_request(source, (first, second)))

    assert transport.requests == [
        {
            "schema_version": "refined_contextual_type_request_v1",
            "source_segment_id": "src_1",
            "source_text_sha256": hashlib.sha256(source.encode()).hexdigest(),
            "source_text": source,
            "model_id": REFINED_MODEL_ID,
            "model_revision": REFINED_MODEL_REVISION,
            "entity_set": REFINED_ENTITY_SET,
            "package_revision": REFINED_PACKAGE_REVISION,
            "data_dir": "/worker/resources",
            "download_files": False,
            "candidates": [
                {"candidate_id": "qfc_1", "text": "Northstar", "start": 0, "end": 9},
                {"candidate_id": "qfc_2", "text": "Southstar", "start": 22, "end": 31},
            ],
        }
    ]
    assert [evidence.candidate_id for evidence in batch.evidences] == ["qfc_1", "qfc_2"]
    assert batch.evidences[0].predicted_entity is not None
    assert batch.evidences[0].predicted_entity.wikidata_entity_id == "Q111"
    assert batch.evidences[0].predicted_entity_types[0].type_label == "organization"


@pytest.mark.parametrize("failure", ["missing", "duplicate", "reordered", "drifted"])
def test_refined_adapter_rejects_span_result_integrity_failures(failure: str) -> None:
    source = "Northstar worked with Southstar."
    first = _candidate(source, "Northstar", 0)
    second = _candidate(source, "Southstar", 22, suffix="2")
    evidences = [_evidence(first), _evidence(second)]
    if failure == "missing":
        evidences = evidences[:1]
    elif failure == "duplicate":
        evidences = [evidences[0], evidences[0]]
    elif failure == "reordered":
        evidences.reverse()
    else:
        evidences[0] = _evidence(first, returned_text="Northstxr")
    transport = FakeTransport(_response(evidences))
    adapter = RefinedContextualOrganizationTypeAdapter(
        _config(),
        transport=transport,
    )

    with pytest.raises(ValueError, match="ordered input candidates|source characters"):
        adapter.qualify(_request(source, (first, second)))

    assert transport.discarded is True


def test_refined_adapter_exposes_typed_worker_failure() -> None:
    source = "Northstar worked."
    candidate = _candidate(source, "Northstar", 0)
    response: dict[str, object] = {
        "schema_version": "refined_contextual_type_response_v1",
        "status": "blocked",
        "failure": "resources_unavailable",
        "diagnostics": ["Pinned ReFinED resources are not installed."],
    }
    transport = FakeTransport(response)
    adapter = RefinedContextualOrganizationTypeAdapter(
        _config(),
        transport=transport,
    )

    with pytest.raises(RefinedWorkerError, match="resources_unavailable") as captured:
        adapter.qualify(_request(source, (candidate,)))

    assert captured.value.failure == "resources_unavailable"
    assert captured.value.diagnostics == ("Pinned ReFinED resources are not installed.",)
    assert transport.discarded is False


def test_refined_adapter_rejects_response_without_protocol_discriminator() -> None:
    source = "Northstar worked."
    candidate = _candidate(source, "Northstar", 0)
    adapter = RefinedContextualOrganizationTypeAdapter(
        _config(),
        transport=FakeTransport({}),
    )

    with pytest.raises(ValueError, match="requires schema_version and status"):
        adapter.qualify(_request(source, (candidate,)))


def test_contextual_type_worker_exchange_echoes_request_id() -> None:
    worker = _load_worker_module()
    request_id = "rwr_11111111111111111111111111111111"

    observed_id, payload = worker._exchange_request(
        {
            "schema_version": "refined_worker_exchange_v1",
            "request_id": request_id,
            "payload": {"fixture": True},
        }
    )

    assert observed_id == request_id
    assert payload == {"fixture": True}
    assert worker._exchange_response(request_id, {"status": "blocked"}) == {
        "schema_version": "refined_worker_exchange_v1",
        "request_id": request_id,
        "payload": {"status": "blocked"},
    }


def _load_worker_module() -> Any:
    path = Path(__file__).resolve().parents[3] / "scripts" / "refined_organization_type_worker.py"
    spec = importlib.util.spec_from_file_location("refined_organization_type_worker_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
