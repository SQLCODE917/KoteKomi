from __future__ import annotations

import hashlib
import importlib
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from kotekomi_application import (
    AttachmentEvidenceReference,
    AttachmentRemainderEnumerationMechanism,
    AttachmentRemainderEnumerationOutcome,
    AttachmentRemainderEnumerationPackageStatus,
    AttachmentRemainderEnumerationReport,
)
from kotekomi_pipelines.config import PipelineConfig

ROOT = Path(__file__).resolve().parents[3]


def _runner() -> Any:
    scripts_path = str(ROOT / "scripts")
    if scripts_path not in sys.path:
        sys.path.insert(0, scripts_path)
    return importlib.import_module("run_competitive_attachment_remainder_enumeration_isolation")


def test_generation_contract_preserves_predecessor_runtime_settings() -> None:
    runner = _runner()
    config = cast(
        PipelineConfig,
        SimpleNamespace(model_execution=SimpleNamespace(max_output_tokens=512)),
    )

    settings = runner._configured_generation(config)

    assert {item.key: item.value for item in settings} == {
        "frequency_penalty": 0.0,
        "max_output_tokens": 512,
        "seed": 17,
        "temperature": 0,
        "top_logprobs": 10,
    }


def test_complete_status_exposes_review_package_without_canonical_changes(
    tmp_path: Path,
) -> None:
    runner = _runner()
    report = cast(
        AttachmentRemainderEnumerationReport,
        SimpleNamespace(
            outcome=AttachmentRemainderEnumerationOutcome.SUPPORTED,
            mechanism=AttachmentRemainderEnumerationMechanism.PART_INVENTORY_SUFFICIENT,
            model_execution_count=4,
        ),
    )

    status = runner._status(
        tmp_path,
        AttachmentRemainderEnumerationPackageStatus.COMPLETE,
        report=report,
    )

    assert status.report_path == str(tmp_path / "report.json")
    assert status.review_path == str(tmp_path / "comparison-review.md")
    assert status.handoff_path == str(tmp_path / "second-opinion-handoff.md")
    assert status.claude_review_path == str(tmp_path / "claude-opus-review.md")
    assert status.proposed_change_count == 0
    assert status.accepted_ledger_change_count == 0


def test_changed_repository_input_validates_against_sealed_revision(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = _runner()
    path = tmp_path / "docs" / "experiment.md"
    path.parent.mkdir()
    path.write_bytes(b"changed after experiment\n")
    reference = AttachmentEvidenceReference(
        label="tdd",
        path=str(path),
        sha256=hashlib.sha256(b"sealed experiment\n").hexdigest(),
    )
    calls: list[list[str]] = []

    def fake_run(command: list[str], **_kwargs: object) -> SimpleNamespace:
        calls.append(command)
        return SimpleNamespace(stdout=b"sealed experiment\n")

    monkeypatch.setattr(runner, "REPOSITORY_ROOT", tmp_path)
    monkeypatch.setattr(runner.subprocess, "run", fake_run)

    runner._validate_sealed_reference(reference, source_revision="a" * 40)

    assert calls == [["git", "show", f"{'a' * 40}:docs/experiment.md"]]


def test_handoff_source_revision_requires_one_full_commit(tmp_path: Path) -> None:
    runner = _runner()
    path = tmp_path / "handoff.md"
    path.write_text(f"Source revision: `{'a' * 40}`\n", encoding="utf-8")

    assert runner._source_revision_from_handoff(path) == "a" * 40

    path.write_text("Source revision: `short`\n", encoding="utf-8")
    with pytest.raises(ValueError, match="one full source revision"):
        runner._source_revision_from_handoff(path)
