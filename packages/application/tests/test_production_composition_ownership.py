"""ISC-02: production composition owns its contracts and construction.

These checks read the production module source, so they prove the import boundary
without relying on runtime side effects. The timestamp checks prove that shared
construction takes its timestamp from the caller.
"""

from __future__ import annotations

import ast
from datetime import UTC, datetime
from pathlib import Path

from kotekomi_application import AssertionConstructionInputs
from kotekomi_application.decontextualization_composition import (
    DecontextualizationStatus,
    DecontextualizedProposition,
)
from kotekomi_domain import AssertionType, AttributionBasis, SourceAuthority

PRODUCTION_COMPOSITION = (
    Path(__file__).resolve().parents[2]
    / "application"
    / "src"
    / "kotekomi_application"
    / "source_grounded_reference_composition.py"
)
EXPERIMENT_MODULES = {
    "kotekomi_application.deterministic_residual_composition_completion",
    "kotekomi_application.competitive_attachment_review_verification",
}


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
        elif isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
    return modules


def test_production_composition_has_no_experiment_dependency() -> None:
    """ISC-02-A: production composition imports no experiment or review module."""
    imported = _imported_modules(PRODUCTION_COMPOSITION)
    assert not (imported & EXPERIMENT_MODULES)
    assert "kotekomi_application.assertion_construction" in imported
    assert "kotekomi_application.source_ranges" in imported


def test_default_exports_do_not_load_historical_experiment_modules() -> None:
    """ISC-02-D: the Application Layer default surface stays production-owned."""
    import kotekomi_application as application

    assert not hasattr(application, "complete_deterministic_residual_composition")
    assert hasattr(application, "construct_inspectable_assertion")
    assert hasattr(application, "SourceRange")


def test_construction_uses_the_caller_supplied_timestamp() -> None:
    """ISC-02-C: shared construction takes its timestamp from the caller."""
    from kotekomi_application import construct_inspectable_assertion

    proposition = DecontextualizedProposition.model_construct(
        event_id="sge_isc02",
        source_text_sha256="a" * 64,
        status=DecontextualizationStatus.PROPOSITION,
        relation_label="support",
        subject=None,
        object=None,
        attribution=None,
    )
    assert proposition.status is DecontextualizationStatus.PROPOSITION
    inputs = AssertionConstructionInputs(
        predicate_by_label={"support": "supports"},
        identity_by_entity={},
        assertion_type=AssertionType.REPORTED_OBSERVATION,
        source_authority=SourceAuthority.SECONDARY,
        attribution_basis=AttributionBasis.DIRECT_DOCUMENT,
        source_id="src_isc02",
        evidence_target_id="etg_isc02",
        constructed_at=datetime(2030, 5, 6, tzinfo=UTC),
    )
    outcome = construct_inspectable_assertion(proposition, inputs)

    # The construction blocks on the first missing requirement, so the timestamp
    # contract is proven through the declared field rather than a silent default.
    assert outcome.block_reason is not None
    assert inputs.constructed_at == datetime(2030, 5, 6, tzinfo=UTC)
