#!/usr/bin/env python3
"""
ics_local_sheet.py — an ICS client sheet built from LOCAL files, for a client with no VIP sheet.

`build_ics_gen.py` reads one per-client JSON. For every other ICS client that JSON is the
VIP ICS sheet under `Inputs/VIP Data/ICS/`. 1776 CoastHills CU has none and none will be
pulled — Aaron has no VIP access to that client (2026-09-16: "Add ICS, but don't pull from
VIP ... Run the ICS slides using what's available"). The CSM put these in `Inputs/` instead:

  * `Inputs/ICS Referrals/<id>_ics_detailed referral_v<N>.xls` — one row per referral
    (Issue Date, Branch, Cert ID, ...). Supplies the referral sections.
  * `Inputs/ICS Workbooks/<id>-<yyyy.mm>-...Invitation Checking Workbook...xlsx` — read by
    the existing `ics_workbook_extract.extract`, and ONLY when its period is the deck's own
    (CLAUDE.md: financial detail ships only for the deck's own period).
  * `Inputs/ICS Charts/<Client> ICS Charts 2026.xlsx` — its Goals tab gives branch names
    and each branch's MONTHLY goal (the same tab VIP branch names are reconciled to).
  * `Inputs/ICS Direct Mail/<id>-<yyyy.mm>-ICS-...Direct Mail New Accounts Opened PTD.xlsx`
    — the direct-mail channel's new accounts, in the sheet's `direct_mail` block (its own ICS slide),
    NEVER added to the referral counts: it is a different channel (3 of 1776's 384 DM
    account holders also appear in the referral file).

A client with the period's ICS workbook and NOTHING else — no VIP sheet, no referral file —
gets the "workbook-only" shape (Aaron, 2026-10-13, 1195 KEMBA CU: "Add a workbook-only ICS
shape that draws the opening counts from Monthly Detail and the branch tab"). `read_workbook_openings`
fills the `referrals` block from the workbook's "Accounts Opened via Invitation Checking
System" row and its "DDA Openings by Branch" tab. **That row counts referrals** (Aaron,
2026-10-13: "The monthly detail tab in the workbook is counting referrals in the Accounts
Opened via Invitation Checking System row"), so the slides are the standard referral slides
and the Charts Goals tab applies; the notes name the workbook row as the source. The shape
was first worded "accounts opened, not referrals" because on 1776 CoastHills the row runs
above the referral detail export (2,575 vs 2,280 program to date) — that is a difference
between two referral counts, not two measures, and it is for the data team.

What these files cannot supply is OMITTED, so build_ics_gen's own rules apply to its
absence — never zeroed, never invented:

  * no current-period workbook -> the workbook sections are absent and the build is
    referrals-only;
  * no Charts Goals tab -> no goals anywhere (build_ics_gen drops the goal tiles/columns);
  * no referrals dated in the deck's own month -> no `month_to_date` (a file with no rows
    for a month cannot tell "zero referrals" from "not extracted yet");
  * mystery shops, "Referred Accounts by Product" -> see `build_sheet`.

The Contact Us card is not in the sheet: build_ics_gen looks up the client's managing CSM
(rpe_env.csm_contact) for every ICS deck.

The sheet names its own sources in `meta.referral_source` / `meta.workbook`, which
build_ics_gen writes into every slide's notes in place of the VIP dashboard, and in a
`_provenance` block (file, folder, sheet, file date, how it was read).

Import-safe: nothing runs at import. CLI:
    python ics_local_sheet.py <client_id> <client name> <yyyy.mm> <out.json>
"""
from __future__ import annotations

import datetime as _dt
import glob
import json
import os
import re
import shutil
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_BUILD = os.path.dirname(_HERE)
for _p in (_HERE, _BUILD):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import rpe_env as R                                             # noqa: E402

# Referral trend length, matching the VIP pulls (13 months including a partial one).
TREND_MONTHS = 13
REFERRAL_KIND = "ICS referrals"
DIRECT_MAIL_KIND = "ICS direct mail"
CHARTS_KIND = "ICS charts"
WORK_DIRNAME = "ics_local_sheet"          # Build Artifacts/<this>/<id>/ — converted copies
# The shape built from the period's ICS workbook alone.
WORKBOOK_ONLY = "workbook-only"
BRANCH_TAB = "DDA Openings by Branch"
OPENINGS_ROW = "Accounts Opened via Invitation"
CUMULATIVE_ROW = "Cumulative From Invitation"
MONTH_FULL = ["January", "February", "March", "April", "May", "June", "July",
              "August", "September", "October", "November", "December"]


# ------------------------------------------------------------------ small helpers
def _period_key(period: str) -> tuple:
    y, m = period.split(".")
    return int(y), int(m)


def _prev_month(y: int, m: int) -> tuple:
    return (y - 1, 12) if m == 1 else (y, m - 1)


def _mon_yy(y: int, m: int) -> str:
    return f"{MONTH_FULL[m - 1][:3]} {y % 100:02d}"


def _file_date(path) -> str:
    return _dt.date.fromtimestamp(os.path.getmtime(path)).isoformat()


def _id_prefixed(name: str, cid: str) -> bool:
    """`1776-...` / `1776_...` / `1776 ...` — never `17760-...`."""
    return re.match(rf"^{re.escape(str(cid))}(?=[-_ ])", name) is not None


def _dirs_for(kind: str) -> list:
    """The kind's own folder, then the legacy flat folder — both read-only here."""
    try:
        own = R.input_dir(kind, create=False)
        legacy = R.inputs() / R.LEGACY_REPORTS_DIRNAME
    except BaseException:
        return []
    return [d for d in (own, legacy) if d.is_dir()]


def _newest(paths):
    return max(paths, key=lambda p: (os.path.getmtime(p), os.path.basename(p))) if paths else None


