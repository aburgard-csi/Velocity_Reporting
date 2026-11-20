#!/usr/bin/env python3
"""build_peer_reference.py — every figure a peer comparison uses, compiled into ONE dated reference on the share.

Aaron, 2026-11-20: "develop a peer comparison reference file that gets saved to the reporting folder. any metrics we use
for peer comparisons should be compiled in one source, tagged and dated."

    python scripts/build_peer_reference.py [--period 2026.11] [--dry-run] [--programs ARS ICS ...] [--allow-partial]

WHERE IT GOES (rpe_env.peer_reference_dir(), never a literal path):

    <RPE_DATA_ROOT>/Peer Reference/peer_metrics_<YYYY-MM-DD>.csv    today's compilation, one row per figure
    <RPE_DATA_ROOT>/Peer Reference/peer_metrics_latest.csv          a copy of the newest dated file
    <RPE_DATA_ROOT>/Peer Reference/manifest.json                    what was read, from where and when; row counts; the
                                                                    metric catalog; the content hash

ONE ROW per (program, metric, segment, scope, client, period): the value and its tags — unit, which way is better, the
definition, the period basis (a month, a 12-month window, program to date, a snapshot, 365 days to an as-of date), whether
the month had ended when the source was made (`month_complete`: yes / no / n/a for a snapshot or program-to-date figure),
the source kind, the source file (relative to RPE_DATA_ROOT) and its date, and which consumers read the figure.
`scope` is `client` for one client's figure and `cohort` for a benchmark computed over many (the CashPlease rollup and
current-client rows), whose `segment` names the cohort and whose client id is blank. Client NUMBERS only: no name field is
carried, although a source file's own name on the share can include one (as the share's file does).

HOW THE VALUES ARE MADE. Not re-derived here. Each program's figures are the rows `review_page/peer_pool.py`'s collectors
return (the code behind Live Review's "How you compare" and every Executive Review deck's "How You Compare" slide, through
`peer_compare.for_deck`), called with a client id that is in no pool so EVERY client comes back as a peer with its own
number. The ARS fields Sheila in Claude ranks (`sheila_mcp.reports.KPIS`) are read straight from the same launcher
`metrics.json` packs. The CashPlease cohort rows are the files the CashPlease deck and the performance dashboard wrote
(`cashplease/packs/peer_benchmark.json`, `perf_dashboard/dataset.json` `cp_peer`). ILS rows are the ILS peer table
(`ils_analysis/peers/ils_peer_metrics*.csv`) through `ils_review.peers_slides.values`. Only the provenance (file, date,
period) is looked up beside them.

Not filtered for a client: a consumer's own rules (a peer's ICS workbook at most three months older than the client's,
an ARS snapshot only from the same activity month, MIN_PEERS) are applied when it compares, so every client's own newest
figure is recorded with its own period and the reader can apply them.

READ-ONLY over the inputs. One side effect it shares with every deck build: the ICS collector refreshes
`Build Artifacts/peer_tables/ics_revenue.json` when an ICS workbook has changed (minutes over the share on a cold cache),
even with --dry-run. Idempotent: a rerun on the same day whose content is unchanged writes nothing; an earlier day's dated
file is never touched. A program that fails to compile stops the write (the reference is never quietly short a program)
unless --allow-partial, which records the failure in the manifest.

Not scheduled and not in the 08:00 watch: run by hand after a month's builds (warm the ICS cache first with
scripts/warm_peer_tables.py when new workbooks have landed).
"""
import argparse
import csv
import datetime
import glob
import hashlib
import io
import json
import os
import subprocess
import sys
import traceback
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
for _p in (REPO / "build", REPO / "build" / "mrpc_pipeline", REPO / "build" / "ils_analysis", REPO):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import month_complete as MC                                  # noqa: E402
import rpe_env                                               # noqa: E402

SENTINEL = "__peer_reference__"      # a client id in no pool: every real client comes back as a peer, with its number
LATEST_NAME = "peer_metrics_latest.csv"
MANIFEST_NAME = "manifest.json"
PROGRAMS = ("ARS", "ICS", "MRPC", "CP", "REMS", "ILS")

