#!/usr/bin/env python3
"""ils_analysis_inputs.py — the naming convention for Inputs/ILS Analysis, and the tool that applies it.

    python scripts/ils_analysis_inputs.py                       # dry run: the plan, nothing moved
    python scripts/ils_analysis_inputs.py --client 1670         # one client
    python scripts/ils_analysis_inputs.py --apply               # do it, writing an undo list first
    python scripts/ils_analysis_inputs.py --undo <renames-...csv>

Aaron, 2026-11-06: "clean up the file names in Inputs\\ILS Analysis and create a naming convention and organization system for
those files going forward." The convention is written out in docs/ILS-ANALYSIS-INPUTS.md; this file is its one implementation,
`target()` being the function the landing step (`land_ils_analysis.py`) calls too, so a file lands where this tool would put it.

    Inputs/ILS Analysis/<client id>/<yyyymmdd>/<id>_<kind>_<yyyymmdd>.<ext>      the extracts of the pull run on that day
                                    (<yyyymm> when a legacy folder recorded only the month)
    Inputs/ILS Analysis/<client id>/<yyyymmdd>/analysis/<name as it was>          everything else from that pull, name kept
    Inputs/ILS Analysis/<client id>/_unplaced/<path as it was>                    a folder with no date the tool can read

`<kind>` is one of EXTRACT_KINDS, lower case, no spaces: the names the ILS Program Analysis builder looks for
(`build/ils_analysis/ils_review/cli.py` find_inputs). Nothing is deleted and nothing is overwritten: a move is an
`os.rename` that refuses an existing target, every move is written to `Build Artifacts/ils_analysis_inputs/renames-<stamp>.csv`
before the first one is made, and `--undo` reverses a list. Only folders the moves emptied are removed (`os.rmdir`).

Import-safe: nothing runs until main() is called.
"""
from __future__ import annotations

import argparse
import csv
import os
import re
import sys
import time
from datetime import date, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
if str(REPO / "build") not in sys.path:
    sys.path.insert(0, str(REPO / "build"))

SUBDIR = "ILS Analysis"
ANALYSIS_DIR = "analysis"
UNPLACED_DIR = "_unplaced"
YEARS = range(2005, 2036)

# The kinds of raw extract. The first group is what `ils_review.cli.find_inputs` globs for (zaccounts, ztrend, matrixval,
# dbic, debitdeclines, refundhistory); the rest are the other pulls the analysts run. Anything else is an analysis file.
EXTRACT_KINDS = (
    "zaccounts", "ztrend", "matrixval", "dbic", "debitdeclines", "refundhistory",
    "adjustments", "dataops", "cashpleaseloans", "loanhistory",
    "account_types", "branches", "institutions", "returned_deposits", "mobile_deposits", "overdraft_history",
)
EXTRACT_EXTS = {".csv", ".txt"}
_QUERY_PARTS = {"accounttypes": "account_types", "branches": "branches", "institutions": "institutions",
                "returneddeposits": "returned_deposits", "mobiledeposits": "mobile_deposits",
                "overdrafthistory": "overdraft_history"}


# ── dates ────────────────────────────────────────────────────────────────────
def _valid(y, m, d=1):
    try:
        return y in YEARS and date(y, m, d) is not None
    except ValueError:
        return False


def date_in(text):
    """A full date (yyyymmdd) written in `text` as 20260810, 2026.8.10, 2026-08-10 or 2026_08_10; else None."""
    for m in re.finditer(r"(?<!\d)(\d{4})[._-](\d{1,2})[._-](\d{1,2})(?!\d)", text):
        y, mo, d = (int(x) for x in m.groups())
        if _valid(y, mo, d):
            return f"{y:04d}{mo:02d}{d:02d}"
    for m in re.finditer(r"(?<!\d)(\d{4})(\d{2})(\d{2})(?!\d)", text):
        y, mo, d = (int(x) for x in m.groups())
        if _valid(y, mo, d):
            return f"{y:04d}{mo:02d}{d:02d}"
    return None


def month_in(text):
    """A month (yyyymm) written in `text` as 202209, 2022.09, 2022-09 or 2022_09; else None."""
    for pat in (r"(?<!\d)(\d{4})[._-](\d{2})(?!\d)", r"(?<!\d)(\d{4})(\d{2})(?!\d)"):
        for m in re.finditer(pat, text):
            y, mo = int(m.group(1)), int(m.group(2))
            if y in YEARS and 1 <= mo <= 12:
                return f"{y:04d}{mo:02d}"
    return None


