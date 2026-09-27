"""Focused tests for the R2 trigger-containment candidate split and Gold correction.

These tests cover the Application Layer splitter, resize, corrected Gold, and the
baseline re-score report.  They build only small synthetic models; the frozen
187-candidate universe is exercised in the Pipeline tests.
"""

from __future__ import annotations

import pytest
from kotekomi_application import (
    AttachmentPartitionRole,
    AttachmentRouteDecision,
    AttachmentRouteKind,
    AttachmentSourceRange,
    CorrectedCandidateLabel,
    build_corrected_attachment_gold,
    build_correction_partition_report,
    build_trigger_containment_correction_report,
    build_trigger_containment_resize,
    corrected_attachment_gold_bytes,
    exact_fragment_membership,
    foreign_trigger_ranges,
    resize_candidate_range,
    trigger_containment_correction_report_fingerprint,
)

_FAKE_SHA = "a" * 64


def _cid(suffix: str) -> str:
    return "cac_" + (suffix * 24)[:24]


def _eid(ordinal: int) -> str:
    return f"TGE-{ordinal:03d}"


def _sge(suffix: str) -> str:
    return "sge_" + (suffix * 24)[:24]


def _range(start: int, end: int, text: str) -> AttachmentSourceRange:
    return AttachmentSourceRange(start=start, end=end, text=text)


def _decision(
    candidate_id: str,
    *,
    partition_role: AttachmentPartitionRole,
    route_kind: AttachmentRouteKind,
) -> AttachmentRouteDecision:
    informing = (
        "development" if partition_role is AttachmentPartitionRole.DEVELOPMENT else "validation"
    )
    allowed = (_sge("b"),) if route_kind is AttachmentRouteKind.ATTACHED else ()
    return AttachmentRouteDecision(
        candidate_id=candidate_id,
        partition_role=partition_role,
        informing_partition=informing,
        route_kind=route_kind,
        allowed_event_ids=allowed,
        selected_policy="path_1" if route_kind is AttachmentRouteKind.ATTACHED else None,
        path_1_supported=route_kind is AttachmentRouteKind.ATTACHED,
        trigger_containment=False,
    )


def _resize(
    candidate_id: str,
    *,
    candidate_range: AttachmentSourceRange,
    foreign_ranges: tuple[AttachmentSourceRange, ...],
    resized_range: AttachmentSourceRange,
    label_before: tuple[str, ...],
    label_after: tuple[str, ...],
    phase: str = "development",
):
    return build_trigger_containment_resize(
        candidate_id=candidate_id,
        phase=phase,  # type: ignore[arg-type]
        candidate_range=candidate_range,
        foreign_ranges=foreign_ranges,
        resized_range=resized_range,
        label_before=label_before,
        label_after=label_after,
    )


def _dev_decision(candidate_id: str, attached: bool = False) -> AttachmentRouteDecision:
    return _decision(
        candidate_id,
        partition_role=AttachmentPartitionRole.DEVELOPMENT,
        route_kind=(AttachmentRouteKind.ATTACHED if attached else AttachmentRouteKind.MODEL_REVIEW),
    )


def _val_decision(candidate_id: str, attached: bool = False) -> AttachmentRouteDecision:
    return _decision(
        candidate_id,
        partition_role=AttachmentPartitionRole.VALIDATION,
        route_kind=(AttachmentRouteKind.ATTACHED if attached else AttachmentRouteKind.MODEL_REVIEW),
    )


def test_foreign_trigger_ranges_detects_strict_containment() -> None:
    candidate = _range(0, 19, "the quick brown fox")
    foreign = _range(4, 9, "quick")
    triggers = ((_range(4, 9, "quick"), _eid(2)),)
    assert foreign_trigger_ranges(
        candidate_range=candidate, triggers=triggers, gold_event_ids=(_eid(1),)
    ) == (foreign,)


def test_foreign_trigger_ranges_keeps_own_event_non_foreign() -> None:
    candidate = _range(0, 19, "the quick brown fox")
    triggers = ((_range(4, 9, "quick"), _eid(1)),)
    assert (
        foreign_trigger_ranges(
            candidate_range=candidate, triggers=triggers, gold_event_ids=(_eid(1),)
        )
        == ()
    )


def test_foreign_trigger_ranges_rejects_boundary_coincidence() -> None:
    candidate = _range(0, 10, "abcdefghij")
    triggers = ((_range(0, 10, "abcdefghij"), _eid(2)),)
    assert (
        foreign_trigger_ranges(candidate_range=candidate, triggers=triggers, gold_event_ids=())
        == ()
    )


