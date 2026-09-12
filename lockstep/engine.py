"""FEDERATION LOCKSTEP reference engine for OVNIS.

This module intentionally uses only the Python standard library so the
federation gate can run in a clean GitHub Actions checkout without adding a
runtime dependency. It is a reference implementation, not yet the canonical
TheHub-owned package.
"""

from __future__ import annotations

import argparse
import copy
import fnmatch
import hashlib
import json
import re
import subprocess
import sys
from collections import defaultdict, deque
from collections.abc import Iterable
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
LOCKSTEP_DIR = ROOT / "governance" / "lockstep"
BASELINE_PATH = LOCKSTEP_DIR / "reference_baseline.json"
CRITERIA_PATH = LOCKSTEP_DIR / "reference_criteria.json"
CONTRACTS_PATH = LOCKSTEP_DIR / "contracts.json"
DEPENDENCIES_PATH = LOCKSTEP_DIR / "dependencies.json"
RECEIPT_PATH = LOCKSTEP_DIR / "receipt.json"

SHA_RE = re.compile(r"^[0-9a-f]{40}$")
CONTRACT_ID_RE = re.compile(r"^[a-z][a-z0-9_]*@[1-9][0-9]*$")
MEMBERS = {
    "thehub-pr",
    "moneysweep-pr",
    "spiderweb-pr",
    "aguayluz-pr",
    "ovnis-pr",
    "skywatcher-pr",
    "centinelas-pr",
}
RELATIONSHIPS = {
    "PRODUCES",
    "CONSUMES",
    "IMPORTS",
    "CALLS",
    "EMITS",
    "READS",
    "WRITES",
    "PERSISTS",
    "DEPLOYS_WITH",
    "AUTHENTICATES_WITH",
    "CONFIGURES",
    "GENERATES",
    "VALIDATES_AGAINST",
}
CARDINALITIES = {"1:1", "1:N", "N:1", "N:N"}
DISPOSITIONS = {
    "UPDATED",
    "COMPATIBLE_UNCHANGED",
    "MIGRATION_STAGED",
    "DEPRECATED_COMPATIBLE",
}
SEVERITY = {
    "NO_CHANGE": 0,
    "INTERNAL": 1,
    "ADDITIVE_COMPATIBLE": 2,
    "DEPRECATED_COMPATIBLE": 3,
    "MIGRATION_REQUIRED": 4,
    "BREAKING": 5,
    "UNKNOWN": 6,
}


class LockstepError(RuntimeError):
    """A fail-closed Lockstep validation failure."""


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise LockstepError(f"invalid JSON at {path.relative_to(ROOT)}: {exc}") from exc


