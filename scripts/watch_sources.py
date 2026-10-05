#!/usr/bin/env python3
"""
watch_sources.py — what the data team landed on the CSI shares since last time.

The monthly inputs arrive on the CSI shares, on nobody's schedule:

    <each CSM's ODD folder>\\<month folder>\\<id>_ODDD.zip   (all five CSMs, see
        deck_status.SRC_ODDD; each CSM names the month folder differently)
    \\\\PADMIS105\\Velocity_clientreports\\<YYYY.MM>\\<Account Manager>\\
        <id>-<YYYY.MM>-<Client>-DCO v2_2.xlsx
        <id>-<YYYY.MM>-<Client>-Workbook_v2_1_0.xlsx
        <id>-<YYYY.MM>-MRPC-<Client>-MRPCPM_Analysis_v10.xlsx

Most of a month's files land in one batch on the first business day, but not
all of them: 1174's 2026.08 extract came four days after the rest, 1502's
2026.09 extract six days after, and a re-landed file (same name, new bytes)
looks exactly like the old one at a glance. `deck_status.py` answers "is it
there NOW"; this script answers "what CHANGED since I last looked", which is
the question a daily check actually asks.

It scans this month's and last month's folders on both shares, compares the
inventory to the one it saved last run, and reports files that are new, have
been re-landed (size or mtime changed), or have disappeared. For each it says
whether the copy the builders read is already current. With `--copy` it
then copies what `Inputs/` lacks into it (Aaron, 2026-09-08): ODD extracts,
DCOs and workbooks for EVERY client on the shares — every CSM's book — except those
clients.md marks as stopped (Aaron, 2026-09-14), each only from the newest month on
the share; see `copy_plan` for why that rule exists. With `--prune` it deletes inputs that
a newer period or weekly of the same client and kind supersedes (Aaron,
2026-09-08); the newest is always kept and a file with no newer version is never
touched — see `prune_plan`.

State and reports live in `Build Artifacts/` (bookkeeping, not a
deliverable, and one copy per pipeline rather than per machine):

    source_watch.json        the inventory as of the last successful check
    source_watch.log         one block per run, appended
    source_watch_latest.md   the most recent report, overwritten

**Off VPN the shares are unknown, not empty.** If either root is unreachable
the run reports that, exits 2, and leaves the saved inventory alone — saving an
empty one would make every file on the share "new" at the next check.

**The first run is a baseline.** With no saved inventory there is no "since",
so the run records what is there and reports the counts, not sixty new files.

Usage:
    python scripts/watch_sources.py                # check, report, save
    python scripts/watch_sources.py --notify       # + Windows toast when there is news
    python scripts/watch_sources.py --copy         # + copy what Inputs/ lacks (see --copy)
    python scripts/watch_sources.py --prune        # + delete inputs a newer version supersedes
    python scripts/watch_sources.py --dry-run      # report only; save nothing
    python scripts/watch_sources.py --period 2026.09 --period 2026.08

Scheduled daily by `scripts/register_watch_task.ps1` (Windows Task Scheduler).
"""
import argparse
import datetime as _dt
import glob
import json
import os
import re
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "build"))
sys.path.insert(0, os.path.join(REPO, "scripts"))

import rpe_env as R                                              # noqa: E402
import deck_status as DS                                         # noqa: E402
from build_month import read_roster                              # noqa: E402

# One definition of the share roots: deck_status owns them (and their env
# overrides RPE_SRC_ODDD / RPE_SRC_REPORTS). A second copy here would be a
# second place to update when a share moves.
SRC_ODDD = DS.SRC_ODDD
SRC_REPORTS = DS.SRC_REPORTS

ODDD, DCO, WORKBOOK, MRPCPM, ICS_WB, OTHER = (
    "ODDD", "DCO", "Workbook", "MRPCPM", "ICS workbook", "other")
KIND_ORDER = [ODDD, DCO, WORKBOOK, MRPCPM, ICS_WB, OTHER]

STATE_NAME = "source_watch.json"
LOG_NAME = "source_watch.log"
REPORT_NAME = "source_watch_latest.md"
RUNS_NAME = "source_watch_runs.json"

# A daily run is late once the next morning's fire has come and gone. 26 hours
# leaves room for the retry window and a drifting clock, and still flags a
# single missed day rather than waiting for two.
STALE_AFTER_HOURS = 26

# SMB reports sub-second mtimes; a copy elsewhere may not. Anything under this
# is the same landing, not a re-landing. A genuine re-land is hours or days apart.
_MTIME_TOLERANCE = 2.0

_PERIOD_RX = re.compile(r"(\d{4}\.\d{2})")
_REPORT_RX = re.compile(r"^(\d{3,5})-(\d{4}\.\d{2})-(.+)$", re.I)
_ODDD_RX = re.compile(r"^(\d{3,5})_ODDD\.zip$", re.I)


# ------------------------------------------------------------------ periods
def periods_to_watch(today=None, back=1):
    """This month and the `back` before it, newest first.

    Two months, not one: the data team is still landing stragglers for the
    period that just closed while the new one starts filling, and a check that
    only watched the newest folder would miss the late file that a client's
    deck was waiting on.
    """
    d = (today or _dt.date.today()).replace(day=1)
    out = []
    for _ in range(back + 1):
        out.append("%04d.%02d" % (d.year, d.month))
        d = (d - _dt.timedelta(days=1)).replace(day=1)
    return out


# ------------------------------------------------------------------ classify
def classify(path, share):
    """One inventory record for a file on a share, or None to ignore it.

    `share` is "oddd" or "reports". Kind, client and period come from the
    filename (and, for the ODD extracts, the month folder) — the same naming the
    builders and deck_status rely on. A file that fits no pattern is still
    recorded, as `other`, so an unexpectedly named workbook is reported rather
    than silently ignored.
    """
    name = os.path.basename(path)
    if name.startswith("~$") or name.startswith("."):     # Office lock files
        return None
    folder = os.path.basename(os.path.dirname(path))
    rec = {"path": path, "name": name, "folder": folder, "share": share,
           "kind": OTHER, "client": None, "period": None}
    if share == "oddd":
        # Every CSM names ODD month folders differently; deck_status reads them all.
        rec["period"] = DS.odd_folder_period(folder)
    else:
        m = _PERIOD_RX.search(folder)
        rec["period"] = m.group(1) if m else None

    if share == "oddd":
        m = _ODDD_RX.match(name)
        if m:
            rec["kind"], rec["client"] = ODDD, m.group(1)
        return rec

    m = _REPORT_RX.match(name)
    if m:
        rec["client"], rec["period"] = m.group(1), m.group(2)
        rest = m.group(3).lower()
        if "mrpcpm" in rest:
            rec["kind"] = MRPCPM
        elif "invitation checking" in rest:
            rec["kind"] = ICS_WB
        elif re.search(r"\bdco\b", rest):
            rec["kind"] = DCO
        elif "workbook" in rest:
            rec["kind"] = WORKBOOK
    return rec


