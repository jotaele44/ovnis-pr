"""The `source_monitors` export stream (thehub-pr ADR 0013).

One row per source in data/reference/source_registry.csv, saying what the
registry declares about it (status, cadence, tier, family) and when it last
succeeded: a run receipt in data/source_run_state.json (RUN_RECEIPT), or
NOT_RECORDED with a null time. OVNIS outputs carry no per-source success time,
so nothing is output-derived and nothing is guessed.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

import jsonschema
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import federation_export as fx  # noqa: E402
import prii_export_utils  # noqa: E402

REGISTRY = REPO / fx.SOURCE_REGISTRY
NOW = "2026-11-13T18:00:00Z"
HEADER = "source_id,name,language,source_family,reliability_default,scrape_method,active,retrieval_cadence,robots_policy,notes\n"
# Required keys and enums of thehub-pr schemas/federation_source_monitor.schema.json 1.0.0.
REQUIRED = {"monitor_id", "source_ref", "name", "declared_status", "cadence", "last_success_basis",
            "lineage", "synthetic", "created_at", "extracted_at"}


def _registered() -> list[dict[str, str]]:
    with REGISTRY.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _registry(tmp_path: Path, *lines: str) -> Path:
    path = tmp_path / "source_registry.csv"
    path.write_text(HEADER + "".join(line + "\n" for line in lines), encoding="utf-8")
    return path


def _no_state(tmp_path: Path) -> Path:
    return tmp_path / "absent_source_run_state.json"


def test_one_row_per_registered_source_on_committed_data():
    rows = fx.build_source_monitors(NOW)
    assert [r["source_ref"] for r in rows] == sorted(r["source_id"] for r in _registered())
    assert len({r["monitor_id"] for r in rows}) == len(rows)
    for row in rows:
        # Deterministic: the package's monitor_id, which is this repo's own fid("mon", ...).
        assert row["monitor_id"] == prii_export_utils.monitor_id(fx.PRODUCER, row["source_ref"])
        assert row["monitor_id"] == prii_export_utils.fid("mon", fx.PRODUCER, row["source_ref"])
        assert row["registry_path"] == "data/reference/source_registry.csv"
        assert row["synthetic"] is False


def test_rows_have_the_hub_schema_shape():
    for row in fx.build_source_monitors(NOW):
        assert set(row) >= REQUIRED
        assert re.fullmatch(r"mon_[a-f0-9]{32}", row["monitor_id"])
        assert row["declared_status"] in prii_export_utils.DECLARED_STATUSES
        assert row["cadence"] in prii_export_utils.CADENCES
        assert row["last_success_basis"] in prii_export_utils.BASES
        assert row["evidence_tier"] in {None, "T1", "T2", "T3", "T4"}
        assert row["cadence_window_seconds"] is None or row["cadence_window_seconds"] >= 1
        assert set(row["lineage"]) >= {"producer_script", "producer_phase", "source_inputs"}


def test_committed_data_reports_a_time_only_from_a_run_receipt():
    # OVNIS outputs carry no per-source success time, so a time can only come from
    # a committed run receipt; every other source is NOT_RECORDED.
    state = prii_export_utils.SourceRunState.load(REPO / fx.SOURCE_RUN_STATE)
    for row in fx.build_source_monitors(NOW):
        success = (state.get(row["source_ref"]) or {}).get("last_success_at")
        expected = ("RUN_RECEIPT", success) if success else ("NOT_RECORDED", None)
        assert (row["last_success_basis"], row["last_success_at"]) == expected


def test_without_a_run_receipt_nothing_is_recorded(tmp_path):
    rows = fx.build_source_monitors(NOW, run_state_path=_no_state(tmp_path))
    assert {(r["last_success_basis"], r["last_success_at"]) for r in rows} == {("NOT_RECORDED", None)}
    assert {(r["last_attempt_at"], r["last_attempt_status"]) for r in rows} == {(None, None)}
    assert rows[0]["lineage"]["source_inputs"] == ["data/reference/source_registry.csv"]


def test_a_run_receipt_is_reported_and_a_failed_attempt_keeps_the_last_success(tmp_path):
    state = tmp_path / "source_run_state.json"
    prii_export_utils.record_run(state, "SRC-0010", "success", "2026-11-10T06:00:00Z")
    prii_export_utils.record_run(state, "SRC-0010", "failure", "2026-11-12T06:00:00Z")
    prii_export_utils.record_run(state, "SRC-9999", "success", "2026-11-12T06:00:00Z")  # unregistered
    rows = fx.build_source_monitors(NOW, run_state_path=state)
    by_ref = {r["source_ref"]: r for r in rows}
    nuforc = by_ref["SRC-0010"]
    assert (nuforc["last_success_basis"], nuforc["last_success_at"]) == ("RUN_RECEIPT", "2026-11-10T06:00:00Z")
    assert (nuforc["last_attempt_at"], nuforc["last_attempt_status"]) == ("2026-11-12T06:00:00Z", "failure")
    assert "SRC-9999" not in by_ref  # a receipt adds no row of its own
    others = [r for r in rows if r["source_ref"] != "SRC-0010"]
    assert all(r["last_success_basis"] == "NOT_RECORDED" and r["last_success_at"] is None for r in others)


def test_a_failure_only_receipt_is_still_not_recorded(tmp_path):
    state = tmp_path / "source_run_state.json"
    prii_export_utils.record_run(state, "A", "failure", "2026-11-12T06:00:00Z")
    [row] = fx.build_source_monitors(NOW, registry_path=_registry(tmp_path, "A,Feed A,en,f,T2,api,yes,weekly,x,y"),
                                     run_state_path=state)
    assert (row["last_success_basis"], row["last_success_at"]) == ("NOT_RECORDED", None)
    assert (row["last_attempt_at"], row["last_attempt_status"]) == ("2026-11-12T06:00:00Z", "failure")


def test_every_committed_registry_value_is_mapped():
    # A new cadence or status value in the registry must get a deliberate mapping
    # (the same one thehub-pr's registry reader gives it), not fall to "unknown".
    registered = _registered()
    cadences = {r["retrieval_cadence"].strip().lower() for r in registered}
    statuses = {r["active"].strip().lower() for r in registered}
    assert cadences <= set(fx.MONITOR_CADENCE), cadences - set(fx.MONITOR_CADENCE)
    assert statuses <= set(fx.MONITOR_STATUS), statuses - set(fx.MONITOR_STATUS)


@pytest.mark.parametrize(("cadence", "expected", "window"), [
    ("quarterly", "quarterly", 92 * 86400),
    ("annual", "yearly", 366 * 86400),
    ("weekly", "weekly", 7 * 86400),
    ("none", "static", None),
    ("on_foia_release", "event", None),
    ("on_legacy_consolidation", "event", None),
    (" Weekly ", "weekly", 7 * 86400),
    ("fortnightly", "unknown", None),
    ("", "unknown", None),
])
def test_cadence_follows_the_hub_registry_reader(tmp_path, cadence, expected, window):
    path = _registry(tmp_path, f"A,Feed A,en,f,T2,api,yes,{cadence},x,y")
    [row] = fx.build_source_monitors(NOW, registry_path=path, run_state_path=_no_state(tmp_path))
    assert (row["cadence"], row["cadence_window_seconds"]) == (expected, window)


@pytest.mark.parametrize(("active", "status"), [
    ("yes", "active"), ("no", "inactive"), ("manual", "manual"), ("Active", "active"),
    ("partial", "unknown"), ("", "unknown"),
])
def test_declared_status_follows_the_hub_registry_reader(tmp_path, active, status):
    path = _registry(tmp_path, f"A,Feed A,en,f,T2,api,{active},weekly,x,y")
    [row] = fx.build_source_monitors(NOW, registry_path=path, run_state_path=_no_state(tmp_path))
    assert row["declared_status"] == status


@pytest.mark.parametrize(("tier", "expected"), [("T1", "T1"), (" t4 ", "T4"), ("0.7", None), ("T5", None), ("", None)])
def test_evidence_tier_keeps_only_a_t_tier(tmp_path, tier, expected):
    path = _registry(tmp_path, f"A,Feed A,en,f,{tier},api,yes,weekly,x,y")
    [row] = fx.build_source_monitors(NOW, registry_path=path, run_state_path=_no_state(tmp_path))
    assert row["evidence_tier"] == expected


def test_blank_name_and_family_fall_back_like_the_hub(tmp_path):
    path = _registry(tmp_path, " B , ,en, ,T2,api,yes,weekly,x,y", "A,Feed A,en,fam,T2,api,yes,weekly,x,y")
    rows = fx.build_source_monitors(NOW, registry_path=path, run_state_path=_no_state(tmp_path))
    assert [(r["source_ref"], r["name"], r["producer_family"]) for r in rows] == [("A", "Feed A", "fam"), ("B", "B", None)]


def test_duplicate_or_missing_source_ids_fail(tmp_path):
    dup = _registry(tmp_path, "A,Feed A,en,f,T2,api,yes,weekly,x,y", "A,Feed A again,en,f,T2,api,yes,weekly,x,y")
    with pytest.raises(ValueError, match="duplicate source_id 'A'"):
        fx.build_source_monitors(NOW, registry_path=dup, run_state_path=_no_state(tmp_path))
    blank = _registry(tmp_path, ",Feed,en,f,T2,api,yes,weekly,x,y")
    with pytest.raises(ValueError, match="no source_id"):
        fx.build_source_monitors(NOW, registry_path=blank, run_state_path=_no_state(tmp_path))
    narrow = tmp_path / "narrow.csv"
    narrow.write_text("source_id,name\nA,Feed A\n", encoding="utf-8")
    with pytest.raises(ValueError, match="missing column"):
        fx.build_source_monitors(NOW, registry_path=narrow, run_state_path=_no_state(tmp_path))


def test_package_lists_the_stream_and_its_manifest_validates(tmp_path):
    rows = fx.build_source_monitors(NOW)
    manifest_path = fx.write_package({"source_monitors": rows}, tmp_path / "pkg", "test", NOW)
    manifest = json.loads(manifest_path.read_text())
    assert [f["stream"] for f in manifest["files"]] == ["source_monitors"]
    entry = manifest["files"][0]
    assert entry["schema_id"] == "federation_source_monitor.schema.json"
    assert entry["record_count"] == len(rows)
    written = (tmp_path / "pkg" / "source_monitors.jsonl").read_text().splitlines()
    assert [json.loads(line) for line in written] == rows
    schema = json.loads((REPO / "schemas/federation_export_manifest.schema.json").read_text())
    jsonschema.validate(manifest, schema)


def test_local_helpers_keep_their_ids_and_reach_the_pinned_package():
    # scripts/prii_export_utils.py shadows the pinned package; its own helpers stay
    # as they were (ids depend on them) and other names come from the package.
    assert Path(prii_export_utils.__file__).resolve() == REPO / "scripts" / "prii_export_utils.py"
    assert prii_export_utils.fid("ent", "a", None) == "ent_" + hashlib.sha256(b"a|").hexdigest()[:32]
    assert prii_export_utils.norm("Río Grande") == "rio_grande"
    assert callable(prii_export_utils.source_monitor_row)
    assert callable(prii_export_utils.resolve_last_success)
    with pytest.raises(AttributeError):
        prii_export_utils.no_such_helper  # noqa: B018


def test_pinned_package_loads_from_an_archive(tmp_path):
    # A frozen build can bundle the pinned package in an archive, where it has no
    # source file on disk, so the shim must import it with the loader its finder
    # returns. A zip on sys.path is the same case: an archive-backed loader.
    import zipfile

    package = Path(prii_export_utils._pinned_package().__file__).parent
    archive = tmp_path / "pinned.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        for path in sorted(package.glob("*.py")):
            zf.write(path, f"prii_export_utils/{path.name}")
    code = "\n".join([
        "import sys",
        "from pathlib import Path",
        f"sys.path[:0] = [{str(REPO / 'scripts')!r}, {str(archive)!r}]",
        "import prii_export_utils as shim",
        f"assert Path(shim.__file__).resolve() == Path({str(REPO / 'scripts' / 'prii_export_utils.py')!r})",
        "assert shim.norm('Río Grande') == 'rio_grande'",
        "row = shim.source_monitor_row",
        "assert callable(row) and row.__module__ == 'prii_export_utils.source_monitor', row.__module__",
        "assert sys.modules['prii_export_utils'] is shim",
    ])
    # -S: no site-packages, so the zip is the only place the pinned package can come from.
    result = subprocess.run([sys.executable, "-S", "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
