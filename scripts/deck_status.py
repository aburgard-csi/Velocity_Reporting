#!/usr/bin/env python3
"""
deck_status.py — where every client's monthly review stands, for one period.

Answers three questions that live in three different places:

  1. **Is the data ready?**  The data team lands files on the CSI shares; they are
     then copied into `Inputs/`, which is what the builders read. Both are checked, and
     they are NOT the same fact: a file at source that nobody has copied yet is a
     five-minute task, while a file missing at source is a wait on someone else.
  2. **Has the deck been built?**  `Outputs/`.
  3. **Has it been SENT?**  Nothing on disk knows this. A deck in `Outputs/` proves
     it was built and nothing more, so sent-state is recorded in its own file —
     `Build Artifacts/deliveries.json` (Aaron, 2026-08-31), written by the
     dashboard. Bookkeeping, not a deliverable, so it stays out of `Outputs/`.

The roster comes from `clients.md` via `build_month.read_roster` — the same parser
the build driver uses, deliberately. A second list of who gets what would be a
second answer to the question clients.md exists to settle.

**The CSI shares need the VPN.** Off VPN they are not "empty", they are unknown,
and reporting unknown as missing would show a full cycle of phantom gaps. The
share roots are probed once; if unreachable, every source column reports
`unknown` and the dashboard says so, rather than inventing bad news.

Usage:
    python3 scripts/deck_status.py <period> [--json out.json] [--no-source]

    period       YYYY.MM, e.g. 2026.09
    --json       write the status document here (default: stdout)
    --no-source  skip the CSI shares entirely (fast, local inputs only)
"""
import argparse
import datetime as _dt
import glob
import json
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "build"))
sys.path.insert(0, os.path.join(REPO, "scripts"))

import rpe_env as R                                              # noqa: E402
from build_month import read_roster, deck_tag                    # noqa: E402

# The data team's landing zones. These are the ORIGIN, and the backup: `Inputs/`
# is a copy of them (Aaron, 2026-09-09 — no separate backup; if an input is lost,
# it is re-copied from here or re-sent by email).
# Overridable so a machine that mounts them differently needs no code edit — the
# same rule as RPE_DATA_ROOT.
#
# ODD extracts land in EACH CSM's own folder (Aaron, 2026-09-14), so RPE_SRC_ODDD
# holds all five as "CSM=path" entries separated by ";". A bare path (the old
# single-folder form) still works and is labelled by its folder name.
_DEFAULT_SRC_ODDD = ";".join([
    "Aaron Burgard=\\\\PADMIS105\\Velocity_company\\Aburgard\\ODDD",
    "Daniel Wood=\\\\PADMIS105\\Velocity_company\\Dan Wood\\OD Data Dumps",
    "Gregg Miller=\\\\PADMIS105\\Velocity_company\\GMiller\\OD Data Dumps",
    "James Gilmore=\\\\PADMIS105\\Velocity_company\\JamesG\\OD Data Dumps",
    "Jordan Berkowitz=\\\\PADMIS105\\Velocity_company\\JBerkowitz\\OD Data Dumps",
])
SRC_ODDD = os.environ.get("RPE_SRC_ODDD", _DEFAULT_SRC_ODDD)
SRC_REPORTS = os.environ.get(
    "RPE_SRC_REPORTS", "\\\\PADMIS105\\Velocity_clientreports")

PRESENT, MISSING, UNKNOWN, NA = "present", "missing", "unknown", "n/a"
# The ODD extract is the one input `Inputs/` CANNOT date from its filename, so it gets
# a state of its own — see the ODD block in requirements() for why.
STALE = "stale"

# Absent this is not a gap: the ICS section simply builds
# referrals-only, which is a valid deck. Everything else missing blocks the build.
OPTIONAL_INPUT = "ICS workbook (email)"


def _period_ok(p):
    return bool(re.fullmatch(r"\d{4}\.\d{2}", p))


# --------------------------------------------------------------- source share
def _reachable(path):
    try:
        return os.path.isdir(path)
    except OSError:
        return False


