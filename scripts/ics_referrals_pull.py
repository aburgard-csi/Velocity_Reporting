"""The ICS referrals pull, kept current by the morning source check (Aaron, 2026-09-17).

"For the ICS query we need to pull that list periodically. Automatically update the query
during the morning file scan to only pull from the last scan to now, then dedup any overlap."

Claude cannot run the query (the referral database refuses Windows authentication), so the pull
stays a person running `scripts/sql/ics_referrals_all_clients.sql` in SQL Server Management Studio.
This module does the two halves around that run, each morning, from `watch_sources.py
--ics-referrals`:

1. **Merge.** Every result saved in `Inputs/ICS Referrals/` as `ics_referrals <YYYY-MM-DD>.csv`
   (the first result grid, with column headers) is folded into ONE file, `ics_referrals.csv`,
   oldest landing first. A referral is `client_id` + `primarydda` + `issue_date`; when a newer
   landing carries a referral already in the merged file, the newer landing's rows REPLACE the old
   ones for that referral, so an overlapping window never double-counts. Replacing by referral,
   not by row, matters: the query's branch join can return one referral on two rows (a branch
   number that two active branch records share), and a row-level dedup would keep both pulls'
   copies of those.
2. **Window.** The query is rewritten to `ICS Referrals - new since last pull.sql` beside the
   results with `@since` set to the day of the newest referral already merged. That day is
   pulled again on purpose, and step 1 removes the overlap. A morning whose query was not run
   does not move the start date, so a skipped day widens the next window instead of leaving a gap.

The merged file is the list; the dated landings are left where they are (nothing here deletes).
A landing whose header or column count is not the query's is reported and not merged: SSMS does
not quote fields, so a comma inside a name would shift every column after it.

Known limit of pulling only new referrals: an older referral's account, spend and balance columns
stay as of the pull that brought it in. A full pull (`@since = null`) refreshes them all; it
merges the same way.
"""
import csv
import datetime as _dt
import json
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "build"))
import rpe_env as R  # noqa: E402

KIND = "ICS referrals"
TEMPLATE = os.path.join(REPO, "scripts", "sql", "ics_referrals_all_clients.sql")
QUERY_NAME = "ICS Referrals - new since last pull.sql"
MERGED_NAME = "ics_referrals.csv"
STATE_NAME = "ics_referrals_pull.json"
COLUMNS = ["client_id", "client_name", "corporation_id", "primarydda", "issue_date",
           "branch_number", "branch_name", "account_found", "name1", "date_opened",
           "has_debitcard", "rege_response", "total_spend", "total_fees", "total_svcchg",
           "total_othchg", "total_nsf", "balance_period", "balance_average", "balance_current"]
KEY = tuple(COLUMNS.index(c) for c in ("client_id", "primarydda", "issue_date"))
_LANDING_RX = re.compile(r"^ics_referrals (\d{4}-\d{2}-\d{2})\b.*\.csv$", re.I)
_SINCE_RX = re.compile(r"^declare @since date = [^;]*;.*$", re.M)


class BadLanding(ValueError):
    """A result file that is not the query's first grid."""


def is_landing(name):
    return bool(_LANDING_RX.match(name))


def read_rows(path):
    """The rows of one result file, checked against the query's columns."""
    with open(path, newline="", encoding="utf-8-sig") as fh:
        r = csv.reader(fh)
        header = next(r, None)
        if header != COLUMNS:
            raise BadLanding("%s: header is not the ICS referrals query's first result "
                             "(save the first grid with column headers)" % os.path.basename(path))
        rows = []
        for n, row in enumerate(r, start=2):
            if not row:
                continue
            if len(row) != len(COLUMNS):
                raise BadLanding("%s line %d: %d fields, expected %d (a comma inside a value?)"
                                 % (os.path.basename(path), n, len(row), len(COLUMNS)))
            rows.append(tuple(row))
    return rows


def group(rows):
    """{referral key: [rows]} in first-seen order."""
    out = {}
    for row in rows:
        out.setdefault(tuple(row[i] for i in KEY), []).append(row)
    return out


def merge(merged, landing_rows):
    """Fold one landing into the merged referrals, in place. Returns (new, replaced) referral counts."""
    new = replaced = 0
    for key, rows in group(landing_rows).items():
        if key in merged:
            replaced += 1
        else:
            new += 1
        merged[key] = rows
    return new, replaced


def _sort_key(key):
    cid, dda, issued = key
    return (int(cid) if cid.isdigit() else sys.maxsize, cid, issued, dda)


