"""Tests for the R20 live identity reference Adapter."""

from __future__ import annotations

from typing import cast

import pytest
from kotekomi_domain import (
    Actor,
    EvidenceTarget,
    IdentityOccurrence,
    IdentityOccurrenceKind,
    Organization,
)
from kotekomi_pipelines.live_identity_reference_provider import (
    LiveIdentityReferenceError,
    LiveIdentityReferenceErrorReason,
    LiveIdentityReferenceLedger,
    LiveIdentityReferenceProvider,
    LiveReferenceDiagnosticReason,
)

NOW_TEXT = "src_r20"


def _target(record_id: str, exact_text: str) -> EvidenceTarget:
    return EvidenceTarget(
        id=record_id,
        source_id=NOW_TEXT,
        document_id="doc_r20",
        representation_id="rep_r20",
        text_view_id="tvw_r20",
        text_view_digest="a" * 64,
        start_char=0,
        end_char=max(len(exact_text), 1),
        exact_text=exact_text,
        normalization_policy="utf8_identity_v1",
        node_ids=("nod_r20",),
    )


def _occurrence(
    record_id: str, identity_id: str, kind: IdentityOccurrenceKind, etg: str
) -> IdentityOccurrence:
    return IdentityOccurrence(
        id=record_id,
        identity_id=identity_id,
        identity_kind=kind,
        evidence_target_id=etg,
        provenance_activity_id="prv_r20",
    )


class _Ledger:
    def __init__(self) -> None:
        self.occurrences: tuple[IdentityOccurrence, ...] = ()
        self.targets: dict[str, EvidenceTarget] = {}
        self.actors: dict[str, Actor] = {}
        self.organizations: dict[str, Organization] = {}

    def list_identity_occurrences(self) -> tuple[IdentityOccurrence, ...]:
        return self.occurrences

    def get_evidence_target(self, record_id: str) -> EvidenceTarget | None:
        return self.targets.get(record_id)

    def get_actor(self, record_id: str) -> Actor | None:
        return self.actors.get(record_id)

    def get_organization(self, record_id: str) -> Organization | None:
        return self.organizations.get(record_id)


def _provider(ledger: _Ledger) -> LiveIdentityReferenceProvider:
    return LiveIdentityReferenceProvider(cast(LiveIdentityReferenceLedger, ledger))


def test_translates_accepted_occurrence_into_a_reference() -> None:
    ledger = _Ledger()
    ledger.actors["act_alpha"] = Actor(id="act_alpha", name="Alpha")
    ledger.targets["etg_alpha"] = _target("etg_alpha", "Alpha")
    ledger.occurrences = (
        _occurrence("ioc_alpha", "act_alpha", IdentityOccurrenceKind.ACTOR, "etg_alpha"),
    )

    references = _provider(ledger).resolve_references("AHE-001", "Alpha met Beta.", "b" * 64)

    assert len(references.entities) == 1
    entity = references.entities[0]
    assert entity.entity_id == "act_alpha"
    assert entity.entity_kind == "actor"
    assert entity.canonical_name == "Alpha"
    assert [(span.start, span.end) for span in entity.accepted_source_occurrences] == [(0, 5)]


def test_locates_a_whitespace_variant_mention() -> None:
    ledger = _Ledger()
    ledger.actors["act_alpha"] = Actor(id="act_alpha", name="Alpha")
    ledger.targets["etg_alpha"] = _target("etg_alpha", "Alpha  Beta")
    ledger.occurrences = (
        _occurrence("ioc_alpha", "act_alpha", IdentityOccurrenceKind.ACTOR, "etg_alpha"),
    )

    references = _provider(ledger).resolve_references("AHE-001", "Alpha Beta met.", "b" * 64)

    assert len(references.entities) == 1
    span = references.entities[0].accepted_source_occurrences[0]
    assert span.text == "Alpha Beta"


def test_ambiguous_mention_leaves_a_diagnostic_and_no_reference() -> None:
    ledger = _Ledger()
    ledger.actors["act_alpha"] = Actor(id="act_alpha", name="Alpha")
    ledger.targets["etg_alpha"] = _target("etg_alpha", "Alpha")
    ledger.occurrences = (
        _occurrence("ioc_alpha", "act_alpha", IdentityOccurrenceKind.ACTOR, "etg_alpha"),
    )

    resolution = _provider(ledger).resolve_references_with_diagnostics(
        "AHE-001", "Alpha met Alpha.", "b" * 64
    )

    assert resolution.references.entities == ()
    assert len(resolution.diagnostics) == 1
    assert resolution.diagnostics[0].reason is LiveReferenceDiagnosticReason.AMBIGUOUS_MENTION
    assert resolution.diagnostics[0].occurrence_id == "ioc_alpha"


