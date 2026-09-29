"""Focused data-in/data-out tests for R4 decontextualization composition."""

from __future__ import annotations

import hashlib
from typing import Literal

from kotekomi_application import (
    AttachmentSourceRange,
    ConstituentCandidateInventory,
    ConstituentSelectionAnswer,
    ConstituentSelectionStatus,
    DecontextualizationAttributionKind,
    DecontextualizationHoldReason,
    DecontextualizationStatus,
    DecontextualizedProposition,
    EventEntityLinguisticToken,
    EventModality,
    EventPolarity,
    ParserConstituent,
    build_decontextualized_proposition,
    parser_constituent_id,
)
from kotekomi_application.decontextualization_composition import (
    DecontextualizationEntityRef,
)

TGE002_SOURCE = (
    "Anthropic CEO Dario Amodei criticized the artificial intelligence investment project Stargate."
)
TGE025_SOURCE = "Sacks stated that Anthropic was running a sophisticated strategy."


def _words(
    source: str, specs: list[tuple[str, str | None, str, str]]
) -> tuple[EventEntityLinguisticToken, ...]:
    positions: dict[str, tuple[int, int]] = {}
    offset = 0
    for word, *_ in specs:
        start = source.index(word, offset)
        end = start + len(word)
        positions[word] = (start, end)
        offset = end
    by_word = {word: f"t{i}" for i, word in enumerate(positions, start=1)}
    tokens: list[EventEntityLinguisticToken] = []
    for word, head, deprel, lemma in specs:
        start, end = positions[word]
        tokens.append(
            EventEntityLinguisticToken(
                token_id=by_word[word],
                sentence_id="s1",
                text=word,
                start=start,
                end=end,
                lemma=lemma,
                part_of_speech="NOUN",
                dependency_relation=deprel,
                head_token_id=by_word[head] if head else None,
            )
        )
    return tuple(tokens)


def _span(source: str, start_word: str, end_word: str) -> AttachmentSourceRange:
    start = source.index(start_word)
    end = source.index(end_word) + len(end_word)
    return AttachmentSourceRange(start=start, end=end, text=source[start:end])


def _constituent(
    source: str,
    event_id: str,
    token_ids: tuple[str, ...],
    start_word: str,
    end_word: str,
) -> ParserConstituent:
    span = _span(source, start_word, end_word)
    digest = hashlib.sha256(source.encode()).hexdigest()
    return ParserConstituent(
        constituent_id=parser_constituent_id(digest, span.start, span.end),
        event_id=event_id,
        source_text_sha256=digest,
        constituent_range=span,
        token_ids=token_ids,
    )


def _entity(
    entity_id: str,
    kind: Literal["actor", "organization"],
    name: str,
    source: str,
    start_word: str,
    end_word: str,
) -> DecontextualizationEntityRef:
    return DecontextualizationEntityRef(
        entity_id=entity_id,
        entity_kind=kind,
        canonical_name=name,
        accepted_source_occurrences=(_span(source, start_word, end_word),),
    )


TGE002_TOKENS = _words(
    TGE002_SOURCE,
    [
        ("Anthropic", "Amodei", "compound", "anthropic"),
        ("CEO", "Amodei", "compound", "ceo"),
        ("Dario", "Amodei", "compound", "dario"),
        ("Amodei", "criticized", "nsubj", "amodei"),
        ("criticized", None, "root", "criticize"),
        ("the", "Stargate", "det", "the"),
        ("artificial", "Stargate", "compound", "artificial"),
        ("intelligence", "Stargate", "compound", "intelligence"),
        ("investment", "Stargate", "compound", "investment"),
        ("project", "Stargate", "compound", "project"),
        ("Stargate", "criticized", "obj", "stargate"),
    ],
)

TGE002_ENTITIES = (_entity("EGE-001", "actor", "Dario Amodei", TGE002_SOURCE, "Dario", "Amodei"),)


def _tge002_inventory() -> ConstituentCandidateInventory:
    digest = hashlib.sha256(TGE002_SOURCE.encode()).hexdigest()
    return ConstituentCandidateInventory(
        event_id="TGE-002",
        source_text_sha256=digest,
        constituents=(
            _constituent(TGE002_SOURCE, "TGE-002", ("t1", "t2", "t3", "t4"), "Anthropic", "Amodei"),
            _constituent(
                TGE002_SOURCE,
                "TGE-002",
                ("t1", "t2", "t3", "t4", "t5", "t6", "t7", "t8", "t9", "t10", "t11"),
                "Anthropic",
                "Stargate",
            ),
            _constituent(TGE002_SOURCE, "TGE-002", ("t5",), "criticized", "criticized"),
            _constituent(
                TGE002_SOURCE,
                "TGE-002",
                ("t6", "t7", "t8", "t9", "t10", "t11"),
                "the",
                "Stargate",
            ),
        ),
    )


