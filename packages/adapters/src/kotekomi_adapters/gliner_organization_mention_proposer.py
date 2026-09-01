"""GLiNER implementation of the Organization mention proposer Port."""

from __future__ import annotations

import time
from collections.abc import Callable
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
GLINER_LABEL = "organization"
GLINER_THRESHOLD = 0.5
GLINER_DEVICE = "cpu"


class _GlinerModel(Protocol):
    def predict_entities(
        self,
        text: str,
        labels: list[str],
        *,
        threshold: float,
    ) -> list[dict[str, object]]: ...


type _ModelLoader = Callable[[str, str, str], _GlinerModel]
type _MonotonicClock = Callable[[], float]


def _load_model(model_id: str, revision: str, device: str) -> _GlinerModel:
    from gliner import GLiNER  # pyright: ignore[reportMissingTypeStubs]
    from huggingface_hub import snapshot_download  # pyright: ignore[reportUnknownVariableType]

    model_path = snapshot_download(repo_id=model_id, revision=revision, dry_run=False)
    loader = cast(
        Callable[..., object],
        GLiNER.from_pretrained,  # pyright: ignore[reportUnknownMemberType]
    )
    return cast(_GlinerModel, loader(str(Path(model_path)), map_location=device))


class GlinerOrganizationMentionProposer:
    """Propose fallible Organization spans with one immutable GLiNER model."""

    def __init__(
        self,
        *,
        model_loader: _ModelLoader = _load_model,
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
        self._model = model_loader(GLINER_MODEL_ID, GLINER_MODEL_REVISION, GLINER_DEVICE)
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
        model_loader: _ModelLoader = _load_model,
        monotonic_clock: _MonotonicClock = time.monotonic,
    ) -> None:
        installed_version = version("gliner")
        if installed_version != GLINER_PACKAGE_VERSION:
            raise RuntimeError(
                f"GLiNER package version must be {GLINER_PACKAGE_VERSION}; "
                f"found {installed_version}."
            )
        self._clock = monotonic_clock
        self._model_loader = model_loader
        self._model: _GlinerModel | None = None
        self._load_elapsed_milliseconds = 0

    @property
    def load_elapsed_milliseconds(self) -> int:
        return self._load_elapsed_milliseconds

    def propose(self, proposal_input: MentionProposalInput) -> MentionProposalBatch:
        if self._model is None:
            load_started = self._clock()
            self._model = self._model_loader(
                GLINER_MODEL_ID,
                GLINER_MODEL_REVISION,
                GLINER_DEVICE,
            )
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