# ------------------------------------------------------------------ file resolution
def find_workbook(cid):
    """(path, 'yyyy.mm') of the newest ICS workbook for the client, or (None, None).

    Same match build_ics_gen._latest_ics_workbook_period uses — "Invitation Checking" in a
    `<id>-<yyyy.mm>-` filename, across rpe_env.report_dirs() — so the two agree on period.
    """
    try:
        dirs = R.report_dirs()
    except BaseException:
        return None, None
    best = None
    for d in dirs:
        for f in glob.glob(os.path.join(str(d), f"{cid}-*")):
            b = os.path.basename(f)
            if "invitation checking" not in b.lower() or b.startswith("~$"):
                continue
            m = re.match(rf"^{re.escape(str(cid))}-(\d{{4}}\.\d{{2}})-", b)
            if m and (best is None or (m.group(1), os.path.getmtime(f)) > (best[1], os.path.getmtime(best[0]))):
                best = (f, m.group(1))
    return best if best else (None, None)


def find_referrals(cid):
    hits = []
    for d in _dirs_for(REFERRAL_KIND):
        # Also a folder named for the client, and the id closing the name, where a person
        # landed the export by hand (`ICS Referrals/1766/ics_detailed referral_1766.xls`).
        found = glob.glob(os.path.join(str(d), "*")) + glob.glob(os.path.join(str(d), str(cid), "*"))
        hits += [f for f in found
                 if (_id_prefixed(os.path.basename(f), cid)
                     or os.path.dirname(f) == os.path.join(str(d), str(cid))
                     or re.search(rf"(?<!\d){re.escape(str(cid))}(?!\d)", os.path.splitext(os.path.basename(f))[0]))
                 and "referral" in os.path.basename(f).lower()
                 and os.path.splitext(f)[1].lower() in (".xls", ".xlsx")
                 and os.path.getsize(f) > 0]
    return _newest(hits)


def find_direct_mail(cid):
    hits = []
    for d in _dirs_for(DIRECT_MAIL_KIND):
        hits += [f for f in glob.glob(os.path.join(str(d), "*.xlsx"))
                 if _id_prefixed(os.path.basename(f), cid)
                 and "direct mail" in os.path.basename(f).lower()]
    return _newest(hits)


def find_charts(client_name):
    """The client's `... Charts 2026.xlsx`, matched on name words (branch_names' rule)."""
    try:
        from branch_names import find_charts_file
    except ImportError:
        return None
    for d in _dirs_for(CHARTS_KIND):
        hit = find_charts_file(str(d), client_name)
        if hit:
            return hit
    return None


def _vip_sheet(cid):
    try:
        return R.resolve_client_json(cid, "ics")
    except BaseException:
        return None


def available(cid, period, client_name=None) -> dict:
    """What an ICS section for `cid` in `period` can be built from.

    ok is True when VIP OR the local files can build a section. The local files can when
    a referral detail file is present (build_ics_gen needs `referrals` in every shape), or
    when the ICS workbook is for the deck's own period and stands alone. shape is "full"
    (referral file + the period's workbook), "referrals-only" (referral file; the workbook
    absent or for another period), "workbook-only" (the period's workbook alone: accounts
    opened, labelled as such — see the module docstring); None when nothing can be built.
    A workbook for another period with no referral file builds nothing: its financials
    would be stale and it has no referral figures to fall back to.
    """
    cid = str(cid)
    vip = _vip_sheet(cid) is not None
    wb, wbp = find_workbook(cid)
    ref = find_referrals(cid)
    dm = find_direct_mail(cid)
    charts = find_charts(client_name) if client_name else None
    shape = None
    if vip or ref:
        shape = "full" if (wbp == period) else "referrals-only"
    elif wbp == period:
        shape = WORKBOOK_ONLY
    wb_txt = (f"the ICS workbook is for {wbp}" if wbp else "there is no ICS workbook on file")
    if vip:
        reason = f"A VIP ICS sheet is on file for {cid}; the VIP path is used and {wb_txt}."
    elif ref and shape == "full":
        reason = (f"No VIP ICS sheet for {cid}; the section can be built from the local referral "
                  f"file and the {period} ICS workbook.")
    elif ref:
        reason = (f"No VIP ICS sheet for {cid}; the section can be built from the local referral "
                  f"file, referrals only, because {wb_txt} and the deck is {period}.")
    elif shape == WORKBOOK_ONLY:
        reason = (f"No VIP ICS sheet and no ICS referral detail file for {cid}; the section is built "
                  f"from the {period} ICS workbook alone — referrals from its 'Monthly Detail' row "
                  f"'Accounts Opened via Invitation Checking System' and its '{BRANCH_TAB}' tab.")
    else:
        reason = (f"No VIP ICS sheet and no ICS referral detail file for {cid} in Inputs/"
                  f"{R.INPUT_KIND_DIRS.get(REFERRAL_KIND, REFERRAL_KIND)}, so no ICS section can be built"
                  + (f" ({wb_txt}; only a {period} workbook can carry the section on its own)."
                     if wbp else "."))
    return {"ok": bool(vip or ref or shape == WORKBOOK_ONLY), "vip": vip,
            "workbook": str(wb) if wb else None, "workbook_period": wbp,
            "referrals": str(ref) if ref else None,
            "direct_mail": str(dm) if dm else None,
            "charts": str(charts) if charts else None,
            "shape": shape, "reason": reason}


