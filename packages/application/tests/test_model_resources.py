from pathlib import Path

import pytest
from kotekomi_application import (
    REQUIRED_MODEL_RESOURCE_IDS,
    ModelResourceId,
    ModelResourceInstallDisposition,
    ModelResourceInstallResult,
    ModelResourceReadiness,
    ModelResourceStatus,
    inspect_required_model_resources,
    install_model_resources,
)


class _ResourceAdapter:
    def __init__(self, resource_id: ModelResourceId, status: ModelResourceStatus) -> None:
        self.resource_id = resource_id
        self.status = status
        self.install_calls: list[bool] = []

    def inspect(self, resource_root: Path) -> ModelResourceReadiness:
        identity = f"identity:{self.resource_id.value}"
        return ModelResourceReadiness(
            resource_id=self.resource_id,
            status=self.status,
            root=(resource_root / self.resource_id.value).resolve(),
            expected_identity=identity,
            observed_identity=identity if self.status is ModelResourceStatus.READY else None,
            diagnostics=() if self.status is ModelResourceStatus.READY else ("missing",),
        )

    def install(
        self,
        resource_root: Path,
        *,
        repair: bool,
    ) -> ModelResourceInstallResult:
        self.install_calls.append(repair)
        self.status = ModelResourceStatus.READY
        return ModelResourceInstallResult(
            ModelResourceInstallDisposition.INSTALLED,
            self.inspect(resource_root),
        )


def test_readiness_is_complete_ordered_and_requires_every_resource(tmp_path: Path) -> None:
    refined = _ResourceAdapter(REQUIRED_MODEL_RESOURCE_IDS[1], ModelResourceStatus.MISSING)
    gliner = _ResourceAdapter(REQUIRED_MODEL_RESOURCE_IDS[0], ModelResourceStatus.READY)

    report = inspect_required_model_resources(tmp_path.resolve(), (refined, gliner))

    assert tuple(item.resource_id for item in report.resources) == REQUIRED_MODEL_RESOURCE_IDS
    assert report.ready is False
    with pytest.raises(ValueError, match="Exactly one Adapter"):
        inspect_required_model_resources(tmp_path.resolve(), (gliner,))


def test_installation_selects_resources_in_canonical_order(tmp_path: Path) -> None:
    gliner = _ResourceAdapter(REQUIRED_MODEL_RESOURCE_IDS[0], ModelResourceStatus.MISSING)
    refined = _ResourceAdapter(REQUIRED_MODEL_RESOURCE_IDS[1], ModelResourceStatus.MISSING)

    results = install_model_resources(
        tmp_path.resolve(),
        (refined, gliner),
        selected=(ModelResourceId.REFINED_WIKIPEDIA_V1,),
        repair=True,
    )

    assert tuple(item.readiness.resource_id for item in results) == (
        ModelResourceId.REFINED_WIKIPEDIA_V1,
    )
    assert gliner.install_calls == []
    assert refined.install_calls == [True]


def test_ready_and_non_ready_contracts_fail_fast(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="ready Model Resource"):
        ModelResourceReadiness(
            resource_id=ModelResourceId.GLINER_MENTION_PROPOSER_V1,
            status=ModelResourceStatus.READY,
            root=tmp_path.resolve(),
            expected_identity="expected",
            observed_identity=None,
            diagnostics=(),
        )
    with pytest.raises(ValueError, match="requires diagnostics"):
        ModelResourceReadiness(
            resource_id=ModelResourceId.GLINER_MENTION_PROPOSER_V1,
            status=ModelResourceStatus.MISSING,
            root=tmp_path.resolve(),
            expected_identity="expected",
            observed_identity=None,
            diagnostics=(),
        )