def _answer(event_id: str, status: ConstituentSelectionStatus, indexes: tuple[int, ...]):
    return ConstituentSelectionAnswer(
        event_id=event_id, status=status, selected_label_indexes=indexes
    )


def _compose_tge002(
    answer: ConstituentSelectionAnswer,
    tokens: tuple[EventEntityLinguisticToken, ...] = TGE002_TOKENS,
    entities: tuple[DecontextualizationEntityRef, ...] = TGE002_ENTITIES,
) -> DecontextualizedProposition:
    digest = hashlib.sha256(TGE002_SOURCE.encode()).hexdigest()
    head = next(token for token in tokens if token.lemma == "criticize")
    return build_decontextualized_proposition(
        event_id="TGE-002",
        source_text=TGE002_SOURCE,
        source_text_sha256=digest,
        inventory=_tge002_inventory(),
        answer=answer,
        trigger_head_start=head.start,
        trigger_head_end=head.end,
        tokens=tokens,
        entities=entities,
    )


def test_tge002_composes_subject_object_relation_and_narrator() -> None:
    result = _compose_tge002(_answer("TGE-002", ConstituentSelectionStatus.SELECTED, (1, 2, 3, 4)))
    assert result.status is DecontextualizationStatus.PROPOSITION
    assert result.hold_reason is None
    assert result.relation_label == "criticize"
    assert result.subject is not None
    assert result.subject.role.value == "subject"
    assert result.subject.exact_fragment.text == "Anthropic CEO Dario Amodei"
    assert result.subject.entity_ref == "EGE-001"
    assert result.object is not None
    assert result.object.role.value == "object"
    assert result.object.entity_ref is None
    assert result.object.object_value == "the artificial intelligence investment project Stargate"
    assert result.polarity is EventPolarity.AFFIRMED
    assert result.modality is EventModality.ACTUAL
    assert result.attribution is not None
    assert result.attribution.kind is DecontextualizationAttributionKind.SOURCE_NARRATOR
    assert result.attribution.exact_carrier is None
    assert result.attribution.reporter_ref is None


def test_rejected_selection_holds_with_no_roles() -> None:
    result = _compose_tge002(_answer("TGE-002", ConstituentSelectionStatus.REJECTED, ()))
    assert result.status is DecontextualizationStatus.HELD
    assert result.hold_reason is DecontextualizationHoldReason.SELECTION_REJECTED
    assert result.subject is None and result.object is None and result.attribution is None


def test_none_selection_holds_with_selection_empty() -> None:
    result = _compose_tge002(_answer("TGE-002", ConstituentSelectionStatus.NONE, ()))
    assert result.status is DecontextualizationStatus.HELD
    assert result.hold_reason is DecontextualizationHoldReason.SELECTION_EMPTY


def test_missing_subject_holds_with_subject_unavailable() -> None:
    source = "criticized the artificial intelligence investment project Stargate."
    tokens = _words(
        source,
        [
            ("criticized", None, "root", "criticize"),
            ("the", "Stargate", "det", "the"),
            ("artificial", "Stargate", "compound", "artificial"),
            ("intelligence", "Stargate", "compound", "intelligence"),
            ("investment", "Stargate", "compound", "investment"),
            ("project", "Stargate", "compound", "project"),
            ("Stargate", "criticized", "obj", "stargate"),
        ],
    )
    digest = hashlib.sha256(source.encode()).hexdigest()
    inventory = ConstituentCandidateInventory(
        event_id="TGE-002",
        source_text_sha256=digest,
        constituents=(
            _constituent(source, "TGE-002", ("t1",), "criticized", "criticized"),
            _constituent(
                source, "TGE-002", ("t2", "t3", "t4", "t5", "t6", "t7"), "the", "Stargate"
            ),
        ),
    )
    head = next(token for token in tokens if token.lemma == "criticize")
    result = build_decontextualized_proposition(
        event_id="TGE-002",
        source_text=source,
        source_text_sha256=digest,
        inventory=inventory,
        answer=_answer("TGE-002", ConstituentSelectionStatus.SELECTED, (1, 2)),
        trigger_head_start=head.start,
        trigger_head_end=head.end,
        tokens=tokens,
        entities=(),
    )
    assert result.status is DecontextualizationStatus.HELD
    assert result.hold_reason is DecontextualizationHoldReason.SUBJECT_UNAVAILABLE
    assert result.subject is None
    assert result.relation_label is None