def test_resize_candidate_range_excludes_foreign_and_stays_source_exact() -> None:
    source = "the quick brown fox"
    candidate = _range(0, 19, source)
    foreign = _range(4, 9, "quick")
    resized = resize_candidate_range(
        candidate_range=candidate, foreign_ranges=(foreign,), source_text=source
    )
    assert resized.start == 9
    assert resized.end == 19
    assert resized.text == " brown fox"
    assert source[resized.start : resized.end] == resized.text


def test_resize_candidate_range_leftmost_longest_tie() -> None:
    source = "AAxxBB"
    candidate = _range(0, 6, source)
    foreign = (_range(2, 4, "xx"),)
    resized = resize_candidate_range(
        candidate_range=candidate, foreign_ranges=foreign, source_text=source
    )
    assert resized.text == "AA"
    assert resized.start == 0
    assert resized.end == 2


def test_resize_candidate_range_rejects_whitespace_only_remainder() -> None:
    source = "   trigger   "
    candidate = _range(0, len(source), source)
    foreign = _range(3, 10, "trigger")
    with pytest.raises(ValueError):
        resize_candidate_range(
            candidate_range=candidate, foreign_ranges=(foreign,), source_text=source
        )


def test_exact_fragment_membership_matches_exact_range_only() -> None:
    fragments = {_eid(1): ((0, 5), (5, 10)), _eid(2): ((0, 5),)}
    assert exact_fragment_membership(_range(0, 5, "abcde"), fragments) == (
        _eid(1),
        _eid(2),
    )
    assert exact_fragment_membership(_range(5, 10, "fghij"), fragments) == (_eid(1),)
    assert exact_fragment_membership(_range(1, 5, "bcde"), fragments) == ()


def test_build_trigger_containment_resize_rejects_non_contained_foreign() -> None:
    candidate = _range(0, 10, "abcdefghij")
    foreign = _range(5, 20, "fghijklmnopqrst")
    with pytest.raises(ValueError):
        _resize(
            _cid("a"),
            candidate_range=candidate,
            foreign_ranges=(foreign,),
            resized_range=_range(0, 5, "abcde"),
            label_before=(_eid(1),),
            label_after=(),
        )


def test_build_corrected_attachment_gold_enforces_label_resize_agreement() -> None:
    candidate_range = _range(0, 10, "abcdefghij")
    resized_range = _range(0, 9, "abcdefghi")
    with pytest.raises(ValueError):
        build_corrected_attachment_gold(
            catalog_id="fixture",
            source_catalog_sha256=_FAKE_SHA,
            corrected_labels=(
                CorrectedCandidateLabel(
                    candidate_id=_cid("a"),
                    phase="development",
                    source_range=resized_range,
                    gold_event_ids=(_eid(1),),
                ),
            ),
            resizes=(
                _resize(
                    _cid("a"),
                    candidate_range=candidate_range,
                    foreign_ranges=(_range(9, 10, "j"),),
                    resized_range=resized_range,
                    label_before=(_eid(1),),
                    label_after=(),
                ),
            ),
        )


def test_corrected_attachment_gold_bytes_byte_identical() -> None:
    def build():
        return build_corrected_attachment_gold(
            catalog_id="fixture",
            source_catalog_sha256=_FAKE_SHA,
            corrected_labels=(
                CorrectedCandidateLabel(
                    candidate_id=_cid("a"),
                    phase="development",
                    source_range=_range(0, 5, "abcde"),
                    gold_event_ids=(_eid(1),),
                ),
            ),
            resizes=(),
        )

    first = corrected_attachment_gold_bytes(build())
    second = corrected_attachment_gold_bytes(build())
    assert first == second
    assert first.endswith(b"\n")


def test_correction_partition_report_recounts_and_lists_changes() -> None:
    decisions = (
        _dev_decision(_cid("a")),
        _dev_decision(_cid("b"), attached=True),
    )
    before_attachment = {_cid("a"): (_eid(1),), _cid("b"): ()}
    before_mixed = {_cid("a"): False, _cid("b"): False}
    before_temporal = {_cid("a"): False, _cid("b"): False}
    after_attachment = {_cid("a"): (), _cid("b"): (_eid(1), _eid(2))}
    after_mixed = {_cid("a"): False, _cid("b"): True}
    after_temporal = {_cid("a"): False, _cid("b"): False}
    report = build_correction_partition_report(
        partition_role="development",
        decisions=decisions,
        before_attachment=before_attachment,
        before_mixed=before_mixed,
        before_temporal=before_temporal,
        after_attachment=after_attachment,
        after_mixed=after_mixed,
        after_temporal=after_temporal,
    )
    assert report.partition_role == "development"
    assert report.before_error_census.none_count == 1
    assert report.before_error_census.mixed_count == 0
    assert report.after_error_census.none_count == 1
    assert report.after_error_census.mixed_count == 1
    assert report.changed_candidate_ids == (_cid("a"), _cid("b"))


