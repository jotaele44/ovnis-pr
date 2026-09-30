from __future__ import annotations

import copy
import unittest

from lockstep.engine import (
    LockstepError,
    compute_impact,
    normalize_event,
    semantic_schema_diff,
    validate_all,
    validate_receipt,
)

SHA_A = "1" * 40
SHA_B = "2" * 40


class EventNormalizationTests(unittest.TestCase):
    def test_pull_request_and_push_contexts_are_equivalent(self) -> None:
        self.assertEqual(normalize_event("pull_request", SHA_A, SHA_B), (SHA_A, SHA_B))
        self.assertEqual(normalize_event("push", SHA_A, SHA_B), (SHA_A, SHA_B))

    def test_zero_sha_fails_closed(self) -> None:
        with self.assertRaises(LockstepError):
            normalize_event("push", "0" * 40, SHA_B)

    def test_unknown_event_fails_closed(self) -> None:
        with self.assertRaises(LockstepError):
            normalize_event("schedule", SHA_A, SHA_B)


class GenerationTests(unittest.TestCase):
    def test_current_reference_generation_validates(self) -> None:
        baseline, contracts, _edges, receipt = validate_all()
        self.assertEqual(receipt["generation"], baseline["generation"])
        self.assertEqual(receipt["baseline_id"], baseline["baseline_id"])

    def test_stale_generation_is_detected(self) -> None:
        baseline, contracts, _edges, _receipt = validate_all()
        future = copy.deepcopy(baseline)
        future["generation"] += 1
        with self.assertRaisesRegex(LockstepError, "LOCKSTEP_DRIFT"):
            validate_receipt(future, contracts)

    def test_wrong_baseline_identity_is_detected(self) -> None:
        baseline, contracts, _edges, _receipt = validate_all()
        wrong = copy.deepcopy(baseline)
        wrong["baseline_id"] = "sha256:" + "0" * 64
        with self.assertRaisesRegex(LockstepError, "LOCKSTEP_DRIFT"):
            validate_receipt(wrong, contracts)


class SemanticSchemaDiffTests(unittest.TestCase):
    def test_optional_property_addition_is_compatible(self) -> None:
        before = {"type": "object", "properties": {"id": {"type": "string"}}, "required": ["id"]}
        after = {
            "type": "object",
            "properties": {"id": {"type": "string"}, "note": {"type": "string"}},
            "required": ["id"],
        }
        self.assertEqual(semantic_schema_diff(before, after)["classification"], "ADDITIVE_COMPATIBLE")

    def test_required_property_addition_is_breaking(self) -> None:
        before = {"type": "object", "properties": {"id": {"type": "string"}}, "required": ["id"]}
        after = {
            "type": "object",
            "properties": {"id": {"type": "string"}, "note": {"type": "string"}},
            "required": ["id", "note"],
        }
        self.assertEqual(semantic_schema_diff(before, after)["classification"], "BREAKING")

    def test_property_removal_is_breaking(self) -> None:
        before = {
            "type": "object",
            "properties": {"id": {"type": "string"}, "note": {"type": "string"}},
            "required": ["id"],
        }
        after = {"type": "object", "properties": {"id": {"type": "string"}}, "required": ["id"]}
        self.assertEqual(semantic_schema_diff(before, after)["classification"], "BREAKING")

    def test_type_mutation_is_breaking(self) -> None:
        before = {"type": "object", "properties": {"id": {"type": "string"}}}
        after = {"type": "object", "properties": {"id": {"type": "integer"}}}
        self.assertEqual(semantic_schema_diff(before, after)["classification"], "BREAKING")

    def test_enum_expansion_is_compatible(self) -> None:
        before = {"type": "object", "properties": {"state": {"type": "string", "enum": ["A"]}}}
        after = {"type": "object", "properties": {"state": {"type": "string", "enum": ["A", "B"]}}}
        self.assertEqual(semantic_schema_diff(before, after)["classification"], "ADDITIVE_COMPATIBLE")

    def test_enum_narrowing_is_breaking(self) -> None:
        before = {"type": "object", "properties": {"state": {"type": "string", "enum": ["A", "B"]}}}
        after = {"type": "object", "properties": {"state": {"type": "string", "enum": ["A"]}}}
        self.assertEqual(semantic_schema_diff(before, after)["classification"], "BREAKING")


class ImpactTests(unittest.TestCase):
    def setUp(self) -> None:
        _baseline, self.contracts, self.edges, _receipt = validate_all()

    def test_centinelas_signal_change_reaches_hub_transitively(self) -> None:
        impact = compute_impact(["scripts/ingest_centinelas_dispatch.py"], self.contracts, self.edges)
        self.assertEqual(impact["union"], ["centinelas-pr", "ovnis-pr", "thehub-pr"])
        self.assertIn("centinelas_ovnis_signal@1", impact["contracts"])

    def test_ovnis_schema_change_includes_reverse_and_forward_impact(self) -> None:
        impact = compute_impact(["data/schemas/case.schema.json"], self.contracts, self.edges)
        self.assertEqual(impact["union"], ["centinelas-pr", "ovnis-pr", "thehub-pr"])
        self.assertIn("ovnis_case_schema@1", impact["contracts"])

    def test_unrelated_documentation_has_no_federation_impact(self) -> None:
        impact = compute_impact(["docs/local-notes.md"], self.contracts, self.edges)
        self.assertEqual(impact["union"], [])

    def test_lockstep_control_plane_change_is_conservatively_transitive(self) -> None:
        impact = compute_impact(["governance/lockstep/contracts.json"], self.contracts, self.edges)
        self.assertEqual(impact["union"], ["centinelas-pr", "ovnis-pr", "thehub-pr"])


if __name__ == "__main__":
    unittest.main()
