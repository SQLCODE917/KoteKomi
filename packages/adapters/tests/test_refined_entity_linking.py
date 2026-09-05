from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from kotekomi_adapters.refined_entity_linking import (
    REFINED_ENTITY_SET,
    REFINED_MODEL_ID,
    REFINED_MODEL_REVISION,
    REFINED_PACKAGE_REVISION,
    REFINED_RESOURCE_MANIFEST_SHA256,
    REFINED_RUNTIME_IDENTITY,
    RefinedEntityLinkingAdapter,
    RefinedEntityLinkingConfig,
    RefinedEntityLinkingWorkerError,
)
from kotekomi_adapters.refined_worker_transport import RefinedWorkerExchange
from kotekomi_application.hybrid_entity_grounding import (
    EntityLinkCandidateKind,
    EntityLinkerIdentity,
    EntityLinkingInput,
    EntityLinkMention,
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


def test_refined_linker_sends_offline_caller_spans_and_preserves_all_ranks() -> None:
    source = "NIST worked."
    request = _request(source)
    transport = FakeTransport(_response(request))
    adapter = RefinedEntityLinkingAdapter(_config(), transport=transport)

    execution = adapter.link(request)

    assert transport.requests[0]["download_files"] is False
    assert transport.requests[0]["options"] == {
        "apply_class_check": False,
        "prune_ner_types": True,
        "return_special_spans": False,
    }
    candidates = execution.batch.evidences[0].candidates
    assert [(item.rank, item.kind, item.wikidata_id) for item in candidates] == [
        (1, EntityLinkCandidateKind.KNOWLEDGE_BASE_ENTITY, "Q176691"),
        (2, EntityLinkCandidateKind.NIL, None),
    ]
    assert candidates[0].wikipedia_title == "National Institute of Standards and Technology"
    assert execution.raw_output


@pytest.mark.parametrize("failure", ["rank", "duplicate", "title", "source", "nonfinite"])
def test_refined_linker_rejects_malformed_external_output(failure: str) -> None:
    source = "NIST worked."
    request = _request(source)
    response = _response(request)
    evidence = response["evidences"][0]  # type: ignore[index]
    candidates = evidence["candidates"]  # type: ignore[index]
    if failure == "rank":
        candidates[0]["rank"] = 2  # type: ignore[index]
    elif failure == "duplicate":
        candidates[1] = dict(candidates[0], rank=2)  # type: ignore[index]
    elif failure == "title":
        candidates[0]["wikipedia_title_wikidata_id"] = "Q1"  # type: ignore[index]
    elif failure == "source":
        evidence["returned_text"] = "NISX"  # type: ignore[index]
    else:
        candidates[0]["score"] = "NaN"  # type: ignore[index]

    transport = FakeTransport(response)
    adapter = RefinedEntityLinkingAdapter(_config(), transport=transport)

    with pytest.raises(ValueError):
        adapter.link(request)

    assert transport.discarded is True


def test_refined_linker_exposes_typed_worker_failure() -> None:
    transport = FakeTransport(
        {
            "schema_version": "refined_entity_linking_response_v1",
            "status": "blocked",
            "failure": "resources_unavailable",
            "diagnostics": ["Pinned resources are unavailable."],
        }
    )
    adapter = RefinedEntityLinkingAdapter(
        _config(),
        transport=transport,
    )

    with pytest.raises(RefinedEntityLinkingWorkerError) as captured:
        adapter.link(_request("NIST worked."))

    assert captured.value.failure == "resources_unavailable"
    assert captured.value.raw_output
    assert transport.discarded is False


def test_worker_looks_up_each_ranked_title_by_its_own_wikidata_id() -> None:
    worker = _load_worker_module()
    processor = SimpleNamespace(
        preprocessor=SimpleNamespace(qcode_to_wiki={"Q1": "Universe", "Q2": "Earth"})
    )
    entity = SimpleNamespace(
        wikidata_entity_id="Q2",
        human_readable_name="Earth",
        parsed_string=None,
    )

    result = worker._ranked_candidate(processor, 2, entity, 0.25)

    assert result["wikidata_id"] == "Q2"
    assert result["wikipedia_title"] == "Earth"
    assert result["wikipedia_title_wikidata_id"] == "Q2"


def test_worker_does_not_duplicate_nil_when_refined_already_ranked_it() -> None:
    worker = _load_worker_module()
    nil_entity = SimpleNamespace(wikidata_entity_id=None)
    span = SimpleNamespace(
        predicted_entity=nil_entity,
        entity_linking_model_confidence_score=0.4,
        top_k_predicted_entities=[(nil_entity, 0.4)],
        text="Michael",
        start=0,
        ln=7,
    )
    processor = SimpleNamespace(preprocessor=SimpleNamespace(qcode_to_wiki={}))

    evidence = worker._evidence(processor, "mnc_fixture", span)

    assert [item["kind"] for item in evidence["candidates"]] == ["nil"]


def test_worker_exchange_echoes_request_id_for_success_and_failure() -> None:
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
    for status in ("completed", "blocked"):
        assert worker._exchange_response(request_id, {"status": status}) == {
            "schema_version": "refined_worker_exchange_v1",
            "request_id": request_id,
            "payload": {"status": status},
        }


def _request(source: str) -> EntityLinkingInput:
    return EntityLinkingInput(
        source_segment_id="src_fixture",
        source_text_sha256=hashlib.sha256(source.encode()).hexdigest(),
        source_text=source,
        mentions=(EntityLinkMention(candidate_id="mnc_" + "1" * 24, text="NIST", start=0, end=4),),
    )


def _config() -> RefinedEntityLinkingConfig:
    return RefinedEntityLinkingConfig(
        python_executable=Path("/worker/bin/python"),
        worker_script=Path("/worker/refined_entity_linking_worker.py"),
        data_dir=Path("/worker/resources"),
    )


def _response(request: EntityLinkingInput) -> dict[str, object]:
    return {
        "schema_version": "refined_entity_linking_response_v1",
        "status": "completed",
        "identity": EntityLinkerIdentity(
            producer_id="refined:1.0",
            model_id=REFINED_MODEL_ID,
            model_revision=REFINED_MODEL_REVISION,
            entity_set=REFINED_ENTITY_SET,
            package_revision=REFINED_PACKAGE_REVISION,
            resource_manifest_sha256=REFINED_RESOURCE_MANIFEST_SHA256,
            runtime_identity=REFINED_RUNTIME_IDENTITY,
            timeout_seconds=300.0,
        ).model_dump(mode="json"),
        "load_elapsed_ms": 100,
        "inference_elapsed_ms": 20,
        "evidences": [
            {
                "candidate_id": request.mentions[0].candidate_id,
                "returned_text": "NIST",
                "start": 0,
                "end": 4,
                "candidates": [
                    {
                        "rank": 1,
                        "kind": "knowledge_base_entity",
                        "wikidata_id": "Q176691",
                        "wikipedia_title": "National Institute of Standards and Technology",
                        "wikipedia_title_wikidata_id": "Q176691",
                        "label": "National Institute of Standards and Technology",
                        "score": 0.99,
                    },
                    {
                        "rank": 2,
                        "kind": "nil",
                        "wikidata_id": None,
                        "wikipedia_title": None,
                        "wikipedia_title_wikidata_id": None,
                        "label": None,
                        "score": 0.01,
                    },
                ],
            }
        ],
    }


def _load_worker_module() -> Any:
    path = Path(__file__).resolve().parents[3] / "scripts" / "refined_entity_linking_worker.py"
    spec = importlib.util.spec_from_file_location("refined_entity_linking_worker_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
