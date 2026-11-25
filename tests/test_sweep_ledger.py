"""Tests for the source sweep ledger and duplicate gate (scripts/sweep_ledger.py)."""

import csv
import json

import pytest

import sweep_ledger as sl


def _write(path, columns, rows):
    sl.write_csv(path, columns, rows)
    return path


def _index_row(**overrides):
    row = {c: "" for c in sl.INDEX_COLUMNS}
    row.update(overrides)
    return row


def _known(tmp_path, rows):
    index = _write(tmp_path / "index.csv", sl.INDEX_COLUMNS, rows)
    return sl._known_records(index, tmp_path / "no_master.jsonl")


# ------------------------------------------------------------------ normalization


@pytest.mark.parametrize(
    "a,b",
    [
        (
            "https://nuforc.org/sighting/?id=79425",
            "http://www.nuforc.org/webreports/reports/079/S79425.html",
        ),
        (
            "https://nuforc.org/sighting/?id=079425",
            "https://web.archive.org/web/2020/https://nuforc.org/sighting/?id=79425",
        ),
        (
            "https://ufosighting.report/sighting/13290/a-slug",
            "https://ufosighting.report/sighting/13290/another",
        ),
        ("https://www.example.com/a/b/?utm_source=x#frag", "http://example.com/a/b"),
        ("https://blog.example.com/p/post.html?m=1", "https://blog.example.com/p/post.html"),
        ("https://example.com/dir/index.html", "https://example.com/dir/"),
        (
            "https://www.ufo-hunters.com/sightings/search/514398D60AD2E1E9BE44AA2F/Title",
            "https://ufo-hunters.com/sightings/search/514398d60ad2e1e9be44aa2f/",
        ),
    ],
)
def test_url_key_treats_variants_as_one_source(a, b):
    assert sl.url_key(a) == sl.url_key(b) != ""


@pytest.mark.parametrize(
    "url",
    [
        "https://evilnuforc.org/sighting/?id=79425",
        "https://nuforc.org.example.com/sighting/?id=79425",
        "https://notufosighting.report/sighting/13290/x",
        "https://ufosighting.report.example.com/sighting/13290/x",
        "https://myufo-hunters.com/sightings/search/514398d60ad2e1e9be44aa2f/",
    ],
)
def test_url_key_does_not_treat_lookalike_hosts_as_a_known_source(url):
    key = sl.url_key(url)
    assert not key.startswith(("nuforc:", "ufosighting.report:", "ufo-hunters:"))


def test_url_key_accepts_subdomains_of_a_known_source():
    assert sl.url_key("https://data.nuforc.org/sighting/?id=79425") == "nuforc:79425"
    assert sl.url_key("https://m.ufosighting.report/sighting/13290/x") == "ufosighting.report:13290"


def test_url_key_keeps_distinct_pages_and_meaningful_queries_apart():
    assert sl.url_key("https://example.com/a") != sl.url_key("https://example.com/b")
    assert sl.url_key("https://example.com/p?id=1") != sl.url_key("https://example.com/p?id=2")
    assert sl.url_key("https://ufosighting.report/sighting/1/x") != sl.url_key(
        "https://ufosighting.report/sighting/2/x"
    )


@pytest.mark.parametrize(
    "value", ["", None, "Primera Hora, March 2025", "offline-placeholder", "localhost/x"]
)
def test_url_key_is_empty_for_citations_that_are_not_urls(value):
    assert sl.url_key(value) == ""


@pytest.mark.parametrize(
    "text,expected",
    [
        ("October 5, 2026", "2026-10-05"),
        ("Oct. 5, 2026", "2026-10-05"),
        ("January 2011", "2011-01"),
        ("1988–1991", "1988"),
        ("Summer 1988 (two occasions)", "1988"),
        ("2026-02-17", "2026-02-17"),
        ("1972", "1972"),
        ("Date not given", ""),
        ("Early 1950s", ""),
        (None, ""),
    ],
)
def test_iso_date_is_never_finer_than_the_text(text, expected):
    assert sl.iso_date(text) == expected


