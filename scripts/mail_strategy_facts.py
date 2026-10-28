#!/usr/bin/env python3
"""mail_strategy_facts.py — the figures behind a client's Delivery Call Notes (Aaron, 2026-10-28).

The notes live in the Business Utilities Mail Strategy form and follow one format per product line:
`<rating>. <facts>. <open issues>. [MM/DD]`. This tool produces the FACTS half from the same inputs the decks
read, so a note and its deck cannot disagree, and the wording of every comparison is one function:

    ICS referrals, MRPC enrollments, CashPlease loans   the last COMPLETE month against the prior six months'
                                                         average, +/-20% band: "consistent with" / "higher
                                                         than" / "lower than" (never % of goal; an MRPC goal
                                                         is always too high)
    ARS profitability                                    stated only below 3:1
    Last sent                                            the newest `sent_at` in Build Artifacts/deliveries.json,
                                                         which is what Recent Review Date is

It never writes anything and never touches the form. Proof status (Outlook) and the on-site date (the calendar's
"Onsite" category) are not in any file; the skill that calls this reads them from the mailbox and the calendar.

    python scripts/mail_strategy_facts.py 1038 1075 [--json]

Paths come from rpe_env (RPE_DATA_ROOT). Import-safe: nothing runs at import.
"""
import argparse
import datetime as dt
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (os.path.join(HERE, os.pardir, "build"), os.path.join(HERE, os.pardir, "build", "mrpc_pipeline"), HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

BAND = 0.20                  # within +/-20% of the usual level is "consistent with"
PRIOR_MONTHS = 6
PROFITABILITY_FLOOR = 3.0    # a ratio is mentioned only below 3:1


def month_label(ym):
    """'2026-09' -> 'Sep 26'."""
    y, m = ym.split("-")
    return dt.date(int(y), int(m), 1).strftime("%b %y")


def usual_level(values, prior=PRIOR_MONTHS):
    """The average of the `prior` months before the last one in `values` (oldest first), or None."""
    before = [v for v in values[:-1] if v is not None][-prior:]
    return sum(before) / len(before) if len(before) >= 3 else None


def comparison(label, last, usual, noun):
    """'Sep 26: 290 referrals, lower than the prior 6-month average of 367 (-21%).'

    consistent within +/-20% (no percentage); higher or lower outside it, with the percentage."""
    if usual is None or usual <= 0:
        return f"{label}: {last:,.0f} {noun}, no prior 6-month average to compare with."
    change = (last - usual) / usual
    if abs(change) <= BAND:
        verb = "consistent with"
    else:
        verb = "higher than" if change > 0 else "lower than"
    tail = "" if verb == "consistent with" else f" ({change:+.0%})"      # the % only when it is outside the band
    return f"{label}: {last:,.0f} {noun}, {verb} the prior {PRIOR_MONTHS}-month average of {usual:,.0f}{tail}."


def complete_series(months, values, partial_last=False, generated=None):
    """(months, values) with the month still in progress dropped.

    A month is incomplete when the source says its last point is partial, or when it is the month of the report's
    generation date or later (the same rule month_complete applies to every comparison)."""
    months, values = list(months), list(values)
    if partial_last and months:
        months.pop()
        values.pop()
    if generated:
        cut = generated[:7]
        while months and months[-1] >= cut:
            months.pop()
            values.pop()
    return months, values


def _ym(label):
    """'Aug 25' / '2026-09' -> '2026-09'."""
    if re.fullmatch(r"\d{4}-\d{2}", str(label)):
        return str(label)
    d = dt.datetime.strptime(str(label), "%b %y")
    return f"{d.year}-{d.month:02d}"


def ics_line(sheet):
    """The ICS referrals line from a VIP ICS sheet, or None when it has no trend."""
    tr = ((sheet or {}).get("referrals") or {}).get("trend") or {}
    if not tr.get("months"):
        return None
    months, vals = complete_series([_ym(m) for m in tr["months"]], tr["referrals"], bool(tr.get("partial_last")))
    if not months:
        return None
    return comparison(month_label(months[-1]), vals[-1], usual_level(vals), "referrals")


def mrpc_line(monthly):
    """The MRPC enrollments line from the weekly's `monthly` rows (primary + joint cardholders per month)."""
    rows = sorted((r for r in (monthly or []) if r.get("month")), key=lambda r: r["month"])
    if not rows:
        return None
    vals = [(r.get("primary") or 0) + (r.get("joint") or 0) for r in rows]
    return comparison(month_label(rows[-1]["month"]), vals[-1], usual_level(vals), "enrollments")


def cp_line(pack):
    """The CashPlease loans line from a client's pack (complete months only)."""
    rows = sorted((r for r in (pack or {}).get("monthly") or [] if r.get("period_month")),
                  key=lambda r: r["period_month"])
    gen = str((pack or {}).get("report_generated") or "")
    m = re.match(r"(\d+)/(\d+)/(\d{4})", gen)
    generated = f"{m.group(3)}-{int(m.group(1)):02d}" if m else None
    months, vals = complete_series([r["period_month"] for r in rows], [r.get("loans") or 0 for r in rows],
                                   generated=generated)
    if not months:
        return None
    return comparison(month_label(months[-1]), vals[-1], usual_level(vals), "loans")


def profitability_phrase(ratio):
    """'Profitability 2.15:1, below 3:1.' only below the floor, else None (nothing to say)."""
    if ratio is None or ratio >= PROFITABILITY_FLOOR:
        return None
    return f"Profitability {ratio:.2f}:1, below {PROFITABILITY_FLOOR:g}:1."


def last_sent(sent, cid):
    """The newest recorded send for `cid` as (sent_at 'YYYY-MM-DD', period), or None."""
    best = None
    for key, v in (sent or {}).items():
        if not key.startswith(f"{cid}|"):
            continue
        at = (v.get("sent_at") if isinstance(v, dict) else v) or ""
        if at and (best is None or at > best[0]):
            best = (at, key.split("|", 1)[1])
    return best


def profitability_of(cid):
    """The client's ARS profitability ratio from the newest base extract on hand, or None."""
    import rpe_env as R
    ba = R.build_artifacts()
    hits = sorted(ba.glob(f"launcher/*/{cid}/base.json"), key=lambda p: p.stat().st_mtime) + \
        [ba / "perf_dashboard" / f"{cid}_base.json"]
    for p in reversed(hits):
        try:
            return json.loads(p.read_text(encoding="utf-8")).get("profitability")
        except (OSError, ValueError):
            continue
    return None


def gather(cids):
    """One dict per client: programs, last send, profitability, and each program's comparison line."""
    import rpe_env as R
    import build_month as BM
    roster = {c[0]: c for c in BM.read_roster()[0]}
    cp_rows = {r["client_id"]: r for r in BM.read_cashplease_roster()}
    try:
        from mrpc_weekly import MrpcWeekly
        weekly = MrpcWeekly(R.report_dirs())
    except Exception:      # noqa: BLE001 — no weekly on hand: the MRPC line says so
        weekly = None
    sent = json.loads((R.build_artifacts() / "deliveries.json").read_text(encoding="utf-8")).get("sent", {})
    out = []
    for cid in cids:
        entry = roster.get(cid)
        progs = list(entry[3]) if entry else []
        doc = {"client": cid, "name": entry[1] if entry else None, "programs": progs}
        ls = last_sent(sent, cid)
        doc["last_sent"] = {"date": ls[0], "period": ls[1]} if ls else None
        if "ARS" in progs:
            ratio = profitability_of(cid)
            doc["profitability"] = ratio
            doc["profitability_phrase"] = profitability_phrase(ratio)
        if any(p.startswith("ICS") for p in progs):
            try:
                doc["ics"] = ics_line(json.loads(open(R.resolve_client_json(cid, "ics"), encoding="utf-8").read()))
            except (SystemExit, OSError, ValueError):
                doc["ics"] = None
        if "MRPC" in progs:
            tab = weekly.client(cid) if weekly and weekly.path else None
            doc["mrpc"] = mrpc_line((tab or {}).get("monthly"))
        if cid in cp_rows and cp_rows[cid]["build"]:
            f = R.build_artifacts() / "cashplease" / "packs" / f"{cid}_cashplease.json"
            try:
                doc["cp"] = cp_line(json.loads(f.read_text(encoding="utf-8")))
            except (OSError, ValueError):
                doc["cp"] = None
        out.append(doc)
    return out


def render(docs):
    lines = []
    for d in docs:
        lines.append(f"{d['client']} {d.get('name') or '(not in clients.md)'}  [{'-'.join(d['programs']) or 'no program'}]")
        ls = d.get("last_sent")
        lines.append("  Recent Review Date (last sent): " + (f"{ls['date']} ({ls['period']})" if ls else "none recorded"))
        if "profitability" in d:
            ratio = d["profitability"]
            lines.append("  ARS: " + (d["profitability_phrase"] or (
                f"{ratio:.2f}:1, at or above 3:1: say nothing about profitability" if ratio is not None
                else "no profitability on hand")))
        for k, label in (("ics", "ICS"), ("mrpc", "MRPC"), ("cp", "CP")):
            if k in d:
                lines.append(f"  {label}: {d[k] or '(no data)'}")
        lines.append("")
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("clients", nargs="+")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    for c in a.clients:
        if not re.fullmatch(r"\d{3,5}", c):
            print(f"'{c}' is not a client number.")
            return 2
    docs = gather(a.clients)
    print(json.dumps(docs, indent=1) if a.json else render(docs))
    return 0


if __name__ == "__main__":
    sys.exit(main())
