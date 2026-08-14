from __future__ import annotations

from pathlib import Path

import pytest
from kotekomi_devtools.lifecycle_evidence import LifecycleEvidenceError, read_ci_result


def test_ci_result_rejects_unsupported_conclusion(tmp_path: Path) -> None:
    path = tmp_path / "ci.json"
    path.write_text('{"schema_version":1,"conclusion":"pending","head_sha":"a"}\n')
    with pytest.raises(LifecycleEvidenceError, match="conclusion"):
        read_ci_result(path)


def test_ci_result_rejects_invalid_sha(tmp_path: Path) -> None:
    path = tmp_path / "ci.json"
    path.write_text('{"schema_version":1,"conclusion":"success","head_sha":"A"}\n')
    with pytest.raises(LifecycleEvidenceError, match="SHA-1"):
        read_ci_result(path)
