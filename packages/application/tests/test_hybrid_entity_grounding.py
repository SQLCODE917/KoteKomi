from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from kotekomi_application.hybrid_document_references import (
    HybridReferencePreview,
    ReferenceDecision,
    ReferenceKind,
    ReferenceStatus,
)
from kotekomi_application.hybrid_entity_grounding import (
    EntityGroundingEligibilityReason,
    EntityGroundingEligibilityStatus,
    EntityLinkCandidate,
    EntityLinkCandidateKind,
    EntityLinkerEvidence,
    EntityLinkerIdentity,
    EntityLinkingBatch,
    EntityLinkingExecution,
    EntityLinkingInput,
    EntityLinkingOutputError,
    EntityLinkingRuntimeResponseError,
    EntityLinkMention,
    HybridEntityGroundingStatus,
    build_entity_linking_inputs,
    entity_grounding_terminal_status,
    evaluate_entity_grounding_eligibility,
    run_recorded_entity_linking,
)
from kotekomi_application.hybrid_mention_interpretation import (
    HybridExtractionPreview,
    HybridPreviewStatus,
    MentionBoundaryDecision,
    MentionBoundaryStatus,
    MentionCandidate,
    MentionInterpretation,
    Referentiality,
)
from kotekomi_domain import ModelRunStatus


def test_eligibility_records_every_candidate_and_only_selects_specific_mentions() -> None:
    candidates = tuple(
        _candidate(index, text)
        for index, text in enumerate(
            ("Anthropic", "companies", "it", "unclear", "overlap", "missing"), start=1
        )
    )
    decisions = tuple(
        _boundary(
            candidate,
            status=(
                MentionBoundaryStatus.AMBIGUOUS
                if candidate.text == "overlap"
                else MentionBoundaryStatus.UNCONTESTED
            ),
        )
        for candidate in candidates
    )
    interpretations = tuple(
        _interpretation(candidate, referentiality)
        for candidate, referentiality in zip(
            candidates[:5],
            (
                Referentiality.SPECIFIC_ENTITY,
                Referentiality.GENERIC_CLASS,
                Referentiality.ANAPHORIC,
                Referentiality.UNCLEAR,
                Referentiality.SPECIFIC_ENTITY,
            ),
            strict=True,
        )
    )
    parent = HybridExtractionPreview.model_construct(
        id="hxp_" + "a" * 24,
        candidates=candidates,
        boundary_decisions=decisions,
        interpretations=interpretations,
    )
    references = HybridReferencePreview.model_construct(
        id="hrp_" + "b" * 24,
        parent_preview_id=parent.id,
        reference_decisions=(),
    )

    results = evaluate_entity_grounding_eligibility(parent, references)

    assert len(results) == len(candidates)
    assert [(item.status, item.reason) for item in results] == [
        (
            EntityGroundingEligibilityStatus.ELIGIBLE,
            EntityGroundingEligibilityReason.SPECIFIC_ENTITY,
        ),
        (
            EntityGroundingEligibilityStatus.INELIGIBLE,
            EntityGroundingEligibilityReason.GENERIC_CLASS,
        ),
        (EntityGroundingEligibilityStatus.INELIGIBLE, EntityGroundingEligibilityReason.ANAPHORIC),
        (
            EntityGroundingEligibilityStatus.INELIGIBLE,
            EntityGroundingEligibilityReason.REFERENTIALITY_UNCLEAR,
        ),
        (
            EntityGroundingEligibilityStatus.INELIGIBLE,
            EntityGroundingEligibilityReason.BOUNDARY_AMBIGUOUS,
        ),
        (
            EntityGroundingEligibilityStatus.INELIGIBLE,
            EntityGroundingEligibilityReason.INTERPRETATION_MISSING,
        ),
    ]


