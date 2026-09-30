"""Validate bound affected-repository receipts for the OVNIS Lockstep reference."""

from __future__ import annotations

import json

from lockstep.engine import (
    DISPOSITIONS,
    LOCKSTEP_DIR,
    LockstepError,
    load_json,
    validate_all,
    validate_sha,
)

PEER_RECEIPTS_PATH = LOCKSTEP_DIR / "peer_receipts.json"


def validate_peer_receipts() -> dict[str, object]:
    baseline, contracts, _edges, receipt = validate_all()
    bindings = load_json(PEER_RECEIPTS_PATH)
    if not isinstance(bindings, dict):
        raise LockstepError("peer receipt bindings must be an object")
    if bindings.get("schema_version") != "federation_lockstep_peer_receipt_bindings_v1":
        raise LockstepError("unsupported peer receipt bindings schema")
    if bindings.get("generation") != baseline["generation"]:
        raise LockstepError("LOCKSTEP_DRIFT: peer receipt generation is stale")
    if bindings.get("baseline_id") != baseline["baseline_id"]:
        raise LockstepError("LOCKSTEP_DRIFT: peer receipt baseline_id mismatch")

    impact_set = set(receipt.get("impact_set") or [])
    expected_peers = impact_set - {receipt["repo"]}
    rows = bindings.get("receipts")
    if not isinstance(rows, list):
        raise LockstepError("peer receipt bindings.receipts must be a list")

    seen: set[str] = set()
    for index, raw in enumerate(rows):
        if not isinstance(raw, dict):
            raise LockstepError(f"peer receipt binding {index} must be an object")
        repo = raw.get("repo")
        if repo not in expected_peers:
            raise LockstepError(f"unexpected peer receipt repo: {repo!r}")
        if repo in seen:
            raise LockstepError(f"duplicate peer receipt binding: {repo}")
        seen.add(repo)
        validate_sha(raw.get("receipt_commit_sha"), f"peer_receipts.{repo}.receipt_commit_sha")
        validate_sha(raw.get("receipt_blob_sha"), f"peer_receipts.{repo}.receipt_blob_sha")
        if not isinstance(raw.get("remote_branch"), str) or not raw["remote_branch"]:
            raise LockstepError(f"peer receipt {repo} missing remote_branch")
        if raw.get("remote_path") != ".federation/lockstep-receipt.json":
            raise LockstepError(f"peer receipt {repo} has unexpected remote_path")

        payload = raw.get("payload")
        if not isinstance(payload, dict):
            raise LockstepError(f"peer receipt {repo} payload must be an object")
        if payload.get("schema_version") != "federation_lockstep_peer_receipt_v1":
            raise LockstepError(f"peer receipt {repo} has unsupported payload schema")
        if payload.get("repo") != repo or payload.get("reference_repo") != "ovnis-pr":
            raise LockstepError(f"peer receipt {repo} identity mismatch")
        if payload.get("generation") != baseline["generation"]:
            raise LockstepError(f"LOCKSTEP_DRIFT: peer receipt {repo} generation mismatch")
        if payload.get("baseline_id") != baseline["baseline_id"]:
            raise LockstepError(f"LOCKSTEP_DRIFT: peer receipt {repo} baseline mismatch")
        if payload.get("source_sha") != baseline["members"][repo]:
            raise LockstepError(f"LOCKSTEP_DRIFT: peer receipt {repo} source SHA mismatch")
        if payload.get("disposition") not in DISPOSITIONS:
            raise LockstepError(f"peer receipt {repo} has invalid disposition")

        expected_contracts = {
            contract_id
            for contract_id, row in contracts.items()
            if row["owner"] == repo or repo in row["consumers"]
        }
        actual_contracts = payload.get("contracts")
        if not isinstance(actual_contracts, list) or set(actual_contracts) != expected_contracts:
            raise LockstepError(
                f"peer receipt {repo} contract mismatch: "
                f"expected={sorted(expected_contracts)} actual={sorted(actual_contracts or [])}"
            )
        actual_impact = payload.get("impact_set")
        if not isinstance(actual_impact, list) or set(actual_impact) != impact_set:
            raise LockstepError(f"peer receipt {repo} impact_set mismatch")

    if seen != expected_peers:
        raise LockstepError(
            f"peer receipt coverage mismatch: expected={sorted(expected_peers)} actual={sorted(seen)}"
        )
    return {
        "status": "PASS",
        "generation": baseline["generation"],
        "baseline_id": baseline["baseline_id"],
        "peers": sorted(seen),
    }


def main() -> int:
    try:
        result = validate_peer_receipts()
    except LockstepError as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, sort_keys=True))
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
