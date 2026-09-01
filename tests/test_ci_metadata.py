"""Local validation for CI, HACS, and repository package metadata."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, cast

import yaml
from packaging.requirements import Requirement

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"


def load_yaml(path: Path) -> dict[str, Any]:
    return cast("dict[str, Any]", yaml.safe_load(path.read_text(encoding="utf-8")))


def load_json(path: Path) -> dict[str, Any]:
    return cast("dict[str, Any]", json.loads(path.read_text(encoding="utf-8")))


def workflow_on(workflow: dict[str, Any]) -> dict[str, Any]:
    raw_workflow = cast("dict[Any, Any]", workflow)
    on_value = raw_workflow["on"] if "on" in raw_workflow else raw_workflow[True]
    return cast("dict[str, Any]", on_value)


def run_steps(workflow: dict[str, Any], job_name: str) -> list[dict[str, Any]]:
    jobs = cast("dict[str, Any]", workflow["jobs"])
    job = cast("dict[str, Any]", jobs[job_name])
    return cast("list[dict[str, Any]]", job["steps"])


def uses_values(steps: list[dict[str, Any]]) -> list[str]:
    return [cast("str", step["uses"]) for step in steps if "uses" in step]


def run_values(steps: list[dict[str, Any]]) -> list[str]:
    return [cast("str", step["run"]) for step in steps if "run" in step]


def test_workflow_yaml_files_parse_with_github_on_key() -> None:
    workflows = {path.name: load_yaml(path) for path in WORKFLOWS.glob("*.yml")}

    assert set(workflows) == {"tests.yml", "validate.yml"}
    for workflow in workflows.values():
        assert isinstance(workflow_on(workflow), dict)


def test_tests_workflow_runs_required_ci_gates_without_continue_on_error() -> None:
    workflow = load_yaml(WORKFLOWS / "tests.yml")
    triggers = workflow_on(workflow)
    steps = run_steps(workflow, "tests")

    assert set(triggers) == {"push", "pull_request", "workflow_dispatch"}
    assert workflow["permissions"] == {"contents": "read"}
    assert workflow["jobs"]["tests"]["runs-on"] == "ubuntu-latest"
    assert uses_values(steps) == [
        "actions/checkout@v7",
        "actions/setup-python@v7",
        "actions/setup-node@v7",
    ]
    assert cast("dict[str, Any]", steps[1]["with"]) == {
        "python-version": "3.14",
        "cache": "pip",
        "cache-dependency-path": "requirements_test.txt",
    }
    assert cast("dict[str, Any]", steps[3]["with"]) == {"node-version": "24", "cache": "npm"}
    assert run_values(steps) == [
        "python -m pip install -r requirements_test.txt",
        "npm ci",
        "npm run test:login-schema",
        "npm audit --audit-level=moderate",
        "python -m ruff format --check .",
        "python -m ruff check .",
        "python -m mypy",
        "python -m pytest tests/test_ci_metadata.py",
        (
            "python -m pytest --cov=custom_components.kepco_on --cov-report=term-missing "
            "--cov-fail-under=95"
        ),
    ]
    assert "continue-on-error" not in json.dumps(workflow)


def test_validate_workflow_runs_hacs_and_hassfest_required_checks() -> None:
    workflow = load_yaml(WORKFLOWS / "validate.yml")
    triggers = workflow_on(workflow)
    jobs = cast("dict[str, Any]", workflow["jobs"])

    assert set(triggers) == {"push", "pull_request", "workflow_dispatch", "schedule"}
    assert triggers["schedule"] == [{"cron": "17 3 * * 0"}]
    assert workflow["permissions"] == {"contents": "read"}
    assert set(jobs) == {"hacs", "hassfest"}
    assert uses_values(run_steps(workflow, "hacs")) == ["actions/checkout@v7", "hacs/action@main"]
    assert cast("dict[str, Any]", run_steps(workflow, "hacs")[1]["with"]) == {
        "category": "integration"
    }
    assert uses_values(run_steps(workflow, "hassfest")) == [
        "actions/checkout@v7",
        "home-assistant/actions/hassfest@master",
    ]
    assert "continue-on-error" not in json.dumps(workflow)


def test_release_metadata_versions_and_runtime_dependencies_are_valid() -> None:
    manifest = load_json(ROOT / "custom_components" / "kepco_on" / "manifest.json")
    hacs = load_json(ROOT / "hacs.json")
    package = load_json(ROOT / "package.json")

    assert manifest["version"] == "0.1.0"
    assert manifest["requirements"] == []
    assert hacs["homeassistant"] == "2026.8.3"
    assert package["private"] is True
    assert "dependencies" not in package
    assert package["devDependencies"] == {"playwright": "1.62.1"}


def test_test_requirements_include_yaml_parser_for_local_workflow_validation() -> None:
    requirements = [
        Requirement(line)
        for line in (ROOT / "requirements_test.txt").read_text(encoding="utf-8").splitlines()
        if line and not line.startswith("#")
    ]

    assert {requirement.name for requirement in requirements} >= {"PyYAML", "pytest-cov"}


def test_coverage_config_keeps_95_branch_gate_and_only_excludes_typing_surfaces() -> None:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert "branch = true" in pyproject
    assert "fail_under = 95" in pyproject
    assert "class .*\\\\(Protocol\\\\):" in pyproject
    assert "TYPE_CHECKING" in pyproject
    assert "pragma: no cover" not in pyproject


def test_repository_tracks_no_raw_capture_or_secret_artifacts() -> None:
    forbidden_suffixes = (".har", ".jsonl", ".trace.zip")
    forbidden_names = {"secrets.yaml"}
    raw_session_prefixes = ("session", "cookies", "login-schema")
    tracked = subprocess.run(
        ["git", "ls-files"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()

    for relative in tracked:
        path = Path(relative)
        assert path.name not in forbidden_names
        assert not relative.endswith(forbidden_suffixes)
        if path.parts[:2] == ("tests", "fixtures"):
            continue
        if path.suffix in {".json", ".zip"}:
            assert not any(path.name.lower().startswith(prefix) for prefix in raw_session_prefixes)
