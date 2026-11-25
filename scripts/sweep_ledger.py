#!/usr/bin/env python3
"""Source sweep ledger and duplicate gate for new-case collection.

Keeps recurring searches from re-covering ground that is already worked, and keeps a new
candidate from entering the log twice. It records and reports; it never merges, promotes or
edits a case, and it never writes to the master ledger.

Files (all under data/reference/, all curator-maintained CSV):

    source_sweep_ledger.csv   one row per source: how it is swept, what the log already holds
                              from it, and how far a sweep has been verified
    sweep_query_log.csv       one row per search run, so the same query is not run twice
    known_case_index.csv      lookup keys (date, place, normalized source URLs) for every case in
                              the working Case Log workbook; the duplicate gate reads it

Commands:

    check    place a candidate (URL, date, place) against the known index and the master ledger
    status   list what to sweep next and what has never been verified
    record   record a completed sweep of a source (verified-through point, date, note)
    query    check whether a search was already run, or log one that was
    refresh  rebuild the known index and the ledger's computed columns from a Case Log workbook

The check command distinguishes EXACT_REPORT, IDENTITY_CONFLICT, SHARED_DOCUMENT,
POSSIBLE_DUPLICATE, INSUFFICIENT_IDENTITY, COMPARISON_UNAVAILABLE and NO_KNOWN_MATCH.
No verdict authorizes promotion.

A possible duplicate is a prompt for review, not a decision: similarity never decides identity
(docs/RESEARCH_LEDGERS.md). Near-duplicates with real differences stay as separate cases.

``refresh`` needs openpyxl; every other command uses only the standard library.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import sys
import tempfile
import unicodedata
from collections import defaultdict
from contextlib import ExitStack
from datetime import date, timedelta
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))

from dedupe_candidates import LOCATION_TEXT_RATIO, date_relation, iter_jsonl  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
LEDGER_PATH = REPO_ROOT / "data" / "reference" / "source_sweep_ledger.csv"
QUERY_LOG_PATH = REPO_ROOT / "data" / "reference" / "sweep_query_log.csv"
INDEX_PATH = REPO_ROOT / "data" / "reference" / "known_case_index.csv"
MASTER_PATH = REPO_ROOT / "data" / "master" / "master_cases.jsonl"

LEDGER_COLUMNS = [
    "source",
    "category",
    "website",
    "kind",
    "state",
    "access",
    "cases_logged",
    "refs_logged",
    "oldest_logged_event",
    "newest_logged_event",
    "highest_item_id",
    "verified_through",
    "last_swept",
    "next_action",
    "notes",
]
COMPUTED_COLUMNS = (
    "cases_logged",
    "refs_logged",
    "oldest_logged_event",
    "newest_logged_event",
    "highest_item_id",
)
INDEX_COLUMNS = [
    "case_id",
    "date_local",
    "date_text",
    "municipality",
    "location_name",
    "object_type",
    "primary_url_key",
    "source_keys",
    "source_names",
]
QUERY_COLUMNS = [
    "run_date",
    "source_or_engine",
    "query",
    "language",
    "scope",
    "results_reviewed",
    "new_cases_found",
    "notes",
]

KINDS = ("live", "static")
# forward: live collection, sweep only items newer than the verified point.
# closed: collection swept in full and not expected to change.
# citation_only: specific pages are cited, but the source was never swept as a collection.
# not_started: a collection-level sweep is wanted and has not been done.
# An empty state means unclassified.
STATES = ("forward", "closed", "citation_only", "not_started")
ACCESS = ("open", "blocked_automated", "manual_only", "unknown")

# A municipality value that does not name a place never anchors a match.
GENERIC_PLACES = {
    "",
    "unknown",
    "island-wide",
    "island wide",
    "puerto rico",
    "pr",
    "various",
    "offshore",
}

PATH_ID_KEYS = {
    "nuforc": re.compile(r"^nuforc:(\d+)$"),
    "ufosighting.report": re.compile(r"^ufosighting\.report:(\d+)$"),
}

_TRACKING_PARAMS = re.compile(r"^(utm_.*|fbclid|gclid|mc_cid|mc_eid|m|spref)$", re.IGNORECASE)
_WAYBACK = re.compile(r"^https?://(?:web\.)?archive\.org/web/\d+[a-z_]*/(.+)$", re.IGNORECASE)
_MONTHS = {
    name: i + 1
    for i, name in enumerate(
        [
            "january",
            "february",
            "march",
            "april",
            "may",
            "june",
            "july",
            "august",
            "september",
            "october",
            "november",
            "december",
        ]
    )
}


# --------------------------------------------------------------------------- normalization


def strip_accents(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))


def _on_domain(host: str, domain: str) -> bool:
    """True when ``host`` is ``domain`` or one of its subdomains, never a look-alike."""
    return host == domain or host.endswith("." + domain)


def url_key(value: Any) -> str:
    """A stable identity key for a source URL, or "" when the value is not a URL.

    Wayback wrappers are unwrapped to the original. Scheme, ``www.``, trailing slashes,
    ``index.html``, fragments and tracking parameters do not change the key. Three sources
    are keyed by their own record id so a changed slug or URL style still matches:
    NUFORC (``nuforc:79425``), ufosighting.report (``ufosighting.report:13290``) and
    UFO-Hunters (``ufo-hunters:<24 hex>``).
    """
    text = str(value or "").strip()
    if not text:
        return ""
    wrapped = _WAYBACK.match(text)
    if wrapped:
        text = wrapped.group(1)
    if "://" not in text:
        if re.match(r"^[\w-]+(\.[\w-]+)+(/|$)", text):
            text = "https://" + text
        else:
            return ""
    parts = urlsplit(text)
    host = parts.netloc.rsplit("@", 1)[-1].split(":")[0].lower()
    if host.startswith("www."):
        host = host[4:]
    if "." not in host:
        return ""
    path = parts.path or ""
    if _on_domain(host, "nuforc.org"):
        found = re.search(r"(?:^|[?&])id=(\d+)", parts.query) or re.search(r"/S(\d+)\.html?$", path)
        if found:
            return f"nuforc:{int(found.group(1))}"
    if _on_domain(host, "ufosighting.report"):
        found = re.match(r"^/sighting/(\d+)", path)
        if found:
            return f"ufosighting.report:{int(found.group(1))}"
    if _on_domain(host, "ufo-hunters.com"):
        found = re.search(r"/sightings/search/([0-9a-fA-F]{24})", path)
        if found:
            return f"ufo-hunters:{found.group(1).lower()}"
    path = re.sub(r"/index\.html?$", "", path).rstrip("/")
    query = "&".join(
        f"{k}={v}"
        for k, v in sorted(parse_qsl(parts.query, keep_blank_values=True))
        if not _TRACKING_PARAMS.match(k)
    )
    return host + path + (f"?{query}" if query else "")


def _month_number(token: str) -> int | None:
    """Month number for a full name or an unambiguous abbreviation ("Oct", "Sept")."""
    name = token.lower()
    if name in _MONTHS:
        return _MONTHS[name]
    if len(name) >= 3:
        hits = [number for full, number in _MONTHS.items() if full.startswith(name)]
        if len(hits) == 1:
            return hits[0]
    return None


def iso_date(text: Any) -> str:
    """The date a log entry records, as ``YYYY-MM-DD``, ``YYYY-MM`` or ``YYYY``, or "".

    Never finer than the text: "January 2011" stays ``2011-01`` and a range such as
    "1988-1991" is indexed by its first year. Text with no year gives "".
    """
    raw = str(text or "").strip()
    if re.fullmatch(r"\d{4}(-\d{2}(-\d{2})?)?", raw):
        return raw
    day = re.match(r"^([A-Za-z]+)\.?\s+(\d{1,2}),\s*(\d{4})\b", raw)
    if day and (number := _month_number(day.group(1))):
        return f"{int(day.group(3)):04d}-{number:02d}-{int(day.group(2)):02d}"
    month = re.match(r"^([A-Za-z]+)\.?\s+(\d{4})\b", raw)
    if month and (number := _month_number(month.group(1))):
        return f"{int(month.group(2)):04d}-{number:02d}"
    year = re.search(r"\b(1[6-9]\d\d|20\d\d)\b", raw)
    return year.group(1) if year else ""


def _places(value: Any) -> set[str]:
    """Municipality names in a field that may hold several ("Ponce / Guayanilla")."""
    parts = re.split(r"\s*(?:/|,|;|\band\b|\by\b)\s*", strip_accents(str(value or "")).casefold())
    return {p.strip() for p in parts if p.strip() and p.strip() not in GENERIC_PLACES}


def place_basis(a: dict[str, Any], b: dict[str, Any]) -> str | None:
    """The place two records share, or None. Two different municipalities never match."""
    munis_a, munis_b = _places(a.get("municipality")), _places(b.get("municipality"))
    if munis_a and munis_b:
        return "MUNICIPALITY" if munis_a & munis_b else None
    loc_a = " ".join(strip_accents(str(a.get("location_name") or "")).casefold().split())
    loc_b = " ".join(strip_accents(str(b.get("location_name") or "")).casefold().split())
    if loc_a and loc_b and SequenceMatcher(None, loc_a, loc_b).ratio() >= LOCATION_TEXT_RATIO:
        return "LOCATION_TEXT"
    return None


def date_agreement(a: str, b: str) -> str | None:
    """How two recorded dates agree, or None. Full dates one day apart count as adjacent."""
    relation = date_relation(a, b)
    if relation:
        return relation
    if len(a) == 10 and len(b) == 10:
        try:
            gap = abs((date.fromisoformat(a) - date.fromisoformat(b)).days)
        except ValueError:
            return None
        if gap == 1:
            return "ADJACENT_DAY"
    return None


# --------------------------------------------------------------------------- CSV helpers


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def write_csv(path: Path, columns: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", newline="", encoding="utf-8", dir=path.parent, delete=False
        ) as fh:
            temporary = Path(fh.name)
            writer = csv.DictWriter(
                fh, fieldnames=columns, lineterminator="\n", extrasaction="ignore"
            )
            writer.writeheader()
            for row in rows:
                writer.writerow({c: ("" if row.get(c) is None else row.get(c)) for c in columns})
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _sorted_ledger(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return sorted(rows, key=lambda r: strip_accents(r["source"]).casefold())


# --------------------------------------------------------------------------- duplicate gate


def _known_records(index_path: Path, master_path: Path) -> list[dict[str, Any]]:
    known: list[dict[str, Any]] = []
    for row in read_csv(index_path):
        known.append(
            {
                "dataset": "known_case_index",
                "case_id": row["case_id"],
                "date_local": row["date_local"],
                "municipality": row["municipality"],
                "location_name": row["location_name"],
                "keys": {k for k in row["source_keys"].split("|") if k},
            }
        )
    for row in iter_jsonl(master_path):
        if row.get("record_type") != "master":
            continue
        key = url_key(row.get("source_url"))
        known.append(
            {
                "dataset": "master_cases",
                "case_id": row.get("case_id") or row.get("record_id"),
                "date_local": str(row.get("date_local") or ""),
                "municipality": row.get("municipality") or "",
                "location_name": row.get("location_name") or "",
                "keys": {key} if key else set(),
            }
        )
    return known


_RELATION_ORDER = {"IDENTICAL_RECORDED_DATE": 0, "ADJACENT_DAY": 1, "COMPATIBLE_PRECISION": 2}


def check_candidate(candidate: dict[str, Any], known: list[dict[str, Any]]) -> dict[str, Any]:
    """Place one candidate against the known records. Pure; reads nothing from disk."""
    raw_urls = candidate.get("urls") or candidate.get("url") or candidate.get("source_url") or []
    urls = [raw_urls] if isinstance(raw_urls, str) else list(raw_urls)
    keys = {k for k in (url_key(u) for u in urls) if k}
    cand_date = iso_date(candidate.get("date") or candidate.get("date_local"))
    cand_place = {
        "municipality": candidate.get("municipality") or "",
        "location_name": candidate.get("location") or candidate.get("location_name") or "",
    }

    exact = [
        {
            "dataset": k["dataset"],
            "case_id": k["case_id"],
            "basis": ["SOURCE_URL_KEY"],
            "shared_keys": sorted(keys & k["keys"]),
        }
        for k in known
        if keys & k["keys"]
    ]
    result: dict[str, Any] = {
        "candidate": {
            "urls": urls,
            "url_keys": sorted(keys),
            "date_local": cand_date,
            **cand_place,
        },
    }
    if exact:
        # A document URL is not an individual report identity.
        native = re.compile(r"^(?:nuforc:\d+|ufosighting\.report:\d+|ufo-hunters:[0-9a-f]{24})$")
        report_matches = [m for m in exact if any(native.fullmatch(k) for k in m["shared_keys"])]
        if report_matches:
            conflict = any(
                (cand_date and rec["date_local"]
                 and not date_relation(cand_date, rec["date_local"]))
                or (_places(cand_place["municipality"]) and _places(rec["municipality"])
                    and not (_places(cand_place["municipality"]) & _places(rec["municipality"])))
                for rec in known
                if any(native.fullmatch(k) for k in keys & rec["keys"])
            )
            verdict = "IDENTITY_CONFLICT" if conflict else "EXACT_REPORT"
        else:
            verdict = "SHARED_DOCUMENT"
        result.update(verdict=verdict, matches=exact, match_count=len(exact))
        return result

    possible = []
    if cand_date:
        for rec in known:
            relation = date_agreement(cand_date, rec["date_local"])
            if not relation:
                continue
            place = place_basis(cand_place, rec)
            if place:
                possible.append(
                    {
                        "dataset": rec["dataset"],
                        "case_id": rec["case_id"],
                        "basis": [relation, place],
                        "date_local": rec["date_local"],
                    }
                )
    possible.sort(key=lambda m: (_RELATION_ORDER[m["basis"][0]], str(m["case_id"])))
    if possible:
        result.update(
            verdict="POSSIBLE_DUPLICATE", matches=possible, match_count=len(possible)
        )
    else:
        sufficient = bool(keys and cand_date and (
            _places(cand_place["municipality"]) or _places(cand_place["location_name"])
        ))
        result.update(
            verdict="NO_KNOWN_MATCH" if sufficient else "INSUFFICIENT_IDENTITY", matches=[]
        )
    return result


def cmd_check(args: argparse.Namespace) -> int:
    candidates: list[dict[str, Any]] = []
    if args.jsonl:
        candidates.extend(iter_jsonl(Path(args.jsonl)))
    if args.url or args.date or args.municipality or args.location:
        candidates.append(
            {
                "urls": args.url or [],
                "date": args.date,
                "municipality": args.municipality,
                "location": args.location,
            }
        )
    if not candidates:
        print("check: give --url/--date/--municipality or --jsonl", file=sys.stderr)
        return 2
    index_path, master_path = Path(args.index), Path(args.master)
    if not index_path.is_file() or not master_path.is_file():
        print(json.dumps({"verdict": "COMPARISON_UNAVAILABLE", "reason": "missing index or master"}))
        return 2
    try:
        with index_path.open(newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            if not set(INDEX_COLUMNS).issubset(reader.fieldnames or []):
                raise ValueError("invalid index header")
            rows = list(reader)
        ids = [row["case_id"] for row in rows]
        if not ids or any(not item or not item.strip() for item in ids):
            raise ValueError("empty index or case identifier")
        if len(ids) != len(set(ids)) or any(None in row or None in row.values() for row in rows):
            raise ValueError("duplicate index identifiers or malformed rows")
        known = _known_records(index_path, master_path)
        # Production CLI checks include all persistent intake ledgers. Explicit
        # fixture paths may supply their own additional comparison ledgers.
        extra_paths = [Path(value) for value in args.candidate_ledger]
        if master_path.resolve() == MASTER_PATH.resolve():
            data_root = master_path.parent.parent
            extra_paths.extend(
                data_root / name for name in (
                    "candidates/candidate_cases.jsonl",
                    "already_listed.jsonl",
                    "updates_new_evidence.jsonl",
                    "echoes_noise.jsonl",
                )
            )
        for path in dict.fromkeys(extra_paths):
            if not path.is_file():
                raise ValueError(f"missing intake ledger: {path.name}")
            for row in iter_jsonl(path):
                identity = row.get("record_id") or row.get("candidate_id")
                if not identity:
                    raise ValueError("missing intake record identity")
                key = url_key(row.get("source_url"))
                known.append(
                    {
                        "dataset": "persistent_intake",
                        "case_id": identity,
                        "date_local": str(row.get("date_local") or ""),
                        "municipality": row.get("municipality") or "",
                        "location_name": row.get("location_name") or "",
                        "keys": {key} if key else set(),
                    }
                )
    except (OSError, ValueError, TypeError, KeyError, AttributeError, csv.Error):
        print(json.dumps({"verdict": "COMPARISON_UNAVAILABLE", "reason": "invalid comparison input"}))
        return 2
    if not known:
        print(json.dumps({"verdict": "COMPARISON_UNAVAILABLE", "reason": "empty comparison"}))
        return 2
    results = []
    for number, candidate in enumerate(candidates):
        result = check_candidate(candidate, known)
        results.append(result)
        normalized = result["candidate"]
        known.append({
            "dataset": "current_batch",
            "case_id": f"batch:{number + 1}",
            "date_local": normalized["date_local"],
            "municipality": normalized["municipality"],
            "location_name": normalized["location_name"],
            "keys": set(normalized["url_keys"]),
        })
    json.dump(results if len(results) > 1 else results[0], sys.stdout, ensure_ascii=False, indent=2)
    print()
    if args.fail_on_match and any(r["verdict"] != "NO_KNOWN_MATCH" for r in results):
        return 1
    return 0


# --------------------------------------------------------------------------- ledger


def cmd_status(args: argparse.Namespace) -> int:
    rows = read_csv(Path(args.ledger))
    if not rows:
        print("status: ledger is empty or missing", file=sys.stderr)
        return 2
    counts: dict[str, int] = defaultdict(int)
    for row in rows:
        counts[row["state"] or "unclassified"] += 1
    summary = ", ".join(f"{name} {n}" for name, n in sorted(counts.items()))
    print(f"Sweep ledger: {len(rows)} sources ({summary})")

    today = date.fromisoformat(args.today) if args.today else date.today()
    cutoff = today - timedelta(days=args.stale_days)
    forward = sorted(
        (r for r in rows if r["state"] == "forward"),
        key=lambda r: (-int(r["refs_logged"] or 0), r["source"]),
    )
    print("\nForward sources (sweep only items newer than the verified point):")
    for row in forward:
        verified = row["verified_through"] or "UNVERIFIED"
        swept = row["last_swept"] or "never"
        stale = not row["last_swept"] or date.fromisoformat(row["last_swept"]) < cutoff
        if row["highest_item_id"]:
            logged = f"highest logged id #{row['highest_item_id']}"
        else:
            logged = f"newest logged event {row['newest_logged_event'] or '-'}"
        flag = "  <- due" if stale else ""
        access = "" if row["access"] in ("", "open", "unknown") else f" [{row['access']}]"
        print(f"  {row['source']}{access}: {logged}; verified {verified}; last swept {swept}{flag}")
    for title, state in (("Not started", "not_started"), ("Unclassified", "")):
        picked = [r for r in rows if r["state"] == state]
        if picked:
            print(f"\n{title}:")
            for row in picked:
                print(f"  {row['source']}")
    blocked = [r for r in rows if r["access"] == "blocked_automated"]
    if blocked:
        print("\nBlocked to automated fetching (load in a browser or use an export):")
        for row in blocked:
            print(f"  {row['source']}")
    return 0


def acquisition_receipt(args: argparse.Namespace, previous_frontier: str) -> str:
    """Validate a local evidence receipt; never infer success from a frontier string."""
    if not args.receipt:
        raise ValueError("acquisition receipt required")
    path = Path(args.receipt)
    raw = path.read_bytes()
    receipt = json.loads(raw)
    expected = {
        "source": args.source,
        "previous_frontier": previous_frontier,
        "verified_through": args.verified_through,
        "status": "success",
        "reconciliation": "complete",
        "sweep_date": args.date or date.today().isoformat(),
    }
    if not isinstance(receipt, dict) or any(receipt.get(k) != v for k, v in expected.items()):
        raise ValueError("receipt does not bind successful reconciled sweep")
    for field in ("execution_id", "interval_start", "configuration_sha256"):
        if not isinstance(receipt.get(field), str) or not receipt[field].strip():
            raise ValueError(f"missing receipt field: {field}")
    if not re.fullmatch(r"[0-9a-f]{64}", receipt["configuration_sha256"]):
        raise ValueError("invalid configuration digest")
    configuration = (path.parent / receipt["configuration_path"]).resolve()
    if not configuration.is_relative_to(path.parent.resolve()):
        raise ValueError("configuration outside receipt directory")
    if hashlib.sha256(configuration.read_bytes()).hexdigest() != receipt["configuration_sha256"]:
        raise ValueError("configuration hash mismatch")
    evidence = receipt.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        raise ValueError("missing acquisition evidence")
    for item in evidence:
        if not isinstance(item, dict):
            raise ValueError("invalid evidence entry")
        artifact = (path.parent / item["path"]).resolve()
        if not artifact.is_relative_to(path.parent.resolve()):
            raise ValueError("evidence outside receipt directory")
        if hashlib.sha256(artifact.read_bytes()).hexdigest() != item["sha256"]:
            raise ValueError("evidence hash mismatch")
    return hashlib.sha256(raw).hexdigest()


def cmd_record(args: argparse.Namespace) -> int:
    path = Path(args.ledger)
    rows = read_csv(path)
    match = [r for r in rows if r["source"] == args.source]
    if not match:
        if not args.add:
            print(
                f"record: no ledger row for {args.source!r}; use --add to create one",
                file=sys.stderr,
            )
            return 2
        row = {c: "" for c in LEDGER_COLUMNS}
        row.update(source=args.source, category=args.category or "", website=args.website or "")
        rows.append(row)
    else:
        row = match[0]
    if args.state is not None:
        if args.state not in STATES:
            print(f"record: state must be one of {', '.join(STATES)}", file=sys.stderr)
            return 2
        row["state"] = args.state
    if args.access is not None:
        if args.access not in ACCESS:
            print(f"record: access must be one of {', '.join(ACCESS)}", file=sys.stderr)
            return 2
        row["access"] = args.access
    if args.kind is not None:
        if args.kind not in KINDS:
            print(f"record: kind must be one of {', '.join(KINDS)}", file=sys.stderr)
            return 2
        row["kind"] = args.kind
    swept = args.date or date.today().isoformat()
    if args.verified_through is not None:
        try:
            digest = hashlib.sha256(Path(args.receipt).read_bytes()).hexdigest() if args.receipt else ""
            if digest and f"receipt_sha256={digest}" in row["notes"].split(" | "):
                prior = json.loads(Path(args.receipt).read_bytes())["previous_frontier"]
                acquisition_receipt(args, prior)
                print("receipt already recorded")
                return 0
            digest = acquisition_receipt(args, row["verified_through"])
            previous = row["verified_through"]
            if previous:
                before = re.fullmatch(r"#?(\d+)", previous)
                after = re.fullmatch(r"#?(\d+)", args.verified_through)
                if before and after:
                    if int(after.group(1)) <= int(before.group(1)):
                        raise ValueError("numeric frontier did not advance")
                else:
                    if date.fromisoformat(args.verified_through) <= date.fromisoformat(previous):
                        raise ValueError("date frontier did not advance")
            if row["last_swept"] and date.fromisoformat(swept) < date.fromisoformat(row["last_swept"]):
                raise ValueError("stale sweep date")
        except (OSError, ValueError, TypeError, KeyError, AttributeError):
            print("record: invalid or missing acquisition receipt", file=sys.stderr)
            return 2
        marker = f"receipt_sha256={digest}"
        if marker in row["notes"].split(" | "):
            print("receipt already recorded")
            return 0
        row["verified_through"] = args.verified_through
        row["last_swept"] = swept
        row["notes"] = (row["notes"] + " | " if row["notes"] else "") + marker
    if args.next_action is not None:
        row["next_action"] = args.next_action
    if args.note:
        row["notes"] = (row["notes"] + " | " if row["notes"] else "") + f"{swept}: {args.note}"
    write_csv(path, LEDGER_COLUMNS, _sorted_ledger(rows))
    print(f"recorded {args.source}")
    return 0


# --------------------------------------------------------------------------- query log


def _normalize_query(text: str) -> str:
    return " ".join(strip_accents(text).casefold().split())


def cmd_query(args: argparse.Namespace) -> int:
    path = Path(args.query_log)
    rows = read_csv(path)
    wanted = _normalize_query(args.text)
    prior = [
        r
        for r in rows
        if _normalize_query(r["query"]) == wanted
        and (not args.source or r["source_or_engine"].casefold() == args.source.casefold())
        and _normalize_query(r["language"]) == _normalize_query(args.language or "")
        and _normalize_query(r["scope"]) == _normalize_query(args.scope or "")
    ]
    if args.log:
        rows.append(
            {
                "run_date": args.date or date.today().isoformat(),
                "source_or_engine": args.source or "",
                "query": args.text,
                "language": args.language or "",
                "scope": args.scope or "",
                "results_reviewed": args.results or "",
                "new_cases_found": args.new or "",
                "notes": args.note or "",
            }
        )
        rows.sort(key=lambda r: (r["run_date"], r["source_or_engine"], r["query"]))
        write_csv(path, QUERY_COLUMNS, rows)
        print("logged")
        return 0
    today = date.fromisoformat(args.today) if args.today else date.today()
    recent = [
        r
        for r in prior
        if r["run_date"] and (today - date.fromisoformat(r["run_date"])).days <= args.within_days
    ]
    if recent:
        last = max(recent, key=lambda r: r["run_date"])
        print(
            f"ALREADY RUN {last['run_date']} on {last['source_or_engine'] or 'any source'}: "
            f"{last['results_reviewed'] or '?'} results reviewed, {last['new_cases_found'] or '?'} new"
        )
        return 1
    print(
        "not run within the window"
        + (f" (last run {max(r['run_date'] for r in prior)})" if prior else "")
    )
    return 0


# --------------------------------------------------------------------------- refresh


def _read_workbook(path: Path) -> dict[str, Any]:
    try:
        import openpyxl
    except ImportError:
        raise SystemExit("refresh needs openpyxl: python -m pip install openpyxl") from None
    workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    cases: list[dict[str, Any]] = []
    sources: list[dict[str, Any]] = []
    directory: dict[str, dict[str, Any]] = {}
    for sheet in workbook.worksheets:
        rows = sheet.iter_rows(values_only=True)
        header = next(rows, None)
        if not header:
            continue
        names = [str(h) if h is not None else "" for h in header]
        records = [
            dict(zip(names, row, strict=False)) for row in rows if any(v is not None for v in row)
        ]
        if "Case ID" in names and "Primary Link" in names:
            cases.extend(records)
        elif "Case ID" in names and "Link" in names and "Source" in names:
            sources.extend(records)
        elif "Source" in names and "Source Category" in names:
            for rec in records:
                directory[str(rec["Source"])] = rec
    workbook.close()
    if not cases or not sources:
        raise SystemExit(f"{path}: no case sheets or no Case Sources sheet found")
    return {"cases": cases, "sources": sources, "directory": directory}


def build_index_and_stats(
    data: dict[str, Any],
) -> tuple[list[dict[str, str]], dict[str, dict[str, str]]]:
    """The known-case index rows and each source's computed ledger columns."""
    cases = {str(c["Case ID"]): c for c in data["cases"]}
    keys_by_case: dict[str, set[str]] = defaultdict(set)
    names_by_case: dict[str, set[str]] = defaultdict(set)
    case_ids_by_source: dict[str, set[str]] = defaultdict(set)
    refs_by_source: dict[str, int] = defaultdict(int)
    ids_by_source: dict[str, list[int]] = defaultdict(list)

    for cid, case in cases.items():
        for column in ("Primary Link", "Archived Copy"):
            key = url_key(case.get(column))
            if key:
                keys_by_case[cid].add(key)
    for src in data["sources"]:
        cid, name = str(src["Case ID"]), str(src["Source"])
        refs_by_source[name] += 1
        case_ids_by_source[name].add(cid)
        names_by_case[cid].add(name)
        for column in ("Link", "Archived Copy"):
            key = url_key(src.get(column))
            if not key:
                continue
            keys_by_case[cid].add(key)
            for pattern in PATH_ID_KEYS.values():
                found = pattern.match(key)
                if found:
                    ids_by_source[name].append(int(found.group(1)))

    index: list[dict[str, str]] = []
    dates: dict[str, str] = {}
    for cid, case in cases.items():
        iso = iso_date(case.get("Date"))
        dates[cid] = iso
        primary = url_key(case.get("Primary Link"))
        index.append(
            {
                "case_id": cid,
                "date_local": iso,
                "date_text": str(case.get("Date") or ""),
                "municipality": str(case.get("Municipality") or ""),
                "location_name": str(case.get("Location") or ""),
                "object_type": str(case.get("Shape") or ""),
                "primary_url_key": primary,
                "source_keys": "|".join(sorted(keys_by_case[cid])),
                "source_names": "|".join(sorted(names_by_case[cid])),
            }
        )
    index.sort(key=lambda r: r["case_id"].casefold())

    stats: dict[str, dict[str, str]] = {}
    for name, ids in case_ids_by_source.items():
        dated = sorted(d for d in (dates.get(c, "") for c in ids) if d)
        stats[name] = {
            "cases_logged": str(len(ids)),
            "refs_logged": str(refs_by_source[name]),
            "oldest_logged_event": dated[0] if dated else "",
            "newest_logged_event": dated[-1] if dated else "",
            "highest_item_id": str(max(ids_by_source[name])) if ids_by_source[name] else "",
        }
    return index, stats


