#!/usr/bin/env python3
"""
figures.py — record which MEASURE each rendered number came from.

The problem this exists for (Wellworth 1549, 2026-08-28): the Jun 2026 drop's
responder count rendered as 1,077 on the mailing slides and 1,026 on Program
Reach, Depth of Engagement, Ranking and Sustained. One measure, one mailing, two
numbers, one deck. Four slides had filtered a HISTORICAL mailing's responders
through the CURRENT eligibility snapshot and dropped 51 accounts.

Why nothing caught it:

  * The swap gate (`build_ars_gen.py`, MISSES) fails the build when a swap
    string matches nothing — so a STALE template number cannot ship. But here
    both swaps succeeded. They just wrote different values. The gate asks "did
    the swap land?", not "do two landed swaps agree?".
  * `validate_deck.figure_identity_findings` reads the finished deck and INFERS
    that two figures are the same measure from the words around them. Inference
    misfires — personal-vs-business take rate reads as a conflict — so it can
    only emit REVIEW.

The builder does not have to infer. When it writes a number it knows which
measure produced it. Recording that turns an inference into an assertion:

    a measure rendered on N slides shows the same value on all N

which is arithmetic, and can therefore FAIL a build.

Usage — the swap helpers take an optional `measure=`; only measures that appear
on more than one slide need naming:

    from figures import log
    set_exact(S[13], "258", lresp, measure="responders_latest_mailing")
    ...
    log.dump(OUT + ".figures.json")

Nothing here raises on its own: recording is a side channel, and a deck must not
fail to build because its bookkeeping hiccuped. `conflicts()` is what decides.
"""
from __future__ import annotations

import json
import os


def slide_title(slide):
    """First non-empty line of text on the slide, or ''.

    Titles rather than indices: a helper receives a slide object, not a
    presentation, and slides move between phases of the ARS build. A title is
    self-contained and is also what the validator can report back.
    """
    try:
        for sh in slide.shapes:
            if sh.has_text_frame and sh.text_frame.text.strip():
                return sh.text_frame.text.strip().split("\n")[0][:80]
    except Exception:
        pass
    return ""


class FigureLog:
    """Every (measure, rendered value, slide) the builder wrote."""

    def __init__(self):
        self.rows = []

    def record(self, measure, value, slide=None, note=None):
        if not measure:
            return
        self.rows.append({
            "measure": str(measure),
            "value": "" if value is None else str(value).strip(),
            "slide": slide_title(slide) if slide is not None else "",
            "note": note or "",
        })

    def by_measure(self):
        out = {}
        for r in self.rows:
            out.setdefault(r["measure"], []).append(r)
        return out

    def conflicts(self):
        """[(measure, {value: [slides]})] for measures rendering >1 value."""
        bad = []
        for measure, rows in sorted(self.by_measure().items()):
            byval = {}
            for r in rows:
                byval.setdefault(r["value"], []).append(r["slide"])
            if len(byval) > 1:
                bad.append((measure, byval))
        return bad

    def dump(self, path):
        """Write the sidecar. Returns the path, or None if it could not write."""
        try:
            with open(path, "w", encoding="utf-8") as fh:
                json.dump({"figures": self.rows}, fh, indent=1)
            return path
        except OSError:
            return None

    @staticmethod
    def load(path):
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        log = FigureLog()
        log.rows = data.get("figures", [])
        return log

    def __len__(self):
        return len(self.rows)


# The builders are script-style with module globals, so a shared default
# instance keeps the call sites to one extra keyword.
log = FigureLog()


def record(measure, value, slide=None, note=None):
    log.record(measure, value, slide=slide, note=note)


def sidecar_path(deck_path):
    return str(deck_path) + ".figures.json"


def find_sidecar(deck_path):
    """The sidecar for a deck, or None."""
    p = sidecar_path(deck_path)
    return p if os.path.exists(p) else None
