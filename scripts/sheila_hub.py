"""CSM Sheila's page: the Hub layout (Aaron, 2026-11-02: "move Sheila entirely to the hub layout").

Served at `/` with the token baked in; `/hub` redirects there. The page talks to the server's own API (clients,
status, job, queue, build, reveal, cycle, changelog, lift, issues, votes, reports, ils), so a check or a build
started here is the launcher's, nothing more. The shell, the Decks tab and the client page are this module; every
other tab is its own module (`sheila_hub_<tab>.py`: a view, its style and its script), added to `TAB_MODULES` and
assembled into the page here. The address names the tab: `#lift`, `#issues`, `#votes`, `#reported`; none is Decks.

Whether a deck was sent is not Sheila's to track (Aaron, 2026-11-02), so there is no sent state anywhere on this
page: a client is Ready, Building, In Outputs, Needs attention or Blocked.

The look is borrowed from the tools people like to use: Linear's dense rows with a status shape in front, J/K and
Enter to move through them; Vercel's pulsing dot for a build in progress; Raycast's command palette (Ctrl K) and its
compact mode; Stripe's calm, tinted status pills. The glass sidebar, tokens and both themes come from the Pack 205
Hub.
"""
import getpass
import html
import json
import os
import sys
from pathlib import Path


# ------------------------------------------------------------------ who is asking
# The Hub opens on the signed-in person's own clients (Aaron, 2026-11-02). Worked out here, once, on the server and
# handed to the page: the page never says who it is. It is a convenience filter, not security: the person can switch
# to every CSM from the page, and a wrong guess is worse than none, so nothing short of exactly one match filters.
OVERRIDE_ENV = "RPE_SHEILA_CSM"
NOT_KNOWN = "Couldn't tell which CSM you are, so every client is shown."


def _name_from_user(user):
    """'aaron.burgard' -> 'Aaron Burgard'."""
    return " ".join(p[:1].upper() + p[1:].lower() for p in user.replace("_", ".").split(".") if p)


def detect(user=None, names=None, email_of=None, environ=None):
    """The CSM this person is, as {csm, how, note}; csm is None unless exactly one CSM matches.

    `names` are the CSMs the Client CSM List names, `email_of(name)` that CSM's email in CSM Contacts.csv
    (rpe_env.contact_by_name). RPE_SHEILA_CSM="Name" (a full name, or a first or last name that only one CSM has)
    replaces the login, for testing and for a person running Sheila from someone else's login. The login
    (aaron.burgard) matches a CSM by name (Aaron Burgard) or by the email's local part (aaron.burgard@csiweb.com);
    two CSMs, or two rules naming different CSMs, is ambiguous and filters nothing.
    """
    environ = os.environ if environ is None else environ
    names = sorted(names or [])
    asked = (environ.get(OVERRIDE_ENV) or "").strip()
    if asked:
        want = asked.casefold()
        hits = [n for n in names if n.casefold() == want] or [n for n in names if want in n.casefold().split()]
        if len(hits) == 1:
            return {"csm": hits[0], "how": "override", "note": ""}
        return {"csm": None, "how": "override",
                "note": f"{OVERRIDE_ENV} names {'more than one CSM' if hits else 'no CSM Sheila knows'}, so every client is shown."}
    user = (user or "").strip()
    if not user:
        return {"csm": None, "how": None, "note": NOT_KNOWN}
    found = {n for n in names if n.casefold() == _name_from_user(user).casefold()}
    for n in names:
        mail = (email_of(n) if email_of else "") or ""
        if "@" in mail and mail.split("@")[0].strip().casefold() == user.casefold():
            found.add(n)
    if len(found) == 1:
        return {"csm": next(iter(found)), "how": "login", "note": ""}
    if found:
        return {"csm": None, "how": None, "note": "More than one CSM could be you, so every client is shown."}
    return {"csm": None, "how": None, "note": NOT_KNOWN}


_me = {}


def who_am_i():
    """`detect` on this PC's login and the share's CSM files, once per process. Never raises: a share that is
    not reachable is the same as no match."""
    if "me" not in _me:
        try:
            import rpe_env as R
            root = str(Path(__file__).resolve().parent.parent)
            if root not in sys.path:
                sys.path.insert(0, root)
            from sheila_mcp import who

            def email_of(name):
                try:
                    return R.contact_by_name(name).get("email", "")
                except SystemExit:
                    return ""
            _me["me"] = detect(getpass.getuser(), who.csm_names(), email_of)
        except (Exception, SystemExit):        # noqa: BLE001 - a convenience, never a reason the page fails
            _me["me"] = detect("", [], environ={})
    return _me["me"]


# The modules the page is assembled from, tabs in sidebar order. Each defines TAB (id, or None for a part of the
# Decks tab), NAME, VIEW (the tab section's inner HTML), CSS and JS; a tab's JS calls registerTab(id, {...}) (see
# "tabs" in the page script).
TAB_MODULES = ("sheila_hub_ils", "sheila_hub_lift", "sheila_hub_issues", "sheila_hub_votes", "sheila_hub_feedback")


# The mark (option E, Aaron 2026-11-02): a navy slide in front of a teal one, light and dark; the favicon draws the same.
MARK_SVG = ('<svg class="mark" viewBox="0 0 40 40" role="img" aria-label="Two stacked slides"><rect class="mb" x="12" y="6" width="24" height="18" rx="4"/>'
            '<rect class="mf" x="4" y="14" width="24" height="18" rx="4"/></svg>')
FAVICON = ('<link rel="icon" type="image/svg+xml" href="data:image/svg+xml,%3Csvg xmlns=\'http://www.w3.org/2000/svg\' viewBox=\'0 0 40 40\'%3E%3Cstyle%3E.b%7Bfill:%2315627E%7D.f%7Bfill:%231C2541%7D'
           '@media(prefers-color-scheme:dark)%7B.b%7Bfill:%235FB3C9%7D.f%7Bfill:%23EEF3FA%7D%7D%3C/style%3E%3Crect class=\'b\' x=\'12\' y=\'6\' width=\'24\' height=\'18\' rx=\'4\'/%3E'
           '%3Crect class=\'f\' x=\'4\' y=\'14\' width=\'24\' height=\'18\' rx=\'4\'/%3E%3C/svg%3E">')


def _assemble():
    import importlib
    views, css, js = [], [], []
    for name in TAB_MODULES:
        m = importlib.import_module(name)
        if m.TAB:
            views.append(f'<section class="view tabview" id="v-{m.TAB}" aria-label="{html.escape(m.NAME)}" hidden>{m.VIEW}</section>')
        css.append(m.CSS)
        js.append(m.JS)
    return (_PAGE.replace("__FAVICON__", FAVICON).replace("__MARK__", MARK_SVG).replace("<!--__TAB_VIEWS__-->", "\n".join(views))
            .replace("/*__TAB_CSS__*/", "\n".join(css)).replace("//__TAB_JS__", "\n".join(js)))


def page(token, version="", me=None):
    v = f"Version {html.escape(version)}" if version else "Preview"
    me = me or {}
    # It sits inside a <script>: nothing in the JSON may close it.
    data = json.dumps({"csm": me.get("csm"), "how": me.get("how"), "note": me.get("note") or ""}).replace("<", "\\u003c")
    return PAGE.replace("__TOKEN__", token).replace("__VERSION__", v).replace("__ME__", data)


_PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>CSM Sheila</title>
__FAVICON__
<style>
:root{
  --display:"Segoe UI Variable Display","Segoe UI",system-ui,sans-serif;
  --body:"Segoe UI Variable Text","Segoe UI",Calibri,system-ui,sans-serif;
  --mono:Consolas,"Cascadia Mono",ui-monospace,monospace;
  /* Hub colors, light */
  --ground:#EDF1F7; --glow-a:rgba(217,119,6,.16); --glow-b:rgba(91,192,222,.26);
  --surface:rgba(255,255,255,.74); --sheet:#FFFFFF; --fill:#E4EAF3; --line:#C6D1E0;
  --glass:rgba(255,255,255,.62); --glass-line:rgba(58,80,107,.22); --glass-hi:rgba(58,80,107,.12);
  --ink:#0B132B; --muted:#4A5C75; --navy:#1C2541;
  --accent:#D97706; --accent-ink:#8F4E03; --accent-soft:rgba(217,119,6,.14); --on-accent:#0B132B;
  --good:#15627E; --good-soft:#D9EFF6; --warn:#6E4A12; --warn-soft:#F8EBD8; --bad:#8F2D0B; --bad-soft:#FAE3D8;
  --shadow:0 1px 2px rgba(11,19,43,.05),0 14px 30px -24px rgba(11,19,43,.35);
  --pop:0 12px 40px -8px rgba(11,19,43,.35),0 2px 6px rgba(11,19,43,.12);
  --toast-bg:#1C2541; --toast-ink:#FFFFFF;
  --mark-front:#1C2541; --mark-back:#15627E;
}
@media (prefers-color-scheme:dark){
  :root:not([data-theme="light"]){
    color-scheme:dark;
    --ground:#0B132B; --glow-a:rgba(217,119,6,.2); --glow-b:rgba(91,192,222,.17);
    --surface:rgba(28,37,65,.66); --sheet:#141D38; --fill:#28344F; --line:#3A506B;
    --glass:rgba(28,37,65,.55); --glass-line:rgba(159,176,199,.24); --glass-hi:rgba(244,247,251,.1);
    --ink:#EEF3FA; --muted:#A3B3C9; --navy:#F4D6B0;
    --accent:#D97706; --accent-ink:#F0A04B; --accent-soft:rgba(217,119,6,.2); --on-accent:#0B132B;
    --good:#5BC0DE; --good-soft:#17324B; --warn:#F4D6B0; --warn-soft:#352F2B; --bad:#F59A78; --bad-soft:#3A241C;
    --shadow:0 1px 2px rgba(0,0,0,.3),0 16px 34px -24px rgba(0,0,0,.85);
    --pop:0 16px 48px -8px rgba(0,0,0,.7),0 2px 6px rgba(0,0,0,.4);
    --toast-bg:#28344F; --toast-ink:#EEF3FA;
    --mark-front:#EEF3FA; --mark-back:#5FB3C9;
  }
}
:root[data-theme="dark"]{
  color-scheme:dark;
  --ground:#0B132B; --glow-a:rgba(217,119,6,.2); --glow-b:rgba(91,192,222,.17);
  --surface:rgba(28,37,65,.66); --sheet:#141D38; --fill:#28344F; --line:#3A506B;
  --glass:rgba(28,37,65,.55); --glass-line:rgba(159,176,199,.24); --glass-hi:rgba(244,247,251,.1);
  --ink:#EEF3FA; --muted:#A3B3C9; --navy:#F4D6B0;
  --accent:#D97706; --accent-ink:#F0A04B; --accent-soft:rgba(217,119,6,.2); --on-accent:#0B132B;
  --good:#5BC0DE; --good-soft:#17324B; --warn:#F4D6B0; --warn-soft:#352F2B; --bad:#F59A78; --bad-soft:#3A241C;
  --shadow:0 1px 2px rgba(0,0,0,.3),0 16px 34px -24px rgba(0,0,0,.85);
  --pop:0 16px 48px -8px rgba(0,0,0,.7),0 2px 6px rgba(0,0,0,.4);
  --toast-bg:#28344F; --toast-ink:#EEF3FA;
  --mark-front:#EEF3FA; --mark-back:#5FB3C9;
}
*{box-sizing:border-box}
html,body{background:var(--ground)}
body{margin:0;color:var(--ink);font-family:var(--body);font-size:15px;line-height:1.45;-webkit-font-smoothing:antialiased}
.glow{position:fixed;inset:0;z-index:-1;pointer-events:none;
  background:radial-gradient(38rem 26rem at 8% 14%,var(--glow-a),transparent 70%),radial-gradient(44rem 30rem at 96% 4%,var(--glow-b),transparent 70%),radial-gradient(36rem 26rem at 88% 96%,var(--glow-a),transparent 72%)}
