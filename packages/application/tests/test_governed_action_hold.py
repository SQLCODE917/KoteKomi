"""Focused rules for holding an unrepresented governed action.

The captured authorization names its recipient as the direct object and attaches
the permitted action as a `to`-marked verbal complement. These data-in/data-out
tests pin that shape and its near misses without a parser mock or model call.
"""

from __future__ import annotations

import hashlib
from typing import Literal

import pytest
from kotekomi_application import (
    ConstituentCandidateInventory,
    ConstituentSelectionAnswer,
    ConstituentSelectionStatus,
    DecontextualizationHoldReason,
    DecontextualizationStatus,
    DecontextualizedProposition,
    EventEntityLinguisticToken,
    ParserConstituent,
    SourceRange,
    build_decontextualized_proposition,
    derive_object_content_completion,
    parser_constituent_id,
)
from kotekomi_application.decontextualization_composition import (
    DecontextualizationEntityRef,
    ObjectContentCompletion,
    derive_unrepresented_governed_actions,
)


def _span(source: str, start_word: str, end_word: str) -> SourceRange:
    start = source.index(start_word)
    end = source.index(end_word) + len(end_word)
    return SourceRange(start=start, end=end, text=source[start:end])


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


def _typed_words(
    source: str, specs: list[tuple[str, str | None, str, str, str]]
) -> tuple[EventEntityLinguisticToken, ...]:
    """Build source-exact tokens with explicit part-of-speech labels."""
    positions: dict[str, tuple[int, int]] = {}
    offset = 0
    for word, _head, _deprel, _lemma, _pos in specs:
        start = source.index(word, offset)
        end = start + len(word)
        positions[word] = (start, end)
        offset = end
    by_word = {word: f"t{i}" for i, word in enumerate(positions, start=1)}
    tokens: list[EventEntityLinguisticToken] = []
    for word, head, deprel, lemma, pos in specs:
        start, end = positions[word]
        tokens.append(
            EventEntityLinguisticToken(
                token_id=by_word[word],
                sentence_id="s1",
                text=word,
                start=start,
                end=end,
                lemma=lemma,
                part_of_speech=pos,
                dependency_relation=deprel,
                head_token_id=by_word[head] if head else None,
            )
        )
    return tuple(tokens)


def _compose(
    *,
    event_id: str,
    source: str,
    tokens: tuple[EventEntityLinguisticToken, ...],
    constituents: tuple[ParserConstituent, ...],
    selected_indexes: tuple[int, ...],
    entities: tuple[DecontextualizationEntityRef, ...],
    head_lemma: str,
    object_completion: ObjectContentCompletion | None = None,
) -> DecontextualizedProposition:
    digest = hashlib.sha256(source.encode()).hexdigest()
    head = next(token for token in tokens if token.lemma == head_lemma)
    return build_decontextualized_proposition(
        event_id=event_id,
        source_text=source,
        source_text_sha256=digest,
        inventory=ConstituentCandidateInventory(
            event_id=event_id,
            source_text_sha256=digest,
            constituents=constituents,
        ),
        answer=ConstituentSelectionAnswer(
            event_id=event_id,
            status=ConstituentSelectionStatus.SELECTED,
            selected_label_indexes=selected_indexes,
        ),
        trigger_head_start=head.start,
        trigger_head_end=head.end,
        tokens=tokens,
        entities=entities,
        object_completion=object_completion,
    )


GOVERNED_ACTION_SOURCE = (
    "The Department of Homeland Security authorized its workers to use "
    "commercial artificial intelligence systems until May 2025."
)


