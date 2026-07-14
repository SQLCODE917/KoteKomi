from __future__ import annotations

import ast
import json
import re
import shutil
import subprocess
import tomllib
from pathlib import Path
from typing import Any, cast

import pytest
from jsonschema import Draft202012Validator

REPO_ROOT = Path(__file__).resolve().parents[4]
DEVTOOLS_ROOT = REPO_ROOT / "packages" / "devtools"
SRC_ROOT = DEVTOOLS_ROOT / "src"
PACKAGE_PYPROJECT = DEVTOOLS_ROOT / "pyproject.toml"
ROOT_PYPROJECT = REPO_ROOT / "pyproject.toml"
SCHEMA_PATH = REPO_ROOT / ".agent" / "schemas" / "task-manifest-v1.schema.json"
FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "task_manifests"

EXPECTED_VALID_DIGEST = "5cddb798f8891c2605639305339cd14bfddcb36271dca777dcba09a185ada298"
HEX64 = re.compile(r"^[0-9a-f]{64}$")
FORBIDDEN_IMPORT_ROOTS = {
    "kotekomi_domain",
    "kotekomi_application",
    "kotekomi_adapters",
    "kotekomi_pipelines",
    "kotekomi_briefing",
}
FORBIDDEN_DISTRIBUTIONS = {
    "kotekomi-domain",
    "kotekomi-application",
    "kotekomi-adapters",
    "kotekomi-pipelines",
    "kotekomi-briefing",
}
PRODUCT_SOURCE_ROOTS = (
    REPO_ROOT / "packages" / "adapters" / "src",
    REPO_ROOT / "packages" / "application" / "src",
    REPO_ROOT / "packages" / "briefing" / "src",
    REPO_ROOT / "packages" / "domain" / "src",
    REPO_ROOT / "packages" / "pipelines" / "src",
)


def _cli() -> str:
    executable = shutil.which("kotekomi-agent")
    if executable is None:
        pytest.fail("kotekomi-agent is not available on PATH")
    return executable


