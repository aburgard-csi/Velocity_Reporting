#!/usr/bin/env python3
"""
sustained_split.py — sustained responder activity by mailing, in total and by offer segment.

ONE definition of "sustained", used by both ARS slides that report it:

  * Sustained Respondent Activity by Mailing (every deck) reads the TOTAL row, and
  * Sustained Activity: Non-User vs Threshold (the opt-in test slide,
    sustained_split_slide.py) reads the NU and TH rows.

Both used to be possible only by copying metrics_gen's loop; computing them in one pass from
one function means the split always reconciles with the total (NU + TH + other == total, in
responders AND in those sustained).

The definition (Aaron, 2026-08-27 / 08-28; unchanged here):
  * a mailing's responders are personal accounts whose '<Mon> Resp' reached a goal tier;
  * the response is measured in the month AFTER the mailing, so attrition can only show from
    mailing + 2 onward: the post window is every COMPLETE activity month from mailing + 2;
  * a responder is sustained when their average monthly swipes over that window are at or
    above the ask attached to THIS mailing ('<Mon> Mail' offer, else the goal implied by
    '<Mon> Resp');
  * a mailing with no post month yet reads 100% by definition (post window 0).

The segment is the OFFER the responder was sent for that mailing — '<Mon> Mail' is 'NU' for a
Non-User (no prior debit usage, asked to start) or 'TH-10'..'TH-25' for a Threshold offer
(an existing user asked to reach a swipe count). The same reading as the Mailing Response
Summary's NU / Threshold rates. When the offer cell is blank the result says which: 'NU 5+'
is a Non-User response, 'TH-nn' a Threshold one. Anything else is 'OTHER' and is counted in
the total but in neither segment, so it is never silently assigned.

Import-safe: no I/O, no plotting, no module-level work.
"""

SEGMENTS = ("NU", "TH")
SEGMENT_NAMES = {"NU": "Non-User", "TH": "Threshold"}
SMALL_N = 30            # a segment with fewer responders than this is flagged, not hidden


def segment(offer, resp=""):
    """'NU', 'TH' or 'OTHER' for one responder at one mailing."""
    o = (offer or "").strip().upper()
    if o == "NU" or o.startswith("NU "):
        return "NU"
    if o.startswith("TH"):
        return "TH"
    if o:
        return "OTHER"          # an offer code we do not know — never guessed from the result
    r = (resp or "").strip().upper()
    if r.startswith("NU"):
        return "NU"
    if r.startswith("TH"):
        return "TH"
    return "OTHER"


def post_window(m, smonths, act_months):
    """The complete activity months from mailing + 2 onward (mailing + 1 is the response
    month, where every responder met the ask by definition)."""
    if m not in smonths:
        return []
    act = set(act_months)
    return [x for x in smonths[smonths.index(m) + 2:] if x in act]


def _cell(rows, post, swipes, ask, m):
    n = len(rows)
    if not n:
        return {"n": 0, "ok": 0, "pct": None}
    if not post:
        return {"n": n, "ok": n, "pct": 100.0}
    ok = sum(1 for r in rows if sum(swipes(r, x) for x in post) / len(post) >= ask(r, m))
    return {"n": n, "ok": ok, "pct": round(100 * ok / n, 1)}


def by_mailing(resp_pop, mailings, smonths, act_months, g, swipes, ask, resp_met,
               label=str):
    """One row per mailing that has responders, oldest first:

        {"m": label(m), "token": m, "post": <months in the post window>,
         "all": cell, "NU": cell, "TH": cell, "OTHER": cell}

    where cell = {"n": responders, "ok": sustained, "pct": share or None when n == 0}.
    """
    out = []
    for m in mailings:
        rs = [r for r in resp_pop if g(r, f"{m} Resp") in resp_met]
        if not rs:
            continue
        post = post_window(m, smonths, act_months)
        groups = {"NU": [], "TH": [], "OTHER": []}
        for r in rs:
            groups[segment(g(r, f"{m} Mail"), g(r, f"{m} Resp"))].append(r)
        row = {"m": label(m), "token": m, "post": len(post),
               "all": _cell(rs, post, swipes, ask, m)}
        for k, v in groups.items():
            row[k] = _cell(v, post, swipes, ask, m)
        out.append(row)
    return out


def total_rows(split):
    """The rows the existing slide has always read: [label, responders, pct, post]."""
    return [[e["m"], e["all"]["n"], e["all"]["pct"], e["post"]] for e in split]


def pooled(split, seg):
    """Responders and sustained for one segment, pooled over the mailings that HAVE a post
    window (a mailing with none is 100% by definition and says nothing about attrition)."""
    n = sum(e[seg]["n"] for e in split if e["post"])
    ok = sum(e[seg]["ok"] for e in split if e["post"])
    return {"n": n, "ok": ok, "pct": round(100 * ok / n, 1) if n else None}
