import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_cell_id_pattern_accepts_every_canonical_grid_row():
    schema = json.loads((ROOT / "schemas" / "pr_grid_cell.schema.json").read_text(encoding="utf-8"))
    pattern = re.compile(schema["properties"]["Cell_ID"]["pattern"])
    grid = ROOT / "registry" / "spatial" / "pr_grid_full_cell_index_saturated.csv"
    with grid.open(encoding="utf-8", newline="") as handle:
        cell_ids = [row["Cell_ID"] for row in csv.DictReader(handle)]
    assert len(cell_ids) == 98304
    assert [cell_id for cell_id in cell_ids if not pattern.search(cell_id)] == []
    assert not pattern.search("R0_C")
