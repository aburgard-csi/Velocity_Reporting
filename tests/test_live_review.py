"""The live review page (prototype, 2026-11-02): what it shows traces to the data pack, a month the deck
would leave out is left out here, and the server answers only the caller that has the page's token.

Every pack here is synthetic (an invented client 9999); nothing reads the share.
"""
import copy
import http.client
import json
import os
import sys
import threading

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(REPO, "scripts"), os.path.join(REPO, "build"), os.path.join(REPO, "build", "ars_pipeline")]

from review_page import registry                            # noqa: E402
from review_page import trace as TR                         # noqa: E402
from review_page.common import Ctx, interior_gaps, usable_series   # noqa: E402
from review_page.page import FONT_FILES, model_json, render_page   # noqa: E402
from review_page import packs as PK                         # noqa: E402

CID, PERIOD = "9999", "2026.10"


# ----------------------------------------------------------------- a synthetic pack
def _months(n, end_year, end_mon):
    names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    out, y, m = [], end_year, end_mon
    for _ in range(n):
        out.append((names[m - 1], y))
        m -= 1
        if m == 0:
            m, y = 12, y - 1
    return list(reversed(out))


def make_pack(root, nsf_gap=True):
    """Write launcher/2026.10/9999/{metrics,base,lift}.json and oddd/oddd_metrics.json under `root`."""
    d = root / "launcher" / PERIOD / CID
    (d / "oddd").mkdir(parents=True)
    ms = _months(16, 2026, 9)
    ms_nsf = _months(24, 2026, 9)
    nsf = [[f"{m} {str(y)[2:]}", 1000 + 10 * i, 300 + i] for i, (m, y) in enumerate(ms_nsf)]
    if nsf_gap:
        nsf[-2] = [nsf[-2][0], 30, 12]          # a collapse in the middle, then recovery
    M = {
        "month_completeness": {"pull_date": "2026-10-02", "activity": {"complete": 24, "excluded": []}},
        "activity_month": "Sep 2026", "n_eligible": 5000, "w3_label": "Jul–Sep 2026",
        "overall_take": 80.5, "take_hist_pct": 80.5, "take_new_pct": 77.4, "take_new_total": 600, "take_new_cards": 464,
        "swipe_tier": [["No Debit Card", 500, 10, 2000, 5], ["1-5", 1500, 4000, 90000, 40], ["26+", 3000, 90000, 2500000, 300]],
        "swipe_tier_total": [5000, 94010, 2592000, 345],
        "take_branch": [["North", 120, 150, 80], ["South", 90, 100, 90], ["East", 30, 50, 60]],
        "take_branch_monthly": [["North", 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 120, 150, 80],
                                ["South", 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 90, 100, 90],
                                ["East", 1, 2, 3, 3, 3, 3, 3, 3, 3, 3, 3, 30, 50, 60]],
        "take_months": ["Nov", "Dec", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep"],
        "take_col_totals": [10, 13, 16, 18, 20, 22, 24, 26, 28, 30, 32],
        "rege_pool": 4000, "rege_in": 1200, "rege_out": 2800, "rege_no": 0, "rege_pct": 30.0,
        "rege_branch": [["North", 500, 1500, 33], ["South", 400, 1400, 29]],
        "rege_new_pool": 500, "rege_new_pct": 40.0, "rege_new_window": ["Oct 2025", "Sep 2026", 12],
        "rege_branch_table": [["North", 100, 150, 0, 250, 40], ["South", 90, 140, 0, 230, 39]],
        "rege_branch_table_total": [190, 290, 0, 480],
        "mail_summary": [["Aug 2026", 1000, 100, 2.0, 12.0, 10.0], ["Jun 2026", 1100, 99, 2.0, 10.0, 9.0]],
        "mail_summary_total": [2100, 199, 2.0, 11.0, 9.5], "mail_in_progress": [["Oct 2026", 900]],
        "latest_mailing": "Aug 2026", "latest_mailed": 1000, "latest_responders": 100, "latest_resprate": 10.0,
        "movement": [["First Response", 60], ["Improved", 20], ["Same", 10], ["Declined", 10]],
        "nsf_series": nsf,
    }
    rows = [[f"{m} {y}", 20000.0 + 100 * i, 8000.0] for i, (m, y) in enumerate(ms)]
    B = {
        "client": "Test Bank", "data_label": "September 2026 Data", "months": 16, "mailings": 8,
        "ltd_revenue": sum(r[1] for r in rows), "ltd_costs": -sum(r[2] for r in rows),
        "cur_revenue": rows[-1][1], "cur_costs": -8000.0, "cur_profit": rows[-1][1] - 8000.0,
        "ltd_profit": sum(r[1] - r[2] for r in rows), "profitability": 2.5,
        "monthly_rev_last12": [[r[0], r[1]] for r in rows[-12:]],
        "swipespend_36": [[r[0], 40.0 + i, 30000 + i] for i, r in enumerate(rows)],
        "actuals": {"available": True, "sheet": "Actuals MM", "months": rows,
                    "lines": [["Respondent Fee", [r[2] for r in rows]], ["Program Fee", [0.0] * len(rows)]],
                    "window": [rows[0][0], rows[-1][0]], "total_column": None},
    }
    L = {"matrix_cols": ["1-5", "6-10", "11-15"],
         "matrix_rows": [["NU", 4.0, 10.0, 15.0], ["1-5", None, 6.0, 11.0], ["6-10", None, None, 5.0]],
         "window": "Aug 2026 – Jul 2027", "in_window": True, "data_past_end": False,
         "seg": [["NU", 100, 1000.0]], "revseg": [["NU", 0.2, 1.0], ["1-5", 0.3, 5.0], ["6-10", 0.2, 11.0], ["11-15", 0.3, 16.0]]}
    O = {"funnel": {"eligible": 4800}, "source_file": "9999-test-ODD (100126_080000).csv"}
    for name, data in (("metrics.json", M), ("base.json", B), ("lift.json", L)):
        (d / name).write_text(json.dumps(data), encoding="utf-8")
    (d / "oddd" / "oddd_metrics.json").write_text(json.dumps(O), encoding="utf-8")
    return d


@pytest.fixture
def pack_root(tmp_path):
    make_pack(tmp_path)
    return tmp_path


def build(root, programs=("ars",)):
    return registry.build_model(CID, PERIOD, root=root, programs=list(programs))


def walk(o):
    if isinstance(o, dict):
        for v in o.values():
            yield from walk(v)
    elif isinstance(o, list):
        for v in o:
            yield from walk(v)
    else:
        yield o


# ----------------------------------------------------------------- traceability
def test_every_figure_traces_to_the_pack(pack_root):
    model, _t, problems = build(pack_root)
    assert problems == []
    ars = model["programs"][0]
    assert ars["state"] == "ready"
    assert [s["id"] for s in ars["screens"]] == ["summary", "financial", "lift", "mailings", "take", "rege", "usage", "peers"]


def test_a_figure_with_no_pack_behind_it_fails_the_audit(pack_root):
    model, tracer, _p = build(pack_root)
    bad = copy.deepcopy(model)
    bad["programs"][0]["screens"][0]["blocks"][0]["items"][1]["value"] = 123456789.5   # typed, not read
    assert any("not in any pack" in p for p in TR.audit(bad, tracer))


def test_a_number_in_a_sentence_that_no_pack_explains_fails(pack_root):
    model, tracer, _p = build(pack_root)
    bad = copy.deepcopy(model)
    bad["programs"][0]["screens"][0]["headline"] += " It is up 37.4% on last year."
    assert any("37.4%" in p for p in TR.audit(bad, tracer))


def test_banned_words_and_lift_as_prose_fail_but_the_lift_matrix_is_a_name(pack_root):
    model, tracer, _p = build(pack_root)
    bad = copy.deepcopy(model)
    bad["programs"][0]["screens"][0]["headline"] = "A robust program."
    bad["programs"][0]["screens"][1]["headline"] = "Revenue lift is strong."
    ok = copy.deepcopy(model)
    ok["programs"][0]["screens"][2]["headline"] = "The Lift Matrix shows it."
    problems = TR.audit(bad, tracer)
    assert any("robust" in p for p in problems) and any("'lift' as prose" in p for p in problems)
    assert TR.audit(ok, tracer) == []


def test_derive_refuses_an_input_that_is_not_a_pack_figure():
    t = TR.Tracer()
    t.see(10)
    assert t.derive(5.0, "half", 10) == 5.0
    with pytest.raises(AssertionError):
        t.derive(1.0, "made up", 777)


def test_the_movement_wording_follows_the_band():
    f = lambda v: f"{v:,.0f}"
    assert "almost flat" in TR.movement("Spend", 1000, 1015, f)
    assert "increased 10.0%" in TR.movement("Spend", 1000, 1100, f)
    assert "did not have an impact on Spend" in TR.movement("Spend", 1000, 900, f)


# ----------------------------------------------------------------- complete months only
def test_the_peer_screens_name_the_client_and_the_page_marks_each_product():
    from review_page import registry
    node = {"series": [{"name": "This client"}, {"name": "Peer median"}], "x": [{"name": "This client"}]}
    registry._name_the_client(node, "Marine FCU")
    assert [s["name"] for s in node["series"]] == ["Marine FCU", "Peer median"] and node["x"][0]["name"] == "Marine FCU"
    js = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "build", "review_page", "static", "live.js"), encoding="utf-8").read()
    assert "This client" not in js.replace('"This client"', "")           # only the fallback when a client has no name
    assert "S.present) showProgramCard" in js                          # the title card shows only while presenting
    assert "prodSections" in js and 'class="prod"' in js                # the rail and the agenda are grouped by product
    assert "showProgramCard" in js and 'class="ptag"' in js and 'setAttribute("data-product"' in js
    assert 'class="dstat"' in js and 'class="dtrack"' in js and "dwedge" in js    # the deck's divider: figures, progress track, wedge
    assert " screens" not in js.split("function showProgramCard")[1].split("function ")[0]   # no slide count on the card
    assert 'setAttribute("data-prog"' not in js                      # the click handler treats any [data-prog] ancestor as a program tab
    css = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "build", "review_page", "static", "live.css"), encoding="utf-8").read()
    for k in ("ars", "analysis", "ti", "ics", "mrpc", "cashplease"):
        assert 'html[data-product="%s"]' % k in css
    assert "html[data-prog" not in css