def test_reference_ambiguity_blocks_but_resolved_and_unmatched_aliases_remain_eligible() -> None:
    resolved, ambiguous, unmatched, anaphoric = (
        _candidate(index, text) for index, text in enumerate(("NIST", "AO", "AISIC", "it"), start=1)
    )
    candidates = (resolved, ambiguous, unmatched, anaphoric)
    parent = HybridExtractionPreview.model_construct(
        id="hxp_" + "a" * 24,
        candidates=candidates,
        boundary_decisions=tuple(_boundary(item) for item in candidates),
        interpretations=tuple(
            _interpretation(
                item,
                Referentiality.ANAPHORIC if item is anaphoric else Referentiality.SPECIFIC_ENTITY,
            )
            for item in candidates
        ),
    )
    references = HybridReferencePreview.model_construct(
        id="hrp_" + "b" * 24,
        parent_preview_id=parent.id,
        reference_decisions=(
            _reference(resolved, ReferenceKind.EXPLICIT_ALIAS, ReferenceStatus.RESOLVED),
            _reference(ambiguous, ReferenceKind.EXPLICIT_ALIAS, ReferenceStatus.AMBIGUOUS),
            _reference(unmatched, ReferenceKind.EXPLICIT_ALIAS, ReferenceStatus.UNRESOLVED),
            _reference(anaphoric, ReferenceKind.ANAPHORIC, ReferenceStatus.UNRESOLVED),
        ),
    )

    results = evaluate_entity_grounding_eligibility(parent, references)

    assert [(item.status, item.reason) for item in results] == [
        (
            EntityGroundingEligibilityStatus.ELIGIBLE,
            EntityGroundingEligibilityReason.SPECIFIC_ENTITY,
        ),
        (
            EntityGroundingEligibilityStatus.INELIGIBLE,
            EntityGroundingEligibilityReason.REFERENCE_AMBIGUOUS,
        ),
        (
            EntityGroundingEligibilityStatus.ELIGIBLE,
            EntityGroundingEligibilityReason.SPECIFIC_ENTITY,
        ),
        (EntityGroundingEligibilityStatus.INELIGIBLE, EntityGroundingEligibilityReason.ANAPHORIC),
    ]
    assert results[0].reference_decision_id is not None
    assert results[2].reference_decision_id is not None


def test_entity_linking_inputs_batch_only_eligible_mentions_by_exact_source_segment() -> None:
    source_one = "NIST works with companies."
    source_two = "The Department of Defense responded."
    nist = _candidate_at(1, "seg_one", source_one, "NIST")
    generic = _candidate_at(2, "seg_one", source_one, "companies")
    defense = _candidate_at(3, "seg_two", source_two, "Department of Defense")
    candidates = (nist, generic, defense)
    parent = HybridExtractionPreview.model_construct(
        id="hxp_" + "a" * 24,
        candidates=candidates,
        boundary_decisions=tuple(_boundary(item) for item in candidates),
        interpretations=(
            _interpretation(nist, Referentiality.SPECIFIC_ENTITY),
            _interpretation(generic, Referentiality.GENERIC_CLASS),
            _interpretation(defense, Referentiality.SPECIFIC_ENTITY),
        ),
    )
    references = HybridReferencePreview.model_construct(
        id="hrp_" + "b" * 24,
        parent_preview_id=parent.id,
        reference_decisions=(),
    )

    requests = build_entity_linking_inputs(
        eligibility=evaluate_entity_grounding_eligibility(parent, references),
        candidates=candidates,
        source_text_by_id={"seg_one": source_one, "seg_two": source_two},
    )

    assert [item.source_segment_id for item in requests] == ["seg_one", "seg_two"]
    assert [[mention.text for mention in item.mentions] for item in requests] == [
        ["NIST"],
        ["Department of Defense"],
    ]
    sent_text = {mention.text for request in requests for mention in request.mentions}
    assert "companies" not in sent_text


@pytest.mark.parametrize(
    ("parent_status", "required", "successful", "expected"),
    [
        (HybridPreviewStatus.COMPLETE, 0, 0, HybridEntityGroundingStatus.COMPLETE),
        (HybridPreviewStatus.PARTIAL, 0, 0, HybridEntityGroundingStatus.PARTIAL),
        (HybridPreviewStatus.COMPLETE, 2, 2, HybridEntityGroundingStatus.COMPLETE),
        (HybridPreviewStatus.PARTIAL, 2, 2, HybridEntityGroundingStatus.PARTIAL),
        (HybridPreviewStatus.COMPLETE, 2, 1, HybridEntityGroundingStatus.PARTIAL),
        (HybridPreviewStatus.COMPLETE, 2, 0, HybridEntityGroundingStatus.BLOCKED),
    ],
)
def test_entity_grounding_terminal_status_is_explicit(
    parent_status: HybridPreviewStatus,
    required: int,
    successful: int,
    expected: HybridEntityGroundingStatus,
) -> None:
    assert (
        entity_grounding_terminal_status(
            parent_status=parent_status,
            required_batches=required,
            successful_batches=successful,
        )
        is expected
    )


