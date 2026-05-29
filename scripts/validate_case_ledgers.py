#!/usr/bin/env python3
"""Validate PRUFON JSONL case ledgers.

This validator is intentionally dependency-light. If jsonschema is installed,
it performs full JSON Schema validation. Without jsonschema, it still enforces
core PRUFON control-plane gates.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

GENERIC_LOCATIONS = {
    "pr",
    "puerto rico",
    "puerto rico, pr",
    "unknown",
    "islandwide",
}

REQUIRED = [
    "record_id",
    "record_type",
    "date_local",
    "location_name",
    "description",
    "source_url",
    "evidence_tier",
    "dedupe_status",
    "review_action",
]

DATE_RE = re.compile(r"^[0-9]{4}(-[0-9]{2}){0,2}$")
TIME_RE = re.compile(r"^([01][0-9]|2[0-3]):[0-5][0-9]$")

EVIDENCE_TIERS = {"T1", "T2", "T3", "T4"}
RECORD_TYPES = {"candidate", "master", "duplicate", "update_existing", "echo_noise", "rejected"}
DEDUPE_STATUSES = {"new", "possible_duplicate", "duplicate", "update_existing", "not_checked", "rejected"}
REVIEW_ACTIONS = {"promote", "merge", "reject", "monitor", "pending"}


def load_schema(schema_path: Path) -> dict[str, Any] | None:
    if not schema_path.exists():
        return None
    return json.loads(schema_path.read_text(encoding="utf-8"))


def iter_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{line_no}: invalid JSON: {exc}") from exc
        if not isinstance(row, dict):
            raise ValueError(f"{path}:{line_no}: row must be a JSON object")
        row["__path"] = str(path)
        row["__line"] = line_no
        rows.append(row)
    return rows


def core_validate(row: dict[str, Any], *, path: Path, line_no: int) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    for field in REQUIRED:
        if field not in row or row[field] in (None, ""):
            errors.append(f"{path}:{line_no}: missing required field `{field}`")

    date_local = str(row.get("date_local", ""))
    if date_local and not DATE_RE.match(date_local):
        errors.append(f"{path}:{line_no}: date_local must be YYYY, YYYY-MM, or YYYY-MM-DD")

    time_local = row.get("time_local")
    if time_local not in (None, "") and not TIME_RE.match(str(time_local)):
        errors.append(f"{path}:{line_no}: time_local must use HH:MM 24-hour format")

    if row.get("evidence_tier") not in EVIDENCE_TIERS:
        errors.append(f"{path}:{line_no}: evidence_tier must be one of {sorted(EVIDENCE_TIERS)}")

    if row.get("record_type") not in RECORD_TYPES:
        errors.append(f"{path}:{line_no}: record_type must be one of {sorted(RECORD_TYPES)}")

    if row.get("dedupe_status") not in DEDUPE_STATUSES:
        errors.append(f"{path}:{line_no}: dedupe_status must be one of {sorted(DEDUPE_STATUSES)}")

    if row.get("review_action") not in REVIEW_ACTIONS:
        errors.append(f"{path}:{line_no}: review_action must be one of {sorted(REVIEW_ACTIONS)}")

    location = str(row.get("location_name", "")).strip().lower()
    if location in GENERIC_LOCATIONS:
        errors.append(f"{path}:{line_no}: location_name is too generic: {row.get('location_name')!r}")

    if row.get("record_type") == "master":
        case_id = row.get("case_id")
        if not case_id:
            errors.append(f"{path}:{line_no}: master record requires case_id")
        if row.get("review_action") not in {"promote", "merge"}:
            errors.append(f"{path}:{line_no}: master record review_action must be promote or merge")
        if row.get("dedupe_status") == "not_checked":
            errors.append(f"{path}:{line_no}: master record cannot have dedupe_status=not_checked")

    if row.get("record_type") == "candidate" and row.get("review_action") == "promote":
        warnings.append(f"{path}:{line_no}: candidate marked promote; ensure promotion PR moves it to master ledger")

    description = str(row.get("description", ""))
    if len(description) < 20:
        errors.append(f"{path}:{line_no}: description must be at least 20 characters")

    return errors, warnings


def schema_validate(rows: list[dict[str, Any]], schema: dict[str, Any] | None) -> list[str]:
    if not schema:
        return []
    try:
        from jsonschema import Draft202012Validator  # type: ignore
    except Exception:
        return ["jsonschema not installed; skipped full JSON Schema validation"]

    validator = Draft202012Validator(schema)
    errors: list[str] = []
    for row in rows:
        clean = {k: v for k, v in row.items() if not k.startswith("__")}
        for exc in validator.iter_errors(clean):
            loc = ".".join(str(part) for part in exc.path) or "<root>"
            errors.append(f"{row['__path']}:{row['__line']}: schema error at {loc}: {exc.message}")
    return errors


def validate(paths: list[Path], schema_path: Path) -> int:
    all_rows: list[dict[str, Any]] = []
    errors: list[str] = []
    warnings: list[str] = []

    for path in paths:
        if not path.exists():
            errors.append(f"missing ledger: {path}")
            continue
        rows = iter_jsonl(path)
        all_rows.extend(rows)
        for row in rows:
            row_errors, row_warnings = core_validate(row, path=path, line_no=int(row["__line"]))
            errors.extend(row_errors)
            warnings.extend(row_warnings)

    seen: dict[str, str] = {}
    for row in all_rows:
        record_id = str(row.get("record_id", ""))
        if record_id in seen:
            errors.append(f"duplicate record_id {record_id!r}: {seen[record_id]} and {row['__path']}:{row['__line']}")
        else:
            seen[record_id] = f"{row['__path']}:{row['__line']}"

    schema = load_schema(schema_path)
    schema_messages = schema_validate(all_rows, schema)
    for message in schema_messages:
        if message.startswith("jsonschema not installed"):
            warnings.append(message)
        else:
            errors.append(message)

    print("# PRUFON ledger validation report")
    print(f"\nRows checked: {len(all_rows)}")
    print(f"Ledgers checked: {len(paths)}")
    print(f"Errors: {len(errors)}")
    print(f"Warnings: {len(warnings)}")

    if errors:
        print("\n## Errors")
        for item in errors:
            print(f"- {item}")

    if warnings:
        print("\n## Warnings")
        for item in warnings:
            print(f"- {item}")

    return 1 if errors else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate PRUFON case ledgers")
    parser.add_argument(
        "--schema",
        default="data/schemas/case.schema.json",
        help="Path to PRUFON JSON Schema",
    )
    parser.add_argument(
        "ledgers",
        nargs="*",
        default=["data/candidates/candidate_cases.jsonl", "data/master/master_cases.jsonl"],
        help="JSONL ledgers to validate",
    )
    args = parser.parse_args()
    return validate([Path(p) for p in args.ledgers], Path(args.schema))


if __name__ == "__main__":
    raise SystemExit(main())
