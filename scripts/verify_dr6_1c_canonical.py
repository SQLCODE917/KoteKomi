"""Verify DR-6.1C temporal evidence graph views with the locked deposited PDF."""

from __future__ import annotations

import json
import re
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from kotekomi_adapters import sqlite_ledger_transaction
from kotekomi_application import (
    ReviewProposedChangeInput,
    approve_proposed_change,
    verify_context_manifest,
)
from kotekomi_domain import (
    Assertion,
    AssertionStatus,
    AssertionType,
    AttributionBasis,
    EpistemicScope,
    EvidenceTarget,
    EvidenceValidationAttempt,
    EvidenceValidationAttemptStatus,
    Organization,
    ProposedChange,
    Relationship,
    ReviewStatus,
    SourceAuthority,
    canonical_evidence_target_digest,
)
from verify_dr5_canonical import (
    ROOT,
    ConformanceError,
    command_json,
    config_text,
    fixture_path,
    read_json,
    run_command,
    validate_json,
)

type JsonObject = dict[str, Any]

SUITE_SCHEMA_PATH = ROOT / ".agent/schemas/evidence-graph-temporal-suite-v1.schema.json"
QUERY_CASE_SCHEMA_PATH = ROOT / ".agent/schemas/evidence-graph-temporal-query-case-v1.schema.json"
SEED_SCHEMA_PATH = ROOT / ".agent/schemas/evidence-graph-temporal-seed-v1.schema.json"
PROMPT_BYTES = b"Use only the supplied original source evidence."
SCHEMA_BYTES = b'{"type":"object"}'


class VerificationTokenizer:
    tokenizer_id = "retrieval_validation_whitespace_v1"

    def count_tokens(self, rendered_input: bytes) -> int:
        return len(rendered_input.decode("utf-8").split())


def run() -> JsonObject:
    scenario = read_json(ROOT / ".agent/scenarios/anthropic-dod-dispute-v1/scenario.json")
    suite = read_json(ROOT / ".agent/scenarios/anthropic-dod-dispute-v1/suites/dr-6-1c-v1.json")
    validate_json(suite, SUITE_SCHEMA_PATH, "temporal_suite_schema_invalid")
    seed = read_json(ROOT / str(suite["seed_path"]))
    validate_json(seed, SEED_SCHEMA_PATH, "temporal_seed_schema_invalid")
    cases = _query_cases(suite)
    fixture = fixture_path(scenario)
    with tempfile.TemporaryDirectory(prefix="kotekomi-dr6-1c-") as temporary:
        root = Path(temporary)
        ledger_path = root / "ledger.sqlite"
        archive_path = root / "archive"
        config_path = root / "kotekomi.toml"
        config_path.write_text(config_text(ledger_path, archive_path), encoding="utf-8")
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
        representation_id = _required(ingest, "representation_id")
        targets = _seed_temporal_correction(ledger_path, representation_id, seed)
        results = {
            str(case["query_id"]): _build_and_explain_case(ledger_path, case, targets)
            for case in cases
        }
        historical = next(case for case in cases if case["view_kind"] == "as_of")
        rebuilt = command_json(
            "retrieval",
            "build-graph-evidence",
            "--ledger-path",
            str(ledger_path),
            "--as-of",
            str(historical["as_of"]),
            "--rebuild",
            "--format",
            "json",
        )
        _complete(rebuilt, "temporal_rebuild_failed")
        repeated = _build_and_explain_case(ledger_path, historical, targets)
        initial = results[str(historical["query_id"])]
        if (
            initial["explanation_id"] != repeated["explanation_id"]
            or initial["contributions"] != repeated["contributions"]
        ):
            raise ConformanceError(
                "temporal_rebuild_mismatch",
                "Rebuilding the as-of view changed its explanation.",
            )
        current = next(case for case in cases if case["view_kind"] == "current")
        preserved_current = _build_and_explain_case(ledger_path, current, targets)
        current_result = results[str(current["query_id"])]
        if preserved_current["explanation_id"] != current_result["explanation_id"]:
            raise ConformanceError(
                "current_view_changed", "Rebuilding the as-of view changed the current view."
            )
        return {
            "status": "passed",
            "representation_id": representation_id,
            "as_of_manifest_id": initial["projection_manifest_id"],
            "current_manifest_id": results[str(current["query_id"])]["projection_manifest_id"],
            "as_of_explanation_id": initial["explanation_id"],
            "current_explanation_id": results[str(current["query_id"])]["explanation_id"],
        }