def _stat_into(rec):
    st = os.stat(rec["path"])
    rec["size"] = st.st_size
    rec["mtime"] = st.st_mtime
    return rec


def _key(path):
    return os.path.normcase(path)


# ------------------------------------------------------------------ scan
def reachable():
    return DS.odd_reachable(SRC_ODDD) and DS._reachable(SRC_REPORTS)


def scan(periods):
    """{key: record} for every file on either share in the given periods.

    The ODD side is every CSM's folder (Aaron, 2026-09-14), and each record is
    tagged with the CSM whose folder it came from.
    """
    found = {}
    for p in periods:
        for csm, month in DS._oddd_month_dirs(p, SRC_ODDD):
            for f in glob.glob(os.path.join(month, "*")):
                if os.path.isfile(f):
                    rec = classify(f, "oddd")
                    if rec:
                        rec["csm"] = csm
                        found[_key(f)] = _stat_into(rec)
        root = os.path.join(SRC_REPORTS, p)
        if not os.path.isdir(root):
            continue
        for am in glob.glob(os.path.join(root, "*")):
            if not os.path.isdir(am):
                continue
            for f in glob.glob(os.path.join(am, "*")):
                if os.path.isfile(f):
                    rec = classify(f, "reports")
                    if rec:
                        found[_key(f)] = _stat_into(rec)
    return found


# ------------------------------------------------------------------ inputs
def input_state(rec, inputs_dir):
    """Is the copy the builders read already this file?

    Same size means the same landing for these files (the rule deck_status
    already uses for the ODD extracts). A different size means Inputs/ holds an
    earlier landing of the same name — which for the ODD extract, overwritten
    in place as `<id>_ODDD.zip`, usually means last month's.
    """
    if inputs_dir is None:
        return "unknown"
    if rec["kind"] == ODDD:
        cand = os.path.join(inputs_dir, "ODDD", rec["client"] + "_ODDD.zip")
    else:
        cand = _find_input(inputs_dir, rec["name"])
    try:
        if not os.path.exists(cand):
            return "not copied"
        return "copied" if os.path.getsize(cand) == rec["size"] else "differs"
    except OSError:
        return "unknown"


def _inputs_dir():
    try:
        return str(R.inputs())
    except BaseException:
        return None


# ------------------------------------------------------------------ copy
def _report_dirs(inputs_dir):
    """Every folder under Inputs/ that can hold a workbook-ish file, newest
    scheme first, then the legacy flat folder. Mirrors rpe_env.report_dirs() but
    takes the directory as an argument so the tests can point it at a tmpdir."""
    names = [v for k, v in R.INPUT_KIND_DIRS.items() if k not in R.NOT_SCANNED_KINDS]
    names.append(R.LEGACY_REPORTS_DIRNAME)
    return [os.path.join(inputs_dir, n) for n in names
            if os.path.isdir(os.path.join(inputs_dir, n))]


# Folders outside the workbook-ish set that still hold one-per-client-per-month files, so
# prune has a newer version to compare (Aaron, 2026-09-21). They stay out of `_report_dirs`
# because no reader globs them: the CashPlease marketing files are resolved by exact path.
PRUNE_ALSO_KINDS = ("CP marketing",)


def _prune_also_dirs(inputs_dir):
    out = []
    for kind in PRUNE_ALSO_KINDS:
        d = os.path.join(inputs_dir, R.INPUT_KIND_DIRS[kind])
        if os.path.isdir(d):
            out.append(d)
    return out


def _find_input(inputs_dir, name):
    """The existing copy of `name`, wherever it was sorted to. Falls back to the
    path it WOULD take, so a caller can stat it and find it absent."""
    for d in _report_dirs(inputs_dir):
        p = os.path.join(d, name)
        if os.path.exists(p):
            return p
    return os.path.join(inputs_dir, R.LEGACY_REPORTS_DIRNAME, name)


def _dest_for(rec, inputs_dir):
    """Where a copied file lands: one folder per KIND (Aaron, 2026-09-09).

    Everything used to go into one flat "ARS & MRPC Reports" folder — DCOs, ARS
    workbooks, MRPC analyses and ICS workbooks together, 55 files deep, with the
    kind readable only from the filename. The folder names live in
    `rpe_env.INPUT_KIND_DIRS` and nowhere else; readers resolve through
    `rpe_env.report_dirs()`, which still includes the old flat folder so a file
    left there is found.
    """
    if rec["kind"] == ODDD:
        d = os.path.join(inputs_dir, R.INPUT_KIND_DIRS["ODDD"])
        os.makedirs(d, exist_ok=True)
        return os.path.join(d, rec["client"] + "_ODDD.zip")
    d = os.path.join(inputs_dir, R.INPUT_KIND_DIRS.get(rec["kind"],
                                                        R.LEGACY_REPORTS_DIRNAME))
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, rec["name"])