def cmd_refresh(args: argparse.Namespace) -> int:
    data = _read_workbook(Path(args.xlsx))
    index, stats = build_index_and_stats(data)
    write_csv(Path(args.index), INDEX_COLUMNS, index)

    ledger_path = Path(args.ledger)
    rows = read_csv(ledger_path)
    by_source = {r["source"]: r for r in rows}
    added: list[str] = []
    for name, computed in stats.items():
        if name not in by_source:
            directory = data["directory"].get(name, {})
            row = {c: "" for c in LEDGER_COLUMNS}
            row.update(
                source=name,
                category=str(directory.get("Source Category") or ""),
                website=str(directory.get("Website") or ""),
            )
            rows.append(row)
            by_source[name] = row
            added.append(name)
        by_source[name].update(computed)
    for name, row in by_source.items():
        if name not in stats:
            row.update({c: "" for c in COMPUTED_COLUMNS})
            row.update(cases_logged="0", refs_logged="0")
    write_csv(ledger_path, LEDGER_COLUMNS, _sorted_ledger(rows))
    print(
        f"index: {len(index)} cases; ledger: {len(rows)} sources ({len(added)} added, unclassified)"
    )
    for name in sorted(added):
        print(f"  added: {name}")
    return 0


# --------------------------------------------------------------------------- CLI


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--ledger", default=str(LEDGER_PATH))
    parser.add_argument("--index", default=str(INDEX_PATH))
    parser.add_argument("--master", default=str(MASTER_PATH))
    parser.add_argument("--query-log", default=str(QUERY_LOG_PATH))
    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser("check", help="place a candidate against the known cases")
    check.add_argument("--url", action="append", help="source URL (repeatable)")
    check.add_argument("--date", help="event date: ISO, or text such as 'October 5, 2026'")
    check.add_argument("--municipality")
    check.add_argument("--location")
    check.add_argument("--jsonl", help="batch file; one candidate object per line")
    check.add_argument("--candidate-ledger", action="append", default=[], help="extra intake ledger")
    check.add_argument(
        "--fail-on-match", action="store_true", help="exit 1 unless every verdict is NO_KNOWN_MATCH"
    )
    check.set_defaults(func=cmd_check)

    status = sub.add_parser("status", help="what to sweep next")
    status.add_argument("--stale-days", type=int, default=90)
    status.add_argument("--today", help="override today's date (YYYY-MM-DD)")
    status.set_defaults(func=cmd_status)

    record = sub.add_parser("record", help="record a completed sweep")
    record.add_argument("--source", required=True)
    record.add_argument(
        "--verified-through", help="newest item confirmed swept, in the source's own terms"
    )
    record.add_argument("--date", help="sweep date (default today)")
    record.add_argument("--receipt", help="local successful acquisition receipt JSON")
    record.add_argument("--state")
    record.add_argument("--access")
    record.add_argument("--kind")
    record.add_argument("--next-action")
    record.add_argument("--note")
    record.add_argument("--add", action="store_true", help="create the row if the source is new")
    record.add_argument("--category")
    record.add_argument("--website")
    record.set_defaults(func=cmd_record)

    query = sub.add_parser("query", help="check or log a search")
    query.add_argument("text", help="the search text")
    query.add_argument("--source", help="source or engine the search ran on")
    query.add_argument("--within-days", type=int, default=90)
    query.add_argument("--log", action="store_true", help="append a run instead of checking")
    query.add_argument("--language")
    query.add_argument("--scope")
    query.add_argument("--results", help="results reviewed")
    query.add_argument("--new", help="new cases found")
    query.add_argument("--note")
    query.add_argument("--date")
    query.add_argument("--today", help="override today's date (YYYY-MM-DD)")
    query.set_defaults(func=cmd_query)

    refresh = sub.add_parser(
        "refresh", help="rebuild the index and computed columns from a workbook"
    )
    refresh.add_argument(
        "--xlsx", required=True, help="Case Log workbook (decade sheets + Case Sources)"
    )
    refresh.set_defaults(func=cmd_refresh)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    # Exclusive lock files protect the entire read-modify-write operation.
    # A crash leaves a lock in place deliberately; an operator must reconcile it.
    paths = []
    if args.command in ("record", "refresh"):
        paths.append(Path(args.ledger).resolve())
    if args.command == "refresh":
        paths.append(Path(args.index).resolve())
    if args.command == "query" and args.log:
        paths.append(Path(args.query_log).resolve())
    with ExitStack() as stack:
        for path in sorted(set(paths)):
            path.parent.mkdir(parents=True, exist_ok=True)
            lock = path.with_name(path.name + ".lock")
            try:
                fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            except FileExistsError:
                print("ledger locked; reconcile existing writer before retrying", file=sys.stderr)
                return 2
            stack.callback(lock.unlink)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(str(os.getpid()) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
        return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
