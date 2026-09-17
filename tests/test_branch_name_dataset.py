"""The branch-name dataset in Inputs/Branch Names (Aaron, 2026-09-17): "create a branch mapping
data set in inputs and update it when new branch names are discovered."

Synthetic clients and branches only.
"""
import csv
import os

import pytest

import branch_names as B

CLIENTS = [("9001", "Harbor FCU"), ("9002", "Harbor Credit Union"), ("9003", "Pine Bank"),
           ("9004", "Pine Valley Bank")]


@pytest.mark.parametrize("fname, want", [
    ("Harbor Federal CU ICS Charts 2026.xlsx", "9001"),        # federal cu = FCU
    ("Harbor Credit Union 2026 Charts.xlsx", "9002"),          # credit union = CU
    ("Pine Valley Bank Charts 2026.xlsx", "9004"),             # the whole-name fit with most words
    ("Z- Pine Bank Charts 2026 Ended.xlsx", None),             # ended client
    ("2026 Wrap up results.xlsx", None),
])
def test_a_charts_file_matches_one_client_or_none(fname, want):
    hit = B.match_charts_client(fname, CLIENTS)
    assert (hit[0] if hit else None) == want


def test_a_tie_is_not_guessed():
    assert B.match_charts_client("Harbor Charts 2026.xlsx", [("1", "Harbor"), ("2", "Harbor")]) is None


def obs(cid, num, name, src_file="f.xlsx"):
    return (cid, "Client %s" % cid, num, name, src_file)


def test_update_adds_new_names_and_keeps_history(tmp_path):
    path = str(tmp_path / "branch_names.csv")
    new = B.update_dataset([(B.SRC_CHARTS, [obs("9001", "1", "Main"), obs("9001", "2", "North")])],
                           path=path, today="2026-09-17")
    assert len(new) == 2
    # Next morning: branch 2 renamed in the Charts file, branch 3 appears via VIP.
    new = B.update_dataset([(B.SRC_CHARTS, [obs("9001", "1", "Main"), obs("9001", "2", "Northside")]),
                            (B.SRC_REFERRALS, [obs("9001", "3", "Digital")])],
                           path=path, today="2026-09-18")
    assert {(r["branch_number"], r["branch_name"]) for r in new} == {("2", "Northside"), ("3", "Digital")}
    rows = B.read_dataset(path)
    main = next(r for r in rows if r["branch_name"] == "Main")
    assert (main["first_seen"], main["last_seen"]) == ("2026-09-17", "2026-09-18")
    assert any(r["branch_name"] == "North" for r in rows)       # never removed
    with open(path, newline="", encoding="utf-8") as fh:
        assert next(csv.reader(fh)) == B.DATASET_COLUMNS


def rows(*items):
    return [dict(client_id=c, client_name="", branch_number=n, branch_name=nm, source=s,
                 source_file="", first_seen="", last_seen="") for c, n, nm, s in items]


def test_charts_name_wins_and_vip_fills_gaps():
    data = rows(("9001", "04", "Corporate", B.SRC_CHARTS), ("9001", "04", "Main Office", B.SRC_REFERRALS),
                ("9001", "12", "Cape Branch", B.SRC_REFERRALS), ("9002", "04", "Elsewhere", B.SRC_CHARTS))
    m = B.client_map("9001", rows=data)
    assert m["04"] == m["4"] == "Corporate"
    assert m["12"] == "Cape Branch"
    assert B.conflicts(data) == [("9001", "04", "Corporate", "Main Office")]


def test_two_names_from_one_source_are_left_unnamed_unless_only_a_suffix_differs():
    data = rows(("9001", "5", "Summerwood", B.SRC_REFERRALS), ("9001", "5", "Summerwood Branch", B.SRC_REFERRALS),
                ("9001", "6", "Jack", B.SRC_REFERRALS), ("9001", "6", "TestBranch", B.SRC_REFERRALS))
    m = B.client_map("9001", rows=data)
    assert m["5"] == "Summerwood"
    assert "6" not in m


def test_referral_observations_skip_nulls(tmp_path):
    p = tmp_path / "ics_referrals.csv"
    p.write_text("client_id,client_name,branch_number,branch_name\n"
                 "9001,Harbor FCU,07,Swansboro\n9001,Harbor FCU,07,Swansboro\n"
                 "9001,Harbor FCU,NULL,NULL\n9001,Harbor FCU,09,NULL\n", encoding="utf-8")
    assert B.referral_observations(str(p)) == [("9001", "Harbor FCU", "7", "Swansboro", "ics_referrals.csv")]


def test_the_morning_task_runs_it():
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    watch = open(os.path.join(repo, "scripts", "watch_sources.py"), encoding="utf-8").read()
    task = open(os.path.join(repo, "scripts", "register_watch_task.ps1"), encoding="utf-8").read()
    assert '"--branch-names"' in watch and "branch_names.morning_update(" in watch
    assert "--branch-names" in task.split("-Argument", 1)[1].split("\n", 1)[0]
