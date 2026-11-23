"""The slide ledger and the portfolio row (fs-06)."""
import csv
import json

import pytest

import ti_build
from ti import chapters_txn as X
from ti import ledger, portfolio
from ti.deck import txn_layers as LAYERS


def _all_keep(tmp_path):
    p = tmp_path / "keep.json"
    p.write_text(json.dumps({"chapters": {}, "slides": {}}), encoding="utf-8")
    return p


# ---------------------------------------------------------------- ledger
def test_every_builder_has_exactly_one_line():
    rows = ledger.rows()
    assert len(rows) == len(X.TI_BUILDERS) + len(X.COMP_BUILDERS) + len(LAYERS.BUILDERS)
    titles = [r[1] for r in rows]
    assert len(set(titles)) == len(titles)


def test_chapters_are_assigned():
    rows = ledger.rows()
    assert {r[0] for r in rows} == {"Transaction Intelligence", "Competition"}
    assert sum(r[0] == "Competition" for r in rows) == len(X.COMP_BUILDERS) + len(LAYERS.BUILDERS)


def test_statuses_are_the_four_and_each_has_a_reason_when_not_drawn():
    for chapter, title, status, reason in ledger.rows():
        assert status in {"drawn", "merged", "hidden", "tossed"}
        assert (status == "drawn") == (reason == "")


def test_a_slide_tossed_in_the_selection_file_is_tossed():
    rows = {r[1]: r for r in ledger.rows()}
    assert rows["How the money moves"][2] == "tossed"
    assert "slides.json" in rows["How the money moves"][3]


def test_all_keep_has_nothing_tossed(tmp_path):
    rows = ledger.rows(selection_path=_all_keep(tmp_path))
    assert not [r for r in rows if r[2] == "tossed"]


def test_a_declined_slide_is_hidden_with_its_reason(tmp_path):
    pack = {"hidden_declined": {"ars": [{"lens": "ars", "chapter": "Competition",
                                         "title": "Winback targets", "reason": "no figures"}]}}
    rows = {r[1]: r for r in ledger.rows(pack, selection_path=_all_keep(tmp_path))}
    assert rows["Winback targets"][2] == "hidden" and rows["Winback targets"][3] == "no figures"


def test_a_merged_pair_names_its_partner(tmp_path):
    rows = {r[1]: r for r in ledger.rows(selection_path=_all_keep(tmp_path))}
    r = rows["How long the relationship has run"]
    assert r[2] == "merged" and "Started and stopped" in r[3]


def test_nothing_goes_missing_without_a_line(tmp_path):
    rows = ledger.rows(selection_path=_all_keep(tmp_path))
    assert ledger.summary(rows).startswith(str(sum(r[2] == "drawn" for r in rows)))


def test_write_roundtrip(tmp_path):
    path = ledger.write(tmp_path / "x" / "ledger.csv", ledger.rows())
    with open(path, newline="", encoding="utf-8") as f:
        got = list(csv.reader(f))
    assert got[0] == ledger.COLUMNS and len(got) == len(ledger.rows()) + 1


# ---------------------------------------------------------------- portfolio
def _pack(client="1798", month="2026.10", any_pct=26.9):
    return {"client_id": client, "client_name": "FirstLight FCU", "data_month": month,
            "computed": "2026-11-16 10:00",
            "metrics": {"fin_definitions": {"base_accounts": 100,
                                            "any": {"accounts": 27, "pct": any_pct, "dollars": 9000},
                                            "addressable": {"accounts": 18, "pct": 18.0, "dollars": 6000},
                                            "adjacency": {"accounts": 40, "pct": 40.0, "dollars": 100}},
                        "fin_coverage": {"matched_rows_pct": 8.8, "matched_dollars_pct": 15.9,
                                         "review_queue_dollars": 1141469},
                        "fininst_named_accounts": 867}}


def test_row_carries_the_finserv_columns():
    r = portfolio.row(_pack())
    assert set(r) == set(portfolio.COLUMNS)
    assert r["fin_any_pct"] == 26.9 and r["fin_matched_dollars_pct"] == 15.9
    assert r["fin_named_depository_accounts"] == 867


