"""R20 normal-ingestion -> hold -> approval -> recomposition -> replay transition.

WORK IN PROGRESS. The test-local analyzer and model responses are deterministic
fixtures that stand in for external analyzer/model output only. They never seed a
composition result; production selection, composition, acceptance, and replay
logic run unchanged.
"""

# pyright: reportPrivateUsage=false, reportMissingParameterType=false
# pyright: reportUnknownParameterType=false, reportUnknownMemberType=false
# pyright: reportUnknownArgumentType=false, reportUnknownVariableType=false

from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime
from multiprocessing.connection import Connection
from pathlib import Path
from typing import Any, cast

from kotekomi_adapters import sqlite_ledger_transaction
from kotekomi_adapters.composition_outcome_store import CompositionOutcomeStore
from kotekomi_application import (
    EventCompositionStatus,
    IdentityOccurrenceProposalInput,
    LinguisticAnalysis,
    LinguisticAnalysisInput,
    LinguisticToken,
    UniversalPartOfSpeech,
    accept_identity_occurrence,
    ingested_grounding_candidates,
    propose_identity_occurrence,
)
from kotekomi_application.ingestion_execution import IngestionProcessRequest
from kotekomi_application.ingestion_inspection import build_profile
from kotekomi_application.parser_constituent_candidate_generation import (
    build_constituent_candidate_inventory,
)
from kotekomi_application.source_occurrences import source_occurrences
from kotekomi_domain import (
    AssertionType,
    AttributionBasis,
    IdentityOccurrenceKind,
    SourceAuthority,
)
from kotekomi_pipelines.hybrid_document_ingestion import _FixtureLinguisticAnalyzer
from kotekomi_pipelines.ingestion_composition_command import (
    RecompositionRequest,
    run_recomposition,
)
from kotekomi_pipelines.ingestion_token_artifact import (
    load_ingestion_token_artifact,
)
from kotekomi_pipelines.replay_reader.ingestion_worker import run_ingestion_worker
from kotekomi_pipelines.replay_reader.transport import load_paragraph_inputs

PDF_FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "adapters"
    / "tests"
    / "fixtures"
    / "pdf"
    / "2025-community-health-improvement-plan-press-release.pdf"
)
TARGET_NODE_SUFFIX = "_0012"
NOW = datetime(2026, 10, 30, tzinfo=UTC)
ROUTE_MARKER = "HealthyJoCo"

VERB = "share"
SUBJECT = "HealthyJoCo"
OBJECT = "Plan"


def _config(tmp_path: Path) -> Path:
    config_path = tmp_path / "kotekomi.toml"
    config_path.write_text(
        f"""
ledger_path = "{(tmp_path / "state" / "kotekomi.db").as_posix()}"
archive_path = "{(tmp_path / "state" / "archive").as_posix()}"

runtime_profile = "fixture"

[processing]
representation_policy_version = "deposited-source-v1"
""".lstrip(),
        encoding="utf-8",
    )
    return config_path


class _ChosenAnalyzer:
    """Deterministic analyzer: a rich parse for the chosen SourceSegment."""

    def __init__(self) -> None:
        self._fallback = _FixtureLinguisticAnalyzer()

    def analyze(self, request: LinguisticAnalysisInput) -> LinguisticAnalysis:
        occurrences = source_occurrences(request.source_text)
        texts = {occurrence.text for occurrence in occurrences}
        if VERB not in texts or SUBJECT not in texts:
            return self._fallback.analyze(request)
        verb_id = next(
            f"t{index}"
            for index, occurrence in enumerate(occurrences, start=1)
            if occurrence.text == VERB
        )
        tokens: list[LinguisticToken] = []
        for index, occurrence in enumerate(occurrences, start=1):
            token_id = f"t{index}"
            if token_id == verb_id:
                part, relation, head = UniversalPartOfSpeech.VERB, "root", None
            elif occurrence.text == SUBJECT:
                part, relation, head = UniversalPartOfSpeech.PROPER_NOUN, "nsubj", verb_id
            elif occurrence.text == OBJECT:
                part, relation, head = UniversalPartOfSpeech.PROPER_NOUN, "obj", verb_id
            else:
                part, relation, head = UniversalPartOfSpeech.PROPER_NOUN, "dep", verb_id
            tokens.append(
                LinguisticToken(
                    token_id=token_id,
                    sentence_id="s1",
                    text=occurrence.text,
                    start=occurrence.start,
                    end=occurrence.end,
                    lemma=occurrence.text.casefold(),
                    part_of_speech=part,
                    dependency_relation=relation,
                    head_token_id=head,
                )
            )
        return LinguisticAnalysis(
            source_text_sha256=hashlib.sha256(request.source_text.encode()).hexdigest(),
            producer_id="r20-chosen-analyzer",
            model_id="r20-chosen-model",
            model_version="1",
            resource_identity="c" * 64,
            tokens=tuple(tokens),
        )


