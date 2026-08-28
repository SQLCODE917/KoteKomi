"""Shared isolated execution support for PHP-1 diagnostics."""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from collections.abc import Callable
from contextlib import redirect_stdout
from dataclasses import dataclass, field
from io import StringIO
from itertools import combinations
from pathlib import Path
from typing import Any

from kotekomi_adapters import LocalArchiveStore, sqlite_ledger_transaction
from kotekomi_application import (
    PARAGRAPH_HYPOTHESIS_EVIDENCE_SELECTION_V1,
    PARAGRAPH_SEGMENT_V3,
    AnalysisUnitPlanningInput,
    BoundedExtractionInput,
    ContextManifestInput,
    ContextManifestStatus,
    ContextModelProfile,
    ExecutionSetting,
    HypothesisVerifierSpec,
    MentionCandidate,
    MentionProposalObservation,
    ModelExecutionSpec,
    ModelTaskRequest,
    ModelTaskResponse,
    OrganizationMentionTaskSchemaRegistry,
    OrganizationQualificationTaskSchemaRegistry,
    ParagraphHypothesisTaskSchemaRegistry,
    Uuid4ModelRunIdFactory,
    build_context_manifest,
    combine_validated_organization_mentions,
    derive_qualified_organization_pairs,
    fuse_mention_proposals,
    model_execution_spec_digest,
    paragraph_source_segments,
    plan_analysis_units,
    resolve_document_organization_identities,
    resolve_organization_qualification,
    run_bounded_extraction,
    source_copy_view,
)
from kotekomi_pipelines.cli import main
from kotekomi_pipelines.config import load_config
from kotekomi_pipelines.model_runtime import build_model_task_runtime

ROOT = Path(__file__).resolve().parents[1]
VERIFIER_PROMPT_ID = "paragraph_hypothesis_faithfulness_v1"
VERIFIER_PROMPT_PATH = ROOT / "prompts" / "paragraph_hypothesis_faithfulness_v1.md"
ANALYSIS_POLICY_ID = "segment_local_hypothesis_v1"
H2_MENTION_PROMPT_ID = "paragraph_organization_mention_v1"
H2_MENTION_PROMPT_PATH = ROOT / "prompts" / "paragraph_organization_mention_v1.md"
H2_PAIR_PROMPT_ID = "paragraph_organization_pair_relation_v1"
H2_PAIR_PROMPT_PATH = ROOT / "prompts" / "paragraph_organization_pair_relation_v1.md"
H22_QUALIFICATION_PROMPT_ID = "paragraph_organization_qualification_v1"
H22_QUALIFICATION_PROMPT_PATH = ROOT / "prompts" / "paragraph_organization_qualification_v1.md"


@dataclass(frozen=True)
class Php1PromptContract:
    """Pins the extraction instruction that produced a diagnostic record."""

    prompt_id: str
    prompt_path: Path
    renderer_version: str


PHP1_SEGMENT_V3_PROMPT = Php1PromptContract(
    "paragraph_hypothesis_segment_v3",
    ROOT / "prompts" / "paragraph_hypothesis_segment_v3.md",
    "paragraph_hypothesis_segment_context_v3",
)
PHP1_SEGMENT_V6_PROMPT = Php1PromptContract(
    "paragraph_hypothesis_segment_v6",
    ROOT / "prompts" / "paragraph_hypothesis_segment_v6.md",
    "paragraph_hypothesis_segment_context_v3",
)
# V6 remains an explicit historical calibration contract.
# The H1 scorecard did not accept it as the production selection.
CURRENT_PHP1_PROMPT = PHP1_SEGMENT_V3_PROMPT


@dataclass(frozen=True)
class H2MentionCandidate:
    organization_text: str
    source_copy_start: int
    source_copy_end: int


@dataclass(frozen=True)
class H2CandidatePair:
    first_organization_text: str
    second_organization_text: str


@dataclass(frozen=True)
class Php1DiagnosticCase:
    case_id: str
    relative_path: str
    source_url: str
    anchor: str
    metadata: dict[str, str] = field(default_factory=lambda: {})


@dataclass(frozen=True)
class Php1Expectation:
    expectation_id: str
    case_ids: tuple[str, ...]
    fixture_path: str
    paragraph_anchor: str
    source_segment_anchor: str
    subject_text: str
    object_text: str
    relationship_shape: str

    @property
    def target_identity(self) -> tuple[str, str, str, str]:
        return (
            self.fixture_path,
            source_copy_view(self.source_segment_anchor),
            source_copy_view(self.subject_text),
            source_copy_view(self.object_text),
        )


def load_packet_source_segments(
    cases: tuple[Php1DiagnosticCase, ...],
    *,
    representation_policy_version: str = "php1-packet-diagnostic-v2",
) -> dict[str, Any]:
    """Reload every packet Source segment without invoking a model."""
    missing = sorted(case.case_id for case in cases if not (ROOT / case.relative_path).is_file())
    if missing:
        return {"status": "fixture_missing", "missing_case_ids": missing, "segments": []}
    with tempfile.TemporaryDirectory(prefix="kotekomi-php1-sources-") as temporary:
        root = Path(temporary)
        ledger_path = root / "ledger.sqlite"
        archive_path = root / "archive"
        ingest_config = root / "ingest.toml"
        ingest_config.write_text(
            f'[processing]\nrepresentation_policy_version = "{representation_policy_version}"\n',
            encoding="utf-8",
        )
        _ledger_init(ledger_path, archive_path)
        representations: dict[str, str] = {}
        sources = {(case.relative_path, case.source_url) for case in cases}
        for relative_path, source_url in sorted(sources):
            output = _source_add(
                ingest_config,
                ledger_path,
                archive_path,
                ROOT / relative_path,
                source_url,
            )
            representations[relative_path] = str(output["representation_id"])
        with sqlite_ledger_transaction(ledger_path) as ledger:
            bundles = {
                path: _required_bundle(ledger, representation_id)
                for path, representation_id in representations.items()
            }
            units_by_node: dict[tuple[str, str], tuple[Any, ...]] = {}
            unresolved: list[dict[str, str]] = []
            selected: dict[tuple[str, str, str], dict[str, Any]] = {}
            for case in cases:
                result = _resolve_case_segments(
                    case,
                    representations[case.relative_path],
                    bundles[case.relative_path],
                    ledger,
                    units_by_node,
                )
                if isinstance(result, dict):
                    unresolved.append(
                        {
                            "case_id": case.case_id,
                            "status": str(result["status"]),
                            "anchor": str(result["anchor"]),
                        }
                    )
                    continue
                for plan in result:
                    source_text = _plan_source_copy(plan)
                    entry = selected.setdefault(
                        plan.key,
                        {
                            "case_ids": [],
                            "fixture_path": plan.fixture_path,
                            "fixture_sha256": hashlib.sha256(
                                (ROOT / plan.fixture_path).read_bytes()
                            ).hexdigest(),
                            "representation_id": plan.representation_id,
                            "paragraph_node_id": plan.paragraph_node_id,
                            "source_segment_label": plan.source_segment_label,
                            "source_text": source_text,
                            "source_text_sha256": hashlib.sha256(source_text.encode()).hexdigest(),
                        },
                    )
                    entry["case_ids"].append(case.case_id)
    return {
        "status": "completed" if not unresolved else "selection_incomplete",
        "unresolved_cases": unresolved,
        "segments": [
            {**entry, "case_ids": sorted(entry["case_ids"])}
            for _, entry in sorted(selected.items())
        ],
    }