def test_presenting_the_review_goes_one_product_at_a_time():
    js = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "build", "review_page", "static", "live.js"), encoding="utf-8").read()
    step = js.split("function step(d)")[1].split("function stepProgram")[0]
    assert 'S.present && S.prog === "story" && d > 0' in step and "showProgramCard(nxt.prog, true)" in step     # a held title card on the first press
    assert "S.hold = null; S.lastFam = nxt.prog" in step                                                       # the second press starts the product
    assert 'S.present && S.prog === "story" && (i < 0 || i >= n)) return' in step                              # the review's ends are its ends
    assert "function showProgramCard(pk, hold)" in js
    assert "if (!hold) S.pdivT = setTimeout" in js                                                              # a held card does not time out


def test_horizontal_bar_charts_can_be_sorted():
    js = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "build", "review_page", "static", "live.js"), encoding="utf-8").read()
    for how in ('"desc"', '"asc"', '"az"', '"list"'):
        assert how in js.split("var SORTS")[1].split("function chartHead")[0]       # largest, smallest, A-Z and as listed
    assert 'data-bsort="' in js and "S.bs[" in js
    assert "function sortOf" in js and 'S.present && b.cats.length > 6 ? "desc" : "list"' in js   # presenting a long list still defaults to largest first


def test_branch_bars_use_the_room_in_the_window_and_larger_names():
    js = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "build", "review_page", "static", "live.js")
    js = open(js, encoding="utf-8").read()
    assert "slice(0, 6)" not in js and "Largest 6 of" not in js      # the six-bar cap is gone
    assert "window.innerHeight" in js and "Math.max(6," in js          # as many as fit, never fewer than six
    assert "font-size:12.5px" not in js and "textW(c, 12.5)" not in js  # the branch names are no longer 12.5 px
    assert "var fs = S.present ? 16 : 14" in js


