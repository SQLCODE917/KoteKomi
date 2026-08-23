"""Verify DR-6.1B reviewed cross-source lineage with the locked deposited PDF."""

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
    EvidenceTarget,
    EvidenceValidationAttempt,
    EvidenceValidationAttemptStatus,
    ProposedChange,
    Relationship,
    ReviewStatus,
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
    seed_ledger,
)

type JsonObject = dict[str, Any]
PROMPT_BYTES = b"Use only the supplied original source evidence."
SCHEMA_BYTES = b'{"type":"object"}'


class VerificationTokenizer:
    tokenizer_id = "retrieval_validation_whitespace_v1"

    def count_tokens(self, rendered_input: bytes) -> int:
        return len(rendered_input.decode("utf-8").split())


def run() -> JsonObject:
    scenario = read_json(ROOT / ".agent/scenarios/anthropic-dod-dispute-v1/scenario.json")
    fixture = fixture_path(scenario)
    source = cast(JsonObject, scenario["source"])
    lineage = cast(JsonObject, scenario["lineage"])
    reprint_source = cast(JsonObject, lineage["reprint_source"])
    seed = read_json(ROOT / ".agent/scenarios/anthropic-dod-dispute-v1/ledger-seed-v1.json")
    with tempfile.TemporaryDirectory(prefix="kotekomi-dr6-1b-") as temporary:
        root = Path(temporary)
        ledger_path = root / "ledger.sqlite"
        archive_path = root / "archive"
        config_path = root / "kotekomi.toml"
        config_path.write_text(config_text(ledger_path, archive_path), encoding="utf-8")
        run_command(
            "--config", str(config_path), "ledger", "init", "--ledger-path", str(ledger_path)
        )
        primary = _ingest(config_path, ledger_path, fixture, str(source["normalized_url"]))
        reprint = _ingest(config_path, ledger_path, fixture, str(reprint_source["normalized_url"]))
        if (
            primary["source_id"] == reprint["source_id"]
            or primary["document_id"] == reprint["document_id"]
        ):
            raise ConformanceError(
                "source_identity_collapsed", "Two declared source URLs must create two Documents."
            )
        seed_ledger(ledger_path, _required(primary, "representation_id"), seed)
        _seed_reprint_evidence(ledger_path, _required(reprint, "representation_id"), seed)
        _approve_two_source_relationship(ledger_path)
        proposed = command_json(
            "lineage",
            "propose-verbatim-republication",
            "--ledger-path",
            str(ledger_path),
            "--document-id",
            _required(primary, "document_id"),
            "--document-id",
            _required(reprint, "document_id"),
            "--proposer",
            "dr6-1b-canonical",
            "--rationale",
            "Both declared sources deposited the same locked PDF bytes.",
            "--format",
            "json",
        )
        if proposed.get("status") != "pending":
            raise ConformanceError("lineage_proposal_failed", str(proposed.get("failure")))
        proposal_id = _required(proposed, "proposed_change_id")
        run_command(
            "review",
            "approve",
            "--ledger-path",
            str(ledger_path),
            "--proposed-change-id",
            proposal_id,
            "--reviewer",
            "dr6-1b-reviewer",
        )
        with sqlite_ledger_transaction(ledger_path) as ledger:
            if len(ledger.list_raw_blobs()) != 1:
                raise ConformanceError(
                    "raw_blob_not_reused", "Identical deposited bytes must reuse RawBlob."
                )
            if len(ledger.list_source_lineage_relations()) != 1:
                raise ConformanceError(
                    "lineage_relation_missing", "Approved source lineage relation is missing."
                )
            if (
                ledger.get_document_representation_bundle(_required(primary, "representation_id"))
                is None
            ):
                raise ConformanceError(
                    "primary_representation_missing", "Primary representation did not reload."
                )
            if (
                ledger.get_document_representation_bundle(_required(reprint, "representation_id"))
                is None
            ):
                raise ConformanceError(
                    "reprint_representation_missing", "Reprint representation did not reload."
                )
        built = command_json(
            "retrieval",
            "build-graph-evidence",
            "--ledger-path",
            str(ledger_path),
            "--format",
            "json",
        )
        _complete(built, "evidence_graph_build_failed")
        explanation = _explain(ledger_path)
        _validate_explanation(explanation, ledger_path, primary, reprint)
        rebuilt = command_json(
            "retrieval",
            "build-graph-evidence",
            "--ledger-path",
            str(ledger_path),
            "--rebuild",
            "--format",
            "json",
        )
        _complete(rebuilt, "evidence_graph_rebuild_failed")
        repeated = _explain(ledger_path)
        if (
            explanation["contributions"] != repeated["contributions"]
            or explanation["lineage_clusters"] != repeated["lineage_clusters"]
        ):
            raise ConformanceError(
                "lineage_rebuild_mismatch", "Rebuild changed the lineage explanation."
            )
        return {
            "status": "passed",
            "primary_document_id": primary["document_id"],
            "reprint_document_id": reprint["document_id"],
            "projection_manifest_id": rebuilt["projection_manifest_id"],
            "lineage_cluster_count": repeated["lineage_cluster_count"],
        }


