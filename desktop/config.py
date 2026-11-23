"""Desktop-wrapper configuration for this repo.

The desktop/ folder is a shared federation template; only this file differs
between repos.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# User-facing window title of the desktop app.
APP_TITLE = "OVNIS"

# Dotted import path of the FastAPI application object.
APP_IMPORT = "server.backend.main:app"

# Directory containing the Vite frontend (with package.json).
FRONTEND_DIR = REPO_ROOT / "dashboard"

# Vite build output served by the desktop app.
DIST_DIR = FRONTEND_DIR / "dist"

# Requirement files installed into the private .venv by desktop/setup.py.
REQUIREMENT_FILES = [
    REPO_ROOT / "server" / "backend" / "requirements.txt",
    REPO_ROOT / "requirements-desktop.txt",
]

# Health endpoint used to detect that the backend is up.
HEALTH_PATH = "/health"


def _launchpad_status() -> list[dict[str, str]]:
    """Readiness rows for the Launch Pad. Runs before the backend exists, so it
    counts the committed corpus files the backend will serve.
    """

    def rows(relative: str) -> list[str]:
        path = REPO_ROOT / relative
        if not path.is_file():
            return []
        return [
            line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
        ]

    def real(lines: list[str]) -> int:
        # Same placeholder rule as server/backend/main.py:is_placeholder.
        markers = ("placeholder", "ovnis-0000", "cand-0000")
        return sum(1 for line in lines if not any(m in line.lower() for m in markers))

    cases = rows("data/master/master_cases.jsonl")
    candidates = real(rows("data/candidates/candidate_cases.jsonl"))
    releases = sorted((REPO_ROOT / "releases").glob("**/ovnis_cases_master.geojson"))
    return [
        {
            "label": "Case corpus",
            "value": f"{real(cases):,} cases" if cases else "Missing",
            "status": "pass" if real(cases) else "fail",
            "detail": (
                "Master case records in data/master/master_cases.jsonl."
                if cases
                else "data/master/master_cases.jsonl was not found or is empty."
            ),
        },
        {
            "label": "Candidates awaiting review",
            "value": f"{candidates:,}",
            "status": "info",
            "detail": "Unpromoted candidate cases in data/candidates/candidate_cases.jsonl.",
        },
        {
            "label": "Map release",
            "value": releases[-1].parent.name if releases else "None",
            "status": "pass" if releases else "warn",
            "detail": (
                "Latest released case GeoJSON used by the map."
                if releases
                else "No released GeoJSON found; the map will have no case layer."
            ),
        },
    ]


# Pre-launch screen shown by the shared runtime (prii_desktop.launchpad).
# OVNIS serves a committed, read-only corpus: its API has no write routes, so
# there is one way in (no Guest/Operator choice) and nothing to configure
# before start. The dashboard has a single route; its views are tabs.
LAUNCHPAD = {
    "tagline": "PRII historical case corpus",
    "summary": (
        "OVNIS is the federation's historical case corpus for anomalous-event "
        "research centred on Puerto Rico. This diagnostic dashboard lets you "
        "browse cases, their chronology, locations and source tiers, and the "
        "candidates still awaiting review. It is read-only: records change "
        "through the review scripts, not through this app."
    ),
    "highlights": ["Cases", "Map", "Statistics", "Candidates", "Activity"],
    "status": _launchpad_status,
    "start_pages": [
        {
            "route": "/",
            "label": "Case dashboard",
            "description": "Opens on the case list; Map, Statistics and Candidates are tabs.",
        },
    ],
}