def test_a_collapse_in_the_middle_of_a_series_is_found():
    vals = [1000, 1010, 1020, 30, 1040, 1050, 1060]
    assert interior_gaps(vals) == [3]
    assert interior_gaps([1000, 1010, 1020, 500, 480, 470, 460, 450]) == []   # a fall that holds is a change


def test_the_nsf_series_leaves_the_collapsed_month_out_and_says_so(pack_root):
    model, _t, problems = build(pack_root)
    assert problems == []
    usage = next(s for s in model["programs"][0]["screens"] if s["id"] == "usage")
    assert any("Aug 26" in n or "Aug 2026" in n for n in usage["notes"] if "left out" in n)
    line = next(b for b in usage["blocks"] if b["t"] == "line" and b["id"] == "nsf-line")
    gap = [v for v in line["series"][0]["values"] if v is None]
    assert len(gap) == 1                                  # a gap in the line, never a zero
    assert not any(v == 0 for v in line["series"][0]["values"])
    assert any("reads n/a" in n for n in usage["notes"])  # the year-to-date comparison needs every month


def test_without_the_collapse_the_year_to_date_comparison_is_stated(tmp_path):
    make_pack(tmp_path, nsf_gap=False)
    model, _t, problems = build(tmp_path)
    assert problems == []
    usage = next(s for s in model["programs"][0]["screens"] if s["id"] == "usage")
    assert any("year to date" in n and "n/a" not in n for n in usage["notes"])


