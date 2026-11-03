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
from datetime import UTC, datetime
from pathlib import Path

from kotekomi_adapters import sqlite_ledger_transaction
from kotekomi_application import (
    EventCompositionStatus,
    EventEntityLinguisticToken,
    GroundingCandidate,
    IdentityOccurrenceProposalInput,
    IngestionTokenArtifact,
    LinguisticAnalysis,
    LinguisticAnalysisInput,
    LinguisticToken,
    UniversalPartOfSpeech,
    accept_identity_occurrence,
    propose_identity_occurrence,
    write_event_composition_record,
)
from kotekomi_application.ingestion_inspection import build_profile
from kotekomi_application.parser_constituent_candidate_generation import (
    build_constituent_candidate_inventory,
)
from kotekomi_application.source_grounded_reference_composition import (
    composition_annotations_for,
)
from kotekomi_application.source_occurrences import source_occurrences
from kotekomi_domain import (
    AssertionType,
    AttributionBasis,
    IdentityOccurrenceKind,
    SourceAuthority,
)
from kotekomi_pipelines.cli import ingest_user_file
from kotekomi_pipelines.hybrid_document_ingestion import _FixtureLinguisticAnalyzer
from kotekomi_pipelines.ingestion_composition_command import (
    RecompositionRequest,
    run_recomposition,
)
from kotekomi_pipelines.ingestion_composition_stage import compose_paragraph_events
from kotekomi_pipelines.ingestion_token_artifact import LocalTokenArtifactWriter
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


def _install_fixtures(monkeypatch) -> None:
    from kotekomi_application import ModelTaskResponse
    from kotekomi_pipelines.hybrid_document_ingestion import _RuntimeResources
    from kotekomi_pipelines.model_runtime import FixtureModelTaskRuntime

    analyzer = _ChosenAnalyzer()
    monkeypatch.setattr(_RuntimeResources, "linguistic_analyzer", property(lambda self: analyzer))
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
        if chosen is not None:
            return ModelTaskResponse(
                raw_output=chosen, execution_receipt=response.execution_receipt
            )
        return response

    monkeypatch.setattr(FixtureModelTaskRuntime, "run_model_task", patched)


def test_ingestion_discovers_a_source_grounded_event(tmp_path: Path, monkeypatch) -> None:
    _install_fixtures(monkeypatch)
    config_path = _config(tmp_path)
    code = ingest_user_file(
        config_path=config_path,
        source_file_path=PDF_FIXTURE,
        source_url="https://example.test/pdf",
        stdout=open("/dev/null", "w"),
    )
    assert code == 0
    state = tmp_path / "state"
    paragraphs = load_paragraph_inputs(state / "kotekomi.db", state / "archive")
    target = next(p for p in paragraphs if p.paragraph_node_id.endswith(TARGET_NODE_SUFFIX))
    profile = build_profile(
        text=target.text,
        representation_id=target.representation_id,
        paragraph_node_id=target.paragraph_node_id,
        node_start_char=target.node_start_char,
        stage_outputs=target.stage_outputs,
        bundle=target.bundle,
    )
    assert profile.text  # paragraph discovered
    assert profile.events, "the chosen paragraph must yield a source-grounded Event"

    analysis = _ChosenAnalyzer().analyze(LinguisticAnalysisInput(target.text))
    artifact = IngestionTokenArtifact(
        representation_id=target.representation_id,
        text_view_id=profile.text_view_id or "",
        paragraph_node_id=target.paragraph_node_id,
        node_start_char=target.node_start_char,
        node_end_char=target.node_start_char + len(target.text),
        source_text_sha256=hashlib.sha256(target.text.encode()).hexdigest(),
        analyzer_identity=analysis.producer_id,
        tokens=tuple(
            EventEntityLinguisticToken(
                token_id=token.token_id,
                sentence_id=token.sentence_id,
                text=token.text,
                start=token.start,
                end=token.end,
                lemma=token.lemma,
                part_of_speech=token.part_of_speech.value,
                dependency_relation=token.dependency_relation,
                head_token_id=token.head_token_id,
            )
            for token in analysis.tokens
        ),
    )
    LocalTokenArtifactWriter(state / "token-artifacts").write(artifact)
    events = tuple(
        (event.event_id, event.trigger_span.start, event.trigger_span.end)
        for event in profile.events
    )
    with sqlite_ledger_transaction(state / "kotekomi.db") as repository:
        records = compose_paragraph_events(
            repository=repository,
            source_text=target.text,
            tokens=artifact.tokens,
            events=events,
            assertion_inputs_by_event={},
            representation_id=target.representation_id,
            text_view_id=artifact.text_view_id,
            composition_root=state / "composition-outcomes",
            node_start_char=target.node_start_char,
        )
    assert records
    assert records[0].status is EventCompositionStatus.HELD
    assert records[0].hold_reason == "assertion_inputs_unavailable"

    # Approve one identity occurrence for the subject and supply reviewed inputs.
    local = target.text.index(SUBJECT)
    assert target.bundle is not None
    text_view = next(view for view in target.bundle.text_views if view.id == profile.text_view_id)
    bundle_document_id = target.bundle.representation.document_id
    with sqlite_ledger_transaction(state / "kotekomi.db") as source_repository:
        source_document = source_repository.get_document(bundle_document_id)
        assert source_document is not None
        source_id = source_document.source_id
    proposal_input = IdentityOccurrenceProposalInput(
        identity_kind=IdentityOccurrenceKind.ACTOR,
        decision="new_identity",
        existing_identity_id=None,
        identity_name=SUBJECT,
        source_id=source_id,
        document_id=bundle_document_id,
        representation_id=target.representation_id,
        text_view_id=text_view.id,
        text_view_digest=text_view.content_digest,
        start_char=target.node_start_char + local,
        end_char=target.node_start_char + local + len(SUBJECT),
        exact_text=SUBJECT,
        node_id=target.paragraph_node_id,
    )
    candidate = GroundingCandidate(
        candidate_kind="knowledge_base_entity",
        eligible=True,
        ambiguous=False,
        identity_name=SUBJECT,
    )
    proposal = propose_identity_occurrence(
        candidate, proposal_input, proposal_id="pcg_r20_transition", now=NOW
    )
    with sqlite_ledger_transaction(state / "kotekomi.db") as repository:
        repository.save_proposed_change(proposal)
        occurrence = accept_identity_occurrence(
            proposal, repository, agent="kotekomi_agent", now=NOW
        )
        event_id = events[0][0]
        request = RecompositionRequest(
            event_id=event_id,
            source_text=target.text,
            source_text_sha256=artifact.source_text_sha256,
            inventory=build_constituent_candidate_inventory(
                source_text=target.text,
                event_id=event_id,
                tokens=artifact.tokens,
                event_expression_start=events[0][1],
                event_expression_end=events[0][2],
            ),
            trigger_head_start=events[0][1],
            trigger_head_end=events[0][2],
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
        )
        record = run_recomposition(request, repository)
        write_event_composition_record(
            state / "composition-outcomes" / f"{event_id}.json", record
        )

    assert record.event_id == event_id
    assert record.status is EventCompositionStatus.COMPOSED
    assert record.assertion is not None
    assert record.assertion.subject_entity_id == occurrence.identity_id
    assert record.assertion.predicate == "shared"
    assert record.supporting_subject_span is not None
    assert record.supporting_subject_span.text == SUBJECT

    replay = composition_annotations_for(state / "composition-outcomes", (event_id,))
    assert len(replay) == 1
    assert replay[0].status == "composed"
    assert SUBJECT in replay[0].summary


def test_chosen_analyzer_emits_valid_tokens() -> None:
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
