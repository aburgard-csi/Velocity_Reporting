#!/usr/bin/env python3
"""
build_month.py — build the monthly client review decks for one period.

The MONTHLY delivery: every active client, every month. Not the Executive
Summit, which runs a couple of times a year and only for attendees (Aaron,
2026-08-29) — different audience, different cadence, different deck.

The roster comes from `clients.md` and nowhere else. That file's own rule is
"this file decides what gets built, not the presence of a data file", so a driver
carrying its own hardcoded list would be a second answer to the same question and
would silently drift. A client whose row this parser cannot read is REPORTED, not
skipped: a roster line nobody builds is the failure mode clients.md exists to
prevent.

Usage:
    python3 scripts/build_month.py <period> <out-dir> [--only 1075,1204]

    period    YYYY.MM, e.g. 2026.08
    out-dir   staging directory; one folder per client, nothing is delivered

Exit code is the number of clients that failed, so it can gate a delivery.
"""
import argparse, glob, json, os, re, subprocess, sys, time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "build"))
import rpe_env as R                                            # noqa: E402

PY = sys.executable
ARSP = os.path.join(REPO, "build", "ars_pipeline")
TPL = os.path.join(REPO, "templates")
ROSTER_FILE = os.path.join(REPO, "clients.md")


# ----------------------------------------------------------------- roster
def _cells(line):
    return [c.strip() for c in line.strip().strip("|").split("|")]


# clients.md groups its tables under bold headings, and the heading is what gives
# a row its meaning — a 4-column row is an ICS-only client under one heading and a
# CANCELLED client under another. Counting columns cannot tell them apart, and
# guessing wrong either drops a client or builds one that has no programs.
_SECTION_PATTERNS = [
    (re.compile(r"##\s*Active clients", re.I),      "active"),
    (re.compile(r"\*\*MRPC-only clients", re.I),     "mrpc_only"),
    (re.compile(r"\*\*ICS-only clients", re.I),      "ics_only"),
    (re.compile(r"\*\*Cancelled\s*/\s*ending", re.I), "cancelled"),
    # CashPlease has its OWN roster table in this file, read by the CashPlease
    # pipeline's `cp_roster.py`. It must be skipped here, not inherited from whatever
    # section precedes it: it sits after the ICS-only table, so without this every
    # CashPlease client was read as an ICS client — including 1658 Truliant, which has
    # no RPE program at all and is exactly the row `clients.md` exists to keep unbuilt.
    (re.compile(r"#{2,4}\s*CashPlease", re.I),      "cashplease"),
    (re.compile(r"##\s*Status changes", re.I),      "prose"),
    (re.compile(r"##\s*Gaps needing", re.I),        "prose"),
    (re.compile(r"##\s*What is NOT a signal", re.I), "prose"),
    (re.compile(r"##\s*What the evidence", re.I),   "prose"),
]


