"""Sheila in Claude (James Gilmore, 2026-10-30): "turn my m365 tools into Sheila tools ... Sheila, create this
report", for every CSM, "built once, no csm has to do it". sheila_mcp/ is a second front door onto the functions
Sheila's page calls; these tests pin the protocol, who is asking, the month view, the build rules (a deck in
Outputs is replaced only on a yes), the review list, and the registration that puts her in Claude Desktop."""
import io
import json
import os
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [REPO, os.path.join(REPO, "scripts"), os.path.join(REPO, "build")]

from sheila_mcp import actions, core, register, stdio, who  # noqa: E402


# ------------------------------------------------------------------ the protocol
def _serve(server, *msgs):
    out = io.StringIO()
    server._out = out
    old = sys.stdout
    try:
        server.run(io.StringIO("".join(json.dumps(m) + "\n" for m in msgs)))
    finally:
        sys.stdout = old
    return [json.loads(l) for l in out.getvalue().splitlines()]


def _toy():
    s = stdio.Server("sheila", "9.9", "be Sheila")

    @s.tool
    def hello(client: str, n: int = 2, loud: bool = False, codes: dict = None) -> dict:
        """Say hello."""
        return {"answer": f"hi {client} x{n}", "data": {"client": client}}

    @s.tool
    def boom() -> dict:
        """Fails."""
        raise SystemExit("RPE_DATA_ROOT is not set.")

    @s.prompt("my-month", "Where my book stands")
    def p() -> str:
        return "Sheila, where am I this month?"
    return s


def test_the_server_speaks_mcp_over_stdio():
    rs = _serve(_toy(),
                {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}},
                {"jsonrpc": "2.0", "method": "notifications/initialized"},
                {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
                {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "hello", "arguments": {"client": "1798"}}},
                {"jsonrpc": "2.0", "id": 4, "method": "prompts/get", "params": {"name": "my-month"}},
                {"jsonrpc": "2.0", "id": 5, "method": "nope"})
    by = {r["id"]: r for r in rs}
    assert len(rs) == 5, "a notification gets no reply"
    init = by[1]["result"]
    assert init["serverInfo"] == {"name": "sheila", "version": "9.9"} and init["instructions"] == "be Sheila"
    assert init["protocolVersion"] == "2025-06-18" and "tools" in init["capabilities"]
    tool = next(t for t in by[2]["result"]["tools"] if t["name"] == "hello")
    assert tool["description"] == "Say hello."
    assert tool["inputSchema"] == {"type": "object", "required": ["client"], "properties": {
        "client": {"type": "string"}, "n": {"type": "integer", "default": 2},
        "loud": {"type": "boolean", "default": False}, "codes": {"type": "object"}}}
    assert by[3]["result"]["content"] == [{"type": "text", "text": "hi 1798 x2"}]
    assert by[3]["result"]["structuredContent"] == {"client": "1798"}
    assert by[4]["result"]["messages"][0]["content"]["text"] == "Sheila, where am I this month?"
    assert by[5]["error"]["code"] == -32601


def test_a_failing_tool_answers_with_its_own_words_and_the_server_keeps_going():
    rs = _serve(_toy(), {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "boom", "arguments": {}}},
                {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "hello", "arguments": {"x": 1}}},
                {"jsonrpc": "2.0", "id": 3, "method": "ping"})
    by = {r["id"]: r for r in rs}
    assert by[1]["result"]["isError"] and "RPE_DATA_ROOT is not set." in by[1]["result"]["content"][0]["text"]
    assert by[2]["result"]["isError"] and "Bad arguments" in by[2]["result"]["content"][0]["text"]
    assert by[3]["result"] == {}


def test_a_slow_call_does_not_hold_up_a_quick_one_and_every_call_is_answered_before_exit():
    s = stdio.Server("t", "1")

    @s.tool
    def slow() -> str:
        """slow"""
        time.sleep(0.4)
        return "slow done"

    @s.tool
    def quick() -> str:
        """quick"""
        return "quick done"
    rs = _serve(s, {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "slow"}},
                {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "quick"}})
    assert [r["id"] for r in rs] == [2, 1]


def test_the_real_server_registers_every_tool_with_a_description():
    import sheila_mcp.__main__ as M
    tools = {t["name"]: t for t in M.mcp.tool_list()}
    assert {"my_month", "clients", "client_status", "build", "build_progress", "deck_summary", "review", "explain",
            "outputs", "data_issues", "ils_status", "ils_run", "ils_progress", "whats_new"} <= set(tools)
    assert all(t["description"] for t in tools.values())
    assert "confirm=true" in M.INSTRUCTIONS and "never sends email" in M.INSTRUCTIONS
    assert {p["name"] for p in M.mcp.prompt_list()} == {"my-month", "build-a-client", "review-a-deck",
                                                         "run-an-ils-analysis"}


