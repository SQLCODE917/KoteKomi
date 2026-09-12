"""Local-only QANom Adapter for nominal Event proposals."""

from __future__ import annotations

import hashlib
import math
from collections.abc import Callable
from pathlib import Path
from typing import Protocol, cast

from kotekomi_application import (
    LinguisticToken,
    NominalizationAnalysis,
    NominalizationAnalysisInput,
    NominalizationCandidate,
    UniversalPartOfSpeech,
)

QANOM_MODEL_ID = "kleinay/nominalization-candidate-classifier"
QANOM_MODEL_REVISION = "45e4bddfa88473e390d89cab5de5868e7a8c2050"
QANOM_LEXICAL_RESOURCE_REVISION = "2bce70e8a39b40157ba97f38e1a8ae7619b30162"
QANOM_NOMINALIZATION_THRESHOLD = 0.45

type _NominalScorer = Callable[[str, tuple[LinguisticToken, ...]], tuple[tuple[float, float], ...]]


class _Tensor(Protocol):
    def __getitem__(self, index: int) -> _Tensor: ...

    def tolist(self) -> list[object]: ...


class _ModelOutput(Protocol):
    logits: _Tensor


class _Tokenizer(Protocol):
    def __call__(
        self,
        text: str,
        *,
        return_tensors: str,
        return_offsets_mapping: bool,
        truncation: bool,
    ) -> dict[str, object]: ...


class _Model(Protocol):
    def eval(self) -> object: ...

    def __call__(self, **features: object) -> _ModelOutput: ...


class QANomNominalizationAnalyzer:
    """Score lexical noun candidates without giving QANom authority over source spans."""

    def __init__(
        self,
        *,
        model_directory: Path,
        lexical_resource_directory: Path,
        resource_identity: str,
        scorer: _NominalScorer | None = None,
    ) -> None:
        if not model_directory.is_absolute() or not lexical_resource_directory.is_absolute():
            raise ValueError("QANom resource directories must be absolute.")
        if not resource_identity:
            raise ValueError("QANom resource identity must be non-empty.")
        self._model_directory = model_directory
        self._lexical_resource_directory = lexical_resource_directory
        self._resource_identity = resource_identity
        self._scorer = scorer
        self._lexical_candidates: frozenset[str] | None = None

    def analyze(self, request: NominalizationAnalysisInput) -> NominalizationAnalysis:
        source_digest = hashlib.sha256(request.source_text.encode()).hexdigest()
        if request.linguistic_analysis.source_text_sha256 != source_digest:
            raise ValueError("QANom linguistic analysis does not match its source text.")
        nouns = tuple(
            item
            for item in request.linguistic_analysis.tokens
            if item.part_of_speech is UniversalPartOfSpeech.NOUN
        )
        scores = (self._scorer or self._load_scorer())(request.source_text, nouns)
        if len(scores) != len(nouns):
            raise RuntimeError("QANom did not return one score pair for every noun.")
        lexical_candidates = self._lexical_candidates or self._load_lexical_candidates()
        self._lexical_candidates = lexical_candidates
        candidates = tuple(
            NominalizationCandidate(
                linguistic_token_id=token.token_id,
                text=token.text,
                start=token.start,
                end=token.end,
                lexical_candidate=token.text.casefold() in lexical_candidates,
                positive_logit=positive,
                negative_logit=negative,
                nominalization_probability=_nominalization_probability(positive, negative),
            )
            for token, (positive, negative) in zip(nouns, scores, strict=True)
        )
        return NominalizationAnalysis(
            source_text_sha256=source_digest,
            producer_id="qanom:nominalization-candidate-classifier",
            model_id=QANOM_MODEL_ID,
            model_revision=QANOM_MODEL_REVISION,
            resource_identity=self._resource_identity,
            threshold=QANOM_NOMINALIZATION_THRESHOLD,
            candidates=candidates,
        )

    def _load_scorer(self) -> _NominalScorer:
        if not self._model_directory.is_dir():
            raise RuntimeError("The managed QANom model directory is unavailable.")
        try:
            import torch
            from transformers import AutoModelForTokenClassification, AutoTokenizer
        except ImportError as error:
            raise RuntimeError("The pinned QANom runtime packages are unavailable.") from error
        tokenizer = cast(
            _Tokenizer,
            AutoTokenizer.from_pretrained(  # pyright: ignore[reportUnknownMemberType]
                self._model_directory,
                local_files_only=True,
            ),
        )
        model = cast(
            _Model,
            AutoModelForTokenClassification.from_pretrained(  # pyright: ignore[reportUnknownMemberType]
                self._model_directory,
                local_files_only=True,
            ),
        )
        model.eval()

        def score(
            source_text: str,
            nouns: tuple[LinguisticToken, ...],
        ) -> tuple[tuple[float, float], ...]:
            features = tokenizer(
                source_text,
                return_tensors="pt",
                return_offsets_mapping=True,
                truncation=False,
            )
            offset_value = features.pop("offset_mapping", None)
            if offset_value is None or not hasattr(offset_value, "__getitem__"):
                raise RuntimeError("QANom tokenizer did not return source offsets.")
            offsets_raw = cast(_Tensor, offset_value)[0].tolist()
            offsets = tuple(_offset_pair(item) for item in offsets_raw)
            with torch.no_grad():
                logits_raw = model(**features).logits[0].tolist()
            logits = tuple(_logit_pair(item) for item in logits_raw)
            if len(offsets) != len(logits):
                raise RuntimeError("QANom tokenizer offsets and model logits disagree.")
            result: list[tuple[float, float]] = []
            for noun in nouns:
                index = next(
                    (
                        ordinal
                        for ordinal, (start, end) in enumerate(offsets)
                        if start == noun.start and end > start
                    ),
                    None,
                )
                if index is None:
                    raise ValueError(f"QANom tokenizer has no exact subtoken for {noun.text!r}.")
                result.append(logits[index])
            return tuple(result)

        self._scorer = score
        return score

    def _load_lexical_candidates(self) -> frozenset[str]:
        catvar = self._lexical_resource_directory / "catvar21.signed"
        affixes = self._lexical_resource_directory / "nom_verb_pairs.txt"
        try:
            words = _catvar_nouns(catvar.read_text(encoding="utf-8"))
            words.update(_affix_nouns(affixes.read_text(encoding="utf-8")))
        except OSError as error:
            raise RuntimeError("The managed QANom lexical resources are unavailable.") from error
        return frozenset(words)


