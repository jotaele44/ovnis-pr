from __future__ import annotations

import ast
import json
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SIGNATURES = ROOT / "governance" / "lockstep" / "signatures"


def _load_signature(name: str) -> dict[str, Any]:
    return json.loads((SIGNATURES / name).read_text(encoding="utf-8"))


def _tree(path: str) -> ast.Module:
    return ast.parse((ROOT / path).read_text(encoding="utf-8"), filename=path)


def _module_literal(tree: ast.Module, name: str) -> Any:
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == name for target in node.targets
        ):
            return ast.literal_eval(node.value)
    raise AssertionError(f"module literal {name!r} not found")


def _function(tree: ast.Module, name: str) -> ast.FunctionDef:
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"function {name!r} not found")


def _dict_keys(node: ast.Dict) -> set[str]:
    keys: set[str] = set()
    for key in node.keys:
        if isinstance(key, ast.Constant) and isinstance(key.value, str):
            keys.add(key.value)
    return keys


class ExportContractSignatureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.signature = _load_signature("federation_export_manifest.contract.json")
        self.tree = _tree("scripts/federation_export.py")

    def test_module_contract_identity_matches_signature(self) -> None:
        self.assertEqual(_module_literal(self.tree, "PRODUCER"), self.signature["producer"])
        self.assertEqual(
            _module_literal(self.tree, "CONTRACT_VERSION"), self.signature["contract_version"]
        )
        self.assertEqual(_module_literal(self.tree, "STREAM_SCHEMA"), self.signature["streams"])

    def test_manifest_shape_matches_signature(self) -> None:
        write_package = _function(self.tree, "write_package")
        manifest_dict: ast.Dict | None = None
        for node in ast.walk(write_package):
            if (
                isinstance(node, ast.Assign)
                and any(
                    isinstance(target, ast.Name) and target.id == "manifest"
                    for target in node.targets
                )
                and isinstance(node.value, ast.Dict)
            ):
                manifest_dict = node.value
                break
        self.assertIsNotNone(manifest_dict)
        assert manifest_dict is not None
        self.assertEqual(_dict_keys(manifest_dict), set(self.signature["manifest_keys"]))

        federation_dict: ast.Dict | None = None
        for key, value in zip(manifest_dict.keys, manifest_dict.values, strict=True):
            if isinstance(key, ast.Constant) and key.value == "federation" and isinstance(value, ast.Dict):
                federation_dict = value
                break
        self.assertIsNotNone(federation_dict)
        assert federation_dict is not None
        federation_keys = _dict_keys(federation_dict)
        self.assertEqual(federation_keys, {"producer_repo", "hub_parent"})
        hub_parent_value = None
        for key, value in zip(federation_dict.keys, federation_dict.values, strict=True):
            if isinstance(key, ast.Constant) and key.value == "hub_parent":
                hub_parent_value = ast.literal_eval(value)
        self.assertEqual(hub_parent_value, self.signature["hub_parent"])

    def test_file_entry_shape_matches_signature(self) -> None:
        write_package = _function(self.tree, "write_package")
        required = set(self.signature["file_entry_required"])
        candidates = [
            _dict_keys(node)
            for node in ast.walk(write_package)
            if isinstance(node, ast.Dict)
        ]
        self.assertTrue(any(required <= keys for keys in candidates))

    def test_export_modes_match_signature(self) -> None:
        main = _function(self.tree, "main")
        choices: set[str] | None = None
        for node in ast.walk(main):
            if not isinstance(node, ast.Call):
                continue
            for keyword in node.keywords:
                if keyword.arg == "choices":
                    value = ast.literal_eval(keyword.value)
                    if isinstance(value, list):
                        choices = set(value)
        self.assertEqual(choices, set(self.signature["modes"]))


class CentinelasEventSignatureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.signature = _load_signature("centinelas_ovnis_signal.contract.json")
        self.tree = _tree("scripts/ingest_centinelas_dispatch.py")

    def test_candidate_output_fields_match_signature(self) -> None:
        func = _function(self.tree, "signal_to_candidate_row")
        returns = [node for node in ast.walk(func) if isinstance(node, ast.Return)]
        dict_returns = [node.value for node in returns if isinstance(node.value, ast.Dict)]
        self.assertEqual(len(dict_returns), 1)
        self.assertEqual(_dict_keys(dict_returns[0]), set(self.signature["candidate_fields"]))

    def test_dispatch_envelope_keys_match_signature(self) -> None:
        func = _function(self.tree, "extract_signals")
        string_literals = {
            node.value
            for node in ast.walk(func)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
        }
        self.assertTrue(set(self.signature["envelope_keys"]) <= string_literals)

    def test_quarantine_required_is_a_candidate_subset(self) -> None:
        self.assertTrue(
            set(self.signature["quarantine_required"]) <= set(self.signature["candidate_fields"])
        )


if __name__ == "__main__":
    unittest.main()
