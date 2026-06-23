#!/usr/bin/env python3
"""Project PRUFON case ledgers into the PRII federation canonical streams.

Maps the PRUFON case model onto the Hub's canonical contract:
  * each master case            -> one `entities` row  (entity_type=uap_case)
  * each master case            -> one `observations` row
  * each distinct municipality  -> one `entities` row  (entity_type=municipality)
  * each distinct source        -> one `sources` row
  * case -> source              -> one `relationships` row (reported_by)
  * case -> municipality        -> one `relationships` row (located_in)
  * case -> matched case        -> one `relationships` row (duplicate_of)

Writes `exports/federation/{sources,entities,relationships,observations}.jsonl`
+ a Hub-conformant `manifest.json` (federation_export_manifest). Dependency-light
(stdlib only), consistent with the rest of PRUFON.

Deterministic IDs: `src_/ent_/rel_/obs_` + sha256(key)[:32], so the same case
always maps to the same federation id.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
PRODUCER = "prufon-pr"
CONTRACT_VERSION = "1.0.0"
PRODUCER_SCRIPT = "scripts/federation_export.py"

# evidence_tier -> confidence
TIER_CONFIDENCE = {"T1": 0.9, "T2": 0.7, "T3": 0.5, "T4": 0.3}


def _fid(prefix: str, *parts: Any) -> str:
    digest = hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()[:32]
    return f"{prefix}_{digest}"


def _norm(name: str) -> str:
    return " ".join(str(name).strip().upper().split())


def _iso(value: Optional[str], fallback: str) -> str:
    if value:
        return value
    return fallback


def _lineage(phase: str, inputs: List[str]) -> Dict[str, Any]:
    return {
        "producer_script": PRODUCER_SCRIPT,
        "producer_phase": phase,
        "source_inputs": inputs,
        "extraction_method": "deterministic_case_projection",
    }


def build_streams(cases: List[Dict[str, Any]], now: str) -> Dict[str, List[Dict[str, Any]]]:
    sources: Dict[str, Dict[str, Any]] = {}
    entities: Dict[str, Dict[str, Any]] = {}
    relationships: Dict[str, Dict[str, Any]] = {}
    observations: Dict[str, Dict[str, Any]] = {}
    src_inputs = ["data/master/master_cases.jsonl"]

    for case in cases:
        if case.get("record_type") != "master":
            continue
        case_key = case.get("case_id") or case.get("record_id")
        synthetic = (case.get("source_family") == "placeholder")
        created = _iso(case.get("created_at"), now)
        confidence = TIER_CONFIDENCE.get(case.get("evidence_tier"), 0.3)

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
            "confidence": confidence,
            "lineage": _lineage("CASE_ENTITY", src_inputs),
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
        observations[obs_id] = {
            "observation_id": obs_id,
            "entity_id": ent_id,
            "source_id": source_id,
            "date_local": case.get("date_local"),
            "time_local": case.get("time_local"),
            "location_name": case.get("location_name"),
            "municipality": case.get("municipality"),
            "latitude": case.get("latitude"),
            "longitude": case.get("longitude"),
            "environment": case.get("environment"),
            "object_type": case.get("object_type"),
            "witness_type": case.get("witness_type"),
            "witness_count": case.get("witness_count"),
            "evidence_tier": case.get("evidence_tier"),
            "confidence": confidence,
            "lineage": _lineage("OBSERVATION", src_inputs),
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
        "synthetic": synthetic,
        "created_at": created,
        "extracted_at": now,
    }


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


STREAM_SCHEMA = {
    "sources": "federation_source.schema.json",
    "entities": "federation_entity.schema.json",
    "relationships": "federation_relationship.schema.json",
    "observations": "federation_observation.schema.json",
}


def write_package(streams: Dict[str, List[Dict[str, Any]]], out_dir: Path, mode: str, now: str) -> Path:
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
    ap = argparse.ArgumentParser(description="Export PRUFON cases as PRII canonical streams.")
    ap.add_argument("--ledger", default=str(REPO_ROOT / "data/master/master_cases.jsonl"))
    ap.add_argument("--out", default=str(REPO_ROOT / "exports/federation"))
    ap.add_argument("--mode", default="test", choices=["test", "production"])
    args = ap.parse_args()

    cases = [json.loads(line) for line in Path(args.ledger).read_text().splitlines() if line.strip()]
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    streams = build_streams(cases, now)

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
