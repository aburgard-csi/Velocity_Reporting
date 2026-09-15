#!/usr/bin/env python3
"""Rebuild the two issue pages: ODD and Workbook Issues, and CSM Data Gaps.

    python scripts/issue_pages/build_issue_pages.py [--no-scan] [--no-notes]

Run `scripts/refresh_performance_dashboard.py` first: gaps_matrix reads its dataset.json. The steps run in
order, each as its own process, and the run stops at the first one that fails:

  1. gaps_matrix.py        per-client gaps from the dashboard dataset, inputs and the trial run -> gaps.json
  2. noprog_odd_dates.py   how current each Missing Workbook client's ODD extract is
  3. missing_wb_history.py every month on the client-reports share, searched for their ARS workbooks
  4. business_flags.py     unreadable Personal/Business flags in every ODD extract   (skipped by --no-scan)
  5. mail_flags.py         unmapped Mail Flags in every ODD extract                  (skipped by --no-scan)
  6. odd_wb_by_csm.py      the ODD and Workbook Issues page, with the Lift Matrix date check
  7. gaps_inject.py        the CSM Data Gaps page

Working data and both pages land in `Build Artifacts/issue_pages/`; then both pages are copied to `Notes/`
for the team (not with --no-notes). `clients_products.py` is separate: run it when a new Velocity client
export arrives. Republishing the two Claude artifacts needs Claude and is not done here.
"""
import argparse, os, subprocess, sys, time

from common import GAPS_PAGE, ODD_PAGE, HERE, notes_dir, work_dir  # noqa: E402

STEPS = ["gaps_matrix.py", "noprog_odd_dates.py", "missing_wb_history.py", "business_flags.py", "mail_flags.py",
         "odd_wb_by_csm.py", "gaps_inject.py"]
SCANS = {"business_flags.py", "mail_flags.py"}


def copy_to_notes(src, dest_dir):
    """Copy a page for the team, with the UTF-8 charset first: a page opened from the share has no server
    header, and without it browsers read the quotes and dashes as Windows-1252."""
    text = src.read_text(encoding="utf-8")
    if "<meta charset" not in text[:200].lower():
        text = '<meta charset="utf-8">\n' + text
    dest = dest_dir / src.name
    dest.write_text(text, encoding="utf-8")
    return dest


def main(argv=None):
    ap = argparse.ArgumentParser(description="Rebuild the ODD and Workbook Issues and CSM Data Gaps pages.")
    ap.add_argument("--no-scan", action="store_true", help="reuse the last Personal/Business and Mail Flag scans")
    ap.add_argument("--no-notes", action="store_true", help="don't copy the pages to Notes")
    a = ap.parse_args(argv)
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    for step in STEPS:
        if a.no_scan and step in SCANS:
            print(f"--- {step}: skipped (--no-scan)")
            continue
        t = time.time()
        print(f"--- {step}", flush=True)
        r = subprocess.run([sys.executable, str(HERE / step)], env=env)
        if r.returncode:
            print(f"STOPPED: {step} exited {r.returncode}")
            return r.returncode
        print(f"    {time.time() - t:.0f}s", flush=True)
    out = work_dir()
    pages = [out / ODD_PAGE, out / GAPS_PAGE]
    if not a.no_notes:
        for p in pages:
            print("copied to", copy_to_notes(p, notes_dir()))
    print("pages:", *pages, sep="\n  ")
    return 0


if __name__ == "__main__":
    sys.exit(main())
