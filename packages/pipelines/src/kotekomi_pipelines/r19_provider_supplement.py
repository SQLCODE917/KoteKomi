"""R19 provider supplement schema and gated loader.

The supplement carries the reviewed evidence the residuals need beyond the frozen
Connection Gold: the Event bindings, the ``non_entity_value`` subject exclusion,
the EGE-to-Actor or Organization identity mapping, the relation-label-to-predicate
mapping, and the Assertion inspection inputs. It is a proposed review record until
a human approves it. Approving is separate from loading: the loader parses and
digest-binds a proposed record for review, while composition requires approval and
a resolved reference closure.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Annotated, Literal, Self

from kotekomi_application import AttachmentSourceRange
from kotekomi_application.ports import LedgerRepository
from pydantic import BaseModel, ConfigDict, Field, model_validator

from kotekomi_pipelines.event_entity_connection_stage_local import (
    load_connection_gold_catalog,
    reanchor_whitespace_spans,
)
from kotekomi_pipelines.source_grounded_proposition_stage_local import (
    load_proposition_gold_catalog,
)

_SHA256 = r"^[a-f0-9]{64}$"
_AHE_ID = r"^AHE-[0-9]{3}$"
_TGE_ID = r"^TGE-[0-9]{3}$"
_EGE_ID = r"^EGE-[0-9]{3}$"
_EGX_ID = r"^EGX-[0-9]{3}$"
_ACTOR_ID = r"^act_[A-Za-z0-9][A-Za-z0-9_-]*$"
_ORG_ID = r"^org_[A-Za-z0-9][A-Za-z0-9_-]*$"
_SOURCE_ID = r"^src_[A-Za-z0-9][A-Za-z0-9_-]*$"
_EVIDENCE_TARGET_ID = r"^etg_[A-Za-z0-9][A-Za-z0-9_-]*$"
_PREDICATE = r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$"


class SupplementFileBinding(BaseModel):
    """One bound file and its digest."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    path: Annotated[str, Field(min_length=1)]
    sha256: Annotated[str, Field(pattern=_SHA256)]


class SupplementInputBinding(BaseModel):
    """One bound residual input file and its source digest."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    event_id: Annotated[str, Field(pattern=_AHE_ID)]
    input_path: Annotated[str, Field(min_length=1)]
    input_sha256: Annotated[str, Field(pattern=_SHA256)]
    source_sha256: Annotated[str, Field(pattern=_SHA256)]


class SupplementTriggerSpan(BaseModel):
    """One exact trigger span in one coordinate system."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    start: Annotated[int, Field(ge=0)]
    end: Annotated[int, Field(gt=0)]
    source_text: Annotated[str, Field(min_length=1)]

    @model_validator(mode="after")
    def validate_range(self) -> Self:
        if self.end - self.start != len(self.source_text):
            raise ValueError("Supplement trigger span does not match its text.")
        return self


class SupplementEventBinding(BaseModel):
    """One reviewed residual-Event to provider-Event binding."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    residual_event_id: Annotated[str, Field(pattern=_AHE_ID)]
    residual_source_sha256: Annotated[str, Field(pattern=_SHA256)]
    residual_trigger: SupplementTriggerSpan
    provider_event_id: Annotated[str, Field(pattern=_TGE_ID)] | None = None
    provider_source_sha256: Annotated[str, Field(pattern=_SHA256)] | None = None
    provider_trigger: SupplementTriggerSpan | None = None
    binding_rationale: Annotated[str, Field(min_length=1)]

    @model_validator(mode="after")
    def validate_provider_parts(self) -> Self:
        provider_parts = (
            self.provider_event_id,
            self.provider_source_sha256,
            self.provider_trigger,
        )
        if any(part is not None for part in provider_parts) and not all(
            part is not None for part in provider_parts
        ):
            raise ValueError(
                "A provider binding requires its Event ID, source digest, and trigger together."
            )
        return self


class SupplementSubjectValueExclusion(BaseModel):
    """One reviewed non-entity value exclusion that authorizes a subject value."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    exclusion_id: Annotated[str, Field(pattern=_EGX_ID)]
    event_id: Annotated[str, Field(pattern=_AHE_ID)]
    start: Annotated[int, Field(ge=0)]
    end: Annotated[int, Field(gt=0)]
    source_text: Annotated[str, Field(min_length=1)]
    contextual_kind: Literal["non_entity_value"]
    rationale: Annotated[str, Field(min_length=1)]

    @model_validator(mode="after")
    def validate_range(self) -> Self:
        if self.end - self.start != len(self.source_text):
            raise ValueError("Supplement exclusion range does not match its text.")
        return self