def copy_plan(inventory, roster_ids, inputs_dir, stopped=None):
    """Which source files should be copied into `Inputs/`: [(record, destination)].

    The destination is whatever `RPE_DATA_ROOT` resolves to — the local tree
    This code has never known where that is — it asks `rpe_env` — which is why
    moving the tree needed no change here beyond the report wording.

    Which clients (Aaron, 2026-09-14): with `stopped` given, EVERY client on the
    shares — all five CSMs' books, ODD extracts, DCOs and workbooks alike — except the
    ids in `stopped`, the clients clients.md marks as ended or cancelled, whose files
    the data team keeps landing (1437 Canandaigua). Without it only `roster_ids` are
    copied, which is what an unreadable clients.md falls back to. Only files `Inputs/`
    does not hold, or holds a different landing of (`differs`). If two CSM folders
    hold the same client and month, the more recent write is taken.

    The ODD extract needs one more rule. It lives in `Inputs/` as `<id>_ODDD.zip`
    with no period in the name, and the watch scans two months, so last month's
    extract at source ALWAYS "differs" once this month's has been
    copied. Only the newest month on the share per client is ever a candidate;
    copying an older one back over a newer one is the stale-ODD failure this
    pipeline keeps guarding against, and this is where it would happen.
    """
    if inputs_dir is None:
        return []

    def wanted(rec):
        if rec["kind"] == OTHER or not rec.get("client"):
            return False
        if stopped is not None:
            return rec["client"] not in stopped
        return rec["client"] in roster_ids
    # Newest period on the share per (client, kind). The same rule for every
    # kind, not only the ODD: with --prune removing what a newer period
    # supersedes, copying last month's DCO back would have it deleted again the
    # same run, every day.
    newest = {}
    for rec in inventory.values():
        if wanted(rec) and rec.get("period"):
            k = (rec["client"], rec["kind"])
            if k not in newest or ((rec["period"], rec.get("mtime") or 0)
                                   > (newest[k]["period"], newest[k].get("mtime") or 0)):
                newest[k] = rec
    on_drive = _input_periods(inputs_dir)
    plan = []
    for rec in sorted(inventory.values(), key=lambda r: (r["kind"], r["client"] or "", r["name"])):
        if not wanted(rec):
            continue
        if newest.get((rec["client"], rec["kind"])) is not rec:
            continue
        if rec["kind"] != ODDD and on_drive.get((rec["client"], rec["kind"]), "") > rec["period"]:
            continue                       # Inputs/ already holds a newer period
        if rec.get("local") not in ("not copied", "differs"):
            continue
        # If Inputs/ already holds this file, replace it WHERE IT IS. Sorting
        # into kind folders must not create a second copy of a file that is
        # sitting in the legacy flat folder — two copies of one workbook is the
        # two-stores problem in miniature, and it would also defeat the
        # changed-on-purpose guard below, which compares against the file that
        # actually exists.
        existing = None if rec["kind"] == ODDD else _find_input(inputs_dir, rec["name"])
        dest = existing if (existing and os.path.exists(existing))             else _dest_for(rec, inputs_dir)
        if rec.get("local") == "differs" and not _source_is_newer(rec, dest):
            # Same name, different bytes, and the copy in Inputs/ is the more
            # recent write: that is a copy someone changed on purpose — a workbook
            # opened and saved in Excel so its formulas carry values — not a
            # re-landing. Overwriting it hands the builders the uncalculated
            # original; it did exactly that to 1539's 2026.08 workbook on
            # 2026-09-08 (every ARS figure read 0 afterwards).
            continue
        plan.append((rec, dest))
    return plan


def _input_periods(inputs_dir):
    """{(client, kind): newest period} for the period-stamped files in Inputs/."""
    out = {}
    names = []
    for d in _report_dirs(inputs_dir):
        try:
            names += os.listdir(d)
        except OSError:
            continue
    for n in names:
        rec = classify(n, "reports")
        if rec and rec["kind"] != OTHER and rec["period"]:
            k = (rec["client"], rec["kind"])
            out[k] = max(out.get(k, ""), rec["period"])
    return out


def _source_is_newer(rec, dest):
    if rec.get("mtime") is None:
        return True
    try:
        return rec["mtime"] > os.path.getmtime(dest) + _MTIME_TOLERANCE
    except OSError:
        return True


def apply_copies(plan):
    """Copy each planned file. Copy-only: nothing at the destination is ever
    deleted, and some mounts refuse deletes anyway. Writes to a `.part` file
    first and renames it over the target so a copy that dies half way never
    leaves a truncated extract under the real name; if the rename is refused,
    falls back to writing the target directly. Size is verified after.

    Returns [(record, destination, outcome)], outcome "copied" or an error."""
    import shutil
    out = []
    for rec, dest in plan:
        try:
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            part = dest + ".part"
            shutil.copy2(rec["path"], part)
            try:
                os.replace(part, dest)
            except OSError:
                shutil.copy2(rec["path"], dest)
                try:
                    os.remove(part)
                except OSError:
                    pass
            if os.path.getsize(dest) != rec["size"]:
                raise OSError("size mismatch after copy (%d vs %d)"
                              % (os.path.getsize(dest), rec["size"]))
            rec["local"] = "copied"
            out.append((rec, dest, "copied"))
        except OSError as e:
            out.append((rec, dest, "FAILED: %s" % e))
    return out


# ------------------------------------------------------------------ prune
_WEEKLY_RX = re.compile(r"(MRPCEnrollmentSummary|CashPleaseSummary)", re.I)
_STAMP_RX = re.compile(r"(\d{6}_\d{6})")


def _prune_group(name):
    """The group an input belongs to, or None if it is never pruned.

    Period-stamped client files group by (client, kind): a newer period of the
    same kind supersedes the older. The weeklies group by family and are ordered
    by the stamp in their name. Everything else — the ICS Charts workbooks, the
    ODD extracts (one per client, overwritten in place), anything unrecognised —
    has no "newer version" this code can identify, so it is left alone.
    """
    if name.startswith("~$"):
        return None
    m = _REPORT_RX.match(name)
    if m:
        rec = classify(name, "reports")
        if rec and rec["kind"] != OTHER:
            return ("client", rec["client"], rec["kind"]), rec["period"]
        return None
    m = _WEEKLY_RX.search(name)
    if m:
        st = _STAMP_RX.search(name)
        return ("weekly", m.group(1).lower()), (st.group(1) if st else "")
    # The CashPlease marketing CSVs, one per client per month (Aaron, 2026-09-21). Their
    # names carry `MM.YYYY` rather than the `<id>-<period>-` convention, so mail_sources
    # — which is where these names are read — resolves them. The per-client workbook has
    # no month, so it has no newer version and is never pruned.
    import mail_sources
    parts = mail_sources.cp_marketing_parts(name)
    if parts and parts[1]:
        return ("client", parts[0], mail_sources.CP_MARKETING), parts[1]
    return None


def prune_plan(names):
    """[(superseded name, the newer name that supersedes it)] for one folder.

    Only when a newer version of the SAME thing exists (Aaron, 2026-09-08). One
    file per group is always kept — the newest — and a file that is the only one
    of its kind for a client is never touched, however old.
    """
    groups = {}
    for n in names:
        g = _prune_group(n)
        if g:
            groups.setdefault(g[0], []).append((g[1], n))
    plan = []
    for key, members in groups.items():
        members.sort()
        top, newest = members[-1]
        # Two files with the same version key (a weekly and its "- Copy", say)
        # are not one newer than the other; both stay.
        plan += [(n, newest) for v, n in members[:-1] if v < top]
    return sorted(plan)