def read_roster(path=ROSTER_FILE):
    """[(id, name, MM|SM|None, [programs])] from clients.md.

    Rows are interpreted by the SECTION they sit under, not by column count.
    A program counts as active only on a literal "yes" (or "referrals-only" for
    ICS); "ended", "cancelled" and "—" are inactive. A numbered row this parser
    cannot classify is REPORTED, never silently dropped — an unbuilt roster line
    is exactly the failure clients.md exists to prevent.
    """
    section = None
    out, skipped, unparsed = [], [], []
    for line in open(path, encoding="utf-8").read().splitlines():
        for rx, tag in _SECTION_PATTERNS:
            if rx.search(line):
                section = tag
                break
        c = _cells(line)
        if not c or not re.fullmatch(r"\d{3,5}", c[0]):
            continue
        cid, name = c[0], c[1]

        if section == "active" and len(c) >= 6:
            mmsm, ars, ics, mrpc = c[2].upper(), c[3], c[4], c[5]
            progs = []
            if ars.lower().startswith("yes"):
                progs.append("ARS")
            if "referrals-only" in ics.lower():
                progs.append("ICS-REFERRALS")
            elif ics.lower().startswith("yes"):
                progs.append("ICS")
            if mrpc.lower().startswith("yes"):
                progs.append("MRPC")
            if progs:
                out.append((cid, name, mmsm if mmsm in ("MM", "SM") else None, progs))
            else:
                skipped.append((cid, name, "no active program"))
        elif section == "mrpc_only":
            out.append((cid, name, None, ["MRPC"]))
        elif section == "ics_only":
            note = " ".join(c[2:]).lower()
            out.append((cid, name, None,
                        ["ICS-REFERRALS"] if ("referrals-only" in note or "none on file" in note)
                        else ["ICS"]))
        elif section == "cancelled":
            skipped.append((cid, name, "cancelled / ending"))
        elif section in (None, "prose", "cashplease"):
            continue
        else:
            unparsed.append((cid, name, f"unreadable row in the {section} table"))

    # A client can appear in the active table AND a status table. First wins, so
    # the active roster is authoritative and a later "cancelled" note about one
    # of its programs does not remove the client.
    seen, uniq = set(), []
    for row in out:
        if row[0] in seen:
            continue
        seen.add(row[0]); uniq.append(row)
    # A stopped client can appear in more than one table (1437 is in the active
    # roster with no programs AND under Cancelled). Report it once.
    skipped = [s for s in skipped if s[0] not in seen] + unparsed
    seen_skip, uniq_skip = set(), []
    for row in skipped:
        if row[0] in seen_skip:
            continue
        seen_skip.add(row[0]); uniq_skip.append(row)
    return uniq, uniq_skip


CASHPLEASE_HEADING = re.compile(r"^#{2,4}\s+CashPlease roster", re.I)


def read_cashplease_roster(path=ROSTER_FILE):
    """[{client_id, client_name, build, ships_as, note}] from the CashPlease table.

    Lives here, beside `read_roster`, because two parsers over one `clients.md` diverge
    — and this one already proved it. The CashPlease table was added between the
    ICS-only table and Status changes, and `read_roster` classifies a row by the section
    above it, so every CashPlease client was briefly read as an ICS client, 1658 Truliant
    included. Same file, same module, one place to look.

    Columns are found by HEADER NAME, not position: the table gained a `Ships as` column
    on 2026-09-01 and a fixed index silently read the wrong cell, blanking every skip
    reason — which is the one thing a skipped row exists to carry.
    """
    lines = open(path, encoding="utf-8").read().splitlines()
    start = next((i for i, ln in enumerate(lines)
                  if CASHPLEASE_HEADING.match(ln.strip())), None)
    if start is None:
        raise SystemExit(
            f"{path} has no '### CashPlease roster' section. The roster is read, never "
            f"inferred — the weekly workbook carries every Velocity CashPlease client "
            f"across all CSMs and is not a roster.")

    header, out = None, []
    for ln in lines[start + 1:]:
        s = ln.strip()
        if s.startswith("#"):
            break
        if not s.startswith("|"):
            continue
        cells = [c.replace("*", "").strip() for c in _cells(s)]
        if header is None:
            if "ID" in cells:
                header = [c.lower() for c in cells]
            continue
        if not re.fullmatch(r"\d{3,5}", cells[0]) or len(cells) != len(header):
            continue
        col = lambda n: cells[header.index(n)] if n in header else ""
        out.append({"client_id": cells[0],
                    "client_name": col("client"),
                    "build": col("build").lower().startswith("y"),
                    "ships_as": col("ships as"),
                    "note": col("note")})
    if not out:
        raise SystemExit(f"{path}: the CashPlease roster table is empty — nothing to "
                         f"build. Add rows rather than reporting success over 0 decks.")
    return out


def deck_name(cid, roster_name):
    """The name that goes on the deck and in its filename.

    clients.md decides, and nothing else (Aaron, 2026-08-29). The workbook is not
    it — 1204's says "First State Bank-MI" while the client is "First State Bank -
    Michigan" — and neither is the previous filename, which is how "FSB Michigan"
    persisted for a cycle. Renaming a client is a delivery decision, so it lives
    in the roster where such decisions are recorded.
    """
    return roster_name


def deck_tag(progs):
    return "-".join(p.replace("-REFERRALS", "") for p in progs)