def test_neg_dependent_records_negated_polarity() -> None:
    source = "Bob did not criticize the plan."
    tokens = _words(
        source,
        [
            ("Bob", "criticize", "nsubj", "bob"),
            ("did", "criticize", "aux", "do"),
            ("not", "criticize", "neg", "not"),
            ("criticize", None, "root", "criticize"),
            ("the", "plan", "det", "the"),
            ("plan", "criticize", "obj", "plan"),
        ],
    )
    digest = hashlib.sha256(source.encode()).hexdigest()
    inventory = ConstituentCandidateInventory(
        event_id="TGE-001",
        source_text_sha256=digest,
        constituents=(
            _constituent(source, "TGE-001", ("t1",), "Bob", "Bob"),
            _constituent(source, "TGE-001", ("t4",), "criticize", "criticize"),
            _constituent(source, "TGE-001", ("t5", "t6"), "the", "plan"),
        ),
    )
    entities = (_entity("EGE-001", "actor", "Bob", source, "Bob", "Bob"),)
    head = next(token for token in tokens if token.lemma == "criticize")
    result = build_decontextualized_proposition(
        event_id="TGE-001",
        source_text=source,
        source_text_sha256=digest,
        inventory=inventory,
        answer=_answer("TGE-001", ConstituentSelectionStatus.SELECTED, (1, 2, 3)),
        trigger_head_start=head.start,
        trigger_head_end=head.end,
        tokens=tokens,
        entities=entities,
    )
    assert result.status is DecontextualizationStatus.PROPOSITION
    assert result.polarity is EventPolarity.NEGATED


def test_targeted_attribution_names_sacks_reporter() -> None:
    tokens = _words(
        TGE025_SOURCE,
        [
            ("Sacks", "stated", "nsubj", "sacks"),
            ("stated", None, "root", "state"),
            ("that", "running", "mark", "that"),
            ("Anthropic", "running", "nsubj", "anthropic"),
            ("was", "running", "aux", "be"),
            ("running", "stated", "ccomp", "run"),
            ("a", "strategy", "det", "a"),
            ("sophisticated", "strategy", "amod", "sophisticated"),
            ("strategy", "running", "obj", "strategy"),
        ],
    )
    digest = hashlib.sha256(TGE025_SOURCE.encode()).hexdigest()
    inventory = ConstituentCandidateInventory(
        event_id="TGE-025",
        source_text_sha256=digest,
        constituents=(
            _constituent(
                TGE025_SOURCE,
                "TGE-025",
                ("t1", "t2", "t3", "t4", "t5", "t6", "t7", "t8", "t9"),
                "Sacks",
                "strategy",
            ),
            _constituent(TGE025_SOURCE, "TGE-025", ("t4",), "Anthropic", "Anthropic"),
            _constituent(TGE025_SOURCE, "TGE-025", ("t6",), "running", "running"),
        ),
    )
    entities = (
        _entity("EGE-035", "organization", "Anthropic", TGE025_SOURCE, "Anthropic", "Anthropic"),
        _entity("EGE-092", "actor", "Sacks", TGE025_SOURCE, "Sacks", "Sacks"),
    )
    head = next(token for token in tokens if token.lemma == "run")
    result = build_decontextualized_proposition(
        event_id="TGE-025",
        source_text=TGE025_SOURCE,
        source_text_sha256=digest,
        inventory=inventory,
        answer=_answer("TGE-025", ConstituentSelectionStatus.SELECTED, (1, 2, 3)),
        trigger_head_start=head.start,
        trigger_head_end=head.end,
        tokens=tokens,
        entities=entities,
    )
    assert result.status is DecontextualizationStatus.PROPOSITION
    assert result.attribution is not None
    assert result.attribution.kind is DecontextualizationAttributionKind.TARGETED
    assert result.attribution.exact_carrier is not None
    assert result.attribution.exact_carrier.text == "Sacks stated"
    assert result.attribution.reporter_ref == "EGE-092"