def run_qwen_mentions_for_packet(
    config_path: Path | None,
    cases: tuple[Php1DiagnosticCase, ...],
    *,
    repetitions: int = 3,
    representation_policy_version: str = "php1-packet-diagnostic-v2",
) -> dict[str, Any]:
    """Run the H2 Qwen mention task repeatedly for every unique packet Source segment."""
    if repetitions != 3:
        raise ValueError("H2.1 requires exactly three Qwen repetitions.")
    missing = sorted(case.case_id for case in cases if not (ROOT / case.relative_path).is_file())
    if missing:
        return {"status": "fixture_missing", "missing_case_ids": missing, "runs": []}
    with tempfile.TemporaryDirectory(prefix="kotekomi-php1-qwen-mentions-") as temporary:
        root = Path(temporary)
        ledger_path = root / "ledger.sqlite"
        archive_path = root / "archive"
        ingest_config = root / "ingest.toml"
        ingest_config.write_text(
            f'[processing]\nrepresentation_policy_version = "{representation_policy_version}"\n',
            encoding="utf-8",
        )
        _ledger_init(ledger_path, archive_path)
        representations: dict[str, str] = {}
        sources = {(case.relative_path, case.source_url) for case in cases}
        for relative_path, source_url in sorted(sources):
            output = _source_add(
                ingest_config,
                ledger_path,
                archive_path,
                ROOT / relative_path,
                source_url,
            )
            representations[relative_path] = str(output["representation_id"])
        config = load_config(
            config_path=config_path,
            ledger_path_override=ledger_path,
            archive_path_override=archive_path,
        )
        runtime = RecordingRuntime(build_model_task_runtime(config.model_execution))
        readiness = runtime.check_readiness()
        if not readiness.ready:
            return {"status": "qwen_unavailable", "runs": []}
        archive = LocalArchiveStore(archive_path)
        tokenizer = DiagnosticTokenizer()
        with sqlite_ledger_transaction(ledger_path) as ledger:
            bundles = {
                path: _required_bundle(ledger, representation_id)
                for path, representation_id in representations.items()
            }
            units_by_node: dict[tuple[str, str], tuple[Any, ...]] = {}
            plans: dict[tuple[str, str, str], _ResolvedSegment] = {}
            unresolved: list[dict[str, str]] = []
            for case in cases:
                result = _resolve_case_segments(
                    case,
                    representations[case.relative_path],
                    bundles[case.relative_path],
                    ledger,
                    units_by_node,
                )
                if isinstance(result, dict):
                    unresolved.append(
                        {
                            "case_id": case.case_id,
                            "status": str(result["status"]),
                        }
                    )
                    continue
                plans.update({plan.key: plan for plan in result})
            if unresolved:
                return {
                    "status": "selection_incomplete",
                    "unresolved_cases": unresolved,
                    "runs": [],
                }
            runs: list[dict[str, Any]] = []
            for repetition in range(1, repetitions + 1):
                results: list[dict[str, Any]] = []
                for key, plan in sorted(plans.items()):
                    mention_result = _h2_mention_result(
                        plan,
                        ledger,
                        archive,
                        config,
                        runtime,
                        tokenizer,
                    )
                    results.append(
                        {
                            "fixture_path": key[0],
                            "paragraph_node_id": key[1],
                            "source_segment_label": key[2],
                            "source_text_sha256": hashlib.sha256(
                                _plan_source_copy(plan).encode()
                            ).hexdigest(),
                            **mention_result,
                        }
                    )
                runs.append({"repetition": repetition, "segments": results})
    identity = runtime.configured_identity
    return {
        "status": "completed",
        "model_identity": {
            "name": identity.name,
            "weights_digest": identity.weights_digest,
            "runtime": identity.runtime,
            "tokenizer_id": identity.tokenizer_id,
            "determinism_settings": [
                {"key": item.key, "value": item.value} for item in identity.determinism_settings
            ],
        },
        "runs": runs,
    }


