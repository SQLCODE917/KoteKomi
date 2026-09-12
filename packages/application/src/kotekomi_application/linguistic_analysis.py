"""Tool-neutral linguistic analysis contracts for exact source text."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

_SHA256 = re.compile(r"^[a-f0-9]{64}$")
_LOCAL_TOKEN = re.compile(r"^t[1-9][0-9]*$")
_LOCAL_SENTENCE = re.compile(r"^s[1-9][0-9]*$")


class UniversalPartOfSpeech(StrEnum):
    """Universal part-of-speech values exposed across the Adapter boundary."""

    ADJECTIVE = "ADJ"
    ADPOSITION = "ADP"
    ADVERB = "ADV"
    AUXILIARY = "AUX"
    COORDINATING_CONJUNCTION = "CCONJ"
    DETERMINER = "DET"
    INTERJECTION = "INTJ"
    NOUN = "NOUN"
    NUMERAL = "NUM"
    PARTICLE = "PART"
    PRONOUN = "PRON"
    PROPER_NOUN = "PROPN"
    PUNCTUATION = "PUNCT"
    SUBORDINATING_CONJUNCTION = "SCONJ"
    SYMBOL = "SYM"
    VERB = "VERB"
    OTHER = "X"


@dataclass(frozen=True)
class LinguisticAnalysisInput:
    """Exact source text submitted to one LinguisticAnalyzer."""

    source_text: str

    def __post_init__(self) -> None:
        if not self.source_text:
            raise ValueError("Linguistic analysis requires non-empty source text.")


@dataclass(frozen=True)
class LinguisticToken:
    """One fallible linguistic annotation over exact source characters."""

    token_id: str
    sentence_id: str
    text: str
    start: int
    end: int
    lemma: str
    part_of_speech: UniversalPartOfSpeech
    dependency_relation: str
    head_token_id: str | None

    def __post_init__(self) -> None:
        if _LOCAL_TOKEN.fullmatch(self.token_id) is None:
            raise ValueError("LinguisticToken requires one ordered local ID.")
        if _LOCAL_SENTENCE.fullmatch(self.sentence_id) is None:
            raise ValueError("LinguisticToken requires one ordered sentence ID.")
        if self.end <= self.start or self.end - self.start != len(self.text):
            raise ValueError("LinguisticToken range does not match its text.")
        if not self.lemma:
            raise ValueError("LinguisticToken lemma must be non-empty.")
        if not self.dependency_relation:
            raise ValueError("LinguisticToken dependency relation must be non-empty.")
        is_root = self.dependency_relation.casefold() == "root"
        if is_root != (self.head_token_id is None):
            raise ValueError("Only a root LinguisticToken omits its dependency head.")
        if self.head_token_id is not None and _LOCAL_TOKEN.fullmatch(self.head_token_id) is None:
            raise ValueError("LinguisticToken dependency head requires one local token ID.")


@dataclass(frozen=True)
class LinguisticAnalysis:
    """One complete Adapter result bound to source text and model identity."""

    source_text_sha256: str
    producer_id: str
    model_id: str
    model_version: str
    resource_identity: str
    tokens: tuple[LinguisticToken, ...]

    def __post_init__(self) -> None:
        if _SHA256.fullmatch(self.source_text_sha256) is None:
            raise ValueError("LinguisticAnalysis requires one source SHA-256 digest.")
        if any(not value for value in (self.producer_id, self.model_id, self.model_version)):
            raise ValueError("LinguisticAnalysis model identity must be complete.")
        if _SHA256.fullmatch(self.resource_identity) is None:
            raise ValueError("LinguisticAnalysis requires one Resource Installation identity.")
        expected_ids = tuple(f"t{ordinal}" for ordinal in range(1, len(self.tokens) + 1))
        if tuple(item.token_id for item in self.tokens) != expected_ids:
            raise ValueError("LinguisticToken IDs must be complete and ordered.")
        token_ids = frozenset(expected_ids)
        token_by_id = {item.token_id: item for item in self.tokens}
        expected_sentence_ids: list[str] = []
        previous_end = 0
        for token in self.tokens:
            if token.start < previous_end:
                raise ValueError("LinguisticToken ranges must be ordered and non-overlapping.")
            if token.sentence_id not in expected_sentence_ids:
                expected_sentence_ids.append(token.sentence_id)
            if token.head_token_id is not None and token.head_token_id not in token_ids:
                raise ValueError("LinguisticToken dependency head is unavailable.")
            if (
                token.head_token_id is not None
                and token_by_id[token.head_token_id].sentence_id != token.sentence_id
            ):
                raise ValueError("LinguisticToken dependency head crosses a sentence boundary.")
            previous_end = token.end
        if tuple(expected_sentence_ids) != tuple(
            f"s{ordinal}" for ordinal in range(1, len(expected_sentence_ids) + 1)
        ):
            raise ValueError("LinguisticToken sentence IDs must be complete and ordered.")
        for sentence_id in expected_sentence_ids:
            roots = [
                item
                for item in self.tokens
                if item.sentence_id == sentence_id and item.head_token_id is None
            ]
            if len(roots) != 1:
                raise ValueError("Each linguistic sentence requires exactly one dependency root.")


class LinguisticAnalyzer(Protocol):
    """Port for fallible linguistic annotations over exact source text."""

    def analyze(self, request: LinguisticAnalysisInput) -> LinguisticAnalysis: ...
