#!/usr/bin/env python3
"""
refresh_performance_dashboard.py — rebuild the cross-client RPE performance page.

The "RPE Client Performance" artifact (one section per program — ARS, ICS, MRPC,
CashPlease — with a ranked bar, a metrics table and trend sparklines, plus a deck
roster) is a static page with its dataset embedded. This script rebuilds that
dataset from the inputs the deck builders read, injects it into the page template,
and says whether anything changed since the version last published. It does NOT
publish: the artifact is republished by the Claude scheduled task
"rpe-dashboard-refresh", which runs this, and publishes only on `STATUS: changed`.

    dataset  <-  ARS workbooks + DCOs (Inputs, sorted by kind) via the ARS
                 extractors; mailing response from the shipped deck's figure sidecar
                 (Build Artifacts/*.figures.json) — the workbook's mailing rates are
                 NOT the response rate the deck prints;
                 VIP ICS / MRPC sheets (Inputs/VIP Data, via the manifest);
                 the newest MRPCEnrollmentSummary weekly;
                 the newest CashPleaseSummary weekly, through the CashPlease repo's
                 own extractor (cp_extract.py) so its figures match its decks.

Everything it writes is bookkeeping and goes to `Build Artifacts/perf_dashboard/`:

    dataset.json        the aggregated dataset (full)
    rpe_dashboard.html  the page, ready to publish
    state.json          content hash of the dataset, and the hash last published
    cp/                 the CashPlease per-client packs cp_extract emitted

**The period is derived, never assumed.** It is the newest `<yyyy.mm>` tagged on an
ARS workbook in `Inputs/ARS Workbooks/` — the dashboard rolls forward the
moment a new month's workbooks are copied to Drive, and not before. Override with
`--period` for a rebuild of an older month.

**Changed means the figures moved.** The hash excludes the generation date, so a
rebuild that finds identical inputs reports `unchanged` and the artifact is not
republished over nothing.

Usage:
    python scripts/refresh_performance_dashboard.py [--period 2026.08] [--force]
    python scripts/refresh_performance_dashboard.py --mark-published
        (after a successful publish: records the current hash as the live one)
"""
import argparse
import datetime as _dt
import glob
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "build"))
sys.path.insert(0, str(REPO / "scripts"))

import rpe_env as R                                              # noqa: E402
from build_month import read_roster                              # noqa: E402

TEMPLATE = REPO / "scripts" / "perf_dashboard_template.html"
PLACEHOLDER = "__DATA__"
OUT_DIRNAME = "perf_dashboard"
PY = sys.executable

_WB_PERIOD_RX = re.compile(r"^\d{3,5}-(\d{4}\.\d{2})-", re.I)


# ------------------------------------------------------------------ helpers
def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def out_dir():
    d = R.build_artifacts() / OUT_DIRNAME
    d.mkdir(parents=True, exist_ok=True)
    return d


def cashplease_home():
    """The CashPlease repo, whose extractor produces the CashPlease figures.

    Resolved, not hardcoded: CASHPLEASE_HOME in the environment or `.env`, else a
    sibling checkout named CashPlease. Absent, the CashPlease section is reported as
    missing rather than the whole refresh failing.
    """
    raw = os.environ.get("CASHPLEASE_HOME") or R._load_dotenv().get("CASHPLEASE_HOME")
    cands = [Path(raw)] if raw else []
    cands.append(REPO.parent / "CashPlease")
    for c in cands:
        if (c / "build" / "cp_extract.py").exists():
            return c
    return None


# ------------------------------------------------------------------ period
def report_glob(reports, pattern):
    """Every match for `pattern` across the report folders.

    `reports` is a LIST since inputs are sorted into a folder per kind
    (Aaron, 2026-09-09); a single folder is still accepted.
    """
    dirs = [reports] if isinstance(reports, (str, os.PathLike)) else list(reports)
    return sorted((f for d in dirs for f in glob.glob(os.path.join(str(d), pattern))),
                  key=os.path.basename)