# ------------------------------------------------------------------ who is asking
NAMES = {"James Gilmore", "Jordan Berkowitz", "Aaron Burgard", "Max Willett"}


def test_the_windows_user_is_read_as_a_csm(monkeypatch):
    monkeypatch.setattr(who, "_contacts", lambda: {"mwillett": "Max Willett"})
    assert who.current_csm("james.gilmore", NAMES) == "James Gilmore"
    assert who.current_csm("mwillett", NAMES) == "Max Willett", "CSM Contacts' email when the name does not match"
    assert who.current_csm("someone.else", NAMES) is None
    assert who.resolve_csm("jordan", NAMES) == "Jordan Berkowitz"
    assert who.resolve_csm("AARON BURGARD", NAMES) == "Aaron Burgard"
    assert who.resolve_csm("nobody", NAMES) is None


# ------------------------------------------------------------------ a fake Sheila behind the tools
CLIENTS = [
    {"id": "1826", "name": "Air Academy FCU", "csm": "James Gilmore", "programs": ["ARS"], "covered": ["ARS"]},
    {"id": "1156", "name": "BancFirst", "csm": "James Gilmore", "programs": ["ARS"], "covered": ["ARS"]},
    {"id": "1615", "name": "Cape & Coast Bank", "csm": "James Gilmore", "programs": ["ARS"], "error": True},
    {"id": "1453", "name": "Connex CU", "csm": "James Gilmore", "programs": ["ARS"], "decks": ["1453-2026.10-ARS-Connex CU ARS Results.pptx"]},
    {"id": "1776", "name": "CoastHills CU", "csm": "James Gilmore", "programs": ["ARS"], "sent": "2026-10-20", "ti_decks": ["x"]},
    {"id": "1798", "name": "FirstLight FCU", "csm": "Jordan Berkowitz", "programs": ["ARS"]},
    {"id": "1539", "name": "Marine FCU", "csm": "Aaron Burgard", "programs": ["ARS", "ICS"]},
]
STATUS = {
    "1826": {"state": "ready", "checks": [{"level": "ok", "text": "fine"}], "builds": {"ars_only": True, "has_ars": True, "base": ["ARS"]}},
    "1156": {"state": "stop", "checks": [{"level": "stop", "text": "ARS workbook: not in Inputs"}],
             "builds": {"ars_only": True, "has_ars": True, "base": ["ARS"]}},
    "1798": {"state": "ask", "period": "2026.10",
             "checks": [{"level": "ask", "text": "The 2026.10 deck is already in Outputs (1798-2026.10-ARS-FirstLight FCU ARS Results.pptx)."}],
             "builds": {"ars_only": True, "has_ars": True, "base": ["ARS"]},
             "ti": {"state": "ready", "checks": []}},
    "1539": {"state": "ready", "period": "2026.10", "checks": [],
             "builds": {"ars_only": False, "has_ars": True, "base": ["ARS"], "combined": ["ARS", "ICS"]}},
}


@pytest.fixture
def fake(monkeypatch):
    started = []
    W = SimpleNamespace(
        clients_doc=lambda: {"period": "2026.10", "clients": [dict(c) for c in CLIENTS]},
        status_doc=lambda cid, fresh=False: dict(STATUS[cid]),
        stop_label=lambda checks: "ARS workbook" if any(k["level"] == "stop" for k in checks) else None,
        current_period=lambda: "2026.10",
        start_build=lambda *a, **k: started.append((a, k)) or (202, {"client": a[0], "queued": None}),
        job_doc=lambda cid: None, queue_doc=lambda: {"building": None, "queued": []})
    monkeypatch.setitem(core._web, "mod", W)
    monkeypatch.setattr(who, "csm_names", lambda: NAMES)
    monkeypatch.setattr(who, "current_csm", lambda user=None, names=None: "James Gilmore")
    return SimpleNamespace(web=W, started=started)


def test_my_month_groups_the_book_and_says_what_to_do_next(fake):
    r = core.my_month("me")
    g = {k: [c["id"] for c in v] for k, v in r["data"]["groups"].items()}
    assert g == {"ready": ["1826"], "blocked": ["1156"], "failed": ["1615"], "in_outputs": ["1453"],
                 "sent": ["1776"], "unchecked": []}
    assert "James Gilmore's book for 2026.10: 5 clients." in r["answer"]
    assert "1156 BancFirst (ARS workbook)" in r["answer"], "a blocked client says what blocks it"
    assert "build all ready" in r["answer"]
    assert "1798" not in r["answer"], "only the CSM's own book"


