"""Deterministic ingestion fixtures for the operator-journey tests.

These fixtures supply external analyzer, linker, and model output only.
Ingestion, selection, composition, review acceptance, persistence, and replay run
through production code.
"""

# pyright: reportPrivateUsage=false

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import pytest
from kotekomi_application import (
    EntityLinkCandidate,
    EntityLinkCandidateKind,
    EntityLinkerEvidence,
    EntityLinkerIdentity,
    EntityLinkingBatch,
    EntityLinkingExecution,
    LinguisticAnalysis,
    LinguisticAnalysisInput,
    LinguisticToken,
    LinkedEntityClassEvidence,
    ModelTaskResponse,
    UniversalPartOfSpeech,
)
from kotekomi_application.source_occurrences import source_occurrences
from kotekomi_pipelines.hybrid_document_ingestion import _FixtureLinguisticAnalyzer

VERB = "share"
SUBJECT = "HealthyJoCo"
OBJECT = "Plan"
PDF_FIXTURE = (
    Path(__file__).resolve().parents[3]
    / "adapters"
    / "tests"
    / "fixtures"
    / "pdf"
    / "2025-community-health-improvement-plan-press-release.pdf"
)


class ChosenAnalyzer:
    """Deterministic analyzer: one verb root with a subject and an object."""

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
            producer_id="operator-journey-analyzer",
            model_id="operator-journey-analyzer-model",
            model_version="1",
            resource_identity="f" * 64,
            tokens=tuple(tokens),
        )


class ChosenEntityLinker:
    """Deterministic entity linker: one knowledge-base candidate for the subject."""

    def __init__(self) -> None:
        self.identity = EntityLinkerIdentity(
            producer_id="operator-journey-linker",
            model_id="operator-journey-linker-model",
            model_revision="1",
            entity_set="operator-journey-entities",
            package_revision="1",
            resource_manifest_sha256="c" * 64,
            runtime_identity="fixture",
            timeout_seconds=1.0,
        )

    def link(self, request: Any) -> EntityLinkingExecution:
        evidences: list[EntityLinkerEvidence] = []
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


def install_ingestion_fixtures(monkeypatch: pytest.MonkeyPatch) -> None:
    """Install deterministic analyzer, linker, and model responses."""
    from kotekomi_pipelines.hybrid_document_ingestion import _RuntimeResources
    from kotekomi_pipelines.model_runtime import FixtureModelTaskRuntime

    analyzer = ChosenAnalyzer()
    monkeypatch.setattr(_RuntimeResources, "linguistic_analyzer", property(lambda self: analyzer))
    monkeypatch.setattr(_RuntimeResources, "linker", property(lambda self: ChosenEntityLinker()))
    original = FixtureModelTaskRuntime.run_model_task

    def patched(self: Any, task: Any) -> ModelTaskResponse:
        response = original(self, task)
        schema = task.execution_spec.schema_id
        rendered = task.rendered_input
        chosen: bytes | None = None
        if schema == "event_verb_role_text_v1" and VERB.encode() in rendered:
            chosen = b"E"
        elif schema == "event_binary_semantic_text_v1" and b"standing similarity" in rendered:
            chosen = b"N"
        elif schema == "event_binary_semantic_text_v1":
            chosen = b"Y"
        elif (
            schema == "hybrid_mention_interpretation_text_v2"
            and b"candidate_text: " + SUBJECT.encode() in rendered
        ):
            chosen = (
                b"candidate: c1\n"
                b"referentiality: specific_entity\n"
                b"contextual_kind: organization\n"
                b"discourse_role: actor\n"
                b"support: s1\n"
            )
        if chosen is None:
            return response
        return ModelTaskResponse(raw_output=chosen, execution_receipt=response.execution_receipt)

    monkeypatch.setattr(FixtureModelTaskRuntime, "run_model_task", patched)
