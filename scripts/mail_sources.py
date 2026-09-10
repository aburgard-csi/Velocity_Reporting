#!/usr/bin/env python3
"""
mail_sources.py — the inputs that arrive by EMAIL, not on the CSI shares.

Two kinds of file never land on `\\\\PADMIS105`:

  * **MRPC and CashPlease reports** from Bradford Sanders
  * **ICS workbooks** from Matt Milliman

`deck_status` has said "arrives by email / n/a" for the ICS workbook since
2026-08-31 because there was no source-side signal to wait on. There is one now:
the mailbox. This reads it and hands `watch_sources` the same kind of record the
share scan produces, so the copy, sort and report paths are shared.

**Read-only.** Messages are never marked read, moved, deleted or replied to;
attachments are saved out and nothing is written back to the mailbox.

**Outlook COM, not Graph** (Aaron, 2026-09-09). The scheduled task already runs
as the logged-on user, so the desktop profile is signed in and there is no app
registration, secret or consent flow to own. The cost is that Outlook must be
running when the task fires — `available()` says so plainly rather than the run
failing halfway.

Senders are matched on the resolved **SMTP address**, never the display name: a
display name is trivially spoofed and a forwarded message would otherwise pass.
Each sender may only supply the kinds listed for them, so an ICS workbook from
the MRPC sender is reported and skipped rather than filed.

Usage:
    python scripts/mail_sources.py [--days 30] [--save] [--inputs <dir>]

Without --save it lists what it would take. `watch_sources.py --mail` runs it as
part of the daily check.
"""
import argparse
import datetime as _dt
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                os.pardir, "build"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import rpe_env as R                                          # noqa: E402

# Kind names are watch_sources' vocabulary; imported lazily so this module can be
# unit-tested without the share paths existing.
MRPCPM, ICS_WB, WEEKLY, OTHER = "MRPCPM", "ICS workbook", "weekly", "other"

# Who may send what. An address here is the ONLY thing that admits a file.
SENDERS = {
    "bradford.sanders@csiweb.com": {MRPCPM, WEEKLY},
    "matt.milliman@csiweb.com": {ICS_WB},
}

WANTED_EXT = (".xlsx", ".xlsm")
DEFAULT_DAYS = 30

# Which folders to read, by name in the default store, plus their subfolders.
# The Inbox alone was not enough: a rule files these senders straight into
# Archive, so a 45-day Inbox scan found 35 messages, 123 attachments and neither
# sender (Aaron, 2026-09-09). Names are matched case-insensitively; a folder that
# does not exist is skipped rather than raising.
MAIL_FOLDERS = ("Inbox", "Archive")
MAX_FOLDER_DEPTH = 3

_WEEKLY_RX = re.compile(r"(MRPCEnrollmentSummary|CashPleaseSummary)", re.I)
_STAMP_RX = re.compile(r"(\d{6}_\d{6})")
_REPORT_RX = re.compile(r"^(\d{3,5})-(\d{4}\.\d{2})-(.+)$", re.I)


# ------------------------------------------------------------------ classify
def classify_attachment(name):
    """(kind, client, period) for an attachment filename.

    The same reading `watch_sources.classify` applies to a file on the share, plus
    the weekly families, whose names carry a stamp instead of an id and period.
    """
    if _WEEKLY_RX.search(name):
        return WEEKLY, None, None
    m = _REPORT_RX.match(name)
    if not m:
        return OTHER, None, None
    client, period, rest = m.group(1), m.group(2), m.group(3).lower()
    if "mrpcpm" in rest:
        return MRPCPM, client, period
    if "invitation checking" in rest:
        return ICS_WB, client, period
    return OTHER, client, period


# ------------------------------------------------------------------ outlook
def available():
    """(ok, reason). False means skip the mail step, not fail the run."""
    try:
        import win32com.client                                # noqa: F401
    except Exception as e:
        return False, "pywin32 not installed (%s)" % e
    try:
        _outlook()
        return True, "Outlook reachable"
    except Exception as e:
        return False, "Outlook is not running (%s)" % e


