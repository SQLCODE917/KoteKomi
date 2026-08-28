from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[3]


def _module() -> Any:
    path = ROOT / "scripts/php1_relation_benchmark.py"
    spec = importlib.util.spec_from_file_location("php1_relation_benchmark_test", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_project_relation_benchmark_declares_complete_segments_and_relations() -> None:
    module = _module()

    segments = module.load_and_validate_relation_benchmark(
        ROOT / "docs/php1-direct-organization-relation-benchmark-v2.json"
    )

    assert len(segments) == 9
    assert sum(len(segment.relations) for segment in segments) == 15
    assert all(segment.relations for segment in segments)


def test_relation_match_requires_direction_relation_and_object() -> None:
    module = _module()
    relation = module.DirectOrganizationRelationExpectation(
        "target-1",
        "UK AISI",
        "was officially established as an evolution of",
        (
            "was officially established as an evolution of",
            "was established as an evolution of",
        ),
        "Frontier AI Taskforce",
        "lineage",
    )

    assert relation.matches(
        {
            "subject_text": "UK AISI",
            "relation_text": "was established as an evolution of",
            "object_text": "Frontier AI Taskforce",
        }
    )
    assert not relation.matches(
        {
            "subject_text": "Frontier AI Taskforce",
            "relation_text": "was established as an evolution of",
            "object_text": "UK AISI",
        }
    )
    assert not relation.matches(
        {
            "subject_text": "UK AISI",
            "relation_text": "worked with",
            "object_text": "Frontier AI Taskforce",
        }
    )


def test_relation_source_validation_rejects_a_missing_literal_expression() -> None:
    module = _module()
    segment = module.CompleteRelationSegment(
        ("TEST-01",),
        "raw/test.pdf",
        "Anthropic partnered",
        "Anthropic partnered with",
        (
            module.DirectOrganizationRelationExpectation(
                "target-1",
                "Anthropic",
                "partnered with",
                ("partnered with",),
                "Palantir",
                "partnership",
            ),
        ),
        (),
    )

    with pytest.raises(ValueError, match="object"):
        module.validate_relation_segment_source(segment, "Anthropic partnered with Amazon")