COLUMNS = ["program", "metric_key", "segment", "scope", "client_id", "period", "period_basis", "month_complete", "value",
           "unit", "higher_is_better", "label", "definition", "source_kind", "source_file", "source_date", "consumers",
           "compiled_at"]

LIVE = "Live Review: How you compare"
DECK = "Executive Review deck: How You Compare slide"

# How each collector metric is measured in time. A month-keyed series is "month"; the rest are named here.
BASIS = {
    ("ARS", "resp_12m"): "12m_window", ("ARS", "spend_gain"): "before_after", ("ARS", "spend_after"): "before_after",
    ("ARS", "moved_up"): "latest_mailing", ("ARS", "swipes_per_acct"): "3m_average", ("ARS", "spend_per_acct"): "3m_average",
    ("ARS", "rege_pct"): "snapshot", ("ARS", "rege_new_pct"): "snapshot", ("ARS", "take_new_pct"): "snapshot",
    ("ARS", "active_cards"): "snapshot", ("ARS", "ret_1yr"): "snapshot", ("ARS", "rev_per_1k"): "12m_average",
    ("ICS", "rev_total"): "program_to_date", ("ICS", "rev_interchange"): "program_to_date",
    ("ICS", "rev_nsf_od"): "program_to_date", ("ICS", "rev_spread"): "program_to_date",
    ("MRPC", "enroll_12_per_1k"): "12m_window", ("MRPC", "still_active"): "snapshot", ("MRPC", "take_active"): "snapshot",
    ("CP", "per_1k"): "12m_window", ("CP", "overdue"): "snapshot", ("CP", "charge_off"): "program_to_date",
    ("CP", "avg_loan"): "program_to_date", ("CP", "avg_interest"): "program_to_date", ("CP", "paid_off"): "program_to_date",
    ("CP", "loans_charged_off"): "program_to_date",
    ("REMS", "pct_opt_in_12"): "12m_window",
}
UNIT_BY_FMT = {"pct1": "percent", "pct0": "percent", "usd": "USD", "usd2": "USD", "int": "count", "dec1": "rate"}
UNIT = {
    ("ICS", "per_1k"): "referrals per 1,000 DDAs", ("CP", "per_1k"): "loans per 1,000 DDAs",
    ("CP", "per_1k_month"): "loans per 1,000 DDAs", ("MRPC", "enroll_12_per_1k"): "enrollments per 1,000 debit-card accounts",
    ("MRPC", "enroll_per_1k"): "enrollments per 1,000 debit-card accounts", ("ARS", "swipes_per_acct"): "swipes per account a month",
    ("ARS", "spend_per_acct"): "USD per account a month", ("ARS", "rev_per_1k"): "USD a month per 1,000 eligible accounts",
    ("ICS", "rev_total"): "USD per account a month", ("ICS", "rev_interchange"): "USD per account a month",
    ("ICS", "rev_nsf_od"): "USD per account a month", ("ICS", "rev_spread"): "USD per account a month",
    ("ILS", "items_per_1k"): "items per 1,000 open accounts", ("ILS", "fees_per_acct"): "USD per open account",
}
# Definitions the deck slide's notes do not carry (peer_slide.DEFS covers the rest).
DEFS = {
    ("CP", "per_1k_month"): "loans booked in the month per 1,000 DDAs (CashPlease Summary and the ILS DDA count)",
    ("CP", "avg_loan"): "principal over loans, program to date (CashPlease Summary)",
    ("CP", "avg_interest"): "interest over loans, program to date (CashPlease Summary)",
    ("CP", "paid_off"): "share of loans booked that are paid off, program to date (CashPlease Summary)",
    ("CP", "loans_charged_off"): "share of loans booked that were charged off, by count (CashPlease Summary)",
    ("REMS", "pct_opt_in_12"): "Reg E opt-ins over REMS responses, the 12 complete months before the report date (pooled)",
    ("REMS", "pct_opt_in"): "Reg E opt-ins over REMS responses in the month (months with 10 or more responses)",
    ("ICS", "pct_goal"): "referrals in the month as a share of the monthly goal (VIP ICS sheet)",
    ("MRPC", "pct_goal"): "enrollments as a share of the monthly goal (VIP MRPC sheet)",
    ("ILS", "items_per_1k"): "NSF/OD items in 365 days per 1,000 open accounts (the client's newest ZAccounts extract)",
    ("ILS", "fees_per_acct"): "collected fees in 365 days per open account (the client's newest ZAccounts extract)",
    ("ILS", "users_pct"): "open accounts with an NSF/OD item in 365 days, share of open accounts",
}