def _outlook():
    """The user's running Outlook if there is one, else a launched one.

    `GetActiveObject` attaches to the instance already running and fails at
    once when there is none — including while Outlook is still starting up,
    which is the state a `Dispatch` call blocks on with no timeout (the 08:00
    runs of 2026-09-09 and -10 hung there for their full 30 minutes). Only when
    nothing is running is `Dispatch` used to start a windowless instance for
    this process; it exits with the process. The caller runs this in a
    subprocess with a deadline, so even the launch path cannot hang a run.
    """
    global _APP, _LAUNCHED
    if _APP is not None:
        return _APP
    import pythoncom
    import win32com.client
    pythoncom.CoInitialize()
    try:
        _APP = win32com.client.GetActiveObject("Outlook.Application")
    except Exception:
        _APP = win32com.client.Dispatch("Outlook.Application")
        _LAUNCHED = True
    return _APP


_APP = None
_LAUNCHED = False


def close_if_launched():
    """Quit the Outlook this process started, and only that one. An instance
    the user had open is theirs and is left alone. A windowless instance left
    behind is what the user's next Outlook launch would attach to, window and
    all — tidier to end it with the scan."""
    global _APP, _LAUNCHED
    if _APP is not None and _LAUNCHED:
        try:
            _APP.Quit()
        except Exception:
            pass
    _APP, _LAUNCHED = None, False


def _smtp_of(msg):
    """The sender's real SMTP address.

    An Exchange sender's `SenderEmailAddress` is an X500 `/o=...` path, not an
    address, so matching on it alone silently accepts nobody. Resolve through the
    Exchange user, then fall back to the PR_SENT_REPRESENTING_SMTP_ADDRESS
    property, then to the raw field for plain SMTP senders.
    """
    try:
        if (msg.SenderEmailType or "").upper() == "EX":
            try:
                u = msg.Sender.GetExchangeUser()
                if u and u.PrimarySmtpAddress:
                    return u.PrimarySmtpAddress.lower()
            except Exception:
                pass
            try:
                return msg.PropertyAccessor.GetProperty(
                    "http://schemas.microsoft.com/mapi/proptag/0x5D01001F").lower()
            except Exception:
                pass
        return (msg.SenderEmailAddress or "").lower()
    except Exception:
        return ""


def _folders(ns):
    """The folders named in MAIL_FOLDERS, plus their subfolders."""
    out = []

    def walk(folder, depth):
        out.append(folder)
        if depth >= MAX_FOLDER_DEPTH:
            return
        try:
            for sub_ in folder.Folders:
                walk(sub_, depth + 1)
        except Exception:
            pass

    wanted = {n.lower() for n in MAIL_FOLDERS}
    try:
        store = ns.GetDefaultFolder(6).Parent                 # the mailbox root
    except Exception:
        return out
    try:
        for f in store.Folders:
            if (f.Name or "").lower() in wanted:
                walk(f, 0)
    except Exception:
        pass
    if not out:                                               # fall back to the Inbox
        try:
            out = [ns.GetDefaultFolder(6)]
        except Exception:
            pass
    return out


def _iter_messages(days, folders=None):
    """Messages from the last `days` across MAIL_FOLDERS. Yields COM items."""
    ns = _outlook().GetNamespace("MAPI")
    cutoff = _dt.datetime.now() - _dt.timedelta(days=days)
    for folder in (folders if folders is not None else _folders(ns)):
        try:
            items = folder.Items
            items.Sort("[ReceivedTime]", True)
        except Exception:
            continue
        # Restrict server-side where we can — Archive holds years of mail and
        # walking it item by item is minutes, not seconds.
        try:
            items = items.Restrict(
                "[ReceivedTime] >= '%s'" % cutoff.strftime("%m/%d/%Y %H:%M %p"))
        except Exception:
            pass
        for m in items:
            try:
                if m.Class != 43:                             # olMail
                    continue
            except Exception:
                continue
            yield m