def odd_roots(spec=None):
    """[(csm, folder)] from an RPE_SRC_ODDD value ("CSM=path;CSM=path" or a bare path)."""
    out = []
    for part in (SRC_ODDD if spec is None else spec).split(";"):
        part = part.strip()
        if not part:
            continue
        name, sep, path = part.partition("=")
        if not sep:
            name, path = os.path.basename(part.rstrip("\\/")) or part, part
        out.append((name.strip(), path.strip()))
    return out


def odd_folder_period(name):
    """'YYYY.MM' for an ODD month folder, or None for anything else ('Archive', '2025').

    Every CSM names these differently (2026-09-14): Aaron '2026.09 Sep', James
    '2026.09', Jordan and Gregg 'September, 2026', Dan '090126' (the first of the
    month, MMDDYY). A folder that fits none of them is not a month and is not read.
    """
    n = name.strip()
    m = re.fullmatch(r"(\d{4})\.(\d{2})(?:\s+[A-Za-z]{3})?", n)
    if m:
        return "%s.%s" % m.groups()
    for rx, fmt in ((r"[A-Za-z]+, \d{4}", "%B, %Y"), (r"\d{6}", "%m%d%y")):
        if re.fullmatch(rx, n):
            try:
                return _dt.datetime.strptime(n, fmt).strftime("%Y.%m")
            except ValueError:
                return None
    return None


def odd_reachable(spec=None):
    """Every CSM's ODD folder is reachable. One unreachable folder counts as off VPN:
    otherwise that CSM's extracts would read as missing, or as gone from the share."""
    roots = odd_roots(spec)
    return bool(roots) and all(_reachable(p) for _, p in roots)


def _oddd_month_dirs(period, spec=None):
    """[(csm, folder)]: every CSM's month folder for `period`."""
    out = []
    for csm, root in odd_roots(spec):
        try:
            names = os.listdir(root)
        except OSError:
            continue
        for d in sorted(names):
            p = os.path.join(root, d)
            if odd_folder_period(d) == period and os.path.isdir(p):
                out.append((csm, p))
    return out


def find_source_odd(cid, period, spec=None):
    """(path, csm) of the client's `period` extract in whichever CSM folder holds it.

    A client normally sits in one CSM's folder. If two hold the same month (a
    handover), the most recent write wins — the same choice the copy makes.
    """
    hits = []
    for csm, month in _oddd_month_dirs(period, spec):
        p = os.path.join(month, cid + "_ODDD.zip")
        if os.path.exists(p):
            hits.append((os.path.getmtime(p), p, csm))
    if not hits:
        return None, None
    _, p, csm = max(hits)
    return p, csm


def _source_reports(period):
    """Every file the data team landed for `period`, across all account managers.

    Foldered by account manager, so a client's workbook is not necessarily under
    Aaron's name. Searching one manager's folder would report another manager's
    client as missing.
    """
    out = []
    root = os.path.join(SRC_REPORTS, period)
    if not _reachable(root):
        return out
    for am in sorted(glob.glob(os.path.join(root, "*"))):
        if os.path.isdir(am):
            out += [f for f in glob.glob(os.path.join(am, "*")) if os.path.isfile(f)]
    return out


# --------------------------------------------------------------- requirements
def _stat(state, detail="", where=""):
    return {"state": state, "detail": detail, "where": where}


def _newest(paths):
    paths = [p for p in paths if os.path.exists(p)]
    if not paths:
        return None
    return max(paths, key=os.path.getmtime)


def _mtime(path):
    return _dt.datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d")


# Some filesystems record mtime to whole seconds; the SMB share keeps sub-second
# precision. A file copied straight across therefore reads as ~0.9s OLDER on
# locally than at source, which a strict comparison calls stale — it flagged
# 1075's 2026.08 extract (byte-identical, 229,507,542 bytes, same second) as a
# previous month's. FAT-derived filesystems round to 2s, so the tolerance covers
# both with room to spare; a genuinely stale extract is a MONTH out, not a minute.
_MTIME_TOLERANCE = 60.0


