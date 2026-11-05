#!/usr/bin/env python3
"""gl_data_ingest.py — the clients' GL data and NSF performance tracking spreadsheets, as one JSON table.

    python scripts/gl_data_ingest.py                 # read what is in Inputs/GL Data, update gl_data.json, report
    python scripts/gl_data_ingest.py --archive       # ... then move each spreadsheet that was placed on a client into _Archive/
    python scripts/gl_data_ingest.py --dry-run       # read and report, write nothing

Some clients email us their general ledger (GL) income by month, or the "NSF Performance Tracking Workbook" (the ILS template that
tracks overdraft income, waivers, refunds and charge-offs). Aaron, 2026-11-03: "These should be added to a JSON table in this folder
to cover all clients. The original files can be archived." They are kept to validate our own figures against, later.

`Inputs/GL Data/gl_data.json` is the table. It is keyed by client id; each client holds one entry per spreadsheet it sent, so a
second year's file is added beside the first. A spreadsheet is one of two shapes:

    monthly_gl     a sheet of dates down the side and a column per measure (IC, NSF, Total NII, Debit Card Spend, ...), as in
                   "FSB Michigan GL.xlsx". Stored as `series`: the dates, and one list per measure.
    nsf_tracking   the ILS NSF/OD Performance Tracking workbook: a "General Ledger Data" header row of statement-cycle dates and
                   a line per item (Gross NSF income, Waivers, Refunds, ...), one sheet each for all, personal and business accounts.
                   Every line with a number is kept, with whether it was typed in or calculated, and the key lines are also
                   gathered under `standard` with one name each, so a validation does not have to know each client's wording.

Which client: a leading client number in the file name, else a name in `aliases.json` beside the table ({"fsb michigan": "1204"}),
else the file stays where it is and the report says so. A file is archived (`_Archive/<id> <client>/`, never deleted) only after
its figures are in the table and read back from it. A workbook that is the blank template (no client's own figures) is reported
as one and left alone.

The workbook's own dates are kept as they are. In the tracking workbook they are statement-cycle dates (11 Jan, 10 Feb, ...), so a
column's calendar month is not necessarily the month the activity happened in.

Import-safe: nothing runs until main() is called.
"""
import argparse
import csv
import datetime
import hashlib
import json
import os
import re
import shutil
import sys
import warnings
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
for _p in (REPO / "build", HERE):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

TABLE = "gl_data.json"
ALIASES = "aliases.json"
ARCHIVE = "_Archive"
SCHEMA = 1

# The few measures every client's workbook is gathered under, by what the line is called (matched on the cleaned lower-case label).
STANDARD = [
    ("gross_nsf_income", re.compile(r"^gross/?potential nsf(/od)? income \(item\)$")),
    ("waivers", re.compile(r"^waivers$")),
    ("refunds", re.compile(r"^refunds( \(minus charge offs\))?$")),
    ("net_nsf_income", re.compile(r"^net nsf(/od)? income( \(prior to cos\)| \(prior to cont od fees\))?$")),
    ("continuous_od_fees", re.compile(r"^continuous od fees$")),
    ("net_continuous_od_fees", re.compile(r"^net continuous od fees$")),
    ("charge_offs", re.compile(r"^charge offs( \(total principal and fees\))?( - (personal|business) accounts)?$")),
    ("recoveries", re.compile(r"^recoveries$")),
]
GL_MEASURES = {"ic": "interchange_income", "nsf": "nsf_income", "total nii": "total_nii",
               "debit card spend": "debit_card_spend", "ic rate": "ic_rate"}


# ----------------------------------------------------------------------------------------------- helpers
def _clean(label):
    return re.sub(r"\s+", " ", str(label or "")).strip().lower()


def _iso(v):
    return v.date().isoformat() if isinstance(v, datetime.datetime) else v.isoformat()


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def _scope(sheet):
    s = sheet.lower()
    return "personal" if "personal" in s else "business" if "business" in s else "all"


def _open(path, data_only):
    import openpyxl
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return openpyxl.load_workbook(path, read_only=True, data_only=data_only)


# ----------------------------------------------------------------------------------------------- the two shapes
def _monthly_gl(wb):
    """A sheet of dates down column A and a column per measure: the series, or None when no sheet looks like that."""
    for ws in wb.worksheets:
        rows = [list(r) for r in ws.iter_rows(values_only=True)]
        if len(rows) < 3 or not isinstance(rows[0][0], str):
            continue
        data = [r for r in rows[1:] if isinstance(r[0], (datetime.datetime, datetime.date))]
        if len(data) < 3:
            continue
        head = rows[0]
        last = 0
        for c in range(1, len(head)):                       # columns run on from B until one has nothing in any dated row
            if any(_num(r[c]) for r in data if c < len(r)):
                last = c
            elif c > last:
                break
        if last == 0:
            continue
        cols, other = {}, {}
        for c in range(1, last + 1):
            name = _clean(head[c]) if c < len(head) and head[c] else ""
            key = GL_MEASURES.get(name) or ("col_" + chr(ord("a") + c)) if not name else GL_MEASURES.get(name, re.sub(r"[^a-z0-9]+", "_", name).strip("_"))
            vals = [r[c] if c < len(r) and _num(r[c]) else None for r in data]
            (cols if not name or name in GL_MEASURES else other)[key] = vals
        cols.update(other)
        dates = [_iso(r[0]) for r in data]
        return {"sheet": ws.title, "title": rows[0][0].strip(), "dates": dates, "columns": cols,
                "unlabeled_columns": [k for k in cols if k.startswith("col_")]}
    return None


