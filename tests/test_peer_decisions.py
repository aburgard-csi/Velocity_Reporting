"""Aaron's three peer-comparison decisions of 2026-11-24, each pinned on synthetic data (client ids 7001 and up).

1. "D: median, pooled internal": every client-facing CashPlease peer figure is the MEDIAN of the other current CashPlease
   clients (peer_compare over peer_pool.collect_cashplease), the How You Compare arithmetic; a rate's gap from the median
   is stated in percentage POINTS everywhere; the pooled book total stays on internal pages only, labelled "CashPlease
   book, pooled".
2. "Leave out of charge-off peers": a 0.0% charge-off on 500 or more loans is taken as not reported, and that client is
   left out of the charge-off comparison only, with the count and the reason said.
3. "A: use the deck's code": Sheila in Claude's ARS peer_compare is peer_compare.for_deck("ARS") at the client's newest
   build period, so it says what the deck says.
"""
import json
import os
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
for p in (REPO, REPO / "build", REPO / "build" / "cashplease_pipeline", REPO / "validation"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import cp_extract                                                 # noqa: E402
import peer_compare as PC                                         # noqa: E402
from review_page import peer_pool as PP                           # noqa: E402

GEN = "11/15/2026 6:00:00 AM"


# ----------------------------------------------------------------- synthetic CashPlease packs
def cp_pack(cid, loans=1000, charge_off=0.03, per_month=20, months=14, dda=10000, overdue=20, paid_off=800,
            principal_per_loan=500.0, interest_per_loan=30.0, name=None):
    """One client's pack as cp_extract writes it, with its metrics computed by cp_extract itself."""
    monthly = []
    for k in range(months):                                   # newest first: Oct 2026 back
        y, m = divmod(2026 * 12 + 9 - k, 12)
        monthly.append({"period": f"{y}-{m + 1:02d}-28", "period_month": f"{y}-{m + 1:02d}", "loans": per_month,
                        "principal": per_month * principal_per_loan, "interest": per_month * interest_per_loan,
                        "funded": 0, "paid_off": 0, "overdue": 0, "charged_off": 0})
    status = {k: {"loans": 0, "principal": 0.0, "interest": 0.0} for k in cp_extract.STATUSES}
    status["Overdue"]["loans"], status["Paid Off"]["loans"] = overdue, paid_off
    status["Charged Off"]["loans"], status["Funded"]["loans"] = int(loans * charge_off), 10
    pack = {"report_generated": GEN, "charge_off_pct": charge_off, "status": status, "monthly": monthly, "daily": [],
            "total": {"loans": loans, "principal": loans * principal_per_loan, "interest": loans * interest_per_loan},
            "pct_active_accounts_with_loans": 0.1, "monthly_in_progress": []}
    d = {"client_id": cid, "client_name": name or f"Synthetic Client {cid}", "sheet_name": f"{cid}-Synthetic",
         "source_file": "CashPleaseSummaryV1_test.xlsx", "dda_source": None, "dda_sent": "2026-11-01",
         "name_truncated": False, "cancelled": None, **pack,
         "metrics": cp_extract.client_metrics(pack, {"dda_accounts": dda, "last_updated": "2026-11-01"} if dda else None)}
    # the pooled rollup a pack still carries for the internal pages: deliberately odd so a leak onto a slide shows
    d["metrics"]["peer"] = {"cohort": "All Velocity CashPlease clients", "cohort_tabs": 76, "charge_off_pct": 0.0625,
                            "loans_per_1k_dda": 99.9, "avg_loan_size": 777.0, "avg_interest_per_loan": 77.0,
                            "pct_loans_paid_off": 0.777, "total_loans": 1, "cohort_dda_clients": 1}
    return d


def write_packs(root, packs):
    folder = Path(root) / "cashplease" / "packs"
    folder.mkdir(parents=True, exist_ok=True)
    for d in packs:
        (folder / f"{d['client_id']}_cashplease.json").write_text(json.dumps(d), encoding="utf-8")
    return folder


def peers(root, n=8, **kw):
    """n current peers 7101.. with charge-off 1%..n% and 20..(20+n) loans a month."""
    return write_packs(root, [cp_pack(str(7101 + i), charge_off=0.01 * (i + 1), per_month=20 + 2 * i, **kw) for i in range(n)])


# ----------------------------------------------------------------- decision 1: points for rates, everywhere
SPEC_PCT = {"key": "x", "label": "Charge-off rate", "fmt": "pct1", "higher": False}
SPEC_DEC = {"key": "y", "label": "Loans per 1,000 DDAs", "fmt": "dec1", "higher": True}


def test_a_rates_gap_is_stated_in_points_and_anything_else_in_percent():
    c = PC.compare_values(SPEC_PCT, 4.6, [3.0, 3.2, 3.4, 3.6, 3.8])
    assert c["diff_pts"] == pytest.approx(1.2)
    assert PC.relation_phrase(c, PC.formatter("pct1")) == "1.2 points above the peer median (3.4%)"
    assert "35.3%" not in PC.sentence(SPEC_PCT, c, "CashPlease")
    c = PC.compare_values(SPEC_DEC, 24.4, [10.0, 11.0, 12.2, 13.0, 14.0])
    assert c["diff_pts"] is None and PC.relation_phrase(c, PC.formatter("dec1")) == "100.0% above the peer median (12.2)"


def test_the_almost_flat_band_is_still_two_percent_of_the_median():
    c = PC.compare_values(SPEC_PCT, 3.45, [3.0, 3.2, 3.4, 3.6, 3.8])           # 1.5% of the median: flat
    assert PC.relation_phrase(c, PC.formatter("pct1")) == "almost flat against the peer median (3.4%)"
    c = PC.compare_values(SPEC_PCT, 0.53, [0.4, 0.45, 0.5, 0.55, 0.6])          # 6% of the median, a 0.03-point gap
    assert PC.relation_phrase(c, PC.formatter("pct1")) == "0.03 points above the peer median (0.5%)"


def test_a_zero_median_states_any_gap_in_points():
    c = PC.compare_values(SPEC_PCT, 0.4, [0.0, 0.0, 0.0, 0.0, 0.2])
    assert c["relation"] == "above" and PC.relation_phrase(c, PC.formatter("pct1")).startswith("0.4 points above")
    c = PC.compare_values(SPEC_PCT, 0.0, [0.0, 0.0, 0.0, 0.0, 0.2])
    assert c["relation"] == "flat"


# ----------------------------------------------------------------- decision 2: 0.0% on a large book is not reported
def test_a_zero_charge_off_on_a_large_book_is_left_out_of_charge_off_only(tmp_path):
    peers(tmp_path, n=6)
    write_packs(tmp_path, [cp_pack("7120", loans=PP.CP_ZERO_CHARGE_OFF_MIN_LOANS, charge_off=0.0, per_month=40),
                           cp_pack("7121", loans=PP.CP_ZERO_CHARGE_OFF_MIN_LOANS - 1, charge_off=0.0, per_month=40)])
    me = cp_pack("7001", charge_off=0.05)
    ev = PC.for_deck("CP", "7001", root=tmp_path, own={"cashplease": me})
    items = {it["spec"]["key"]: it for it in ev["items"]}
    assert ev["n_pool"] == 8
    assert items["charge_off"]["c"]["n"] == 7, "the 500-loan zero is out; the 499-loan zero is in, as reported"
    assert items["per_1k"]["c"]["n"] == 8 and items["overdue"]["c"]["n"] == 8, "still counted for every other measure"
    assert ev["excluded"] == {"charge_off": 1}
    note, = [n for n in items["charge_off"]["notes"] if "left out" in n]
    assert "1 other client left out" in note and "0.0%" in note and "not reported" in note
    assert not any("had no current data" in n for n in items["charge_off"]["notes"]), "the reason is not 'no data'"


def test_a_client_whose_own_zero_is_not_reported_is_told_so_not_ranked_first(tmp_path):
    peers(tmp_path, n=6)
    me = cp_pack("7001", loans=700, charge_off=0.0)
    ev = PC.for_deck("CP", "7001", root=tmp_path, own={"cashplease": me})
    assert "charge_off" not in {it["spec"]["key"] for it in ev["items"]}
    why, = [x for x in ev["left"] if x.startswith("Charge-off rate:")]
    assert "not compared" in why and "700 loans" in why and "not reported" in why
    import build_cp_gen as G
    me["_peer_eval"] = ev
    s = G.charge_off_sentence(me)
    assert "not compared with other clients" in s and "1st" not in s and "below" not in s


@pytest.mark.parametrize("own_zero", [False, True])
def test_live_reviews_cashplease_screen_states_the_exclusion_and_every_figure_traces(tmp_path, own_zero):
    """Live Review reads the same collector: the note naming the left-out clients must pass its tracer's audit."""
    from review_page import peers as LR
    from review_page.trace import Tracer, audit
    peers(tmp_path, n=6)
    write_packs(tmp_path, [cp_pack("7120", loans=900, charge_off=0.0)])
    me = cp_pack("7001", loans=1234 if own_zero else 1000, charge_off=0.0 if own_zero else 0.05)
    coll = PP.collect_cashplease(PP.PeerCtx(client="7001", root=tmp_path, own={"cashplease": me}))
    t = Tracer()
    scr = LR.peers_screen(t, "CashPlease", "CashPlease", coll, PP.CP_METRICS)
    text = " ".join(scr["notes"])
    if own_zero:            # the client's own charge-off is not compared, and the screen says why
        assert "Charge-off rate: not compared" in text and "1,234 loans booked" in text and "not reported" in text
    else:
        assert "1 other client left out of this comparison only" in text and "not reported" in text
    assert audit({"screens": [scr]}, t) == []


# ----------------------------------------------------------------- decision 1: the CashPlease deck reads the median
def _deck_slides(tmp_path, me):
    from pptx import Presentation
    import build_cp_gen as G
    prs = Presentation(str(REPO / "templates" / "cashplease_template.pptx"))
    me["_peer_eval"] = PC.for_deck("CP", me["client_id"], root=tmp_path / "ba", own={"cashplease": me})
    ov = G.slide_overview(prs, me, "PTD · test", str(tmp_path))
    pe = G.slide_peer(prs, me, "PTD · test", str(tmp_path))
    return prs, ov, pe


def _texts(slide):
    return " ".join(sh.text_frame.text for sh in slide.shapes if sh.has_text_frame)


def test_the_overview_and_peer_comparison_compare_with_the_median_not_the_pooled_rollup(tmp_path):
    peers(tmp_path / "ba", n=8)
    write_packs(tmp_path / "ba", [cp_pack("7130", loans=900, charge_off=0.0)])      # a not-reported zero among the peers
    me = cp_pack("7001", charge_off=0.08, per_month=40, name="Synthetic Federal Credit Union of the Long Name Valley")
    prs, ov, pe = _deck_slides(tmp_path, me)
    ev = me["_peer_eval"]
    per_1k = next(it for it in ev["items"] if it["spec"]["key"] == "per_1k")
    face = _texts(ov)
    assert f"median of {per_1k['c']['n']} other current CashPlease clients ({per_1k['c']['median']:.1f})" in face
    assert "points above the median of 8 other current CashPlease clients" in face      # charge-off: points, 8 of 9
    for pooled in ("99.9", "6.25%", "client average", "Cohort:", "All Clients Summary"):
        assert pooled not in face, pooled
    pface = _texts(pe)
    assert "Median client" in pface and "against the median current CashPlease client" in pface
    assert "Charge-off leaves out 1 client reading exactly 0.0% on 500+ loans" in pface
    for pooled in ("99.9", "$777", "77.7%", "Cohort"):
        assert pooled not in pface, pooled
    notes = pe.notes_slide.notes_text_frame.text
    assert "MEDIAN of the other current CashPlease clients" in notes and "rollup (a pooled book total) is not used" in notes
    assert "left out of this comparison only" in notes


def test_the_cashplease_peer_slides_pass_the_gate_rules_for_text(tmp_path):
    """The new sentences are longer than the old ones: the validator's claim, fit and collision rules must stay quiet."""
    import fit_layout
    import validate_deck as vd
    peers(tmp_path / "ba", n=8)
    me = cp_pack("7001", charge_off=0.012, per_month=9, name="Synthetic Bank and Trust Company")   # 31 characters, the longest the header box takes
    prs, _ov, _pe = _deck_slides(tmp_path, me)
    fit_layout.fit(prs)
    found = []
    for check in (vd.claim_consistency_findings, vd.single_line_overflow_findings, vd.text_collision_findings,
                  vd.geometry_findings, vd.text_rule_findings, vd.autofit_findings, vd.pill_wrap_findings):
        found += [f for f in check(prs) if f[0] == "FAIL"]
    assert found == [], found


def test_a_peer_comparison_with_too_few_peers_says_so_and_keeps_the_slide(tmp_path):
    peers(tmp_path / "ba", n=3)
    me = cp_pack("7001")
    _prs, ov, pe = _deck_slides(tmp_path, me)
    assert "CashPlease Peer Comparison" in _texts(pe)
    assert "No peer comparison is shown" in _texts(pe) and "No measure has 5 other current CashPlease clients" in _texts(pe)
    assert "It is not compared with other clients: fewer than 5 other current clients have a figure." in _texts(ov)


def test_the_deck_hands_the_how_you_compare_slides_the_same_evaluation():
    src = (REPO / "build" / "cashplease_pipeline" / "build_cp_gen.py").read_text(encoding="utf-8")
    assert "evaluation=peer_eval(d)" in src and "COHORT_NOTE" not in src and "against_peer" not in src


# ----------------------------------------------------------------- Sheila in Claude
@pytest.fixture
def sheila(tmp_path, monkeypatch):
    sys.path.insert(0, str(REPO))
    from sheila_mcp import core, reports
    ba = tmp_path / "Build Artifacts"
    ba.mkdir()
    monkeypatch.setattr(reports.R, "build_artifacts", lambda: ba)
    reports._cache.clear()
    monkeypatch.setattr(core, "find_client", lambda c: ({"id": str(c), "name": f"Synthetic Client {c}"}, None))
    monkeypatch.setattr(reports, "find_client", lambda c: ({"id": str(c), "name": f"Synthetic Client {c}"}, None))
    monkeypatch.setattr(reports, "label", lambda c: f"{c['id']} {c['name']}")
    return reports, ba


def test_sheilas_cashplease_report_gives_the_decks_median_and_the_portfolio_the_pooled_book(sheila):
    reports, ba = sheila
    peers(ba, n=8)
    me = cp_pack("7001", charge_off=0.08, per_month=40)
    write_packs(ba, [me])
    (ba / "cashplease" / "packs" / "index.json").write_text(json.dumps(
        {"source_file": "CashPleaseSummaryV1_test.xlsx", "report_generated": GEN,
         "clients": [{"client_id": str(7101 + i)} for i in range(8)] + [{"client_id": "7001"}], "flags": []}),
        encoding="utf-8")
    r = reports.cashplease_report("7001")
    ev = PC.for_deck("CP", "7001", root=ba)
    co = next(it for it in ev["items"] if it["spec"]["key"] == "charge_off")
    row = next(x for x in r["data"]["rows"] if x["measure"].startswith("Charge-off"))
    assert row["median"] == pytest.approx(co["c"]["median"] / 100) and row["rank"] == co["c"]["rank"]
    assert row["relation"] == PC.relation_phrase(co["c"], PC.formatter("pct1")) and "points above" in row["relation"]
    assert "99.9" not in r["answer"] and "All CP" not in r["answer"] and "Median" in r["answer"]
    p = reports.cashplease_portfolio()
    assert "CashPlease book, pooled (internal only" in p["answer"]
    assert p["data"]["book_pooled"]["cohort_clients"] == 9


def _ars_pack(ba, period, cid, rege, take, activity="Oct 2026"):
    d = ba / "launcher" / period / cid
    d.mkdir(parents=True)
    (d / "metrics.json").write_text(json.dumps({
        "activity_month": activity, "mail_summary": [["Mar26", 2000, 100, 0, 0, 5.0]],
        "rege_pct": rege, "rege_pool": 500, "overall_take": take, "n_eligible": 5000, "ret_1yr": 88.0,
        "n_open_personal": 5000}), encoding="utf-8")


def test_sheilas_ars_peer_compare_says_what_the_deck_says_at_the_clients_own_build_period(sheila):
    reports, ba = sheila
    _ars_pack(ba, "2026.10", "7001", 33.0, 86.0)
    for i in range(7):
        _ars_pack(ba, "2026.10", str(7201 + i), 25.0 + i, 80.0 + i)
    for i in range(3):                                            # three peers already rebuilt for the next month
        _ars_pack(ba, "2026.11", str(7201 + i), 60.0, 99.0, activity="Nov 2026")
    r = reports.peer_compare("7001")
    assert r["data"]["period"] == "2026.10", "no period asked: the client's own newest build, never 'today'"
    deck = PC.for_deck("ARS", "7001", period="2026.10", root=ba)
    want = {it["spec"]["key"]: it for it in deck["items"]}
    got = {x["kpi"]: x for x in r["data"]["rows"] if x["value"] is not None}
    assert set(got) == set(want) and {"rege_pct", "take_all", "ret_1yr"} <= set(got)
    for k, it in want.items():
        assert got[k]["sentence"] == it["sentence"] and it["sentence"] in r["answer"]
        assert (got[k]["rank"], got[k]["of"], got[k]["median"]) == (it["c"]["rank"], it["c"]["total"], it["c"]["median"])
    assert "points" in got["rege_pct"]["relation"] or "almost flat" in got["rege_pct"]["relation"]
    assert got["take_all"]["n"] == 7, "the client is not in its own pool"
    # measures the deck does not draw are said, not ranked
    assert any(x["kpi"] == "acct_growth" and x["value"] is None for x in r["data"]["rows"])
    # the old names still work; the retired ones and unknown ones are said
    assert [x["kpi"] for x in reports.peer_compare("7001", "debit_take, rege")["data"]["rows"]] == ["take_all", "rege_pct"]
    assert "not compared with other clients" in reports.peer_compare("7001", "retention_3yr")["answer"]
    assert "Unknown measure(s): reach" in reports.peer_compare("7001", "reach")["answer"]


def test_sheilas_ars_peer_compare_keeps_the_five_peer_minimum(sheila):
    reports, ba = sheila
    _ars_pack(ba, "2026.10", "7001", 33.0, 86.0)
    for i in range(4):
        _ars_pack(ba, "2026.10", str(7201 + i), 25.0 + i, 80.0 + i)
    r = reports.peer_compare("7001", "rege")
    row, = r["data"]["rows"]
    assert row["value"] is None and not r["data"]["quotable"]
    assert "not compared" in r["answer"] and "at least 5 other clients" in r["answer"]