def _same_file(a, b):
    """Same size => same extract, for these files.

    The ODD extracts are 6-220 MB zips of a month's account rows. Two different
    months matching to the byte does not happen, so an exact size match is a
    stronger identity signal than any timestamp a network filesystem reports.
    """
    try:
        return os.path.getsize(a) == os.path.getsize(b)
    except OSError:
        return False


def _vip_sheet(cid, program):
    """The VIP sheet for one client, via the manifest resolver.

    resolve_client_json raises SystemExit when the store cannot answer, which is
    a missing input here, not a reason to abandon the whole report.
    """
    try:
        p = str(R.resolve_client_json(cid, program))
    except BaseException:
        return _stat(MISSING, "not pulled", "local")
    if os.path.exists(p):
        return _stat(PRESENT, _mtime(p), "local")
    return _stat(MISSING, "not pulled", "local")


def requirements(cid, progs, period, reports_dir, oddd_dir, src_files, src_up):
    """What this client needs for `period`, and whether each piece is there.

    One row per required input. `src` is what the data team landed; `local` is the
    copy the builders actually read. Keeping them apart is the point — they fail
    for different reasons and the fix is different.
    """
    rows = []
    src_names = {os.path.basename(f).lower(): f for f in src_files}

    def src_match(pattern):
        if not src_up:
            return _stat(UNKNOWN, "VPN not connected", "source")
        rx = re.compile(pattern, re.I)
        hit = [p for n, p in src_names.items() if rx.search(n)]
        if hit:
            return _stat(PRESENT, _mtime(_newest(hit)), "source")
        return _stat(MISSING, "not landed", "source")

    def input_glob(pattern, exclude=None):
        # `reports_dir` is a LIST since inputs are sorted into a folder per kind
        # (Aaron, 2026-09-09). A pattern built against it is expanded per folder.
        pats = pattern if isinstance(pattern, (list, tuple)) else [pattern]
        hit = [f for p in pats for f in glob.glob(p)
               if not (exclude and exclude in os.path.basename(f).lower())]
        if hit:
            return _stat(PRESENT, _mtime(_newest(hit)), "local")
        return _stat(MISSING, "not copied", "local")

    if "ARS" in progs:
        # The ODD extract is period-stamped at SOURCE (month folders) but NOT on
        # in `Inputs/`, where it is overwritten in place as `<id>_ODDD.zip`. So
        # "a file exists" does NOT mean "this period's extract is there" —
        # last month's sits at exactly the same path under exactly the same name.
        #
        # Reporting that as present is the stale-data failure this pipeline keeps
        # hitting: the build would run to completion on the previous month's ODD
        # and validate perfectly, because month-old figures are internally
        # consistent. So the source folder is treated as the authority on which
        # month `Inputs/` is holding, and anything it cannot vouch for is STALE, not
        # present. Off VPN there is no authority, so the period is unconfirmed and
        # says so rather than passing itself off as current.
        src_file = None
        if not src_up:
            src_odd = _stat(UNKNOWN, "VPN not connected", "source")
        else:
            # Whichever CSM's folder holds it (Aaron, 2026-09-14).
            src_file, _csm = find_source_odd(cid, period)
            if src_file:
                src_odd = _stat(PRESENT, _mtime(src_file), "source")
            else:
                src_odd = _stat(MISSING, "not landed", "source")

        z = str(oddd_dir / (cid + "_ODDD.zip"))
        if not os.path.exists(z):
            local_odd = _stat(MISSING, "not copied", "local")
        elif not src_up:
            local_odd = _stat(UNKNOWN, "held, period unconfirmed "
                                       "(" + _mtime(z) + ")", "local")
        elif src_file is None:
            local_odd = _stat(STALE, "previous month (" + _mtime(z) + "); no "
                              + period + " extract at source", "local")
        elif _same_file(z, src_file):
            local_odd = _stat(PRESENT, _mtime(z), "local")
        elif os.path.getmtime(z) + _MTIME_TOLERANCE < os.path.getmtime(src_file):
            local_odd = _stat(STALE, "older than source (" + _mtime(z) + ")", "local")
        else:
            local_odd = _stat(PRESENT, _mtime(z), "local")

        rows.append({"program": "ARS", "input": "ODD extract",
                     "src": src_odd, "local": local_odd})
        rows.append({
            "program": "ARS", "input": "ARS workbook",
            "src": src_match("^" + cid + "-" + re.escape(period) + "-.*workbook.*[.]xlsx$"),
            "local": input_glob(
                [os.path.join(d, cid + "-" + period + "-*Workbook*.xlsx")
                 for d in reports_dir],
                exclude="invitation checking")})
        rows.append({
            "program": "ARS", "input": "DCO",
            "src": src_match("^" + cid + "-" + re.escape(period) + "-.*dco.*[.]xlsx$"),
            "local": input_glob(
                [os.path.join(d, cid + "-" + period + "-*DCO*.xlsx")
                 for d in reports_dir])})

    if any(p.startswith("ICS") for p in progs):
        rows.append({"program": "ICS", "input": "VIP referral sheet",
                     "src": _stat(NA, "VIP dashboard", "source"),
                     "local": _vip_sheet(cid, "ics")})
        # ICS workbooks reach Aaron by EMAIL, not the CSI share (Aaron,
        # 2026-08-31). There is no source-side signal to wait on, so the source
        # column is n/a rather than a gap.
        rows.append({"program": "ICS", "input": OPTIONAL_INPUT,
                     "src": _stat(NA, "arrives by email", "source"),
                     "local": input_glob(
                         [os.path.join(d, cid + "-" + period
                                       + "-*Invitation Checking*.xlsx")
                          for d in reports_dir])})

    if "MRPC" in progs:
        rows.append({"program": "MRPC", "input": "VIP MRPC sheet",
                     "src": _stat(NA, "VIP dashboard", "source"),
                     "local": _vip_sheet(cid, "mrpc")})
        rows.append({
            "program": "MRPC", "input": "MRPCPM analysis",
            "src": src_match("^" + cid + "-" + re.escape(period)
                             + "-mrpc-.*mrpcpm.*[.]xlsx$"),
            "local": input_glob(
                [os.path.join(d, cid + "-" + period
                              + "-MRPC-*MRPCPM_Analysis*.xlsx")
                 for d in reports_dir])})
    return rows


