from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "validate_dependency_planes", ROOT / "scripts" / "validate_dependency_planes.py"
)
assert SPEC and SPEC.loader
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)

RUNTIME = """jsonschema
prii-maintenance @ git+https://example.test/hub.git@abc#subdirectory=maintenance
prii-export-utils @ git+https://example.test/hub.git@abc#subdirectory=export
"""
RUNTIME_LOCK = """attrs==1
jsonschema==4
prii-maintenance @ git+https://example.test/hub.git@abc#subdirectory=maintenance
prii-export-utils @ git+https://example.test/hub.git@abc#subdirectory=export
referencing==1
"""
DEV = """-r requirements.txt
pytest
pytest-cov
"""
DEV_LOCK = RUNTIME_LOCK + "pytest==9\npytest-cov==7\ncoverage==7\n"
DESKTOP = """attrs==1
jsonschema==4
referencing==1
"""
COMMANDS = {
    "setup": "python -m pip install -r requirements-dev.lock",
    "runtime_setup": "python -m pip install -r requirements.lock",
    "test_suite": "python -m pytest -q",
}


def _write(
    root: Path,
    *,
    runtime=RUNTIME,
    runtime_lock=RUNTIME_LOCK,
    dev=DEV,
    dev_lock=DEV_LOCK,
    desktop=DESKTOP,
    commands=COMMANDS,
):
    (root / "requirements.txt").write_text(runtime, encoding="utf-8")
    (root / "requirements.lock").write_text(runtime_lock, encoding="utf-8")
    (root / "requirements-dev.txt").write_text(dev, encoding="utf-8")
    (root / "requirements-dev.lock").write_text(dev_lock, encoding="utf-8")
    (root / "constraints-desktop.txt").write_text(desktop, encoding="utf-8")
    (root / "federation.json").write_text(
        json.dumps({"hub_callable_commands": commands}), encoding="utf-8"
    )


def test_repository_dependency_planes_pass() -> None:
    summary = validator.validate(ROOT)
    assert summary["status"] == "PASS"
    assert summary["test_packages_in_runtime"] == 0
    assert summary["runtime_is_subset_of_development_lock"] is True
    assert summary["hub_setup_profile_bound"] is True
    assert summary["hub_runtime_profile_bound"] is True


def test_runtime_direct_test_dependency_fails(tmp_path: Path) -> None:
    _write(tmp_path, runtime=RUNTIME + "pytest\n")
    with pytest.raises(validator.DependencyPlaneError, match="leaked into runtime"):
        validator.validate(tmp_path)


def test_development_lock_must_conserve_runtime_closure(tmp_path: Path) -> None:
    _write(tmp_path, dev_lock="pytest==9\npytest-cov==7\n")
    with pytest.raises(validator.DependencyPlaneError, match="does not conserve"):
        validator.validate(tmp_path)


def test_desktop_constraints_cannot_acquire_test_packages(tmp_path: Path) -> None:
    _write(tmp_path, desktop=DESKTOP + "pytest==9\n")
    with pytest.raises(validator.DependencyPlaneError, match="non-runtime packages"):
        validator.validate(tmp_path)


def test_development_manifest_must_include_runtime_manifest(tmp_path: Path) -> None:
    _write(tmp_path, dev="pytest\npytest-cov\n")
    with pytest.raises(validator.DependencyPlaneError, match="must include"):
        validator.validate(tmp_path)


def test_hub_runtime_setup_cannot_install_development_lock(tmp_path: Path) -> None:
    commands = dict(COMMANDS)
    commands["runtime_setup"] = "python -m pip install -r requirements-dev.lock"
    _write(tmp_path, commands=commands)
    with pytest.raises(validator.DependencyPlaneError, match="only the runtime lock"):
        validator.validate(tmp_path)


def test_hub_setup_must_prepare_test_suite(tmp_path: Path) -> None:
    commands = dict(COMMANDS)
    commands["setup"] = "python -m pip install -r requirements.lock"
    _write(tmp_path, commands=commands)
    with pytest.raises(validator.DependencyPlaneError, match="development lock"):
        validator.validate(tmp_path)
