"""Stanza Adapter for exact source-bound linguistic annotations."""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from pathlib import Path
from typing import Protocol, cast

from kotekomi_application import (
    LinguisticAnalysis,
    LinguisticAnalysisInput,
    LinguisticToken,
    UniversalPartOfSpeech,
)

STANZA_PACKAGE_VERSION = "1.14.0"
STANZA_MODEL_ID = "en_ewt"
STANZA_MODEL_VERSION = "1.14.0"


class _StanzaWord(Protocol):
    id: int
    text: str
    start_char: int | None
    end_char: int | None
    lemma: str | None
    upos: str | None
    deprel: str | None
    head: int


class _StanzaSentence(Protocol):
    @property
    def words(self) -> Sequence[_StanzaWord]: ...


class _StanzaDocument(Protocol):
    @property
    def sentences(self) -> Sequence[_StanzaSentence]: ...


class _StanzaPipeline(Protocol):
    def __call__(self, text: str) -> _StanzaDocument: ...


class StanzaLinguisticAnalyzer:
    """Map one pinned Stanza EWT result into Application Layer DTOs."""

    def __init__(
        self,
        *,
        model_directory: Path,
        resource_identity: str,
        pipeline: _StanzaPipeline | None = None,
    ) -> None:
        self._model_directory = model_directory.resolve()
        self._resource_identity = resource_identity
        self._pipeline = pipeline

    def analyze(self, request: LinguisticAnalysisInput) -> LinguisticAnalysis:
        pipeline = self._pipeline or _load_stanza_pipeline(self._model_directory)
        self._pipeline = pipeline
        document = pipeline(request.source_text)
        native_words = tuple(
            (sentence_ordinal, word)
            for sentence_ordinal, sentence in enumerate(document.sentences, 1)
            for word in sentence.words
        )
        local_ids = {
            (sentence_ordinal, word.id): f"t{token_ordinal}"
            for token_ordinal, (sentence_ordinal, word) in enumerate(native_words, 1)
        }
        tokens: list[LinguisticToken] = []
        for sentence_ordinal, word in native_words:
            if word.start_char is None or word.end_char is None:
                raise ValueError("Stanza token has no exact source range.")
            if request.source_text[word.start_char : word.end_char] != word.text:
                raise ValueError("Stanza token does not match exact source characters.")
            if not word.lemma or not word.upos or not word.deprel:
                raise ValueError("Stanza token is missing a required linguistic annotation.")
            try:
                part_of_speech = UniversalPartOfSpeech(word.upos)
            except ValueError as error:
                raise ValueError(
                    f"Stanza returned an unsupported part of speech: {word.upos}."
                ) from error
            head_token_id = None if word.head == 0 else local_ids.get((sentence_ordinal, word.head))
            if word.head != 0 and head_token_id is None:
                raise ValueError("Stanza dependency head does not map to a retained token.")
            tokens.append(
                LinguisticToken(
                    token_id=local_ids[(sentence_ordinal, word.id)],
                    sentence_id=f"s{sentence_ordinal}",
                    text=word.text,
                    start=word.start_char,
                    end=word.end_char,
                    lemma=word.lemma,
                    part_of_speech=part_of_speech,
                    dependency_relation=word.deprel.casefold(),
                    head_token_id=head_token_id,
                )
            )
        return LinguisticAnalysis(
            source_text_sha256=hashlib.sha256(request.source_text.encode()).hexdigest(),
            producer_id=f"stanza:{STANZA_PACKAGE_VERSION}",
            model_id=STANZA_MODEL_ID,
            model_version=STANZA_MODEL_VERSION,
            resource_identity=self._resource_identity,
            tokens=tuple(tokens),
        )


def _load_stanza_pipeline(model_directory: Path) -> _StanzaPipeline:
    if not model_directory.is_dir():
        raise FileNotFoundError(f"Stanza model directory is unavailable: {model_directory}")
    import stanza  # pyright: ignore[reportMissingTypeStubs]

    pipeline = stanza.Pipeline(
        "en",
        processors="tokenize,pos,lemma,depparse",
        package="ewt",
        dir=str(model_directory),
        download_method=stanza.DownloadMethod.NONE,
        use_gpu=False,
        verbose=False,
    )
    return cast(_StanzaPipeline, pipeline)