def _governed_action_tokens(
    source: str, trigger: str, trigger_lemma: str
) -> tuple[EventEntityLinguisticToken, ...]:
    """Rebuild the captured authorization dependency shape with one trigger verb."""
    return _typed_words(
        source,
        [
            ("The", "Department", "det", "the", "DET"),
            ("Department", trigger, "nsubj", "department", "PROPN"),
            ("of", "Department", "case", "of", "ADP"),
            ("Homeland", "Department", "compound", "homeland", "PROPN"),
            ("Security", "Department", "compound", "security", "PROPN"),
            (trigger, None, "root", trigger_lemma, "VERB"),
            ("its", "workers", "det", "its", "PRON"),
            ("workers", trigger, "obj", "worker", "NOUN"),
            ("to", "use", "mark", "to", "PART"),
            ("use", trigger, "xcomp", "use", "VERB"),
            ("commercial", "systems", "amod", "commercial", "ADJ"),
            ("artificial", "intelligence", "compound", "artificial", "ADJ"),
            ("intelligence", "systems", "compound", "intelligence", "NOUN"),
            ("systems", "use", "obj", "system", "NOUN"),
            ("until", "May", "case", "until", "ADP"),
            ("May", "use", "obl", "may", "PROPN"),
            ("2025", "May", "nmod:unmarked", "2025", "NUM"),
        ],
    )


def _governed_action_constituents(source: str, trigger: str) -> tuple[ParserConstituent, ...]:
    return (
        _constituent(source, "AHE-911", ("t1", "t2", "t3", "t4", "t5"), "The", "Security"),
        _constituent(source, "AHE-911", ("t6",), trigger, trigger),
        _constituent(source, "AHE-911", ("t7", "t8"), "its", "workers"),
    )


@pytest.mark.parametrize(
    ("trigger", "trigger_lemma"),
    [("authorized", "authorize"), ("permitted", "permit")],
)
def test_governed_verbal_complement_outside_the_object_holds(
    trigger: str, trigger_lemma: str
) -> None:
    """The captured authorization shape drops its action; a new verb must hold too."""
    source = GOVERNED_ACTION_SOURCE.replace("authorized", trigger)
    tokens = _governed_action_tokens(source, trigger, trigger_lemma)
    entities = (
        _entity(
            "EGE-911",
            "organization",
            "Department of Homeland Security",
            source,
            "Department",
            "Security",
        ),
    )
    result = _compose(
        event_id="AHE-911",
        source=source,
        tokens=tokens,
        constituents=_governed_action_constituents(source, trigger),
        selected_indexes=(1, 2, 3),
        entities=entities,
        head_lemma=trigger_lemma,
    )
    assert result.status is DecontextualizationStatus.HELD
    assert result.hold_reason is DecontextualizationHoldReason.UNSUPPORTED_PREDICATE_COMPLEMENT
    assert result.relation_label is None and result.subject is None and result.object is None

    actions = derive_unrepresented_governed_actions(
        source_text=source,
        tokens=tokens,
        trigger_head_start=source.index(trigger),
        trigger_head_end=source.index(trigger) + len(trigger),
        represented_ranges=(
            _span(source, "The", "Security"),
            _span(source, "its", "workers"),
        ),
    )
    assert len(actions) == 1
    assert actions[0].text == ("to use commercial artificial intelligence systems until May 2025")


def test_missing_subject_identity_precedes_the_governed_action_hold() -> None:
    """Existing subject diagnostics stay ahead of the new predicate-complement hold."""
    source = GOVERNED_ACTION_SOURCE
    tokens = _governed_action_tokens(source, "authorized", "authorize")
    result = _compose(
        event_id="AHE-911",
        source=source,
        tokens=tokens,
        constituents=_governed_action_constituents(source, "authorized"),
        selected_indexes=(1, 2, 3),
        entities=(),
        head_lemma="authorize",
    )
    assert result.status is DecontextualizationStatus.HELD
    assert result.hold_reason is DecontextualizationHoldReason.SUBJECT_UNAVAILABLE


