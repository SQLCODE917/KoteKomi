#!/usr/bin/env python3
"""Run HSQ-7 mention, reference, and event-trigger stage experiments."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol, cast

from kotekomi_adapters import (
    FCorefAdapter,
    FCorefConfig,
    GlinerMentionProposer,
    LocalArchiveStore,
    QANomNominalizationAnalyzer,
    StanzaLinguisticAnalyzer,
)
from kotekomi_adapters.model_resources import (
    fcoref_expected_resource_identity,
    fcoref_model_path,
    fcoref_python_path,
    gliner_model_path,
    qanom_expected_resource_identity,
    qanom_lexical_resource_path,
    qanom_model_path,
    stanza_expected_resource_identity,
    stanza_model_path,
)
from kotekomi_application import (
    ContextModelProfile,
    CoreferenceExecution,
    CoreferenceInput,
    ExecutionSetting,
    HybridEntityGroundingStatus,
    HybridEventTriggerCommand,
    HybridEventTriggerPrompts,
    HybridMentionPreviewCommand,
    HybridPreviewStatus,
    HybridReferencePreviewCommand,
    LinguisticAnalysis,
    LinguisticAnalysisInput,
    LinguisticAnalyzer,
    LinguisticToken,
    NominalizationAnalysis,
    NominalizationAnalysisInput,
    NominalizationAnalyzer,
    NominalizationCandidate,
    UniversalPartOfSpeech,
    Uuid4ModelRunIdFactory,
    build_hybrid_entity_grounding_preview_record,
    canonical_hybrid_entity_grounding_preview_bytes,
    canonical_hybrid_extraction_preview_bytes,
    canonical_hybrid_reference_preview_bytes,
    evaluate_entity_grounding_eligibility,
    hybrid_extraction_preview_sha256,
    hybrid_reference_preview_sha256,
    load_context_manifest,
    run_hybrid_event_trigger_preview,
    run_hybrid_mention_preview,
    run_hybrid_reference_preview,
)
from kotekomi_application.hybrid_document_references import (
    HybridReferencePreview,
)
from kotekomi_application.hybrid_event_trigger_model_output import (
    binary_semantic_answer_schema_bytes,
    event_head_answer_schema_bytes,
    event_verb_role_answer_schema_bytes,
)
from kotekomi_application.hybrid_event_trigger_preview import (
    EVENT_BINARY_SEMANTIC_SCHEMA_ID,
    EVENT_HEAD_JUDGMENT_SCHEMA_ID,
    EVENT_VERB_ROLE_SCHEMA_ID,
    TRIGGER_RECONCILIATION_POLICY_ID,
    HybridEventTriggerArchive,
    HybridEventTriggerLedger,
)
from kotekomi_application.hybrid_event_triggers import (
    HYBRID_EVENT_TRIGGER_POLICY_ID,
    HybridEventTriggerPreview,
)
from kotekomi_application.hybrid_mention_boundary_adjudication import (
    HYBRID_MENTION_BOUNDARY_ADJUDICATION_POLICY_ID,
    HYBRID_MENTION_BOUNDARY_ADJUDICATION_SCHEMA_ID,
    boundary_candidate_judgment_schema_bytes,
)
from kotekomi_application.hybrid_mention_interpretation import (
    HYBRID_MENTION_BOUNDARY_POLICY_ID,
    HYBRID_MENTION_INTERPRETATION_SCHEMA_ID,
    HYBRID_MENTION_PREVIEW_POLICY_ID,
    HYBRID_MENTION_PROPOSAL_SCHEMA_ID,
    HybridExtractionPreview,
    mention_interpretation_schema_bytes,
    mention_proposal_schema_bytes,
)
from kotekomi_application.hybrid_mention_preview import HybridMentionArchive, HybridMentionLedger
from kotekomi_application.hybrid_reference_preview import (
    HybridReferenceArchive,
    HybridReferenceLedger,
)
from kotekomi_application.mention_proposer import (
    MentionProposalBatch,
    MentionProposalInput,
    MentionProposer,
)
from kotekomi_application.semantic_reference_challenge_model_output import (
    semantic_reference_challenge_schema_bytes,
)
from kotekomi_application.semantic_reference_validation_model_output import (
    semantic_reference_candidate_validation_schema_bytes,
)
from kotekomi_application.semantic_references import (
    SEMANTIC_REFERENCE_POLICY_ID,
    CoreferenceProposerPort,
    CoreferenceTokenizer,
)
from kotekomi_application.source_occurrences import source_occurrences
from kotekomi_domain import (
    AnalysisUnitArtifact,
    ContextManifestArtifact,
    Document,
    DocumentNode,
    DocumentRepresentation,
    DocumentRepresentationBundle,
    ExtractionTask,
    ModelRun,
    ParseQualityReport,
    RepresentationAnalyzability,
    Source,
    SourceType,
    TextView,
    TextViewKind,
    canonical_representation_digest,
)
from kotekomi_pipelines.config import PipelineConfig, load_config
from kotekomi_pipelines.evaluation_contracts import EvaluationPhase
from kotekomi_pipelines.event_trigger_stage_local import (
    TriggerGoldCatalog,
    TriggerStageSegmentEvaluation,
    build_trigger_stage_report,
    evaluate_trigger_segment,
    load_trigger_gold_catalog,
)
from kotekomi_pipelines.front_half_stage_local import (
    FrontHalfCaseEvaluation,
    FrontHalfInput,
    build_front_half_report,
    evaluate_front_half_boundary_contract,
    evaluate_front_half_case,
    load_front_half_inputs,
)
from kotekomi_pipelines.model_runtime import build_model_task_runtime

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SPLIT = REPOSITORY_ROOT / "docs" / "hsq-front-half-split-v1.json"
DEFAULT_TRIGGER_GOLD = REPOSITORY_ROOT / "docs" / "hsq-event-trigger-gold-v1.json"
_FIXED_TIME = datetime(2026, 9, 9, tzinfo=UTC)


class _ExperimentLedger:
    """Narrow ephemeral repository that rejects every accepted-state write."""

    def __init__(
        self,
        source: Source,
        document: Document,
        bundle: DocumentRepresentationBundle,
    ) -> None:
        self.source = source
        self.document = document
        self.bundle = bundle
        self.analysis_units: dict[str, AnalysisUnitArtifact] = {}
        self.context_manifests: dict[str, ContextManifestArtifact] = {}
        self.extraction_tasks: dict[str, ExtractionTask] = {}
        self.model_runs: dict[str, ModelRun] = {}
        self.accepted_ledger_change_count = 0

    def get_source(self, record_id: str) -> Source | None:
        return self.source if record_id == self.source.id else None

    def get_document(self, record_id: str) -> Document | None:
        return self.document if record_id == self.document.id else None

    def get_document_representation_bundle(
        self, record_id: str
    ) -> DocumentRepresentationBundle | None:
        return self.bundle if record_id == self.bundle.representation.id else None

    def save_analysis_unit_artifact(self, record: AnalysisUnitArtifact) -> None:
        self.analysis_units[record.id] = record

    def get_analysis_unit_artifact(self, record_id: str) -> AnalysisUnitArtifact | None:
        return self.analysis_units.get(record_id)

    def save_context_manifest_artifact(self, record: ContextManifestArtifact) -> None:
        self.context_manifests[record.id] = record

    def get_context_manifest_artifact(self, record_id: str) -> ContextManifestArtifact | None:
        return self.context_manifests.get(record_id)

    def commit_context_planning_outcome(
        self,
        *,
        manifest: ContextManifestArtifact,
        child_analysis_units: tuple[AnalysisUnitArtifact, ...],
    ) -> None:
        self.context_manifests[manifest.id] = manifest
        self.analysis_units.update({item.id: item for item in child_analysis_units})

    def save_extraction_task(self, record: ExtractionTask) -> None:
        self.extraction_tasks[record.id] = record

    def save_model_run(self, record: ModelRun) -> None:
        self.model_runs[record.id] = record

    def commit_successful_model_run_and_candidate_batch(
        self, *, model_run: ModelRun, batch: object
    ) -> None:
        del model_run, batch
        self.accepted_ledger_change_count += 1
        raise AssertionError("Stage-local evaluation cannot write ProposedChanges.")

    def to_json(self) -> dict[str, object]:
        return {
            "source": self.source.model_dump(mode="json"),
            "document": self.document.model_dump(mode="json"),
            "bundle": self.bundle.model_dump(mode="json"),
            "analysis_units": [
                item.model_dump(mode="json")
                for item in sorted(self.analysis_units.values(), key=lambda value: value.id)
            ],
            "context_manifests": [
                item.model_dump(mode="json")
                for item in sorted(self.context_manifests.values(), key=lambda value: value.id)
            ],
            "extraction_tasks": [
                item.model_dump(mode="json")
                for item in sorted(self.extraction_tasks.values(), key=lambda value: value.id)
            ],
            "model_runs": [
                item.model_dump(mode="json")
                for item in sorted(self.model_runs.values(), key=lambda value: value.id)
            ],
            "accepted_ledger_change_count": self.accepted_ledger_change_count,
        }

    @classmethod
    def from_json(cls, value: dict[str, object]) -> _ExperimentLedger:
        ledger = cls(
            Source.model_validate_json(_canonical_json(value["source"])),
            Document.model_validate_json(_canonical_json(value["document"])),
            DocumentRepresentationBundle.model_validate_json(_canonical_json(value["bundle"])),
        )
        ledger.analysis_units = {
            item.id: item
            for item in (
                AnalysisUnitArtifact.model_validate_json(_canonical_json(raw))
                for raw in cast(list[object], value["analysis_units"])
            )
        }
        ledger.context_manifests = {
            item.id: item
            for item in (
                ContextManifestArtifact.model_validate_json(_canonical_json(raw))
                for raw in cast(list[object], value["context_manifests"])
            )
        }
        ledger.extraction_tasks = {
            item.id: item
            for item in (
                ExtractionTask.model_validate_json(_canonical_json(raw))
                for raw in cast(list[object], value["extraction_tasks"])
            )
        }
        ledger.model_runs = {
            item.id: item
            for item in (
                ModelRun.model_validate_json(_canonical_json(raw))
                for raw in cast(list[object], value["model_runs"])
            )
        }
        ledger.accepted_ledger_change_count = cast(int, value["accepted_ledger_change_count"])
        return ledger


@dataclass(frozen=True)
class _PreparedRun:
    root: Path
    phase: EvaluationPhase
    inputs: tuple[FrontHalfInput, ...]
    trigger_gold: TriggerGoldCatalog


class _FixtureMentionProposer:
    """Explicit no-candidate proposer for fast runner contract tests."""

    def propose(self, proposal_input: MentionProposalInput) -> MentionProposalBatch:
        del proposal_input
        return MentionProposalBatch(
            proposer_id="hsq-stage-local-fixture:1",
            model_id="hsq-stage-local-fixture",
            model_revision="1",
            configuration=(),
            load_elapsed_milliseconds=0,
            inference_elapsed_milliseconds=0,
            proposals=(),
        )


class _FixtureCoreference:
    tokenizer_id = "hsq-stage-local-fixture-tokenizer"

    def count_tokens(self, rendered_input: bytes) -> int:
        return max(1, len(rendered_input.decode("utf-8").split()))

    def propose(self, request: CoreferenceInput) -> CoreferenceExecution:
        del request
        return CoreferenceExecution(
            model_id="hsq-stage-local-fixture",
            model_revision="1",
            resource_identity="hsq-stage-local-fixture",
            clusters=(),
            elapsed_milliseconds=0,
            raw_output=b'{"clusters":[]}',
        )

    def close(self) -> None:
        return None


class _FixtureLinguisticAnalyzer:
    def analyze(self, request: LinguisticAnalysisInput) -> LinguisticAnalysis:
        occurrences = source_occurrences(request.source_text)
        return LinguisticAnalysis(
            source_text_sha256=hashlib.sha256(request.source_text.encode()).hexdigest(),
            producer_id="fixture",
            model_id="fixture",
            model_version="1",
            resource_identity="f" * 64,
            tokens=tuple(
                LinguisticToken(
                    token_id=f"t{ordinal}",
                    sentence_id="s1",
                    text=item.text,
                    start=item.start,
                    end=item.end,
                    lemma=item.text.casefold(),
                    part_of_speech=UniversalPartOfSpeech.NOUN,
                    dependency_relation="root" if ordinal == 1 else "dep",
                    head_token_id=None if ordinal == 1 else "t1",
                )
                for ordinal, item in enumerate(occurrences, start=1)
            ),
        )


class _FixtureNominalizationAnalyzer:
    def analyze(self, request: NominalizationAnalysisInput) -> NominalizationAnalysis:
        return NominalizationAnalysis(
            source_text_sha256=hashlib.sha256(request.source_text.encode()).hexdigest(),
            producer_id="fixture",
            model_id="fixture",
            model_revision="1",
            resource_identity="f" * 64,
            threshold=0.45,
            candidates=tuple(
                NominalizationCandidate(
                    linguistic_token_id=token.token_id,
                    text=token.text,
                    start=token.start,
                    end=token.end,
                    lexical_candidate=True,
                    positive_logit=1.0,
                    negative_logit=-1.0,
                    nominalization_probability=0.7310585786300049,
                )
                for token in request.linguistic_analysis.tokens
                if token.part_of_speech is UniversalPartOfSpeech.NOUN
            ),
        )


class _CoreferenceRuntime(CoreferenceProposerPort, CoreferenceTokenizer, Protocol):
    pass


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare = subparsers.add_parser("prepare")
    _common_run_arguments(prepare, needs_config=False)
    prepare.add_argument("--upstream-run-root", type=Path)
    mentions = subparsers.add_parser("run-mentions")
    _common_run_arguments(mentions, needs_config=True)
    references = subparsers.add_parser("run-references")
    _common_run_arguments(references, needs_config=True)
    triggers = subparsers.add_parser("run-triggers")
    _common_run_arguments(triggers, needs_config=True)
    finalize = subparsers.add_parser("finalize")
    _common_run_arguments(finalize, needs_config=False)
    compare = subparsers.add_parser("compare")
    compare.add_argument("--development-report", type=Path, required=True)
    compare.add_argument("--validation-report", type=Path, required=True)
    compare.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "prepare":
        return _prepare(args)
    if args.command == "run-mentions":
        return _run_mentions(args)
    if args.command == "run-references":
        return _run_references(args)
    if args.command == "run-triggers":
        return _run_triggers(args)
    if args.command == "finalize":
        return _finalize(args)
    return _compare(args)


def _common_run_arguments(parser: argparse.ArgumentParser, *, needs_config: bool) -> None:
    parser.add_argument("--phase", choices=("development", "validation"), required=True)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--split", type=Path, default=DEFAULT_SPLIT)
    parser.add_argument("--trigger-gold", type=Path, default=DEFAULT_TRIGGER_GOLD)
    parser.add_argument(
        "--item-id",
        action="append",
        default=[],
        help="Prepare a diagnostic subset; later commands reuse the prepared item IDs.",
    )
    if needs_config:
        parser.add_argument("--config", type=Path, required=True)


def _prepare(args: argparse.Namespace) -> int:
    run_root = args.run_root.resolve()
    if run_root.exists() and any(run_root.iterdir()):
        raise ValueError("Stage-local prepare requires an absent or empty run root.")
    run_root.mkdir(parents=True, exist_ok=True)
    _, inputs = load_front_half_inputs(args.split.resolve(), repository_root=REPOSITORY_ROOT)
    trigger_gold_path = args.trigger_gold.resolve()
    trigger_gold = load_trigger_gold_catalog(
        trigger_gold_path,
        repository_root=REPOSITORY_ROOT,
        inputs=inputs,
        require_approved=args.phase == "validation",
    )
    selected = _select_run_inputs(inputs, phase=args.phase, item_ids=tuple(args.item_id))
    _write_jsonl(run_root / "inputs.jsonl", [item.model_dump(mode="json") for item in selected])
    upstream_evidence = (
        _seed_upstream_evidence(
            run_root=run_root,
            upstream_root=args.upstream_run_root.resolve(),
            phase=cast(EvaluationPhase, args.phase),
            inputs=selected,
        )
        if args.upstream_run_root is not None
        else None
    )
    metadata = {
        "schema_version": "hsq_stage_local_run_v2",
        "phase": args.phase,
        "split_path": _relative_or_absolute(args.split.resolve()),
        "split_sha256": _sha(args.split.read_bytes()),
        "trigger_gold_path": _relative_or_absolute(trigger_gold_path),
        "trigger_gold_sha256": _sha(trigger_gold_path.read_bytes()),
        "trigger_gold_review_status": trigger_gold.review_status,
        "item_count": len(selected),
        "item_ids": [item.item.item_id for item in selected],
        "unique_source_segment_count": len({item.source_text_sha256 for item in selected}),
        "experiment": _experiment_contract(),
        "upstream_evidence": upstream_evidence,
        "status": "references_complete" if upstream_evidence is not None else "prepared",
    }
    _write_json(run_root / "run.json", metadata)
    print(json.dumps(metadata, sort_keys=True))
    return 0


def _seed_upstream_evidence(
    *,
    run_root: Path,
    upstream_root: Path,
    phase: EvaluationPhase,
    inputs: tuple[FrontHalfInput, ...],
) -> dict[str, object]:
    """Validate and rehydrate immutable v10 mention/reference evidence."""
    authorized = _validate_evidence_manifest(
        upstream_root,
        require_marker=phase == "validation",
    )
    if "inputs.jsonl" not in authorized:
        raise ValueError("Upstream stage evidence does not authorize its inputs.")
    upstream_inputs = tuple(
        FrontHalfInput.model_validate_json(line)
        for line in (upstream_root / "inputs.jsonl").read_text(encoding="utf-8").splitlines()
        if line
    )
    upstream_by_id = {item.item.item_id: item for item in upstream_inputs}
    if len(upstream_by_id) != len(upstream_inputs):
        raise ValueError("Upstream stage evidence repeats a Gold item.")
    try:
        selected_upstream = tuple(upstream_by_id[item.item.item_id] for item in inputs)
    except KeyError as error:
        raise ValueError("Upstream stage evidence is missing a selected Gold item.") from error
    if selected_upstream != inputs:
        raise ValueError("Upstream stage evidence does not match the selected Gold inputs.")

    archive = LocalArchiveStore(run_root / "archive")
    archive.initialize()
    copied: list[dict[str, object]] = []
    context_rehydrations: list[dict[str, object]] = []
    synthesized_reference_digests: list[str] = []
    for stage_input in _unique_segment_inputs(inputs):
        digest = stage_input.source_text_sha256
        mention_relative = f"mentions/{digest}.json"
        reference_relative = f"references/{digest}.json"
        if mention_relative not in authorized or reference_relative not in authorized:
            raise ValueError("Upstream stage evidence lacks one selected SourceSegment.")
        mention_source = upstream_root / mention_relative
        reference_source = upstream_root / reference_relative
        mention_record = _read_json(mention_source)
        reference_record = _read_json(reference_source)
        _validate_upstream_stage_record(mention_record, stage_input, "mentions")
        _validate_upstream_stage_record(reference_record, stage_input, "references")

        ledger = _synthetic_ledger(stage_input)
        mention_value = mention_record.get("preview")
        if not isinstance(mention_value, dict):
            raise ValueError("Upstream mention evidence lacks its typed Preview.")
        mention = HybridExtractionPreview.model_validate_json(
            _canonical_json(cast(dict[str, object], mention_value))
        )
        mention_payload = canonical_hybrid_extraction_preview_bytes(mention)
        archive.put_hybrid_extraction_preview(
            mention,
            mention_payload,
            _sha(mention_payload),
        )
        context_rehydrations.append(
            _rehydrate_pinned_context_manifest(
                upstream_root=upstream_root,
                source_text_sha256=digest,
                mention=mention,
                ledger=ledger,
            )
        )

        reference_value = reference_record.get("preview")
        downstream_reference_record: dict[str, object]
        if isinstance(reference_value, dict):
            references = HybridReferencePreview.model_validate_json(
                _canonical_json(cast(dict[str, object], reference_value))
            )
            reference_payload = canonical_hybrid_reference_preview_bytes(references)
            archive.put_hybrid_reference_preview(
                references,
                reference_payload,
                _sha(reference_payload),
            )
            downstream_reference_record = reference_record
            reference_action = "copied"
        elif reference_value is None:
            result = run_hybrid_reference_preview(
                command=HybridReferencePreviewCommand(mention.id),
                ledger=cast(HybridReferenceLedger, ledger),
                archive=cast(HybridReferenceArchive, archive),
            )
            downstream_reference_record = {
                "schema_version": "hsq_stage_local_execution_v1",
                "stage": "references",
                "source_text_sha256": digest,
                "status": "deterministic_parent_completion",
                "preview": result.preview.model_dump(mode="json"),
                "model_executions": cast(list[object], []),
                "upstream_record_sha256": _sha(reference_source.read_bytes()),
            }
            synthesized_reference_digests.append(digest)
            reference_action = "deterministic_parent_completion"
        else:
            raise ValueError("Upstream reference Preview has an invalid shape.")

        _write_json(run_root / "state" / f"{digest}.json", ledger.to_json())
        _write_json(run_root / mention_relative, mention_record)
        _write_json(run_root / reference_relative, downstream_reference_record)
        copied.extend(
            (
                {
                    "path": mention_relative,
                    "upstream_sha256": _sha(mention_source.read_bytes()),
                    "local_sha256": _sha((run_root / mention_relative).read_bytes()),
                    "action": "copied",
                },
                {
                    "path": reference_relative,
                    "upstream_sha256": _sha(reference_source.read_bytes()),
                    "local_sha256": _sha((run_root / reference_relative).read_bytes()),
                    "action": reference_action,
                },
            )
        )
    envelope: dict[str, object] = {
        "schema_version": "hsq_stage_local_upstream_evidence_v1",
        "upstream_run_root": str(upstream_root),
        "upstream_manifest_sha256": _sha((upstream_root / "manifest.json").read_bytes()),
        "phase": phase,
        "source_segment_count": len(_unique_segment_inputs(inputs)),
        "synthesized_reference_source_text_sha256s": sorted(synthesized_reference_digests),
        "context_manifest_rehydrations": context_rehydrations,
        "records": copied,
    }
    _write_json(run_root / "upstream-evidence.json", envelope)
    return envelope


def _rehydrate_pinned_context_manifest(
    *,
    upstream_root: Path,
    source_text_sha256: str,
    mention: HybridExtractionPreview,
    ledger: _ExperimentLedger,
) -> dict[str, object]:
    """Load only the context artifact whose content address is pinned by the Preview."""
    state_path = upstream_root / "state" / f"{source_text_sha256}.json"
    state = _read_json(state_path)
    if state.get("accepted_ledger_change_count") != 0:
        raise ValueError("Upstream context state contains an accepted Ledger write.")
    raw_artifacts = state.get("context_manifests")
    if not isinstance(raw_artifacts, list):
        raise ValueError("Upstream context state lacks ContextManifest artifacts.")
    matching_values: list[dict[str, object]] = []
    for value in cast(list[object], raw_artifacts):
        if not isinstance(value, dict):
            continue
        artifact_value = cast(dict[str, object], value)
        if artifact_value.get("id") == mention.context_manifest_id:
            matching_values.append(artifact_value)
    matching = tuple(matching_values)
    if len(matching) != 1:
        raise ValueError("Upstream context state lacks one uniquely pinned ContextManifest.")
    artifact_payload = _canonical_json(matching[0])
    artifact = ContextManifestArtifact.model_validate_json(artifact_payload)
    ledger.save_context_manifest_artifact(artifact)
    manifest = load_context_manifest(
        artifact.id,
        ledger,
        verified_bundle=ledger.bundle,
    )
    if (
        manifest.id != mention.context_manifest_id
        or manifest.representation_id != mention.representation_id
    ):
        raise ValueError("Upstream ContextManifest does not close MentionPreview lineage.")
    return {
        "source_text_sha256": source_text_sha256,
        "state_path": state_path.relative_to(upstream_root).as_posix(),
        "state_sha256": _sha(state_path.read_bytes()),
        "context_manifest_id": artifact.id,
        "context_manifest_artifact_sha256": _sha(artifact_payload),
        "validation": "content_addressed_lineage_closed",
    }


def _validate_upstream_stage_record(
    record: dict[str, object],
    stage_input: FrontHalfInput,
    stage: str,
) -> None:
    if (
        record.get("schema_version") != "hsq_stage_local_execution_v1"
        or record.get("stage") != stage
        or record.get("source_text_sha256") != stage_input.source_text_sha256
    ):
        raise ValueError(f"Upstream {stage} evidence does not match its SourceSegment.")
    accepted_count = record.get("accepted_ledger_change_count", 0)
    if accepted_count != 0:
        raise ValueError(f"Upstream {stage} evidence contains an accepted Ledger write.")


def _run_mentions(args: argparse.Namespace) -> int:
    prepared = _load_prepared(args)
    _require_not_finalized(prepared)
    _require_run_status(prepared.root, "prepared")
    config = _config(args.config)
    archive = LocalArchiveStore(prepared.root / "archive")
    archive.initialize()
    proposer: MentionProposer = (
        _FixtureMentionProposer()
        if config.model_execution.adapter == "fixture"
        else GlinerMentionProposer(model_directory=gliner_model_path(config.model_resource_root))
    )
    runtime = build_model_task_runtime(config.model_execution)
    profile = _profile(config)
    prompts = _prompts()
    unique_inputs = _unique_segment_inputs(prepared.inputs)
    try:
        for ordinal, stage_input in enumerate(unique_inputs, start=1):
            target = prepared.root / "mentions" / f"{stage_input.source_text_sha256}.json"
            if target.exists():
                print(f"Mention segment {ordinal}/{len(unique_inputs)}: reused")
                continue
            ledger = _synthetic_ledger(stage_input)
            result = run_hybrid_mention_preview(
                command=HybridMentionPreviewCommand(
                    representation_id=ledger.bundle.representation.id,
                    paragraph_node_id=_paragraph_node(ledger.bundle).id,
                    model_profile=profile,
                    generation_parameters=_generation(config),
                ),
                ledger=cast(HybridMentionLedger, ledger),
                archive=cast(HybridMentionArchive, archive),
                proposer=proposer,
                model_runtime=runtime,
                model_run_id_factory=Uuid4ModelRunIdFactory(),
                tokenizer=runtime,
                proposal_prompt_bytes=prompts["proposal"],
                boundary_adjudication_prompt_bytes=prompts["boundary_adjudication"],
                interpretation_prompt_bytes=prompts["interpretation"],
                ontology_card_bytes=prompts["ontology"],
            )
            if ledger.accepted_ledger_change_count:
                raise AssertionError("Mention evaluation changed accepted Ledger state.")
            _write_json(
                prepared.root / "state" / f"{stage_input.source_text_sha256}.json",
                ledger.to_json(),
            )
            _write_json(
                target,
                _stage_record(
                    stage_input=stage_input,
                    preview=result.preview.model_dump(mode="json"),
                    ledger=ledger,
                    archive=archive,
                    stage="mentions",
                ),
            )
            print(
                f"Mention segment {ordinal}/{len(unique_inputs)}: "
                f"{result.preview.terminal_status.value}"
            )
    finally:
        _close_runtime(runtime)
    _update_run_status(prepared.root, "mentions_complete")
    return 0


def _run_references(args: argparse.Namespace) -> int:
    prepared = _load_prepared(args)
    _require_not_finalized(prepared)
    _require_run_status(prepared.root, "mentions_complete")
    config = _config(args.config)
    archive = LocalArchiveStore(prepared.root / "archive")
    archive.initialize()
    runtime = build_model_task_runtime(config.model_execution)
    root = config.model_resource_root
    coreference: _CoreferenceRuntime = (
        _FixtureCoreference()
        if config.model_execution.adapter == "fixture"
        else FCorefAdapter(
            FCorefConfig(
                python_executable=fcoref_python_path(root),
                worker_script=(REPOSITORY_ROOT / "scripts" / "fcoref_worker.py").resolve(),
                model_directory=fcoref_model_path(root).resolve(),
                resource_identity=fcoref_expected_resource_identity(),
            )
        )
    )
    prompts = _prompts()
    unique_inputs = _unique_segment_inputs(prepared.inputs)
    try:
        for ordinal, stage_input in enumerate(unique_inputs, start=1):
            target = prepared.root / "references" / f"{stage_input.source_text_sha256}.json"
            if target.exists():
                print(f"Reference segment {ordinal}/{len(unique_inputs)}: reused")
                continue
            related = tuple(
                item
                for item in prepared.inputs
                if item.source_text_sha256 == stage_input.source_text_sha256
            )
            ledger = _ExperimentLedger.from_json(
                _read_json(prepared.root / "state" / f"{stage_input.source_text_sha256}.json")
            )
            mention_record = _read_json(
                prepared.root / "mentions" / f"{stage_input.source_text_sha256}.json"
            )
            mention = HybridExtractionPreview.model_validate_json(
                _canonical_json(mention_record["preview"])
            )
            before_ids = set(ledger.model_runs)
            has_expected_reference = any(item.item.expected_references for item in related)
            if mention.terminal_status is HybridPreviewStatus.BLOCKED or not has_expected_reference:
                result = run_hybrid_reference_preview(
                    command=HybridReferencePreviewCommand(mention.id),
                    ledger=cast(HybridReferenceLedger, ledger),
                    archive=cast(HybridReferenceArchive, archive),
                )
                reference_preview = result.preview
                status = (
                    "parent_blocked_passthrough"
                    if mention.terminal_status is HybridPreviewStatus.BLOCKED
                    else "not_applicable"
                )
            else:
                result = run_hybrid_reference_preview(
                    command=HybridReferencePreviewCommand(
                        mention.id,
                        model_profile=_profile(config),
                        generation_parameters=_generation(config),
                    ),
                    ledger=cast(HybridReferenceLedger, ledger),
                    archive=cast(HybridReferenceArchive, archive),
                    coreference_proposer=coreference,
                    coreference_tokenizer=coreference,
                    model_runtime=runtime,
                    model_run_id_factory=Uuid4ModelRunIdFactory(),
                    challenge_prompt_bytes=prompts["reference_selection"],
                    validation_prompt_bytes=prompts["reference_validation"],
                )
                reference_preview = result.preview
                status = "complete"
            if ledger.accepted_ledger_change_count:
                raise AssertionError("Reference evaluation changed accepted Ledger state.")
            _write_json(
                prepared.root / "state" / f"{stage_input.source_text_sha256}.json",
                ledger.to_json(),
            )
            _write_json(
                target,
                {
                    "schema_version": "hsq_stage_local_execution_v1",
                    "stage": "references",
                    "source_text_sha256": stage_input.source_text_sha256,
                    "status": status,
                    "preview": reference_preview.model_dump(mode="json"),
                    "model_executions": _model_execution_records(
                        ledger, archive, set(ledger.model_runs) - before_ids
                    ),
                },
            )
            print(f"Reference segment {ordinal}/{len(unique_inputs)}: {status}")
    finally:
        close_coreference = getattr(coreference, "close", None)
        if callable(close_coreference):
            close_coreference()
        _close_runtime(runtime)
    _update_run_status(prepared.root, "references_complete")
    return 0


def _run_triggers(args: argparse.Namespace) -> int:
    prepared = _load_prepared(args)
    _require_not_finalized(prepared)
    _require_run_status(prepared.root, "references_complete")
    config = _config(args.config)
    archive = LocalArchiveStore(prepared.root / "archive")
    archive.initialize()
    runtime = build_model_task_runtime(config.model_execution)
    linguistic_analyzer: LinguisticAnalyzer = (
        _FixtureLinguisticAnalyzer()
        if config.model_execution.adapter == "fixture"
        else StanzaLinguisticAnalyzer(
            model_directory=stanza_model_path(config.model_resource_root),
            resource_identity=stanza_expected_resource_identity(),
        )
    )
    nominalization_analyzer: NominalizationAnalyzer = (
        _FixtureNominalizationAnalyzer()
        if config.model_execution.adapter == "fixture"
        else QANomNominalizationAnalyzer(
            model_directory=qanom_model_path(config.model_resource_root),
            lexical_resource_directory=qanom_lexical_resource_path(config.model_resource_root),
            resource_identity=qanom_expected_resource_identity(),
        )
    )
    prompts = _prompts()
    unique_inputs = _unique_segment_inputs(prepared.inputs)
    try:
        for ordinal, stage_input in enumerate(unique_inputs, start=1):
            target = prepared.root / "triggers" / f"{stage_input.source_text_sha256}.json"
            if target.exists():
                print(f"Trigger segment {ordinal}/{len(unique_inputs)}: reused")
                continue
            ledger = _ExperimentLedger.from_json(
                _read_json(prepared.root / "state" / f"{stage_input.source_text_sha256}.json")
            )
            mention_record = _read_json(
                prepared.root / "mentions" / f"{stage_input.source_text_sha256}.json"
            )
            reference_record = _read_json(
                prepared.root / "references" / f"{stage_input.source_text_sha256}.json"
            )
            mention = HybridExtractionPreview.model_validate_json(
                _canonical_json(mention_record["preview"])
            )
            reference_value = reference_record.get("preview")
            if not isinstance(reference_value, dict):
                _write_json(
                    target,
                    {
                        "schema_version": "hsq_stage_local_execution_v1",
                        "stage": "triggers",
                        "source_text_sha256": stage_input.source_text_sha256,
                        "status": "parent_blocked",
                        "preview": None,
                        "model_executions": [],
                        "accepted_ledger_change_count": ledger.accepted_ledger_change_count,
                    },
                )
                print(f"Trigger segment {ordinal}/{len(unique_inputs)}: parent blocked")
                continue
            references = HybridReferencePreview.model_validate_json(
                _canonical_json(cast(dict[str, object], reference_value))
            )
            eligibility = evaluate_entity_grounding_eligibility(mention, references)
            grounding_diagnostics = (
                ("stage_local_entity_linking_not_run",)
                if any(item.status.value == "eligible" for item in eligibility)
                else ()
            )
            grounding = build_hybrid_entity_grounding_preview_record(
                parent_preview_id=references.id,
                parent_preview_sha256=hybrid_reference_preview_sha256(references),
                mention_preview_id=mention.id,
                mention_preview_sha256=hybrid_extraction_preview_sha256(mention),
                representation_id=mention.representation_id,
                eligibility=eligibility,
                link_evidence=(),
                extraction_task_ids=(),
                model_run_ids=(),
                traces=(),
                terminal_status=(
                    HybridEntityGroundingStatus.PARTIAL
                    if grounding_diagnostics
                    else HybridEntityGroundingStatus.COMPLETE
                ),
                diagnostics=grounding_diagnostics,
            )
            grounding_payload = canonical_hybrid_entity_grounding_preview_bytes(grounding)
            archive.put_hybrid_entity_grounding_preview(
                grounding,
                grounding_payload,
                _sha(grounding_payload),
            )
            before_ids = set(ledger.model_runs)
            result = run_hybrid_event_trigger_preview(
                command=HybridEventTriggerCommand(
                    grounding.id,
                    _profile(config),
                    _generation(config),
                ),
                ledger=cast(HybridEventTriggerLedger, ledger),
                archive=cast(HybridEventTriggerArchive, archive),
                model_runtime=runtime,
                model_run_id_factory=Uuid4ModelRunIdFactory(),
                tokenizer=runtime,
                prompts=HybridEventTriggerPrompts(
                    verb_role=prompts["event_verb_role"],
                    verb_similarity=prompts["event_verb_similarity"],
                    noun_inventory=prompts["event_noun_inventory"],
                    noun_dependent_kind=prompts["event_noun_dependent_kind"],
                    noun_media_artifact=prompts["event_noun_media_artifact"],
                    noun_governor_distinct=prompts["event_noun_governor_distinct"],
                    noun_reaction=prompts["event_noun_reaction"],
                    noun_standing=prompts["event_noun_standing"],
                ),
                linguistic_analyzer=linguistic_analyzer,
                nominalization_analyzer=nominalization_analyzer,
            )
            if ledger.accepted_ledger_change_count:
                raise AssertionError("Trigger evaluation changed accepted Ledger state.")
            _write_json(
                prepared.root / "state" / f"{stage_input.source_text_sha256}.json",
                ledger.to_json(),
            )
            _write_json(
                target,
                {
                    **_stage_record(
                        stage_input=stage_input,
                        preview=result.preview.model_dump(mode="json"),
                        ledger=ledger,
                        archive=archive,
                        stage="triggers",
                        model_run_ids=set(ledger.model_runs) - before_ids,
                    ),
                    "status": result.preview.terminal_status.value,
                },
            )
            print(
                f"Trigger segment {ordinal}/{len(unique_inputs)}: "
                f"{result.preview.terminal_status.value}"
            )
    finally:
        _close_runtime(runtime)
    _update_run_status(prepared.root, "triggers_complete")
    return 0


def _finalize(args: argparse.Namespace) -> int:
    prepared = _load_prepared(args)
    _require_not_finalized(prepared)
    _require_run_status(prepared.root, "triggers_complete")
    evaluations: list[FrontHalfCaseEvaluation] = []
    elapsed: dict[str, int] = {}
    alias_opportunity_items = 0
    alias_opportunity_segments: set[str] = set()
    mention_by_source_digest: dict[str, HybridExtractionPreview] = {}
    for stage_input in prepared.inputs:
        mention_record = _read_json(
            prepared.root / "mentions" / f"{stage_input.source_text_sha256}.json"
        )
        reference_record = _read_json(
            prepared.root / "references" / f"{stage_input.source_text_sha256}.json"
        )
        mention = HybridExtractionPreview.model_validate_json(
            _canonical_json(mention_record["preview"])
        )
        mention_by_source_digest[stage_input.source_text_sha256] = mention
        reference_value = reference_record.get("preview")
        references = (
            HybridReferencePreview.model_validate_json(_canonical_json(reference_value))
            if reference_value is not None
            else None
        )
        evaluation = evaluate_front_half_case(stage_input, mention, references)
        evaluations.append(evaluation)
        if evaluation.first_failed_stage == "mention_proposal":
            alias_opportunity_items += 1
            alias_opportunity_segments.add(stage_input.source_text_sha256)
    avoidable_interpretations = 0
    for stage_input in _unique_segment_inputs(prepared.inputs):
        mention_record = _read_json(
            prepared.root / "mentions" / f"{stage_input.source_text_sha256}.json"
        )
        mention = HybridExtractionPreview.model_validate_json(
            _canonical_json(mention_record["preview"])
        )
        related_inputs = tuple(
            item
            for item in prepared.inputs
            if item.source_text_sha256 == stage_input.source_text_sha256
        )
        required_candidate_ids = {
            candidate.id
            for candidate in mention.candidates
            if candidate.source_text_sha256 == stage_input.source_text_sha256
            and any(_candidate_is_required(candidate.text, item) for item in related_inputs)
        }
        avoidable_interpretations += sum(
            item.candidate_id not in required_candidate_ids for item in mention.interpretations
        )
    for path in sorted((prepared.root / "mentions").glob("*.json")) + sorted(
        (prepared.root / "references").glob("*.json")
    ):
        executions = cast(list[dict[str, object]], _read_json(path).get("model_executions", []))
        for execution in executions:
            producer = str(execution["producer"])
            elapsed[producer] = elapsed.get(producer, 0) + _required_int(
                execution["elapsed_milliseconds"], "model elapsed milliseconds"
            )
    for path in sorted((prepared.root / "references").glob("*.json")):
        preview = _read_json(path).get("preview")
        if isinstance(preview, dict):
            preview_object = cast(dict[str, object], preview)
            observations = cast(
                list[dict[str, object]],
                preview_object.get("coreference_observations", []),
            )
            for observation in observations:
                producer = str(observation["model_id"])
                elapsed[producer] = elapsed.get(producer, 0) + _required_int(
                    observation["elapsed_milliseconds"],
                    "specialist elapsed milliseconds",
                )
    report = build_front_half_report(
        phase=prepared.phase,
        evaluations=tuple(evaluations),
        producer_elapsed_milliseconds=elapsed,
        boundary_contract=evaluate_front_half_boundary_contract(
            tuple(mention_by_source_digest[key] for key in sorted(mention_by_source_digest))
        ),
        optional_experiment_measurements={
            "source_alias_rescue_opportunity_item_count": alias_opportunity_items,
            "source_alias_rescue_opportunity_segment_count": len(alias_opportunity_segments),
            "selective_interpretation_avoidable_call_count": avoidable_interpretations,
        },
    )
    payload = report.model_dump(mode="json")
    gold_by_digest = {
        item.source_text_sha256: item
        for item in prepared.trigger_gold.segments
        if item.phase == prepared.phase
    }
    trigger_evaluations: list[TriggerStageSegmentEvaluation] = []
    trigger_model_execution_count = 0
    trigger_model_elapsed = 0
    for stage_input in _unique_segment_inputs(prepared.inputs):
        trigger_record = _read_json(
            prepared.root / "triggers" / f"{stage_input.source_text_sha256}.json"
        )
        preview_value = trigger_record.get("preview")
        if not isinstance(preview_value, dict):
            raise ValueError("Trigger stage cannot finalize a missing parent result.")
        trigger_preview = HybridEventTriggerPreview.model_validate_json(
            _canonical_json(cast(dict[str, object], preview_value))
        )
        trigger_evaluations.append(
            evaluate_trigger_segment(
                gold_by_digest[stage_input.source_text_sha256],
                trigger_preview,
            )
        )
        executions = cast(list[dict[str, object]], trigger_record.get("model_executions", []))
        trigger_model_execution_count += len(executions)
        trigger_model_elapsed += sum(
            _required_int(item["elapsed_milliseconds"], "trigger elapsed milliseconds")
            for item in executions
        )
    trigger_report = build_trigger_stage_report(
        phase=prepared.phase,
        evaluations=tuple(trigger_evaluations),
        model_execution_count=trigger_model_execution_count,
        model_elapsed_milliseconds=trigger_model_elapsed,
    )
    trigger_payload = trigger_report.model_dump(mode="json")
    report_path = prepared.root / "report.json"
    _write_json(report_path, payload)
    trigger_report_path = prepared.root / "trigger-report.json"
    _write_json(trigger_report_path, trigger_payload)
    _write_review(prepared.root / "review.md", prepared.inputs, payload)
    _write_trigger_review(
        prepared.root / "trigger-review.md",
        prepared.trigger_gold,
        trigger_payload,
    )
    evidence_paths = [
        prepared.root / "inputs.jsonl",
        report_path,
        trigger_report_path,
        prepared.root / "review.md",
        prepared.root / "trigger-review.md",
        *sorted((prepared.root / "mentions").glob("*.json")),
        *sorted((prepared.root / "references").glob("*.json")),
        *sorted((prepared.root / "triggers").glob("*.json")),
    ]
    upstream_evidence_path = prepared.root / "upstream-evidence.json"
    if upstream_evidence_path.is_file():
        evidence_paths.append(upstream_evidence_path)
    manifest = {
        "schema_version": "hsq_stage_local_manifest_v1",
        "phase": prepared.phase,
        "files": [
            {
                "path": path.relative_to(prepared.root).as_posix(),
                "sha256": _sha(path.read_bytes()),
            }
            for path in evidence_paths
        ],
    }
    _write_json(prepared.root / "manifest.json", manifest)
    if prepared.phase == "validation":
        (prepared.root / "FINALIZED").write_text(_sha(_canonical_json(manifest)), encoding="utf-8")
    _update_run_status(prepared.root, "finalized")
    print(
        json.dumps(
            {
                "phase": prepared.phase,
                "passed_count": payload["passed_count"],
                "item_count": payload["item_count"],
                "first_failed_stage_counts": payload["first_failed_stage_counts"],
                "report": str(report_path),
                "trigger_report": str(trigger_report_path),
                "trigger_passed": trigger_payload["passed"],
            },
            sort_keys=True,
        )
    )
    return 0


def _compare(args: argparse.Namespace) -> int:
    _validate_evidence_manifest(args.development_report.resolve().parent)
    _validate_evidence_manifest(args.validation_report.resolve().parent, require_marker=True)
    development = _read_json(args.development_report)
    validation = _read_json(args.validation_report)
    development_triggers = _read_json(
        args.development_report.resolve().parent / "trigger-report.json"
    )
    validation_triggers = _read_json(
        args.validation_report.resolve().parent / "trigger-report.json"
    )
    result = {
        "schema_version": "hsq_stage_local_comparison_v1",
        "development": _comparison_summary(development),
        "validation": _comparison_summary(validation),
        "event_triggers": {
            "development": _trigger_comparison_summary(development_triggers),
            "validation": _trigger_comparison_summary(validation_triggers),
        },
        "quality_regression_gate": "manual_baseline_comparison_required",
        "production_adoption": {
            "source_alias_rescue": "not_activated",
            "selective_interpretation": "not_activated",
        },
    }
    _write_json(args.output.resolve(), result)
    print(json.dumps(result, sort_keys=True))
    return 0


def _load_prepared(args: argparse.Namespace) -> _PreparedRun:
    root = args.run_root.resolve()
    if (root / "FINALIZED").exists():
        _validate_evidence_manifest(root, require_marker=True)
    metadata = _read_json(root / "run.json")
    if metadata.get("phase") != args.phase:
        raise ValueError("Stage-local run phase does not match its prepared metadata.")
    selected_split = args.split.resolve()
    if metadata.get("split_path") != _relative_or_absolute(selected_split):
        raise ValueError("Stage-local run split path changed after preparation.")
    if metadata.get("split_sha256") != _sha(selected_split.read_bytes()):
        raise ValueError("Stage-local run split bytes changed after preparation.")
    trigger_gold_path = args.trigger_gold.resolve()
    if metadata.get("trigger_gold_path") != _relative_or_absolute(trigger_gold_path):
        raise ValueError("Stage-local Trigger Gold path changed after preparation.")
    if metadata.get("trigger_gold_sha256") != _sha(trigger_gold_path.read_bytes()):
        raise ValueError("Stage-local Trigger Gold bytes changed after preparation.")
    if metadata.get("experiment") != _experiment_contract():
        raise ValueError("Stage-local prompt, schema, or policy changed after preparation.")
    inputs = tuple(
        FrontHalfInput.model_validate_json(line)
        for line in (root / "inputs.jsonl").read_text(encoding="utf-8").splitlines()
        if line
    )
    _, current_inputs = load_front_half_inputs(
        selected_split,
        repository_root=REPOSITORY_ROOT,
    )
    trigger_gold = load_trigger_gold_catalog(
        trigger_gold_path,
        repository_root=REPOSITORY_ROOT,
        inputs=current_inputs,
        require_approved=args.phase == "validation",
    )
    raw_item_ids = metadata.get("item_ids")
    if not isinstance(raw_item_ids, list):
        raise ValueError("Stage-local run metadata does not contain valid item IDs.")
    item_id_values = cast(list[object], raw_item_ids)
    if not all(isinstance(item, str) for item in item_id_values):
        raise ValueError("Stage-local run metadata does not contain valid item IDs.")
    item_ids = tuple(cast(list[str], item_id_values))
    if args.item_id and tuple(args.item_id) != item_ids:
        raise ValueError("Stage-local command item IDs differ from the prepared run.")
    expected_inputs = _select_run_inputs(
        current_inputs,
        phase=args.phase,
        item_ids=item_ids,
    )
    if inputs != expected_inputs:
        raise ValueError("Stage-local prepared inputs changed or no longer match the split.")
    if not inputs or any(item.phase != args.phase for item in inputs):
        raise ValueError("Stage-local prepared inputs are incomplete.")
    phase = cast(EvaluationPhase, args.phase)
    return _PreparedRun(root, phase, inputs, trigger_gold)


def _require_not_finalized(prepared: _PreparedRun) -> None:
    if (prepared.root / "FINALIZED").exists():
        raise ValueError("A finalized validation run is immutable.")


def _validate_evidence_manifest(
    root: Path,
    *,
    require_marker: bool = False,
) -> set[str]:
    manifest_path = root / "manifest.json"
    manifest = _read_json(manifest_path)
    if manifest.get("schema_version") != "hsq_stage_local_manifest_v1":
        raise ValueError("Stage-local evidence manifest schema is unknown.")
    raw_files = manifest.get("files")
    if not isinstance(raw_files, list) or not raw_files:
        raise ValueError("Stage-local evidence manifest has no files.")
    files = cast(list[object], raw_files)
    seen: set[str] = set()
    for value in files:
        if not isinstance(value, dict):
            raise ValueError("Stage-local evidence manifest entry is invalid.")
        entry = cast(dict[str, object], value)
        relative = entry.get("path")
        digest = entry.get("sha256")
        if (
            not isinstance(relative, str)
            or not relative
            or relative in seen
            or Path(relative).is_absolute()
            or ".." in Path(relative).parts
            or not isinstance(digest, str)
        ):
            raise ValueError("Stage-local evidence manifest entry is unsafe or duplicated.")
        seen.add(relative)
        evidence_path = root / relative
        if not evidence_path.is_file() or _sha(evidence_path.read_bytes()) != digest:
            raise ValueError(f"Stage-local evidence changed after finalization: {relative}")
    marker = root / "FINALIZED"
    if require_marker:
        expected_marker = _sha(manifest_path.read_bytes())
        if not marker.is_file() or marker.read_text(encoding="utf-8") != expected_marker:
            raise ValueError("Stage-local validation finalization marker is missing or invalid.")
    return seen


def _require_run_status(root: Path, expected: str) -> None:
    observed = _read_json(root / "run.json").get("status")
    if observed != expected:
        raise ValueError(f"Stage-local run requires status {expected}; found {observed}.")


def _update_run_status(root: Path, status: str) -> None:
    metadata = _read_json(root / "run.json")
    metadata["status"] = status
    _write_json(root / "run.json", metadata)


def _unique_segment_inputs(inputs: tuple[FrontHalfInput, ...]) -> tuple[FrontHalfInput, ...]:
    by_sha: dict[str, FrontHalfInput] = {}
    for item in inputs:
        existing = by_sha.setdefault(item.source_text_sha256, item)
        if existing.source_text != item.source_text:
            raise ValueError("One SourceSegment SHA-256 identifies conflicting text.")
    return tuple(by_sha[key] for key in sorted(by_sha))


def _select_run_inputs(
    inputs: tuple[FrontHalfInput, ...],
    *,
    phase: EvaluationPhase,
    item_ids: tuple[str, ...],
) -> tuple[FrontHalfInput, ...]:
    phase_inputs = tuple(item for item in inputs if item.phase == phase)
    if not item_ids:
        return phase_inputs
    if len(set(item_ids)) != len(item_ids):
        raise ValueError("Stage-local diagnostic item IDs must be distinct.")
    by_id = {item.item.item_id: item for item in phase_inputs}
    unknown = set(item_ids) - set(by_id)
    if unknown:
        raise ValueError(
            "Stage-local diagnostic items are absent from the selected phase: "
            + ", ".join(sorted(unknown))
        )
    return tuple(by_id[item_id] for item_id in item_ids)


def _candidate_is_required(candidate_text: str, stage_input: FrontHalfInput) -> bool:
    candidate = _normalized_literal(candidate_text)
    focus_literals = {_normalized_literal(stage_input.focus_entity_name)}
    if stage_input.focus_record_type == "Actor":
        focus_literals.add(
            _normalized_literal(stage_input.focus_entity_name.rsplit(" ", maxsplit=1)[-1])
        )
    reference_literals = {
        _normalized_literal(item.reference_text) for item in stage_input.item.expected_references
    }
    return candidate in focus_literals | reference_literals


def _normalized_literal(value: str) -> str:
    normalized = " ".join(value.casefold().split())
    if normalized.endswith(("'s", "’s")):
        normalized = normalized[:-2]
    return normalized.removeprefix("the ")


def _synthetic_ledger(stage_input: FrontHalfInput) -> _ExperimentLedger:
    digest = stage_input.source_text_sha256
    suffix = digest[:24]
    source = Source(
        id=f"src_{suffix}",
        source_type=SourceType.MANUAL_FILE,
        identity_policy_id="hsq_stage_local_source_v1",
        canonical_identity_key=f"hsq-stage-local:{digest}",
    )
    document = Document(id=f"doc_{suffix}", source_id=source.id, content_sha256=digest)
    representation_id = f"rep_{suffix}"
    text_view = TextView(
        id=f"tvw_{suffix}",
        representation_id=representation_id,
        kind=TextViewKind.LOGICAL,
        content_digest=digest,
        text=stage_input.source_text,
        normalization_policy="utf8_identity_v1",
    )
    root = DocumentNode(
        id=f"nod_{suffix}_root",
        representation_id=representation_id,
        node_type="document",
        order_index=0,
        text_view_id=text_view.id,
        start_char=0,
        end_char=len(stage_input.source_text),
    )
    paragraph = DocumentNode(
        id=f"nod_{suffix}_paragraph",
        representation_id=representation_id,
        parent_node_id=root.id,
        node_type="paragraph",
        order_index=1,
        text_view_id=text_view.id,
        start_char=0,
        end_char=len(stage_input.source_text),
    )
    quality = ParseQualityReport(
        id=f"pqr_{suffix}",
        representation_id=representation_id,
        metric_values={"text_char_count": len(stage_input.source_text)},
        analyzability=RepresentationAnalyzability.ACCEPTABLE,
    )
    template = DocumentRepresentation(
        id=representation_id,
        document_id=document.id,
        parser_name="hsq-stage-local",
        parser_version="1",
        parser_config_digest=_sha(b"hsq-stage-local-v1"),
        processing_task_fingerprint_id=f"ptf_{suffix}",
        input_blob_digest=digest,
        canonical_output_digest="0" * 64,
        created_at=_FIXED_TIME,
    )
    nodes = (root, paragraph)
    representation = template.model_copy(
        update={
            "canonical_output_digest": canonical_representation_digest(
                template,
                text_views=(text_view,),
                nodes=nodes,
                edges=(),
                source_regions=(),
                quality_report=quality,
            )
        }
    )
    bundle = DocumentRepresentationBundle(
        representation=representation,
        text_views=(text_view,),
        nodes=nodes,
        quality_report=quality,
    )
    return _ExperimentLedger(source, document, bundle)


def _paragraph_node(bundle: DocumentRepresentationBundle) -> DocumentNode:
    return next(item for item in bundle.nodes if item.node_type == "paragraph")


def _config(path: Path) -> PipelineConfig:
    return load_config(
        config_path=path.resolve(),
        ledger_path_override=None,
        archive_path_override=None,
    )


def _profile(config: PipelineConfig) -> ContextModelProfile:
    return ContextModelProfile(
        config.model_execution.profile_name or "lm-studio",
        config.model_execution.context_tokens,
        config.model_execution.max_output_tokens,
        256,
    )


def _generation(config: PipelineConfig) -> tuple[ExecutionSetting, ...]:
    return (
        ExecutionSetting("max_output_tokens", config.model_execution.max_output_tokens),
        ExecutionSetting("seed", 17),
        ExecutionSetting("temperature", 0),
    )


def _prompts() -> dict[str, bytes]:
    prompt_root = REPOSITORY_ROOT / "prompts"
    return {
        "proposal": (prompt_root / "hybrid_mention_occurrence_selection_v2.md").read_bytes(),
        "boundary_adjudication": (
            prompt_root / "hybrid_mention_boundary_adjudication_v2.md"
        ).read_bytes(),
        "interpretation": (prompt_root / "hybrid_mention_interpretation_task_v2.md").read_bytes(),
        "ontology": (prompt_root / "hybrid_mention_ontology_card_v1.md").read_bytes(),
        "reference_selection": (prompt_root / "semantic_reference_challenge_v4.md").read_bytes(),
        "reference_validation": (
            prompt_root / "semantic_reference_candidate_validation_v1.md"
        ).read_bytes(),
        "event_verb_role": (prompt_root / "event_verb_role_v1.md").read_bytes(),
        "event_verb_similarity": (prompt_root / "event_verb_similarity_v1.md").read_bytes(),
        "event_noun_inventory": (prompt_root / "event_noun_inventory_v1.md").read_bytes(),
        "event_noun_dependent_kind": (prompt_root / "event_noun_dependent_kind_v1.md").read_bytes(),
        "event_noun_media_artifact": (prompt_root / "event_noun_media_artifact_v1.md").read_bytes(),
        "event_noun_governor_distinct": (
            prompt_root / "event_noun_governor_distinct_v1.md"
        ).read_bytes(),
        "event_noun_reaction": (prompt_root / "event_noun_reaction_v1.md").read_bytes(),
        "event_noun_standing": (prompt_root / "event_noun_standing_v1.md").read_bytes(),
    }


def _experiment_contract() -> dict[str, object]:
    prompts = _prompts()
    policies = {
        "mention_boundary": HYBRID_MENTION_BOUNDARY_POLICY_ID,
        "mention_boundary_adjudication": HYBRID_MENTION_BOUNDARY_ADJUDICATION_POLICY_ID,
        "mention_preview": HYBRID_MENTION_PREVIEW_POLICY_ID,
        "semantic_reference": SEMANTIC_REFERENCE_POLICY_ID,
        "event_trigger": HYBRID_EVENT_TRIGGER_POLICY_ID,
        "event_trigger_reconciliation": TRIGGER_RECONCILIATION_POLICY_ID,
    }
    return {
        "experiment_id": "hsq_event_routed_stanza_qanom_v1",
        "parent_experiment_id": "hsq7_stage_local_event_self_contribution_v25",
        "changed_hypotheses": [
            "stanza_and_qanom_propose_source_bound_linguistic_candidates",
            "narrow_semantic_routes_outperform_one_general_event_prompt",
            "deterministic_reconciliation_owns_event_selection",
        ],
        "prompt_sha256": {name: _sha(payload) for name, payload in sorted(prompts.items())},
        "schema_sha256": {
            HYBRID_MENTION_PROPOSAL_SCHEMA_ID: _sha(mention_proposal_schema_bytes()),
            HYBRID_MENTION_BOUNDARY_ADJUDICATION_SCHEMA_ID: _sha(
                boundary_candidate_judgment_schema_bytes()
            ),
            HYBRID_MENTION_INTERPRETATION_SCHEMA_ID: _sha(mention_interpretation_schema_bytes()),
            "semantic_reference_challenge_text_v2": _sha(
                semantic_reference_challenge_schema_bytes()
            ),
            "semantic_reference_candidate_validation_text_v1": _sha(
                semantic_reference_candidate_validation_schema_bytes()
            ),
            EVENT_HEAD_JUDGMENT_SCHEMA_ID: _sha(event_head_answer_schema_bytes()),
            EVENT_VERB_ROLE_SCHEMA_ID: _sha(event_verb_role_answer_schema_bytes()),
            EVENT_BINARY_SEMANTIC_SCHEMA_ID: _sha(binary_semantic_answer_schema_bytes()),
        },
        "policy_sha256": _sha(_canonical_json(policies)),
        "optional_hypotheses": {
            "h6_source_alias_rescue": "measured_not_activated",
            "h7_selective_interpretation": "measured_not_activated",
        },
    }


def _stage_record(
    *,
    stage_input: FrontHalfInput,
    preview: dict[str, object],
    ledger: _ExperimentLedger,
    archive: LocalArchiveStore,
    stage: str,
    model_run_ids: set[str] | None = None,
) -> dict[str, object]:
    model_executions = _model_execution_records(
        ledger,
        archive,
        set(ledger.model_runs) if model_run_ids is None else model_run_ids,
    )
    trace_input_by_run = {
        str(execution_id): trace["input"].get("exact_model_input")
        for trace in cast(list[dict[str, Any]], preview.get("traces", []))
        for execution_id in cast(list[str], trace.get("execution_record_ids", []))
        if isinstance(trace.get("input"), dict)
        and isinstance(cast(dict[str, object], trace["input"]).get("exact_model_input"), str)
    }
    for execution in model_executions:
        if execution["exact_model_input"] is None:
            execution["exact_model_input"] = trace_input_by_run.get(str(execution["model_run_id"]))
    return {
        "schema_version": "hsq_stage_local_execution_v1",
        "stage": stage,
        "source_text_sha256": stage_input.source_text_sha256,
        "exact_input": stage_input.source_text,
        "preview": preview,
        "model_executions": model_executions,
        "accepted_ledger_change_count": ledger.accepted_ledger_change_count,
    }


def _model_execution_records(
    ledger: _ExperimentLedger,
    archive: LocalArchiveStore,
    run_ids: set[str],
) -> list[dict[str, object]]:
    task_by_id = {item.id: item for item in ledger.extraction_tasks.values()}
    records: list[dict[str, object]] = []
    for run_id in sorted(run_ids):
        run = ledger.model_runs[run_id]
        task = task_by_id[run.extraction_task_id]
        try:
            raw_output = archive.read_model_run_output(run.id).decode("utf-8")
        except FileNotFoundError:
            raw_output = None
        records.append(
            {
                "extraction_task_id": task.id,
                "model_run_id": run.id,
                "task_type": task.task_type,
                "producer": str(run.model_identity.get("name", "unknown")),
                "status": run.status.value,
                "elapsed_milliseconds": _required_int(
                    run.execution_diagnostics["elapsed_milliseconds"],
                    "ModelRun elapsed milliseconds",
                ),
                "exact_model_input": _model_visible_input(task),
                "raw_output": raw_output,
                "raw_output_sha256": run.output_digest,
                "parsed_outcome_metadata": run.outcome_metadata,
            }
        )
    return records


def _model_visible_input(task: ExtractionTask) -> str | None:
    import base64

    task_payload = cast(dict[str, object], task.context_manifest_payload)
    rendered_input_base64 = task_payload.get("rendered_input_base64")
    if not isinstance(rendered_input_base64, str):
        return None
    context = base64.b64decode(rendered_input_base64)
    task_local_base64 = task_payload.get("task_local_input_base64")
    if not isinstance(task_local_base64, str) or not task_local_base64:
        return context.decode("utf-8")
    local = base64.b64decode(task_local_base64)
    return (context + b"\n\n[task]\n" + local).decode("utf-8")


def _write_review(
    path: Path,
    inputs: tuple[FrontHalfInput, ...],
    report: dict[str, object],
) -> None:
    by_id = {item.item.item_id: item for item in inputs}
    lines = [
        f"# HSQ-7 {report['phase']} stage-local review",
        "",
        f"Passed: {report['passed_count']}/{report['item_count']}",
        "",
        "Boundary output-contract coverage:",
        "",
        "```json",
        json.dumps(report["boundary_contract"], ensure_ascii=False, indent=2, sort_keys=True),
        "```",
        "",
    ]
    for result in cast(list[dict[str, object]], report["cases"]):
        stage_input = by_id[str(result["item_id"])]
        lines.extend(
            (
                f"## {result['item_id']}",
                "",
                "Exact SourceSegment:",
                "",
                f"> {stage_input.source_text}",
                "",
                f"Expected: {stage_input.item.expected_summary}",
                "",
                f"First failed stage: {result['first_failed_stage'] or 'none'}",
                "",
                "Exact execution evidence:",
                "",
                f"- `mentions/{stage_input.source_text_sha256}.json`",
                f"- `references/{stage_input.source_text_sha256}.json`",
                "",
            )
        )
        for check in cast(list[dict[str, object]], result["checks"]):
            lines.extend(
                (
                    f"### {check['stage_id']} — {'pass' if check['passed'] else 'fail'}",
                    "",
                    "Expected:",
                    "",
                    "```json",
                    json.dumps(check["expected"], ensure_ascii=False, indent=2, sort_keys=True),
                    "```",
                    "",
                    "Actual:",
                    "",
                    "```json",
                    json.dumps(check["actual"], ensure_ascii=False, indent=2, sort_keys=True),
                    "```",
                    "",
                )
            )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_trigger_review(
    path: Path,
    gold: TriggerGoldCatalog,
    report: dict[str, object],
) -> None:
    gold_by_digest = {item.source_text_sha256: item for item in gold.segments}
    lines = [
        f"# HSQ-7 {report['phase']} event-trigger review",
        "",
        f"Passed: {report['passed_segment_count']}/{report['segment_count']} SourceSegments",
        "",
    ]
    for result in cast(list[dict[str, object]], report["segments"]):
        digest = str(result["source_text_sha256"])
        segment = gold_by_digest[digest]
        lines.extend(
            (
                f"## {digest}",
                "",
                "Exact SourceSegment:",
                "",
                f"> {segment.source_text}",
                "",
                "Expected Events:",
                "",
            )
        )
        if segment.event_free:
            lines.extend(("- None.", ""))
        else:
            lines.extend(
                f"- `{event.event_id}`: {event.meaning} (head `{event.head_occurrence_id}`)"
                for event in segment.events
            )
            lines.append("")
        lines.extend(
            (
                "Evaluation:",
                "",
                "```json",
                json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True),
                "```",
                "",
                f"Exact execution evidence: `triggers/{digest}.json`",
                "",
            )
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def _comparison_summary(value: dict[str, object]) -> dict[str, object]:
    return {
        "passed_count": value["passed_count"],
        "item_count": value["item_count"],
        "first_failed_stage_counts": value["first_failed_stage_counts"],
        "producer_elapsed_milliseconds": value["producer_elapsed_milliseconds"],
        "optional_experiment_measurements": value.get("optional_experiment_measurements", {}),
        "boundary_contract": value["boundary_contract"],
    }


def _trigger_comparison_summary(value: dict[str, object]) -> dict[str, object]:
    return {
        "passed": value["passed"],
        "passed_segment_count": value["passed_segment_count"],
        "segment_count": value["segment_count"],
        "expected_event_count": value["expected_event_count"],
        "actual_event_count": value["actual_event_count"],
        "exact_head_match_count": value["exact_head_match_count"],
        "exact_expression_match_count": value["exact_expression_match_count"],
        "missing_event_count": value["missing_event_count"],
        "extra_trigger_count": value["extra_trigger_count"],
        "duplicate_trigger_count": value["duplicate_trigger_count"],
        "bounded_semantic_judgment_count": value["bounded_semantic_judgment_count"],
        "failed_model_judgment_count": value["failed_model_judgment_count"],
        "source_occurrence_count": value["source_occurrence_count"],
        "event_head_candidate_count": value["event_head_candidate_count"],
        "classified_candidate_count": value["classified_candidate_count"],
        "unclassified_candidate_count": value["unclassified_candidate_count"],
        "gold_candidate_miss_count": value["gold_candidate_miss_count"],
        "model_execution_count": value["model_execution_count"],
        "model_elapsed_milliseconds": value["model_elapsed_milliseconds"],
    }


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_bytes(_canonical_json(value))
    os.replace(temporary, path)


def _write_jsonl(path: Path, values: list[object]) -> None:
    payload = b"".join(_canonical_json(value) + b"\n" for value in values)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_bytes())
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return cast(dict[str, Any], value)


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _relative_or_absolute(path: Path) -> str:
    try:
        return path.relative_to(REPOSITORY_ROOT).as_posix()
    except ValueError:
        return str(path)


def _required_int(value: object, label: str) -> int:
    if type(value) is not int:
        raise ValueError(f"{label} must be an integer.")
    return value


def _close_runtime(runtime: object) -> None:
    close = getattr(runtime, "close", None)
    if callable(close):
        close()


if __name__ == "__main__":
    raise SystemExit(main())