def run_qwen_qualifications_for_packet(
    config_path: Path | None,
    cases: tuple[Php1DiagnosticCase, ...],
    expectations: tuple[Php1Expectation, ...],
    candidate_runs: list[dict[str, Any]],
    *,
    representation_policy_version: str = "php1-packet-diagnostic-v2",
    checkpoint: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Qualify fused Mention candidates and run target Relationship judgments."""
    if len(candidate_runs) != 3:
        raise ValueError("H2.2 requires exactly three candidate repetitions.")
    missing = sorted(case.case_id for case in cases if not (ROOT / case.relative_path).is_file())
    if missing:
        return {"status": "fixture_missing", "missing_case_ids": missing, "runs": []}
    with tempfile.TemporaryDirectory(prefix="kotekomi-php1-qualifications-") as temporary:
        root = Path(temporary)
        ledger_path = root / "ledger.sqlite"
        archive_path = root / "archive"
        ingest_config = root / "ingest.toml"
        ingest_config.write_text(
            f'[processing]\nrepresentation_policy_version = "{representation_policy_version}"\n',
            encoding="utf-8",
        )
        _ledger_init(ledger_path, archive_path)
        representations: dict[str, str] = {}
        sources = {(case.relative_path, case.source_url) for case in cases}
        for relative_path, source_url in sorted(sources):
            output = _source_add(
                ingest_config,
                ledger_path,
                archive_path,
                ROOT / relative_path,
                source_url,
            )
            representations[relative_path] = str(output["representation_id"])
        config = load_config(
            config_path=config_path,
            ledger_path_override=ledger_path,
            archive_path_override=archive_path,
        )
        runtime = RecordingRuntime(build_model_task_runtime(config.model_execution))
        if not runtime.check_readiness().ready:
            return {"status": "qwen_unavailable", "runs": []}
        archive = LocalArchiveStore(archive_path)
        tokenizer = DiagnosticTokenizer()
        verifier_prompt = VERIFIER_PROMPT_PATH.read_bytes()
        with sqlite_ledger_transaction(ledger_path) as ledger:
            bundles = {
                path: _required_bundle(ledger, representation_id)
                for path, representation_id in representations.items()
            }
            units_by_node: dict[tuple[str, str], tuple[Any, ...]] = {}
            plans: dict[tuple[str, str, str], _ResolvedSegment] = {}
            review_plans: dict[tuple[str, str, str], _ResolvedSegment] = {}
            unresolved: list[dict[str, str]] = []
            for case in cases:
                resolved = _resolve_case_segments(
                    case,
                    representations[case.relative_path],
                    bundles[case.relative_path],
                    ledger,
                    units_by_node,
                )
                if isinstance(resolved, dict):
                    unresolved.append({"case_id": case.case_id, "status": str(resolved["status"])})
                    continue
                for plan in resolved:
                    plans[plan.key] = plan
                    source_text = _plan_source_copy(plan)
                    review_key = (
                        plan.fixture_path,
                        hashlib.sha256(source_text.encode()).hexdigest(),
                        plan.source_segment_label,
                    )
                    existing = review_plans.get(review_key)
                    if existing is not None and existing.key != plan.key:
                        raise ValueError("H2.2 Source segment review identity is ambiguous.")
                    review_plans[review_key] = plan
            if unresolved:
                return {
                    "status": "selection_incomplete",
                    "unresolved_cases": unresolved,
                    "runs": [],
                }
            expectation_resolutions = {
                expectation.expectation_id: _resolve_expectation(
                    expectation,
                    representations[expectation.fixture_path],
                    bundles[expectation.fixture_path],
                    ledger,
                    units_by_node,
                )
                for expectation in expectations
            }
            expected_pairs_by_plan: dict[tuple[str, str, str], set[frozenset[str]]] = {}
            for expectation in expectations:
                plan = expectation_resolutions[expectation.expectation_id].get("plan")
                if isinstance(plan, _ResolvedSegment):
                    expected_pairs_by_plan.setdefault(plan.key, set()).add(
                        frozenset(
                            (
                                source_copy_view(expectation.subject_text),
                                source_copy_view(expectation.object_text),
                            )
                        )
                    )
            runs: list[dict[str, Any]] = []
            for candidate_run in candidate_runs:
                repetition = int(candidate_run["repetition"])
                _progress({"event": "h22_qualification_run_started", "repetition": repetition})
                candidate_segments = {
                    (
                        str(item["fixture_path"]),
                        str(item["source_text_sha256"]),
                        str(item["source_segment_label"]),
                    ): item
                    for item in candidate_run["segments"]
                }
                if set(candidate_segments) != set(review_plans):
                    raise ValueError("H2.2 candidate run does not cover every Source segment.")
                segment_values: dict[tuple[str, str, str], dict[str, Any]] = {}
                all_mentions: list[Any] = []
                for review_key, plan in sorted(review_plans.items()):
                    candidate_segment = candidate_segments[review_key]
                    source_text = _plan_source_copy(plan)
                    candidates = tuple(
                        _mention_candidate_from_value(item, source_text)
                        for item in candidate_segment["candidates"]
                    )
                    qualifications = tuple(
                        _h22_qualification_result(
                            plan,
                            candidate,
                            ledger,
                            archive,
                            config,
                            runtime,
                            tokenizer,
                        )
                        for candidate in candidates
                    )
                    mentions = combine_validated_organization_mentions(
                        tuple(
                            item["mention_record"]
                            for item in qualifications
                            if item["mention_record"] is not None
                        )
                    )
                    all_mentions.extend(mentions)
                    segment_values[plan.key] = {
                        "fixture_path": plan.fixture_path,
                        "representation_id": plan.representation_id,
                        "paragraph_node_id": plan.paragraph_node_id,
                        "source_segment_label": plan.source_segment_label,
                        "source_segment_id": candidates[0].source_segment_id
                        if candidates
                        else "\x1f".join(review_key),
                        "source_text_sha256": review_key[1],
                        "source_text": source_text,
                        "candidates": list(candidate_segment["candidates"]),
                        "qualification_results": [
                            {key: value for key, value in item.items() if key != "mention_record"}
                            for item in qualifications
                        ],
                        "mention_records": mentions,
                    }
                resolutions = {
                    representation_id: resolve_document_organization_identities(
                        representation_id,
                        tuple(
                            mention
                            for mention in all_mentions
                            if mention.representation_id == representation_id
                        ),
                    )
                    for representation_id in sorted(representations.values())
                }
                identities = tuple(
                    identity
                    for resolution in resolutions.values()
                    for identity in resolution.identities
                )
                pair_results: dict[tuple[str, str, str], tuple[dict[str, Any], ...]] = {}
                for key, segment in sorted(segment_values.items()):
                    mentions = tuple(segment.pop("mention_records"))
                    pairs = derive_qualified_organization_pairs(
                        str(segment["source_segment_id"]),
                        mentions,
                        identities,
                    )
                    segment["proposals"] = [
                        {"text": item.text, "start": item.start, "end": item.end, "score": None}
                        for item in mentions
                    ]
                    segment["validated_mentions"] = [
                        _validated_mention_value(item) for item in mentions
                    ]
                    segment["qualified_pairs"] = [_qualified_pair_value(item) for item in pairs]
                    expected_pairs = expected_pairs_by_plan.get(key, set())
                    pairs_to_judge = tuple(
                        item
                        for item in pairs
                        if frozenset(
                            (
                                source_copy_view(item.first_organization_text),
                                source_copy_view(item.second_organization_text),
                            )
                        )
                        in expected_pairs
                    )
                    plan = plans[key]
                    pair_results[key] = tuple(
                        _h2_pair_judgment(
                            plan,
                            H2CandidatePair(
                                pair.first_organization_text,
                                pair.second_organization_text,
                            ),
                            ledger,
                            archive,
                            config,
                            runtime,
                            tokenizer,
                            verifier_prompt,
                        )
                        for pair in pairs_to_judge
                    )
                    segment["relationship_judgments"] = list(pair_results[key])
                target_results: list[dict[str, Any]] = []
                for expectation in expectations:
                    resolution = expectation_resolutions[expectation.expectation_id]
                    plan = resolution.get("plan")
                    if not isinstance(plan, _ResolvedSegment):
                        target_results.append(
                            {
                                "expectation_id": expectation.expectation_id,
                                "target_status": "unresolved",
                                "candidate_pair_state": "not_created",
                                "diagnostics": list(resolution["diagnostics"]),
                            }
                        )
                        continue
                    segment = segment_values[plan.key]
                    qualification_values = segment["qualification_results"]
                    mention_result = {
                        "status": "complete",
                        "mention_candidates": [
                            {
                                "organization_text": item["text"],
                                "source_copy_start": item["start"],
                                "source_copy_end": item["end"],
                            }
                            for item in segment["proposals"]
                        ],
                        "context_manifest_id": (
                            qualification_values[0]["context_manifest_id"]
                            if qualification_values
                            else None
                        ),
                        "model_run_id": (
                            qualification_values[0]["model_run_id"]
                            if qualification_values
                            else None
                        ),
                        "diagnostics": [],
                    }
                    target_results.append(
                        h2_target_result(
                            expectation,
                            plan,
                            mention_result,
                            pair_results.get(plan.key, ()),
                        )
                    )
                runs.append(
                    {
                        "repetition": repetition,
                        "segments": [segment_values[key] for key in sorted(segment_values)],
                        "identities": [_organization_identity_value(item) for item in identities],
                        "alias_decisions": [
                            _alias_decision_value(item)
                            for resolution in resolutions.values()
                            for item in resolution.alias_decisions
                        ],
                        "target_results": target_results,
                        "unexpected_hypotheses": _h2_unexpected_hypotheses(
                            pair_results,
                            expectations,
                        ),
                    }
                )
                if checkpoint is not None:
                    checkpoint({"status": "in_progress", "runs": runs})
                _progress({"event": "h22_qualification_run_completed", "repetition": repetition})
    result = {"status": "completed", "runs": runs}
    if checkpoint is not None:
        checkpoint(result)
    return result


@dataclass(frozen=True)
class _ResolvedSegment:
    fixture_path: str
    representation_id: str
    paragraph_node_id: str
    paragraph_text: str
    source_segment_label: str
    unit: Any

    @property
    def key(self) -> tuple[str, str, str]:
        return (self.fixture_path, self.paragraph_node_id, self.source_segment_label)


class DiagnosticTokenizer:
    tokenizer_id = "lm_studio_whitespace_v1"

    def count_tokens(self, rendered_input: bytes) -> int:
        return len(rendered_input.decode("utf-8").split())


def evaluate_eight_claim_limit(
    raw_output: str | None, provisional_eligibility: str
) -> dict[str, int | str]:
    """Measure the PHP-1 limit without changing production validation."""
    if provisional_eligibility != "eligible":
        return {"state": "not_applicable", "excess_claim_line_count": 0}
    if raw_output is None:
        return {"state": "not_measurable", "excess_claim_line_count": 0}
    lines = raw_output.splitlines()
    if not lines or any(not line or line != line.strip() for line in lines):
        return {"state": "not_measurable", "excess_claim_line_count": 0}
    if not all(_has_claim_shape(line) for line in lines):
        return {"state": "not_measurable", "excess_claim_line_count": 0}
    return {
        "state": "measured",
        "excess_claim_line_count": max(0, len(lines) - 8),
    }


def _has_claim_shape(line: str) -> bool:
    if not line.startswith("claim: "):
        return False
    parts = line.removeprefix("claim: ").split(" | ")
    return len(parts) == 4 and all(part and part == part.strip() for part in parts)


def diagnostic_segment_status(
    model_run_status: str,
    proposed_change_count: int,
    outcome_metadata: dict[str, Any],
) -> str:
    """Expose verifier rejection separately from successful candidate publication."""
    if model_run_status != "succeeded":
        return model_run_status
    if (
        proposed_change_count == 0
        and int(outcome_metadata.get("faithfulness_rejected_claim_count", 0)) > 0
    ):
        return "faithfulness_rejected"
    return "complete"


def diagnostic_case_status(segment_statuses: set[str]) -> str:
    """Return one visible case result from all of its sentence outcomes."""
    if "complete" in segment_statuses:
        return "complete"
    if "invalid_output" in segment_statuses:
        return "invalid_output"
    if "faithfulness_rejected" in segment_statuses:
        return "faithfulness_rejected"
    if segment_statuses == {"abstained"}:
        return "abstained"
    return "context_not_ready"


class RecordingRuntime:
    """Records a task response without changing the ModelTaskRuntime contract."""

    def __init__(self, delegate: Any) -> None:
        self._delegate = delegate
        self.responses: list[ModelTaskResponse] = []

    @property
    def configured_identity(self) -> Any:
        return self._delegate.configured_identity

    @property
    def task_deadline_seconds(self) -> float:
        return self._delegate.task_deadline_seconds

    def check_readiness(self) -> Any:
        return self._delegate.check_readiness()

    def run_model_task(self, task: ModelTaskRequest) -> ModelTaskResponse:
        response = self._delegate.run_model_task(task)
        self.responses.append(response)
        return response


def run_cases(
    config_path: Path | None,
    cases: tuple[Php1DiagnosticCase, ...],
    *,
    representation_policy_version: str,
    include_raw_output: bool,
    expectations: tuple[Php1Expectation, ...] = (),
    prompt_contract: Php1PromptContract = CURRENT_PHP1_PROMPT,
) -> dict[str, Any]:
    _progress({"event": "run_started", "case_count": len(cases)})
    missing = [case.case_id for case in cases if not (ROOT / case.relative_path).is_file()]
    if missing:
        _progress({"event": "run_completed", "status": "fixture_missing"})
        return {
            "status": "fixture_missing",
            "cases": [{"case_id": case_id, "status": "fixture_missing"} for case_id in missing],
        }
    with tempfile.TemporaryDirectory(prefix="kotekomi-php1-") as temporary:
        root = Path(temporary)
        ledger_path = root / "ledger.sqlite"
        archive_path = root / "archive"
        ingest_config = root / "ingest.toml"
        ingest_config.write_text(
            f'[processing]\nrepresentation_policy_version = "{representation_policy_version}"\n',
            encoding="utf-8",
        )
        _ledger_init(ledger_path, archive_path)
        representations: dict[str, str] = {}
        sources = {(case.relative_path, case.source_url) for case in cases}
        for relative_path, source_url in sorted(sources):
            _progress({"event": "source_ingest_started", "path": relative_path})
            output = _source_add(
                ingest_config, ledger_path, archive_path, ROOT / relative_path, source_url
            )
            representations[relative_path] = str(output["representation_id"])
            _progress({"event": "source_ingest_completed", "path": relative_path})
        config = load_config(
            config_path=config_path,
            ledger_path_override=ledger_path,
            archive_path_override=archive_path,
        )
        runtime = RecordingRuntime(build_model_task_runtime(config.model_execution))
        if not runtime.check_readiness().ready:
            _progress({"event": "run_completed", "status": "runtime_unavailable"})
            return {"status": "runtime_unavailable", "cases": []}
        archive = LocalArchiveStore(archive_path)
        schema = ParagraphHypothesisTaskSchemaRegistry().resolve("paragraph_hypothesis_text_v1")
        prompt = prompt_contract.prompt_path.read_bytes()
        verifier_prompt = VERIFIER_PROMPT_PATH.read_bytes()
        tokenizer = DiagnosticTokenizer()
        with sqlite_ledger_transaction(ledger_path) as ledger:
            bundles = {
                path: _required_bundle(ledger, representation_id)
                for path, representation_id in representations.items()
            }
            units_by_node: dict[tuple[str, str], tuple[Any, ...]] = {}
            case_plans: dict[str, tuple[_ResolvedSegment, ...]] = {}
            case_selection_results: dict[str, dict[str, Any]] = {}
            planned_segments: dict[tuple[str, str, str], _ResolvedSegment] = {}
            for case in cases:
                selection = _resolve_case_segments(
                    case,
                    representations[case.relative_path],
                    bundles[case.relative_path],
                    ledger,
                    units_by_node,
                )
                if isinstance(selection, dict):
                    case_selection_results[case.case_id] = selection
                    continue
                case_plans[case.case_id] = selection
                planned_segments.update({plan.key: plan for plan in selection})

            expectation_resolutions = {
                expectation.expectation_id: _resolve_expectation(
                    expectation,
                    representations[expectation.fixture_path],
                    bundles[expectation.fixture_path],
                    ledger,
                    units_by_node,
                )
                for expectation in expectations
            }
            for resolution in expectation_resolutions.values():
                plan = resolution.get("plan")
                if isinstance(plan, _ResolvedSegment):
                    planned_segments[plan.key] = plan

            segment_results: dict[tuple[str, str, str], dict[str, Any]] = {}
            for key, plan in sorted(planned_segments.items()):
                _progress(
                    {
                        "event": "source_segment_started",
                        "fixture_path": plan.fixture_path,
                        "paragraph_node_id": plan.paragraph_node_id,
                        "source_segment_label": plan.source_segment_label,
                    }
                )
                segment_results[key] = _run_segment(
                    plan,
                    ledger,
                    archive,
                    config,
                    runtime,
                    schema,
                    prompt,
                    verifier_prompt,
                    tokenizer,
                    include_raw_output,
                    prompt_contract,
                )

            results: list[dict[str, Any]] = []
            for case in cases:
                _progress({"event": "case_started", "case_id": case.case_id})
                selection_result = case_selection_results.get(case.case_id)
                if selection_result is not None:
                    result = {"case_id": case.case_id, **case.metadata, **selection_result}
                else:
                    result = _case_result_from_segments(
                        case,
                        case_plans[case.case_id],
                        segment_results,
                        include_raw_output,
                    )
                results.append(result)
                _progress(
                    {
                        "event": "case_completed",
                        "case_id": case.case_id,
                        "status": result["status"],
                    }
                )
            target_report = (
                _target_report(expectations, expectation_resolutions, segment_results)
                if expectations
                else None
            )
    summary: dict[str, Any] = {"status": "completed", "cases": results}
    if target_report is not None:
        summary["target_report"] = target_report
    _progress({"event": "run_completed", "status": summary["status"]})
    return summary


def run_h2(
    config_path: Path | None,
    cases: tuple[Php1DiagnosticCase, ...],
    expectations: tuple[Php1Expectation, ...],
) -> dict[str, Any]:
    """Run bounded mention and pair diagnostics for resolved H0 Expectations."""
    cases_by_fixture = {case.relative_path: case for case in cases}
    missing = sorted(
        expectation.fixture_path
        for expectation in expectations
        if not (ROOT / expectation.fixture_path).is_file()
    )
    if missing:
        return {
            "status": "fixture_missing",
            "h2_target_report": {
                "target_results": [
                    {
                        "expectation_id": expectation.expectation_id,
                        "target_status": "fixture_missing",
                    }
                    for expectation in expectations
                    if expectation.fixture_path in missing
                ],
                "unexpected_hypotheses": [],
            },
        }
    with tempfile.TemporaryDirectory(prefix="kotekomi-php1-h2-") as temporary:
        root = Path(temporary)
        ledger_path = root / "ledger.sqlite"
        archive_path = root / "archive"
        ingest_config = root / "ingest.toml"
        ingest_config.write_text(
            '[processing]\nrepresentation_policy_version = "php1-packet-diagnostic-v2"\n',
            encoding="utf-8",
        )
        _ledger_init(ledger_path, archive_path)
        representations: dict[str, str] = {}
        for fixture_path in sorted({item.fixture_path for item in expectations}):
            case = cases_by_fixture.get(fixture_path)
            if case is None:
                raise ValueError("H2 Expectation fixture has no annotation packet case.")
            _progress({"event": "source_ingest_started", "path": fixture_path})
            output = _source_add(
                ingest_config,
                ledger_path,
                archive_path,
                ROOT / fixture_path,
                case.source_url,
            )
            representations[fixture_path] = str(output["representation_id"])
            _progress({"event": "source_ingest_completed", "path": fixture_path})
        config = load_config(
            config_path=config_path,
            ledger_path_override=ledger_path,
            archive_path_override=archive_path,
        )
        runtime = RecordingRuntime(build_model_task_runtime(config.model_execution))
        if not runtime.check_readiness().ready:
            return {"status": "runtime_unavailable", "h2_target_report": {"target_results": []}}
        archive = LocalArchiveStore(archive_path)
        verifier_prompt = VERIFIER_PROMPT_PATH.read_bytes()
        tokenizer = DiagnosticTokenizer()
        with sqlite_ledger_transaction(ledger_path) as ledger:
            bundles = {
                path: _required_bundle(ledger, representation_id)
                for path, representation_id in representations.items()
            }
            units_by_node: dict[tuple[str, str], tuple[Any, ...]] = {}
            resolutions = {
                expectation.expectation_id: _resolve_expectation(
                    expectation,
                    representations[expectation.fixture_path],
                    bundles[expectation.fixture_path],
                    ledger,
                    units_by_node,
                )
                for expectation in expectations
            }
            plans = {
                plan.key: plan
                for resolution in resolutions.values()
                if isinstance((plan := resolution.get("plan")), _ResolvedSegment)
            }
            mention_results: dict[tuple[str, str, str], dict[str, Any]] = {}
            pair_results: dict[tuple[str, str, str], tuple[dict[str, Any], ...]] = {}
            for key, plan in sorted(plans.items()):
                _progress(
                    {
                        "event": "h2_mention_started",
                        "fixture_path": plan.fixture_path,
                        "source_segment_label": plan.source_segment_label,
                    }
                )
                mention_result = _h2_mention_result(
                    plan,
                    ledger,
                    archive,
                    config,
                    runtime,
                    tokenizer,
                )
                mention_results[key] = mention_result
                candidate_values = tuple(
                    H2MentionCandidate(
                        str(item["organization_text"]),
                        int(item["source_copy_start"]),
                        int(item["source_copy_end"]),
                    )
                    for item in mention_result["mention_candidates"]
                )
                pairs = candidate_pairs(candidate_values)
                pair_results[key] = tuple(
                    _h2_pair_judgment(
                        plan,
                        pair,
                        ledger,
                        archive,
                        config,
                        runtime,
                        tokenizer,
                        verifier_prompt,
                    )
                    for pair in pairs
                )
            target_results: list[dict[str, Any]] = []
            for expectation in expectations:
                resolution = resolutions[expectation.expectation_id]
                plan = resolution.get("plan")
                if not isinstance(plan, _ResolvedSegment):
                    target_results.append(
                        {
                            "expectation_id": expectation.expectation_id,
                            "target_status": "unresolved",
                            "diagnostics": list(resolution["diagnostics"]),
                        }
                    )
                    continue
                target_results.append(
                    h2_target_result(
                        expectation,
                        plan,
                        mention_results[plan.key],
                        pair_results[plan.key],
                    )
                )
            unexpected = _h2_unexpected_hypotheses(pair_results, expectations)
    result = {
        "status": "completed",
        "h2_target_report": {
            "target_results": target_results,
            "unexpected_hypotheses": unexpected,
        },
        "mention_results": [
            {
                "fixture_path": key[0],
                "paragraph_node_id": key[1],
                "source_segment_label": key[2],
                **item,
            }
            for key, item in sorted(mention_results.items())
        ],
        "pair_results": [
            {
                "fixture_path": key[0],
                "paragraph_node_id": key[1],
                "source_segment_label": key[2],
                "judgments": list(items),
            }
            for key, items in sorted(pair_results.items())
        ],
    }
    _progress({"event": "run_completed", "status": result["status"]})
    return result


def _required_bundle(ledger: Any, representation_id: str) -> Any:
    bundle = ledger.get_document_representation_bundle(representation_id)
    if bundle is None:
        raise ValueError("PHP-1 diagnostic representation is missing.")
    return bundle


def _units_for_node(
    representation_id: str,
    node_id: str,
    ledger: Any,
    cache: dict[tuple[str, str], tuple[Any, ...]],
) -> tuple[Any, ...]:
    key = (representation_id, node_id)
    cached = cache.get(key)
    if cached is not None:
        return cached
    units = tuple(
        item
        for item in plan_analysis_units(
            AnalysisUnitPlanningInput(
                representation_id,
                ANALYSIS_POLICY_ID,
                "claim_extraction",
                focus_node_types=("paragraph",),
            ),
            ledger,
        ).units
        if item.focus_node_ids == (node_id,)
    )
    cache[key] = units
    return units


def _resolve_case_segments(
    case: Php1DiagnosticCase,
    representation_id: str,
    bundle: Any,
    ledger: Any,
    units_by_node: dict[tuple[str, str], tuple[Any, ...]],
) -> tuple[_ResolvedSegment, ...] | dict[str, Any]:
    selected = _first_paragraph_for_anchor(bundle, case.anchor)
    if selected is None:
        return {"status": "selection_missing", "anchor": case.anchor}
    node_id, paragraph_text = selected
    units = _units_for_node(representation_id, node_id, ledger, units_by_node)
    if not units:
        return {"status": "selection_missing", "anchor": case.anchor}
    return tuple(
        _ResolvedSegment(
            case.relative_path,
            representation_id,
            node_id,
            paragraph_text,
            str(unit.source_segment_label),
            unit,
        )
        for unit in units
    )


def _resolve_expectation(
    expectation: Php1Expectation,
    representation_id: str,
    bundle: Any,
    ledger: Any,
    units_by_node: dict[tuple[str, str], tuple[Any, ...]],
) -> dict[str, Any]:
    paragraphs = _paragraphs_for_anchor(bundle, expectation.paragraph_anchor)
    if len(paragraphs) != 1:
        return {
            "resolution_status": "unresolved",
            "diagnostics": ["paragraph_anchor_not_unique"],
        }
    node_id, paragraph_text = paragraphs[0]
    segments = tuple(
        segment
        for segment in paragraph_source_segments(paragraph_text, PARAGRAPH_SEGMENT_V3)
        if _anchor_matches(segment.exact_text, expectation.source_segment_anchor)
    )
    if len(segments) != 1:
        return {
            "resolution_status": "unresolved",
            "diagnostics": ["source_segment_anchor_not_unique"],
        }
    units = _units_for_node(representation_id, node_id, ledger, units_by_node)
    source_segment = segments[0]
    matching_units = tuple(
        unit for unit in units if unit.source_segment_label == source_segment.label
    )
    if len(matching_units) != 1:
        return {
            "resolution_status": "unresolved",
            "diagnostics": ["source_segment_unit_not_unique"],
        }
    return {
        "resolution_status": "resolved",
        "diagnostics": [],
        "plan": _ResolvedSegment(
            expectation.fixture_path,
            representation_id,
            node_id,
            paragraph_text,
            source_segment.label,
            matching_units[0],
        ),
    }


def _run_segment(
    plan: _ResolvedSegment,
    ledger: Any,
    archive: LocalArchiveStore,
    config: Any,
    runtime: RecordingRuntime,
    schema: Any,
    prompt: bytes,
    verifier_prompt: bytes,
    tokenizer: DiagnosticTokenizer,
    include_raw_output: bool,
    prompt_contract: Php1PromptContract,
) -> dict[str, Any]:
    bundle = _required_bundle(ledger, plan.representation_id)
    document = ledger.get_document(bundle.representation.document_id)
    if document is None:
        raise ValueError("PHP-1 diagnostic Document is missing.")
    manifest = build_context_manifest(
        ContextManifestInput(
            plan.unit,
            ContextModelProfile(
                config.model_execution.profile_name or "lm-studio",
                config.model_execution.context_tokens,
                config.model_execution.max_output_tokens,
                256,
            ),
            prompt_contract.prompt_id,
            prompt,
            schema.schema_id,
            schema.canonical_schema_bytes,
            prompt_contract.renderer_version,
            PARAGRAPH_HYPOTHESIS_EVIDENCE_SELECTION_V1,
            PARAGRAPH_SEGMENT_V3,
        ),
        ledger,
        tokenizer,
    ).manifest
    if manifest.status is not ContextManifestStatus.READY:
        return {
            "source_segment_label": plan.source_segment_label,
            "status": "context_not_ready",
            "model_run_id": None,
            "proposed_change_ids": [],
            "verified_hypotheses": [],
            "prompt_digest": hashlib.sha256(prompt).hexdigest(),
            "schema_digest": schema.digest,
            "execution_spec_digest": None,
        }
    spec = ModelExecutionSpec(
        config.model_execution.profile_name or "lm-studio",
        runtime.configured_identity,
        (
            ExecutionSetting("max_output_tokens", config.model_execution.max_output_tokens),
            ExecutionSetting("seed", 17),
            ExecutionSetting("temperature", 0),
        ),
        prompt_contract.prompt_id,
        hashlib.sha256(prompt).hexdigest(),
        schema.schema_id,
        schema.digest,
        manifest.id,
        manifest.manifest_digest,
        manifest.rendered_input_digest,
        schema.output_contract_version,
    )
    response_count = len(runtime.responses)
    outcome = run_bounded_extraction(
        BoundedExtractionInput(
            document.source_id,
            document.id,
            plan.representation_id,
            manifest.id,
            prompt,
            spec,
            "paragraph_hypothesis_validator_v1",
            HypothesisVerifierSpec(VERIFIER_PROMPT_ID, verifier_prompt),
        ),
        ledger,
        archive,
        runtime,
        Uuid4ModelRunIdFactory(),
        tokenizer,
        ParagraphHypothesisTaskSchemaRegistry(),
    )
    responses = runtime.responses[response_count:]
    raw_output = (
        responses[0].raw_output.decode("utf-8", errors="replace")
        if include_raw_output and responses
        else None
    )
    verifier_raw_outputs = (
        [response.raw_output.decode("utf-8", errors="replace") for response in responses[1:]]
        if include_raw_output
        else []
    )
    proposed_change_ids = (
        list(outcome.proposed_change_batch.proposed_change_ids_by_local_id.values())
        if outcome.proposed_change_batch
        else []
    )
    outcome_metadata = outcome.model_run.outcome_metadata
    return {
        "source_segment_label": plan.source_segment_label,
        "status": diagnostic_segment_status(
            outcome.model_run.status.value,
            len(proposed_change_ids),
            outcome_metadata,
        ),
        "model_run_id": outcome.model_run.id,
        "raw_output": raw_output,
        "verifier_raw_outputs": verifier_raw_outputs,
        "error_code": outcome.model_run.error_code,
        "error_message": outcome.model_run.error_message,
        "abstention_reason": outcome.model_run.abstention_reason,
        "execution_diagnostics": outcome.model_run.execution_diagnostics,
        "proposed_change_ids": proposed_change_ids,
        "faithfulness_accepted_claim_count": outcome_metadata.get(
            "faithfulness_accepted_claim_count", 0
        ),
        "faithfulness_rejected_claim_count": outcome_metadata.get(
            "faithfulness_rejected_claim_count", 0
        ),
        "verified_hypotheses": [
            {
                "subject_text": item.hypothesis.subject,
                "relation_text": item.hypothesis.relation,
                "object_text": item.hypothesis.object_value,
                "proposed_change_id": item.proposed_change_id,
            }
            for item in outcome.verified_hypotheses
        ],
        "prompt_digest": spec.prompt_digest,
        "schema_digest": spec.schema_digest,
        "execution_spec_digest": model_execution_spec_digest(spec),
    }


def candidate_pairs(mentions: tuple[H2MentionCandidate, ...]) -> tuple[H2CandidatePair, ...]:
    """Derive each unordered source-segment-local mention pair once."""
    return tuple(
        H2CandidatePair(first.organization_text, second.organization_text)
        for first, second in combinations(mentions, 2)
    )


def _plan_source_copy(plan: _ResolvedSegment) -> str:
    segments = tuple(
        item
        for item in paragraph_source_segments(plan.paragraph_text, PARAGRAPH_SEGMENT_V3)
        if item.label == plan.source_segment_label
    )
    if len(segments) != 1:
        raise ValueError("H2 Source segment resolution is not unique.")
    return source_copy_view(segments[0].exact_text)


def _h2_execution_spec(
    prompt_id: str,
    prompt: bytes,
    schema: Any,
    manifest: Any,
    config: Any,
    runtime: RecordingRuntime,
) -> ModelExecutionSpec:
    return ModelExecutionSpec(
        config.model_execution.profile_name or "lm-studio",
        runtime.configured_identity,
        (
            ExecutionSetting("max_output_tokens", config.model_execution.max_output_tokens),
            ExecutionSetting("seed", 17),
            ExecutionSetting("temperature", 0),
        ),
        prompt_id,
        hashlib.sha256(prompt).hexdigest(),
        schema.schema_id,
        schema.digest,
        manifest.id,
        manifest.manifest_digest,
        manifest.rendered_input_digest,
        schema.output_contract_version,
    )


def _h2_mention_result(
    plan: _ResolvedSegment,
    ledger: Any,
    archive: LocalArchiveStore,
    config: Any,
    runtime: RecordingRuntime,
    tokenizer: DiagnosticTokenizer,
) -> dict[str, Any]:
    bundle = _required_bundle(ledger, plan.representation_id)
    document = ledger.get_document(bundle.representation.document_id)
    if document is None:
        raise ValueError("H2 diagnostic Document is missing.")
    prompt = H2_MENTION_PROMPT_PATH.read_bytes()
    schema = OrganizationMentionTaskSchemaRegistry().resolve("organization_mention_text_v1")
    manifest = build_context_manifest(
        ContextManifestInput(
            plan.unit,
            ContextModelProfile(
                config.model_execution.profile_name or "lm-studio",
                config.model_execution.context_tokens,
                config.model_execution.max_output_tokens,
                256,
            ),
            H2_MENTION_PROMPT_ID,
            prompt,
            schema.schema_id,
            schema.canonical_schema_bytes,
            "paragraph_hypothesis_segment_context_v3",
            PARAGRAPH_HYPOTHESIS_EVIDENCE_SELECTION_V1,
            PARAGRAPH_SEGMENT_V3,
        ),
        ledger,
        tokenizer,
    ).manifest
    base: dict[str, Any] = {
        "source_segment_label": plan.source_segment_label,
        "source_copy_text": _plan_source_copy(plan),
        "prompt_id": H2_MENTION_PROMPT_ID,
        "prompt_digest": hashlib.sha256(prompt).hexdigest(),
        "schema_digest": schema.digest,
        "context_manifest_id": manifest.id,
        "model_run_id": None,
        "raw_output": None,
        "mention_candidates": [],
        "diagnostics": [],
    }
    if manifest.status is not ContextManifestStatus.READY:
        return {**base, "status": "context_not_ready", "execution_spec_digest": None}
    spec = _h2_execution_spec(H2_MENTION_PROMPT_ID, prompt, schema, manifest, config, runtime)
    response_count = len(runtime.responses)
    outcome = run_bounded_extraction(
        BoundedExtractionInput(
            document.source_id,
            document.id,
            plan.representation_id,
            manifest.id,
            prompt,
            spec,
            "organization_mention_validator_v1",
            task_type="organization_mention_extraction",
        ),
        ledger,
        archive,
        runtime,
        Uuid4ModelRunIdFactory(),
        tokenizer,
        OrganizationMentionTaskSchemaRegistry(),
    )
    responses = runtime.responses[response_count:]
    raw_output = responses[0].raw_output.decode("utf-8", errors="replace") if responses else None
    result: dict[str, Any] = {
        **base,
        "model_run_id": outcome.model_run.id,
        "raw_output": raw_output,
        "execution_diagnostics": outcome.model_run.execution_diagnostics,
        "execution_spec_digest": model_execution_spec_digest(spec),
    }
    if outcome.model_run.status.value == "abstained":
        return {
            **result,
            "status": "abstained",
            "diagnostics": [f"abstention_reason:{outcome.model_run.abstention_reason}"],
        }
    if outcome.model_run.status.value != "succeeded":
        return {
            **result,
            "status": "invalid",
            "diagnostics": [
                f"model_run_status:{outcome.model_run.status.value}",
                f"error:{outcome.model_run.error_message}",
            ],
        }
    source_copy = _plan_source_copy(plan)
    mapped: list[H2MentionCandidate] = []
    for mention in outcome.organization_mentions:
        if mention.source_segment_label != plan.source_segment_label:
            return {
                **result,
                "status": "invalid",
                "diagnostics": ["source_segment_label_mismatch"],
            }
        start = source_copy.find(mention.organization_text)
        if start < 0:
            return {
                **result,
                "status": "invalid",
                "diagnostics": [f"mention_not_literal:{mention.organization_text}"],
            }
        mapped.append(
            H2MentionCandidate(
                mention.organization_text, start, start + len(mention.organization_text)
            )
        )
    ordered = tuple(
        sorted(mapped, key=lambda item: (item.source_copy_start, item.organization_text))
    )
    return {
        **result,
        "status": "complete",
        "mention_candidates": [item.__dict__ for item in ordered],
    }


def _mention_candidate_from_value(value: dict[str, Any], source_text: str) -> MentionCandidate:
    observations = tuple(
        MentionProposalObservation(
            proposer_id=str(item["proposer_id"]),
            text=str(item["text"]),
            start=int(item["start"]),
            end=int(item["end"]),
            score=float(item["score"]) if item["score"] is not None else None,
            model_run_id=str(item["model_run_id"]) if item["model_run_id"] is not None else None,
        )
        for item in value["observations"]
    )
    candidate = MentionCandidate(
        id=str(value["id"]),
        source_segment_id=str(value["source_segment_id"]),
        source_text_digest=str(value["source_text_digest"]),
        text=str(value["text"]),
        start=int(value["start"]),
        end=int(value["end"]),
        observations=observations,
    )
    rebuilt = fuse_mention_proposals(
        source_text,
        candidate.source_segment_id,
        observations,
    )
    if len(rebuilt) != 1 or rebuilt[0] != candidate:
        raise ValueError("H2.2 serialized Mention candidate does not match its observations.")
    return candidate


def _h22_qualification_prompt(candidate: MentionCandidate) -> bytes:
    return (
        H22_QUALIFICATION_PROMPT_PATH.read_bytes()
        + b"\n\nMENTION CANDIDATE:\n"
        + candidate.text.encode("utf-8")
        + b"\n"
    )


def _h22_qualification_result(
    plan: _ResolvedSegment,
    candidate: MentionCandidate,
    ledger: Any,
    archive: LocalArchiveStore,
    config: Any,
    runtime: RecordingRuntime,
    tokenizer: DiagnosticTokenizer,
) -> dict[str, Any]:
    source_text = _plan_source_copy(plan)
    if hashlib.sha256(source_text.encode()).hexdigest() != candidate.source_text_digest:
        raise ValueError("H2.2 Mention candidate source digest drifted.")
    if source_text[candidate.start : candidate.end] != candidate.text:
        raise ValueError("H2.2 Mention candidate does not match source characters.")
    bundle = _required_bundle(ledger, plan.representation_id)
    document = ledger.get_document(bundle.representation.document_id)
    if document is None:
        raise ValueError("H2.2 diagnostic Document is missing.")
    prompt = _h22_qualification_prompt(candidate)
    schema = OrganizationQualificationTaskSchemaRegistry().resolve(
        "organization_qualification_text_v1"
    )
    manifest = build_context_manifest(
        ContextManifestInput(
            plan.unit,
            ContextModelProfile(
                config.model_execution.profile_name or "lm-studio",
                config.model_execution.context_tokens,
                config.model_execution.max_output_tokens,
                256,
            ),
            H22_QUALIFICATION_PROMPT_ID,
            prompt,
            schema.schema_id,
            schema.canonical_schema_bytes,
            "paragraph_hypothesis_segment_context_v3",
            PARAGRAPH_HYPOTHESIS_EVIDENCE_SELECTION_V1,
            PARAGRAPH_SEGMENT_V3,
        ),
        ledger,
        tokenizer,
    ).manifest
    base: dict[str, Any] = {
        "candidate_id": candidate.id,
        "candidate_text": candidate.text,
        "candidate_start": candidate.start,
        "candidate_end": candidate.end,
        "prompt_id": H22_QUALIFICATION_PROMPT_ID,
        "prompt_digest": hashlib.sha256(prompt).hexdigest(),
        "schema_digest": schema.digest,
        "context_manifest_id": manifest.id,
        "model_run_id": None,
        "raw_output": None,
        "returned_text": None,
        "diagnostics": [],
        "mention": None,
        "mention_record": None,
    }
    if manifest.status is not ContextManifestStatus.READY:
        return {**base, "status": "invalid", "diagnostics": ["context_not_ready"]}
    spec = _h2_execution_spec(
        H22_QUALIFICATION_PROMPT_ID,
        prompt,
        schema,
        manifest,
        config,
        runtime,
    )
    response_count = len(runtime.responses)
    outcome = run_bounded_extraction(
        BoundedExtractionInput(
            document.source_id,
            document.id,
            plan.representation_id,
            manifest.id,
            prompt,
            spec,
            "organization_qualification_validator_v1",
            task_type="organization_qualification",
        ),
        ledger,
        archive,
        runtime,
        Uuid4ModelRunIdFactory(),
        tokenizer,
        OrganizationQualificationTaskSchemaRegistry(),
    )
    responses = runtime.responses[response_count:]
    raw_output = responses[0].raw_output.decode("utf-8", errors="replace") if responses else None
    result = {
        **base,
        "model_run_id": outcome.model_run.id,
        "raw_output": raw_output,
        "execution_diagnostics": outcome.model_run.execution_diagnostics,
        "execution_spec_digest": model_execution_spec_digest(spec),
    }
    if outcome.model_run.status.value == "abstained":
        resolved = resolve_organization_qualification(
            representation_id=plan.representation_id,
            source_text=source_text,
            candidate=candidate,
            returned_text=None,
            rejected=True,
            model_run_id=outcome.model_run.id,
        )
    elif outcome.model_run.status.value == "succeeded":
        if outcome.organization_qualification is None:
            return {**result, "status": "invalid", "diagnostics": ["judgment_missing"]}
        resolved = resolve_organization_qualification(
            representation_id=plan.representation_id,
            source_text=source_text,
            candidate=candidate,
            returned_text=outcome.organization_qualification.organization_text,
            rejected=False,
            model_run_id=outcome.model_run.id,
        )
    else:
        return {
            **result,
            "status": "invalid",
            "diagnostics": [
                f"model_run_status:{outcome.model_run.status.value}",
                f"error:{outcome.model_run.error_message}",
            ],
        }
    return {
        **result,
        "status": resolved.status.value,
        "returned_text": resolved.returned_text,
        "diagnostics": list(resolved.diagnostics),
        "mention": _validated_mention_value(resolved.mention)
        if resolved.mention is not None
        else None,
        "mention_record": resolved.mention,
    }


def _validated_mention_value(mention: Any) -> dict[str, Any]:
    return {
        "id": mention.id,
        "representation_id": mention.representation_id,
        "source_segment_id": mention.source_segment_id,
        "source_text_digest": mention.source_text_digest,
        "text": mention.text,
        "start": mention.start,
        "end": mention.end,
        "candidate_ids": list(mention.candidate_ids),
        "proposer_ids": list(mention.proposer_ids),
        "qualification_model_run_ids": list(mention.qualification_model_run_ids),
    }


def _organization_identity_value(identity: Any) -> dict[str, Any]:
    return {
        "id": identity.id,
        "representation_id": identity.representation_id,
        "preferred_name": identity.preferred_name,
        "alias_names": list(identity.alias_names),
        "mention_ids": list(identity.mention_ids),
    }


def _alias_decision_value(decision: Any) -> dict[str, Any]:
    return {
        "expression": decision.expression,
        "expanded_name": decision.expanded_name,
        "alias": decision.alias,
        "status": decision.status.value,
    }


def _qualified_pair_value(pair: Any) -> dict[str, Any]:
    return {
        "id": pair.id,
        "source_segment_id": pair.source_segment_id,
        "first_identity_id": pair.first_identity_id,
        "first_organization_text": pair.first_organization_text,
        "second_identity_id": pair.second_identity_id,
        "second_organization_text": pair.second_organization_text,
    }


def _h2_pair_prompt(pair: H2CandidatePair) -> bytes:
    return (
        H2_PAIR_PROMPT_PATH.read_bytes()
        + b"\n\nCANDIDATE PAIR:\n"
        + f"first organization: {pair.first_organization_text}\n".encode()
        + f"second organization: {pair.second_organization_text}\n".encode()
    )


def _h2_pair_judgment(
    plan: _ResolvedSegment,
    pair: H2CandidatePair,
    ledger: Any,
    archive: LocalArchiveStore,
    config: Any,
    runtime: RecordingRuntime,
    tokenizer: DiagnosticTokenizer,
    verifier_prompt: bytes,
) -> dict[str, Any]:
    prompt = _h2_pair_prompt(pair)
    prompt_contract = Php1PromptContract(
        H2_PAIR_PROMPT_ID,
        H2_PAIR_PROMPT_PATH,
        "paragraph_hypothesis_segment_context_v3",
    )
    schema = ParagraphHypothesisTaskSchemaRegistry().resolve("paragraph_hypothesis_text_v1")
    result = _run_segment(
        plan,
        ledger,
        archive,
        config,
        runtime,
        schema,
        prompt,
        verifier_prompt,
        tokenizer,
        True,
        prompt_contract,
    )
    base: dict[str, Any] = {
        "first_organization_text": pair.first_organization_text,
        "second_organization_text": pair.second_organization_text,
        **result,
    }
    if result["status"] == "abstained":
        return {**base, "status": "pair_abstained"}
    if result["status"] != "complete":
        return {**base, "status": "pair_unverified"}
    hypotheses = result["verified_hypotheses"]
    expected = {
        source_copy_view(pair.first_organization_text),
        source_copy_view(pair.second_organization_text),
    }
    if (
        len(hypotheses) != 1
        or {source_copy_view(str(hypothesis["subject_text"])) for hypothesis in hypotheses}
        | {source_copy_view(str(hypothesis["object_text"])) for hypothesis in hypotheses}
        != expected
    ):
        return {**base, "status": "pair_invalid"}
    return {**base, "status": "verified"}


def h2_target_result(
    expectation: Php1Expectation,
    plan: _ResolvedSegment,
    mention_result: dict[str, Any],
    pair_results: tuple[dict[str, Any], ...],
) -> dict[str, Any]:
    base: dict[str, Any] = {
        "expectation_id": expectation.expectation_id,
        "fixture_path": expectation.fixture_path,
        "paragraph_node_id": plan.paragraph_node_id,
        "source_segment_label": plan.source_segment_label,
        "subject_mention_state": "unknown",
        "object_mention_state": "unknown",
        "candidate_pair_state": "not_created",
        "pair_judgment_state": "not_run",
        "target_status": "blocked",
        "diagnostics": [],
        "mention_context_manifest_id": mention_result["context_manifest_id"],
        "mention_model_run_id": mention_result["model_run_id"],
        "pair_model_run_id": None,
    }
    if mention_result["status"] != "complete":
        return {
            **base,
            "subject_mention_state": mention_result["status"],
            "object_mention_state": mention_result["status"],
            "target_status": f"mention_{mention_result['status']}",
            "diagnostics": list(mention_result["diagnostics"]),
        }
    names = {
        source_copy_view(str(item["organization_text"]))
        for item in mention_result["mention_candidates"]
    }
    subject_found = source_copy_view(expectation.subject_text) in names
    object_found = source_copy_view(expectation.object_text) in names
    mention_fields = {
        "subject_mention_state": "present" if subject_found else "missing",
        "object_mention_state": "present" if object_found else "missing",
    }
    if not subject_found:
        return {**base, **mention_fields, "target_status": "subject_mention_missing"}
    if not object_found:
        return {**base, **mention_fields, "target_status": "object_mention_missing"}
    expected_pair = {
        source_copy_view(expectation.subject_text),
        source_copy_view(expectation.object_text),
    }
    judgments = tuple(
        item
        for item in pair_results
        if {
            source_copy_view(str(item["first_organization_text"])),
            source_copy_view(str(item["second_organization_text"])),
        }
        == expected_pair
    )
    if len(judgments) != 1:
        return {**base, **mention_fields, "target_status": "candidate_pair_missing"}
    judgment = judgments[0]
    judgment_fields = {
        "candidate_pair_state": "present",
        "pair_judgment_state": judgment["status"],
        "pair_model_run_id": judgment["model_run_id"],
    }
    if judgment["status"] != "verified":
        return {
            **base,
            **mention_fields,
            **judgment_fields,
            "target_status": judgment["status"],
        }
    matches = tuple(
        item
        for item in judgment["verified_hypotheses"]
        if source_copy_view(str(item["subject_text"])) == source_copy_view(expectation.subject_text)
        and source_copy_view(str(item["object_text"])) == source_copy_view(expectation.object_text)
    )
    if not matches:
        return {
            **base,
            **mention_fields,
            **judgment_fields,
            "target_status": "pair_mismatched",
        }
    return {
        **base,
        **mention_fields,
        **judgment_fields,
        "target_status": "matched",
        "matched_model_run_ids": [judgment["model_run_id"]],
        "matched_proposed_change_ids": [str(item["proposed_change_id"]) for item in matches],
    }


def _h2_unexpected_hypotheses(
    pair_results: dict[tuple[str, str, str], tuple[dict[str, Any], ...]],
    expectations: tuple[Php1Expectation, ...],
) -> list[dict[str, Any]]:
    expected_pairs = {
        (
            expectation.fixture_path,
            source_copy_view(expectation.subject_text),
            source_copy_view(expectation.object_text),
        )
        for expectation in expectations
    }
    unexpected: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str, str]] = set()
    for key, judgments in sorted(pair_results.items()):
        fixture_path, paragraph_node_id, source_segment_label = key
        for judgment in judgments:
            for hypothesis in judgment["verified_hypotheses"]:
                subject_text = str(hypothesis["subject_text"])
                object_text = str(hypothesis["object_text"])
                identity = (
                    fixture_path,
                    source_copy_view(subject_text),
                    source_copy_view(object_text),
                )
                if identity in expected_pairs:
                    continue
                unique_key = (
                    fixture_path,
                    paragraph_node_id,
                    source_segment_label,
                    subject_text,
                    object_text,
                )
                if unique_key in seen:
                    continue
                seen.add(unique_key)
                unexpected.append(
                    {
                        "fixture_path": fixture_path,
                        "paragraph_node_id": paragraph_node_id,
                        "source_segment_label": source_segment_label,
                        "subject_text": subject_text,
                        "relation_text": hypothesis["relation_text"],
                        "object_text": object_text,
                        "model_run_id": judgment["model_run_id"],
                        "proposed_change_id": hypothesis["proposed_change_id"],
                    }
                )
    return unexpected


def _case_result_from_segments(
    case: Php1DiagnosticCase,
    plans: tuple[_ResolvedSegment, ...],
    segment_results: dict[tuple[str, str, str], dict[str, Any]],
    include_raw_output: bool,
) -> dict[str, Any]:
    segments = [segment_results[plan.key] for plan in plans]
    statuses = {item["status"] for item in segments}
    status = diagnostic_case_status(statuses)
    limit_records = tuple(
        evaluate_eight_claim_limit(
            item["raw_output"],
            str(case.metadata.get("provisional_eligibility", "")),
        )
        for item in segments
    )
    measurable = tuple(record for record in limit_records if record["state"] == "measured")
    return {
        "case_id": case.case_id,
        **case.metadata,
        "status": status,
        "node_id": plans[0].paragraph_node_id,
        "paragraph_text": plans[0].paragraph_text if include_raw_output else None,
        "segments": segments,
        "eight_claim_evaluation": {
            "state": "measured" if measurable else limit_records[0]["state"],
            "excess_claim_line_count": sum(
                int(record["excess_claim_line_count"]) for record in measurable
            ),
        },
    }


def _target_report(
    expectations: tuple[Php1Expectation, ...],
    resolutions: dict[str, dict[str, Any]],
    segment_results: dict[tuple[str, str, str], dict[str, Any]],
) -> dict[str, Any]:
    target_results: list[dict[str, Any]] = []
    matched_hypotheses: set[tuple[tuple[str, str, str], str, str]] = set()
    for expectation in expectations:
        resolution = resolutions[expectation.expectation_id]
        diagnostics = list(resolution["diagnostics"])
        base = {
            "expectation_id": expectation.expectation_id,
            "case_ids": list(expectation.case_ids),
            "fixture_path": expectation.fixture_path,
            "relationship_shape": expectation.relationship_shape,
            "resolution_status": resolution["resolution_status"],
            "matched_model_run_ids": [],
            "matched_proposed_change_ids": [],
            "prompt_digest": None,
            "schema_digest": None,
            "execution_spec_digest": None,
        }
        plan = resolution.get("plan")
        if not isinstance(plan, _ResolvedSegment):
            target_results.append({**base, "target_status": None, "diagnostics": diagnostics})
            continue
        segment = segment_results[plan.key]
        base.update(
            {
                "paragraph_node_id": plan.paragraph_node_id,
                "source_segment_label": plan.source_segment_label,
                "prompt_digest": segment["prompt_digest"],
                "schema_digest": segment["schema_digest"],
                "execution_spec_digest": segment["execution_spec_digest"],
            }
        )
        matches = tuple(
            hypothesis
            for hypothesis in segment["verified_hypotheses"]
            if _hypothesis_matches_expectation(hypothesis, expectation)
        )
        if matches:
            for hypothesis in matches:
                matched_hypotheses.add(
                    (
                        plan.key,
                        str(hypothesis["subject_text"]),
                        str(hypothesis["object_text"]),
                    )
                )
            target_results.append(
                {
                    **base,
                    "target_status": "matched",
                    "matched_model_run_ids": [segment["model_run_id"]],
                    "matched_proposed_change_ids": sorted(
                        str(hypothesis["proposed_change_id"]) for hypothesis in matches
                    ),
                    "diagnostics": diagnostics,
                }
            )
            continue
        target_status = (
            "missing"
            if segment["status"] in {"complete", "abstained", "faithfulness_rejected"}
            else "blocked"
        )
        diagnostics.append(f"source_segment_status:{segment['status']}")
        target_results.append({**base, "target_status": target_status, "diagnostics": diagnostics})

    unexpected: list[dict[str, Any]] = []
    unexpected_keys: set[tuple[tuple[str, str, str], str, str, str]] = set()
    for key, segment in sorted(segment_results.items()):
        fixture_path, paragraph_node_id, source_segment_label = key
        for hypothesis in segment["verified_hypotheses"]:
            hypothesis_key = (
                key,
                str(hypothesis["subject_text"]),
                str(hypothesis["object_text"]),
            )
            if hypothesis_key in matched_hypotheses:
                continue
            unexpected_key = (
                key,
                str(hypothesis["subject_text"]),
                str(hypothesis["relation_text"]),
                str(hypothesis["object_text"]),
            )
            if unexpected_key in unexpected_keys:
                continue
            unexpected_keys.add(unexpected_key)
            unexpected.append(
                {
                    "source_fixture_path": fixture_path,
                    "paragraph_node_id": paragraph_node_id,
                    "source_segment_label": source_segment_label,
                    "subject_text": hypothesis["subject_text"],
                    "relation_text": hypothesis["relation_text"],
                    "object_text": hypothesis["object_text"],
                    "model_run_id": segment["model_run_id"],
                    "proposed_change_ids": [hypothesis["proposed_change_id"]],
                }
            )
    return {
        "target_results": target_results,
        "unexpected_hypotheses": unexpected,
    }


def _hypothesis_matches_expectation(
    hypothesis: dict[str, Any], expectation: Php1Expectation
) -> bool:
    return source_copy_view(str(hypothesis["subject_text"])) == source_copy_view(
        expectation.subject_text
    ) and source_copy_view(str(hypothesis["object_text"])) == source_copy_view(
        expectation.object_text
    )


def _paragraphs_for_anchor(bundle: Any, anchor: str) -> tuple[tuple[str, str], ...]:
    text_views = {item.id: item.text for item in bundle.text_views}
    return tuple(
        (node.id, text_views[node.text_view_id][node.start_char : node.end_char])
        for node in bundle.nodes
        if node.node_type == "paragraph"
        and _anchor_matches(text_views[node.text_view_id][node.start_char : node.end_char], anchor)
    )


def _first_paragraph_for_anchor(bundle: Any, anchor: str) -> tuple[str, str] | None:
    paragraphs = _paragraphs_for_anchor(bundle, anchor)
    return paragraphs[0] if paragraphs else None


def _anchor_matches(text: str, anchor: str) -> bool:
    normalized_text = " ".join(text.split())
    cursor = 0
    for part in anchor.split("..."):
        normalized_part = " ".join(part.split())
        position = normalized_text.find(normalized_part, cursor)
        if position < 0:
            return False
        cursor = position + len(normalized_part)
    return True


def _progress(event: dict[str, Any]) -> None:
    print(json.dumps(event, sort_keys=True), file=sys.stderr, flush=True)


def _ledger_init(ledger_path: Path, archive_path: Path) -> None:
    with redirect_stdout(StringIO()):
        exit_code = main(
            [
                "ledger",
                "init",
                "--ledger-path",
                str(ledger_path),
                "--archive-path",
                str(archive_path),
            ]
        )
    if exit_code != 0:
        raise ValueError("PHP-1 diagnostic Ledger initialization failed.")


def _source_add(config: Path, ledger: Path, archive: Path, path: Path, url: str) -> dict[str, Any]:
    stream = StringIO()
    with redirect_stdout(stream):
        exit_code = main(
            [
                "--config",
                str(config),
                "source",
                "add-file",
                str(path),
                "--source-url",
                url,
                "--ledger-path",
                str(ledger),
                "--archive-path",
                str(archive),
                "--format",
                "json",
            ]
        )
    if exit_code != 0:
        raise ValueError(f"PHP-1 diagnostic could not ingest {path.name}.")
    return json.loads(stream.getvalue())