def test_complement_governed_by_another_verb_does_not_hold() -> None:
    """A `to` complement beneath another trigger is outside this rule."""
    source = "Sacks viewed the plan while Amodei wanted to change it."
    tokens = _typed_words(
        source,
        [
            ("Sacks", "viewed", "nsubj", "sacks", "PROPN"),
            ("viewed", None, "root", "view", "VERB"),
            ("the", "plan", "det", "the", "DET"),
            ("plan", "viewed", "obj", "plan", "NOUN"),
            ("while", "wanted", "mark", "while", "SCONJ"),
            ("Amodei", "wanted", "nsubj", "amodei", "PROPN"),
            ("wanted", "viewed", "advcl", "want", "VERB"),
            ("to", "change", "mark", "to", "PART"),
            ("change", "wanted", "xcomp", "change", "VERB"),
            ("it", "change", "obj", "it", "PRON"),
        ],
    )
    constituents = (
        _constituent(source, "AHE-912", ("t1",), "Sacks", "Sacks"),
        _constituent(source, "AHE-912", ("t2",), "viewed", "viewed"),
        _constituent(source, "AHE-912", ("t3", "t4"), "the", "plan"),
    )
    entities = (_entity("EGE-912", "actor", "Sacks", source, "Sacks", "Sacks"),)
    result = _compose(
        event_id="AHE-912",
        source=source,
        tokens=tokens,
        constituents=constituents,
        selected_indexes=(1, 2, 3),
        entities=entities,
        head_lemma="view",
    )
    assert result.status is DecontextualizationStatus.PROPOSITION
    assert result.hold_reason is None
    assert result.object is not None and result.object.object_value == "the plan"


def test_direct_complement_without_to_does_not_hold() -> None:
    """A bare open complement is not this rule's `to`-marked shape."""
    source = "Sacks watched Amodei change the plan."
    tokens = _typed_words(
        source,
        [
            ("Sacks", "watched", "nsubj", "sacks", "PROPN"),
            ("watched", None, "root", "watch", "VERB"),
            ("Amodei", "watched", "obj", "amodei", "PROPN"),
            ("change", "watched", "xcomp", "change", "VERB"),
            ("the", "plan", "det", "the", "DET"),
            ("plan", "change", "obj", "plan", "NOUN"),
        ],
    )
    constituents = (
        _constituent(source, "AHE-913", ("t1",), "Sacks", "Sacks"),
        _constituent(source, "AHE-913", ("t2",), "watched", "watched"),
        _constituent(source, "AHE-913", ("t3",), "Amodei", "Amodei"),
    )
    entities = (_entity("EGE-913", "actor", "Sacks", source, "Sacks", "Sacks"),)
    result = _compose(
        event_id="AHE-913",
        source=source,
        tokens=tokens,
        constituents=constituents,
        selected_indexes=(1, 2, 3),
        entities=entities,
        head_lemma="watch",
    )
    assert result.status is DecontextualizationStatus.PROPOSITION
    assert result.hold_reason is None
    assert result.object is not None and result.object.object_value == "Amodei"


def test_supported_object_completion_without_a_governed_action_composes() -> None:
    """The supported participial completion stays compositional."""
    source = "Amodei published a post praising fraud."
    tokens = _typed_words(
        source,
        [
            ("Amodei", "published", "nsubj", "amodei", "PROPN"),
            ("published", None, "root", "publish", "VERB"),
            ("a", "post", "det", "a", "DET"),
            ("post", "published", "obj", "post", "NOUN"),
            ("praising", "post", "acl", "praise", "VERB"),
            ("fraud", "praising", "obj", "fraud", "NOUN"),
        ],
    )
    constituents = (
        _constituent(source, "AHE-914", ("t1",), "Amodei", "Amodei"),
        _constituent(source, "AHE-914", ("t2",), "published", "published"),
        _constituent(source, "AHE-914", ("t3", "t4"), "a", "post"),
    )
    entities = (_entity("EGE-914", "actor", "Amodei", source, "Amodei", "Amodei"),)
    completion = derive_object_content_completion(
        event_id="AHE-914",
        source_text=source,
        tokens=tokens,
        selected_object_range=_span(source, "a", "post"),
    )
    assert completion is not None
    result = _compose(
        event_id="AHE-914",
        source=source,
        tokens=tokens,
        constituents=constituents,
        selected_indexes=(1, 2, 3),
        entities=entities,
        head_lemma="publish",
        object_completion=completion,
    )
    assert result.status is DecontextualizationStatus.PROPOSITION
    assert result.hold_reason is None
    assert result.object is not None
    assert result.object.object_value == "a post praising fraud"