# ----------------------------------------------------------------- build
def run(cmd, log, stdout_to=None):
    with open(log, "a", encoding="utf-8") as lf:
        lf.write("\n$ " + " ".join(str(c) for c in cmd) + "\n")
        if stdout_to:
            with open(stdout_to, "w", encoding="utf-8") as out:
                r = subprocess.run([str(c) for c in cmd], stdout=out, stderr=lf)
        else:
            r = subprocess.run([str(c) for c in cmd], stdout=lf, stderr=lf)
    return r.returncode


def ars_workbook(reports, cid, period):
    """The ARS workbook, never the Invitation Checking one.

    Several clients carry both, and "Invitation" sorts first — handing the ICS
    workbook to the ARS extractor dies on a missing Executive Financials tab.

    `reports` is one folder or several: inputs are sorted into a folder per kind
    (Aaron, 2026-09-09) and the legacy flat folder is still read, so a caller
    passes `rpe_env.report_dirs()`. A bare path still works.
    """
    dirs = [reports] if isinstance(reports, (str, os.PathLike)) else list(reports)
    hits = []
    for d in dirs:
        hits += [f for f in glob.glob(os.path.join(str(d), f"{cid}-{period}-*Workbook*.xlsx"))
                 if "invitation checking" not in os.path.basename(f).lower()]
    return sorted(hits)


def build_client(cid, name, mmsm, progs, period, stage):
    d = os.path.join(stage, cid); os.makedirs(d, exist_ok=True)
    log = os.path.join(d, "build.log"); open(log, "w", encoding="utf-8").close()
    made = {}
    I = R.inputs(); REPORTS = R.report_dirs(); ODDD = I / "ODDD"

    if "ARS" in progs:
        wb = ars_workbook(REPORTS, cid, period)
        if not wb:
            return "no ARS workbook", made
        z = str(ODDD / f"{cid}_ODDD.zip")
        if not os.path.exists(z):
            return "no ODDD extract", made
        base, lift = os.path.join(d, "base.json"), os.path.join(d, "lift.json")
        if mmsm == "MM":
            if run([PY, f"{ARSP}/extract_base_gen.py", wb[0], base], log): return "extract_base_gen", made
            if run([PY, f"{ARSP}/extract_lift.py", wb[0]], log, stdout_to=lift): return "extract_lift", made
        else:
            dco = sorted(glob.glob(os.path.join(str(REPORTS), f"{cid}-{period}-*DCO*.xlsx")))
            if run([PY, f"{ARSP}/base_tab_extract.py", wb[0]] + ([dco[0]] if dco else []),
                   log, stdout_to=base): return "base_tab_extract", made
            open(lift, "w", encoding="utf-8").write("{}")
        # The roster decides the client's name, so it overrides what the workbook
        # carries. build_ars_gen takes NAME from base.json["client"], which for
        # 1204 reads "First State Bank-MI" — renaming only the FILE would leave
        # the cover and every source note still saying the old name.
        try:
            _b = json.load(open(base, encoding="utf-8"))
            if _b.get("client") != name:
                print(f"    {cid}: workbook says {_b.get('client')!r}; "
                      f"clients.md says {name!r} — using the roster name")
                _b["client"] = name
                json.dump(_b, open(base, "w", encoding="utf-8"), indent=1)
        except (OSError, ValueError) as e:
            return f"base.json unreadable ({e})", made

        oddd = os.path.join(d, "oddd")
        if run([PY, os.path.join(REPO, "scripts/oddd_optimize.py"), "--input", z,
                "--out", oddd, "--client", cid, "--name", name], log): return "oddd_optimize", made
        met = os.path.join(d, "metrics.json")
        if run([PY, f"{ARSP}/metrics_gen.py", z, met], log): return "metrics_gen", made
        charts = os.path.join(d, "charts"); os.makedirs(charts, exist_ok=True)
        if run([PY, f"{ARSP}/charts_gen.py", met, base, charts], log): return "charts_gen", made
        out = os.path.join(d, f"{cid}-{period}-ARS-{name} ARS Results.pptx")
        if run([PY, f"{ARSP}/build_ars_gen.py", f"{TPL}/ars_template.pptx", met, base, lift,
                os.path.join(oddd, "oddd_metrics.json"), charts, out, z], log): return "build_ars_gen", made
        # NO restyle_fonts here. build_ars_gen already runs it (and then the branding,
        # geometry and layout-fit passes) before it saves, so a second pass from the
        # driver re-applied font roles AFTER fit_layout had clamped them. Measured on
        # a finished 49-slide deck it changed nothing at all — a subprocess and a full
        # load/save per ARS client for a no-op — and ICS and MRPC never had it, so ARS
        # was the odd one out (2026-09-11).
        made["ARS"] = out

    for p in progs:
        if p.startswith("ICS") or p == "MRPC":
            prog = "ics" if p.startswith("ICS") else "mrpc"
            U = prog.upper()
            try:
                sheet = str(R.resolve_client_json(cid, prog))
            except SystemExit as e:
                return f"no {U} sheet ({str(e).splitlines()[0]})", made
            out = os.path.join(d, f"{cid}-{period}-{U}-{name} {U} Results.pptx")
            cmd = [PY, os.path.join(REPO, f"build/{prog}_pipeline/build_{prog}_gen.py")]
            if p.endswith("REFERRALS"):
                cmd.append("--referrals-only")
            if run(cmd + [sheet, f"{TPL}/{prog}_template.pptx", out], log):
                return f"build_{prog}_gen", made
            made[U] = out

    if len(made) > 1:
        combo = os.path.join(d, f"{cid}-{period}-{deck_tag(progs)}-{name} Results.pptx")
        cmd = [PY, os.path.join(REPO, "build/assemble_combined.py"), "--ars", made["ARS"]]
        for U in ("ICS", "MRPC"):
            if U in made:
                cmd += [f"--{U.lower()}", made[U]]
        if run(cmd + ["--out", combo], log):
            return "assemble_combined", made
        made["DELIVERABLE"] = combo
    else:
        made["DELIVERABLE"] = next(iter(made.values()), None)
    return None, made