def _ingest(config_path: Path, ledger_path: Path, fixture: Path, source_url: str) -> JsonObject:
    return command_json(
        "--config",
        str(config_path),
        "source",
        "add-file",
        str(fixture),
        "--source-url",
        source_url,
        "--ledger-path",
        str(ledger_path),
        "--format",
        "json",
    )


def _seed_reprint_evidence(ledger_path: Path, representation_id: str, seed: JsonObject) -> None:
    with sqlite_ledger_transaction(ledger_path) as ledger:
        bundle = ledger.get_document_representation_bundle(representation_id)
        if bundle is None:
            raise ConformanceError(
                "reprint_representation_missing", "Reprint representation is missing."
            )
        anchor = _normalize(str(seed["evidence_anchor"]))
        node = next(
            (item for item in bundle.nodes if anchor in _normalize(_node_text(item.id, bundle))),
            None,
        )
        if node is None:
            raise ConformanceError("reprint_anchor_missing", "Reprint omits Directive 3000.09.")
        document = ledger.get_document(bundle.representation.document_id)
        view = next(item for item in bundle.text_views if item.id == node.text_view_id)
        if document is None:
            raise ConformanceError("reprint_document_missing", "Reprint Document is missing.")
        evidence = EvidenceTarget(
            id="etg_directive_reprint",
            source_id=document.source_id,
            document_id=document.id,
            representation_id=representation_id,
            text_view_id=view.id,
            text_view_digest=view.content_digest,
            start_char=node.start_char,
            end_char=node.end_char,
            exact_text=_node_text(node.id, bundle),
            normalization_policy=view.normalization_policy,
            node_ids=(node.id,),
        )
        _approve(ledger, "pcg_evidence_reprint", "EvidenceTarget", evidence.model_dump(mode="json"))
        ledger.save_evidence_validation_attempt(
            EvidenceValidationAttempt(
                id="eva_directive_reprint",
                evidence_target_id=evidence.id,
                target_digest=canonical_evidence_target_digest(evidence),
                validator_version="dr6-1b-canonical-v1",
                status=EvidenceValidationAttemptStatus.SUCCEEDED,
            )
        )
        _approve(
            ledger,
            "pcg_assertion_reprint",
            "Assertion",
            {
                "id": "ast_directive_reprint",
                "assertion_type": "source_claim",
                "epistemic_scope": "source_report",
                "subject_entity_id": "org_anthropic",
                "predicate": "is_subject_to_policy",
                "object_value": "Directive 3000.09",
                "status": "reported",
                "source_authority": "secondary",
                "attribution_basis": "reported_by_source",
                "source_ids": [document.source_id],
                "evidence_target_ids": [evidence.id],
                "provenance_activity_ids": [],
            },
            evidence.id,
            "eva_directive_reprint",
        )


def _approve_two_source_relationship(ledger_path: Path) -> None:
    with sqlite_ledger_transaction(ledger_path) as ledger:
        _approve(
            ledger,
            "pcg_relation_two_sources",
            "Relationship",
            Relationship(
                id="rel_anthropic_policy_two_sources",
                subject_id="org_anthropic",
                predicate="is_subject_to_policy",
                object_id="org_us_department_of_defense",
                assertion_ids=("ast_directive_current", "ast_directive_reprint"),
            ).model_dump(mode="json"),
        )


