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
# The ODD page's own findings, for CSM Sheila's Data Issues tab (Aaron, 2026-10-02: "the refresh for data issues
# should also refresh what's shown in Sheila"). Sheila already reads gaps.json, so only the findings the ODD page
# adds on top of it go here: the Personal/Business and Mail Flag scans, the trial run, the Lift Matrix date
# window and the extract's missing card months.
ODD_FINDINGS = "odd_findings.json"
KIND_SEVERITY = {"block": "blocker", "map": "decision", "fix": "gap", "pending": "gap"}


def odd_findings(items, cats, period, generated):
    """The JSON document for ODD_FINDINGS: every ODD-page item that did not come from gaps.json, in Sheila's
    issue shape (severity, program, issue, fix). `cats` is the page's {cat: (title, kind, next step)}."""
    out = []
    for x in items:
        if x.get("src", "gaps") == "gaps":
            continue
        title, kind, nxt = cats[x["cat"]]
        out.append({"id": x["id"], "name": x.get("name"), "csm": x.get("csm"), "program": "ARS",
                    "severity": KIND_SEVERITY[kind], "category": title,
                    "issue": f"{title}: {x['detail']}" if x.get("detail") else title,
                    "fix": nxt, "src": x["src"]})
    return {"period": period, "generated": generated, "findings": out}


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
