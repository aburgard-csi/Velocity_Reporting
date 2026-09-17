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

BRANCH_KEYS = ("rege_branch", "rege_new_branch", "take_branch", "take_branch_monthly",
               "rege_branch_table")


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



# ------------------------------------------------------------------ the branch-name dataset
# Aaron, 2026-09-17: "create a branch mapping data set in inputs and update it when new branch
# names are discovered." One CSV, `Inputs/Branch Names/branch_names.csv`, one row per name a
# source has ever given a client's branch number. The morning source check
# (`watch_sources.py --branch-names`) adds what it finds and moves `last_seen`; nothing is ever
# removed, so a renamed or closed branch keeps its history.
#
# Two sources, both keyed so a name can never land on the wrong client:
#   * the client's Charts workbook, Branch Results tab (`load_map`), matched to a client id by
#     its filename only when exactly one client's whole name fits it; an ambiguous or unmatched
#     file is reported, never guessed at;
#   * the ICS referrals pull (`Inputs/ICS Referrals/ics_referrals.csv`), which carries client_id,
#     branch_number and branch_name from the VIP branch table.
# `client_map` reads it back: the Charts name wins over the VIP name; a number one source gives
# two different names is left unnamed. The deck's own coverage check (most of the ODD's branch
# ids must resolve) still applies, because a client's ODD can number branches differently.
DATASET_KIND = "Branch names"
DATASET_NAME = "branch_names.csv"
DATASET_COLUMNS = ["client_id", "client_name", "branch_number", "branch_name", "source",
                   "source_file", "first_seen", "last_seen"]
SRC_CHARTS = "Charts workbook, Branch Results tab"
SRC_REFERRALS = "ICS referrals pull (VIP branch table)"
# A Charts file whose name does not identify one client (Charts names are informal: "CapEd CU"
# for Capital Educators FCU) is matched by a person, one row per file: charts_file,client_id.
CHARTS_INDEX_NAME = "charts_files.csv"
_TYPE_RX = [(re.compile(r"\bfederal\s+credit\s+union\b"), " fcu "),
            (re.compile(r"\bfederal\s+cu\b"), " fcu "),
            (re.compile(r"\bcredit\s+union\b"), " cu ")]
_FILE_STOP = {"the", "and", "of", "co", "company", "inc", "charts", "chart", "ics", "for", "use",
              "this", "one", "formerly", "fka", "results"}


def _tokens(text):
    t = " " + str(text).lower().replace("&", " and ") + " "
    for rx, rep in _TYPE_RX:
        t = rx.sub(rep, t)
    return {w for w in re.findall(r"[a-z0-9]+", t) if w not in _FILE_STOP and not w.isdigit()}


def match_charts_client(filename, clients):
    """(client_id, client_name) whose whole name fits this Charts filename, or None.

    Every word of the client's name must appear in the filename ("federal credit union" and
    "credit union" are read as FCU and CU, so Marine FCU and Marine Credit Union stay apart),
    and exactly one client may fit with the most words. A tie is ambiguous and returns None.
    """
    base = os.path.splitext(os.path.basename(filename))[0]
    if re.match(r"^z\s*-", base, re.I):              # the Charts team's prefix for ended clients
        return None
    have = _tokens(base)
    best, score, tie = None, 0, False
    for cid, name in clients:
        need = _tokens(name)
        if not need or not need <= have:
            continue
        if len(need) > score:
            best, score, tie = (str(cid), name), len(need), False
        elif len(need) == score:
            tie = True
    return None if tie else best


def _num(v):
    v = _norm(v)
    return str(int(v)) if v.isdigit() else v


def _same_name(a, b):
    strip = lambda n: re.sub(r"\s+branch$", "", n.strip(), flags=re.I).lower()
    return strip(a) == strip(b)


def dataset_path():
    import rpe_env as R
    return str(R.input_dir(DATASET_KIND) / DATASET_NAME)


