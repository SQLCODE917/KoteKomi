"""Deterministic local verification planning for Task Manifest revisions."""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

type JsonObject = dict[str, object]
type CheckSource = Literal["manifest", "retained", "quality", "touched-path"]

_CLI_PATH = "packages/devtools/src/kotekomi_devtools/cli.py"
_QUALITY_CHECKS = {
    "repository-static-checks": ("uv", "run", "ruff", "check"),
    "repository-type-checks": ("uv", "run", "pyright"),
}
_CLI_TOUCHED_CHECKS = (
    (
        "task-manifest-contract",
        (
            "uv",
            "run",
            "pytest",
            "-p",
            "no:cacheprovider",
            "packages/devtools/tests/acceptance/test_task_manifest_contract.py",
        ),
    ),
    (
        "task-preflight-contract",
        (
            "uv",
            "run",
            "pytest",
            "-p",
            "no:cacheprovider",
            "packages/devtools/tests/acceptance/test_task_preflight_contract.py",
        ),
    ),
    (
        "cli-delimiter-regression-contract",
        (
            "uv",
            "run",
            "pytest",
            "-p",
            "no:cacheprovider",
            "packages/devtools/tests/acceptance/test_verification_execution_contract.py",
            "-k",
            "delimiter",
        ),
    ),
    (
        "tdd-binding-acceptance-contract",
        (
            "uv",
            "run",
            "pytest",
            "-p",
            "no:cacheprovider",
            "packages/devtools/tests/acceptance/test_tdd_binding_contract.py",
        ),
    ),
)


