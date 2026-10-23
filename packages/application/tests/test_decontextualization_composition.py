"""Focused data-in/data-out tests for R4 decontextualization composition."""

from __future__ import annotations

import hashlib
from typing import Literal

import pytest
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
    DecontextualizationExclusion,
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


def _exclusion(
    exclusion_id: str,
    source: str,
    start_word: str,
    end_word: str,
) -> DecontextualizationExclusion:
    return DecontextualizationExclusion(
        exclusion_id=exclusion_id,
        contextual_kind="non_entity_value",
        source_range=_span(source, start_word, end_word),
        rationale="Reviewed exclusion: the span is not an Actor or Organization.",
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


def _compose(
    *,
    event_id: str,
    source: str,
    tokens: tuple[EventEntityLinguisticToken, ...],
    constituents: tuple[ParserConstituent, ...],
    selected_indexes: tuple[int, ...],
    entities: tuple[DecontextualizationEntityRef, ...],
    head_lemma: str,
    subject_value_authorizations: tuple[DecontextualizationExclusion, ...] = (),
) -> DecontextualizedProposition:
    digest = hashlib.sha256(source.encode()).hexdigest()
    head = next(token for token in tokens if token.lemma == head_lemma)
    inventory = ConstituentCandidateInventory(
        event_id=event_id,
        source_text_sha256=digest,
        constituents=constituents,
    )
    return build_decontextualized_proposition(
        event_id=event_id,
        source_text=source,
        source_text_sha256=digest,
        inventory=inventory,
        answer=_answer(event_id, ConstituentSelectionStatus.SELECTED, selected_indexes),
        trigger_head_start=head.start,
        trigger_head_end=head.end,
        tokens=tokens,
        entities=entities,
        subject_value_authorizations=subject_value_authorizations,
    )


def test_advmod_negation_and_modal_derive_negated_hypothetical_content() -> None:
    source = "Mira would not sign the agreement."
    tokens = _words(
        source,
        [
            ("Mira", "sign", "nsubj", "mira"),
            ("would", "sign", "aux", "would"),
            ("not", "sign", "advmod", "not"),
            ("sign", None, "root", "sign"),
            ("the", "agreement", "det", "the"),
            ("agreement", "sign", "obj", "agreement"),
        ],
    )
    constituents = (
        _constituent(source, "AHE-903", ("t1",), "Mira", "Mira"),
        _constituent(source, "AHE-903", ("t4",), "sign", "sign"),
        _constituent(source, "AHE-903", ("t5", "t6"), "the", "agreement"),
    )
    entities = (_entity("EGE-901", "actor", "Mira", source, "Mira", "Mira"),)
    result = _compose(
        event_id="AHE-903",
        source=source,
        tokens=tokens,
        constituents=constituents,
        selected_indexes=(1, 2, 3),
        entities=entities,
        head_lemma="sign",
    )
    assert result.status is DecontextualizationStatus.PROPOSITION
    assert result.relation_label == "sign"
    assert result.subject is not None
    assert result.subject.entity_ref == "EGE-901"
    assert result.subject.exact_fragment.text == "Mira"
    assert result.object is not None
    assert result.object.object_value == "the agreement"
    assert result.polarity is EventPolarity.NEGATED
    assert result.modality is EventModality.HYPOTHETICAL
    assert result.attribution is not None
    assert result.attribution.kind is DecontextualizationAttributionKind.SOURCE_NARRATOR


def test_copular_predicate_adjective_composes_copula_relation_and_subject_value() -> None:
    source = "The April order is not final."
    tokens = _words(
        source,
        [
            ("The", "order", "det", "the"),
            ("April", "order", "compound", "april"),
            ("order", "final", "nsubj", "order"),
            ("is", "final", "cop", "be"),
            ("not", "final", "advmod", "not"),
            ("final", None, "root", "final"),
        ],
    )
    constituents = (_constituent(source, "AHE-051", ("t1", "t2", "t3"), "The", "order"),)
    result = _compose(
        event_id="AHE-051",
        source=source,
        tokens=tokens,
        constituents=constituents,
        selected_indexes=(1,),
        entities=(),
        head_lemma="final",
        subject_value_authorizations=(_exclusion("EGX-051", source, "The", "order"),),
    )
    assert result.status is DecontextualizationStatus.PROPOSITION
    assert result.relation_label == "is"
    assert result.relation_range is not None
    assert result.relation_range.text == "is"
    assert result.relation_range.start == 16
    assert result.relation_range.end == 18
    assert result.subject is not None
    assert result.subject.entity_ref is None
    assert result.subject.subject_value == "The April order"
    assert result.subject.exact_fragment.text == "The April order"
    assert result.object is not None
    assert result.object.object_value == "final"
    assert result.object.exact_fragment.text == "final"
    assert result.polarity is EventPolarity.NEGATED
    assert result.modality is EventModality.ACTUAL
    assert result.attribution is not None
    assert result.attribution.kind is DecontextualizationAttributionKind.SOURCE_NARRATOR


def test_subject_without_entity_or_exclusion_holds_subject_unavailable() -> None:
    source = "The April order is not final."
    tokens = _words(
        source,
        [
            ("The", "order", "det", "the"),
            ("April", "order", "compound", "april"),
            ("order", "final", "nsubj", "order"),
            ("is", "final", "cop", "be"),
            ("not", "final", "advmod", "not"),
            ("final", None, "root", "final"),
        ],
    )
    constituents = (_constituent(source, "AHE-051", ("t1", "t2", "t3"), "The", "order"),)
    result = _compose(
        event_id="AHE-051",
        source=source,
        tokens=tokens,
        constituents=constituents,
        selected_indexes=(1,),
        entities=(),
        head_lemma="final",
    )
    assert result.status is DecontextualizationStatus.HELD
    assert result.hold_reason is DecontextualizationHoldReason.SUBJECT_UNAVAILABLE
    assert result.subject is None and result.object is None and result.relation_label is None


def test_subject_value_authorization_requires_source_exact_span() -> None:
    source = "The April order is not final."
    tokens = _words(
        source,
        [
            ("The", "order", "det", "the"),
            ("April", "order", "compound", "april"),
            ("order", "final", "nsubj", "order"),
            ("is", "final", "cop", "be"),
            ("not", "final", "advmod", "not"),
            ("final", None, "root", "final"),
        ],
    )
    constituents = (_constituent(source, "AHE-051", ("t1", "t2", "t3"), "The", "order"),)
    result = _compose(
        event_id="AHE-051",
        source=source,
        tokens=tokens,
        constituents=constituents,
        selected_indexes=(1,),
        entities=(),
        head_lemma="final",
        subject_value_authorizations=(_exclusion("EGX-051", source, "The", "is"),),
    )
    assert result.status is DecontextualizationStatus.HELD
    assert result.hold_reason is DecontextualizationHoldReason.SUBJECT_UNAVAILABLE


def test_subject_value_authorization_rejects_overlapping_authorizations() -> None:
    source = "The April order is not final."
    tokens = _words(
        source,
        [
            ("The", "order", "det", "the"),
            ("April", "order", "compound", "april"),
            ("order", "final", "nsubj", "order"),
            ("is", "final", "cop", "be"),
            ("not", "final", "advmod", "not"),
            ("final", None, "root", "final"),
        ],
    )
    constituents = (_constituent(source, "AHE-051", ("t1", "t2", "t3"), "The", "order"),)
    with pytest.raises(ValueError, match="overlap"):
        _compose(
            event_id="AHE-051",
            source=source,
            tokens=tokens,
            constituents=constituents,
            selected_indexes=(1,),
            entities=(),
            head_lemma="final",
            subject_value_authorizations=(
                _exclusion("EGX-051", source, "The", "order"),
                _exclusion("EGX-052", source, "The", "is"),
            ),
        )


def test_oblique_time_place_holds_unsupported_time_place() -> None:
    source = "Sacks viewed the documents in April."
    tokens = _words(
        source,
        [
            ("Sacks", "viewed", "nsubj", "sacks"),
            ("viewed", None, "root", "view"),
            ("the", "documents", "det", "the"),
            ("documents", "viewed", "obj", "document"),
            ("in", "April", "case", "in"),
            ("April", "viewed", "obl", "april"),
        ],
    )
    constituents = (
        _constituent(source, "AHE-902", ("t1",), "Sacks", "Sacks"),
        _constituent(source, "AHE-902", ("t2",), "viewed", "viewed"),
        _constituent(source, "AHE-902", ("t3", "t4"), "the", "documents"),
        _constituent(source, "AHE-902", ("t5", "t6"), "in", "April"),
    )
    entities = (_entity("EGE-902", "actor", "Sacks", source, "Sacks", "Sacks"),)
    result = _compose(
        event_id="AHE-902",
        source=source,
        tokens=tokens,
        constituents=constituents,
        selected_indexes=(1, 2, 3),
        entities=entities,
        head_lemma="view",
    )
    assert result.status is DecontextualizationStatus.HELD
    assert result.hold_reason is DecontextualizationHoldReason.UNSUPPORTED_TIME_PLACE
    assert result.relation_label is None and result.relation_range is None
    assert result.subject is None and result.object is None


def test_coordinated_subject_holds_unsupported_coordination() -> None:
    source = "Sacks and Amodei viewed the decision."
    tokens = _words(
        source,
        [
            ("Sacks", "viewed", "nsubj", "sacks"),
            ("and", "Amodei", "cc", "and"),
            ("Amodei", "Sacks", "conj", "amodei"),
            ("viewed", None, "root", "view"),
            ("the", "decision", "det", "the"),
            ("decision", "viewed", "obj", "decision"),
        ],
    )
    constituents = (
        _constituent(source, "AHE-904", ("t1",), "Sacks", "Sacks"),
        _constituent(source, "AHE-904", ("t3",), "Amodei", "Amodei"),
        _constituent(source, "AHE-904", ("t4",), "viewed", "viewed"),
        _constituent(source, "AHE-904", ("t5", "t6"), "the", "decision"),
    )
    entities = (
        _entity("EGE-903", "actor", "Sacks", source, "Sacks", "Sacks"),
        _entity("EGE-904", "actor", "Amodei", source, "Amodei", "Amodei"),
    )
    result = _compose(
        event_id="AHE-904",
        source=source,
        tokens=tokens,
        constituents=constituents,
        selected_indexes=(1, 2, 3, 4),
        entities=entities,
        head_lemma="view",
    )
    assert result.status is DecontextualizationStatus.HELD
    assert result.hold_reason is DecontextualizationHoldReason.UNSUPPORTED_COORDINATION
    assert result.subject is None and result.object is None and result.relation_label is None


def test_indirect_object_dependent_routes_to_object_role() -> None:
    source = "Sacks emailed Amodei."
    tokens = _words(
        source,
        [
            ("Sacks", "emailed", "nsubj", "sacks"),
            ("emailed", None, "root", "email"),
            ("Amodei", "emailed", "iobj", "amodei"),
        ],
    )
    constituents = (
        _constituent(source, "TGE-900", ("t1",), "Sacks", "Sacks"),
        _constituent(source, "TGE-900", ("t2",), "emailed", "emailed"),
        _constituent(source, "TGE-900", ("t3",), "Amodei", "Amodei"),
    )
    entities = (_entity("EGE-905", "actor", "Sacks", source, "Sacks", "Sacks"),)
    result = _compose(
        event_id="TGE-900",
        source=source,
        tokens=tokens,
        constituents=constituents,
        selected_indexes=(1, 2, 3),
        entities=entities,
        head_lemma="email",
    )
    assert result.status is DecontextualizationStatus.PROPOSITION
    assert result.subject is not None
    assert result.subject.entity_ref == "EGE-905"
    assert result.object is not None
    assert result.object.entity_ref is None
    assert result.object.object_value == "Amodei"
