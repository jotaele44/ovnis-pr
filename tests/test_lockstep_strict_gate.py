from __future__ import annotations

import unittest

from lockstep.engine import LockstepError
from lockstep.strict_gate import enforce_semantic_policy


def result(classification: str) -> dict:
    return {
        "semantic_diff": {
            "ovnis_case_schema@1": {
                "classification": classification,
                "paths": [],
            }
        }
    }


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
