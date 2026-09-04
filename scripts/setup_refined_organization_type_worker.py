"""Install/download check for the pinned external ReFinED ORG-R2 worker."""

from __future__ import annotations

import argparse
import importlib
import json
import os
import time
from pathlib import Path
from typing import Any, cast

from refined_organization_type_worker import (
    REFINED_ENTITY_SET,
    REFINED_MODEL_ID,
    REFINED_MODEL_REVISION,
    REFINED_PACKAGE_REVISION,
    REFINED_PACKAGE_VERSION,
    resource_tree_digest,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--offline", action="store_true")
    arguments = parser.parse_args()
    if arguments.offline:
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
    refined_type = cast(Any, importlib.import_module("refined.inference.processor")).Refined
    span_type = cast(Any, importlib.import_module("refined.data_types.base_types")).Span
    arguments.data_dir.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    processor = refined_type.from_pretrained(
        model_name=REFINED_MODEL_ID,
        entity_set=REFINED_ENTITY_SET,
        data_dir=str(arguments.data_dir),
        device="cpu",
        use_precomputed_descriptions=True,
        download_files=not arguments.offline,
        return_titles=True,
    )
    spans = processor.process_text(
        "Amazon and Anthropic announced updates.",
        spans=[span_type("Amazon", 0, 6), span_type("Anthropic", 11, 9)],
        prune_ner_types=True,
        apply_class_check=True,
        return_special_spans=False,
    )
    digest = resource_tree_digest(arguments.data_dir)
    payload: dict[str, object] = {
        "schema_version": "refined_worker_resource_manifest_v1",
        "package_version": REFINED_PACKAGE_VERSION,
        "package_revision": REFINED_PACKAGE_REVISION,
        "model_id": REFINED_MODEL_ID,
        "model_revision": REFINED_MODEL_REVISION,
        "entity_set": REFINED_ENTITY_SET,
        "resource_manifest_sha256": digest,
        "setup_elapsed_ms": round((time.monotonic() - started) * 1000),
        "smoke_spans": [
            {
                "text": span.text,
                "start": span.start,
                "end": span.start + span.ln,
                "coarse_mention_type": span.coarse_mention_type,
            }
            for span in cast(list[Any], spans)
        ],
    }
    arguments.manifest.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
