#!/usr/bin/env python3
"""
responder_activity.py — responder before/after activity from the raw ODDD.

Feeds the Executive Summit one-pager. The before/after measure is NOT computed
here: it is `before_after.compute`, the same function the monthly deck's
metrics_gen calls, so the one-pager and the client's own deck cannot disagree
(Aaron, 2026-09-08 — "the Summits and the regular delivery decks should use the
same logic").

They did disagree. This file's docstring used to claim it mirrored metrics_gen
while differing in four ways at once — the eligible-at-snapshot cohort, an
after window running to the end of the extract, a separate winsorizing cap per
window, and a headline that averaged the per-mailing means. `before_after.py`
records what each of those cost. What remains here:

  * eligible cohort = personal accounts with <latest month> Elig == Yes
    (the count of who CAN be mailed — a present-tense question, so the
    present-tense filter is right here and wrong on a historical cohort)
  * responders / reach / depth = every personal account that met a goal, the
    same historical cohort the deck's Reach and Depth slides count
  * transaction increase over the ask = swipes in the month after the latest
    met-goal offer, minus that offer's goal

Reads the extract itself rather than importing metrics_gen because importing
metrics_gen RUNS it (it reads sys.argv at module scope) and it picks the first
.csv in the zip — which on several clients is the raw transaction file, not the
ODD extract. `before_after` and `odd_rows` are import-safe by design.

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

import before_after
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
    # MTD is the NSF/OD item count. It was not kept, so before_after's NSF
    # figures would have come back 0 for the one-pager while the deck reported
    # them — the same measure, two answers, which is the whole point of sharing.
    fam = re.compile(r"^[A-Z][a-z]{2}\d{2} (Sig #|PIN #|Sig \$|PIN \$|MTD|Mail|Resp)$")
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

    # Two different cohorts, deliberately. `elig` answers "how many can we mail",
    # which is a question about NOW. `responders` answers "who has ever responded",
    # which is history — filtering that through today's eligibility silently drops
    # everyone who responded and has since closed, and made the one-pager count 51
    # fewer responders than the deck for the same Wellworth mailing.
    personal_pop = [r for r in rows if odd.personal(r)]
    elig = [r for r in personal_pop if g(r, f"{latest} Elig") == "Yes"]
    responders = [r for r in personal_pop
                  if any(g(r, f"{m} Resp") in RESP_MET for m in mailmonths)]

    nextm = {}
    for m in mailmonths:
        i = smonths.index(m) if m in smonths else -1
        if i >= 0 and i + 1 < len(smonths):
            nextm[m] = smonths[i + 1]
    mature = [m for m in mailmonths if m in nextm]

    # ---- before / after: the deck's function, not a second copy of it ----
    out = {"latest_month": latest, "n_eligible": len(elig),
           "n_responders": len(responders)}
    out.update(before_after.compute(rows, odd, smonths, mature))
    out["ba_pct_mean"] = before_after.pct_change(out["ba_spend_before"],
                                                 out["ba_spend_after"])
    out["ba_pct_med"] = before_after.pct_change(out["ba_spend_med_before"],
                                                out["ba_spend_med_after"])

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
                if any(g(r, f"{m} Resp") in RESP_MET for r in personal_pop)])
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
