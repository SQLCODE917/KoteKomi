"""Pipeline composition for configured ModelRuntime Adapters."""

from __future__ import annotations

import hashlib
import json
from typing import Protocol

from kotekomi_adapters import (
    LlamaServerModelRuntime,
    LMStudioModelRuntime,
    OllamaModelRuntime,
)
from kotekomi_application import (
    ModelExecutionReceipt,
    ModelIdentitySnapshot,
    ModelRuntimeReadiness,
    ModelRuntimeStatus,
    ModelTaskRequest,
    ModelTaskResponse,
    ModelTaskRuntime,
    generation_parameters_digest,
    model_identity_snapshot_digest,
)

from kotekomi_pipelines.config import ModelExecutionConfig


class ExecutableModelRuntime(ModelTaskRuntime, Protocol):
    def check_readiness(self) -> ModelRuntimeStatus: ...


class FixtureModelTaskRuntime:
    """An explicit deterministic runtime for Pipeline fixture tests."""

    def __init__(self, config: ModelExecutionConfig) -> None:
        self.config = config

    @property
    def configured_identity(self) -> ModelIdentitySnapshot:
        return ModelIdentitySnapshot(
            name=self.config.model,
            weights_digest=None,
            runtime="fixture",
            tokenizer_id="lm_studio_whitespace_v1",
        )

    @property
    def task_deadline_seconds(self) -> float:
        return self.config.timeout_seconds

    def check_readiness(self) -> ModelRuntimeStatus:
        return ModelRuntimeStatus(
            adapter="fixture",
            endpoint=self.config.endpoint,
            model=self.config.model,
            reachable=True,
            model_available=True,
            model_state="available",
            idle_slots=None,
            total_slots=None,
            ready=True,
        )

    def run_model_task(self, task: ModelTaskRequest) -> ModelTaskResponse:
        raw_output = json.dumps(
            {
                "kind": "abstain",
                "schema_id": task.execution_spec.schema_id,
                "reason": "fixture_no_claim",
            },
            separators=(",", ":"),
        ).encode()
        return ModelTaskResponse(
            raw_output=raw_output,
            execution_receipt=ModelExecutionReceipt(
                model_identity_digest=model_identity_snapshot_digest(self.configured_identity),
                generation_parameters_digest=generation_parameters_digest(
                    task.execution_spec.generation_parameters
                ),
                rendered_input_digest=hashlib.sha256(task.rendered_input).hexdigest(),
                input_token_count=len(task.rendered_input.decode("utf-8").split()),
                output_token_count=None,
            ),
        )


def build_model_runtime_readiness(config: ModelExecutionConfig) -> ModelRuntimeReadiness:
    if config.adapter == "fixture":
        raise ValueError("model status requires lm_studio, llama_server, or ollama runtime.")
    if config.adapter == "lm_studio":
        return LMStudioModelRuntime(
            endpoint=config.endpoint,
            model=config.model,
            timeout_seconds=config.timeout_seconds,
            context_tokens=config.context_tokens,
            max_output_tokens=config.max_output_tokens,
        )
    if config.adapter == "llama_server":
        return LlamaServerModelRuntime(
            endpoint=config.endpoint,
            model=config.model,
            timeout_seconds=config.timeout_seconds,
            context_tokens=config.context_tokens,
            max_output_tokens=config.max_output_tokens,
        )
    if config.adapter == "ollama":
        return OllamaModelRuntime(
            endpoint=config.endpoint,
            model=config.model,
            timeout_seconds=config.timeout_seconds,
            context_tokens=config.context_tokens,
            max_output_tokens=config.max_output_tokens,
        )
    raise ValueError(f"Unsupported model runtime: {config.adapter}")


def build_model_task_runtime(config: ModelExecutionConfig) -> ExecutableModelRuntime:
    """Build the configured runtime only when it can execute staged model tasks."""
    if config.adapter == "lm_studio":
        return LMStudioModelRuntime(
            endpoint=config.endpoint,
            model=config.model,
            timeout_seconds=config.timeout_seconds,
            context_tokens=config.context_tokens,
            max_output_tokens=config.max_output_tokens,
        )
    if config.adapter == "fixture":
        return FixtureModelTaskRuntime(config)
    raise ValueError(f"Automatic extraction requires a task runtime: {config.adapter}")