def _query_cases(suite: JsonObject) -> tuple[JsonObject, ...]:
    cases: list[JsonObject] = []
    for relative_path in cast(list[str], suite["query_pack_paths"]):
        for line in (ROOT / relative_path).read_text(encoding="utf-8").splitlines():
            if line.strip():
                case = cast(JsonObject, json.loads(line))
                validate_json(case, QUERY_CASE_SCHEMA_PATH, "temporal_case_schema_invalid")
                cases.append(case)
    if len(cases) != 2:
        raise ConformanceError(
            "temporal_case_count_invalid", "The suite requires two temporal cases."
        )
    return tuple(cases)


def _seed_temporal_correction(
    ledger_path: Path, representation_id: str, seed: JsonObject
) -> dict[str, EvidenceTarget]:
    initial_time = _timestamp(seed, "initial_reviewed_at")
    correction_time = _timestamp(seed, "correction_reviewed_at")
    cutoff = _timestamp(seed, "as_of")
    if not initial_time < cutoff < correction_time:
        raise ConformanceError(
            "temporal_seed_invalid", "The as_of timestamp must fall between the two reviews."
        )
    with sqlite_ledger_transaction(ledger_path) as ledger:
        bundle = ledger.get_document_representation_bundle(representation_id)
        if bundle is None:
            raise ConformanceError(
                "representation_missing", "The public ingest did not persist a representation."
            )
        document = ledger.get_document(bundle.representation.document_id)
        if document is None:
            raise ConformanceError("document_missing", "The representation Document is missing.")
        _approve(
            ledger,
            "pcg_org_anthropic",
            Organization(id="org_anthropic", name="Anthropic"),
            initial_time,
        )
        _approve(
            ledger,
            "pcg_org_department",
            Organization(
                id="org_us_department_of_defense", name="United States Department of Defense"
            ),
            initial_time,
        )
        initial_spec = cast(JsonObject, seed["initial"])
        corrected_spec = cast(JsonObject, seed["corrected"])
        initial_target = _target(bundle, document.id, document.source_id, initial_spec)
        corrected_target = _target(bundle, document.id, document.source_id, corrected_spec)
        _approve(ledger, "pcg_temporal_target_initial", initial_target, initial_time)
        _validate(ledger, "eva_temporal_initial", initial_target, initial_time)
        initial_assertion = _assertion(initial_spec, initial_target, document.source_id)
        _approve(
            ledger,
            "pcg_temporal_assertion_initial",
            initial_assertion,
            initial_time,
            evidence_target_id=initial_target.id,
            validation_attempt_id="eva_temporal_initial",
        )
        _approve(
            ledger,
            "pcg_temporal_relationship_initial",
            _relationship(initial_spec, initial_assertion.id),
            initial_time,
        )
        _approve(ledger, "pcg_temporal_target_corrected", corrected_target, correction_time)
        _validate(ledger, "eva_temporal_corrected", corrected_target, correction_time)
        corrected_assertion = _assertion(
            corrected_spec,
            corrected_target,
            document.source_id,
            supersedes_assertion_id=initial_assertion.id,
        )
        _approve(
            ledger,
            "pcg_temporal_assertion_corrected",
            corrected_assertion,
            correction_time,
            evidence_target_id=corrected_target.id,
            validation_attempt_id="eva_temporal_corrected",
        )
        _approve(
            ledger,
            "pcg_temporal_relationship_corrected",
            _relationship(corrected_spec, corrected_assertion.id),
            correction_time,
        )
    return {initial_target.id: initial_target, corrected_target.id: corrected_target}


