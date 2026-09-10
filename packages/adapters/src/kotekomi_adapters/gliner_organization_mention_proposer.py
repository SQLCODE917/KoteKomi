"""GLiNER implementation of the Organization mention proposer Port."""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable, Generator
from contextlib import contextmanager
from importlib.metadata import version
from pathlib import Path
from typing import Protocol, cast

from kotekomi_application import (
    MentionProposal,
    MentionProposalBatch,
    MentionProposalInput,
    OrganizationMentionProposal,
    OrganizationMentionProposalBatch,
    OrganizationMentionProposalInput,
)

GLINER_PACKAGE_VERSION = "0.2.28"
GLINER_MODEL_ID = "urchade/gliner_medium-v2.1"
GLINER_MODEL_REVISION = "40ec419335d09393f298636f471328b722c6da9e"
GLINER_TOKENIZER_ID = "microsoft/deberta-v3-base"
GLINER_TOKENIZER_REVISION = "8ccc9b6f36199bec6961081d44eb72fb3f7353f3"
GLINER_LABEL = "organization"
GLINER_THRESHOLD = 0.5
GLINER_DEVICE = "cpu"
_TRANSFORMERS_TOKENIZER_LOGGER = "transformers.tokenization_utils_tokenizers"
_MISTRAL_REGEX_WARNING_FRAGMENT = (
    "with an incorrect regex pattern: "
    "https://huggingface.co/mistralai/"
    "Mistral-Small-3.1-24B-Instruct-2503/discussions/84"
)


class _GlinerModel(Protocol):
    def predict_entities(
        self,
        text: str,
        labels: list[str],
        *,
        threshold: float,
    ) -> list[dict[str, object]]: ...


type _ModelLoader = Callable[[Path, str], _GlinerModel]
type _MonotonicClock = Callable[[], float]


class _PinnedDebertaMistralRegexWarningFilter(logging.Filter):
    def __init__(self, model_directory: Path) -> None:
        super().__init__()
        self._message_prefix = f"The tokenizer you are loading from '{model_directory}'"

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        return not (
            message.startswith(self._message_prefix) and _MISTRAL_REGEX_WARNING_FRAGMENT in message
        )


def load_gliner_model(model_directory: Path, device: str) -> _GlinerModel:
    """Load the pinned local GLiNER model without changing DeBERTa tokenization."""
    from gliner import GLiNER  # pyright: ignore[reportMissingTypeStubs]

    loader = cast(
        Callable[..., object],
        GLiNER.from_pretrained,  # pyright: ignore[reportUnknownMemberType]
    )
    with _suppress_false_mistral_regex_warning(model_directory):
        return cast(
            _GlinerModel,
            loader(str(model_directory), map_location=device, local_files_only=True),
        )


@contextmanager
def _suppress_false_mistral_regex_warning(
    model_directory: Path,
) -> Generator[None]:
    """Hide a Transformers 5.8.1 misclassification, not a real tokenizer defect.

    Transformers flags large local tokenizers whose model config omits its
    historical ``transformers_version``.  This pinned resource is DeBERTa-v3
    SentencePiece.  Applying ``fix_mistral_regex=True`` would replace its
    intended pre-tokenizer with Mistral's regex and change GLiNER input tokens.
    """
    if not _is_pinned_deberta_sentencepiece_resource(model_directory):
        yield
        return
    logger = logging.getLogger(_TRANSFORMERS_TOKENIZER_LOGGER)
    warning_filter = _PinnedDebertaMistralRegexWarningFilter(model_directory)
    logger.addFilter(warning_filter)
    try:
        yield
    finally:
        logger.removeFilter(warning_filter)


def _is_pinned_deberta_sentencepiece_resource(model_directory: Path) -> bool:
    gliner_config = _load_json_object(model_directory / "gliner_config.json")
    model_config = _load_json_object(model_directory / "config.json")
    tokenizer_config = _load_json_object(model_directory / "tokenizer_config.json")
    return (
        gliner_config is not None
        and gliner_config.get("model_name") == GLINER_TOKENIZER_ID
        and model_config is not None
        and model_config.get("model_type") == "deberta-v2"
        and tokenizer_config is not None
        and tokenizer_config.get("vocab_type") == "spm"
        and (model_directory / "spm.model").is_file()
    )


