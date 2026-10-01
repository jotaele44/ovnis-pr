from __future__ import annotations

import unittest
from unittest import mock

from lockstep import engine
from lockstep.engine import LockstepError
from lockstep.strict_gate import enforce_semantic_policy

RECEIPT = "governance/lockstep/receipt.json"
DECLARED = ["centinelas-pr", "ovnis-pr", "thehub-pr"]


def result(classification: str) -> dict:
    return {
        "semantic_diff": {
            "ovnis_case_schema@1": {
                "classification": classification,
                "paths": [],
            }
        }
    }


def run_gate(changed: list[str], union: list[str], contracts: list[str]) -> dict:
    baseline = {"generation": 2, "baseline_id": "sha256:" + "0" * 64}
    receipt = {"impact_set": DECLARED}
    with (
        mock.patch.object(engine, "normalize_event", side_effect=lambda event, base, head: (base, head)),
        mock.patch.object(engine, "validate_all", return_value=(baseline, {}, [], receipt)),
        mock.patch.object(engine, "changed_paths", return_value=changed),
        mock.patch.object(engine, "compute_impact", return_value={"contracts": contracts, "union": union}),
        mock.patch.object(engine, "classify_changed_contracts", return_value={}),
    ):
        return engine.gate("a" * 40, "b" * 40, "pull_request")


class ImpactSetDeclarationTests(unittest.TestCase):
    def test_ungoverned_change_passes_under_a_standing_declaration(self) -> None:
        self.assertEqual(run_gate([".github/workflows/pip-audit.yml"], [], [])["status"], "PASS")

    def test_receipt_update_must_match_the_computed_impact(self) -> None:
        with self.assertRaisesRegex(LockstepError, "LOCKSTEP_IMPACT_SET mismatch"):
            run_gate([RECEIPT, "scripts/federation_export.py"], ["ovnis-pr", "thehub-pr"], ["federation_export_manifest@1"])

    def test_receipt_update_matching_the_computed_impact_passes(self) -> None:
        result = run_gate([RECEIPT, "scripts/federation_export.py"], DECLARED, ["federation_export_manifest@1"])
        self.assertEqual(result["status"], "PASS")

    def test_governed_change_still_requires_a_receipt_update(self) -> None:
        with self.assertRaisesRegex(LockstepError, "without a Lockstep receipt update"):
            run_gate(["scripts/federation_export.py"], DECLARED, ["federation_export_manifest@1"])


class StrictSemanticPolicyTests(unittest.TestCase):
    def test_breaking_change_is_blocked(self) -> None:
        with self.assertRaisesRegex(LockstepError, "BREAKING"):
            enforce_semantic_policy(result("BREAKING"), "UPDATED")

    def test_migration_required_is_blocked_without_staged_migration(self) -> None:
        with self.assertRaisesRegex(LockstepError, "MIGRATION_REQUIRED"):
            enforce_semantic_policy(result("MIGRATION_REQUIRED"), "UPDATED")

    def test_migration_required_passes_with_staged_migration(self) -> None:
        self.assertEqual(
            enforce_semantic_policy(result("MIGRATION_REQUIRED"), "MIGRATION_STAGED")["semantic_diff"]["ovnis_case_schema@1"]["classification"],
            "MIGRATION_REQUIRED",
        )

    def test_additive_change_passes(self) -> None:
        self.assertEqual(
            enforce_semantic_policy(result("ADDITIVE_COMPATIBLE"), "UPDATED")["semantic_diff"]["ovnis_case_schema@1"]["classification"],
            "ADDITIVE_COMPATIBLE",
        )

    def test_unknown_change_is_blocked(self) -> None:
        with self.assertRaisesRegex(LockstepError, "unsupported semantic classification"):
            enforce_semantic_policy(result("UNKNOWN"), "UPDATED")


if __name__ == "__main__":
    unittest.main()
