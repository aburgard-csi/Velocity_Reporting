"""Paths shared by the issue-page scripts: the ODD and Workbook Issues page and the CSM Data Gaps page.

Everything resolves through rpe_env, never a written-in path. Working data and the generated pages go to
`Build Artifacts/issue_pages/` (they carry client names and products, so they never go in git); the team
copies go to `<RPE_DATA_ROOT>/Notes/`. Importing this module also puts build/, build/ars_pipeline/ and
scripts/ on sys.path, so a script here can import rpe_env, build_month, deck_status, odd_rows and
lift_window.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
for _p in (REPO / "build", REPO / "build" / "ars_pipeline", REPO / "scripts"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import rpe_env as R  # noqa: E402

TEMPLATE = HERE / "gaps_template.html"
ODD_PAGE = "ODD and Workbook Issues.html"
GAPS_PAGE = "CSM Data Gaps.html"


def work_dir():
    """`Build Artifacts/issue_pages/`, created on demand."""
    d = R.build_artifacts() / "issue_pages"
    d.mkdir(parents=True, exist_ok=True)
    return d


def notes_dir():
    return R.data_root() / "Notes"


def trial_dir(period):
    """The all-client ARS trial run for `period` (`Build Artifacts/allclients_<period>/`)."""
    return R.build_artifacts() / f"allclients_{period}"