def canonical_sha256(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    return hashlib.sha256(encoded).hexdigest()


def require_object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise LockstepError(f"{label} must be an object")
    return value


def validate_sha(value: Any, label: str) -> str:
    if not isinstance(value, str) or not SHA_RE.fullmatch(value) or value == "0" * 40:
        raise LockstepError(f"{label} must be a nonzero 40-character lowercase SHA")
    return value


def validate_baseline() -> dict[str, Any]:
    baseline = require_object(load_json(BASELINE_PATH), "baseline")
    if baseline.get("schema_version") != "federation_lockstep_baseline_v1":
        raise LockstepError("unsupported baseline schema")
    if baseline.get("protocol_version") != "1.0":
        raise LockstepError("unsupported Lockstep protocol version")
    generation = baseline.get("generation")
    if not isinstance(generation, int) or isinstance(generation, bool) or generation < 1:
        raise LockstepError("baseline generation must be a positive integer")
    if baseline.get("reference_repo") != "ovnis-pr":
        raise LockstepError("reference baseline must identify ovnis-pr")
    members = require_object(baseline.get("members"), "baseline.members")
    if set(members) != MEMBERS:
        missing = sorted(MEMBERS - set(members))
        extra = sorted(set(members) - MEMBERS)
        raise LockstepError(f"baseline membership mismatch: missing={missing} extra={extra}")
    for repo, sha in members.items():
        validate_sha(sha, f"baseline.members.{repo}")

    baseline_id = baseline.get("baseline_id")
    if not isinstance(baseline_id, str) or not baseline_id.startswith("sha256:"):
        raise LockstepError("baseline_id must be a sha256 content identity")
    payload = copy.deepcopy(baseline)
    payload.pop("baseline_id", None)
    expected = f"sha256:{canonical_sha256(payload)}"
    if baseline_id != expected:
        raise LockstepError(f"baseline content identity mismatch: expected {expected}")
    return baseline


def validate_contracts(baseline: dict[str, Any]) -> dict[str, dict[str, Any]]:
    registry = require_object(load_json(CONTRACTS_PATH), "contract registry")
    if registry.get("schema_version") != "federation_lockstep_contract_registry_v1":
        raise LockstepError("unsupported contract registry schema")
    rows = registry.get("contracts")
    if not isinstance(rows, list) or not rows:
        raise LockstepError("contract registry must contain contracts")
    by_id: dict[str, dict[str, Any]] = {}
    for index, raw in enumerate(rows):
        row = require_object(raw, f"contracts[{index}]")
        contract_id = row.get("id")
        if not isinstance(contract_id, str) or not CONTRACT_ID_RE.fullmatch(contract_id):
            raise LockstepError(f"invalid contract id at index {index}: {contract_id!r}")
        if contract_id in by_id:
            raise LockstepError(f"duplicate contract id: {contract_id}")
        owner = row.get("owner")
        if owner not in baseline["members"]:
            raise LockstepError(f"unknown contract owner for {contract_id}: {owner!r}")
        consumers = row.get("consumers")
        if not isinstance(consumers, list) or not consumers:
            raise LockstepError(f"contract {contract_id} must declare consumers")
        if len(consumers) != len(set(consumers)):
            raise LockstepError(f"contract {contract_id} has duplicate consumers")
        unknown_consumers = sorted(set(consumers) - set(baseline["members"]))
        if unknown_consumers:
            raise LockstepError(f"contract {contract_id} has unknown consumers: {unknown_consumers}")
        paths = row.get("paths")
        if not isinstance(paths, list) or not paths or not all(isinstance(p, str) and p for p in paths):
            raise LockstepError(f"contract {contract_id} must declare non-empty paths")
        contract_type = row.get("type")
        if contract_type not in {"json_manifest", "json_schema", "export_contract", "event_contract"}:
            raise LockstepError(f"unsupported contract type for {contract_id}: {contract_type!r}")
        if contract_type in {"export_contract", "event_contract"}:
            semantic_path = row.get("semantic_path")
            if not isinstance(semantic_path, str) or not semantic_path:
                raise LockstepError(f"contract {contract_id} must declare semantic_path")
            if semantic_path not in paths:
                raise LockstepError(f"contract {contract_id} semantic_path must also be governed by paths")
        by_id[contract_id] = row
    return by_id


def validate_dependencies(
    baseline: dict[str, Any], contracts: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    graph = require_object(load_json(DEPENDENCIES_PATH), "dependency multigraph")
    if graph.get("schema_version") != "federation_lockstep_dependency_multigraph_v1":
        raise LockstepError("unsupported dependency multigraph schema")
    edges = graph.get("edges")
    if not isinstance(edges, list) or not edges:
        raise LockstepError("dependency multigraph must contain edges")
    seen: set[tuple[str, str, str, str]] = set()
    for index, raw in enumerate(edges):
        edge = require_object(raw, f"edges[{index}]")
        source = edge.get("from")
        target = edge.get("to")
        contract = edge.get("contract")
        relationship = edge.get("relationship")
        cardinality = edge.get("cardinality")
        if source not in baseline["members"] or target not in baseline["members"]:
            raise LockstepError(f"edge {index} references an unregistered member")
        if source == target:
            raise LockstepError(f"edge {index} may not self-reference")
        if contract not in contracts:
            raise LockstepError(f"edge {index} references unknown contract {contract!r}")
        if relationship not in RELATIONSHIPS:
            raise LockstepError(f"edge {index} has unknown relationship {relationship!r}")
        if cardinality not in CARDINALITIES:
            raise LockstepError(f"edge {index} has invalid cardinality {cardinality!r}")
        if not isinstance(edge.get("required"), bool):
            raise LockstepError(f"edge {index}.required must be boolean")
        identity = (source, target, relationship, contract)
        if identity in seen:
            raise LockstepError(f"duplicate dependency edge: {identity}")
        seen.add(identity)
    return edges


def validate_receipt(
    baseline: dict[str, Any], contracts: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    receipt = require_object(load_json(RECEIPT_PATH), "Lockstep receipt")
    if receipt.get("schema_version") != "federation_lockstep_receipt_v1":
        raise LockstepError("unsupported Lockstep receipt schema")
    if receipt.get("repo") != "ovnis-pr":
        raise LockstepError("receipt repo must be ovnis-pr")
    if receipt.get("generation") != baseline.get("generation"):
        raise LockstepError(
            f"LOCKSTEP_DRIFT: receipt generation {receipt.get('generation')!r} != "
            f"required generation {baseline.get('generation')!r}"
        )
    if receipt.get("baseline_id") != baseline.get("baseline_id"):
        raise LockstepError("LOCKSTEP_DRIFT: receipt baseline_id does not match required baseline")
    if receipt.get("disposition") not in DISPOSITIONS:
        raise LockstepError(f"invalid Lockstep disposition: {receipt.get('disposition')!r}")
    receipt_contracts = receipt.get("contracts")
    if not isinstance(receipt_contracts, list) or not receipt_contracts:
        raise LockstepError("receipt contracts must be a non-empty list")
    if len(receipt_contracts) != len(set(receipt_contracts)):
        raise LockstepError("receipt contracts must not contain duplicates")
    unknown = sorted(set(receipt_contracts) - set(contracts))
    if unknown:
        raise LockstepError(f"receipt references unknown contracts: {unknown}")
    impact_set = receipt.get("impact_set")
    if impact_set is not None:
        if not isinstance(impact_set, list) or not all(isinstance(x, str) for x in impact_set):
            raise LockstepError("receipt impact_set must be a string list")
        unknown_impact = sorted(set(impact_set) - set(baseline["members"]))
        if unknown_impact:
            raise LockstepError(f"receipt impact_set has unknown members: {unknown_impact}")
    return receipt


def validate_all() -> tuple[dict[str, Any], dict[str, dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    baseline = validate_baseline()
    contracts = validate_contracts(baseline)
    edges = validate_dependencies(baseline, contracts)
    receipt = validate_receipt(baseline, contracts)
    criteria = require_object(load_json(CRITERIA_PATH), "reference criteria")
    if criteria.get("schema_version") != "ovnis_lockstep_reference_criteria_v1":
        raise LockstepError("unsupported reference criteria schema")
    if criteria.get("reference_status") not in {"NOT_CERTIFIED", "PASS"}:
        raise LockstepError("invalid reference status")
    required = criteria.get("required")
    if not isinstance(required, list) or not required or len(required) != len(set(required)):
        raise LockstepError("reference criteria must be a unique non-empty list")
    return baseline, contracts, edges, receipt


def normalize_event(event_name: str, base_sha: str, head_sha: str) -> tuple[str, str]:
    if event_name not in {"pull_request", "push", "workflow_dispatch"}:
        raise LockstepError(f"unsupported event context: {event_name!r}")
    return validate_sha(base_sha, "BASE_SHA"), validate_sha(head_sha, "HEAD_SHA")


def path_matches(path: str, patterns: Iterable[str]) -> bool:
    return any(fnmatch.fnmatch(path, pattern) for pattern in patterns)


def matched_contracts(
    changed_paths: Iterable[str], contracts: dict[str, dict[str, Any]]
) -> set[str]:
    changed = tuple(changed_paths)
    return {
        contract_id
        for contract_id, row in contracts.items()
        if any(path_matches(path, row["paths"]) for path in changed)
    }


def closure(start: set[str], adjacency: dict[str, set[str]]) -> set[str]:
    result: set[str] = set()
    queue: deque[str] = deque(sorted(start))
    while queue:
        node = queue.popleft()
        for neighbour in sorted(adjacency.get(node, set())):
            if neighbour not in result and neighbour not in start:
                result.add(neighbour)
                queue.append(neighbour)
    return result


def compute_impact(
    changed_paths: Iterable[str],
    contracts: dict[str, dict[str, Any]],
    edges: list[dict[str, Any]],
) -> dict[str, list[str]]:
    matched = matched_contracts(changed_paths, contracts)
    direct: set[str] = set()
    for contract_id in matched:
        contract = contracts[contract_id]
        direct.add(contract["owner"])
        direct.update(contract["consumers"])

    # Lockstep governance changes are always local-impacting even when they are
    # not themselves a producer data contract.
    if any(path.startswith("governance/lockstep/") or path == ".github/workflows/federation-lockstep.yml" for path in changed_paths):
        direct.add("ovnis-pr")

    outgoing: dict[str, set[str]] = defaultdict(set)
    incoming: dict[str, set[str]] = defaultdict(set)
    for edge in edges:
        if edge["required"]:
            outgoing[edge["from"]].add(edge["to"])
            incoming[edge["to"]].add(edge["from"])

    reverse = closure(direct, incoming)
    transitive = closure(direct, outgoing)
    union = direct | reverse | transitive
    return {
        "contracts": sorted(matched),
        "direct": sorted(direct),
        "reverse": sorted(reverse),
        "transitive": sorted(transitive),
        "union": sorted(union),
    }


def json_type(schema: dict[str, Any], property_name: str) -> Any:
    props = schema.get("properties")
    if not isinstance(props, dict):
        return None
    item = props.get(property_name)
    return item.get("type") if isinstance(item, dict) else None


def semantic_schema_diff(before: Any, after: Any) -> dict[str, Any]:
    if not isinstance(before, dict) or not isinstance(after, dict):
        return {"classification": "UNKNOWN", "changes": ["schema root is not an object"]}
    changes: list[dict[str, str]] = []
    before_props = before.get("properties") if isinstance(before.get("properties"), dict) else {}
    after_props = after.get("properties") if isinstance(after.get("properties"), dict) else {}
    before_required = set(before.get("required") if isinstance(before.get("required"), list) else [])
    after_required = set(after.get("required") if isinstance(after.get("required"), list) else [])

    for name in sorted(set(before_props) - set(after_props)):
        changes.append({"classification": "BREAKING", "detail": f"property removed: {name}"})
    for name in sorted(set(after_props) - set(before_props)):
        classification = "BREAKING" if name in after_required else "ADDITIVE_COMPATIBLE"
        changes.append({"classification": classification, "detail": f"property added: {name}"})
    for name in sorted(set(before_props) & set(after_props)):
        before_type = json_type(before, name)
        after_type = json_type(after, name)
        if before_type != after_type:
            changes.append({"classification": "BREAKING", "detail": f"type changed: {name}: {before_type!r} -> {after_type!r}"})
        before_enum = before_props[name].get("enum") if isinstance(before_props[name], dict) else None
        after_enum = after_props[name].get("enum") if isinstance(after_props[name], dict) else None
        if isinstance(before_enum, list) and isinstance(after_enum, list):
            removed = set(before_enum) - set(after_enum)
            added = set(after_enum) - set(before_enum)
            if removed:
                changes.append({"classification": "BREAKING", "detail": f"enum narrowed: {name}"})
            elif added:
                changes.append({"classification": "ADDITIVE_COMPATIBLE", "detail": f"enum expanded: {name}"})
    for name in sorted(after_required - before_required):
        if name in before_props:
            changes.append({"classification": "BREAKING", "detail": f"optional became required: {name}"})
    for name in sorted(before_required - after_required):
        if name in after_props:
            changes.append({"classification": "ADDITIVE_COMPATIBLE", "detail": f"required became optional: {name}"})

    classification = "NO_CHANGE"
    if changes:
        classification = max((c["classification"] for c in changes), key=SEVERITY.__getitem__)
    return {"classification": classification, "changes": changes}


def semantic_manifest_diff(before: Any, after: Any) -> dict[str, Any]:
    if not isinstance(before, dict) or not isinstance(after, dict):
        return {"classification": "UNKNOWN", "changes": ["manifest root is not an object"]}
    changes: list[dict[str, str]] = []
    for key in sorted(set(before) - set(after)):
        changes.append({"classification": "BREAKING", "detail": f"top-level key removed: {key}"})
    for key in sorted(set(after) - set(before)):
        changes.append({"classification": "ADDITIVE_COMPATIBLE", "detail": f"top-level key added: {key}"})
    for key in sorted(set(before) & set(after)):
        if type(before[key]) is not type(after[key]):
            changes.append({"classification": "BREAKING", "detail": f"top-level type changed: {key}"})
        elif before[key] != after[key]:
            changes.append({"classification": "MIGRATION_REQUIRED", "detail": f"top-level value changed: {key}"})
    classification = "NO_CHANGE"
    if changes:
        classification = max((c["classification"] for c in changes), key=SEVERITY.__getitem__)
    return {"classification": classification, "changes": changes}


def semantic_descriptor_diff(before: Any, after: Any, path: str = "$") -> dict[str, Any]:
    changes: list[dict[str, str]] = []

    def walk(left: Any, right: Any, current: str) -> None:
        if type(left) is not type(right):
            changes.append(
                {
                    "classification": "BREAKING",
                    "detail": f"type changed at {current}: {type(left).__name__} -> {type(right).__name__}",
                }
            )
            return
        if isinstance(left, dict):
            for key in sorted(set(left) - set(right)):
                changes.append(
                    {"classification": "BREAKING", "detail": f"key removed at {current}.{key}"}
                )
            for key in sorted(set(right) - set(left)):
                changes.append(
                    {
                        "classification": "ADDITIVE_COMPATIBLE",
                        "detail": f"key added at {current}.{key}",
                    }
                )
            for key in sorted(set(left) & set(right)):
                walk(left[key], right[key], f"{current}.{key}")
            return
        if isinstance(left, list):
            if all(isinstance(value, (str, int, float, bool, type(None))) for value in left + right):
                left_set = set(left)
                right_set = set(right)
                for value in sorted(left_set - right_set, key=repr):
                    changes.append(
                        {
                            "classification": "BREAKING",
                            "detail": f"list value removed at {current}: {value!r}",
                        }
                    )
                for value in sorted(right_set - left_set, key=repr):
                    changes.append(
                        {
                            "classification": "ADDITIVE_COMPATIBLE",
                            "detail": f"list value added at {current}: {value!r}",
                        }
                    )
                return
            if left != right:
                changes.append(
                    {
                        "classification": "MIGRATION_REQUIRED",
                        "detail": f"structured list changed at {current}",
                    }
                )
            return
        if left != right:
            changes.append(
                {
                    "classification": "MIGRATION_REQUIRED",
                    "detail": f"value changed at {current}: {left!r} -> {right!r}",
                }
            )

    walk(before, after, path)
    classification = "NO_CHANGE"
    if changes:
        classification = max((change["classification"] for change in changes), key=SEVERITY.__getitem__)
    return {"classification": classification, "changes": changes}


def run_git(args: list[str]) -> str:
    try:
        return subprocess.run(
            ["git", *args], cwd=ROOT, check=True, capture_output=True, text=True
        ).stdout
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr.strip() or exc.stdout.strip()
        raise LockstepError(f"git {' '.join(args)} failed: {detail}") from exc


def changed_paths(base_sha: str, head_sha: str) -> list[str]:
    output = run_git(["diff", "--name-only", "--diff-filter=ACDMRTUXB", f"{base_sha}...{head_sha}"])
    return [line.strip() for line in output.splitlines() if line.strip()]


def git_json_at(sha: str, path: str) -> Any:
    raw = run_git(["show", f"{sha}:{path}"])
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise LockstepError(f"{path} at {sha} is not valid JSON: {exc}") from exc


def classify_changed_contracts(
    base_sha: str,
    head_sha: str,
    changed: list[str],
    contracts: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    results: dict[str, dict[str, Any]] = {}
    for contract_id in sorted(matched_contracts(changed, contracts)):
        row = contracts[contract_id]
        contract_type = row["type"]
        paths = [path for path in changed if path_matches(path, row["paths"])]
        contract_results: list[dict[str, Any]] = []

        if contract_type in {"export_contract", "event_contract"}:
            semantic_path = row["semantic_path"]
            try:
                before = git_json_at(base_sha, semantic_path)
                after = git_json_at(head_sha, semantic_path)
                result = semantic_descriptor_diff(before, after)
                if result["classification"] == "NO_CHANGE" and paths:
                    result = {
                        "classification": "INTERNAL",
                        "changes": [
                            f"implementation/evidence changed while canonical signature stayed stable: {', '.join(sorted(paths))}"
                        ],
                    }
                contract_results.append({"path": semantic_path, **result})
            except LockstepError as exc:
                contract_results.append(
                    {
                        "path": semantic_path,
                        "classification": "BREAKING",
                        "changes": [str(exc)],
                    }
                )
        else:
            for path in paths:
                try:
                    before = git_json_at(base_sha, path)
                    after = git_json_at(head_sha, path)
                except LockstepError as exc:
                    contract_results.append(
                        {"path": path, "classification": "BREAKING", "changes": [str(exc)]}
                    )
                    continue
                result = (
                    semantic_schema_diff(before, after)
                    if contract_type == "json_schema"
                    else semantic_manifest_diff(before, after)
                )
                contract_results.append({"path": path, **result})

        classification = "NO_CHANGE"
        if contract_results:
            classification = max(
                (item["classification"] for item in contract_results), key=SEVERITY.__getitem__
            )
        results[contract_id] = {"classification": classification, "paths": contract_results}
    return results


def gate(base_sha: str, head_sha: str, event_name: str) -> dict[str, Any]:
    base_sha, head_sha = normalize_event(event_name, base_sha, head_sha)
    baseline, contracts, edges, receipt = validate_all()
    changed = changed_paths(base_sha, head_sha)
    impact = compute_impact(changed, contracts, edges)
    semantic = classify_changed_contracts(base_sha, head_sha, changed, contracts)

    governed_changed = bool(impact["contracts"])
    lockstep_changed = any(path.startswith("governance/lockstep/") for path in changed)
    receipt_changed = RECEIPT_PATH.relative_to(ROOT).as_posix() in changed
    if (governed_changed or lockstep_changed) and not receipt_changed:
        raise LockstepError("governed federation state changed without a Lockstep receipt update")

    for contract_id, result in semantic.items():
        if result["classification"] == "UNKNOWN":
            raise LockstepError(f"UNKNOWN semantic compatibility for {contract_id}; fail closed")

    declared = set(receipt.get("impact_set") or [])
    computed = set(impact["union"])
    if declared:
        symmetric_difference = sorted(declared ^ computed)
        if symmetric_difference:
            raise LockstepError(
                f"LOCKSTEP_IMPACT_SET mismatch: declared={sorted(declared)} computed={sorted(computed)} "
                f"symmetric_difference={symmetric_difference}"
            )

    return {
        "status": "PASS",
        "event": event_name,
        "base_sha": base_sha,
        "head_sha": head_sha,
        "generation": baseline["generation"],
        "baseline_id": baseline["baseline_id"],
        "changed_paths": changed,
        "impact": impact,
        "semantic_diff": semantic,
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m lockstep.engine")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("validate")

    event_parser = subparsers.add_parser("normalize-event")
    event_parser.add_argument("--event-name", required=True)
    event_parser.add_argument("--base-sha", required=True)
    event_parser.add_argument("--head-sha", required=True)

    impact_parser = subparsers.add_parser("impact")
    impact_parser.add_argument("--changed", nargs="+", required=True)

    gate_parser = subparsers.add_parser("gate")
    gate_parser.add_argument("--event-name", required=True)
    gate_parser.add_argument("--base-sha", required=True)
    gate_parser.add_argument("--head-sha", required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        baseline, contracts, edges, _receipt = validate_all()
        if args.command == "validate":
            result = {
                "status": "PASS",
                "generation": baseline["generation"],
                "baseline_id": baseline["baseline_id"],
                "members": sorted(baseline["members"]),
                "contracts": sorted(contracts),
                "edges": len(edges),
            }
        elif args.command == "normalize-event":
            base_sha, head_sha = normalize_event(args.event_name, args.base_sha, args.head_sha)
            result = {"status": "PASS", "base_sha": base_sha, "head_sha": head_sha}
        elif args.command == "impact":
            result = {"status": "PASS", "impact": compute_impact(args.changed, contracts, edges)}
        elif args.command == "gate":
            result = gate(args.base_sha, args.head_sha, args.event_name)
        else:  # pragma: no cover - argparse prevents this
            raise LockstepError(f"unknown command: {args.command}")
    except LockstepError as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, sort_keys=True))
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
