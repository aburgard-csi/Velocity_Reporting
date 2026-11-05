"""
selection.py — which chapters and slides of the Transaction Intelligence cut go in the deck.

`ti/slides.json` lists every chapter and every slide by its fixed title (the topic the cut records
for it, never the data-driven headline), each "keep" or "toss". A tossed chapter loses its divider
and agenda row; a tossed slide is left out of the deck altogether, with no stated page, because
leaving it out was a decision, not missing data. A slide whose title is not listed is kept. A key may
carry `*` for slides named per offer ("Mailer * summary"). The file starts with every entry "keep";
what survives a review is decided there, in a reviewed change, so the decks only ever change by a
commit (James and Aaron, 2026-10-26: "an easy way to include/toss slides, especially those that
conflict").

This file decides for every client. A slide a chapter DECLINES for one client (its figures are not
in that client's files) is a different thing: build_ti_gen hides it from that client's deck and
lists it in the build log and the pack's `hidden_declined` (2026-10-30), whatever this file says.

`TI_SLIDES` points at another file (the tests use it).
"""
import fnmatch
import json
import os
from pathlib import Path

DEFAULT = Path(__file__).resolve().parent / "slides.json"
_cache = {}


def load(path=None):
    """{"chapters": {title: state}, "slides": {title: state}}; states are "keep" or "toss"."""
    p = Path(path or os.environ.get("TI_SLIDES") or DEFAULT)
    key = (str(p), p.stat().st_mtime_ns if p.exists() else None)
    if key not in _cache:
        data = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
        out = {"chapters": dict(data.get("chapters") or {}), "slides": dict(data.get("slides") or {})}
        for part in out.values():
            bad = {k: v for k, v in part.items() if v not in ("keep", "toss")}
            if bad:
                raise SystemExit(f"{p}: every entry is \"keep\" or \"toss\"; not {bad}")
        _cache.clear()
        _cache[key] = out
    return _cache[key]


def _state(part, title):
    if title in part:
        return part[title]
    for pattern, state in part.items():
        if "*" in pattern and fnmatch.fnmatchcase(title, pattern):
            return state
    return "keep"


def chapter_kept(title, path=None):
    return _state(load(path)["chapters"], title) != "toss"


def slide_kept(title, path=None):
    return _state(load(path)["slides"], title) != "toss"