class SupplementIdentityMapping(BaseModel):
    """One reviewed EGE identity binding and its canonical resolution."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    entity_id: Annotated[str, Field(pattern=_EGE_ID)]
    entity_kind: Literal["actor", "organization"]
    canonical_name: Annotated[str, Field(min_length=1)]
    actor_id: Annotated[str, Field(pattern=_ACTOR_ID)] | None = None
    organization_id: Annotated[str, Field(pattern=_ORG_ID)] | None = None
    unresolved_reason: Annotated[str, Field(min_length=1)] | None = None

    @model_validator(mode="after")
    def validate_resolution(self) -> Self:
        if self.actor_id is not None and self.organization_id is not None:
            raise ValueError("One identity mapping resolves to a single Actor or Organization.")
        if self.entity_kind == "actor" and self.organization_id is not None:
            raise ValueError("An actor identity cannot map to an Organization.")
        if self.entity_kind == "organization" and self.actor_id is not None:
            raise ValueError("An Organization identity cannot map to an Actor.")
        resolved = self.actor_id is not None or self.organization_id is not None
        if resolved and self.unresolved_reason is not None:
            raise ValueError("A resolved identity mapping cannot carry an unresolved reason.")
        if not resolved and self.unresolved_reason is None:
            raise ValueError("An unresolved identity mapping requires an unresolved reason.")
        return self


class SupplementPredicateMapping(BaseModel):
    """One reviewed relation-label to predicate mapping."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    relation_label: Annotated[str, Field(min_length=1)]
    predicate: Annotated[str, Field(pattern=_PREDICATE)]
    rationale: Annotated[str, Field(min_length=1)]


class SupplementEventEvidence(BaseModel):
    """One residual Event's reviewed Assertion evidence and classification."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    event_id: Annotated[str, Field(pattern=_AHE_ID)]
    source_authority: Annotated[str, Field(min_length=1)]
    attribution_basis: Annotated[str, Field(min_length=1)]
    source_id: Annotated[str, Field(pattern=_SOURCE_ID)] | None = None
    evidence_target_id: Annotated[str, Field(pattern=_EVIDENCE_TARGET_ID)] | None = None
    unresolved_reason: Annotated[str, Field(min_length=1)] | None = None

    @model_validator(mode="after")
    def validate_closure(self) -> Self:
        resolved = self.source_id is not None and self.evidence_target_id is not None
        if resolved and self.unresolved_reason is not None:
            raise ValueError("Resolved Event evidence cannot carry an unresolved reason.")
        if not resolved and self.unresolved_reason is None:
            raise ValueError("Unresolved Event evidence requires an unresolved reason.")
        return self


class R19ProviderSupplement(BaseModel):
    """The reviewed R19 provider supplement, loaded and digest-bound."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["hsq_r19_provider_supplement_v1"] = "hsq_r19_provider_supplement_v1"
    supplement_id: Annotated[str, Field(min_length=1)]
    review_status: Literal["proposed", "approved"]
    bound_connection_gold: SupplementFileBinding
    bound_proposition_gold: SupplementFileBinding
    residual_inputs: tuple[SupplementInputBinding, ...]
    event_bindings: tuple[SupplementEventBinding, ...]
    event_evidence: tuple[SupplementEventEvidence, ...]
    subject_value_exclusions: tuple[SupplementSubjectValueExclusion, ...]
    identity_mappings: tuple[SupplementIdentityMapping, ...]
    predicate_mappings: tuple[SupplementPredicateMapping, ...]

    @model_validator(mode="after")
    def validate_distinctness(self) -> Self:
        residual_ids = tuple(item.event_id for item in self.residual_inputs)
        if tuple(sorted(set(residual_ids))) != residual_ids:
            raise ValueError("Supplement residual inputs must be ordered and distinct.")
        binding_ids = tuple(item.residual_event_id for item in self.event_bindings)
        if tuple(sorted(set(binding_ids))) != binding_ids:
            raise ValueError("Supplement Event bindings must be ordered and distinct.")
        if set(binding_ids) != set(residual_ids):
            raise ValueError("Every residual input requires one Event binding.")
        evidence_ids = tuple(item.event_id for item in self.event_evidence)
        if tuple(sorted(set(evidence_ids))) != evidence_ids:
            raise ValueError("Supplement Event evidence must be ordered and distinct.")
        if set(evidence_ids) != set(residual_ids):
            raise ValueError("Every residual input requires one Event evidence record.")
        entity_ids = tuple(item.entity_id for item in self.identity_mappings)
        if tuple(sorted(set(entity_ids))) != entity_ids:
            raise ValueError("Supplement identity mappings must be ordered and distinct.")
        exclusion_ids = tuple(item.exclusion_id for item in self.subject_value_exclusions)
        if tuple(sorted(set(exclusion_ids))) != exclusion_ids:
            raise ValueError("Supplement exclusions must be ordered and distinct.")
        labels = tuple(item.relation_label for item in self.predicate_mappings)
        if tuple(sorted(set(labels))) != labels:
            raise ValueError("Supplement predicate mappings must be ordered and distinct.")
        return self


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _bound_path(repository_root: Path, value: str) -> Path:
    root = repository_root.resolve()
    path = (root / value).resolve()
    if not path.is_relative_to(root):
        raise ValueError(f"Supplement path leaves the repository: {value}.")
    return path


