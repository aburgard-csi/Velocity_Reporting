#!/usr/bin/env python3
"""peer_compare.py — "How you compare": the arithmetic and the sentences, defined ONCE.

Two things show a client against the other clients on the same program: Live Review's "How you compare" screens
(`review_page/peers.py`) and the peer slide each Executive Review deck carries (`peer_slide.py`). They must agree, so both
call this module, the way the monthly deck and the Summit one-pager both call `before_after.py` (Aaron, 2026-11-03: "I'd
like to see our LR peer comparisons in the Sheila decks"). Nothing here knows about a page, a tracer or a slide.

    quantile, percentile_rank, rank_among, relation, histogram     the arithmetic
    align_month(me, peers)                                          like periods for month-keyed series
    compare_values(spec, client, peer_values, peer_ids)             one metric's comparison, or None under MIN_PEERS
    sentence(spec, c, who, month_label)                             the plain sentence a strip carries
    evaluate(collected, metrics, who)                               every metric of a program, with the notes
    for_deck(program, client, ...)                                  evaluate() on the program's own peer pool

WHAT IS IDENTIFIED. A comparison here carries the peers' VALUES and, for Live Review's hover, each peer's client number in
`dot_ids` (Aaron, 2026-11-03). A DECK DOES NOT: a printed deck is forwarded, so `for_deck` strips `dot_ids` and every
other trace of who a peer is before anything reaches a slide, and `tests/test_peer_slide.py` checks the finished file.

SMALL POOLS. A metric with fewer than MIN_PEERS other clients having current data is left out and said to be.

LIKE PERIODS. Month-based metrics compare the client's latest complete month with the peers' value for the same month;
when fewer than MIN_PEERS peers have it, the comparison falls back to the most recent month the client and enough peers
share, and says so.

Import-safe: nothing is read until `for_deck` is called.
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import month_complete as MC                                  # noqa: E402

MIN_PEERS = 5
BAND = 2.0               # +/-2%: "almost flat" (CLAUDE.md)


# ----------------------------------------------------------------- the arithmetic
def ordinal(n):
    n = int(n)
    if 10 <= n % 100 <= 20:
        suf = "th"
    else:
        suf = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suf}"


def quantile(vals, q):
    """Linear interpolation between order statistics (the usual 'type 7' quantile) of a non-empty list."""
    v = sorted(vals)
    if not v:
        raise ValueError("no values")
    if len(v) == 1:
        return float(v[0])
    pos = q * (len(v) - 1)
    lo, hi = int(math.floor(pos)), int(math.ceil(pos))
    return float(v[lo] + (v[hi] - v[lo]) * (pos - lo))


def percentile_rank(client, peers):
    """Share of peers below the client, counting half of any tie: 0 to 100."""
    n = len(peers)
    if not n:
        return None
    below = sum(1 for p in peers if p < client)
    equal = sum(1 for p in peers if p == client)
    return 100.0 * (below + 0.5 * equal) / n


def rank_among(client, peers, higher_is_better=True):
    """1-based rank of the client among itself and its peers (1 = best); ties share the better rank."""
    if higher_is_better:
        return 1 + sum(1 for p in peers if p > client)
    return 1 + sum(1 for p in peers if p < client)


def relation(client, median):
    """('flat'|'above'|'below', percent difference from the median). Within +/-2% is almost flat."""
    if median in (None, 0):
        return ("flat", None)
    d = 100.0 * (client - median) / abs(median)
    if abs(d) <= BAND:
        return ("flat", d)
    return ("above" if d > 0 else "below", d)


def histogram(vals, bins=8):
    lo, hi = min(vals), max(vals)
    if hi == lo:
        return [lo, hi], [len(vals)]
    w = (hi - lo) / bins
    edges = [lo + i * w for i in range(bins + 1)]
    counts = [0] * bins
    for v in vals:
        counts[min(bins - 1, int((v - lo) / w))] += 1
    return edges, counts


# ----------------------------------------------------------------- the comparison of one metric
def compare_values(spec, client_val, peer_vals, peer_ids=None):
    """One metric's comparison dict, or None when it has too few peers. `spec`:
    {"key","label","fmt","higher"} where higher is True (more is better), False (less is better) or None (neither).
    `peer_ids`, when given, is each peer's client number in the order of `peer_vals`; the result carries it as `dot_ids`,
    sorted with `dots`."""
    peers = [float(v) for v in peer_vals if v is not None]
    pairs = sorted(((float(v), str(peer_ids[i]) if peer_ids and peer_ids[i] is not None else None)
                    for i, v in enumerate(peer_vals) if v is not None), key=lambda x: x[0])
    if client_val is None or len(peers) < MIN_PEERS:
        return None
    n = len(peers)
    sv = sorted(peers)
    q1, med, q3 = (quantile(sv, 0.25), quantile(sv, 0.5), quantile(sv, 0.75))
    higher = spec.get("higher")
    rank = rank_among(client_val, peers, True if higher is None else higher)
    kind, diff = relation(client_val, med)
    edges, counts = histogram(sv)
    return {"key": spec["key"], "label": spec["label"], "fmt": spec["fmt"], "higher": higher, "client": client_val, "median": med,
            "q1": q1, "q3": q3, "min": sv[0], "max": sv[-1], "dots": sv, "dot_ids": [p[1] for p in pairs] if peer_ids else None,
            "n": n, "total": n + 1, "rank": rank, "pct": percentile_rank(client_val, peers),
            "relation": kind, "diff": diff, "edges": edges, "counts": counts}


def rank_phrase(c, who):
    """'3rd of 14 ICS clients' (the client counts in the 14)."""
    return f"{ordinal(c['rank'])} of {int(c['total'])} {who} clients"


def relation_phrase(c, fmt):
    med = fmt(c["median"])
    if c["relation"] == "flat":
        return f"almost flat against the peer median ({med})"
    pct = f"{abs(c['diff']):.1f}%"
    return f"{pct} {'above' if c['relation'] == 'above' else 'below'} the peer median ({med})"


def formatter(f):
    return {"pct1": lambda v: f"{v:.1f}%", "pct0": lambda v: f"{v:.0f}%", "dec1": lambda v: f"{v:.1f}", "int": lambda v: f"{v:,.0f}",
            "usd": lambda v: f"${v:,.0f}", "usd2": lambda v: f"${v:,.2f}"}.get(f, lambda v: f"{v}")


def sentence(spec, c, who, month_label=None):
    """The one plain sentence a strip carries."""
    f = formatter(spec["fmt"])
    return (f"{spec['label']}{' in ' + month_label if month_label else ''}: {f(c['client'])}, {rank_phrase(c, who)}; "
            f"{relation_phrase(c, f)}.")


# ----------------------------------------------------------------- period alignment
def align_month(me_series, peer_series, min_peers=MIN_PEERS):
    """(month, client value, [peer values], fell_back, left_out) for month-keyed series.

    The client's latest month is the comparison month. When fewer than `min_peers` peers have a value for it, the
    comparison moves back to the most recent month the client and at least `min_peers` peers share. `peer_series` is a
    list of {month: value} dicts (no ids; the caller keeps them aligned). Returns None when no month qualifies.
    """
    months = sorted((m for m, v in me_series.items() if v is not None), key=lambda x: MC.month_start(x) or MC.month_start("Jan 2000"))
    if not months:
        return None
    for k, m in enumerate(reversed(months)):
        vals = [s[m] for s in peer_series if s.get(m) is not None]
        if len(vals) >= min_peers:
            return m, me_series[m], vals, k > 0, len(peer_series) - len(vals)
    return None


# ----------------------------------------------------------------- every metric of a program
def evaluate(collected, metrics, who):
    """The comparison of every metric in `metrics` for one program.

    collected: {"n_pool": other clients on the program at all, "me": {...}, "peers": [...]}, where `me` and each peer are
               {"point": {key: value}, "series": {key: {month: value}}} (a peer may carry "id").
    Returns {"n_pool", "items": [{"spec","c","month","fell","out","sentence"}], "left": [...], "notes": [...],
             "unavailable": text or None}. `unavailable` is set when the program has fewer than MIN_PEERS other clients at
    all or no metric reached MIN_PEERS."""
    n_pool = collected["n_pool"]
    if n_pool < MIN_PEERS:
        return {"n_pool": n_pool, "items": [], "left": [], "notes": [],
                "unavailable": (f"A comparison needs at least {MIN_PEERS} other clients on {who}; this book has {n_pool}. "
                                f"Nothing is shown rather than a comparison a reader could trace to one client.")}
    me, peers = collected["me"], collected["peers"]
    items, left, notes = [], [], []
    for spec in metrics:
        key = spec["key"]
        if spec.get("month"):
            if not any(v is not None for v in (me["series"].get(key) or {}).values()):
                left.append(f"{spec['label']}: this client has no current figure for it")
                continue
            al = align_month(me["series"].get(key) or {}, [p["series"].get(key) or {} for p in peers])
            if not al:
                left.append(f"{spec['label']}: fewer than {MIN_PEERS} peers have current data")
                continue
            month, cv, pv, fell, out = al
            pid = [p.get("id") for p in peers if (p["series"].get(key) or {}).get(month) is not None]   # same order as pv
        else:
            cv = me["point"].get(key)
            if cv is None:
                left.append(f"{spec['label']}: this client has no current figure for it")
                continue
            pv = [p["point"].get(key) for p in peers]
            pid = [p.get("id") for p, v in zip(peers, pv) if v is not None]
            pv = [v for v in pv if v is not None]
            month, fell, out = None, False, len(peers) - len(pv)
        c = compare_values(spec, cv, pv, pid)
        if c is None:
            left.append(f"{spec['label']}: fewer than {MIN_PEERS} peers have current data")
            continue
        mlabel = MC.label(month) if month else None
        item = {"spec": spec, "c": c, "month": mlabel, "fell": fell, "out": out, "sentence": sentence(spec, c, who, mlabel), "notes": []}
        if fell:
            item["notes"].append(f"{spec['label']}: the client's latest month has too few peers with data, so this compares {mlabel}, the most recent month enough peers share.")
        if out:
            item["notes"].append(f"{spec['label']}: {int(out)} other clients had no current data for it and are not in n.")
        items.append(item)
    unavailable = None
    if not items:
        unavailable = "; ".join(left) + f". Each metric needs at least {MIN_PEERS} other clients with current data."
    return {"n_pool": n_pool, "items": items, "left": left, "notes": notes, "unavailable": unavailable}


def trend_series(me, peers, key, last=12):
    """(months, client values, peer medians) over the client's last `last` months that at least MIN_PEERS peers also have."""
    ms = sorted((m for m, v in (me["series"].get(key) or {}).items() if v is not None),
                key=lambda x: MC.month_start(x) or MC.month_start("Jan 2000"))[-last:]
    cser, mser, months = [], [], []
    for m in ms:
        vals = [p["series"][key][m] for p in peers if (p["series"].get(key) or {}).get(m) is not None]
        if len(vals) < MIN_PEERS:
            continue
        months.append(m)
        cser.append(me["series"][key][m])
        mser.append(quantile(vals, 0.5))
    return months, cser, mser


# ----------------------------------------------------------------- what a deck gets
def anonymous(item):
    """A comparison item with every trace of who a peer is taken out: values only, no client numbers."""
    c = dict(item["c"])
    c["dot_ids"] = None
    return dict(item, c=c)


def for_deck(program, client, period=None, root=None, who=None, keys=None):
    """The deck's comparison for one program and client, from the SAME collectors and metric lists Live Review uses.

    program: "ARS" | "ICS" | "MRPC" | "CP" (also "REMS"); `keys` limits and orders the metrics to those the slide shows.
    Returns {"program","who","n_pool","pull","items","left","notes","unavailable"} with every peer anonymous."""
    from review_page import peer_pool as PP
    collect, metrics, label = PP.PROGRAMS[program]
    ctx = PP.PeerCtx(client=str(client), period=period, root=root)
    coll = collect(ctx)
    if keys:
        by = {m["key"]: m for m in metrics}
        metrics = [by[k] for k in keys if k in by]
    ev = evaluate(coll, metrics, who or label)
    ev["items"] = [anonymous(i) for i in ev["items"]]
    ev.update(program=program, who=who or label, pull=coll.get("pull"))
    return ev
