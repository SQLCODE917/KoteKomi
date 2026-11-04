#!/usr/bin/env python3
"""Run the R19 deterministic residual composition completion Pipeline.

The runner wires the real Event-Entity Connection Adapter, the supplement gates,
the frozen R17 policy, and the SQLite Ledger through the Application Layer use
case. It writes one sealed report and changes no canonical state.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from kotekomi_adapters.sqlite_ledger import sqlite_ledger_transaction
from kotekomi_application import (
    DecontextualizationEntityRef,
    DecontextualizationExclusion,
    EventEntityReferences,
    ReferencePolicyRecord,
    SourceRange,
    frozen_semantic_selection_contract,
    load_reference_policy_records,
)
from kotekomi_pipelines.deterministic_residual_composition_completion import (
    run_deterministic_residual_composition,
)
from kotekomi_pipelines.event_entity_connection_stage_local import (
    ConnectionGoldCatalog,
    ConnectionGoldEvent,
    event_entity_references,
    load_connection_gold_catalog,
    reanchor_whitespace_spans,
)
from kotekomi_pipelines.r19_provider_supplement import (
    R19ProviderSupplement,
    SupplementSubjectValueExclusion,
    load_r19_provider_supplement,
)
from kotekomi_pipelines.source_grounded_proposition_stage_local import (
    PropositionGoldCatalog,
    load_proposition_gold_catalog,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SUPPLEMENT = REPOSITORY_ROOT / "docs" / "hsq-r19-provider-supplement-v1.json"
DEFAULT_DATA = REPOSITORY_ROOT / "data" / "r17-semantic-selection-contract"
DEFAULT_LEDGER = REPOSITORY_ROOT / "data" / "kotekomi.db"


class _ReanchoredProvider:
    def __init__(self, event: ConnectionGoldEvent, provider_text: str, residual_text: str) -> None:
        references = event_entity_references(event, provider_text)
        entities = tuple(
            DecontextualizationEntityRef(
                entity_id=entity.entity_id,
                entity_kind=entity.entity_kind,
                canonical_name=entity.canonical_name,
                accepted_source_occurrences=reanchor_whitespace_spans(
                    provider_text=provider_text,
                    residual_text=residual_text,
                    spans=entity.accepted_source_occurrences,
                ),
            )
            for entity in references.entities
        )
        self._references = EventEntityReferences(entities=entities, subject_value_authorizations=())

    def resolve_references(
        self, event_id: str, source_text: str, source_text_sha256: str
    ) -> EventEntityReferences:
        del event_id, source_text, source_text_sha256
        return self._references


class _ProviderOnly:
    def __init__(self, exclusion: SupplementSubjectValueExclusion, residual_text: str) -> None:
        authorization = DecontextualizationExclusion(
            exclusion_id=exclusion.exclusion_id,
            contextual_kind="non_entity_value",
            source_range=SourceRange(
                start=exclusion.start, end=exclusion.end, text=exclusion.source_text
            ),
            rationale=exclusion.rationale,
        )
        self._references = EventEntityReferences(
            entities=(), subject_value_authorizations=(authorization,)
        )

    def resolve_references(
        self, event_id: str, source_text: str, source_text_sha256: str
    ) -> EventEntityReferences:
        del event_id, source_text, source_text_sha256
        return self._references


def _build_providers(
    supplement: R19ProviderSupplement,
    policy_records: tuple[ReferencePolicyRecord, ...],
    connection_catalog: ConnectionGoldCatalog,
    proposition_catalog: PropositionGoldCatalog,
) -> dict[str, _ReanchoredProvider | _ProviderOnly]:
    connection_events = {item.event_id: item for item in connection_catalog.events}
    proposition_events = {item.event_id: item for item in proposition_catalog.events}
    binding_by_event = {item.residual_event_id: item for item in supplement.event_bindings}
    exclusion_by_event = {item.event_id: item for item in supplement.subject_value_exclusions}

    providers: dict[str, _ReanchoredProvider | _ProviderOnly] = {}
    for policy in policy_records:
        binding = binding_by_event[policy.event_id]
        if binding.provider_event_id is None:
            providers[policy.event_id] = _ProviderOnly(
                exclusion_by_event[policy.event_id], policy.source_text
            )
        else:
            provider_event = connection_events[binding.provider_event_id]
            provider_text = proposition_events[binding.provider_event_id].source_text
            providers[policy.event_id] = _ReanchoredProvider(
                provider_event, provider_text, policy.source_text
            )
    return providers


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--supplement", default=str(DEFAULT_SUPPLEMENT))
    parser.add_argument("--ledger", default=str(DEFAULT_LEDGER))
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    supplement = load_r19_provider_supplement(
        Path(args.supplement), repository_root=REPOSITORY_ROOT
    )
    contract = frozen_semantic_selection_contract(directory=DEFAULT_DATA)
    all_policy_records = load_reference_policy_records(contract=contract, directory=DEFAULT_DATA)
    bound_events = {item.residual_event_id for item in supplement.event_bindings}
    policy_records = tuple(item for item in all_policy_records if item.event_id in bound_events)

    connection_catalog, _, _ = load_connection_gold_catalog(
        REPOSITORY_ROOT / supplement.bound_connection_gold.path,
        repository_root=REPOSITORY_ROOT,
        require_approved=True,
    )
    proposition_catalog = load_proposition_gold_catalog(
        REPOSITORY_ROOT / supplement.bound_proposition_gold.path,
        repository_root=REPOSITORY_ROOT,
    )
    provider_by_event = _build_providers(
        supplement, policy_records, connection_catalog, proposition_catalog
    )

    with sqlite_ledger_transaction(Path(args.ledger)) as repository:
        report = run_deterministic_residual_composition(
            report_id="r19-deterministic-residual-composition",
            supplement=supplement,
            policy_records=policy_records,
            closure_ledger=repository,
            evidence_ledger=repository,
            build_provider=lambda event_id, text, digest: provider_by_event[event_id],
        )

    output_root = Path(args.out)
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "report.json").write_text(report.model_dump_json(indent=2), encoding="utf-8")
    run_summary = {
        "schema_version": "r19_residual_composition_run_v1",
        "report": "report.json",
        "residuals": [
            {
                "event_id": item.event_id,
                "terminal_status": item.terminal_status.value,
                "block_reason": item.block_reason,
            }
            for item in report.residuals
        ],
        "model_execution_count": 0,
        "canonical_write_count": 0,
        "proposed_change_count": 0,
        "result_fingerprint": report.result_fingerprint,
    }
    (output_root / "run.json").write_text(
        json.dumps(run_summary, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(run_summary, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