def test_a_month_pulled_before_it_ended_is_left_out():
    keep, excl = usable_series(["Aug 26", "Sep 26", "Oct 26"], [1000, 1010, 400], as_of=__import__("datetime").date(2026, 10, 15), measure="x")
    assert keep == [True, True, False] and excl[0]["reason"] == "pulled"


def test_a_month_still_in_progress_is_not_in_any_rate(pack_root):
    model, _t, _p = build(pack_root)
    mail = next(s for s in model["programs"][0]["screens"] if s["id"] == "mailings")
    assert any("in progress" in n and "Oct 2026" in n for n in mail["notes"])


# ----------------------------------------------------------------- the rest of the model
def test_branch_tables_carry_every_listed_branch_and_say_what_is_not_listed(pack_root):
    model, _t, _p = build(pack_root)
    take = next(s for s in model["programs"][0]["screens"] if s["id"] == "take")
    tbl = take["blocks"][0]["table"]
    assert [r["name"] for r in tbl["rows"]] == ["North", "South", "East"]
    assert tbl["total"]["elig"] == 300 and any("sit at branches with too few" in n for n in take["notes"])
    assert take["blocks"][0]["chart"]["drill"] == {"table": tbl["id"]}


def test_the_reg_e_screen_offers_both_cohorts(pack_root):
    model, _t, _p = build(pack_root)
    rege = next(s for s in model["programs"][0]["screens"] if s["id"] == "rege")
    v = rege["blocks"][0]
    assert v["t"] == "variants" and [o["key"] for o in v["options"]] == ["new", "all"]


def test_the_lift_matrix_is_not_outlined(pack_root):
    model, _t, _p = build(pack_root)
    lift = next(s for s in model["programs"][0]["screens"] if s["id"] == "lift")
    assert lift["blocks"][0]["mark"] is None   # the deck dropped the orange box on 2026-10-27


def test_a_missing_pack_is_a_stub_that_says_what_to_run(tmp_path):
    model, _t, problems = registry.build_model("1234", PERIOD, root=tmp_path, programs=["ars"])
    ars = model["programs"][0]
    assert ars["state"] == "missing" and "Build the 2026.10 ARS deck for 1234" in ars["fix"]
    assert problems == []


def test_a_program_that_fails_does_not_take_the_others_down(pack_root, monkeypatch):
    from review_page.programs import ars as A
    monkeypatch.setattr(A, "build", lambda ctx, p: (_ for _ in ()).throw(KeyError("boom")))
    model, _t, _p = build(pack_root)
    assert model["programs"][0]["state"] == "error" and "KeyError" in model["programs"][0]["note"]