def apply_prune(folder, plan, locate=None):
    """Delete the superseded files. The newer file must exist and be non-empty
    at the moment of deletion, or the older one stays. Returns
    [(name, newer, outcome)], outcome "removed" or an error.

    `locate` maps a filename to its full path — inputs are sorted into a folder
    per kind, so the superseded file and its replacement are not necessarily in
    the same one. Without it, names resolve inside `folder`."""
    loc = locate or (lambda nm: os.path.join(folder, nm))
    out = []
    for old, new in plan:
        op, np_ = loc(old), loc(new)
        try:
            if not os.path.exists(np_) or os.path.getsize(np_) == 0:
                raise OSError("newer file %s is missing or empty" % new)
            os.remove(op)
            out.append((old, new, "removed"))
        except OSError as e:
            out.append((old, new, "FAILED: %s" % e))
    return out


# ------------------------------------------------------------------ diff
def diff(previous, current, periods):
    """(new, changed, gone) records, comparing only the periods just scanned.

    Entries the previous inventory holds for OTHER periods are not "gone" —
    they were not looked at. They are carried forward by `merge`.
    """
    prev_files = (previous or {}).get("files", {})
    new, changed, gone = [], [], []
    for k, rec in current.items():
        old = prev_files.get(k)
        if old is None:
            new.append(rec)
        elif (old.get("size") != rec["size"]
              or abs(float(old.get("mtime", 0)) - rec["mtime"]) > _MTIME_TOLERANCE):
            changed.append(dict(rec, old_size=old.get("size"), old_mtime=old.get("mtime")))
    for k, old in prev_files.items():
        if old.get("period") in periods and k not in current:
            gone.append(old)
    return new, changed, gone


def merge(previous, current, periods):
    """The next saved inventory: scanned periods replaced, the rest kept."""
    files = {k: v for k, v in (previous or {}).get("files", {}).items()
             if v.get("period") not in periods}
    files.update(current)
    return {"version": 1,
            "checked": _dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
            "periods": periods,
            "source_oddd": SRC_ODDD, "source_reports": SRC_REPORTS,
            "files": files}


# ------------------------------------------------------------------ state io
def state_path():
    return str(R.build_artifacts() / STATE_NAME)


def read_state(path=None):
    p = path or state_path()
    if not os.path.exists(p):
        return None
    try:
        with open(p, encoding="utf-8") as fh:
            d = json.load(fh)
    except (OSError, ValueError) as e:
        # A damaged inventory must not be read as an empty one: the next report
        # would list every file on the share as news.
        raise SystemExit("%s is unreadable (%s). Fix or move it; refusing to treat "
                         "a damaged inventory as 'nothing seen'." % (p, e))
    if not isinstance(d, dict) or not isinstance(d.get("files"), dict):
        raise SystemExit("%s is not a source inventory (no 'files' object)." % p)
    return d


def write_state(doc, path=None):
    p = path or state_path()
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=1, ensure_ascii=False)
        fh.write("\n")
    os.replace(tmp, p)
    return p


# ------------------------------------------------------------------ run record
# The run record is how anything OUTSIDE this process can tell "the watch ran
# and there was no news" from "the watch did not run". In `source_watch.log`
# those are the same thing: the log is only ever written by a run that got far
# enough to write it.
#
# 2026-09-09, -10 and -11 is why it exists. The 08:00 task was created by the
# scheduler and left SUSPENDED — zero CPU, no modules loaded, 2.4 MB peak
# working set: the interpreter never initialized — and was killed at the
# 30-minute limit three mornings running. Nothing was written because no code
# ran, so nothing noticed for three days. An entry line inside this script
# would not have caught that either; only a check somewhere else can, which is
# what `run_health` is for. `refresh_performance_dashboard.py` (a separate
# daily task, on a different scheduler) reports it every morning at 08:30.
def local_runs_path():
    r"""Where the run record REALLY lives: on this machine, not on the share.

    Aaron, 2026-09-23: fix the run record flaw. The record was kept in `Build Artifacts/`
    with everything else, so on 2026-09-22 and -23 the 08:00 runs found the VPN down, could
    not write a single byte anywhere, and left no trace that they had run at all. The
    watchdog then read "no run has reached the shares today", went hunting for a suspended
    process, found none, and logged "needs a human look" twice — when the true answer was
    "off VPN, nothing to do". A record of WHETHER SOMETHING RAN cannot be stored on the
    resource whose absence is the most common reason it did not.

    %LOCALAPPDATA%\RPE is the same place the released launcher unpacks its runtime to, so
    it exists on every machine that runs this task, and it is writable with the VPN down.
    """
    # NOT a temp dir, deliberately: rpe_env.temp_dir is build scratch and is swept, and a
    # record of "did this run?" that a cleaner can delete answers the question wrongly the
    # one week nobody looks. %LOCALAPPDATA% on Windows, the home directory elsewhere.
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~")
    d = os.path.join(base, "RPE")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, RUNS_NAME)


def shared_runs_path():
    """The copy on the share — for the dashboard and for anyone reading from another
    machine. Best effort: written when the share answers, never depended on."""
    return str(R.build_artifacts() / RUNS_NAME)


def runs_path():
    return local_runs_path()


def read_runs(path=None):
    """The run record, or {} when there is none.

    A damaged record is NOT fatal here, unlike a damaged inventory: this is
    bookkeeping ABOUT runs, not data a report is derived from, and refusing to
    run the daily check because its own logbook is corrupt would be the wrong
    trade. It reads as unknown — never as healthy.
    """
    if path:
        return _read_one(path)
    # Local first, then the share, and the NEWER of the two wins. A machine that has been
    # off the VPN for a day has the newer local record; a fresh checkout has only the shared
    # one. Neither is authoritative on its own.
    local, shared = _read_one(local_runs_path()), _read_one_quietly(shared_runs_path)
    if not shared:
        return local
    if not local:
        return shared
    return max((local, shared), key=_recorded_at)


def _recorded_at(doc):
    """The latest moment a record knows about — for choosing between two copies."""
    stamps = [_parse_stamp(doc.get(k)) for k in ("last_finished", "last_started")]
    return max([s for s in stamps if s] or [_dt.datetime.min])


def _read_one(p):
    try:
        with open(p, encoding="utf-8") as fh:
            d = json.load(fh)
    except FileNotFoundError:
        return {}
    except (OSError, ValueError):
        return {"damaged": True}
    return d if isinstance(d, dict) else {"damaged": True}


def _read_one_quietly(path_fn):
    """The share copy, or {} — resolving its path can itself fail off VPN."""
    try:
        return _read_one(path_fn())
    except (OSError, ValueError, SystemExit):
        return {}


