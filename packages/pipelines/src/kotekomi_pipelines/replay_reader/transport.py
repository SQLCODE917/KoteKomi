"""Command-line transport for the replay reader.

Reads the same isolated state root the HP-8 verifier produces and hands the
persisted stage outputs to the pure model and render layers. Read-only: this
module never opens the Ledger or Archive for writing.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from kotekomi_adapters import LocalArchiveStore, sqlite_ledger_transaction
from kotekomi_application import (
    HybridDocumentCoverageRecord,
    HybridDocumentCoverageReport,
    HybridParagraphReceipt,
    hybrid_document_coverage_report_from_bytes,
    hybrid_paragraph_receipt_from_bytes,
    read_hybrid_stage_output,
)

from kotekomi_pipelines.replay_reader.model import build_profile
from kotekomi_pipelines.replay_reader.render import run_replay


def _read_coverage_report(archive_path: Path) -> HybridDocumentCoverageReport:
    paths = tuple((archive_path / "extraction" / "document-coverage").glob("*.json"))
    if len(paths) != 1:
        raise ValueError("expected exactly one document-coverage report in the Archive.")
    return hybrid_document_coverage_report_from_bytes(paths[0].read_bytes())


def _read_receipt(
    archive: LocalArchiveStore, coverage: HybridDocumentCoverageRecord
) -> HybridParagraphReceipt:
    return hybrid_paragraph_receipt_from_bytes(
        archive.read_hybrid_paragraph_receipt(coverage.receipt_id)
    )


def _read_stage_outputs(
    archive: LocalArchiveStore, receipt: HybridParagraphReceipt
) -> dict[str, object]:
    outputs: dict[str, object] = {}
    for stage in receipt.stages:
        if stage.output_id is None:
            continue
        _, parsed = read_hybrid_stage_output(stage.stage_id, stage.output_id, archive)
        outputs[stage.stage_id.value] = parsed
    return outputs


@dataclass(frozen=True)
class ParagraphInput:
    """One authoritative paragraph plus the persisted stage outputs behind it."""

    ordinal: int
    text: str
    representation_id: str
    paragraph_node_id: str
    node_start_char: int
    status: str
    gap_reasons: tuple[str, ...]
    stage_outputs: Mapping[str, object]


def load_paragraph_inputs(ledger_path: Path, archive_path: Path) -> tuple[ParagraphInput, ...]:
    """Load every paragraph's authoritative text and persisted stage outputs."""
    report = _read_coverage_report(archive_path)
    with sqlite_ledger_transaction(ledger_path) as ledger:
        bundle = ledger.get_document_representation_bundle(report.representation_id)
    if bundle is None:
        raise ValueError("coverage references a missing representation.")
    nodes = {item.id: item for item in bundle.nodes}
    text_views = {item.id: item for item in bundle.text_views}
    archive = LocalArchiveStore(archive_path)

    inputs: list[ParagraphInput] = []
    for coverage in report.records:
        node = nodes[coverage.paragraph_node_id]
        text_view = text_views[node.text_view_id]
        receipt = _read_receipt(archive, coverage)
        inputs.append(
            ParagraphInput(
                ordinal=coverage.ordinal,
                text=text_view.text[node.start_char : node.end_char],
                representation_id=report.representation_id,
                paragraph_node_id=coverage.paragraph_node_id,
                node_start_char=node.start_char,
                status=receipt.status.value,
                gap_reasons=receipt.gap_reasons,
                stage_outputs=_read_stage_outputs(archive, receipt),
            )
        )
    return tuple(inputs)


def _render_one(paragraph: ParagraphInput, delay: float) -> None:
    print(
        f"paragraph {paragraph.ordinal}  node {paragraph.paragraph_node_id}  "
        f"status {paragraph.status}"
    )
    profile = build_profile(
        text=paragraph.text,
        representation_id=paragraph.representation_id,
        paragraph_node_id=paragraph.paragraph_node_id,
        node_start_char=paragraph.node_start_char,
        stage_outputs=paragraph.stage_outputs,
    )
    run_replay(profile, delay=delay)
    print()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="kotekomi-replay",
        description="Replay persisted HP-8 state as per-paragraph stage annotations.",
    )
    parser.add_argument("--state-root", type=Path, required=True)
    parser.add_argument(
        "--paragraph",
        type=int,
        default=None,
        help="one-based paragraph ordinal to render; omit to render all paragraphs",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.0,
        help="seconds between reveal lines; 0 renders the block at once",
    )
    args = parser.parse_args(argv)
    ledger_path = (args.state_root / "kotekomi.db").resolve()
    archive_path = (args.state_root / "archive").resolve()
    if not ledger_path.exists() or not archive_path.exists():
        parser.error(f"state root is missing kotekomi.db or archive/: {args.state_root}")
    inputs = load_paragraph_inputs(ledger_path, archive_path)
    if args.paragraph is None:
        selected = list(inputs)
    else:
        if args.paragraph < 1:
            parser.error("--paragraph must be >= 1")
        selected = [item for item in inputs if item.ordinal + 1 == args.paragraph]
        if not selected:
            raise SystemExit(f"no paragraph with ordinal {args.paragraph - 1}")
    for paragraph in selected:
        _render_one(paragraph, args.delay)
    return 0
