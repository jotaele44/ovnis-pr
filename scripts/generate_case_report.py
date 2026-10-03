#!/usr/bin/env python3
"""Generate deterministic per-case reports from the OVNIS ledgers.

A report restates one master case exactly as the ledger records it, lists the
federation evidence ids its export rows carry, the research records that name
it, and what is still unresolved about it. Nothing is inferred: a date keeps its
recorded precision, an absent field is reported as not recorded, and research
links come only from the curated ledgers and the computed CANDIDATE pairs.

Each report carries a reproducibility receipt shaped after TheHub's
``analytical_run_receipt.v1`` fields, plus the sha256 of every input and of the
report body itself. The same inputs always produce the same report body and
``report_sha256``; only ``created_at`` and the generator commit vary by run.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any

from prii_export_utils import fid as _fid
from validate_research_ledgers import CANDIDATES_FILE, CANDIDATES_KIND, LEDGERS, load_research

REPO_ROOT = Path(__file__).resolve().parent.parent
GENERATOR = "scripts/generate_case_report.py"
REPORT_VERSION = "ovnis-case-report-v1"
ACCESS_CONTEXT = "ovnis-pr committed ledgers (public repository)"

_PRECISION = {4: "YEAR_ONLY", 7: "MONTH_YEAR", 10: "DATE_ONLY"}
_DATE_RE = re.compile(r"^\d{4}(-\d{2}(-\d{2})?)?$")


def case_key(case: dict[str, Any]) -> str:
    return str(case.get("case_id") or case.get("record_id"))


def temporal_precision(case: dict[str, Any]) -> str:
    """The precision of the recorded date; the same rule the federation export declares."""
    date = str(case.get("date_local") or "")
    if not _DATE_RE.match(date):
        return "UNKNOWN"
    if len(date) == 10 and case.get("time_local"):
        return "EXACT_TIMESTAMP"
    return _PRECISION[len(date)]


def evidence_ids(case: dict[str, Any]) -> dict[str, str]:
    """The ids the federation export gives this case's entity, observation and source rows."""
    key = case_key(case)
    source_key = case.get("source_hash") or f"{case.get('source_family')}|{case.get('source_url') or ''}"
    return {
        "entity": f"evo:entities:{_fid('ent', 'case', key)}",
        "observation": f"evo:observations:{_fid('obs', 'case', key)}",
        "source": f"evo:sources:{_fid('src', source_key)}",
    }


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else hashlib.sha256(b"").hexdigest()


def input_hashes(master_path: Path, research_dir: Path, repo_root: Path = REPO_ROOT) -> dict[str, str]:
    """sha256 of every ledger a report reads, keyed by repository-relative path."""
    paths = [master_path] + [research_dir / filename for filename, _ in LEDGERS.values()] + [research_dir / CANDIDATES_FILE]

    def rel(path: Path) -> str:
        try:
            return path.resolve().relative_to(repo_root.resolve()).as_posix()
        except ValueError:
            return path.name

    return {rel(path): sha256_file(path) for path in paths}


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _names_case(row: dict[str, Any], key: str) -> bool:
    if key in (row.get("case_ids") or []) or key in (row.get("case_a"), row.get("case_b")):
        return True
    refs = list(row.get("source_refs") or [])
    refs += [row[side].get("source_ref") for side in ("claim_a", "claim_b") if isinstance(row.get(side), dict)]
    return any(isinstance(ref, dict) and ref.get("case_id") == key for ref in refs)


def _linked(research: dict[str, list[dict[str, Any]]], key: str) -> dict[str, list[dict[str, Any]]]:
    return {kind: [row for row in rows if _names_case(row, key)] for kind, rows in research.items()}


def _source(case: dict[str, Any]) -> dict[str, Any]:
    """The cited source as recorded. ``source_url`` sometimes holds a publication name
    rather than a link; only an http(s) value is reported as a URL."""
    recorded = str(case.get("source_url") or "").strip()
    is_url = bool(re.match(r"^https?://", recorded, re.IGNORECASE))
    return {"citation": case.get("source_citation") or None, "url": recorded if is_url else None,
            "locator": recorded if recorded and not is_url else None, "family": case.get("source_family") or None}


def _ids(rows: list[dict[str, Any]], id_field: str) -> list[str]:
    return sorted(str(row.get(id_field)) for row in rows)