def _tracking(path):
    """The ILS NSF/OD Performance Tracking workbook: every sheet with a 'General Ledger Data' header row, or None."""
    vals, forms = _open(path, True), _open(path, False)
    sheets = []
    for ws in vals.worksheets:
        rows = [list(r) for r in ws.iter_rows(values_only=True)]
        frows = [list(r) for r in forms[ws.title].iter_rows(values_only=True)]
        hi = lc = None
        for i, r in enumerate(rows):
            for c in (0, 1):
                if c < len(r) and isinstance(r[c], str) and r[c].strip().lower().startswith("general ledger data"):
                    hi, lc = i, c
                    break
            if hi is not None:
                break
        if hi is None:
            continue
        dcols = [(j, v) for j, v in enumerate(rows[hi]) if isinstance(v, (datetime.datetime, datetime.date))]
        if not dcols:
            continue
        lines, group = [], None
        for i in range(hi + 1, len(rows)):
            r, fr = rows[i], (frows[i] if i < len(frows) else [])
            label = r[lc] if lc < len(r) else None
            if not isinstance(label, str) or not label.strip():
                continue
            nums = [(j, r[j]) for j, _ in dcols if j < len(r) and _num(r[j])]
            if not nums:
                group = label.strip()
                continue
            nform = sum(1 for j, _ in nums if j < len(fr) and isinstance(fr[j], str) and fr[j].startswith("="))
            kind = "formula" if nform >= 0.9 * len(nums) else "input" if nform <= 0.1 * len(nums) else "mixed"
            item = r[0] if lc == 1 and _num(r[0]) else None
            byc = dict(nums)
            lines.append({"row": i + 1, "item": int(item) if item is not None else None, "group": group, "label": label.strip(),
                          "kind": kind, "values": [byc.get(j) for j, _ in dcols]})
        sheets.append({"sheet": ws.title.strip(), "scope": _scope(ws.title), "header_row": hi + 1,
                       "dates": [_iso(v) for _, v in dcols], "lines": lines})
    vals.close()
    forms.close()
    return sheets or None


def _standard(sheets):
    """{scope: {measure: {date: value}}} for the key lines of the all, personal and business sheets."""
    out = {}
    for sh in sheets:
        for ln in sh["lines"]:
            lab = _clean(ln["label"])
            for key, rx in STANDARD:
                if rx.match(lab):
                    ser = {d: v for d, v in zip(sh["dates"], ln["values"]) if v is not None}
                    if ser and key not in out.setdefault(sh["scope"], {}):
                        out[sh["scope"]][key] = ser
                    break
    return out


def _quality(sheets):
    """How much of a tracking workbook is a client's own figures: a template carries one example value per line."""
    lines = [ln for sh in sheets for ln in sh["lines"]]
    with_data = [ln for ln in lines if any(v is not None for v in ln["values"])]
    flat = [ln for ln in with_data if len({v for v in ln["values"] if v is not None}) <= 2]
    dates = sorted({d for sh in sheets for ln in sh["lines"] for d, v in zip(sh["dates"], ln["values"]) if v})
    gross = [ln for ln in with_data if _clean(ln["label"]).startswith("gross/potential nsf") and ln["kind"] == "input"]
    template = bool(with_data) and len(flat) >= 0.7 * len(with_data) and all(len([v for v in g["values"] if v is not None]) <= 2 for g in gross)
    return {"lines": len(lines), "lines_with_numbers": len(with_data), "lines_with_one_or_two_values": len(flat),
            "first_date_with_data": dates[0] if dates else None, "last_date_with_data": dates[-1] if dates else None,
            "template_only": template}


# ----------------------------------------------------------------------------------------------- the table
def read_workbook(path):
    """The source entry for one spreadsheet, or (None, why) when it is neither shape."""
    path = Path(path)
    wb = _open(path, True)
    props = wb.properties
    base = {"file": path.name, "sha256": _sha(path), "bytes": path.stat().st_size,
            "workbook_author": props.creator, "workbook_last_modified_by": props.lastModifiedBy,
            "workbook_modified": props.modified.isoformat() if props.modified else None}
    sheets = _tracking(path)
    if sheets:
        wb.close()
        return dict(base, kind="nsf_tracking", sheets=sheets, standard=_standard(sheets), quality=_quality(sheets)), None
    series = _monthly_gl(wb)
    wb.close()
    if series:
        dates = series["dates"]
        return dict(base, kind="monthly_gl", series=series,
                    quality={"months": len(dates), "first_date": dates[0], "last_date": dates[-1]}), None
    return None, "neither a monthly GL sheet nor an NSF/OD Performance Tracking workbook"


