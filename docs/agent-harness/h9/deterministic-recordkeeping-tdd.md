# H9 Deterministic Recordkeeping TDD

Searchable labels: H9-DETERMINISTIC-RECORDING, H9-AGENT-COMMAND-CONTRACT, H9-EVIDENCE-LEDGER, H9-NO-MANUAL-STATE, H9-RECORD-INTEGRITY.

## Purpose

Implementation agents must not hand-write records, roadmap state, goal status, or final summaries. The harness owns those artifacts through deterministic commands.

## Design

```text
H9-NO-MANUAL-STATE
The implementation agent executes code and runs checks.
The harness records, formats, validates, hashes, and summarizes.
```

```text
H9-DETERMINISTIC-RECORDING
[Command Intent] -> [Domain Validation] -> [Stable Serialization] -> [SHA-256 Computation] -> [Evidence Ledger Update]
```

## Acceptance criteria

- No H9 completion path requires the implementation agent to hand-write receipt JSON.
- No H9 completion path requires the implementation agent to hand-write goal status Markdown.
- No H9 completion path requires the implementation agent to hand-write the final summary.
- Deterministic commands use sorted keys, stable ordering, and final newlines.
- Commands fail closed when evidence is missing or malformed.
- Repeated commands with the same inputs produce byte-identical output.

## Definition of Done

Acceptance tests must guarantee:

- `test_recordkeeping_command_writes_sorted_json`
- `test_recordkeeping_command_writes_final_newline`
- `test_recordkeeping_command_rejects_missing_evidence`
- `test_recordkeeping_command_is_idempotent`
- `test_final_summary_is_generated_by_command`
- `test_agent_guidance_forbids_manual_state_files`

Unit tests must guarantee:

- `test_stable_json_serializer_orders_keys`
- `test_markdown_renderer_is_deterministic`
- `test_receipt_integrity_rejects_sha_mismatch`
- `test_record_command_preserves_existing_valid_record`
