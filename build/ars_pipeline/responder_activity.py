#!/usr/bin/env python3
"""
responder_activity.py — responder before/after activity from the raw ODDD.

Mirrors the method in build/ars_pipeline/metrics_gen.py (the ARS deck's
"Responder Activity: Before vs After" and "Transaction Increase Over the Ask"
slides) so the one-pager agrees with the client's deck instead of restating it:

  * eligible cohort = personal accounts with <latest month> Elig == Yes
  * a responder met the goal in any mailing month (Resp in RESP_MET)
  * per mature mailing with >= 5 responders: mean monthly debit spend over the
    3 months BEFORE the mailing vs every month AFTER, winsorized at 3 SD;
    headline = the mean across mailings
  * transaction increase over the ask = swipes in the month after the latest
    met-goal offer, minus that offer's goal

Written standalone rather than by importing metrics_gen because metrics_gen
carries two stale-month assumptions ('Jun26 Elig', w3/NOW = Jun 2026) and picks
the first .csv in the zip — which on several clients is the raw transaction
file, not the ODD extract.

Usage: python3 responder_activity.py <ODDD.zip|.csv> <out.json>
"""
import csv
import datetime
import io
import json
import re
import statistics
import sys
import zipfile

from odd_rows import accessors

csv.field_size_limit(10 ** 7)

RESP_MET = {"NU 5+", "TH-10", "TH-15", "TH-20", "TH-25"}
RESP_GOAL = {"NU 5+": 5, "TH-10": 10, "TH-15": 15, "TH-20": 20, "TH-25": 25}
OFFER_GOAL = dict(RESP_GOAL)


def mkey(t):
    return datetime.datetime.strptime(t[:3] + " " + t[3:], "%b %y")


def lbl(t):
    return mkey(t).strftime("%b %Y")


def linesrc(path):
    if path.lower().endswith(".zip"):
        zf = zipfile.ZipFile(path)
        members = [n for n in zf.namelist() if n.lower().endswith(".csv")]
        odd = [n for n in members if "-odd" in n.lower() or "_v2_" in n.lower()]
        name = odd[0] if odd else max(members,
                                      key=lambda n: zf.getinfo(n).file_size)
        return io.TextIOWrapper(zf.open(name), encoding="latin-1",
                                errors="replace", newline="")
    return open(path, encoding="latin-1", errors="replace")


def load(path):
    with linesrc(path) as fh:
        head = []
        for i, line in enumerate(fh):
            head.append(line)
            if i >= 4:
                break
    hdr = [h.strip() for h in
           next(csv.reader([head[4].replace("\x00", "")]))]

    smonths = sorted({m.group(1) for m in
                      (re.match(r"^([A-Z][a-z]{2}\d{2}) Sig #$", h) for h in hdr)
                      if m}, key=mkey)
    mailmonths = sorted({m.group(1) for m in
                         (re.match(r"^([A-Z][a-z]{2}\d{2}) Mail$", h) for h in hdr)
                         if m}, key=mkey)
    latest = smonths[-1]

    keep = {f"{latest} Elig", "Business?", "Debit?"}
    fam = re.compile(r"^[A-Z][a-z]{2}\d{2} (Sig #|PIN #|Sig \$|PIN \$|Mail|Resp)$")
    need = [i for i, c in enumerate(hdr) if c in keep or fam.match(c)]
    redhdr = [hdr[i] for i in need]
    H = {h: j for j, h in enumerate(redhdr)}
    pad = max(need) + 1

    rows = []
    with linesrc(path) as fh:
        rdr = csv.reader((l.replace("\x00", "") for l in fh))
        for k, row in enumerate(rdr):
            if k < 5:
                continue
            if len(row) < pad:
                row = row + [""] * (pad - len(row))
            if "".join(row).strip():
                rows.append([row[i] for i in need])
    return H, smonths, mailmonths, latest, rows