def derive_period(reports_dir, names=None):
    """Newest `<yyyy.mm>` on an ARS workbook in the reports folders, or None."""
    if names is None:
        names = [os.path.basename(f) for f in report_glob(reports_dir, "*.xlsx")]
    periods = []
    for n in names:
        if n.startswith("~$") or "workbook" not in n.lower() \
                or "invitation checking" in n.lower():
            continue
        m = _WB_PERIOD_RX.match(n)
        if m:
            periods.append(m.group(1))
    return max(periods) if periods else None


def _newest_for(names, rx, period):
    """(period, name) of the newest file matching `rx` with a period at or
    before `period`, or (None, None). Ties go to the last name in sort order."""
    best = (None, None)
    for n in sorted(names):
        if n.startswith("~$"):
            continue
        m = rx.match(n)
        if m and m.group(1) <= period and (best[0] is None or m.group(1) >= best[0]):
            best = (m.group(1), n)
    return best


def pick_workbook(names, cid, period):
    """The client's newest ARS workbook at or before the cycle period.

    Per client, not per cycle: the data team lands the month's workbooks over a
    week or more, so on any given morning some clients have this month's and
    some still only last month's. A page that showed "no workbook" for the
    latter while the older one sat on Drive would be less informative than the
    one it replaced. The period used is carried on the row so it is not mistaken
    for the cycle's.
    """
    rx = re.compile(r"^%s-(\d{4}\.\d{2})-(?!.*invitation checking).*workbook.*\.xlsx$"
                    % re.escape(cid), re.I)
    return _newest_for(names, rx, period)


def pick_sidecar(names, cid, period):
    """The newest shipped ARS deck's figure sidecar for the client."""
    rx = re.compile(r"^%s-(\d{4}\.\d{2})-ARS-.*ARS Results\.pptx\.figures\.json$"
                    % re.escape(cid), re.I)
    return _newest_for(names, rx, period)


def newest_deck_period(names, cid, period):
    """The most recent period with a built deck for the client, or None."""
    rx = re.compile(r"^%s-(\d{4}\.\d{2})-.*\.pptx$" % re.escape(cid), re.I)
    return _newest_for(names, rx, period)[0]


# ------------------------------------------------------------------ roster
def roster_clients():
    """{id: client record} for every roster client, CashPlease included."""
    roster, _skipped = read_roster(str(REPO / "clients.md"))
    clients = {}
    for cid, name, mmsm, progs in roster:
        clients[cid] = {"id": cid, "name": name, "path": mmsm, "programs": [],
                        "roster_programs": list(progs)}
    for cid, nm in cashplease_roster().items():
        c = clients.setdefault(cid, {"id": cid, "name": nm, "path": None,
                                     "programs": [], "roster_programs": []})
        if "CP" not in c["roster_programs"]:
            c["roster_programs"].append("CP")
    return clients


def cashplease_roster(text=None):
    """{id: name} for `Build = yes` rows of the CashPlease roster in clients.md."""
    if text is None:
        text = (REPO / "clients.md").read_text(encoding="utf-8")
    if "### CashPlease roster" not in text:
        return {}
    sec = text.split("### CashPlease roster", 1)[1]
    out = {}
    for line in sec.splitlines():
        if line.startswith("## ") or line.startswith("### "):
            break
        c = [x.strip() for x in line.strip().strip("|").split("|")]
        if len(c) >= 3 and re.fullmatch(r"\d{3,5}", c[0]) and c[2].lower().startswith("yes"):
            out[c[0]] = c[1]
    return out


# ------------------------------------------------------------------ ARS
sys.path.insert(0, str(REPO / "build" / "ars_pipeline"))
from base_guard import uncalculated                              # noqa: E402  (one definition, shared with the ARS builder)


