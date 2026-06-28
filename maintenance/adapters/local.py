"""OVNIS-specific maintenance checks (workbook Adapter Rules).

- check_case_provenance: master/candidate rows must carry provenance
  (source_ref/source_url/source_citation/source_tier) and a review marker
  (review_status/review_action/dedupe_status).
- check_unknown_values_not_inferred: a coordinate asserted without a
  location_confidence is treated as a guessed/inferred value.

Read-only and audit-first; problems are quarantined, never auto-corrected.
Intake writes only to the candidate ledger; master promotion is reviewed.
"""
from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

from ..models import MaintenanceFinding

LEDGER_KEYS = ("master_cases", "candidate_cases")
_PROVENANCE_FIELDS = ("source_ref", "source_url", "source_citation", "source_tier")
_REVIEW_FIELDS = ("review_status", "review_action", "dedupe_status")


def _iter_jsonl(path: Path) -> Iterator[tuple[int, dict]]:
    if not path.exists():
        return
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines()):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            yield i, row


def _ledger_paths(root: Path, state: dict) -> list[tuple[str, Path]]:
    outputs = state["canonical_outputs"]
    return [
        (key, root / outputs[key])
        for key in LEDGER_KEYS
        if isinstance(outputs.get(key), str)
    ]


def check_case_provenance(repo: str, root: Path, state: dict) -> list[MaintenanceFinding]:
    findings: list[MaintenanceFinding] = []
    for _key, path in _ledger_paths(root, state):
        for i, row in _iter_jsonl(path):
            has_provenance = any(str(row.get(f) or "").strip() for f in _PROVENANCE_FIELDS)
            has_review = any(row.get(f) for f in _REVIEW_FIELDS)
            if has_provenance and has_review:
                continue
            rid = row.get("record_id", i)
            findings.append(
                MaintenanceFinding(
                    finding_id=f"{repo}:lineage:provenance_{rid}",
                    repo=repo,
                    category="lineage",
                    severity="error",
                    action="quarantined",
                    message="case row missing provenance or review marker",
                    path=str(path.relative_to(root)),
                    detail={"record_id": rid, "has_provenance": has_provenance, "has_review": has_review},
                )
            )
    return findings


def check_unknown_values_not_inferred(repo: str, root: Path, state: dict) -> list[MaintenanceFinding]:
    findings: list[MaintenanceFinding] = []
    for _key, path in _ledger_paths(root, state):
        for i, row in _iter_jsonl(path):
            has_coord = row.get("latitude") is not None or row.get("longitude") is not None
            if has_coord and row.get("location_confidence") in (None, ""):
                rid = row.get("record_id", i)
                findings.append(
                    MaintenanceFinding(
                        finding_id=f"{repo}:contradiction:coord_{rid}",
                        repo=repo,
                        category="contradiction",
                        severity="error",
                        action="quarantined",
                        message="coordinates asserted without location_confidence (possible inferred value)",
                        path=str(path.relative_to(root)),
                        detail={"record_id": rid},
                    )
                )
    return findings


CHECKS = (check_case_provenance, check_unknown_values_not_inferred)


def run_checks(repo: str, root: Path, state: dict) -> list[MaintenanceFinding]:
    findings: list[MaintenanceFinding] = []
    for check in CHECKS:
        findings.extend(check(repo, root, state))
    return findings
