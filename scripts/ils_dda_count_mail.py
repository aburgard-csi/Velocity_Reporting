"""Save the newest "ILS Management Server DDA Count" email as the CashPlease DDA denominator.

Aaron, 2026-09-17: "Update the ILS DDA count from Charles's email with subject 'ILS Management
Server DDA Count'. Our CSI Email Monitor task can do this as part of its checks."

The ILS Hosted Server sends a fixed-width table every Thursday and Charles Baker forwards it.
`scripts/build_cashplease.py` reads the newest `Inputs/CashPlease/ILS-DDA-Count-<YYYY-MM-DD>.txt`
(the email body) through `build/cashplease_pipeline/dda_counts.py`. This takes the body from
Outlook over COM, word for word, so none of the ~280 counts is retyped: the Email Monitor's
Claude run reads mail through a read-only connector and would have to rewrite the table by
hand to save it, which is where a transposed digit gets in.

Run by `C:\\Data Pipelines\\Email Pipeline\\run-monitor.ps1` before its Claude step; safe to run
any time. Read-only in Outlook. Writes nothing unless the email parses to at least one client,
and never overwrites a saved week with different text (that is reported instead).

    python scripts/ils_dda_count_mail.py [--days 21] [--dry-run]

Exit 0 saved, already current, or no new email while a recent count is saved; 1 nothing usable found
or the saved count has gone stale; 2 Outlook unavailable.
"""
import argparse
import datetime as _dt
import html
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "build"))
sys.path.insert(0, os.path.join(REPO, "build", "cashplease_pipeline"))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import rpe_env as R  # noqa: E402
import dda_counts  # noqa: E402

SUBJECT = "ils management server dda count"
SENDERS = ("charles.baker@csiweb.com", "velocityalerts@csiweb.com")
KIND = "CP weekly"
SAVED_RE = re.compile(r"^ILS-DDA-Count-(\d{4}-\d{2}-\d{2})\.txt$")
# The email is weekly, so one skipped Thursday should not read as a failure: the search window is
# wide enough to still find the last one, a count older than LATE_DAYS is noted in the log, and only
# a gap long enough to leave the window is reported as a problem. Aaron, 2026-10-06: the 10/1 email
# never arrived and every run since logged an error against a saved count that was perfectly current.
LATE_DAYS = 10
STALE_DAYS = 14


def _age_days(datestr):
    """Whole days from a YYYY-MM-DD string to today, or None if it will not parse."""
    try:
        return (_dt.date.today() - _dt.date(*[int(p) for p in datestr.split("-")])).days
    except Exception:
        return None


def newest_saved(folder):
    """(date string, age in days) for the newest count already saved, or (None, None)."""
    try:
        names = os.listdir(str(folder))
    except Exception:
        return None, None
    dates = sorted(m.group(1) for m in (SAVED_RE.match(n) for n in names) if m)
    if not dates:
        return None, None
    return dates[-1], _age_days(dates[-1])


def _late_note(sent):
    """A note for the log when the newest count in the mailbox is older than a week."""
    age = _age_days(sent)
    if age is not None and age > LATE_DAYS:
        return "; nothing newer in %d days, so the Thursday email looks late" % age
    return ""


def report_no_email(days):
    """Nothing in the window: fine if a recent count is saved, a problem if it is stale."""
    missing = ("no '%s' email from %s in the last %d days"
               % ("ILS Management Server DDA Count", " or ".join(SENDERS), days))
    try:
        saved, age = newest_saved(R.input_dir(KIND))
    except Exception as exc:
        print("DDA count: %s (could not check what is saved: %s)" % (missing, exc))
        return 1
    if saved is None:
        print("DDA count: %s, and no count has ever been saved" % missing)
        return 1
    if age is None or age > STALE_DAYS:
        print("DDA count: STALE - newest saved count is %s (%s days old) and %s. The server sends "
              "this every Thursday, so check with Charles whether the job still runs."
              % (saved, age, missing))
        return 1
    print("DDA count: current through %s; %s" % (saved, missing))
    return 0


def pick(messages):
    """The newest (received, body) whose subject and sender match, or None."""
    best = None
    for received, subject, sender, body in messages:
        if SUBJECT not in (subject or "").lower() or (sender or "").lower() not in SENDERS:
            continue
        if best is None or received > best[0]:
            best = (received, body)
    return best


def plan(body, folder):
    """(path, parsed, action) for one email body; action is save | current | differs | unusable."""
    parsed = dda_counts.parse(html.unescape(body))
    if not parsed["clients"] or not parsed["sent"]:
        return None, parsed, "unusable"
    path = os.path.join(str(folder), "ILS-DDA-Count-%s.txt" % parsed["sent"])
    if os.path.exists(path):
        with open(path, encoding="utf-8", errors="replace") as fh:
            held = dda_counts.parse(html.unescape(fh.read()))
        # Compared as parsed tables: a body taken through Graph and the same body through COM
        # differ in line endings and entities ("&amp;") but carry the same counts.
        same = (held["clients"], held["null_counts"]) == (parsed["clients"], parsed["null_counts"])
        return path, parsed, "current" if same else "differs"
    return path, parsed, "save"


def _outlook_messages(days):
    import mail_sources as MS
    for m in MS._iter_messages(days):
        try:
            yield m.ReceivedTime, m.Subject, MS._smtp_of(m), m.Body
        except Exception:
            continue


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--days", type=int, default=21)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    import mail_sources as MS
    ok, why = MS.available()
    if not ok:
        print("DDA count: skipped, %s" % why)
        return 2
    try:
        hit = pick(_outlook_messages(a.days))
    finally:
        MS.close_if_launched()
    if hit is None:
        return report_no_email(a.days)
    folder = R.input_dir(KIND)
    path, parsed, action = plan(hit[1], folder)
    counts = "%d clients with a count, %d NULL" % (len(parsed["clients"]), len(parsed["null_counts"]))
    if action == "unusable":
        print("DDA count: the newest email did not parse to a table; nothing saved")
        return 1
    name = os.path.basename(path)
    if action == "current":
        print("DDA count: %s already saved (%s)%s" % (name, counts, _late_note(parsed["sent"])))
    elif action == "differs":
        print("DDA count: %s exists with different text; left as it is (%s)" % (name, counts))
    elif a.dry_run:
        print("DDA count: would save %s (%s)" % (name, counts))
    else:
        with open(path + ".part", "w", encoding="utf-8") as fh:
            fh.write(hit[1])
        os.replace(path + ".part", path)
        print("DDA count: saved %s (%s, sent %s)" % (name, counts, parsed["sent"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
