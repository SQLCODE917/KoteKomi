"""Coordinate tests for mapping segment-local Event triggers to paragraphs."""

from __future__ import annotations

import pytest
from kotekomi_application.context_planning import (
    PARAGRAPH_SEGMENT_V3,
    paragraph_source_segments,
)
from kotekomi_application.ingestion_inspection import normalize_segment_span


def test_maps_each_segment_trigger_by_coordinate_not_text() -> None:
    text = "Alpha supports Mira. Alpha supports Tomas."
    segments = paragraph_source_segments(text, PARAGRAPH_SEGMENT_V3)
    assert len(segments) == 2

    first = normalize_segment_span(segment=segments[0], start=6, end=14)
    second = normalize_segment_span(segment=segments[1], start=6, end=14)

    assert text[first.start : first.end] == "supports"
    assert text[second.start : second.end] == "supports"
    assert first.start == segments[0].start_char + 6
    assert second.start == segments[1].start_char + 6
    # Repeated trigger text maps to distinct paragraph occurrences.
    assert first.start != second.start


def test_maps_a_trigger_inside_collapsed_whitespace_segment() -> None:
    text = "Alpha  supports  Tomas.  Mira  supports  Sacks."
    segments = paragraph_source_segments(text, PARAGRAPH_SEGMENT_V3)
    assert len(segments) == 2
    second = segments[1]
    local = second.exact_text.index("supports")

    span = normalize_segment_span(segment=second, start=local, end=local + len("supports"))

    assert span.start == second.start_char + local
    assert text[span.start : span.end] == "supports"
    assert span.text == "supports"


def test_rejects_a_segment_local_span_outside_its_segment() -> None:
    text = "Alpha supports Mira. Tomas."
    segments = paragraph_source_segments(text, PARAGRAPH_SEGMENT_V3)
    with pytest.raises(ValueError, match="outside its SourceSegment"):
        normalize_segment_span(segment=segments[0], start=0, end=len(text) + 1)
