from datetime import UTC, datetime

from kotekomi_application.support_edge_production import (
    SUPPORT_EDGE_ACTIVITY_TYPE,
    ProduceSupportEdgeInput,
    SupportEdgeError,
    SupportEdgeFailureCode,
    produce_support_edge,
    support_argument_edge_id,
)
from kotekomi_domain import (
    ArgumentEdge,
    ArgumentEdgeRelation,
    Assertion,
    AssertionStatus,
    AssertionType,
    AttributionBasis,
    EpistemicScope,
    ProvenanceActivity,
    SourceAuthority,
)
from pytest import raises

NOW = datetime(2026, 9, 22, tzinfo=UTC)


def _assertion(assertion_id: str, status: AssertionStatus) -> Assertion:
    return Assertion(
        id=assertion_id,
        assertion_type=AssertionType.SOURCE_CLAIM,
        epistemic_scope=EpistemicScope.SOURCE_REPORT,
        subject_entity_id="org_anthropic",
        predicate="runs_campaign",
        object_value="a campaign",
        status=status,
        source_authority=SourceAuthority.SECONDARY,
        attribution_basis=AttributionBasis.REPORTED_BY_SOURCE,
        source_ids=("src_policy",),
        evidence_target_ids=("etg_policy",),
        provenance_activity_ids=("prv_policy",),
        created_at=NOW,
        updated_at=NOW,
    )


class FakeLedger:
    def __init__(self, assertions: tuple[Assertion, ...]) -> None:
        self._assertions = {item.id: item for item in assertions}
        self.argument_edges: list[ArgumentEdge] = []
        self.provenance_activities: list[ProvenanceActivity] = []

    def get_assertion(self, record_id: str) -> Assertion | None:
        return self._assertions.get(record_id)

    def save_argument_edge(self, record: ArgumentEdge) -> None:
        self.argument_edges.append(record)

    def save_provenance_activity(self, record: ProvenanceActivity) -> None:
        self.provenance_activities.append(record)


def _input(
    *,
    from_id: str = "ast_evidence",
    to_id: str = "ast_supported",
    rationale: str = "The source-backed quote supports the attributed statement.",
    confidence: float = 0.92,
) -> ProduceSupportEdgeInput:
    return ProduceSupportEdgeInput(
        from_assertion_id=from_id,
        to_assertion_id=to_id,
        rationale=rationale,
        confidence=confidence,
        evidence_target_ids=("etg_policy",),
        support_decision_id="pdc_decision",
        support_judgment_id="spj_judgment",
        nli_observation_id="nlo_observation",
        occurred_at=NOW,
    )


def test_produce_support_edge_builds_edge_and_provenance() -> None:
    evidence = _assertion("ast_evidence", AssertionStatus.REPORTED)
    supported = _assertion("ast_supported", AssertionStatus.CONFIRMED)
    ledger = FakeLedger((evidence, supported))

    result = produce_support_edge(production_input=_input(), ledger=ledger)

    edge = result.argument_edge
    assert edge.relation is ArgumentEdgeRelation.SUPPORTS
    assert edge.from_assertion_id == "ast_evidence"
    assert edge.to_assertion_id == "ast_supported"
    assert edge.rationale == "The source-backed quote supports the attributed statement."
    assert edge.confidence == 0.92
    assert edge.evidence_target_ids == ("etg_policy",)
    assert edge.id == support_argument_edge_id(
        from_assertion_id="ast_evidence",
        to_assertion_id="ast_supported",
        rationale="The source-backed quote supports the attributed statement.",
        confidence=0.92,
        evidence_target_ids=("etg_policy",),
        support_decision_id="pdc_decision",
    )

    activity = result.provenance_activity
    assert activity.activity_type == SUPPORT_EDGE_ACTIVITY_TYPE
    assert activity.output_ids == (edge.id,)
    assert activity.input_ids == (
        "ast_evidence",
        "ast_supported",
        "etg_policy",
        "nlo_observation",
        "pdc_decision",
        "spj_judgment",
    )
    assert ledger.argument_edges == [edge]
    assert ledger.provenance_activities == [activity]


def test_produce_support_edge_rejects_missing_from_assertion() -> None:
    ledger = FakeLedger((_assertion("ast_supported", AssertionStatus.CONFIRMED),))

    with raises(SupportEdgeError) as raised:
        produce_support_edge(production_input=_input(), ledger=ledger)

    assert raised.value.code is SupportEdgeFailureCode.FROM_ASSERTION_MISSING
    assert ledger.argument_edges == []
    assert ledger.provenance_activities == []


def test_produce_support_edge_rejects_missing_to_assertion() -> None:
    ledger = FakeLedger((_assertion("ast_evidence", AssertionStatus.REPORTED),))

    with raises(SupportEdgeError) as raised:
        produce_support_edge(production_input=_input(), ledger=ledger)

    assert raised.value.code is SupportEdgeFailureCode.TO_ASSERTION_MISSING
    assert ledger.argument_edges == []
    assert ledger.provenance_activities == []


def test_produce_support_edge_rejects_non_accepted_from_assertion() -> None:
    evidence = _assertion("ast_evidence", AssertionStatus.PROPOSED)
    supported = _assertion("ast_supported", AssertionStatus.CONFIRMED)
    ledger = FakeLedger((evidence, supported))

    with raises(SupportEdgeError) as raised:
        produce_support_edge(production_input=_input(), ledger=ledger)

    assert raised.value.code is SupportEdgeFailureCode.FROM_ASSERTION_NOT_ACCEPTED
    assert ledger.argument_edges == []
    assert ledger.provenance_activities == []


def test_produce_support_edge_rejects_non_accepted_to_assertion() -> None:
    evidence = _assertion("ast_evidence", AssertionStatus.REPORTED)
    supported = _assertion("ast_supported", AssertionStatus.PROPOSED)
    ledger = FakeLedger((evidence, supported))

    with raises(SupportEdgeError) as raised:
        produce_support_edge(production_input=_input(), ledger=ledger)

    assert raised.value.code is SupportEdgeFailureCode.TO_ASSERTION_NOT_ACCEPTED
    assert ledger.argument_edges == []
    assert ledger.provenance_activities == []


def test_support_edge_input_rejects_blank_rationale() -> None:
    with raises(ValueError, match="rationale"):
        _input(rationale="   ")
