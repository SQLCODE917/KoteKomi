"""Demonstrate source-backed wiki questions against the locked deposited PDF."""

from __future__ import annotations

import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from verify_dr5_canonical import (
    ROOT,
    ConformanceError,
    command_json,
    config_text,
    fixture_path,
    read_json,
    run_command,
)

type JsonObject = dict[str, Any]


@dataclass(frozen=True)
class DemoQuestion:
    question: str
    expected_anchor: str


QUESTIONS = (
    DemoQuestion(
        "all lawful purposes",
        "all lawful purposes",
    ),
    DemoQuestion(
        "1789 Capital",
        "1789 Capital",
    ),
    DemoQuestion(
        "preliminary injunction",
        "preliminary injunction",
    ),
    DemoQuestion(
        "cross the Rubicon",
        "cross the Rubicon",
    ),
    DemoQuestion(
        "Directive 3000.09",
        "Directive 3000.09",
    ),
)


def run() -> tuple[JsonObject, ...]:
    scenario = read_json(ROOT / ".agent/scenarios/anthropic-dod-dispute-v1/scenario.json")
    fixture = fixture_path(scenario)
    with tempfile.TemporaryDirectory(prefix="kotekomi-wiki-demo-") as temporary:
        root = Path(temporary)
        ledger_path = root / "ledger.sqlite"
        config_path = root / "kotekomi.toml"
        config_path.write_text(config_text(ledger_path, root / "archive"), encoding="utf-8")
        run_command(
            "--config", str(config_path), "ledger", "init", "--ledger-path", str(ledger_path)
        )
        ingest = command_json(
            "--config",
            str(config_path),
            "source",
            "add-file",
            str(fixture),
            "--source-url",
            str(cast(JsonObject, scenario["source"])["normalized_url"]),
            "--format",
            "json",
        )
        representation_id = _required_string(ingest, "representation_id")
        return tuple(
            _run_question(ledger_path, representation_id, question) for question in QUESTIONS
        )


def _run_question(
    ledger_path: Path,
    representation_id: str,
    question: DemoQuestion,
) -> JsonObject:
    result = command_json(
        "retrieval",
        "query",
        "--ledger-path",
        str(ledger_path),
        "--representation-id",
        representation_id,
        "--query",
        question.question,
        "--maximum-hits",
        "3",
        "--context-profile",
        "retrieval-validation-v1",
        "--channel",
        "exact-lexical",
        "--format",
        "json",
    )
    if result.get("status") != "complete":
        raise ConformanceError("wiki_query_failed", str(result.get("failure")))
    nodes = cast(list[JsonObject], result["authoritative_nodes"])
    context = str(result.get("context_manifest_rendered_input") or "")
    matching_node = next(
        (node for node in nodes if _contains_anchor(str(node["text"]), question.expected_anchor)),
        None,
    )
    if matching_node is None and not _contains_anchor(context, question.expected_anchor):
        raise ConformanceError(
            "wiki_answer_anchor_missing",
            f"Question did not retrieve its source anchor: {question.expected_anchor}",
        )
    hit = cast(list[JsonObject], result["hits"])[0]
    return {
        "question": question.question,
        "expected_anchor": question.expected_anchor,
        "retrieved_source_excerpt": _excerpt(
            str(matching_node["text"]) if matching_node is not None else context,
            question.expected_anchor,
        ),
        "section_path": matching_node["section_path"] if matching_node is not None else [],
        "authoritative_node_ids": result["selected_node_ids"],
        "retrieval_query_id": result["retrieval_query_id"],
        "index_manifest_ids": result["index_manifest_ids"],
        "context_manifest_id": result["context_manifest_id"],
        "channels": result["consulted_channels"],
        "selection_reason": hit["selection_reason"],
        "source_text_digest": hit["original_text_digest"],
    }


def _excerpt(value: str, anchor: str, maximum_length: int = 420) -> str:
    compact = " ".join(value.split())
    if len(compact) <= maximum_length:
        return compact
    anchor_start = compact.casefold().find(anchor.casefold())
    if anchor_start < 0:
        return compact[: maximum_length - 1] + "…"
    start = max(0, anchor_start - maximum_length // 2)
    end = min(len(compact), start + maximum_length)
    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(compact) else ""
    return prefix + compact[start:end].strip() + suffix


def _contains_anchor(source_text: str, anchor: str) -> bool:
    normalized_source = re.sub(r"\s+", " ", source_text).casefold()
    normalized_anchor = re.sub(r"\s+", " ", anchor).casefold()
    return normalized_anchor in normalized_source


def _required_string(value: JsonObject, key: str) -> str:
    result = value.get(key)
    if not isinstance(result, str):
        raise ConformanceError("wiki_ingest_invalid", f"Missing string field: {key}")
    return result


if __name__ == "__main__":
    import json

    try:
        print(json.dumps(run(), indent=2, sort_keys=True))
    except ConformanceError as error:
        print(json.dumps({"status": "failed", "failure": error.code, "message": str(error)}))
        raise SystemExit(1) from None
