"""Tool-neutral nominal Event proposal contracts over exact source text."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Protocol

from kotekomi_application.linguistic_analysis import LinguisticAnalysis

_SHA256 = re.compile(r"^[a-f0-9]{64}$")
_LOCAL_TOKEN = re.compile(r"^t[1-9][0-9]*$")


@dataclass(frozen=True)
class NominalizationAnalysisInput:
    """Exact source text and validated syntax supplied to one proposer."""

    source_text: str
    linguistic_analysis: LinguisticAnalysis

    def __post_init__(self) -> None:
        if not self.source_text:
            raise ValueError("Nominalization analysis requires non-empty source text.")


@dataclass(frozen=True)
class NominalizationCandidate:
    """One fallible QANom score bound to a source-owned linguistic token."""

    linguistic_token_id: str
    text: str
    start: int
    end: int
    lexical_candidate: bool
    positive_logit: float
    negative_logit: float
    nominalization_probability: float

    def __post_init__(self) -> None:
        if _LOCAL_TOKEN.fullmatch(self.linguistic_token_id) is None:
            raise ValueError("NominalizationCandidate requires one linguistic token ID.")
        if self.end <= self.start or self.end - self.start != len(self.text):
            raise ValueError("NominalizationCandidate range does not match its text.")
        if not all(math.isfinite(item) for item in (self.positive_logit, self.negative_logit)):
            raise ValueError("NominalizationCandidate logits must be finite.")
        if not 0.0 <= self.nominalization_probability <= 1.0:
            raise ValueError("NominalizationCandidate probability must be between zero and one.")


@dataclass(frozen=True)
class NominalizationAnalysis:
    """One complete specialized-model result with reproducible identity."""

    source_text_sha256: str
    producer_id: str
    model_id: str
    model_revision: str
    resource_identity: str
    threshold: float
    candidates: tuple[NominalizationCandidate, ...]

    def __post_init__(self) -> None:
        if _SHA256.fullmatch(self.source_text_sha256) is None:
            raise ValueError("NominalizationAnalysis requires one source SHA-256 digest.")
        if any(not value for value in (self.producer_id, self.model_id, self.model_revision)):
            raise ValueError("NominalizationAnalysis model identity must be complete.")
        if _SHA256.fullmatch(self.resource_identity) is None:
            raise ValueError("NominalizationAnalysis requires one Resource Installation identity.")
        if not 0.0 <= self.threshold <= 1.0:
            raise ValueError("NominalizationAnalysis threshold must be between zero and one.")
        token_ids = tuple(item.linguistic_token_id for item in self.candidates)
        if len(set(token_ids)) != len(token_ids):
            raise ValueError("NominalizationAnalysis repeats a linguistic token.")
        ranges = tuple((item.start, item.end) for item in self.candidates)
        if ranges != tuple(sorted(ranges)):
            raise ValueError("NominalizationCandidates must remain in source order.")


class NominalizationAnalyzer(Protocol):
    """Port for fallible nominal Event proposals."""

    def analyze(self, request: NominalizationAnalysisInput) -> NominalizationAnalysis: ...