def test_place_basis_matches_shared_municipality_and_never_different_ones():
    assert (
        sl.place_basis({"municipality": "Salinas"}, {"municipality": "salinas"}) == "MUNICIPALITY"
    )
    assert (
        sl.place_basis({"municipality": "Ponce"}, {"municipality": "Guayanilla / Ponce"})
        == "MUNICIPALITY"
    )
    assert sl.place_basis({"municipality": "Ponce"}, {"municipality": "Salinas"}) is None
    # Accents do not separate the same place.
    assert (
        sl.place_basis({"municipality": "Bayamón"}, {"municipality": "Bayamon"}) == "MUNICIPALITY"
    )
    # A generic value anchors nothing, so text similarity decides.
    assert (
        sl.place_basis(
            {"municipality": "Island-wide", "location_name": "Cerro Las Tetas"},
            {"municipality": "Salinas", "location_name": "Cerro Las Tetas"},
        )
        == "LOCATION_TEXT"
    )
    assert (
        sl.place_basis(
            {"municipality": "", "location_name": "A"}, {"municipality": "", "location_name": "B"}
        )
        is None
    )


def test_date_agreement_allows_one_day_only_between_full_dates():
    assert sl.date_agreement("2026-10-05", "2026-10-06") == "ADJACENT_DAY"
    assert sl.date_agreement("2026-10-05", "2026-10-07") is None
    assert sl.date_agreement("2026-10", "2026-10-31") == "COMPATIBLE_PRECISION"
    assert sl.date_agreement("2026-10-05", "2026-10-05") == "IDENTICAL_RECORDED_DATE"
    assert sl.date_agreement("2026-10", "2026-11") is None


# ------------------------------------------------------------------ duplicate gate


def test_check_native_report_with_conflicting_date(tmp_path):
    known = _known(
        tmp_path,
        [
            _index_row(
                case_id="C1",
                date_local="2010-12-25",
                municipality="Salinas",
                source_keys="nuforc:79425",
            )
        ],
    )
    out = sl.check_candidate(
        {"url": "https://nuforc.org/sighting/?id=79425", "date": "1999"}, known
    )
    assert out["verdict"] == "IDENTITY_CONFLICT"
    assert out["matches"][0]["case_id"] == "C1"


def test_check_possible_duplicate_needs_date_and_place_together(tmp_path):
    known = _known(
        tmp_path,
        [
            _index_row(
                case_id="C1",
                date_local="2026-10-05",
                municipality="Salinas",
                source_keys="a.example/x",
            ),
            _index_row(
                case_id="C2",
                date_local="2026-10-05",
                municipality="Ponce",
                source_keys="b.example/y",
            ),
            _index_row(
                case_id="C3",
                date_local="2026-03-01",
                municipality="Salinas",
                source_keys="c.example/z",
            ),
        ],
    )
    out = sl.check_candidate(
        {"url": "https://other.example/q", "date": "October 6, 2026", "municipality": "Salinas"},
        known,
    )
    assert out["verdict"] == "POSSIBLE_DUPLICATE"
    assert [m["case_id"] for m in out["matches"]] == ["C1"]
    assert out["matches"][0]["basis"] == ["ADJACENT_DAY", "MUNICIPALITY"]


def test_check_new_when_nothing_agrees(tmp_path):
    known = _known(
        tmp_path, [_index_row(case_id="C1", date_local="2026-10-05", municipality="Salinas")]
    )
    out = sl.check_candidate(
        {"url": "https://new.example/a", "date": "2026-10-05", "municipality": "Ponce"}, known
    )
    assert out["verdict"] == "NO_KNOWN_MATCH" and out["matches"] == []


def test_check_without_a_date_cannot_be_a_possible_duplicate(tmp_path):
    known = _known(
        tmp_path, [_index_row(case_id="C1", date_local="2026-10-05", municipality="Salinas")]
    )
    out = sl.check_candidate({"url": "https://new.example/a", "municipality": "Salinas"}, known)
    assert out["verdict"] == "INSUFFICIENT_IDENTITY"