class _ChosenEntityLinker:
    """Deterministic entity linker: one knowledge-base candidate for the subject."""

    def __init__(self) -> None:
        from kotekomi_application import EntityLinkerIdentity

        self.identity = EntityLinkerIdentity(
            producer_id="r20-chosen-linker",
            model_id="r20-chosen-linker-model",
            model_revision="1",
            entity_set="r20-fixture-entities",
            package_revision="1",
            resource_manifest_sha256="d" * 64,
            runtime_identity="fixture",
            timeout_seconds=1.0,
        )

    def link(self, request):
        from kotekomi_application import (
            EntityLinkCandidate,
            EntityLinkCandidateKind,
            EntityLinkerEvidence,
            EntityLinkingBatch,
            EntityLinkingExecution,
            LinkedEntityClassEvidence,
        )

        evidences = []
        for mention in request.mentions:
            if mention.text != SUBJECT:
                continue
            evidences.append(
                EntityLinkerEvidence(
                    candidate_id=mention.candidate_id,
                    returned_text=mention.text,
                    start=mention.start,
                    end=mention.end,
                    coarse_mention_type="ORGANIZATION",
                    candidates=(
                        EntityLinkCandidate(
                            rank=1,
                            kind=EntityLinkCandidateKind.KNOWLEDGE_BASE_ENTITY,
                            wikidata_id="Q1000001",
                            wikipedia_title=SUBJECT,
                            label=SUBJECT,
                            score=0.93,
                        ),
                    ),
                    linked_entity_classes=LinkedEntityClassEvidence(
                        wikidata_id="Q1000001", classes=()
                    ),
                )
            )
        batch = EntityLinkingBatch(
            identity=self.identity,
            load_elapsed_ms=0,
            inference_elapsed_ms=0,
            evidences=tuple(evidences),
        )
        return EntityLinkingExecution(batch=batch, raw_output=batch.model_dump_json().encode())


def _install_fixtures(monkeypatch) -> None:
    from kotekomi_application import ModelTaskResponse
    from kotekomi_pipelines.hybrid_document_ingestion import _RuntimeResources
    from kotekomi_pipelines.model_runtime import FixtureModelTaskRuntime

    analyzer = _ChosenAnalyzer()
    monkeypatch.setattr(_RuntimeResources, "linguistic_analyzer", property(lambda self: analyzer))
    monkeypatch.setattr(_RuntimeResources, "linker", property(lambda self: _ChosenEntityLinker()))
    original = FixtureModelTaskRuntime.run_model_task

    def patched(self, task):
        response = original(self, task)
        schema = task.execution_spec.schema_id
        rendered = task.rendered_input
        chosen: bytes | None = None
        if schema == "event_verb_role_text_v1" and VERB.encode() in rendered:
            chosen = b"E"
        elif schema == "event_binary_semantic_text_v1" and b"standing similarity" in rendered:
            # The verb-similarity route shares this schema with HP6 semantics.
            chosen = b"N"
        elif schema == "event_binary_semantic_text_v1":
            # HP6 event semantics: the chosen verb is the only realized Event.
            chosen = b"Y"
        elif (
            schema == "hybrid_mention_interpretation_text_v2"
            and b"candidate_text: " + SUBJECT.encode() in rendered
        ):
            # Only the chosen mention is a specific entity; the rest stay anaphoric.
            chosen = (
                b"candidate: c1\n"
                b"referentiality: specific_entity\n"
                b"contextual_kind: organization\n"
                b"discourse_role: actor\n"
                b"support: s1\n"
            )
        if chosen is not None:
            return ModelTaskResponse(
                raw_output=chosen, execution_receipt=response.execution_receipt
            )
        return response

    monkeypatch.setattr(FixtureModelTaskRuntime, "run_model_task", patched)