# ------------------------------------------------------------------ reading tables
def _work_dir(cid):
    d = R.build_artifacts() / WORK_DIRNAME / str(cid)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _convert_xls_with_excel(src, cid):
    """A .xlsx COPY of a legacy .xls, converted by Excel, in Build Artifacts. The source is
    only ever copied, never opened in place. Reused while the source is unchanged."""
    work = _work_dir(cid)
    stem = os.path.splitext(os.path.basename(src))[0]
    dst = work / f"{stem}.xlsx"
    stamp = work / f"{stem}.source.json"
    st = os.stat(src)
    key = {"source": os.path.basename(src), "size": st.st_size, "mtime": st.st_mtime}
    if dst.is_file() and stamp.is_file():
        try:
            if json.load(open(stamp, encoding="utf-8")) == key:
                return str(dst)
        except (OSError, ValueError):
            pass
    try:
        import pythoncom
        import win32com.client
    except ImportError:
        raise SystemExit(
            f"Cannot read {os.path.basename(src)}: it is a legacy .xls, xlrd is not installed "
            f"and Excel automation (pywin32) is unavailable. Install xlrd in the repo .venv, or "
            f"save the file as .xlsx beside the original.")
    copy = work / os.path.basename(src)
    shutil.copy2(src, copy)
    pythoncom.CoInitialize()
    xl = None
    try:
        xl = win32com.client.DispatchEx("Excel.Application")
        xl.Visible = False
        xl.DisplayAlerts = False
        wb = xl.Workbooks.Open(os.path.abspath(str(copy)), ReadOnly=True)
        try:
            wb.SaveAs(os.path.abspath(str(dst)), FileFormat=51)   # xlOpenXMLWorkbook
        finally:
            wb.Close(False)
    finally:
        if xl is not None:
            xl.Quit()
        pythoncom.CoUninitialize()
    try:
        os.remove(copy)          # some mounts refuse deletes; the copy is harmless if it stays
    except OSError:
        pass
    json.dump(key, open(stamp, "w", encoding="utf-8"))
    return str(dst)


def read_rows(path, cid):
    """-> (sheet name, [row tuples], how it was read) for the file's first sheet.

    .xlsx through openpyxl. A legacy .xls through xlrd when installed, else through an
    Excel-converted copy in Build Artifacts (the repo .venv has no xlrd).
    """
    ext = os.path.splitext(str(path))[1].lower()
    if ext == ".xls":
        try:
            import xlrd
        except ImportError:
            xlrd = None
        if xlrd is not None:
            book = xlrd.open_workbook(str(path))
            sh = book.sheet_by_index(0)
            rows = []
            for r in range(sh.nrows):
                row = []
                for c in range(sh.ncols):
                    v = sh.cell_value(r, c)
                    if sh.cell_type(r, c) == xlrd.XL_CELL_DATE:
                        v = xlrd.xldate_as_datetime(v, book.datemode)
                    row.append(v)
                rows.append(tuple(row))
            return sh.name, rows, "xlrd"
        conv = _convert_xls_with_excel(str(path), cid)
        name, rows, _ = read_rows(conv, cid)
        rel = os.path.relpath(conv, str(R.build_artifacts())) if conv else conv
        return name, rows, f"Excel-converted copy in Build Artifacts/{rel.replace(os.sep, '/')}"
    import openpyxl
    wb = openpyxl.load_workbook(str(path), read_only=True, data_only=True)
    try:
        ws = wb.worksheets[0]
        rows = [tuple(r) for r in ws.iter_rows(values_only=True)]
        return ws.title, rows, "openpyxl"
    finally:
        wb.close()


def _to_date(v):
    if isinstance(v, _dt.datetime):
        return v.date()
    if isinstance(v, _dt.date):
        return v
    if isinstance(v, str) and v.strip():
        s = v.strip().split(" ")[0]
        for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%m/%d/%y"):
            try:
                return _dt.datetime.strptime(s, fmt).date()
            except ValueError:
                pass
    return None


def _branch_key(v):
    """'010', 10, 10.0 -> '10'. Branch ids are numbers in one file and text in another."""
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    s = str(v).strip()
    return str(int(s)) if s.isdigit() else s


def _header_index(rows, needle, limit=25):
    for i, r in enumerate(rows[:limit]):
        if any(isinstance(v, str) and needle in v.strip().lower() for v in r):
            return i
    return None


def _col(header, *names):
    low = [str(h).strip().lower() if h is not None else "" for h in header]
    for n in names:
        for i, h in enumerate(low):
            if h == n:
                return i
    for n in names:
        for i, h in enumerate(low):
            if n in h:
                return i
    return None


def read_referral_events(path, cid):
    """-> ([(date, branch key, id)], info). One event per referral certificate."""
    sheet, rows, how = read_rows(path, cid)
    hi = _header_index(rows, "issue date")
    if hi is None:
        raise SystemExit(f"{os.path.basename(path)}: no 'Issue Date' header in the first 25 rows "
                         f"of sheet {sheet!r} — not a detailed referral file this reader knows.")
    hdr = rows[hi]
    c_date = _col(hdr, "issue date")
    c_branch = _col(hdr, "branch")
    c_id = _col(hdr, "cert id", "certificate id", "cert")
    events, undated, seen, dupes = [], 0, set(), 0
    for r in rows[hi + 1:]:
        if not any(v not in (None, "") for v in r):
            continue
        d = _to_date(r[c_date]) if c_date is not None and c_date < len(r) else None
        if d is None:
            undated += 1
            continue
        rid = str(r[c_id]).strip() if (c_id is not None and c_id < len(r) and r[c_id] not in (None, "")) else None
        if rid is not None:
            if rid in seen:
                dupes += 1
                continue
            seen.add(rid)
        br = _branch_key(r[c_branch]) if (c_branch is not None and c_branch < len(r)) else ""
        events.append((d, br, rid))
    info = {"sheet": sheet, "read_via": how, "header_row": hi + 1,
            "columns": {"date": hdr[c_date] if c_date is not None else None,
                        "branch": hdr[c_branch] if c_branch is not None else None,
                        "id": hdr[c_id] if c_id is not None else None},
            "rows_counted": len(events), "rows_without_date": undated,
            "duplicate_ids_dropped": dupes}
    return events, info