# ================================================================= small helpers
def _yyyymm(token):
    d = MC.month_start(str(token).replace(".", "-")) if token else None
    return f"{d.year:04d}.{d.month:02d}" if d else ""


def _date(v):
    """A date from 'YYYY-MM-DD', 'YYYYMMDD', 'M/D/YYYY ...' or a date; None otherwise."""
    if isinstance(v, datetime.datetime):
        return v.date()
    if isinstance(v, datetime.date):
        return v
    s = str(v or "").strip()
    for fmt, n in (("%Y-%m-%d", 10), ("%Y%m%d", 8)):
        try:
            return datetime.datetime.strptime(s[:n], fmt).date()
        except ValueError:
            pass
    return MC.report_date(s)


def _complete(month, as_of, basis):
    """'yes' / 'no' when the period is a month or ends a window and the source's date is known; 'n/a' for a snapshot or a
    program-to-date figure; '' when the source carries no date."""
    if basis in ("snapshot", "program_to_date", "latest_mailing", "365d_to_as_of"):
        return "n/a"
    if not month or not as_of:
        return ""
    done = MC.month_ended(str(month).replace(".", "-"), as_of)
    return "" if done is None else ("yes" if done else "no")


def _rel(path):
    """A path relative to RPE_DATA_ROOT, with forward slashes ('' when it is not under it)."""
    if not path:
        return ""
    try:
        return Path(path).resolve().relative_to(rpe_env.data_root().resolve()).as_posix()
    except (ValueError, OSError, SystemExit):
        return Path(path).name


def _value(v):
    if v is None or isinstance(v, bool):
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if f != f else f


class Catalog:
    """Every metric the reference carries: {(program, metric_key): entry}."""

    def __init__(self):
        self.items = {}

    def add(self, program, key, label, unit, higher, basis, definition, source_kind, consumers):
        self.items[(program, key)] = {"program": program, "metric_key": key, "label": label, "unit": unit,
                                      "higher_is_better": higher, "period_basis": basis, "definition": definition,
                                      "source_kind": source_kind, "consumers": consumers}
        return self.items[(program, key)]


def _row(cat, program, key, cid, period, value, as_of=None, source_file="", segment="", scope="client", source_kind=None,
         basis=None):
    e = cat.items[(program, key)]
    v = _value(value)
    if v is None:
        return None
    b = basis or e["period_basis"]
    return {"program": program, "metric_key": key, "segment": segment, "scope": scope,
            "client_id": "" if scope == "cohort" else str(cid), "period": period, "period_basis": b,
            "month_complete": _complete(period, as_of, b), "value": v, "unit": e["unit"],
            "higher_is_better": {True: "yes", False: "no", None: "neither"}[e["higher_is_better"]], "label": e["label"],
            "definition": e["definition"], "source_kind": source_kind or e["source_kind"], "source_file": source_file,
            "source_date": as_of.isoformat() if isinstance(as_of, datetime.date) else (as_of or ""),
            "consumers": e["consumers"]}


def _collector_catalog(cat, program, source_kind):
    """Catalog entries for one peer_pool program, from its own metric list (labels, formats, direction)."""
    from review_page import peer_pool as PP
    import peer_slide as PS
    _collect, metrics, _who = PP.PROGRAMS[program]
    on_deck = set(PS.METRICS.get(program, []))
    for spec in metrics:
        key = spec["key"]
        basis = "month" if spec.get("month") else BASIS.get((program, key), "snapshot")
        defin = DEFS.get((program, key)) or (PS._def(program, key) if key in PS.DEFS or key == "per_1k" else None) or spec["label"]
        consumers = LIVE + (f"; {DECK}" if key in on_deck else "")
        cat.add(program, key, spec["label"], UNIT.get((program, key)) or UNIT_BY_FMT.get(spec["fmt"], spec["fmt"]),
                spec.get("higher"), basis, defin, source_kind, consumers)
    return metrics