def _nominalization_probability(positive: float, negative: float) -> float:
    if not math.isfinite(positive) or not math.isfinite(negative):
        raise ValueError("QANom logits must be finite.")
    positive_probability = 1.0 / (1.0 + math.exp(-positive))
    negative_probability = 1.0 / (1.0 + math.exp(-negative))
    return (positive_probability + (1.0 - negative_probability)) / 2.0


def _catvar_nouns(payload: str) -> set[str]:
    result: set[str] = set()
    for line in payload.splitlines():
        for item in line.split("#"):
            try:
                word_and_part, _signature = item.split("%", 1)
                word, part_of_speech = word_and_part.rsplit("_", 1)
            except ValueError as error:
                raise ValueError("QANom CatVar data is malformed.") from error
            if part_of_speech == "N":
                result.add(word.casefold())
    return result


def _affix_nouns(payload: str) -> set[str]:
    result: set[str] = set()
    for line in payload.splitlines():
        if not line or "\t" not in line:
            continue
        result.add(line.split("\t", 1)[0].casefold())
    return result


def _offset_pair(value: object) -> tuple[int, int]:
    if not isinstance(value, list):
        raise RuntimeError("QANom tokenizer returned an invalid source offset.")
    items = cast(list[object], value)
    if len(items) != 2 or not all(isinstance(item, int) for item in items):
        raise RuntimeError("QANom tokenizer returned an invalid source offset.")
    return cast(int, items[0]), cast(int, items[1])


def _logit_pair(value: object) -> tuple[float, float]:
    if not isinstance(value, list):
        raise RuntimeError("QANom returned an invalid logit pair.")
    items = cast(list[object], value)
    if len(items) != 2 or not all(isinstance(item, int | float) for item in items):
        raise RuntimeError("QANom returned an invalid logit pair.")
    return float(cast(int | float, items[0])), float(cast(int | float, items[1]))
