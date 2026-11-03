#!/usr/bin/env python3
"""peers.py — "How you compare": the client against the other clients on the same program.

WHAT A PEER SHOWS (Aaron, 2026-11-03, asked and answered: "Always show the peer's ID"). Live Review is shown to the client.
A peer's CLIENT NUMBER is on the page: each dot's hover says "Client 1234: 61%". Another client's name, logo, CSM or any
other value that identifies one never reaches the page, the model JSON or the Sources drawer. The collectors below read the
other clients' rows (the same rows the performance dashboard reads, `build/peer_data.py`) and HAND OVER ONLY:

    the client's own value,
    the peers' values (a dot each, with that peer's client number in `dot_ids`) and their quartiles, a histogram,
    the count of peers, and the count left out for want of current data.

`tests/test_live_review_peers.py` serialises the model and the page for a synthetic pool and asserts no peer NAME appears
anywhere and that a peer's number appears only in `dot_ids`.

SMALL POOLS. A comparison is stated as unavailable, plainly, when fewer than MIN_PEERS other clients have the program
at all, and a metric is left out (and said to be) when fewer than MIN_PEERS have current data for it.

LIKE PERIODS. Month-based metrics compare the client's latest complete month with the peers' value for the same month;
when fewer than MIN_PEERS peers have it, the comparison falls back to the most recent month the client and enough peers
share, and says so. A peer with no value for the month is not current for the metric and is counted in "left out".

Import-safe.
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BUILD = os.path.abspath(os.path.join(HERE, os.pardir))
if BUILD not in sys.path:
    sys.path.insert(0, BUILD)

import month_complete as MC                                  # noqa: E402
from review_page import blocks as B                          # noqa: E402

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
def compare(t, spec, client_val, peer_vals, peer_ids=None):
    """One metric's comparison dict, or None when it has too few peers. `spec`:
    {"key","label","fmt","higher"} where higher is True (more is better), False (less is better) or None (neither).
    `peer_ids`, when given, is each peer's client number in the order of `peer_vals`; the result carries it as `dot_ids`,
    sorted with `dots`."""
    peers = [float(v) for v in peer_vals if v is not None]
    pairs = sorted(((float(v), str(peer_ids[i]) if peer_ids and peer_ids[i] is not None else None)
                    for i, v in enumerate(peer_vals) if v is not None), key=lambda x: x[0])
    if client_val is None or len(peers) < MIN_PEERS:
        return None
    for v in peers:
        t.see(v)
    for _v, cid in pairs:               # a client number is read from the pack like any other figure the page prints
        if cid and cid.isdigit():
            t.see(int(cid))
    t.see(client_val)
    n = len(peers)
    sv = sorted(peers)
    t.derive(n, "peers with current data for the metric", sv[0])
    q1, med, q3 = (quantile(sv, 0.25), quantile(sv, 0.5), quantile(sv, 0.75))
    for name, val in (("first quartile", q1), ("median", med), ("third quartile", q3)):
        t.derive(val, f"peer {name}", sv[0])
    pr = t.derive(percentile_rank(client_val, peers), "percentile rank among peers", client_val, sv[0])
    higher = spec.get("higher")
    rank = t.derive(rank_among(client_val, peers, True if higher is None else higher), "rank among the client and its peers", client_val)
    total = t.derive(n + 1, "the client and its peers", sv[0])
    kind, diff = relation(client_val, med)
    if diff is not None:
        t.derive(abs(diff), "percent difference from the median", client_val, med)
    edges, counts = histogram(sv)
    for c in counts:
        t.derive(c, "peers in a histogram bin", sv[0])
    for e in edges:
        t.derive(e, "histogram bin edge", sv[0])
    return {"key": spec["key"], "label": spec["label"], "fmt": spec["fmt"], "higher": higher, "client": client_val, "median": med,
            "q1": q1, "q3": q3, "min": sv[0], "max": sv[-1], "dots": sv, "dot_ids": [p[1] for p in pairs] if peer_ids else None, "n": n, "total": total, "rank": rank, "pct": pr,
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


# ----------------------------------------------------------------- the screen
def _fmt(f):
    return {"pct1": lambda v: f"{v:.1f}%", "pct0": lambda v: f"{v:.0f}%", "dec1": lambda v: f"{v:.1f}", "int": lambda v: f"{v:,.0f}"}.get(f, lambda v: f"{v}")


def peers_screen(t, program_label, who, collected, metrics, trend=None, extra_notes=None, pull_dates=None):
    """The 'How you compare' screen for one program.

    collected: {"n_pool": other clients on the program at all, "me": {...}, "peers": [...]}, where `me` and each peer are
               {"point": {key: value}, "series": {key: {month: value}}}. Peer ids are NOT in it.
    metrics:   [{"key","label","fmt","higher","month": True/False}] in the order shown.
    trend:     the series key drawn as client against median over the last complete months, or None.
    """
    n_pool = collected["n_pool"]
    t.derive(n_pool, "other clients on the program", )
    t.derive(MIN_PEERS, "the smallest peer pool shown")
    sources = [{"title": f"{program_label} peer set",
                "text": (f"Peers are all other clients on {program_label} with current data, n = {n_pool}. Figures are read from the same "
                         f"per-client sheets the performance dashboard reads" + (f"; pulled {pull_dates}" if pull_dates else "")
                         + ". Each dot is one other client and its hover gives that client's number; no name, logo or CSM of another client appears on this page.")}]
    if n_pool < MIN_PEERS:
        blk = {"t": "statement", "title": "Not enough peers to compare",
               "text": (f"A comparison needs at least {MIN_PEERS} other clients on {program_label}; this book has {n_pool}. "
                        f"Nothing is shown rather than a comparison a reader could trace to one client.")}
        t.derive(MIN_PEERS, "the smallest peer pool shown")
        return B.screen("peers", "How you compare", f"{program_label} · How you compare",
                        f"{program_label} is not compared with peers here: too few other clients have it.", [blk], sources, [])
    me, peers = collected["me"], collected["peers"]
    options, left, notes, first = [], [], list(extra_notes or []), None
    for spec in metrics:
        key = spec["key"]
        if spec.get("month"):
            al = align_month(me["series"].get(key) or {}, [p["series"].get(key) or {} for p in peers])
            if not al:
                left.append(f"{spec['label']}: fewer than {MIN_PEERS} peers have current data")
                continue
            month, cv, pv, fell, out = al
            pid = [p.get("id") for p in peers if (p["series"].get(key) or {}).get(month) is not None]   # same order as pv
        else:
            cv = me["point"].get(key)
            pv = [p["point"].get(key) for p in peers]
            pid = [p.get("id") for p, v in zip(peers, pv) if v is not None]
            pv = [v for v in pv if v is not None]
            month, fell, out = None, False, len(peers) - len(pv)
        c = compare(t, spec, cv, pv, pid)
        if c is None:
            left.append(f"{spec['label']}: fewer than {MIN_PEERS} peers have current data")
            continue
        f = _fmt(spec["fmt"])
        mlabel = MC.label(month) if month else None
        sentence = (f"{spec['label']}{' in ' + mlabel if mlabel else ''}: {f(c['client'])}, {rank_phrase(c, who)}; "
                    f"{relation_phrase(c, f)}.")
        if fell:
            notes.append(f"{spec['label']}: the client's latest month has too few peers with data, so this compares {mlabel}, the most recent month enough peers share.")
        if out:
            notes.append(f"{spec['label']}: {int(t.derive(out, 'peers left out for want of current data', c['dots'][0]))} other clients had no current data for it and are not in n.")
        blocks = [{"t": "peerstrip", "id": f"strip-{key}", "title": spec["label"], "fmt": spec["fmt"], "sentence": sentence, "month": mlabel,
                   "client": c["client"], "median": c["median"], "q1": c["q1"], "q3": c["q3"], "min": c["min"], "max": c["max"],
                   "dots": c["dots"], "dot_ids": c["dot_ids"], "n": c["n"], "higher": c["higher"]}]
        if trend and trend == key:
            months, cser, mser = _trend(t, me, peers, key)
            if months:
                blocks.append(B.line(f"trend-{key}", f"{spec['label']}: the client against the peer median", months,
                                     [{"name": "This client", "values": cser, "color": "orange"}, {"name": "Peer median", "values": mser, "color": "navy"}], spec["fmt"],
                                     sub="Complete months only; a month with fewer than five peers is left out."))
        e = ["%s to %s" % (f(c["edges"][i]), f(c["edges"][i + 1])) for i in range(len(c["counts"]))] if len(c["edges"]) > 2 else [f(c["edges"][0])]
        blocks.append(B.bars(f"hist-{key}", f"How {int(c['n'])} peers are spread", e, [{"name": "Peers", "values": c["counts"], "color": "steel"}], "int",
                             sub="Each peer is counted once; none is named."))
        options.append({"key": key, "label": spec["label"], "blocks": blocks, "_sentence": sentence})
        first = first or (spec, c, sentence)
    if not options:
        blk = {"t": "statement", "title": "Not enough peers with current data",
               "text": "; ".join(left) + f". Each metric needs at least {MIN_PEERS} other clients with current data."}
        t.derive(MIN_PEERS, "the smallest peer pool shown")
        return B.screen("peers", "How you compare", f"{program_label} · How you compare",
                        f"{program_label} is not compared with peers here: too few peers have current data.", [blk], sources, [])
    for o in options:
        o["blocks"].insert(0, {"t": "statement", "title": None, "text": o.pop("_sentence"), "lead": True})
    blocks = [B.variants("peer-metric", "Measure", options)] if len(options) > 1 else options[0]["blocks"]
    if left:
        notes.append("Left out: " + "; ".join(left) + ".")
    spec, c, sentence = first
    return B.screen("peers", "How you compare", f"{program_label} · How you compare", sentence, blocks, sources,
                    [f"Peers are all other clients on {program_label} with current data, n = {int(c['n'])}."] + notes)


def _trend(t, me, peers, key, last=12):
    ms = sorted((m for m, v in (me["series"].get(key) or {}).items() if v is not None),
                key=lambda x: MC.month_start(x) or MC.month_start("Jan 2000"))[-last:]
    cser, mser, months = [], [], []
    for m in ms:
        vals = [p["series"][key][m] for p in peers if (p["series"].get(key) or {}).get(m) is not None]
        if len(vals) < MIN_PEERS:
            continue
        for v in vals:
            t.see(v)
        t.see(me["series"][key][m])
        months.append(m)
        cser.append(me["series"][key][m])
        mser.append(t.derive(quantile(vals, 0.5), "peer median in the month", vals[0]))
    return months, cser, mser