def _peer_rows(coll):
    """{client id: {"point", "series"}} from a collector run with the sentinel client."""
    return {str(p["id"]): p for p in coll["peers"] if p.get("id") is not None}


# ================================================================= ARS
def compile_ars(cat, period, notes):
    from review_page import peer_pool as PP
    import peer_tables as PT
    metrics = _collector_catalog(cat, "ARS", "ARS launcher data pack (metrics.json, base.json)")
    ba = rpe_env.build_artifacts()
    coll = PP.collect_ars(PP.PeerCtx(client=SENTINEL, period=period))
    rows, meta = [], {}
    for cid, (per, folder) in PT.ars_pack_dirs(ba, period).items():
        m = PT._json(Path(folder) / "metrics.json") or {}
        b = PT._json(Path(folder) / "base.json") or {}
        meta[cid] = {"folder": folder, "pack_period": per, "metrics": m,
                     "activity": m.get("activity_month"), "pull": _date((m.get("month_completeness") or {}).get("pull_date")),
                     "rev_month": ((b.get("monthly_rev_last12") or [[None]])[-1] or [None])[0]}
    for cid, r in _peer_rows(coll).items():
        mt = meta.get(cid) or {}
        src = _rel(Path(mt["folder"]) / "metrics.json") if mt.get("folder") else ""
        for spec in metrics:
            k = spec["key"]
            if spec.get("month"):
                for mon, v in (r["series"].get(k) or {}).items():
                    rows.append(_row(cat, "ARS", k, cid, _yyyymm(mon), v, mt.get("pull"), src))
            elif k in r["point"]:
                if k == "rev_per_1k":
                    rows.append(_row(cat, "ARS", k, cid, _yyyymm(mt.get("rev_month")), r["point"][k], None,
                                     _rel(Path(mt["folder"]) / "base.json") if mt.get("folder") else ""))
                else:
                    rows.append(_row(cat, "ARS", k, cid, _yyyymm(mt.get("activity")), r["point"][k], mt.get("pull"), src))
    # The fields Sheila in Claude ranks clients on (sheila_mcp.reports.KPIS), read as they are from the same packs. Sheila
    # compares the clients whose deck was built for one period; the reference records every client's newest pack.
    try:
        from sheila_mcp import reports as SR
        kpis = SR.KPIS
    except Exception as exc:                                  # noqa: BLE001 - a broken import is reported, never fatal here
        notes.append(f"ARS: Sheila in Claude's KPI list could not be read ({type(exc).__name__}: {exc}); its fields are left out")
        kpis = {}
    for kpi, (label, field, higher) in kpis.items():
        key = f"metrics.{field}"
        ent = cat.items.get(("ARS", key))
        if ent:
            ent["consumers"] += f"; Sheila in Claude: peer_compare ({kpi})"
            continue
        cat.add("ARS", key, label, "percent", higher, "snapshot" if field != "latest_resprate" else "latest_mailing",
                f"the launcher pack's `{field}` field as the deck states it, unfiltered (Sheila in Claude ranks it among "
                f"the clients built for the same period)", "ARS launcher data pack (metrics.json)",
                f"Sheila in Claude: peer_compare ({kpi})")
    for cid, mt in meta.items():
        for kpi, (label, field, higher) in kpis.items():
            rows.append(_row(cat, "ARS", f"metrics.{field}", cid, _yyyymm(mt.get("activity")), mt["metrics"].get(field),
                             mt.get("pull"), _rel(Path(mt["folder"]) / "metrics.json")))
    return [r for r in rows if r], {"launcher packs": len(meta), "pull": coll.get("pull")}


