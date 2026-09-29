#!/usr/bin/env python3
"""Run the R4 deterministic decontextualization-composition pipeline.

This runner is model-free. It binds the frozen Proposition Gold, trigger Gold,
connection Gold, pinned Stanza dependency runtime, and the frozen R3-A
Constituent Candidate Inventory plus raw Constituent Selection Answers
(`answers.jsonl`) by SHA-256;
re-derives the pinned dependency tokens once per unique SourceSegment; locates
each Event trigger head; and composes one ``DecontextualizedProposition`` (or one
typed hold) per Event from the Selected Constituent Set.

It writes three derived-evidence outputs and changes no canonical state:

- ``propositions.json``: one proposition or typed hold per Event, in canonical
  Event order.
- ``report.json``: the sealed ``DecontextualizationReport`` with both partition
  censuses and a semantic fingerprint.
- ``review.md``: a human-readable review of every Event meaning alongside its
  composed proposition or hold reason.

The runner executes zero models, creates zero canonical Ledger writes, and
creates zero ProposedChanges. The held-out partition stays reserved and unread.

All inputs and outputs are explicit paths or a TOML config file. No environment
variables are assumed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

from kotekomi_adapters import StanzaLinguisticAnalyzer
from kotekomi_adapters.model_resources import (
    stanza_expected_resource_identity,
    stanza_model_path,
)
from kotekomi_application import (
    AttachmentSourceRange,
    ConstituentCandidateInventory,
    DecontextualizationEntityRef,
    DecontextualizedProposition,
    EventEntityLinguisticToken,
    LinguisticAnalysis,
    LinguisticAnalysisInput,
    build_decontextualization_census,
    build_decontextualization_report,
    build_decontextualized_proposition,
    parse_constituent_selection_answers,
)
from kotekomi_application.context_planning import derive_source_copy_view
from kotekomi_application.source_occurrences import source_occurrences
from kotekomi_pipelines.config import PipelineConfig, load_config
from kotekomi_pipelines.event_entity_connection_stage_local import (
    ConnectionGoldCatalog,
    ConnectionGoldEntity,
    ConnectionGoldEvent,
)
from kotekomi_pipelines.event_trigger_stage_local import (
    TriggerGoldCatalog,
    TriggerGoldEvent,
    TriggerGoldSegment,
)
from kotekomi_pipelines.parser_constituent_candidate_generation import (
    verify_frozen_evidence_digests,
)
from kotekomi_pipelines.source_grounded_proposition_stage_local import (
    PropositionGoldCatalog,
    load_proposition_gold_catalog,
)
from pydantic import BaseModel

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
TDD_PATH = REPOSITORY_ROOT / "docs/2026-09-28-decontextualization-composition.md"
DEFAULT_GOLD = REPOSITORY_ROOT / "docs/hsq-source-grounded-proposition-gold-v1.json"
DEFAULT_TRIGGER_GOLD = REPOSITORY_ROOT / "docs/hsq-event-trigger-gold-v1.json"
DEFAULT_CONNECTION_GOLD = REPOSITORY_ROOT / "docs/hsq-event-entity-connection-gold-v2.json"
DEFAULT_STANZA_LOCK = (
    REPOSITORY_ROOT / "packages/adapters/src/kotekomi_adapters/stanza-model-lock.json"
)
DEFAULT_R3_RUN_ROOT = REPOSITORY_ROOT / "data/r3-parser-constituent-runs/run-002"

RUN_SCHEMA_VERSION = "decontextualization_composition_run_v1"

PINNED_INVENTORIES_SHA256 = "5579dedfaf02b9271e5046c446989e8f7907ba93a3315b88a15cc72aaa889c3f"
PINNED_ANSWERS_SHA256 = "b9d1834785ec3116b1f2057282296914460f638c07a37b20327c55ef895a15dc"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compose one decontextualized proposition per Event, deterministically."
    )
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--gold", type=Path, default=DEFAULT_GOLD)
    parser.add_argument("--trigger-gold", type=Path, default=DEFAULT_TRIGGER_GOLD)
    parser.add_argument("--connection-gold", type=Path, default=DEFAULT_CONNECTION_GOLD)
    parser.add_argument("--stanza-lock", type=Path, default=DEFAULT_STANZA_LOCK)
    parser.add_argument(
        "--inventories", type=Path, default=DEFAULT_R3_RUN_ROOT / "inventories.json"
    )
    parser.add_argument(
        "--answers",
        type=Path,
        default=DEFAULT_R3_RUN_ROOT / "answers.jsonl",
    )
    args = parser.parse_args()
    return _run(args)


def _run(args: argparse.Namespace) -> int:
    root = args.run_root.resolve()
    if root.exists() and any(root.iterdir()):
        raise ValueError("R4 run root must be absent or empty.")
    root.mkdir(parents=True, exist_ok=True)

    _verify_frozen_inputs(
        gold=args.gold.resolve(),
        trigger_gold=args.trigger_gold.resolve(),
        connection_gold=args.connection_gold.resolve(),
        stanza_lock=args.stanza_lock.resolve(),
        inventories=args.inventories.resolve(),
        answers=args.answers.resolve(),
    )

    config = _config(args.config.resolve())
    catalog = load_proposition_gold_catalog(args.gold.resolve(), repository_root=REPOSITORY_ROOT)
    if catalog.review_status.value != "approved":
        raise ValueError("R4 requires approved Proposition Gold.")
    trigger_gold = TriggerGoldCatalog.model_validate_json(args.trigger_gold.read_bytes())
    connection_gold = ConnectionGoldCatalog.model_validate_json(args.connection_gold.read_bytes())
    if connection_gold.review_status != "approved":
        raise ValueError("R4 requires approved Connection Gold.")

    inventories = _load_models(ConstituentCandidateInventory, args.inventories.resolve())
    inventory_by_event = {item.event_id: item for item in inventories}
    answer_by_event = {
        item.event_id: item
        for item in parse_constituent_selection_answers(
            answers=_read_raw_answers(args.answers.resolve()),
            inventories_by_event=inventory_by_event,
        )
    }
    event_ids = [event.event_id for event in catalog.events]
    if set(inventory_by_event) != set(event_ids):
        raise ValueError("R3-A inventory does not cover every R4 Event.")
    if set(answer_by_event) != set(event_ids):
        raise ValueError("R3-A selection answers do not cover every R4 Event.")

    head_spans = _head_spans(trigger_gold, catalog)

    analyzer = StanzaLinguisticAnalyzer(
        model_directory=stanza_model_path(config.model_resource_root),
        resource_identity=stanza_expected_resource_identity(),
    )
    tokens_by_digest = _build_tokens_by_digest(catalog, analyzer)

    connection_by_event = {event.event_id: event for event in connection_gold.events}
    propositions: dict[str, DecontextualizedProposition] = {}
    for event in catalog.events:
        entity_event = connection_by_event[event.event_id]
        propositions[event.event_id] = build_decontextualized_proposition(
            event_id=event.event_id,
            source_text=event.source_text,
            source_text_sha256=event.source_text_sha256,
            inventory=inventory_by_event[event.event_id],
            answer=answer_by_event[event.event_id],
            trigger_head_start=head_spans[event.event_id][0],
            trigger_head_end=head_spans[event.event_id][1],
            tokens=tokens_by_digest[event.source_text_sha256],
            entities=_entity_refs(entity_event),
        )

    development_census = build_decontextualization_census(
        partition_role="development",
        event_ids=tuple(event.event_id for event in catalog.events if event.phase == "development"),
        propositions=propositions,
    )
    validation_census = build_decontextualization_census(
        partition_role="validation",
        event_ids=tuple(event.event_id for event in catalog.events if event.phase == "validation"),
        propositions=propositions,
    )
    report = build_decontextualization_report(
        development=development_census,
        validation=validation_census,
    )

    _write_json(
        root / "propositions.json",
        [item.model_dump(mode="json") for item in propositions.values()],
    )
    _write_json(root / "report.json", report.model_dump(mode="json"))
    review_path = root / "review.md"
    review_path.write_text(
        _render_review(catalog=catalog, propositions=propositions, report=report),
        encoding="utf-8",
    )

    _write_json(
        root / "run.json",
        {
            "schema_version": RUN_SCHEMA_VERSION,
            "status": "complete",
            "model_execution_count": 0,
            "canonical_write_count": 0,
            "proposed_change_count": 0,
            "event_count": len(catalog.events),
            "result_fingerprint": report.result_fingerprint,
            "inputs": {
                "tdd": _sha256_file(TDD_PATH),
                "proposition_gold": _sha256_file(args.gold.resolve()),
                "trigger_gold": _sha256_file(args.trigger_gold.resolve()),
                "connection_gold": _sha256_file(args.connection_gold.resolve()),
                "stanza_lock": _sha256_file(args.stanza_lock.resolve()),
                "inventories": _sha256_file(args.inventories.resolve()),
                "answers": _sha256_file(args.answers.resolve()),
            },
            "outputs": {
                "propositions": _sha256_file(root / "propositions.json"),
                "report": _sha256_file(root / "report.json"),
                "review": _sha256_file(root / "review.md"),
            },
        },
    )

    print(
        json.dumps(
            {
                "status": "complete",
                "run_root": str(root),
                "composed_count": development_census.composed_count
                + validation_census.composed_count,
                "held_count": development_census.held_count + validation_census.held_count,
                "model_execution_count": 0,
                "canonical_write_count": 0,
                "proposed_change_count": 0,
            },
            sort_keys=True,
        )
    )
    return 0


def _verify_frozen_inputs(
    *,
    gold: Path,
    trigger_gold: Path,
    connection_gold: Path,
    stanza_lock: Path,
    inventories: Path,
    answers: Path,
) -> None:
    verify_frozen_evidence_digests(
        proposition_gold=gold,
        trigger_gold=trigger_gold,
        connection_gold=connection_gold,
        stanza_lock=stanza_lock,
    )
    for path, pinned in (
        (inventories, PINNED_INVENTORIES_SHA256),
        (answers, PINNED_ANSWERS_SHA256),
    ):
        if _sha256_file(path) != pinned:
            raise ValueError(f"R4 frozen input drifted from its pinned digest: {path}.")


def _entity_refs(
    event: ConnectionGoldEvent,
) -> tuple[DecontextualizationEntityRef, ...]:
    return tuple(_entity_ref(item) for item in event.expected_entities)


def _entity_ref(entity: ConnectionGoldEntity) -> DecontextualizationEntityRef:
    return DecontextualizationEntityRef(
        entity_id=entity.entity_id,
        entity_kind=entity.entity_kind.value,
        canonical_name=entity.canonical_name,
        accepted_source_occurrences=tuple(
            AttachmentSourceRange(start=item.start, end=item.end, text=item.source_text)
            for item in entity.accepted_source_occurrences
        ),
    )


def _head_spans(
    trigger_gold: TriggerGoldCatalog,
    catalog: PropositionGoldCatalog,
) -> dict[str, tuple[int, int]]:
    event_ids = {event.event_id for event in catalog.events}
    spans: dict[str, tuple[int, int]] = {}
    for segment in trigger_gold.segments:
        for event in segment.events:
            if event.event_id in event_ids:
                spans[event.event_id] = _authoritative_head_span(segment, event)
    if set(spans) != event_ids:
        missing = sorted(event_ids - set(spans))
        raise ValueError(f"Trigger Gold does not cover every R4 Event expression: {missing}.")
    return spans


def _authoritative_head_span(
    segment: TriggerGoldSegment,
    event: TriggerGoldEvent,
) -> tuple[int, int]:
    source_copy = derive_source_copy_view(segment.source_text)
    occurrences = {item.occurrence_id: item for item in source_occurrences(source_copy.text)}
    head = occurrences[event.head_occurrence_id]
    return source_copy.authoritative_range(head.start, head.end)


def _build_tokens_by_digest(
    catalog: PropositionGoldCatalog,
    analyzer: StanzaLinguisticAnalyzer,
) -> dict[str, tuple[EventEntityLinguisticToken, ...]]:
    sources: dict[str, str] = {}
    for event in catalog.events:
        prior = sources.get(event.source_text_sha256)
        if prior is None:
            sources[event.source_text_sha256] = event.source_text
        elif prior != event.source_text:
            raise ValueError("Proposition Gold repeats a digest with different text.")
    result: dict[str, tuple[EventEntityLinguisticToken, ...]] = {}
    for digest, text in sources.items():
        analysis = analyzer.analyze(LinguisticAnalysisInput(source_text=text))
        if analysis.source_text_sha256 != digest:
            raise ValueError("Stanza analysis digest drifted from its source text.")
        result[digest] = _linguistic_tokens(analysis)
    return result


def _linguistic_tokens(analysis: LinguisticAnalysis) -> tuple[EventEntityLinguisticToken, ...]:
    return tuple(
        EventEntityLinguisticToken(
            token_id=item.token_id,
            sentence_id=item.sentence_id,
            text=item.text,
            start=item.start,
            end=item.end,
            lemma=item.lemma,
            part_of_speech=item.part_of_speech.value,
            dependency_relation=item.dependency_relation,
            head_token_id=item.head_token_id,
        )
        for item in analysis.tokens
    )


def _render_review(
    *,
    catalog: PropositionGoldCatalog,
    propositions: Mapping[str, DecontextualizedProposition],
    report: Any,
) -> str:
    lines = [
        "# R4 Decontextualization Composition",
        "",
        "Model executions: 0.",
        "Canonical writes: 0.",
        "ProposedChanges: 0.",
        "",
        "## Census",
        "",
        f"- development: `{report.development.composed_count}` composed, "
        f"`{report.development.held_count}` held.",
        f"- validation: `{report.validation.composed_count}` composed, "
        f"`{report.validation.held_count}` held.",
        "",
        "## Events",
        "",
    ]
    for event in catalog.events:
        proposition = propositions[event.event_id]
        lines.append(f"### {event.event_id} ({event.phase})")
        lines.append("")
        lines.append(f"- meaning: {event.event_meaning}")
        lines.append(f"- status: `{proposition.status.value}`")
        if proposition.status.value == "held":
            assert proposition.hold_reason is not None
            lines.append(f"- hold reason: `{proposition.hold_reason.value}`")
        else:
            assert proposition.relation_label is not None
            assert proposition.subject is not None
            assert proposition.polarity is not None
            assert proposition.modality is not None
            assert proposition.attribution is not None
            lines.append(f"- relation: `{proposition.relation_label}`")
            premise = proposition.subject
            lines.append(f"- subject: `{premise.exact_fragment.text}` -> `{premise.entity_ref}`")
            if proposition.object is not None:
                obj = proposition.object
                target = obj.entity_ref if obj.entity_ref is not None else obj.object_value
                lines.append(f"- object: `{obj.exact_fragment.text}` -> `{target}`")
            lines.append(f"- polarity: `{proposition.polarity.value}`")
            lines.append(f"- modality: `{proposition.modality.value}`")
            lines.append(f"- attribution: `{proposition.attribution.kind.value}`")
            if proposition.attribution.exact_carrier is not None:
                lines.append(
                    f"- carrier: `{proposition.attribution.exact_carrier.text}`"
                    f" -> `{proposition.attribution.reporter_ref}`"
                )
        lines.append("")
    return "\n".join(lines)


def _config(path: Path) -> PipelineConfig:
    return load_config(
        config_path=path,
        ledger_path_override=None,
        archive_path_override=None,
    )


def _read_raw_answers(path: Path) -> dict[str, str]:
    """Read ``answers.jsonl`` into an ``event_id -> raw_answer`` mapping."""
    result: dict[str, str] = {}
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        record = json.loads(line)
        if not isinstance(record, dict):
            raise ValueError(f"R3 answers record must be one object: {path}:{line_number}.")
        record = cast("dict[str, object]", record)
        if set(record) != {"event_id", "raw_answer"}:
            raise ValueError(
                f"R3 answers record must carry event_id and raw_answer only: {path}:{line_number}."
            )
        event_id = record["event_id"]
        raw_answer = record["raw_answer"]
        if not isinstance(event_id, str) or not isinstance(raw_answer, str):
            raise ValueError(f"R3 answers record fields must be strings: {path}:{line_number}.")
        if event_id in result:
            raise ValueError(f"R3 answers record repeats an event_id: {path}:{line_number}.")
        result[event_id] = raw_answer
    return result


def _load_models[T: BaseModel](model: type[T], path: Path) -> tuple[T, ...]:
    raw = json.loads(path.read_bytes())
    if not isinstance(raw, list):
        raise ValueError(f"Expected one JSON array: {path}.")
    values = cast("list[object]", raw)
    return tuple(model.model_validate_json(_canonical_json(item)) for item in values)


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(
            value, allow_nan=False, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        + "\n",
        encoding="utf-8",
    )


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value, allow_nan=False, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
