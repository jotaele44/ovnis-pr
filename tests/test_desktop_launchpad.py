"""OVNIS's Launch Pad declaration (desktop/config.py).

The screen itself lives in the shared prii_desktop runtime; these tests keep the
declaration true to this repository. They skip when the installed runtime
predates the Launch Pad.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

launchpad = pytest.importorskip("prii_desktop.launchpad")

from desktop import config  # noqa: E402
from prii_desktop import DesktopConfig  # noqa: E402


def test_declaration_is_valid_and_single_mode():
    spec = launchpad.launchpad_spec(DesktopConfig.from_module(config))
    assert spec is not None
    # The API is GET-only, so offering Guest vs Operator would promise a
    # difference that does not exist.
    assert spec.has_modes is False and spec.options == ()
    backend = (Path(config.REPO_ROOT) / "server/backend/main.py").read_text()
    for verb in ("post", "put", "patch", "delete"):
        assert f"@app.{verb}(" not in backend
    assert [page.route for page in spec.start_pages] == ["/"]


def test_status_reports_the_committed_corpus():
    rows = {row["label"]: row for row in config._launchpad_status()}
    assert rows["Case corpus"]["status"] == "pass"
    assert rows["Case corpus"]["value"].endswith("cases")
    assert rows["Map release"]["status"] == "pass"


def test_status_degrades_when_the_corpus_is_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "REPO_ROOT", tmp_path)
    rows = {row["label"]: row for row in config._launchpad_status()}
    assert rows["Case corpus"]["status"] == "fail"
    assert rows["Map release"]["status"] == "warn"
