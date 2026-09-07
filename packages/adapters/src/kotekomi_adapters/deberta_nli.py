"""Local-only DeBERTa natural-language-inference Adapter."""

from __future__ import annotations

import math
import time
from pathlib import Path
from typing import Protocol, cast

from kotekomi_application import (
    NaturalLanguageInferenceExecution,
    NaturalLanguageInferenceInput,
)

NLI_MODEL_ID = "cross-encoder/nli-deberta-v3-base"
NLI_MODEL_REVISION = "6c749ce3425cd33b46d187e45b92bbf96ee12ec7"


class _Predictor(Protocol):
    def __call__(self, premise: str, hypothesis: str) -> tuple[float, float, float]: ...


class _Tensor(Protocol):
    def __getitem__(self, index: int) -> _Tensor: ...

    def tolist(self) -> list[float]: ...


class _InputIds(Protocol):
    @property
    def shape(self) -> tuple[int, ...]: ...


class _ModelOutput(Protocol):
    logits: _Tensor


class _NliTokenizer(Protocol):
    def __call__(
        self,
        premise: str,
        hypothesis: str,
        *,
        padding: bool,
        truncation: bool,
        max_length: int,
        return_tensors: str,
    ) -> dict[str, object]: ...


class _NliModel(Protocol):
    def eval(self) -> object: ...

    def __call__(self, **features: object) -> _ModelOutput: ...


class DebertaNliAdapter:
    """Map local model logits into the Application Layer NLI contract."""

    def __init__(
        self,
        *,
        model_directory: Path,
        resource_identity: str,
        predictor: _Predictor | None = None,
    ) -> None:
        if not model_directory.is_absolute():
            raise ValueError("NLI model directory must be absolute.")
        if not resource_identity:
            raise ValueError("NLI resource identity must be non-empty.")
        self._model_directory = model_directory
        self._resource_identity = resource_identity
        self._predictor = predictor

    def classify(self, request: NaturalLanguageInferenceInput) -> NaturalLanguageInferenceExecution:
        started = time.monotonic()
        logits = (self._predictor or self._load_predictor())(request.premise, request.hypothesis)
        probabilities = _softmax(logits)
        return NaturalLanguageInferenceExecution(
            model_id=NLI_MODEL_ID,
            model_revision=NLI_MODEL_REVISION,
            resource_identity=self._resource_identity,
            contradiction_score=probabilities[0],
            entailment_score=probabilities[1],
            neutral_score=probabilities[2],
            elapsed_milliseconds=round((time.monotonic() - started) * 1000),
        )

    def _load_predictor(self) -> _Predictor:
        if not self._model_directory.is_dir():
            raise RuntimeError("The managed NLI model directory is unavailable.")
        try:
            import torch
            from transformers import AutoModelForSequenceClassification, AutoTokenizer
        except ImportError as error:
            raise RuntimeError("The pinned NLI runtime packages are unavailable.") from error
        tokenizer = cast(
            _NliTokenizer,
            AutoTokenizer.from_pretrained(  # pyright: ignore[reportUnknownMemberType]
                self._model_directory,
                local_files_only=True,
            ),
        )
        model = cast(
            _NliModel,
            AutoModelForSequenceClassification.from_pretrained(  # pyright: ignore[reportUnknownMemberType]
                self._model_directory,
                local_files_only=True,
                use_safetensors=True,
            ),
        )
        model.eval()

        def predict(premise: str, hypothesis: str) -> tuple[float, float, float]:
            features = tokenizer(
                premise,
                hypothesis,
                padding=True,
                truncation=False,
                max_length=512,
                return_tensors="pt",
            )
            _require_untruncated_input(features, maximum_tokens=512)
            with torch.no_grad():
                raw = model(**features).logits[0].tolist()
            if len(raw) != 3:
                raise RuntimeError("The NLI model returned an unexpected label shape.")
            return cast(tuple[float, float, float], tuple(raw))

        self._predictor = predict
        return predict


def _require_untruncated_input(features: dict[str, object], *, maximum_tokens: int) -> None:
    input_ids = features.get("input_ids")
    if input_ids is None or not hasattr(input_ids, "shape"):
        raise RuntimeError("The NLI tokenizer did not return input IDs.")
    shape = cast(_InputIds, input_ids).shape
    if len(shape) != 2 or shape[0] != 1 or shape[1] <= 0:
        raise RuntimeError("The NLI tokenizer returned an unexpected input shape.")
    if shape[1] > maximum_tokens:
        raise ValueError("The complete NLI premise and hypothesis exceed the model limit.")


def _softmax(logits: tuple[float, float, float]) -> tuple[float, float, float]:
    if any(not math.isfinite(item) for item in logits):
        raise ValueError("NLI logits must be finite.")
    maximum = max(logits)
    exponentials = tuple(math.exp(item - maximum) for item in logits)
    total = sum(exponentials)
    return cast(tuple[float, float, float], tuple(item / total for item in exponentials))
