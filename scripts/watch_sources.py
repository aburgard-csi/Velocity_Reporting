#!/usr/bin/env python3
"""
watch_sources.py — what the data team landed on the CSI shares since last time.

The monthly inputs arrive on two shares, on nobody's schedule:

    \\\\PADMIS105\\Velocity_company\\Aburgard\\ODDD\\<YYYY.MM Mon>\\<id>_ODDD.zip
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
whether the Drive copy the builders read is already current. With `--copy` it
then copies roster clients' files that Drive lacks into `Inputs/` (Aaron,
2026-09-08), the ODD extract only from the newest month on the share — see
`copy_plan` for why that rule exists. With `--prune` it deletes Drive inputs that
a newer period or weekly of the same client and kind supersedes (Aaron,
2026-09-08); the newest is always kept and a file with no newer version is never
touched — see `prune_plan`.

State and reports live in `Build Artifacts/` on Drive (bookkeeping, not a
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
    python scripts/watch_sources.py --copy         # + copy roster clients' files to Drive
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
    return DS._reachable(SRC_ODDD) and DS._reachable(SRC_REPORTS)


def scan(periods):
    """{key: record} for every file on either share in the given periods."""
    found = {}
    for p in periods:
        for month in glob.glob(os.path.join(SRC_ODDD, p + "*")):
            if not os.path.isdir(month):
                continue
            for f in glob.glob(os.path.join(month, "*")):
                if os.path.isfile(f):
                    rec = classify(f, "oddd")
                    if rec:
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


# ------------------------------------------------------------------ drive
def drive_state(rec, inputs_dir):
    """Is the copy the builders read already this file?

    Same size means the same landing for these files (the rule deck_status
    already uses for the ODD extracts). A different size means Drive holds an
    earlier landing of the same name — which for the ODD extract, overwritten
    in place as `<id>_ODDD.zip`, usually means last month's.
    """
    if inputs_dir is None:
        return "unknown"
    if rec["kind"] == ODDD:
        cand = os.path.join(inputs_dir, "ODDD", rec["client"] + "_ODDD.zip")
    else:
        cand = os.path.join(inputs_dir, "ARS & MRPC Reports", rec["name"])
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
def _dest_for(rec, inputs_dir):
    if rec["kind"] == ODDD:
        return os.path.join(inputs_dir, "ODDD", rec["client"] + "_ODDD.zip")
    return os.path.join(inputs_dir, "ARS & MRPC Reports", rec["name"])


def copy_plan(inventory, roster_ids, inputs_dir):
    """Which source files should be copied to Drive: [(record, destination)].

    Roster clients only — the shares carry every account manager's clients, and
    a file on Drive for a client nobody builds is clutter at best. Only files
    Drive does not hold, or holds a different landing of (`differs`).

    The ODD extract needs one more rule. It lives on Drive as `<id>_ODDD.zip`
    with no period in the name, and the watch scans two months, so last month's
    extract at source ALWAYS "differs" from Drive once this month's has been
    copied. Only the newest month on the share per client is ever a candidate;
    copying an older one back over a newer one is the stale-ODD failure this
    pipeline keeps guarding against, and this is where it would happen.
    """
    if inputs_dir is None:
        return []
    # Newest period on the share per (client, kind). The same rule for every
    # kind, not only the ODD: with --prune removing what a newer period
    # supersedes, copying last month's DCO back would have it deleted again the
    # same run, every day.
    newest = {}
    for rec in inventory.values():
        if rec["kind"] != OTHER and rec["client"] in roster_ids and rec.get("period"):
            k = (rec["client"], rec["kind"])
            if k not in newest or rec["period"] > newest[k]["period"]:
                newest[k] = rec
    on_drive = _drive_periods(inputs_dir)
    plan = []
    for rec in sorted(inventory.values(), key=lambda r: (r["kind"], r["client"] or "", r["name"])):
        if rec["kind"] == OTHER or rec["client"] not in roster_ids:
            continue
        if newest.get((rec["client"], rec["kind"])) is not rec:
            continue
        if rec["kind"] != ODDD and on_drive.get((rec["client"], rec["kind"]), "") > rec["period"]:
            continue                       # Drive already holds a newer period
        if rec.get("drive") not in ("not copied", "differs"):
            continue
        dest = _dest_for(rec, inputs_dir)
        if rec.get("drive") == "differs" and not _source_is_newer(rec, dest):
            # Same name, different bytes, and the Drive copy is the more recent
            # write: that is a Drive copy someone changed on purpose — a workbook
            # opened and saved in Excel so its formulas carry values — not a
            # re-landing. Overwriting it hands the builders the uncalculated
            # original; it did exactly that to 1539's 2026.08 workbook on
            # 2026-09-08 (every ARS figure read 0 afterwards).
            continue
        plan.append((rec, dest))
    return plan


def _drive_periods(inputs_dir):
    """{(client, kind): newest period} for the period-stamped files on Drive."""
    out = {}
    try:
        names = os.listdir(os.path.join(inputs_dir, "ARS & MRPC Reports"))
    except OSError:
        return out
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
            rec["drive"] = "copied"
            out.append((rec, dest, "copied"))
        except OSError as e:
            out.append((rec, dest, "FAILED: %s" % e))
    return out


# ------------------------------------------------------------------ prune
_WEEKLY_RX = re.compile(r"(MRPCEnrollmentSummary|CashPleaseSummary)", re.I)
_STAMP_RX = re.compile(r"(\d{6}_\d{6})")


def _prune_group(name):
    """The group a Drive input belongs to, or None if it is never pruned.

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