def _write_runs(doc, path=None):
    """Write the record locally, then mirror it to the share if the share is there.

    The local write is the one that matters and the one that must not be skipped: it is the
    only write that still works on the morning this record exists to describe.
    """
    p = path or local_runs_path()
    _write_one(doc, p)
    if not path:
        try:
            _write_one(doc, shared_runs_path())
        except (OSError, ValueError, SystemExit):
            pass                   # off VPN: the local copy is the record
    return p


def _write_one(doc, p):
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=1, ensure_ascii=False)
        fh.write("\n")
    os.replace(tmp, p)
    return p


def _stamp(now=None):
    return (now or _dt.datetime.now()).strftime("%Y-%m-%d %H:%M:%S")


def record_start(argv, path=None, now=None):
    """Stamp the start of a run. Never raises: a check must not die for want of
    somewhere to put its own bookkeeping (the same rule `build_artifacts` follows)."""
    try:
        doc = read_runs(path)
        doc.pop("damaged", None)
        doc["last_started"] = _stamp(now)
        doc["last_started_argv"] = list(argv)
        doc["last_started_pid"] = os.getpid()
        return _write_runs(doc, path)
    except (OSError, ValueError):
        return None


def record_finish(outcome, path=None, now=None):
    """Stamp a run that got through the share check and wrote its report.

    Written BEFORE the mail step, for the same reason the log and report are:
    the mail step can time out, and a share check that finished is a run that
    finished.
    """
    try:
        doc = read_runs(path)
        doc.pop("damaged", None)
        doc["last_finished"] = _stamp(now)
        doc["last_outcome"] = outcome
        return _write_runs(doc, path)
    except (OSError, ValueError):
        return None


def _parse_stamp(s):
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return _dt.datetime.strptime(s, fmt)
        except (TypeError, ValueError):
            continue
    return None


def run_health(now=None, path=None, stale_after=STALE_AFTER_HOURS):
    """(state, detail) for "has the daily watch actually been running?"

        ok      a run completed within `stale_after` hours
        stale   the last completed run is older than that
        never   no run has ever completed, or the record is unreadable

    Age is measured from the last FINISH, not the last start: a run that is
    killed part way leaves a start with no finish, and a run that never starts
    at all leaves neither. Both must read as "not running".

    Outcome is deliberately not consulted. A run that found the shares down
    still RAN — that is the VPN's news, not this check's — and
    `completed_today` is the one that cares about the outcome.
    """
    now = now or _dt.datetime.now()
    doc = read_runs(path)
    if doc.get("damaged"):
        return "never", "the run record is unreadable"
    fin = _parse_stamp(doc.get("last_finished"))
    started = _parse_stamp(doc.get("last_started"))
    if fin is None:
        if started is not None:
            return "never", ("a run started %s and never finished"
                             % started.strftime("%Y-%m-%d %H:%M"))
        return "never", "no run has ever been recorded"
    hours = (now - fin).total_seconds() / 3600.0
    detail = "last completed %s (%.1f h ago)" % (fin.strftime("%Y-%m-%d %H:%M"), hours)
    if started is not None and started > fin:
        detail += ("; a later run started %s and did not finish"
                   % started.strftime("%Y-%m-%d %H:%M"))
    return ("stale" if hours > stale_after else "ok"), detail


def completed_today(now=None, path=None):
    """Has a run already reached the shares today? The retry fires ask this.

    Reaching the shares is the bar, not merely finishing: a run that found the
    VPN down did its job and reported honestly, but it copied nothing, so the
    later fires in the retry window must still go and look.
    """
    now = now or _dt.datetime.now()
    doc = read_runs(path)
    fin = _parse_stamp(doc.get("last_finished"))
    return (fin is not None and fin.date() == now.date()
            and doc.get("last_outcome") == "reachable")


# ------------------------------------------------------------------ report
def _roster():
    try:
        active, _skipped = read_roster()
    except BaseException:
        return {}
    return {cid: name for cid, name, _mmsm, _progs in active}


def _roster_stopped():
    """Client ids clients.md marks as stopped (ended, cancelled, no active program).

    None when clients.md cannot be read, which keeps the copy on the roster rule — and
    an unreadable roster is an empty one, so nothing is copied rather than everything.
    """
    try:
        _active, skipped = read_roster()
    except BaseException:
        return None
    return {cid for cid, _name, _why in skipped}


def _fmt_size(n):
    if n is None:
        return "?"
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return ("%d %s" if unit == "B" else "%.1f %s") % (n, unit)
        n /= 1024.0


def _fmt_when(ts):
    return _dt.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M") if ts else "?"


def _line(rec, roster):
    who = rec["client"] or "—"
    name = roster.get(rec["client"], "")
    tag = " (%s)" % name if name else ""
    if rec["kind"] == ODDD and rec.get("csm"):
        tag += " · %s's folder" % rec["csm"]
    held = rec.get("local", "")
    local_s = "" if not held else "  · Inputs: " + held
    return "- **%s** %s%s — `%s`  %s, landed %s%s" % (
        rec["kind"], who, tag, rec["name"], _fmt_size(rec.get("size")),
        _fmt_when(rec.get("mtime")), local_s)


def _section(title, recs, roster):
    if not recs:
        return []
    mine = [r for r in recs if r["client"] in roster]
    theirs = [r for r in recs if r["client"] not in roster]

    def order(r):
        return (KIND_ORDER.index(r["kind"]), r["client"] or "", r["name"])

    out = ["", "## %s (%d)" % (title, len(recs))]
    if mine:
        out += ["", "### Roster clients (%d)" % len(mine), ""]
        out += [_line(r, roster) for r in sorted(mine, key=order)]
    if theirs:
        out += ["", "### Other account managers' clients (%d)" % len(theirs), ""]
        out += [_line(r, roster) for r in sorted(theirs, key=order)]
    return out