def scan(days=DEFAULT_DAYS, messages=None):
    """[record] for every attachment worth taking.

    `messages` is an injection point for the tests: any iterable of objects with
    `.Attachments`, `.ReceivedTime`, `.Subject` and a resolvable sender.
    """
    out, seen = [], set()
    src = messages if messages is not None else _iter_messages(days)
    for m in src:
        smtp = m.smtp.lower() if hasattr(m, "smtp") else _smtp_of(m)
        allowed = SENDERS.get(smtp)
        if not allowed:
            continue
        try:
            received = m.ReceivedTime
            subject = m.Subject or ""
        except Exception:
            received, subject = None, ""
        for att in m.Attachments:
            name = getattr(att, "FileName", None) or getattr(att, "name", "")
            if not name.lower().endswith(WANTED_EXT) or name.startswith("~$"):
                continue
            kind, client, period = classify_attachment(name)
            rec = {"name": name, "kind": kind, "client": client, "period": period,
                   "sender": smtp, "subject": subject, "received": received,
                   "att": att,
                   "size": getattr(att, "Size", 0)}
            if kind == OTHER:
                # Checked BEFORE the sender rule: "not expected from Bradford" is
                # a misleading way to say "I could not read this filename".
                rec["skip"] = "filename does not match the <id>-<period>-<kind> convention"
            elif kind not in allowed:
                # Reported, not filed: an ICS workbook from the MRPC sender means
                # either a mis-send or a rule that needs widening, and silently
                # accepting it would make SENDERS decorative.
                rec["skip"] = ("kind %r not expected from %s" % (kind, smtp))
            # Newest message wins when the same attachment name appears twice.
            if name.lower() in seen:
                continue
            seen.add(name.lower())
            out.append(rec)
    return newest_only(out)


def _version_key(rec):
    """What makes two attachments versions of the same thing.

    ('weekly', family) for the weeklies, whose names carry a stamp instead of a
    client and period; (kind, client) for everything else.
    """
    if rec["kind"] == WEEKLY:
        m = _WEEKLY_RX.search(rec["name"])
        return (WEEKLY, m.group(1).lower() if m else rec["name"].lower())
    return (rec["kind"], rec["client"])


def _version_of(rec):
    """The comparable version within a group: the period, or the weekly stamp."""
    if rec["kind"] == WEEKLY:
        m = _STAMP_RX.search(rec["name"])
        return m.group(1) if m else ""
    return rec["period"] or ""


def newest_only(records):
    """Just the newest of each thing, the same rule the share copier applies.

    A mailbox holds every weekly ever sent: a 120-day scan turned up twenty
    MRPCEnrollmentSummary and CashPleaseSummary files, of which the pipeline
    reads exactly one — the newest — and `--prune` would delete the other
    nineteen the same run (Aaron, 2026-09-09). Copying to immediately delete is
    churn, and on the ICS side it would have pulled 2026.05 workbooks in on top
    of the 2026.07 ones already held.

    Records that could not be classified are all kept: they are reported, not
    filed, and there is no version to compare.
    """
    best = {}
    keep_all = []
    for rec in records:
        if rec.get("skip") or rec["kind"] == OTHER:
            keep_all.append(rec)
            continue
        k = _version_key(rec)
        if k not in best or _version_of(rec) > _version_of(best[k]):
            best[k] = rec
    return list(best.values()) + keep_all


# ------------------------------------------------------------------ save
def destination(rec, inputs_dir=None):
    """Where the attachment belongs — the same per-kind folders the share copier
    uses. An unrecognised name parks in the legacy folder (Aaron, 2026-09-09):
    reported and kept, never dropped and never guessed at."""
    I = inputs_dir or R.inputs()
    if rec.get("skip") or rec["kind"] == OTHER:
        d = os.path.join(str(I), R.LEGACY_REPORTS_DIRNAME)
    else:
        d = str(R.input_dir(rec["kind"], create=False))
        if inputs_dir:
            d = os.path.join(str(inputs_dir), R.INPUT_KIND_DIRS[rec["kind"]])
    return os.path.join(d, rec["name"])