:focus-visible{outline:2px solid var(--good);outline-offset:2px}
button,input,select{font:inherit;color:inherit}
button{cursor:pointer}
[hidden]{display:none!important}
kbd{font:600 11.5px/1 var(--mono);padding:3px 6px;border-radius:6px;background:var(--fill);border:1px solid var(--line);color:var(--muted);white-space:nowrap}
.app{display:grid;grid-template-columns:auto minmax(0,1fr);gap:22px;align-items:start;max-width:1560px;margin:0 auto;
  padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px));padding-block:16px 56px}

/* ---- sidebar: glass, folds to a rail ---- */
.side{position:sticky;top:calc(16px + env(safe-area-inset-top,0px));width:236px;display:flex;flex-direction:column;gap:4px;
  padding:14px 12px;border-radius:26px;background:var(--glass);border:1px solid var(--glass-line);box-shadow:var(--shadow);
  -webkit-backdrop-filter:blur(18px) saturate(1.3);backdrop-filter:blur(18px) saturate(1.3);transition:width .22s ease}
.brand{display:flex;align-items:center;gap:10px;padding:2px 4px 10px;position:relative}
.mark{flex:none;width:40px;height:40px;display:block}
.mark .mf{fill:var(--mark-front)} .mark .mb{fill:var(--mark-back)}
.brand b{display:block;font:700 15.5px/1.15 var(--display)}
.brand small{display:block;font-size:12.5px;color:var(--muted)}
.foldbtn{position:absolute;right:-22px;top:9px;width:26px;height:26px;border-radius:50%;border:1px solid var(--glass-line);background:var(--sheet);display:grid;place-items:center;padding:0}
.foldbtn svg{width:13px;height:13px;fill:none;stroke:currentColor;stroke-width:2.2;stroke-linecap:round;stroke-linejoin:round;transition:transform .2s}
.sec{font-size:12px;letter-spacing:.04em;color:var(--muted);padding:12px 10px 3px}
.nl{position:relative;display:flex;align-items:center;gap:11px;min-height:40px;padding:0 11px;border-radius:12px;color:var(--ink);text-decoration:none;font-size:14.5px;border:1px solid transparent;background:none;width:100%;text-align:left}
.nl svg{flex:none;width:19px;height:19px;fill:none;stroke:currentColor;stroke-width:1.7;stroke-linecap:round;stroke-linejoin:round}
.nl:hover{background:var(--glass-hi)}
.nl[aria-current="page"]{background:var(--glass-hi);border-color:var(--glass-line);font-weight:700}
.nl .tag{margin-left:auto;font-size:11px;color:var(--muted);letter-spacing:.02em}
.nl .badge{margin-left:auto}
.badge{min-width:22px;height:20px;padding:0 6px;border-radius:999px;background:var(--fill);font-size:12px;font-weight:700;display:grid;place-items:center;font-variant-numeric:tabular-nums}
.badge.hot{background:var(--ink);color:var(--ground)}
.badge:empty{display:none}
.app.rail .side{width:68px}
.app.rail .brand b,.app.rail .brand small,.app.rail .sec,.app.rail .lbl,.app.rail .nl .tag{display:none}
.app.rail .nl,.app.rail .brand{justify-content:center;padding-inline:0}
.app.rail .foldbtn svg{transform:rotate(180deg)}
.app.rail .badge{position:absolute;top:4px;right:4px;min-width:9px;width:9px;height:9px;padding:0;font-size:0}

/* ---- main ---- */
main{min-width:0;display:flex;flex-direction:column;gap:16px;padding-top:2px}
.bar{display:flex;flex-wrap:wrap;gap:8px 10px;align-items:center;padding:7px 8px 7px 8px;border-radius:18px;background:var(--glass);border:1px solid var(--glass-line);
  -webkit-backdrop-filter:blur(14px);backdrop-filter:blur(14px)}
.bar .sp{flex:1 1 20px}
.ctl{display:inline-flex;align-items:center;gap:8px;min-height:36px;padding:0 12px;border-radius:12px;border:1px solid var(--glass-line);background:var(--sheet);font-size:13.5px;transition:background .12s,border-color .12s}
.ctl:hover{border-color:var(--muted)}
.ctl.ghost{background:none}
.ctl svg{width:16px;height:16px;fill:none;stroke:currentColor;stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round}
.search{flex:1 1 220px;max-width:360px;justify-content:flex-start;color:var(--muted)}
.search kbd{margin-left:auto}
.seg{display:inline-flex;gap:2px;padding:2px;border-radius:12px;background:var(--fill)}
.seg button{border:0;background:none;min-height:32px;padding:0 10px;border-radius:10px;font-size:13px}
.seg button[aria-pressed="true"]{background:var(--sheet);font-weight:700;box-shadow:0 1px 2px rgba(11,19,43,.2)}
.buildpill{display:inline-flex;align-items:center;gap:8px;min-height:36px;padding:0 13px;border-radius:12px;background:var(--accent-soft);color:var(--accent-ink);font-weight:700;font-size:13.5px;border:1px solid transparent}
.buildpill:hover{border-color:var(--accent-ink)}
.view{display:flex;flex-direction:column;gap:16px;min-width:0}
.vh{display:flex;flex-wrap:wrap;gap:6px 14px;align-items:baseline;justify-content:space-between}
.vh h1{font:700 26px/1.15 var(--display);margin:0;letter-spacing:-.015em}
.vh p{margin:4px 0 0;color:var(--muted);font-size:14px}
.link{background:none;border:0;padding:0;color:var(--accent-ink);text-decoration:underline;text-underline-offset:2px}
.mine{display:flex;flex-wrap:wrap;gap:4px 12px;align-items:center;font-size:13.5px;color:var(--muted);margin-top:-8px}
.mine:empty{display:none}
.mine .who{display:inline-flex;align-items:center;gap:6px;padding:2px 10px;border-radius:999px;background:var(--accent-soft);color:var(--accent-ink);font-weight:700}

/* ---- status shapes (Linear): the shape carries the state, the colour only backs it up ---- */
.si{display:inline-block;flex:none;width:16px;height:16px;vertical-align:-3px}
.si svg{display:block;width:16px;height:16px;fill:none;stroke:currentColor;stroke-width:1.7;stroke-linecap:round;stroke-linejoin:round}
.k-ready{color:var(--accent-ink)} .k-building{color:var(--accent-ink)} .k-outputs{color:var(--good)}
.k-attention{color:var(--warn)} .k-blocked{color:var(--bad)} .k-checking{color:var(--muted)}
.k-building svg .spin{transform-origin:8px 8px}
.k-idle{color:var(--muted)}
/* Nothing moves unless a build is running or queued: `busy` is set on <body> by paintBusy() and nowhere else. */
.busy .k-building svg .spin{animation:spin 1.1s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.35}}
.dotp{width:8px;height:8px;border-radius:50%;background:var(--accent)}
.busy .dotp{animation:pulse 1.4s ease-in-out infinite}

/* ---- KPI tiles double as the filter ---- */
.kpis{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:10px}
.kpi{display:flex;flex-direction:column;gap:2px;padding:12px 14px;border-radius:14px;border:1px solid var(--glass-line);background:var(--surface);box-shadow:var(--shadow);text-align:left;min-width:0;
  -webkit-backdrop-filter:blur(14px);backdrop-filter:blur(14px);transition:transform .12s,border-color .12s}
.kpi:hover{border-color:var(--muted);transform:translateY(-1px)}
.kpi[aria-pressed="true"]{border-color:var(--ink);box-shadow:0 0 0 1px var(--ink)}
.kpi .k{display:flex;align-items:center;gap:7px;font-size:13px;color:var(--muted)}
.kpi .v{font:700 28px/1.1 var(--display);font-variant-numeric:tabular-nums}
.kpi .n{font-size:12.5px;color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}

.split{display:grid;grid-template-columns:minmax(360px,.95fr) minmax(0,1.5fr);gap:14px;align-items:start}
.card{background:var(--surface);border:1px solid var(--glass-line);border-radius:18px;box-shadow:var(--shadow);min-width:0;
  -webkit-backdrop-filter:blur(14px);backdrop-filter:blur(14px)}
.card>header{display:flex;flex-wrap:wrap;gap:8px 12px;align-items:center;justify-content:space-between;padding:14px 16px 8px}
.card h2{margin:0;font:700 16px var(--display)}
.card .sub{margin:0;font-size:13px;color:var(--muted)}