def test_row_for_a_client_without_transactions_is_blank_not_an_error():
    r = portfolio.row({"client_id": "1100", "client_name": "X", "data_month": "2026.10", "metrics": {}})
    assert r["fin_any_pct"] is None and r["client_id"] == "1100"


def test_upsert_replaces_the_same_client_and_month(tmp_path):
    f = tmp_path / "p.csv"
    portfolio.upsert(f, portfolio.row(_pack(any_pct=26.9)))
    portfolio.upsert(f, portfolio.row(_pack(any_pct=30.0)))
    rows = list(csv.DictReader(open(f, encoding="utf-8")))
    assert len(rows) == 1 and rows[0]["fin_any_pct"] == "30.0"


def test_upsert_keeps_other_clients_and_months_in_order(tmp_path):
    f = tmp_path / "p.csv"
    portfolio.upsert(f, portfolio.row(_pack("1798", "2026.10")))
    portfolio.upsert(f, portfolio.row(_pack("1100", "2026.10")))
    portfolio.upsert(f, portfolio.row(_pack("1798", "2026.09")))
    rows = list(csv.DictReader(open(f, encoding="utf-8")))
    assert [(r["client_id"], r["data_month"]) for r in rows] == [
        ("1100", "2026.10"), ("1798", "2026.09"), ("1798", "2026.10")]


def test_upsert_keeps_columns_a_newer_build_added(tmp_path):
    f = tmp_path / "p.csv"
    f.write_text("client_id,client_name,data_month,computed,comp_with_competitor_pct\n"
                 "1100,X,2026.10,t,12.5\n", encoding="utf-8")
    portfolio.upsert(f, portfolio.row(_pack("1798", "2026.10")))
    rows = {r["client_id"]: r for r in csv.DictReader(open(f, encoding="utf-8"))}
    assert rows["1100"]["comp_with_competitor_pct"] == "12.5"
    assert "comp_with_competitor_pct" in rows["1798"]


def test_the_shared_table_is_only_used_when_named(monkeypatch):
    monkeypatch.delenv("RPE_TI_PORTFOLIO", raising=False)
    assert portfolio.shared_table() is None
    monkeypatch.setenv("RPE_TI_PORTFOLIO", r"X:\somewhere\p.csv")
    assert portfolio.shared_table() == r"X:\somewhere\p.csv"


# ---------------------------------------------------------------- the build hook
def test_the_build_writes_both_files_beside_the_decks(tmp_path, monkeypatch):
    monkeypatch.delenv("RPE_TI_PORTFOLIO", raising=False)
    ti_build.write_run_tables(_pack(), tmp_path)
    assert (tmp_path / "ti_slide_ledger.csv").is_file()
    assert (tmp_path / "ti_portfolio_row.csv").is_file()


def test_the_build_upserts_the_shared_table_only_when_named(tmp_path, monkeypatch):
    shared = tmp_path / "shared" / "p.csv"
    monkeypatch.setenv("RPE_TI_PORTFOLIO", str(shared))
    ti_build.write_run_tables(_pack(), tmp_path / "out")
    assert shared.is_file()


def test_a_failure_never_costs_the_decks(tmp_path, capsys):
    ti_build.write_run_tables({"client_id": "1798"}, tmp_path)         # no metrics, no month
    assert "not written" in capsys.readouterr().out or (tmp_path / "ti_slide_ledger.csv").is_file()


def test_the_layers_slides_are_in_the_ledger_with_their_status(tmp_path):
    """The ledger listed only the older competition slides, so 55 layers slides were drawn or declined with no line."""
    rows = {r[1]: r for r in ledger.rows(selection_path=_all_keep(tmp_path))}
    for b in LAYERS.BUILDERS:
        assert X.TITLES[b.__name__] in rows and rows[X.TITLES[b.__name__]][0] == "Competition"
    first = X.TITLES[LAYERS.BUILDERS[0].__name__]
    pack = {"hidden_declined": {"ars": [{"title": first, "reason": "no layered figures"}]}}
    got = {r[1]: r for r in ledger.rows(pack, selection_path=_all_keep(tmp_path))}
    assert got[first][2] == "hidden" and got[first][3] == "no layered figures"