def test_check_reads_the_master_ledger_too(tmp_path):
    master = tmp_path / "master.jsonl"
    master.write_text(
        json.dumps(
            {
                "record_type": "master",
                "record_id": "PRUFON-0001",
                "case_id": "PRUAP-0001",
                "date_local": "1927-10-06",
                "municipality": "Ponce",
                "location_name": "Offshore",
                "source_url": "https://archive.example.org/article/1",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    known = sl._known_records(tmp_path / "missing_index.csv", master)
    out = sl.check_candidate({"url": "http://www.archive.example.org/article/1/"}, known)
    assert out["verdict"] == "SHARED_DOCUMENT" and out["matches"][0]["dataset"] == "master_cases"


def test_check_cli_fail_on_match_and_json(tmp_path, capsys):
    index = _write(
        tmp_path / "index.csv",
        sl.INDEX_COLUMNS,
        [
            _index_row(
                case_id="C1",
                date_local="2026-10-05",
                municipality="Salinas",
                source_keys="a.example/x",
            )
        ],
    )
    master = tmp_path / "none.jsonl"
    master.write_text("", encoding="utf-8")
    base = ["--index", str(index), "--master", str(master)]
    assert sl.main([*base, "check", "--url", "https://a.example/x", "--fail-on-match"]) == 1
    assert json.loads(capsys.readouterr().out)["verdict"] == "SHARED_DOCUMENT"
    assert sl.main([*base, "check", "--url", "https://z.example/new", "--date", "2025-01-01", "--municipality", "Ponce", "--fail-on-match"]) == 0
    assert sl.main([*base, "check"]) == 2


def test_check_batch_jsonl(tmp_path, capsys):
    index = _write(
        tmp_path / "index.csv",
        sl.INDEX_COLUMNS,
        [_index_row(case_id="C1", source_keys="a.example/x")],
    )
    (tmp_path / "none.jsonl").write_text("", encoding="utf-8")
    batch = tmp_path / "batch.jsonl"
    batch.write_text(
        '{"url": "https://a.example/x"}\n{"url": "https://b.example/y", "date": "2026-01-01"}\n',
        encoding="utf-8",
    )
    sl.main(
        [
            "--index",
            str(index),
            "--master",
            str(tmp_path / "none.jsonl"),
            "check",
            "--jsonl",
            str(batch),
        ]
    )
    verdicts = [r["verdict"] for r in json.loads(capsys.readouterr().out)]
    assert verdicts == ["SHARED_DOCUMENT", "INSUFFICIENT_IDENTITY"]


# ------------------------------------------------------------------ ledger, record, status


def _ledger(tmp_path, **rows):
    data = []
    for name, fields in rows.items():
        row = {c: "" for c in sl.LEDGER_COLUMNS}
        row.update(source=name, **fields)
        data.append(row)
    return _write(tmp_path / "ledger.csv", sl.LEDGER_COLUMNS, data)


def test_record_sets_verified_point_date_and_appends_notes(tmp_path):
    import hashlib

    ledger = _ledger(tmp_path, Alpha={"state": "forward"})
    evidence = tmp_path / "evidence.txt"
    evidence.write_text("fixture evidence", encoding="utf-8")
    configuration = tmp_path / "configuration.json"
    configuration.write_text("{}", encoding="utf-8")
    receipt = tmp_path / "receipt.json"
    receipt.write_text(
        json.dumps({
            "source": "Alpha",
            "verified_through": "2026-11-01",
            "sweep_date": "2026-11-25",
            "status": "success",
            "reconciliation": "complete",
            "execution_id": "fixture-1",
            "interval_start": "2026-10-01",
            "previous_frontier": "",
            "configuration_path": configuration.name,
            "configuration_sha256": hashlib.sha256(configuration.read_bytes()).hexdigest(),
            "evidence": [{"path": evidence.name, "sha256": hashlib.sha256(evidence.read_bytes()).hexdigest()}],
        }),
        encoding="utf-8",
    )
    argv = [
        "--ledger", str(ledger), "record", "--source", "Alpha",
        "--verified-through", "2026-11-01", "--date", "2026-11-25",
        "--receipt", str(receipt), "--note", "swept",
    ]
    assert sl.main(argv) == 0
    before = ledger.read_bytes()
    assert sl.main(argv) == 0
    assert ledger.read_bytes() == before
    row = sl.read_csv(ledger)[0]
    assert (row["verified_through"], row["last_swept"]) == ("2026-11-01", "2026-11-25")
    assert "receipt_sha256=" in row["notes"]
    assert "2026-11-25: swept" in row["notes"]
    stale = json.loads(receipt.read_text(encoding="utf-8"))
    stale["previous_frontier"] = "2026-11-01"
    stale["verified_through"] = "2026-10-31"
    stale_receipt = tmp_path / "stale.json"
    stale_receipt.write_text(json.dumps(stale), encoding="utf-8")
    rollback = [
        "--ledger", str(ledger), "record", "--source", "Alpha",
        "--verified-through", "2026-10-31", "--date", "2026-11-25",
        "--receipt", str(stale_receipt),
    ]
    assert sl.main(rollback) == 2
    assert ledger.read_bytes() == before
    configuration.write_text("tampered", encoding="utf-8")
    assert sl.main(argv) == 2
    assert ledger.read_bytes() == before
    configuration.write_text("{}", encoding="utf-8")
    evidence.write_text("tampered", encoding="utf-8")
    assert sl.main(argv) == 2
    assert ledger.read_bytes() == before


def test_frontier_requires_receipt(tmp_path):
    ledger = _ledger(tmp_path, Alpha={"state": "forward"})
    before = ledger.read_bytes()
    assert sl.main([
        "--ledger", str(ledger), "record", "--source", "Alpha",
        "--verified-through", "#200",
    ]) == 2
    assert ledger.read_bytes() == before


def test_record_rejects_unknown_source_and_bad_vocabulary(tmp_path, capsys):
    ledger = _ledger(tmp_path, Alpha={})
    assert sl.main(["--ledger", str(ledger), "record", "--source", "Nope"]) == 2
    assert sl.main(["--ledger", str(ledger), "record", "--source", "Alpha", "--state", "done"]) == 2
    assert (
        sl.main(["--ledger", str(ledger), "record", "--source", "Alpha", "--access", "fine"]) == 2
    )
    assert sl.main(["--ledger", str(ledger), "record", "--source", "Alpha", "--kind", "both"]) == 2
    assert sl.read_csv(ledger)[0]["state"] == ""
    assert "no ledger row" in capsys.readouterr().err


def test_record_add_creates_a_sorted_row(tmp_path):
    ledger = _ledger(tmp_path, Zulu={})
    argv = [
        "--ledger",
        str(ledger),
        "record",
        "--source",
        "Alpha",
        "--add",
        "--category",
        "News media",
        "--state",
        "not_started",
    ]
    assert sl.main(argv) == 0
    assert [r["source"] for r in sl.read_csv(ledger)] == ["Alpha", "Zulu"]
    assert sl.read_csv(ledger)[0]["category"] == "News media"


def test_status_flags_unverified_and_due_forward_sources(tmp_path, capsys):
    ledger = _ledger(
        tmp_path,
        Fresh={
            "state": "forward",
            "refs_logged": "9",
            "verified_through": "x",
            "last_swept": "2026-11-20",
        },
        Stale={
            "state": "forward",
            "refs_logged": "5",
            "verified_through": "y",
            "last_swept": "2026-01-01",
        },
        Never={"state": "forward", "refs_logged": "1", "access": "blocked_automated"},
        Static={"state": "closed"},
        New={"state": "not_started"},
        Loose={"state": ""},
    )
    assert sl.main(["--ledger", str(ledger), "status", "--today", "2026-11-25"]) == 0
    out = capsys.readouterr().out
    assert "6 sources" in out and "unclassified 1" in out
    forward = out.split("Forward sources")[1].split("Not started")[0]
    lines = {
        line.strip().split(" [")[0].split(":")[0]: line
        for line in forward.splitlines()
        if line.startswith("  ")
    }
    assert set(lines) == {"Fresh", "Stale", "Never"}
    assert "<- due" not in lines["Fresh"]
    assert "<- due" in lines["Stale"]
    assert "UNVERIFIED" in lines["Never"] and "<- due" in lines["Never"]
    assert "Not started:\n  New" in out and "Unclassified:\n  Loose" in out
    assert "Blocked to automated fetching" in out


def test_status_on_missing_ledger_is_an_error(tmp_path):
    assert sl.main(["--ledger", str(tmp_path / "none.csv"), "status"]) == 2


# ------------------------------------------------------------------ query log


def test_query_log_then_check_within_window(tmp_path, capsys):
    log = tmp_path / "queries.csv"
    base = ["--query-log", str(log), "query"]
    assert (
        sl.main(
            [
                *base,
                "Luces  extrañas Salinas",
                "--source",
                "Google",
                "--log",
                "--date",
                "2026-11-01",
                "--results",
                "20",
                "--new",
                "2",
            ]
        )
        == 0
    )
    capsys.readouterr()
    # Case, spacing and accents do not make it a different query.
    assert (
        sl.main([*base, "luces extranas salinas", "--source", "google", "--today", "2026-11-25"])
        == 1
    )
    assert "ALREADY RUN 2026-11-01" in capsys.readouterr().out
    # Outside the window it may be re-run; a different source is a different sweep.
    assert (
        sl.main([*base, "luces extranas salinas", "--within-days", "10", "--today", "2026-11-25"])
        == 0
    )
    assert (
        sl.main([*base, "luces extranas salinas", "--source", "Bing", "--today", "2026-11-25"]) == 0
    )


# ------------------------------------------------------------------ refresh from a workbook


def _make_workbook(path):
    openpyxl = pytest.importorskip("openpyxl")
    wb = openpyxl.Workbook()
    case_cols = [
        "Case ID",
        "Date",
        "Municipality",
        "Location",
        "Shape",
        "Primary Link",
        "Archived Copy",
    ]
    ws = wb.active
    ws.title = "2020s"
    ws.append(case_cols)
    ws.append(
        [
            "N-1",
            "March 3, 2024",
            "Ponce",
            "Ponce",
            "Orb",
            "https://nuforc.org/sighting/?id=200",
            None,
        ]
    )
    ws.append(
        [
            "N-2",
            "January 2025",
            "Salinas",
            "Salinas",
            "Sphere",
            "https://ufosighting.report/sighting/50/x",
            None,
        ]
    )
    ws2 = wb.create_sheet("Undated")
    ws2.append(case_cols)
    ws2.append(["U-1", "Date not given", None, "Island", None, "https://blog.example/post", None])
    cs = wb.create_sheet("Case Sources")
    cs.append(
        [
            "Case ID",
            "Case Date",
            "Case Location",
            "Source",
            "Citation / Attribution",
            "Link",
            "Archived Copy",
        ]
    )
    cs.append(["N-1", None, None, "NUFORC", None, "https://nuforc.org/sighting/?id=200", None])
    cs.append(
        [
            "N-1",
            None,
            None,
            "UFO-Hunters.com",
            None,
            "https://www.ufo-hunters.com/sightings/search/514398d60ad2e1e9be44aa2f/",
            None,
        ]
    )
    cs.append(
        [
            "N-2",
            None,
            None,
            "ufosighting.report",
            None,
            "https://ufosighting.report/sighting/50/x",
            None,
        ]
    )
    cs.append(
        [
            "U-1",
            None,
            None,
            "Blog",
            None,
            "https://blog.example/post",
            "https://web.archive.org/web/2024/https://blog.example/post",
        ]
    )
    cs.append(["U-1", None, None, "Blog", None, "Primera Hora, March 2025", None])
    sd = wb.create_sheet("Source Directory")
    sd.append(["Source", "Source Category", "Website", "References in Log"])
    sd.append(["NUFORC", "Report database", "https://nuforc.org", 1])
    sd.append(["Blog", "Research website / blog", "https://blog.example", 2])
    wb.create_sheet("Pending Reports").append(["Report ID", "Status", "Link"])
    wb.save(path)
    return path


def test_refresh_builds_index_and_ledger_and_keeps_manual_columns(tmp_path, capsys):
    xlsx = _make_workbook(tmp_path / "log.xlsx")
    ledger = _ledger(
        tmp_path,
        NUFORC={"state": "forward", "notes": "kept", "verified_through": "#150"},
        Retired={"state": "closed", "cases_logged": "9", "newest_logged_event": "2000"},
    )
    index = tmp_path / "index.csv"
    argv = ["--ledger", str(ledger), "--index", str(index), "refresh", "--xlsx", str(xlsx)]
    assert sl.main(argv) == 0

    rows = {r["case_id"]: r for r in sl.read_csv(index)}
    assert set(rows) == {"N-1", "N-2", "U-1"}
    assert rows["N-1"]["date_local"] == "2024-03-03" and rows["N-2"]["date_local"] == "2025-01"
    assert rows["U-1"]["date_local"] == ""
    assert rows["N-1"]["source_keys"] == "nuforc:200|ufo-hunters:514398d60ad2e1e9be44aa2f"
    assert rows["N-1"]["source_names"] == "NUFORC|UFO-Hunters.com"
    assert (
        rows["U-1"]["source_keys"] == "blog.example/post"
    )  # archived copy unwraps to the same page

    led = {r["source"]: r for r in sl.read_csv(ledger)}
    assert led["NUFORC"]["highest_item_id"] == "200" and led["NUFORC"]["cases_logged"] == "1"
    assert (led["NUFORC"]["state"], led["NUFORC"]["notes"], led["NUFORC"]["verified_through"]) == (
        "forward",
        "kept",
        "#150",
    )
    assert (
        led["ufosighting.report"]["highest_item_id"] == "50"
        and led["ufosighting.report"]["state"] == ""
    )
    assert (
        led["Blog"]["category"] == "Research website / blog" and led["Blog"]["refs_logged"] == "2"
    )
    assert led["Blog"]["cases_logged"] == "1"
    assert led["Retired"]["cases_logged"] == "0" and led["Retired"]["newest_logged_event"] == ""
    assert "added: Blog" in capsys.readouterr().out

    before = (index.read_bytes(), ledger.read_bytes())
    assert sl.main(argv) == 0
    assert (index.read_bytes(), ledger.read_bytes()) == before  # deterministic


def test_refresh_rejects_a_workbook_without_case_sheets(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    wb = openpyxl.Workbook()
    wb.active.append(["Nothing", "Useful"])
    wb.save(tmp_path / "empty.xlsx")
    with pytest.raises(SystemExit):
        sl.main(
            [
                "--ledger",
                str(tmp_path / "l.csv"),
                "--index",
                str(tmp_path / "i.csv"),
                "refresh",
                "--xlsx",
                str(tmp_path / "empty.xlsx"),
            ]
        )


# ------------------------------------------------------------------ the committed files


def test_committed_ledger_uses_the_declared_vocabulary():
    with sl.LEDGER_PATH.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        assert reader.fieldnames == sl.LEDGER_COLUMNS
        rows = list(reader)
    assert rows and len({r["source"] for r in rows}) == len(rows)
    for row in rows:
        assert row["state"] in (*sl.STATES, ""), row["source"]
        assert row["access"] in (*sl.ACCESS, ""), row["source"]
        assert row["kind"] in (*sl.KINDS, ""), row["source"]
        if row["state"] == "forward":
            assert row["next_action"], row["source"]
    assert rows == sl._sorted_ledger(rows)


def test_committed_index_is_consistent():
    with sl.INDEX_PATH.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        assert reader.fieldnames == sl.INDEX_COLUMNS
        rows = list(reader)
    ids = [r["case_id"] for r in rows]
    assert len(ids) == len(set(ids))
    for row in rows:
        keys = [k for k in row["source_keys"].split("|") if k]
        if row["primary_url_key"]:
            assert row["primary_url_key"] in keys, row["case_id"]
        assert row["date_local"] == sl.iso_date(row["date_local"]), row["case_id"]


def test_committed_query_log_has_the_declared_columns():
    with sl.QUERY_LOG_PATH.open(newline="", encoding="utf-8") as fh:
        assert csv.DictReader(fh).fieldnames == sl.QUERY_COLUMNS


def test_native_report_identity_without_date_conflict(tmp_path):
    known = _known(tmp_path, [_index_row(case_id="C1", source_keys="nuforc:123")])
    out = sl.check_candidate({"url": "https://nuforc.org/sighting/?id=123"}, known)
    assert out["verdict"] == "EXACT_REPORT"


def test_shared_document_preserves_all_matches(tmp_path):
    rows = [
        _index_row(case_id=f"C{i}", source_keys="example.com/compilation") for i in range(12)
    ]
    known = _known(tmp_path, rows)
    out = sl.check_candidate({"url": "https://example.com/compilation"}, known)
    assert out["verdict"] == "SHARED_DOCUMENT"
    assert len(out["matches"]) == 12


def test_possible_duplicate_preserves_all_matches(tmp_path):
    rows = [
        _index_row(case_id=f"C{i}", date_local="2026-01-01", municipality="Ponce")
        for i in range(12)
    ]
    known = _known(tmp_path, rows)
    out = sl.check_candidate({"date": "2026-01-02", "municipality": "Ponce"}, known)
    assert out["verdict"] == "POSSIBLE_DUPLICATE"
    assert len(out["matches"]) == 12


def test_check_cli_missing_comparison_fails_closed(tmp_path, capsys):
    argv = [
        "--index", str(tmp_path / "missing.csv"),
        "--master", str(tmp_path / "missing.jsonl"),
        "check", "--url", "https://example.com/report",
    ]
    assert sl.main(argv) == 2
    assert json.loads(capsys.readouterr().out)["verdict"] == "COMPARISON_UNAVAILABLE"


def test_native_report_municipality_conflict(tmp_path):
    known = _known(tmp_path, [
        _index_row(case_id="C1", source_keys="nuforc:123", municipality="Ponce")
    ])
    out = sl.check_candidate(
        {"url": "https://nuforc.org/sighting/?id=123", "municipality": "Salinas"}, known
    )
    assert out["verdict"] == "IDENTITY_CONFLICT"


def test_check_persistent_intake(tmp_path, capsys):
    index = _write(tmp_path / "index.csv", sl.INDEX_COLUMNS, [_index_row(case_id="C1")])
    master = tmp_path / "master.jsonl"
    master.write_text("", encoding="utf-8")
    staged = tmp_path / "staged.jsonl"
    staged.write_text(
        json.dumps({"record_id": "CAND-1", "source_url": "https://nuforc.org/sighting/?id=123"})
        + "\n",
        encoding="utf-8",
    )
    assert sl.main([
        "--index", str(index), "--master", str(master), "check",
        "--candidate-ledger", str(staged), "--url", "https://nuforc.org/sighting/?id=123",
    ]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["verdict"] == "EXACT_REPORT"
    assert result["matches"][0]["dataset"] == "persistent_intake"


def test_check_malformed_index(tmp_path, capsys):
    index = tmp_path / "index.csv"
    index.write_text("wrong_header\nvalue\n", encoding="utf-8")
    master = tmp_path / "master.jsonl"
    master.write_text("", encoding="utf-8")
    assert sl.main([
        "--index", str(index), "--master", str(master), "check",
        "--url", "https://example.com/report",
    ]) == 2
    assert json.loads(capsys.readouterr().out)["verdict"] == "COMPARISON_UNAVAILABLE"


def test_atomic_csv_preserves_previous_file_on_replace_failure(tmp_path, monkeypatch):
    target = tmp_path / "ledger.csv"
    sl.write_csv(target, ["value"], [{"value": "before"}])
    original = target.read_bytes()

    def fail_replace(*args):
        raise OSError("simulated interruption")

    monkeypatch.setattr(sl.os, "replace", fail_replace)
    with pytest.raises(OSError):
        sl.write_csv(target, ["value"], [{"value": "after"}])
    assert target.read_bytes() == original
    assert list(tmp_path.iterdir()) == [target]
