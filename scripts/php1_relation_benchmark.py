"""Validation and exact matching for the PHP-1 complete relation subset."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from kotekomi_application import source_copy_view

SCHEMA_VERSION = "php1_direct_organization_relation_benchmark_v2"
ANNOTATION_STATUS = "policy_aligned_development_benchmark"
COMPLETE_COVERAGE_STATUS = "complete_php1_direct_organization_relations"


@dataclass(frozen=True)
class DirectOrganizationRelationExpectation:
    expectation_id: str
    subject_text: str
    relation_text: str
    accepted_relation_texts: tuple[str, ...]
    object_text: str
    relationship_shape: str

    def matches(self, hypothesis: dict[str, Any]) -> bool:
        """Match direction and one reviewed relation expression."""
        return (
            source_copy_view(str(hypothesis["subject_text"])) == source_copy_view(self.subject_text)
            and source_copy_view(str(hypothesis["relation_text"]))
            in {source_copy_view(item) for item in self.accepted_relation_texts}
            and source_copy_view(str(hypothesis["object_text"]))
            == source_copy_view(self.object_text)
        )


@dataclass(frozen=True)
class CompleteRelationSegment:
    case_ids: tuple[str, ...]
    fixture_path: str
    paragraph_anchor: str
    source_segment_anchor: str
    relations: tuple[DirectOrganizationRelationExpectation, ...]
    excluded_pair_decisions: tuple[dict[str, str], ...]


def load_and_validate_relation_benchmark(path: Path) -> tuple[CompleteRelationSegment, ...]:
    """Load the policy-aligned complete relation subset."""
    raw_value: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw_value, dict):
        raise ValueError("PHP-1 relation benchmark must be an object.")
    raw = cast(dict[str, Any], raw_value)
    if set(raw) != {"schema_version", "annotation_status", "segments"}:
        raise ValueError("PHP-1 relation benchmark fields do not match the contract.")
    if raw["schema_version"] != SCHEMA_VERSION:
        raise ValueError("PHP-1 relation benchmark schema does not match the contract.")
    if raw["annotation_status"] != ANNOTATION_STATUS:
        raise ValueError("PHP-1 relation benchmark status does not match the contract.")
    segments_value = raw["segments"]
    if not isinstance(segments_value, list) or not segments_value:
        raise ValueError("PHP-1 relation benchmark requires segments.")
    segments: list[CompleteRelationSegment] = []
    expectation_ids: set[str] = set()
    segment_ids: set[tuple[str, str]] = set()
    for segment_value in cast(list[object], segments_value):
        if not isinstance(segment_value, dict):
            raise ValueError("PHP-1 relation benchmark segment must be an object.")
        segment = cast(dict[str, Any], segment_value)
        required = {
            "case_ids",
            "fixture_path",
            "paragraph_anchor",
            "source_segment_anchor",
            "coverage_status",
            "relations",
        }
        allowed = required | {"excluded_pair_decisions"}
        if not required.issubset(segment) or not set(segment).issubset(allowed):
            raise ValueError("PHP-1 relation benchmark segment fields do not match.")
        if segment["coverage_status"] != COMPLETE_COVERAGE_STATUS:
            raise ValueError("PHP-1 relation benchmark segment is not complete.")
        case_ids = _string_tuple(segment["case_ids"], "case IDs")
        fixture_path = _string(segment["fixture_path"], "fixture path")
        paragraph_anchor = _string(segment["paragraph_anchor"], "paragraph anchor")
        source_segment_anchor = _string(segment["source_segment_anchor"], "Source segment anchor")
        segment_id = (fixture_path, source_copy_view(source_segment_anchor))
        if segment_id in segment_ids:
            raise ValueError("PHP-1 relation benchmark repeats a complete Source segment.")
        segment_ids.add(segment_id)
        relation_values = segment["relations"]
        if not isinstance(relation_values, list) or not relation_values:
            raise ValueError("PHP-1 complete relation segment requires relations.")
        relations: list[DirectOrganizationRelationExpectation] = []
        relation_identities: set[tuple[str, str, str]] = set()
        for relation_value in cast(list[object], relation_values):
            relation = _relation(relation_value)
            if relation.expectation_id in expectation_ids:
                raise ValueError("PHP-1 relation benchmark repeats an expectation ID.")
            expectation_ids.add(relation.expectation_id)
            identity = (
                source_copy_view(relation.subject_text),
                source_copy_view(relation.relation_text),
                source_copy_view(relation.object_text),
            )
            if identity in relation_identities:
                raise ValueError("PHP-1 relation benchmark repeats a relation identity.")
            relation_identities.add(identity)
            relations.append(relation)
        excluded_values = segment.get("excluded_pair_decisions", [])
        if not isinstance(excluded_values, list):
            raise ValueError("PHP-1 excluded pair decisions must be an array.")
        excluded = tuple(_excluded_pair(item) for item in cast(list[object], excluded_values))
        segments.append(
            CompleteRelationSegment(
                case_ids,
                fixture_path,
                paragraph_anchor,
                source_segment_anchor,
                tuple(relations),
                excluded,
            )
        )
    return tuple(segments)


def validate_relation_segment_source(
    segment: CompleteRelationSegment, source_copy_text: str
) -> None:
    """Prove every reviewed literal expression occurs in the selected Source copy."""
    if source_copy_view(segment.source_segment_anchor) not in source_copy_view(source_copy_text):
        raise ValueError("PHP-1 relation Source segment anchor does not match source text.")
    for relation in segment.relations:
        for field, expression in (
            ("subject", relation.subject_text),
            ("relation", relation.relation_text),
            ("object", relation.object_text),
        ):
            if source_copy_view(expression) not in source_copy_view(source_copy_text):
                raise ValueError(f"PHP-1 relation {field} does not match source text.")


def score_relation_run(
    benchmark: tuple[CompleteRelationSegment, ...],
    run: dict[str, Any],
    expectation_segment_keys: dict[str, list[str]],
) -> dict[str, Any]:
    """Score one complete-subset relation run with direction and meaning."""
    relations = {
        relation.expectation_id: relation for segment in benchmark for relation in segment.relations
    }
    if set(relations) != set(expectation_segment_keys):
        raise ValueError("PHP-1 relation run does not bind every benchmark expectation.")
    segment_results = {
        (
            str(segment["fixture_path"]),
            str(segment["paragraph_node_id"]),
            str(segment["source_segment_label"]),
        ): segment
        for segment in cast(list[dict[str, Any]], run["segments"])
    }
    expected_by_segment: dict[
        tuple[str, str, str], list[DirectOrganizationRelationExpectation]
    ] = {}
    for expectation_id, key_value in expectation_segment_keys.items():
        if len(key_value) != 3:
            raise ValueError("PHP-1 relation segment key must contain three values.")
        key = (str(key_value[0]), str(key_value[1]), str(key_value[2]))
        expected_by_segment.setdefault(key, []).append(relations[expectation_id])
    if set(expected_by_segment) != set(segment_results):
        raise ValueError("PHP-1 relation run does not cover the complete subset.")
    target_results: list[dict[str, Any]] = []
    unexpected: list[dict[str, Any]] = []
    pair_task_count = 0
    terminal_pair_task_count = 0
    for key, segment in sorted(segment_results.items()):
        judgments = cast(list[dict[str, Any]], segment["pair_results"])
        pair_task_count += len(judgments)
        terminal_pair_task_count += sum(
            str(judgment["status"])
            in {"verified", "pair_abstained", "pair_unverified", "pair_invalid"}
            for judgment in judgments
        )
        hypotheses = [
            {
                **hypothesis,
                "model_run_id": judgment.get("model_run_id"),
                "pair": [
                    judgment.get("first_organization_text"),
                    judgment.get("second_organization_text"),
                ],
            }
            for judgment in judgments
            if judgment["status"] == "verified"
            for hypothesis in cast(list[dict[str, Any]], judgment["verified_hypotheses"])
        ]
        expected = expected_by_segment[key]
        for relation in expected:
            matches = [item for item in hypotheses if relation.matches(item)]
            target_results.append(
                {
                    "expectation_id": relation.expectation_id,
                    "target_status": "matched" if matches else "missing",
                    "matches": matches,
                }
            )
        for hypothesis in hypotheses:
            if any(relation.matches(hypothesis) for relation in expected):
                continue
            unexpected.append(
                {
                    "fixture_path": key[0],
                    "paragraph_node_id": key[1],
                    "source_segment_label": key[2],
                    **hypothesis,
                }
            )
    matched_count = sum(item["target_status"] == "matched" for item in target_results)
    return {
        "repetition": int(run["repetition"]),
        "target_count": len(target_results),
        "matched_target_count": matched_count,
        "missing_target_count": len(target_results) - matched_count,
        "target_results": target_results,
        "unexpected_accepted_relations": unexpected,
        "pair_task_count": pair_task_count,
        "terminal_pair_task_count": terminal_pair_task_count,
        "all_pair_tasks_terminal": pair_task_count == terminal_pair_task_count,
    }


def _relation(value: object) -> DirectOrganizationRelationExpectation:
    if not isinstance(value, dict):
        raise ValueError("PHP-1 relation expectation must be an object.")
    raw = cast(dict[str, Any], value)
    required = {
        "expectation_id",
        "subject_text",
        "relation_text",
        "object_text",
        "relationship_shape",
    }
    allowed = required | {"accepted_relation_texts"}
    if not required.issubset(raw) or not set(raw).issubset(allowed):
        raise ValueError("PHP-1 relation expectation fields do not match.")
    relation_text = _string(raw["relation_text"], "relation text")
    accepted = (
        _string_tuple(raw["accepted_relation_texts"], "accepted relation texts")
        if "accepted_relation_texts" in raw
        else (relation_text,)
    )
    if relation_text not in accepted:
        raise ValueError("PHP-1 accepted relation texts must include the source expression.")
    subject = _string(raw["subject_text"], "subject text")
    object_text = _string(raw["object_text"], "object text")
    if source_copy_view(subject) == source_copy_view(object_text):
        raise ValueError("PHP-1 direct relation requires distinct Organizations.")
    return DirectOrganizationRelationExpectation(
        _string(raw["expectation_id"], "expectation ID"),
        subject,
        relation_text,
        accepted,
        object_text,
        _string(raw["relationship_shape"], "relationship shape"),
    )


def _excluded_pair(value: object) -> dict[str, str]:
    if not isinstance(value, dict):
        raise ValueError("PHP-1 excluded pair decision fields do not match.")
    raw = cast(dict[str, Any], value)
    if set(raw) != {"subject_text", "object_text", "reason"}:
        raise ValueError("PHP-1 excluded pair decision fields do not match.")
    return {key: _string(raw[key], key.replace("_", " ")) for key in sorted(raw)}


def _string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"PHP-1 relation benchmark {label} must be non-empty.")
    return value


def _string_tuple(value: object, label: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"PHP-1 relation benchmark {label} must be a non-empty array.")
    result = tuple(_string(item, label) for item in cast(list[object], value))
    if len(set(result)) != len(result):
        raise ValueError(f"PHP-1 relation benchmark {label} repeats a value.")
    return result