def analyse(path):
    H, smonths, mailmonths, latest, rows = load(path)

    # These were re-implemented here because importing metrics_gen RUNS it (it
    # reads sys.argv at module scope). odd_rows is import-safe, so the vocabulary
    # can now be shared without that hazard.
    odd = accessors(H)
    g, fnum, spend, swipes = odd.g, odd.fnum, odd.spend, odd.swipes

    elig = [r for r in rows
            if odd.personal(r) and g(r, f"{latest} Elig") == "Yes"]
    responders = [r for r in elig
                  if any(g(r, f"{m} Resp") in RESP_MET for m in mailmonths)]

    nextm = {}
    for m in mailmonths:
        i = smonths.index(m) if m in smonths else -1
        if i >= 0 and i + 1 < len(smonths):
            nextm[m] = smonths[i + 1]
    mature = [m for m in mailmonths if m in nextm]

    # ---- before / after ----
    ba = []
    for m in mature:
        if m not in smonths:
            continue
        idx = smonths.index(m)
        if idx < 3 or idx + 1 >= len(smonths):
            continue
        rs = [r for r in elig if g(r, f"{m} Resp") in RESP_MET]
        if len(rs) < 5:
            continue
        pre, post = smonths[idx - 3:idx], smonths[idx + 1:]
        sb = [statistics.mean([spend(r, x) for x in pre]) for r in rs]
        sa = [statistics.mean([spend(r, x) for x in post]) for r in rs]

        def wins(vals):
            mu = statistics.mean(vals)
            cap = mu + 3 * statistics.pstdev(vals)
            return [min(v, cap) for v in vals]

        ba.append({"m": lbl(m), "n": len(rs),
                   "sb_mean": round(statistics.mean(wins(sb))),
                   "sa_mean": round(statistics.mean(wins(sa))),
                   "sb_med": round(statistics.median(sb)),
                   "sa_med": round(statistics.median(sa))})

    out = {"latest_month": latest, "n_eligible": len(elig),
           "n_responders": len(responders), "before_after": ba}

    if ba:
        out["ba_spend_before"] = round(statistics.mean([e["sb_mean"] for e in ba]))
        out["ba_spend_after"] = round(statistics.mean([e["sa_mean"] for e in ba]))
        out["ba_spend_med_before"] = round(
            statistics.mean([e["sb_med"] for e in ba]))
        out["ba_spend_med_after"] = round(
            statistics.mean([e["sa_med"] for e in ba]))
        out["ba_pct_mean"] = round(
            100 * (out["ba_spend_after"] - out["ba_spend_before"])
            / out["ba_spend_before"], 1)
        out["ba_pct_med"] = round(
            100 * (out["ba_spend_med_after"] - out["ba_spend_med_before"])
            / out["ba_spend_med_before"], 1)
        out["ba_n_mailings"] = len(ba)

    # ---- transaction increase over the ask ----
    incs = []
    for r in responders:
        lm = None
        for m in mature:
            if g(r, f"{m} Resp") in RESP_MET:
                lm = m
        if not lm:
            continue
        goal = OFFER_GOAL.get(g(r, f"{lm} Mail"),
                              RESP_GOAL.get(g(r, f"{lm} Resp"), 5))
        incs.append(swipes(r, nextm[lm]) - goal)
    if incs:
        out["dot_n"] = len(incs)
        out["dot_mean"] = round(statistics.mean(incs), 1)
        out["dot_median"] = round(statistics.median(incs), 1)

    # ---- reach + repeat depth ----
    n_ml = len([m for m in mailmonths
                if any(g(r, f"{m} Resp") in RESP_MET for r in elig)])
    out["reach_total"] = len(responders)
    out["reach_perml"] = round(len(responders) / max(1, n_ml))
    if responders:
        rep = sum(1 for r in responders
                  if sum(1 for m in mailmonths
                         if g(r, f"{m} Resp") in RESP_MET) >= 2)
        out["depth_repeat_n"] = rep
        out["depth_repeat_pct"] = round(100 * rep / len(responders), 1)
    return out


if __name__ == "__main__":
    res = analyse(sys.argv[1])
    json.dump(res, open(sys.argv[2], "w", encoding="utf-8"), indent=1)
    print(f"latest {res['latest_month']} | eligible {res['n_eligible']:,} | "
          f"responders {res['n_responders']:,}")
    if "ba_spend_before" in res:
        print(f"  spend before/after MEAN   ${res['ba_spend_before']:,} -> "
              f"${res['ba_spend_after']:,}  ({res['ba_pct_mean']:+.1f}%)")
        print(f"  spend before/after MEDIAN ${res['ba_spend_med_before']:,} -> "
              f"${res['ba_spend_med_after']:,}  ({res['ba_pct_med']:+.1f}%)")
        print(f"  mailings in the window     {res['ba_n_mailings']}")
    if "dot_mean" in res:
        print(f"  txns over the ask          mean {res['dot_mean']:+.1f} | "
              f"median {res['dot_median']:+.1f}  (n={res['dot_n']:,})")
    print(f"  customers reached          {res['reach_total']:,} "
          f"(~{res['reach_perml']}/mailing)")
    print(f"  repeat responders          {res.get('depth_repeat_pct')}% "
          f"({res.get('depth_repeat_n'):,})")
