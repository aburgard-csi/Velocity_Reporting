#!/usr/bin/env python3
"""ARS deck launcher — build one client's ARS deck into Outputs without Claude.

    python scripts/ars_launcher.py status <client id> [--period 2026.09]
    python scripts/ars_launcher.py build  <client id> [--period 2026.09] [--rebuild] [--combined]

`--combined` builds one deck with ARS plus every other clients.md program that has the data it
needs this period (`program_availability`): ICS from its VIP sheet or, without one, from the ICS
workbook and referral files in Inputs; MRPC from its VIP sheet. The CSM chooses in CSM Sheila
(Aaron, 2026-09-16: "add a second Create button so the CSM can elect to build an ARS only deck, or a
combined deck for whichever products have the appropriate data").

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
    "assemble_combined.py": "Combining the sections",
}


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


# ------------------------------------------------------------------ the checks
def program_availability(cid, period, programs):
    """For each clients.md program other than ARS: (ok, how or why not).

    ICS: the client's VIP sheet, else the local ICS files (`ics_local_sheet.available`: the ICS workbook,
    referral detail and direct-mail lists James and the mailbox land in Inputs). MRPC: its VIP sheet.
    Anything else (CashPlease) is not built by the launcher and is left out.
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
    return out


def combined_programs(availability):
    """The programs a combined deck would carry besides ARS, in section order."""
    return [p for p in ("ICS", "MRPC") if availability.get(p, (False,))[0]]


def rule_checks(cid, period, row, roster, sent, rebuild=False, in_outputs=(), combined=False):
    """The launcher's rules, independent of the filesystem so they can be tested.

    `row` is the Client CSM List row, `roster` the build_month.read_roster() active list,
    `sent` the deliveries.json "sent" map. Returns [(level, message)]. `combined` is a combined-deck
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
    entry = next((r for r in roster if r[0] == cid), None)
    # clients.md names the client, as it names the deck. The Client CSM List name is taken from a
    # workbook filename and can carry a data-team flag ("LM EXPIRED-USF CU / USF CU", 2026-09-15).
    name = (entry[1] if entry else None) or row.get("client_name") or cid
    csm = row.get("csm") or "no CSM"
    out.append((OK, f"{cid} {name} (CSM: {csm})"))

    products = [p.strip() for p in (row.get("products") or "").split(";") if p.strip()]
    if not products:
        out.append((WARN, "The Velocity product list has no products for this client; ARS is assumed from clients.md."))
    elif "ARS" not in products:
        out.append((STOP, f"Not an ARS client: the Velocity product list shows {', '.join(products)}. "
                          "Only ARS clients get ARS decks."))

    if entry is None or "ARS" not in entry[3]:
        out.append((STOP, "clients.md does not list this client for ARS, and that file decides what gets built. "
                          "Ask Aaron to add it."))
    else:
        out.append((OK, f"clients.md: {'-'.join(entry[3])}, {entry[2] or 'path unknown'} workbook"))
        # Checked before the build now that a clean build goes straight to Outputs: a lone ARS
        # deck must never replace one of Aaron's combined decks. Any CSM may build a combined deck
        # (Aaron, 2026-09-16), so for his clients that is the build on offer.
        if csm == AARON and len(entry[3]) > 1 and not combined:
            out.append((STOP, f"This client ships a combined {'-'.join(entry[3])} deck, so build the combined "
                              "deck instead of an ARS-only one."))

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
    """This client's ARS-bearing decks for `period` in Outputs (any CSM folder), by name."""
    return sorted(p.name for p in R.output_decks(f"{cid}-{period}-ARS*.pptx") if not p.name.startswith("~$"))


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
    return [(OK, f"Lift Matrix: current ({w['window']}; data {w['data_date']})")]


def all_checks(cid, period, row, roster, sent, rebuild=False, combined=False):
    """Every pre-build check, in the order they print: the rules, the inputs, the Lift Matrix, and for a
    combined deck the other programs' data."""
    checks = rule_checks(cid, period, row, roster, sent, rebuild=rebuild,
                         in_outputs=decks_in_outputs(cid, period), combined=combined)
    # Already built and nobody has asked for a rebuild: the inputs are not going to be read,
    # so do not go to the share and ask about them (Aaron, 2026-10-02). These three are the
    # slow checks — the ODD extract's month, the workbook, the Lift Matrix window, and for a
    # combined deck every other program's data. A rebuild re-runs all of them.
    if not rebuild and any(l == ASK for l, _ in checks):
        return checks
    checks += input_checks(cid, period) + lift_checks(cid, period, roster)
    if combined:
        checks += combined_checks(cid, period, roster)
    return checks