def render(result, roster):
    """The report as Markdown. Also the log block and the stdout text."""
    r = result
    head = ["# Source check — %s" % r["checked"],
            "",
            "Periods: %s  ·  ODD folders: %s  ·  Reports: `%s`" % (
                ", ".join(r["periods"]),
                ", ".join("%s `%s`" % (c, p) for c, p in DS.odd_roots(SRC_ODDD)),
                SRC_REPORTS)]
    if not r["reachable"]:
        down = ["%s's ODD folder" % c for c, p in DS.odd_roots(SRC_ODDD) if not DS._reachable(p)]
        if not DS._reachable(SRC_REPORTS):
            down.append("the client reports share")
        return "\n".join(head + [
            "", "**Shares not reachable (VPN?).** Nothing checked; the saved "
            "inventory from %s was left as it is." % (r.get("previous_checked") or "never")]
            + (["", "Not reachable: " + ", ".join(down) + "."] if down else []))
    if r["baseline"]:
        counts = {}
        for rec in r["inventory"].values():
            counts[rec["kind"]] = counts.get(rec["kind"], 0) + 1
        body = ["", "**First run — baseline recorded.** %d files on the shares for "
                "these periods; the next check reports what changes." % len(r["inventory"]),
                ""] + ["- %s: %d" % (k, counts[k]) for k in KIND_ORDER if k in counts]
        return "\n".join(head + body + _copies_section(r))
    new, changed, gone = r["new"], r["changed"], r["gone"]
    if not (new or changed or gone):
        body = ["", "Nothing new since %s. %d files on the shares for these periods."
                % (r.get("previous_checked") or "the last check", len(r["inventory"]))]
        return "\n".join(head + body + _copies_section(r))
    body = ["", "Since %s: **%d new**, **%d re-landed**, **%d gone**." % (
        r.get("previous_checked") or "the last check", len(new), len(changed), len(gone))]
    to_copy = [x for x in new + changed
               if x["client"] in roster and x.get("local") in ("not copied", "differs")]
    if to_copy:
        body += ["", "**%d of these are for roster clients and not yet in Inputs.**"
                 % len(to_copy)]
    body += _section("New", new, roster)
    body += _section("Re-landed (same name, new bytes)", changed, roster)
    body += _section("Gone from the share", gone, roster)
    return "\n".join(head + body + _copies_section(r))


def _copies_section(result):
    """The copy step's outcome, appended to whichever report shape rendered."""
    done, planned = result.get("copies") or [], result.get("copy_plan") or []
    out = []
    if done:
        ok = [x for x in done if x[2] == "copied"]
        bad = [x for x in done if x[2] != "copied"]
        out += ["", "## Copied into Inputs (%d)" % len(ok) + (", %d FAILED" % len(bad) if bad else ""), ""]
        out += ["- **%s** %s — `%s` -> `%s`" % (r["kind"], r["client"], r["name"], d) for r, d, _ in ok]
        out += ["- **%s** %s — `%s` %s" % (r["kind"], r["client"], r["name"], o) for r, d, o in bad]
    elif planned:
        out += ["", "## Would copy into Inputs (%d) — dry run" % len(planned), ""]
        out += ["- **%s** %s — `%s` -> `%s`" % (r["kind"], r["client"], r["name"], d) for r, d in planned]
    pruned, prune_planned = result.get("pruned") or [], result.get("prune_plan") or []
    if pruned:
        ok = [x for x in pruned if x[2] == "removed"]
        bad = [x for x in pruned if x[2] != "removed"]
        out += ["", "## Removed superseded inputs (%d)" % len(ok)
                + (", %d FAILED" % len(bad) if bad else ""), ""]
        out += ["- `%s` — superseded by `%s`" % (o, n) for o, n, _ in ok]
        out += ["- `%s` %s" % (o, r) for o, n, r in bad]
    elif prune_planned:
        out += ["", "## Would remove superseded inputs (%d) — dry run" % len(prune_planned), ""]
        out += ["- `%s` — superseded by `%s`" % (o, n) for o, n in prune_planned]
    return out + (result.get("ics_referrals") or []) + (result.get("branch_names") or [])


def summary_line(result, roster):
    """One line for the toast and the console."""
    if not result["reachable"]:
        return "Shares not reachable (VPN?) — nothing checked."
    copies = result.get("copies") or []
    copied = sum(1 for x in copies if x[2] == "copied")
    failed = len(copies) - copied
    tail = ""
    if copies:
        tail = " Copied %d into Inputs." % copied + (" %d FAILED." % failed if failed else "")
    pruned = result.get("pruned") or []
    if pruned:
        removed = sum(1 for x in pruned if x[2] == "removed")
        tail += " Removed %d superseded." % removed + (
            " %d FAILED." % (len(pruned) - removed) if len(pruned) > removed else "")
    ics = result.get("ics_referrals") or []
    merged = sum(1 for ln in ics if ln.startswith("- merged "))
    if merged:
        tail += " Merged %d ICS referral pull%s." % (merged, "" if merged == 1 else "s")
    if any(ln.startswith(("- NOT merged", "- FAILED")) for ln in ics):
        tail += " ICS referrals need a look."
    if result["baseline"]:
        return "Baseline recorded: %d files." % len(result["inventory"]) + tail
    new, changed, gone = result["new"], result["changed"], result["gone"]
    if not (new or changed or gone):
        return "Nothing new on the CSI shares." + tail
    mine = [x for x in new + changed if x["client"] in roster]
    parts = []
    if new:
        parts.append("%d new" % len(new))
    if changed:
        parts.append("%d re-landed" % len(changed))
    if gone:
        parts.append("%d gone" % len(gone))
    s = ", ".join(parts)
    if mine:
        kinds = {}
        for x in mine:
            kinds[x["kind"]] = kinds.get(x["kind"], 0) + 1
        s += " — roster: " + ", ".join(
            "%d %s" % (kinds[k], k) for k in KIND_ORDER if k in kinds)
    return s + tail


# ------------------------------------------------------------------ notify
_TOAST_PS = r"""
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
$xml = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
$t = $xml.GetElementsByTagName("text")
$t.Item(0).AppendChild($xml.CreateTextNode($env:RPE_TOAST_TITLE)) | Out-Null
$t.Item(1).AppendChild($xml.CreateTextNode($env:RPE_TOAST_BODY)) | Out-Null
$toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
$app = '{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe'
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($app).Show($toast)
"""


def notify(title, body):
    """A Windows toast, via PowerShell's WinRT bridge. Best effort: a check that
    ran is worth more than a notification that failed, so this never raises."""
    if sys.platform != "win32":
        return False
    env = dict(os.environ, RPE_TOAST_TITLE=title, RPE_TOAST_BODY=body)
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive",
                            "-Command", _TOAST_PS],
                           env=env, capture_output=True, text=True, timeout=30,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return r.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


# ------------------------------------------------------------------ mail
# A COM call into an Outlook that is starting up, syncing, or showing a modal
# dialog blocks until Outlook is done — there is no timeout on the call and a
# thread cannot interrupt it. So the mail step runs as its own process, which
# CAN be killed. Ten minutes is generous: by hand the step takes seconds.
MAIL_TIMEOUT = 600


