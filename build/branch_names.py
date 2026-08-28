#!/usr/bin/env python3
"""Branch number -> branch name, read from a client's `<Client> Charts 2026` workbook.

The ODD identifies a branch only by number, so every branch chart and table shipped as
"Branch 43". The Charts 2026 file each client already has carries the mapping on its
**Branch Results** tab (`Branch #` / `Branch Name`), so the deck can name them instead
(Aaron, 2026-08-27).

Deliberately narrow: only the Branch Results tab is read. Some files carry branch numbers
on other tabs too (Mystery Shops, Goals) and those can DISAGREE — FNBT's Mystery Shops tab
calls 10 "Blanchard" and 40 "Downtown" while its Goals tab calls 10 "Downtown" and 40
"Grand". Picking between them would be a guess, so when Branch Results is missing or empty
this returns nothing and the deck keeps the numbers rather than risk mislabelling a branch.

Usage:
    from branch_names import load_map, find_charts_file, apply_to_metrics
    m = load_map(find_charts_file(inputs_dir, "Austin Bank"))
    apply_to_metrics(metrics, m)
"""
from __future__ import annotations

import glob
import os
import re

BRANCH_KEYS = ("rege_branch", "rege_new_branch", "take_branch", "take_branch_monthly")


def _norm(v):
    """Branch ids compare as strings; Excel hands back ints, the ODD hands back text."""
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return str(v).strip()


def _strip_prefix(name: str) -> str:
    """Drop a leading "Br"/"Branch" marker: the files write "Br Jacksonville Main", which
    reads as "Br Jacksonville Main" under a column already headed Branch (Aaron 2026-08-27).

    Only a SEPARATE leading token is removed — "Brentwood" and "Brownsville" keep their
    names, because the pattern requires the marker to be followed by a separator.
    """
    return re.sub(r"^(?:br|branch)\.?[\s\-]+", "", name, flags=re.I).strip()


def find_charts_file(inputs_dir: str, client_name: str) -> str | None:
    """Locate `<something> Charts 2026.xlsx` for this client.

    Names are inconsistent — "Austin ICS Charts 2026.xlsx", "Texas Bay Credit Union Charts
    2026.xlsx", "FNBT-First National Bank & Trust Co- Charts 2026.xlsx" — so match on the
    client's distinguishing words rather than expecting one pattern.
    """
    cands = glob.glob(os.path.join(inputs_dir, "*Charts 2026*.xlsx"))
    if not cands:
        return None
    stop = {"bank", "credit", "union", "cu", "fcu", "federal", "the", "company", "co",
            "and", "trust", "national", "first"}
    words = [w for w in re.findall(r"[A-Za-z]+", client_name.lower()) if w not in stop]
    best, best_score = None, 0
    for c in cands:
        base = os.path.basename(c).lower()
        score = sum(1 for w in words if w in base)
        if score > best_score:
            best, best_score = c, score
    return best if best_score else None


def load_map(charts_path: str | None) -> dict:
    """{branch number: branch name} from the Branch Results tab. {} when unavailable."""
    if not charts_path or not os.path.exists(charts_path):
        return {}
    import warnings

    import openpyxl
    warnings.filterwarnings("ignore")
    try:
        wb = openpyxl.load_workbook(charts_path, read_only=True, data_only=True)
    except Exception:
        return {}
    try:
        tab = next((t for t in wb.sheetnames if t.strip().lower() == "branch results"), None)
        if tab is None:
            return {}
        ws = wb[tab]
        rows = [list(r) for r in ws.iter_rows(min_row=1, max_row=200, max_col=12,
                                              values_only=True)]
    finally:
        wb.close()

    num_col = name_col = None
    start = None
    for i, row in enumerate(rows):
        cells = [_norm(c).lower() for c in row]
        for j, c in enumerate(cells):
            if c in ("branch #", "branch number", "branch#", "#"):
                num_col = j
            elif c in ("branch name", "branch"):
                name_col = j
        if num_col is not None and name_col is not None:
            start = i + 1
            break
        num_col = name_col = None
    if start is None:
        return {}

    out = {}
    for row in rows[start:]:
        num, name = _norm(row[num_col]), _norm(row[name_col])
        if not num and not name:
            continue                      # blank spacer row; keep scanning
        if not num or not name or not re.fullmatch(r"\d+", num):
            continue
        name = _strip_prefix(name)
        if not name:
            continue
        out.setdefault(num, name)
        # The Charts file may zero-pad ("03") where the ODD does not ("3") — Texas Bay 1509
        # pads, Austin 1075 does not. Register both so the lookup matches either way.
        out.setdefault(str(int(num)), name)
    return out


def apply_to_metrics(metrics: dict, mapping: dict) -> int:
    """Relabel branch ids in place. Returns how many rows were renamed.

    Unmapped branches keep their number: a partial file must not blank out a branch.
    """
    if not mapping:
        return 0
    renamed = 0
    for key in BRANCH_KEYS:
        rows = metrics.get(key)
        if not rows:
            continue
        new = []
        for row in rows:
            row = list(row)
            bid = _norm(row[0])          # not `key`: that is the metrics key being rebuilt
            name = mapping.get(bid)
            if name is None and bid.isdigit():
                name = mapping.get(str(int(bid)))
            if name:
                row[0] = name
                renamed += 1
            new.append(row)
        metrics[key] = new
    return renamed


if __name__ == "__main__":
    import json
    import sys
    path = sys.argv[1]
    m = load_map(path)
    print(json.dumps(m, indent=1))
    print(f"{len(m)} branches", file=sys.stderr)
