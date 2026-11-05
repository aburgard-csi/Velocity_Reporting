"""
Command line for the ILS Program Analysis deck.

PROVENANCE: the analysis team's `cli.py`. The template, rebrand and stale-data flags are gone (the deck is
built from blank RPE slides, see template.py) and the new extracts (debit declines, refund history) and the
client id (which names the file and resolves the logo and CSM) are added. The desktop GUI is not carried over.

    python -m ils_review.cli --from-folder "<...>\\DataPull_20260911" --client "Achieva Credit Union" --client-id 1544 \\
        --out-dir "<RPE_DATA_ROOT>\\Build Artifacts\\ils_analysis\\out"

Run it with `build/ils_analysis` as the working directory's import root (`python -m` from there), never from
inside a client's data folder.
"""
from __future__ import annotations

import argparse
import glob
import os
import re
import sys

from .config import DEFAULT_SECTIONS, SECTIONS, BuildConfig


def _find(folder, *patterns):
    for pat in patterns:
        hits = sorted(glob.glob(os.path.join(folder, pat)), key=os.path.getmtime, reverse=True)
        hits = [h for h in hits if os.path.isfile(h)]
        if hits:
            return hits[0]
    return None


def find_inputs(folder):
    """The extracts in one data-pull folder, found by file name (newest wins)."""
    return {
        "zaccounts_path": _find(folder, "*zaccounts*.csv", "*zaccounts*.txt"),
        "ztrend_path": _find(folder, "*ztrend*.csv", "*ztrend*.txt"),
        "matrix_path": _find(folder, "*matrixval*.txt"),
        "dbic_path": _find(folder, "*dbic*.txt"),
        "declines_path": _find(folder, "*debitdecline*.csv"),
        "refunds_path": _find(folder, "*refundhistory*.csv"),
    }


def main(argv=None):
    ap = argparse.ArgumentParser(prog="ils_review", description="Build the ILS Program Analysis deck.")
    ap.add_argument("--from-folder", help="a client's data-pull folder; the extracts are found by file name")
    ap.add_argument("--client", help="organization reviewed (titles the deck)")
    ap.add_argument("--client-id", default="", help="client number (names the file; resolves logo and CSM)")
    for name in ("zaccounts", "ztrend", "matrix", "dbic", "declines", "refunds", "logic-image"):
        ap.add_argument(f"--{name}")
    ap.add_argument("--out-dir", help="folder for the deck (never Outputs/: that holds finished client decks)")
    ap.add_argument("--chart-dir", help="folder for the chart PNGs and their sidecars")
    ap.add_argument("--sections", help="comma-separated section keys, in order")
    ap.add_argument("--list-sections", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--all-rows", action="store_true")
    ap.add_argument("--exclude-branches", default="")
    ap.add_argument("--digital-branches", default="")
    ap.add_argument("--retail-branches", default="")
    ap.add_argument("--exclude-digital", action="store_true")
    ap.add_argument("--default-basis", choices=("deck", "readme"), default="deck",
                    help="Scoring Summary default rule: the hand-built deck's (40 days, never-repaid excluded) or the README's")
    a = ap.parse_args(argv)

    if a.list_sections:
        for k, s in SECTIONS.items():
            print(f"{k:18s} {s.label}")
        return 0
    paths = find_inputs(a.from_folder) if a.from_folder else {}
    for k, v in (("zaccounts_path", a.zaccounts), ("ztrend_path", a.ztrend), ("matrix_path", a.matrix),
                 ("dbic_path", a.dbic), ("declines_path", a.declines), ("refunds_path", a.refunds)):
        if v:
            paths[k] = v
    if not paths.get("zaccounts_path"):
        ap.error("a ZAccounts file is required (--from-folder or --zaccounts)")
    client = a.client
    if not client:
        from .ils_data import client_from_folder
        client = client_from_folder(paths["zaccounts_path"])
    sections = [s.strip() for s in a.sections.split(",")] if a.sections else list(DEFAULT_SECTIONS)
    cfg = BuildConfig(client_name=client, client_id=a.client_id, sections=sections, output_dir=a.out_dir,
                      chart_dir=a.chart_dir, show_all_rows=a.all_rows, exclude_branches=a.exclude_branches,
                      digital_branches=a.digital_branches, retail_branches=a.retail_branches,
                      include_digital=not a.exclude_digital, logic_image=a.logic_image, **paths)
    cfg.default_basis = a.default_basis
    from . import build
    if a.dry_run:
        print("\n".join(build.summarize(cfg)))
        return 0
    out = build.build_review(cfg, progress=print)
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