def _run_path(path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        (_cli(), "validate-task", str(path)),
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def _run_fixture(name: str) -> subprocess.CompletedProcess[str]:
    return _run_path(FIXTURE_ROOT / name)


def _payload(completed: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    assert completed.stdout.endswith("\n")
    assert completed.stdout.count("\n") == 1
    value: object = json.loads(completed.stdout)
    assert isinstance(value, dict)
    return cast(dict[str, Any], value)


def _assert_invalid_path(
    path: Path,
    *,
    diagnostics: list[dict[str, str]],
    schema_version: int | None = 1,
    task_id: str | None = "example-task",
) -> None:
    completed = _run_path(path)

    assert completed.returncode == 1
    assert completed.stderr == ""
    assert _payload(completed) == {
        "status": "invalid",
        "schema_version": schema_version,
        "task_id": task_id,
        "manifest_sha256": None,
        "diagnostics": diagnostics,
    }


def _assert_invalid(
    name: str,
    *,
    diagnostics: list[dict[str, str]],
    schema_version: int | None = 1,
    task_id: str | None = "example-task",
) -> None:
    _assert_invalid_path(
        FIXTURE_ROOT / name,
        diagnostics=diagnostics,
        schema_version=schema_version,
        task_id=task_id,
    )


def _write_variant(
    tmp_path: Path,
    name: str,
    replacements: tuple[tuple[str, str], ...],
) -> Path:
    text = (FIXTURE_ROOT / "valid.toml").read_text()

    for old, new in replacements:
        count = text.count(old)
        assert count == 1, (old, count)
        text = text.replace(old, new, 1)

    path = tmp_path / name
    path.write_text(text)
    return path


def _root_status() -> str:
    completed = subprocess.run(
        ("git", "status", "--porcelain=v1", "--untracked-files=all"),
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    return completed.stdout


def _import_roots(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    roots: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            roots.add(node.module.split(".", 1)[0])

    return roots


def _dependency_names(values: list[str]) -> set[str]:
    return {
        re.split(r"[\s<>=!~\[]", dependency, maxsplit=1)[0].lower()
        for dependency in values
    }


def _diagnostic(code: str, location: str, rule: str) -> dict[str, str]:
    return {"code": code, "location": location, "rule": rule}


def test_protected_schema_is_valid_draft_2020_12() -> None:
    schema = json.loads(SCHEMA_PATH.read_text())
    Draft202012Validator.check_schema(schema)


def test_valid_manifest_has_exact_compact_output_and_digest() -> None:
    completed = _run_fixture("valid.toml")
    expected: dict[str, Any] = {
        "status": "valid",
        "schema_version": 1,
        "task_id": "example-task",
        "manifest_sha256": EXPECTED_VALID_DIGEST,
        "diagnostics": [],
    }
    expected_stdout = json.dumps(
        expected,
        ensure_ascii=False,
        separators=(",", ":"),
    ) + "\n"

    assert completed.returncode == 0
    assert completed.stderr == ""
    assert completed.stdout == expected_stdout
    assert HEX64.fullmatch(EXPECTED_VALID_DIGEST) is not None


def test_equivalent_toml_formatting_has_identical_digest() -> None:
    first = _payload(_run_fixture("valid.toml"))
    second = _payload(_run_fixture("valid-reformatted.toml"))

    assert first["status"] == "valid"
    assert second["status"] == "valid"
    assert first["manifest_sha256"] == second["manifest_sha256"] == EXPECTED_VALID_DIGEST


def test_array_order_changes_the_digest() -> None:
    first = _payload(_run_fixture("valid.toml"))
    reordered = _payload(_run_fixture("valid-reordered.toml"))

    assert first["status"] == "valid"
    assert reordered["status"] == "valid"
    assert reordered["manifest_sha256"] != first["manifest_sha256"]
    assert HEX64.fullmatch(str(reordered["manifest_sha256"])) is not None


@pytest.mark.parametrize(
    ("name", "diagnostics", "task_id"),
    [
        (
            "missing-required.toml",
            [_diagnostic("task_manifest.schema_violation", "", "required")],
            "example-task",
        ),
        (
            "unknown-top-level.toml",
            [_diagnostic("task_manifest.schema_violation", "", "additionalProperties")],
            "example-task",
        ),
        (
            "unknown-nested.toml",
            [
                _diagnostic(
                    "task_manifest.schema_violation",
                    "/budget",
                    "additionalProperties",
                )
            ],
            "example-task",
        ),
        (
            "invalid-task-id.toml",
            [_diagnostic("task_manifest.schema_violation", "/task_id", "pattern")],
            None,
        ),
        (
            "invalid-baseline-revision.toml",
            [
                _diagnostic(
                    "task_manifest.schema_violation",
                    "/baseline_revision",
                    "pattern",
                )
            ],
            "example-task",
        ),
        (
            "invalid-digest.toml",
            [_diagnostic("task_manifest.schema_violation", "/tdd_sha256", "pattern")],
            "example-task",
        ),
        (
            "empty-argv.toml",
            [
                _diagnostic(
                    "task_manifest.schema_violation",
                    "/acceptance/0/argv",
                    "minItems",
                )
            ],
            "example-task",
        ),
        (
            "shell-command-string.toml",
            [
                _diagnostic(
                    "task_manifest.schema_violation",
                    "/acceptance/0",
                    "additionalProperties",
                ),
                _diagnostic(
                    "task_manifest.schema_violation",
                    "/acceptance/0",
                    "required",
                ),
            ],
            "example-task",
        ),
        (
            "invalid-profile.toml",
            [
                _diagnostic(
                    "task_manifest.schema_violation",
                    "/acceptance/0/profile",
                    "enum",
                )
            ],
            "example-task",
        ),
        (
            "unresolved-decisions.toml",
            [
                _diagnostic(
                    "task_manifest.schema_violation",
                    "/readiness/unresolved_decisions",
                    "maxItems",
                )
            ],
            "example-task",
        ),
    ],
)
def test_protected_schema_failures(
    name: str,
    diagnostics: list[dict[str, str]],
    task_id: str | None,
) -> None:
    _assert_invalid(name, diagnostics=diagnostics, task_id=task_id)


@pytest.mark.parametrize(
    ("name", "location", "rule"),
    [
        ("absolute-path.toml", "/allowed_paths/0", "repository_relative_posix"),
        ("parent-traversal.toml", "/allowed_paths/0", "repository_relative_posix"),
        ("backslash-path.toml", "/allowed_paths/0", "repository_relative_posix"),
        ("duplicate-allowed-path.toml", "/allowed_paths/1", "unique_path"),
        ("protected-directory-path.toml", "/protected_artifacts/0/path", "exact_file"),
    ],
)
def test_protected_path_fixtures_are_rejected(
    name: str,
    location: str,
    rule: str,
) -> None:
    _assert_invalid(
        name,
        diagnostics=[_diagnostic("task_manifest.path_violation", location, rule)],
    )


@pytest.mark.parametrize(
    ("name", "old", "new", "location", "rule"),
    [
        (
            "dot-prefix.toml",
            'allowed_paths = ["pyproject.toml", "packages/devtools/src/"]',
            'allowed_paths = ["./pyproject.toml", "packages/devtools/src/"]',
            "/allowed_paths/0",
            "repository_relative_posix",
        ),
        (
            "repeated-slash.toml",
            'allowed_paths = ["pyproject.toml", "packages/devtools/src/"]',
            'allowed_paths = ["packages//devtools", "packages/devtools/src/"]',
            "/allowed_paths/0",
            "repository_relative_posix",
        ),
        (
            "tilde-prefix.toml",
            'allowed_paths = ["pyproject.toml", "packages/devtools/src/"]',
            'allowed_paths = ["~/file", "packages/devtools/src/"]',
            "/allowed_paths/0",
            "repository_relative_posix",
        ),
        (
            "wildcard.toml",
            'allowed_paths = ["pyproject.toml", "packages/devtools/src/"]',
            'allowed_paths = ["packages/*/src/", "packages/devtools/src/"]',
            "/allowed_paths/0",
            "repository_relative_posix",
        ),
        (
            "tdd-directory.toml",
            'tdd_path = "docs/example-task.md"',
            'tdd_path = "docs/"',
            "/tdd_path",
            "exact_file",
        ),
    ],
)
def test_additional_repository_path_rules(
    tmp_path: Path,
    name: str,
    old: str,
    new: str,
    location: str,
    rule: str,
) -> None:
    path = _write_variant(tmp_path, name, ((old, new),))
    _assert_invalid_path(
        path,
        diagnostics=[_diagnostic("task_manifest.path_violation", location, rule)],
    )


def test_duplicate_reference_path_is_rejected(tmp_path: Path) -> None:
    path = _write_variant(
        tmp_path,
        "duplicate-reference-path.toml",
        (
            (
                'reference_paths = ["AGENTS.md", "docs/agent/writing-tdds.md"]',
                'reference_paths = ["AGENTS.md", "AGENTS.md"]',
            ),
        ),
    )
    _assert_invalid_path(
        path,
        diagnostics=[
            _diagnostic(
                "task_manifest.path_violation",
                "/reference_paths/1",
                "unique_path",
            )
        ],
    )


def test_duplicate_protected_artifact_path_is_rejected(tmp_path: Path) -> None:
    block = (
        '[[protected_artifacts]]\n'
        'path = "docs/example-task.md"\n'
        'sha256 = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"\n'
        'kind = "leaf-tdd"\n'
    )
    path = _write_variant(
        tmp_path,
        "duplicate-protected-path.toml",
        ((block, block + "\n" + block),),
    )
    _assert_invalid_path(
        path,
        diagnostics=[
            _diagnostic(
                "task_manifest.path_violation",
                "/protected_artifacts/1/path",
                "unique_path",
            )
        ],
    )


def test_duplicate_acceptance_id_is_rejected(tmp_path: Path) -> None:
    path = _write_variant(
        tmp_path,
        "duplicate-acceptance-id.toml",
        (('id = "linux-regression"', 'id = "portable-contract"'),),
    )
    _assert_invalid_path(
        path,
        diagnostics=[
            _diagnostic(
                "task_manifest.semantic_violation",
                "/acceptance/1/id",
                "unique_identifier",
            )
        ],
    )


def test_multiple_path_errors_have_stable_order(tmp_path: Path) -> None:
    path = _write_variant(
        tmp_path,
        "multiple-path-errors.toml",
        (
            (
                'allowed_paths = ["pyproject.toml", "packages/devtools/src/"]',
                'allowed_paths = ["/absolute", "../outside"]',
            ),
            (
                'reference_paths = ["AGENTS.md", "docs/agent/writing-tdds.md"]',
                'reference_paths = ["./AGENTS.md", "docs//agent"]',
            ),
            ('tdd_path = "docs/example-task.md"', 'tdd_path = "docs/"'),
        ),
    )
    expected = [
        _diagnostic(
            "task_manifest.path_violation",
            "/allowed_paths/0",
            "repository_relative_posix",
        ),
        _diagnostic(
            "task_manifest.path_violation",
            "/allowed_paths/1",
            "repository_relative_posix",
        ),
        _diagnostic(
            "task_manifest.path_violation",
            "/reference_paths/0",
            "repository_relative_posix",
        ),
        _diagnostic(
            "task_manifest.path_violation",
            "/reference_paths/1",
            "repository_relative_posix",
        ),
        _diagnostic("task_manifest.path_violation", "/tdd_path", "exact_file"),
    ]
    _assert_invalid_path(path, diagnostics=expected)


def test_schema_failure_prevents_path_validation(tmp_path: Path) -> None:
    path = _write_variant(
        tmp_path,
        "schema-short-circuit.toml",
        (
            ('task_id = "example-task"', 'task_id = "Example_Task"'),
            (
                'allowed_paths = ["pyproject.toml", "packages/devtools/src/"]',
                'allowed_paths = ["/absolute", "packages/devtools/src/"]',
            ),
        ),
    )
    _assert_invalid_path(
        path,
        diagnostics=[
            _diagnostic(
                "task_manifest.schema_violation",
                "/task_id",
                "pattern",
            )
        ],
        task_id=None,
    )


def test_missing_file_has_stable_diagnostic() -> None:
    completed = _run_path(FIXTURE_ROOT / "does-not-exist.toml")
    assert completed.returncode == 1
    assert completed.stderr == ""
    assert _payload(completed) == {
        "status": "invalid",
        "schema_version": None,
        "task_id": None,
        "manifest_sha256": None,
        "diagnostics": [
            _diagnostic("task_manifest.file_not_found", "", "exists")
        ],
    }


def test_directory_has_stable_unreadable_diagnostic(tmp_path: Path) -> None:
    _assert_invalid_path(
        tmp_path,
        diagnostics=[
            _diagnostic("task_manifest.file_unreadable", "", "readable")
        ],
        schema_version=None,
        task_id=None,
    )


def test_invalid_utf8_has_stable_unreadable_diagnostic(tmp_path: Path) -> None:
    path = tmp_path / "invalid-utf8.toml"
    path.write_bytes(b"\xff")
    _assert_invalid_path(
        path,
        diagnostics=[_diagnostic("task_manifest.file_unreadable", "", "utf8")],
        schema_version=None,
        task_id=None,
    )


def test_malformed_toml_has_stable_diagnostic() -> None:
    completed = _run_fixture("malformed.toml")
    assert completed.returncode == 1
    assert completed.stderr == ""
    assert _payload(completed) == {
        "status": "invalid",
        "schema_version": None,
        "task_id": None,
        "manifest_sha256": None,
        "diagnostics": [
            _diagnostic("task_manifest.toml_parse_error", "", "toml")
        ],
    }


def test_multiple_schema_errors_have_stable_order() -> None:
    _assert_invalid(
        "multiple-errors.toml",
        diagnostics=[
            _diagnostic(
                "task_manifest.schema_violation",
                "/baseline_revision",
                "pattern",
            ),
            _diagnostic("task_manifest.schema_violation", "/task_id", "pattern"),
            _diagnostic(
                "task_manifest.schema_violation",
                "/tdd_sha256",
                "pattern",
            ),
        ],
        task_id=None,
    )


def test_invalid_cli_invocation_has_usage_error() -> None:
    completed = subprocess.run(
        (_cli(),),
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 2
    assert completed.stdout == ""
    assert "usage" in completed.stderr.lower()
    assert "traceback" not in completed.stderr.lower()


def test_validation_executes_no_command_and_changes_no_repository_state(
    tmp_path: Path,
) -> None:
    sentinel = tmp_path / "executed.txt"
    command = (
        "from pathlib import Path; "
        f"Path({str(sentinel)!r}).write_text('executed')"
    )
    replacement = "argv = [" + ", ".join(
        json.dumps(value)
        for value in ("python", "-c", command)
    ) + "]"
    path = _write_variant(
        tmp_path,
        "inert-command.toml",
        (
            (
                'argv = ["uv", "run", "pytest", '
                '"packages/devtools/tests/acceptance/test_task_manifest_contract.py"]',
                replacement,
            ),
        ),
    )
    before = _root_status()
    completed = _run_path(path)
    after = _root_status()

    assert completed.returncode == 0
    assert completed.stderr == ""
    assert _payload(completed)["status"] == "valid"
    assert not sentinel.exists()
    assert after == before


def test_devtools_source_imports_no_product_package() -> None:
    source_files = sorted(SRC_ROOT.rglob("*.py"))
    assert source_files
    violations = [
        f"{source_file.relative_to(REPO_ROOT)} imports {name}"
        for source_file in source_files
        for name in sorted(_import_roots(source_file) & FORBIDDEN_IMPORT_ROOTS)
    ]
    assert violations == []


def test_product_source_imports_no_devtools_package() -> None:
    violations = [
        f"{source_file.relative_to(REPO_ROOT)} imports kotekomi_devtools"
        for root in PRODUCT_SOURCE_ROOTS
        for source_file in sorted(root.rglob("*.py"))
        if "kotekomi_devtools" in _import_roots(source_file)
    ]
    assert violations == []


def test_devtools_runtime_dependencies_include_no_product_package() -> None:
    configuration = tomllib.loads(PACKAGE_PYPROJECT.read_text())
    dependencies = configuration.get("project", {}).get("dependencies", [])
    assert _dependency_names(dependencies).isdisjoint(FORBIDDEN_DISTRIBUTIONS)


def test_root_workspace_and_quality_tools_include_devtools() -> None:
    configuration = tomllib.loads(ROOT_PYPROJECT.read_text())
    tool = configuration["tool"]
    uv = tool["uv"]
    pytest_configuration = tool["pytest"]["ini_options"]
    pyright = tool["pyright"]

    assert "packages/devtools" in uv["workspace"]["members"]
    assert uv["sources"]["kotekomi-devtools"] == {"workspace": True}
    assert "kotekomi-devtools" in _dependency_names(
        configuration["dependency-groups"]["dev"]
    )
    assert "packages/devtools/tests" in pytest_configuration["testpaths"]
    assert "packages/devtools/src" in pytest_configuration["pythonpath"]
    assert "packages/devtools/src" in pyright["include"]
    assert "packages/devtools/tests" in pyright["include"]
    assert any(
        environment.get("root") == "."
        and "packages/devtools/src" in environment.get("extraPaths", [])
        for environment in pyright["executionEnvironments"]
    )
