#!/usr/bin/env python3
"""
perf_clients.py — who the RPE Client Performance page lists, and which programs it shows.

The page shows EVERY current client across all five CSMs (Aaron, 2026-09-14), filtered by
CSM at the top, not only the clients.md roster. Two facts have to come from somewhere for
the clients clients.md does not cover:

  * **Who is current.** A client the data team filed reports for this cycle, on
    `Velocity_clientreports\\<period>\\<Account Manager>\\`. The newest period folder at or
    before the cycle that holds any client file is read, so early in a month, before the
    first files land, the page still lists last month's clients rather than nobody. The
    last answer is kept in `current.json` because the share needs the VPN; off it, the
    list would otherwise empty, move the content hash and republish.

  * **Which programs.** For a clients.md client, clients.md says, exactly as for the
    builders. For anyone else there is no record, so the programs are INFERRED from this
    month's data (Aaron chose this, 2026-09-14) and the page tags them as such:
        ARS workbook on the share     -> ARS
        VIP ICS referral sheet        -> ICS
        MRPCPM analysis or a tab in the MRPC weekly -> MRPC
        a tab in the CashPlease weekly -> CP
    A DCO alone implies nothing: a DCO accompanies an ARS build but does not imply one
    (clients.md, "What is NOT a signal to build"). A client whose files carry no program
    is still listed, with no program sections.

This is for reading only. `clients.md` still decides what gets BUILT, and nothing here
feeds a builder.
"""
import datetime as _dt
import json
import os
import re

_PERIOD_DIR_RX = re.compile(r"^\d{4}\.\d{2}$")
_FILE_RX = re.compile(r"^(\d{3,5})-(\d{4}\.\d{2})-(.+)\.xls[xm]?$", re.I)
# Everything from the first kind marker on is not part of the client's name:
# "Brooks Bank-DCO v2_2", "First State Bank-MI-Workbook_v2_1_0", "Austin-Invitation Checking ...".
_KIND_TAIL_RX = re.compile(r"-(?:DCO|MRPCPM|Invitation Checking|Workbook).*$", re.I)

DCO, WORKBOOK, MRPCPM, ICS_WORKBOOK = "DCO", "WORKBOOK", "MRPCPM", "ICS WORKBOOK"


def file_kind(rest):
    """The kind of report a filename's tail names, or None."""
    r = rest.lower()
    if "mrpcpm" in r:
        return MRPCPM
    if "invitation checking" in r:
        return ICS_WORKBOOK
    if "workbook" in r:
        return WORKBOOK
    if "dco" in r:
        return DCO
    return None


def parse_report_name(filename):
    """(client id, kind, client name) for a landed report file, or None.

    The MRPCPM analyses carry a "MRPC-" prefix before the name
    (`<id>-<period>-MRPC-<name>-MRPCPM_Analysis_v10.xlsx`), which is dropped.
    """
    if filename.startswith("~$"):
        return None
    m = _FILE_RX.match(filename)
    if not m:
        return None
    rest = re.sub(r"^MRPC-", "", m.group(3), flags=re.I)
    name = _KIND_TAIL_RX.sub("", rest).strip(" -_")
    return m.group(1), file_kind(rest), name


def share_reports(root, period, log=print):
    """(folder period, {id: {"csm", "name", "kinds"}}) from the reports share, or None.

    Reads the newest `<yyyy.mm>` folder at or before `period` that holds any client file.
    None means the share could not be read — the top folder or ANY account-manager folder
    in it — because a partial read would drop every client in the folder that failed.
    A name prefers the DCO's spelling, the one file every client has.
    """
    try:
        pdirs = sorted((d for d in os.listdir(root) if _PERIOD_DIR_RX.match(d) and d <= period),
                       reverse=True)
    except OSError:
        return None
    for pd in pdirs:
        base = os.path.join(root, pd)
        try:
            ams = sorted(e for e in os.listdir(base) if os.path.isdir(os.path.join(base, e)))
        except OSError:
            return None
        out = {}
        for am in ams:
            try:
                names = sorted(os.listdir(os.path.join(base, am)))
            except OSError:
                log("current clients: %s\\%s could not be read" % (pd, am))
                return None
            for n in names:
                got = parse_report_name(n)
                if not got:
                    continue
                cid, kind, name = got
                rec = out.setdefault(cid, {"csm": am, "name": "", "kinds": []})
                if kind and kind not in rec["kinds"]:
                    rec["kinds"].append(kind)
                if name and (not rec["name"] or kind == DCO):
                    rec["name"] = name
        if out:
            for rec in out.values():
                rec["kinds"].sort()
            return pd, out
    return None, {}


def current_clients(period, work, root, log=print):
    """({id: {"csm", "name", "kinds"}}, folder period) — this cycle's clients.

    Falls back to the list saved in `<work>/current.json` when the share cannot be read,
    and says so; with no saved list either, it is empty and the page shows the roster only.
    """
    cache_p = os.path.join(str(work), "current.json")
    got = share_reports(root, period, log=log)
    if got is None:
        try:
            with open(cache_p, encoding="utf-8") as fh:
                doc = json.load(fh)
        except (OSError, ValueError):
            doc = {}
        log("current clients: reports share not reachable - using the list last read (%s)"
            % (doc.get("folder") or "none saved"))
        return doc.get("clients") or {}, doc.get("folder")
    folder, clients = got
    tmp = cache_p + ".part"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump({"folder": folder, "read": _dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
                   "clients": clients}, fh, indent=1)
    os.replace(tmp, cache_p)
    return clients, folder


def infer_programs(cid, kinds, mrpc_tabs=(), cp_ids=(), has_ics_sheet=False):
    """Programs for a client clients.md does not cover, in page order (ARS, ICS, MRPC, CP)."""
    progs = []
    if WORKBOOK in kinds:
        progs.append("ARS")
    if has_ics_sheet:
        progs.append("ICS")
    if MRPCPM in kinds or cid in mrpc_tabs:
        progs.append("MRPC")
    if cid in cp_ids:
        progs.append("CP")
    return progs


def detect_path(workbook):
    """"MM" or "SM" for an ARS workbook clients.md has no Path for, or None if unreadable.

    The same test clients.md's own Path column was set by (2026-08-28): the
    `Executive Financials MM` tab names the client for a Lift Matrix workbook and carries
    the `Bank Name` template placeholder for a Monthly Summary one.
    """
    import openpyxl
    try:
        wb = openpyxl.load_workbook(workbook, read_only=True, data_only=True)
    except Exception:
        return None
    try:
        if "Executive Financials MM" not in wb.sheetnames:
            return "SM"
        for row in wb["Executive Financials MM"].iter_rows(min_row=1, max_row=6, values_only=True):
            if any(isinstance(v, str) and v.strip() == "Bank Name" for v in row):
                return "SM"
        return "MM"
    finally:
        wb.close()