def load_r19_provider_supplement(
    path: Path,
    *,
    repository_root: Path,
) -> R19ProviderSupplement:
    """Load, digest-bind, and substantively validate one R19 provider supplement.

    The loader verifies the bound Connection Gold and Proposition Gold digests,
    each bound residual input file and source digest, and then cross-checks each
    Event binding against those files: the residual source digest and trigger must
    match the residual input, the provider source digest must match both Gold
    catalogs, and the provider trigger must re-anchor into the residual trigger
    through the whitespace-only correspondence.
    """
    supplement = R19ProviderSupplement.model_validate_json(path.read_bytes())

    connection_gold_path = _bound_path(repository_root, supplement.bound_connection_gold.path)
    if _sha256_bytes(connection_gold_path.read_bytes()) != supplement.bound_connection_gold.sha256:
        raise ValueError("Supplement Connection Gold digest drifted from its bound file.")
    connection_catalog, _, _ = load_connection_gold_catalog(
        connection_gold_path,
        repository_root=repository_root,
        require_approved=False,
    )
    connection_events = {event.event_id: event for event in connection_catalog.events}

    proposition_gold_path = _bound_path(repository_root, supplement.bound_proposition_gold.path)
    if (
        _sha256_bytes(proposition_gold_path.read_bytes())
        != supplement.bound_proposition_gold.sha256
    ):
        raise ValueError("Supplement Proposition Gold digest drifted from its bound file.")
    proposition_catalog = load_proposition_gold_catalog(
        proposition_gold_path,
        repository_root=repository_root,
    )
    proposition_events = {event.event_id: event for event in proposition_catalog.events}

    residual_by_event: dict[str, tuple[str, tuple[int, int, str]]] = {}
    source_digest_by_event: dict[str, str] = {}
    for input_binding in supplement.residual_inputs:
        input_path = _bound_path(repository_root, input_binding.input_path)
        if _sha256_bytes(input_path.read_bytes()) != input_binding.input_sha256:
            raise ValueError(
                f"Supplement residual input digest drifted for {input_binding.event_id}."
            )
        frozen_input = json.loads(input_path.read_text(encoding="utf-8"))
        source_text = str(frozen_input["source_text"])
        if _sha256_bytes(source_text.encode()) != input_binding.source_sha256:
            raise ValueError(
                f"Supplement residual source digest drifted for {input_binding.event_id}."
            )
        trigger = frozen_input["event_frame"]["trigger"]
        residual_by_event[input_binding.event_id] = (
            source_text,
            (int(trigger["start"]), int(trigger["end"]), str(trigger["text"])),
        )
        source_digest_by_event[input_binding.event_id] = input_binding.source_sha256

    for binding in supplement.event_bindings:
        residual_text, residual_trigger = residual_by_event[binding.residual_event_id]
        if binding.residual_source_sha256 != source_digest_by_event[binding.residual_event_id]:
            raise ValueError(
                f"Supplement binding source digest disagrees for {binding.residual_event_id}."
            )
        if _trigger_tuple(binding.residual_trigger) != residual_trigger:
            raise ValueError(
                f"Supplement binding trigger disagrees for {binding.residual_event_id}."
            )
        if binding.provider_event_id is None:
            continue
        connection_event = connection_events.get(binding.provider_event_id)
        proposition_event = proposition_events.get(binding.provider_event_id)
        if connection_event is None or proposition_event is None:
            raise ValueError(
                f"Supplement binding names an unknown provider Event {binding.provider_event_id}."
            )
        if connection_event.source_text_sha256 != binding.provider_source_sha256:
            raise ValueError(
                "Supplement binding provider source digest disagrees for "
                f"{binding.provider_event_id}."
            )
        if proposition_event.source_text_sha256 != binding.provider_source_sha256:
            raise ValueError(
                "Supplement binding provider source digest disagrees for "
                f"{binding.provider_event_id}."
            )
        provider_text = proposition_event.source_text
        assert binding.provider_trigger is not None
        reanchored = reanchor_whitespace_spans(
            provider_text=provider_text,
            residual_text=residual_text,
            spans=(_attachment_range(binding.provider_trigger),),
        )
        if _source_range_tuple(reanchored[0]) != residual_trigger:
            raise ValueError(
                f"Supplement binding trigger does not re-anchor for {binding.residual_event_id}."
            )

    return supplement


