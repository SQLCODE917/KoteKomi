from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]


def _module() -> Any:
    scripts_path = str(ROOT / "scripts")
    if scripts_path not in sys.path:
        sys.path.insert(0, scripts_path)
    path = ROOT / "scripts/verify_organization_held_out_proposers.py"
    spec = importlib.util.spec_from_file_location(
        "verify_organization_held_out_proposers_test", path
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_held_out_qwen_input_uses_the_pinned_prompt_schema_and_exact_source() -> None:
    module = _module()
    rendered = module.render_qwen_input(
        b"prompt",
        b"schema",
        "s3",
        "Anthropic replied.",
    )

    assert rendered == (
        b"prompt\n\nschema\n\n[direct_prose]\n[paragraph]\nSOURCE SEGMENT: s3\nAnthropic replied."
    )


def test_held_out_qwen_output_is_parsed_by_the_application_schema_and_source_resolved() -> None:
    module = _module()
    schema = module.OrganizationMentionTaskSchemaRegistry().resolve("organization_mention_text_v1")
    status, proposals, diagnostics = module.parse_qwen_proposals(
        b"mention: s1 | Anthropic",
        "s1",
        "Anthropic met Anthropic.",
        schema,
    )

    assert status == "complete"
    assert proposals == [
        {"text": "Anthropic", "start": 0, "end": 9, "score": None},
        {"text": "Anthropic", "start": 14, "end": 23, "score": None},
    ]
    assert diagnostics == []


def test_held_out_qwen_invalid_output_remains_visible() -> None:
    module = _module()
    schema = module.OrganizationMentionTaskSchemaRegistry().resolve("organization_mention_text_v1")
    status, proposals, diagnostics = module.parse_qwen_proposals(
        b'{"organization":"Anthropic"}',
        "s1",
        "Anthropic replied.",
        schema,
    )

    assert status == "invalid_output"
    assert proposals == []
    assert diagnostics
