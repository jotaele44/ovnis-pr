from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOUNDARY = ROOT / "governance" / "lockstep" / "deployment_boundary.json"
BASELINE = ROOT / "governance" / "lockstep" / "reference_baseline.json"


class DeploymentBoundaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.boundary = json.loads(BOUNDARY.read_text(encoding="utf-8"))
        self.baseline = json.loads(BASELINE.read_text(encoding="utf-8"))

    def test_production_is_bound_to_frozen_ovnis_source(self) -> None:
        production = self.boundary["production"]
        self.assertEqual(production["git_repository"], "jotaele44/ovnis-pr")
        self.assertEqual(production["frozen_git_source_sha"], self.baseline["members"]["ovnis-pr"])
        self.assertEqual(production["deployment_state"], "DEPLOYED_NATIVE_MOBILE")

    def test_reference_is_explicitly_not_deployed(self) -> None:
        reference = self.boundary["lockstep_reference"]
        self.assertEqual(reference["git_branch"], "lockstep-reference-v1")
        self.assertEqual(reference["baseline_generation"], self.baseline["generation"])
        self.assertEqual(reference["baseline_id"], self.baseline["baseline_id"])
        self.assertEqual(reference["deployment_state"], "NOT_DEPLOYED")
        self.assertFalse(reference["production_authority"])
        self.assertFalse(reference["deployment_evidence_eligible"])
        self.assertTrue(reference["promotion_required"])

    def test_boundary_invariants_are_fail_closed(self) -> None:
        invariants = self.boundary["invariants"]
        self.assertTrue(invariants)
        self.assertTrue(all(value is True for value in invariants.values()))

    def test_application_open_residue_is_preserved(self) -> None:
        production = self.boundary["production"]
        self.assertEqual(production["application_certification_state"], "OPEN")
        self.assertEqual(
            set(production["application_unresolved"]),
            {"native-package", "physical-device-verification"},
        )


if __name__ == "__main__":
    unittest.main()
