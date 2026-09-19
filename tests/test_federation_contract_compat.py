"""Federation canonical-export contract-compat test (hub-facing).

Pins the manifest envelope produced by ``scripts/federation_export.py``
``write_package`` against the hub's contract: the exact top-level key set,
the federation handshake block, the per-file entries, and validity against
the vendored copy of thehub-pr's ``federation_export_manifest`` schema
(``schemas/federation_export_manifest.schema.json``). A producer-side change
that alters any of these breaks this test before it can silently break the
hub's consumer.
"""

import json
from pathlib import Path

import jsonschema

from federation_export import build_streams, write_package

REPO = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO / "schemas" / "federation_export_manifest.schema.json"
COMPATIBILITY_RECEIPT = REPO / "governance" / "federation_compatibility.json"

FIXED_NOW = "2026-01-01T00:00:00Z"
MODE = "test"

EXPECTED_MANIFEST_KEYS = {
    "package_id",
    "producer",
    "export_contract_version",
    "mode",
    "created_at",
    "extracted_at",
    "federation",
    "files",
}


def test_spatial_attestation_preserves_repository_compatibility():
    receipt = json.loads(COMPATIBILITY_RECEIPT.read_text())
    assert receipt["disposition"] == "COMPATIBLE"
    assert receipt["spatial_disposition"] == "ATTESTED"


def _manifest(master_case, tmp_path):
    streams = build_streams([master_case()], FIXED_NOW)
    manifest_path = write_package(streams, tmp_path, MODE, FIXED_NOW)
    return json.loads(manifest_path.read_text())


def test_manifest_top_level_keys_exact(master_case, tmp_path):
    manifest = _manifest(master_case, tmp_path)
    assert set(manifest) == EXPECTED_MANIFEST_KEYS


def test_federation_handshake_block(master_case, tmp_path):
    manifest = _manifest(master_case, tmp_path)
    assert manifest["federation"]["hub_parent"] == "thehub-pr"
    assert manifest["federation"]["producer_repo"] == "ovnis-pr"


def test_file_entries_carry_required_fields(master_case, tmp_path):
    manifest = _manifest(master_case, tmp_path)
    assert manifest["files"]
    for f in manifest["files"]:
        assert set(f) >= {"filename", "stream", "record_count", "sha256", "schema_id"}


def test_manifest_validates_against_vendored_hub_schema(master_case, tmp_path):
    schema = json.loads(SCHEMA_PATH.read_text())
    jsonschema.validate(_manifest(master_case, tmp_path), schema)


def test_package_id_is_deterministic(master_case, tmp_path):
    a = _manifest(master_case, tmp_path / "a")
    b = _manifest(master_case, tmp_path / "b")
    assert a["package_id"] == b["package_id"]
    assert a == b
