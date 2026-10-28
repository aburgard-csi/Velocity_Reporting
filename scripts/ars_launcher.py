#!/usr/bin/env python3
"""Deck launcher — build one client's Executive Review (or CashPlease module) into Outputs without Claude.

    python scripts/ars_launcher.py status <client id> [--period 2026.09]
    python scripts/ars_launcher.py build  <client id> [--period 2026.09] [--rebuild] [--combined]

For an ARS client, `--combined` builds one deck with ARS plus every other clients.md program that
has the data it needs this period (`program_availability`): ICS from its VIP sheet or, without one,
from the ICS workbook and referral files in Inputs; MRPC from its VIP sheet. The CSM chooses in CSM
Sheila (Aaron, 2026-09-16: "add a second Create button so the CSM can elect to build an ARS only
deck, or a combined deck for whichever products have the appropriate data").

A client with no ARS (Aaron, 2026-10-13: "bring CP only, ICS only, and MRPC only decks into Sheila,
also any combination of those") builds the one deck their programs make — ICS, MRPC, ICS-CP,
ICS-MRPC, ICS-MRPC-CP, or the standalone CashPlease module — from every program whose data is on
hand; `--combined` is implied. The ARS-only rules below (the ODD extract, the workbook, the DCO, the
Lift Matrix) apply to ARS clients only; a non-ARS client is checked on each program's own data.

Anyone can run it, from `Build ARS Deck.bat` in the CSM_Reporting folder (Aaron, 2026-09-15: "a
way where anyone can run an ARS deck so long as the inputs are in place ... without Claude").
Every rule that used to be applied by hand is checked BEFORE the build, and every stop says in
plain English what is wrong and who fixes it:

  * the client has the ARS product (Client CSM List `products`, from the Velocity export);
  * clients.md lists the client for ARS — that file decides what gets built;
  * a client of Aaron's with more than one program ships a combined deck, so an ARS-only build
    stops there and only `--combined` is offered;
  * the ODD extract is this period's, and this period's ARS workbook is in Inputs
    (`deck_status.requirements`, the same check as the delivery dashboard);
  * an MM client's Lift Matrix is current: the workbook's data month is inside its window and the
    data team hasn't flagged it in the filename (`lift_checks`);
  * a deck already in Outputs for the period (or recorded as sent) is rebuilt only when the person
    running it says so: the launcher asks, and on the command line it takes --rebuild;
  * one person at a time per client: a lock file in the client's work folder.

A build works in `Build Artifacts/launcher/<period>/<id>/`, where its log, charts and data stay
out of sight. A deck that passes validation with 0 FAIL goes straight to `Outputs/<CSM>/`, and
whatever it supersedes is archived (promote_month). There is no staging step: each CSM reviews,
PDFs and emails the deck from Outputs themselves (Aaron, 2026-09-15). Nothing is ever deleted.
"""
import argparse
import csv
import datetime as dt
import getpass
import json
import os
import re
import shutil
import subprocess
import sys
import textwrap
import threading
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
for _p in (REPO / "build", REPO / "build" / "ars_pipeline", REPO / "scripts"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import rpe_env as R          # noqa: E402
from lift_window import workbook_window   # noqa: E402

LOCK_STALE_HOURS = 3
AARON = "Aaron Burgard"
OK, WARN, STOP = "ok", "warn", "stop"
# A deck already sent is a question, not a stop (Aaron, 2026-09-15: "can the script prompt
# whether the user wants the presentation re-run rather than failing?"). `status` exits
# ASKED_EXIT when it is the only thing in the way, and Build ARS Deck.bat asks.
ASK = "ask"
ASKED_EXIT = 3
# build_month.run writes "$ <python> <script> ..." to build.log before each step and sends the
# step's own output to the log, so a build is silent on screen for up to 15 minutes. The
# launcher watches the log and names each step as it starts (2026-09-15).
STEPS = {
    "extract_base_gen.py": "Reading the ARS workbook",
    "extract_lift.py": "Reading the Lift Matrix",
    "base_tab_extract.py": "Reading the ARS workbook and DCO",
    "oddd_optimize.py": "Reading the ODD extract",
    "metrics_gen.py": "Computing the ODD metrics",
    "charts_gen.py": "Drawing the charts",
    "build_ars_gen.py": "Assembling the deck",
    "build_ics_gen.py": "Building the ICS section",
    "build_mrpc_gen.py": "Building the MRPC section",
    "cp_extract.py": "Reading the CashPlease weekly",
    "build_cp_gen.py": "Building the CashPlease slides",
    "assemble_combined.py": "Combining the sections",
    "ti_build.py": "Building the Transaction Intelligence cut",
}
# The Velocity product a program needs on the client's product list (Client CSM List `products`).
PRODUCT_OF = {"ARS": "ARS", "ICS": "ICS", "MRPC": "MRPC", "CP": "CashPlease"}


# ------------------------------------------------------------------ small helpers
def say(level, text):
    mark = {OK: "  [ok]  ", WARN: "  [!!]  ", ASK: " [built]", STOP: "  [STOP]"}[level]
    # Wrapped at the window's width on word boundaries: the console otherwise splits a word
    # across lines ("for exampl / e"). Paths are never broken.
    width = max(60, shutil.get_terminal_size((100, 24)).columns - 1)
    print(textwrap.fill(f"{mark} {text}", width=width, subsequent_indent=" " * (len(mark) + 1),
                        break_long_words=False, break_on_hyphens=False), flush=True)


def csm_list_row(cid):
    """The client's row from Client CSM List.csv, or {}."""
    p = R.csm_list_file()
    if not p or not p.is_file():
        return {}
    with open(p, encoding="utf-8-sig", newline="") as fh:
        return next((r for r in csv.DictReader(fh) if r.get("client_id", "").strip() == cid), {})


def cycle_period(today=None):
    """The current cycle: THIS CALENDAR MONTH, which advances on the 1st.

    It used to be the newest period of any ARS workbook in Inputs, so the tool sat on last
    month's cycle until the data team's first workbook of the new month landed — on
    2026-10-02 it still read 2026.09 (Aaron: "sheila needs to auto-advance the cycle on the
    1st, so today's should show october").

    A cycle is a calendar fact. Whether its workbooks have arrived is a different question,
    and one the per-client checks already answer by name: `input_checks` reports a missing
    workbook for the period, which is the right thing to see on the 2nd of the month, rather
    than a dashboard quietly still showing last month's finished work.

    `newest_workbook_period` keeps the old reading for the checks that want it.
    """
    return (today or dt.date.today()).strftime("%Y.%m")


def newest_workbook_period(cid):
    """The newest period with an ARS workbook for this client ('*' for any client) in Inputs, or None."""
    pers = []
    for f in R.report_files(f"{cid}-*Workbook*.xlsx"):
        if "invitation checking" in f.name.lower():
            continue
        m = re.match(r"^\d+-(\d{4}\.\d{2})-", f.name)
        if m:
            pers.append(m.group(1))
    return max(pers) if pers else None


# ------------------------------------------------------------------ who gets what
def cp_roster_row(cid):
    """The client's CashPlease roster row, or None (also None when the table cannot be read)."""
    try:
        import build_month as BM
        return next((r for r in BM.read_cashplease_roster() if r["client_id"] == cid), None)
    except SystemExit:
        return None


def covered_programs(progs, cp_row=None):
    """The programs a client's deck covers, in section order: clients.md's tokens (ICS-REFERRALS
    is ICS) plus CP when the CashPlease roster ships their slides as a section — or CP alone for
    a standalone module client. Pure, so Sheila's list never waits on the share for it."""
    base = []
    for p in progs or []:
        k = p.split("-")[0].upper()
        if k in ("ARS", "ICS", "MRPC", "CP") and k not in base:
            base.append(k)
    if cp_row and cp_row.get("build") and "section" in (cp_row.get("ships_as") or "").lower() and "CP" not in base:
        base.append("CP")
    return [p for p in ("ARS", "ICS", "MRPC", "CP") if p in base]


def standalone_cp(cp_row):
    """A CashPlease roster row whose slides ship as their own module, not inside another deck."""
    return bool(cp_row and cp_row.get("build") and "section" not in (cp_row.get("ships_as") or "").lower())


def client_entry(cid, roster, cp_row=None):
    """The client's roster entry (id, name, MM|SM|None, [programs]); for a standalone CashPlease
    client, who is not on the main roster, one made from their CashPlease row with ["CP"]."""
    entry = next((r for r in roster if r[0] == cid), None)
    if entry is None and standalone_cp(cp_row):
        return (cid, cp_row.get("client_name") or cid, None, ["CP"])
    return entry


# ------------------------------------------------------------------ the checks
def program_availability(cid, period, programs):
    """For each clients.md program other than ARS: (ok, how or why not).

    ICS: the client's VIP sheet, else the local ICS files (`ics_local_sheet.available`: the ICS workbook,
    referral detail and direct-mail lists James and the mailbox land in Inputs). MRPC: its VIP sheet.
    CashPlease: its OWN roster table in clients.md, because it is not in the main roster row this
    is given — which is why a combined rebuild of 1539 Marine built ARS-ICS-MRPC and archived
    the four-product deck as a different program mix (Aaron, 2026-10-02).
    """
    out = {}
    for p in programs:
        if p == "ARS":
            continue
        if p.startswith("ICS"):
            try:
                R.resolve_client_json(cid, "ics")
                out["ICS"] = (True, "VIP ICS sheet")
                continue
            except SystemExit:
                pass
            try:
                if str(REPO / "build" / "ics_pipeline") not in sys.path:   # once, not once per check
                    sys.path.insert(0, str(REPO / "build" / "ics_pipeline"))
                import ics_local_sheet as ILS
                a = ILS.available(cid, period)
            except ImportError:
                out["ICS"] = (False, "no VIP ICS sheet, and the local ICS builder is not installed")
                continue
            except Exception as e:          # an unreadable file is reported, not guessed at
                out["ICS"] = (False, f"the local ICS files could not be read ({type(e).__name__}: {e})")
                continue
            out["ICS"] = (bool(a.get("ok")), a.get("reason") or ("local ICS files" if a.get("ok") else "no ICS data"))
        elif p == "MRPC":
            try:
                R.resolve_client_json(cid, "mrpc")
                out["MRPC"] = (True, "VIP MRPC sheet")
            except SystemExit:
                out["MRPC"] = (False, "no VIP MRPC sheet")
    # "CP" in `programs` is the standalone module client (client_entry); a section rides on the
    # CashPlease roster's say-so whatever the main roster row says.
    cp = cashplease_availability(cid, standalone="CP" in programs)
    if cp is not None:
        out["CP"] = cp
    return out


def cashplease_availability(cid, standalone=False):
    """(ok, how or why not) for this client's CashPlease slides, or None if they have none.

    Read from the CashPlease ROSTER in clients.md, never from the weekly workbook, which
    carries every Velocity CashPlease client across all CSMs: a tab proves a client is live
    on the program and proves nothing about whether a deck is wanted (CLAUDE.md).

    Only a client whose roster row ships CashPlease AS A SECTION joins another deck. One
    marked "standalone deck" gets its own module instead — the launcher builds that too when
    asked with `standalone` (Aaron, 2026-10-13) — and a client whose slides ship inside a
    combined deck does not also get one.
    """
    try:
        import build_month as BM
        row = next((r for r in BM.read_cashplease_roster() if r["client_id"] == cid), None)
    except SystemExit as e:                 # no roster table at all — say so, do not guess
        return (False, f"the CashPlease roster could not be read ({e})")
    if row is None or not row.get("build"):
        return None
    if "section" not in (row.get("ships_as") or "").lower() and not standalone:
        return None                         # a standalone module, not part of this deck
    wb = R.report_files("CashPleaseSummary*.xlsx")
    if not wb:
        return (False, "no CashPleaseSummary workbook in Inputs")
    return (True, f"CashPlease roster, {wb[-1].name}")


def combined_programs(availability):
    """The programs a combined deck would carry besides ARS, in SECTION order.

    CashPlease is last: the deck runs ARS, ICS, MRPC, CashPlease, and deck_tag names the
    file from this order (1539's is ARS-ICS-MRPC-CP).
    """
    return [p for p in ("ICS", "MRPC", "CP") if availability.get(p, (False,))[0]]


def build_programs(entry_programs, availability, combined):
    """The programs ONE build carries, in section order, with clients.md's own tokens.

    CashPlease rides on every deck of a client whose roster row ships it as a section (Aaron,
    2026-10-12: "add the CashPlease slides into Sheila decks"): the build Sheila offers as the
    plain ARS deck is ARS-CP for those clients, and `combined` adds ICS and MRPC on top. Before
    this a CSM who chose "ARS only" shipped a deck with no CashPlease section at all.

    clients.md's own token (e.g. ICS-REFERRALS) is kept where there is one so build_month builds
    the right shape; CashPlease has no token in the main roster row, so it carries its own name.
    """
    extra = combined_programs(availability)
    has_ars = "ARS" in (entry_programs or [])
    if has_ars and not combined:
        extra = [p for p in extra if p == "CP"]
    # A client with no ARS builds the one deck their programs make, from every program with
    # data (Aaron, 2026-10-13); nothing else is on offer, so `combined` means nothing here.
    return (["ARS"] if has_ars else []) + [next((t for t in entry_programs if t.startswith(p)), p) for p in extra]


def cashplease_checks(cid):
    """The CashPlease line on a plain (not combined) build: in the deck, left out, or nothing
    for a client with no CashPlease section."""
    cp = cashplease_availability(cid)
    if cp is None:
        return []
    ok, why = cp
    return [(OK if ok else WARN, f"CashPlease: {'in the deck' if ok else 'left out'} ({why})")]


def rule_checks(cid, period, row, roster, sent, rebuild=False, in_outputs=(), combined=False, cp_row=None):
    """The launcher's rules, independent of the filesystem so they can be tested.

    `row` is the Client CSM List row, `roster` the build_month.read_roster() active list,
    `sent` the deliveries.json "sent" map, `cp_row` the client's CashPlease roster row (a standalone
    module client is on that roster alone). Returns [(level, message)]. `combined` is a combined-deck
    build, which lifts the stop on an ARS-only deck for Aaron's multi-program clients.
    """
    out = []
    # FIRST, before the client's own name: it is the one fact that decides whether anything
    # else on this page matters (Aaron, 2026-10-02).
    _built = built_line(cid, period, sent, in_outputs, rebuild)
    if _built:
        out.append(_built)
    if not row:
        out.append((STOP, f"{cid} is not in Client CSM List.csv. Check the client number."))
        return out
    entry = client_entry(cid, roster, cp_row)
    # clients.md names the client, as it names the deck. The Client CSM List name is taken from a
    # workbook filename and can carry a data-team flag ("LM EXPIRED-USF CU / USF CU", 2026-09-15).
    name = (entry[1] if entry else None) or row.get("client_name") or cid
    csm = row.get("csm") or "no CSM"
    out.append((OK, f"{cid} {name} (CSM: {csm})"))

    if entry is None:
        out.append((STOP, "clients.md does not list this client for any program, and that file decides what "
                          "gets built. Ask Aaron to add it."))
        return out
    covered = covered_programs(entry[3], cp_row)
    has_ars = "ARS" in covered

    products = [p.strip() for p in (row.get("products") or "").split(";") if p.strip()]
    if not products:
        out.append((WARN, "The Velocity product list has no products for this client; "
                          f"{'-'.join(covered)} is assumed from clients.md."))
    elif has_ars and "ARS" not in products:
        out.append((STOP, f"Not an ARS client: the Velocity product list shows {', '.join(products)}. "
                          "Only ARS clients get ARS decks."))
    elif not has_ars:
        # A non-ARS client's deck covers ICS, MRPC and/or CashPlease: the client needs at least one of
        # those products. (The product list predates some program starts, so one missing is a warning.)
        missing = [p for p in covered if PRODUCT_OF[p].lower() not in (x.lower() for x in products)]
        if len(missing) == len(covered):
            out.append((STOP, f"Not a {' / '.join(PRODUCT_OF[p] for p in covered)} client: the Velocity product "
                              f"list shows {', '.join(products)}."))
        elif missing:
            out.append((WARN, f"The Velocity product list does not show {', '.join(PRODUCT_OF[p] for p in missing)} "
                              "for this client; clients.md says to build it."))

    if has_ars:
        out.append((OK, f"clients.md: {'-'.join(entry[3])}, {entry[2] or 'path unknown'} workbook"))
        # Checked before the build now that a clean build goes straight to Outputs: a lone ARS
        # deck must never replace one of Aaron's combined decks. Any CSM may build a combined deck
        # (Aaron, 2026-09-16), so for his clients that is the build on offer.
        if csm == AARON and len(entry[3]) > 1 and not combined:
            out.append((STOP, f"This client ships a combined {'-'.join(entry[3])} deck, so build the combined "
                              "deck instead of an ARS-only one."))
    else:
        what = "standalone CashPlease module" if covered == ["CP"] and standalone_cp(cp_row) else f"{'-'.join(covered)} deck"
        out.append((OK, f"clients.md: {what} (no ARS, so no ODD extract, ARS workbook or Lift Matrix is needed)"))

    return out


def built_line(cid, period, sent, in_outputs, rebuild=False):
    """The BUILT / rebuilding line, or None when this period has no deck yet.

    A deck already in Outputs, or already recorded as sent, is rebuilt only when the person
    running it says so (Aaron, 2026-09-15: "The deck is already in Outputs, but it says Build
    and put in Outputs. It should ask if we need to rebuild"). Outputs is what every CSM has;
    only Aaron records sends.
    """
    key = f"{cid}|{period}"
    when = None
    if key in sent:
        when = (sent[key] or {}).get("sent_at", "") if isinstance(sent[key], dict) else sent[key]
    if not (in_outputs or when):
        return None
    what = (f"The {period} deck is already in Outputs ({in_outputs[0]})" if in_outputs
            else f"The {period} deck was already made")
    if when:
        what += f" and was sent {when}"
    return (WARN, what + ". Rebuilding it, as asked.") if rebuild else (ASK, what + ".")


def decks_in_outputs(cid, period):
    """This client's RPE decks for `period` in Outputs (any CSM folder, any program mix), by name.
    A Transaction Intelligence deck is a separate presentation and is left out (ti_decks_in_outputs)."""
    return sorted(p.name for p in R.output_decks(f"{cid}-{period}-*.pptx")
                  if not p.name.startswith("~$") and not is_ti_deck(p.name) and not is_companion_deck(p.name))


def input_checks(cid, period):
    """This period's ODD extract, ARS workbook and DCO — the delivery dashboard's own check."""
    import deck_status as DS
    src_up = DS._reachable(DS.SRC_REPORTS) and DS.odd_reachable()
    src_files = DS._source_reports(period) if src_up else []
    rows = DS.requirements(cid, ["ARS"], period, [str(d) for d in R.report_dirs()],
                           R.inputs() / "ODDD", src_files, src_up)
    out = []
    if not src_up:
        out.append((WARN, "The CSI shares can't be reached (VPN?), so the ODD extract's month can't be confirmed."))
    for r in rows:
        st, detail = r["local"]["state"], r["local"]["detail"]
        label = r["input"]
        if st == DS.PRESENT:
            out.append((OK, f"{label}: in Inputs ({detail})"))
        elif st == DS.UNKNOWN:
            out.append((WARN, f"{label}: in Inputs, month not confirmed ({detail})"))
        elif label == "DCO":
            out.append((WARN, f"DCO: {detail}. The deck builds without it, but eligible accounts from the DCO will be blank."))
        else:
            fix = ("Data team: land this month's ODD extract in the CSM's OD Data Dumps folder; the 08:00 watch copies it."
                   if label == "ODD extract" else
                   "Data team: land this month's ARS workbook on the client reports share; the 08:00 watch copies it.")
            out.append((STOP, f"{label}: {detail}. {fix}"))
    return out


_WINDOWS = {}


def _window(path):
    """workbook_window, remembered per file landing (path + mtime). Opening a workbook over the share
    takes 0.4-2s; CSM Sheila (the browser builder) checks the same workbooks over and over (2026-09-15)."""
    try:
        key = (str(path), os.stat(path).st_mtime_ns)
    except OSError:
        key = None
    if key in _WINDOWS:
        return _WINDOWS[key]
    w = workbook_window(path)
    if key:
        _WINDOWS[key] = w
    return w


def lift_checks(cid, period, roster):
    """An expired Lift Matrix stops an MM client's build (Aaron, 2026-09-15: "Add the lift matrix date
    check to the build criteria").

    Expired = the workbook's data month is past the Lift Matrix MM End Date (`lift_window`, the same
    reading extract_lift puts in the deck), or the data team's filename flag ("LM EXPIRED", "NEEDS
    LIFT MATRIX"; `perf_actions.lift_matrix_flag`) says so. Either way the per-segment revenue the
    deck charts was set for an earlier window. SM clients have no Lift Matrix and are not checked; a
    missing workbook is input_checks' STOP, not this one's.
    """
    import build_month as BM
    entry = next((r for r in roster if r[0] == cid), None)
    if not entry or entry[2] != "MM":
        return []
    wbs = BM.ars_workbook(R.report_dirs(), cid, period)
    if not wbs:
        return []
    name = os.path.basename(wbs[0])
    try:
        from perf_actions import lift_matrix_flag
        flag = lift_matrix_flag(name)
    except ImportError:
        flag = None
    try:
        w = _window(wbs[0])
    except Exception as e:     # an unreadable workbook is reported, never guessed at
        return [(WARN, f"Lift Matrix: couldn't read its dates from {name} ({type(e).__name__}).")]
    fix = "CSM: create a new Lift Matrix, then build again."
    if w is None:
        return [(WARN, f"Lift Matrix: {name} has no Lift Matrix MM tab.")]
    if w["data_past_end"]:
        return [(STOP, f"Lift Matrix expired: its window is {w['window']}, and the workbook's data is "
                       f"{w['data_date']}. {fix}")]
    if flag:
        return [(STOP, f"Lift Matrix flagged as out of date by the data team (the workbook is named "
                       f"\"{flag}\"). {fix}")]
    if not w["in_window"]:
        return [(WARN, f"Lift Matrix window is {w['window'] or 'undated'}; the workbook's data is {w['data_date']}.")]
    # The window ends with this data month or the next: the build is fine, and the next Lift Matrix is
    # due before it expires (Aaron, 2026-10-28).
    left = _months_between(w["data_date"], w.get("window_end"))
    if left is not None and left <= 1:
        return [(WARN, f"Lift Matrix window ends {w['window_end']}; the next workbook is due. "
                       f"(window {w['window']}; data {w['data_date']})")]
    return [(OK, f"Lift Matrix: current ({w['window']}; data {w['data_date']})")]


def _months_between(a, b):
    """Whole months from month label a to month label b ("Aug 2026"), or None when either is not one."""
    import datetime as _dt
    try:
        da, db = (_dt.datetime.strptime(str(x), "%b %Y") for x in (a, b))
    except (TypeError, ValueError):
        return None
    return (db.year - da.year) * 12 + db.month - da.month


def all_checks(cid, period, row, roster, sent, rebuild=False, combined=False, cp_row=None):
    """Every pre-build check, in the order they print: the rules, then for an ARS client the inputs, the
    Lift Matrix and (combined) the other programs' data; for a client with no ARS, each program's data."""
    if cp_row is None:
        cp_row = cp_roster_row(cid)
    checks = rule_checks(cid, period, row, roster, sent, rebuild=rebuild,
                         in_outputs=decks_in_outputs(cid, period), combined=combined, cp_row=cp_row)
    # Already built and nobody has asked for a rebuild: the inputs are not going to be read,
    # so do not go to the share and ask about them (Aaron, 2026-10-02). These three are the
    # slow checks — the ODD extract's month, the workbook, the Lift Matrix window, and for a
    # combined deck every other program's data. A rebuild re-runs all of them.
    if not rebuild and any(l == ASK for l, _ in checks):
        return checks
    if any(l == STOP for l, _ in checks) and not row:
        return checks
    entry = client_entry(cid, roster, cp_row)
    if entry is None or "ARS" in entry[3]:
        checks += input_checks(cid, period) + lift_checks(cid, period, roster)
        if combined:
            checks += combined_checks(cid, period, roster, cp_row)
        else:
            checks += cashplease_checks(cid)
    else:
        checks += combined_checks(cid, period, roster, cp_row)
    return checks


def combined_checks(cid, period, roster, cp_row=None):
    """What the deck would carry: each program's data, and a stop when none has any."""
    entry = client_entry(cid, roster, cp_row)
    progs = entry[3] if entry else []
    avail = program_availability(cid, period, progs)
    has_ars = "ARS" in progs
    out = [(OK if ok else WARN, f"{p}: {'in the deck' if ok else 'left out'} ({why})")
           for p, (ok, why) in avail.items()]
    if not combined_programs(avail):
        out.append((STOP, "No other program has the data it needs this period, so there is no combined deck "
                          "to build. Build the ARS-only deck." if has_ars else
                          "No program has the data it needs this period, so there is nothing to build."))
    return out


# ------------------------------------------------------------------ Transaction Intelligence
# A SEPARATE presentation, never the Executive Review (Aaron, 2026-10-23: "add the ability to create a
# separate Transaction Intelligence presentation, separate from the currently approved RPE
# presentation"). It is James Gilmore's cut (build/ars_pipeline/ti/, CLAUDE.md): one deck per lens,
# built by ti_build.py from the ODD extract, the client's transaction files and, for the ICS lens,
# the ICS lists. `build <id> --ti` builds it; `status <id> --ti` shows its checks. The RPE deck's
# rules, inputs and Lift Matrix are not consulted, and a TI deck in Outputs never counts as the
# period's RPE deck (decks_in_outputs leaves it out) nor is archived by an RPE build.
TI_TAG = "TI"
TI_MONTHS = 12                       # v5's transaction window, as ti_build.attach_txn asks for it
TI_RESULT_NAME = "_launcher_result_ti.json"
_TI_DECK_RX = re.compile(r"^\d{3,5}-\d{4}\.\d{2}-%s-" % TI_TAG)


def is_ti_deck(name):
    return bool(_TI_DECK_RX.match(os.path.basename(str(name))))


def _ti_modules():
    """James's ti package (pandas behind it), imported once per process."""
    p = str(REPO / "build" / "ars_pipeline")
    if p not in sys.path:
        sys.path.insert(0, p)
    from ti import cut, txn_stage, lens as ti_lens, config as ti_config
    return cut, txn_stage, ti_lens, ti_config


def ti_decks_in_outputs(cid, period):
    """This client's Transaction Intelligence decks for `period` in Outputs, by name."""
    return sorted(p.name for p in R.output_decks(f"{cid}-{period}-{TI_TAG}-*.pptx")
                  if not p.name.startswith("~$") and is_ti_deck(p.name))


_CODE_TABLE_CLIENTS = {}


def code_table_clients():
    """The client ids ars_code_tables.json carries, or None when the file is not in Inputs.

    Read again only when the file's size or modified time changes: it is one file for every
    client, and every client's check would otherwise parse it over the share."""
    p = R.input_dir("ARS codes", create=False) / "ars_code_tables.json"
    try:
        st = p.stat()
    except OSError:
        return None
    key = (str(p), st.st_mtime_ns, st.st_size)
    hit = _CODE_TABLE_CLIENTS.get(key)
    if hit is None:
        doc = json.loads(p.read_text(encoding="utf-8"))
        ids = set()
        for table in ("status_codes", "product_codes", "rege_codes"):
            ids |= set(map(str, (doc.get(table) or {}).keys()))
        _CODE_TABLE_CLIENTS.clear()
        hit = _CODE_TABLE_CLIENTS[key] = frozenset(ids)
    return hit


def txn_months_on_hand(cid, period, months=TI_MONTHS):
    """(the data months with a transaction file on hand, the window's data months) for the window
    of `months` ending at the period's DATA month — from the file NAMES in Inputs/Txn Files/<id>/,
    never by opening a zip (one folder listing). v5's own name and window rules (ti/txn_stage): a
    file dated in month M carries month M-1's data. Months are counted as year*12 + month-1.

    The builder anchors on the ODD's newest month (ti_build: `odd.frame_data_month`), which for a
    cycle's extract is the month before the cycle — 1615's October 2026 extract runs to September,
    and the window it built was Oct 25 to Sep 26 (2026-10-23). The check anchors the same way."""
    _, txn_stage, _, _ = _ti_modules()
    import pandas as pd
    y, m = (int(x) for x in str(period).split("."))
    anchor = pd.Timestamp(y, m, 1) - pd.offsets.MonthEnd(1)       # the data month: the one before the cycle
    hi = anchor.year * 12 + anchor.month - 1
    window = list(range(hi - (months - 1), hi + 1))
    found = set()
    for p in R.txn_files(cid):
        name = p.name[:-4] if p.suffix.lower() == ".zip" else p.name
        if not (txn_stage._is_txn_name(name) and txn_stage.in_window(name, months, anchor)):
            continue
        d = txn_stage.loader.file_date(Path(name))
        found.add(d.year * 12 + d.month - 2)          # the file's month - 1, as the loader reads it
    return found & set(window), window


def _month_label(n):
    import pandas as pd
    return f"{pd.Timestamp(n // 12, n % 12 + 1, 1):%b %y}"


def ti_checks(cid, period, row, roster, sent=None, rebuild=False):
    """Every check before a Transaction Intelligence build, [(level, message)].

    The cut needs: a chapter to build (James's branches add them one at a time), the client on
    ARS in clients.md, this period's ODD extract, the client's codes (ars_code_tables.json, or a
    v5 config file), its transaction files for the window, and for the ICS lens its ICS lists.
    Missing transaction files or ICS lists do not stop the build — the cut states what it could
    not render — so they warn. Like all_checks, the slow checks are skipped when the decks are
    already in Outputs and no rebuild was asked for.
    """
    out = []
    in_out = ti_decks_in_outputs(cid, period)
    if in_out:
        what = (f"The {period} Transaction Intelligence deck{'s are' if len(in_out) > 1 else ' is'} "
                f"already in Outputs ({', '.join(in_out)}).")
        out.append((WARN, what + " Rebuilding, as asked.") if rebuild else (ASK, what))
    if not row:
        out.append((STOP, f"{cid} is not in Client CSM List.csv. Check the client number."))
        return out
    entry = client_entry(cid, roster)
    name = (entry[1] if entry else None) or row.get("client_name") or cid
    out.append((OK, f"{cid} {name} (CSM: {row.get('csm') or 'no CSM'})"))
    if entry is None or "ARS" not in entry[3]:
        out.append((STOP, "The Transaction Intelligence cut is built from the ODD extract, so it is for ARS "
                          "clients; clients.md does not list this client on ARS."))
        return out
    try:
        cut, _, ti_lens, ti_config = _ti_modules()
    except ImportError as e:
        out.append((STOP, f"The Transaction Intelligence code is not installed with this copy of Sheila ({e})."))
        return out
    ics = any(p.startswith("ICS") for p in entry[3])
    if cut.CHAPTERS:
        out.append((OK, f"Chapters: {', '.join(ch.title for ch in cut.CHAPTERS)}; "
                        f"lenses: ARS{' and ICS' if ics else ''}"))
    else:
        out.append((STOP, "No chapter of the Transaction Intelligence cut is ported yet, so there is "
                          "nothing to build. The chapters land one at a time on James's branches."))
    if not rebuild and any(l == ASK for l, _ in out):
        return out
    out += [(l, m) for l, m in input_checks(cid, period)
            if m.startswith(("ODD extract", "The CSI shares"))]
    try:
        cfg = ti_config.config_path()
        in_cfg = cfg.is_file() and str(cid) in (json.loads(cfg.read_text(encoding="utf-8-sig")) or {})
    except (OSError, ValueError):
        in_cfg = False
    if in_cfg:
        out.append((OK, f"Client codes: {cfg.name} (v5 config, as the parity check reads it)"))
    else:
        ids = code_table_clients()
        if ids is None:
            out.append((STOP, "Client codes: ars_code_tables.json is not in Inputs/ARS Settings, so the eligible "
                              "accounts cannot be found. Run scripts/ars_code_tables.py on an ARS database export."))
        elif str(cid) in ids:
            out.append((OK, "Client codes: eligibility and Reg E codes derived from ars_code_tables.json"))
        else:
            out.append((STOP, f"Client codes: {cid} is not in ars_code_tables.json, so the eligible accounts "
                              "cannot be found. Ask Aaron to refresh the code tables."))
    found, window = txn_months_on_hand(cid, period)
    span = f"{_month_label(window[0])} to {_month_label(window[-1])}"
    if not found:
        out.append((WARN, f"Transaction files: none in Inputs/Txn Files for {span}; the transaction chapters "
                          "are stated, not rendered. scripts/land_txn_files.py lands them from the CSM ODDD folders."))
    elif len(found) < len(window):
        gaps = [_month_label(n) for n in window if n not in found]
        out.append((WARN, f"Transaction files: {len(found)} of {len(window)} months on hand ({span}); "
                          f"missing {', '.join(gaps)}. The transaction chapters cover the months on hand."))
    else:
        out.append((OK, f"Transaction files: all {len(window)} months on hand ({span})"))
    if ics:
        try:
            lists = ti_lens.ics_list_files(cid)
        except OSError as e:
            lists = {}
            out.append((WARN, f"ICS lens: the ICS lists could not be read ({e})"))
        have = [f"{k} {v.name}" for k, v in lists.items() if v]
        if have:
            out.append((OK, f"ICS lens: {', '.join(have)}"))
        elif lists:
            out.append((WARN, "ICS lens: no direct-mail list or referral export in Inputs for this client, so "
                              "only the ARS lens is built."))
    return out


def ti_status(cid, period, row, roster, sent=None):
    """The Transaction Intelligence block of a client's status: its checks, state and last build."""
    checks = ti_checks(cid, period, row, roster, sent)
    state = ("stop" if any(l == STOP for l, _ in checks) else
             "ask" if any(l == ASK for l, _ in checks) else "ready")
    res = R.build_artifacts() / "launcher" / period / cid / TI_RESULT_NAME
    try:
        last = json.loads(res.read_text(encoding="utf-8")) if res.exists() else None
    except (OSError, ValueError):
        last = None
    return {"checks": [{"level": l, "text": m} for l, m in checks], "state": state, "last": last,
            "decks": ti_decks_in_outputs(cid, period)}


def ti_to_outputs(cid, deck, client_name=""):
    """Put a validated Transaction Intelligence deck in `Outputs/<CSM>/`, archiving the one it replaces.

    promote_one cannot be used: it files a name it cannot parse (TI is not a program tag) under the
    root archive. Only the SAME file name is superseded — never the client's RPE deck, never the
    other lens. Returns (level, message)."""
    import promote_month as P
    out = R.outputs()
    dest = R.client_outputs(cid, root=out)
    cur = dest / os.path.basename(deck)
    if cur.exists() and P.same(str(cur), deck):
        return OK, f"The deck in Outputs is already identical to this build: {cur}"
    stamp = dt.date.today().isoformat()
    try:
        if cur.exists():
            folder = P.client_folder(out / R.ARCHIVE_DIRNAME, cid, client_name)
            folder.mkdir(parents=True, exist_ok=True)
            arch = folder / f"{cur.stem} (superseded {stamp}){cur.suffix}"
            k = 1
            while arch.exists():
                k += 1
                arch = folder / f"{cur.stem} (superseded {stamp}-{k}){cur.suffix}"
            shutil.move(str(cur), str(arch))
            print(f"         archive   {cur.name}", flush=True)
        dest.mkdir(parents=True, exist_ok=True)
        shutil.copy2(deck, cur)
        if cur.stat().st_size != os.path.getsize(deck):
            raise OSError(f"{cur.name} is {cur.stat().st_size:,} bytes in Outputs, {os.path.getsize(deck):,} built")
    except OSError as e:
        return STOP, (f"The deck built clean but could not be put in Outputs ({e}). If it is open in "
                      "PowerPoint, close it and build again.")
    return OK, f"In Outputs: {cur}"


def build_ti(a, BM, row, period, roster, sent, work):
    """`build <id> --ti`: the Transaction Intelligence decks, one per lens, into Outputs."""
    print(f"\nBuilding the Transaction Intelligence decks: client {a.client}, period {period}\n")
    checks = ti_checks(a.client, period, row, roster, sent, rebuild=a.rebuild)
    for lvl, msg in checks:
        say(lvl, msg)
    if any(l == STOP for l, _ in checks):
        print("\nNot built. Fix the items marked STOP, then run it again.")
        return 1
    if any(l == ASK for l, _ in checks):
        print("\nNot built: this month's Transaction Intelligence decks are already in Outputs. Pass --rebuild to replace them.")
        return ASKED_EXIT
    entry = client_entry(a.client, roster)
    name = BM.deck_name(a.client, entry[1])
    ics = any(p.startswith("ICS") for p in entry[3])
    tdir = work / "ti"
    lk = lock(work)
    t0 = time.time()
    result, delivered, made, where = "did not finish", False, [], []
    stop = threading.Event()
    try:
        tdir.mkdir(parents=True, exist_ok=True)
        for old in tdir.glob("*.pptx"):      # a previous build's decks are never mistaken for this one's
            old.unlink()
        print(f"\nBuilding the ARS{' and ICS' if ics else ''} lens{'es' if ics else ''} (this takes a few minutes)...", flush=True)
        log = tdir / "build.log"           # its own log: the RPE build's steps are not this build's
        log.unlink(missing_ok=True)
        threading.Thread(target=watch_steps, args=(log, stop, t0), daemon=True).start()
        try:
            rc = BM.run([BM.PY, os.path.join(BM.ARSP, "ti_build.py"), a.client, period, name, str(tdir)]
                        + (["--ics"] if ics else []), log)
        finally:
            stop.set()
        made = sorted(str(p) for p in tdir.glob(f"{a.client}-{period}-{TI_TAG}-*.pptx"))
        if rc or not made:
            reason = _log_reason(log) or f"exit code {rc}"
            say(STOP, f"The build stopped: {reason}")
            result = f"stopped: {reason}"
        else:
            sys.path.insert(0, str(REPO / "validation"))
            import validate_deck as V
            gates = []
            for deck in made:
                print(f"  [..]   Validating {os.path.basename(deck)}  ({(time.time() - t0) / 60:.0f} min)", flush=True)
                gate, fails = run_validator(deck)
                for f in fails:
                    say(STOP, f"Validator: {f}")
                if gate.startswith("0 FAIL"):
                    pkg = V.package_findings(deck)
                    if pkg:
                        gate = f"package check failed ({len(pkg)} finding(s): {pkg[0]})"
                gates.append(gate)
                if not gate.startswith("0 FAIL"):
                    say(STOP, f"Validation of {os.path.basename(deck)}: {gate}. Only a deck with 0 FAIL goes to Outputs.")
                    continue
                say(OK, f"Validation of {os.path.basename(deck)}: {gate}")
                lvl, msg = ti_to_outputs(a.client, deck, entry[1])
                say(lvl, msg)
                if lvl == OK:
                    where.append(msg)
            result = "; ".join(gates)
            delivered = bool(where) and len(where) == len(made)
    finally:
        lk.unlink(missing_ok=True)
    (work / TI_RESULT_NAME).write_text(json.dumps({
        "client": a.client, "period": period, "decks": [os.path.basename(d) for d in made],
        "lenses": ["ARS"] + (["ICS"] if ics else []), "result": result, "delivered": delivered,
        "by": getpass.getuser(), "finished": f"{dt.datetime.now():%Y-%m-%d %H:%M}",
        "minutes": round((time.time() - t0) / 60, 1)}, indent=1), encoding="utf-8")
    if delivered:
        print(f"\nDone. The Transaction Intelligence deck{'s are' if len(made) > 1 else ' is'} in Outputs.")
        return 0
    print("\nNot put in Outputs. Details are in " + str(tdir / "build.log"))
    return 1


# ------------------------------------------------------------------ ARS Companion deck
# James Gilmore's analysis slides as a deck of their own (Aaron, 2026-10-27: "Build functionality in Sheila (a
# new button) to build a ARS Companion Deck with James's slides"). A SEPARATE presentation beside the approved
# Executive Review, never in its place and never changing it: the ARS deck is built in a staging folder of its
# own with every opt-in view switched on (RPE_JAMES_SLIDES, RPE_SPEND_SLIDES, RPE_COMPANION), and
# companion_deck.py keeps only the slides those views added. `build <id> --companion` builds it;
# `status <id> --companion` shows its checks. Filed in Outputs with the tag COMP, which is not a program tag, so
# promote_month never reads it as an ARS deck, and decks_in_outputs never counts it as the period's RPE deck.
COMPANION_TAG = "COMP"
COMPANION_RESULT_NAME = "_launcher_result_companion.json"
_COMPANION_DECK_RX = re.compile(r"^\d{3,5}-\d{4}\.\d{2}-%s-" % COMPANION_TAG)
COMPANION_ENV = {"RPE_JAMES_SLIDES": "1", "RPE_SPEND_SLIDES": "1", "RPE_COMPANION": "1"}


def is_companion_deck(name):
    return bool(_COMPANION_DECK_RX.match(os.path.basename(str(name))))


def companion_deck_name(cid, period, client):
    return f"{cid}-{period}-{COMPANION_TAG}-{client} ARS Companion.pptx"


def companion_decks_in_outputs(cid, period):
    """This client's ARS Companion deck for `period` in Outputs, by name."""
    return sorted(p.name for p in R.output_decks(f"{cid}-{period}-{COMPANION_TAG}-*.pptx")
                  if not p.name.startswith("~$") and is_companion_deck(p.name))


def companion_checks(cid, period, row, roster, sent=None, rebuild=False):
    """Every check before an ARS Companion build, [(level, message)].

    The companion is built from the ARS pipeline, so it needs what an ARS deck needs: the client on ARS
    in clients.md and the Velocity product list, this period's ODD extract, the ARS workbook and DCO, and
    the Lift Matrix window. Like all_checks, the slow checks are skipped when the deck is already in
    Outputs and no rebuild was asked for."""
    out = []
    in_out = companion_decks_in_outputs(cid, period)
    if in_out:
        what = f"The {period} ARS Companion deck is already in Outputs ({in_out[0]})."
        out.append((WARN, what + " Rebuilding, as asked.") if rebuild else (ASK, what))
    if not row:
        out.append((STOP, f"{cid} is not in Client CSM List.csv. Check the client number."))
        return out
    entry = client_entry(cid, roster)
    name = (entry[1] if entry else None) or row.get("client_name") or cid
    out.append((OK, f"{cid} {name} (CSM: {row.get('csm') or 'no CSM'})"))
    if entry is None or "ARS" not in entry[3]:
        out.append((STOP, "The ARS Companion deck is built from the ODD extract and the ARS workbook, so it is "
                          "for ARS clients; clients.md does not list this client on ARS."))
        return out
    products = [x.strip() for x in (row.get("products") or "").split(";") if x.strip()]
    if products and "ARS" not in products:
        out.append((STOP, f"Not an ARS client: the Velocity product list shows {', '.join(products)}. "
                          "Only ARS clients get ARS decks."))
        return out
    out.append((OK, f"clients.md: {'-'.join(entry[3])}, {entry[2] or 'path unknown'} workbook; "
                    "the Companion carries James's analysis slides only"))
    if not rebuild and any(l == ASK for l, _ in out):
        return out
    return out + input_checks(cid, period) + lift_checks(cid, period, roster)


def companion_status(cid, period, row, roster, sent=None):
    """The ARS Companion block of a client's status: its checks, state and last build."""
    checks = companion_checks(cid, period, row, roster, sent)
    state = ("stop" if any(l == STOP for l, _ in checks) else
             "ask" if any(l == ASK for l, _ in checks) else "ready")
    res = R.build_artifacts() / "launcher" / period / cid / COMPANION_RESULT_NAME
    try:
        last = json.loads(res.read_text(encoding="utf-8")) if res.exists() else None
    except (OSError, ValueError):
        last = None
    return {"checks": [{"level": l, "text": m} for l, m in checks], "state": state, "last": last,
            "decks": companion_decks_in_outputs(cid, period)}


def build_companion(a, BM, row, period, roster, sent, work):
    """`build <id> --companion`: the ARS Companion deck, into Outputs."""
    print(f"\nBuilding the ARS Companion deck: client {a.client}, period {period}\n")
    checks = companion_checks(a.client, period, row, roster, sent, rebuild=a.rebuild)
    for lvl, msg in checks:
        say(lvl, msg)
    if any(l == STOP for l, _ in checks):
        print("\nNot built. Fix the items marked STOP, then run it again.")
        return 1
    if any(l == ASK for l, _ in checks):
        print("\nNot built: this month's ARS Companion deck is already in Outputs. Pass --rebuild to replace it.")
        return ASKED_EXIT
    entry = client_entry(a.client, roster)
    client = entry[1]
    stage = work / "companion"
    lk = lock(work)
    t0 = time.time()
    result, delivered, deck, where = "did not finish", False, None, None
    stop = threading.Event()
    try:
        stage.mkdir(parents=True, exist_ok=True)
        log = stage / a.client / "build.log"
        print("\nBuilding the ARS deck with James's views, then keeping those slides (3 to 20 minutes)...", flush=True)
        threading.Thread(target=watch_steps, args=(log, stop, t0), daemon=True).start()
        # build_month copies the environment ONCE, when it is imported (_CHILD_ENV), so the flags must go there:
        # setting os.environ here never reached the build and the views were never added (1075, 2026-10-28).
        BM._CHILD_ENV.update(COMPANION_ENV)
        try:
            err, made = BM.build_client(a.client, client, entry[2], ["ARS"], period, str(stage))
        finally:
            stop.set()
        full = made.get("ARS")
        if err or not full:
            reason = _log_reason(log) or err
            say(STOP, f"The build stopped at '{err}': {reason}")
            result = f"stopped at {err}: {reason}"
        else:
            sys.path.insert(0, os.path.join(str(REPO), "build", "ars_pipeline"))
            import companion_deck as CD
            deck = str(stage / a.client / companion_deck_name(a.client, period, client))
            try:
                n = CD.build(full, str(stage / a.client / "companion_slides.json"), deck)
            except SystemExit as e:
                say(STOP, f"The companion deck could not be cut from the build: {e}")
                result = f"not cut: {e}"
                deck = None
            else:
                say(OK, f"{n} analysis slide{'s' if n != 1 else ''} kept from the build")
        if deck:
            sys.path.insert(0, str(REPO / "validation"))
            import validate_deck as V
            print(f"  [..]   Validating the deck  ({(time.time() - t0) / 60:.0f} min)", flush=True)
            # No base.json: its cross-check looks for the whole ARS deck's figures (LTD profit, months) in the
            # deck, and this one carries only James's views; each view's own builder checks its figures.
            gate, fails = run_validator(deck)
            for f in fails:
                say(STOP, f"Validator: {f}")
            if gate.startswith("0 FAIL"):
                pkg = V.package_findings(deck)
                if pkg:
                    gate = f"package check failed ({len(pkg)} finding(s): {pkg[0]})"
            result = gate
            if not gate.startswith("0 FAIL"):
                say(STOP, f"Validation: {gate}. Only a deck with 0 FAIL goes to Outputs.")
            else:
                say(OK, f"Validation: {gate}")
                lvl, msg = ti_to_outputs(a.client, deck, client)     # files any aux deck: only its own name is superseded
                say(lvl, msg)
                delivered = lvl == OK
                where = msg if delivered else None
                if not delivered:
                    result = gate + " (not put in Outputs)"
    finally:
        lk.unlink(missing_ok=True)
    (work / COMPANION_RESULT_NAME).write_text(json.dumps({
        "client": a.client, "period": period, "deck": os.path.basename(deck) if deck else None,
        "result": result, "delivered": delivered, "by": getpass.getuser(),
        "finished": f"{dt.datetime.now():%Y-%m-%d %H:%M}", "minutes": round((time.time() - t0) / 60, 1)},
        indent=1), encoding="utf-8")
    if delivered:
        print("\nDone. The ARS Companion deck is in Outputs.")
        return 0
    print("\nNot put in Outputs. Details are in " + str(stage / a.client / "build.log"))
    return 1


# ------------------------------------------------------------------ locking
def _process_start(pid):
    """The process's creation time (Windows FILETIME), or None when it cannot be read.

    A pid alone is not an identity: Windows hands a dead process's number to a new one. Paired with the
    start time it is."""
    if os.name != "nt":
        return None
    import ctypes
    from ctypes import wintypes
    k = ctypes.windll.kernel32
    k.OpenProcess.restype = wintypes.HANDLE
    h = k.OpenProcess(0x1000, False, pid)          # PROCESS_QUERY_LIMITED_INFORMATION
    if not h:
        return None
    try:
        c, e, kt, u = (wintypes.FILETIME() for _ in range(4))
        if not k.GetProcessTimes(h, ctypes.byref(c), ctypes.byref(e), ctypes.byref(kt), ctypes.byref(u)):
            return None
        return (c.dwHighDateTime << 32) | c.dwLowDateTime
    finally:
        k.CloseHandle(h)


def _process_alive(pid, started=None):
    """True when process `pid` is still running (and, when `started` is given, is the SAME process)."""
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes
        k = ctypes.windll.kernel32
        k.OpenProcess.restype = wintypes.HANDLE
        h = k.OpenProcess(0x1000, False, pid)
        if not h:
            return ctypes.GetLastError() == 5      # access denied: it exists, we may not look
        try:
            code = wintypes.DWORD()
            if not k.GetExitCodeProcess(h, ctypes.byref(code)) or code.value != 259:      # STILL_ACTIVE
                return False
        finally:
            k.CloseHandle(h)
        return started is None or _process_start(pid) in (None, started)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


_HOLDER_RX = re.compile(r"host (\S+), pid (\d+)(?:, started (\d+))?")


def _holder_is_gone(holder):
    """The lock names this machine and a process that no longer exists: a build that was killed.

    A lock from another machine, or one with no process on it, can't be judged here and is left to the age
    limit. 2026-10-06: a killed build left its lock, and the client could not be rebuilt for hours."""
    m = _HOLDER_RX.search(holder or "")
    if not m or m.group(1).lower() != _host().lower():
        return False
    return not _process_alive(int(m.group(2)), int(m.group(3)) if m.group(3) else None)


def _host():
    import socket
    return socket.gethostname()


def lock(work_dir):
    work_dir.mkdir(parents=True, exist_ok=True)
    p = work_dir / ".launcher.lock"
    if p.exists():
        age_h = (time.time() - p.stat().st_mtime) / 3600
        holder = p.read_text(encoding="utf-8", errors="replace").strip()
        if age_h < LOCK_STALE_HOURS and not _holder_is_gone(holder):
            raise SystemExit(f"  [STOP] Someone is already building this client ({holder}). Try again when it finishes.")
        if age_h < LOCK_STALE_HOURS:
            print(f"  [..]   The last build's lock ({holder}) belongs to a process that is gone. Taking over.")
    pid = os.getpid()
    started = _process_start(pid)
    p.write_text(f"{getpass.getuser()} since {dt.datetime.now():%Y-%m-%d %H:%M} (host {_host()}, pid {pid}"
                 + (f", started {started}" if started else "") + ")", encoding="utf-8")
    return p


# ------------------------------------------------------------------ commands
def _context(cid, period):
    import build_month as BM
    import deck_status as DS
    row = csm_list_row(cid)
    period = period or cycle_period()
    if not period:
        say(STOP, "No ARS workbooks are in Inputs at all, so there is no period to build.")
        raise SystemExit(2)
    roster, _ = BM.read_roster()
    sent = DS.read_deliveries()["sent"]
    work = R.build_artifacts() / "launcher" / period / cid
    return BM, row, period, roster, sent, work


def cmd_status(a):
    BM, row, period, roster, sent, work = _context(a.client, a.period)
    if getattr(a, "ti", False):
        print(f"\nTransaction Intelligence status: client {a.client}, period {period}\n")
        checks = ti_checks(a.client, period, row, roster, sent)
        for lvl, msg in checks:
            say(lvl, msg)
        if any(l == STOP for l, _ in checks):
            print("\nNot ready to build.")
            return 1
        if any(l == ASK for l, _ in checks):
            print("\nReady to rebuild (pass --rebuild).")
            return ASKED_EXIT
        print("\nReady to build.")
        return 0
    if getattr(a, "companion", False):
        print(f"\nARS Companion status: client {a.client}, period {period}\n")
        checks = companion_checks(a.client, period, row, roster, sent)
        for lvl, msg in checks:
            say(lvl, msg)
        if any(l == STOP for l, _ in checks):
            print("\nNot ready to build.")
            return 1
        if any(l == ASK for l, _ in checks):
            print("\nReady to rebuild (pass --rebuild).")
            return ASKED_EXIT
        print("\nReady to build.")
        return 0
    print(f"\nDeck status: client {a.client}, period {period}\n")
    checks = all_checks(a.client, period, row, roster, sent)
    for lvl, msg in checks:
        say(lvl, msg)
    res = work / "_launcher_result.json"
    if res.exists():
        r = json.loads(res.read_text(encoding="utf-8"))
        say(OK if r.get("delivered") else WARN, f"Last launcher build {r.get('finished')}: {r.get('result')}"
                                                + ("" if r.get("delivered") else " (not put in Outputs)"))
    if any(l == STOP for l, _ in checks):
        print("\nNot ready to build.")
        return 1
    if any(l == ASK for l, _ in checks):
        print("\nReady to rebuild, if something has changed since it was built (a formatting change, a corrected input).")
        return ASKED_EXIT
    print("\nReady to build.")
    return 0


def step_of(line):
    """The plain name of the build step a build.log command line starts, or None."""
    if not line.startswith("$ "):
        return None
    m = re.search(r"([\w]+\.py)\b", line)
    return STEPS.get(m.group(1)) if m else None


def watch_steps(log, stop, t0):
    """Print each step as build.log records it, until `stop` is set."""
    pos, seen = 0, set()
    while not stop.wait(2):
        try:
            st = log.stat()
            if st.st_mtime < t0 - 1:      # the previous build's log, not yet truncated
                continue
            if st.st_size < pos:
                pos = 0
            with open(log, "rb") as f:
                f.seek(pos)
                chunk = f.read()
                pos = f.tell()
        except OSError:
            continue
        for line in chunk.decode("utf-8", "replace").splitlines():
            step = step_of(line)
            if step and step not in seen:
                seen.add(step)
                print(f"  [..]   {step}  ({(time.time() - t0) / 60:.0f} min)", flush=True)


def to_outputs(cid, deck):
    """Put a validated deck in `Outputs/<CSM>/`, archiving what it supersedes.

    Returns (level, message). A deck already identical in Outputs is left as it is. A locked
    file (open in PowerPoint) fails the whole move — promote_one is all or nothing.
    """
    import promote_month as P
    out = R.outputs()
    dest = R.client_outputs(cid, root=out)
    cur = dest / os.path.basename(deck)
    if cur.exists() and P.same(str(cur), deck):
        return OK, f"The deck in Outputs is already identical to this build: {cur}"
    try:
        n, _ = P.promote_one(deck, dest, out / R.ARCHIVE_DIRNAME, dt.date.today().isoformat(), apply=True,
                             legacy=(out,), log=lambda m: print("         " + m.strip(), flush=True))
    except OSError as e:
        return STOP, (f"The deck built clean but could not be put in Outputs ({e}). If this client's deck "
                      "is open in PowerPoint, close it and run Build ARS Deck again.")
    # One deck per client per month: a combined deck supersedes the ARS-only one and the other way round,
    # which promote_one (same filename only) does not see. Moved to the archive, never deleted.
    n += supersede_other_ars_decks(cid, deck, out)
    return OK, f"In Outputs: {cur}" + (f" ({n} older file(s) archived, none deleted)" if n else "")


def supersede_other_ars_decks(cid, deck, out):
    """Archive this client's other decks for the same period (a different program mix). One deck per
    client per period, whatever the mix: an ICS-CP deck supersedes a plain ICS one and the other way round."""
    import promote_month as P
    info = P.parse_deck_name(os.path.basename(deck))
    if not info:
        return 0
    stamp = dt.date.today().isoformat()
    moved = 0
    for other in R.output_decks(f"{cid}-{info['period']}-*.pptx"):
        if (other.name.startswith("~$") or other.name == os.path.basename(deck) or is_ti_deck(other.name)
                or is_companion_deck(other.name)):
            continue                    # a Transaction Intelligence or Companion deck is a separate presentation
        folder = P.client_folder(out / R.ARCHIVE_DIRNAME, cid, info.get("client") or "")
        folder.mkdir(parents=True, exist_ok=True)
        dest = folder / f"{other.stem} (superseded {stamp}){other.suffix}"
        k = 1
        while dest.exists():
            k += 1
            dest = folder / f"{other.stem} (superseded {stamp}-{k}){other.suffix}"
        try:
            shutil.move(str(other), str(dest))
            moved += 1
            print(f"         archive   {other.name} (replaced by a different program mix)", flush=True)
        except OSError as e:
            print(f"         !! could not archive {other.name} ({e}); it is still in Outputs", flush=True)
    return moved


def cmd_build(a):
    BM, row, period, roster, sent, work = _context(a.client, a.period)
    if getattr(a, "ti", False):
        return build_ti(a, BM, row, period, roster, sent, work)
    if getattr(a, "companion", False):
        return build_companion(a, BM, row, period, roster, sent, work)
    combined = getattr(a, "combined", False)
    cp_row = cp_roster_row(a.client)
    entry = client_entry(a.client, roster, cp_row)
    if entry is not None and "ARS" not in entry[3]:
        combined = True             # a non-ARS client builds everything with data; there is no other deck
    print(f"\nBuilding the {'combined' if combined else 'ARS'} deck: client {a.client}, period {period}\n")
    checks = all_checks(a.client, period, row, roster, sent, rebuild=a.rebuild, combined=combined, cp_row=cp_row)
    for lvl, msg in checks:
        say(lvl, msg)
    if any(l == STOP for l, _ in checks):
        print("\nNot built. Fix the items marked STOP, then run it again.")
        return 1
    if any(l == ASK for l, _ in checks):
        print("\nNot built: this month's deck is already in Outputs. To rebuild it, answer Y when Build ARS Deck asks, or pass --rebuild.")
        return ASKED_EXIT

    name = BM.deck_name(a.client, entry[1])
    # A plain build is ARS, plus CashPlease for a client who ships it as a section; a combined
    # build adds the other programs whose data is on hand; a non-ARS client builds every program
    # with data (build_programs).
    progs = build_programs(entry[3], program_availability(a.client, period, entry[3]), combined)
    multi = len(progs) > 1          # assembled from sections: the deliverable is the combined file
    lk = lock(work)
    t0 = time.time()
    made, result, delivered, where = {}, "did not finish", False, None
    stop = threading.Event()
    try:
        print(f"\nBuilding {'-'.join(progs)} (this takes 3 to 20 minutes)...", flush=True)
        threading.Thread(target=watch_steps, args=(work / "build.log", stop, t0), daemon=True).start()
        try:
            err, made = BM.build_client(a.client, name, entry[2], progs, period, str(work.parent))
        finally:
            stop.set()
        deck = made.get("DELIVERABLE")      # build_month names the one file to ship, single or assembled
        if err or not deck:
            reason = _log_reason(work / "build.log") or err
            say(STOP, f"The build stopped at '{err}': {reason}")
            result = f"stopped at {err}: {reason}"
        else:
            print(f"  [..]   Validating the deck  ({(time.time() - t0) / 60:.0f} min)", flush=True)
            gate, fails = run_validator(deck, str(work / "base.json"))
            for f in fails:
                say(STOP, f"Validator: {f}")
            if multi and gate.startswith("0 FAIL"):
                # A deck assembled from sections: check the package, which the text rules can't see.
                sys.path.insert(0, str(REPO / "validation"))
                import validate_deck as V
                pkg = V.package_findings(deck)
                if pkg:
                    gate = f"package check failed ({len(pkg)} finding(s): {pkg[0]})"
            result = gate
            if not gate.startswith("0 FAIL"):
                say(STOP, f"Validation: {gate}. Only a deck with 0 FAIL goes to Outputs.")
            else:
                say(OK, f"Validation: {gate}")
                lvl, msg = to_outputs(a.client, deck)
                say(lvl, msg)
                delivered = lvl == OK
                where = msg if delivered else None
                if not delivered:
                    result = gate + " (not put in Outputs)"
    finally:
        lk.unlink(missing_ok=True)
    (work / "_launcher_result.json").write_text(json.dumps({
        "client": a.client, "period": period, "deck": made.get("DELIVERABLE"),
        "programs": progs, "combined": combined, "result": result,
        "delivered": delivered, "by": getpass.getuser(),
        "finished": f"{dt.datetime.now():%Y-%m-%d %H:%M}", "minutes": round((time.time() - t0) / 60, 1)},
        indent=1), encoding="utf-8")
    if delivered:
        print(f"\nDone. The deck is in Outputs, ready to review, save as PDF and email.")
        return 0
    print("\nNot put in Outputs. Details are in " + str(work / "build.log"))
    return 1


def run_validator(deck, base=None):
    """(the validator's verdict line, its FAIL lines). One run of validate_deck.py.

    build_month.validate keeps only the verdict, and Sheila showed "1 FAIL, 10 REVIEW" with
    nothing to say which slide or why (Austin Bank's Transaction Intelligence build,
    2026-10-26). The FAIL lines are what a CSM, or Aaron, needs to act on."""
    import build_month as BM
    cmd = [BM.PY, os.path.join(BM.REPO, "validation", "validate_deck.py"), str(deck)]
    if base and os.path.exists(base):
        cmd.append(str(base))
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    lines = [l.strip() for l in r.stdout.splitlines()]
    verdict = next((l for l in lines if "FAIL," in l), "?")
    fails = [l for l in lines if l.startswith("[FAIL")]
    return verdict, fails


def _log_reason(log):
    if not log.exists():
        return ""
    lines = [l.strip() for l in log.read_text(encoding="utf-8", errors="replace").splitlines() if l.strip()]
    for key in ("POSSIBLE DATA ISSUE", "UNEVALUATED WORKBOOK"):
        hit = next((l for l in reversed(lines) if key in l), None)
        if hit:
            return hit
    return lines[-1] if lines else ""


def main(argv=None):
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for c in ("status", "build"):
        sp = sub.add_parser(c)
        sp.add_argument("client")
        sp.add_argument("--period", default=None, help="YYYY.MM; default: the newest ARS workbook period in Inputs")
        sp.add_argument("--ti", action="store_true",
                        help="the Transaction Intelligence decks (a separate presentation), not the RPE deck")
        sp.add_argument("--companion", action="store_true",
                        help="the ARS Companion deck (James's analysis slides, a separate presentation), not the RPE deck")
        if c == "build":
            sp.add_argument("--rebuild", action="store_true", help="rebuild a deck already recorded as sent")
            sp.add_argument("--combined", action="store_true",
                            help="one deck with ARS plus every other clients.md program that has its data")
    a = ap.parse_args(argv)
    a.client = a.client.strip()
    if not re.fullmatch(r"\d{3,5}", a.client):
        print(f"  [STOP] '{a.client}' is not a client number.")
        return 2
    if a.period and not re.fullmatch(r"20\d\d\.\d\d", a.period):
        print(f"  [STOP] Period must look like 2026.09, not '{a.period}'.")
        return 2
    return {"status": cmd_status, "build": cmd_build}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
