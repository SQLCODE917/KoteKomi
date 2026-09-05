"""Pipeline composition for configured ModelRuntime Adapters."""

from __future__ import annotations

import hashlib
from typing import Protocol

from kotekomi_adapters import (
    LlamaServerModelRuntime,
    LMStudioModelRuntime,
    OllamaModelRuntime,
)
from kotekomi_application import (
    ModelExecutionReceipt,
    ModelIdentitySnapshot,
    ModelInputInspectionRequest,
    ModelInputMeasurement,
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
            tokenizer_id="fixture_whitespace_tokenizer_v1",
        )

    @property
    def task_deadline_seconds(self) -> float:
        return self.config.timeout_seconds

    @property
    def tokenizer_id(self) -> str:
        return self.configured_identity.tokenizer_id

    def count_tokens(self, rendered_input: bytes) -> int:
        return len(rendered_input.decode("utf-8").split())

    def inspect_model_input(self, request: ModelInputInspectionRequest) -> ModelInputMeasurement:
        return ModelInputMeasurement(
            model_identity_digest=model_identity_snapshot_digest(request.model_identity),
            runtime_identity="fixture",
            model_instance_id=self.config.model,
            tokenizer_id=self.tokenizer_id,
            prompt_template_identity="fixture_no_prompt_template_v1",
            logical_input_digest=request.logical_input_digest,
            formatted_input_digest=request.logical_input_digest,
            formatted_input_token_count=self.count_tokens(request.logical_input),
            loaded_context_limit=self.config.context_tokens,
        )

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
            configured_context_limit=self.config.context_tokens,
            loaded_context_limit=self.config.context_tokens,
            effective_context_limit=self.config.context_tokens,
        )

    def close(self) -> None:
        return None

    def run_model_task(self, task: ModelTaskRequest) -> ModelTaskResponse:
        if task.execution_spec.schema_id == "paragraph_hypothesis_text_v1":
            raw_output = b"abstain: fixture_no_claim\n"
        elif (
            task.execution_spec.schema_id == "hybrid_mention_task_text_v1"
            and task.task_type == "hybrid_mention_proposal"
        ):
            raw_output = b"abstain: fixture_no_mentions\n"
        elif task.execution_spec.schema_id == "hybrid_event_trigger_text_v1":
            raw_output = b"abstain: fixture_no_event\n"
        else:
            raw_output = b"outcome: abstain\nreason: fixture_no_claim\n"
        return ModelTaskResponse(
            raw_output=raw_output,
            execution_receipt=ModelExecutionReceipt(
                model_identity_digest=model_identity_snapshot_digest(self.configured_identity),
                generation_parameters_digest=generation_parameters_digest(
                    task.execution_spec.generation_parameters
                ),
                rendered_input_digest=hashlib.sha256(task.rendered_input).hexdigest(),
                input_token_count=task.input_admission.formatted_input_token_count,
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