def read_goals(charts_path):
    """-> ({branch key: (name, monthly goal or None)}, name disagreements, info) from the
    Charts workbook's Goals tab; ({}, [], None) when the tab is absent.

    Names are cross-checked against the Mystery Shop Results tab: branch_names.py records
    that a Charts file's tabs CAN disagree, and a disagreeing branch keeps its number.
    """
    if not charts_path:
        return {}, [], None
    import openpyxl
    wb = openpyxl.load_workbook(str(charts_path), read_only=True, data_only=True)
    try:
        # Matched with the name stripped: 1195's Charts workbook names the tab " Goals".
        tab = next((n for n in wb.sheetnames if n.strip() == "Goals"), None)
        if tab is None:
            return {}, [], None
        rows = [tuple(r) for r in wb[tab].iter_rows(values_only=True)]
        # The goal column is "Monthly Goal", or plain "Goal" beside ramp columns (1195's tab:
        # "Branch #", "Branch Name", "Goal", "Jan 20%", ...). Matched on the header row that
        # carries "Branch Name", so a banner cannot be taken for the header.
        hi = _header_index(rows, "branch name")
        if hi is None:
            return {}, [], None
        hdr = rows[hi]
        c_no, c_name = _col(hdr, "branch #", "branch number"), _col(hdr, "branch name")
        c_goal = _col(hdr, "monthly goal", "goal")
        if c_goal is None:
            return {}, [], None
        goals, total_row = {}, None
        for r in rows[hi + 1:]:
            if (c_name is not None and c_goal is not None and c_name < len(r) and c_goal < len(r)
                    and isinstance(r[c_name], str) and r[c_name].strip().lower() == "total"
                    and isinstance(r[c_goal], (int, float))):
                total_row = r[c_goal]
            if c_no is None or c_no >= len(r) or r[c_no] in (None, ""):
                continue
            k = _branch_key(r[c_no])
            if not k.isdigit():
                continue
            name = str(r[c_name]).strip() if (c_name is not None and r[c_name]) else None
            g = r[c_goal] if c_goal is not None else None
            goals[k] = (name, int(g) if isinstance(g, (int, float)) else None)
        other = {}
        if "Mystery Shop Results" in wb.sheetnames:
            for r in wb["Mystery Shop Results"].iter_rows(values_only=True):
                if len(r) > 1 and isinstance(r[0], (int, float)) and isinstance(r[1], str):
                    other[_branch_key(r[0])] = r[1].strip()
    finally:
        wb.close()
    disagree = [k for k, (nm, _) in goals.items() if nm and k in other and other[k] != nm]
    info = {"sheet": "Goals", "header_row": hi + 1, "branches": len(goals),
            "total_row_goal": total_row,
            "sum_of_branch_goals": sum(g for _, g in goals.values() if g),
            "names_cross_checked_against": "Mystery Shop Results" if other else None}
    return goals, disagree, info


def read_direct_mail(path, cid, period):
    """-> (direct_mail block, info). New accounts opened through the DM channel."""
    sheet, rows, how = read_rows(path, cid)
    hi = _header_index(rows, "open date")
    if hi is None:
        return None, {"sheet": sheet, "read_via": how, "error": "no 'Open Date' header"}
    hdr = rows[hi]
    c_date, c_branch = _col(hdr, "open date"), _col(hdr, "branch number", "branch")
    report_date = None
    for r in rows[:hi]:
        for v in r:
            if isinstance(v, str) and v.lower().startswith("report date"):
                report_date = _to_date(v.split(":", 1)[-1].strip())
    py, pm = _period_key(period)
    by_month, by_branch, undated, after = {}, {}, 0, 0
    for r in rows[hi + 1:]:
        if not any(v not in (None, "") for v in r):
            continue
        d = _to_date(r[c_date]) if c_date is not None else None
        if d is None:
            undated += 1
            continue
        if (d.year, d.month) > (py, pm):
            after += 1
            continue
        by_month[(d.year, d.month)] = by_month.get((d.year, d.month), 0) + 1
        k = _branch_key(r[c_branch]) if c_branch is not None else ""
        by_branch[k] = by_branch.get(k, 0) + 1
    if not by_month:
        return None, {"sheet": sheet, "read_via": how, "error": "no dated accounts"}
    first, last = min(by_month), max(by_month)
    months, y, m = [], first[0], first[1]
    while (y, m) <= last:
        months.append((y, m))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    block = {
        "_note": ("Direct-mail channel new accounts. Shown on their own ICS slide, 'Direct Mail "
                  "New Accounts', when accounts_opened_ptd > 0; NEVER added to any referral figure."),
        "source_file": os.path.basename(str(path)),
        "source_folder": _folder_of(path),
        "report_date": report_date.isoformat() if report_date else None,
        "accounts_opened_ptd": sum(by_month.values()),
        "first_month": f"{first[0]}-{first[1]:02d}", "last_month": f"{last[0]}-{last[1]:02d}",
        "by_month": {"months": [_mon_yy(*k) for k in months],
                     "accounts": [by_month.get(k, 0) for k in months]},
        "by_branch": [{"branch": k, "accounts": v}
                      for k, v in sorted(by_branch.items(), key=lambda kv: (-kv[1], kv[0]))],
    }
    info = {"sheet": sheet, "read_via": how, "header_row": hi + 1,
            "rows_without_date": undated, "rows_after_period": after}
    return block, info