def test_trigger_containment_correction_report_records_zero_writes() -> None:
    development = build_correction_partition_report(
        partition_role="development",
        decisions=(_dev_decision(_cid("a")),),
        before_attachment={_cid("a"): (_eid(1),)},
        before_mixed={_cid("a"): False},
        before_temporal={_cid("a"): False},
        after_attachment={_cid("a"): ()},
        after_mixed={_cid("a"): False},
        after_temporal={_cid("a"): False},
    )
    validation = build_correction_partition_report(
        partition_role="validation",
        decisions=(_val_decision(_cid("c")),),
        before_attachment={_cid("c"): ()},
        before_mixed={_cid("c"): False},
        before_temporal={_cid("c"): False},
        after_attachment={_cid("c"): (_eid(1), _eid(2))},
        after_mixed={_cid("c"): True},
        after_temporal={_cid("c"): False},
    )
    report = build_trigger_containment_correction_report(
        development=development,
        validation=validation,
        corrected_gold_sha256=_FAKE_SHA,
    )
    assert report.model_execution_count == 0
    assert report.canonical_write_count == 0
    assert report.changed_candidate_count == 2
    assert report.partitions[0].partition_role == "development"
    assert report.partitions[1].partition_role == "validation"


def test_build_trigger_containment_correction_report_rejects_partition_order() -> None:
    development = build_correction_partition_report(
        partition_role="development",
        decisions=(_dev_decision(_cid("a")),),
        before_attachment={_cid("a"): ()},
        before_mixed={_cid("a"): False},
        before_temporal={_cid("a"): False},
        after_attachment={_cid("a"): ()},
        after_mixed={_cid("a"): False},
        after_temporal={_cid("a"): False},
    )
    with pytest.raises(ValueError):
        build_trigger_containment_correction_report(
            development=development,
            validation=development,
            corrected_gold_sha256=_FAKE_SHA,
        )


def test_trigger_containment_correction_report_fingerprint_is_stable() -> None:
    development = build_correction_partition_report(
        partition_role="development",
        decisions=(_dev_decision(_cid("a")),),
        before_attachment={_cid("a"): ()},
        before_mixed={_cid("a"): False},
        before_temporal={_cid("a"): False},
        after_attachment={_cid("a"): ()},
        after_mixed={_cid("a"): False},
        after_temporal={_cid("a"): False},
    )
    validation = build_correction_partition_report(
        partition_role="validation",
        decisions=(_val_decision(_cid("c")),),
        before_attachment={_cid("c"): ()},
        before_mixed={_cid("c"): False},
        before_temporal={_cid("c"): False},
        after_attachment={_cid("c"): ()},
        after_mixed={_cid("c"): False},
        after_temporal={_cid("c"): False},
    )
    first = build_trigger_containment_correction_report(
        development=development,
        validation=validation,
        corrected_gold_sha256=_FAKE_SHA,
    )
    second = build_trigger_containment_correction_report(
        development=development,
        validation=validation,
        corrected_gold_sha256=_FAKE_SHA,
    )
    assert trigger_containment_correction_report_fingerprint(first) == (
        trigger_containment_correction_report_fingerprint(second)
    )
    assert first.result_fingerprint == second.result_fingerprint


def test_correction_partition_report_rejects_unknown_partition_role() -> None:
    with pytest.raises(ValueError):
        build_correction_partition_report(
            partition_role="held_out",  # type: ignore[arg-type]
            decisions=(_dev_decision(_cid("a")),),
            before_attachment={_cid("a"): ()},
            before_mixed={_cid("a"): False},
            before_temporal={_cid("a"): False},
            after_attachment={_cid("a"): ()},
            after_mixed={_cid("a"): False},
            after_temporal={_cid("a"): False},
        )


def test_correction_partition_report_records_off_universe_census() -> None:
    report = build_correction_partition_report(
        partition_role="development",
        decisions=(_dev_decision(_cid("a")),),
        before_attachment={_cid("a"): ()},
        before_mixed={_cid("a"): False},
        before_temporal={_cid("a"): False},
        after_attachment={_cid("a"): ()},
        after_mixed={_cid("a"): False},
        after_temporal={_cid("a"): False},
        off_universe_candidate_ids=(_cid("b"), _cid("a")),
    )
    assert report.off_universe_candidate_ids == (_cid("a"), _cid("b"))