def mail_step(days, dry_run, timeout=MAIL_TIMEOUT):
    """(report text, [(name, outcome)]) for the mailbox step, run in a
    subprocess with a hard timeout. Never raises: an unreachable, hung or
    failing mailbox is reported, and the share check has already been saved."""
    cmd = [sys.executable, os.path.join(REPO, "scripts", "mail_sources.py")]
    if days:
        cmd += ["--days", str(days)]
    if not dry_run:
        cmd.append("--save")
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=timeout,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except subprocess.TimeoutExpired:
        return ("## From email — TIMED OUT after %d s. Outlook did not answer "
                "(starting up, syncing, or waiting on a dialog?). The share check "
                "above is unaffected; the mailbox is read again tomorrow." % timeout, [])
    except OSError as e:
        return "## From email — FAILED to start: %s" % e, []
    out = (r.stdout or "").strip()
    if r.returncode == 2:
        return "## From email — skipped: " + out.replace("mail step skipped: ", ""), []
    if r.returncode != 0:
        return ("## From email — FAILED (exit %d): %s" % (
            r.returncode, (r.stderr or out).strip()[-600:])), []
    saved = [(ln.split(None, 1)[1], ln.split(None, 1)[0])
             for ln in out.splitlines()
             if ln.startswith("  ") and ln.split(None, 1)[0] in ("saved", "skipped", "FAILED")]
    return out, saved


