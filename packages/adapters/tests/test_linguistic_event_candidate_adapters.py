from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import pytest
from kotekomi_adapters.qanom_nominalization import QANomNominalizationAnalyzer
from kotekomi_adapters.stanza_linguistic_analysis import StanzaLinguisticAnalyzer
from kotekomi_application import (
    LinguisticAnalysis,
    LinguisticAnalysisInput,
    LinguisticToken,
    NominalizationAnalysisInput,
    UniversalPartOfSpeech,
)


@dataclass
class _Word:
    id: int
    text: str
    start_char: int | None
    end_char: int | None
    lemma: str | None
    upos: str | None
    deprel: str | None
    head: int


@dataclass
class _Sentence:
    words: tuple[_Word, ...]


@dataclass
class _Document:
    sentences: tuple[_Sentence, ...]


class _Pipeline:
    def __init__(self, document: _Document) -> None:
        self.document = document

    def __call__(self, text: str) -> _Document:
        assert text == "Anthropic–DoD partnered."
        return self.document


def _document(*, changed: bool = False, upos: str = "PROPN") -> _Document:
    return _Document(
        (
            _Sentence(
                (
                    _Word(
                        1,
                        "Changed" if changed else "Anthropic",
                        0,
                        9,
                        "Anthropic",
                        upos,
                        "nsubj",
                        4,
                    ),
                    _Word(2, "–", 9, 10, "–", "PUNCT", "punct", 4),
                    _Word(3, "DoD", 10, 13, "DoD", "PROPN", "appos", 1),
                    _Word(4, "partnered", 14, 23, "partner", "VERB", "root", 0),
                    _Word(5, ".", 23, 24, ".", "PUNCT", "punct", 4),
                )
            ),
        )
    )


def test_stanza_adapter_preserves_exact_unicode_offsets_and_dependencies(
    tmp_path: Path,
) -> None:
    result = StanzaLinguisticAnalyzer(
        model_directory=tmp_path,
        resource_identity="a" * 64,
        pipeline=_Pipeline(_document()),
    ).analyze(LinguisticAnalysisInput("Anthropic–DoD partnered."))

    assert (
        result.source_text_sha256 == hashlib.sha256("Anthropic–DoD partnered.".encode()).hexdigest()
    )
    assert result.model_id == "en_ewt"
    assert result.resource_identity == "a" * 64
    assert [(item.token_id, item.sentence_id, item.text) for item in result.tokens] == [
        ("t1", "s1", "Anthropic"),
        ("t2", "s1", "–"),
        ("t3", "s1", "DoD"),
        ("t4", "s1", "partnered"),
        ("t5", "s1", "."),
    ]
    assert result.tokens[3].head_token_id is None
    assert result.tokens[0].head_token_id == "t4"


@pytest.mark.parametrize(
    ("document", "message"),
    [
        (_document(changed=True), "exact source characters"),
        (_document(upos="UNKNOWN"), "unsupported part of speech"),
    ],
)
def test_stanza_adapter_rejects_invalid_boundary_output(
    tmp_path: Path,
    document: _Document,
    message: str,
) -> None:
    analyzer = StanzaLinguisticAnalyzer(
        model_directory=tmp_path,
        resource_identity="a" * 64,
        pipeline=_Pipeline(document),
    )

    with pytest.raises(ValueError, match=message):
        analyzer.analyze(LinguisticAnalysisInput("Anthropic–DoD partnered."))


def test_qanom_adapter_scores_only_source_bound_common_nouns(tmp_path: Path) -> None:
    source = "They reached an agreement."
    analysis = LinguisticAnalysis(
        source_text_sha256=hashlib.sha256(source.encode()).hexdigest(),
        producer_id="fixture",
        model_id="fixture",
        model_version="1",
        resource_identity="a" * 64,
        tokens=(
            LinguisticToken(
                "t1", "s1", "They", 0, 4, "they", UniversalPartOfSpeech.PRONOUN, "nsubj", "t2"
            ),
            LinguisticToken(
                "t2", "s1", "reached", 5, 12, "reach", UniversalPartOfSpeech.VERB, "root", None
            ),
            LinguisticToken(
                "t3", "s1", "an", 13, 15, "a", UniversalPartOfSpeech.DETERMINER, "det", "t4"
            ),
            LinguisticToken(
                "t4",
                "s1",
                "agreement",
                16,
                25,
                "agreement",
                UniversalPartOfSpeech.NOUN,
                "obj",
                "t2",
            ),
            LinguisticToken(
                "t5", "s1", ".", 25, 26, ".", UniversalPartOfSpeech.PUNCTUATION, "punct", "t2"
            ),
        ),
    )
    lexical = tmp_path / "lexical"
    lexical.mkdir()
    (lexical / "catvar21.signed").write_text("agreement_N%fixture", encoding="utf-8")
    (lexical / "nom_verb_pairs.txt").write_text("", encoding="utf-8")
    analyzer = QANomNominalizationAnalyzer(
        model_directory=(tmp_path / "model").resolve(),
        lexical_resource_directory=lexical.resolve(),
        resource_identity="b" * 64,
        scorer=lambda _text, nouns: tuple((2.0, -2.0) for _ in nouns),
    )

    result = analyzer.analyze(NominalizationAnalysisInput(source, analysis))

    assert len(result.candidates) == 1
    candidate = result.candidates[0]
    assert candidate.text == "agreement"
    assert candidate.lexical_candidate is True
    assert candidate.nominalization_probability > result.threshold