def _unresolved(case: dict[str, Any], linked: dict[str, list[dict[str, Any]]],
                adjudicated_pairs: set[frozenset[str]]) -> list[dict[str, str]]:
    key = case_key(case)
    items: list[dict[str, str]] = []
    for row in linked["contradiction"]:
        if row.get("status") in ("OPEN", "NARROWED"):
            items.append({"kind": "OPEN_CONTRADICTION", "detail": f"contradiction {row.get('status')}",
                          "ref": str(row["contradiction_id"])})
    for row in linked["hypothesis"]:
        if row.get("status") == "OPEN":
            items.append({"kind": "OPEN_HYPOTHESIS", "detail": "hypothesis under test", "ref": str(row["hypothesis_id"])})
    for row in linked["research_queue_item"]:
        if row.get("status") in ("OPEN", "IN_PROGRESS"):
            items.append({"kind": "OPEN_QUESTION", "detail": str(row.get("question")), "ref": str(row["item_id"])})
    for row in linked[CANDIDATES_KIND]:
        if frozenset((row["case_a"], row["case_b"])) not in adjudicated_pairs:
            other = row["case_b"] if row["case_a"] == key else row["case_a"]
            items.append({"kind": "UNADJUDICATED_DUPLICATE_CANDIDATE",
                          "detail": f"may record the same event as {other}; not yet reviewed",
                          "ref": str(row["adjudication_id"])})
    precision = temporal_precision(case)
    if precision == "UNKNOWN":
        items.append({"kind": "RECORD_GAP", "detail": "date not recorded"})
    elif precision in ("YEAR_ONLY", "MONTH_YEAR"):
        items.append({"kind": "RECORD_GAP",
                      "detail": "date recorded only to the " + ("year" if precision == "YEAR_ONLY" else "month")})
    if not str(case.get("municipality") or "").strip():
        items.append({"kind": "RECORD_GAP", "detail": "municipality not recorded"})
    if not str(case.get("description") or "").strip():
        items.append({"kind": "RECORD_GAP", "detail": "narrative not recorded"})
    return items


_CASE_FIELDS = ("date_local", "time_local", "location_name", "municipality", "object_type", "environment",
                "evidence_tier", "witness_type", "witness_count")


def build_report(
    case: dict[str, Any],
    research: dict[str, list[dict[str, Any]]],
    *,
    inputs: dict[str, str],
    snapshot_id: str,
    created_at: str,
    git_sha: str | None = None,
) -> dict[str, Any]:
    """One case's report. ``inputs`` maps each input path to its sha256; ``snapshot_id``
    is ``sha256:<digest of the master ledger>``."""
    key = case_key(case)
    linked = _linked(research, key)
    adjudicated = {frozenset((str(row.get("case_a")), str(row.get("case_b"))))
                   for row in research["manifestation_adjudication"]}
    ids = evidence_ids(case)
    recorded = {field: case[field] for field in _CASE_FIELDS if case.get(field) not in (None, "")}
    recorded["temporal_precision"] = temporal_precision(case)
    body: dict[str, Any] = {
        "report_id": f"RPT-{key}",
        "report_version": REPORT_VERSION,
        "case_id": key,
        "case": recorded,
        "narrative": case.get("description") if str(case.get("description") or "").strip() else None,
        "source": _source(case),
        "evidence_ids": ids,
        "linked": {
            "findings": _ids(linked["finding"], "finding_id"),
            "hypotheses": _ids(linked["hypothesis"], "hypothesis_id"),
            "contradictions": _ids(linked["contradiction"], "contradiction_id"),
            "manifestation_candidates": _ids(linked[CANDIDATES_KIND], "adjudication_id"),
            "adjudications": _ids(linked["manifestation_adjudication"], "adjudication_id"),
            "queue_items": _ids(linked["research_queue_item"], "item_id"),
            "episodes": _ids(linked["media_episode"], "episode_id"),
        },
        "unresolved": _unresolved(case, linked, adjudicated),
    }
    report_sha256 = hashlib.sha256(_canonical(body)).hexdigest()
    run_digest = hashlib.sha256(f"{snapshot_id}|{report_sha256}|{REPORT_VERSION}".encode()).hexdigest()
    body["receipt"] = {
        "run_id": f"run_{run_digest[:32]}",
        "snapshot_id": snapshot_id,
        "retrieval_profile": REPORT_VERSION,
        "provider_config": {"generator": GENERATOR, "generator_git_sha": git_sha},
        "evidence_ids": sorted(ids.values()),
        "access_context": ACCESS_CONTEXT,
        "input_sha256": dict(sorted(inputs.items())),
        "report_sha256": report_sha256,
        "created_at": created_at,
    }
    return body


