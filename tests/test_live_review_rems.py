"""Live Review's REMS (Reg E Management Solution) section: responses and opt-ins by month, and how the client compares.

Synthetic clients only: 9999 is the client; 7001-7009 are invented peers. The file is shaped like the result of
sql/rems_responses_report.sql: client_id, client_name, response_year, response_month, num_responses, num_opt_in, pct_opt_in.
"""
import csv
import json
import os
import sys

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(REPO, "scripts"), os.path.join(REPO, "build"), os.path.join(REPO, "build", "ars_pipeline"), os.path.join(REPO, "tests")]

from review_page import registry   # noqa: E402
from review_page import peer_pool  # noqa: E402

CID, PERIOD = "9999", "2026.10"
PEERS = [str(7000 + i) for i in range(1, 10)]
MONTHS = [(2026, m) for m in range(3, 11)]                      # Mar - Oct 2026; October is the month the file was pulled in


def write_rems(tmp_path, name="rems_responses_2026-10-30.csv", skip=(), client=True, peers=PEERS):
    d = tmp_path / "rems"
    d.mkdir(exist_ok=True)
    ids = ([CID] if client else []) + list(peers)
    with open(d / name, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["client_id", "client_name", "response_year", "response_month", "num_responses", "num_opt_in", "pct_opt_in"])
        for i, cid in enumerate(ids):
            for y, m in MONTHS:
                if (cid, m) in skip:
                    continue
                n = 200 + 10 * i + m
                o = round(n * (0.40 + 0.03 * i))
                w.writerow([cid, "Test Bank" if cid == CID else f"Zephyrville Peer {i} CU", y, m, n, o, o / n])


def build(tmp_path):
    return registry.build_model(CID, PERIOD, root=tmp_path, programs=["rems"])


def test_a_client_with_rems_rows_gets_a_summary_and_a_peer_screen(tmp_path):
    write_rems(tmp_path)
    model, _t, problems = build(tmp_path)
    assert problems == []
    rems = model["programs"][0]
    assert rems["key"] == "rems" and rems["state"] == "ready" and rems["label"] == "REMS"
    assert [s["id"] for s in rems["screens"]] == ["summary", "peers"]
    summary = rems["screens"][0]
    assert "Test Bank" in summary["headline"] and "Reg E Management Solution responses in Sep 2026" in summary["headline"]
    assert rems["client_name"] == "Test Bank"


def test_the_month_the_file_was_pulled_in_is_not_a_complete_month(tmp_path):
    write_rems(tmp_path)
    model, _t, _p = build(tmp_path)
    summary = model["programs"][0]["screens"][0]
    chart = next(b for b in summary["blocks"] if b["t"] == "drill")["chart"]
    assert chart["cats"][-1] == "Sep 26" and "Oct 26" not in chart["cats"]        # October is in progress


def test_the_peers_are_the_other_clients_in_the_file_and_are_numbered_not_named(tmp_path):
    write_rems(tmp_path)
    model, _t, problems = build(tmp_path)
    assert problems == []
    ps = next(s for s in model["programs"][0]["screens"] if s["id"] == "peers")

    def strips(bs):
        for b in bs:
            if b["t"] == "variants":
                for o in b["options"]:
                    yield from strips(o["blocks"])
            elif b["t"] == "peerstrip":
                yield b
    st = next(strips(ps["blocks"]))
    assert st["title"] == "Opt-in rate, last 12 months" and st["n"] == len(PEERS) == len(st["dots"]) == len(st["dot_ids"])
    assert set(st["dot_ids"]) == set(PEERS)
    assert "Zephyrville" not in json.dumps(model)                                # a peer's name never reaches the page


def test_a_client_not_in_the_file_has_no_rems_section(tmp_path):
    write_rems(tmp_path, client=False)
    model, _t, _p = build(tmp_path)
    rems = model["programs"][0]
    assert rems["state"] == "missing" and "no REMS responses" in rems["note"]


def test_without_the_file_it_says_what_to_run(tmp_path):
    model, _t, _p = build(tmp_path)
    rems = model["programs"][0]
    assert rems["state"] == "missing" and "Inputs/REMS" in rems["note"] and "sql/rems_responses_report.sql" in rems["fix"]


def test_the_headline_comparison_pools_twelve_complete_months_and_skips_the_demo_client(tmp_path):
    class Ctx:
        client = CID
        root = tmp_path
    d = tmp_path / "rems"
    d.mkdir()
    with open(d / "rems_responses 2026-11-03.csv", "w", newline="", encoding="utf-8") as f:     # a space in the name, as saved
        w = csv.writer(f)
        w.writerow(["client_id", "client_name", "response_year", "response_month", "num_responses", "num_opt_in", "pct_opt_in"])
        for m in range(11, 13):
            w.writerow(["7001", "A", 2025, m, 20, 10, 0.5])                                    # inside the 12 months
        for m in range(1, 11):
            w.writerow(["7001", "A", 2026, m, 20, 20, 1.0])
        w.writerow(["7001", "A", 2026, 11, 500, 0, 0.0])                                       # November is in progress: left out
        w.writerow(["7002", "B", 2026, 10, 12, 6, 0.5])                                        # 12 responses in the window: under the minimum
        w.writerow(["999", "Union Financial Bank", 2026, 10, 500, 400, 0.8])                   # the demo client
        w.writerow(["7003", "Old", 2023, 4, 900, 400, 0.44])                                   # no responses in the last six months
    coll = peer_pool.collect_rems(Ctx)
    ids = sorted(p["id"] for p in coll["peers"])
    assert ids == ["7001", "7002"]                                                             # not 999, not the lapsed client
    p1 = next(p for p in coll["peers"] if p["id"] == "7001")
    assert p1["point"]["pct_opt_in_12"] == pytest.approx(100.0 * (10 + 10 + 200) / 240)           # 2 months of 20 with 10 opted, 10 months of 20 all opted, over 240
    assert "pct_opt_in_12" not in next(p for p in coll["peers"] if p["id"] == "7002")["point"]


def test_a_small_month_is_left_out_of_the_rate_comparison(tmp_path):
    class Ctx:
        client = CID
        root = tmp_path
    d = tmp_path / "rems"
    d.mkdir()
    with open(d / "rems_responses_2026-10-30.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["client_id", "client_name", "response_year", "response_month", "num_responses", "num_opt_in", "pct_opt_in"])
        w.writerow(["7001", "A", 2026, 8, 4, 2, 0.5])          # 4 responses: too few for a rate
        w.writerow(["7001", "A", 2026, 9, 40, 20, 0.5])
    coll = peer_pool.collect_rems(Ctx)
    assert list(coll["peers"][0]["series"]["pct_opt_in"]) == ["Sep 2026"]


def test_the_rems_folder_is_a_known_input_kind():
    import rpe_env
    assert rpe_env.INPUT_KIND_DIRS["REMS"] == "REMS" and "REMS" in rpe_env.NOT_SCANNED_KINDS