def save_report(text, result, log_text=None):
    """Write the report, append to the log, and save the inventory when the shares answered.

    Called TWICE in a run (Aaron, 2026-09-21): once as soon as the scan is done, again when the
    copy, prune, referrals and branch-name steps have finished. Until then the only write came
    after all of them, and on a slow share those outrun the task's execution limit: the 08:00
    runs of 2026-09-18 through 2026-09-20 were killed part way and left NO report, which the
    watchdog cannot tell apart from a run that never executed. The scan is the part that must
    survive; the rest is appended when it lands.
    """
    # Off VPN every one of these writes fails, and an unguarded failure killed the run
    # BEFORE it could stamp the run record — so the morning that most needed recording was
    # the one that recorded nothing (Aaron, 2026-09-23). The report is share-only by nature:
    # if it cannot be written, say so and carry on to the parts that still work.
    try:
        art = R.build_artifacts()
        if log_text:
            with open(str(art / LOG_NAME), "a", encoding="utf-8") as fh:
                fh.write(log_text + "\n\n---\n\n")
        with open(str(art / REPORT_NAME), "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
    except (OSError, SystemExit) as e:
        print("!! could not write the report to the share (%s). The run is still recorded "
              "locally; %s --check-stale can answer for it." % (e, os.path.basename(__file__)),
              file=sys.stderr)
        return
    if result["reachable"] and not result.get("_state_saved"):
        write_state(result["next_state"])
        result["_state_saved"] = True
        print("saved " + state_path())


# ------------------------------------------------------------------ run
def check(periods, previous, use_drive=True):
    """Scan, diff and annotate. Pure with respect to the saved state — the
    caller decides whether to persist `result['next_state']`."""
    result = {"checked": _dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
              "periods": periods,
              "previous_checked": (previous or {}).get("checked"),
              "reachable": reachable(), "baseline": previous is None,
              "new": [], "changed": [], "gone": [], "inventory": {},
              "next_state": previous}
    if not result["reachable"]:
        return result
    current = scan(periods)
    inputs_dir = _inputs_dir() if use_drive else None
    for rec in current.values():
        rec["local"] = input_state(rec, inputs_dir)
    result["inventory"] = current
    if previous is not None:
        result["new"], result["changed"], result["gone"] = diff(previous, current, periods)
    result["next_state"] = merge(previous, current, periods)
    return result


def issues_step(dry_run=False):
    """File what Sheila queued, and say what happened. -> markdown for the report.

    Never raises: this runs inside the morning task, and an issue report that cannot be
    filed today is still on the share tomorrow.
    """
    head = "## Reported issues"
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import issue_reports as IR
        queued = [r for r in IR.load_reports() if r.get("status") == "queued"]
        if dry_run:
            return f"{head}\n\n- {len(queued)} queued; --dry-run, so nothing was filed."
        if not queued and not IR.cache_path().exists():
            return f"{head}\n\n- nothing queued."
        res = IR.sync()
        lines = []
        for rid, num in res["filed"]:
            lines.append(f"- filed **#{num}** — `{rid}`")
        for rid, why in res["failed"]:
            lines.append(f"- NOT filed `{rid}`: {why} (still queued)")
        if res.get("list_error"):
            lines.append(f"- the issue list was not refreshed: {res['list_error']}")
        elif not lines:
            lines.append(f"- nothing queued; {res['issues']} issue(s) cached for Sheila.")
        return head + "\n\n" + "\n".join(lines)
    except Exception as e:                      # gh missing, no internet, a bad report file
        return f"{head}\n\n- SKIPPED: {type(e).__name__}: {e}. Reports stay queued."


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Report what landed on the CSI shares since the last check.")
    ap.add_argument("--period", action="append", default=None,
                    help="YYYY.MM to watch (repeatable; default: this month and last)")
    ap.add_argument("--notify", action="store_true",
                    help="Windows toast when there is news or the shares are unreachable")
    ap.add_argument("--dry-run", action="store_true",
                    help="report only; do not save the inventory, log or report")
    ap.add_argument("--no-inputs", action="store_true",
                    help="skip the Inputs-copy comparison")
    ap.add_argument("--copy", action="store_true",
                    help="copy what Inputs/ lacks into it: ODD extracts, DCOs and "
                         "workbooks for every client on the shares except stopped ones "
                         "(copy-only; newest month only)")
    ap.add_argument("--prune", action="store_true",
                    help="delete inputs that a newer period / weekly of the same "
                         "client and kind supersedes (the newest is always kept)")
    ap.add_argument("--mail", action="store_true",
                    help="also take MRPC/CashPlease reports and ICS workbooks from "
                         "the two senders that email them (scripts/mail_sources.py)")
    ap.add_argument("--ics-referrals", action="store_true",
                    help="merge ICS referral query results landed in Inputs/ICS Referrals and "
                         "point the query at referrals since the last pull "
                         "(scripts/ics_referrals_pull.py)")
    ap.add_argument("--branch-names", action="store_true",
                    help="add branch names found in the Charts workbooks and the ICS referrals "
                         "pull to Inputs/Branch Names/branch_names.csv")
    ap.add_argument("--mail-days", type=int, default=None,
                    help="how far back to read the mailbox (default 30)")
    ap.add_argument("--issues", action="store_true",
                    help="file the issue reports CSM Sheila queued on the share, and refresh "
                         "the issue list its Reported tab reads (needs gh; this machine only)")
    ap.add_argument("--once-daily", action="store_true",
                    help="do nothing if a run already reached the shares today "
                         "(what the retry fires after the 08:00 one pass)")
    ap.add_argument("--check-stale", action="store_true",
                    help="report whether the daily watch has been running, and "
                         "exit non-zero if it has not; checks nothing else")
    ap.add_argument("--check-today", action="store_true",
                    help="exit 0 if a run reached the shares TODAY, 1 if not; checks "
                         "nothing else (what the watchdog asks before it intervenes)")
    a = ap.parse_args(argv)
    # A cp1252 console must not kill a scheduled run over an em dash.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    # Asks only "has this watch been running?", so it comes before everything
    # that touches a share — it has to answer on a machine that is off the VPN.
    if a.check_stale:
        state, detail = run_health()
        print("source watch: %s — %s" % (state, detail))
        return 0 if state == "ok" else 1

    # The watchdog's question (Aaron, 2026-09-21). Report freshness cannot answer it: a report
    # written at 08:14 is fresh at 09:00 while the 09:00 fire sits suspended and the morning's
    # copy never happens. The run record can — it is stamped by the run itself, and only when
    # the share check got through.
    if a.check_today:
        done = completed_today()
        print("source watch reached the shares today: %s" % ("yes" if done else "no"))
        return 0 if done else 1

    periods = a.period or periods_to_watch()
    for p in periods:
        if not DS._period_ok(p):
            raise SystemExit("period must be YYYY.MM, got %r" % p)

    if a.once_daily and completed_today():
        print("source watch already reached the shares today; nothing to do.")
        return 0

    # Before the first share call, so a run that is killed part way leaves a
    # start with no finish rather than no trace at all. A dry run is not the
    # daily run and does not stamp one.
    if not a.dry_run:
        record_start(sys.argv[1:] if argv is None else list(argv))

    previous = read_state()
    result = check(periods, previous, use_drive=not a.no_inputs)
    roster = _roster()
    # The scan is saved HERE, before the copy and the steps after it: see save_report. The run
    # is recorded as finished with it (Aaron, 2026-09-21): "finished" means the share check got
    # through and wrote its report, which is exactly what has just happened; the copy and the
    # steps after it can still be killed without making the morning read as a run that never ran.
    if not a.dry_run:
        scan_text = render(result, roster)
        save_report(scan_text, result, log_text=scan_text)
        record_finish("reachable" if result["reachable"] else "unreachable")
    if a.copy and result["reachable"] and not a.no_inputs:
        plan = copy_plan(result["inventory"], set(roster), _inputs_dir(),
                         stopped=_roster_stopped())
        if a.dry_run:
            result["copy_plan"] = plan
        else:
            result["copies"] = apply_copies(plan)
    if a.prune and not a.no_inputs and _inputs_dir():
        # Across every kind folder, not one: a client's ARS workbook and the DCO
        # it supersedes now live apart, and prune compares them by name.
        inputs_dir = _inputs_dir()
        where = {}
        for d in _report_dirs(inputs_dir) + _prune_also_dirs(inputs_dir):
            try:
                for nm in os.listdir(d):
                    where.setdefault(nm, os.path.join(d, nm))
            except OSError:
                continue
        plan = prune_plan(sorted(where))
        if a.dry_run:
            result["prune_plan"] = plan
        else:
            result["pruned"] = apply_prune(
                os.path.join(inputs_dir, R.LEGACY_REPORTS_DIRNAME), plan,
                locate=lambda nm: where.get(
                    nm, os.path.join(inputs_dir, R.LEGACY_REPORTS_DIRNAME, nm)))
    # The ICS referrals list (Aaron, 2026-09-17): a person runs the query, so this
    # merges whatever result landed since the last check and rewrites the query to
    # start at the newest referral merged. Reported, never fatal.
    if a.ics_referrals and not a.no_inputs and _inputs_dir():
        import ics_referrals_pull
        result["ics_referrals"] = ics_referrals_pull.run(dry_run=a.dry_run)
    # Branch names (Aaron, 2026-09-17), after the referrals merge so a new pull's names count.
    if a.branch_names and not a.no_inputs and _inputs_dir():
        import branch_names
        result["branch_names"] = branch_names.morning_update(dry_run=a.dry_run)
    # The inputs that arrive by EMAIL, not on a share: MRPC and CashPlease
    # reports from Bradford, ICS workbooks from Matt (Aaron, 2026-09-09). A
    # mailbox that cannot be reached is reported and skipped — it must not fail
    # the share check, which is the part that runs every day regardless.
    text = render(result, roster)
    line = summary_line(result, roster)
    print(text)
    print()
    print(line)

    # The share results are saved BEFORE the mail step. On 2026-09-09 and -10 the
    # 08:00 run hung inside Outlook COM for the full 30 minutes and the scheduler
    # killed it; the share check had finished in under a minute and every one of
    # its findings died with the process, unwritten.
    if not a.dry_run:
        # The report is rewritten whole; the LOG gets only what the steps added, since the scan
        # went in above.
        steps = "\n".join(_copies_section(result)).strip()
        save_report(text, result, log_text=steps or None)

    mail_text = ""
    if a.mail:
        mail_text, result["mail_saved"] = mail_step(a.mail_days, a.dry_run)
        print()
        print(mail_text)
        if not a.dry_run:
            art = R.build_artifacts()
            with open(str(art / LOG_NAME), "a", encoding="utf-8") as fh:
                fh.write(mail_text + "\n\n---\n\n")
            with open(str(art / REPORT_NAME), "a", encoding="utf-8") as fh:
                fh.write("\n" + mail_text + "\n")

    # Sheila's queued issue reports (Aaron, 2026-10-05). With the mail step and for the
    # same reason: it reaches off this machine, and a slow or broken network must not take
    # the share check's findings with it — they are already saved above. Reported, never
    # fatal: a morning with no gh, or no internet, leaves the reports queued for tomorrow,
    # which is exactly what queueing them is for.
    if a.issues:
        issues_text = issues_step(a.dry_run)
        print()
        print(issues_text)
        if not a.dry_run:
            art = R.build_artifacts()
            with open(str(art / LOG_NAME), "a", encoding="utf-8") as fh:
                fh.write(issues_text + "\n\n---\n\n")
            with open(str(art / REPORT_NAME), "a", encoding="utf-8") as fh:
                fh.write("\n" + issues_text + "\n")

    if a.notify and (not result["reachable"] or result["new"]
                     or result["changed"] or result["gone"]):
        notify("RPE source check", line)

    return 2 if not result["reachable"] else 0


if __name__ == "__main__":
    sys.exit(main())