def _target(
    bundle: Any, document_id: str, source_id: str, specification: JsonObject
) -> EvidenceTarget:
    anchor = str(specification["anchor_text"])
    node = next(
        (
            item
            for item in bundle.nodes
            if _normalize(anchor) in _normalize(_node_text(bundle, item.id))
        ),
        None,
    )
    if node is None:
        raise ConformanceError("temporal_anchor_missing", f"Missing PDF anchor: {anchor}")
    view = next(item for item in bundle.text_views if item.id == node.text_view_id)
    return EvidenceTarget(
        id=str(specification["evidence_target_id"]),
        source_id=source_id,
        document_id=document_id,
        representation_id=bundle.representation.id,
        text_view_id=view.id,
        text_view_digest=view.content_digest,
        start_char=node.start_char,
        end_char=node.end_char,
        exact_text=_node_text(bundle, node.id),
        normalization_policy=view.normalization_policy,
        node_ids=(node.id,),
    )


def _assertion(
    specification: JsonObject,
    target: EvidenceTarget,
    source_id: str,
    *,
    supersedes_assertion_id: str | None = None,
) -> Assertion:
    return Assertion(
        id=str(specification["assertion_id"]),
        assertion_type=AssertionType.SOURCE_CLAIM,
        epistemic_scope=EpistemicScope.SOURCE_REPORT,
        subject_entity_id="org_anthropic",
        predicate="contract_requirement",
        object_value=str(specification["object_value"]),
        status=AssertionStatus.PROPOSED,
        source_authority=SourceAuthority.SECONDARY,
        attribution_basis=AttributionBasis.REPORTED_BY_SOURCE,
        source_ids=(source_id,),
        evidence_target_ids=(target.id,),
        supersedes_assertion_id=supersedes_assertion_id,
    )


def _relationship(specification: JsonObject, assertion_id: str) -> Relationship:
    return Relationship(
        id=str(specification["relationship_id"]),
        subject_id="org_anthropic",
        predicate="contract_requirement",
        object_id="org_us_department_of_defense",
        assertion_ids=(assertion_id,),
    )


def _validate(ledger: Any, attempt_id: str, target: EvidenceTarget, attempted_at: datetime) -> None:
    ledger.save_evidence_validation_attempt(
        EvidenceValidationAttempt(
            id=attempt_id,
            evidence_target_id=target.id,
            target_digest=canonical_evidence_target_digest(target),
            validator_version="dr6_1c_canonical_v1",
            status=EvidenceValidationAttemptStatus.SUCCEEDED,
            attempted_at=attempted_at,
        )
    )


def _approve(
    ledger: Any,
    change_id: str,
    record: Organization | EvidenceTarget | Assertion | Relationship,
    reviewed_at: datetime,
    *,
    evidence_target_id: str | None = None,
    validation_attempt_id: str | None = None,
) -> None:
    proposed: JsonObject = {
        "record_type": type(record).__name__,
        "stable_label": change_id,
        "record": record.model_dump(mode="json"),
    }
    if evidence_target_id is not None and validation_attempt_id is not None:
        proposed["evidence_links"] = [
            {
                "evidence_target_id": evidence_target_id,
                "validation_attempt_id": validation_attempt_id,
                "role": "direct_support",
                "polarity": "supports",
                "necessity": "required",
            }
        ]
    ledger.save_proposed_change(
        ProposedChange(
            id=change_id,
            review_status=ReviewStatus.PENDING,
            proposed_json=proposed,
            provenance_activity_id="prv_temporal_seed",
            created_at=reviewed_at,
            updated_at=reviewed_at,
        )
    )
    approve_proposed_change(
        ReviewProposedChangeInput(
            proposed_change_id=change_id,
            reviewer="dr6-1c-canonical",
            reviewed_at=reviewed_at,
        ),
        ledger,
    )