def _explain(ledger_path: Path) -> JsonObject:
    payload = command_json(
        "retrieval",
        "explain-graph-relationship",
        "--ledger-path",
        str(ledger_path),
        "--relationship-id",
        "rel_anthropic_policy_two_sources",
        "--context-profile",
        "retrieval-validation-v1",
        "--format",
        "json",
    )
    _complete(payload, "evidence_graph_explain_failed")
    return payload


def _validate_explanation(
    explanation: JsonObject, ledger_path: Path, primary: JsonObject, reprint: JsonObject
) -> None:
    documents = {
        document_id
        for contribution in cast(list[JsonObject], explanation["contributions"])
        for document_id in cast(list[str], contribution["source_document_ids"])
    }
    expected = {_required(primary, "document_id"), _required(reprint, "document_id")}
    if documents != expected:
        raise ConformanceError(
            "contributing_documents_mismatch", "Explanation lost a contributing Document."
        )
    clusters = cast(list[JsonObject], explanation["lineage_clusters"])
    if explanation.get("raw_document_count") != 2 or explanation.get("lineage_cluster_count") != 1:
        raise ConformanceError(
            "lineage_counts_invalid", "Explanation did not expose two Documents and one cluster."
        )
    if len(clusters) != 1 or clusters[0].get("cross_source_relation_state") != "recorded_relation":
        raise ConformanceError("recorded_cluster_missing", "Reviewed lineage cluster is missing.")
    _verify_contexts(ledger_path, cast(list[JsonObject], explanation["context_results"]))


def _complete(payload: JsonObject, code: str) -> None:
    if payload.get("status") != "complete":
        raise ConformanceError(code, str(payload.get("failure")))


def _approve(
    ledger: Any,
    change_id: str,
    record_type: str,
    record: JsonObject,
    evidence_id: str | None = None,
    validation_attempt_id: str = "eva_directive",
) -> None:
    proposed: JsonObject = {"record_type": record_type, "stable_label": change_id, "record": record}
    if evidence_id is not None:
        proposed["evidence_links"] = [
            {
                "evidence_target_id": evidence_id,
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
            provenance_activity_id="prv_dr6_1b_seed",
        )
    )
    approve_proposed_change(
        ReviewProposedChangeInput(
            proposed_change_id=change_id,
            reviewer="dr6-1b-canonical",
            reviewed_at=datetime(2026, 8, 23, tzinfo=UTC),
        ),
        ledger,
    )


def _node_text(node_id: str, bundle: Any) -> str:
    node = next(item for item in bundle.nodes if item.id == node_id)
    view = next(item for item in bundle.text_views if item.id == node.text_view_id)
    return view.text[node.start_char : node.end_char]


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().lower()


def _verify_contexts(ledger_path: Path, contexts: list[JsonObject]) -> None:
    if not contexts or any(item.get("status") != "ready" for item in contexts):
        raise ConformanceError(
            "evidence_graph_context_missing", "The explanation has no ready context."
        )
    with sqlite_ledger_transaction(ledger_path) as ledger:
        for context in contexts:
            manifest_id = context.get("context_manifest_id")
            if not isinstance(manifest_id, str):
                raise ConformanceError(
                    "context_manifest_missing", "A context result omitted its manifest ID."
                )
            manifest = verify_context_manifest(
                manifest_id, ledger, VerificationTokenizer(), PROMPT_BYTES, SCHEMA_BYTES
            ).manifest
            if "directive 3000.09" not in _normalize(manifest.rendered_input.decode("utf-8")):
                raise ConformanceError(
                    "context_anchor_missing", "Context lost original source evidence."
                )


def _required(payload: JsonObject, key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str):
        raise ConformanceError("public_command_invalid", f"Missing string field: {key}")
    return value


if __name__ == "__main__":
    try:
        print(json.dumps(run(), sort_keys=True))
    except ConformanceError as error:
        print(json.dumps({"status": "failed", "failure": error.code, "message": str(error)}))
        raise SystemExit(1) from None