def _load_json_object(path: Path) -> dict[str, object] | None:
    try:
        value = cast(object, json.loads(path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(value, dict):
        return None
    return cast(dict[str, object], value)


class GlinerOrganizationMentionProposer:
    """Propose fallible Organization spans with one immutable GLiNER model."""

    def __init__(
        self,
        *,
        model_directory: Path,
        model_loader: _ModelLoader = load_gliner_model,
        monotonic_clock: _MonotonicClock = time.monotonic,
    ) -> None:
        installed_version = version("gliner")
        if installed_version != GLINER_PACKAGE_VERSION:
            raise RuntimeError(
                f"GLiNER package version must be {GLINER_PACKAGE_VERSION}; "
                f"found {installed_version}."
            )
        self._clock = monotonic_clock
        started = self._clock()
        self._model = model_loader(model_directory, GLINER_DEVICE)
        self._load_elapsed_milliseconds = _elapsed_milliseconds(started, self._clock())

    @property
    def load_elapsed_milliseconds(self) -> int:
        return self._load_elapsed_milliseconds

    def propose(
        self, proposal_input: OrganizationMentionProposalInput
    ) -> OrganizationMentionProposalBatch:
        started = self._clock()
        raw_results = self._model.predict_entities(
            proposal_input.source_text,
            [GLINER_LABEL],
            threshold=GLINER_THRESHOLD,
        )
        completed = self._clock()
        proposals = tuple(_proposal_from_gliner(item) for item in raw_results)
        return OrganizationMentionProposalBatch(
            proposer_id=f"gliner:{GLINER_PACKAGE_VERSION}",
            model_id=GLINER_MODEL_ID,
            model_revision=GLINER_MODEL_REVISION,
            threshold=GLINER_THRESHOLD,
            load_elapsed_milliseconds=self._load_elapsed_milliseconds,
            inference_elapsed_milliseconds=_elapsed_milliseconds(started, completed),
            proposals=proposals,
        )


class GlinerMentionProposer:
    """Propose broad mention spans with the pinned GLiNER model."""

    def __init__(
        self,
        *,
        model_directory: Path,
        model_loader: _ModelLoader = load_gliner_model,
        monotonic_clock: _MonotonicClock = time.monotonic,
    ) -> None:
        installed_version = version("gliner")
        if installed_version != GLINER_PACKAGE_VERSION:
            raise RuntimeError(
                f"GLiNER package version must be {GLINER_PACKAGE_VERSION}; "
                f"found {installed_version}."
            )
        self._clock = monotonic_clock
        self._model_directory = model_directory
        self._model_loader = model_loader
        self._model: _GlinerModel | None = None
        self._load_elapsed_milliseconds = 0

    @property
    def load_elapsed_milliseconds(self) -> int:
        return self._load_elapsed_milliseconds

    def propose(self, proposal_input: MentionProposalInput) -> MentionProposalBatch:
        if self._model is None:
            load_started = self._clock()
            self._model = self._model_loader(self._model_directory, GLINER_DEVICE)
            self._load_elapsed_milliseconds = _elapsed_milliseconds(
                load_started,
                self._clock(),
            )
        started = self._clock()
        proposals: list[MentionProposal] = []
        requested_labels = list(proposal_input.type_hints)
        for segment in proposal_input.source_segments:
            raw_results = self._model.predict_entities(
                segment.exact_text,
                requested_labels,
                threshold=GLINER_THRESHOLD,
            )
            proposals.extend(
                _generic_proposal_from_gliner(item, segment.label, proposal_input.type_hints)
                for item in raw_results
            )
        completed = self._clock()
        return MentionProposalBatch(
            proposer_id=f"gliner:{GLINER_PACKAGE_VERSION}",
            model_id=GLINER_MODEL_ID,
            model_revision=GLINER_MODEL_REVISION,
            configuration=(
                ("device", GLINER_DEVICE),
                ("threshold", GLINER_THRESHOLD),
                ("tokenizer_id", GLINER_TOKENIZER_ID),
                ("tokenizer_revision", GLINER_TOKENIZER_REVISION),
            ),
            load_elapsed_milliseconds=self._load_elapsed_milliseconds,
            inference_elapsed_milliseconds=_elapsed_milliseconds(started, completed),
            proposals=tuple(proposals),
        )


def _proposal_from_gliner(value: dict[str, object]) -> OrganizationMentionProposal:
    required = {"text", "start", "end", "score", "label"}
    if set(value) != required:
        raise ValueError("GLiNER result fields do not match the pinned Adapter contract.")
    text = value["text"]
    start = value["start"]
    end = value["end"]
    score = value["score"]
    label = value["label"]
    if not isinstance(text, str) or not text:
        raise ValueError("GLiNER result text must be a non-empty string.")
    if type(start) is not int or type(end) is not int:
        raise ValueError("GLiNER result positions must be integers.")
    if not isinstance(score, (int, float)) or isinstance(score, bool):
        raise ValueError("GLiNER result score must be numeric.")
    if label != GLINER_LABEL:
        raise ValueError("GLiNER result label does not match the requested label.")
    return OrganizationMentionProposal(text, start, end, float(score))


def _generic_proposal_from_gliner(
    value: dict[str, object],
    source_segment_label: str,
    requested_labels: tuple[str, ...],
) -> MentionProposal:
    required = {"text", "start", "end", "score", "label"}
    if set(value) != required:
        raise ValueError("GLiNER result fields do not match the pinned Adapter contract.")
    text = value["text"]
    start = value["start"]
    end = value["end"]
    score = value["score"]
    label = value["label"]
    if not isinstance(text, str) or not text:
        raise ValueError("GLiNER result text must be a non-empty string.")
    if type(start) is not int or type(end) is not int:
        raise ValueError("GLiNER result positions must be integers.")
    if not isinstance(score, (int, float)) or isinstance(score, bool):
        raise ValueError("GLiNER result score must be numeric.")
    if not isinstance(label, str) or label not in requested_labels:
        raise ValueError("GLiNER result label does not match a requested label.")
    return MentionProposal(
        source_segment_label=source_segment_label,
        text=text,
        start=start,
        end=end,
        type_hints=(label,),
        score=float(score),
    )


def _elapsed_milliseconds(started: float, completed: float) -> int:
    if completed < started:
        raise RuntimeError("GLiNER monotonic clock moved backwards.")
    return round((completed - started) * 1000)