# ── what a file is ───────────────────────────────────────────────────────────
def kind_of(name):
    """The extract kind a file name stands for, or None for an analysis file (a workbook, a pivot, a chart table ...)."""
    stem, ext = os.path.splitext(name)
    if ext.lower() not in EXTRACT_EXTS:
        return None
    key = re.sub(r"[^a-z0-9]", "", re.sub(r"\d{4}[._-]\d{1,2}[._-]\d{1,2}|\d{6,8}", "", stem.lower()))
    key = re.sub(r"^\d{4}", "", key) if re.match(r"^\d{4}[a-z]", key) else key        # a leading client id
    if "matrixval" in key:
        return "matrixval"
    if key.startswith("dbic"):
        return "dbic"
    if any(w in key for w in ("pivot", "validate", "summary")):
        return None
    if "refund" in key:
        return "refundhistory"
    if "debitdecline" in key:
        return "debitdeclines"
    if "dataops" in key:
        return "ztrend" if "ztrend" in key else "dataops"
    if "ztrend" in key:
        return "ztrend"
    if key.startswith("zaccounts"):
        return "zaccounts"
    if key.startswith("adjustment"):
        return "adjustments"
    if "cashplease" in key or key.startswith("cploans"):
        return "cashpleaseloans"
    if "loanhistory" in key:
        return "loanhistory"
    return _QUERY_PARTS.get(key)


def canonical_name(client, kind, ymd, ext):
    return f"{client}_{kind}_{ymd}{ext.lower()}"


# ── where a file goes ────────────────────────────────────────────────────────
def pull_date(folder_name, file_dates, inner_dates=None):
    """The day a pull was run, as yyyymmdd: the date written in its folder name; else the one date its extract files carry;
    else, when only the month was recorded (DataPull_202209, 2015_08), the month as yyyymm. A legacy folder never gets a
    day it does not state. None when the folder says no date at all."""
    d = date_in(folder_name)
    if d:
        return d
    mo = month_in(folder_name)
    for dates in (inner_dates or [], file_dates):                      # a dated folder inside, then the extract files' own dates
        uniq = sorted(set(x for x in dates if x))
        if len(uniq) == 1 and (mo is None or uniq[0][:6] == mo):
            return uniq[0]
    return mo


def _is_pull_name(name):
    """A folder already named by the convention: yyyymmdd, or yyyymm when only the month was recorded."""
    if re.fullmatch(r"\d{8}", name):
        return _valid(int(name[:4]), int(name[4:6]), int(name[6:]))
    return bool(re.fullmatch(r"\d{6}", name)) and month_in(name) == name


def target(client, rel, pull, mtime=None):
    """The path under the client's folder a file belongs at. `rel` is its path under the client's folder (parts), `pull`
    the date of its pull folder (yyyymmdd, or None). Returns (path parts, reason)."""
    name = rel[-1]
    if pull is None:
        return list(rel), "no pull date could be read; left where it is"
    filed = _is_pull_name(rel[0]) and len(rel) > 2 and rel[1] == ANALYSIS_DIR      # already under <pull>/analysis/: stays an analysis file
    kind = None if filed else kind_of(name)
    if kind:
        own = date_in(name) or pull
        return [pull, canonical_name(client, kind, own, os.path.splitext(name)[1])], f"extract: {kind}"
    below = list(rel[1:-1])
    top = rel[0].lower()
    if _is_pull_name(rel[0]) and below and below[0] == ANALYSIS_DIR:
        below = below[1:]                                        # already filed: <pull>/analysis/...
    while below and below[0].lower() == top:                    # DataPull_x/DataPull_x/file: the folder said twice
        below = below[1:]
    return [pull, ANALYSIS_DIR, *below, name], "analysis file; name kept"


# ── the plan ─────────────────────────────────────────────────────────────────
def _scan(client_dir):
    out = []
    for dp, _dn, fn in os.walk(client_dir):
        for f in fn:
            p = Path(dp) / f
            try:
                out.append((p, p.stat().st_mtime))
            except OSError:
                continue
    return out