# ================================================================= ICS
def _in(kind, name):
    """`Inputs/<kind folder>/<name>`, relative to RPE_DATA_ROOT ('' when there is no name)."""
    if not name:
        return ""
    try:
        return _rel(rpe_env.input_dir(kind, create=False) / name)
    except (SystemExit, OSError, KeyError):
        return f"Inputs/{rpe_env.INPUT_KIND_DIRS.get(kind, kind)}/{name}"


def _vip_meta(program):
    """{client id: (file relative to RPE_DATA_ROOT, data_pull date)} from the VIP manifest."""
    root = rpe_env.vip_data()
    out = {}
    for e in rpe_env.vip_manifest() or []:
        if str(e.get("program", "")).upper() == program and root is not None:
            out[str(e.get("client_id"))] = (_rel(root / e.get("file", "")), _date(e.get("data_pull")))
    return out


def compile_ics(cat, period, notes):
    from review_page import peer_pool as PP
    import peer_tables as PT
    metrics = _collector_catalog(cat, "ICS", "VIP ICS sheet; ICS referrals file + ILS DDA count; ICS workbook")
    ctx = PP.PeerCtx(client=SENTINEL, period=None)           # no period: the workbook age rule is the consumer's, not ours
    coll = PP.collect_ics(ctx)
    vip = _vip_meta("ICS")
    refs, newest = PP.referrals_by_month()
    from_file = set(PP._ics_per_1k(refs, newest, PP._dda(ctx)))
    ref_file = _in("ICS referrals", "ics_referrals.csv")
    try:
        wb_dir = rpe_env.input_dir("ICS workbook", create=False)
    except Exception:                                          # noqa: BLE001
        wb_dir = None
    wbs = PT.ics_revenue_rows(folder=wb_dir) if wb_dir else {}
    rows = []
    for cid, r in _peer_rows(coll).items():
        vf, vpull = vip.get(cid, ("", None))
        for spec in metrics:
            k = spec["key"]
            if spec.get("month"):
                for mon, v in (r["series"].get(k) or {}).items():
                    if k == "per_1k" and cid in from_file:
                        rows.append(_row(cat, "ICS", k, cid, _yyyymm(mon), v, _date(newest), ref_file,
                                         source_kind="ICS referrals file (all clients) + ILS DDA count"))
                    elif k == "per_1k":
                        rows.append(_row(cat, "ICS", k, cid, _yyyymm(mon), v, vpull, vf,
                                         source_kind="VIP ICS sheet referral trend + ILS DDA count"))
                    else:
                        rows.append(_row(cat, "ICS", k, cid, _yyyymm(mon), v, vpull, vf, source_kind="VIP ICS sheet"))
            elif k in r["point"]:
                w = wbs.get(cid) or {}
                rows.append(_row(cat, "ICS", k, cid, _yyyymm(w.get("month") or w.get("period")), r["point"][k], None,
                                 _rel(Path(wb_dir) / w["file"]) if w.get("file") and wb_dir else "",
                                 source_kind="ICS workbook, Monthly Detail tab (peer_tables cache)"))
    return [r for r in rows if r], {"VIP ICS sheets": len(vip), "referral file clients": len(from_file),
                                    "ICS workbooks": len(wbs), "pull": coll.get("pull")}


# ================================================================= MRPC
def compile_mrpc(cat, period, notes):
    from review_page import peer_pool as PP
    metrics = _collector_catalog(cat, "MRPC", "MRPCEnrollmentSummary weekly; VIP MRPC sheet")
    coll = PP.collect_mrpc(PP.PeerCtx(client=SENTINEL, period=None))
    wk = PP._weekly()
    wk_file = _rel(wk.path) if getattr(wk, "path", None) else ""
    vip = _vip_meta("MRPC")
    rows = []
    for cid, r in _peer_rows(coll).items():
        w = wk.client(cid) if cid in wk.tabs else None
        gen = MC.report_date((w or {}).get("report_generated"))
        newest = max((x["month"] for x in (w or {}).get("monthly") or []), default=None)
        vf, vpull = vip.get(cid, ("", None))
        for spec in metrics:
            k = spec["key"]
            if spec.get("month"):
                for mon, v in (r["series"].get(k) or {}).items():
                    if k == "pct_goal":
                        rows.append(_row(cat, "MRPC", k, cid, _yyyymm(mon), v, vpull, vf, source_kind="VIP MRPC sheet"))
                    else:
                        rows.append(_row(cat, "MRPC", k, cid, _yyyymm(mon), v, gen, wk_file,
                                         source_kind="MRPCEnrollmentSummary weekly"))
            elif k in r["point"]:
                per = _yyyymm(newest) if k == "enroll_12_per_1k" else (gen.strftime("%Y.%m") if gen else "")
                rows.append(_row(cat, "MRPC", k, cid, per, r["point"][k], gen, wk_file,
                                 source_kind="MRPCEnrollmentSummary weekly"))
    return [r for r in rows if r], {"weekly": Path(wk.path).name if getattr(wk, "path", None) else None,
                                    "VIP MRPC sheets": len(vip), "pull": coll.get("pull")}


