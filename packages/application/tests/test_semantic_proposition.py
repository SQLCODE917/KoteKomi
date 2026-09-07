from kotekomi_application import (
    NaturalLanguageInferenceExecution,
    NliLabel,
    PropositionDisposition,
    PropositionHoldReason,
    PropositionKind,
    build_complete_proposition,
    build_nli_observation,
    build_proposition_decision,
)


def _execution(scores: tuple[float, float, float]) -> NaturalLanguageInferenceExecution:
    return NaturalLanguageInferenceExecution(
        model_id="fixture-nli",
        model_revision="1",
        resource_identity="sha256:fixture",
        contradiction_score=scores[0],
        entailment_score=scores[1],
        neutral_score=scores[2],
        elapsed_milliseconds=4,
    )


def test_complete_proposition_and_nli_observation_are_content_addressed() -> None:
    proposition = build_complete_proposition(
        kind=PropositionKind.EVENT,
        subject_record_id="esn_" + "a" * 24,
        text="Amodei criticized Trump's export restrictions.",
        evidence_target_id="etg_" + "b" * 24,
    )
    observation = build_nli_observation(
        proposition_id=proposition.id,
        premise="Amodei criticized Trump's approach to export restrictions.",
        hypothesis=proposition.text,
        execution=_execution((0.01, 0.98, 0.01)),
    )

    assert observation.selected_label is NliLabel.ENTAILMENT
    assert observation.proposition_id == proposition.id
    assert len(observation.premise_sha256) == len(observation.hypothesis_sha256) == 64


def test_proposition_decision_requires_qwen_and_nli_support() -> None:
    proposition = build_complete_proposition(
        kind=PropositionKind.EVENT,
        subject_record_id="esn_" + "a" * 24,
        text="Amodei criticized Trump.",
        evidence_target_id="etg_" + "b" * 24,
    )
    entailed = build_nli_observation(
        proposition_id=proposition.id,
        premise="Amodei criticized Trump.",
        hypothesis=proposition.text,
        execution=_execution((0.01, 0.98, 0.01)),
    )

    supported = build_proposition_decision(
        proposition_id=proposition.id,
        qwen_judgment_id="spj_" + "c" * 24,
        nli_observation=entailed,
        qwen_directly_supported=True,
        entailment_threshold=0.5,
    )
    rejected_by_qwen = build_proposition_decision(
        proposition_id=proposition.id,
        qwen_judgment_id="spj_" + "d" * 24,
        nli_observation=entailed,
        qwen_directly_supported=False,
        entailment_threshold=0.5,
    )
    neutral = build_nli_observation(
        proposition_id=proposition.id,
        premise="Amodei discussed Trump.",
        hypothesis=proposition.text,
        execution=_execution((0.02, 0.08, 0.90)),
    )
    rejected_by_nli = build_proposition_decision(
        proposition_id=proposition.id,
        qwen_judgment_id="spj_" + "e" * 24,
        nli_observation=neutral,
        qwen_directly_supported=True,
        entailment_threshold=0.5,
    )

    assert supported.disposition is PropositionDisposition.SUPPORTED
    assert rejected_by_qwen.hold_reason is PropositionHoldReason.QWEN_NON_DIRECT_SUPPORT
    assert rejected_by_nli.hold_reason is PropositionHoldReason.NLI_NEUTRAL


def test_proposition_decision_holds_when_qwen_evidence_is_unavailable() -> None:
    decision = build_proposition_decision(
        proposition_id="cpr_" + "a" * 24,
        qwen_judgment_id=None,
        nli_observation=None,
        qwen_directly_supported=None,
        entailment_threshold=0.5,
    )

    assert decision.disposition is PropositionDisposition.HELD
    assert decision.hold_reason is PropositionHoldReason.QWEN_UNAVAILABLE