/* ---- client list: dense rows ---- */
.lhead{display:grid;gap:8px;padding:12px 12px 8px;border-bottom:1px solid var(--line)}
.lhead .row1{display:flex;gap:8px;align-items:center}
.lhead select{flex:1;min-height:34px;padding:0 8px;border-radius:10px;border:1px solid var(--line);background:var(--sheet)}
.lhead .find{display:flex;align-items:center;gap:8px;min-height:34px;padding:0 10px;border-radius:10px;border:1px solid var(--line);background:var(--sheet)}
.lhead .find svg{width:15px;height:15px;fill:none;stroke:var(--muted);stroke-width:1.8;stroke-linecap:round}
.lhead .find input{flex:1;border:0;background:none;outline:0;min-width:0}
.lhead .find:focus-within{border-color:var(--accent-ink);box-shadow:0 0 0 2px var(--accent-soft)}
.filt{display:flex;align-items:center;gap:8px;font-size:12.5px;color:var(--muted)}
.filt .x{border:1px solid var(--line);background:var(--sheet);border-radius:999px;padding:1px 9px;font-size:12px}
.list{max-height:calc(100vh - 360px);min-height:240px;overflow:auto;padding:4px 6px 8px}
.gh{position:sticky;top:0;z-index:1;padding:9px 8px 4px;font-size:11.5px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);background:linear-gradient(var(--sheet) 70%,transparent)}
.row{display:grid;grid-template-columns:20px 3.2em minmax(0,1fr) auto auto;gap:8px;align-items:center;width:100%;min-height:40px;padding:4px 8px;border:0;background:none;border-radius:10px;text-align:left;transition:background .1s}
:root[data-density="compact"] .row{min-height:31px;padding-block:1px}
.row:hover{background:var(--glass-hi)}
.row[aria-current="true"]{background:var(--fill);box-shadow:inset 0 0 0 1px var(--glass-line)}
.row .rid{font:12.5px var(--mono);color:var(--muted)}
.row .rnm{font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.pd{display:inline-flex;gap:3px}
.pdot{width:7px;height:7px;border-radius:50%;background:var(--line)}
.pdot.ars{background:var(--navy)} .pdot.ics{background:var(--accent)} .pdot.mrpc{background:var(--good)} .pdot.cp{background:var(--warn)}
.chip{display:inline-flex;align-items:center;gap:5px;font-size:12px;font-weight:600;padding:1px 8px;border-radius:999px;white-space:nowrap;background:var(--fill);color:var(--muted)}
.chip.k-ready{background:var(--accent-soft);color:var(--accent-ink)} .chip.k-building{background:var(--accent-soft);color:var(--accent-ink)}
.chip.k-outputs{background:var(--good-soft);color:var(--good)} .chip.k-attention{background:var(--warn-soft);color:var(--warn)}
.chip.k-blocked{background:var(--bad-soft);color:var(--bad)}
.row .chip{max-width:150px;overflow:hidden;text-overflow:ellipsis}
.sk{display:block;border-radius:8px;background:linear-gradient(90deg,var(--fill) 25%,var(--glass-hi) 50%,var(--fill) 75%);background-size:200% 100%;animation:shimmer 1.3s linear infinite}
@keyframes shimmer{to{background-position:-200% 0}}
.legend{display:flex;gap:12px;padding:4px 10px 0;font-size:11.5px;color:var(--muted)}
.legend span{display:inline-flex;align-items:center;gap:5px}

/* ---- detail ---- */
#detail{position:sticky;top:16px;min-height:300px}
.dh{display:flex;flex-wrap:wrap;gap:4px 12px;align-items:center;padding:16px 18px 6px}
.dh h2{font:700 22px/1.15 var(--display);margin:0;letter-spacing:-.01em}
.dh .meta{flex-basis:100%;color:var(--muted);font-size:13px;display:flex;flex-wrap:wrap;gap:4px 12px;align-items:center}
.back{display:none}
.pres{display:grid;gap:12px;padding:10px 14px 16px}
.pc{border:1px solid var(--line);border-radius:14px;background:var(--sheet);padding:12px 14px;display:grid;gap:8px}
.pc.stopc{border-color:var(--bad)}
.pch{display:flex;flex-wrap:wrap;gap:8px 12px;align-items:center}
.pch h3{margin:0;font:700 15px var(--display);display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.pch .mix{font:400 12.5px var(--body);color:var(--muted)}
.pch .act{margin-left:auto;display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.why{font-size:12px;color:var(--muted)}
.fact{margin:0;font-size:13.5px;color:var(--muted)} .fact b{color:var(--ink)}
.fact .err{color:var(--bad)}
.btn{display:inline-flex;align-items:center;gap:8px;min-height:36px;padding:0 15px;border-radius:12px;border:1px solid var(--line);background:var(--sheet);font-weight:600;font-size:14px;transition:transform .12s,box-shadow .12s,filter .12s}
.btn:hover{border-color:var(--muted)}
.btn.primary{background:var(--accent);color:var(--on-accent);border-color:transparent;box-shadow:0 1px 2px rgba(0,0,0,.2),0 6px 16px -8px var(--accent)}
.btn.primary:hover{filter:brightness(1.06);transform:translateY(-1px)}
.btn.primary:active{transform:translateY(0)}
.btn.warn{background:var(--warn-soft);color:var(--warn);border-color:var(--warn)}
.btn:disabled{opacity:.55;cursor:not-allowed;transform:none;filter:none}
.btn kbd{background:rgba(0,0,0,.1);border-color:transparent;color:inherit}
.checks{list-style:none;margin:0;padding:0;display:grid;gap:5px;font-size:13.5px}
.checks li{display:grid;grid-template-columns:18px 1fr;gap:8px;align-items:start}
.checks .t{margin-top:2px}
.ck-ok{color:var(--good)} .ck-warn,.ck-ask{color:var(--warn)} .ck-stop{color:var(--bad)}
details.fold summary{cursor:pointer;font-size:12.5px;color:var(--muted);list-style:none}
details.fold summary::-webkit-details-marker{display:none}
details.fold summary::before{content:"\25B8 ";}
details.fold[open] summary::before{content:"\25BE ";}
.prog{border-top:1px dashed var(--line);padding-top:10px;display:grid;gap:8px}
.prog h4{margin:0;font-size:12.5px;letter-spacing:.04em;color:var(--muted);font-weight:700;text-transform:uppercase}
.steps{list-style:none;margin:0;padding:0;display:grid;gap:6px;font-size:13.5px}
.steps li{display:flex;gap:9px;align-items:center}
.steps .tm{margin-left:auto;color:var(--muted);font-size:12.5px;font-variant-numeric:tabular-nums}
.steps .sd{width:10px;height:10px;border-radius:50%;border:2px solid var(--line);flex:none}
.steps .sd.done{background:var(--good);border-color:var(--good)} .steps .sd.now{border-color:var(--accent);background:var(--accent)}
.busy .steps .sd.now{animation:pulse 1.2s ease-in-out infinite}
.result{border-radius:12px;padding:12px 14px;display:grid;gap:6px}
.result.good{background:var(--good-soft);color:var(--ink)} .result.bad{background:var(--bad-soft)}
.result h4{margin:0;font:700 15px var(--display);text-transform:none;letter-spacing:0;color:var(--ink)}
.result .nm{font:12.5px var(--mono);color:var(--muted);word-break:break-all}
.result ul{margin:0;padding-left:18px;font-size:13px}
.pop{animation:pop .45s cubic-bezier(.2,1.4,.4,1)}
@keyframes pop{0%{transform:scale(.96);opacity:0}100%{transform:none;opacity:1}}

/* waiting on you, the right pane's first state */
.wait{display:grid;gap:0;padding:4px 8px 12px}
.wi{display:grid;grid-template-columns:20px minmax(0,1fr) auto;gap:10px;align-items:center;padding:9px 8px;border-radius:10px;border:0;background:none;text-align:left;width:100%}
.wi:hover{background:var(--glass-hi)}
.wi b{font-weight:600} .wi small{display:block;color:var(--muted);font-size:12.5px}
.hint{display:flex;flex-wrap:wrap;gap:6px 16px;padding:0 16px 16px;font-size:12.5px;color:var(--muted)}
.hint span{display:inline-flex;gap:6px;align-items:center}
.allgood{padding:18px 16px;display:grid;gap:4px;justify-items:start}
.allgood b{font:700 16px var(--display)}

/* ---- popovers, palette, toasts ---- */
.menu{position:absolute;z-index:60;min-width:200px;background:var(--sheet);border:1px solid var(--glass-line);border-radius:14px;box-shadow:var(--pop);padding:6px}
.menu h4{margin:6px 10px 4px;font-size:11.5px;letter-spacing:.06em;text-transform:uppercase;color:var(--muted)}
.menu button,.menu a{display:flex;align-items:center;gap:8px;width:100%;min-height:34px;padding:0 10px;border:0;border-radius:9px;background:none;text-align:left;color:var(--ink);text-decoration:none;font-size:14px}
.menu button:hover,.menu a:hover{background:var(--fill)}
.menu [aria-current="true"]{font-weight:700;background:var(--accent-soft)}
.menu .nw{display:grid;gap:2px;min-height:0;padding:8px 10px;align-items:start}
.menu .nw small{color:var(--muted);font-size:12.5px;font-weight:400}
dialog{border:1px solid var(--glass-line);border-radius:18px;background:var(--sheet);color:var(--ink);box-shadow:var(--pop);padding:0;max-width:calc(100vw - 24px)}
dialog::backdrop{background:rgba(11,19,43,.38);-webkit-backdrop-filter:blur(3px);backdrop-filter:blur(3px)}
#pal{width:min(620px,calc(100vw - 24px));margin-top:12vh;overflow:hidden}
#pal input{width:100%;border:0;border-bottom:1px solid var(--line);background:none;outline:0;padding:16px 18px;font-size:17px}
#pal ul{list-style:none;margin:0;padding:6px;max-height:min(52vh,420px);overflow:auto}
#pal li button{display:flex;align-items:center;gap:10px;width:100%;min-height:42px;padding:0 12px;border:0;border-radius:10px;background:none;text-align:left}
#pal li button[aria-selected="true"]{background:var(--fill);box-shadow:inset 0 0 0 1px var(--glass-line)}
#pal li small{margin-left:auto;color:var(--muted);font-size:12px}
#pal .gt{padding:8px 12px 2px;font-size:11.5px;letter-spacing:.06em;text-transform:uppercase;color:var(--muted)}
#pal .foot{display:flex;gap:14px;padding:9px 14px;border-top:1px solid var(--line);font-size:12px;color:var(--muted)}
#keys{width:min(520px,calc(100vw - 24px));padding:18px 20px}
#keys h2{margin:0 0 10px;font:700 18px var(--display)}
#keys dl{display:grid;grid-template-columns:auto 1fr;gap:8px 16px;margin:0;font-size:14px;align-items:center}
#keys dt{display:flex;gap:4px} #keys dd{margin:0;color:var(--muted)}
#toasts{position:fixed;right:max(16px,env(safe-area-inset-right,0px));bottom:calc(18px + env(safe-area-inset-bottom,0px));display:grid;gap:8px;z-index:90;justify-items:end}
.toast{display:flex;gap:10px;align-items:center;max-width:min(420px,calc(100vw - 32px));padding:10px 14px;border-radius:14px;background:var(--toast-bg);color:var(--toast-ink);box-shadow:var(--pop);font-size:14px;animation:pop .3s ease}
.toast.bad{border-left:4px solid var(--bad)} .toast.good{border-left:4px solid var(--good)}
.toast button{margin-left:6px;border:0;background:none;color:inherit;text-decoration:underline;padding:0}
#confetti{position:fixed;inset:0;pointer-events:none;z-index:95}
.tabbar{display:none}
.empty{padding:24px 18px;color:var(--muted)}

@media (max-width:1180px){.split{grid-template-columns:1fr}#detail{position:static}.list{max-height:none}}
@media (max-width:980px){.kpis{grid-template-columns:repeat(3,minmax(0,1fr))}}
@media (max-width:820px){
  .app{grid-template-columns:1fr;gap:12px;padding-block:10px 96px}
  .side{display:none}
  .opt{display:none}
  .kpis{display:flex;overflow-x:auto;scroll-snap-type:x proximity;padding-bottom:4px;margin-inline:-2px}
  .kpi{flex:0 0 138px;scroll-snap-align:start}
  .search kbd,.btn kbd,#detail .dh kbd,[data-act=close]{display:none}
  .tabbar{display:flex;position:fixed;left:max(10px,env(safe-area-inset-left,0px));right:max(10px,env(safe-area-inset-right,0px));bottom:calc(10px + env(safe-area-inset-bottom,0px));z-index:50;
    gap:2px;padding:6px;border-radius:22px;background:var(--glass);border:1px solid var(--glass-line);box-shadow:var(--pop);-webkit-backdrop-filter:blur(18px);backdrop-filter:blur(18px)}
  .tabbar a{flex:1;display:grid;justify-items:center;gap:2px;min-height:48px;align-content:center;border-radius:16px;color:var(--ink);text-decoration:none;font-size:11px}
  .tabbar a svg{width:20px;height:20px;fill:none;stroke:currentColor;stroke-width:1.7;stroke-linecap:round;stroke-linejoin:round}
  .tabbar a[aria-current="page"]{background:var(--glass-hi);font-weight:700}
  .search{max-width:none}
  .sheetmode #detail{position:fixed;inset:0;z-index:70;border-radius:0;overflow:auto;background:var(--sheet);padding-top:env(safe-area-inset-top,0px)}
  .sheetmode .back{display:inline-flex}
  .row{grid-template-columns:20px 3em minmax(0,1fr) auto}
  .row .pd{display:none}
}
@media (prefers-reduced-motion:reduce){*,*::before,*::after{animation-duration:.01ms!important;animation-iteration-count:1!important;transition-duration:.01ms!important}}
/*__TAB_CSS__*/
</style>
</head>
<body>
<div class="glow"></div>
<div class="app" id="app">
  <aside class="side" aria-label="Sheila">
    <div class="brand">
      __MARK__
      <div class="lbl"><b>CSM Sheila</b><small>__VERSION__</small></div>
      <button class="foldbtn" id="fold" aria-label="Fold the sidebar" title="Fold the sidebar"><svg viewBox="0 0 16 16"><path d="M10 3 5 8l5 5"/></svg></button>
    </div>
    <nav class="nav" aria-label="Views">
      <a class="nl" data-tab="decks" href="#" aria-current="page"><svg viewBox="0 0 20 20"><rect x="3" y="3" width="6" height="6" rx="1.5"/><rect x="11" y="3" width="6" height="6" rx="1.5"/><rect x="3" y="11" width="6" height="6" rx="1.5"/><rect x="11" y="11" width="6" height="6" rx="1.5"/></svg><span class="lbl">Decks</span><span class="badge hot" id="b-attn" title="Needs attention or blocked"></span></a>
      <a class="nl" data-tab="lift" href="#lift" data-tip="Lift Matrix"><svg viewBox="0 0 20 20"><path d="M3 16h14M5 16V9m5 7V4m5 12v-5"/></svg><span class="lbl">Lift Matrix</span></a>
      <a class="nl" data-tab="issues" href="#issues" data-tip="Data Issues"><svg viewBox="0 0 20 20"><path d="M10 3 2.5 16h15L10 3Zm0 5v4m0 2.5v.01"/></svg><span class="lbl">Data Issues</span><span class="badge hot" id="b-issues" title="Open data issues"></span></a>
      <a class="nl" data-tab="votes" href="#votes" data-tip="Slide Review"><svg viewBox="0 0 20 20"><rect x="3" y="4" width="14" height="10" rx="2"/><path d="m7 17 3-3 3 3"/></svg><span class="lbl">Slide Review</span></a>
      <a class="nl" data-tab="reported" href="#reported" data-tip="Feedback"><svg viewBox="0 0 20 20"><path d="M4 4h12v9H9l-4 3v-3H4V4Z"/></svg><span class="lbl">Feedback</span></a>
    </nav>
    <div class="sec">Reference</div>
    <nav class="nav">
      <button class="nl small" id="news-btn" data-tip="What's new"><svg viewBox="0 0 20 20"><path d="m10 3 1.8 4.2L16 9l-4.2 1.8L10 15l-1.8-4.2L4 9l4.2-1.8L10 3Z"/></svg><span class="lbl">What's new</span></button>
      <a class="nl small" href="/changelog" target="_blank" rel="noopener" data-tip="Change log"><svg viewBox="0 0 20 20"><path d="M5 3h10v14H5V3Zm3 4h4m-4 3h4m-4 3h2"/></svg><span class="lbl">Change log</span></a>
    </nav>
  </aside>
  <main>
    <div class="bar" role="toolbar" aria-label="Page controls">
      <button class="ctl search" id="palbtn" aria-label="Search clients and actions"><svg viewBox="0 0 16 16"><circle cx="7" cy="7" r="4.5"/><path d="m10.5 10.5 3 3"/></svg>Search…<kbd>Ctrl K</kbd></button>
      <span class="sp"></span>
      <button class="buildpill" id="buildpill" hidden></button>
      <span class="seg opt" role="group" aria-label="Row density"><button id="dn-c" aria-pressed="true">Comfortable</button><button id="dn-k" aria-pressed="false">Compact</button></span>
      <button class="ctl" id="reportbtn" title="Report a problem with Sheila or a deck"><svg viewBox="0 0 16 16"><path d="M3 3h10v7H8l-3 2.5V10H3V3Z"/></svg><span class="opt">Report</span></button>
      <button class="ctl" id="night" aria-label="Switch between night and day"><svg viewBox="0 0 16 16"><path d="M13 9.5A5.5 5.5 0 0 1 6.5 3a5.5 5.5 0 1 0 6.5 6.5Z"/></svg><span id="night-l">Night</span></button>
      <button class="ctl" id="period" aria-haspopup="menu" aria-expanded="false"></button>
    </div>
    <section class="view" id="v-decks" aria-label="Decks">
      <div class="vh"><div><h1>Decks</h1><p id="sub">Loading this cycle…</p></div></div>
      <div class="mine" id="mine"></div>
      <div class="kpis" id="kpis" role="group" aria-label="Filter by status"></div>
      <div class="split" id="split">
        <section class="card" aria-label="Clients">
          <div class="lhead">
            <div class="row1"><select id="csm" aria-label="CSM"><option value="">All CSMs</option></select></div>
            <label class="find"><svg viewBox="0 0 16 16"><circle cx="7" cy="7" r="4.5"/><path d="m10.5 10.5 3 3"/></svg><input id="q" type="search" placeholder="Name or number" autocomplete="off" aria-label="Find a client"><kbd>/</kbd></label>
            <div class="filt" id="filt"></div>
          </div>
          <div class="list" id="list" role="list" aria-live="polite"></div>
        </section>
        <section class="card" id="detail" aria-label="Client" aria-live="polite"></section>
      </div>
    </section>
<!--__TAB_VIEWS__-->
  </main>
</div>
<nav class="tabbar" aria-label="Views">
  <a data-tab="decks" href="#" aria-current="page"><svg viewBox="0 0 20 20"><rect x="3" y="3" width="6" height="6" rx="1.5"/><rect x="11" y="3" width="6" height="6" rx="1.5"/><rect x="3" y="11" width="6" height="6" rx="1.5"/><rect x="11" y="11" width="6" height="6" rx="1.5"/></svg>Decks</a>
  <a data-tab="lift" href="#lift"><svg viewBox="0 0 20 20"><path d="M3 16h14M5 16V9m5 7V4m5 12v-5"/></svg>Lift</a>
  <a data-tab="issues" href="#issues"><svg viewBox="0 0 20 20"><path d="M10 3 2.5 16h15L10 3Zm0 5v4m0 2.5v.01"/></svg>Issues</a>
  <a data-tab="votes" href="#votes"><svg viewBox="0 0 20 20"><rect x="3" y="4" width="14" height="10" rx="2"/><path d="m7 17 3-3 3 3"/></svg>Review</a>
  <a data-tab="reported" href="#reported"><svg viewBox="0 0 20 20"><path d="M4 4h12v9H9l-4 3v-3H4V4Z"/></svg>Feedback</a>
</nav>
<dialog id="pal" aria-label="Search and actions"><input id="pq" type="text" placeholder="Search a client, or type an action…" autocomplete="off" aria-label="Search"><ul id="pl" role="listbox"></ul><div class="foot"><span><kbd>↑</kbd> <kbd>↓</kbd> move</span><span><kbd>Enter</kbd> open</span><span><kbd>Esc</kbd> close</span></div></dialog>
<dialog id="keys"><h2>Keyboard shortcuts</h2><dl id="keyl"></dl><p style="margin:14px 0 0;text-align:right"><button class="btn" id="keyx">Close</button></p></dialog>
<div id="toasts" role="status" aria-live="polite"></div>
<canvas id="confetti"></canvas>
<script>
const TOKEN = "__TOKEN__";
const ME = __ME__;          // who the server says is asking: {csm, how, note}; csm is null unless exactly one CSM matched
const $ = (s, r = document) => r.querySelector(s), $$ = (s, r = document) => [...r.querySelectorAll(s)];
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const store = (k, v) => { try { localStorage.setItem(k, v); } catch (e) {} };
const recall = k => { try { return localStorage.getItem(k); } catch (e) { return null; } };
async function api(path, opts = {}) {
  const r = await fetch(path, {...opts, headers: {"X-Token": TOKEN, "Content-Type": "application/json", ...(opts.headers || {})}});
  const body = await r.json().catch(() => ({}));
  if (!r.ok && r.status !== 409) throw new Error(body.error || ("HTTP " + r.status));
  return {status: r.status, body};
}

// ------------------------------------------------------------ status shapes
const ICONS = {
  ready:     '<svg viewBox="0 0 16 16"><circle cx="8" cy="8" r="6"/><circle cx="8" cy="8" r="2" fill="currentColor" stroke="none"/></svg>',
  building:  '<svg viewBox="0 0 16 16"><circle cx="8" cy="8" r="6" opacity=".35"/><path class="spin" d="M8 2a6 6 0 0 1 6 6"/></svg>',
  outputs:   '<svg viewBox="0 0 16 16"><circle cx="8" cy="8" r="6.2" fill="currentColor" stroke="none"/><path d="m5.2 8.2 2 2 3.6-4" stroke="#fff"/></svg>',
  attention: '<svg viewBox="0 0 16 16"><path d="M8 2.2 14 13H2L8 2.2Z"/><path d="M8 6.5v3M8 11.3v.01"/></svg>',
  blocked:   '<svg viewBox="0 0 16 16"><circle cx="8" cy="8" r="6"/><path d="M5 8h6"/></svg>',
  idle:      '<svg viewBox="0 0 16 16"><circle cx="8" cy="8" r="6"/></svg>',
  checking:  '<svg viewBox="0 0 16 16"><circle cx="8" cy="8" r="6" stroke-dasharray="2.4 2.4"/></svg>',
  ok:        '<svg viewBox="0 0 16 16"><path d="m3.5 8.3 3 3 6-6.6"/></svg>',
  warn:      '<svg viewBox="0 0 16 16"><path d="M8 2.2 14 13H2L8 2.2Z"/><path d="M8 6.5v3M8 11.3v.01"/></svg>',
  stop:      '<svg viewBox="0 0 16 16"><circle cx="8" cy="8" r="6"/><path d="m5.8 5.8 4.4 4.4m0-4.4-4.4 4.4"/></svg>',
};
const si = k => `<span class="si k-${k}" aria-hidden="true">${ICONS[k]}</span>`;
const KINDS = [["ready", "Ready", "to build"], ["building", "Building", "now"], ["outputs", "In Outputs", "this cycle"], ["attention", "Needs attention", "failed or expired"], ["blocked", "Blocked", "waiting on inputs"]];
const WORD = Object.fromEntries(KINDS.map(([k, w]) => [k, w]));

let CLIENTS = [], PERIOD = null, PERIODS = [], CYCLE_NOW = null, AGE = null, REFRESHING = false;
let QUEUE = {building: null, queued: []}, CUR = null, S = null, JOB = null, ARMED = null;
let ME_APPLIED = false, FILTER = "", CURSOR = null, poller = null, statusTimer = null, clientsTimer = null, openTimer = null, LOADED = false;

function kindOf(c) {
  const place = QUEUE.queued.indexOf(c.id);
  if (QUEUE.building === c.id) return {k: "building", label: "Building"};
  if (place >= 0) return {k: "building", label: "Queued #" + (place + 1)};
  if (c.error) return {k: "attention", label: "Last build failed", short: "Failed"};
  if (c.lift_expired) return {k: "attention", label: "Lift Matrix expired", short: "Lift expired"};
  if ((c.decks || []).length) return {k: "outputs", label: "In Outputs"};
  if (c.blocked) return {k: "blocked", label: "Blocked · " + c.blocked, short: "Blocked"};
  if (c.ready) return {k: "ready", label: "Ready"};
  return {k: "checking", label: "Checking"};
}

// ------------------------------------------------------------ list
const DOT_ORDER = ["ARS", "ICS", "MRPC", "CP"], DOT_NAME = {ARS: "ARS", ICS: "ICS", MRPC: "MRPC", CP: "CashPlease"};
const pdots = c => { const cov = new Set(c.covered || []);
  return `<span class="pd" title="${esc(DOT_ORDER.filter(p => cov.has(p)).map(p => DOT_NAME[p]).join(" · ") || "no program")}">` +
    DOT_ORDER.map(p => `<span class="pdot${cov.has(p) ? " " + p.toLowerCase() : ""}"></span>`).join("") + "</span>"; };

function visible() {
  const csm = $("#csm").value, q = $("#q").value.trim().toLowerCase();
  return CLIENTS.filter(c => (!csm || c.csm === csm) && (!q || c.id.includes(q) || (c.name || "").toLowerCase().includes(q)) && (!FILTER || kindOf(c).k === FILTER));
}

function running() { return !!(QUEUE.building || QUEUE.queued.length); }
// The one switch for every animation tied to building: on while a build runs or waits (or the open client's job has not finished), off otherwise.
function paintBusy() { document.body.classList.toggle("busy", running() || !!(JOB && !JOB.done)); }

function renderKpis() {
  paintBusy();
  const csm = $("#csm").value, base = CLIENTS.filter(c => !csm || c.csm === csm);
  const n = {}; for (const [k] of KINDS) n[k] = 0;
  for (const c of base) { const k = kindOf(c).k; if (n[k] !== undefined) n[k]++; }
  const queued = QUEUE.queued.length;
  const sub = {building: QUEUE.building ? "now" + (queued ? " · " + queued + " queued" : "") : "nothing running"};
  $("#kpis").innerHTML = KINDS.map(([k, w, s]) => `<button class="kpi" data-kind="${k}" aria-pressed="${FILTER === k}" title="Show only: ${esc(w)}">
      <span class="k">${si(k === "building" && !running() ? "idle" : k)}${esc(w)}</span><span class="v">${LOADED ? n[k] : "–"}</span><span class="n">${esc(sub[k] || s)}</span></button>`).join("");
  const bad = n.attention + n.blocked;
  const b = $("#b-attn"); b.textContent = bad ? String(bad) : "";
}

function renderList() {
  renderKpis();
  const csm = $("#csm").value, rows = visible();
  $("#filt").innerHTML = !LOADED ? "Loading clients…" : FILTER ? `Showing <b>${esc(WORD[FILTER])}</b> <button class="x" id="clearf">Clear ✕</button>` : `${rows.length} client${rows.length === 1 ? "" : "s"}`;
  if (!LOADED) { $("#list").innerHTML = Array.from({length: 9}, () => `<div class="row"><span class="sk" style="width:16px;height:16px"></span><span class="sk" style="width:38px;height:12px"></span><span class="sk" style="width:${50 + Math.random() * 40 | 0}%;height:14px"></span><span></span><span class="sk" style="width:70px;height:16px"></span></div>`).join(""); return; }
  let html = '<div class="legend">' + DOT_ORDER.map(p => `<span><span class="pdot ${p.toLowerCase()}"></span>${DOT_NAME[p]}</span>`).join("") + "</div>", last = null;
  const multi = new Set(CLIENTS.map(c => c.csm)).size > 1;
  for (const c of rows) {
    if (!csm && multi && c.csm !== last) { html += `<div class="gh">${esc(c.csm)}</div>`; last = c.csm; }
    const k = kindOf(c);
    html += `<button class="row" role="listitem" data-id="${esc(c.id)}" aria-current="${(CUR || CURSOR) === c.id}">${si(k.k)}<span class="rid">${esc(c.id)}</span><span class="rnm">${esc(c.name)}</span>${pdots(c)}<span class="chip k-${k.k}" title="${esc(k.label)}">${esc(k.short || k.label)}</span></button>`;
  }
  $("#list").innerHTML = rows.length ? html : `<p class="empty">No clients match.</p>`;
}

// The chip above the list: whose clients it shows, and the way to the others. Said quietly when nobody was recognised.
function paintMine() {
  const el = $("#mine"), sel = $("#csm").value;
  if (!LOADED) { el.innerHTML = ""; return; }
  if (!ME.csm) { el.innerHTML = `<span>${esc(ME.note || "Couldn't tell which CSM you are, so every client is shown.")}</span>`; return; }
  if (![...$("#csm").options].some(o => o.value === ME.csm)) { el.innerHTML = `<span>${esc(ME.csm)} has no clients this cycle, so every client is shown.</span>`; return; }
  const mine = `<button class="link" data-act="mycsm">Show ${esc(ME.csm)}'s</button>`, all = `<button class="link" data-act="allcsm">Show all</button>`;
  if (sel === ME.csm) el.innerHTML = `<span class="who">Showing ${esc(ME.csm)}'s clients</span>${all}`;
  else if (!sel) el.innerHTML = `<span>Showing every CSM's clients</span>${mine}`;
  else el.innerHTML = `<span class="who">Showing ${esc(sel)}'s clients</span>${mine}${all}`;
}

function ago(sec) { return sec == null ? "" : sec < 60 ? "just now" : sec < 3600 ? Math.round(sec / 60) + " min ago" : Math.round(sec / 3600) + " h ago"; }

function applyClients(body) {
  CLIENTS = body.clients || []; PERIOD = body.period; AGE = body.age_seconds; REFRESHING = !!body.refreshing; LOADED = true;
  if (body.periods) PERIODS = body.periods; if (body.cycle_now) CYCLE_NOW = body.cycle_now;
  const csms = [...new Set(CLIENTS.map(c => c.csm))], keep = $("#csm").value;
  $("#csm").innerHTML = `<option value="">All CSMs</option>` + csms.map(c => `<option>${esc(c)}</option>`).join("");
  // First list: the person's own CSM when the server knew who they are, else what they last picked. Later lists keep the choice.
  const want = ME_APPLIED ? keep : ME.csm && csms.includes(ME.csm) ? ME.csm : (recall("ars-builder-csm") || keep);
  if (want && csms.includes(want)) $("#csm").value = want;
  ME_APPLIED = true;
  paintPeriod(); renderList(); paintMine();
  $("#sub").innerHTML = `${esc(PERIOD || "No period")} · list as of ${esc(ago(AGE))}${REFRESHING ? ", updating…" : ""} · <button class="link" id="relist">Refresh</button>`;
  if (!CUR) renderOverview();
}

async function loadClients(fresh) {
  clearTimeout(clientsTimer);
  let wait = 60000;
  try {
    const {body} = await api("/api/clients" + (fresh ? "?fresh=1" : ""));
    applyClients(body);
    wait = (body.refreshing || fresh) ? 2500 : body.lift_pending ? 8000 : 60000;
  } catch (e) {
    $("#list").innerHTML = `<p class="empty">Couldn't load clients: ${esc(e.message)}. Check the VPN and reload.</p>`; wait = 15000;
  } finally { clearTimeout(clientsTimer); clientsTimer = setTimeout(() => loadClients(), wait); }
}

async function pollQueue() {
  try {
    const {body} = await api("/api/queue");
    const before = JSON.stringify(QUEUE);
    QUEUE = {building: body.building || null, queued: body.queued || []};
    if (before !== JSON.stringify(QUEUE)) {
      const was = JSON.parse(before);
      if (was.building && was.building !== QUEUE.building) {
        loadClients();
        if (CUR !== was.building) toast(`The build for ${was.building} finished. Open it to see how it went.`, "", 6000);
      } else renderList();
      paintBuildPill();
    }
  } catch (e) {}
}

let buildSince = null;
function paintBuildPill() {
  const b = $("#buildpill");
  paintBusy();
  if (!QUEUE.building) { b.hidden = true; buildSince = null; return; }
  if (!buildSince) buildSince = Date.now();
  const s = Math.round((Date.now() - buildSince) / 1000), q = QUEUE.queued.length;
  b.hidden = false;
  b.innerHTML = `<span class="dotp"></span>Building ${esc(QUEUE.building)} · ${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}${q ? " · +" + q : ""}`;
  b.onclick = () => openClient(QUEUE.building);
}

// ------------------------------------------------------------ cycle menu, what's new
function paintPeriod() {
  const back = PERIOD && CYCLE_NOW && PERIOD !== CYCLE_NOW;
  $("#period").innerHTML = `<svg viewBox="0 0 16 16"><rect x="2.5" y="3.5" width="11" height="10" rx="2"/><path d="M2.5 7h11M5.5 2v3m5-3v3"/></svg>${PERIOD ? "Cycle " + esc(PERIOD) : LOADED ? "No period" : "Cycle…"}${back ? " · past" : ""}`;
}
function closeMenus() { $$(".menu").forEach(m => m.remove()); $("#period").setAttribute("aria-expanded", "false"); }
function menuAt(anchor, html, id) {
  closeMenus();
  const m = document.createElement("div"); m.className = "menu"; m.id = id; m.innerHTML = html; document.body.appendChild(m);
  const r = anchor.getBoundingClientRect(), mw = m.offsetWidth;
  m.style.top = (window.scrollY + r.bottom + 6) + "px";
  m.style.left = Math.max(8, Math.min(window.scrollX + r.right - mw, window.scrollX + innerWidth - mw - 8)) + "px";
  if (anchor.id === "news-btn") m.style.left = Math.max(8, window.scrollX + r.right + 10) + "px", m.style.top = (window.scrollY + r.top) + "px";
  setTimeout(() => document.addEventListener("click", function off(ev) { if (!ev.target.closest(".menu")) { closeMenus(); document.removeEventListener("click", off); } }), 0);
  return m;
}
function openCycles() {
  if ($("#cycles")) return closeMenus();
  const list = PERIODS.length ? PERIODS : (PERIOD ? [PERIOD] : []);
  const m = menuAt($("#period"), "<h4>Cycle</h4>" + list.map(p => `<button data-cycle="${esc(p)}" aria-current="${p === PERIOD}">${esc(p)}${p === CYCLE_NOW ? ' <small style="color:var(--muted)">· this month</small>' : ""}</button>`).join(""), "cycles");
  $("#period").setAttribute("aria-expanded", "true");
  m.addEventListener("click", ev => { const b = ev.target.closest("[data-cycle]"); if (b) pickCycle(b.dataset.cycle); });
}
async function pickCycle(period) {
  closeMenus();
  try {
    const {body} = await api("/api/cycle", {method: "POST", body: JSON.stringify({period})});
    PERIOD = body.period; PERIODS = body.periods || PERIODS; CYCLE_NOW = body.cycle_now || CYCLE_NOW;
    CUR = null; S = null; JOB = null; LOADED = false; renderList(); renderOverview(); await loadClients(true);
    toast("Now looking at cycle " + PERIOD, "good");
  } catch (e) { toast("Could not change cycle: " + e.message, "bad"); }
}
async function openNews() {
  if ($("#news")) return closeMenus();
  const m = menuAt($("#news-btn"), "<h4>What's new</h4><div class='nw'><small>Loading…</small></div>", "news");
  try {
    const {body} = await api("/api/changelog");
    m.innerHTML = "<h4>What's new</h4>" + ((body.entries || []).map(e => `<a class="nw" href="/changelog#${esc(e.anchor)}" target="_blank" rel="noopener"><small>${esc(e.date)}</small><b>${esc(e.title)}</b><small>${esc(e.summary)}</small></a>`).join("") || "<div class='nw'><small>No entries yet.</small></div>") + `<a href="/changelog" target="_blank" rel="noopener" style="font-weight:600">Full change log</a>`;
    m.style.maxWidth = "min(420px,92vw)"; m.style.maxHeight = "70vh"; m.style.overflow = "auto";
  } catch (e) { m.innerHTML = "<h4>What's new</h4><div class='nw'><small>The change log could not be read.</small></div>"; }
}

// ------------------------------------------------------------ overview (right pane, nothing selected)
function renderOverview() {
  document.body.classList.remove("sheetmode");
  const csm = $("#csm").value, base = CLIENTS.filter(c => !csm || c.csm === csm);
  const items = base.map(c => ({c, k: kindOf(c)})).filter(x => x.k.k === "attention" || x.k.k === "blocked")
    .sort((a, b) => (a.k.k === "attention" ? 0 : 1) - (b.k.k === "attention" ? 0 : 1));
  const ready = base.filter(c => kindOf(c).k === "ready").length;
  let body;
  if (!LOADED) body = `<div class="allgood"><span class="sk" style="width:60%;height:18px"></span><span class="sk" style="width:80%;height:12px"></span></div>`;
  else if (!items.length) body = `<div class="allgood"><b>Nothing is waiting on you.</b><span class="sub">${ready ? ready + " client" + (ready === 1 ? " is" : "s are") + " ready to build. Pick one, or press <kbd>Ctrl K</kbd>." : "Every client in this view is built or building."}</span></div>`;
  else body = `<div class="wait">` + items.slice(0, 8).map(({c, k}) => `<button class="wi" data-id="${esc(c.id)}">${si(k.k)}<span><b>${esc(c.name)}</b><small>${esc(c.id)} · ${esc(k.label)}</small></span><span class="link">Open</span></button>`).join("") + `</div>`;
  $("#detail").innerHTML = `<header class="dh"><h2>Waiting on you</h2><span class="meta">${LOADED ? items.length + " thing" + (items.length === 1 ? "" : "s") + " need a look" : "Checking…"}</span></header>${body}
    <div class="hint"><span><kbd>j</kbd><kbd>k</kbd> move</span><span><kbd>Enter</kbd> open</span><span><kbd>/</kbd> search</span><span><kbd>Ctrl K</kbd> everything</span><span><kbd>?</kbd> all shortcuts</span></div>`;
}

// ------------------------------------------------------------ client detail
const LEVEL = {ok: "ok", warn: "warn", ask: "warn", stop: "stop"};
function openClient(id, fresh) {
  clearTimeout(openTimer); CUR = id; CURSOR = id; ARMED = null; JOB = null; clearInterval(poller); clearTimeout(statusTimer);
  document.body.classList.add("sheetmode"); syncHash(); renderList();
  const c = CLIENTS.find(x => x.id === id) || {id};
  $("#detail").innerHTML = `<header class="dh"><button class="ctl back" data-act="back">← Back</button><h2>${esc(c.name || id)}</h2><span class="meta">${esc(id)} · ${esc(c.csm || "")}</span></header>
    <div class="pres">${[1, 2].map(() => `<div class="pc"><span class="sk" style="width:40%;height:18px"></span><span class="sk" style="width:85%;height:12px"></span><span class="sk" style="width:60%;height:12px"></span></div>`).join("")}</div>`;
  api("/api/status?client=" + encodeURIComponent(id) + (fresh ? "&fresh=1" : "")).then(({body}) => {
    if (CUR !== id) return;
    S = body; JOB = body.job || null;
    renderDetail();
    if (JOB && !JOB.done) follow(id);
    if (body.refreshing) statusTimer = setTimeout(() => recheckQuietly(id), 2000);
  }).catch(e => { if (CUR === id) $("#detail").insertAdjacentHTML("beforeend", `<p class="empty">Couldn't check ${esc(id)}: ${esc(e.message)}</p>`); });
}
async function recheckQuietly(id) {
  try {
    const {body} = await api("/api/status?client=" + encodeURIComponent(id));
    if (CUR !== id) return;
    if (body.refreshing) { statusTimer = setTimeout(() => recheckQuietly(id), 2000); return; }
    if (JOB && !JOB.done) return;
    S = body; if (body.job) JOB = body.job; renderDetail();
  } catch (e) { statusTimer = setTimeout(() => recheckQuietly(id), 5000); }
}
// Back to the Decks overview (the KPI tiles, the list, "Waiting on you"): no client open, no cursor, no #client in the address.
// A build for the client keeps running on the server; its steps come back when the client is opened again, and the Building pill
// and the finished toast reach it meanwhile.
function closeClient() {
  const was = CUR, building = !!was && (QUEUE.building === was || QUEUE.queued.includes(was) || !!(JOB && !JOB.done));
  clearTimeout(openTimer); clearTimeout(statusTimer); clearInterval(poller);
  CUR = null; CURSOR = null; S = null; JOB = null; ARMED = null;
  syncHash(); renderList(); renderOverview();
  if (building) toast(`${was} is still building. Open it again, or the Building pill, to see the steps.`, "", 5000);
}


function presentation(o) {
  const rows = (o.checks || []).map(c => ({...c, ck: LEVEL[c.level] || "ok"}));
  const need = r => r.level === "stop" || r.level === "warn", shown = rows.filter(need), folded = rows.filter(r => !need(r));
  const li = r => `<li><span class="t ck-${r.ck}">${ICONS[r.ck === "ok" ? "ok" : r.ck === "warn" ? "warn" : "stop"].replace('<svg', '<svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"')}</span><span>${esc(r.text)}</span></li>`;
  const decks = o.decks || [], run = JOB && !JOB.done && o.match(JOB);
  const stateChip = o.state === "stop" ? `<span class="chip k-blocked">${si("blocked")}Can't build yet</span>` : decks.length ? `<span class="chip k-outputs">${si("outputs")}In Outputs</span>` : `<span class="chip k-ready">${si("ready")}Ready to build</span>`;
  const lens = n => { const m = n.match(/-TI-(ARS|ICS)-/); return m ? "the " + m[1] + " lens" : n; };
  const open = decks.map(n => `<button class="link" data-reveal="${esc(n)}">${decks.length > 1 ? "open " + esc(lens(n)) : "open the deck"}</button>`).join(" · ");
  const l = o.last; let fact = "";
  if (l && l.delivered) fact = `Built <b>${esc(l.finished)}</b> by ${esc(l.by)} · ${esc(l.result)}`;
  else if (l) fact = `<span class="err">Last build ${esc(l.finished)} by ${esc(l.by)} was not put in Outputs: ${esc(l.result)}</span>`;
  else if (decks.length) fact = decks.length === 1 ? "Deck in Outputs" : "Decks in Outputs";
  if (open) fact += (fact ? " · " : "") + open;
  const anyRun = JOB && !JOB.done;
  const btn = (kind, label, first) => {
    const key = o.key + ":" + kind;
    if (ARMED === key) return `<button class="btn warn" data-act="confirm" data-kind="${esc(kind)}">Yes, replace it</button><button class="btn" data-act="cancel">Cancel</button>`;
    const txt = run && o.match(JOB, kind) ? (JOB.queued ? "Queued #" + JOB.queued : "Building…") : label;
    return `<button class="btn${o.state === "ask" ? "" : " primary"}" data-act="build" data-kind="${esc(kind)}"${anyRun ? " disabled" : ""}${first ? ' data-first="1"' : ""}>${esc(txt)}${first && !anyRun ? " <kbd>B</kbd>" : ""}</button>`;
  };
  const act = o.state === "stop" ? `<button class="btn" data-act="recheck">Check again <kbd>R</kbd></button>` : o.buttons(btn);
  const why = o.state === "stop" ? "" : `<span class="why">${o.state === "ask" ? "replaces the deck in Outputs" : "goes to Outputs when it passes validation"}</span>`;
  return `<section class="pc${o.state === "stop" ? " stopc" : ""}" id="pc-${o.key || "rpe"}">
    <div class="pch"><h3>${esc(o.title)}${o.mix ? ` <span class="mix">${esc(o.mix)}</span>` : ""}${stateChip}</h3><div class="act">${act}${why}</div></div>
    ${fact ? `<p class="fact">${fact}</p>` : ""}${o.note || ""}
    ${shown.length ? `<ul class="checks">${shown.map(li).join("")}</ul>` : ""}
    ${folded.length ? `<details class="fold"><summary>${folded.length}${shown.length ? " other" : ""} check${folded.length === 1 ? "" : "s"} passed</summary><ul class="checks" style="margin-top:6px">${folded.map(li).join("")}</ul></details>` : ""}
    <div id="job-${o.key || "rpe"}"></div></section>`;
}

function renderDetail() {
  const s = S; if (!s) return;
  const c = CLIENTS.find(x => x.id === s.client) || {};
  const b = s.builds || {ars_only: true, has_ars: true, base: ["ARS"], combined: null, left_out: {}};
  const noArs = b.has_ars === false, baseList = b.base && b.base.length ? b.base : ["ARS"], plain = baseList.join(" + ");
  const base = baseList.length > 1 ? plain : "ARS only", combo = b.combined ? b.combined.join(" + ") : "";
  const sameDeck = !!b.combined && b.ars_only && baseList.join("+") === b.combined.join("+");
  const two = b.ars_only && !!b.combined && !sameDeck;
  const failed = c.error || (JOB && JOB.done && JOB.code);
  const leftOut = Object.entries(b.left_out || {}).map(([p, why]) => `${p} left out: ${why}`).join(" · ");
  const mix = noArs ? (b.combined && b.combined.length < baseList.length ? `${plain}; the build carries ${combo}` : b.combined ? combo : plain)
    : sameDeck ? `${plain}, one deck` : two ? `${base}, or combined (${combo})` : b.combined ? `${combo}, combined` : plain;
  const verb = ask => failed ? (ask ? "Retry rebuild" : "Retry build") : (ask ? "Rebuild" : "Build");
  const rpeBtns = btn => (b.ars_only ? btn("ars", verb(s.state === "ask") + (two ? " " + base : ""), true) : "") + (b.combined && !sameDeck ? btn("combined", verb(s.state === "ask") + (two ? " combined" : ""), !b.ars_only) : "");
  const kindOfJob = j => j.ti ? "ti" : j.companion ? "comp" : j.combined ? "combined" : "ars";
  const note = (leftOut ? `<p class="why">${esc(leftOut)}</p>` : "") + (failed ? `<p class="fact"><span class="err">The last build failed; see why below.</span></p>` : "");
  const cards = [presentation({key: "", title: "Executive Review", mix, state: s.state, checks: s.checks, last: s.last, decks: c.decks || [], note, buttons: rpeBtns,
                               match: (j, k) => (!j.ti && !j.companion) && (!k || k === kindOfJob(j))})];
  if (s.ti) cards.push(presentation({key: "ti", title: "Transaction Intelligence", mix: "one deck per lens", state: s.ti.state, checks: s.ti.checks, last: s.ti.last, decks: s.ti.decks || [],
                                     buttons: btn => btn("ti", s.ti.state === "ask" ? "Rebuild" : (s.ti.last && !s.ti.last.delivered) ? "Retry" : "Build", false), match: j => !!j.ti}));
  if (s.companion) cards.push(presentation({key: "comp", title: "ARS Companion", mix: "James's analysis slides", state: s.companion.state, checks: s.companion.checks, last: s.companion.last, decks: s.companion.decks || [],
                                            buttons: btn => btn("comp", s.companion.state === "ask" ? "Rebuild" : (s.companion.last && !s.companion.last.delivered) ? "Retry" : "Build", false), match: j => !!j.companion}));
  const age = s.age_seconds == null ? "" : (s.age_seconds < 60 ? "checked just now" : "checked " + Math.round(s.age_seconds / 60) + " min ago") + (s.refreshing ? ", checking again…" : "");
  const k = kindOf(c);
  $("#detail").innerHTML = `<header class="dh"><button class="ctl back" data-act="back">← Back</button><h2>${esc(s.name || c.name || s.client)}</h2><span class="chip k-${k.k}">${si(k.k)}${esc(k.label)}</span>
    <span class="meta"><span>${esc(s.client)} · ${esc(s.csm || c.csm || "")} · ${esc(s.period || "")}</span><span>${esc(age)} · <button class="link" data-act="recheck">Check again</button></span><button class="link" data-act="close" style="margin-left:auto">Close <kbd>Esc</kbd></button></span><span class="meta clientlinks" id="clientlinks"></span></header>
    <div class="pres">${cards.join("")}<div id="ilscards"></div></div>`;
  ilsCards(s.client); clientLinks(s.client, "decks", $("#clientlinks"));
  if (JOB) renderJob(JOB);
  if (s.refreshing) for (const x of $$("#detail [data-act=build]")) { x.disabled = true; x.title = "Waiting for the fresh check"; }
}

// ------------------------------------------------------------ building
async function startBuild(kind) {
  const s = S; if (!s) return;
  const ask = kind === "ti" ? s.ti.state === "ask" : kind === "comp" ? s.companion.state === "ask" : s.state === "ask";
  const key = (kind === "ti" ? "ti" : kind === "comp" ? "comp" : "") + ":" + kind;
  if (ask && ARMED !== key) { ARMED = key; renderDetail(); return; }
  ARMED = null;
  const req = {client: s.client, rebuild: ask, ...(kind === "combined" ? {combined: true} : {}), ...(kind === "ti" ? {ti: true} : {}), ...(kind === "comp" ? {companion: true} : {})};
  try {
    const {status, body} = await api("/api/build", {method: "POST", body: JSON.stringify(req)});
    if (status === 409) { toast(body.error || "That client is already building.", "bad"); renderDetail(); return; }
    JOB = body; renderDetail(); pollQueue();
    toast(body.queued ? `Queued ${s.client} (#${body.queued})` : `Building ${s.client}…`, "good");
    follow(s.client);
  } catch (e) { toast("Could not start the build: " + e.message, "bad"); renderDetail(); }
}

const CELEBRATED = new Set();
function follow(id) {
  clearInterval(poller);
  const tick = async () => {
    try {
      const {body} = await api("/api/job?client=" + encodeURIComponent(id));
      if (CUR !== id) return clearInterval(poller);
      const wasRunning = JOB && !JOB.done, before = JOB && JOB.queued;
      JOB = body && body.lines ? body : JOB;
      // The buttons say "Queued #1" until the build starts, then "Building…": draw them again when that changes.
      if (body && body.lines) { if (before !== body.queued || body.done) renderDetail(); else renderJob(body); }
      if (body && body.done) {
        clearInterval(poller); loadClients(); recheckQuietly(id);
        const key = id + ":" + (body.deck || body.code);
        if (wasRunning !== false && !CELEBRATED.has(key)) {
          CELEBRATED.add(key);
          if (!body.code && body.deck) { toast(`Done. ${id} is in Outputs.`, "good", 6000); celebrate(); }
          else toast(`${id} was not put in Outputs.`, "bad", 8000);
        }
      }
    } catch (e) {}
  };
  tick(); poller = setInterval(tick, 1500);
}

function renderJob(j) {
  if (!j || !j.lines) return;
  paintBusy();
  const key = j.ti ? "ti" : j.companion ? "comp" : "rpe", box = $("#job-" + key);
  for (const o of $$("#detail [id^=job-]")) if (o !== box) o.innerHTML = "";
  if (!box) return;
  const steps = [], marks = [];
  for (const line of j.lines) {
    const m = line.match(/^\s*\[(ok|!!|built|STOP|\.\.)\]\s+(.*)$/); if (!m) continue;
    if (m[1] === "..") { const sm = m[2].match(/^(.*?)\s+\((\d+) min\)$/); steps.push({name: sm ? sm[1] : m[2], min: sm ? sm[2] : ""}); }
    else if (steps.length) marks.push({level: m[1], text: m[2]});
  }
  const mins = Math.floor(j.seconds / 60), secs = String(j.seconds % 60).padStart(2, "0");
  let html = `<div class="prog"><h4>${j.ti ? "Transaction Intelligence build" : j.companion ? "ARS Companion build" : j.combined ? "Combined build" : "Build"}${j.rebuild ? " (rebuild)" : ""} · ${j.queued ? "queued #" + j.queued : mins + ":" + secs}</h4><ul class="steps">`;
  if (j.queued) html += `<li><span class="sd"></span><span>Queued #${j.queued}. It starts on its own when ${j.queued > 1 ? "the builds ahead of it finish" : "the build for " + esc(j.after || "another client") + " finishes"}. Keep Sheila's black window open.</span></li>`;
  steps.forEach((st, i) => { const done = j.done || i < steps.length - 1; html += `<li><span class="sd ${done ? "done" : "now"}"></span><span>${esc(st.name)}</span><span class="tm">${st.min !== "" ? esc(st.min) + " min" : ""}</span></li>`; });
  if (!steps.length && !j.done && !j.queued) html += `<li><span class="sd now"></span><span>Starting the build…</span></li>`;
  html += "</ul>";
  const notes = marks.filter(x => x.level !== "STOP");
  const notesHtml = notes.length ? `<ul>${notes.map(x => `<li>${esc(x.text)}</li>`).join("")}</ul>` : "";
  const stop = marks.find(x => x.level === "STOP") || (j.done && j.code ? {text: [...j.lines].reverse().find(l => l.trim()) || "The build stopped."} : null);
  if (j.done && !j.code && j.deck) {
    html += `<div class="result good pop"><h4>Done. The ${j.ti ? "Transaction Intelligence decks are" : j.companion ? "ARS Companion deck is" : "deck is"} in Outputs.</h4><span class="nm">${esc(j.deck.split(/[\\/]/).pop())}</span>${notesHtml}
      <span>Review it, save it as a PDF and email it as usual. <button class="link" data-act="revealpath" data-path="${esc(j.deck)}">Show it in File Explorer</button></span></div>`;
  } else if (j.done) {
    html += `<div class="result bad pop"><h4>Not put in Outputs.</h4><span>${esc(stop ? stop.text : "The build stopped.")}</span>${notesHtml}<span>If it's not clear what to do, send Aaron the client number.</span></div>`;
  }
  box.innerHTML = html + "</div>";
  const was = $$("#detail [data-act=build]"); const run = !j.done;
  for (const x of was) x.disabled = run;
}

// ------------------------------------------------------------ toasts, confetti
function toast(msg, kind, ms) {
  const t = document.createElement("div"); t.className = "toast " + (kind || ""); t.textContent = msg;
  $("#toasts").appendChild(t); setTimeout(() => t.remove(), ms || 3800);
}
function celebrate() {
  if (matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  const cv = $("#confetti"), cx = cv.getContext("2d"); cv.width = innerWidth; cv.height = innerHeight;
  const st = getComputedStyle(document.documentElement), cols = ["--accent", "--good", "--navy", "--accent-ink"].map(n => st.getPropertyValue(n).trim() || "#D97706");
  const ps = Array.from({length: 70}, () => ({x: innerWidth * (.4 + Math.random() * .2), y: innerHeight * .35, vx: (Math.random() - .5) * 11, vy: -Math.random() * 10 - 3, r: Math.random() * 6 + 3, c: cols[Math.random() * cols.length | 0], a: Math.random() * 6, va: (Math.random() - .5) * .4}));
  let f = 0;
  (function step() {
    cx.clearRect(0, 0, cv.width, cv.height);
    for (const p of ps) { p.vy += .28; p.x += p.vx; p.y += p.vy; p.vx *= .99; p.a += p.va; cx.save(); cx.translate(p.x, p.y); cx.rotate(p.a); cx.fillStyle = p.c; cx.globalAlpha = Math.max(0, 1 - f / 90); cx.fillRect(-p.r / 2, -p.r / 4, p.r, p.r / 2); cx.restore(); }
    if (++f < 90) requestAnimationFrame(step); else cx.clearRect(0, 0, cv.width, cv.height);
  })();
}

// ------------------------------------------------------------ command palette
const ACTIONS = () => [
  ...Object.entries(TAB_NAMES).filter(([id]) => id !== TAB).map(([id, n]) => ({t: "Go to " + n, s: "G " + Object.keys(TAB_KEY).find(k => TAB_KEY[k] === id).toUpperCase(), run: () => go(id)})),
  ...(TAB !== "decks" && TABS[TAB] && TABS[TAB].palette ? TABS[TAB].palette() : []),
  ...Object.values(TABS).flatMap(t => t.global ? t.global() : []),
  ...(TAB === "decks" && CUR ? [{t: "Back to the Decks overview", s: "Esc", run: () => closeClient()}] : []),
  {t: "Refresh the client list", s: "", run: () => { loadClients(true); toast("Refreshing the list…"); }},
  ...(ME.csm ? [{t: "Show my clients (" + ME.csm + ")", s: "", run: () => setCsm(ME.csm)}, {t: "Show every CSM's clients", s: "", run: () => setCsm("")}] : []),
  ...(CUR && S ? [{t: "Check " + CUR + " again", s: "R", run: () => openClient(CUR, true)}, {t: "Build the Executive Review for " + CUR, s: "B", run: () => firstBuild()}] : []),
  {t: "Open the change log", s: "", run: () => window.open("/changelog", "_blank", "noopener")},
  {t: "Switch to night or day", s: "T", run: toggleNight},
  {t: "Compact rows on or off", s: "C", run: () => setDensity(document.documentElement.dataset.density === "compact" ? "" : "compact")},
  {t: "Show keyboard shortcuts", s: "?", run: showKeys},
];
function fuzzy(q, text) {
  q = q.toLowerCase(); text = text.toLowerCase(); if (!q) return 1;
  const at = text.indexOf(q); if (at >= 0) return 100 - at;
  let i = 0, score = 0; for (const ch of text) { if (ch === q[i]) { i++; score += 2; } } return i === q.length ? score : 0;
}
let PAL = [], PSEL = 0;
function paint() {
  const q = $("#pq").value.trim();
  const cl = CLIENTS.map(c => ({c, sc: fuzzy(q, c.id + " " + c.name)})).filter(x => x.sc).sort((a, b) => b.sc - a.sc).slice(0, q ? 8 : 5)
    .map(({c}) => ({t: c.id + "  " + c.name, s: kindOf(c).label, ic: kindOf(c).k, run: () => openClient(c.id)}));
  const ac = ACTIONS().map(a => ({...a, sc: fuzzy(q, a.t)})).filter(a => a.sc).sort((a, b) => b.sc - a.sc).slice(0, q ? 8 : 20);
  PAL = [...cl, ...ac]; PSEL = Math.min(PSEL, Math.max(0, PAL.length - 1));
  let html = "", shownC = false, shownA = false;
  PAL.forEach((it, i) => {
    if (it.ic && !shownC) { html += '<li class="gt">Clients</li>'; shownC = true; }
    if (!it.ic && !shownA) { html += '<li class="gt">Actions</li>'; shownA = true; }
    html += `<li><button role="option" data-i="${i}" aria-selected="${i === PSEL}">${it.ic ? si(it.ic) : ""}<span>${esc(it.t)}</span><small>${esc(it.s || "")}</small></button></li>`;
  });
  $("#pl").innerHTML = html || '<li class="empty">Nothing matches.</li>';
  const sel = $("#pl [aria-selected=true]"); if (sel) sel.scrollIntoView({block: "nearest"});
}
function openPalette() { $("#pq").value = ""; PSEL = 0; $("#pal").showModal(); paint(); $("#pq").focus(); }
function runPal(i) { const it = PAL[i]; if (!it) return; $("#pal").close(); setTimeout(it.run, 0); }

// ------------------------------------------------------------ preferences
function setTheme(t) { if (t) document.documentElement.dataset.theme = t; else delete document.documentElement.dataset.theme; store("hub-theme", t || ""); syncNight(); }
function effectiveDark() { const t = document.documentElement.dataset.theme; return t ? t === "dark" : matchMedia("(prefers-color-scheme: dark)").matches; }
function toggleNight() { setTheme(effectiveDark() ? "light" : "dark"); }
function syncNight() { $("#night-l").textContent = effectiveDark() ? "Day" : "Night"; }
function setDensity(d) { if (d) document.documentElement.dataset.density = d; else delete document.documentElement.dataset.density; store("hub-density", d || ""); $("#dn-c").setAttribute("aria-pressed", !d); $("#dn-k").setAttribute("aria-pressed", !!d); }
function setRail(on) { $("#app").classList.toggle("rail", on); store("hub-rail", on ? "1" : ""); $("#fold").setAttribute("aria-label", on ? "Unfold the sidebar" : "Fold the sidebar"); }

function firstBuild() { const b = $("#detail [data-act=build]:not([disabled])"); if (b) b.click(); else toast("Nothing to build for this client right now."); }

// ------------------------------------------------------------ tabs
// Each tab after Decks is a <section class="view tabview" id="v-<id>"> that its module fills when it is opened:
// registerTab(id, {enter(params), leave(), refresh(), key(e), keys: [[keys, what]], palette(): [{t, s, run}]}).
// The address names the tab (#lift, #issues, #votes, #reported; none is Decks) and carries what it shows
// (#lift&client=1705, #votes&program=ICS), so a bookmark or a link from another tab lands where it says.
const TABS = {}, TAB_NAMES = {decks: "Decks", lift: "Lift Matrix", issues: "Data Issues", votes: "Slide Review", reported: "Feedback"};
const TAB_KEY = {d: "decks", l: "lift", i: "issues", v: "votes", f: "reported"};
let TAB = "decks", TABPARAMS = {};
function registerTab(id, def) { TABS[id] = def; }
function readHash() {
  const parts = location.hash.slice(1).split("&"), tab = parts[0] && !parts[0].includes("=") ? parts.shift() : "decks";
  return {tab, p: new URLSearchParams(parts.join("&"))};
}
const HP = readHash().p;           // theme and density from the address: for this load only, never stored
function syncHash() {
  const p = new URLSearchParams(), q = TAB === "decks" ? (CUR ? {client: CUR} : {}) : TABPARAMS;
  for (const [k, v] of Object.entries(q)) if (v) p.set(k, v);
  for (const k of ["theme", "density"]) if (HP.get(k)) p.set(k, HP.get(k));
  const rest = p.toString(), h = (TAB === "decks" ? "" : TAB) + (rest ? (TAB === "decks" ? "" : "&") + rest : "");
  try { history.replaceState(null, "", location.pathname + location.search + (h ? "#" + h : "")); } catch (e) {}
}
function setTabParams(o) { TABPARAMS = {...TABPARAMS, ...o}; syncHash(); }
function setTab(id, params) {
  if (id !== "decks" && !TABS[id]) id = "decks";
  if (TAB !== id && TAB !== "decks" && TABS[TAB] && TABS[TAB].leave) TABS[TAB].leave();
  TAB = id; TABPARAMS = params || {};
  for (const v of $$(".view[id^=v-]")) v.hidden = v.id !== "v-" + id;
  for (const a of $$("[data-tab]")) { if (a.dataset.tab === id) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current"); }
  document.title = id === "decks" ? "CSM Sheila" : "CSM Sheila · " + TAB_NAMES[id];
  closeMenus(); syncHash();
  if (id !== "decks" && TABS[id].enter) TABS[id].enter(TABPARAMS);
}
function go(id, params) { setTab(id, params); window.scrollTo(0, 0); }
window.addEventListener("hashchange", () => { const h = readHash(); setTab(h.tab, Object.fromEntries(h.p)); });

// ------------------------------------------------------------ events
document.addEventListener("click", ev => {
  const t = ev.target;
  const tabLink = t.closest("[data-tab]");
  if (tabLink && TABS[tabLink.dataset.tab] || tabLink && tabLink.dataset.tab === "decks") { ev.preventDefault(); return go(tabLink.dataset.tab); }
  // The open client's row again closes it (Aaron, 2026-11-02): back to the overview.
  const row = t.closest(".row[data-id], .wi[data-id]"); if (row) return row.dataset.id === CUR ? closeClient() : openClient(row.dataset.id);
  const kp = t.closest("#kpis .kpi"); if (kp) { FILTER = FILTER === kp.dataset.kind ? "" : kp.dataset.kind; return renderList(); }
  if (t.closest("#clearf")) { FILTER = ""; return renderList(); }
  if (t.closest("#relist")) return loadClients(true);
  if (t.closest("#period")) return openCycles();
  if (t.closest("#news-btn")) return openNews();
  const rv = t.closest("[data-reveal]");
  if (rv) return api("/api/reveal", {method: "POST", body: JSON.stringify({client: S.client, period: S.period, deck: rv.dataset.reveal})}).then(() => toast("Shown in File Explorer.")).catch(e => toast(e.message, "bad"));
  const act = t.closest("[data-act]"); if (!act) return;
  const a = act.dataset.act;
  if (a === "build") startBuild(act.dataset.kind);
  else if (a === "confirm") startBuild(act.dataset.kind);
  else if (a === "cancel") { ARMED = null; renderDetail(); }
  else if (a === "mycsm") setCsm(ME.csm);
  else if (a === "allcsm") setCsm("");
  else if (a === "recheck") openClient(CUR, true);
  else if (a === "close" || a === "back") closeClient();
  else if (a === "revealpath") api("/api/reveal", {method: "POST", body: JSON.stringify({path: act.dataset.path})}).then(() => toast("Shown in File Explorer.")).catch(e => toast(e.message, "bad"));
});
function setCsm(v) {
  $("#csm").value = v; if (!ME.csm) store("ars-builder-csm", v); renderList(); paintMine(); if (!CUR) renderOverview(); paintIssueBadge();
  for (const s of $$(".csmpick")) s.value = v;
  if (TAB !== "decks" && TABS[TAB] && TABS[TAB].refresh) TABS[TAB].refresh();
}
// The same CSM filter in a tab's header: one choice for every tab, kept in the Decks list's own select.
function csmPick() {
  const opts = [...$("#csm").options].map(o => `<option value="${esc(o.value)}"${o.value === $("#csm").value ? " selected" : ""}>${esc(o.textContent)}</option>`).join("");
  return `<select class="csmpick ctl" aria-label="CSM">${opts}</select>`;
}
document.addEventListener("change", e => { if (e.target.classList.contains("csmpick")) setCsm(e.target.value); });
$("#csm").addEventListener("change", e => setCsm(e.target.value));
$("#q").addEventListener("input", renderList);
$("#palbtn").addEventListener("click", openPalette);
$("#night").addEventListener("click", toggleNight);
$("#dn-c").addEventListener("click", () => setDensity("")); $("#dn-k").addEventListener("click", () => setDensity("compact"));
$("#fold").addEventListener("click", () => setRail(!$("#app").classList.contains("rail")));
$("#keyx").addEventListener("click", () => $("#keys").close());
$("#pq").addEventListener("input", () => { PSEL = 0; paint(); });
$("#pl").addEventListener("click", e => { const b = e.target.closest("[data-i]"); if (b) runPal(+b.dataset.i); });
$("#pal").addEventListener("keydown", e => {
  if (e.key === "ArrowDown") { e.preventDefault(); PSEL = Math.min(PAL.length - 1, PSEL + 1); paint(); }
  else if (e.key === "ArrowUp") { e.preventDefault(); PSEL = Math.max(0, PSEL - 1); paint(); }
  else if (e.key === "Enter") { e.preventDefault(); runPal(PSEL); }
});
$("#pal").addEventListener("click", e => { if (e.target === $("#pal")) $("#pal").close(); });
// A closed dialog must not keep the keyboard: with focus left in its box every shortcut would read as typing.
for (const d of ["#pal", "#keys"]) $(d).addEventListener("close", () => { if (document.activeElement && document.activeElement !== document.body) document.activeElement.blur(); });
$("#keys").addEventListener("click", e => { if (e.target === $("#keys")) $("#keys").close(); });
const KEYS_DECKS = [["j  k", "Move down or up the list"], ["Enter", "Open the client; again to close it"], ["/", "Find a client"], ["B", "Build (asks first if a deck is in Outputs)"],
  ["R", "Check the open client again"], ["E", "Show the deck in File Explorer"], ["Esc", "Close the client or a menu"]];
const KEYS_ALL = [["Ctrl K", "Search clients, tabs and actions"], ["G  D", "Go to Decks (G then L, I, V or F for the other tabs)"], ["T", "Night or day"], ["C", "Compact rows"], ["?", "This list"]];
function showKeys() {
  const tab = TAB === "decks" ? KEYS_DECKS : ((TABS[TAB] && TABS[TAB].keys) || []);
  const dl = (rows) => rows.map(([k, d]) => `<dt>${k.split("  ").map(x => `<kbd>${esc(x)}</kbd>`).join("")}</dt><dd>${esc(d)}</dd>`).join("");
  $("#keyl").innerHTML = `<dt style="grid-column:1/-1;font-size:12px;letter-spacing:.06em;text-transform:uppercase;color:var(--muted)">${esc(TAB_NAMES[TAB])}</dt>` + dl(tab) +
    `<dt style="grid-column:1/-1;font-size:12px;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);margin-top:6px">Everywhere</dt>` + dl(KEYS_ALL);
  $("#keys").showModal();
}

let CHORD = 0;
document.addEventListener("keydown", e => {
  const typing = /^(INPUT|SELECT|TEXTAREA)$/.test(document.activeElement.tagName);
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") { e.preventDefault(); return $("#pal").open ? $("#pal").close() : openPalette(); }
  if (e.key === "Escape") {
    if ($(".menu")) return closeMenus(); if (typing) return document.activeElement.blur();
    if (TAB !== "decks") { if (TABS[TAB] && TABS[TAB].key) TABS[TAB].key(e); return; }
    if (CUR) closeClient(); return;
  }
  if (typing || e.ctrlKey || e.metaKey || e.altKey || $("#pal").open || $("#keys").open || $("dialog[open]")) return;
  const k = e.key;
  if (TAB !== "decks" && TABS[TAB] && TABS[TAB].key && TABS[TAB].key(e) === true) return;
  if (CHORD && Date.now() - CHORD < 1500) { CHORD = 0; if (TAB_KEY[k]) { e.preventDefault(); go(TAB_KEY[k]); return; } }
  CHORD = 0;
  if (k === "g") { CHORD = Date.now(); return; }
  if (k === "?") return showKeys();
  if (k === "t") return toggleNight();
  if (k === "c") return setDensity(document.documentElement.dataset.density === "compact" ? "" : "compact");
  if (TAB !== "decks") return;
  if (k === "/") { e.preventDefault(); $("#q").focus(); }
  else if (k === "j" || k === "k" || k === "ArrowDown" || k === "ArrowUp") {
    e.preventDefault();
    const rows = visible(), i = rows.findIndex(c => c.id === (CURSOR || CUR)), n = (k === "j" || k === "ArrowDown") ? i + 1 : i - 1;
    const next = rows[Math.max(0, Math.min(rows.length - 1, i < 0 ? 0 : n))];
    if (next) { CURSOR = next.id; renderList(); const el = $(`.row[data-id="${next.id}"]`); if (el) el.scrollIntoView({block: "nearest"}); clearTimeout(openTimer); openTimer = setTimeout(() => openClient(next.id), 260); }
  }
  else if (k === "Enter" && CURSOR && !document.activeElement.closest(".row")) { if (CURSOR === CUR) closeClient(); else openClient(CURSOR); }
  else if (k === "b" && CUR) firstBuild();
  else if (k === "r" && CUR) openClient(CUR, true);
  else if (k === "e" && CUR && S) { const c = CLIENTS.find(x => x.id === CUR), d = c && (c.decks || [])[0]; if (d) api("/api/reveal", {method: "POST", body: JSON.stringify({client: S.client, period: S.period, deck: d})}).then(() => toast("Shown in File Explorer.")).catch(er => toast(er.message, "bad")); }
});

// ------------------------------------------------------------ start
setRail(recall("hub-rail") === "1"); setDensity(recall("hub-density") || ""); setTheme(recall("hub-theme") || ""); syncNight();
matchMedia("(prefers-color-scheme: dark)").addEventListener("change", syncNight);
renderList(); renderOverview(); paintPeriod();
loadClients(); pollQueue(); setInterval(pollQueue, 3000); setInterval(paintBuildPill, 1000);
//__TAB_JS__
// A link can set the view: /#client=1441&theme=dark&density=compact (none of it is stored).
const HASH = HP;
if (HASH.get("theme") === "dark" || HASH.get("theme") === "light") document.documentElement.dataset.theme = HASH.get("theme");
if (HASH.get("density") === "compact") document.documentElement.dataset.density = "compact";
syncNight();
$("#dn-c").setAttribute("aria-pressed", !document.documentElement.dataset.density); $("#dn-k").setAttribute("aria-pressed", !!document.documentElement.dataset.density);
{ const h = readHash(); if (h.tab !== "decks") setTab(h.tab, Object.fromEntries(h.p)); }
const first = TAB === "decks" && (HASH.get("client") || "").match(/^\d{3,5}$/) ? HASH.get("client") : null;
if (first) { const t = setInterval(() => { if (LOADED) { clearInterval(t); openClient(first); } }, 200); }
</script>
</body>
</html>
"""


PAGE = _assemble()