# ================================================================= CashPlease
def compile_cp(cat, period, notes):
    from review_page import peer_pool as PP
    metrics = _collector_catalog(cat, "CP", "CashPlease pack (cp_extract, from the CashPleaseSummary weekly)")
    for k in ("per_1k", "overdue", "charge_off", "avg_loan", "avg_interest", "paid_off"):
        if ("CP", k) in cat.items:
            cat.items[("CP", k)]["consumers"] += "; CashPlease deck: Peer Comparison slide (cohort rows); Sheila in Claude: cashplease_report"
    cat.add("CP", "loans_charged_off", "Share of loans charged off", "percent", False, "program_to_date",
            DEFS[("CP", "loans_charged_off")], "CashPlease pack (cp_extract)", "Sheila in Claude: cashplease_report")
    coll = PP.collect_cashplease(PP.PeerCtx(client=SENTINEL))
    packs = rpe_env.build_artifacts() / "cashplease" / "packs"
    rows, n = [], 0
    for cid, r in _peer_rows(coll).items():
        d = _json_file(packs / f"{cid}_cashplease.json") or {}
        gen = MC.report_date(d.get("report_generated"))
        src = _in("CP weekly", d.get("source_file")) or _rel(packs / f"{cid}_cashplease.json")
        mon = sorted((x.get("period_month") for x in d.get("monthly") or [] if x.get("period_month")), reverse=True)
        n += 1
        for spec in metrics:
            k = spec["key"]
            if spec.get("month"):
                for m_, v in (r["series"].get(k) or {}).items():
                    rows.append(_row(cat, "CP", k, cid, _yyyymm(m_), v, gen, src))
            elif k in r["point"]:
                per = _yyyymm(mon[0]) if (k == "per_1k" and mon) else (gen.strftime("%Y.%m") if gen else "")
                rows.append(_row(cat, "CP", k, cid, per, r["point"][k], gen, src))
        v = (d.get("metrics") or {}).get("pct_loans_charged_off")
        rows.append(_row(cat, "CP", "loans_charged_off", cid, gen.strftime("%Y.%m") if gen else "",
                         None if v is None else 100.0 * v, gen, src))
    # The two cohort benchmarks other consumers compare a client with (rates and averages; the values these files hold,
    # in the per-client rows' units).
    cohorts = []
    bench = _json_file(packs / "peer_benchmark.json")
    ds = _json_file(rpe_env.build_artifacts() / "perf_dashboard" / "dataset.json") or {}
    for seg, d, src, gen_date in (
            ("all_tabs_rollup", bench, _rel(packs / "peer_benchmark.json"), None),
            ("current_clients", ds.get("cp_peer"), _rel(rpe_env.build_artifacts() / "perf_dashboard" / "dataset.json"),
             _date(ds.get("generated") or ds.get("generated_at")))):
        if not d:
            continue
        cohorts.append(seg)
        for k, field, scale in (("per_1k", "loans_per_1k_dda", 1), ("charge_off", "charge_off_pct", 100),
                                ("avg_loan", "avg_loan_size", 1), ("avg_interest", "avg_interest_per_loan", 1),
                                ("overdue", "pct_loans_overdue", 100), ("paid_off", "pct_loans_paid_off", 100),
                                ("loans_charged_off", "pct_loans_charged_off", 100)):
            v = d.get(field)
            rows.append(_row(cat, "CP", k, "", "", None if v is None else scale * v, gen_date, src, segment=seg,
                             scope="cohort", source_kind=d.get("cohort") or seg))
    return [r for r in rows if r], {"CashPlease packs": n, "cohorts": cohorts, "pull": coll.get("pull")}


