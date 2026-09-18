from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import lockstep.engine as engine
import lockstep.peer_receipts as peer_receipts

ROOT = Path(__file__).resolve().parents[1]
GOVERNANCE_FILES = [
    ROOT / "governance" / "lockstep" / "reference_baseline.json",
    ROOT / "governance" / "lockstep" / "reference_criteria.json",
    ROOT / "governance" / "lockstep" / "contracts.json",
    ROOT / "governance" / "lockstep" / "dependencies.json",
    ROOT / "governance" / "lockstep" / "receipt.json",
    ROOT / "governance" / "lockstep" / "peer_receipts.json",
    ROOT / "governance" / "lockstep" / "deployment_boundary.json",
]


def _hashes() -> dict[str, str]:
    return {
        path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in GOVERNANCE_FILES
    }


class LockstepRecoveryTests(unittest.TestCase):
    def test_validation_is_restart_deterministic_and_read_only(self) -> None:
        before = _hashes()
        first = engine.validate_all()
        second = engine.validate_all()
        peer_first = peer_receipts.validate_peer_receipts()
        peer_second = peer_receipts.validate_peer_receipts()
        after = _hashes()
        self.assertEqual(first, second)
        self.assertEqual(peer_first, peer_second)
        self.assertEqual(before, after)

    def test_partial_receipt_crash_fails_closed_then_recovers(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            partial = Path(tmp) / "receipt.json"
            partial.write_text('{"schema_version":', encoding="utf-8")
            with (
                patch.object(engine, "RECEIPT_PATH", partial),
                self.assertRaises(engine.LockstepError),
            ):
                engine.validate_all()
        baseline, contracts, edges, receipt = engine.validate_all()
        self.assertEqual(receipt["generation"], baseline["generation"])
        self.assertTrue(contracts)
        self.assertTrue(edges)

    def test_stale_peer_receipt_fails_closed_then_recovers(self) -> None:
        source = json.loads(peer_receipts.PEER_RECEIPTS_PATH.read_text(encoding="utf-8"))
        source["generation"] += 1
        with tempfile.TemporaryDirectory() as tmp:
            stale = Path(tmp) / "peer_receipts.json"
            stale.write_text(json.dumps(source), encoding="utf-8")
            with (
                patch.object(peer_receipts, "PEER_RECEIPTS_PATH", stale),
                self.assertRaisesRegex(engine.LockstepError, "LOCKSTEP_DRIFT"),
            ):
                peer_receipts.validate_peer_receipts()
        self.assertEqual(peer_receipts.validate_peer_receipts()["status"], "PASS")

    def test_baseline_corruption_fails_closed_then_rollback_recovers(self) -> None:
        source = json.loads(engine.BASELINE_PATH.read_text(encoding="utf-8"))
        source["members"]["ovnis-pr"] = "0" * 40
        with tempfile.TemporaryDirectory() as tmp:
            corrupt = Path(tmp) / "reference_baseline.json"
            corrupt.write_text(json.dumps(source), encoding="utf-8")
            with (
                patch.object(engine, "BASELINE_PATH", corrupt),
                self.assertRaises(engine.LockstepError),
            ):
                engine.validate_all()
        self.assertEqual(engine.validate_all()[0]["generation"], 1)


if __name__ == "__main__":
    unittest.main()