def client_names():
    import rpe_env
    out = {}
    try:
        with open(rpe_env.data_root() / "Client CSM List.csv", encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                if r.get("client_id"):
                    out[str(r["client_id"]).strip()] = (r.get("client_name") or "").strip()
    except OSError:
        pass
    return out


def resolve_client(filename, aliases):
    """(client id, how) from the file name: a leading client number, else an alias in aliases.json; (None, why) otherwise."""
    m = re.match(r"^\s*(\d{3,5})\b", filename)
    if m:
        return m.group(1), "the client number at the start of the file name"
    low = filename.lower()
    hits = {cid for alias, cid in aliases.items() if alias.lower() in low}
    if len(hits) == 1:
        return hits.pop(), "an alias in aliases.json"
    if len(hits) > 1:
        return None, "the file name matches more than one client in aliases.json"
    return None, "no client number in the file name and no alias for it in aliases.json"


def load_table(path):
    if Path(path).is_file():
        return json.loads(Path(path).read_text(encoding="utf-8"))
    return {"schema": SCHEMA, "clients": {}, "unassigned": []}


def add_source(table, cid, name, entry, how):
    """Put `entry` on the client, replacing an earlier read of the same spreadsheet (same bytes or same file name)."""
    ent = table["clients"].setdefault(cid, {"client_name": name, "sources": []})
    ent["client_name"] = name or ent.get("client_name")
    ent["sources"] = [s for s in ent["sources"] if s["sha256"] != entry["sha256"] and s["file"] != entry["file"]]
    ent["sources"].append(dict(entry, placed_by=how))
    ent["sources"].sort(key=lambda s: s["file"])


def run(folder=None, archive=False, dry_run=False, say=print):
    import rpe_env
    folder = Path(folder) if folder else rpe_env.input_dir("GL Data", create=False)
    tpath = folder / TABLE
    table = load_table(tpath)
    table.update(schema=SCHEMA, generated=datetime.datetime.now().isoformat(timespec="minutes"))
    try:
        aliases = {k.lower(): str(v) for k, v in json.loads((folder / ALIASES).read_text(encoding="utf-8")).items()}
    except (OSError, ValueError):
        aliases = {}
    names = client_names()
    report = {"placed": [], "left": [], "archived": []}
    files = sorted(p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in (".xlsx", ".xlsm") and not p.name.startswith("~$"))
    for p in files:
        try:
            entry, why = read_workbook(p)
        except Exception as e:
            entry, why = None, f"could not be read: {type(e).__name__}: {e}"
        if entry is None:
            report["left"].append((p.name, why))
            continue
        if entry["kind"] == "nsf_tracking" and entry["quality"]["template_only"]:
            report["left"].append((p.name, "the blank NSF/OD Performance Tracking template: no client's own figures in it"))
            continue
        cid, how = resolve_client(p.name, aliases)
        if cid is None:
            table["unassigned"] = [s for s in table["unassigned"] if s["sha256"] != entry["sha256"]] + [dict(entry, why_unassigned=how)]
            report["left"].append((p.name, how + "; its figures are kept under `unassigned` until it has a client"))
            continue
        add_source(table, cid, names.get(cid, ""), entry, how)
        report["placed"].append((p.name, cid, names.get(cid, ""), entry["kind"]))
    if dry_run:
        return report
    folder.mkdir(parents=True, exist_ok=True)
    part = tpath.with_name(TABLE + ".part")
    part.write_text(json.dumps(table, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    back = json.loads(part.read_text(encoding="utf-8"))                       # read it back before the table or any original changes
    for fname, cid, _n, _k in report["placed"]:
        assert any(s["file"] == fname for s in back["clients"][cid]["sources"]), f"{fname} is not in the table"
    os.replace(part, tpath)
    if archive:
        for fname, cid, cname, _k in report["placed"]:
            dest = folder / ARCHIVE / (f"{cid} {cname}".strip())
            dest.mkdir(parents=True, exist_ok=True)
            target = dest / fname
            if target.exists():
                target = dest / (target.stem + "." + datetime.date.today().isoformat() + target.suffix)
            shutil.move(str(folder / fname), str(target))
            rel = target.relative_to(folder).as_posix()
            for s in table["clients"][cid]["sources"]:
                if s["file"] == fname:
                    s["archived_to"] = rel
            report["archived"].append((fname, rel))
        tpath.write_text(json.dumps(table, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    return report


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--folder", help="default: Inputs/GL Data")
    ap.add_argument("--archive", action="store_true", help="move each spreadsheet placed on a client into _Archive/")
    ap.add_argument("--dry-run", action="store_true", help="read and report, write nothing")
    a = ap.parse_args(argv)
    r = run(a.folder, a.archive, a.dry_run)
    for fname, cid, cname, kind in r["placed"]:
        print(f"placed    {fname}  ->  {cid} {cname}  ({kind})")
    for fname, why in r["left"]:
        print(f"left      {fname}: {why}")
    for fname, to in r["archived"]:
        print(f"archived  {fname}  ->  {to}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
