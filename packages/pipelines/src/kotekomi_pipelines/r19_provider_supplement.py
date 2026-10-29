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

from pydantic import BaseModel, ConfigDict, Field, model_validator

from kotekomi_pipelines.event_entity_connection_stage_local import (
    load_connection_gold_catalog,
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


class SupplementAssertionInputs(BaseModel):
    """The reviewed classification inputs for the inspectable Assertion."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    source_authority: Annotated[str, Field(min_length=1)]
    attribution_basis: Annotated[str, Field(min_length=1)]
    source_id: Annotated[str, Field(pattern=_SOURCE_ID)] | None = None
    evidence_target_id: Annotated[str, Field(pattern=_EVIDENCE_TARGET_ID)] | None = None
    unresolved_reason: Annotated[str, Field(min_length=1)] | None = None

    @model_validator(mode="after")
    def validate_closure(self) -> Self:
        resolved = self.source_id is not None and self.evidence_target_id is not None
        if resolved and self.unresolved_reason is not None:
            raise ValueError("Resolved Assertion inputs cannot carry an unresolved reason.")
        if not resolved and self.unresolved_reason is None:
            raise ValueError("Unresolved Assertion inputs require an unresolved reason.")
        return self


class R19ProviderSupplement(BaseModel):
    """The reviewed R19 provider supplement, loaded and digest-bound."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["hsq_r19_provider_supplement_v1"] = "hsq_r19_provider_supplement_v1"
    supplement_id: Annotated[str, Field(min_length=1)]
    review_status: Literal["proposed", "approved"]
    bound_connection_gold: SupplementFileBinding
    residual_inputs: tuple[SupplementInputBinding, ...]
    event_bindings: tuple[SupplementEventBinding, ...]
    subject_value_exclusions: tuple[SupplementSubjectValueExclusion, ...]
    identity_mappings: tuple[SupplementIdentityMapping, ...]
    predicate_mappings: tuple[SupplementPredicateMapping, ...]
    assertion_inputs: SupplementAssertionInputs

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
    """Load and digest-bind one R19 provider supplement.

    The loader reads and validates the supplement shape, then verifies that the
    bound Connection Gold, each bound residual input file, and each residual source
    digest match the files on disk. It also rejects a binding that names a provider
    Event absent from the bound Connection Gold.
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
    provider_event_ids = {event.event_id for event in connection_catalog.events}

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

    for binding in supplement.event_bindings:
        if binding.provider_event_id is not None:
            if binding.provider_event_id not in provider_event_ids:
                raise ValueError(
                    "Supplement binding names an unknown provider Event "
                    f"{binding.provider_event_id}."
                )

    return supplement


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
    if supplement.assertion_inputs.source_id is None:
        unresolved.append(f"Assertion source_id: {supplement.assertion_inputs.unresolved_reason}")
    if supplement.assertion_inputs.evidence_target_id is None:
        unresolved.append(
            f"Assertion evidence_target_id: {supplement.assertion_inputs.unresolved_reason}"
        )
    return tuple(unresolved)


def require_resolved_closure(supplement: R19ProviderSupplement) -> None:
    """Fail when any required reference remains unresolved."""

    unresolved = unresolved_references(supplement)
    if unresolved:
        raise ValueError(
            "R19 provider supplement has unresolved required references: " + "; ".join(unresolved)
        )