def test_the_combined_view_needs_two_programs_that_built(pack_root):
    model, _t, _p = build(pack_root)
    assert model["combined"] is None


def test_ids_are_validated_before_any_path_is_built():
    for bad in ("../x", "12", "abc", "1539/..", ""):
        with pytest.raises(ValueError):
            PK.check_ids(bad, PERIOD)
    with pytest.raises(ValueError):
        PK.check_ids("1539", "2026-10")


def test_the_registry_lists_the_programs_in_order():
    assert [k for k, _l, _m in registry.REGISTRY] == ["ars", "analysis", "ti", "ics", "mrpc", "cashplease", "rems"]


# ----------------------------------------------------------------- the page and the server
def test_the_embedded_model_cannot_end_the_script_early(pack_root):
    model, _t, _p = build(pack_root)
    model["client"]["name"] = "</script><script>alert(1)</script>"
    html = render_page(model, "tok")
    assert "</script><script>alert(1)" not in html
    assert json.loads(model_json(model))["client"]["name"].startswith("</script>")
    assert 'name="token" content="tok"' in html


def test_the_page_names_no_host_but_its_own():
    css = open(os.path.join(REPO, "build", "review_page", "static", "live.css"), encoding="utf-8").read()
    js = open(os.path.join(REPO, "build", "review_page", "static", "live.js"), encoding="utf-8").read()
    for text in (css, js):
        assert "http://" not in text.replace("http://www.w3.org", "") and "https://" not in text   # works offline
    assert all(f.is_file() for f in FONT_FILES.values())


def test_closing_the_table_drops_the_highlight_on_the_chart():
    # the bar clicked to open a row stays outlined only while its table is open (Aaron, 2026-11-02)
    js = open(os.path.join(REPO, "build", "review_page", "static", "live.js"), encoding="utf-8").read()
    body = js.split("function closePanel() {", 1)[1].split("\n  }", 1)[0]
    assert "S.drill = null" in body and "render()" in body


def test_presenter_stays_windowed_and_arrows_walk_every_section():
    # Aaron, 2026-11-02: presenting must not go full screen (Teams on a 36-inch monitor), and the arrow keys carry on into the next program
    js = open(os.path.join(REPO, 'build', 'review_page', 'static', 'live.js'), encoding='utf-8').read()
    assert 'requestFullscreen' not in js
    step = js.split('function step(d) {', 1)[1].split('function stepProgram', 1)[0]
    assert 'walkOrder()' in step and 'S.prog = order[to]' in step


def test_bars_draw_in_only_when_a_screen_first_appears():
    # Aaron, 2026-11-02: opening or closing the branch detail re-rendered the screen and replayed the bar animation
    root = os.path.join(REPO, 'build', 'review_page', 'static')
    js = open(os.path.join(root, 'live.js'), encoding='utf-8').read()
    css = open(os.path.join(root, 'live.css'), encoding='utf-8').read()
    assert 'classList.toggle("still", !!S.plain)' in js
    assert '#stage.still .grow-x' in css and '#stage.still .grow-y' in css


