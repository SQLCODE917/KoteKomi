"""Deterministic R10 runner that disposes the frozen run-005 residual set.

This runner reads the sealed run-005 report, maps its three residual Events to
one typed disposition each, validates held safety, and seals one R10 report.
It is model-free and writes only its own run root.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from kotekomi_application import (
    ResidualReviewReason,
    SelectionRouting,
    SelectionRoutingDecision,
    build_residual_composition_hold_report,
    dispose_residual_set,
    validate_held_safety,
)


def _load_selection_routing(report_path: Path) -> tuple[SelectionRouting, ...]:
    payload = json.loads(report_path.read_text())
    routing: list[SelectionRouting] = []
    for entry in payload["selection_routing"]:
        routing.append(
            SelectionRouting(
                event_id=entry["event_id"],
                decision=SelectionRoutingDecision(entry["decision"]),
                reason=ResidualReviewReason(entry["reason"]) if entry["reason"] else None,
            )
        )
    return tuple(routing)


def _main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-005-root", required=True)
    parser.add_argument("--run-root", required=True)
    args = parser.parse_args()

    source_root = Path(args.run_005_root)
    run_root = Path(args.run_root)
    run_root.mkdir(parents=True, exist_ok=True)

    report = json.loads((source_root / "report.json").read_text())
    routing = _load_selection_routing(source_root / "report.json")
    residual_event_ids = tuple(report["residual_review_event_ids"])

    dispositions = dispose_residual_set(routing=routing)
    validate_held_safety(dispositions=dispositions, residual_event_ids=residual_event_ids)
    sealed = build_residual_composition_hold_report(
        dispositions=dispositions,
        residual_review_event_ids=residual_event_ids,
    )

    dispositions_payload = [
        {
            "event_id": item.event_id,
            "reason": item.reason.value,
            "hold_reason": item.hold_reason.value if item.hold_reason else None,
        }
        for item in dispositions
    ]
    (run_root / "dispositions.json").write_text(
        json.dumps(dispositions_payload, indent=2, sort_keys=True) + "\n"
    )
    (run_root / "report.json").write_text(
        json.dumps(sealed.model_dump(mode="json"), indent=2, sort_keys=True) + "\n"
    )
    (run_root / "run.json").write_text(
        json.dumps(
            {
                "source_report_fingerprint": report["result_fingerprint"],
                "result_fingerprint": sealed.result_fingerprint,
                "residual_review_event_ids": list(residual_event_ids),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )

    for item in dispositions:
        print(f"{item.event_id}: {item.reason.value}")
    print(f"fingerprint: {sealed.result_fingerprint}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())