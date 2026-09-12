#!/usr/bin/env python3
"""Render proposed HSQ event-trigger Gold as a human-reviewable document."""

from __future__ import annotations

import argparse
from pathlib import Path

from kotekomi_pipelines.event_trigger_stage_local import (
    TriggerGoldCatalog,
    render_trigger_gold_review,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    catalog = TriggerGoldCatalog.model_validate_json(args.catalog.read_bytes())
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_trigger_gold_review(catalog), encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