def _trigger_tuple(trigger: SupplementTriggerSpan) -> tuple[int, int, str]:
    return (trigger.start, trigger.end, trigger.source_text)


def _source_range_tuple(value: AttachmentSourceRange) -> tuple[int, int, str]:
    return (value.start, value.end, value.text)


def _attachment_range(trigger: SupplementTriggerSpan) -> AttachmentSourceRange:
    return AttachmentSourceRange(start=trigger.start, end=trigger.end, text=trigger.source_text)


def require_approved_supplement(supplement: R19ProviderSupplement) -> None:
    """Fail unless a human has approved the supplement for composition."""

    if supplement.review_status != "approved":
        raise ValueError("Composition requires an approved R19 provider supplement.")


def unresolved_references(supplement: R19ProviderSupplement) -> tuple[str, ...]:
    """Return the supplement's unresolved required references, each described once."""

    unresolved: list[str] = []
    for mapping in supplement.identity_mappings:
        if mapping.actor_id is None and mapping.organization_id is None:
            unresolved.append(
                f"{mapping.entity_id} ({mapping.canonical_name}): {mapping.unresolved_reason}"
            )
    for evidence in supplement.event_evidence:
        if evidence.source_id is None:
            unresolved.append(f"{evidence.event_id} source_id: {evidence.unresolved_reason}")
        if evidence.evidence_target_id is None:
            unresolved.append(
                f"{evidence.event_id} evidence_target_id: {evidence.unresolved_reason}"
            )
    return tuple(unresolved)


def require_resolved_closure(
    supplement: R19ProviderSupplement,
    repository: LedgerRepository,
) -> None:
    """Fail on unresolved or nonexistent required references through the repository.

    The check runs in two phases. The first rejects any null required ID. The
    second verifies through the typed repository boundary that each resolved ID
    exists, has the expected record type, and that each EvidenceTarget references
    the Event's declared Source.
    """
    unresolved = unresolved_references(supplement)
    if unresolved:
        raise ValueError(
            "R19 provider supplement has unresolved required references: " + "; ".join(unresolved)
        )

    for mapping in supplement.identity_mappings:
        if mapping.actor_id is not None:
            if repository.get_actor(mapping.actor_id) is None:
                raise ValueError(
                    f"Actor record {mapping.actor_id} for {mapping.entity_id} does not exist."
                )
        elif mapping.organization_id is not None:
            if repository.get_organization(mapping.organization_id) is None:
                raise ValueError(
                    f"Organization record {mapping.organization_id} for {mapping.entity_id} "
                    "does not exist."
                )

    for evidence in supplement.event_evidence:
        source_id = evidence.source_id
        evidence_target_id = evidence.evidence_target_id
        assert source_id is not None
        assert evidence_target_id is not None
        if repository.get_source(source_id) is None:
            raise ValueError(f"Source record {source_id} for {evidence.event_id} does not exist.")
        target = repository.get_evidence_target(evidence_target_id)
        if target is None:
            raise ValueError(
                f"EvidenceTarget record {evidence_target_id} for {evidence.event_id} "
                "does not exist."
            )
        if target.source_id != source_id:
            raise ValueError(
                f"EvidenceTarget {evidence_target_id} does not reference Source {source_id}."
            )