def combined_checks(cid, period, roster):
    """What a combined deck would carry: each other program's data, and a stop when none has any."""
    entry = next((r for r in roster if r[0] == cid), None)
    avail = program_availability(cid, period, entry[3] if entry else [])
    out = [(OK if ok else WARN, f"{p}: {'in the combined deck' if ok else 'left out'} ({why})")
           for p, (ok, why) in avail.items()]
    if not combined_programs(avail):
        out.append((STOP, "No other program has the data it needs this period, so there is no combined deck "
                          "to build. Build the ARS-only deck."))
    return out


# ------------------------------------------------------------------ locking
def lock(work_dir):
    work_dir.mkdir(parents=True, exist_ok=True)
    p = work_dir / ".launcher.lock"
    if p.exists():
        age_h = (time.time() - p.stat().st_mtime) / 3600
        holder = p.read_text(encoding="utf-8", errors="replace").strip()
        if age_h < LOCK_STALE_HOURS:
            raise SystemExit(f"  [STOP] Someone is already building this client ({holder}). Try again when it finishes.")
    p.write_text(f"{getpass.getuser()} since {dt.datetime.now():%Y-%m-%d %H:%M}", encoding="utf-8")
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
    print(f"\nARS deck status: client {a.client}, period {period}\n")
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
    """Archive this client's other ARS-bearing decks for the same period (a different program mix)."""
    import promote_month as P
    info = P.parse_deck_name(os.path.basename(deck))
    if not info:
        return 0
    stamp = dt.date.today().isoformat()
    moved = 0
    for other in R.output_decks(f"{cid}-{info['period']}-ARS*.pptx"):
        if other.name.startswith("~$") or other.name == os.path.basename(deck):
            continue
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
    combined = getattr(a, "combined", False)
    print(f"\nBuilding the {'combined' if combined else 'ARS'} deck: client {a.client}, period {period}\n")
    checks = all_checks(a.client, period, row, roster, sent, rebuild=a.rebuild, combined=combined)
    for lvl, msg in checks:
        say(lvl, msg)
    if any(l == STOP for l, _ in checks):
        print("\nNot built. Fix the items marked STOP, then run it again.")
        return 1
    if any(l == ASK for l, _ in checks):
        print("\nNot built: this month's deck is already in Outputs. To rebuild it, answer Y when Build ARS Deck asks, or pass --rebuild.")
        return ASKED_EXIT

    entry = next(r for r in roster if r[0] == a.client)
    name = BM.deck_name(a.client, entry[1])
    progs = ["ARS"]
    if combined:
        extra = combined_programs(program_availability(a.client, period, entry[3]))
        # keep clients.md's own token (e.g. ICS-REFERRALS) so build_month builds the right shape
        progs += [next(t for t in entry[3] if t.startswith(p)) for p in extra]
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
        deck = made.get("DELIVERABLE") if combined else made.get("ARS")
        if err or not deck:
            reason = _log_reason(work / "build.log") or err
            say(STOP, f"The build stopped at '{err}': {reason}")
            result = f"stopped at {err}: {reason}"
        else:
            print(f"  [..]   Validating the deck  ({(time.time() - t0) / 60:.0f} min)", flush=True)
            gate = BM.validate(deck, str(work / "base.json"))
            if combined and gate.startswith("0 FAIL"):
                # A combined deck is assembled from parts; check the package, which the text rules can't see.
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
        "client": a.client, "period": period, "deck": made.get("DELIVERABLE") if combined else made.get("ARS"),
        "programs": progs, "combined": combined, "result": result,
        "delivered": delivered, "by": getpass.getuser(),
        "finished": f"{dt.datetime.now():%Y-%m-%d %H:%M}", "minutes": round((time.time() - t0) / 60, 1)},
        indent=1), encoding="utf-8")
    if delivered:
        print(f"\nDone. The deck is in Outputs, ready to review, save as PDF and email.")
        return 0
    print("\nNot put in Outputs. Details are in " + str(work / "build.log"))
    return 1


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