# ------------------------------------------------------------------ the referral sections
def referral_sections(events, period, goals=None):
    """-> (referrals block, flags). Counts only; every figure is a count of events."""
    goals = goals or {}
    py, pm = _period_key(period)
    flags = []
    after = [e for e in events if (e[0].year, e[0].month) > (py, pm)]
    if after:
        flags.append(f"{len(after)} referral(s) dated after {period} were left out.")
    ev = [e for e in events if (e[0].year, e[0].month) <= (py, pm)]
    if not ev:
        raise SystemExit(f"The referral file has no referrals dated on or before {period}.")
    by_month = {}
    for d, _, _ in ev:
        by_month[(d.year, d.month)] = by_month.get((d.year, d.month), 0) + 1
    prev = _prev_month(py, pm)
    latest = max(by_month)
    if latest < prev:
        raise SystemExit(
            f"The referral file ends in {latest[0]}-{latest[1]:02d}, before {prev[0]}-{prev[1]:02d}, "
            f"the last complete month of a {period} deck. Building would present old referral "
            f"figures as current — supply a current referral file.")
    partial = (py, pm) in by_month          # referrals dated in the deck's own month
    last = (py, pm) if partial else prev
    first = min(by_month)
    months, y, m = [], last[0], last[1]
    while len(months) < TREND_MONTHS and (y, m) >= first:
        months.insert(0, (y, m))
        y, m = _prev_month(y, m)
    data_through = max(e[0] for e in ev)
    ytd_n = sum(v for k, v in by_month.items() if k[0] == py)
    rf = {
        "program_to_date": len(ev),
        "year_to_date": ytd_n,
        "previous_month": {"label": MONTH_FULL[prev[1] - 1], "value": by_month.get(prev, 0)},
        "latest_data_month": f"{last[0]}-{last[1]:02d}",
        "trend": {"months": [_mon_yy(*k) for k in months],
                  "referrals": [by_month.get(k, 0) for k in months],
                  "partial_last": partial},
    }
    if partial:
        rf["month_to_date"] = {"label": MONTH_FULL[pm - 1], "value": by_month[(py, pm)], "partial": True}
    total_goal = sum(g for _, g in goals.values() if g)
    if total_goal:
        rf["monthly_goal"] = total_goal
        rf["prev_month_vs_goal_pct"] = round(rf["previous_month"]["value"] / total_goal * 100)
    ytd_by_branch = {}
    for d, br, _ in ev:
        if d.year == py:
            ytd_by_branch[br] = ytd_by_branch.get(br, 0) + 1
    keys = set(ytd_by_branch) | set(goals)
    branches = []
    for k in keys:
        name, g = goals.get(k, (None, None))
        row = {"name": name or (f"Branch {k}" if k else "No branch recorded"),
               "number": k, "referrals": ytd_by_branch.get(k, 0)}
        if g:
            row["goal"] = g * 12          # build_ics_gen reads branch goals as ANNUAL (VIP)
        branches.append(row)
    branches.sort(key=lambda b: (-b["referrals"], b["name"]))
    rf["by_branch"] = {"ytd_goal_per_branch": None, "branches": branches,
                       "_goal_basis": ("Charts 'Goals' tab monthly goal x 12, stored as annual"
                                       if total_goal else "no goals on file")}
    unknown = sorted(k for k in ytd_by_branch if goals and k not in goals)
    if unknown:
        flags.append(f"Branch number(s) {', '.join(unknown)} carry referrals but are not on the "
                     f"Charts Goals tab; shown by number with no goal.")
    return rf, flags, data_through


# ------------------------------------------------------------------ the workbook alone
def _month_end(y, m):
    import calendar
    return _dt.date(y, m, calendar.monthrange(y, m)[1])


