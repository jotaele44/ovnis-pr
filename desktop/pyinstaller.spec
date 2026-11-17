# PyInstaller spec for the standalone desktop build (Phase 2).
# Build (on the target OS):
#   pip install pyinstaller
#   pyinstaller desktop/pyinstaller.spec --distpath dist-desktop
# Produces a self-contained one-folder app: dist-desktop/PRII-OVNIS/
# The bundle mirrors the repo layout so server/backend/main.py finds data/
# and releases/ with its normal relative paths.

import os
import sys
from pathlib import Path

REPO_ROOT = Path(SPECPATH).resolve().parent
APP_NAME = "PRII-OVNIS"

# Branding is generated from assets/branding/icon.png by
# thehub-pr/tools/build_program_icons.py, so the frozen build, the committed
# PRII-*.app bundle and the web favicons all trace back to one master.
BRANDING = REPO_ROOT / "assets" / "branding"
# PyInstaller wants .ico on Windows and .icns on macOS; it warns and ignores the
# argument on other platforms, so leave it unset there.
EXE_ICON = str(BRANDING / "icon.ico") if sys.platform == "win32" else None

# Windowed by default (no console window for double-click users). CI sets
# PRII_CONSOLE=1 to build a console binary it can smoke-test with visible stdio.
CONSOLE = os.environ.get("PRII_CONSOLE") == "1"

datas = [
    (str(REPO_ROOT / "dashboard" / "dist"), "dashboard/dist"),
    (str(REPO_ROOT / "data"), "data"),
]
if (REPO_ROOT / "releases").exists():
    datas.append((str(REPO_ROOT / "releases"), "releases"))

# PR Grid V2 Cell_Profile API (server/backend/grid_v2_api.py): it resolves its pin
# and repository identity relative to the bundle root and imports the shared
# runtime from federation/spatial via sys.path, which PyInstaller cannot follow.
datas += [
    (str(REPO_ROOT / "federation.json"), "."),
    (
        str(REPO_ROOT / "federation" / "spatial" / "pr_grid_geographic_v2.pin.json"),
        "federation/spatial",
    ),
]
GRID_V2_SPATIAL = str(REPO_ROOT / "federation" / "spatial")

a = Analysis(
    [str(REPO_ROOT / "desktop" / "launch.py")],
    pathex=[str(REPO_ROOT), GRID_V2_SPATIAL],
    datas=datas,
    hiddenimports=[
        "server.backend.grid_v2_api",
        "pr_grid_v2_runtime",
        "uvicorn.logging",
        "uvicorn.loops.auto",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan.on",
        "desktop.app_server",
        "server.backend.main",
        # Shared desktop-wrapper runtime (thehub-pr/packages/prii_desktop),
        # imported by the desktop/ shims — bundle it into the frozen build.
        "prii_desktop",
        "prii_desktop.launcher",
        "prii_desktop.appserver",
        "prii_desktop.config",
    ],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    exclude_binaries=True,
    name=APP_NAME,
    console=CONSOLE,
    icon=EXE_ICON,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    name=APP_NAME,
)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name=f"{APP_NAME}.app",
        icon=str(BRANDING / "AppIcon.icns"),
        bundle_identifier="pr.prii.ovnis",
    )