def validate(deck, base=None):
    cmd = [PY, os.path.join(REPO, "validation/validate_deck.py"), deck]
    if base and os.path.exists(base):
        cmd.append(base)
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return next((l.strip() for l in r.stdout.splitlines() if "FAIL," in l), "?")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("period"); ap.add_argument("out")
    ap.add_argument("--only", help="comma-separated client ids")
    a = ap.parse_args()
    if not re.fullmatch(r"20\d\d\.\d\d", a.period):
        raise SystemExit(f"period must be YYYY.MM, got {a.period!r}")
    os.makedirs(a.out, exist_ok=True)

    roster, skipped = read_roster()
    if a.only:
        want = {x.strip() for x in a.only.split(",")}
        roster = [r for r in roster if r[0] in want]
    print(f"clients.md: {len(roster)} to build, {len(skipped)} with no active program")
    for cid, name, why in skipped:
        print(f"    skip {cid} {name} — {why}")
    print()

    results = []
    for i, (cid, roster_name, mmsm, progs) in enumerate(roster, 1):
        t = time.time()
        name = deck_name(cid, roster_name)
        err, made = build_client(cid, name, mmsm, progs, a.period, a.out)
        deck = made.get("DELIVERABLE")
        gate = validate(deck, os.path.join(a.out, cid, "base.json")) if (not err and deck) else "-"
        status = err or gate
        print(f"[{i:>2}/{len(roster)}] {cid} {name[:26]:<26} {deck_tag(progs):<12} "
              f"{status:<26} {time.time()-t:>5.0f}s", flush=True)
        results.append((cid, name, progs, err, gate, deck))

    json.dump([(c, n, p, e, g, d) for c, n, p, e, g, d in results],
              open(os.path.join(a.out, "_results.json"), "w", encoding="utf-8"), indent=1)
    failed = [r for r in results if r[3] or not r[4].startswith("0 FAIL")]
    print("\n" + "=" * 72)
    print(f"{len(results)-len(failed)}/{len(results)} clients resolved without error")
    for cid, name, progs, err, gate, deck in failed:
        print(f"  {cid} {name}: {err or gate}")
    return len(failed)


if __name__ == "__main__":
    sys.exit(main())