class _RecordingConnection:
    """Minimal transport stand-in that records the worker's event frames."""

    def __init__(self) -> None:
        self.frames: list[bytes] = []

    def send_bytes(self, payload: bytes) -> None:
        self.frames.append(payload)

    def close(self) -> None:
        return None

    def finished_code(self) -> int:
        for frame in self.frames:
            payload = json.loads(frame)
            if payload["kind"] == "finished":
                return int(payload["code"])
        raise AssertionError("the worker never reported a terminal frame")


def test_normal_worker_persists_the_hold_then_recomposition_composes(
    tmp_path: Path, monkeypatch
) -> None:
    """The worker alone produces the hold; approval plus recomposition composes."""
    _install_fixtures(monkeypatch)
    # Session setup belongs to the spawned worker; in-process it is a no-op shim.
    monkeypatch.setattr(os, "setsid", lambda: None)
    config_path = _config(tmp_path)
    state = tmp_path / "state"

    connection = _RecordingConnection()
    run_ingestion_worker(
        IngestionProcessRequest(
            config_path=str(config_path),
            source_path=str(PDF_FIXTURE),
            source_url="https://example.test/pdf",
            ledger_path=str(state / "kotekomi.db"),
            ingestion_run_id="igr_r20_worker",
            paragraph_ordinal=None,
        ),
        cast("Connection[Any, Any]", connection),
    )
    assert connection.finished_code() == 0

    # Paragraph coverage and the Event exist before any composition assertion.
    paragraphs = load_paragraph_inputs(state / "kotekomi.db", state / "archive")
    assert paragraphs
    target = next(p for p in paragraphs if p.paragraph_node_id.endswith(TARGET_NODE_SUFFIX))
    profile = build_profile(
        text=target.text,
        representation_id=target.representation_id,
        paragraph_node_id=target.paragraph_node_id,
        node_start_char=target.node_start_char,
        stage_outputs=target.stage_outputs,
        bundle=target.bundle,
    )
    assert profile.events

    # The worker, not the test, produced the token artifact and the hold.
    artifact = load_ingestion_token_artifact(
        state / "token-artifacts" / f"{target.paragraph_node_id}.json",
        paragraph_text=target.text,
    )
    event = profile.events[0]
    event_id = event.event_id
    replay_before = CompositionOutcomeStore(state / "composition-outcomes").annotations(
        (event_id,)
    )
    assert len(replay_before) == 1
    assert replay_before[0].status == "held"
    assert "assertion_inputs_unavailable" in replay_before[0].summary

    # Approve the candidate ingestion persisted, then recompose explicitly.
    ingested_candidates = ingested_grounding_candidates(
        text=target.text,
        representation_id=target.representation_id,
        paragraph_node_id=target.paragraph_node_id,
        stage_outputs=target.stage_outputs,
    )
    assert ingested_candidates, "ingestion must persist a review-selectable candidate"
    assert all(
        item.candidate.candidate_kind == "knowledge_base_entity" for item in ingested_candidates
    )
    subject_token = next(token for token in artifact.tokens if token.dependency_relation == "nsubj")
    chosen = next(
        item
        for item in ingested_candidates
        if item.start == subject_token.start and item.exact_text == SUBJECT
    )
    assert chosen.candidate.identity_name == SUBJECT
    local = chosen.start
    assert target.bundle is not None
    text_view = next(view for view in target.bundle.text_views if view.id == artifact.text_view_id)
    bundle_document_id = target.bundle.representation.document_id
    with sqlite_ledger_transaction(state / "kotekomi.db") as source_repository:
        source_document = source_repository.get_document(bundle_document_id)
        assert source_document is not None
        source_id = source_document.source_id
    proposal = propose_identity_occurrence(
        chosen.candidate,
        IdentityOccurrenceProposalInput(
            identity_kind=IdentityOccurrenceKind.ACTOR,
            decision="new_identity",
            existing_identity_id=None,
            identity_name=chosen.candidate.identity_name,
            source_id=source_id,
            document_id=bundle_document_id,
            representation_id=target.representation_id,
            text_view_id=text_view.id,
            text_view_digest=text_view.content_digest,
            start_char=target.node_start_char + local,
            end_char=target.node_start_char + chosen.end,
            exact_text=chosen.exact_text,
            node_id=target.paragraph_node_id,
        ),
        proposal_id="pcg_r20_worker",
        now=NOW,
    )
    with sqlite_ledger_transaction(state / "kotekomi.db") as repository:
        repository.save_proposed_change(proposal)
        occurrence = accept_identity_occurrence(
            proposal, repository, agent="kotekomi_agent", now=NOW
        )
        record = run_recomposition(
            RecompositionRequest(
                event_id=event_id,
                source_text=target.text,
                source_text_sha256=artifact.source_text_sha256,
                inventory=build_constituent_candidate_inventory(
                    source_text=target.text,
                    event_id=event_id,
                    tokens=artifact.tokens,
                    event_expression_start=event.trigger_span.start,
                    event_expression_end=event.trigger_span.end,
                ),
                trigger_head_start=event.trigger_span.start,
                trigger_head_end=event.trigger_span.end,
                tokens=artifact.tokens,
                representation_id=target.representation_id,
                text_view_id=artifact.text_view_id,
                node_start_char=target.node_start_char,
                predicate_by_label={"share": "shared"},
                identity_by_entity={occurrence.identity_id: occurrence.identity_id},
                assertion_type=AssertionType.REPORTED_OBSERVATION,
                source_authority=SourceAuthority.SECONDARY,
                attribution_basis=AttributionBasis.DIRECT_DOCUMENT,
                source_id=source_id,
                evidence_target_id=occurrence.evidence_target_id,
            ),
            repository,
        )
        CompositionOutcomeStore(state / "composition-outcomes").save(record)

    assert record.status is EventCompositionStatus.COMPOSED
    assert record.assertion is not None
    assert record.assertion.subject_entity_id == occurrence.identity_id
    assert record.assertion.predicate == "shared"
    assert record.supporting_subject_span is not None
    assert record.supporting_subject_span.text == SUBJECT

    replay_after = CompositionOutcomeStore(state / "composition-outcomes").annotations(
        (event_id,)
    )
    assert len(replay_after) == 1
    assert replay_after[0].status == "composed"
    assert SUBJECT in replay_after[0].summary


def test_chosen_analyzer_emits_valid_tokens() -> None:
    """The deterministic analyzer fixture satisfies the production token DTOs."""
    text = "HealthyJoCo is excited to share the Plan."
    analysis = _ChosenAnalyzer().analyze(LinguisticAnalysisInput(text))

    assert analysis.source_text_sha256 == hashlib.sha256(text.encode()).hexdigest()
    assert all(text[token.start : token.end] == token.text for token in analysis.tokens)
    verb = next(
        token for token in analysis.tokens if token.part_of_speech is UniversalPartOfSpeech.VERB
    )
    assert verb.dependency_relation == "root"
    assert any(token.dependency_relation == "nsubj" for token in analysis.tokens)
    assert any(token.dependency_relation == "obj" for token in analysis.tokens)
    assert analysis.producer_id == "r20-chosen-analyzer"