def plan(records, inputs_dir=None):
    """[(record, destination, reason)] — reason None means "save it"."""
    out = []
    for rec in records:
        dest = destination(rec, inputs_dir)
        if rec.get("skip"):
            out.append((rec, dest, rec["skip"]))
            continue
        held = _held_version(rec, inputs_dir)
        if held and held > _version_of(rec):
            out.append((rec, dest, "Inputs/ already holds a newer one (%s)" % held))
            continue
        if os.path.exists(dest):
            # Same guard as the share copier: a local file written AFTER the mail
            # arrived is a deliberate change — a workbook opened and recalculated
            # in Excel so its formulas carry values — and must not be clobbered.
            try:
                local = _dt.datetime.fromtimestamp(os.path.getmtime(dest))
                recv = rec.get("received")
                if recv is not None and local > _to_naive(recv):
                    out.append((rec, dest, "already held, and the local copy is newer"))
                    continue
            except Exception:
                pass
            if os.path.getsize(dest) == rec.get("size", -1):
                out.append((rec, dest, "already held"))
                continue
        out.append((rec, dest, None))
    return out


def _held_version(rec, inputs_dir=None):
    """The newest version of this thing already in Inputs/, or ''."""
    if rec.get("skip") or rec["kind"] == OTHER:
        return ""
    try:
        d = os.path.dirname(destination(rec, inputs_dir))
        names = os.listdir(d)
    except OSError:
        return ""
    key = _version_key(rec)
    best = ""
    for nm in names:
        other = {"name": nm, "kind": rec["kind"]}
        k2, _c, p2 = classify_attachment(nm)
        other["kind"], other["client"], other["period"] = k2, _c, p2
        if _version_key(other) != key:
            continue
        v = _version_of(other)
        if v > best:
            best = v
    return best


def _to_naive(dtv):
    try:
        return _dt.datetime(dtv.year, dtv.month, dtv.day, dtv.hour,
                            dtv.minute, dtv.second)
    except Exception:
        return _dt.datetime.now()


def save(planned):
    """Write the attachments whose reason is None. [(name, dest, outcome)]."""
    out = []
    for rec, dest, reason in planned:
        if reason:
            out.append((rec["name"], dest, "skipped: " + reason))
            continue
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        tmp = dest + ".part"
        try:
            rec["att"].SaveAsFile(tmp)
            if os.path.getsize(tmp) == 0:
                raise OSError("saved 0 bytes")
            os.replace(tmp, dest)
            out.append((rec["name"], dest, "saved"))
        except Exception as e:
            if os.path.exists(tmp):
                try:
                    os.remove(tmp)
                except OSError:
                    pass
            out.append((rec["name"], dest, "FAILED: %s" % e))
    return out


# ------------------------------------------------------------------ report
def render(planned, ok_reason="Outlook reachable"):
    lines = []
    take = [p for p in planned if p[2] is None]
    skip = [p for p in planned if p[2]]
    lines.append("## From email (%d to take, %d skipped) — %s"
                 % (len(take), len(skip), ok_reason))
    lines.append("")
    for rec, dest, _ in take:
        lines.append("- **%s** %s — `%s` -> `%s`"
                     % (rec["kind"], rec.get("client") or "", rec["name"], dest))
    for rec, _dest, why in skip:
        lines.append("- ~~`%s`~~ — %s" % (rec["name"], why))
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=DEFAULT_DAYS)
    ap.add_argument("--save", action="store_true")
    ap.add_argument("--inputs", default=None)
    a = ap.parse_args(argv)

    ok, why = available()
    if not ok:
        print("mail step skipped: " + why)
        return 2
    try:
        recs = scan(a.days)
        planned = plan(recs, a.inputs)
        print(render(planned, why))
        if a.save:
            print()
            for name, dest, outcome in save(planned):
                print("  %-9s %s" % (outcome.split(":")[0], name))
        else:
            print("\ndry run — nothing saved. Re-run with --save")
    finally:
        close_if_launched()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
