#!/usr/bin/env python3
"""Validate the OVNIS research ledgers under data/research/.

Curators record research by editing these JSONL ledgers; nothing here is
generated except data/research/manifestation_candidates.jsonl (written by
``dedupe_candidates.py --master-pairs``). The validator enforces what the
ledgers may claim:

* every row matches its schema under schemas/research/;
* every case, source, topic, finding, hypothesis and adjudication id a row
  names resolves to a real record;
* a finding is ACCEPTED only with at least one cited source and a review, and
  an INTERPRETIVE finding states its interpretation basis;
* a hypothesis is SUPPORTED only when all nine falsification checks were run
  and none FAILED;
* a SUPERSEDED record names the record that supersedes it;
* curated records are CURATED: nothing is promoted from search output;
* a curated manifestation adjudication is a reviewed decision, and a computed
  one is never anything but CANDIDATE;
* with ``--base REF``, no record present at REF has been deleted. Records are
  retired by status (REJECTED, SUPERSEDED, DROPPED), never removed.
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
RESEARCH_DIR = REPO_ROOT / "data" / "research"
MASTER_PATH = REPO_ROOT / "data" / "master" / "master_cases.jsonl"
REGISTRY_PATH = REPO_ROOT / "data" / "reference" / "source_registry.csv"
SCHEMA_DIR = REPO_ROOT / "schemas" / "research"

# kind -> (ledger file, id field). Curated ledgers only.
LEDGERS: dict[str, tuple[str, str]] = {
    "research_topic": ("topics.jsonl", "topic_id"),
    "finding": ("findings.jsonl", "finding_id"),
    "hypothesis": ("hypotheses.jsonl", "hypothesis_id"),
    "contradiction": ("contradictions.jsonl", "contradiction_id"),
    "manifestation_adjudication": ("manifestation_adjudications.jsonl", "adjudication_id"),
    "research_queue_item": ("research_queue.jsonl", "item_id"),
    "media_episode": ("media_episodes.jsonl", "episode_id"),
}
# Computed CANDIDATE pairs; regenerated, so exempt from the retention rule.
CANDIDATES_KIND = "manifestation_candidate"
CANDIDATES_FILE = "manifestation_candidates.jsonl"

FALSIFICATION_CHECKS = (
    "identity_errors", "duplicate_manifestations", "ordinary_explanations", "background_prevalence",
    "missing_data", "source_dependence", "temporal_mismatch", "geometry_uncertainty", "contradictions",
)
ADJUDICATION_DECISIONS = {"SAME_EVENT", "DISTINCT", "UNRESOLVABLE"}


def read_ledger(path: Path) -> list[tuple[int, dict[str, Any]]]:
    """``(line number, row)`` for every non-blank line; a missing ledger is empty."""
    if not path.exists():
        return []
    rows: list[tuple[int, dict[str, Any]]] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path.name}:{line_no}: invalid JSON: {exc}") from exc
        if not isinstance(row, dict):
            raise ValueError(f"{path.name}:{line_no}: row must be a JSON object")
        rows.append((line_no, row))
    return rows


def load_research(research_dir: Path = RESEARCH_DIR) -> dict[str, list[dict[str, Any]]]:
    """Every research ledger's rows by kind, plus the computed candidate pairs."""
    research = {kind: [row for _, row in read_ledger(research_dir / filename)]
                for kind, (filename, _) in LEDGERS.items()}
    research[CANDIDATES_KIND] = [row for _, row in read_ledger(research_dir / CANDIDATES_FILE)]
    return research


def load_case_ids(master_path: Path = MASTER_PATH) -> set[str]:
    ids: set[str] = set()
    for _, row in read_ledger(master_path):
        if row.get("record_type") == "master":
            ids.add(str(row.get("case_id") or row.get("record_id")))
    return ids


def load_registry_ids(registry_path: Path = REGISTRY_PATH) -> set[str]:
    if not registry_path.exists():
        return set()
    with registry_path.open(encoding="utf-8", newline="") as handle:
        return {row["source_id"] for row in csv.DictReader(handle) if row.get("source_id")}


