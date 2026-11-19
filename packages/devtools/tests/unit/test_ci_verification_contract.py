"""CI verification contract regression.

The shard plan in `scripts/verify.sh` partitions the complete pytest collection
that `testpaths` in `pyproject.toml` declares. Every node ID runs in exactly one
shard, and the smoke selection only overlaps shards on purpose.

The CI matrix in `.github/workflows/ci.yml` must match that plan. The aggregate
`verify` result must fail closed when a required job is missing, red, cancelled,
skipped, or unknown.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import cast

REPO_ROOT = Path(__file__).resolve().parents[4]
VERIFY_SCRIPT = REPO_ROOT / "scripts" / "verify.sh"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"
COLLECTION_ARGUMENTS = (
    "-o",
    "addopts=",
    "--collect-only",
    "--import-mode=importlib",
    "-q",
    "-p",
    "no:cacheprovider",
)
# pytest arguments that would change the selection and let a shard stay green
# while skipping tests that earlier jobs ran.
FORBIDDEN_SELECTION_ARGUMENTS = (
    "-k",
    "-m",
    "--ignore",
    "--ignore-glob",
    "--deselect",
    "--last-failed",
    "--failed-first",
    "--lf",
    "--ff",
    "--stepwise",
    "--sw",
    "--sw-skip",
    "--stepwise-skip",
    "--collect-only",
)
PDF_TOOL_PACKAGES = ("packages/adapters/tests", "packages/pipelines/tests")
_COLLECTION_CACHE: dict[tuple[str, ...], frozenset[str]] = {}

type JsonObject = dict[str, object]


def _run(argv: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, cwd=REPO_ROOT, capture_output=True, text=True, check=False)


def _verify(*arguments: str) -> subprocess.CompletedProcess[str]:
    return _run(["bash", str(VERIFY_SCRIPT), *arguments])


def _collect_node_ids(*paths: str) -> frozenset[str]:
    key = tuple(paths)
    cached = _COLLECTION_CACHE.get(key)
    if cached is not None:
        return cached

    completed = _run([sys.executable, "-m", "pytest", *COLLECTION_ARGUMENTS, *paths])
    assert completed.returncode == 0, completed.stderr
    node_ids = frozenset(line.strip() for line in completed.stdout.splitlines() if "::" in line)
    assert node_ids, f"pytest collected no node IDs for {paths or ('testpaths',)}"
    _COLLECTION_CACHE[key] = node_ids
    return node_ids


def _shard_plan() -> JsonObject:
    completed = _verify("shard-plan")
    assert completed.returncode == 0, completed.stderr
    parsed: object = json.loads(completed.stdout)
    assert isinstance(parsed, dict)
    return cast(JsonObject, parsed)


def _plan_entry(plan: JsonObject, key: str) -> JsonObject:
    value = plan[key]
    assert isinstance(value, dict), f"{key} must be a plan object"
    return cast(JsonObject, value)


def _plan_shards(plan: JsonObject) -> list[JsonObject]:
    value = plan["shards"]
    assert isinstance(value, list), "shards must be a list"
    shards: list[JsonObject] = []
    for entry in cast(list[object], value):
        assert isinstance(entry, dict), "each shard must be a plan object"
        shards.append(cast(JsonObject, entry))
    return shards


def _string_list(entry: JsonObject, key: str) -> list[str]:
    value = entry[key]
    assert isinstance(value, list) and value, f"{key} must be a non-empty list"
    items: list[str] = []
    for item in cast(list[object], value):
        assert isinstance(item, str) and item, f"{key} entries must be strings"
        items.append(item)
    return items


def _string(entry: JsonObject, key: str) -> str:
    value = entry[key]
    assert isinstance(value, str) and value, f"{key} must be a non-empty string"
    return value


def _shard_paths(shard: JsonObject) -> list[str]:
    return _string_list(shard, "paths")


def _shard_excludes(shard: JsonObject) -> list[str]:
    value = shard["excludes"]
    assert isinstance(value, list), "excludes must be a list"
    excludes: list[str] = []
    for item in cast(list[object], value):
        assert isinstance(item, str) and item, "excludes entries must be strings"
        excludes.append(item)
    return excludes


def _selection_arguments(shard: JsonObject) -> list[str]:
    return [
        *_shard_paths(shard),
        *(f"--ignore={path}" for path in _shard_excludes(shard)),
    ]


def _shard_arguments(shard: JsonObject) -> list[str]:
    return _string_list(shard, "pytest_arguments")


def _is_forbidden_selection_argument(argument: str) -> bool:
    for flag in FORBIDDEN_SELECTION_ARGUMENTS:
        if argument == flag or argument.startswith(f"{flag}="):
            return True
        if len(flag) == 2 and argument.startswith(flag):
            return True
    return False


def _job_block(workflow: str, job: str) -> str:
    marker = f"\n  {job}:\n"
    start = workflow.find(marker)
    assert start != -1, f"workflow must declare the {job} job"
    body = workflow[start + len(marker) :]
    next_job = re.search(r"\n  [a-z_]+:\n", body)
    return body if next_job is None else body[: next_job.start()]


def _matrix_shard_names(workflow: str) -> list[str]:
    matches = re.findall(r"^\s+shard: \[([^\]]*)\]$", workflow, flags=re.MULTILINE)
    assert len(matches) == 1, "workflow must declare exactly one shard matrix list"
    names = [name.strip() for name in matches[0].split(",")]
    assert all(names), "the shard matrix list must contain names"
    return names


def test_shard_plan_covers_the_complete_pytest_collection_exactly_once() -> None:
    plan = _shard_plan()
    assert plan["schema_version"] == 1

    shards = _plan_shards(plan)
    assert len(shards) >= 2, "the full gate must run at least two shards"
    names = [_string(shard, "name") for shard in shards]
    assert len(set(names)) == len(names), "shard names must be unique"

    baseline = _collect_node_ids()
    covered: set[str] = set()

    for shard in shards:
        collected = _collect_node_ids(*_selection_arguments(shard))
        repeated = covered.intersection(collected)
        assert not repeated, (
            f"shard {names} repeats node IDs that another shard already collects: "
            f"{sorted(repeated)[:3]}"
        )
        covered.update(collected)

    missing = baseline.difference(covered)
    unexpected = covered.difference(baseline)
    assert not missing, f"shards omit {len(missing)} collected node IDs: {sorted(missing)[:3]}"
    assert not unexpected, (
        f"shards collect {len(unexpected)} node IDs outside testpaths: {sorted(unexpected)[:3]}"
    )

    for shard in shards:
        for excluded in _shard_excludes(shard):
            owners = [_string(other, "name") for other in shards if excluded in _shard_paths(other)]
            assert len(owners) == 1, (
                f"{excluded} must be selected by exactly one other shard; found {owners}"
            )


def test_shard_arguments_add_no_selection_filter() -> None:
    plan = _shard_plan()
    entries = [_plan_entry(plan, "smoke"), *_plan_shards(plan)]

    for entry in entries:
        name = _string(entry, "name") if "name" in entry else "smoke"
        expected = _selection_arguments(entry) if "excludes" in entry else _shard_paths(entry)
        arguments = _shard_arguments(entry)

        assert arguments[-len(expected) :] == expected, (
            f"{name} must pass the declared selection unchanged and last"
        )
        for argument in arguments[: -len(expected)]:
            assert not _is_forbidden_selection_argument(argument), (
                f"{name} must not narrow the selection with {argument}"
            )


def test_smoke_selection_is_a_tool_free_subset_of_the_baseline() -> None:
    plan = _shard_plan()
    smoke = _plan_entry(plan, "smoke")
    smoke_paths = _shard_paths(smoke)

    baseline = _collect_node_ids()
    visited = _collect_node_ids(*smoke_paths)
    assert visited.issubset(baseline), "smoke must select tests from the baseline collection"

    for smoke_path in smoke_paths:
        for pdf_package in PDF_TOOL_PACKAGES:
            assert not (smoke_path == pdf_package or smoke_path.startswith(f"{pdf_package}/")), (
                f"smoke path {smoke_path} needs PDF tooling; the fast job installs none"
            )

    shard_paths = [path for shard in _plan_shards(plan) for path in _shard_paths(shard)]
    for smoke_path in smoke_paths:
        assert any(
            smoke_path == shard_path or smoke_path.startswith(f"{shard_path}/")
            for shard_path in shard_paths
        ), f"smoke path {smoke_path} must overlap a shard"


def test_ci_matrix_and_aggregate_gate_match_the_shard_plan() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    plan_names = [_string(shard, "name") for shard in _plan_shards(_shard_plan())]

    assert _matrix_shard_names(workflow) == plan_names, (
        "the CI shard matrix must list exactly the planned shards"
    )

    fast_job = _job_block(workflow, "fast")
    assert "./scripts/verify.sh fast" in fast_job
    assert "apt-get" not in fast_job, "the fast job must not install PDF tools"

    shard_job = _job_block(workflow, "shard")
    assert './scripts/verify.sh shard "${{ matrix.shard }}"' in shard_job
    assert "steps.shard_plan.outputs.needs_pdf_tools == 'true'" in shard_job, (
        "the workflow installs PDF tools only when the shard plan declares them"
    )

    aggregate_job = _job_block(workflow, "verify")
    assert "name: verify" in aggregate_job, "the aggregate result keeps its stable name"
    assert "if: always()" in aggregate_job
    assert "needs: [fast, shard]" in aggregate_job
    assert "./scripts/verify.sh aggregate \\" in aggregate_job
    assert '"fast=${{ needs.fast.result }}"' in aggregate_job
    assert '"shard=${{ needs.shard.result }}"' in aggregate_job


def test_aggregate_gate_fails_closed() -> None:
    cases = (
        (("fast=success", "shard=success"), 0),
        (("fast=failure", "shard=success"), 1),
        (("fast=success", "shard=cancelled"), 1),
        (("fast=success", "shard=skipped"), 1),
        (("fast=success", "shard="), 1),
        (("fast=", "shard=success"), 1),
        (("fast=success",), 2),
    )

    for arguments, expected in cases:
        completed = _verify("aggregate", *arguments)
        assert completed.returncode == expected, (
            f"aggregate returned {completed.returncode} for {arguments}: {completed.stderr}"
        )