def test_governed_to_complement_without_a_direct_object_does_not_hold() -> None:
    """The rule requires an existing selected direct object."""
    source = "The agency decided to act."
    tokens = _typed_words(
        source,
        [
            ("The", "agency", "det", "the", "DET"),
            ("agency", "decided", "nsubj", "agency", "NOUN"),
            ("decided", None, "root", "decide", "VERB"),
            ("to", "act", "mark", "to", "PART"),
            ("act", "decided", "xcomp", "act", "VERB"),
        ],
    )
    constituents = (
        _constituent(source, "AHE-915", ("t1", "t2"), "The", "agency"),
        _constituent(source, "AHE-915", ("t3",), "decided", "decided"),
    )
    entities = (_entity("EGE-915", "organization", "agency", source, "agency", "agency"),)
    result = _compose(
        event_id="AHE-915",
        source=source,
        tokens=tokens,
        constituents=constituents,
        selected_indexes=(1, 2),
        entities=entities,
        head_lemma="decide",
    )
    assert result.status is DecontextualizationStatus.PROPOSITION
    assert result.hold_reason is None
    assert result.object is None


def test_indirect_object_only_selection_does_not_activate_the_governed_action_hold() -> None:
    """The guard requires a selected direct object, not an indirect object."""
    source = "Sacks emailed Amodei to review the file."
    tokens = _typed_words(
        source,
        [
            ("Sacks", "emailed", "nsubj", "sacks", "PROPN"),
            ("emailed", None, "root", "email", "VERB"),
            ("Amodei", "emailed", "iobj", "amodei", "PROPN"),
            ("to", "review", "mark", "to", "PART"),
            ("review", "emailed", "xcomp", "review", "VERB"),
            ("the", "file", "det", "the", "DET"),
            ("file", "review", "obj", "file", "NOUN"),
        ],
    )
    constituents = (
        _constituent(source, "AHE-916", ("t1",), "Sacks", "Sacks"),
        _constituent(source, "AHE-916", ("t2",), "emailed", "emailed"),
        _constituent(source, "AHE-916", ("t3",), "Amodei", "Amodei"),
    )
    entities = (_entity("EGE-916", "actor", "Sacks", source, "Sacks", "Sacks"),)
    result = _compose(
        event_id="AHE-916",
        source=source,
        tokens=tokens,
        constituents=constituents,
        selected_indexes=(1, 2, 3),
        entities=entities,
        head_lemma="email",
    )
    assert result.status is DecontextualizationStatus.PROPOSITION
    assert result.hold_reason is None
    assert result.object is not None and result.object.object_value == "Amodei"


def test_unsupported_trigger_oblique_precedes_the_governed_action_hold() -> None:
    """An earlier unsupported time-place hold stays authoritative in composition."""
    source = "The agency authorized its workers to use the tools with the lawyers."
    tokens = _typed_words(
        source,
        [
            ("The", "agency", "det", "the", "DET"),
            ("agency", "authorized", "nsubj", "agency", "NOUN"),
            ("authorized", None, "root", "authorize", "VERB"),
            ("its", "workers", "det", "its", "PRON"),
            ("workers", "authorized", "obj", "worker", "NOUN"),
            ("to", "use", "mark", "to", "PART"),
            ("use", "authorized", "xcomp", "use", "VERB"),
            ("the", "tools", "det", "the", "DET"),
            ("tools", "use", "obj", "tool", "NOUN"),
            ("with", "lawyers", "case", "with", "ADP"),
            ("lawyers", "authorized", "obl", "lawyer", "NOUN"),
        ],
    )
    constituents = (
        _constituent(source, "AHE-917", ("t1", "t2"), "The", "agency"),
        _constituent(source, "AHE-917", ("t3",), "authorized", "authorized"),
        _constituent(source, "AHE-917", ("t4", "t5"), "its", "workers"),
    )
    entities = (_entity("EGE-917", "organization", "agency", source, "agency", "agency"),)
    result = _compose(
        event_id="AHE-917",
        source=source,
        tokens=tokens,
        constituents=constituents,
        selected_indexes=(1, 2, 3),
        entities=entities,
        head_lemma="authorize",
    )
    assert result.status is DecontextualizationStatus.HELD
    assert result.hold_reason is DecontextualizationHoldReason.UNSUPPORTED_TIME_PLACE
