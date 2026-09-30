"""Strict policy layer for the OVNIS FEDERATION LOCKSTEP reference gate."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from lockstep.engine import RECEIPT_PATH, LockstepError, gate, load_json

PASS_CLASSES = {
    "NO_CHANGE",
    "INTERNAL",
    "ADDITIVE_COMPATIBLE",
    "DEPRECATED_COMPATIBLE",
}


def enforce_semantic_policy(result: dict[str, Any], disposition: str) -> dict[str, Any]:
    violations: list[str] = []
    for contract_id, contract_result in result.get("semantic_diff", {}).items():
        classification = contract_result.get("classification")
        if classification in PASS_CLASSES:
            continue
        if classification == "MIGRATION_REQUIRED" and disposition == "MIGRATION_STAGED":
            continue
        if classification == "BREAKING":
            violations.append(f"{contract_id}: BREAKING contract change")
        elif classification == "MIGRATION_REQUIRED":
            violations.append(
                f"{contract_id}: MIGRATION_REQUIRED but receipt disposition is {disposition!r}"
            )
        else:
            violations.append(f"{contract_id}: unsupported semantic classification {classification!r}")
    if violations:
        raise LockstepError("semantic compatibility blocked: " + "; ".join(violations))
    return result


def strict_gate(base_sha: str, head_sha: str, event_name: str) -> dict[str, Any]:
    result = gate(base_sha, head_sha, event_name)
    receipt = load_json(RECEIPT_PATH)
    disposition = receipt.get("disposition") if isinstance(receipt, dict) else None
    return enforce_semantic_policy(result, disposition)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m lockstep.strict_gate")
    parser.add_argument("--event-name", required=True)
    parser.add_argument("--base-sha", required=True)
    parser.add_argument("--head-sha", required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        result = strict_gate(args.base_sha, args.head_sha, args.event_name)
    except LockstepError as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, sort_keys=True))
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
