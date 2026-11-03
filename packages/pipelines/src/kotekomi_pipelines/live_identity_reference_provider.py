"""Live identity reference provider (R20 increment 2).

The Adapter translates accepted ``IdentityOccurrence`` records into
``EventEntityReferences``. It never reads a grounding candidate.

An accepted occurrence that references a missing identity or an invalid
``EvidenceTarget`` fails fast. A mention the Adapter cannot locate unambiguously
leaves a typed diagnostic and no reference; the composition stage turns that
diagnostic into an Event-specific hold.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Protocol

from kotekomi_application import (
    AttachmentSourceRange,
    DecontextualizationEntityRef,
    EventEntityReferences,
    ReferenceDiagnostic,
    ReferenceDiagnosticReason,
    ReferenceResolution,
)
from kotekomi_domain import (
    Actor,
    EvidenceTarget,
    IdentityOccurrence,
    IdentityOccurrenceKind,
    Organization,
)


class LiveIdentityReferenceErrorReason(StrEnum):
    """Typed reason an accepted occurrence cannot become a reference."""

    MISSING_EVIDENCE = "missing_evidence"
    MISSING_IDENTITY = "missing_identity"
    COORDINATE_MISMATCH = "coordinate_mismatch"


class LiveIdentityReferenceError(ValueError):
    """Fail-fast error for an accepted occurrence with invalid evidence or identity."""

    def __init__(self, reason: LiveIdentityReferenceErrorReason, detail: str) -> None:
        super().__init__(f"Live identity reference error: {reason.value}: {detail}")
        self.reason = reason


LiveReferenceDiagnosticReason = ReferenceDiagnosticReason
LiveReferenceDiagnostic = ReferenceDiagnostic
LiveReferenceResolution = ReferenceResolution


class LiveIdentityReferenceLedger(Protocol):
    """The accepted ledgers the live Adapter reads."""

    def list_identity_occurrences(self) -> tuple[IdentityOccurrence, ...]: ...
    def get_evidence_target(self, record_id: str) -> EvidenceTarget | None: ...
    def get_actor(self, record_id: str) -> Actor | None: ...
    def get_organization(self, record_id: str) -> Organization | None: ...


def _normalized(value: str) -> str:
    return "".join(char for char in value if not char.isspace())


def _locate_text(
    source_text: str,
    exact_text: str,
) -> tuple[AttachmentSourceRange | None, LiveReferenceDiagnosticReason | None]:
    """Locate one mention uniquely, or report why it stays unresolved."""
    exact_hits = [
        index for index in range(len(source_text)) if source_text.startswith(exact_text, index)
    ]
    if len(exact_hits) == 1:
        index = exact_hits[0]
        return (
            AttachmentSourceRange(start=index, end=index + len(exact_text), text=exact_text),
            None,
        )
    if len(exact_hits) > 1:
        return (None, LiveReferenceDiagnosticReason.AMBIGUOUS_MENTION)

    positions = [index for index, char in enumerate(source_text) if not char.isspace()]
    normalized_source = "".join(source_text[index] for index in positions)
    target = _normalized(exact_text)
    if not target:
        return (None, LiveReferenceDiagnosticReason.MENTION_NOT_FOUND)
    starts: list[int] = []
    cursor = 0
    while True:
        found = normalized_source.find(target, cursor)
        if found < 0:
            break
        starts.append(found)
        cursor = found + 1
    if not starts:
        return (None, LiveReferenceDiagnosticReason.MENTION_NOT_FOUND)
    if len(starts) > 1:
        return (None, LiveReferenceDiagnosticReason.AMBIGUOUS_MENTION)
    start = positions[starts[0]]
    end = positions[starts[0] + len(target) - 1] + 1
    return (
        AttachmentSourceRange(start=start, end=end, text=source_text[start:end]),
        None,
    )


class LiveIdentityReferenceProvider:
    """Adapter that translates accepted IdentityOccurrences into references."""

    def __init__(
        self,
        repository: LiveIdentityReferenceLedger,
        *,
        representation_id: str | None = None,
        text_view_id: str | None = None,
    ) -> None:
        self._repository = repository
        self._representation_id = representation_id
        self._text_view_id = text_view_id

    def resolve_references(
        self,
        event_id: str,
        source_text: str,
        source_text_sha256: str,
    ) -> EventEntityReferences:
        return self.resolve_references_with_diagnostics(
            event_id, source_text, source_text_sha256
        ).references

    def resolve_references_with_diagnostics(
        self,
        event_id: str,
        source_text: str,
        source_text_sha256: str,
    ) -> LiveReferenceResolution:
        del event_id, source_text_sha256
        grouped: dict[str, tuple[IdentityOccurrenceKind, list[AttachmentSourceRange]]] = {}
        diagnostics: list[LiveReferenceDiagnostic] = []
        for occurrence in self._repository.list_identity_occurrences():
            target = self._repository.get_evidence_target(occurrence.evidence_target_id)
            if target is None:
                raise LiveIdentityReferenceError(
                    LiveIdentityReferenceErrorReason.MISSING_EVIDENCE,
                    f"Occurrence {occurrence.id} references missing "
                    f"{occurrence.evidence_target_id}.",
                )
            kind = occurrence.identity_kind
            name = self._identity_name(str(occurrence.identity_id), kind)
            if name is None:
                raise LiveIdentityReferenceError(
                    LiveIdentityReferenceErrorReason.MISSING_IDENTITY,
                    f"Occurrence {occurrence.id} references missing identity "
                    f"{occurrence.identity_id}.",
                )
            located = self._locate_occurrence(occurrence.id, target, source_text, diagnostics)
            if located is None:
                continue
            _, spans = grouped.setdefault(str(occurrence.identity_id), (kind, []))
            spans.append(located)

        entities = [
            DecontextualizationEntityRef(
                entity_id=identity_id,
                entity_kind=grouped[identity_id][0].value,
                canonical_name=self._identity_name(identity_id, grouped[identity_id][0]) or "",
                accepted_source_occurrences=tuple(
                    sorted(grouped[identity_id][1], key=lambda span: (span.start, span.end))
                ),
            )
            for identity_id in sorted(grouped)
        ]
        return LiveReferenceResolution(
            references=EventEntityReferences(
                entities=tuple(entities), subject_value_authorizations=()
            ),
            diagnostics=tuple(diagnostics),
        )

    def _locate_occurrence(
        self,
        occurrence_id: str,
        target: EvidenceTarget,
        source_text: str,
        diagnostics: list[LiveReferenceDiagnostic],
    ) -> AttachmentSourceRange | None:
        if (
            self._representation_id is not None
            and self._text_view_id is not None
            and target.representation_id == self._representation_id
            and target.text_view_id == self._text_view_id
        ):
            slice_text = source_text[target.start_char : target.end_char]
            if not slice_text or _normalized(slice_text) != _normalized(target.exact_text):
                raise LiveIdentityReferenceError(
                    LiveIdentityReferenceErrorReason.COORDINATE_MISMATCH,
                    f"Occurrence {occurrence_id} coordinates do not replay its exact text.",
                )
            return AttachmentSourceRange(
                start=target.start_char, end=target.end_char, text=slice_text
            )
        located, reason = _locate_text(source_text, target.exact_text)
        if located is None:
            assert reason is not None
            diagnostics.append(
                LiveReferenceDiagnostic(
                    occurrence_id=occurrence_id,
                    identity_id=target.id,
                    reason=reason,
                    detail=f"Mention for EvidenceTarget {target.id} is not resolvable here.",
                )
            )
        return located

    def _identity_name(self, identity_id: str, kind: IdentityOccurrenceKind) -> str | None:
        if kind is IdentityOccurrenceKind.ACTOR:
            actor = self._repository.get_actor(identity_id)
            return None if actor is None else actor.name
        organization = self._repository.get_organization(identity_id)
        return None if organization is None else organization.name