def test_reviewed_gold_pins_fixture_bytes_and_exact_source_characters() -> None:
    path = Path(__file__).resolve().parents[3] / "docs" / "hp3-entity-grounding-gold-v1.json"
    payload = path.read_bytes()
    catalog = json.loads(payload)

    assert (
        json.dumps(catalog, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
        + b"\n"
        == payload
    )
    assert catalog["schema_version"] == "hp3_entity_grounding_gold_v1"
    assert {item["case_id"] for item in catalog["cases"]} == {
        "HP3-AISI-NIST",
        "HP3-ANTHROPIC-DOD",
    }
    assert {item["expected"][0]["wikidata_id"] for item in catalog["cases"]} == {
        "Q176691",
        "Q11209",
    }
    for case in catalog["cases"]:
        source_text = case["source_text"]
        assert hashlib.sha256(source_text.encode()).hexdigest() == case["source_text_sha256"]
        assert len(case["fixture_sha256"]) == 64
        for expectation in (*case["expected"], *case["known_snapshot_gaps"]):
            assert expectation["candidate_text"] in source_text


def test_entity_linking_input_and_rank_contracts_fail_fast() -> None:
    source = "NIST worked with NIST."
    request = EntityLinkingInput(
        source_segment_id="src_fixture",
        source_text_sha256=hashlib.sha256(source.encode()).hexdigest(),
        source_text=source,
        mentions=(EntityLinkMention(candidate_id="mnc_" + "1" * 24, text="NIST", start=0, end=4),),
    )
    assert request.source_text[:4] == request.mentions[0].text

    with pytest.raises(ValueError, match="source characters"):
        EntityLinkingInput(
            source_segment_id="src_fixture",
            source_text_sha256=hashlib.sha256(source.encode()).hexdigest(),
            source_text=source,
            mentions=(
                EntityLinkMention(candidate_id="mnc_" + "1" * 24, text="NISX", start=0, end=4),
            ),
        )

    with pytest.raises(ValueError, match="contiguous"):
        EntityLinkerEvidence(
            candidate_id="mnc_" + "1" * 24,
            returned_text="NIST",
            start=0,
            end=4,
            candidates=(
                EntityLinkCandidate(
                    rank=2,
                    kind=EntityLinkCandidateKind.KNOWLEDGE_BASE_ENTITY,
                    wikidata_id="Q176691",
                    wikipedia_title="National Institute of Standards and Technology",
                    score=0.99,
                ),
            ),
        )


def test_nil_is_explicit_and_cannot_name_an_external_identity() -> None:
    candidate = EntityLinkCandidate(rank=1, kind=EntityLinkCandidateKind.NIL, score=0.2)
    assert candidate.wikidata_id is None

    with pytest.raises(ValueError, match="NIL"):
        EntityLinkCandidate(
            rank=1,
            kind=EntityLinkCandidateKind.NIL,
            wikidata_id="Q1",
            score=0.2,
        )


def test_recorded_entity_linking_archives_raw_output_and_task_run_lineage() -> None:
    source = "NIST worked."
    request = EntityLinkingInput(
        source_segment_id="src_fixture",
        source_text_sha256=hashlib.sha256(source.encode()).hexdigest(),
        source_text=source,
        mentions=(
            EntityLinkMention(
                candidate_id="mnc_" + "1" * 24,
                text="NIST",
                start=0,
                end=4,
            ),
        ),
    )
    raw_output = b'{"status":"completed"}'
    linker = _FixtureLinker(raw_output=raw_output)
    ledger = _FixtureExecutionLedger()
    archive = _FixtureOutputArchive()

    outcome = run_recorded_entity_linking(
        representation_id="rep_fixture",
        context_manifest_id="ctx_fixture",
        context_manifest_digest="a" * 64,
        context_manifest_payload={"id": "ctx_fixture"},
        request=request,
        linker=linker,
        ledger=ledger,
        archive=archive,
    )

    assert outcome.model_run.status is ModelRunStatus.SUCCEEDED
    assert outcome.extraction_task.input_candidate_ids == (request.mentions[0].candidate_id,)
    assert ledger.tasks == [outcome.extraction_task]
    assert ledger.runs == [outcome.model_run]
    assert archive.outputs[outcome.model_run.id] == raw_output


def test_recorded_entity_linking_preserves_runtime_failure_as_failed_model_run() -> None:
    source = "NIST worked."
    request = EntityLinkingInput(
        source_segment_id="src_fixture",
        source_text_sha256=hashlib.sha256(source.encode()).hexdigest(),
        source_text=source,
        mentions=(
            EntityLinkMention(
                candidate_id="mnc_" + "1" * 24,
                text="NIST",
                start=0,
                end=4,
            ),
        ),
    )
    ledger = _FixtureExecutionLedger()

    outcome = run_recorded_entity_linking(
        representation_id="rep_fixture",
        context_manifest_id="ctx_fixture",
        context_manifest_digest="a" * 64,
        context_manifest_payload={"id": "ctx_fixture"},
        request=request,
        linker=_FixtureLinker(error=RuntimeError("resources unavailable")),
        ledger=ledger,
        archive=_FixtureOutputArchive(),
    )

    assert outcome.batch is None
    assert outcome.model_run.status is ModelRunStatus.RUNTIME_FAILED
    assert outcome.model_run.error_message == "resources unavailable"
    assert ledger.runs == [outcome.model_run]


def test_recorded_worker_failure_archives_its_typed_response() -> None:
    source = "NIST worked."
    request = EntityLinkingInput(
        source_segment_id="src_fixture",
        source_text_sha256=hashlib.sha256(source.encode()).hexdigest(),
        source_text=source,
        mentions=(
            EntityLinkMention(
                candidate_id="mnc_" + "1" * 24,
                text="NIST",
                start=0,
                end=4,
            ),
        ),
    )
    raw_output = b'{"failure":"resources_unavailable","status":"blocked"}'
    ledger = _FixtureExecutionLedger()
    archive = _FixtureOutputArchive()

    outcome = run_recorded_entity_linking(
        representation_id="rep_fixture",
        context_manifest_id="ctx_fixture",
        context_manifest_digest="a" * 64,
        context_manifest_payload={"id": "ctx_fixture"},
        request=request,
        linker=_FixtureLinker(
            error=EntityLinkingRuntimeResponseError("Pinned resources are unavailable.", raw_output)
        ),
        ledger=ledger,
        archive=archive,
    )

    assert outcome.batch is None
    assert outcome.model_run.status is ModelRunStatus.RUNTIME_FAILED
    assert outcome.model_run.output_digest == hashlib.sha256(raw_output).hexdigest()
    assert archive.outputs[outcome.model_run.id] == raw_output


def test_recorded_invalid_output_is_quarantined_with_exact_raw_bytes() -> None:
    source = "NIST worked."
    request = EntityLinkingInput(
        source_segment_id="src_fixture",
        source_text_sha256=hashlib.sha256(source.encode()).hexdigest(),
        source_text=source,
        mentions=(
            EntityLinkMention(
                candidate_id="mnc_" + "1" * 24,
                text="NIST",
                start=0,
                end=4,
            ),
        ),
    )
    raw_output = b'{"unexpected":"shape"}'
    ledger = _FixtureExecutionLedger()
    archive = _FixtureOutputArchive()

    outcome = run_recorded_entity_linking(
        representation_id="rep_fixture",
        context_manifest_id="ctx_fixture",
        context_manifest_digest="a" * 64,
        context_manifest_payload={"id": "ctx_fixture"},
        request=request,
        linker=_FixtureLinker(error=EntityLinkingOutputError("Invalid response.", raw_output)),
        ledger=ledger,
        archive=archive,
    )

    assert outcome.batch is None
    assert outcome.model_run.status is ModelRunStatus.INVALID_OUTPUT
    assert archive.outputs[outcome.model_run.id] == raw_output


def _candidate(index: int, text: str) -> MentionCandidate:
    return MentionCandidate.model_construct(
        id=f"mnc_{index:024x}",
        source_segment_id="src_fixture",
        source_text_sha256="a" * 64,
        start=index,
        end=index + len(text),
        text=text,
    )


def _candidate_at(
    index: int,
    source_segment_id: str,
    source_text: str,
    text: str,
) -> MentionCandidate:
    start = source_text.index(text)
    return MentionCandidate.model_construct(
        id=f"mnc_{index:024x}",
        source_segment_id=source_segment_id,
        source_text_sha256=hashlib.sha256(source_text.encode()).hexdigest(),
        start=start,
        end=start + len(text),
        text=text,
    )


def _boundary(
    candidate: MentionCandidate,
    status: MentionBoundaryStatus = MentionBoundaryStatus.UNCONTESTED,
) -> MentionBoundaryDecision:
    return MentionBoundaryDecision.model_construct(
        id=f"mbd_{candidate.id[-24:]}",
        source_segment_id=candidate.source_segment_id,
        status=status,
        candidate_ids=(candidate.id,),
        selected_candidate_ids=(candidate.id,),
    )


def _interpretation(
    candidate: MentionCandidate,
    referentiality: Referentiality,
) -> MentionInterpretation:
    return MentionInterpretation.model_construct(
        id=f"mit_{candidate.id[-24:]}",
        candidate_id=candidate.id,
        referentiality=referentiality,
    )


def _reference(
    candidate: MentionCandidate,
    kind: ReferenceKind,
    status: ReferenceStatus,
) -> ReferenceDecision:
    return ReferenceDecision.model_construct(
        id=f"rfd_{candidate.id[-24:]}",
        candidate_id=candidate.id,
        reference_kind=kind,
        status=status,
    )


class _FixtureLinker:
    identity = EntityLinkerIdentity(
        producer_id="fixture",
        model_id="fixture",
        model_revision="fixture-v1",
        entity_set="fixture",
        package_revision="fixture-v1",
        resource_manifest_sha256="f" * 64,
        runtime_identity="fixture:entity-linker",
        timeout_seconds=1.0,
    )

    def __init__(self, *, raw_output: bytes = b"", error: Exception | None = None) -> None:
        self.raw_output = raw_output
        self.error = error

    def link(self, request: EntityLinkingInput) -> EntityLinkingExecution:
        if self.error is not None:
            raise self.error
        mention = request.mentions[0]
        return EntityLinkingExecution(
            batch=EntityLinkingBatch(
                identity=self.identity,
                load_elapsed_ms=0,
                inference_elapsed_ms=1,
                evidences=(
                    EntityLinkerEvidence(
                        candidate_id=mention.candidate_id,
                        returned_text=mention.text,
                        start=mention.start,
                        end=mention.end,
                        candidates=(
                            EntityLinkCandidate(
                                rank=1,
                                kind=EntityLinkCandidateKind.KNOWLEDGE_BASE_ENTITY,
                                wikidata_id="Q176691",
                                wikipedia_title=("National Institute of Standards and Technology"),
                                score=0.99,
                            ),
                        ),
                    ),
                ),
            ),
            raw_output=self.raw_output,
        )


class _FixtureExecutionLedger:
    def __init__(self) -> None:
        self.tasks: list[object] = []
        self.runs: list[object] = []

    def save_extraction_task(self, record: object) -> None:
        self.tasks.append(record)

    def save_model_run(self, record: object) -> None:
        self.runs.append(record)


class _FixtureOutputArchive:
    def __init__(self) -> None:
        self.outputs: dict[str, bytes] = {}

    def put_model_run_output(
        self, model_run_id: str, payload: bytes, expected_digest: str
    ) -> object:
        assert hashlib.sha256(payload).hexdigest() == expected_digest
        self.outputs[model_run_id] = payload
        return object()
