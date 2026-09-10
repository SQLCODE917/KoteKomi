from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[3]


def _module() -> Any:
    path = ROOT / "scripts" / "evaluate_hsq4_coreference.py"
    spec = importlib.util.spec_from_file_location("evaluate_hsq4_coreference_test", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_frozen_catalog_compiles_exact_source_selectors() -> None:
    module = _module()

    catalog, cases = module.load_catalog(module.DEFAULT_CATALOG)

    assert catalog.catalog_id == "hsq4_coreference_held_out_v2"
    assert len(cases) == 9
    assert cases[0].source_text[cases[0].target.start : cases[0].target.end] == "him"
    assert [
        cases[0].source_text[item.start : item.end] for item in cases[0].expected_antecedents
    ] == ["Trump"]
    assert (
        cases[-1].source_text[
            cases[-1].expected_antecedents[0].start : cases[-1].expected_antecedents[0].end
        ]
        == "The  NIST itself"
    )
    assert cases[-1].source_text[cases[-1].target.start : cases[-1].target.end] == "its"
    assert cases[-1].target.start == 275


def test_catalog_rejects_source_drift(tmp_path: Path) -> None:
    module = _module()
    payload = json.loads(module.DEFAULT_CATALOG.read_text(encoding="utf-8"))
    payload["cases"][0]["source_text"] += " drift"
    path = tmp_path / "drifted.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="source digest"):
        module.load_catalog(path)