def apply_prune(folder, plan):
    """Delete the superseded files. The newer file must exist and be non-empty
    at the moment of deletion, or the older one stays. Returns
    [(name, newer, outcome)], outcome "removed" or an error."""
    out = []
    for old, new in plan:
        op, np_ = os.path.join(folder, old), os.path.join(folder, new)
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


# ------------------------------------------------------------------ report
def _roster():
    try:
        active, _skipped = read_roster()
    except BaseException:
        return {}
    return {cid: name for cid, name, _mmsm, _progs in active}


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
    drive = rec.get("drive", "")
    drive_s = "" if not drive else "  · Drive: " + drive
    return "- **%s** %s%s — `%s`  %s, landed %s%s" % (
        rec["kind"], who, tag, rec["name"], _fmt_size(rec.get("size")),
        _fmt_when(rec.get("mtime")), drive_s)


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
            "Periods: %s  ·  ODDD: `%s`  ·  Reports: `%s`" % (
                ", ".join(r["periods"]), SRC_ODDD, SRC_REPORTS)]
    if not r["reachable"]:
        return "\n".join(head + [
            "", "**Shares not reachable (VPN?).** Nothing checked; the saved "
            "inventory from %s was left as it is." % (r.get("previous_checked") or "never")])
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
               if x["client"] in roster and x.get("drive") in ("not copied", "differs")]
    if to_copy:
        body += ["", "**%d of these are for roster clients and not yet current on Drive.**"
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
        out += ["", "## Copied to Drive (%d)" % len(ok) + (", %d FAILED" % len(bad) if bad else ""), ""]
        out += ["- **%s** %s — `%s` -> `%s`" % (r["kind"], r["client"], r["name"], d) for r, d, _ in ok]
        out += ["- **%s** %s — `%s` %s" % (r["kind"], r["client"], r["name"], o) for r, d, o in bad]
    elif planned:
        out += ["", "## Would copy to Drive (%d) — dry run" % len(planned), ""]
        out += ["- **%s** %s — `%s` -> `%s`" % (r["kind"], r["client"], r["name"], d) for r, d in planned]
    pruned, prune_planned = result.get("pruned") or [], result.get("prune_plan") or []
    if pruned:
        ok = [x for x in pruned if x[2] == "removed"]
        bad = [x for x in pruned if x[2] != "removed"]
        out += ["", "## Removed superseded inputs from Drive (%d)" % len(ok)
                + (", %d FAILED" % len(bad) if bad else ""), ""]
        out += ["- `%s` — superseded by `%s`" % (o, n) for o, n, _ in ok]
        out += ["- `%s` %s" % (o, r) for o, n, r in bad]
    elif prune_planned:
        out += ["", "## Would remove superseded inputs (%d) — dry run" % len(prune_planned), ""]
        out += ["- `%s` — superseded by `%s`" % (o, n) for o, n in prune_planned]
    return out


def summary_line(result, roster):
    """One line for the toast and the console."""
    if not result["reachable"]:
        return "Shares not reachable (VPN?) — nothing checked."
    copies = result.get("copies") or []
    copied = sum(1 for x in copies if x[2] == "copied")
    failed = len(copies) - copied
    tail = ""
    if copies:
        tail = " Copied %d to Drive." % copied + (" %d FAILED." % failed if failed else "")
    pruned = result.get("pruned") or []
    if pruned:
        removed = sum(1 for x in pruned if x[2] == "removed")
        tail += " Removed %d superseded." % removed + (
            " %d FAILED." % (len(pruned) - removed) if len(pruned) > removed else "")
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
        rec["drive"] = drive_state(rec, inputs_dir)
    result["inventory"] = current
    if previous is not None:
        result["new"], result["changed"], result["gone"] = diff(previous, current, periods)
    result["next_state"] = merge(previous, current, periods)
    return result


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Report what landed on the CSI shares since the last check.")
    ap.add_argument("--period", action="append", default=None,
                    help="YYYY.MM to watch (repeatable; default: this month and last)")
    ap.add_argument("--notify", action="store_true",
                    help="Windows toast when there is news or the shares are unreachable")
    ap.add_argument("--dry-run", action="store_true",
                    help="report only; do not save the inventory, log or report")
    ap.add_argument("--no-drive", action="store_true",
                    help="skip the Drive-copy comparison")
    ap.add_argument("--copy", action="store_true",
                    help="copy roster clients' files that Drive lacks into Inputs/ "
                         "(copy-only; the ODD extract only from the newest month)")
    ap.add_argument("--prune", action="store_true",
                    help="delete Drive inputs that a newer period / weekly of the same "
                         "client and kind supersedes (the newest is always kept)")
    a = ap.parse_args(argv)
    # A cp1252 console must not kill a scheduled run over an em dash.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    periods = a.period or periods_to_watch()
    for p in periods:
        if not DS._period_ok(p):
            raise SystemExit("period must be YYYY.MM, got %r" % p)

    previous = read_state()
    result = check(periods, previous, use_drive=not a.no_drive)
    roster = _roster()
    if a.copy and result["reachable"] and not a.no_drive:
        plan = copy_plan(result["inventory"], set(roster), _inputs_dir())
        if a.dry_run:
            result["copy_plan"] = plan
        else:
            result["copies"] = apply_copies(plan)
    if a.prune and not a.no_drive and _inputs_dir():
        folder = os.path.join(_inputs_dir(), "ARS & MRPC Reports")
        try:
            names = os.listdir(folder)
        except OSError:
            names = []
        plan = prune_plan(names)
        if a.dry_run:
            result["prune_plan"] = plan
        else:
            result["pruned"] = apply_prune(folder, plan)
    text = render(result, roster)
    line = summary_line(result, roster)
    print(text)
    print()
    print(line)

    if not a.dry_run:
        art = R.build_artifacts()
        with open(str(art / LOG_NAME), "a", encoding="utf-8") as fh:
            fh.write(text + "\n\n---\n\n")
        with open(str(art / REPORT_NAME), "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
        if result["reachable"]:
            write_state(result["next_state"])
            print("saved " + state_path())

    if a.notify and (not result["reachable"] or result["new"]
                     or result["changed"] or result["gone"]):
        notify("RPE source check", line)

    return 2 if not result["reachable"] else 0


if __name__ == "__main__":
    sys.exit(main())