_H14_TOUCHED_PATH_CHECKS = {
    "packages/devtools/src/kotekomi_devtools/step_scripts.py": (
        (
            "step-scripts-acceptance-contract",
            (
                "uv",
                "run",
                "pytest",
                "-p",
                "no:cacheprovider",
                "packages/devtools/tests/acceptance/test_step_scripts_contract.py",
            ),
        ),
        (
            "step-scripts-unit-contract",
            (
                "uv",
                "run",
                "pytest",
                "-p",
                "no:cacheprovider",
                "packages/devtools/tests/unit/test_step_scripts.py",
            ),
        ),
    ),
    "packages/devtools/tests/acceptance/test_step_scripts_contract.py": (
        (
            "step-scripts-acceptance-contract",
            (
                "uv",
                "run",
                "pytest",
                "-p",
                "no:cacheprovider",
                "packages/devtools/tests/acceptance/test_step_scripts_contract.py",
            ),
        ),
    ),
    "packages/devtools/tests/unit/test_step_scripts.py": (
        (
            "step-scripts-unit-contract",
            (
                "uv",
                "run",
                "pytest",
                "-p",
                "no:cacheprovider",
                "packages/devtools/tests/unit/test_step_scripts.py",
            ),
        ),
    ),
    "packages/devtools/src/kotekomi_devtools/task_lifecycle.py": (
        (
            "task-lifecycle-acceptance-contract",
            (
                "uv",
                "run",
                "pytest",
                "-p",
                "no:cacheprovider",
                "packages/devtools/tests/acceptance/test_task_lifecycle_contract.py",
            ),
        ),
        (
            "task-lifecycle-unit-contract",
            (
                "uv",
                "run",
                "pytest",
                "-p",
                "no:cacheprovider",
                "packages/devtools/tests/unit/test_task_lifecycle.py",
            ),
        ),
    ),
    "packages/devtools/tests/acceptance/test_task_lifecycle_contract.py": (
        (
            "task-lifecycle-acceptance-contract",
            (
                "uv",
                "run",
                "pytest",
                "-p",
                "no:cacheprovider",
                "packages/devtools/tests/acceptance/test_task_lifecycle_contract.py",
            ),
        ),
    ),
    "packages/devtools/tests/unit/test_task_lifecycle.py": (
        (
            "task-lifecycle-unit-contract",
            (
                "uv",
                "run",
                "pytest",
                "-p",
                "no:cacheprovider",
                "packages/devtools/tests/unit/test_task_lifecycle.py",
            ),
        ),
    ),
    "packages/devtools/src/kotekomi_devtools/task_manifest.py": (
        (
            "task-manifest-contract",
            (
                "uv",
                "run",
                "pytest",
                "-p",
                "no:cacheprovider",
                "packages/devtools/tests/acceptance/test_task_manifest_contract.py",
            ),
        ),
    ),
    "packages/devtools/tests/acceptance/test_task_manifest_contract.py": (
        (
            "task-manifest-contract",
            (
                "uv",
                "run",
                "pytest",
                "-p",
                "no:cacheprovider",
                "packages/devtools/tests/acceptance/test_task_manifest_contract.py",
            ),
        ),
    ),
    "packages/devtools/src/kotekomi_devtools/task_preflight.py": (
        (
            "task-preflight-contract",
            (
                "uv",
                "run",
                "pytest",
                "-p",
                "no:cacheprovider",
                "packages/devtools/tests/acceptance/test_task_preflight_contract.py",
            ),
        ),
    ),
    "packages/devtools/tests/acceptance/test_task_preflight_contract.py": (
        (
            "task-preflight-contract",
            (
                "uv",
                "run",
                "pytest",
                "-p",
                "no:cacheprovider",
                "packages/devtools/tests/acceptance/test_task_preflight_contract.py",
            ),
        ),
    ),
    "packages/devtools/src/kotekomi_devtools/tdd_binding.py": (
        (
            "tdd-binding-acceptance-contract",
            (
                "uv",
                "run",
                "pytest",
                "-p",
                "no:cacheprovider",
                "packages/devtools/tests/acceptance/test_tdd_binding_contract.py",
            ),
        ),
        (
            "tdd-binding-unit-contract",
            (
                "uv",
                "run",
                "pytest",
                "-p",
                "no:cacheprovider",
                "packages/devtools/tests/unit/test_tdd_binding.py",
            ),
        ),
    ),
    "packages/devtools/tests/acceptance/test_tdd_binding_contract.py": (
        (
            "tdd-binding-acceptance-contract",
            (
                "uv",
                "run",
                "pytest",
                "-p",
                "no:cacheprovider",
                "packages/devtools/tests/acceptance/test_tdd_binding_contract.py",
            ),
        ),
    ),
    "packages/devtools/tests/unit/test_tdd_binding.py": (
        (
            "tdd-binding-unit-contract",
            (
                "uv",
                "run",
                "pytest",
                "-p",
                "no:cacheprovider",
                "packages/devtools/tests/unit/test_tdd_binding.py",
            ),
        ),
    ),
    "packages/devtools/src/kotekomi_devtools/verification_execution.py": (
        (
            "verification-execution-contract",
            (
                "uv",
                "run",
                "pytest",
                "-p",
                "no:cacheprovider",
                "packages/devtools/tests/acceptance/test_verification_execution_contract.py",
            ),
        ),
    ),
    "packages/devtools/tests/acceptance/test_verification_execution_contract.py": (
        (
            "verification-execution-contract",
            (
                "uv",
                "run",
                "pytest",
                "-p",
                "no:cacheprovider",
                "packages/devtools/tests/acceptance/test_verification_execution_contract.py",
            ),
        ),
    ),
    "packages/devtools/src/kotekomi_devtools/verification_plan.py": (
        (
            "verification-plan-acceptance-contract",
            (
                "uv",
                "run",
                "pytest",
                "-p",
                "no:cacheprovider",
                "packages/devtools/tests/acceptance/test_verification_plan_contract.py",
            ),
        ),
        (
            "verification-plan-unit-contract",
            (
                "uv",
                "run",
                "pytest",
                "-p",
                "no:cacheprovider",
                "packages/devtools/tests/unit/test_verification_plan.py",
            ),
        ),
    ),
    "packages/devtools/tests/acceptance/test_verification_plan_contract.py": (
        (
            "verification-plan-acceptance-contract",
            (
                "uv",
                "run",
                "pytest",
                "-p",
                "no:cacheprovider",
                "packages/devtools/tests/acceptance/test_verification_plan_contract.py",
            ),
        ),
    ),
    "packages/devtools/tests/unit/test_verification_plan.py": (
        (
            "verification-plan-unit-contract",
            (
                "uv",
                "run",
                "pytest",
                "-p",
                "no:cacheprovider",
                "packages/devtools/tests/unit/test_verification_plan.py",
            ),
        ),
    ),
    "packages/devtools/src/kotekomi_devtools/candidate_verifier.py": (
        (
            "independent-verifier-receipt-contract",
            (
                "uv",
                "run",
                "pytest",
                "-p",
                "no:cacheprovider",
                "packages/devtools/tests/acceptance/test_independent_verifier_receipt_contract.py",
                "packages/devtools/tests/unit/test_candidate_verifier.py",
            ),
        ),
    ),
    "packages/devtools/tests/unit/test_candidate_verifier.py": (
        (
            "independent-verifier-receipt-contract",
            (
                "uv",
                "run",
                "pytest",
                "-p",
                "no:cacheprovider",
                "packages/devtools/tests/acceptance/test_independent_verifier_receipt_contract.py",
                "packages/devtools/tests/unit/test_candidate_verifier.py",
            ),
        ),
    ),
}