def write_merged(path, merged):
    part = path + ".part"
    with open(part, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(COLUMNS)
        for key in sorted(merged, key=_sort_key):
            w.writerows(merged[key])
    os.replace(part, path)


def newest_issue(merged):
    """The latest issue_date in the merged referrals ('' when there are none)."""
    return max((k[2] for k in merged if k[2] and k[2] != "NULL"), default="")


def since_for(newest):
    """The query's start date: the day of the newest merged referral, or None for full history."""
    m = re.match(r"(\d{4}-\d{2}-\d{2})", newest or "")
    return m.group(1) if m else None


def render_query(template_text, since, now=None):
    """The template with @since set, and a header saying where the result goes."""
    now = now or _dt.datetime.now()
    value = "'%s'" % since if since else "null"
    line = ("declare @since date = %s;  -- written by the morning source check %s: the day of the "
            "newest referral already merged; that day is pulled again and the overlap is removed "
            "when the result is merged" % (value, now.strftime("%Y-%m-%d %H:%M")))
    if not _SINCE_RX.search(template_text):
        raise ValueError("the query template has no 'declare @since date = ...;' line")
    body = _SINCE_RX.sub(lambda _m: line, template_text, count=1)
    head = ("/*  RUN THIS, then save the FIRST result grid (with column headers) as\n"
            "        Inputs\\ICS Referrals\\ics_referrals %s.csv\n"
            "    The next morning's source check merges it into ics_referrals.csv and moves @since on.\n"
            "    Pulls referrals issued %s.\n*/\n"
            % (now.strftime("%Y-%m-%d"), "on or after " + since if since else "at any time (full history)"))
    return head + body


def _state_path():
    return str(R.build_artifacts() / STATE_NAME)


def read_state(path=None):
    path = path or _state_path()
    if not os.path.exists(path):
        return {"files": {}}
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def write_state(doc, path=None):
    path = path or _state_path()
    part = path + ".part"
    with open(part, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2)
    os.replace(part, path)


def _stamp(path):
    st = os.stat(path)
    return [st.st_size, int(st.st_mtime)]


def run(folder=None, dry_run=False, state_path=None, template=TEMPLATE, now=None):
    """Merge new landings and rewrite the query. Returns report lines; never raises."""
    head = ["", "## ICS referrals query", ""]
    try:
        now = now or _dt.datetime.now()
        folder = str(folder or R.input_dir(KIND))
        state = read_state(state_path)
        seen = state.get("files", {})
        merged_path = os.path.join(folder, MERGED_NAME)
        merged = group(read_rows(merged_path)) if os.path.exists(merged_path) else {}
        pending = sorted((os.path.join(folder, n) for n in os.listdir(folder)
                          if is_landing(n) and seen.get(n) != _stamp(os.path.join(folder, n))),
                         key=os.path.getmtime)
        lines, changed = [], False
        for path in pending:
            name = os.path.basename(path)
            try:
                rows = read_rows(path)
            except BadLanding as e:
                lines.append("- NOT merged: %s" % e)
                continue
            new, replaced = merge(merged, rows)
            seen[name] = _stamp(path)
            changed = True
            lines.append("- merged `%s`: %d rows, %d new referrals, %d already merged (replaced)"
                         % (name, len(rows), new, replaced))
        newest = newest_issue(merged)
        since = since_for(newest)
        with open(template, encoding="utf-8") as fh:
            text = render_query(fh.read(), since, now)
        if not dry_run:
            if changed:
                write_merged(merged_path, merged)
            query_path = os.path.join(folder, QUERY_NAME)
            with open(query_path + ".part", "w", encoding="utf-8") as fh:
                fh.write(text)
            os.replace(query_path + ".part", query_path)
            state.update(files=seen, newest_issue=newest, query_since=since,
                         updated=now.strftime("%Y-%m-%d %H:%M"))
            write_state(state, state_path)
        summary = "%d referrals in `%s`, newest issued %s." % (len(merged), MERGED_NAME, newest or "never")
        query = "- `%s` %s: referrals issued %s" % (
            QUERY_NAME, "would be written" if dry_run else "written",
            "on or after " + since if since else "at any time (no pull merged yet)")
        return head + [summary, ""] + (lines or ["- no new result files"]) + [query]
    except Exception as e:  # a failed merge must not fail the share check
        return head + ["- FAILED: %s: %s" % (type(e).__name__, e)]


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--dry-run", action="store_true", help="report only; write nothing")
    a = ap.parse_args(argv)
    print("\n".join(run(dry_run=a.dry_run)).strip())
    return 0


if __name__ == "__main__":
    sys.exit(main())