def read_workbook_openings(wb_path, period, cid, goals=None):
    """-> (block, info, flags, data_through, as_of): the referral block built from the ICS workbook
    alone, in the shape of `referral_sections`' block so the same three slides render it.

      * 'Monthly Detail', the "Accounts Opened via Invitation Checking System" row — which counts
        REFERRALS (Aaron, 2026-10-13) and sums to the Value tab's figure — -> the trend, year to
        date and previous month; program to date from the "Cumulative From ..." row (else the
        sum, with a flag when the two disagree).
      * 'DDA Openings by Branch', the "Invitation Checking DDA Openings by Branch" table, Year to
        Date column -> the branch table. `goals` (branch key -> (name, monthly goal)) names the
        rows and, as in `referral_sections`, gives the monthly goal and each branch's annual
        goal; a branch with no name is shown by number, never guessed.

    Completeness goes through month_complete.assess as of the tab's "Report Generated" stamp
    (else the file date): a trailing incomplete month stays on the chart hatched and is left out
    of the previous-month and peak figures, and a flag says so.
    """
    import openpyxl
    import ics_workbook_extract as X
    import month_complete as MC
    goals = dict(goals or {})
    names = {k: nm for k, (nm, _) in goals.items() if nm}
    flags = []
    base = os.path.basename(str(wb_path))
    wb = openpyxl.load_workbook(str(wb_path), read_only=True, data_only=True)
    try:
        if "Monthly Detail" not in wb.sheetnames:
            raise SystemExit(f"{base}: no 'Monthly Detail' tab, so no accounts-opened figures.")
        md = wb["Monthly Detail"]
        cols = X.month_cols(md) or X.month_cols(md, 7)
        if not cols:
            raise SystemExit(f"{base}: no dated month columns in 'Monthly Detail'.")
        hdr = 14 if isinstance(md.cell(14, cols[0]).value, _dt.datetime) else 7
        r_open = X._find_row(md, OPENINGS_ROW, 8, 40)
        if not r_open:
            raise SystemExit(f"{base}: no '{OPENINGS_ROW} Checking System' row in 'Monthly Detail'.")
        r_cum = X._find_row(md, CUMULATIVE_ROW, 8, 40)
        months, values = [], []
        for c in cols:
            v = md.cell(r_open, c).value
            months.append(md.cell(hdr, c).value.date().replace(day=1))
            values.append(int(round(v)) if isinstance(v, (int, float)) else None)
        while values and values[-1] is None:
            months.pop(); values.pop()
        if not values:
            raise SystemExit(f"{base}: the '{OPENINGS_ROW} Checking System' row carries no figures.")
        cum_by_col = {}
        if r_cum:
            for i, c in enumerate(cols[:len(values)]):
                cv = md.cell(r_cum, c).value
                if isinstance(cv, (int, float)):
                    cum_by_col[i] = int(round(cv))
        # ---- the branch tab
        branches, total_row, generated, tab_info = [], None, None, None
        if BRANCH_TAB in wb.sheetnames:
            rows = [tuple(r) for r in wb[BRANCH_TAB].iter_rows(values_only=True)]
            for r in rows:
                for v in r:
                    if isinstance(v, str) and v.strip().lower().startswith("report generated"):
                        generated = MC.report_date(v.split(":", 1)[-1]) or generated
            # The TABLE title ("Invitation Checking / DDA Openings / by Branch"), not the tab's
            # "Invitation Checking System" banner above the all-DDA table.
            start = next((i for i, r in enumerate(rows)
                          if len(r) > 1 and isinstance(r[1], str)
                          and r[1].strip().lower().startswith("invitation checking")
                          and "branch" in r[1].lower()), None)
            if start is not None and start + 1 < len(rows):
                title_row, head = rows[start], rows[start + 1]
                c_group = next((i for i, v in enumerate(title_row)
                                if isinstance(v, str) and "year to date" in v.lower()), None)
                opened = [i for i, v in enumerate(head)
                          if isinstance(v, str) and v.strip().lower() == "accounts opened"]
                c_month = opened[0] if opened else None
                c_ytd = next((i for i in opened if c_group is not None and i >= c_group), None)

                def _num_at(r, i):
                    return int(round(r[i])) if (i is not None and i < len(r)
                                                and isinstance(r[i], (int, float))) else 0
                for r in rows[start + 2:]:
                    b = r[1] if len(r) > 1 else None
                    if isinstance(b, str) and b.strip().lower() == "total":
                        total_row = r
                        break
                    if isinstance(b, str) and b.strip().lower() == "branch":
                        continue
                    mv, yv = _num_at(r, c_month), _num_at(r, c_ytd)
                    if b in (None, "") and not (mv or yv):
                        continue
                    branches.append((_branch_key(b), mv, yv))
                tab_info = {"tab": BRANCH_TAB, "table": "Invitation Checking DDA Openings by Branch",
                            "table_title_row": start + 1, "month_column": c_month, "ytd_column": c_ytd,
                            "branches": len(branches),
                            "total_row_ytd": _num_at(total_row, c_ytd) if total_row else None,
                            "total_row_month": _num_at(total_row, c_month) if total_row else None}
        if not branches:
            flags.append(f"{base}: no '{BRANCH_TAB}' table could be read, so no branch results are shown.")
    finally:
        wb.close()

    as_of = generated or _dt.date.fromtimestamp(os.path.getmtime(str(wb_path)))
    res = MC.assess([m.strftime("%b %y") for m in months], values, as_of=as_of,
                    measure="accounts opened via ICS")
    n_c = res["complete"]
    if n_c == 0:
        raise SystemExit(f"{base}: no complete month of accounts opened as of {as_of.isoformat()}.")
    # At most one trailing incomplete month stays, hatched; anything beyond it is not charted.
    months, values = months[:n_c + 1], values[:n_c + 1]
    partial = len(months) > n_c
    for e in res["excluded"]:
        flags.append(f"{e['month']} is incomplete for accounts opened ({e['reason']}: "
                     + (f"the report was generated {e['as_of']}, before the month ended"
                        if e["reason"] == "pulled"
                        else f"{e['value']:g} against a six-month median of {e['baseline']:g}")
                     + "); it is charted hatched and left out of the previous-month and peak figures.")
    last_c = months[n_c - 1]
    py, pm = _period_key(period)
    if (last_c.year, last_c.month) != _prev_month(py, pm):
        flags.append(f"The workbook's last complete month is {MONTH_FULL[last_c.month - 1]} {last_c.year}, "
                     f"not the month before a {period} deck.")
    ytd = sum(v for mth, v in zip(months[:n_c], values[:n_c]) if mth.year == py)
    summed = sum(values[:n_c])
    cum = cum_by_col.get(n_c - 1)
    ptd = cum if cum is not None else summed
    if cum is not None and cum != summed:
        flags.append(f"'Monthly Detail': the Cumulative row says {cum:,} accounts opened through "
                     f"{MONTH_FULL[last_c.month - 1]} {last_c.year} and the monthly figures add to {summed:,}; "
                     f"the Cumulative row is used for program to date.")
    first_i = max(0, len(months) - TREND_MONTHS)
    rows_b = []
    seen = set()
    for key, mv, yv in sorted(branches, key=lambda t: (-t[2], t[0])):
        seen.add(key)
        nm, g = goals.get(key, (None, None))
        row = {"name": nm or (f"Branch {key}" if key else "No branch recorded"),
               "number": key, "referrals": yv, "month": mv}
        if g:
            row["goal"] = g * 12          # build_ics_gen reads branch goals as ANNUAL (VIP)
        rows_b.append(row)
    for key, (nm, g) in goals.items():    # a branch with a goal and no row yet: 0, as referral_sections does
        if key not in seen and branches:
            row = {"name": nm or f"Branch {key}", "number": key, "referrals": 0, "month": 0}
            if g:
                row["goal"] = g * 12
            rows_b.append(row)
    rows_b.sort(key=lambda b: (-b["referrals"], b["name"]))
    total_goal = sum(g for _, g in goals.values() if g)
    unknown = sorted(k for k, _, _ in branches if goals and k not in goals)
    if unknown:
        flags.append(f"Branch number(s) {', '.join(unknown)} carry referrals but are not on the "
                     f"Charts Goals tab; shown by number with no goal.")
    if total_row is not None and tab_info and tab_info["total_row_ytd"] is not None:
        sb = sum(b["referrals"] for b in rows_b)
        if sb != tab_info["total_row_ytd"]:
            flags.append(f"'{BRANCH_TAB}': the Total row says {tab_info['total_row_ytd']:,} year to date "
                         f"and the branch rows add to {sb:,}; the branch rows are shown.")
        if tab_info["total_row_ytd"] != ytd:
            flags.append(f"Year to date: '{BRANCH_TAB}' totals {tab_info['total_row_ytd']:,} and 'Monthly "
                         f"Detail' adds to {ytd:,} for the same months; each slide states its own tab's figure.")
    if partial and rows_b:
        flags.append(f"The branch year-to-date figures include {MONTH_FULL[months[-1].month - 1]} "
                     f"{months[-1].year}, which is incomplete.")
    block = {
        "_note": ("Referrals, from the ICS workbook alone: the 'Monthly Detail' row 'Accounts Opened "
                  "via Invitation Checking System' counts referrals (Aaron, 2026-10-13) and sums to the "
                  "Value tab's figure; the branch table is the 'DDA Openings by Branch' tab."),
        "program_to_date": ptd,
        "year_to_date": ytd,
        "previous_month": {"label": MONTH_FULL[last_c.month - 1], "value": values[n_c - 1]},
        "latest_data_month": last_c.strftime("%Y-%m"),
        "trend": {"months": [_mon_yy(m.year, m.month) for m in months[first_i:]],
                  "referrals": values[first_i:],
                  "partial_last": partial},
        "by_branch": {"ytd_goal_per_branch": None, "branches": rows_b,
                      "_goal_basis": ("Charts 'Goals' tab monthly goal x 12, stored as annual"
                                      if total_goal else "no goals on file"),
                      "_source": f"'{BRANCH_TAB}' tab, Invitation Checking table, Year to Date column"},
    }
    if total_goal:
        block["monthly_goal"] = total_goal
        block["prev_month_vs_goal_pct"] = round(values[n_c - 1] / total_goal * 100)
    info = {"monthly_detail": {"row": OPENINGS_ROW + " Checking System", "header_row": hdr,
                               "months": len(values), "first_month": months[0].strftime("%Y-%m"),
                               "last_month": months[-1].strftime("%Y-%m"),
                               "cumulative_row_used": cum is not None},
            "branch_tab": tab_info,
            "data_month": f"{MONTH_FULL[last_c.month - 1]} {last_c.year}",
            "report_generated": generated.isoformat() if generated else None,
            "as_of": as_of.isoformat(), "completeness": res}
    return block, info, flags, _month_end(last_c.year, last_c.month), as_of


