"""Per-client data gaps across every current client -> gaps.json, the data both issue pages are built from.

    python scripts/issue_pages/gaps_matrix.py [out.json]      (default: Build Artifacts/issue_pages/gaps.json)

Reads the performance dashboard's dataset.json (run refresh_performance_dashboard.py first), the Client CSM
List, clients.md, the VIP manifest, the CashPlease packs and the period's all-client ARS trial run.
"""
import csv, json, re, sys
from collections import Counter
from pathlib import Path

from common import R, trial_dir, work_dir  # noqa: E402
import build_month as BM     # noqa: E402
import base_guard as BG      # noqa: E402

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else work_dir() / "gaps.json"
root, I, BA = R.data_root(), R.inputs(), R.build_artifacts()
ds = json.load(open(BA / "perf_dashboard" / "dataset.json", encoding="utf-8"))
period = ds["period"]
csv_rows = {r["client_id"]: r for r in csv.DictReader(open(root / R.CSM_LIST_NAME, encoding="utf-8-sig"))}
former = [r for r in csv_rows.values() if r["notes"].startswith("ODD only in older months")]

roster, stopped = BM.read_roster()
roster_ids = {cid for cid, *_ in roster}
cp_roster = {r["client_id"]: r for r in BM.read_cashplease_roster()}
vip = json.load(open(I / "VIP Data" / "manifest.json", encoding="utf-8"))["clients"]
vip_has = {(v["program"], v["client_id"]): v for v in vip}
cp_idx = json.load(open(BA / "cashplease" / "packs" / "index.json", encoding="utf-8"))
cp_tabs = {c["client_id"]: c for c in cp_idx["clients"]}
no_dda = set()
for f in cp_idx.get("flags", []):
    if "no DDA count" in f:
        no_dda |= set(re.findall(r"\b(1\d{3})\b", f.split(":", 1)[1]))
trial_p = trial_dir(period) / "_trial_results.json"
trial = json.load(open(trial_p, encoding="utf-8")) if trial_p.exists() else {}


def kind_files(kind, cid):
    d = I / R.INPUT_KIND_DIRS[kind]
    return sorted(p.name for p in d.glob(f"{cid}-*")) if d.exists() else []


def per(name):
    m = re.match(r"^\d+-(\d{4}\.\d{2})-", name)
    return m.group(1) if m else None


def pack_flags(cid):
    p = trial_dir(period) / cid / "oddd" / "oddd_metrics.json"
    if not p.exists():
        return {}
    f = json.load(open(p, encoding="utf-8")).get("flags", {})
    return {k: v for k, v in f.items() if v and (not isinstance(v, dict) or v.get("total", 1))}


def trial_class(t):
    if not t:
        return None, None
    err = t.get("error")
    if not err:
        gate = str(t.get("gate") or "")
        return ("clean" if gate.startswith("0 FAIL") else "gate"), gate
    tail = t.get("log_tail") or ""
    for key in ("UNEVALUATED WORKBOOK", "POSSIBLE DATA ISSUE"):
        if key in tail:
            line = next(l for l in tail.splitlines() if key in l).strip()
            return key.lower().replace(" ", "_"), line
    last = [l.strip() for l in tail.splitlines() if l.strip() and not l.strip().startswith("$")]
    return "crash", f"{err}: {last[-1] if last else ''}"[:300]


clients, issues = [], []
# The 2026.09 trial logs predate that day's data-issue guards, so these three state what the extract
# actually carries, in VIP Data Specification terms (2026-09-15).
DATA_ISSUES = {
    "1226": "The Account Status description is blank on all 11,495 personal accounts; the Account Status Code holds words (ACTIVE / DORMANT / INACTIVE), not the specification's codes, so no account reads as open and there is no Reg E base",
    "1615": "18,912 accounts have a blank Account Status description and Account Status Code '0', which is not a specification code, so almost no account reads as open and there is no active-card base to compare spend against",
    "1121": "All 2,699 personal accounts opened since Sep 2025 carry a code ('1', '39', '18') or a blank as their Product Code Description instead of a descriptive name, so there are no new checking accounts to compare",
}


