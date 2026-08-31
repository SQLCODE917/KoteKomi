from __future__ import annotations

from typing import Any

import pytest
from kotekomi_application.extraction_stage_trace import (
    ExtractionStageStatus,
    ExtractionStageTrace,
    build_extraction_stage_trace,
    canonical_extraction_stage_trace_json,
    extraction_stage_trace_from_json,
    extraction_stage_trace_to_json,
    validate_extraction_stage_trace_chain,
)


def _trace(**overrides: Any) -> ExtractionStageTrace:
    values: dict[str, Any] = {
        "trace_run_id": "etr_test",
        "ordinal": 0,
        "stage_id": "organization_mention_proposal",
        "stage_version": "v1",
        "producer_id": "gliner-medium-v2.1",
        "source_segment_id": "seg_test",
        "source_text_sha256": "a" * 64,
        "configuration": {"threshold": 0.5},
        "input_payload": {"source_text": "Anthropic met Palantir."},
        "output_payload": {"proposals": [{"start": 0, "end": 9}]},
        "status": ExtractionStageStatus.COMPLETED,
    }
    values.update(overrides)
    return build_extraction_stage_trace(**values)


def test_trace_is_deterministic_and_serializes_every_boundary_digest() -> None:
    first = _trace(
        configuration={"labels": ["Organization"], "threshold": 0.5},
        input_payload={"source_text": "Anthropic met Palantir.", "eligible": True},
    )
    second = _trace(
        configuration={"threshold": 0.5, "labels": ["Organization"]},
        input_payload={"eligible": True, "source_text": "Anthropic met Palantir."},
    )

    assert first == second
    payload = extraction_stage_trace_to_json(first)
    assert payload["authority"] == "derived_diagnostic"
    assert payload["configuration_sha256"]
    assert payload["input_sha256"]
    assert payload["output_sha256"]
    assert canonical_extraction_stage_trace_json(first).startswith('{"authority"')


def test_trace_rejects_non_json_and_non_terminal_failure_evidence() -> None:
    with pytest.raises(ValueError, match="finite JSON"):
        _trace(configuration={"threshold": float("nan")})
    with pytest.raises(ValueError, match="requires a diagnostic"):
        _trace(status=ExtractionStageStatus.BLOCKED)
    with pytest.raises(ValueError, match="ordered and distinct"):
        _trace(execution_record_ids=("run_2", "run_1"))


def test_trace_rejects_tampered_payload_digest_and_identity() -> None:
    trace = _trace()
    payload = extraction_stage_trace_to_json(trace)
    payload["output"] = {"proposals": []}

    with pytest.raises(ValueError, match="output digest"):
        extraction_stage_trace_from_json(payload)

    payload = extraction_stage_trace_to_json(trace)
    payload["id"] = "xst_" + "b" * 24
    with pytest.raises(ValueError, match="ID does not match"):
        extraction_stage_trace_from_json(payload)


def test_trace_chain_requires_one_source_and_prior_contiguous_parents() -> None:
    proposer = _trace()
    fusion = _trace(
        ordinal=1,
        stage_id="organization_candidate_fusion",
        producer_id="kotekomi",
        parent_trace_ids=(proposer.id,),
    )
    validate_extraction_stage_trace_chain((fusion, proposer))

    with pytest.raises(ValueError, match="contiguous"):
        validate_extraction_stage_trace_chain((proposer, _trace(ordinal=2)))
    with pytest.raises(ValueError, match="parents must be earlier"):
        validate_extraction_stage_trace_chain((_trace(parent_trace_ids=("xst_" + "c" * 24,)),))
    with pytest.raises(ValueError, match="one Source segment"):
        validate_extraction_stage_trace_chain(
            (proposer, _trace(ordinal=1, source_segment_id="seg_other"))
        )