def test_a_name_that_matches_two_clients_is_asked_about_not_guessed(fake):
    c, why = core.find_client("fcu")
    assert c is None and "More than one client matches" in why and "1826 Air Academy FCU" in why
    assert core.find_client("firstlight")[0]["id"] == "1798"
    assert "not a client Sheila builds for" in core.find_client("9999")[1]


def test_a_blocked_client_is_not_built(fake):
    r = actions.build("1156")
    assert r["answer"].startswith("Not started: 1156 BancFirst can't build yet.")
    assert "ARS workbook: not in Inputs" in r["answer"] and not fake.started


def test_a_deck_already_in_outputs_is_replaced_only_on_a_yes(fake):
    r = actions.build("1798")
    assert r["data"]["needs_confirm"] and not fake.started
    assert "already in Outputs" in r["answer"] and "confirm=true" in r["answer"]
    r = actions.build("1798", confirm=True)
    (args, kw), = fake.started
    assert args[:3] == ("1798", True, False), "rebuild, not combined"
    assert "the ARS deck started" in r["answer"]


def test_a_client_with_only_the_combined_button_builds_combined(fake):
    actions.build("1539")
    (args, kw), = fake.started
    assert args[:3] == ("1539", False, True)


def test_a_ti_build_and_a_deck_only_redraw(fake):
    actions.build("1798", kind="ti")
    assert fake.started[-1][1] == {"ti": True, "companion": False}
    r = actions.build("1798", kind="ti", deck_only=True)
    assert r["data"]["needs_confirm"], "a redraw replaces the decks in Outputs, so it asks too"
    actions.build("1798", kind="ti", deck_only=True, confirm=True)
    assert fake.started[-1][0][1] is True and fake.started[-1][1]["deck_only"] is True
    assert "Transaction Intelligence decks only" in actions.build("1798", kind="ars", deck_only=True)["answer"]


def test_build_progress_reads_the_launchers_own_lines():
    c = {"id": "1798", "name": "FirstLight FCU"}
    running = {"lines": ["  [ok]   1798 FirstLight FCU", "  [..]   Validating the deck  (3 min)"], "done": False,
               "seconds": 300, "queued": None}
    assert actions._job_text(c, running) == "1798 FirstLight FCU: building, 5 min so far. Now: Validating the deck  (3 min)."
    done = {"lines": ["  [ok]   Validation of x.pptx: 0 FAIL, 26 REVIEW"], "done": True, "code": 0, "seconds": 2000,
            "deck": r"M:\Outputs\Jordan Berkowitz\x.pptx"}
    assert "In Outputs: M:\\Outputs\\Jordan Berkowitz\\x.pptx (0 FAIL, 26 REVIEW)." in actions._job_text(c, done)
    failed = {"lines": ["  [STOP] financial_services failed: MemoryError", "", "Not put in Outputs."], "done": True,
              "code": 1, "seconds": 60}
    t = actions._job_text(c, failed)
    assert "NOT put in Outputs" in t and "MemoryError" in t
    assert "queued #2, behind 1441" in actions._job_text(c, {"queued": 2, "after": "1441", "lines": []})


# ------------------------------------------------------------------ review and provenance
def test_the_validators_report_is_read_slide_by_slide(tmp_path, monkeypatch):
    period = tmp_path / "Build Artifacts" / "launcher" / "2026.10" / "1798" / "ti"
    period.mkdir(parents=True)
    name = "1798-2026.10-TI-ARS-FirstLight FCU Transaction Intelligence.pptx"
    (period / name).write_bytes(b"")
    (period / (name + ".validation.txt")).write_text(
        "validate_deck: x\n  0 FAIL, 2 REVIEW\n\n"
        "  [REVIEW] slide 12  one labelled measure, two values\n"
        "  [REVIEW] deck-wide a pill wraps\n", encoding="utf-8")
    monkeypatch.setattr(actions.R, "build_artifacts", lambda: tmp_path / "Build Artifacts")
    items = actions.review_items(Path("M:/Outputs/Jordan Berkowitz") / name, "1798")
    assert items == [("REVIEW", 12, "one labelled measure, two values"), ("REVIEW", None, "a pill wraps")]


def test_a_slides_figures_leave_out_its_page_number_years_and_month_labels():
    text = "Aug26 reached 22,914 accounts and 2,226 responded: 9.7% | September 2026 Data | $1.1B moved | 127"
    assert actions.figures_in(text, 127) == ["22,914", "2,226", "9.7%", "$1.1B"]