def plan_client(client, client_dir):
    """[(old Path, new Path, reason)] for one client's folder. Idempotent: a file already in place is not listed."""
    files = _scan(client_dir)
    by_top = {}
    for p, mt in files:
        rel = p.relative_to(client_dir).parts
        if len(rel) == 1:
            continue                                            # a file loose in the client folder is left alone
        by_top.setdefault(rel[0], []).append((rel, p, mt))
    moves, taken = [], set()
    for top, group in sorted(by_top.items()):
        if top == UNPLACED_DIR:
            continue                                            # already set aside by an earlier run
        dates = [date_in(r[-1]) for r, _p, _m in group if kind_of(r[-1])]
        inner = [date_in(part) for r, _p, _m in group for part in r[1:-1]]
        pull = top if _is_pull_name(top) else pull_date(top, dates, inner)
        for rel, p, mt in sorted(group, key=lambda x: x[0]):
            parts, reason = target(client, rel, pull, mt)
            if pull is None:
                parts = [UNPLACED_DIR, *rel]
                reason = "no pull date could be read from the folder or the files"
            new = client_dir.joinpath(*parts)
            if new == p:
                continue
            key = str(new).lower()
            if key in taken:
                moves.append((p, None, f"collision: another file in this run goes to {new.name}"))
                continue
            taken.add(key)
            if new.exists():
                moves.append((p, None, f"collision: {new.name} already exists"))
                continue
            moves.append((p, new, reason))
    return moves


def plan(root, client=None):
    root = Path(root)
    out = []
    for c in sorted(os.listdir(root)):
        cd = root / c
        if not cd.is_dir() or not re.fullmatch(r"\d{4}", c) or (client and c != str(client)):
            continue
        out.extend((c, *m) for m in plan_client(c, cd))
    return out


def write_manifest(rows, folder):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"renames-{time.strftime('%Y%m%d-%H%M%S')}.csv"
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["client", "old", "new", "reason"])
        for c, old, new, why in rows:
            w.writerow([c, str(old), str(new) if new else "", why])
    return path


def apply(rows, *, say=print):
    """Make the moves. -> (moved, failed). Each is `os.rename`, which refuses an existing target."""
    moved = failed = 0
    touched = set()
    for _c, old, new, _why in rows:
        if new is None:
            continue
        try:
            new.parent.mkdir(parents=True, exist_ok=True)
            os.rename(old, new)
            moved += 1
            touched.add(old.parent)
        except OSError as exc:
            failed += 1
            say(f"  ! {old} -> {new}: {exc}")
    removed = prune_empty(touched)
    say(f"moved {moved}, failed {failed}, emptied folders removed {removed}")
    return moved, failed


def prune_empty(folders):
    """Remove each folder in `folders` (and its parents, up to the client folder) that the moves left empty."""
    removed = 0
    for f in sorted(folders, key=lambda p: -len(p.parts)):
        cur = f
        while cur.name and not re.fullmatch(r"\d{4}", cur.name):
            try:
                os.rmdir(cur)
            except OSError:
                break
            removed += 1
            cur = cur.parent
    return removed


def undo(manifest, *, say=print):
    n = 0
    with open(manifest, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if not r["new"]:
                continue
            old, new = Path(r["old"]), Path(r["new"])
            if new.exists() and not old.exists():
                old.parent.mkdir(parents=True, exist_ok=True)
                os.rename(new, old)
                n += 1
    removed = prune_empty({Path(r["new"]).parent for r in csv.DictReader(open(manifest, newline="", encoding="utf-8")) if r["new"]})
    say(f"restored {n} file(s), removed {removed} emptied folder(s)")
    return n


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--root", help="the ILS Analysis folder (default: Inputs/ILS Analysis under RPE_DATA_ROOT)")
    ap.add_argument("--client")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--undo")
    a = ap.parse_args(argv)
    import rpe_env
    if a.undo:
        undo(a.undo)
        return 0
    root = Path(a.root) if a.root else rpe_env.inputs() / SUBDIR
    rows = plan(root, a.client)
    moves = [r for r in rows if r[2] is not None]
    skipped = [r for r in rows if r[2] is None]
    unplaced = [r for r in moves if UNPLACED_DIR in r[2].parts]
    ext = sum(1 for r in moves if r[3].startswith("extract"))
    print(f"{len(moves)} to move ({ext} extracts renamed to the convention, {len(moves) - ext - len(unplaced)} analysis files "
          f"kept by name, {len(unplaced)} left under {UNPLACED_DIR}); {len(skipped)} skipped for a collision.")
    for c, old, _new, why in skipped:
        print(f"  skip {old}: {why}")
    folder = rpe_env.build_artifacts() / "ils_analysis_inputs"
    manifest = write_manifest(rows, folder)
    print(f"plan written to {manifest}")
    if not a.apply:
        print("dry run: nothing moved (add --apply).")
        return 0
    _moved, failed = apply(rows)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
