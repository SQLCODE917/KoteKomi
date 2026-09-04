"""Application contracts for installed specialized-model resources."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Protocol


class ModelResourceId(StrEnum):
    GLINER_MENTION_PROPOSER_V1 = "gliner_mention_proposer_v1"
    REFINED_WIKIPEDIA_V1 = "refined_wikipedia_v1"


REQUIRED_MODEL_RESOURCE_IDS = (
    ModelResourceId.GLINER_MENTION_PROPOSER_V1,
    ModelResourceId.REFINED_WIKIPEDIA_V1,
)


class ModelResourceStatus(StrEnum):
    READY = "ready"
    MISSING = "missing"
    INCOMPLETE = "incomplete"
    IDENTITY_MISMATCH = "identity_mismatch"


@dataclass(frozen=True)
class ModelResourceReadiness:
    resource_id: ModelResourceId
    status: ModelResourceStatus
    root: Path
    expected_identity: str
    observed_identity: str | None
    diagnostics: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.root.is_absolute():
            raise ValueError("Model Resource root must be absolute.")
        if not self.expected_identity:
            raise ValueError("Expected Model Resource identity must be non-empty.")
        if any(not item for item in self.diagnostics):
            raise ValueError("Model Resource diagnostics must be non-empty strings.")
        if self.status is ModelResourceStatus.READY:
            if self.observed_identity != self.expected_identity or self.diagnostics:
                raise ValueError("A ready Model Resource must match its expected identity.")
        elif not self.diagnostics:
            raise ValueError("A non-ready Model Resource requires diagnostics.")

    @property
    def ready(self) -> bool:
        return self.status is ModelResourceStatus.READY


@dataclass(frozen=True)
class ModelResourceReadinessReport:
    resource_root: Path
    resources: tuple[ModelResourceReadiness, ...]

    def __post_init__(self) -> None:
        if not self.resource_root.is_absolute():
            raise ValueError("Model Resource root must be absolute.")
        if tuple(item.resource_id for item in self.resources) != REQUIRED_MODEL_RESOURCE_IDS:
            raise ValueError(
                "Model Resource readiness must contain every required resource in order."
            )

    @property
    def ready(self) -> bool:
        return all(item.ready for item in self.resources)


class ModelResourceInstallDisposition(StrEnum):
    INSTALLED = "installed"
    REUSED = "reused"
    REPAIRED = "repaired"


@dataclass(frozen=True)
class ModelResourceInstallResult:
    disposition: ModelResourceInstallDisposition
    readiness: ModelResourceReadiness

    def __post_init__(self) -> None:
        if not self.readiness.ready:
            raise ValueError("A Model Resource installation result must be ready.")


class ModelResourceAdapter(Protocol):
    @property
    def resource_id(self) -> ModelResourceId: ...

    def inspect(self, resource_root: Path) -> ModelResourceReadiness: ...

    def install(
        self,
        resource_root: Path,
        *,
        repair: bool,
    ) -> ModelResourceInstallResult: ...


def inspect_required_model_resources(
    resource_root: Path,
    adapters: tuple[ModelResourceAdapter, ...],
) -> ModelResourceReadinessReport:
    """Inspect every required resource through exactly one Adapter."""
    ordered = _ordered_adapters(adapters)
    return ModelResourceReadinessReport(
        resource_root=resource_root,
        resources=tuple(adapter.inspect(resource_root) for adapter in ordered),
    )


def install_model_resources(
    resource_root: Path,
    adapters: tuple[ModelResourceAdapter, ...],
    *,
    selected: tuple[ModelResourceId, ...],
    repair: bool,
) -> tuple[ModelResourceInstallResult, ...]:
    """Install selected resources in canonical order."""
    ordered = _ordered_adapters(adapters)
    requested = frozenset(selected or REQUIRED_MODEL_RESOURCE_IDS)
    if not requested.issubset(REQUIRED_MODEL_RESOURCE_IDS):
        raise ValueError("Model Resource selection contains an unsupported identifier.")
    return tuple(
        adapter.install(resource_root, repair=repair)
        for adapter in ordered
        if adapter.resource_id in requested
    )


def _ordered_adapters(
    adapters: tuple[ModelResourceAdapter, ...],
) -> tuple[ModelResourceAdapter, ...]:
    by_id = {adapter.resource_id: adapter for adapter in adapters}
    if len(by_id) != len(adapters) or set(by_id) != set(REQUIRED_MODEL_RESOURCE_IDS):
        raise ValueError("Exactly one Adapter is required for every Model Resource.")
    return tuple(by_id[resource_id] for resource_id in REQUIRED_MODEL_RESOURCE_IDS)