def _schema_errors(schema_dir: Path, kind: str, rows: list[tuple[int, dict[str, Any]]], filename: str) -> list[str]:
    from jsonschema import Draft202012Validator

    schema_kind = "manifestation_adjudication" if kind == CANDIDATES_KIND else kind
    schema = json.loads((schema_dir / f"{schema_kind}.v1.schema.json").read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    errors: list[str] = []
    for line_no, row in rows:
        for exc in sorted(validator.iter_errors(row), key=lambda e: list(e.path)):
            where = ".".join(str(part) for part in exc.path) or "<root>"
            errors.append(f"{filename}:{line_no}: schema error at {where}: {exc.message}")
    return errors


def _base_ids(ref: str, research_dir: Path, repo_root: Path) -> dict[str, set[str]]:
    """Ids each curated ledger held at git ``ref``; an absent ledger holds none."""
    ids: dict[str, set[str]] = {}
    for kind, (filename, id_field) in LEDGERS.items():
        relpath = (research_dir / filename).resolve().relative_to(repo_root.resolve()).as_posix()
        shown = subprocess.run(
            ["git", "show", f"{ref}:{relpath}"], cwd=repo_root, capture_output=True, text=True, check=False
        )
        rows = [json.loads(line) for line in shown.stdout.splitlines() if line.strip()] if shown.returncode == 0 else []
        ids[kind] = {str(row.get(id_field)) for row in rows if isinstance(row, dict)}
    return ids


class _Checker:
    def __init__(self, ledgers: dict[str, list[tuple[int, dict[str, Any]]]], case_ids: set[str],
                 source_ids: set[str]) -> None:
        self.ledgers = ledgers
        self.case_ids = case_ids
        self.source_ids = source_ids
        self.errors: list[str] = []
        self.ids: dict[str, set[str]] = {}
        for kind, rows in ledgers.items():
            id_field = LEDGERS[kind][1] if kind in LEDGERS else "adjudication_id"
            self.ids[kind] = {str(row.get(id_field)) for _, row in rows}
        self.adjudication_ids = self.ids["manifestation_adjudication"] | self.ids[CANDIDATES_KIND]

    def error(self, where: str, message: str) -> None:
        self.errors.append(f"{where}: {message}")

    def cases(self, where: str, values: Any) -> None:
        for value in values or []:
            if value not in self.case_ids:
                self.error(where, f"unknown case id {value!r}")

    def refs(self, where: str, kind: str, values: Any) -> None:
        for value in values or []:
            if value not in self.ids[kind]:
                self.error(where, f"unknown {kind} id {value!r}")

    def source_ref(self, where: str, ref: Any) -> None:
        if not isinstance(ref, dict):
            return
        if "case_id" in ref:
            self.cases(where, [ref["case_id"]])
        if "source_id" in ref and ref["source_id"] not in self.source_ids:
            self.error(where, f"unknown source id {ref['source_id']!r}")

    def evidence_ref(self, where: str, value: str) -> None:
        known = (self.case_ids | self.source_ids | self.ids["finding"] | self.ids["hypothesis"]
                 | self.ids["contradiction"] | self.adjudication_ids)
        if value not in known:
            self.error(where, f"evidence ref {value!r} does not resolve to a case, source or research record")

    def superseded(self, where: str, kind: str, row: dict[str, Any], own_id: str) -> None:
        if row.get("status") != "SUPERSEDED":
            return
        target = row.get("superseded_by")
        if not target or target == own_id or target not in self.ids[kind]:
            self.error(where, f"SUPERSEDED requires superseded_by naming another {kind}")

    def run(self) -> list[str]:
        for kind, rows in self.ledgers.items():
            filename = CANDIDATES_FILE if kind == CANDIDATES_KIND else LEDGERS[kind][0]
            id_field = "adjudication_id" if kind == CANDIDATES_KIND else LEDGERS[kind][1]
            seen: set[str] = set()
            for line_no, row in rows:
                where = f"{filename}:{line_no}"
                own_id = str(row.get(id_field))
                if own_id in seen:
                    self.error(where, f"duplicate {id_field} {own_id!r}")
                seen.add(own_id)
                if kind != CANDIDATES_KIND and row.get("origin") != "CURATED":
                    self.error(where, f"origin {row.get('origin')!r} is not CURATED; research records are "
                                      "recorded by curators, never promoted from search output")
                getattr(self, f"_{kind}")(where, row, own_id)
        return self.errors

    def _research_topic(self, where: str, row: dict[str, Any], own_id: str) -> None:
        return None

    def _finding(self, where: str, row: dict[str, Any], own_id: str) -> None:
        self.refs(where, "research_topic", row.get("topic_ids"))
        self.cases(where, row.get("case_ids"))
        for ref in row.get("source_refs") or []:
            self.source_ref(where, ref)
        if row.get("status") == "ACCEPTED" and not (row.get("source_refs") and row.get("review")):
            self.error(where, "ACCEPTED finding requires at least one source_ref and a review")
        if row.get("epistemic_class") == "INTERPRETIVE" and not str(row.get("interpretation_basis") or "").strip():
            self.error(where, "INTERPRETIVE finding requires an interpretation_basis")
        self.superseded(where, "finding", row, own_id)

    def _hypothesis(self, where: str, row: dict[str, Any], own_id: str) -> None:
        self.cases(where, row.get("case_ids"))
        self.refs(where, "finding", row.get("finding_ids"))
        falsification = row.get("falsification")
        checks: dict[str, Any] = falsification if isinstance(falsification, dict) else {}
        statuses: dict[str, Any] = {}
        for name in FALSIFICATION_CHECKS:
            entry = checks.get(name)
            check: dict[str, Any] = entry if isinstance(entry, dict) else {}
            statuses[name] = check.get("status")
            for value in check.get("evidence_refs") or []:
                self.evidence_ref(where, value)
        if row.get("status") == "SUPPORTED":
            open_checks = sorted(
                name for name, status in statuses.items() if status in (None, "NOT_RUN", "FAILED")
            )
            if open_checks:
                self.error(where, "SUPPORTED hypothesis requires every falsification check run and none FAILED: "
                                  + ", ".join(open_checks))
        self.superseded(where, "hypothesis", row, own_id)

    def _contradiction(self, where: str, row: dict[str, Any], own_id: str) -> None:
        self.cases(where, row.get("case_ids"))
        for side in ("claim_a", "claim_b"):
            claim = row.get(side)
            if isinstance(claim, dict):
                self.source_ref(where, claim.get("source_ref"))
        self.superseded(where, "contradiction", row, own_id)

    def _adjudication_pair(self, where: str, row: dict[str, Any]) -> None:
        self.cases(where, [row.get("case_a"), row.get("case_b")])
        if row.get("case_a") == row.get("case_b"):
            self.error(where, "an adjudication pairs two different cases")

    def _manifestation_adjudication(self, where: str, row: dict[str, Any], own_id: str) -> None:
        self._adjudication_pair(where, row)
        if row.get("status") not in ADJUDICATION_DECISIONS:
            self.error(where, "a curated adjudication must decide SAME_EVENT, DISTINCT or UNRESOLVABLE; "
                              f"computed CANDIDATE pairs live in {CANDIDATES_FILE}")
        elif not (row.get("reviewed_by") and row.get("rationale")):
            self.error(where, f"{row.get('status')} requires reviewed_by and rationale")

    def _manifestation_candidate(self, where: str, row: dict[str, Any], own_id: str) -> None:
        self._adjudication_pair(where, row)
        if row.get("origin") != "COMPUTED" or row.get("status") != "CANDIDATE":
            self.error(where, "computed pairs are always COMPUTED and CANDIDATE: similarity never decides identity")

    def _research_queue_item(self, where: str, row: dict[str, Any], own_id: str) -> None:
        self.cases(where, row.get("case_ids"))
        self.refs(where, "finding", row.get("finding_ids"))
        self.refs(where, "hypothesis", row.get("hypothesis_ids"))

    def _media_episode(self, where: str, row: dict[str, Any], own_id: str) -> None:
        self.cases(where, row.get("case_ids"))
        self.refs(where, "finding", row.get("finding_ids"))


def validate(
    research_dir: Path = RESEARCH_DIR,
    *,
    master_path: Path = MASTER_PATH,
    registry_path: Path = REGISTRY_PATH,
    schema_dir: Path = SCHEMA_DIR,
    base: str | None = None,
    repo_root: Path = REPO_ROOT,
) -> list[str]:
    """Every rule violation in the research ledgers; empty when they are valid."""
    ledgers = {kind: read_ledger(research_dir / filename) for kind, (filename, _) in LEDGERS.items()}
    ledgers[CANDIDATES_KIND] = read_ledger(research_dir / CANDIDATES_FILE)

    errors: list[str] = []
    for kind, rows in ledgers.items():
        filename = CANDIDATES_FILE if kind == CANDIDATES_KIND else LEDGERS[kind][0]
        errors += _schema_errors(schema_dir, kind, rows, filename)
    errors += _Checker(ledgers, load_case_ids(master_path), load_registry_ids(registry_path)).run()

    if base:
        for kind, previous in _base_ids(base, research_dir, repo_root).items():
            filename, id_field = LEDGERS[kind]
            current = {str(row.get(id_field)) for _, row in ledgers[kind]}
            for missing in sorted(previous - current):
                errors.append(f"{filename}: {id_field} {missing!r} existed at {base} and is gone; research records "
                              "are retired by status (REJECTED, SUPERSEDED, DROPPED), never deleted")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate the OVNIS research ledgers")
    parser.add_argument("--research-dir", type=Path, default=RESEARCH_DIR)
    parser.add_argument("--master", type=Path, default=MASTER_PATH)
    parser.add_argument("--registry", type=Path, default=REGISTRY_PATH)
    parser.add_argument("--schema-dir", type=Path, default=SCHEMA_DIR)
    parser.add_argument("--base", help="git ref whose research records must all still exist")
    args = parser.parse_args(argv)

    errors = validate(args.research_dir, master_path=args.master, registry_path=args.registry,
                      schema_dir=args.schema_dir, base=args.base)
    research = load_research(args.research_dir)
    print("# OVNIS research ledger validation report")
    print("\n" + ", ".join(f"{kind}: {len(rows)}" for kind, rows in research.items()))
    print(f"Errors: {len(errors)}")
    for item in errors:
        print(f"- {item}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