class VerificationPlanError(ValueError):
    """Raised when deterministic verification planning inputs cannot be read."""


@dataclass(frozen=True)
class VerificationDiagnostic:
    """One fail-closed changed-path diagnostic."""

    code: str
    location: str
    rule: str

    def as_json(self) -> dict[str, str]:
        return {"code": self.code, "location": self.location, "rule": self.rule}


@dataclass(frozen=True)
class VerificationCheck:
    """One required local command and its deterministic rationale."""

    id: str
    argv: tuple[str, ...]
    reason: str
    source: CheckSource

    def as_json(self) -> dict[str, str]:
        return {
            "id": self.id,
            "command": shlex.join(self.argv),
            "reason": self.reason,
            "source": self.source,
        }


@dataclass(frozen=True)
class VerificationPlan:
    """The complete deterministic local verification plan for one revision range."""

    task_id: str
    base_revision: str
    head_revision: str
    changed_paths: tuple[str, ...]
    checks: tuple[VerificationCheck, ...]
    diagnostics: tuple[VerificationDiagnostic, ...]

    @property
    def ready(self) -> bool:
        return not self.diagnostics

    @property
    def exit_code(self) -> int:
        return 0 if self.ready else 1

    def as_json(self) -> JsonObject:
        return {
            "status": "ready" if self.ready else "not_ready",
            "schema_version": 1,
            "task_id": self.task_id,
            "base_revision": self.base_revision,
            "head_revision": self.head_revision,
            "changed_paths": list(self.changed_paths),
            "checks": [check.as_json() for check in self.checks],
            "diagnostics": [diagnostic.as_json() for diagnostic in self.diagnostics],
        }

    def markdown(self) -> str:
        lines = [
            f"# Verification Plan: {self.task_id}",
            "",
            f"Status: {'ready' if self.ready else 'not_ready'}",
            f"Base revision: `{self.base_revision}`",
            f"Head revision: `{self.head_revision}`",
            "",
            "## Changed paths",
            "",
        ]
        lines.extend(f"- `{path}`" for path in self.changed_paths)
        if not self.changed_paths:
            lines.append("- None.")

        lines.extend(["", "## Required checks", ""])
        for check in self.checks:
            lines.extend(
                [
                    f"- `{check.id}`",
                    f"  - Command: `{shlex.join(check.argv)}`",
                    f"  - Reason: {check.reason}",
                    f"  - Source: {check.source}",
                ]
            )
        if not self.checks:
            lines.append("- None.")

        lines.extend(["", "## Diagnostics", ""])
        if self.diagnostics:
            lines.extend(
                f"- `{diagnostic.code}` at `{diagnostic.location}`: {diagnostic.rule}"
                for diagnostic in self.diagnostics
            )
        else:
            lines.append("- None.")
        return "\n".join(lines) + "\n"


def write_verification_plan(
    manifest_path: Path,
    *,
    base_revision: str,
    head_revision: str,
    output: Path,
    markdown: Path,
) -> VerificationPlan:
    """Plan checks from one manifest and Git revision range, then write stable reports."""
    plan = build_verification_plan(
        manifest_path,
        base_revision=base_revision,
        head_revision=head_revision,
    )
    _write_text(output, json.dumps(plan.as_json(), indent=2, sort_keys=True) + "\n")
    _write_text(markdown, plan.markdown())
    return plan


def build_verification_plan(
    manifest_path: Path, *, base_revision: str, head_revision: str
) -> VerificationPlan:
    """Plan required checks without running them or modifying Git state."""
    manifest = _load_manifest(manifest_path)
    changed_paths = _changed_paths(base_revision, head_revision)
    allowed_paths = _string_list(manifest, "allowed_paths")
    diagnostics = tuple(
        VerificationDiagnostic(
            "verification_plan.uncovered_changed_path",
            f"/changed_paths/{index}",
            "changed_paths_require_manifest_or_shared_rule",
        )
        for index, path in enumerate(changed_paths)
        if path not in allowed_paths and not _has_shared_rule(path)
    )
    checks = _checks(manifest, changed_paths)
    return VerificationPlan(
        _required_string(manifest, "task_id"),
        base_revision,
        head_revision,
        changed_paths,
        checks,
        diagnostics,
    )