def _json_file(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


# ================================================================= REMS
def compile_rems(cat, period, notes):
    from review_page import peer_pool as PP
    metrics = _collector_catalog(cat, "REMS", "REMS responses report (Inputs/REMS)")
    ctx = PP.PeerCtx(client=SENTINEL)
    coll = PP.collect_rems(ctx)
    _rows, as_of, fname = PP.rems_rows(ctx)
    src = _in("REMS", fname)
    end = None
    if as_of:
        y, m = divmod(as_of.year * 12 + as_of.month - 2, 12)
        end = f"{y:04d}.{m + 1:02d}"                         # the last complete month of the 12-month window
    rows = []
    for cid, r in _peer_rows(coll).items():
        for spec in metrics:
            k = spec["key"]
            if spec.get("month"):
                for mon, v in (r["series"].get(k) or {}).items():
                    rows.append(_row(cat, "REMS", k, cid, _yyyymm(mon), v, as_of, src))
            elif k in r["point"]:
                rows.append(_row(cat, "REMS", k, cid, end, r["point"][k], as_of, src))
    return [r for r in rows if r], {"file": fname, "pull": coll.get("pull")}


# ================================================================= ILS
def compile_ils(cat, period, notes):
    from ils_review import peers_slides as IP
    for spec in IP.METRICS:
        k = spec["key"]
        cat.add("ILS", k, spec["label"], UNIT.get(("ILS", k)) or UNIT_BY_FMT.get(spec["fmt"], spec["fmt"]), spec.get("higher"),
                "365d_to_as_of", DEFS[("ILS", k)], "ILS peer table (peer_pull, ZAccounts extracts)",
                "ILS analysis review: peer comparison slides (peers_slides)")
    folder = rpe_env.build_artifacts() / "ils_analysis" / "peers"
    files = sorted(glob.glob(str(folder / "ils_peer_metrics*.csv")))   # peer_pull.metrics_files(), without its makedirs
    table, src_of = {}, {}
    for f in files:                                            # later files win, as peers_slides.read_metrics reads them
        for key, r in IP.read_metrics(f).items():
            table[key] = r
            src_of[key] = _rel(f)
    rows = []
    for (cid, acct), r in sorted(table.items()):
        vals = IP.values(r)
        if not vals:
            continue
        as_of = _date(r.get("as_of"))
        for spec in IP.METRICS:
            rows.append(_row(cat, "ILS", spec["key"], cid, as_of.strftime("%Y.%m") if as_of else "", vals.get(spec["key"]),
                             as_of, src_of[(cid, acct)], segment=str(acct).lower()))
    return [r for r in rows if r], {"tables": [Path(f).name for f in files], "client segments": len(table)}


COMPILERS = {"ARS": compile_ars, "ICS": compile_ics, "MRPC": compile_mrpc, "CP": compile_cp, "REMS": compile_rems,
             "ILS": compile_ils}


# ================================================================= assemble and write
def compile_all(period, programs=PROGRAMS, log=print):
    cat, rows, sources, failed, notes = Catalog(), [], {}, {}, []
    for p in programs:
        try:
            got, src = COMPILERS[p](cat, period, notes)
        except (Exception, SystemExit) as exc:                # noqa: BLE001 - every failure is named, never swallowed
            failed[p] = f"{type(exc).__name__}: {exc}"
            log(f"{p}: FAILED - {failed[p]}")
            log(traceback.format_exc(limit=3))
            continue
        rows.extend(got)
        sources[p] = src
        log(f"{p}: {len(got)} rows")
    rows.sort(key=lambda r: (r["program"], r["metric_key"], r["segment"], r["scope"], r["client_id"].zfill(6), r["period"]))
    return {"rows": rows, "catalog": list(cat.items.values()), "sources": sources, "failed": failed, "notes": notes}


def _csv_text(rows, compiled_at):
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=COLUMNS, lineterminator="\n")
    w.writeheader()
    for r in rows:
        out = dict(r, compiled_at=compiled_at)
        out["value"] = format(r["value"], ".10g")
        w.writerow(out)
    return buf.getvalue()