def issue(c, program, severity, what, fix):
    issues.append({"id": c["id"], "name": c["name"], "csm": c["csm"] or "Unassigned",
                   "program": program, "severity": severity, "issue": what, "fix": fix})


for c in ds["clients"]:
    cid = c["id"]
    row = csv_rows.get(cid, {})
    progs = set(c.get("programs") or []) | set(c.get("roster_programs") or [])
    odd_zip = (I / "ODDD" / f"{cid}_ODDD.zip").exists()
    dcos, wbs = kind_files("DCO", cid), [w for w in kind_files("Workbook", cid)]
    mrpcs, icsw = kind_files("MRPCPM", cid), kind_files("ICS workbook", cid)
    settings = R.cp_settings_file(cid)
    base_p = BA / "perf_dashboard" / f"{cid}_base.json"
    uncalc = False
    if base_p.exists():
        try:
            uncalc = BG.uncalculated(json.load(open(base_p, encoding="utf-8")))
        except Exception:
            pass
    tcls, tdetail = trial_class(trial.get(cid))
    rec = {
        "id": cid, "name": c["name"], "csm": c["csm"] or "Unassigned", "path": c.get("path"),
        "programs": sorted(progs), "on_roster": cid in roster_ids or bool(cp_roster.get(cid, {}).get("build")),
        "odd_month": row.get("newest_odd_month") or None, "odd_current": row.get("odd_current") == "yes",
        "odd_in_inputs": odd_zip,
        "dco": per(dcos[-1]) if dcos else None, "workbook": per(wbs[-1]) if wbs else None,
        "workbook_file": wbs[-1] if wbs else None,
        "mrpc_analysis": per(mrpcs[-1]) if mrpcs else None, "ics_workbook": per(icsw[-1]) if icsw else None,
        "vip_ics": ("ICS", cid) in vip_has, "vip_mrpc": ("MRPC", cid) in vip_has,
        "cp_tab": cid in cp_tabs and not cp_tabs[cid].get("cancelled"), "cp_settings": bool(settings),
        "cp_no_dda": cid in no_dda, "uncalculated": uncalc,
        "trial": tcls, "trial_detail": tdetail, "pack_flags": pack_flags(cid),
        "overview_missing": (c.get("overview") or {}).get("missing"),
    }
    clients.append(rec)

    if cid in DATA_ISSUES:
        tcls, tdetail = "possible_data_issue", DATA_ISSUES[cid]
    rec["trial"], rec["trial_detail"] = tcls, tdetail

    ars = "ARS" in progs or bool(wbs)
    if wbs and per(wbs[-1]) != period:
        issue(rec, "ARS", "blocker", f"Newest ARS workbook is {per(wbs[-1])}; no {period} workbook",
              "Data team: land this month's workbook on the client-reports share")
    if not (progs or wbs or mrpcs or icsw or rec["cp_tab"] or rec["vip_ics"] or rec["vip_mrpc"]):
        issue(rec, "All", "gap", "Pending first workbook (new client): current ODD extract on hand, no program inputs yet (no workbook, MRPCPM analysis, CashPlease tab or VIP sheet)",
              "No action yet: the first ARS workbook has not been produced")
    if ars:
        if not rec["odd_current"]:
            issue(rec, "ARS", "blocker",
                  f"No {period} ODD extract in any CSM folder" + (f" (newest {rec['odd_month']})" if rec["odd_month"] else ""),
                  "Data team: land the ODD extract in the CSM's OD Data Dumps folder")
        if not wbs:
            issue(rec, "ARS", "blocker", "No ARS workbook in Inputs", "Data team: land the workbook on the client-reports share")
        if not dcos:
            issue(rec, "ARS", "gap", "No DCO in Inputs (dco_eligible is blank)", "Data team: land the DCO")
        if wbs and re.search(r"(?i)expired|need", wbs[-1]):
            issue(rec, "ARS", "warning", f"Workbook is flagged in its filename: {wbs[-1]}",
                  "Check the Lift Matrix with the data team before trusting MM figures")
        if uncalc or tcls == "unevaluated_workbook":
            issue(rec, "ARS", "blocker", "Workbook formulas were never calculated (reads as 1 month, $0)",
                  "Open the workbook in Excel, save, and rebuild")
        if tcls == "possible_data_issue":
            issue(rec, "ARS", "blocker", tdetail.replace("POSSIBLE DATA ISSUE: ", ""), "CSM: correct the client's code sheet (the pipeline does not map codes)")
        if tcls == "crash":
            issue(rec, "ARS", "blocker", f"Build failed: {tdetail}", "Pipeline fix")
        for k, v in rec["pack_flags"].items():
            issue(rec, "ARS", "warning", f"ODD pack flag {k}: {json.dumps(v)[:160]}",
                  ("CSM: correct the Reg E Codes on the client's code sheet (Y / N / D)" if k == "regE_unmapped" else "CSM: correct the Account Status Codes on the client's code sheet (O, C, X, I, F, R, D, Z)" if k == "status_other_raw" else "Data team: check the extract"))
    if rec["mrpc_analysis"] or "MRPC" in progs:
        if not rec["vip_mrpc"]:
            issue(rec, "MRPC", "blocker", "No VIP MRPC client sheet (MRPCPM analysis alone cannot build the deck)",
                  "Pull the client's sheet from the VIP MyRewards dashboard into Inputs/VIP Data/MRPC")
        if not rec["mrpc_analysis"]:
            issue(rec, "MRPC", "gap", "No MRPCPM analysis in Inputs", "Bradford Sanders / client-reports share")
    if "ICS" in progs:
        if not rec["vip_ics"]:
            issue(rec, "ICS", "blocker", "No VIP ICS referral sheet", "Pull from the VIP ICS Referral dashboard")
        if rec["ics_workbook"] != period:
            issue(rec, "ICS", "gap",
                  f"No {period} ICS workbook" + (f" (newest {rec['ics_workbook']})" if rec["ics_workbook"] else "")
                  + " — the section builds referrals-only", "Matt Milliman: the quarterly ICS workbook")
    if rec["cp_tab"] or "CP" in progs:
        if not rec["cp_settings"]:
            issue(rec, "CP", "gap", "No CashPlease product settings record (no Program Settings slide)",
                  "Export from the Velocity Product Settings Power BI app to Inputs/Product Settings")
        if rec["cp_no_dda"]:
            issue(rec, "CP", "gap", "No DDA count, so no loans-per-1,000-DDA rate",
                  "ILS Management Server DDA Count email")
    if not rec["on_roster"] and (progs or wbs or mrpcs or rec["cp_tab"]):
        issue(rec, "All", "decision", "Not on the clients.md roster, so nothing is delivered",
              "Aaron: confirm programs and add to clients.md")

summary = {
    "period": period, "generated": ds["generated"], "current_clients": len(clients),
    "former_clients": len(former), "trial_done": len(trial), "trial_total": len(trial),
    "trial_classes": dict(Counter(t for t, _ in map(trial_class, trial.values()))),
    "by_csm": dict(Counter(c["csm"] for c in clients)),
    "roster_clients": len(roster),
    "issues_by_severity": dict(Counter(i["severity"] for i in issues)),
    "issues_by_program": dict(Counter(i["program"] for i in issues)),
    "inputs": {k: len(list((I / d).glob("*"))) for k, d in R.INPUT_KIND_DIRS.items() if (I / d).exists()},
    "vip_sheets": dict(Counter(v["program"] for v in vip)),
    "cp_tabs_total": len(cp_tabs), "cp_flags": cp_idx.get("flags", []),
}
json.dump({"summary": summary, "clients": clients, "issues": issues,
           "former": [{"id": r["client_id"], "name": r["client_name"], "csm": r["csm"],
                       "odd_month": r["newest_odd_month"]} for r in former]},
          open(OUT, "w", encoding="utf-8"), indent=1)
print(f"gaps.json: {len(clients)} clients, {len(issues)} issues, period {period} -> {OUT}")