def _import_script():
    import importlib.util
    spec = importlib.util.spec_from_file_location("live_review_script", os.path.join(REPO, "scripts", "live_review.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def server(pack_root):
    S = _import_script()
    svc = S.Service(CID, PERIOD, root=pack_root, programs=["ars"])
    srv = S.make_server(svc, "secret-token", 0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield srv.server_address[1], S, svc
    srv.shutdown()


def call(port, method, path, body=None, token=None, host=None):
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    headers = {}
    if token:
        headers["X-Token"] = token
    if host:
        headers["Host"] = host
    c.request(method, path, body=body, headers=headers)
    r = c.getresponse()
    data = r.read()
    c.close()
    return r.status, data


def test_the_page_carries_its_token_and_the_model(server):
    port, _S, _svc = server
    status, data = call(port, "GET", "/")
    assert status == 200
    html = data.decode("utf-8")
    assert 'content="secret-token"' in html and "Test Bank" in html and 'id="model"' in html


def test_the_api_refuses_a_call_without_the_token(server):
    port, _S, _svc = server
    assert call(port, "GET", "/api/model")[0] == 403
    assert call(port, "GET", "/api/model", token="wrong")[0] == 403
    status, data = call(port, "GET", "/api/model", token="secret-token")
    assert status == 200 and json.loads(data)["programs"][0]["key"] == "ars"


def test_a_page_on_another_name_is_refused_even_with_the_token(server):
    port, _S, _svc = server
    # DNS rebinding: a page on another name resolving to 127.0.0.1 still sends its own Host.
    assert call(port, "GET", "/", host="evil.example")[0] == 403
    assert call(port, "GET", "/api/model", token="secret-token", host="evil.example")[0] == 403
    assert call(port, "GET", "/fonts/Carlito-Regular.ttf", host="evil.example")[0] == 403
    assert call(port, "GET", "/api/model", token="secret-token", host="localhost:1234")[0] == 200


def test_a_post_is_refused_and_a_refused_post_with_a_body_is_answered(server):
    port, _S, _svc = server
    body = "x" * 100_000
    assert {call(port, "POST", "/api/model", body=body)[0] for _ in range(60)} == {403}
    assert call(port, "POST", "/api/model", body="{}", token="secret-token")[0] == 405   # read-only


def test_only_the_bundled_fonts_are_served(server):
    port, _S, _svc = server
    status, data = call(port, "GET", "/fonts/Carlito-Regular.ttf")
    assert status == 200 and len(data) > 10_000
    for bad in ("/fonts/../../CLAUDE.md", "/fonts/..%2f..%2fCLAUDE.md", "/fonts/OFL.txt", "/fonts/", "/static/live.js", "/etc/passwd"):
        assert call(port, "GET", bad)[0] in (403, 404)


def test_it_binds_to_loopback_only(server):
    port, _S, _svc = server
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    c.request("GET", "/")
    assert c.getresponse().status == 200
    # the server socket is on 127.0.0.1, not 0.0.0.0
    S = _import_script()
    svc = S.Service(CID, PERIOD, programs=["ars"])
    srv = S.make_server(svc, "t", 0)
    try:
        assert srv.server_address[0] == "127.0.0.1"
    finally:
        srv.server_close()


def test_a_model_with_an_untraced_figure_is_not_served(pack_root, monkeypatch):
    S = _import_script()
    monkeypatch.setattr(registry, "audit", lambda model, t: ["number not in any pack or derivation: 1.0 at x"])
    svc = S.Service(CID, PERIOD, root=pack_root, programs=["ars"])
    with pytest.raises(ValueError, match="do not trace"):
        svc.rebuild()
    srv = S.make_server(svc, "tok", 0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        status, data = call(srv.server_address[1], "GET", "/")
        assert status == 500 and b"could not start" in data
    finally:
        srv.shutdown()


# ----------------------------------------------------------------- it stays out of Sheila and the delivery record
def test_sheila_does_not_know_about_it():
    sheila = open(os.path.join(REPO, "scripts", "ars_launcher_web.py"), encoding="utf-8").read()
    assert "review_page" not in sheila and "live review" not in sheila.lower()


def test_it_writes_nothing():
    """No module of the page opens a file for writing, and none names Outputs or the delivery record."""
    root = os.path.join(REPO, "build", "review_page")
    sources = [os.path.join(dp, f) for dp, _d, fs in os.walk(root) for f in fs if f.endswith(".py")]
    sources.append(os.path.join(REPO, "scripts", "live_review.py"))
    for path in sources:
        text = open(path, encoding="utf-8").read()
        for needle in ("deliveries.json", "client_outputs", "outputs()", "promote_month", "write_text(", "open(path, \"w"):
            if path.endswith("live_review.py") and needle == "write_text(":
                continue         # --dump writes the model JSON where the caller says
            assert needle not in text, f"{os.path.basename(path)} mentions {needle}"


# ----------------------------------------------------------------- the other programs (thin screens)
def test_cashplease_reads_its_pack_and_leaves_a_month_not_yet_ended_out(tmp_path):
    packs = tmp_path / "cashplease" / "packs"
    packs.mkdir(parents=True)
    months = [{"period_month": f"2026-{m:02d}", "loans": 100 + m, "principal": 40000.0 + m, "interest": 1000.0 + m,
               "funded": 90, "paid_off": 10, "overdue": 0, "charged_off": 0} for m in range(1, 11)]
    pack = {"client_id": CID, "client_name": "Test Bank", "source_file": "CashPleaseSummaryV1_261012_090000.xlsx",
            "dda_sent": None, "report_generated": "10/12/2026 8:57:13 AM", "charge_off_pct": 0.04,
            "status": {"Funded": {"principal": 1.0, "interest": 1.0, "loans": 50}, "Paid Off": {"principal": 9.0, "interest": 2.0, "loans": 500}},
            "total": {"principal": 10.0, "interest": 3.0, "loans": 550}, "monthly": months,
            "metrics": {"total_loans": 550, "total_principal": 10.0, "active_loans": 50, "active_principal": 1.0, "avg_loan_size": 40.0,
                        "loans_per_1k_dda": None, "dda_missing_reason": "no DDA count for this client in the ILS Management Server report"}}
    (packs / f"{CID}_cashplease.json").write_text(json.dumps(pack), encoding="utf-8")
    model, _t, problems = build(tmp_path, ("cashplease",))
    assert problems == []
    cp = model["programs"][0]
    assert cp["state"] == "ready"
    vol = next(s for s in cp["screens"] if s["id"] == "volume")
    cats = vol["blocks"][0]["chart"]["cats"]
    assert "Oct 26" not in cats and cats[-1] == "Sep 26"       # October had not ended on 10/12
    summary = cp["screens"][0]
    assert any("Loans per 1,000 DDAs is not shown" in n for n in summary["notes"])   # absence is stated, never a zero


def test_ics_shows_referrals_only_without_a_workbook_for_the_period(tmp_path, monkeypatch):
    import rpe_env
    sheet = {"meta": {"client_name": "Test Bank", "workbook": "9999-2026.08-Test-Invitation Checking Workbook v1.7.1.xlsx",
                      "program_start": "2018-12", "vip_source": "VIP", "data_pull": "2026-10-27"},
             "referrals": {"program_to_date": 700, "year_to_date": 90, "previous_month": {"label": "September", "value": 9},
                           "month_to_date": {"label": "October", "value": 5, "partial": True}, "monthly_goal": 8,
                           "prev_month_vs_goal_pct": 112,
                           "trend": {"months": ["Aug 26", "Sep 26", "Oct 26"], "referrals": [7, 9, 5], "goal": [8, 8, 8], "partial_last": True},
                           "by_branch": {"branches": [{"name": "North", "referrals": 40, "goal": 30}, {"name": "South", "referrals": 0, "goal": 0}]}}}
    f = tmp_path / "9999_ics.json"
    f.write_text(json.dumps(sheet), encoding="utf-8")
    monkeypatch.setattr(rpe_env, "resolve_client_json", lambda cid, prog: f)
    model, _t, problems = build(tmp_path, ("ics",))
    assert problems == []
    ics = model["programs"][0]
    refs = ics["screens"][0]
    assert refs["blocks"][1]["cats"] == ["Aug 26", "Sep 26"]            # the month in progress is left out of the trend
    assert any("2026.08" in n and "workbook" in n for n in refs["notes"])
    branch = ics["screens"][1]["blocks"][0]["table"]
    south = next(r for r in branch["rows"] if r["name"] == "South")
    assert south["pct"] is None                                          # no goal: a dash, never a zero or infinity


def test_mrpc_reads_the_weekly_through_the_decks_own_figures(tmp_path, monkeypatch):
    from review_page.programs import mrpc as MP
    monthly = [{"platinum": 80 + i, "gold": 10, "business": 0, "primary": 90, "joint": 5, "web_branch": 60, "web_enduser": 10,
                "phone": 20, "paper": 0, "existing": 40, "new": 50, "employees": 1, "non_employees": 89,
                "month": f"2026-{m:02d}"} for i, m in enumerate(range(1, 10))]
    w = {"file": "261001_000000-MRPCEnrollmentSummary_v3_13.xlsx", "tab": "9999-Test Bank", "report_generated": "10/1/2026 9:00:00 AM",
         "open_with_debit": 5000, "all_mrpc_accounts": 900, "take_rate_all": 0.18, "active_mrpc_accounts": 400, "take_rate_active": 0.08,
         "all_cardholders": 1000, "active_cardholders": 450, "new_account_take": {},
         "totals": {"platinum": 800, "gold": 200, "business": 0, "primary": 950, "joint": 50, "web_branch": 600, "web_enduser": 100,
                    "phone": 300, "paper": 0, "existing": 500, "new": 500, "employees": 10, "non_employees": 990},
         "cardholders_active_buckets": {"1-90": 50, "91-180": 60, "180+": 340, "inactive": 550}, "monthly": monthly}

    class FakeWeekly:
        path, name, tabs = "x", w["file"], {CID: "9999-Test Bank"}

        def client(self, cid):
            return w if cid == CID else None

    monkeypatch.setitem(MP._CACHE, "w", FakeWeekly())
    from review_page import peer_pool
    monkeypatch.setattr(peer_pool, "_vip_ids", lambda program: [])
    monkeypatch.setitem(peer_pool._WEEKLY, "w", FakeWeekly())
    model, _t, problems = build(tmp_path, ("mrpc",))
    assert problems == []
    mrpc = model["programs"][0]
    assert mrpc["state"] == "ready" and [s["id"] for s in mrpc["screens"]] == ["status", "enrollments", "peers"]
    assert mrpc["screens"][0]["blocks"][0]["items"][0]["value"] == 450
    assert "9999" not in json.dumps(mrpc["client_name"])


def test_two_programs_make_a_combined_view(tmp_path, monkeypatch):
    make_pack(tmp_path)
    packs = tmp_path / "cashplease" / "packs"
    packs.mkdir(parents=True)
    pack = {"client_id": CID, "client_name": "Test Bank", "source_file": "x.xlsx", "report_generated": "10/12/2026 8:00:00 AM",
            "charge_off_pct": 0.04, "status": {}, "total": {"principal": 10.0, "interest": 3.0, "loans": 550},
            "monthly": [{"period_month": "2026-05", "loans": 5, "principal": 1.0, "interest": 1.0, "funded": 1, "paid_off": 1, "overdue": 0, "charged_off": 0}],
            "metrics": {"total_loans": 550, "total_principal": 10.0, "active_loans": 50, "active_principal": 1.0, "avg_loan_size": 40.0, "loans_per_1k_dda": None}}
    (packs / f"{CID}_cashplease.json").write_text(json.dumps(pack), encoding="utf-8")
    model, _t, problems = build(tmp_path, ("ars", "cashplease"))
    assert problems == []
    assert model["combined"]["screens"][0]["blocks"][0]["cards"][0]["open"] == "ars:summary"
    assert [c["program"] for c in model["combined"]["screens"][0]["blocks"][0]["cards"]] == ["ars", "cashplease"]


# ----------------------------------------------------------------- against a real deck (needs the share; skipped without it)
def test_the_page_states_what_the_deck_it_mirrors_states():
    """Marine FCU 1539, 2026.10: the figures the deck's own sidecar records are the page's."""
    try:
        import rpe_env
        ba = rpe_env.build_artifacts()
        sidecar = ba / "1539-2026.10-ARS-Marine FCU ARS Results.pptx.figures.json"
        if not sidecar.is_file() or not (ba / "launcher" / "2026.10" / "1539" / "metrics.json").is_file():
            pytest.skip("no 1539 pack on this machine")
    except (SystemExit, Exception) as e:      # no data root (CI)
        pytest.skip(f"no share: {e}")
    figs = {f["measure"]: f["value"] for f in json.loads(sidecar.read_text(encoding="utf-8"))["figures"]}
    model, _t, problems = registry.build_model("1539", "2026.10", programs=["ars"])
    assert problems == []
    mail = next(s for s in model["programs"][0]["screens"] if s["id"] == "mailings")
    assert f"{int(figs['mailed_latest_mailing'].replace(',', '')):,}" in mail["headline"]
    assert figs["responders_latest_mailing"] in mail["headline"] and figs["resprate_latest_mailing"] in mail["headline"]
