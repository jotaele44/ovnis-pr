#!/usr/bin/env python3
"""Fail-closed validation for Ovnis runtime, development, and desktop planes."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_REQUIREMENTS = "requirements.txt"
DEV_REQUIREMENTS = "requirements-dev.txt"
RUNTIME_LOCK = "requirements.lock"
DEV_LOCK = "requirements-dev.lock"
DESKTOP_CONSTRAINTS = "constraints-desktop.txt"
FEDERATION_MANIFEST = "federation.json"
TEST_ONLY = {"pytest", "pytest-cov"}
_REQUIREMENT_NAME = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)")


class DependencyPlaneError(RuntimeError):
    """Raised when dependency ownership or lock conservation fails."""


def _logical_lines(path: Path) -> list[str]:
    if not path.is_file():
        raise DependencyPlaneError(f"required dependency file is missing: {path.name}")
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def _names(lines: Iterable[str]) -> set[str]:
    names: set[str] = set()
    for line in lines:
        if line.startswith(("-r ", "--requirement ", "-c ", "--constraint ")):
            continue
        match = _REQUIREMENT_NAME.match(line)
        if not match:
            raise DependencyPlaneError(f"unrecognized requirement record: {line!r}")
        names.add(match.group(1).lower().replace("_", "-"))
    return names


def _commands(root: Path) -> dict[str, str]:
    path = root / FEDERATION_MANIFEST
    if not path.is_file():
        raise DependencyPlaneError(f"required dependency file is missing: {path.name}")
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DependencyPlaneError(f"federation.json is not valid JSON: {exc}") from exc
    commands = manifest.get("hub_callable_commands")
    if not isinstance(commands, dict) or not all(
        isinstance(key, str) and isinstance(value, str) for key, value in commands.items()
    ):
        raise DependencyPlaneError("federation.json hub_callable_commands must be string pairs")
    return commands


def validate(root: Path = REPO_ROOT) -> dict[str, object]:
    runtime_direct_lines = _logical_lines(root / RUNTIME_REQUIREMENTS)
    dev_direct_lines = _logical_lines(root / DEV_REQUIREMENTS)
    runtime_lock_lines = _logical_lines(root / RUNTIME_LOCK)
    dev_lock_lines = _logical_lines(root / DEV_LOCK)
    desktop_lines = _logical_lines(root / DESKTOP_CONSTRAINTS)

    includes_runtime = any(
        line in {"-r requirements.txt", "--requirement requirements.txt"}
        for line in dev_direct_lines
    )
    if not includes_runtime:
        raise DependencyPlaneError("development requirements must include requirements.txt")

    runtime_direct = _names(runtime_direct_lines)
    dev_direct = _names(dev_direct_lines)
    runtime_locked = _names(runtime_lock_lines)
    dev_locked = _names(dev_lock_lines)
    desktop_constrained = _names(desktop_lines)

    leaked_direct = sorted(runtime_direct & TEST_ONLY)
    leaked_locked = sorted(runtime_locked & TEST_ONLY)
    if leaked_direct or leaked_locked:
        raise DependencyPlaneError(
            f"test tooling leaked into runtime plane: direct={leaked_direct} locked={leaked_locked}"
        )
    missing_test_tools = sorted(TEST_ONLY - dev_direct)
    if missing_test_tools:
        raise DependencyPlaneError(
            f"development requirements omit test tools: {missing_test_tools}"
        )

    missing_runtime_locks = sorted(runtime_direct - runtime_locked)
    if missing_runtime_locks:
        raise DependencyPlaneError(
            f"runtime direct requirements missing from runtime lock: {missing_runtime_locks}"
        )
    missing_dev_runtime = sorted(runtime_locked - dev_locked)
    if missing_dev_runtime:
        raise DependencyPlaneError(
            f"development lock does not conserve runtime closure: {missing_dev_runtime}"
        )
    missing_dev_tools = sorted(TEST_ONLY - dev_locked)
    if missing_dev_tools:
        raise DependencyPlaneError(
            f"development lock omits declared test tools: {missing_dev_tools}"
        )
    foreign_desktop = sorted(desktop_constrained - runtime_locked)
    if foreign_desktop:
        raise DependencyPlaneError(
            f"desktop constraints contain non-runtime packages: {foreign_desktop}"
        )

    commands = _commands(root)
    setup = commands.get("setup", "")
    runtime_setup = commands.get("runtime_setup", "")
    test_suite = commands.get("test_suite", "")
    if DEV_LOCK not in setup:
        raise DependencyPlaneError(
            f"Hub setup must install the development lock before tests: {DEV_LOCK}"
        )
    if RUNTIME_LOCK not in runtime_setup or DEV_LOCK in runtime_setup:
        raise DependencyPlaneError(
            f"Hub runtime_setup must install only the runtime lock: {RUNTIME_LOCK}"
        )
    if "pytest" not in test_suite:
        raise DependencyPlaneError("Hub test_suite must execute the declared test runner")

    summary: dict[str, object] = {
        "status": "PASS",
        "runtime_direct_count": len(runtime_direct),
        "runtime_locked_count": len(runtime_locked),
        "development_direct_count": len(dev_direct),
        "development_locked_count": len(dev_locked),
        "desktop_constraint_count": len(desktop_constrained),
        "runtime_is_subset_of_development_lock": True,
        "test_packages_in_runtime": 0,
        "hub_setup_profile_bound": True,
        "hub_runtime_profile_bound": True,
    }
    return summary


def main() -> int:
    try:
        summary = validate()
    except DependencyPlaneError as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, sort_keys=True))
        return 1
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
