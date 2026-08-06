from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from kotekomi_devtools.receipt_writer import ReceiptWriterError, write_receipt


def test_write_receipt_hashes_supplied_files_and_preserves_paths(tmp_path: Path) -> None:
    input_record = tmp_path / "candidate.json"
    artifact = tmp_path / "manifest.toml"
    output = tmp_path / "nested" / "receipt.json"
    input_record.write_text('{"status":"passed"}\n', encoding="utf-8")
    artifact.write_text('task_id = "task"\n', encoding="utf-8")

    result = write_receipt(
        task_id="task",
        record_kind="candidate-ci",
        result="passed",
        output=output,
        input_records=[f"candidate={input_record}"],
        artifacts=[f"manifest={artifact}"],
        fields=["run_id=123", "empty="],
    )

    receipt = json.loads(output.read_text(encoding="utf-8"))
    assert result.receipt_sha256 == hashlib.sha256(output.read_bytes()).hexdigest()
    assert receipt["input_records"] == {
        "candidate": {"path": str(input_record), "sha256": _sha256(input_record)}
    }
    assert receipt["artifacts"] == {
        "manifest": {"path": str(artifact), "sha256": _sha256(artifact)}
    }
    assert receipt["fields"] == {"run_id": "123", "empty": ""}


@pytest.mark.parametrize(
    ("input_records", "artifacts", "fields"),
    [
        (["=record.json"], [], []),
        (["record="], [], []),
        ([], ["artifact"], []),
        ([], [], ["=value"]),
        ([], [], ["key"]),
        (["same=first", "same=second"], [], []),
        ([], [], ["same=first", "same=second"]),
    ],
)
def test_write_receipt_rejects_invalid_repeatable_entries(
    tmp_path: Path,
    input_records: list[str],
    artifacts: list[str],
    fields: list[str],
) -> None:
    output = tmp_path / "nested" / "receipt.json"

    with pytest.raises(ReceiptWriterError):
        write_receipt(
            task_id="task",
            record_kind="kind",
            result="result",
            output=output,
            input_records=input_records,
            artifacts=artifacts,
            fields=fields,
        )

    assert not output.parent.exists()


def test_write_receipt_does_not_overwrite_without_force(tmp_path: Path) -> None:
    output = tmp_path / "receipt.json"
    output.write_text("original\n", encoding="utf-8")

    with pytest.raises(ReceiptWriterError, match="already exists"):
        write_receipt(task_id="task", record_kind="kind", result="result", output=output)

    assert output.read_text(encoding="utf-8") == "original\n"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
