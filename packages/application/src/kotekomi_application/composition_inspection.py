"""Shared inspection of composed Assertions and held Events; no composition is rerun."""

from __future__ import annotations

import hashlib
from dataclasses import replace
from pathlib import PurePosixPath

from kotekomi_domain import Actor, Organization, ProposedChange
from kotekomi_domain.models import JsonValue

from kotekomi_application.ingestion_inspection import (
    STAGE_ORDER,
    CompositionAnnotation,
    InspectionRecord,
    ParagraphAnnotationProfile,
)

COMPOSITION_LAYER = "composition"
INSPECTION_LAYERS = (*STAGE_ORDER, COMPOSITION_LAYER)


def validate_composition_outcome_handle(path: str, sha256: str) -> None:
    """Validate the same relative file handle in inspection and copied summaries."""
    parsed = PurePosixPath(path)
    if (
        parsed.is_absolute()
        or ".." in parsed.parts
        or len(parsed.parts) != 2
        or parsed.suffix != ".json"
    ):
        raise ValueError("Composition outcome handle must be relative to the state root.")
    if len(sha256) != 64 or any(char not in "0123456789abcdef" for char in sha256):
        raise ValueError("Composition outcome handle requires a SHA-256 digest.")


def enrich_composition_annotation(
    annotation: CompositionAnnotation,
    *,
    subject: Actor | Organization | None,
    proposals: tuple[ProposedChange, ...],
) -> CompositionAnnotation:
    """Attach accepted identity names and canonical proposal review handles."""
    assertion = annotation.assertion
    if assertion is None:
        return annotation
    if assertion.subject_entity_id is not None:
        if subject is None or subject.id != assertion.subject_entity_id:
            raise ValueError(
                "Composition inspection references a missing accepted subject identity."
            )
    elif subject is not None:
        raise ValueError("A value subject cannot name an accepted identity.")
    handles = tuple(
        (proposal.id, proposal.review_status.value)
        for proposal in proposals
        if proposal.proposed_json.get("record_type") == "Assertion"
        and proposal.proposed_json.get("stable_label") == assertion.id
    )
    return replace(
        annotation,
        subject_name=None if subject is None else subject.name,
        proposal_handles=handles,
    )


def composition_inspection_records(
    profile: ParagraphAnnotationProfile,
) -> tuple[InspectionRecord, ...]:
    """Resolve each composition into one record shared by all inspection outputs."""
    events = {event.event_id: event for event in profile.events}
    digest = hashlib.sha256(profile.text.encode()).hexdigest()
    records: list[InspectionRecord] = []
    for item in sorted(
        profile.composition, key=lambda item: (item.status != "composed", item.event_id)
    ):
        if item.source_text_sha256 != digest:
            raise ValueError("Composition inspection source digest differs from the paragraph.")
        event = events.get(item.event_id)
        if event is None:
            raise ValueError("Composition inspection Event is missing from the paragraph.")
        spans = tuple(
            dict.fromkeys(
                span
                for span in (event.trigger_span, item.span, item.object_span)
                if span is not None
            )
        )
        for span in spans:
            if not 0 <= span.start < span.end <= len(profile.text):
                raise ValueError("Composition inspection span lies outside the paragraph.")
            if profile.text[span.start : span.end] != span.text:
                raise ValueError("Composition inspection span differs from authoritative text.")
        data: dict[str, JsonValue] = {"event_id": item.event_id, "status": item.status}
        related_ids = [item.event_id]
        record_id = item.event_id
        if item.status == "composed":
            assertion = item.assertion
            if assertion is None or item.span is None or item.object_span is None:
                raise ValueError(
                    "Composed inspection requires an Assertion and both argument spans."
                )
            record_id = assertion.id
            data.update(
                {
                    "assertion_status": assertion.status.value,
                    "subject": item.subject_name or item.span.text,
                    "subject_entity_id": assertion.subject_entity_id,
                    "predicate": assertion.predicate,
                    "object": assertion.object_value
                    if assertion.object_entity_id is None
                    else item.object_span.text,
                    "object_entity_id": assertion.object_entity_id,
                    "epistemic_scope": assertion.epistemic_scope.value,
                    "source_authority": assertion.source_authority.value,
                    "attribution_basis": assertion.attribution_basis.value,
                    "qualifiers": assertion.qualifiers,
                    "source_ids": list(assertion.source_ids),
                    "evidence_target_ids": list(assertion.evidence_target_ids),
                    "proposals": [
                        {"id": identity, "review_status": status}
                        for identity, status in item.proposal_handles
                    ],
                }
            )
            related_ids.extend((*assertion.source_ids, *assertion.evidence_target_ids))
            related_ids.extend(identity for identity, _status in item.proposal_handles)
        elif item.status == "held":
            if item.assertion is not None or not item.hold_reason:
                raise ValueError("Held inspection requires a reason and no Assertion.")
            data.update(
                {
                    "hold_reason": item.hold_reason,
                    "unavailable_reference": item.unavailable_reference,
                }
            )
        else:
            raise ValueError("Unknown composition inspection status.")
        if item.outcome_path is not None or item.outcome_sha256 is not None:
            sha = item.outcome_sha256 or ""
            validate_composition_outcome_handle(item.outcome_path or "", sha)
            data.update({"outcome_path": item.outcome_path, "outcome_sha256": sha})
        records.append(
            InspectionRecord(
                key=f"composition:{item.event_id}",
                stage=COMPOSITION_LAYER,
                record_id=record_id,
                record_type="Assertion" if item.assertion is not None else "EventCompositionHold",
                spans=spans,
                data=data,
                related_ids=tuple(related_ids),
            )
        )
    return tuple(records)
