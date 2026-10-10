#!/usr/bin/env python3
"""Project OVNIS case ledgers into the PRII federation canonical streams.

Maps the OVNIS case model onto the Hub's canonical contract:
  * each master case            -> one `entities` row  (entity_type=uap_case)
  * each master case            -> one `observations` row
  * each distinct municipality  -> one `entities` row  (entity_type=municipality)
  * each distinct source        -> one `sources` row
  * case -> source              -> one `relationships` row (reported_by)
  * case -> municipality        -> one `relationships` row (located_in)
  * case -> matched case        -> one `relationships` row (duplicate_of)

and, from the research ledgers under data/research/ (build_research_streams):
  * each curated research record -> one typed `entities` row (research_topic,
    finding, hypothesis, contradiction, manifestation_adjudication,
    research_queue_item, media_episode) with its links as `relationships`
  * each computed CANDIDATE pair -> one manifestation_adjudication entity and a
    case -> case `candidate_duplicate_of` edge whose weak match_basis keeps it
    a candidate in the Hub
  * each master case            -> one case_report entity (about_case)

Writes `exports/federation/{sources,entities,relationships,observations}.jsonl`
+ a Hub-conformant `manifest.json` (federation_export_manifest). Dependency-light
(stdlib only), consistent with the rest of OVNIS.

Deterministic IDs: `src_/ent_/rel_/obs_` + sha256(key)[:32], so the same case
always maps to the same federation id.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from generate_case_report import REPORT_VERSION, build_reports, git_head
from prii_export_utils import fid as _fid
from prii_export_utils import norm as _norm
from prii_export_utils import sha256 as _sha256
from validate_research_ledgers import CANDIDATES_KIND, LEDGERS, load_research

REPO_ROOT = Path(__file__).resolve().parent.parent
PRODUCER = "ovnis-pr"
CONTRACT_VERSION = "1.0.0"
PRODUCER_SCRIPT = "scripts/federation_export.py"

# evidence_tier -> confidence
TIER_CONFIDENCE = {"T1": 0.9, "T2": 0.7, "T3": 0.5, "T4": 0.3}


def _iso(value: str | None, fallback: str) -> str:
    if value:
        return value
    return fallback


def _lineage(phase: str, inputs: list[str]) -> dict[str, Any]:
    return {
        "producer_script": PRODUCER_SCRIPT,
        "producer_phase": phase,
        "source_inputs": inputs,
        "extraction_method": "deterministic_case_projection",
    }


# Additive FEDERATION_EPISTEMIC_STATE_CONTRACT_V1 declaration (thehub-pr,
# candidate; vendored at schemas/federation_epistemic_state.v1.schema.json).
# Only what OVNIS can truthfully assert is declared: case records and their
# sources are CURATED documentary evidence. Geometry precision is deliberately
# NOT declared — the ledger does not record how case coordinates were derived
# (docs/ROAD_TO_100.md item 5), so the Hub fails closed to UNKNOWN.
EVIDENCE_STATE_CONTRACT = "federation-evidence-state-v1"
_TEMPORAL_PRECISION = {"year": "YEAR_ONLY", "month": "MONTH_YEAR", "day": "DATE_ONLY", "unknown": "UNKNOWN"}


def _evidence_state(**fields: Any) -> dict[str, Any]:
    return {"contract": EVIDENCE_STATE_CONTRACT, "data_stage": "CANONICAL", "epistemic_class": "CURATED", **fields}


def _temporal_precision(case: dict[str, Any], date_precision: str) -> str:
    """Resolution of what the source reports: a full date with a reported
    local time is minute-resolved; everything else keeps its date precision."""
    if date_precision == "day" and case.get("time_local"):
        return "EXACT_TIMESTAMP"
    return _TEMPORAL_PRECISION.get(date_precision, "UNKNOWN")


def _case_narrative(case: dict[str, Any], case_key: Any) -> dict[str, Any]:
    """The case's own identifier and narrative, for timeline and case views.

    Only what the ledger holds is copied: a missing description or citation is
    omitted, never filled with a placeholder.
    """
    fields = {"case_id": case_key}
    for key in ("description", "source_citation"):
        value = case.get(key)
        if isinstance(value, str) and value.strip():
            fields[key] = value
    return fields


def _observed_at(case: dict[str, Any], fallback: str) -> tuple:
    """Hub-required tz-aware observed_at from date_local/time_local.

    Historical cases carry year / year-month / full-date precision; the
    timestamp is floored to the period start (AST, UTC-4) and the true
    precision is preserved alongside it.
    """
    import re

    date = str(case.get("date_local") or "")
    if re.fullmatch(r"\d{4}", date):
        date, precision = f"{date}-01-01", "year"
    elif re.fullmatch(r"\d{4}-\d{2}", date):
        date, precision = f"{date}-01", "month"
    elif re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
        precision = "day"
    else:
        return fallback, "unknown"
    time = str(case.get("time_local") or "00:00")
    return f"{date}T{time}:00-04:00", precision


def build_streams(cases: list[dict[str, Any]], now: str) -> dict[str, list[dict[str, Any]]]:
    sources: dict[str, dict[str, Any]] = {}
    entities: dict[str, dict[str, Any]] = {}
    relationships: dict[str, dict[str, Any]] = {}
    observations: dict[str, dict[str, Any]] = {}
    src_inputs = ["data/master/master_cases.jsonl"]

    for case in cases:
        if case.get("record_type") != "master":
            continue
        case_key = case.get("case_id") or case.get("record_id")
        synthetic = (case.get("source_family") == "placeholder")
        created = _iso(case.get("created_at"), now)
        evidence_tier = case.get("evidence_tier")
        confidence = TIER_CONFIDENCE.get(evidence_tier, 0.3) if isinstance(evidence_tier, str) else 0.3

        # --- source ---
        source_url = case.get("source_url") or ""
        source_key = case.get("source_hash") or f"{case.get('source_family')}|{source_url}"
        source_id = _fid("src", source_key)
        if source_id not in sources:
            src_row = {
                "source_id": source_id,
                "source_type": case.get("source_family") or "unknown",
                "source_name": case.get("source_citation") or source_url or "unknown",
                "confidence": confidence,
                "lineage": _lineage("SOURCE_REGISTRY", src_inputs),
                "evidence_state": _evidence_state(),
                "synthetic": synthetic,
                "created_at": created,
                "extracted_at": now,
            }
            # satisfy anyOf(source_url | source_ref)
            if source_url and source_url not in ("offline-placeholder",):
                src_row["source_url"] = source_url
            else:
                src_row["source_ref"] = source_key
            sources[source_id] = src_row

        # --- case entity ---
        ent_id = _fid("ent", "case", case_key)
        entities[ent_id] = {
            "entity_id": ent_id,
            "source_id": source_id,
            "name": case.get("location_name") or case_key,
            "normalized_name": _norm(case.get("location_name") or case_key),
            "entity_type": "uap_case",
            "jurisdiction": "PR",
            "external_ids": {"ovnis_case_id": case_key},
            # Read by the Hub's case ledger and timeline views.
            "attributes": {
                **_case_narrative(case, case_key),
                **{k: v for k, v in (("object_type", case.get("object_type")),
                                      ("event_date", case.get("date_local")),
                                      ("evidence_tier", case.get("evidence_tier"))) if v},
            },
            "confidence": confidence,
            "lineage": _lineage("CASE_ENTITY", src_inputs),
            "evidence_state": _evidence_state(),
            "synthetic": synthetic,
            "created_at": created,
            "extracted_at": now,
        }

        # --- municipality entity + located_in ---
        muni = case.get("municipality")
        if muni:
            muni_id = _fid("ent", "municipality", _norm(muni))
            entities.setdefault(muni_id, {
                "entity_id": muni_id,
                "source_id": source_id,
                "name": muni,
                "normalized_name": _norm(muni),
                "entity_type": "municipality",
                "jurisdiction": "PR",
                "confidence": 0.95,
                "lineage": _lineage("MUNICIPALITY_ENTITY", src_inputs),
                "evidence_state": _evidence_state(),
                "synthetic": synthetic,
                "created_at": created,
                "extracted_at": now,
            })
            rel_id = _fid("rel", ent_id, "located_in", muni_id)
            relationships[rel_id] = _relationship(rel_id, source_id, ent_id, muni_id,
                                                  "located_in", confidence, synthetic, created, now)

        # --- reported_by (case -> source-as-entity) ---
        # model the source as an entity too so the edge is entity->entity
        source_ent_id = _fid("ent", "source", source_key)
        entities.setdefault(source_ent_id, {
            "entity_id": source_ent_id,
            "source_id": source_id,
            "name": case.get("source_citation") or source_url or "unknown source",
            "normalized_name": _norm(case.get("source_citation") or source_url or "unknown source"),
            "entity_type": "source_document",
            "jurisdiction": "PR",
            "confidence": confidence,
            "lineage": _lineage("SOURCE_ENTITY", src_inputs),
            "evidence_state": _evidence_state(),
            "synthetic": synthetic,
            "created_at": created,
            "extracted_at": now,
        })
        rel_id = _fid("rel", ent_id, "reported_by", source_ent_id)
        relationships[rel_id] = _relationship(rel_id, source_id, ent_id, source_ent_id,
                                              "reported_by", confidence, synthetic, created, now)

        # --- duplicate_of ---
        matched = case.get("matched_case_id")
        if matched and case.get("dedupe_status") == "duplicate":
            target = _fid("ent", "case", matched)
            rel_id = _fid("rel", ent_id, "duplicate_of", target)
            relationships[rel_id] = _relationship(rel_id, source_id, ent_id, target,
                                                  "duplicate_of", confidence, synthetic, created, now)

        # --- observation ---
        obs_id = _fid("obs", "case", case_key)
        observed_at, date_precision = _observed_at(case, created)
        observations[obs_id] = {
            "observation_id": obs_id,
            "entity_id": ent_id,
            "source_id": source_id,
            "observation_type": "uap_case",
            "observed_at": observed_at,
            "date_precision": date_precision,
            "date_local": case.get("date_local"),
            "time_local": case.get("time_local"),
            "location_name": case.get("location_name"),
            "municipality": case.get("municipality"),
            "latitude": case.get("latitude"),
            "longitude": case.get("longitude"),
            # Nested for the Hub's correlate_observations() municipality
            # co-location join (row["location"]["municipality"], etc.),
            # which the flat top-level fields above don't satisfy.
            "location": {
                "municipality": case.get("municipality"),
                "lat": case.get("latitude"),
                "lon": case.get("longitude"),
            },
            "environment": case.get("environment"),
            "object_type": case.get("object_type"),
            "witness_type": case.get("witness_type"),
            "witness_count": case.get("witness_count"),
            "evidence_tier": case.get("evidence_tier"),
            "attributes": _case_narrative(case, case_key),
            "confidence": confidence,
            "lineage": _lineage("OBSERVATION", src_inputs),
            # A case record documents a source-reported sighting: the phenomenon
            # was reported present. That is not instrument verification; the
            # CURATED class and the source state carry that distinction.
            "evidence_state": _evidence_state(
                observation_state="OBSERVED_PRESENT",
                temporal_precision=_temporal_precision(case, date_precision),
            ),
            "synthetic": synthetic,
            "created_at": created,
            "extracted_at": now,
        }

    return {
        "sources": list(sources.values()),
        "entities": list(entities.values()),
        "relationships": list(relationships.values()),
        "observations": list(observations.values()),
    }


# --- research ledgers ------------------------------------------------------

RESEARCH_INPUT = "data/research"
# The research ledger and each generator are cited as the source of the rows
# they produce, so every research row's provenance names where it came from.
_RESEARCH_SOURCES = {
    "ledger": ("research_ledger", "OVNIS research ledgers (curated)", "ovnis-pr:data/research", "CURATED"),
    "pairs": ("computed_derivation", "OVNIS duplicate-manifestation candidate pairs",
              "ovnis-pr:scripts/dedupe_candidates.py#master-pairs", "COMPUTED"),
    "reports": ("computed_derivation", "OVNIS case reports", "ovnis-pr:scripts/generate_case_report.py", "COMPUTED"),
}
# Hub-side weak basis: a pair from co-occurring date and place stays CANDIDATE.
CANDIDATE_MATCH_BASIS = "co_occurrence"
HYPOTHESIS_BASIS = "hypothesis under falsification test (OVNIS research ledger)"
_TITLE_FIELDS = {
    "research_topic": "title", "finding": "statement", "hypothesis": "statement", "contradiction": "contradiction_id",
    "manifestation_adjudication": "adjudication_id", "research_queue_item": "question", "media_episode": "title",
}


def _research_evidence_state(kind: str, row: dict[str, Any]) -> dict[str, Any]:
    if kind == "finding":
        state = {"data_stage": "FINDING", "epistemic_class": row.get("epistemic_class") or "CURATED"}
        if row.get("epistemic_class") == "INTERPRETIVE":
            state["interpretation_basis"] = row.get("interpretation_basis")
        return _evidence_state(**state)
    if kind == "hypothesis":
        return _evidence_state(data_stage="INTERPRETATION", epistemic_class="INTERPRETIVE",
                               interpretation_basis=HYPOTHESIS_BASIS)
    return _evidence_state()


def build_research_streams(
    cases: list[dict[str, Any]],
    research: dict[str, list[dict[str, Any]]],
    now: str,
    *,
    reports: list[dict[str, Any]] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """Typed research rows for the existing entities/relationships/sources streams.

    Only records the ledgers hold are emitted; empty ledgers emit nothing. Links
    to unknown cases are dropped rather than pointed at invented entities (the
    research validator rejects them before export in CI).
    """
    masters = {str(c.get("case_id") or c.get("record_id")): c for c in cases if c.get("record_type") == "master"}
    case_entity = {key: _fid("ent", "case", key) for key in masters}
    synthetic_case = {key: c.get("source_family") == "placeholder" for key, c in masters.items()}
    sources: dict[str, dict[str, Any]] = {}
    entities: list[dict[str, Any]] = []
    relationships: dict[str, dict[str, Any]] = {}

    def source_for(name: str) -> str:
        source_type, title, ref, klass = _RESEARCH_SOURCES[name]
        source_id = _fid("src", "ovnis-research", name)
        sources.setdefault(source_id, {
            "source_id": source_id, "source_type": source_type, "source_name": title, "source_ref": ref,
            "confidence": 0.9, "lineage": _lineage("RESEARCH_SOURCE", [RESEARCH_INPUT]),
            "evidence_state": _evidence_state(epistemic_class=klass), "synthetic": False,
            "created_at": now, "extracted_at": now,
        })
        return source_id

    def link(source_id: str, src: str, tgt: str | None, rtype: str, synthetic: bool, **extra: Any) -> None:
        if not tgt:
            return
        rel_id = _fid("rel", src, rtype, tgt)
        row = _relationship(rel_id, source_id, src, tgt, rtype, 0.9, synthetic, now, now)
        row["lineage"] = _lineage("RESEARCH_RELATIONSHIP", [RESEARCH_INPUT])
        row.update(extra)
        relationships[rel_id] = row

    def case_targets(row: dict[str, Any]) -> list[str]:
        keys = list(row.get("case_ids") or [])
        refs = list(row.get("source_refs") or [])
        refs += [row[side].get("source_ref") for side in ("claim_a", "claim_b") if isinstance(row.get(side), dict)]
        keys += [ref["case_id"] for ref in refs if isinstance(ref, dict) and ref.get("case_id")]
        return [case_entity[k] for k in dict.fromkeys(keys) if k in case_entity]

    # Created only when a curated ledger holds a record, so empty ledgers emit no source row.
    ledger_source = source_for("ledger") if any(research.get(kind) for kind in LEDGERS) else ""
    for kind, (_, id_field) in LEDGERS.items():
        for row in research.get(kind) or []:
            record_id = str(row[id_field])
            ent_id = _fid("ent", kind, record_id)
            title = str(row.get(_TITLE_FIELDS[kind]) or record_id)
            entities.append({
                "entity_id": ent_id, "source_id": ledger_source, "name": title[:200],
                "normalized_name": _norm(title[:200]), "entity_type": kind, "jurisdiction": "PR",
                "external_ids": {f"ovnis_{id_field}": record_id},
                "attributes": {k: v for k, v in row.items() if k != id_field},
                "confidence": 0.9, "lineage": _lineage(f"RESEARCH_{kind.upper()}", [RESEARCH_INPUT]),
                "evidence_state": _research_evidence_state(kind, row), "synthetic": False,
                "created_at": row.get("recorded_at") or now, "extracted_at": now,
            })
            for target in case_targets(row):
                link(ledger_source, ent_id, target, "about_case", False)
            for topic in row.get("topic_ids") or []:
                link(ledger_source, ent_id, _fid("ent", "research_topic", topic), "in_topic", False)
            for finding in row.get("finding_ids") or []:
                rtype = "tests" if kind == "hypothesis" else "mentions"
                link(ledger_source, ent_id, _fid("ent", "finding", finding), rtype, False)
            for ref in row.get("source_refs") or []:
                case = masters.get(str(ref.get("case_id"))) if isinstance(ref, dict) else None
                if case is not None:
                    source_key = case.get("source_hash") or f"{case.get('source_family')}|{case.get('source_url') or ''}"
                    link(ledger_source, ent_id, _fid("ent", "source", source_key), "cites", False,
                         locator=ref.get("locator"))
            if kind == "manifestation_adjudication" and row.get("status") == "SAME_EVENT":
                a, b = case_entity.get(row["case_a"]), case_entity.get(row["case_b"])
                if a and b:
                    link(ledger_source, a, b, "same_event_as", False, adjudication_id=record_id)

    decided = {frozenset((r.get("case_a"), r.get("case_b"))) for r in research.get("manifestation_adjudication") or []}
    pairs = [r for r in research.get(CANDIDATES_KIND) or [] if frozenset((r["case_a"], r["case_b"])) not in decided]
    if pairs:
        pair_source = source_for("pairs")
        for row in pairs:
            a, b = case_entity.get(row["case_a"]), case_entity.get(row["case_b"])
            if not (a and b):
                continue
            synthetic = synthetic_case[row["case_a"]] or synthetic_case[row["case_b"]]
            ent_id = _fid("ent", "manifestation_adjudication", row["adjudication_id"])
            entities.append({
                "entity_id": ent_id, "source_id": pair_source, "name": f"{row['case_a']} / {row['case_b']}",
                "normalized_name": _norm(f"{row['case_a']} {row['case_b']}"), "entity_type": "manifestation_adjudication",
                "jurisdiction": "PR", "external_ids": {"ovnis_adjudication_id": row["adjudication_id"]},
                "attributes": {k: v for k, v in row.items() if k != "adjudication_id"},
                "confidence": 0.5, "lineage": _lineage("RESEARCH_MANIFESTATION_CANDIDATE", [RESEARCH_INPUT]),
                "evidence_state": _evidence_state(data_stage="COMPUTATION", epistemic_class="COMPUTED"),
                "synthetic": synthetic, "created_at": now, "extracted_at": now,
            })
            link(pair_source, ent_id, a, "about_case", synthetic)
            link(pair_source, ent_id, b, "about_case", synthetic)
            link(pair_source, a, b, "candidate_duplicate_of", synthetic,
                 match_basis=CANDIDATE_MATCH_BASIS, adjudication_id=row["adjudication_id"],
                 evidence_state=_evidence_state(data_stage="COMPUTATION", epistemic_class="COMPUTED"))

    if reports:
        report_source = source_for("reports")
        for report in reports:
            key = report["case_id"]
            if key not in case_entity:
                continue
            ent_id = _fid("ent", "case_report", key)
            entities.append({
                "entity_id": ent_id, "source_id": report_source, "name": f"Case report {key}",
                "normalized_name": _norm(f"case report {key}"), "entity_type": "case_report", "jurisdiction": "PR",
                "external_ids": {"ovnis_report_id": report["report_id"], "ovnis_case_id": key},
                "attributes": {"report_version": REPORT_VERSION, "report": report},
                "confidence": 0.9, "lineage": _lineage("CASE_REPORT", ["data/master/master_cases.jsonl", RESEARCH_INPUT]),
                "evidence_state": _evidence_state(data_stage="REPORT", epistemic_class="COMPUTED"),
                "synthetic": synthetic_case[key], "created_at": now, "extracted_at": now,
            })
            link(report_source, ent_id, case_entity[key], "about_case", synthetic_case[key])

    return {"sources": list(sources.values()), "entities": entities, "relationships": list(relationships.values())}


def merge_streams(base: dict[str, list[dict[str, Any]]], extra: dict[str, list[dict[str, Any]]]) -> dict[str, list[dict[str, Any]]]:
    return {stream: rows + list(extra.get(stream, [])) for stream, rows in base.items()}


def _relationship(rel_id, source_id, src_ent, tgt_ent, rtype, confidence, synthetic, created, now):
    return {
        "relationship_id": rel_id,
        "source_id": source_id,
        "source_entity_id": src_ent,
        "target_entity_id": tgt_ent,
        "relationship_type": rtype,
        "evidence_source_id": source_id,
        "confidence": confidence,
        "lineage": _lineage("RELATIONSHIP", ["data/master/master_cases.jsonl"]),
        "evidence_state": _evidence_state(),
        "synthetic": synthetic,
        "created_at": created,
        "extracted_at": now,
    }


STREAM_SCHEMA = {
    "sources": "federation_source.schema.json",
    "entities": "federation_entity.schema.json",
    "relationships": "federation_relationship.schema.json",
    "observations": "federation_observation.schema.json",
}


def write_package(streams: dict[str, list[dict[str, Any]]], out_dir: Path, mode: str, now: str) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    files = []
    for stream in ("sources", "entities", "relationships", "observations"):
        rows = streams[stream]
        if not rows:
            continue
        fpath = out_dir / f"{stream}.jsonl"
        fpath.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in rows))
        files.append({
            "filename": f"{stream}.jsonl",
            "stream": stream,
            "record_count": len(rows),
            "sha256": _sha256(fpath),
            "schema_id": STREAM_SCHEMA[stream],
        })
    digest = hashlib.sha256(
        ("|".join(f"{f['filename']}:{f['sha256']}" for f in files) + f"|{mode}").encode()
    ).hexdigest()[:32]
    manifest = {
        "package_id": f"pkg_{digest}",
        "producer": PRODUCER,
        "export_contract_version": CONTRACT_VERSION,
        "mode": mode,
        "created_at": now,
        "extracted_at": now,
        "federation": {"producer_repo": PRODUCER, "hub_parent": "thehub-pr"},
        "files": files,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True))
    return out_dir / "manifest.json"


def main() -> int:
    ap = argparse.ArgumentParser(description="Export OVNIS cases as PRII canonical streams.")
    ap.add_argument("--ledger", default=str(REPO_ROOT / "data/master/master_cases.jsonl"))
    ap.add_argument("--out", default=str(REPO_ROOT / "exports/federation"))
    ap.add_argument("--mode", default="test", choices=["test", "production"])
    ap.add_argument("--research-dir", default=str(REPO_ROOT / RESEARCH_INPUT))
    args = ap.parse_args()

    cases = [json.loads(line) for line in Path(args.ledger).read_text().splitlines() if line.strip()]
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    research = load_research(Path(args.research_dir))
    reports = build_reports(cases, research, master_path=Path(args.ledger), research_dir=Path(args.research_dir),
                            created_at=now, git_sha=git_head())
    streams = merge_streams(build_streams(cases, now), build_research_streams(cases, research, now, reports=reports))

    if args.mode == "production":
        synthetic = [r for s in streams.values() for r in s if r.get("synthetic")]
        if synthetic:
            print(f"FAIL — {len(synthetic)} synthetic rows are not allowed in production mode")
            return 1

    manifest_path = write_package(streams, Path(args.out), args.mode, now)
    counts = {k: len(v) for k, v in streams.items()}
    print(f"wrote {manifest_path} — {counts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
