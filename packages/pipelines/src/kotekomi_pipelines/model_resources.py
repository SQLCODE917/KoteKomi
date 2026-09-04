"""Compose managed specialized-model resources for CLI and ingestion preflight."""

from __future__ import annotations

import json
import shlex
from pathlib import Path

from kotekomi_adapters import GlinerModelResourceAdapter, RefinedModelResourceAdapter
from kotekomi_application import (
    ModelResourceAdapter,
    ModelResourceId,
    ModelResourceInstallResult,
    ModelResourceReadinessReport,
    ModelResourceStatus,
    inspect_required_model_resources,
    install_model_resources,
)

from .config import PipelineConfig

MODEL_RESOURCE_STATUS_SCHEMA = "model_resource_status_v1"


def model_resource_adapters() -> tuple[ModelResourceAdapter, ...]:
    return (GlinerModelResourceAdapter(), RefinedModelResourceAdapter())


def inspect_configured_model_resources(
    config: PipelineConfig,
    *,
    adapters: tuple[ModelResourceAdapter, ...] | None = None,
) -> ModelResourceReadinessReport:
    return inspect_required_model_resources(
        config.model_resource_root,
        adapters or model_resource_adapters(),
    )


def install_configured_model_resources(
    config: PipelineConfig,
    *,
    selected: tuple[ModelResourceId, ...],
    repair: bool,
    adapters: tuple[ModelResourceAdapter, ...] | None = None,
) -> tuple[ModelResourceInstallResult, ...]:
    return install_model_resources(
        config.model_resource_root,
        adapters or model_resource_adapters(),
        selected=selected,
        repair=repair,
    )


def model_resource_report_json(report: ModelResourceReadinessReport) -> str:
    return json.dumps(_report_payload(report), sort_keys=True)


def model_resource_report_text(
    report: ModelResourceReadinessReport,
    *,
    config_path: Path | None,
) -> str:
    lines = [
        f"Model resources: {'ready' if report.ready else 'not ready'}",
        f"Resource root: {report.resource_root}",
    ]
    for readiness in report.resources:
        lines.append(f"{readiness.resource_id.value}: {readiness.status.value}")
        lines.extend(f"  {diagnostic}" for diagnostic in readiness.diagnostics)
    if not report.ready:
        lines.append(f"Run: {corrective_install_command(report, config_path=config_path)}")
    return "\n".join(lines)


def corrective_install_command(
    report: ModelResourceReadinessReport,
    *,
    config_path: Path | None,
) -> str:
    arguments = ["uv", "run", "kotekomi"]
    if config_path is not None:
        arguments.extend(("--config", str(config_path)))
    arguments.extend(("model", "resources", "install"))
    if any(
        item.status in {ModelResourceStatus.INCOMPLETE, ModelResourceStatus.IDENTITY_MISMATCH}
        for item in report.resources
    ):
        arguments.append("--repair")
    return shlex.join(arguments)


def _report_payload(report: ModelResourceReadinessReport) -> dict[str, object]:
    return {
        "schema_version": MODEL_RESOURCE_STATUS_SCHEMA,
        "status": "ready" if report.ready else "not_ready",
        "resource_root": str(report.resource_root),
        "resources": [
            {
                "resource_id": item.resource_id.value,
                "status": item.status.value,
                "root": str(item.root),
                "expected_identity": item.expected_identity,
                "observed_identity": item.observed_identity,
                "diagnostics": list(item.diagnostics),
            }
            for item in report.resources
        ],
    }
