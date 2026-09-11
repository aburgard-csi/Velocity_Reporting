#!/usr/bin/env python3
"""
build_cashplease.py — build the CashPlease deck for every client on the roster.

Runs `cp_extract` then `build_cp_gen` per client and validates each deck with
`validation/validate_deck.py`, whose text-over-text rule now covers what the
CashPlease project's own `cp_qa.py` used to.

The roster is `clients.md`, never the workbook: the weekly workbook carries every
Velocity CashPlease client across all CSMs, so a tab proves a client is LIVE on the
program and proves nothing about whether a deck is wanted. A cancelled client is
skipped BY NAME with the reason stated — their tab keeps arriving every week, and
leftover data is never a signal to build (CLAUDE.md).

Usage:
    python scripts/build_cashplease.py [--workbook <xlsx>] [--period 2026.09]
                                       [--only 1632,1539]
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
for _p in (REPO / "build", REPO / "scripts"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import rpe_env
from build_month import read_cashplease_roster

PIPELINE = REPO / "build" / "cashplease_pipeline"
TEMPLATE = REPO / "templates" / "cashplease_template.pptx"
VALIDATOR = REPO / "validation" / "validate_deck.py"
PACKS = rpe_env.build_artifacts() / "cashplease" / "packs"
OUT = rpe_env.outputs()          # finished decks only; evidence goes to Build Artifacts


def newest(pattern):
    """The newest matching input, by FILENAME.

    Both inputs carry a sortable date stamp, so name order is date order. Modification
    time is not used: copying a file onto the pipeline rewrites its mtime, which would
    make a re-copied older workbook look like the newest one.
    """
    found = rpe_env.report_files(pattern)
    return found[-1] if found else None


def safe(name):
    """Filenames carry client names verbatim except for characters Windows rejects."""
    for ch in '<>:"/\\|?*':
        name = name.replace(ch, "")
    return name.strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workbook")
    ap.add_argument("--period", default="2026.08")
    ap.add_argument("--only", help="comma-separated client ids")
    a = ap.parse_args()

    wb = Path(a.workbook) if a.workbook else newest("CashPleaseSummary*.xlsx")
    if wb is None:
        raise SystemExit(f"no CashPleaseSummary*.xlsx under {rpe_env.inputs()} — save "
                         f"Bradford Sanders' weekly 'CashPlease Summary' attachment to "
                         f"{rpe_env.input_dir('weekly', create=False)} first")
    print(f"workbook: {wb.name}")

    # The DDA denominator. Without it every client silently loses its loans-per-DDA
    # rate — which is exactly what happened on the first run of this metric, because
    # cp_extract was still being called with two arguments. Absence is reported here
    # rather than left to look like 71 clients genuinely having no count.
    dda_json = None
    dda_txt = newest("ILS-DDA-Count-*.txt")
    if dda_txt:
        dda_json = rpe_env.build_artifacts() / "cashplease" / "dda_counts.json"
        dda_json.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([sys.executable, str(PIPELINE / "dda_counts.py"),
                        str(dda_txt), str(dda_json)], check=True)
        print(f"DDA counts: {dda_txt.name}")
    else:
        print(f"DDA counts: NONE under {rpe_env.inputs()} — no loans-per-DDA rate will be "
              f"shown on any deck. Save the weekly 'ILS Management Server DDA Count' "
              f"email body as Inputs/ILS-DDA-Count-<YYYY-MM-DD>.txt to enable it.")

    cmd = [sys.executable, str(PIPELINE / "cp_extract.py"),
           str(wb), str(PACKS)]
    if dda_json:
        cmd.append(str(dda_json))
    subprocess.run(cmd, check=True)

    idx = json.loads((PACKS / "index.json").read_text(encoding="utf-8"))
    only = {s.strip() for s in a.only.split(",")} if a.only else None

    # The roster decides. The workbook carries every Velocity CashPlease client across
    # all CSMs, so a tab means the client is LIVE on the program, never that a deck is
    # wanted (clients.md, and the CoastLife-ICS lesson it opens with).
    roster = {r["client_id"]: r for r in read_cashplease_roster()}
    print(f"roster: clients.md — {sum(1 for r in roster.values() if r['build'])} to build")

    packed = {c["client_id"] for c in idx["clients"]}
    absent = [f"{r['client_id']} {r['client_name']}" for r in roster.values()
              if r["build"] and r["client_id"] not in packed]

    built, skipped, failed = [], [], []
    for rec in idx["clients"]:
        cid, name = rec["client_id"], rec["client_name"]
        if only and cid not in only:
            continue
        row = roster.get(cid)
        if row is None:
            continue                     # another CSM's client — not ours to build
        if not row["build"]:
            skipped.append(f"{cid} {name} — roster says no"
                           + (f" ({row['note']})" if row["note"] else ""))
            continue
        if rec.get("cancelled"):
            skipped.append(f"{cid} {name} — {rec['cancelled']}")
            continue
        out = OUT / f"{cid}-{a.period}-CP-{safe(name)} CashPlease Module.pptx"
        r = subprocess.run([sys.executable,
                            str(PIPELINE / "build_cp_gen.py"),
                            str(PACKS / f"{cid}_cashplease.json"),
                            str(TEMPLATE), str(out)],
                           capture_output=True, text=True)
        if r.returncode != 0:
            failed.append(f"{cid} {name}: {r.stderr.strip().splitlines()[-1:]}")
            continue
        v = subprocess.run([sys.executable, str(VALIDATOR), str(out)],
                           capture_output=True, text=True)
        tail = v.stdout.strip().splitlines()[-1] if v.stdout.strip() else ""
        if v.returncode != 0:
            failed.append(f"{cid} {name}: validation {tail}")
            continue
        built.append(f"{cid} {name} — {tail.strip()}")

    print(f"\nbuilt {len(built)}, skipped {len(skipped)}, failed {len(failed)}")
    for s in skipped:
        print("  skip:", s)
    for x in built:
        print("  ok:  ", x)
    for x in absent:
        print(f"  MISSING: {x} is on the roster but has no tab in this workbook — "
              f"no module built. Ask the data team, do not drop the row.")
    for f in failed:
        print("  FAIL:", f)
    if idx["flags"]:
        # The packs cover EVERY workbook tab because the peer cohort spans all of them,
        # so these flags name clients no module is built for. Saying so stops the list
        # reading as a pile of gaps in the delivery.
        print("\nextract flags (all workbook tabs — the peer cohort spans every client, "
              "so these name clients no module is built for):")
        for f in idx["flags"]:
            print("  ", f)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
