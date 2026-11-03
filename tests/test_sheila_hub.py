"""CSM Sheila's page, the Hub layout, served at /: behind the token and host checks, and free of
sent state (2026-11-02)."""
import http.client
import json
import os
import re
import sys
import threading

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(REPO, "scripts"), os.path.join(REPO, "build")]
import ars_launcher_web as W  # noqa: E402
import sheila_hub as H  # noqa: E402


@pytest.fixture
def server(monkeypatch):
    monkeypatch.setattr(W, "clients_doc", lambda: {"period": "2026.10", "clients": []})
    srv = W.make_server(0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield srv.server_address[1]
    srv.shutdown()


def get(port, path, host=None, token=False):
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    headers = {"Host": host} if host else {}
    if token:
        headers["X-Token"] = W.TOKEN
    c.request("GET", path, headers=headers)
    r = c.getresponse()
    data = r.read()
    c.close()
    return r.status, data


def test_the_hub_is_sheila_at_slash_and_its_old_address_goes_there(server):
    """Aaron, 2026-11-02: "move Sheila entirely to the hub layout": no switch, no second layout."""
    status, data = get(server, "/")
    assert status == 200 and W.TOKEN.encode() in data and b"__TOKEN__" not in data and b"Two stacked slides" in data
    c = http.client.HTTPConnection("127.0.0.1", server, timeout=10)
    c.request("GET", "/hub")
    r = c.getresponse()
    r.read()
    assert r.status == 302 and r.getheader("Location") == "/"
    assert "RPE_SHEILA_HUB" not in open(os.path.join(REPO, "scripts", "sheila_hub.py"), encoding="utf-8").read().split('_PAGE = r"""')[0].split('"""', 2)[2]


def test_the_page_keeps_the_hosts_check_and_the_api_keeps_its_token(server):
    assert get(server, "/", host="evil.example")[0] == 403
    assert get(server, "/api/clients")[0] == 403
    assert get(server, "/api/clients", token=True)[0] == 200


def test_there_is_no_second_layout(server):
    """The classic page is gone (Aaron, 2026-11-02): nothing serves it, and nothing links to it."""
    assert get(server, "/classic")[0] in (403, 404)   # unknown paths want the token like the API
    import ars_launcher_web as W
    assert not hasattr(W, "PAGE") and not hasattr(W, "_version_html")
    assert not os.path.exists(os.path.join(REPO, "scripts", "slide_review_ui.py"))


def test_there_is_no_sent_state_on_the_page():
    """Sending is tracked in the delivery dashboard, not in Sheila (Aaron, 2026-11-02)."""
    assert not re.search(r"\bsent\b", H.PAGE, re.I) and "deliveries" not in H.PAGE
    for status in ("Ready", "Building", "In Outputs", "Needs attention", "Blocked"):
        assert status in H.PAGE


def test_every_element_the_script_looks_up_exists():
    ids = set(re.findall(r'id="([A-Za-z0-9_-]+)"', H.PAGE))
    looked = set(re.findall(r"\$\(\s*[\"']#([A-Za-z0-9_-]+)[\"']\s*\)", H.PAGE))
    created = {"cycles", "news"}          # the two menus, made by the script when opened
    assert not (looked - ids - created), sorted(looked - ids - created)


def test_the_hub_defines_every_colour_it_uses_and_themes_alike():
    css = H.PAGE.split("<style>", 1)[1].split("</style>", 1)[0]
    used = set(re.findall(r"var\(--([a-z0-9-]+)", css))
    base = css.split("@media (prefers-color-scheme:dark)", 1)[0]
    defined = set(re.findall(r"(?<![a-z0-9-])--([a-z0-9-]+)\s*:", base))
    assert not (used - defined), sorted(used - defined)
    # a token the dark theme redefines is one the light theme defines first
    dark = css.split("@media (prefers-color-scheme:dark)", 1)[1]
    assert set(re.findall(r"(?<![a-z0-9-])--([a-z0-9-]+)\s*:", dark)) <= defined


def _lum(hx):
    r, g, b = (int(hx[i:i + 2], 16) / 255 for i in (1, 3, 5))
    f = lambda c: c / 12.92 if c <= .03928 else ((c + .055) / 1.055) ** 2.4
    return .2126 * f(r) + .7152 * f(g) + .0722 * f(b)


def _ratio(a, b):
    hi, lo = sorted((_lum(a), _lum(b)), reverse=True)
    return (hi + .05) / (lo + .05)


def test_there_is_one_set_of_colours_and_no_switch_for_another():
    """Aaron, 2026-11-02: the CSI colours barely differ from the Hub's, so the Hub keeps only its own."""
    assert "data-skin" not in H.PAGE and "hub-skin" not in H.PAGE and "CSI" not in H.PAGE


def test_muted_text_reads_on_every_solid_ground_in_both_themes():
    css = H.PAGE.split("<style>", 1)[1].split("</style>", 1)[0]
    blocks = {
        "light": css.split("@media (prefers-color-scheme:dark)", 1)[0],
        "dark": css.split(':root[data-theme="dark"]{', 1)[1].split("}", 1)[0],
    }
    for name, block in blocks.items():
        t = dict(re.findall(r"--([a-z0-9-]+):\s*(#[0-9A-Fa-f]{6})", block))
        for fg, bg in (("muted", "ground"), ("muted", "sheet"), ("muted", "fill"), ("ink", "ground"), ("ink", "fill"), ("accent-ink", "sheet"),
                       ("good", "good-soft"), ("bad", "bad-soft"), ("warn", "warn-soft")):
            if fg in t and bg in t:
                assert _ratio(t[fg], t[bg]) >= 4.5, (name, fg, bg, round(_ratio(t[fg], t[bg]), 2))


# ------------------------------------------------------------------ who is asking (Aaron, 2026-11-02)
NAMES = ["Aaron Burgard", "James Gilmore", "Jordan Berkowitz", "Jordan Lee"]
EMAILS = {"Aaron Burgard": "Aaron.Burgard@csiweb.com", "James Gilmore": "jgilmore@csiweb.com",
          "Jordan Berkowitz": "jberkowitz@csiweb.com", "Jordan Lee": "jlee@csiweb.com"}


def who(user, environ=None, names=NAMES, emails=EMAILS):
    return H.detect(user, names, lambda n: emails.get(n, ""), environ or {})


def test_the_login_matches_a_csm_by_name():
    me = who("aaron.burgard")
    assert me["csm"] == "Aaron Burgard" and me["how"] == "login"
    assert who("James_Gilmore")["csm"] == "James Gilmore"
    assert who("AARON.BURGARD", emails={})["csm"] == "Aaron Burgard", "case never matters"


def test_the_login_matches_a_csm_by_the_local_part_of_their_email():
    me = who("jgilmore")                      # not their name, but James Gilmore's email is jgilmore@
    assert me["csm"] == "James Gilmore" and me["how"] == "login"
    assert who("JBerkowitz")["csm"] == "Jordan Berkowitz"


def test_a_login_nobody_has_filters_nothing_and_says_so_quietly():
    me = who("svc.build")
    assert me["csm"] is None and "every client is shown" in me["note"]
    assert who("")["csm"] is None and who(None)["csm"] is None
    assert who("aaron.burgard", names=[])["csm"] is None, "a CSM list that cannot be read is no match"


def test_two_csms_for_one_login_is_ambiguous_never_a_guess():
    twin = dict(EMAILS, **{"Jordan Lee": "jberkowitz@csiweb.com"})      # two rows with one local part
    me = who("jberkowitz", emails=twin)
    assert me["csm"] is None and "More than one" in me["note"]
    # the name says one CSM and the email another
    crossed = dict(EMAILS, **{"James Gilmore": "aaron.burgard@csiweb.com"})
    assert who("aaron.burgard", emails=crossed)["csm"] is None


def test_the_override_replaces_the_login_and_a_bad_one_filters_nothing():
    assert who("aaron.burgard", {"RPE_SHEILA_CSM": "James Gilmore"})["csm"] == "James Gilmore"
    me = who("svc.build", {"RPE_SHEILA_CSM": "gilmore"})              # a last name only one CSM has
    assert me["csm"] == "James Gilmore" and me["how"] == "override"
    assert who("aaron.burgard", {"RPE_SHEILA_CSM": "jordan"})["csm"] is None, "two Jordans: ambiguous"
    bad = who("aaron.burgard", {"RPE_SHEILA_CSM": "Nobody Here"})
    assert bad["csm"] is None and bad["how"] == "override" and "no CSM Sheila knows" in bad["note"]


def test_the_server_hands_the_page_who_it_is_and_the_page_cannot_be_broken_by_it(server, monkeypatch):
    monkeypatch.setattr(H, "who_am_i", lambda: {"csm": "Aaron Burgard", "how": "login", "note": ""})
    status, data = get(server, "/")
    assert status == 200 and b'"csm": "Aaron Burgard"' in data and b"__ME__" not in data
    page = H.page("T", "", {"csm": "x</script><b>", "how": "login", "note": ""})
    assert "</script><b>" not in page and "\\u003c/script" in page
    assert '"csm": null' in H.page("T", "")


def test_who_am_i_never_raises_and_is_worked_out_once(monkeypatch):
    H._me.clear()
    monkeypatch.setenv("RPE_DATA_ROOT", os.path.join(REPO, "no-such-root"))
    monkeypatch.delenv("RPE_SHEILA_CSM", raising=False)
    first = H.who_am_i()
    assert first["csm"] is None and H.who_am_i() is first
    H._me.clear()


def test_the_selected_row_has_no_accent_bar():
    """Aaron, 2026-11-02: no amber edge on the selected client; the tinted fill and a thin ring say it."""
    assert "inset 3px 0 0" not in H.PAGE
    row = re.search(r'\.row\[aria-current="true"\]\{([^}]*)\}', H.PAGE).group(1)
    assert "var(--fill)" in row and "var(--accent" not in row


def test_nothing_spins_or_pulses_unless_a_build_is_running():
    """Aaron, 2026-11-02: the Building tile spun while it said 0 and nothing running. Every animation tied to
    building hangs off <body class="busy">, set from the queue (or the open client's unfinished job) and nowhere
    else, and the tile draws a still ring when nothing is running."""
    css = H.PAGE.split("<style>", 1)[1].split("</style>", 1)[0]
    for sel in (r"\.k-building svg \.spin", r"\.dotp", r"\.steps \.sd\.now"):
        for m in re.finditer(r"([^{}]*" + sel + r"[^{}]*)\{([^}]*)\}", css):
            if "animation" in m.group(2):
                assert ".busy " in m.group(1), (m.group(1), m.group(2))
    assert not re.search(r"(?m)^\s*\.k-building svg \.spin\{[^}]*animation", css)
    still = re.search(r"\s idle:\s*'([^']*)'", H.PAGE).group(1)
    assert "spin" not in still and "animate" not in still
    assert 'si(k === "building" && !running() ? "idle" : k)' in H.PAGE
    assert "function running() { return !!(QUEUE.building || QUEUE.queued.length); }" in H.PAGE
    assert H.PAGE.count('classList.toggle("busy"') == 1, "one place decides"
    # the only other animations are one-shot (pop) or loading skeletons
    spin_uses = re.findall(r"animation:\s*(\w+)", css)
    assert set(spin_uses) <= {"spin", "pulse", "pop", "shimmer"}


def test_the_open_clients_row_again_closes_it_back_to_the_overview():
    """Aaron, 2026-11-02: a second click (or Enter on the cursor row) unselects the client and returns to the Decks
    overview. A build keeps running; the address and the keyboard cursor follow."""
    page = H.PAGE
    assert "row.dataset.id === CUR ? closeClient() : openClient(row.dataset.id)" in page
    assert 'if (CURSOR === CUR) closeClient(); else openClient(CURSOR);' in page
    body = re.search(r"function closeClient\(\) \{(.*?)\n\}\n", page, re.S).group(1)
    assert "CUR = null; CURSOR = null;" in body and "renderOverview()" in body and "syncHash()" in body
    assert "clearInterval(poller)" in body, "no polling of a client that is not open"
    assert "stopBuild" not in body and "/api/build" not in body, "closing never touches the build"
    assert "is still building" in body, "it says where the steps went"
    assert "function syncHash()" in page and "{client: CUR}" in page
    assert "Enter" in page and 'document.activeElement.closest(".row")' in page, "a focused row's own click is not counted twice"


def test_the_corner_mark_is_two_stacked_slides_and_there_is_no_orange_in_it():
    """Aaron, 2026-11-02, option E: a navy slide in front of a teal one, light and dark, and the same as the favicon."""
    svg = re.search(r'<svg class="mark"[^>]*>.*?</svg>', H.PAGE, re.S).group(0)
    assert 'aria-label="Two stacked slides"' in svg and 'viewBox="0 0 40 40"' in svg
    assert 'x="4" y="14" width="24" height="18" rx="4"' in svg and 'x="12" y="6" width="24" height="18" rx="4"' in svg
    assert "--mark-front:#1C2541; --mark-back:#15627E;" in H.PAGE and "--mark-front:#EEF3FA; --mark-back:#5FB3C9;" in H.PAGE
    assert ">S</div>" not in H.PAGE and "var(--accent)" not in re.search(r"\.mark\{[^}]*\}", H.PAGE).group(0)
    assert 'rel="icon"' in H.PAGE and "%2315627E" in H.PAGE and "%231C2541" in H.PAGE
    assert "Classic Sheila" not in H.PAGE and ">classic<" not in H.PAGE


def test_the_address_names_the_tab_and_the_old_bookmarks_still_work():
    page = H.PAGE
    for tab in ("decks", "lift", "issues", "votes", "reported"):
        assert f'data-tab="{tab}"' in page
    assert "function readHash()" in page and "function setTab(" in page and 'addEventListener("hashchange"' in page
    assert 'const TAB_KEY = {d: "decks", l: "lift", i: "issues", v: "votes", f: "reported"}' in page