# --------------------------------------------------------------- built / sent
def built_deck(cid, period, outputs_dir):
    """The finished deck for this client+period, if one is in Outputs/.

    Matched on the `<id>-<period>-` prefix only. The program tag and the client
    name both vary — and the name CHANGES (1537 became Brooks Bank on
    2026-08-31) — so the id and period are the only stable parts of the filename.

    Decks are filed in a folder per CSM (2026-09-14), so every `Outputs/<CSM>/` is
    searched, plus the flat root; never Archive/.
    """
    hits = [str(p) for p in R.output_decks(cid + "-" + period + "-*.pptx", root=outputs_dir)]
    if not hits:
        return None
    f = _newest(hits)
    return {"file": os.path.basename(f), "built": _mtime(f)}


def deliveries_path():
    return str(R.build_artifacts() / "deliveries.json")


def read_deliveries():
    p = deliveries_path()
    if not os.path.exists(p):
        return {"version": 1, "sent": {}}
    try:
        with open(p, encoding="utf-8") as fh:
            d = json.load(fh)
    except (OSError, ValueError) as e:
        # A corrupt log must not be silently replaced with an empty one — that
        # would report every delivered deck as unsent and invite sending twice.
        raise SystemExit("%s is unreadable (%s). Fix or move it; refusing to "
                         "treat a damaged delivery log as 'nothing sent'." % (p, e))
    if not isinstance(d, dict) or not isinstance(d.get("sent"), dict):
        raise SystemExit("%s is not a delivery log (no 'sent' object)." % p)
    return d


