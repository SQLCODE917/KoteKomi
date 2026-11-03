"""Live identity reference provider (R20 increment 2).

The Adapter translates accepted ``IdentityOccurrence`` records into
``EventEntityReferences``. It never reads a grounding candidate. Each accepted
occurrence names one exact mention through its ``EvidenceTarget``. The Adapter
locates that mention in the Event source, and it excludes an ambiguous mention
instead of guessing.
"""

from __future__ import annotations

from typing import Protocol

from kotekomi_application import (
    AttachmentSourceRange,
    DecontextualizationEntityRef,
    EventEntityReferences,
)
from kotekomi_domain import (
    Actor,
    EvidenceTarget,
    IdentityOccurrence,
    IdentityOccurrenceKind,
    Organization,
)


class LiveIdentityReferenceLedger(Protocol):
    """The accepted ledgers the live Adapter reads."""

    def list_identity_occurrences(self) -> tuple[IdentityOccurrence, ...]: ...
    def get_evidence_target(self, record_id: str) -> EvidenceTarget | None: ...
    def get_actor(self, record_id: str) -> Actor | None: ...
    def get_organization(self, record_id: str) -> Organization | None: ...


def _normalized(value: str) -> str:
    return "".join(char for char in value if not char.isspace())


def _locate(source_text: str, exact_text: str) -> AttachmentSourceRange | None:
    """Locate one exact or whitespace-equivalent mention, or return None.

    The Adapter accepts a mention only when the source contains exactly one
    exact match, or exactly one whitespace-normalized match. A repeated mention
    stays unresolved; it never becomes a guessed reference.
    """
    exact_hits = [
        index for index in range(len(source_text)) if source_text.startswith(exact_text, index)
    ]
    if len(exact_hits) == 1:
        index = exact_hits[0]
        return AttachmentSourceRange(start=index, end=index + len(exact_text), text=exact_text)
    if exact_hits:
        return None

    positions = [index for index, char in enumerate(source_text) if not char.isspace()]
    normalized_source = "".join(source_text[index] for index in positions)
    target = _normalized(exact_text)
    if not target:
        return None
    starts: list[int] = []
    cursor = 0
    while True:
        found = normalized_source.find(target, cursor)
        if found < 0:
            break
        starts.append(found)
        cursor = found + 1
    if len(starts) != 1:
        return None
    start = positions[starts[0]]
    end = positions[starts[0] + len(target) - 1] + 1
    return AttachmentSourceRange(start=start, end=end, text=source_text[start:end])


class LiveIdentityReferenceProvider:
    """Adapter that translates accepted IdentityOccurrences into references."""

    def __init__(self, repository: LiveIdentityReferenceLedger) -> None:
        self._repository = repository

    def resolve_references(
        self,
        event_id: str,
        source_text: str,
        source_text_sha256: str,
    ) -> EventEntityReferences:
        del event_id, source_text_sha256
        grouped: dict[str, tuple[IdentityOccurrenceKind, list[AttachmentSourceRange]]] = {}
        for occurrence in self._repository.list_identity_occurrences():
            target = self._repository.get_evidence_target(occurrence.evidence_target_id)
            if target is None:
                continue
            located = _locate(source_text, target.exact_text)
            if located is None:
                continue
            kind, spans = grouped.setdefault(
                str(occurrence.identity_id), (occurrence.identity_kind, [])
            )
            spans.append(located)

        entities: list[DecontextualizationEntityRef] = []
        for identity_id in sorted(grouped):
            kind, spans = grouped[identity_id]
            name = self._identity_name(identity_id, kind)
            if name is None:
                continue
            entities.append(
                DecontextualizationEntityRef(
                    entity_id=identity_id,
                    entity_kind=kind.value,
                    canonical_name=name,
                    accepted_source_occurrences=tuple(
                        sorted(spans, key=lambda span: (span.start, span.end))
                    ),
                )
            )
        return EventEntityReferences(entities=tuple(entities), subject_value_authorizations=())

    def _identity_name(self, identity_id: str, kind: IdentityOccurrenceKind) -> str | None:
        if kind is IdentityOccurrenceKind.ACTOR:
            actor = self._repository.get_actor(identity_id)
            return None if actor is None else actor.name
        organization = self._repository.get_organization(identity_id)
        return None if organization is None else organization.name