def ars_section(cid, c, period, reports, ba, work):
    found = {os.path.basename(f): f for f in report_glob(reports, "*.xlsx")}
    wb_period, wb_name = pick_workbook(sorted(found), cid, period)
    if not wb_name:
        return {"missing": "no ARS workbook in Inputs"}
    wb = found[wb_name]
    if c["path"] == "MM":
        out = work / f"{cid}_base.json"
        r = subprocess.run([PY, str(REPO / "build/ars_pipeline/extract_base_gen.py"), wb, str(out)],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        if "UNEVALUATED WORKBOOK" in r.stderr:
            return {"missing": r.stderr.strip().splitlines()[-1],
                    "workbook": wb_name, "workbook_period": wb_period}
        if r.returncode != 0 or not out.exists():
            return {"missing": "extract_base_gen failed: " + r.stderr.strip()[-300:]}
        b = json.load(open(out, encoding="utf-8"))
    else:
        dco = report_glob(reports, f"{cid}-{wb_period}-*DCO*.xlsx")
        r = subprocess.run([PY, str(REPO / "build/ars_pipeline/base_tab_extract.py"), wb] + dco[:1],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        if "UNEVALUATED WORKBOOK" in r.stderr:
            return {"missing": r.stderr.strip().splitlines()[-1],
                    "workbook": wb_name, "workbook_period": wb_period}
        i = r.stdout.find("{")
        if r.returncode != 0 or i < 0:
            return {"missing": "base_tab_extract failed: " + r.stderr.strip()[-300:]}
        b = json.loads(r.stdout[i:])
    if uncalculated(b):
        # The data team's workbook can arrive with its formulas never evaluated,
        # so the cached values openpyxl reads are the template's defaults. Zeros
        # on the page would look like a client with no revenue; say what it is.
        return {"missing": "workbook %s carries no calculated values — open it in "
                           "Excel and save, then rebuild" % os.path.basename(wb),
                "workbook": os.path.basename(wb), "workbook_period": wb_period}
    a = {
        "workbook": os.path.basename(wb), "workbook_period": wb_period,
        "path": c["path"], "data_label": b.get("data_label"),
        "months_live": b.get("months"), "mailings": b.get("mailings"),
        "cur_revenue": num(b.get("cur_revenue")), "ltd_revenue": num(b.get("ltd_revenue")),
        "cur_profit": num(b.get("cur_profit")), "ltd_profit": num(b.get("ltd_profit")),
        "ltd_costs": num(b.get("ltd_costs")), "profitability": num(b.get("profitability")),
        "rev12_sum": b.get("monthly_rev_sum12"), "rev12_avg": b.get("monthly_rev_avg12"),
        "monthly_rev": [[m, round(v or 0)] for m, v in b.get("monthly_rev_last12", [])],
        "spend_cards": [[m, s, k] for m, s, k in b.get("swipespend_36", [])][-1:],
        "dco_eligible": b.get("dco_eligible"),
    }
    # The shipped deck's figures are the audited numbers; the response rate comes
    # from there, not from the workbook's mailing tab.
    sc_period, sc_name = pick_sidecar(os.listdir(ba), cid, period)
    if sc_name:
        got = {}
        for f in json.load(open(ba / sc_name, encoding="utf-8")).get("figures", []):
            got.setdefault(f["measure"], f)

        def fv(k):
            v = got.get(k, {}).get("value")
            return None if v is None else num(str(v).replace(",", "").replace("%", ""))

        lm = {"slide": got.get("mailed_latest_mailing", {}).get("slide", ""),
              "mailed": fv("mailed_latest_mailing"), "responders": fv("responders_latest_mailing"),
              "response_rate": fv("resprate_latest_mailing"), "reach_total": fv("reach_total")}
        m = re.search(r"—\s*(\w+ \d{4})", lm["slide"]) or re.search(r"-\s*(\w+ \d{4})", lm["slide"])
        lm["month"] = m.group(1) if m else None
        lm["deck_period"] = sc_period
        a["latest_mailing"] = lm
    return a


# ------------------------------------------------------------------ ICS
def _wb_period(fn):
    m = re.search(r"-(20\d\d\.\d\d)-", fn or "")
    return m.group(1) if m else None


def ics_section(cid, c):
    try:
        p = R.resolve_client_json(cid, "ics")
    except BaseException as e:
        return {"missing": str(e).splitlines()[0] if str(e) else "no VIP ICS sheet"}
    d = json.load(open(p, encoding="utf-8"))
    meta, ref = d.get("meta", {}), d.get("referrals", {})
    perf, fs = d.get("performance") or {}, d.get("financial_summary") or {}
    has_wb = bool(perf.get("roi")) and "ICS-REFERRALS" not in c["roster_programs"]
    ics = {
        "period": meta.get("period"), "data_pull": meta.get("data_pull"),
        "program_start": meta.get("program_start"),
        "workbook": meta.get("workbook"), "workbook_period": _wb_period(meta.get("workbook")),
        "referrals_only": not has_wb,
        "ptd": ref.get("program_to_date"), "ytd": ref.get("year_to_date"),
        "prev_month": ref.get("previous_month"), "mtd": ref.get("month_to_date"),
        "monthly_goal": ref.get("monthly_goal"), "prev_vs_goal_pct": ref.get("prev_month_vs_goal_pct"),
        "trend": ref.get("trend"),
    }
    if has_wb:
        rev = d.get("revenue") or {}
        ics.update({
            "roi": perf.get("roi"), "ltv": perf.get("lifetime_value_per_account"),
            "annual_profit_per_account": perf.get("annual_profit_per_account"),
            "cost_per_account": perf.get("cost_per_account"),
            "payback_months": perf.get("payback_months"),
            "avg_life_years": perf.get("average_account_life_years"),
            "net_profit": fs.get("net_profit"), "ics_accounts": fs.get("ics_accounts"),
            "profit_contribution": fs.get("account_profit_contribution"),
            "program_expense": fs.get("total_program_expense"),
            "avg_balance": fs.get("average_balance"), "revenue_total": rev.get("total"),
        })
    return ics


# ------------------------------------------------------------------ MRPC
class MrpcWeekly:
    """The newest MRPCEnrollmentSummary weekly, one tab per client."""

    def __init__(self, reports):
        import openpyxl
        hits = report_glob(reports, "*MRPCEnrollmentSummary*.xlsx")
        self.path = hits[-1] if hits else None
        self.tabs = {}
        if self.path:
            self.wb = openpyxl.load_workbook(self.path, read_only=True, data_only=True)
            self.tabs = {s[:4]: s for s in self.wb.sheetnames
                         if s[:4].isdigit() and not s.endswith(("-Loans", "-Issues"))}

    @property
    def name(self):
        return os.path.basename(self.path) if self.path else None

    def client(self, cid):
        if cid not in self.tabs:
            return None
        ws = self.wb[self.tabs[cid]]
        rows = list(ws.iter_rows(min_row=1, max_row=ws.max_row, values_only=True))
        gen = str(rows[5][1] or "").replace("Report Generated:", "").strip()
        kv, take = {}, {}
        for r in rows[7:60]:
            if isinstance(r[15], str) and r[21] is not None:
                kv[r[15].strip()] = r[21]
            if r[15] == "New Account Take Rates":
                take["ptd_label"], take["cur_label"] = r[18], r[21]
            if r[15] == "New Accounts Opened":
                take["ptd_opened"], take["cur_opened"] = r[18], r[20]
            if r[15] == "New Accounts Enrolled":
                take["ptd_enrolled"], take["ptd_rate"] = r[18], r[19]
                take["cur_enrolled"], take["cur_rate"] = r[20], r[21]
        hdr_i = next(i for i, r in enumerate(rows) if r[1] == "Enroll Date")
        tot = next(r for r in rows if r[1] == "TOTAL ")
        ah = next((r for r in rows if r[1] == "TOTAL ACCOUNTHOLDERS"), None)
        monthly = []
        for r in rows[hdr_i + 1:]:
            lab = r[1]
            if not isinstance(lab, str) or not lab.endswith("*") or "roll-up" in lab.lower():
                continue
            mm, dd, yy = lab.rstrip("*").split("/")
            monthly.append({
                "platinum": r[2] or 0, "gold": r[3] or 0, "business": r[4] or 0,
                "primary": r[6] or 0, "joint": r[7] or 0, "web_branch": r[9] or 0,
                "web_enduser": r[10] or 0, "phone": r[11] or 0, "paper": r[12] or 0,
                "existing": r[14] or 0, "new": r[15] or 0, "employees": r[17] or 0,
                "non_employees": r[18] or 0, "month": f"{yy}-{mm}"})
        monthly.sort(key=lambda r: r["month"])
        return {
            "file": self.name, "report_generated": gen,
            "open_with_debit": kv.get("Open/Active Accounts w/ Debit Card"),
            "open_without_debit": kv.get("Open/Active Accounts w/o Debit Card (Not Factored in Rates Below)"),
            "all_mrpc_accounts": kv.get("All MRPC Accounts"),
            "take_rate_all": kv.get("Take Rate - All MRPC Accounts"),
            "active_mrpc_accounts": kv.get("Active/Signed MRPC Accounts"),
            "take_rate_active": kv.get("Take Rate - Active MRPC Accounts"),
            "all_cardholders": kv.get("All MRPC Primary and Joint Card Holders"),
            "active_cardholders": kv.get("Active MRPC Primary and Joint Card Holders"),
            "take_rate_active_cardholders": kv.get("Take Rate - Active MRPC Primary and Joint Card Holders"),
            "new_account_take": take,
            "totals": {"platinum": tot[2], "gold": tot[3], "business": tot[4], "primary": tot[6],
                       "joint": tot[7], "web_branch": tot[9], "web_enduser": tot[10],
                       "phone": tot[11], "paper": tot[12], "existing": tot[14], "new": tot[15],
                       "employees": tot[17], "non_employees": tot[18]},
            "cardholders_active_buckets": ({"1-90": ah[10], "91-180": ah[11], "180+": ah[12],
                                            "inactive": ah[13]} if ah else None),
            "monthly": monthly[-24:],
        }


def mrpc_section(cid, weekly):
    m = {"weekly": weekly.client(cid)}
    try:
        p = R.resolve_client_json(cid, "mrpc")
        d = json.load(open(p, encoding="utf-8"))
        meta = d.get("meta", {})
        pv, rev = d.get("performance_vs_goal") or {}, d.get("revenue") or {}
        m.update({
            "period": meta.get("period"), "data_pull": meta.get("data_pull"),
            "key_metrics": d.get("key_metrics") or {},
            "goal_pct": pv.get("goal_pct"), "pct_of_goal": pv.get("pct_of_goal"),
            "goal_months": pv.get("months"), "goal_enrollments": pv.get("enrollments"),
            "goal_new_accounts": pv.get("new_accounts"),
            "revenue_ltd": rev.get("life_of_program"), "revenue_2025": rev.get("year_2025"),
        })
    except BaseException as ex:
        m["missing_vip"] = str(ex).splitlines()[0] if str(ex) else "no VIP MRPC sheet"
    return m


# ------------------------------------------------------------------ CashPlease
def cashplease_packs(reports, work):
    """Run the CashPlease repo's extractor on the newest weekly. Returns
    (packs_dir, weekly_name, peer, note) — packs_dir None when it could not run."""
    home = cashplease_home()
    if home is None:
        return None, None, None, "CashPlease repo not found (set CASHPLEASE_HOME)"
    sys.path.insert(0, str(home / "build"))
    cands = report_glob(reports, "CashPleaseSummary*.xlsx")
    dda = None
    try:
        import cp_env
        cands += glob.glob(str(cp_env.inputs() / "CashPleaseSummary*.xlsx"))
        d = cp_env.build_artifacts() / "dda_counts.json"
        dda = str(d) if d.exists() else None
    except BaseException:
        pass
    cands = [c for c in cands if not os.path.basename(c).startswith("~$")]
    if not cands:
        return None, None, None, "no CashPleaseSummary*.xlsx found"
    # The stamp in the name orders them; the newest weekly wins wherever it landed.
    wb = max(cands, key=os.path.basename)
    packs = work / "cp"
    cmd = [PY, str(home / "build" / "cp_extract.py"), wb, str(packs)] + ([dda] if dda else [])
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0 or not (packs / "peer_benchmark.json").exists():
        return None, os.path.basename(wb), None, "cp_extract failed: " + r.stderr.strip()[-300:]
    peer = json.load(open(packs / "peer_benchmark.json", encoding="utf-8"))
    return packs, os.path.basename(wb), peer, None


def cp_section(cid, packs):
    f = packs / f"{cid}_cashplease.json"
    if not f.exists():
        return {"missing": "no tab in the CashPlease workbook"}
    d = json.load(open(f, encoding="utf-8"))
    mt = d["metrics"]
    mon = sorted(d["monthly"], key=lambda r: r["period_month"])[-24:]
    return {
        "file": d["source_file"], "report_generated": d["report_generated"],
        "cp_name": d["client_name"],
        "total_loans": mt["total_loans"], "total_principal": mt["total_principal"],
        "total_interest": mt["total_interest"], "active_loans": mt["active_loans"],
        "active_principal": mt["active_principal"], "avg_loan_size": mt["avg_loan_size"],
        "avg_interest_per_loan": mt["avg_interest_per_loan"],
        "charge_off_pct": mt["charge_off_pct"], "pct_overdue": mt["pct_loans_overdue"],
        "pct_charged_off": mt["pct_loans_charged_off"], "pct_paid_off": mt["pct_loans_paid_off"],
        "pct_active_accounts_with_loans": d["pct_active_accounts_with_loans"],
        "window_loans": mt["window_loans"], "window_months": mt["window_months"],
        "status": {k: v["loans"] for k, v in d["status"].items()},
        "monthly": [{"month": r["period_month"], "loans": r["loans"],
                     "principal": r["principal"], "interest": r["interest"]} for r in mon],
        "mtd": {"days": len(d["daily"]), "loans": sum(r["loans"] for r in d["daily"])},
    }


# ------------------------------------------------------------------ decks / sent
def decks_and_sent(cid, period, outputs, ba):
    """The client's most recently built deck(s) at or before the cycle period,
    that period, and whether they were sent. Newest per client, for the same
    reason as the workbook: early in a cycle nobody has this month's deck yet,
    and "not built" for every client says nothing the date does not."""
    names = [os.path.basename(f) for f in glob.glob(str(outputs / f"{cid}-*.pptx"))]
    try:
        import cp_env
        names += [os.path.basename(f) for f in glob.glob(str(cp_env.outputs() / f"{cid}-*.pptx"))]
    except BaseException:
        pass
    dp = newest_deck_period(names, cid, period)
    decks = sorted({n for n in names if n.startswith(f"{cid}-{dp}-")}) if dp else []
    sent = None
    dpath = ba / "deliveries.json"
    if dp and dpath.exists():
        try:
            s = json.load(open(dpath, encoding="utf-8")).get("sent", {}).get(f"{cid}|{dp}")
            sent = s["sent_at"] if s else None
        except (OSError, ValueError, KeyError, TypeError):
            sent = None
    return decks, sent, dp


def vip_pull_date(program):
    """Newest data_pull in the VIP manifest for one program, or None."""
    try:
        man = R.vip_manifest() or []
    except BaseException:
        return None
    pulls = [e.get("data_pull") for e in man
             if str(e.get("program", "")).upper() == program and e.get("data_pull")]
    return max(pulls) if pulls else None


# ------------------------------------------------------------------ assemble
def build_dataset(period, work, log=print):
    I, O, BA = R.inputs(), R.outputs(), R.build_artifacts()
    reports = R.report_dirs()
    clients = roster_clients()
    weekly = MrpcWeekly(reports)
    packs, cp_weekly, peer, cp_note = cashplease_packs(reports, work)
    if cp_note:
        log("CashPlease: " + cp_note)

    for cid, c in clients.items():
        rp = c["roster_programs"]
        if "ARS" in rp:
            c["ars"] = ars_section(cid, c, period, reports, BA, work)
            c["programs"].append("ARS")
        if any(p.startswith("ICS") for p in rp):
            c["ics"] = ics_section(cid, c)
            c["programs"].append("ICS")
        if "MRPC" in rp:
            c["mrpc"] = mrpc_section(cid, weekly)
            c["programs"].append("MRPC")
        if "CP" in rp:
            c["cp"] = cp_section(cid, packs) if packs else {"missing": cp_note}
            c["programs"].append("CP")
        c["decks"], c["sent"], c["deck_period"] = decks_and_sent(cid, period, O, BA)

    ics_pull, mrpc_pull = vip_pull_date("ICS"), vip_pull_date("MRPC")
    return {
        "generated": _dt.date.today().isoformat(), "period": period,
        "sources": {
            "ars": f"each client's newest ARS workbook through {period} (Inputs/ARS Workbooks) + the mailing response from their newest shipped deck's figure sidecar (Build Artifacts)",
            "ics": "VIP ICS sheets" + (f", pulled {ics_pull}" if ics_pull else "") + " (Inputs/VIP Data/ICS)",
            "mrpc": "VIP MRPC sheets" + (f", pulled {mrpc_pull}" if mrpc_pull else "")
                    + (f" + {weekly.name}" if weekly.name else ""),
            "cp": (cp_weekly or "CashPlease weekly") + " (Inputs/Weekly Summaries)",
        },
        "cp_peer": peer,
        "clients": sorted([c for c in clients.values() if c["programs"]], key=lambda c: c["id"]),
    }


# ------------------------------------------------------------------ render
def render(dataset, template_text=None):
    """The page: the template with the dataset injected. `</` is escaped so no
    value can close the script tag."""
    if template_text is None:
        template_text = TEMPLATE.read_text(encoding="utf-8")
    if PLACEHOLDER not in template_text:
        raise SystemExit(f"{TEMPLATE} has no {PLACEHOLDER} placeholder")
    js = json.dumps(dataset, separators=(",", ":"), default=str).replace("</", r"<\/")
    return template_text.replace(PLACEHOLDER, js, 1)


def content_hash(dataset):
    """Hash of the figures, not the run: `generated` is excluded so rebuilding the
    same inputs on another day reads as unchanged."""
    d = dict(dataset)
    d.pop("generated", None)
    return hashlib.sha256(json.dumps(d, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def read_state(p):
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def write_state(p, doc):
    p.write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8")


def summarize(dataset):
    lines = []
    for c in dataset["clients"]:
        miss = [k for k in ("ars", "ics", "mrpc", "cp")
                if isinstance(c.get(k), dict) and c[k].get("missing")]
        wb = (c.get("ars") or {}).get("workbook_period") or "-"
        lines.append("  %s %-30s %-16s wb %s  deck %s  sent %s%s" % (
            c["id"], c["name"][:30], "+".join(c["programs"]), wb,
            c.get("deck_period") or "-", c["sent"] or "-",
            ("  MISSING " + ",".join(miss)) if miss else ""))
    return "\n".join(lines)


# ------------------------------------------------------------------ main
def main(argv=None):
    ap = argparse.ArgumentParser(description="Rebuild the RPE performance dashboard page.")
    ap.add_argument("--period", default=None, help="YYYY.MM (default: newest ARS workbook on Drive)")
    ap.add_argument("--force", action="store_true", help="report changed even if the hash matches")
    ap.add_argument("--mark-published", action="store_true",
                    help="record the current dataset hash as the published one, then exit")
    a = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")

    work = out_dir()
    state_p = work / "state.json"
    state = read_state(state_p)

    if a.mark_published:
        if not state.get("hash"):
            raise SystemExit("nothing to mark: no dataset has been built yet")
        state["published_hash"] = state["hash"]
        state["published_at"] = _dt.datetime.now().strftime("%Y-%m-%d %H:%M")
        write_state(state_p, state)
        print("marked published: " + state["hash"][:12])
        return 0

    reports = R.report_dirs()
    period = a.period or derive_period(reports)
    if not period:
        raise SystemExit("no ARS workbook in %s to derive a period from; pass --period"
                         % ", ".join(str(d) for d in reports))
    if not re.fullmatch(r"\d{4}\.\d{2}", period):
        raise SystemExit("period must be YYYY.MM, got %r" % period)

    dataset = build_dataset(period, work)
    html = render(dataset)
    (work / "dataset.json").write_text(json.dumps(dataset, indent=1, default=str), encoding="utf-8")
    (work / "rpe_dashboard.html").write_text(html, encoding="utf-8")

    h = content_hash(dataset)
    changed = a.force or h != state.get("published_hash")
    state.update({"hash": h, "period": period, "built_at": _dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
                  "html": str(work / "rpe_dashboard.html")})
    write_state(state_p, state)

    print("period %s  clients %d  hash %s  published %s" % (
        period, len(dataset["clients"]), h[:12], (state.get("published_hash") or "-")[:12]))
    print(summarize(dataset))
    print("html " + str(work / "rpe_dashboard.html"))
    print("STATUS: " + ("changed" if changed else "unchanged"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