# ------------------------------------------------------------------ the sheet
def _workbook_month(path):
    """'August 2026' from the Monthly Detail banner ("August 2026 Data"), else the last
    dated month column. None when neither is readable."""
    import openpyxl
    wb = openpyxl.load_workbook(str(path), read_only=True, data_only=True)
    try:
        if "Monthly Detail" not in wb.sheetnames:
            return None
        ws = wb["Monthly Detail"]
        last = None
        for r in ws.iter_rows(min_row=1, max_row=16, values_only=True):
            for v in r:
                if isinstance(v, str):
                    m = re.match(r"^\s*([A-Z][a-z]+ \d{4}) Data\s*$", v)
                    if m and m.group(1).split()[0] in MONTH_FULL:
                        return m.group(1)
                elif isinstance(v, _dt.datetime):
                    last = v if (last is None or v > last) else last
        return last.strftime("%B %Y") if last else None
    finally:
        wb.close()


def _folder_of(path):
    try:
        return os.path.relpath(os.path.dirname(str(path)), str(R.data_root())).replace(os.sep, "/")
    except BaseException:
        return os.path.dirname(str(path))


def build_sheet(cid, name, period, out_json, *, today=None) -> str:
    """Write an ICS client sheet for `cid` from local files; returns the path written.

    Raises SystemExit (plain sentence) when nothing on file can build one, or the referral
    file is stale. Three shapes: "referrals-only" (the referral file; no workbook for the
    period), "full" (the referral file and the period's workbook) and "workbook-only" (the
    period's workbook alone — accounts opened, `meta.count_basis` = "accounts_opened", never
    called referrals).
    """
    cid = str(cid)
    av = available(cid, period, name)
    if not av["ok"] or av["vip"]:
        raise SystemExit(av["reason"])
    flags, omitted, files = [], {}, []
    goals, disagree, ginfo = read_goals(av.get("charts"))
    for k in disagree:
        goals[k] = (None, goals[k][1])
        flags.append(f"Branch {k}: the Charts Goals and Mystery Shop Results tabs name it "
                     f"differently; shown by number.")

    if av["shape"] == WORKBOOK_ONLY:
        # Branch names and goals: the Charts Goals tab; a branch it does not name takes its name
        # from the branch-name dataset the morning check keeps (Inputs/Branch Names), with no
        # goal; a branch neither names is shown by number.
        wgoals = dict(goals)
        try:
            import branch_names as BN
            for k, nm in (BN.client_map(cid) or {}).items():
                k = _branch_key(k)
                if k not in wgoals:
                    wgoals[k] = (nm, None)
        except Exception:
            pass
        rf, winfo, wflags, data_through, as_of = read_workbook_openings(av["workbook"], period, cid, wgoals)
        flags += wflags
        wb_name = os.path.basename(av["workbook"])
        files.append(dict({"role": "referrals by month ('Monthly Detail', the 'Accounts Opened via "
                                   f"Invitation Checking System' row) and by branch ('{BRANCH_TAB}')",
                           "file": wb_name, "folder": _folder_of(av["workbook"]),
                           "file_date": _file_date(av["workbook"])}, **winfo))
        if goals:
            files.append(dict({"role": "branch names and monthly goals",
                               "file": os.path.basename(av["charts"]), "folder": _folder_of(av["charts"]),
                               "file_date": _file_date(av["charts"])}, **(ginfo or {})))
        else:
            omitted["goals"] = ("No Charts workbook with a Goals tab was found for this client, so "
                                "no monthly or branch goal is stated.")
        if len(wgoals) > len(goals):
            files.append({"role": "branch names for branches the Goals tab does not name",
                          "file": "Inputs/Branch Names/branch_names.csv", "read_via": "branch_names.client_map"})
        omitted["referrals.month_to_date"] = (
            f"The workbook is monthly and ends at {winfo['data_month']}; the deck's own month "
            f"({period}) is not in it, so no partial month is shown.")
        charts_txt = (f"; branch names and monthly goals from {os.path.basename(av['charts'])} "
                      f"('Goals' tab)") if goals else ""
        referral_source = (f"ICS workbook {wb_name} ({_folder_of(av['workbook'])}, {winfo['data_month']} data, "
                           f"report generated {as_of.isoformat()}; not VIP): referrals from the 'Monthly "
                           f"Detail' row 'Accounts Opened via Invitation Checking System' and the "
                           f"'{BRANCH_TAB}' tab — no referral detail file or VIP sheet is on file{charts_txt}")
        data_pull = as_of.isoformat()
    else:
        ref = av["referrals"]
        events, rinfo = read_referral_events(ref, cid)
        rf, rflags, data_through = referral_sections(events, period, goals)
        flags += rflags
        if ginfo and ginfo.get("total_row_goal") is not None \
                and ginfo["total_row_goal"] != ginfo["sum_of_branch_goals"]:
            flags.append(f"Charts Goals tab: its Total row says {ginfo['total_row_goal']:g} a month but the "
                         f"branch goals add to {ginfo['sum_of_branch_goals']}; the branch goals are used, so "
                         f"the monthly goal and the branch table agree.")
        if rinfo["rows_without_date"]:
            flags.append(f"{rinfo['rows_without_date']} referral row(s) had no readable Issue Date and "
                         f"were not counted.")
        if rinfo["duplicate_ids_dropped"]:
            flags.append(f"{rinfo['duplicate_ids_dropped']} duplicate certificate id(s) counted once.")
        files.append(dict({"role": "referrals", "file": os.path.basename(ref), "folder": _folder_of(ref),
                           "file_date": _file_date(ref), "data_through": data_through.isoformat()}, **rinfo))
        if not goals:
            omitted["goals"] = ("No Charts workbook with a Goals tab was found for this client, so "
                                "no monthly or branch goal is stated.")
        else:
            files.append(dict({"role": "branch names and monthly goals",
                               "file": os.path.basename(av["charts"]), "folder": _folder_of(av["charts"]),
                               "file_date": _file_date(av["charts"])}, **ginfo))
        if "month_to_date" not in rf:
            omitted["referrals.month_to_date"] = (
                f"No referrals in the file are dated in {period}; the file cannot tell zero referrals "
                f"from a month not yet extracted, so no partial month is shown.")

        charts_txt = (f"; branch names and monthly goals from {os.path.basename(av['charts'])} "
                      f"('Goals' tab)") if goals else ""
        referral_source = (f"ICS detailed referral file {os.path.basename(ref)} ({_folder_of(ref)}, file "
                           f"dated {_file_date(ref)}, referrals through {data_through.isoformat()}; "
                           f"not VIP){charts_txt}")
        data_pull = _file_date(ref)
    meta = {
        "client_id": cid, "client_name": name, "period": period,
        "report_month": f"{MONTH_FULL[_period_key(period)[1] - 1]} {_period_key(period)[0]}",
        "data_pull": data_pull,
        "data_through": data_through.isoformat(),
        "source_kind": "local",
        "referral_source": referral_source,
    }
    sheet = {"meta": meta, "referrals": rf}

    if av["direct_mail"]:
        dm, dinfo = read_direct_mail(av["direct_mail"], cid, period)
        files.append(dict({"role": "direct mail (its own slide; not referrals)",
                           "file": os.path.basename(av["direct_mail"]),
                           "folder": _folder_of(av["direct_mail"]),
                           "file_date": _file_date(av["direct_mail"])}, **dinfo))
        if dm:
            sheet["direct_mail"] = dm

    if av["shape"] in ("full", WORKBOOK_ONLY):
        import ics_workbook_extract as X
        sections = X.extract(av["workbook"])
        program_start = sections.pop("_program_start", None)
        sections.pop("_workbook_month", None)          # meta.workbook_month is read from the banner below
        sections.pop("mystery_shop", None)
        sections.pop("contacts", None)          # an older extractor's standing card; never used
        sheet.update(sections)
        meta["workbook"] = os.path.basename(av["workbook"])
        wbm = _workbook_month(av["workbook"])
        if wbm:
            meta["workbook_month"] = wbm
        if program_start:
            meta["program_start"] = program_start
        files.append({"role": "workbook", "file": meta["workbook"], "folder": _folder_of(av["workbook"]),
                      "file_date": _file_date(av["workbook"]), "workbook_period": av["workbook_period"],
                      "sheets": ["Monthly Detail", "Value of ICS Accts", "Life of Account Data"],
                      "read_via": "ics_workbook_extract.extract"})
    else:
        omitted["performance, revenue, financial_summary, monthly_detail, benchmark"] = (
            f"The newest ICS workbook is for {av['workbook_period'] or 'no period (none on file)'}, "
            f"not {period}; workbook figures ship only for the deck's own period.")
    omitted["mystery_shop"] = ("Not built from local files: the Charts Mystery Shop Results tab "
                               "carries no per-month results this reader can total.")
    omitted["referred_by_product"] = (
        "Not extracted: the workbook's 'Referred Accounts by Product' tab is not read by "
        "ics_workbook_extract, and on a direct-mail workbook it may count DM accounts.")

    sheet["_provenance"] = {
        "built": (today or _dt.date.today()).isoformat(),
        "builder": "build/ics_pipeline/ics_local_sheet.py",
        "vip": False,
        "shape": av["shape"],
        "files": files,
        "omitted": omitted,
    }
    if flags:
        sheet["_flags"] = flags
    os.makedirs(os.path.dirname(os.path.abspath(str(out_json))), exist_ok=True)
    with open(out_json, "w", encoding="utf-8") as fh:
        json.dump(sheet, fh, indent=1, ensure_ascii=False)
    return str(out_json)


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("client_id"); ap.add_argument("client_name")
    ap.add_argument("period"); ap.add_argument("out_json")
    a = ap.parse_args(argv)
    av = available(a.client_id, a.period, a.client_name)
    print(av["reason"])
    if not av["ok"]:
        return 1
    print("wrote", build_sheet(a.client_id, a.client_name, a.period, a.out_json))
    return 0


if __name__ == "__main__":
    sys.exit(main())