def _build_and_explain_case(
    ledger_path: Path, case: JsonObject, targets: dict[str, EvidenceTarget]
) -> JsonObject:
    view_args = (
        ("--as-of", str(case["as_of"])) if case["view_kind"] == "as_of" else ()
    )
    built = command_json(
        "retrieval",
        "build-graph-evidence",
        "--ledger-path",
        str(ledger_path),
        *view_args,
        "--format",
        "json",
    )
    _complete(built, "temporal_graph_build_failed")
    explanation = command_json(
        "retrieval",
        "explain-graph-relationship",
        "--ledger-path",
        str(ledger_path),
        "--relationship-id",
        str(case["relationship_id"]),
        "--context-profile",
        "retrieval-validation-v1",
        *view_args,
        "--format",
        "json",
    )
    _complete(explanation, "temporal_graph_explain_failed")
    actual_as_of = _canonical_timestamp_text(explanation["as_of"])
    if explanation["view_kind"] != case["view_kind"] or actual_as_of != case["as_of"]:
        raise ConformanceError(
            "temporal_view_mismatch",
            f"Expected {case['view_kind']} {case['as_of']}; got "
            f"{explanation['view_kind']} {actual_as_of}.",
        )
    contributions = cast(list[JsonObject], explanation["contributions"])
    terminal_ids = {item for row in contributions for item in row["terminal_assertion_ids"]}
    target_ids = {item for row in contributions for item in row["evidence_target_ids"]}
    if not set(cast(list[str], case["required_terminal_assertion_ids"])).issubset(terminal_ids):
        raise ConformanceError(
            "temporal_terminal_missing", "The explanation omitted a temporal Assertion."
        )
    if not set(cast(list[str], case["required_evidence_target_ids"])).issubset(target_ids):
        raise ConformanceError(
            "temporal_target_missing", "The explanation omitted source evidence."
        )
    _verify_contexts(
        ledger_path,
        cast(list[JsonObject], explanation["context_results"]),
        str(case["required_anchor_text"]),
        tuple(targets[target_id].node_ids[0] for target_id in target_ids),
    )
    return explanation


def _verify_contexts(
    ledger_path: Path,
    contexts: list[JsonObject],
    anchor: str,
    required_node_ids: tuple[str, ...],
) -> None:
    if not contexts or any(item.get("status") != "ready" for item in contexts):
        raise ConformanceError(
            "temporal_context_missing", "The explanation has no ready source context."
        )
    with sqlite_ledger_transaction(ledger_path) as ledger:
        for context in contexts:
            focus_node_ids = set(cast(list[str], context["focus_node_ids"]))
            if not set(required_node_ids).issubset(focus_node_ids):
                raise ConformanceError(
                    "temporal_focus_missing", "Context omitted an EvidenceTarget node."
                )
            manifest_id = context.get("context_manifest_id")
            if not isinstance(manifest_id, str):
                raise ConformanceError(
                    "temporal_manifest_missing", "Context omitted its manifest ID."
                )
            manifest = verify_context_manifest(
                manifest_id,
                ledger,
                VerificationTokenizer(),
                PROMPT_BYTES,
                SCHEMA_BYTES,
            ).manifest
            if _normalize(anchor) not in _normalize(manifest.rendered_input.decode("utf-8")):
                raise ConformanceError(
                    "temporal_anchor_missing", "Context omitted the locked PDF anchor."
                )


def _node_text(bundle: Any, node_id: str) -> str:
    node = next(item for item in bundle.nodes if item.id == node_id)
    view = next(item for item in bundle.text_views if item.id == node.text_view_id)
    return view.text[node.start_char : node.end_char]


def _timestamp(seed: JsonObject, key: str) -> datetime:
    value = seed.get(key)
    if not isinstance(value, str):
        raise ConformanceError("temporal_seed_invalid", f"Missing timestamp: {key}")
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def _canonical_timestamp_text(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ConformanceError("temporal_view_invalid", "The explanation as_of value is invalid.")
    return value.replace("+00:00", "Z")


def _complete(payload: JsonObject, code: str) -> None:
    if payload.get("status") != "complete":
        raise ConformanceError(code, str(payload.get("failure")))


def _required(payload: JsonObject, key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str):
        raise ConformanceError("public_command_invalid", f"Missing string field: {key}")
    return value


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().lower()


if __name__ == "__main__":
    try:
        print(json.dumps(run(), sort_keys=True))
    except ConformanceError as error:
        print(json.dumps({"status": "failed", "failure": error.code, "message": str(error)}))
        raise SystemExit(1) from None
