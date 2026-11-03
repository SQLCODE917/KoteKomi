"""Re-bind the R18 current-test contract to the live implementation.

The current-test contract under `data/r18-current-test-contract` binds four
digests to the live code: policy records, renderer, scoring rules, and
thresholds. `scoring_rules_sha256` covers the shared R4 composer and R16 parser
modules, so any intentional change to those modules drifts the contract and the
R18 runner regression fails until the contract is re-bound.

This script recomputes the binding from the persisted records and the current
implementation and rewrites only the `binding` block. It calls no model.
"""

from __future__ import annotations

import json
from pathlib import Path

from kotekomi_application import compute_contract_binding, frozen_semantic_selection_contract

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_DIR = ROOT / "data" / "r18-current-test-contract"


def main() -> int:
    contract_path = CONTRACT_DIR / "semantic_selection_contract.json"
    payload = json.loads(contract_path.read_text(encoding="utf-8"))
    contract = frozen_semantic_selection_contract(directory=CONTRACT_DIR)
    records = json.loads((CONTRACT_DIR / "reference_policy_records.json").read_text())["records"]
    binding = compute_contract_binding(
        records=records,
        eligibility_rule=contract.eligibility_rule,
        complete_selected_set_rules=contract.complete_selected_set_rules,
        none_rule=contract.none_rule,
        canonical_boundary_rules=contract.canonical_boundary_rules,
        signal_definitions=contract.signal_definitions,
    )
    previous = contract.binding
    payload["contract"]["binding"] = binding.model_dump(mode="json")
    contract_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    for name in (
        "policy_records_sha256",
        "renderer_sha256",
        "scoring_rules_sha256",
        "thresholds_sha256",
    ):
        mark = "changed" if getattr(binding, name) != getattr(previous, name) else "unchanged"
        print(f"{name}: {mark}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
