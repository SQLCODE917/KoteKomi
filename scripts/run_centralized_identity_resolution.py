"""Deterministic R14 runner that links the frozen AHE-004 vague mention.

This runner binds the frozen R13 AHE-004 vague mention (an eventive subject,
exact text ``Efforts``, no reference) and one deterministic concrete-mention
fixture that names the vague Assertion through ``supersedes_assertion_id``. It
runs the centralized identity-resolution step once, seals one zero-write
report, and writes only its own run root.

The concrete mention fixture stands for a later article that resolves the same
activity to a published entity reference and declares the supersede. It is a
labeled deterministic fixture, not model output and not a held-out read. The
runner is model-free, reads no held-out partition, and writes no canonical
state.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from kotekomi_application import (
    IdentityResolutionMention,
    ReificationSubject,
    ReificationSubjectKind,
    build_identity_resolution_report,
    resolve_identity,
)


def _main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", required=True)
    args = parser.parse_args()

    run_root = Path(args.run_root)
    run_root.mkdir(parents=True, exist_ok=True)

    vague = IdentityResolutionMention(
        assertion_id="ast_ahe004_vague_001",
        event_id="AHE-004",
        subject=ReificationSubject(
            kind=ReificationSubjectKind.EVENT,
            exact_text="Efforts",
        ),
    )
    concrete = IdentityResolutionMention(
        assertion_id="ast_ahe004_concrete_001",
        event_id="TGE-017",
        subject=ReificationSubject(
            kind=ReificationSubjectKind.ENTITY,
            exact_text="AI/autonomy efforts",
            reference_id="ent_ahe004_efforts_001",
        ),
        supersedes_assertion_id="ast_ahe004_vague_001",
    )

    resolution = resolve_identity(vague=vague, concrete=concrete)
    report = build_identity_resolution_report(items=(resolution,))

    (run_root / "items.json").write_text(
        json.dumps([resolution.model_dump(mode="json")], indent=2, sort_keys=True) + "\n"
    )
    (run_root / "report.json").write_text(
        json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True) + "\n"
    )
    (run_root / "run.json").write_text(
        json.dumps(
            {
                "vague_event_id": vague.event_id,
                "vague_assertion_id": vague.assertion_id,
                "concrete_event_id": concrete.event_id,
                "concrete_assertion_id": concrete.assertion_id,
                "signal": resolution.signal.value,
                "outcome": resolution.outcome.value,
                "result_fingerprint": report.result_fingerprint,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )

    print(f"fingerprint: {report.result_fingerprint}")
    print(f"signal: {resolution.signal.value}")
    print(f"outcome: {resolution.outcome.value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())