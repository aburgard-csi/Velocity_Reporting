"""The Hub layout preview at /hub: off unless RPE_SHEILA_HUB=1, behind the same token and host checks, and free of
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


def test_the_hub_is_off_unless_the_environment_turns_it_on(server, monkeypatch):
    monkeypatch.delenv("RPE_SHEILA_HUB", raising=False)
    assert get(server, "/hub")[0] == 404
    monkeypatch.setenv("RPE_SHEILA_HUB", "0")
    assert get(server, "/hub")[0] == 404
    monkeypatch.setenv("RPE_SHEILA_HUB", "1")
    status, data = get(server, "/hub")
    assert status == 200 and W.TOKEN.encode() in data and b"__TOKEN__" not in data


def test_the_hub_keeps_the_hosts_check_and_the_api_keeps_its_token(server, monkeypatch):
    monkeypatch.setenv("RPE_SHEILA_HUB", "1")
    assert get(server, "/hub", host="evil.example")[0] == 403
    assert get(server, "/api/clients")[0] == 403
    assert get(server, "/api/clients", token=True)[0] == 200


def test_the_classic_page_is_unchanged_by_the_hub_and_opens_a_tab_from_its_link(server, monkeypatch):
    monkeypatch.delenv("RPE_SHEILA_HUB", raising=False)
    status, data = get(server, "/")
    assert status == 200 and b"CSM Sheila" in data
    assert b"/^[a-z]+$/.test(h)" in data, "the hub's /#lift links open that tab"


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
    base = css.split("/* CSI brand colors, light */", 1)[0]
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


def test_muted_text_reads_on_every_solid_ground_in_every_theme_and_skin():
    css = H.PAGE.split("<style>", 1)[1].split("</style>", 1)[0]
    blocks = {
        "hub-light": css.split("/* CSI brand colors, light */", 1)[0],
        "csi-light": css.split("/* CSI brand colors, light */", 1)[1].split("@media", 1)[0],
        "hub-dark": css.split(':root[data-theme="dark"]{', 1)[1].split("}", 1)[0],
        "csi-dark": css.split(':root[data-theme="dark"][data-skin="csi"]{', 1)[1].split("}", 1)[0],
    }
    for name, block in blocks.items():
        t = dict(re.findall(r"--([a-z0-9-]+):\s*(#[0-9A-Fa-f]{6})", block))
        for fg, bg in (("muted", "ground"), ("muted", "sheet"), ("muted", "fill"), ("ink", "ground"), ("ink", "fill"), ("accent-ink", "sheet"),
                       ("good", "good-soft"), ("bad", "bad-soft"), ("warn", "warn-soft")):
            if fg in t and bg in t:
                assert _ratio(t[fg], t[bg]) >= 4.5, (name, fg, bg, round(_ratio(t[fg], t[bg]), 2))