def content_hash(rows):
    """SHA-256 of the rows without the compile time, so an unchanged rerun is recognised."""
    return hashlib.sha256(_csv_text(rows, "").encode("utf-8")).hexdigest()


def counts(rows):
    out = {}
    for r in rows:
        key = f"{r['program']} {r['metric_key']}" + (f" [{r['segment']}]" if r["segment"] else "")
        out[key] = out.get(key, 0) + 1
    return dict(sorted(out.items()))


def _git_commit():
    try:
        return subprocess.run(["git", "-C", str(REPO), "rev-parse", "HEAD"], capture_output=True, text=True,
                              timeout=10).stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def _write(path, text):
    part = path.with_name(path.name + ".part")
    part.write_text(text, encoding="utf-8", newline="")
    os.replace(part, path)


def write_reference(result, period, today=None, now=None, log=print):
    """Write today's dated file, the latest copy and the manifest. Returns (status, folder): 'unchanged' when today's
    file already holds the same content; an earlier day's dated file is never opened for writing."""
    today = today or datetime.date.today()
    now = now or datetime.datetime.now()
    folder = rpe_env.peer_reference_dir(create=True)
    dated = folder / f"peer_metrics_{today.isoformat()}.csv"
    h = content_hash(result["rows"])
    old = _json_file(folder / MANIFEST_NAME) or {}
    if dated.exists() and old.get("content_hash") == h and old.get("dated_file") == dated.name:
        log(f"unchanged: {dated} already holds this content")
        return "unchanged", folder
    compiled_at = now.isoformat(timespec="seconds")
    text = _csv_text(result["rows"], compiled_at)
    _write(dated, text)
    _write(folder / LATEST_NAME, text)
    manifest = {
        "compiled_at": compiled_at, "date": today.isoformat(), "period": period, "dated_file": dated.name,
        "latest_file": LATEST_NAME, "content_hash": h, "git_commit": _git_commit(), "rows": len(result["rows"]),
        "rows_by_program": {p: sum(1 for r in result["rows"] if r["program"] == p) for p in PROGRAMS},
        "rows_by_metric": counts(result["rows"]), "sources": result["sources"], "failed": result["failed"],
        "notes": result["notes"], "columns": COLUMNS, "catalog": result["catalog"],
    }
    _write(folder / MANIFEST_NAME, json.dumps(manifest, indent=2, default=str))
    log(f"wrote {dated} ({len(result['rows'])} rows), {LATEST_NAME} and {MANIFEST_NAME}")
    return "written", folder


def main(argv=None, today=None, log=print):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--period", help="yyyy.mm; ARS packs at or before it (default: the calendar month)")
    ap.add_argument("--programs", nargs="*", default=list(PROGRAMS), choices=PROGRAMS)
    ap.add_argument("--dry-run", action="store_true", help="compile and report; write nothing")
    ap.add_argument("--allow-partial", action="store_true", help="write even when a program failed to compile")
    a = ap.parse_args(argv)
    period = a.period or (today or datetime.date.today()).strftime("%Y.%m")
    result = compile_all(period, a.programs, log=log)
    for k, v in counts(result["rows"]).items():
        log(f"  {k}: {v}")
    for n in result["notes"]:
        log("note: " + n)
    log(f"{len(result['rows'])} rows; content hash {content_hash(result['rows'])[:12]}")
    if a.dry_run:
        log("dry run: nothing written")
        return 1 if result["failed"] else 0
    if result["failed"] and not a.allow_partial:
        log("not written: " + "; ".join(f"{p} ({e})" for p, e in result["failed"].items())
            + ". Fix it, or rerun with --allow-partial to record the failure in the manifest.")
        return 1
    write_reference(result, period, today=today, log=log)
    return 1 if result["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
