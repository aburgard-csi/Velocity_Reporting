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

import peer_compare as PC                                    # noqa: E402

# The arithmetic, the sentences and the period alignment live in build/peer_compare.py, shared with the Executive Review
# decks' peer slide (Aaron, 2026-11-03); these names stay here for the page's callers and its tests.
MIN_PEERS, BAND = PC.MIN_PEERS, PC.BAND
ordinal, quantile, percentile_rank, rank_among = PC.ordinal, PC.quantile, PC.percentile_rank, PC.rank_among
relation, histogram, align_month = PC.relation, PC.histogram, PC.align_month
rank_phrase, relation_phrase = PC.rank_phrase, PC.relation_phrase
_fmt = PC.formatter


# ----------------------------------------------------------------- the tracer's view of a comparison
def register(t, spec, c):
    """Put every figure of a finished comparison `c` in the page's ledger, in the order the page derives them."""
    sv = c["dots"]
    for v in sv:
        t.see(v)
    for cid in (c["dot_ids"] or []):      # a client number is read from the pack like any other figure the page prints
        if cid and str(cid).isdigit():
            t.see(int(cid))
    t.see(c["client"])
    t.derive(c["n"], "peers with current data for the metric", sv[0])
    for name, val in (("first quartile", c["q1"]), ("median", c["median"]), ("third quartile", c["q3"])):
        t.derive(val, f"peer {name}", sv[0])
    t.derive(c["pct"], "percentile rank among peers", c["client"], sv[0])
    t.derive(c["rank"], "rank among the client and its peers", c["client"])
    t.derive(c["total"], "the client and its peers", sv[0])
    if c["diff"] is not None:
        t.derive(abs(c["diff"]), "percent difference from the median", c["client"], c["median"])
    for n in c["counts"]:
        t.derive(n, "peers in a histogram bin", sv[0])
    for e in c["edges"]:
        t.derive(e, "histogram bin edge", sv[0])


def compare(t, spec, client_val, peer_vals, peer_ids=None):
    """One metric's comparison dict (see peer_compare.compare_values), or None when it has too few peers; the figures it
    carries are put in the tracer's ledger."""
    c = PC.compare_values(spec, client_val, peer_vals, peer_ids)
    if c is not None:
        register(t, spec, c)
    return c


# ----------------------------------------------------------------- the screen
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
    ev = PC.evaluate(collected, metrics, who)
    if n_pool < MIN_PEERS:
        blk = {"t": "statement", "title": "Not enough peers to compare", "text": ev["unavailable"]}
        t.derive(MIN_PEERS, "the smallest peer pool shown")
        return B.screen("peers", "How you compare", f"{program_label} · How you compare",
                        f"{program_label} is not compared with peers here: too few other clients have it.", [blk], sources, [])
    me, peers = collected["me"], collected["peers"]
    options, notes, first = [], list(extra_notes or []), None
    for item in ev["items"]:
        spec, c, sentence, mlabel = item["spec"], item["c"], item["sentence"], item["month"]
        key = spec["key"]
        register(t, spec, c)
        f = _fmt(spec["fmt"])
        notes.extend(item["notes"])
        if item["out"]:
            t.derive(item["out"], "peers left out for want of current data", c["dots"][0])
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
        options.append({"key": key, "label": spec["label"], "blocks": blocks})
        first = first or (spec, c, sentence)
    if not options:
        blk = {"t": "statement", "title": "Not enough peers with current data", "text": ev["unavailable"]}
        t.derive(MIN_PEERS, "the smallest peer pool shown")
        return B.screen("peers", "How you compare", f"{program_label} · How you compare",
                        f"{program_label} is not compared with peers here: too few peers have current data.", [blk], sources, [])
    blocks = [B.variants("peer-metric", "Measure", options)] if len(options) > 1 else options[0]["blocks"]
    if ev["left"]:
        notes.append("Left out: " + "; ".join(ev["left"]) + ".")
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