def _load_manifest(path: Path) -> JsonObject:
    try:
        parsed = cast(object, tomllib.loads(path.read_text(encoding="utf-8")))
    except FileNotFoundError as error:
        raise VerificationPlanError("verification-plan manifest does not exist") from error
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as error:
        raise VerificationPlanError("verification-plan manifest is not readable TOML") from error
    if not isinstance(parsed, Mapping):
        raise VerificationPlanError("verification-plan manifest must be a TOML table")
    manifest = cast(JsonObject, parsed)
    _required_string(manifest, "task_id")
    _string_list(manifest, "allowed_paths")
    _acceptance_checks(manifest)
    return manifest


def _required_string(value: Mapping[str, object], key: str) -> str:
    item = value.get(key)
    if not isinstance(item, str) or not item:
        raise VerificationPlanError(f"verification-plan manifest requires {key}")
    return item


def _string_list(value: Mapping[str, object], key: str) -> tuple[str, ...]:
    item = value.get(key)
    if not isinstance(item, list):
        raise VerificationPlanError(f"verification-plan manifest requires {key} strings")
    entries = cast(list[object], item)
    if not all(isinstance(entry, str) for entry in entries):
        raise VerificationPlanError(f"verification-plan manifest requires {key} strings")
    return tuple(cast(str, entry) for entry in entries)


def _acceptance_checks(manifest: Mapping[str, object]) -> tuple[VerificationCheck, ...]:
    acceptance = manifest.get("acceptance")
    if not isinstance(acceptance, list):
        raise VerificationPlanError("verification-plan manifest requires acceptance checks")
    checks: list[VerificationCheck] = []
    for item in cast(list[object], acceptance):
        if not isinstance(item, Mapping):
            raise VerificationPlanError("verification-plan acceptance check must be a table")
        check = cast(Mapping[str, object], item)
        identifier = _required_string(check, "id")
        argv = _string_list(check, "argv")
        checks.append(_manifest_check(identifier, argv))
    if len({check.id for check in checks}) != len(checks):
        raise VerificationPlanError(
            "verification-plan manifest acceptance check ids must be unique"
        )
    return tuple(checks)


def _manifest_check(identifier: str, argv: tuple[str, ...]) -> VerificationCheck:
    if identifier in _QUALITY_CHECKS:
        return VerificationCheck(identifier, argv, "required quality check", "quality")
    if identifier.endswith("-retained"):
        return VerificationCheck(identifier, argv, "manifest retained acceptance check", "retained")
    return VerificationCheck(identifier, argv, "manifest acceptance check", "manifest")


def _checks(
    manifest: Mapping[str, object], changed_paths: tuple[str, ...]
) -> tuple[VerificationCheck, ...]:
    checks = {check.id: check for check in _acceptance_checks(manifest)}
    for identifier, argv in _QUALITY_CHECKS.items():
        checks.setdefault(
            identifier,
            VerificationCheck(identifier, argv, "required quality check", "quality"),
        )
    if _CLI_PATH in changed_paths:
        for identifier, argv in _CLI_TOUCHED_CHECKS:
            checks[identifier] = VerificationCheck(
                identifier,
                argv,
                "cli.py touched; exact-output CLI contract must be retained",
                "touched-path",
            )
    for changed_path in changed_paths:
        for identifier, argv in _H14_TOUCHED_PATH_CHECKS.get(changed_path, ()):
            checks[identifier] = VerificationCheck(
                identifier,
                argv,
                "changed harness path requires deterministic coverage check",
                "touched-path",
            )
    return tuple(sorted(checks.values(), key=lambda check: check.id))


def _has_shared_rule(path: str) -> bool:
    return path in {_CLI_PATH, "docs/CHECK_PLAN.md"}


def _changed_paths(base_revision: str, head_revision: str) -> tuple[str, ...]:
    result = _git("diff", "--name-only", "--no-renames", "-z", base_revision, head_revision)
    if result.returncode != 0:
        raise VerificationPlanError("verification-plan could not inspect the Git diff")
    return tuple(sorted(path.decode("utf-8") for path in result.stdout.split(b"\0") if path))


def _git(*arguments: str) -> subprocess.CompletedProcess[bytes]:
    try:
        return subprocess.run(
            ["git", "--no-optional-locks", *arguments],
            capture_output=True,
            check=False,
            env=os.environ | {"GIT_OPTIONAL_LOCKS": "0"},
        )
    except OSError as error:
        raise VerificationPlanError("verification-plan could not run Git") from error


def _write_text(path: Path, text: str) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    except OSError as error:
        raise VerificationPlanError("verification-plan could not write output") from error
