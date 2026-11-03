#!/usr/bin/env python3
"""common.py — the context a program module builds with, and the complete-months rule on a series.

`usable_series` is the page's one use of `month_complete` (CLAUDE.md, "Comparisons use complete
months only"): trailing months through `month_complete.assess` (the calendar and the activity rule),
and a collapse in the MIDDLE of a series (Marine FCU's Aug 2026 NSF/OD, 390 items against about
19,000 either side, which stopped being a trailing month when September loaded) through
`month_complete.usable_months` when that module has it, else through the same thresholds here. A month
left out is returned as a sentence; the page states it and never zeroes it.

Import-safe.
"""
import datetime
import statistics
from dataclasses import dataclass, field
from pathlib import Path

import month_complete as MC
from review_page.trace import Tracer


@dataclass
class Ctx:
    client: str
    period: str                       # yyyy.mm
    root: Path = None                 # Build Artifacts folder (None -> rpe_env.build_artifacts())
    tracer: Tracer = field(default_factory=Tracer)

    @property
    def month_label(self):
        y, m = self.period.split(".")
        return f"{MC._MON[int(m) - 1]} {y}"

    @property
    def month_long(self):
        y, m = self.period.split(".")
        return datetime.date(int(y), int(m), 1).strftime("%B %Y")


def parse_date(s):
    try:
        return datetime.date.fromisoformat(str(s)[:10])
    except ValueError:
        return None


def interior_gaps(values, min_volume=MC.MIN_VOLUME):
    """Indexes of months that collapsed in the middle of a series and then recovered.

    Below half the median of the (up to six) usable months before it, a baseline median of at
    least `min_volume`, at most two such months in a row, and the next month back above half its own
    baseline. A fall that holds is a real change and is not a gap.
    """
    n = len(values)
    gaps = set()
    i = 0
    while i < n:
        v = values[i]
        base = [x for j, x in enumerate(values[max(0, i - MC.BASELINE_MONTHS):i], max(0, i - MC.BASELINE_MONTHS))
                if x is not None and j not in gaps]
        if v is not None and len(base) >= MC.MIN_BASELINE:
            med = statistics.median(base)
            if med >= min_volume and med > 0 and v < MC.PARTIAL_SHARE * med:
                run = [i]
                k = i + 1
                while k < n and len(run) < MC.MAX_TRAILING + 1 and values[k] is not None and values[k] < MC.PARTIAL_SHARE * med:
                    run.append(k)
                    k += 1
                recovered = k < n and values[k] is not None and values[k] >= MC.PARTIAL_SHARE * med
                if recovered and len(run) <= MC.MAX_TRAILING:
                    gaps.update(run)
                    i = k
                    continue
        i += 1
    return sorted(gaps)


def usable_series(tokens, values, as_of=None, measure="", min_volume=MC.MIN_VOLUME):
    """(keep, sentences): `keep` is a list of booleans, one per month, True when the month is usable.

    Trailing months go through month_complete.assess; interior collapses through
    month_complete.usable_months when it exists, else interior_gaps.
    """
    tokens = list(tokens)
    n = len(tokens)
    res = MC.assess(tokens, values, as_of=as_of, measure=measure, min_volume=min_volume)
    keep = [i < res["complete"] for i in range(n)]
    left = [dict(e) for e in res["excluded"]]
    usable_months = getattr(MC, "usable_months", None)
    if usable_months is not None:
        try:
            ok = set(map(str, usable_months(tokens, res)))
            keep = [keep[i] and str(tokens[i]) in ok for i in range(n)]
        except Exception:
            usable_months = None
    if usable_months is None:
        head = [values[i] for i in range(res["complete"])]
        for g in interior_gaps(head, min_volume):
            keep[g] = False
            base = [x for x in head[max(0, g - MC.BASELINE_MONTHS):g] if x is not None]
            left.append({"month": str(tokens[g]), "value": values[g], "measure": measure,
                         "baseline": statistics.median(base) if base else None, "reason": "activity"})
    sentences = []
    for e in left:
        e.setdefault("measure", measure)
        sentences.append(e)
    return keep, sentences


def left_out_text(excluded, what):
    """One sentence for months left out of a series (month_complete.excluded_sentence's wording)."""
    if not excluded:
        return ""
    months = sorted({MC.label(e["month"]) for e in excluded}, key=lambda s: MC.month_start(s))
    e0 = excluded[0]
    if e0.get("reason") == "pulled":
        return f"{', '.join(months)} left out: the data was pulled before the month ended."
    return (f"{', '.join(months)} left out of {what} as incomplete in this extract "
            f"(its total is under half the usual for the months around it).")