def write_deliveries(doc):
    p = deliveries_path()
    doc["version"] = 1
    doc["updated"] = _dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=1, ensure_ascii=False)
        fh.write("\n")
    os.replace(tmp, p)
    return p


def mark_sent(cid, period, sent_at=None, note="", by=""):
    """Record one deck as sent. Returns the updated record."""
    doc = read_deliveries()
    key = cid + "|" + period
    doc["sent"][key] = {
        "client_id": cid, "period": period,
        "sent_at": sent_at or _dt.date.today().strftime("%Y-%m-%d"),
        "note": note, "by": by,
    }
    write_deliveries(doc)
    return doc["sent"][key]


def clear_sent(cid, period):
    """Undo a sent mark — a misclick must be correctable, or the log gets edited
    by hand and stops being trustworthy."""
    doc = read_deliveries()
    doc["sent"].pop(cid + "|" + period, None)
    write_deliveries(doc)


# --------------------------------------------------------------- assembly
def collect(period, use_source=True):
    roster, skipped = read_roster()
    I = R.inputs()
    reports_dir = [str(d) for d in R.report_dirs()]
    oddd_dir = I / "ODDD"
    outputs_dir = str(R.outputs())

    src_up = bool(use_source) and _reachable(SRC_REPORTS) and odd_reachable()
    src_files = _source_reports(period) if src_up else []
    sent = read_deliveries()["sent"]

    clients = []
    for cid, name, mmsm, progs in roster:
        rows = requirements(cid, progs, period, reports_dir, oddd_dir, src_files, src_up)
        # STALE blocks exactly as hard as MISSING. A previous month's ODD builds a
        # deck that passes every check and reports the wrong month's numbers,
        # which is worse than a build that fails outright.
        blocked = [r["input"] for r in rows
                   if r["local"]["state"] in (MISSING, STALE)
                   and r["input"] != OPTIONAL_INPUT]
        # Waiting on the data team is a different problem from waiting on a copy,
        # and only the second one is Aaron's to fix right now.
        at_source = [r["input"] for r in rows
                     if r["local"]["state"] == MISSING
                     and r["src"]["state"] == PRESENT]
        clients.append({
            "id": cid, "name": name, "path": mmsm, "programs": progs,
            "tag": deck_tag(progs), "inputs": rows,
            "ready": not blocked,
            "blocked_on": blocked,
            "copyable": at_source,
            "built": built_deck(cid, period, outputs_dir),
            "sent": sent.get(cid + "|" + period),
        })

    return {
        "period": period,
        "generated": _dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "source_reachable": src_up,
        "source_checked": bool(use_source),
        "source_oddd": SRC_ODDD,
        "source_reports": SRC_REPORTS,
        "deliveries_file": deliveries_path(),
        "clients": clients,
        "not_built": [{"id": c, "name": n, "why": w} for c, n, w in skipped],
    }


def main():
    ap = argparse.ArgumentParser(
        description="Data readiness, build and delivery status for one period.")
    ap.add_argument("period")
    ap.add_argument("--json", default=None)
    ap.add_argument("--no-source", action="store_true",
                    help="skip the CSI shares (local inputs only)")
    a = ap.parse_args()
    if not _period_ok(a.period):
        raise SystemExit("period must be YYYY.MM, got %r" % a.period)

    doc = collect(a.period, use_source=not a.no_source)
    text = json.dumps(doc, indent=1)
    if a.json:
        with open(a.json, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
        n = len(doc["clients"])
        ready = sum(1 for c in doc["clients"] if c["ready"])
        built = sum(1 for c in doc["clients"] if c["built"])
        sent = sum(1 for c in doc["clients"] if c["sent"])
        src = "yes" if doc["source_reachable"] else (
            "skipped" if not doc["source_checked"] else "NOT REACHABLE (VPN?)")
        print("%s: %d clients | data ready %d | built %d | sent %d | source %s"
              % (a.period, n, ready, built, sent, src))
        print("wrote " + a.json)
    else:
        print(text)


if __name__ == "__main__":
    main()