def test_missing_evidence_fails_fast() -> None:
    ledger = _Ledger()
    ledger.actors["act_alpha"] = Actor(id="act_alpha", name="Alpha")
    ledger.occurrences = (
        _occurrence("ioc_alpha", "act_alpha", IdentityOccurrenceKind.ACTOR, "etg_absent"),
    )

    with pytest.raises(LiveIdentityReferenceError) as error:
        _provider(ledger).resolve_references("AHE-001", "Alpha met Beta.", "b" * 64)
    assert error.value.reason is LiveIdentityReferenceErrorReason.MISSING_EVIDENCE


def test_missing_identity_fails_fast() -> None:
    ledger = _Ledger()
    ledger.targets["etg_alpha"] = _target("etg_alpha", "Alpha")
    ledger.occurrences = (
        _occurrence("ioc_alpha", "act_absent", IdentityOccurrenceKind.ACTOR, "etg_alpha"),
    )

    with pytest.raises(LiveIdentityReferenceError) as error:
        _provider(ledger).resolve_references("AHE-001", "Alpha met Beta.", "b" * 64)
    assert error.value.reason is LiveIdentityReferenceErrorReason.MISSING_IDENTITY


def test_prefers_accepted_coordinates_when_the_view_matches() -> None:
    ledger = _Ledger()
    ledger.actors["act_alpha"] = Actor(id="act_alpha", name="Alpha")
    target = _target("etg_alpha", "Alpha").model_copy(update={"start_char": 10, "end_char": 15})
    ledger.targets["etg_alpha"] = target
    ledger.occurrences = (
        _occurrence("ioc_alpha", "act_alpha", IdentityOccurrenceKind.ACTOR, "etg_alpha"),
    )
    provider = LiveIdentityReferenceProvider(
        cast(LiveIdentityReferenceLedger, ledger),
        representation_id="rep_r20",
        text_view_id="tvw_r20",
    )

    references = provider.resolve_references("AHE-001", "Alpha met Alpha.", "b" * 64)

    span = references.entities[0].accepted_source_occurrences[0]
    assert (span.start, span.end) == (10, 15)


def test_coordinate_mismatch_fails_fast() -> None:
    ledger = _Ledger()
    ledger.actors["act_alpha"] = Actor(id="act_alpha", name="Alpha")
    target = _target("etg_alpha", "Alpha").model_copy(update={"start_char": 10, "end_char": 15})
    ledger.targets["etg_alpha"] = target
    ledger.occurrences = (
        _occurrence("ioc_alpha", "act_alpha", IdentityOccurrenceKind.ACTOR, "etg_alpha"),
    )
    provider = LiveIdentityReferenceProvider(
        cast(LiveIdentityReferenceLedger, ledger),
        representation_id="rep_r20",
        text_view_id="tvw_r20",
    )

    with pytest.raises(LiveIdentityReferenceError) as error:
        provider.resolve_references("AHE-001", "Alpha met Alphx.", "b" * 64)
    assert error.value.reason is LiveIdentityReferenceErrorReason.COORDINATE_MISMATCH


def test_returns_no_reference_without_an_accepted_occurrence() -> None:
    ledger = _Ledger()

    references = _provider(ledger).resolve_references("AHE-001", "Alpha met Beta.", "b" * 64)

    assert references.entities == ()
    assert references.subject_value_authorizations == ()


def test_translates_an_organization_occurrence() -> None:
    ledger = _Ledger()
    ledger.organizations["org_anthropic"] = Organization(id="org_anthropic", name="Anthropic")
    ledger.targets["etg_anthropic"] = _target("etg_anthropic", "Anthropic")
    ledger.occurrences = (
        _occurrence(
            "ioc_anthropic", "org_anthropic", IdentityOccurrenceKind.ORGANIZATION, "etg_anthropic"
        ),
    )

    references = _provider(ledger).resolve_references("AHE-001", "Anthropic replied.", "b" * 64)

    assert references.entities[0].entity_id == "org_anthropic"
    assert references.entities[0].entity_kind == "organization"