def read_dataset(path=None):
    path = path or dataset_path()
    if not os.path.exists(path):
        return []
    import csv
    with open(path, newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def read_charts_index(path):
    """{charts file name (lower case): client id} from the hand-kept index."""
    import csv
    if not path or not os.path.exists(path):
        return {}
    with open(path, newline="", encoding="utf-8-sig") as fh:
        return {r["charts_file"].strip().lower(): r["client_id"].strip()
                for r in csv.DictReader(fh) if r.get("charts_file") and r.get("client_id")}


def charts_observations(charts_dir, clients, index=None):
    """([(client_id, client_name, number, name, source_file)], [report lines])."""
    obs, notes = [], []
    names = {str(c): n for c, n in clients}
    index = index or {}
    for path in sorted(glob.glob(os.path.join(str(charts_dir), "*.xlsx"))):
        fname = os.path.basename(path)
        if fname.startswith("~$"):
            continue
        cid = index.get(fname.lower())
        hit = (cid, names.get(cid, "")) if cid else match_charts_client(fname, clients)
        if hit is None:
            if not re.match(r"^z\s*-", fname, re.I):
                notes.append("- Charts file not matched to one client (add it to `%s`): `%s`"
                             % (CHARTS_INDEX_NAME, fname))
            continue
        m = load_map(path)
        seen = set()
        for num, name in m.items():
            key = _num(num)
            if key in seen:                           # load_map registers "03" and "3"
                continue
            seen.add(key)
            obs.append((hit[0], hit[1], key, name, fname))
    return obs, notes


def referral_observations(referrals_csv):
    """[(client_id, client_name, number, name, source_file)] from the merged ICS referrals pull."""
    import csv
    if not referrals_csv or not os.path.exists(referrals_csv):
        return []
    found = {}
    with open(referrals_csv, newline="", encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            num, name = _num(row.get("branch_number")), _norm(row.get("branch_name"))
            if not num or num == "NULL" or not name or name == "NULL":
                continue
            found.setdefault((row["client_id"], num, _strip_prefix(name)), row.get("client_name", ""))
    fname = os.path.basename(referrals_csv)
    return [(cid, cname, num, name, fname) for (cid, num, name), cname in sorted(found.items())]


def update_dataset(observations, path=None, today=None):
    """Fold observations into the dataset. Returns the rows that are new names."""
    import csv
    import datetime as _dt
    path = path or dataset_path()
    today = today or _dt.date.today().isoformat()
    rows = read_dataset(path)
    index = {(r["client_id"], r["branch_number"], r["branch_name"], r["source"]): r for r in rows}
    new = []
    for source, items in observations:
        for cid, cname, num, name, sfile in items:
            key = (str(cid), num, name, source)
            r = index.get(key)
            if r:
                r["last_seen"], r["source_file"] = today, sfile
                continue
            r = dict(client_id=str(cid), client_name=cname, branch_number=num, branch_name=name,
                     source=source, source_file=sfile, first_seen=today, last_seen=today)
            index[key] = r
            rows.append(r)
            new.append(r)
    rows.sort(key=lambda r: (int(r["client_id"]) if r["client_id"].isdigit() else 10 ** 9,
                             int(r["branch_number"]) if r["branch_number"].isdigit() else 10 ** 9,
                             r["branch_number"], r["source"], r["branch_name"]))
    part = path + ".part"
    with open(part, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=DATASET_COLUMNS)
        w.writeheader()
        w.writerows(rows)
    os.replace(part, path)
    return new


def _one_name(names):
    """The single name a source gives a branch, or None when it gives two different ones.
    "North Shore" and "North Shore Branch" are one name; the shorter is kept."""
    names = sorted(set(names), key=len)
    return names[0] if names and all(_same_name(names[0], n) for n in names[1:]) else None


def client_map(client_id, path=None, rows=None):
    """{branch number: name} for one client from the dataset; numbers are registered both as
    written and without leading zeros, like `load_map`. Charts names win over VIP names."""
    rows = rows if rows is not None else read_dataset(path)
    by = {}
    for r in rows:
        if r["client_id"] == str(client_id):
            by.setdefault(r["branch_number"], {}).setdefault(r["source"], []).append(r["branch_name"])
    out = {}
    for num, sources in by.items():
        name = None
        for src in (SRC_CHARTS, SRC_REFERRALS):
            if src in sources:
                name = _one_name(sources[src])
                if name:
                    break
        if name:
            out.setdefault(num, name)
            if num.isdigit():
                out.setdefault(str(int(num)), name)
    return out


def conflicts(rows):
    """[(client_id, number, charts name, VIP name)] where the two sources disagree."""
    by = {}
    for r in rows:
        by.setdefault((r["client_id"], r["branch_number"]), {}).setdefault(r["source"], []).append(r["branch_name"])
    out = []
    for (cid, num), s in sorted(by.items()):
        c, v = _one_name(s.get(SRC_CHARTS, [])), _one_name(s.get(SRC_REFERRALS, []))
        if c and v and not _same_name(c, v):
            out.append((cid, num, c, v))
    return out


def morning_update(dry_run=False, today=None):
    """The source check's step: report lines, never raises."""
    head = ["", "## Branch names", ""]
    try:
        import csv
        import rpe_env as R
        with open(str(R.data_root() / R.CSM_LIST_NAME), newline="", encoding="utf-8-sig") as fh:
            clients = [(r["client_id"], r["client_name"]) for r in csv.DictReader(fh)
                       if r.get("client_id") and r.get("client_name")]
        index_path = str(R.input_dir(DATASET_KIND) / CHARTS_INDEX_NAME)
        if not os.path.exists(index_path) and not dry_run:
            with open(index_path, "w", encoding="utf-8", newline="") as fh:
                fh.write("charts_file,client_id\n")
        charts, notes = charts_observations(R.input_dir("ICS charts", create=False), clients,
                                            read_charts_index(index_path))
        refs = referral_observations(str(R.input_dir("ICS referrals", create=False) / "ics_referrals.csv"))
        if dry_run:
            known = {(r["client_id"], r["branch_number"], r["branch_name"], r["source"])
                     for r in read_dataset()}
            new = [o for src, items in ((SRC_CHARTS, charts), (SRC_REFERRALS, refs))
                   for o in items if (str(o[0]), o[2], o[3], src) not in known]
            lines = ["- would add %d new branch names" % len(new)]
        else:
            added = update_dataset([(SRC_CHARTS, charts), (SRC_REFERRALS, refs)], today=today)
            rows = read_dataset()
            lines = ["- %d new branch names added to `%s` (%d names for %d clients in all)" % (
                len(added), DATASET_NAME, len(rows), len({r["client_id"] for r in rows}))]
            lines += ["  - %s %s: %s %s (%s)" % (r["client_id"], r["client_name"], r["branch_number"],
                                                 r["branch_name"], r["source"]) for r in added[:25]]
            if len(added) > 25:
                lines.append("  - and %d more" % (len(added) - 25))
            diff = conflicts(rows)
            if diff:
                lines.append("- %d branch numbers where the Charts workbook and VIP give different "
                             "names (the Charts name is used)" % len(diff))
        return head + lines + notes
    except Exception as e:
        return head + ["- FAILED: %s: %s" % (type(e).__name__, e)]

if __name__ == "__main__":
    import json
    import sys
    path = sys.argv[1]
    m = load_map(path)
    print(json.dumps(m, indent=1))
    print(f"{len(m)} branches", file=sys.stderr)