def build_reports(
    cases: list[dict[str, Any]],
    research: dict[str, list[dict[str, Any]]],
    *,
    master_path: Path,
    research_dir: Path,
    created_at: str,
    git_sha: str | None = None,
) -> list[dict[str, Any]]:
    """A report for every master case, in case-id order."""
    inputs = input_hashes(master_path, research_dir)
    snapshot_id = f"sha256:{sha256_file(master_path)}"
    masters = sorted((c for c in cases if c.get("record_type") == "master"), key=case_key)
    return [build_report(case, research, inputs=inputs, snapshot_id=snapshot_id, created_at=created_at,
                         git_sha=git_sha) for case in masters]


def render_markdown(report: dict[str, Any]) -> str:
    case = report["case"]
    lines = [
        f"# Case report {report['case_id']}",
        "",
        f"- Date as recorded: {case.get('date_local', 'not recorded')} ({case['temporal_precision']})"
        + (f", {case['time_local']}" if case.get("time_local") else ""),
        f"- Place as recorded: {case.get('location_name', 'not recorded')}"
        + (f" ({case['municipality']})" if case.get("municipality") else ""),
        f"- Category: {case.get('object_type', 'not recorded')} · Evidence tier: {case.get('evidence_tier', 'not recorded')}",
        "- Source: " + (report["source"].get("citation") or report["source"].get("locator") or "not recorded")
        + (f" <{report['source']['url']}>" if report["source"].get("url") else ""),
        "",
        "## Narrative",
        "",
        report["narrative"] or "Not recorded.",
        "",
        "## Evidence ids",
        "",
        *[f"- {name}: `{value}`" for name, value in report["evidence_ids"].items()],
        "",
        "## Linked research",
        "",
        *[f"- {name.replace('_', ' ')}: {', '.join(ids) if ids else 'none recorded'}"
          for name, ids in report["linked"].items()],
        "",
        "## Unresolved",
        "",
        *([f"- {item['kind']}: {item['detail']}" + (f" ({item['ref']})" if item.get("ref") else "")
           for item in report["unresolved"]] or ["- nothing recorded as unresolved"]),
        "",
        "## Reproducibility receipt",
        "",
        "```json",
        json.dumps(report["receipt"], indent=2, sort_keys=True, ensure_ascii=False),
        "```",
        "",
    ]
    return "\n".join(lines)


def git_head(repo_root: Path = REPO_ROOT) -> str | None:
    result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo_root, capture_output=True, text=True, check=False)
    return result.stdout.strip() or None if result.returncode == 0 else None


def main(argv: list[str] | None = None) -> int:
    from datetime import datetime, timezone

    parser = argparse.ArgumentParser(description="Generate deterministic OVNIS case reports")
    parser.add_argument("--master", type=Path, default=REPO_ROOT / "data/master/master_cases.jsonl")
    parser.add_argument("--research-dir", type=Path, default=REPO_ROOT / "data/research")
    parser.add_argument("--out", type=Path, default=REPO_ROOT / "reports/cases")
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--case", help="case id to report on")
    target.add_argument("--all", action="store_true", help="report on every master case")
    args = parser.parse_args(argv)

    cases = [json.loads(line) for line in args.master.read_text(encoding="utf-8").splitlines() if line.strip()]
    created_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    reports = build_reports(cases, load_research(args.research_dir), master_path=args.master,
                            research_dir=args.research_dir, created_at=created_at, git_sha=git_head())
    if args.case:
        reports = [r for r in reports if r["case_id"] == args.case]
        if not reports:
            print(f"no master case {args.case!r}")
            return 1
    args.out.mkdir(parents=True, exist_ok=True)
    for report in reports:
        (args.out / f"{report['case_id']}.json").write_text(
            json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
        (args.out / f"{report['case_id']}.md").write_text(render_markdown(report), encoding="utf-8")
    print(f"wrote {len(reports)} case report(s) to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
