"""The ICS referrals pull: overlapping query windows merge without double counting, and the
query always starts at the newest referral already merged (Aaron, 2026-09-17).

Every row here is synthetic: invented client ids, hashed-looking account strings, no names.
"""
import csv
import datetime as dt
import importlib
import os
import sys

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
P = importlib.import_module("ics_referrals_pull")

NOW = dt.datetime(2026, 9, 18, 8, 0)


def row(cid, dda, issued, branch="Main", spend="0.00"):
    r = dict.fromkeys(P.COLUMNS, "NULL")
    r.update(client_id=str(cid), client_name="Test CU %s" % cid, primarydda=dda,
             issue_date=issued, branch_name=branch, account_found="Y", total_spend=spend)
    return [r[c] for c in P.COLUMNS]


def land(folder, name, rows, header=None, mtime=None):
    path = os.path.join(folder, name)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(header or P.COLUMNS)
        w.writerows(rows)
    if mtime:
        os.utime(path, (mtime, mtime))
    return path


def merged_rows(folder):
    with open(os.path.join(folder, P.MERGED_NAME), newline="", encoding="utf-8") as fh:
        return list(csv.reader(fh))[1:]


@pytest.fixture
def box(tmp_path):
    folder = tmp_path / "ICS Referrals"
    folder.mkdir()
    return str(folder), str(tmp_path / "state.json")


def test_overlapping_pulls_do_not_double_count(box):
    folder, state = box
    land(folder, "ics_referrals 2026-09-16.csv",
         [row(9001, "AAA", "2026-09-15 10:00:00.000"), row(9001, "BBB", "2026-09-16 09:00:00.000", spend="5.00")],
         mtime=1_000_000)
    P.run(folder, state_path=state, now=NOW)
    # The next pull starts on 2026-09-16, so BBB comes back (with newer spend) beside a new referral.
    land(folder, "ics_referrals 2026-09-17.csv",
         [row(9001, "BBB", "2026-09-16 09:00:00.000", spend="12.00"), row(9001, "CCC", "2026-09-17 11:00:00.000")],
         mtime=2_000_000)
    lines = P.run(folder, state_path=state, now=NOW)
    rows = merged_rows(folder)
    assert sorted(r[3] for r in rows) == ["AAA", "BBB", "CCC"]
    assert next(r for r in rows if r[3] == "BBB")[P.COLUMNS.index("total_spend")] == "12.00"
    assert any("1 new referrals, 1 already merged" in ln for ln in lines)


def test_one_referral_on_two_rows_is_replaced_whole(box):
    """The query's branch join can return one referral twice (two branch records share a number).
    A second pull replaces that referral's rows; it never stacks a second pair on the first."""
    folder, state = box
    pair = [row(9002, "DDD", "2026-09-10 08:00:00.000", branch="North"),
            row(9002, "DDD", "2026-09-10 08:00:00.000", branch="North Branch")]
    land(folder, "ics_referrals 2026-09-16.csv", pair, mtime=1_000_000)
    P.run(folder, state_path=state, now=NOW)
    land(folder, "ics_referrals 2026-09-17.csv", pair, mtime=2_000_000)
    P.run(folder, state_path=state, now=NOW)
    assert len(merged_rows(folder)) == 2


def test_the_query_starts_on_the_newest_merged_day(box, tmp_path):
    folder, state = box
    land(folder, "ics_referrals 2026-09-16.csv", [row(9001, "AAA", "2026-09-16 14:30:17.000")])
    lines = P.run(folder, state_path=state, now=NOW)
    text = open(os.path.join(folder, P.QUERY_NAME), encoding="utf-8").read()
    assert "declare @since date = '2026-09-16';" in text
    assert "ics_referrals 2026-09-18.csv" in text          # the save-as name for today's run
    assert text.count("declare @since date") == 1
    assert any("on or after 2026-09-16" in ln for ln in lines)


def test_a_skipped_day_does_not_move_the_start(box):
    folder, state = box
    land(folder, "ics_referrals 2026-09-16.csv", [row(9001, "AAA", "2026-09-16 14:30:17.000")])
    P.run(folder, state_path=state, now=NOW)
    for day in (19, 20, 21):                                 # nobody ran the query
        P.run(folder, state_path=state, now=NOW.replace(day=day))
    text = open(os.path.join(folder, P.QUERY_NAME), encoding="utf-8").read()
    assert "declare @since date = '2026-09-16';" in text


def test_no_pull_yet_means_full_history(box):
    folder, state = box
    P.run(folder, state_path=state, now=NOW)
    text = open(os.path.join(folder, P.QUERY_NAME), encoding="utf-8").read()
    assert "declare @since date = null;" in text


def test_a_landing_is_merged_once(box):
    folder, state = box
    land(folder, "ics_referrals 2026-09-16.csv", [row(9001, "AAA", "2026-09-16 10:00:00.000")])
    P.run(folder, state_path=state, now=NOW)
    lines = P.run(folder, state_path=state, now=NOW)
    assert "- no new result files" in lines


@pytest.mark.parametrize("bad, why", [
    ("header", "header is not"),
    ("comma", "fields, expected"),
])
def test_a_malformed_landing_is_reported_not_merged(box, bad, why):
    folder, state = box
    rows = [row(9001, "AAA", "2026-09-16 10:00:00.000")]
    if bad == "header":
        land(folder, "ics_referrals 2026-09-16.csv", rows, header=["client_id", "client_name"])
    else:
        rows[0][P.COLUMNS.index("name1")] = "Smith, Pat"      # SSMS does not quote
        path = os.path.join(folder, "ics_referrals 2026-09-16.csv")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(",".join(P.COLUMNS) + "\n" + ",".join(rows[0]) + "\n")
    lines = P.run(folder, state_path=state, now=NOW)
    assert any(ln.startswith("- NOT merged") and why in ln for ln in lines)
    assert not os.path.exists(os.path.join(folder, P.MERGED_NAME))


def test_summary_and_merged_files_are_not_landings():
    assert P.is_landing("ics_referrals 2026-09-16.csv")
    assert not P.is_landing("ics_referrals_summary 2026-09-16.csv")
    assert not P.is_landing(P.MERGED_NAME)


def test_the_template_carries_the_since_line():
    text = open(P.TEMPLATE, encoding="utf-8").read()
    assert P._SINCE_RX.search(text)
    assert "rv.issuedate >= @since" in text


def test_the_morning_task_runs_it():
    watch = open(os.path.join(REPO, "scripts", "watch_sources.py"), encoding="utf-8").read()
    task = open(os.path.join(REPO, "scripts", "register_watch_task.ps1"), encoding="utf-8").read()
    assert '"--ics-referrals"' in watch and "ics_referrals_pull.run(" in watch
    # the task's argument string is built into $TaskArgs (the retry fires were added 2026-09-21)
    assert "--ics-referrals" in next(l for l in task.splitlines() if l.strip().startswith("$TaskArgs ="))