def test_the_launcher_keeps_the_validators_full_report_beside_the_deck(tmp_path, monkeypatch):
    import ars_launcher as L
    import build_month as BM
    deck = tmp_path / "x.pptx"
    out = "validate_deck: x\n  1 FAIL, 1 REVIEW\n\n  [FAIL  ] slide 3   bad\n  [REVIEW] slide 4   look\n"
    monkeypatch.setattr(L.subprocess, "run", lambda *a, **k: SimpleNamespace(stdout=out))
    verdict, fails = L.run_validator(deck)
    assert verdict == "1 FAIL, 1 REVIEW" and fails == ["[FAIL  ] slide 3   bad"]
    assert (tmp_path / ("x.pptx" + L.VALIDATION_SUFFIX)).read_text(encoding="utf-8") == out


# ------------------------------------------------------------------ the build path both front doors share
def test_build_cmd_passes_deck_only_and_one_build_runs_at_a_time_on_a_pc(tmp_path, monkeypatch):
    import ars_launcher_web as W
    assert W.build_cmd("1798", True, False, "2026.10", ti=True, deck_only=True)[-2:] == ["--ti", "--deck-only"]
    assert "--deck-only" not in W.build_cmd("1798", True, False, "2026.10", ti=True)
    monkeypatch.setattr(W, "BUILD_LOCK", tmp_path / "build.lock")
    monkeypatch.setattr(W, "forget_status", lambda cid: None)
    monkeypatch.setattr(W, "invalidate_clients", lambda: None)
    script = "import time\nprint('start', flush=True)\ntime.sleep(0.5)\nprint('end', flush=True)\n"
    monkeypatch.setattr(W, "build_cmd", lambda *a, **k: [sys.executable, "-c", script])
    a, b = W.Job("1001", False, period="2026.10"), W.Job("1002", False, period="2026.10")
    ta, tb = threading.Thread(target=a.run), threading.Thread(target=b.run)
    ta.start()
    time.sleep(0.15)
    tb.start()
    ta.join(10)
    tb.join(10)
    assert a.code == 0 and b.code == 0
    assert b.lines[0].strip().startswith("[..]   Waiting for another build on this PC")
    assert a.finished <= b.finished


# ------------------------------------------------------------------ registration
def test_registration_adds_sheila_and_keeps_everything_else(tmp_path):
    cfg = tmp_path / "Claude" / "claude_desktop_config.json"
    cfg.parent.mkdir()
    before = {"mcpServers": {"m365": {"command": "py", "args": ["m365_server.py"]}}, "theme": "dark"}
    cfg.write_text(json.dumps(before), encoding="utf-8")
    local = tmp_path / "RPE"
    assert register.register("M:\\CSM_Reporting\\", local, [cfg]) == {str(cfg): "added"}
    doc = json.loads(cfg.read_text(encoding="utf-8"))
    assert doc["mcpServers"]["m365"] == before["mcpServers"]["m365"] and doc["theme"] == "dark"
    s = doc["mcpServers"]["sheila"]
    assert s["command"] == str(local / "Python" / "python.exe") and s["args"][-1] == str(local / "sheila_start.py")
    assert s["env"]["RPE_DATA_ROOT"] == "M:\\CSM_Reporting" and s["env"]["ROOT"] == "M:\\CSM_Reporting\\"
    assert json.loads((tmp_path / "Claude" / "claude_desktop_config.json.bak").read_text(encoding="utf-8")) == before
    assert "runpy.run_module(\"sheila_mcp\"" in (local / "sheila_start.py").read_text(encoding="utf-8")
    stamp = cfg.stat().st_mtime_ns
    assert register.register("M:\\CSM_Reporting\\", local, [cfg]) == {str(cfg): "unchanged"}
    assert cfg.stat().st_mtime_ns == stamp, "opening Sheila again rewrites nothing"


def test_registration_leaves_a_broken_config_alone_and_creates_a_missing_one(tmp_path):
    bad = tmp_path / "a" / "claude_desktop_config.json"
    bad.parent.mkdir()
    bad.write_text("{not json", encoding="utf-8")
    new = tmp_path / "b" / "claude_desktop_config.json"
    new.parent.mkdir()
    r = register.register("\\\\PADMIS105\\Velocity_company\\CSM_Reporting\\", tmp_path / "RPE", [bad, new])
    assert r[str(bad)].startswith("skipped") and bad.read_text(encoding="utf-8") == "{not json"
    assert r[str(new)] == "added" and "sheila" in json.loads(new.read_text(encoding="utf-8"))["mcpServers"]


def test_the_release_ships_sheila_and_opening_sheila_registers_her():
    ps = Path(REPO, "scripts", "release_launcher.ps1").read_text(encoding="utf-8")
    assert "'sheila_mcp')" in ps
    cmd = Path(REPO, "scripts", "launchers", "runtime.cmd").read_text(encoding="utf-8")
    assert '"%PY%" "%CODE%\\sheila_mcp\\register.py" >nul 2>&1' in cmd
